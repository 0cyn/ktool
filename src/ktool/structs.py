from collections import namedtuple
from typing import NamedTuple

struct = namedtuple("struct", ["struct", "sizes"])

symtab_entry = namedtuple("symtab_entry", ["off", "str_index", "type", "sect_index", "desc", "value"])
symtab_entry_t = struct(symtab_entry, [4, 1, 1, 2, 8])


def sizeof(t: struct):
    assert isinstance(t, struct)
    return sum(t.sizes)


class fat_header(NamedTuple):
    off: int
    magic: int
    nfat_archs: int


fat_header_t = struct(fat_header, [4, 4])


class fat_arch(NamedTuple):
    off: int
    cputype: int
    cpusubtype: int
    offset: int
    size: int
    align: int


fat_arch_t = struct(fat_arch, [4, 4, 4, 4, 4])


class dyld_header(NamedTuple):
    off: int
    header: int
    cputype: int
    cpu_subtype: int
    filetype: int
    loadcnt: int
    loadsize: int
    flags: int
    void: int


dyld_header_t = struct(dyld_header, [4, 4, 4, 4, 4, 4, 4, 4])


class dylib(NamedTuple):
    off: int
    name: int
    timestamp: int
    current_version: int
    compatibility_version: int


dylib_t = struct(dylib, [4, 4, 4, 4])


class unk_command(NamedTuple):
    off: int
    cmd: int
    cmdsize: int


unk_command_t = struct(unk_command, [4, 4])


class dylib_command(NamedTuple):
    off: int
    cmd: int
    cmdsize: int
    dylib: int


dylib_command_t = struct(dylib_command, [4, 4, 16])


class dylinker_command(NamedTuple):
    off: int
    cmd: int
    cmdsize: int
    name: int


dylinker_command_t = struct(dylinker_command, [4, 4, 4])


class entry_point_command(NamedTuple):
    off: int
    cmd: int
    cmdsize: int
    entryoff: int
    stacksize: int


entry_point_command_t = struct(entry_point_command, [4, 4, 8, 8])


class rpath_command(NamedTuple):
    off: int
    cmd: int
    cmdsize: int
    path: int


rpath_command_t = struct(rpath_command, [4, 4, 4])


class dyld_info_command(NamedTuple):
    off: int
    cmd: int
    cmdsize: int
    rebase_off: int
    rebase_size: int
    bind_off: int
    bind_size: int
    weak_bind_off: int
    weak_bind_size: int
    lazy_bind_off: int
    lazy_bind_size: int
    export_off: int
    export_size: int


dyld_info_command_t = struct(dyld_info_command, [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4])


class symtab_command(NamedTuple):
    off: int
    cmd: int
    cmdsize: int
    symoff: int
    nsyms: int
    stroff: int
    strsize: int


symtab_command_t = struct(symtab_command, [4, 4, 4, 4, 4, 4])


class dysymtab_command(NamedTuple):
    off: int
    cmd: int
    cmdsize: int
    ilocalsym: int
    nlocalsym: int
    iextdefsym: int
    nextdefsym: int
    tocoff: int
    ntoc: int
    modtaboff: int
    nmodtab: int
    extrefsymoff: int
    nextrefsyms: int
    indirectsymoff: int
    nindirectsyms: int
    extreloff: int
    nextrel: int
    locreloff: int
    nlocrel: int


dysymtab_command_t = struct(dysymtab_command, [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4])


class uuid_command(NamedTuple):
    off: int
    cmd: int
    cmdsize: int
    uuid: int


uuid_command_t = struct(uuid_command, [4, 4, 16])


class build_version_command(NamedTuple):
    off: int
    cmd: int
    cmdsize: int
    platform: int
    minos: int
    sdk: int
    ntools: int


build_version_command_t = struct(build_version_command, [4, 4, 4, 4, 4, 4])


class source_version_command(NamedTuple):
    off: int
    cmd: int
    cmdsize: int
    version: int


source_version_command_t = struct(source_version_command, [4, 4, 8])


class sub_client_command(NamedTuple):
    off: int
    cmd: int
    cmdsize: int
    offset: int


sub_client_command_t = struct(sub_client_command, [4, 4, 4])


