
# Cell
from collections import namedtuple

# Cell
"""
C Struct representation in Python
I have done what I can to make the syntax used similar to C syntax

The `struct` variable is a subclass of Tuple which contains a struct 'typedef' and a list of byte sizes for each field in the struct, in order.
"""
struct = namedtuple("struct", ["struct", "sizes"])

# Cell
"""
DYLD STRUCTS
VALUES OF FIELDS SHOULD LINE UP WITH THOSE IN DYLD SOURCE
"""

fat_header = namedtuple("fat_header", ["off", "magic", "nfat_archs"])
fat_header_t = struct(fat_header, [4, 4])

fat_arch = namedtuple("fat_arch", ["off", "cputype", "cpusubtype", "offset", "size", "align"])
fat_arch_t = struct(fat_arch, [4, 4, 4, 4, 4])

dyld_header = namedtuple("dyld_header", ["off", "header", "cpu", "cput", "filetype", "loadcnt", "loadsze", "flags", "void"])
dyld_header_t = struct(dyld_header, [4, 4, 4, 4, 4, 4, 4, 4])

dylib = namedtuple("dylib", ["off", "name", "timestamp", "current_version", "compatibility_version"])
dylib_t = struct(dylib, [4,4,4,4])

unk_command = namedtuple("unk_command", ["off", "cmd", "cmdsize"])
unk_command_t = struct(unk_command, [4, 4])

dylib_command = namedtuple("dylib_command", ["off", "cmd", "cmdsize", "dylib"])
dylib_command_t = struct(dylib_command, [4, 4, 16])

dylinker_command = namedtuple("dylinker_command", ["off", "cmd", "cmdsize", "name"])
dylinker_command_t = struct(dylinker_command, [4, 4, 4])

entry_point_command = namedtuple("entry_point_command", ["off", "cmd", "cmdsize", "entryoff", "stacksize"])
entry_point_command_t = struct(entry_point_command, [4, 4, 8, 8])

rpath_command = namedtuple("rpath_command", ["off", "cmd", "cmdsize", "path"])
rpath_command_t = struct(rpath_command, [4, 4, 4])

dyld_info_command = namedtuple("dyld_info_command", ["off", "cmd", "cmdsize", "rebase_off", "rebase_size", "bind_off", "bind_size", "weak_bind_off", "weak_bind_size", "lazy_bind_off", "lazy_bind_size", "export_off", "export_size"])
dyld_info_command_t = struct(dyld_info_command, [4,4,4,4,4,4,4,4,4,4,4,4])

symtab_command = namedtuple("symtab_command", ["off", "cmd", "cmdsize", "symoff", "nsyms", "stroff", "strsize"])
symtab_command_t = struct(symtab_command, [4, 4, 4, 4, 4, 4])

dysymtab_command = namedtuple("dysymtab_command", ["off", "cmd", "cmdsize", "ilocalsym", "nlocalsym", "iextdefsym", "nextdefsym", "tocoff", "ntoc", "modtaboff", "nmodtab", "extrefsymoff", "nextrefsyms", "inderectsymoff", "nindirectsyms", "extreloff", "nextrel", "locreloff", "nlocrel"])
dysymtab_command_t = struct(dysymtab_command, [4,4,4,4, 4,4,4,4 ,4,4,4,4 ,4,4,4,4,4,4])

uuid_command = namedtuple("uuid_command", ["off", "cmd", "cmdsize", "uuid"])
uuid_command_t = struct(uuid_command, [4, 4, 16])

build_version_command = namedtuple("build_version_command", ["off", "cmd", "cmdsize", "platform", "minos", "sdk", "ntools"])
build_version_command_t = struct(build_version_command, [4,4,4,4,4,4])

source_version_command = namedtuple("source_version_command", ["off", "cmd", "cmdsize", "version"])
source_version_command_t = struct(source_version_command, [4, 4, 8])

linkedit_data_command = namedtuple("linkedit_data_command", ["off", "cmd", "cmdsize", "dataoff", "datasize"])
linkedit_data_command_t = struct(linkedit_data_command, [4, 4, 4, 4])

segment_command_64 = namedtuple("segment_command_64", ["off", "cmd", "cmdsize", "segname", "vmaddr", "vmsize", "fileoff", "filesize", "maxprot", "initprot", "nsects", "flags"])
segment_command_64_t = struct(segment_command_64, [4, 4, 16, 8, 8, 8, 8, 4, 4, 4, 4])

section_64 = namedtuple("section_64", ["off", "sectname", "segname", "addr", "size", "offset", "align", "reloff", "nreloc", "flags", "void1", "void2", "void3"])
section_64_t = struct(section_64, [16, 16, 8, 8, 4, 4, 4, 4, 4, 4, 4, 4])


# Cell


"""
LOAD COMMAND MAP
Maps Mach-O Load Commands to respective structs
"""
LOAD_COMMAND_TYPEMAP = {
    0x19: segment_command_64_t,
    0xD: dylib_command_t,
    0x80000022: dyld_info_command_t,
    0x80000028: entry_point_command_t,
    0x8000001C: rpath_command_t,
    0x2: symtab_command_t,
    0xB: dysymtab_command_t,
    0xe: dylinker_command_t,
    0x1B: uuid_command_t,
    0x32: build_version_command_t,
    0x2A: source_version_command_t,
    0xC: dylib_command_t,
    0x26: linkedit_data_command_t,
    0x29: linkedit_data_command_t,
    0x1D: linkedit_data_command_t,
    0x1E: linkedit_data_command_t,
}

def sizeof(t: struct):
    return sum(t.sizes)