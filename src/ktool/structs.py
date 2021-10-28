#
#  ktool | ktool
#  structs.py
#
#  This file contains a custom system for representing structures used within a mach-o header
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2021.
#
import math

from kmacho import *

from typing import NamedTuple
from collections import namedtuple

struct = namedtuple("struct", ["struct", "sizes"])

symtab_entry = namedtuple("symtab_entry", ["off", "raw", "str_index", "type", "sect_index", "desc", "value"])
symtab_entry_t = struct(symtab_entry, [4, 1, 1, 2, 8])


def sizeof(t: struct):
    assert isinstance(t, struct)
    return sum(t.sizes)


def patch_field(struc, struct_t: struct, field_index: int, value: int, endian="little"):
    rar = bytearray(struc.raw)
    before_size = sum(struct_t.sizes[:field_index])
    f_size = struct_t.sizes[field_index]
    after_start = before_size + f_size
    return bytes(rar[:before_size] + bytearray(value.to_bytes(f_size, endian)) + rar[after_start:])


def assemble_lc(struct_t, load_command: LOAD_COMMAND, fields, endian="little"):
    ol_fields = fields
    raw_bytes: bytes = b''
    cmd = load_command.value

    cmd_off = 0

    cmdsize = sizeof(LOAD_COMMAND_TYPEMAP[load_command])

    raw_bytes += cmd.to_bytes(4, endian)
    raw_bytes += cmdsize.to_bytes(4, endian)

    for index, field_size in enumerate(struct_t.sizes[2:]):
        original_field = ol_fields[index]
        if not isinstance(original_field, bytes):
            original_field = original_field.to_bytes(field_size, endian)
        raw_bytes += original_field

    cmd_raw = raw_bytes
    fields = [cmd_off, cmd_raw, cmd, cmdsize] + ol_fields

    struct_item = struct_t.struct._make(fields)
    return struct_item


def assemble_lc_with_suffix(struct_t, load_command: LOAD_COMMAND, fields, suffix, endian="little"):
    ol_fields = fields
    raw_bytes: bytes = b''
    cmd = load_command.value

    encoded = suffix.encode('utf-8') + b'\x00'
    cmd_off = 0

    cmdsize = sizeof(LOAD_COMMAND_TYPEMAP[load_command])
    cmdsize += len(encoded)
    cmdsize = 0x8 * math.ceil(cmdsize / 0x8)
    raw_bytes += cmd.to_bytes(4, endian)
    raw_bytes += cmdsize.to_bytes(4, endian)

    for index, field_size in enumerate(struct_t.sizes[2:]):
        original_field = ol_fields[index]
        if not isinstance(original_field, bytes):
            original_field = original_field.to_bytes(field_size, endian)
        raw_bytes += original_field

    raw_bytes += encoded

    ocmdsize = sizeof(LOAD_COMMAND_TYPEMAP[load_command])
    ocmdsize += len(encoded)
    pad_bytes = cmdsize - ocmdsize
    for i in range(0, pad_bytes):
        raw_bytes += b'\x00'

    cmd_raw = raw_bytes
    fields = [cmd_off, cmd_raw, cmd, cmdsize] + ol_fields

    struct_item = struct_t.struct._make(fields)
    return struct_item


class fat_header(NamedTuple):
    off: int
    raw: bytes
    magic: int
    nfat_archs: int


fat_header_t = struct(fat_header, [4, 4])


class fat_arch(NamedTuple):
    off: int
    raw: bytes
    cputype: int
    cpusubtype: int
    offset: int
    size: int
    align: int


fat_arch_t = struct(fat_arch, [4, 4, 4, 4, 4])


class dyld_header(NamedTuple):
    off: int
    raw: bytes
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
    raw: bytes
    name: int
    timestamp: int
    current_version: int
    compatibility_version: int

    @staticmethod
    def assemble():
        raw = b'\x18\x00\x00\x00\x02\x00\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00'
        return dylib(0, raw, 0x18, 0x2, 0x010000, 0x010000)


dylib_t = struct(dylib, [4, 4, 4, 4])


