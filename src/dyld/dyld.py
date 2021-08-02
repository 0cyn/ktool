from macho.segment import Segment
from macho.structs import *
from .binding import BindingProcessor
from .enums import *
from .dylib import ExternalDylib
from .library import Library
from .symtab import SymbolTable
from collections import namedtuple


os_version = namedtuple("os_version", ["x", "y", "z"])


class Dyld:

    @staticmethod
    def load(slice):
        library = Library(slice)
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
                binding = BindingProcessor(library)
                library.binding_actions = binding.actions

            if isinstance(cmd, symtab_command):
                library.symtab = SymbolTable(library, cmd)

            if isinstance(cmd, uuid_command):
                library.uuid = cmd.uuid

            # https://www.rubydoc.info/gems/ruby-macho/0.1.8/MachO/SourceVersionCommand

            if isinstance(cmd, build_version_command):
                library.platform = PlatformType(cmd.platform)
                library.minos = os_version(x=library.get_bytes(cmd.off + 14, 2), y=library.get_bytes(cmd.off + 13, 1), z=library.get_bytes(cmd.off + 12, 1))
                library.sdk_version = os_version(x=library.get_bytes(cmd.off + 18, 2), y=library.get_bytes(cmd.off + 17, 1), z=library.get_bytes(cmd.off + 16, 1))

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