class linkedit_data_command(NamedTuple):
    off: int
    cmd: int
    cmdsize: int
    dataoff: int
    datasize: int


linkedit_data_command_t = struct(linkedit_data_command, [4, 4, 4, 4])


class segment_command_64(NamedTuple):
    off: int
    cmd: int
    cmdsize: int
    segname: int
    vmaddr: int
    vmsize: int
    fileoff: int
    filesize: int
    maxprot: int
    initprot: int
    nsects: int
    flags: int


segment_command_64_t = struct(segment_command_64, [4, 4, 16, 8, 8, 8, 8, 4, 4, 4, 4])


class section_64(NamedTuple):
    off: int
    sectname: int
    segname: int
    addr: int
    size: int
    offset: int
    align: int
    reloff: int
    nreloc: int
    flags: int
    void1: int
    void2: int
    void3: int


section_64_t = struct(section_64, [16, 16, 8, 8, 4, 4, 4, 4, 4, 4, 4, 4])

LOAD_COMMAND_TYPEMAP = {
    0x2: symtab_command_t,
    0xB: dysymtab_command_t,
    0xC: dylib_command_t,
    0xD: dylib_command_t,
    0xe: dylinker_command_t,
    0x14: sub_client_command_t,
    0x19: segment_command_64_t,
    0x1B: uuid_command_t,
    0x1D: linkedit_data_command_t,
    0x1E: linkedit_data_command_t,
    0x2A: source_version_command_t,
    0x26: linkedit_data_command_t,
    0x29: linkedit_data_command_t,
    0x32: build_version_command_t,
    0x80000018: dylib_command_t,
    0x80000022: dyld_info_command_t,
    0x80000028: entry_point_command_t,
    0x8000001C: rpath_command_t,
}

class objc2_class(NamedTuple):
    off: int
    isa: int
    superclass: int
    cache: int
    vtable: int
    info: int


objc2_class_t = struct(objc2_class, [8, 8, 8, 8, 8])

class objc2_class_ro(NamedTuple):
    off: int
    flags: int
    ivar_base_start: int
    ivar_base_size: int
    reserved: int
    ivar_lyt: int
    name: int
    base_meths: int
    base_prots: int
    ivars: int
    weak_ivar_lyt: int
    base_props: int


objc2_class_ro_t = struct(objc2_class_ro, [4, 4, 4, 4, 8, 8, 8, 8, 8, 8, 8])


class objc2_meth(NamedTuple):
    off: int
    selector: int
    types: int
    imp: int


objc2_meth_t = struct(objc2_meth, [8, 8, 8])
objc2_meth_list_entry_t = struct(objc2_meth, [4, 4, 4])


class objc2_meth_list(NamedTuple):
    off: int
    entrysize: int
    count: int


objc2_meth_list_t = struct(objc2_meth_list, [4, 4])


class objc2_prop_list(NamedTuple):
    off: int
    entrysize: int
    count: int


objc2_prop_list_t = struct(objc2_prop_list, [4, 4])


class objc2_prop(NamedTuple):
    off: int
    name: int
    attr: int


objc2_prop_t = struct(objc2_prop, [8, 8])


class objc2_prot_list(NamedTuple):
    off: int
    cnt: int


objc2_prot_list_t = struct(objc2_prot_list, [8])


class objc2_prot(NamedTuple):
    off: int
    isa: int
    name: int
    prots: int
    inst_meths: int
    class_meths: int
    opt_inst_meths: int
    opt_class_meths: int
    inst_props: int
    cb: int
    flags: int


objc2_prot_t = struct(objc2_prot, [8, 8, 8, 8, 8, 8, 8, 8, 4, 4])


class objc2_ivar_list(NamedTuple):
    off: int
    entrysize: int
    cnt: int

objc2_ivar_list_t = struct(objc2_ivar_list, [4, 4])


class objc2_ivar(NamedTuple):
    off: int
    offs: int
    name: int
    type: int
    align: int
    size: int


objc2_ivar_t = struct(objc2_ivar, [8, 8, 8, 4, 4])


class objc2_category(NamedTuple):
    off: int
    name: int
    s_class: int
    inst_meths: int
    class_meths: int
    prots: int
    props: int


objc2_category_t = struct(objc2_category, [8, 8, 8, 8, 8, 8])
