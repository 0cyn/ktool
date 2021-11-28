#
#  ktool | ktool
#  dyld.py
#
#  This file includes a lot of utilities, classes, and abstractions
#  designed for replicating certain functionality within dyld.
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2021.
#
import math
from collections import namedtuple
from enum import Enum

from kmacho import (
    MH_FLAGS,
    MH_FILETYPE,
    LOAD_COMMAND,
    BINDING_OPCODE,
    LOAD_COMMAND_MAP
)
from kmacho.structs import *
from kmacho.base import Constructable
from .macho import _VirtualMemoryMap, Segment
from .util import log, macho_is_malformed
from .exceptions import *


class Dyld:
    """
    This is a static class containing several methods for, essentially, recreating the functionality of Dyld for our
    own purposes.

    It isn't meant to be a faithful recreation of dyld so to speak, it just does things dyld also does, kinda.

    """

    @classmethod
    def load(cls, macho_slice, load_symtab=True, load_imports=True, load_exports=True):
        """
        Take a slice of a macho file and process it using the dyld functions

        :param load_binding: Load Binding Info?
        :param load_symtab: Load Symbol Table?
        :param macho_slice: Slice to load. If your image is not fat, that'll be MachOFile.slices[0]
        :type macho_slice: Slice
        :return: Processed image object
        :rtype: Image
        """
        log.info("Loading image")
        image = Image(macho_slice)

        log.info("Processing Load Commands")
        Dyld._parse_load_commands(image, load_symtab, load_imports, load_exports)
        return image

    @classmethod
    def _parse_load_commands(cls, image, load_symtab=True, load_imports=True, load_exports=True):
        # noinspection PyUnusedLocal
        fixups = None
        log.info(f'registered {len(image.macho_header.load_commands)} Load Commands')
        for cmd in image.macho_header.load_commands:
            if isinstance(cmd, segment_command_64):
                log.debug("Loading segment_command_64")
                segment = Segment(image, cmd)

                log.info(f'Loaded Segment {segment.name}')
                image.vm.add_segment(segment)
                image.segments[segment.name] = segment

                log.debug(f'Added {segment.name} to VM Map')

            elif isinstance(cmd, dyld_info_command):
                image.info = cmd
                if load_imports:
                    log.info("Loading Binding Info")
                    image.binding_table = BindingTable(image, cmd.bind_off, cmd.bind_size)
                    image.weak_binding_table = BindingTable(image, cmd.weak_bind_off, cmd.weak_bind_size)
                    image.lazy_binding_table = BindingTable(image, cmd.lazy_bind_off, cmd.lazy_bind_size)
                if load_exports:
                    log.info("Loading Export Trie")
                    image.exports = ExportTrie.from_bytes(image, cmd.export_off, cmd.export_size)

            elif LOAD_COMMAND(cmd.cmd) == LOAD_COMMAND.LC_DYLD_EXPORTS_TRIE:
                log.info("Loading Export Trie")
                image.exports = ExportTrie.from_bytes(image, cmd.dataoff, cmd.datasize)

            elif LOAD_COMMAND(cmd.cmd) == LOAD_COMMAND.LC_DYLD_CHAINED_FIXUPS:
                log.warning("image uses LC_DYLD_CHAINED_FIXUPS; This is not yet supported in ktool, off-image symbol resolution (superclasses, etc) will not work")
                # fixups = ChainedFixups(image, cmd.dataoff, cmd.datasize)
                pass

            elif isinstance(cmd, symtab_command):
                if load_symtab:
                    log.info("Loading Symbol Table")
                    image.symbol_table = SymbolTable(image, cmd)

            elif isinstance(cmd, uuid_command):
                image.uuid = cmd.uuid.to_bytes(16, "little")
                log.info(f'image UUID: {image.uuid}')

            elif isinstance(cmd, sub_client_command):
                string = image.get_cstr_at(cmd.off + cmd.offset)
                image.allowed_clients.append(string)
                log.debug(f'Loaded Subclient "{string}"')

            elif isinstance(cmd, rpath_command):
                string = image.get_cstr_at(cmd.off + cmd.path)
                image.rpath = string
                log.info(f'image Resource Path: {string}')

            elif isinstance(cmd, build_version_command):
                image.platform = PlatformType(cmd.platform)
                image.minos = os_version(x=image.get_int_at(cmd.off + 14, 2), y=image.get_int_at(cmd.off + 13, 1),
                                         z=image.get_int_at(cmd.off + 12, 1))
                image.sdk_version = os_version(x=image.get_int_at(cmd.off + 18, 2),
                                               y=image.get_int_at(cmd.off + 17, 1),
                                               z=image.get_int_at(cmd.off + 16, 1))
                log.info(f'Loaded platform {image.platform.name} | '
                          f'Minimum OS {image.minos.x}.{image.minos.y}'
                          f'.{image.minos.z} | SDK Version {image.sdk_version.x}'
                          f'.{image.sdk_version.y}.{image.sdk_version.z}')

            elif isinstance(cmd, version_min_command):
                # Only override this if it wasn't set by build_version
                if image.platform == PlatformType.UNK:
                    if LOAD_COMMAND(cmd.cmd) == LOAD_COMMAND.VERSION_MIN_MACOSX:
                        image.platform = PlatformType.MACOS
                    elif LOAD_COMMAND(cmd.cmd) == LOAD_COMMAND.VERSION_MIN_IPHONEOS:
                        image.platform = PlatformType.IOS
                    elif LOAD_COMMAND(cmd.cmd) == LOAD_COMMAND.VERSION_MIN_TVOS:
                        image.platform = PlatformType.TVOS
                    elif LOAD_COMMAND(cmd.cmd) == LOAD_COMMAND.VERSION_MIN_WATCHOS:
                        image.platform = PlatformType.WATCHOS

                    image.minos = os_version(x=image.get_int_at(cmd.off + 10, 2),
                                             y=image.get_int_at(cmd.off + 9, 1),
                                             z=image.get_int_at(cmd.off + 8, 1))

            elif isinstance(cmd, dylib_command):
                if cmd.cmd == 0xD:  # local
                    image.dylib = ExternalDylib(image, cmd)
                    log.info(f'Loaded local dylib_command with install_name {image.dylib.install_name}')
                else:
                    external_dylib = ExternalDylib(image, cmd)
                    image.linked.append(external_dylib)
                    log.info(f'Loaded linked dylib_command with install name {external_dylib.install_name}')

        if image.dylib is not None:
            image.name = image.dylib.install_name.split('/')[-1]
        else:
            image.name = ""


