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
from typing import List, Union, Dict

from kmacho import (
    MH_FLAGS,
    MH_FILETYPE,
    LOAD_COMMAND,
    BINDING_OPCODE,
    LOAD_COMMAND_MAP,
    BIND_SUBOPCODE_THREADED_SET_BIND_ORDINAL_TABLE_SIZE_ULEB,
    BIND_SUBOPCODE_THREADED_APPLY, MH_MAGIC_64
)
from kmacho.structs import *
from kmacho.base import Constructable
from .macho import _VirtualMemoryMap, Segment, Slice
from .util import log, macho_is_malformed


class ImageHeader(Constructable):
    """
    This class represents the Mach-O Header
    It contains the basic header info along with all load commands within it.

    It doesn't handle complex abstraction logic, it simply loads in the load commands as their raw structs
    """

    @classmethod
    def from_image(cls, macho_slice) -> 'ImageHeader':

        image_header = ImageHeader()

        offset = 0

        header: dyld_header = macho_slice.load_struct(offset, dyld_header)
        if header.magic == MH_MAGIC_64:
            header: dyld_header_64 = macho_slice.load_struct(offset, dyld_header_64)
            image_header.is64 = True

        raw = header.raw

        image_header.filetype = MH_FILETYPE(header.filetype)

        for flag in MH_FLAGS:
            if header.flags & flag.value:
                image_header.flags.append(flag)

        offset += header.SIZE

        load_commands = []

        for i in range(1, header.loadcnt + 1):
            cmd = macho_slice.get_int_at(offset, 4)
            cmd_size = macho_slice.get_int_at(offset + 4, 4)

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

    @classmethod
    def from_values(cls, *args, **kwargs):
        pass

    def __init__(self):
        self.is64 = False
        self.dyld_header = None
        self.filetype = MH_FILETYPE(0)
        self.flags: List[MH_FILETYPE] = []
        self.load_commands = []
        self.raw = bytearray()

    def raw_bytes(self) -> bytes:
        return self.raw


class Image:
    """
    This class represents the Mach-O Binary as a whole.

    It's the root object in the massive tree of information we're going to build up about the binary

    This class on its own does not handle populating its fields.
    The Dyld class set is responsible for loading in and processing the raw values to it.
    """

    def __init__(self, macho_slice: Slice):
        """
        Create a MachO image

        :param macho_slice: MachO Slice being processed
        :type macho_slice: MachO Slice
        """
        self.slice: Slice = macho_slice

        if self.slice:
            self.macho_header: ImageHeader = ImageHeader.from_image(macho_slice=macho_slice)

        self.linked_images: List[ExternalDylib] = []

        self.name = ""  # TODO: Remove this field soon.
        self.base_name = ""  # copy of self.name
        self.install_name = ""

        self.segments = {}

        log.debug("Initializing VM Map")
        self.vm = _VirtualMemoryMap(macho_slice)

        self.info: Union[dyld_info_command, None] = None
        self.dylib: Union[ExternalDylib, None] = None
        self.uuid = None

        self.platform: PlatformType = PlatformType.UNK

        self.allowed_clients: List[str] = []

        self.rpath: Union[str, None] = None

        self.minos = os_version(0, 0, 0)
        self.sdk_version = os_version(0, 0, 0)

        self.imports: List[Symbol] = []
        self.exports: List[Symbol] = []

        self.symbols: Dict[int, Symbol] = {}
        self.import_table: Dict[int, Symbol] = {}
        self.export_table: Dict[int, Symbol] = {}

        self.binding_table = None
        self.weak_binding_table = None
        self.lazy_binding_table = None
        self.export_trie: Union[ExportTrie, None] = None

        self.symbol_table: Union[SymbolTable, None] = None

        self.struct_cache: Dict[int, Struct] = {}

    def vm_check(self, address):
        return self.vm.vm_check(address)

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
        if address not in self.struct_cache:
            if vm:
                address = self.vm.get_file_address(address, section_name)
            struct = self.slice.load_struct(address, struct_type, endian)
            self.struct_cache[address] = struct
            return struct

        return self.struct_cache[address]

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


