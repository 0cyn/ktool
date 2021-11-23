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
from enum import IntEnum, Enum
from collections import namedtuple

from kmacho import (
    MH_FLAGS,
    MH_FILETYPE,
    LOAD_COMMAND,
    BINDING_OPCODE,
    REBASE_OPCODE, LOAD_COMMAND_MAP
)

from kmacho.structs import *
# from kmacho.fixups import *

from .util import log
from .macho import _VirtualMemoryMap, Segment


class Dyld:
    """
    This is a static class containing several methods for, essentially, recreating the functionality of Dyld for our
    own purposes.

    It isn't meant to be a faithful recreation of dyld so to speak, it just does things dyld also does, kinda.

    """

    @staticmethod
    def load(macho_slice, load_symtab=True, load_binding=True):
        """
        Take a slice of a macho file and process it using the dyld functions

        :param macho_slice: Slice to load. If your library is not fat, that'll be MachOFile.slices[0]
        :type macho_slice: Slice
        :return: Processed Library object
        :rtype: Library
        """
        log.info("Loading Library")
        library = Library(macho_slice)

        log.info("Processing Load Commands")
        Dyld._parse_load_commands(library, load_symtab, load_binding)
        return library

    @staticmethod
    def _parse_load_commands(library, load_symtab=True, load_binding=True):
        fixups = None
        for cmd in library.macho_header.load_commands:
            if isinstance(cmd, segment_command_64):
                log.debug("Loading segment_command_64")
                segment = Segment(library, cmd)

                log.debug(f'Loaded Segment {segment.name}')
                library.vm.add_segment(segment)
                library.segments[segment.name] = segment

                log.debug(f'Added {segment.name} to VM Map')

            elif isinstance(cmd, dyld_info_command):
                library.info = cmd
                if load_binding:
                    log.info("Loading Binding Info")
                    library.binding_table = BindingTable(library, cmd.bind_off, cmd.bind_size)
                    library.weak_binding_table = BindingTable(library, cmd.weak_bind_off, cmd.weak_bind_size)
                    library.lazy_binding_table = BindingTable(library, cmd.lazy_bind_off, cmd.lazy_bind_size)
                    library.exports = ExportTrie(library, cmd.export_off, cmd.export_size)

            elif LOAD_COMMAND(cmd.cmd) == LOAD_COMMAND.LC_DYLD_EXPORTS_TRIE:
                library.exports = ExportTrie(library, cmd.dataoff, cmd.datasize)

            elif LOAD_COMMAND(cmd.cmd) == LOAD_COMMAND.LC_DYLD_CHAINED_FIXUPS:
                # fixups = ChainedFixups(library, cmd.dataoff, cmd.datasize)
                pass

            elif isinstance(cmd, symtab_command):
                if load_symtab:
                    log.info("Loading Symbol Table")
                    library.symbol_table = SymbolTable(library, cmd)

            elif isinstance(cmd, uuid_command):
                library.uuid = cmd.uuid.to_bytes(16, "little")

            elif isinstance(cmd, sub_client_command):
                string = library.get_cstr_at(cmd.off + cmd.offset)
                library.allowed_clients.append(string)
                log.debug(f'Loaded Subclient "{string}"')

            elif isinstance(cmd, rpath_command):
                string = library.get_cstr_at(cmd.off + cmd.path)
                library.rpath = string

            elif isinstance(cmd, build_version_command):
                library.platform = PlatformType(cmd.platform)
                library.minos = os_version(x=library.get_bytes(cmd.off + 14, 2), y=library.get_bytes(cmd.off + 13, 1),
                                           z=library.get_bytes(cmd.off + 12, 1))
                library.sdk_version = os_version(x=library.get_bytes(cmd.off + 18, 2),
                                                 y=library.get_bytes(cmd.off + 17, 1),
                                                 z=library.get_bytes(cmd.off + 16, 1))
                log.debug(f'Loaded platform {library.platform.name} | '
                              f'Minimum OS {library.minos.x}.{library.minos.y}'
                              f'.{library.minos.z} | SDK Version {library.sdk_version.x}'
                              f'.{library.sdk_version.y}.{library.sdk_version.z}')

            elif isinstance(cmd, version_min_command):
                if library.platform == PlatformType.UNK:

                    if LOAD_COMMAND(cmd.cmd) == LOAD_COMMAND.VERSION_MIN_MACOSX:
                        library.platform = PlatformType.MACOS
                    elif LOAD_COMMAND(cmd.cmd) == LOAD_COMMAND.VERSION_MIN_IPHONEOS:
                        library.platform = PlatformType.IOS
                    elif LOAD_COMMAND(cmd.cmd) == LOAD_COMMAND.VERSION_MIN_TVOS:
                        library.platform = PlatformType.TVOS
                    elif LOAD_COMMAND(cmd.cmd) == LOAD_COMMAND.VERSION_MIN_WATCHOS:
                        library.platform = PlatformType.WATCHOS

                    library.minos = os_version(x=library.get_bytes(cmd.off + 10, 2),
                                               y=library.get_bytes(cmd.off + 9, 1),
                                               z=library.get_bytes(cmd.off + 8, 1))

            elif isinstance(cmd, dylib_command):
                if cmd.cmd == 0xD:  # local
                    library.dylib = ExternalDylib(library, cmd)
                    log.debug(f'Loaded local dylib_command with install_name {library.dylib.install_name}')
                else:
                    external_dylib = ExternalDylib(library, cmd)
                    library.linked.append(external_dylib)
                    log.debug(f'Loaded linked dylib_command with install name {external_dylib.install_name}')

        if library.dylib is not None:
            library.name = library.dylib.install_name.split('/')[-1]
        else:
            library.name = ""