class Image:
    """
    This class represents the Mach-O Binary as a whole.

    It's the root object in the massive tree of information we're going to build up about the binary

    This is an abstracted version, other classes will handle the raw struct interaction;
        here, we facilitate that interaction within those classes and generate our abstract representation

    This class on its own does not handle populating its fields.
    The Dyld class set is responsible for loading in and processing the raw values to it.
    """

    def __init__(self, macho_slice):
        """
        Create a MachO image

        :param macho_slice: MachO Slice being processed
        :type macho_slice: MachO Slice
        """
        self.macho_header = ImageHeader.from_bytes(macho_slice=macho_slice)

        self.slice = macho_slice

        self.linked = []
        self.name = ""
        self.segments = {}

        log.debug("Initializing VM Map")
        self.vm = _VirtualMemoryMap(macho_slice)

        self.info = None
        self.dylib = None
        self.uuid = None

        self.platform = PlatformType.UNK

        self.allowed_clients = []

        self.rpath = None

        self.minos = os_version(0, 0, 0)
        self.sdk_version = os_version(0, 0, 0)

        self.binding_table = None
        self.weak_binding_table = None
        self.lazy_binding_table = None
        self.exports = None

        self.symbol_table = None

    def get_int_at(self, offset: int, length: int, vm=False, section_name=None):
        """
        Get a sequence of bytes (as an int) from a location

        :param offset: Offset within the image
        :param length: Amount of bytes to get
        :param vm: Is `offset` a VM address
        :param section_name: Section Name if vm==True (improves translation time slightly)
        :return: `length` Bytes at `offset`
        """
        if vm:
            offset = self.vm.get_file_address(offset, section_name)
        return self.slice.get_int_at(offset, length)

    def get_bytes_at(self, offset: int, length: int, vm=False, section_name=None):
        """
        Get a sequence of bytes from a location

        :param offset: Offset within the image
        :param length: Amount of bytes to get
        :param vm: Is `offset` a VM address
        :param section_name: Section Name if vm==True (improves translation time slightly)
        :return: `length` Bytes at `offset`
        """
        if vm:
            offset = self.vm.get_file_address(offset, section_name)
        return self.slice.get_bytes_at(offset, length)

    def load_struct(self, address: int, struct_type, vm=False, section_name=None, endian="little"):
        """
        Load a struct (struct_type_t) from a location and return the processed object

        :param address: Address to load struct from
        :param struct_type: type of struct (e.g. dyld_header)
        :param vm:  Is `address` a VM address?
        :param section_name: if `vm==True`, the section name (slightly improves translation speed)
        :param endian: Endianness of bytes to read.
        :return: Loaded struct
        """
        if vm:
            address = self.vm.get_file_address(address, section_name)
        return self.slice.load_struct(address, struct_type, endian)

    def get_str_at(self, address: int, count: int, vm=False, section_name=None):
        """
        Get string with set length from location (to be used essentially only for loading segment names)

        :param address: Address of string start
        :param count: Length of string
        :param vm: Is `address` a VM address?
        :param section_name: if `vm==True`, the section name (unused here, really)
        :return: The loaded string.
        """
        if vm:
            address = self.vm.get_file_address(address, section_name)
        return self.slice.get_str_at(address, count)

    def get_cstr_at(self, address: int, limit: int = 0, vm=False, section_name=None):
        """
        Load a C style string from a location, stopping once a null byte is encountered.

        :param address: Address to load string from
        :param limit: Limit of the length of bytes, 0 = unlimited
        :param vm: Is `address` a VM address?
        :param section_name: if `vm==True`, the section name (vastly improves VM lookup time)
        :return: The loaded C string
        """
        if vm:
            address = self.vm.get_file_address(address, section_name)
        return self.slice.get_cstr_at(address, limit)

    def decode_uleb128(self, readHead: int):
        """
        Decode a uleb128 integer from a location

        :param readHead: Start location
        :return: (end location, value)
        """
        return self.slice.decode_uleb128(readHead)

    def rm_load_command(self, index):
        b_load_cmd = self.macho_header.load_commands.pop(index)

        off = b_load_cmd.off + b_load_cmd.cmdsize
        after_bytes = self.macho_header.raw_bytes()[off:self.macho_header.dyld_header.loadsize + 32]

        self.slice.patch(b_load_cmd.off, after_bytes)
        self.slice.patch(self.macho_header.dyld_header.loadsize + 32 - b_load_cmd.cmdsize, b'\x00' * b_load_cmd.cmdsize)

        dyld_head = self.macho_header.dyld_header
        dyld_head.loadcnt -= 1
        dyld_head.loadsize -= b_load_cmd.cmdsize

        self.slice.patch(self.macho_header.dyld_header.off, dyld_head.raw)

    def insert_lc(self, lc, fields, index=-1):
        lc_type = LOAD_COMMAND_MAP[lc]

        load_cmd = Struct.create_with_values(lc_type, [lc.value, lc_type.SIZE] + fields)

        off = dyld_header.SIZE
        off += self.macho_header.dyld_header.loadsize
        raw = load_cmd.raw
        size = len(load_cmd.raw)

        if index != -1:
            b_load_cmd = self.macho_header.load_commands[index - 1]
            off = b_load_cmd.off + b_load_cmd.cmdsize
            after_bytes = self.macho_header.raw_bytes()[off:self.macho_header.dyld_header.loadsize + 32]
            self.slice.patch(off, raw)
            self.slice.patch(off + size, after_bytes)
        else:
            self.slice.patch(off, raw)

        self.macho_header.load_commands.append(load_cmd)

        dyld_head = self.macho_header.dyld_header
        dyld_head.loadcnt += 1
        dyld_head.loadsize += size

        self.slice.patch(self.macho_header.dyld_header.off, dyld_head.raw)

    def insert_lc_with_suf(self, lc, fields, suffix, index=-1):
        lc_type = LOAD_COMMAND_MAP[lc]

        load_cmd = Struct.create_with_values(lc_type, [lc.value, lc_type.SIZE] + fields)
        # log.debug(f'Fabricated Load Command {str(load_cmd)}')

        encoded = suffix.encode('utf-8') + b'\x00'

        cmdsize = lc_type.SIZE
        cmdsize += len(encoded)
        cmdsize = 0x8 * math.ceil(cmdsize / 0x8)
        log.debug(f'Computed Struct Size of {cmdsize}')

        load_cmd.cmdsize = cmdsize

        off = dyld_header.SIZE
        off += self.macho_header.dyld_header.loadsize
        raw = load_cmd.raw + encoded + (b'\x00' * (cmdsize - (lc_type.SIZE + len(encoded))))
        log.debug(f'Padding Size {(cmdsize - (lc_type.SIZE + len(encoded)))}')
        size = len(raw)

        if index != -1:
            b_load_cmd = self.macho_header.load_commands[index - 1]
            off = b_load_cmd.off + b_load_cmd.cmdsize
            after_bytes = self.macho_header.raw_bytes()[off:self.macho_header.dyld_header.loadsize + 32]
            self.slice.patch(off, raw)
            self.slice.patch(off + size, after_bytes)
        else:
            self.slice.patch(off, raw)

        self.macho_header.load_commands.append(load_cmd)

        dyld_head = self.macho_header.dyld_header
        dyld_head.loadcnt += 1
        dyld_head.loadsize += size

        self.slice.patch(self.macho_header.dyld_header.off, dyld_head.raw)