class Dyld:
    """
    This class takes our initialized "Image" object, parses through the raw data behind it, and fills out its properties.

    """

    @classmethod
    def load(cls, macho_slice: Slice, load_symtab=True, load_imports=True, load_exports=True) -> Image:
        """
        Take a slice of a macho file and process it using the dyld functions

        :param load_exports: Load Exports
        :param load_imports: Load Imports
        :param load_symtab: Load Symbol Table
        :param macho_slice: Slice to load. If your image is not fat, that'll be MachOFile.slices[0]
        :type macho_slice: Slice
        :return: Processed image object
        :rtype: Image
        """
        log.info("Loading image")
        image = Image(macho_slice)

        log.info("Processing Load Commands")
        Dyld._parse_load_commands(image, load_symtab, load_imports, load_exports)

        log.info("Processing Image")
        Dyld._process_image(image)
        return image

    @classmethod
    def _parse_load_commands(cls, image: Image, load_symtab=True, load_imports=True, load_exports=True) -> None:
        # noinspection PyUnusedLocal
        fixups = None
        log.info(f'registered {len(image.macho_header.load_commands)} Load Commands')
        for cmd in image.macho_header.load_commands:
            try:
                load_command = LOAD_COMMAND(cmd.cmd)
            except ValueError:
                continue

            if load_command == LOAD_COMMAND.SEGMENT_64 or load_command == LOAD_COMMAND.SEGMENT:
                log.debug("Loading Segment")
                segment = Segment(image, cmd)

                log.info(f'Loaded Segment {segment.name}')

                image.vm.add_segment(segment)
                image.segments[segment.name] = segment

                log.debug(f'Added {segment.name} to VM Map')

            elif load_command == LOAD_COMMAND.DYLD_INFO_ONLY:
                image.info = cmd

                if load_imports:
                    log.info("Loading Binding Info")
                    image.binding_table = BindingTable(image, cmd.bind_off, cmd.bind_size)
                    image.weak_binding_table = BindingTable(image, cmd.weak_bind_off, cmd.weak_bind_size)
                    image.lazy_binding_table = BindingTable(image, cmd.lazy_bind_off, cmd.lazy_bind_size)

                if load_exports:
                    log.info("Loading Export Trie")
                    image.export_trie = ExportTrie.from_image(image, cmd.export_off, cmd.export_size)

            elif load_command == LOAD_COMMAND.LC_DYLD_EXPORTS_TRIE:
                log.info("Loading Export Trie")
                image.export_trie = ExportTrie.from_image(image, cmd.dataoff, cmd.datasize)

            elif load_command == LOAD_COMMAND.LC_DYLD_CHAINED_FIXUPS:
                log.warning(
                    "image uses LC_DYLD_CHAINED_FIXUPS; This is not yet supported in ktool, off-image symbol resolution (superclasses, etc) will not work")
                pass

            elif load_command == LOAD_COMMAND.SYMTAB:
                if load_symtab:
                    log.info("Loading Symbol Table")
                    image.symbol_table = SymbolTable(image, cmd)

            elif load_command == LOAD_COMMAND.DYSYMTAB:
                cmd = cmd

            elif load_command == LOAD_COMMAND.UUID:
                image.uuid = cmd.uuid.to_bytes(16, "little")
                log.info(f'image UUID: {image.uuid}')

            elif load_command == LOAD_COMMAND.SUB_CLIENT:
                string = image.get_cstr_at(cmd.off + cmd.offset)
                image.allowed_clients.append(string)
                log.debug(f'Loaded Subclient "{string}"')

            elif load_command == LOAD_COMMAND.RPATH:
                string = image.get_cstr_at(cmd.off + cmd.path)
                image.rpath = string
                log.info(f'image Resource Path: {string}')

            elif load_command == LOAD_COMMAND.BUILD_VERSION:
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
                    if load_command == LOAD_COMMAND.VERSION_MIN_MACOSX:
                        image.platform = PlatformType.MACOS
                    elif load_command == LOAD_COMMAND.VERSION_MIN_IPHONEOS:
                        image.platform = PlatformType.IOS
                    elif load_command == LOAD_COMMAND.VERSION_MIN_TVOS:
                        image.platform = PlatformType.TVOS
                    elif load_command == LOAD_COMMAND.VERSION_MIN_WATCHOS:
                        image.platform = PlatformType.WATCHOS

                    image.minos = os_version(x=image.get_int_at(cmd.off + 10, 2),
                                             y=image.get_int_at(cmd.off + 9, 1),
                                             z=image.get_int_at(cmd.off + 8, 1))

            elif load_command == LOAD_COMMAND.ID_DYLIB:
                image.dylib = ExternalDylib(image, cmd)
                log.info(f'Loaded local dylib_command with install_name {image.dylib.install_name}')

            elif isinstance(cmd, dylib_command):
                # noinspection PyTypeChecker
                external_dylib = ExternalDylib(image, cmd)

                image.linked_images.append(external_dylib)
                log.info(f'Loaded linked dylib_command with install name {external_dylib.install_name}')

    @staticmethod
    def _process_image(image: Image) -> None:
        """
        Once all load commands have been processed, process the results.
        This is mainly for things which need to be done once *all* lcs have been processed.

        :param image:
        :return:
        """
        if image.dylib is not None:
            image.name = image.dylib.install_name.split('/')[-1]
            image.base_name = image.dylib.install_name.split('/')[-1]
            image.install_name = image.dylib.install_name
        else:
            image.name = ""
            image.base_name = image.slice.macho_file.filename
            image.install_name = ""

        if image.export_trie:
            for symbol in image.export_trie.symbols:
                image.exports.append(symbol)
                image.export_table[symbol.address] = symbol

        if image.binding_table:
            for symbol in image.binding_table.symbol_table:
                symbol.attr = ''
                image.imports.append(symbol)
                image.import_table[symbol.address] = symbol
            for symbol in image.weak_binding_table.symbol_table:
                symbol.attr = 'Weak'
                image.imports.append(symbol)
                image.import_table[symbol.address] = symbol
            for symbol in image.lazy_binding_table.symbol_table:
                symbol.attr = 'Lazy'
                image.imports.append(symbol)
                image.import_table[symbol.address] = symbol

        if image.symbol_table:
            for symbol in image.symbol_table.table:
                image.symbols[symbol.address] = symbol