class unk_command(NamedTuple):
    off: int
    raw: bytes
    cmd: int
    cmdsize: int

    def desc(self, library=None):
        ret = []
        ret.append(f'cmd: {hex(self.cmd)}')
        ret.append(f'cmdsize: {hex(self.cmdsize)}')
        ret.append(f'raw: {str(self.raw)}')
        return '\n'.join(ret)

    def __str__(self):
        return 'unk_command'


unk_command_t = struct(unk_command, [4, 4])


class dylib_command(NamedTuple):
    off: int
    raw: bytes
    cmd: int
    cmdsize: int
    dylib: int

    def desc(self, library=None):
        if self.cmd == 0xD:
            ref_dylib = library.dylib
        else:
            for exlib in library.linked:
                if exlib.cmd.off == self.off:
                    ref_dylib = exlib
                    break
        lines = []
        if ref_dylib.local:
            lines.append('"Local" dylib Command')
        if ref_dylib.weak:
            lines.append('Weak Linked')
        lines.append(f'Install Name: {ref_dylib.install_name}')
        return '\n'.join(lines)

    def __str__(self):
        if self.cmd == 0xD:
            return 'dylib_command (local)'
        return 'dylib_command'


dylib_command_t = struct(dylib_command, [4, 4, 16])


class dylinker_command(NamedTuple):
    off: int
    raw: bytes
    cmd: int
    cmdsize: int
    name: int

    def desc(self, library=None):
        return ''

    def __str__(self):
        return 'dylinker_cmd'


dylinker_command_t = struct(dylinker_command, [4, 4, 4])


class entry_point_command(NamedTuple):
    off: int
    raw: bytes
    cmd: int
    cmdsize: int
    entryoff: int
    stacksize: int

    def desc(self, library=None):
        lines = [
            f'Entry Offset: {hex(self.entryoff)}',
            f'Stack Size: {hex(self.stacksize)}'
        ]
        return '\n'.join(lines)

    def __str__(self):
        return 'entry_point_cmd'


entry_point_command_t = struct(entry_point_command, [4, 4, 8, 8])


class rpath_command(NamedTuple):
    off: int
    raw: bytes
    cmd: int
    cmdsize: int
    path: int

    def desc(self, library=None):
        return library.rpath

    def __str__(self):
        return 'rpath_command'


rpath_command_t = struct(rpath_command, [4, 4, 4])


class dyld_info_command(NamedTuple):
    off: int
    raw: bytes
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

    def desc(self, library=None):
        lines = [
            f'Rebase Table Offset: {hex(self.rebase_off)}',
            f'Rebase Size: {hex(self.rebase_size)}',
            f'Binding Table Offset: {hex(self.bind_off)}',
            f'Binding Table Size: {hex(self.bind_size)}',
            f'Weak Binding Table Offset: {hex(self.weak_bind_off)}',
            f'Weak Binding Table Size: {hex(self.weak_bind_size)}',
            f'Lazy Binding Table Offset: {hex(self.lazy_bind_off)}',
            f'Lazy Binding Table Size: {hex(self.lazy_bind_size)}',
            f'Export Table Offset: {hex(self.export_off)}',
            f'Export Table Size: {hex(self.export_size)}'
        ]
        return '\n'.join(lines)

    def __str__(self):
        return 'dyld_info_command'


dyld_info_command_t = struct(dyld_info_command, [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4])


class symtab_command(NamedTuple):
    off: int
    raw: bytes
    cmd: int
    cmdsize: int
    symoff: int
    nsyms: int
    stroff: int
    strsize: int

    def desc(self, library=None):
        lines = [
            f'Symbol Table Offset: {hex(self.symoff)}',
            f'Number of Symtab Entries: {self.nsyms}',
            f'String Table Offset: {hex(self.stroff)}',
            f'Size of String Table: {hex(self.strsize)}'
        ]
        return '\n'.join(lines)

    def __str__(self):
        return 'symtab_command'


symtab_command_t = struct(symtab_command, [4, 4, 4, 4, 4, 4])