class ImageHeader(Constructable):
    """
    This class represents the Mach-O Header
    It contains the basic header info along with all load commands within it.

    It doesn't handle complex abstraction logic, it simply loads in the load commands as their raw structs
    """

    @staticmethod
    def from_bytes(macho_slice):

        image_header = ImageHeader()

        offset = 0
        header: dyld_header = macho_slice.load_struct(offset, dyld_header)
        raw = header.raw

        image_header.filetype = MH_FILETYPE(header.filetype)

        for flag in MH_FLAGS:
            if header.flags & flag.value:
                image_header.flags.append(flag)

        offset += header.SIZE

        load_commands = []

        for i in range(1, header.loadcnt + 1):
            cmd = macho_slice.get_int_at(offset, 4)
            cmd_size = macho_slice.get_int_at(offset+4, 4)

            cmd_raw = macho_slice.get_bytes_at(offset, cmd_size)
            try:
                load_cmd = Struct.create_with_bytes(LOAD_COMMAND_MAP[LOAD_COMMAND(cmd)], cmd_raw)
                load_cmd.off = offset
            except ValueError:
                unk_lc = macho_slice.load_struct(offset, unk_command)
                load_cmd = unk_lc
            except KeyError:
                unk_lc = macho_slice.load_struct(offset, unk_command)
                load_cmd = unk_lc

            load_commands.append(load_cmd)
            raw += cmd_raw
            offset += load_cmd.cmdsize

        image_header.raw = raw
        image_header.dyld_header = header
        image_header.load_commands = load_commands

        return image_header

    @staticmethod
    def from_values(*args, **kwargs):
        pass

    def __init__(self):
        self.dyld_header = None
        self.filetype = MH_FILETYPE(0)
        self.flags = []
        self.load_commands = []
        self.raw = bytearray()

    def raw_bytes(self):
        return self.raw


