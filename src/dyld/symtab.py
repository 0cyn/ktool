

from macho.structs import *
from dyld.structs import symtab_entry, symtab_entry_t


#symtab_command = namedtuple("symtab_command", ["off", "cmd", "cmdsize", "symoff", "nsyms", "stroff", "strsize"])
#symtab_command_t = struct(symtab_command, [4, 4, 4, 4, 4, 4])

# symtab_entry = namedtuple("symtab_entry", ["off", "str_index", "type", "sect_index", "desc", "value"])
class Symbol:
    def __init__(self, lib, cmd, entry):
        self.name = lib.get_cstr_at(entry.str_index + cmd.stroff)
        self.entry = entry


class SymbolTable:
    def __init__(self, library, cmd: symtab_command):
        self.library = library
        self.cmd = cmd
        self.table = self._load_symbol_table()

    def _load_symbol_table(self):
        symtab = []
        ea = self.cmd.symoff
        for i in range(0, self.cmd.nsyms):
            symtab.append(self.library.load_struct(ea + sizeof(symtab_entry_t)*i, symtab_entry_t))

        table = []
        for sym in symtab:
            table.append(Symbol(self.library, self.cmd, sym))
        return table