class LD64:
    @classmethod
    def insert_load_cmd(cls, image: Image, lc, fields, index=-1):
        lc_type = LOAD_COMMAND_MAP[lc]

        load_cmd = Struct.create_with_values(lc_type, [lc.value, lc_type.SIZE] + fields)

        off = dyld_header.SIZE
        off += image.macho_header.dyld_header.loadsize
        raw = load_cmd.raw
        size = len(load_cmd.raw)

        if index != -1:
            b_load_cmd = image.macho_header.load_commands[index - 1]
            off = b_load_cmd.off + b_load_cmd.cmdsize
            after_bytes = image.macho_header.raw_bytes()[off:image.macho_header.dyld_header.loadsize + 32]
            image.slice.patch(off, raw)
            image.slice.patch(off + size, after_bytes)
        else:
            image.slice.patch(off, raw)

        image.macho_header.load_commands.append(load_cmd)

        image.macho_header.dyld_header.loadcnt += 1
        image.macho_header.dyld_header.loadsize += size

        image.slice.patch(image.macho_header.dyld_header.off, image.macho_header.dyld_header.raw)

    @classmethod
    def insert_load_cmd_with_str(cls, image: Image, lc, fields, suffix, index=-1):
        lc_type = LOAD_COMMAND_MAP[lc]

        load_cmd = Struct.create_with_values(lc_type, [lc.value, lc_type.SIZE] + fields)
        log.debug(f'Fabricated Load Command {str(load_cmd)}')

        encoded = suffix.encode('utf-8') + b'\x00'

        cmd_size = lc_type.SIZE
        cmd_size += len(encoded)
        cmd_size = 0x8 * math.ceil(cmd_size / 0x8)
        log.debug_tm(f'Computed cmd size (w/ pad) Size of {cmd_size}')

        load_cmd.cmdsize = cmd_size

        off = dyld_header.SIZE
        off += image.macho_header.dyld_header.loadsize
        raw = load_cmd.raw + encoded + (b'\x00' * (cmd_size - (lc_type.SIZE + len(encoded))))
        log.debug_tm(f'Padding Size {(cmd_size - (lc_type.SIZE + len(encoded)))}')
        size = len(raw)

        if index != -1:
            b_load_cmd = image.macho_header.load_commands[index - 1]
            off = b_load_cmd.off + b_load_cmd.cmdsize
            after_bytes = image.macho_header.raw_bytes()[off:image.macho_header.dyld_header.loadsize + 32]
            image.slice.patch(off, raw)
            image.slice.patch(off + size, after_bytes)
            image.macho_header.load_commands.insert(index, load_cmd)
        else:
            image.slice.patch(off, raw)
            image.macho_header.load_commands.append(load_cmd)

        image.macho_header.dyld_header.loadcnt += 1
        image.macho_header.dyld_header.loadsize -= size

        image.slice.patch(image.macho_header.dyld_header.off, image.macho_header.dyld_header.raw)

    @classmethod
    def remove_load_command(cls, image: Image, index):
        b_load_cmd = image.macho_header.load_commands.pop(index)

        off = b_load_cmd.off + b_load_cmd.cmdsize
        after_bytes = image.macho_header.raw_bytes()[off:image.macho_header.dyld_header.loadsize + 32]

        image.slice.patch(b_load_cmd.off, after_bytes)
        image.slice.patch(image.macho_header.dyld_header.loadsize + 32 - b_load_cmd.cmdsize, b'\x00' * b_load_cmd.cmdsize)

        image.macho_header.dyld_header.loadcnt -= 1
        image.macho_header.dyld_header.loadsize -= b_load_cmd.cmdsize

        image.slice.patch(image.macho_header.dyld_header.off, image.macho_header.dyld_header.raw)