class ExternalDylib:
    def __init__(self, source_image, cmd):
        self.cmd = cmd
        self.source_image = source_image
        self.install_name = self._get_name(cmd)
        self.weak = cmd.cmd == 0x18 | 0x80000000
        self.local = cmd.cmd == 0xD

    def _get_name(self, cmd):
        read_address = cmd.off + dylib_command.SIZE
        return self.source_image.get_cstr_at(read_address)


os_version = namedtuple("os_version", ["x", "y", "z"])


class PlatformType(Enum):
    MACOS = 1
    IOS = 2
    TVOS = 3
    WATCHOS = 4
    BRIDGE_OS = 5
    MAC_CATALYST = 6
    IOS_SIMULATOR = 7
    TVOS_SIMULATOR = 8
    WATCHOS_SIMULATOR = 9
    DRIVER_KIT = 10
    UNK = 64


class ToolType(Enum):
    CLANG = 1
    SWIFT = 2
    LD = 3


class SymbolType(Enum):
    CLASS = 0
    METACLASS = 1
    IVAR = 2
    FUNC = 3
    UNK = 4


class Symbol:
    """
    This class can represent several types of symbols.

    It can represent an external or internal symbol declaration and is used for both across the image

    .external is a BOOL that can be used to check whether it's an external or internal declaration

    .fullname contains the full name of the symbol (e.g. _OBJC_CLASS_$_MyDumbClassnameHere)

    .name contains the (somewhat) processed name of the symbol (e.g. _MyDumbClassnameHere for an @interface
    MyDumbClassnameHere)

    .type contains a SymbolType if it was able to figure one out

    .addr contains the address of the symbol in the image

    """

    def __init__(self, lib, cmd=None, entry=None, fullname=None, ordinal=None, addr=None):
        if fullname:
            self.fullname = fullname
        else:
            self.fullname = lib.get_cstr_at(entry.str_index + cmd.stroff)
        if '_$_' in self.fullname:
            if self.fullname.startswith('_OBJC_CLASS_$'):
                self.type = SymbolType.CLASS
            elif self.fullname.startswith('_OBJC_METACLASS_$'):
                self.type = SymbolType.METACLASS
            elif self.fullname.startswith('_OBJC_IVAR_$'):
                self.type = SymbolType.IVAR
            else:
                self.type = SymbolType.UNK
            self.name = self.fullname.split('$')[1]
        else:
            self.name = self.fullname
            self.type = SymbolType.FUNC
        if entry:
            self.external = False
            self.addr = entry.value
        else:
            self.external = True
            self.addr = addr
        self.entry = entry
        self.ordinal = ordinal