class dysymtab_command(NamedTuple):
    off: int
    raw: bytes
    cmd: int
    cmdsize: int
    ilocalsym: int
    nlocalsym: int
    iextdefsym: int
    nextdefsym: int
    iundefsym: int
    nundefsym: int
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

    def desc(self, library=None):
        lines = [f'Index to local symbols: {self.ilocalsym}', f'Number of Local Symbols: {self.nlocalsym}',
                 f'Index to Externally Defined Symbols: {self.iextdefsym}',
                 f'Number of Indirect External Symbols: {self.nextdefsym}',
                 f'Index to Undefined symbols: {self.iundefsym}', f'Number of Local Symbols: {self.nundefsym}',
                 f'File Offset to table of contents: {hex(self.tocoff)}', f'Table of Contents Entries: {self.ntoc}',
                 f'Module Table File Offset: {hex(self.modtaboff)}', f'Module Table Entries: {self.nmodtab}',
                 f'Offset to referenced symbol table: {hex(self.extrefsymoff)}',
                 f'Number of entries in that table: {self.nextrefsyms}',
                 f'Offset to indirect symbol table: {hex(self.indirectsymoff)}',
                 f'Number of indirect symtab entries: {self.nindirectsyms}',
                 f'File offset to external reloc entries: {hex(self.extreloff)}',
                 f'Number of external reloc entries: {self.nextrel}',
                 f'Local relocation entries: {hex(self.locreloff)}',
                 f'Number of local relocation entries: {self.nlocrel}']
        return '\n'.join(lines)

    def __str__(self):
        return 'dysymtab_command'


dysymtab_command_t = struct(dysymtab_command, [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4])


class uuid_command(NamedTuple):
    off: int
    raw: bytes
    cmd: int
    cmdsize: int
    uuid: int

    def desc(self, library=None):
        return f'Library UUID: {self.uuid.to_bytes(16, "little").hex().upper()}'

    def __str__(self):
        return 'uuid_command'


uuid_command_t = struct(uuid_command, [4, 4, 16])


class build_version_command(NamedTuple):
    off: int
    raw: bytes
    cmd: int
    cmdsize: int
    platform: int
    minos: int
    sdk: int
    ntools: int

    def desc(self, library=None):
        lines = []
        lines.append(f'Platform: {library.platform.name}')
        lines.append(f'Minimum OS {library.minos.x}.{library.minos.y}.{library.minos.z}')
        lines.append(f'SDK Version {library.sdk_version.x}.{library.sdk_version.y}.{library.sdk_version.z}')
        lines.append(f'ntools: {self.ntools}')
        return '\n'.join(lines)

    def __str__(self):
        return 'build_version_cmd'


build_version_command_t = struct(build_version_command, [4, 4, 4, 4, 4, 4])


class source_version_command(NamedTuple):
    off: int
    raw: bytes
    cmd: int
    cmdsize: int
    version: int

    def desc(self, library=None):
        return ''

    def __str__(self):
        return 'source_version_command'


source_version_command_t = struct(source_version_command, [4, 4, 8])


class sub_client_command(NamedTuple):
    off: int
    raw: bytes
    cmd: int
    cmdsize: int
    offset: int

    def desc(self, library=None):
        subclient_name = library.get_cstr_at(self.off + self.offset)
        return f'Subclient: {subclient_name}'

    def __str__(self):
        return 'sub_client_cmd'


sub_client_command_t = struct(sub_client_command, [4, 4, 4])


class linkedit_data_command(NamedTuple):
    off: int
    raw: bytes
    cmd: int
    cmdsize: int
    dataoff: int
    datasize: int

    def desc(self, library=None):
        lines = [f'LinkEdit Data Offset: {hex(self.dataoff)}', f'LinkEdit Data Size: {hex(self.datasize)}']
        return '\n'.join(lines)

    def __str__(self):
        return f'linkedit_data_command'


linkedit_data_command_t = struct(linkedit_data_command, [4, 4, 4, 4])