class ExternalDylib:
    def __init__(self, source_image: Image, cmd):
        self.cmd = cmd
        self.source_image = source_image

        self.install_name = self._get_name(cmd)
        self.weak = cmd.cmd == 0x18 | 0x80000000
        self.local = cmd.cmd == 0xD

    def _get_name(self, cmd) -> str:
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


class Symbol(Constructable):
    """
    This class can represent several types of symbols.

    """

    @classmethod
    def from_image(cls, image, cmd, entry):
        fullname = image.get_cstr_at(entry.str_index + cmd.stroff)
        addr = entry.value

        symbol = cls.from_values(fullname, addr)

        N_STAB = 0xe0
        N_PEXT = 0x10
        N_TYPE = 0x0e
        N_EXT = 0x01

        type_masked = N_TYPE & entry.type
        for name, flag in {'N_UNDF':0x0, 'N_ABS': 0x2, 'N_SECT':0xe, 'N_PBUD':0xc, 'N_INDR':0xa}.items():
            if type_masked & flag:
                symbol.types.append(name)

        if entry.type & N_EXT:
            symbol.external = True

        return symbol

    @classmethod
    def from_values(cls, fullname, value, external=False, ordinal=0):

        if '_$_' in fullname:
            if fullname.startswith('_OBJC_CLASS_$'):
                dec_type = SymbolType.CLASS
            elif fullname.startswith('_OBJC_METACLASS_$'):
                dec_type = SymbolType.METACLASS
            elif fullname.startswith('_OBJC_IVAR_$'):
                dec_type = SymbolType.IVAR
            else:
                dec_type = SymbolType.UNK
            name = fullname.split('$')[1]
        else:
            name = fullname
            dec_type = SymbolType.FUNC

        return cls(fullname, name=name, dec_type=dec_type, external=external, value=value, ordinal=ordinal)

    def raw_bytes(self):
        pass

    def __init__(self, fullname=None, name=None, dec_type=None, external=False, value=0, ordinal=0):
        self.fullname = fullname
        self.name = name
        self.dec_type = dec_type

        self.address = value

        self.entry = None
        self.ordinal = ordinal

        self.types = []
        self.external = external

        self.attr = None


