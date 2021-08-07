from collections import namedtuple
from enum import IntEnum, Enum

import ktool.structs
from ktool.structs import symtab_entry_t, dyld_header, dyld_header_t, unk_command_t, dylib_command, dylib_command_t, \
    dyld_info_command, symtab_command, uuid_command, build_version_command, segment_command_64, LOAD_COMMAND_TYPEMAP, \
    sizeof, struct, sub_client_command
from ktool.macho import _VirtualMemoryMap, Segment


class Dyld:

    @staticmethod
    def load(macho_slice):
        library = Library(macho_slice)
        Dyld.parse_load_commands(library)
        return library

    @staticmethod
    def parse_load_commands(library):
        for cmd in library.macho_header.load_commands:
            # my structLoad function *ALWAYS* saves the offset on-disk to the .off field, regardless of the struct
            #   loaded.
            ea = cmd.off

            if isinstance(cmd, segment_command_64):
                segment = Segment(library, cmd)
                library.vm.add_segment(segment)
                library.segments[segment.name] = segment

            if isinstance(cmd, dyld_info_command):
                library.info = cmd
                library.binding_table = BindingTable(library)

            if isinstance(cmd, symtab_command):
                library.symbol_table = SymbolTable(library, cmd)

            if isinstance(cmd, uuid_command):
                library.uuid = cmd.uuid

            if isinstance(cmd, sub_client_command):
                string = library.get_cstr_at(cmd.off + cmd.offset)
                library.allowed_clients.append(string)

            # https://www.rubydoc.info/gems/ruby-macho/0.1.8/MachO/SourceVersionCommand

            if isinstance(cmd, build_version_command):
                library.platform = PlatformType(cmd.platform)
                library.minos = os_version(x=library.get_bytes(cmd.off + 14, 2), y=library.get_bytes(cmd.off + 13, 1),
                                           z=library.get_bytes(cmd.off + 12, 1))
                library.sdk_version = os_version(x=library.get_bytes(cmd.off + 18, 2),
                                                 y=library.get_bytes(cmd.off + 17, 1),
                                                 z=library.get_bytes(cmd.off + 16, 1))

            if isinstance(cmd, dylib_command):
                ea += sizeof(dylib_command_t)
                if cmd.cmd == 0xD:  # local
                    library.dylib = ExternalDylib(library, cmd)
                else:
                    library.linked.append(ExternalDylib(library, cmd))

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

    Calling __init__ on this class will kickstart the full process.
    """

    def __init__(self, macho_slice):
        self.macho_header = LibraryHeader(macho_slice)
        self.slice = macho_slice

        self.linked = []
        self.segments = {}

        self.vm = _VirtualMemoryMap(macho_slice)

        self.info = None
        self.dylib = None
        self.uuid = None

        self.platform = None

        self.allowed_clients = []

        self.minos = None
        self.sdk_version = None
        self.binding_table = None

        self.symbol_table = None

    def get_bytes(self, offset: int, length: int, vm=False, section_name=None):
        if vm:
            offset = self.vm.get_file_address(offset, section_name)
        return self.slice.get_at(offset, length)

    def load_struct(self, address: int, struct_type: struct, vm=False, section_name=None, endian="little"):
        if vm:
            address = self.vm.get_file_address(address, section_name)
        return self.slice.load_struct(address, struct_type, endian)

    def get_str_at(self, address: int, count: int, vm=False, section_name=None):
        if vm:
            address = self.vm.get_file_address(address, section_name)
        return self.slice.get_str_at(address, count)

    def get_cstr_at(self, address: int, limit: int = 0, vm=False, section_name=None):
        if vm:
            address = self.vm.get_file_address(address, section_name)
        return self.slice.get_cstr_at(address, limit)

    def decode_uleb128(self, readHead: int):
        return self.slice.decode_uleb128(readHead)


class ExternalDylib:
    def __init__(self, source_library, cmd):
        self.source_library = source_library
        self.install_name = self._get_name(cmd)
        self.local = cmd.cmd == 0xD

    def _get_name(self, cmd):
        ea = cmd.off + sizeof(dylib_command_t)
        return self.source_library.get_cstr_at(ea)


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


class LibraryHeader:
    """
    This class represents the Mach-O Header
    It contains the basic header info along with all load commands within it.

    It doesn't handle complex abstraction logic, it simply loads in the load commands as their raw structs
    """

    def __init__(self, macho_slice):
        offset = 0
        self.dyld_header: dyld_header = macho_slice.load_struct(offset, dyld_header_t)
        self.load_commands = []
        self._process_load_commands(macho_slice)

    def _process_load_commands(self, macho_slice):
        """
        This function takes the raw slice and parses through its load commands

        :param macho_slice: MachO Library Slice 
        :return:
        """

        # Start address of the load commands.
        ea = self.dyld_header.off + 0x20

        # Loop through the dyld_header by load command count
        # possibly this could be modified to check for other load commands
        #       as a rare obfuscation technique involves fucking with these to screw with RE tools.

        for i in range(1, self.dyld_header.loadcnt):
            cmd = macho_slice.get_at(ea, 4)
            try:
                load_cmd = macho_slice.load_struct(ea, LOAD_COMMAND_TYPEMAP[cmd])
            except KeyError:
                unk_lc = macho_slice.load_struct(ea, unk_command_t)
                load_cmd = unk_lc

            self.load_commands.append(load_cmd)
            ea += load_cmd.cmdsize


class SymbolType(Enum):
    CLASS = 0
    METACLASS = 1
    IVAR = 2
    FUNC = 3
    UNK = 4



class Symbol:
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
    def __init__(self, library, cmd: symtab_command):
        self.library = library
        self.cmd = cmd
        self.ext = []
        self.table = self._load_symbol_table()

    def _load_symbol_table(self):
        symbol_table = []
        ea = self.cmd.symoff
        for i in range(0, self.cmd.nsyms):
            symbol_table.append(self.library.load_struct(ea + sizeof(symtab_entry_t) * i, symtab_entry_t))

        table = []
        for sym in symbol_table:
            symbol = Symbol(self.library, self.cmd, sym)
            table.append(symbol)
            if sym.type == 0xf:
                self.ext.append(symbol)
        return table


action = namedtuple("action", ["vmaddr", "libname", "item"])
record = namedtuple("record",
                    ["seg_index", "seg_offset", "lib_ordinal", "type", "flags", "name", "addend", "special_dylib"])


class BindingTable:
    def __init__(self, library):
        self.library = library
        self.import_stack = self._load_binding_info()
        self.actions = self._create_action_list()
        self.symbol_table = self._load_symbol_table()

    def _load_symbol_table(self):
        table = []
        for act in self.actions:
            if act.item:
                table.append(Symbol(self.library, fullname=act.item, ordinal=act.libname, addr=act.vmaddr))
        return table

    def _create_action_list(self):
        actions = []
        for bind_command in self.import_stack:
            segment = list(self.library.segments.values())[bind_command.seg_index]
            vm_address = segment.vm_address + bind_command.seg_offset
            try:
                lib = self.library.linked[bind_command.lib_ordinal - 1].install_name
            except IndexError:
                lib = str(bind_command.lib_ordinal)
            item = bind_command.name
            actions.append(action(vm_address & 0xFFFFFFFFF, lib, item))
        return actions

    def _load_binding_info(self):
        lib = self.library
        ea = lib.info.bind_off
        import_stack = []
        while True:
            # print(hex(ea))
            if ea - lib.info.bind_size >= lib.info.bind_off:
                break
            seg_index = 0x0
            seg_offset = 0x0
            lib_ordinal = 0x0
            btype = 0x0
            flags = 0x0
            name = ""
            addend = 0x0
            special_dylib = 0x1
            while True:
                # There are 0xc opcodes total
                # Bitmask opcode byte with 0xF0 to get opcode, 0xF to get value
                op = self.library.get_bytes(ea, 1) & 0xF0
                value = self.library.get_bytes(ea, 1) & 0x0F
                ea += 1
                if op == OPCODE.BIND_OPCODE_DONE:
                    import_stack.append(
                        record(seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
                    break
                elif op == OPCODE.BIND_OPCODE_SET_DYLIB_ORDINAL_IMM:
                    lib_ordinal = value
                elif op == OPCODE.BIND_OPCODE_SET_DYLIB_ORDINAL_ULEB:
                    lib_ordinal, bump = self.library.decode_uleb128(ea)
                    ea = bump
                elif op == OPCODE.BIND_OPCODE_SET_DYLIB_SPECIAL_IMM:
                    special_dylib = 0x1
                    lib_ordinal = value
                elif op == OPCODE.BIND_OPCODE_SET_SYMBOL_TRAILING_FLAGS_IMM:
                    flags = value
                    name = self.library.get_cstr_at(ea)
                    ea += len(name)
                    ea += 1
                elif op == OPCODE.BIND_OPCODE_SET_TYPE_IMM:
                    btype = value
                elif op == OPCODE.BIND_OPCODE_SET_ADDEND_SLEB:
                    ea += 1
                elif op == OPCODE.BIND_OPCODE_SET_SEGMENT_AND_OFFSET_ULEB:
                    seg_index = value
                    number, head = self.library.decode_uleb128(ea)
                    seg_offset = number
                    ea = head
                elif op == OPCODE.BIND_OPCODE_ADD_ADDR_ULEB:
                    o, bump = self.library.decode_uleb128(ea)
                    seg_offset += o
                    ea = bump
                elif op == OPCODE.BIND_OPCODE_DO_BIND_ADD_ADDR_ULEB:
                    import_stack.append(
                        record(seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
                    seg_offset += 8
                    o, bump = self.library.decode_uleb128(ea)
                    seg_offset += o
                    ea = bump

                elif op == OPCODE.BIND_OPCODE_DO_BIND_ADD_ADDR_IMM_SCALED:
                    import_stack.append(
                        record(seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
                    seg_offset = seg_offset + (value * 8) + 8
                elif op == OPCODE.BIND_OPCODE_DO_BIND_ULEB_TIMES_SKIPPING_ULEB:
                    t, bump = self.library.decode_uleb128(ea)
                    count = t
                    ea = bump
                    s, bump = self.library.decode_uleb128(ea)
                    skip = s
                    ea = bump
                    for i in range(0, count):
                        import_stack.append(
                            record(seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
                        seg_offset += skip + 8
                elif op == OPCODE.BIND_OPCODE_DO_BIND:
                    import_stack.append(
                        record(seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
                    seg_offset += 8
                else:
                    assert 0 == 1

        return import_stack



class OPCODE(IntEnum):
    BIND_OPCODE_DONE = 0x0
    BIND_OPCODE_SET_DYLIB_ORDINAL_IMM = 0x10
    BIND_OPCODE_SET_DYLIB_ORDINAL_ULEB = 0x20
    BIND_OPCODE_SET_DYLIB_SPECIAL_IMM = 0x30
    BIND_OPCODE_SET_SYMBOL_TRAILING_FLAGS_IMM = 0x40
    BIND_OPCODE_SET_TYPE_IMM = 0x50
    BIND_OPCODE_SET_ADDEND_SLEB = 0x60
    BIND_OPCODE_SET_SEGMENT_AND_OFFSET_ULEB = 0x70
    BIND_OPCODE_ADD_ADDR_ULEB = 0x80
    BIND_OPCODE_DO_BIND = 0x90
    BIND_OPCODE_DO_BIND_ADD_ADDR_ULEB = 0xa0
    BIND_OPCODE_DO_BIND_ADD_ADDR_IMM_SCALED = 0xb0
    BIND_OPCODE_DO_BIND_ULEB_TIMES_SKIPPING_ULEB = 0xc0
