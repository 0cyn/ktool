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

from enum import IntEnum, Enum
from collections import namedtuple

from kmacho import (
    MH_FLAGS,
    MH_FILETYPE,
    LOAD_COMMAND
)

from .util import log
from .macho import _VirtualMemoryMap, Segment
from .structs import *


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
                    library.binding_table = BindingTable(library)

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

        self.platform = None

        self.allowed_clients = []

        self.rpath = None

        self.minos = None
        self.sdk_version = None
        self.binding_table = None

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

    def load_struct(self, address: int, struct_type: struct, vm=False, section_name=None, endian="little"):
        """
        Load a struct (struct_type_t) from a location and return the processed object

        :param address: Address to load struct from
        :param struct_type: type of struct (e.g. dyld_header_t)
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

    def increase_header_pad(self, amount):

        first_segment_file_addr = 0xFFFFFFFF

        for cmd in self.macho_header.load_commands:
            if isinstance(cmd, segment_command_64):
                segment = Segment(self, cmd)
                if 'PAGEZERO' in segment.name:
                    continue
                new_seg_file_addr = segment.file_address + amount if segment.file_address != 0 else 0
                new_seg_vm_addr = segment.vm_address + amount
                seg_raw = segment.cmd.raw
                nsfa_bytes = new_seg_file_addr.to_bytes(8, byteorder='little')
                ba_seg_raw = bytearray(seg_raw)
                ba_seg_raw = ba_seg_raw[0:40] + bytearray(nsfa_bytes) + ba_seg_raw[48:]
                raw_array = ba_seg_raw

                sections = segment.sections
                for _, sect in sections.items():
                    first_segment_file_addr = min(first_segment_file_addr, sect.cmd.offset)
                    sect_cmd = sect.cmd
                    sect_raw = sect_cmd.raw
                    ba_sect_raw = bytearray(sect_raw)
                    new_sect_file_addr = sect_cmd.offset + amount
                    new_sect_vm_addr = sect_cmd.addr + amount
                    nsectfa = new_sect_file_addr.to_bytes(4, byteorder='little')
                    ba_sect_raw = ba_sect_raw[0:48] + bytearray(nsectfa) + ba_sect_raw[52:]
                    raw_array = raw_array + ba_sect_raw

                raw = bytes(raw_array)

                self.slice.patch(cmd.off, raw)

            if isinstance(cmd, symtab_command):
                stc_raw = bytearray(cmd.raw)
                nsto = bytearray((cmd.symoff + amount).to_bytes(4, byteorder='little'))
                nstto = bytearray((cmd.stroff + amount).to_bytes(4, byteorder='little'))
                stc_raw = stc_raw[:8] + nsto + stc_raw[12:16] + nstto + stc_raw[20:]

                self.slice.patch(cmd.off, bytes(stc_raw))

            if isinstance(cmd, dyld_info_command):
                dic_raw = bytearray(cmd.raw)

                new_rebase_off = bytearray((cmd.rebase_off + amount).to_bytes(4, byteorder='little'))
                new_bind_off = bytearray((cmd.bind_off + amount).to_bytes(4, byteorder='little'))
                new_weak_bind_off = bytearray((cmd.weak_bind_off + amount).to_bytes(4, byteorder='little'))
                new_lazy_bind_off = bytearray((cmd.lazy_bind_off + amount).to_bytes(4, byteorder='little'))
                new_export_off = bytearray((cmd.export_off + amount).to_bytes(4, byteorder='little'))

                dic_raw = dic_raw[0:8] + new_rebase_off + dic_raw[12:16] + new_bind_off + dic_raw[20:24] + new_weak_bind_off + dic_raw[28:32] + new_lazy_bind_off + dic_raw[36:40] + new_export_off + dic_raw[44:]

                self.slice.patch(cmd.off, bytes(dic_raw))

            if isinstance(cmd, dysymtab_command):
                dstc_raw = bytearray(cmd.raw)

                ntocoff = bytearray((cmd.tocoff + amount).to_bytes(4, byteorder='little')) if cmd.tocoff > 0 else bytearray(b'\x00\x00\x00\x00')
                nmodtaboff = bytearray((cmd.modtaboff + amount).to_bytes(4, byteorder='little')) if cmd.modtaboff > 0 else bytearray(b'\x00\x00\x00\x00')
                nextrefsymoff = bytearray((cmd.extrefsymoff + amount).to_bytes(4, byteorder='little')) if cmd.extrefsymoff > 0 else bytearray(b'\x00\x00\x00\x00')
                nindirsymoff = bytearray((cmd.indirectsymoff + amount).to_bytes(4, byteorder='little')) if cmd.indirectsymoff > 0 else bytearray(b'\x00\x00\x00\x00')
                nextreloff = bytearray((cmd.extreloff + amount).to_bytes(4, byteorder='little')) if cmd.extreloff > 0 else bytearray(b'\x00\x00\x00\x00')
                nlocreloff = bytearray((cmd.locreloff + amount).to_bytes(4, byteorder='little')) if cmd.locreloff > 0 else bytearray(b'\x00\x00\x00\x00')

                dstc_raw = dstc_raw[:32] + ntocoff + dstc_raw[36:40] + nmodtaboff + dstc_raw[44:48] + nextrefsymoff + dstc_raw[52:56] + nindirsymoff + dstc_raw[60:64] + nextreloff + dstc_raw[68:72] + nlocreloff + dstc_raw[76:]

                self.slice.patch(cmd.off, bytes(dstc_raw))

            if isinstance(cmd, linkedit_data_command):
                patched = patch_field(cmd, linkedit_data_command_t, 2, cmd.dataoff+amount)
                self.slice.patch(cmd.off, patched)

        after_bytes = self.slice.full_bytes_for_slice()[first_segment_file_addr:]
        new_after_bytes_prefix = b'\x00' * amount
        new_after_bytes = new_after_bytes_prefix + after_bytes
        self.slice.patch(first_segment_file_addr, new_after_bytes_prefix)
        self.slice.patch(first_segment_file_addr + len(new_after_bytes_prefix), after_bytes)


    def rm_load_command(self, index):
        b_load_cmd = self.macho_header.load_commands.pop(index)

        off = b_load_cmd.off + b_load_cmd.cmdsize
        after_bytes = self.macho_header.raw_bytes()[off:self.macho_header.dyld_header.loadsize + 32]

        self.slice.patch(b_load_cmd.off, after_bytes)
        self.slice.patch(self.macho_header.dyld_header.loadsize + 32 - b_load_cmd.cmdsize, b'\x00'*b_load_cmd.cmdsize)

        nd_header_magic = self.macho_header.dyld_header.header
        nd_cputype = self.macho_header.dyld_header.cputype
        nd_cpusub = self.macho_header.dyld_header.cpu_subtype
        nd_filetype = self.macho_header.dyld_header.filetype
        nd_loadcnt = self.macho_header.dyld_header.loadcnt - 1
        nd_loadsize = self.macho_header.dyld_header.loadsize - b_load_cmd.cmdsize
        nd_flags = self.macho_header.dyld_header.flags
        nd_void = self.macho_header.dyld_header.void

        nd_hc = assemble_lc(dyld_header_t, [nd_header_magic, nd_cputype, nd_cpusub, nd_filetype, nd_loadcnt, nd_loadsize, nd_flags, nd_void])
        nd_hc_raw = nd_hc.raw

        self.slice.patch(self.macho_header.dyld_header.off, nd_hc_raw)
        self.macho_header.dyld_header = nd_hc

    def insert_lc(self, struct_t, lc, fields, index=-1):
        load_cmd = assemble_lc(struct_t, lc, fields)

        off = sizeof(dyld_header_t)
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

        nd_header_magic = self.macho_header.dyld_header.header
        nd_cputype = self.macho_header.dyld_header.cputype
        nd_cpusub = self.macho_header.dyld_header.cpu_subtype
        nd_filetype = self.macho_header.dyld_header.filetype
        nd_loadcnt = self.macho_header.dyld_header.loadcnt + 1
        nd_loadsize = self.macho_header.dyld_header.loadsize + size
        nd_flags = self.macho_header.dyld_header.flags
        nd_void = self.macho_header.dyld_header.void

        nd_hc = assemble_lc(dyld_header_t, [nd_header_magic, nd_cputype, nd_cpusub, nd_filetype, nd_loadcnt, nd_loadsize, nd_flags, nd_void])
        nd_hc_raw = nd_hc.raw

        self.slice.patch(self.macho_header.dyld_header.off, nd_hc_raw)
        self.macho_header.dyld_header = nd_hc


    def insert_lc_with_suf(self, struct_t, lc, fields, suffix, index=-1):
        load_cmd = assemble_lc_with_suffix(struct_t, lc, fields, suffix)

        off = sizeof(dyld_header_t)
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

        nd_header_magic = self.macho_header.dyld_header.header
        nd_cputype = self.macho_header.dyld_header.cputype
        nd_cpusub = self.macho_header.dyld_header.cpu_subtype
        nd_filetype = self.macho_header.dyld_header.filetype
        nd_loadcnt = self.macho_header.dyld_header.loadcnt + 1
        nd_loadsize = self.macho_header.dyld_header.loadsize + size
        nd_flags = self.macho_header.dyld_header.flags
        nd_void = self.macho_header.dyld_header.void

        nd_hc = assemble_lc(dyld_header_t, [nd_header_magic, nd_cputype, nd_cpusub, nd_filetype, nd_loadcnt, nd_loadsize, nd_flags, nd_void])
        nd_hc_raw = nd_hc.raw

        self.slice.patch(self.macho_header.dyld_header.off, nd_hc_raw)
        self.macho_header.dyld_header = nd_hc


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
        self.dyld_header: dyld_header = macho_slice.load_struct(offset, dyld_header_t)
        self.filetype = MH_FILETYPE(self.dyld_header.filetype)
        self.flags = []
        for flag in MH_FLAGS:
            if self.dyld_header.flags & flag.value:
                self.flags.append(flag)
        self.load_commands = []
        self._process_load_commands(macho_slice)

    def raw_bytes(self):
        size = sizeof(dyld_header_t)
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
                load_cmd = macho_slice.load_struct(read_address, LOAD_COMMAND_TYPEMAP[LOAD_COMMAND(cmd)])
            except ValueError:
                unk_lc = macho_slice.load_struct(read_address, unk_command_t)
                load_cmd = unk_lc
            except KeyError:
                unk_lc = macho_slice.load_struct(read_address, unk_command_t)
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
        read_address = cmd.off + sizeof(dylib_command_t)
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
            symbol_table.append(self.library.load_struct(read_address + sizeof(symtab_entry_t) * i, symtab_entry_t))

        table = []
        for sym in symbol_table:
            symbol = Symbol(self.library, self.cmd, sym)
            # log.debug(f'Symbol Table: Loaded symbol:{symbol.name} ordinal:{symbol.ordinal} type:{symbol.type}')
            table.append(symbol)
            if sym.type == 0xf:
                self.ext.append(symbol)
        return table


action = namedtuple("action", ["vmaddr", "libname", "item"])
record = namedtuple("record", [
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
    def __init__(self, library):
        """
        Pass a library to be processed

        :param library: Library to be processed
        :type library: Library
        """
        self.library = library
        self.import_stack = self._load_binding_info()
        self.actions = self._create_action_list()
        self.lookup_table = {}
        self.link_table = {}
        self.symbol_table = self._load_symbol_table()
        self.rebase_table = self._load_rebase_info()

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

    def _load_rebase_info(self):
        read_addr = self.library.info.rebase_off


    def _load_binding_info(self):
        lib = self.library
        read_address = lib.info.bind_off
        import_stack = []
        while True:
            if read_address - lib.info.bind_size >= lib.info.bind_off:
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
                read_address += 1

                if binding_opcode == BINDING_OPCODE.DONE:
                    import_stack.append(
                        record(seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
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
                        record(seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
                    seg_offset += 8
                    o, read_address = self.library.decode_uleb128(read_address)
                    seg_offset += o

                elif binding_opcode == BINDING_OPCODE.DO_BIND_ADD_ADDR_IMM_SCALED:
                    import_stack.append(
                        record(seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
                    seg_offset = seg_offset + (value * 8) + 8

                elif binding_opcode == BINDING_OPCODE.DO_BIND_ULEB_TIMES_SKIPPING_ULEB:
                    count, read_address = self.library.decode_uleb128(read_address)
                    skip, read_address = self.library.decode_uleb128(read_address)

                    for i in range(0, count):
                        import_stack.append(
                            record(seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
                        seg_offset += skip + 8

                elif binding_opcode == BINDING_OPCODE.DO_BIND:
                    import_stack.append(
                        record(seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
                    seg_offset += 8

        return import_stack


class REBASE_OPCODE(IntEnum):
    DONE = 0x0
    SET_TYPE_IMM = 0x10
    SET_SEGMENT_AND_OFFSET_ULEB = 0x20
    ADD_ADDR_ULEB = 0x30
    ADD_ADDR_IMM_SCALED = 0x40
    DO_REBASE_IMM_TIMES = 0x50
    DO_REBASE_ULEB_TIMES = 0x60
    DO_REBASE_ADD_ADDR_ULEB = 0x70
    DO_REBASE_ULEB_TIMES_SKIPPING_ULEB = 0x80


class BINDING_OPCODE(IntEnum):
    DONE = 0x0
    SET_DYLIB_ORDINAL_IMM = 0x10
    SET_DYLIB_ORDINAL_ULEB = 0x20
    SET_DYLIB_SPECIAL_IMM = 0x30
    SET_SYMBOL_TRAILING_FLAGS_IMM = 0x40
    SET_TYPE_IMM = 0x50
    SET_ADDEND_SLEB = 0x60
    SET_SEGMENT_AND_OFFSET_ULEB = 0x70
    ADD_ADDR_ULEB = 0x80
    DO_BIND = 0x90
    DO_BIND_ADD_ADDR_ULEB = 0xa0
    DO_BIND_ADD_ADDR_IMM_SCALED = 0xb0
    DO_BIND_ULEB_TIMES_SKIPPING_ULEB = 0xc0