class SymbolTable:
    """
    This class represents the symbol table declared in the MachO File

    .table contains the symbol table

    .ext contains exported symbols, i think?

    This class is incomplete

    """

    def __init__(self, image, cmd: symtab_command):
        self.image = image
        self.cmd = cmd
        self.ext = []
        self.table = self._load_symbol_table()

    def _load_symbol_table(self):
        symbol_table = []
        read_address = self.cmd.symoff
        for i in range(0, self.cmd.nsyms):
            symbol_table.append(self.image.load_struct(read_address + symtab_entry.SIZE * i, symtab_entry))

        table = []
        for sym in symbol_table:
            symbol = Symbol(self.image, self.cmd, sym)
            # log.debug(f'Symbol Table: Loaded symbol:{symbol.name} ordinal:{symbol.ordinal} type:{symbol.type}')
            table.append(symbol)
            if sym.type == 0xf:
                self.ext.append(symbol)
        return table


export_node = namedtuple("export_node", ['text', 'offset'])


class ExportTrie(Constructable):
    @staticmethod
    def from_bytes(image, export_start, export_size):
        trie = ExportTrie()

        endpoint = export_start + export_size
        nodes = ExportTrie.read_node(image, export_start, '', export_start, endpoint)
        symbols = []

        for node in nodes:
            symbols.append(Symbol(image, fullname=node.text, addr=node.offset))

        trie.nodes = nodes
        trie.symbols = symbols
        trie.raw = image.get_bytes_at(export_start, export_size)

        return trie

    @staticmethod
    def from_values(*args, **kwargs):
        pass

    def raw_bytes(self):
        return self.raw

    def __init__(self):
        self.raw = bytearray()
        self.nodes = []
        self.symbols = []

    @classmethod
    def read_node(cls, image, trie_start, string, cursor, endpoint):

        if cursor > endpoint:
            macho_is_malformed()

        start = cursor
        byte = image.get_int_at(cursor, 1)
        results = []
        log.debug_tm(f'@ {hex(start)} node: {hex(byte)} current_symbol: {string}')
        if byte == 0:
            cursor += 1
            branches = image.get_int_at(cursor, 1)
            log.debug_tm(f'BRAN {branches}')
            for i in range(0, branches):
                if i == 0:
                    cursor += 1
                proc_str = image.get_cstr_at(cursor)
                cursor += len(proc_str) + 1
                offset, cursor = image.decode_uleb128(cursor)
                log.debug_tm(f'({i}) string: {string + proc_str} next_node: {hex(trie_start + offset)}')
                results += ExportTrie.read_node(image, trie_start, string + proc_str, trie_start + offset, endpoint)
        else:
            log.debug_tm(f'TERM: 0')
            size, cursor = image.decode_uleb128(cursor)
            flags = image.get_int_at(cursor, 1)
            cursor += 1
            offset, cursor = image.decode_uleb128(cursor)
            results.append(export_node(string, offset))

        return results