class SymbolTable:
    """
    This class represents the symbol table declared in the MachO File

    .table contains the symbol table

    .ext contains exported symbols, i think?

    This class is incomplete

    """

    def __init__(self, image: Image, cmd: symtab_command):
        self.image: Image = image
        self.cmd: symtab_command = cmd

        self.ext: List[Symbol] = []
        self.table: List[Symbol] = self._load_symbol_table()

    def _load_symbol_table(self) -> List[Symbol]:
        symbol_table = []
        read_address = self.cmd.symoff
        for i in range(0, self.cmd.nsyms):
            typing = symtab_entry if self.image.macho_header.is64 else symtab_entry_32
            entry = self.image.load_struct(read_address + typing.SIZE * i, typing)
            symbol_table.append(entry)
            log.debug_tm(str(entry))

        table = []
        for sym in symbol_table:
            symbol = Symbol.from_image(self.image, self.cmd, sym)
            log.debug_tm(f'Symbol Table: Loaded symbol:{symbol.name} ordinal:{symbol.ordinal} type:{symbol.dec_type}')
            table.append(symbol)
            if sym.type == 0xf:
                self.ext.append(symbol)
        return table


export_node = namedtuple("export_node", ['text', 'offset', 'flags'])


class ExportTrie(Constructable):
    @classmethod
    def from_image(cls, image: Image, export_start: int, export_size: int) -> 'ExportTrie':
        trie = ExportTrie()

        endpoint = export_start + export_size
        nodes = ExportTrie.read_node(image, export_start, '', export_start, endpoint)
        symbols = []

        for node in nodes:
            if node.text:
                symbols.append(Symbol.from_values(node.text, node.offset, False))

        trie.nodes = nodes
        trie.symbols = symbols
        trie.raw = image.get_bytes_at(export_start, export_size)

        return trie

    @classmethod
    def from_values(cls, *args, **kwargs):
        pass

    def raw_bytes(self):
        return self.raw

    def __init__(self):
        self.raw = bytearray()
        self.nodes: List[export_node] = []
        self.symbols: List[Symbol] = []

    @classmethod
    def read_node(cls, image: Image, trie_start: int, string: str, cursor: int, endpoint: int) -> List[export_node]:

        if cursor > endpoint:
            log.error("Node offset greater than size of export trie")
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
            results.append(export_node(string, offset, flags))

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

    def __init__(self, image: Image, table_start: int, table_size: int):
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

    def _load_symbol_table(self) -> List[Symbol]:
        table = []
        for act in self.actions:
            if act.item:
                sym = Symbol.from_values(act.item, act.vmaddr, external=True, ordinal=act.libname)
                table.append(sym)
                self.lookup_table[act.vmaddr] = sym
        return table

    def _create_action_list(self) -> List[action]:
        actions = []
        for bind_command in self.import_stack:
            segment = list(self.image.segments.values())[bind_command.seg_index]
            vm_address = segment.vm_address + bind_command.seg_offset
            try:
                lib = self.image.linked_images[bind_command.lib_ordinal - 1].install_name
            except IndexError:
                lib = str(bind_command.lib_ordinal)
            item = bind_command.name
            actions.append(action(vm_address & 0xFFFFFFFFF, lib, item))
        return actions

    def _load_binding_info(self, table_start: int, table_size: int) -> List[record]:
        read_address = table_start
        import_stack = []
        threaded_stack = []
        uses_threaded_bind = False
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
                read_address += 1

                if binding_opcode == BINDING_OPCODE.THREADED:
                    if value == BIND_SUBOPCODE_THREADED_SET_BIND_ORDINAL_TABLE_SIZE_ULEB:
                        a_table_size, read_address = self.image.decode_uleb128(read_address)
                        uses_threaded_bind = True
                    elif value == BIND_SUBOPCODE_THREADED_APPLY:
                        pass

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
                    if not uses_threaded_bind:
                        import_stack.append(
                            record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend,
                                   special_dylib))
                        seg_offset += 8
                    else:
                        threaded_stack.append(
                            record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend,
                                   special_dylib))
                        seg_offset += 8

        return import_stack
