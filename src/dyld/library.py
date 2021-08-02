from enum import Enum

from macho.segment import Segment

from dyld.binding import BindingProcessor

from macho._vm import _VirtualMemoryMap
from macho.structs import *
from collections import namedtuple


class LibraryHeader:
    """
    This class represents the Mach-O Header
    It contains the basic header info along with all load commands within it.

    It doesn't handle complex abstraction logic, it simply loads in the load commands as their raw structs
    """
    def __init__(self, slice):
        offset = 0
        self.dyld_header: dyld_header = slice.load_struct(offset, dyld_header_t)
        self.load_commands = []
        self._process_load_commands(slice)

    def _process_load_commands(self, slice):
        """
        This function takes the raw file and parses through its load commands

        :param fd: file
        :return:
        """

        # Start address of the load commands.
        ea = self.dyld_header.off + 0x20

        # Loop through the dyld_header by load command count
        # possibly this could be modified to check for other load commands
        #       as a rare obfuscation technique involves fucking with these to screw with RE tools.

        for i in range(1, self.dyld_header.loadcnt):
            cmd = slice.get_at(ea, 4)
            try:
                load_cmd = slice.load_struct(ea, LOAD_COMMAND_TYPEMAP[cmd])
            except KeyError as ex:
                unk_lc = slice.load_struct(ea, unk_command_t)
                load_cmd = unk_lc

            self.load_commands.append(load_cmd)
            ea += load_cmd.cmdsize


class Library:
    """
    This class represents the Mach-O Binary as a whole.

    It's the root object in the massive tree of information we're going to build up about the binary

    This is an abstracted version, other classes will handle the raw struct interaction;
        here, we facilitate that interaction within those classes and generate our abstract representation

    Calling __init__ on this class will kickstart the full process.
    """
    def __init__(self, slice):
        self.macho_header = LibraryHeader(slice)
        self.slice = slice

        self.linked = []
        self.segments = {}

        self.vm = _VirtualMemoryMap(slice)

        self.info = None
        self.dylib = None
        self.uuid = None

        self.platform = None

        self.minos = None
        self.sdk_version = None
        self.binding_actions = None

        self.symtab = None


    def get_bytes(self, offset: int, length: int, vm=False, sectname=None):
        if vm:
            offset = self.vm.get_file_address(offset, sectname)
        return self.slice.get_at(offset, length)

    def load_struct(self, addr: int, struct_type: struct, vm=False, sectname=None, endian="little"):
        if vm:
            addr = self.vm.get_file_address(addr, sectname)
        return self.slice.load_struct(addr, struct_type, endian)

    def get_str_at(self, addr: int, count: int, vm=False, sectname=None):
        if vm:
            addr = self.vm.get_file_address(addr, sectname)
        return self.slice.get_str_at(addr, count)

    def get_cstr_at(self, addr: int, limit: int = 0, vm=False, sectname=None):
        if vm:
            addr = self.vm.get_file_address(addr, sectname)
        return self.slice.get_cstr_at(addr, limit)

    def decode_uleb128(self, readHead: int):
        return self.slice.decode_uleb128(readHead)