action = namedtuple("action", ["vmaddr", "libname", "item"])
record = namedtuple("record", [
    "off",
    "seg_index",
    "seg_offset",
    "lib_ordinal",
    "type",
    "flags",
    "name",
    "addend",
    "special_dylib"
])


class BindingTable:
    """
    The binding table contains a ton of information related to the binding info in the image

    .lookup_table - Contains a map of address -> Symbol declarations which should be used for processing off-image
    symbol decorations

    .symbol_table - Contains a full list of symbols declared in the binding info. Avoid iterating through this for
    speed purposes.

    .actions - contains a list of, you guessed it, actions.

    .import_stack - contains a fairly raw unprocessed list of binding info commands

    """

    def __init__(self, image, table_start, table_size):
        """
        Pass a image to be processed

        :param image: image to be processed
        :type image: Image
        """
        self.image = image
        self.import_stack = self._load_binding_info(table_start, table_size)
        self.actions = self._create_action_list()
        self.lookup_table = {}
        self.link_table = {}
        self.symbol_table = self._load_symbol_table()

    def _load_symbol_table(self):
        table = []
        for act in self.actions:
            if act.item:
                sym = Symbol(self.image, fullname=act.item, ordinal=act.libname, addr=act.vmaddr)
                # log.debug(f'Binding info: Loaded symbol:{act.item} ordinal:{act.libname} addr:{act.vmaddr}')
                table.append(sym)
                self.lookup_table[act.vmaddr] = sym
        return table

    def _create_action_list(self):
        actions = []
        for bind_command in self.import_stack:
            segment = list(self.image.segments.values())[bind_command.seg_index]
            vm_address = segment.vm_address + bind_command.seg_offset
            try:
                lib = self.image.linked[bind_command.lib_ordinal - 1].install_name
            except IndexError:
                # log.debug(f'Binding Info: {bind_command.lib_ordinal} Ordinal wasn't found, Something is wrong')
                lib = str(bind_command.lib_ordinal)
            item = bind_command.name
            actions.append(action(vm_address & 0xFFFFFFFFF, lib, item))
        return actions

    def _load_binding_info(self, table_start, table_size):
        read_address = table_start
        import_stack = []
        while True:
            if read_address - table_size >= table_start:
                break
            seg_index = 0x0
            seg_offset = 0x0
            lib_ordinal = 0x0
            btype = 0x0
            flags = 0x0
            name = ""
            addend = 0x0
            special_dylib = 0x0
            while True:
                # There are 0xc opcodes total
                # Bitmask opcode byte with 0xF0 to get opcode, 0xF to get value
                binding_opcode = self.image.get_int_at(read_address, 1) & 0xF0
                value = self.image.get_int_at(read_address, 1) & 0x0F
                log.debug_tm(f'{BINDING_OPCODE(binding_opcode).name}: {hex(value)}')
                cmd_start_addr = read_address
                is_beginning_stream = read_address == table_start
                read_address += 1

                if is_beginning_stream and binding_opcode == BINDING_OPCODE.SUBCODE_THREAED_APPLY:
                    o, read_address = self.image.decode_uleb128(read_address)

                if binding_opcode == BINDING_OPCODE.DONE:
                    import_stack.append(
                        record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend,
                               special_dylib))
                    break

                elif binding_opcode == BINDING_OPCODE.SET_DYLIB_ORDINAL_IMM:
                    lib_ordinal = value

                elif binding_opcode == BINDING_OPCODE.SET_DYLIB_ORDINAL_ULEB:
                    lib_ordinal, read_address = self.image.decode_uleb128(read_address)

                elif binding_opcode == BINDING_OPCODE.SET_DYLIB_SPECIAL_IMM:
                    special_dylib = 0x1
                    lib_ordinal = value

                elif binding_opcode == BINDING_OPCODE.SET_SYMBOL_TRAILING_FLAGS_IMM:
                    flags = value
                    name = self.image.get_cstr_at(read_address)
                    read_address += len(name) + 1

                elif binding_opcode == BINDING_OPCODE.SET_TYPE_IMM:
                    btype = value

                elif binding_opcode == BINDING_OPCODE.SET_ADDEND_SLEB:
                    addend, read_address = self.image.decode_uleb128(read_address)

                elif binding_opcode == BINDING_OPCODE.SET_SEGMENT_AND_OFFSET_ULEB:
                    seg_index = value
                    seg_offset, read_address = self.image.decode_uleb128(read_address)

                elif binding_opcode == BINDING_OPCODE.ADD_ADDR_ULEB:
                    o, read_address = self.image.decode_uleb128(read_address)
                    seg_offset += o

                elif binding_opcode == BINDING_OPCODE.DO_BIND_ADD_ADDR_ULEB:
                    import_stack.append(
                        record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend,
                               special_dylib))
                    seg_offset += 8
                    o, read_address = self.image.decode_uleb128(read_address)
                    seg_offset += o

                elif binding_opcode == BINDING_OPCODE.DO_BIND_ADD_ADDR_IMM_SCALED:
                    import_stack.append(
                        record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend,
                               special_dylib))
                    seg_offset = seg_offset + (value * 8) + 8

                elif binding_opcode == BINDING_OPCODE.DO_BIND_ULEB_TIMES_SKIPPING_ULEB:
                    count, read_address = self.image.decode_uleb128(read_address)
                    skip, read_address = self.image.decode_uleb128(read_address)

                    for i in range(0, count):
                        import_stack.append(
                            record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend,
                                   special_dylib))
                        seg_offset += skip + 8

                elif binding_opcode == BINDING_OPCODE.DO_BIND:
                    import_stack.append(
                        record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend,
                               special_dylib))
                    seg_offset += 8

        return import_stack