class Library:
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
        Create a MachO Library

        :param macho_slice: MachO Slice being processed
        :type macho_slice: MachO Slice
        """
        self.macho_header = LibraryHeader(macho_slice)
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

    def get_bytes(self, offset: int, length: int, vm=False, section_name=None):
        """
        Get a sequence of bytes (as an int) from a location

        :param offset: Offset within the library
        :param length: Amount of bytes to get
        :param vm: Is `offset` a VM address
        :param section_name: Section Name if vm==True (improves translation time slightly)
        :return: `length` Bytes at `offset`
        """
        if vm:
            offset = self.vm.get_file_address(offset, section_name)
        return self.slice.get_at(offset, length)

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
        self.slice.patch(self.macho_header.dyld_header.loadsize + 32 - b_load_cmd.cmdsize, b'\x00'*b_load_cmd.cmdsize)

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
            b_load_cmd = self.macho_header.load_commands[index-1]
            off = b_load_cmd.off + b_load_cmd.cmdsize
            after_bytes = self.macho_header.raw_bytes()[off:self.macho_header.dyld_header.loadsize + 32]
            self.slice.patch(off, raw)
            self.slice.patch(off+size, after_bytes)
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
        #log.debug(f'Fabricated Load Command {str(load_cmd)}')

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
            b_load_cmd = self.macho_header.load_commands[index-1]
            off = b_load_cmd.off + b_load_cmd.cmdsize
            after_bytes = self.macho_header.raw_bytes()[off:self.macho_header.dyld_header.loadsize + 32]
            self.slice.patch(off, raw)
            self.slice.patch(off+size, after_bytes)
        else:
            self.slice.patch(off, raw)

        self.macho_header.load_commands.append(load_cmd)

        dyld_head = self.macho_header.dyld_header
        dyld_head.loadcnt += 1
        dyld_head.loadsize += size

        self.slice.patch(self.macho_header.dyld_header.off, dyld_head.raw)


class LibraryHeader:
    """
    This class represents the Mach-O Header
    It contains the basic header info along with all load commands within it.

    It doesn't handle complex abstraction logic, it simply loads in the load commands as their raw structs
    """

    def __init__(self, macho_slice):
        """

        :param macho_slice: MachO Slice object being loaded
        :type macho_slice: Slice
        """
        offset = 0
        self.slice = macho_slice
        self.dyld_header: dyld_header = macho_slice.load_struct(offset, dyld_header)
        self.filetype = MH_FILETYPE(self.dyld_header.filetype)
        self.flags = []
        for flag in MH_FLAGS:
            if self.dyld_header.flags & flag.value:
                self.flags.append(flag)
        self.load_commands = []
        self._process_load_commands(macho_slice)

    def raw_bytes(self):
        size = dyld_header.SIZE
        size += self.dyld_header.loadsize
        read_addr = self.dyld_header.off
        return self.slice.get_bytes_at(read_addr, size)

    def _process_load_commands(self, macho_slice):
        """
        This function takes the raw slice and parses through its load commands

        :param macho_slice: MachO Library Slice
        :return:
        """

        # Start address of the load commands.
        read_address = self.dyld_header.off + 0x20

        # Loop through the dyld_header by load command count
        # possibly this could be modified to check for other load commands
        #       as a rare obfuscation technique involves fucking with these to screw with RE tools.

        for i in range(1, self.dyld_header.loadcnt+1):
            cmd = macho_slice.get_at(read_address, 4)
            try:
                load_cmd = macho_slice.load_struct(read_address, LOAD_COMMAND_MAP[LOAD_COMMAND(cmd)])
            except ValueError:
                unk_lc = macho_slice.load_struct(read_address, unk_command)
                load_cmd = unk_lc
            except KeyError:
                unk_lc = macho_slice.load_struct(read_address, unk_command)
                load_cmd = unk_lc

            self.load_commands.append(load_cmd)
            read_address += load_cmd.cmdsize


class ExternalDylib:
    def __init__(self, source_library, cmd):
        self.cmd = cmd
        self.source_library = source_library
        self.install_name = self._get_name(cmd)
        self.weak = cmd.cmd == 0x18 | 0x80000000
        self.local = cmd.cmd == 0xD

    def _get_name(self, cmd):
        read_address = cmd.off + dylib_command.SIZE
        return self.source_library.get_cstr_at(read_address)


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

    It can represent an external or internal symbol declaration and is used for both across the library

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
    def __init__(self, library, cmd: symtab_command):
        self.library = library
        self.cmd = cmd
        self.ext = []
        self.table = self._load_symbol_table()

    def _load_symbol_table(self):
        symbol_table = []
        read_address = self.cmd.symoff
        for i in range(0, self.cmd.nsyms):
            symbol_table.append(self.library.load_struct(read_address + symtab_entry.SIZE * i, symtab_entry))

        table = []
        for sym in symbol_table:
            symbol = Symbol(self.library, self.cmd, sym)
            # log.debug(f'Symbol Table: Loaded symbol:{symbol.name} ordinal:{symbol.ordinal} type:{symbol.type}')
            table.append(symbol)
            if sym.type == 0xf:
                self.ext.append(symbol)
        return table


export_node = namedtuple("export_node", ['text', 'offset'])


class ExportTrie:
    def __init__(self, library, export_start, export_size):
        self.library = library
        self.start = export_start
        self.size = export_size
        self.nodes = []

        self.read_export_trie()

    def read_export_trie(self):
        cursor = self.start
        self.nodes = self.read_node("", cursor)

    def read_node(self, string, cursor):
        start = cursor
        byte = self.library.get_bytes(cursor, 1)
        results = []
        log.debug(f'@ {hex(start)} node: {hex(byte)} current_symbol: {string}')
        if byte == 0:
            cursor += 1
            branches = self.library.get_bytes(cursor, 1)
            log.debug(f'BRAN {branches}')
            for i in range(0, branches):
                if i == 0:
                    cursor += 1
                proc_str = self.library.get_cstr_at(cursor)
                cursor += len(proc_str) + 1
                offset, cursor = self.library.decode_uleb128(cursor)
                log.debug(f'({i}) string: {string+proc_str} next_node: {hex(self.start+offset)}')
                results += self.read_node(string + proc_str, self.start + offset)
        else:
            log.debug(f'TERM: 0')
            size, cursor = self.library.decode_uleb128(cursor)
            flags = self.library.get_bytes(cursor, 1)
            cursor += 1
            offset, cursor = self.library.decode_uleb128(cursor)
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
    The binding table contains a ton of information related to the binding info in the library

    .lookup_table - Contains a map of address -> Symbol declarations which should be used for processing off-image
    symbol decorations

    .symbol_table - Contains a full list of symbols declared in the binding info. Avoid iterating through this for
    speed purposes.

    .actions - contains a list of, you guessed it, actions.

    .import_stack - contains a fairly raw unprocessed list of binding info commands

    """
    def __init__(self, library, table_start, table_size):
        """
        Pass a library to be processed

        :param library: Library to be processed
        :type library: Library
        """
        self.library = library
        self.import_stack = self._load_binding_info(table_start, table_size)
        self.actions = self._create_action_list()
        self.lookup_table = {}
        self.link_table = {}
        self.symbol_table = self._load_symbol_table()

    def _load_symbol_table(self):
        table = []
        for act in self.actions:
            if act.item:
                sym = Symbol(self.library, fullname=act.item, ordinal=act.libname, addr=act.vmaddr)
                # log.debug(f'Binding info: Loaded symbol:{act.item} ordinal:{act.libname} addr:{act.vmaddr}')
                table.append(sym)
                self.lookup_table[act.vmaddr] = sym
        return table

    def _create_action_list(self):
        actions = []
        for bind_command in self.import_stack:
            segment = list(self.library.segments.values())[bind_command.seg_index]
            vm_address = segment.vm_address + bind_command.seg_offset
            try:
                lib = self.library.linked[bind_command.lib_ordinal - 1].install_name
            except IndexError:
                # log.debug(f'Binding Info: {bind_command.lib_ordinal} Ordinal wasn't found, Something is wrong')
                lib = str(bind_command.lib_ordinal)
            item = bind_command.name
            actions.append(action(vm_address & 0xFFFFFFFFF, lib, item))
        return actions

    def _load_binding_info(self, table_start, table_size):
        lib = self.library
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
                binding_opcode = self.library.get_bytes(read_address, 1) & 0xF0
                value = self.library.get_bytes(read_address, 1) & 0x0F
                cmd_start_addr = read_address
                read_address += 1

                if binding_opcode == BINDING_OPCODE.DONE:
                    import_stack.append(
                        record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
                    break

                elif binding_opcode == BINDING_OPCODE.SET_DYLIB_ORDINAL_IMM:
                    lib_ordinal = value

                elif binding_opcode == BINDING_OPCODE.SET_DYLIB_ORDINAL_ULEB:
                    lib_ordinal, read_address = self.library.decode_uleb128(read_address)

                elif binding_opcode == BINDING_OPCODE.SET_DYLIB_SPECIAL_IMM:
                    special_dylib = 0x1
                    lib_ordinal = value

                elif binding_opcode == BINDING_OPCODE.SET_SYMBOL_TRAILING_FLAGS_IMM:
                    flags = value
                    name = self.library.get_cstr_at(read_address)
                    read_address += len(name) + 1

                elif binding_opcode == BINDING_OPCODE.SET_TYPE_IMM:
                    btype = value

                elif binding_opcode == BINDING_OPCODE.SET_ADDEND_SLEB:
                    addend, read_address = self.library.decode_uleb128(read_address)

                elif binding_opcode == BINDING_OPCODE.SET_SEGMENT_AND_OFFSET_ULEB:
                    seg_index = value
                    seg_offset, read_address = self.library.decode_uleb128(read_address)

                elif binding_opcode == BINDING_OPCODE.ADD_ADDR_ULEB:
                    o, read_address = self.library.decode_uleb128(read_address)
                    seg_offset += o

                elif binding_opcode == BINDING_OPCODE.DO_BIND_ADD_ADDR_ULEB:
                    import_stack.append(
                        record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
                    seg_offset += 8
                    o, read_address = self.library.decode_uleb128(read_address)
                    seg_offset += o

                elif binding_opcode == BINDING_OPCODE.DO_BIND_ADD_ADDR_IMM_SCALED:
                    import_stack.append(
                        record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
                    seg_offset = seg_offset + (value * 8) + 8

                elif binding_opcode == BINDING_OPCODE.DO_BIND_ULEB_TIMES_SKIPPING_ULEB:
                    count, read_address = self.library.decode_uleb128(read_address)
                    skip, read_address = self.library.decode_uleb128(read_address)

                    for i in range(0, count):
                        import_stack.append(
                            record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
                        seg_offset += skip + 8

                elif binding_opcode == BINDING_OPCODE.DO_BIND:
                    import_stack.append(
                        record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
                    seg_offset += 8

        return import_stack