class segment_command_64(NamedTuple):
    off: int
    raw: bytes
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

    def desc(self, library=None):
        segname_hex = hex(self.segname)[2:]
        segn_bytes = bytes.fromhex(segname_hex)
        segname = segn_bytes.decode("ascii")[::-1]
        lines = [f'Command: {hex(self.cmd)}', f'Command Size: {hex(self.cmdsize)}', f'Segment Name: {segname}',
                 f'VM Address: {hex(self.vmaddr)}', f'VM Size: {hex(self.vmsize)}', f'File Offset: {hex(self.fileoff)}',
                 f'File Size: {hex(self.filesize)}', f'maxprot: {hex(self.maxprot)}', f'initprot: {hex(self.initprot)}',
                 f'Number of Sections: {self.nsects}', f'Flags: {hex(self.flags)}']
        return '\n'.join(lines)

    def __str__(self):
        segname_hex = hex(self.segname)[2:]
        segn_bytes = bytes.fromhex(segname_hex)
        segname = segn_bytes.decode("ascii")[::-1]
        return f'segment_command_64'


segment_command_64_t = struct(segment_command_64, [4, 4, 16, 8, 8, 8, 8, 4, 4, 4, 4])


class section_64(NamedTuple):
    off: int
    raw: bytes
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
    LOAD_COMMAND.SYMTAB: symtab_command_t,
    LOAD_COMMAND.DYSYMTAB: dysymtab_command_t,
    LOAD_COMMAND.LOAD_DYLIB: dylib_command_t,
    LOAD_COMMAND.ID_DYLIB: dylib_command_t,
    LOAD_COMMAND.LOAD_DYLINKER: dylinker_command_t,
    LOAD_COMMAND.SUB_CLIENT: sub_client_command_t,
    LOAD_COMMAND.LOAD_WEAK_DYLIB: dylib_command_t,
    LOAD_COMMAND.SEGMENT_64: segment_command_64_t,
    LOAD_COMMAND.UUID: uuid_command_t,
    LOAD_COMMAND.CODE_SIGNATURE: linkedit_data_command_t,
    LOAD_COMMAND.SEGMENT_SPLIT_INFO: linkedit_data_command_t,
    LOAD_COMMAND.SOURCE_VERSION: source_version_command_t,
    LOAD_COMMAND.DYLD_INFO_ONLY: dyld_info_command_t,
    LOAD_COMMAND.FUNCTION_STARTS: linkedit_data_command_t,
    LOAD_COMMAND.DATA_IN_CODE: linkedit_data_command_t,
    LOAD_COMMAND.BUILD_VERSION: build_version_command_t,
    LOAD_COMMAND.MAIN: entry_point_command_t,
    LOAD_COMMAND.RPATH: rpath_command_t,
}


class objc2_class(NamedTuple):
    off: int
    raw: bytes
    isa: int
    superclass: int
    cache: int
    vtable: int
    info: int


objc2_class_t = struct(objc2_class, [8, 8, 8, 8, 8])


class objc2_class_ro(NamedTuple):
    off: int
    raw: bytes
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
    raw: bytes
    selector: int
    types: int
    imp: int


objc2_meth_t = struct(objc2_meth, [8, 8, 8])
objc2_meth_list_entry_t = struct(objc2_meth, [4, 4, 4])


class objc2_meth_list(NamedTuple):
    off: int
    raw: bytes
    entrysize: int
    count: int


objc2_meth_list_t = struct(objc2_meth_list, [4, 4])


class objc2_prop_list(NamedTuple):
    off: int
    raw: bytes
    entrysize: int
    count: int


objc2_prop_list_t = struct(objc2_prop_list, [4, 4])


class objc2_prop(NamedTuple):
    off: int
    raw: bytes
    name: int
    attr: int


objc2_prop_t = struct(objc2_prop, [8, 8])


class objc2_prot_list(NamedTuple):
    off: int
    raw: bytes
    cnt: int


objc2_prot_list_t = struct(objc2_prot_list, [8])


class objc2_prot(NamedTuple):
    off: int
    raw: bytes
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
    raw: bytes
    entrysize: int
    cnt: int


objc2_ivar_list_t = struct(objc2_ivar_list, [4, 4])


class objc2_ivar(NamedTuple):
    off: int
    raw: bytes
    offs: int
    name: int
    type: int
    align: int
    size: int


objc2_ivar_t = struct(objc2_ivar, [8, 8, 8, 4, 4])


class objc2_category(NamedTuple):
    off: int
    raw: bytes
    name: int
    s_class: int
    inst_meths: int
    class_meths: int
    prots: int
    props: int


objc2_category_t = struct(objc2_category, [8, 8, 8, 8, 8, 8])
