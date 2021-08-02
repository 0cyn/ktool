
from macho.structs import *


class ExternalDylib:
    def __init__(self, source_library, cmd):
        self.source_library = source_library
        self.install_name = self._get_name(cmd)
        self.local = cmd.cmd == 0xD

    def _get_name(self, cmd):
        ea = cmd.off + sizeof(dylib_command_t)
        return self.source_library.get_cstr_at(ea)