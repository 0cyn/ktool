
from collections import namedtuple

struct = namedtuple("struct", ["struct", "sizes"])

symtab_entry = namedtuple("symtab_entry", ["off", "str_index", "type", "sect_index", "desc", "value"])
symtab_entry_t = struct(symtab_entry, [4, 1, 1, 2, 8])


def sizeof(t: struct):
    assert isinstance(t, struct)
    return sum(t.sizes)