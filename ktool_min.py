
import browser

from enum import IntEnum

import math

from typing import NamedTuple
from collections import namedtuple

class MH_FLAGS(IntEnum):
    NOUNDEFS = 0x1
    INCRLINK = 0x2
    DYLDLINK = 0x4
    BINDATLOAD = 0x8
    PREBOUND = 0x10
    SPLIT_SEGS = 0x20
    LAZY_INIT = 0x40
    TWOLEVEL = 0x80
    FORCE_FLAT = 0x100
    NOMULTIEFS = 0x200
    NOFIXPREBINDING = 0x400
    PREBINDABLE = 0x800
    ALLMODSBOUND = 0x1000
    SUBSECTIONS_VIA_SYMBOLS = 0x2000
    CANONICAL = 0x4000
    WEAK_DEFINES = 0x8000
    BINDS_TO_WEAK = 0x10000
    ALLOW_STACK_EXECUTION = 0x20000
    ROOT_SAFE = 0x40000
    SETUID_SAFE = 0x80000
    NO_REEXPORTED_DYLIBS = 0x100000
    PIE = 0x200000
    DEAD_STRIPPABLE_DYLIB = 0x400000
    HAS_TLV_DESCRIPTORS = 0x800000
    NO_HEAP_EXECUTION = 0x1000000
    APP_EXTENSION_SAFE = 0x02000000
    NLIST_OUTOFSYNC_WITH_DYLDINFO = 0x04000000
    SIM_SUPPORT = 0x08000000


class MH_FILETYPE(IntEnum):
    OBJECT = 0x1
    EXECUTE = 0x2
    FVMLIB = 0x3
    CORE = 0x4
    PRELOAD = 0x5
    DYLIB = 0x6
    DYLINKER = 0x7
    BUNDLE = 0x8
    DYLIB_STUB = 0x9
    DSYM = 0xA
    KEXT_BUNDLE = 0xB


LC_REQ_DYLD = 0x80000000


class LOAD_COMMAND(IntEnum):
    SEGMENT = 0x1
    SYMTAB = 0x2
    SYMSEG = 0x3
    THREAD = 0x4
    UNIXTHREAD = 0x5
    LOADFVMLIB = 0x6
    IDFVMLIB = 0x7
    IDENT = 0x8
    FVMFILE = 0x9
    PREPAGE = 0xA
    DYSYMTAB = 0xB
    LOAD_DYLIB = 0xC
    ID_DYLIB = 0xD
    LOAD_DYLINKER = 0xE
    ID_DYLINKER = 0xF
    PREBOUND_DYLIB = 0x10
    ROUTINES = 0x11
    SUB_FRAMEWORK = 0x12
    SUB_UMBRELLA = 0x13
    SUB_CLIENT = 0x14
    SUB_LIBRARY = 0x15
    TWOLEVEL_HINTS = 0x16
    PREBIND_CKSUM = 0x17
    LOAD_WEAK_DYLIB = 0x18 | LC_REQ_DYLD
    SEGMENT_64 = 0x19
    ROUTINES_64 = 0x1a
    UUID = 0x1b
    RPATH = 0x1C | LC_REQ_DYLD
    CODE_SIGNATURE = 0x1D
    SEGMENT_SPLIT_INFO = 0x1E
    REEXPORT_DYLIB = 0x1F | LC_REQ_DYLD
    LAZY_LOAD_DYLIB = 0x20
    ENCRYPTION_INFO = 0x21
    DYLD_INFO = 0x22
    DYLD_INFO_ONLY = 0x22 | LC_REQ_DYLD
    LOAD_UPWARD_DYLIB = 0x23 | LC_REQ_DYLD
    VERSION_MIN_MACOSX = 0x24
    VERSION_MIN_IPHONEOS = 0x25
    FUNCTION_STARTS = 0x26
    DYLD_ENVIRONMENT = 0x27
    MAIN = 0x28 | LC_REQ_DYLD
    DATA_IN_CODE = 0x29
    SOURCE_VERSION = 0x2A
    DYLIB_CODE_SIGN_DRS = 0x2B
    ENCRYPTION_INFO_64 = 0x2C
    LINKER_OPTION = 0x2D
    LINKER_OPTIMIZATION_HINT = 0x2E
    VERSION_MIN_TVOS = 0x2F
    VERSION_MIN_WATCHOS = 0x30
    NOTE = 0x31
    BUILD_VERSION = 0x32


struct = namedtuple("struct", ["struct", "sizes"])

symtab_entry = namedtuple("symtab_entry", ["off", "raw", "str_index", "type", "sect_index", "desc", "value"])
symtab_entry_t = struct(symtab_entry, [4, 1, 1, 2, 8])


def read_bytes(file, start, end):
    file.seek(start)
    b = file.read(end-start)
    file.seek(0)
    return b

def sizeof(t: struct):
    assert isinstance(t, struct)
    return sum(t.sizes)


def patch_field(struc, struct_t: struct, field_index: int, value: int, endian="little"):
    rar = bytearray(struc.raw)
    before_size = sum(struct_t.sizes[:field_index])
    f_size = struct_t.sizes[field_index]
    after_start = before_size + f_size
    return bytes(rar[:before_size] + bytearray(value.to_bytes(f_size, endian)) + rar[after_start:])


def assemble_dyld_header(fields, endian="little"):
    ol_fields = fields
    raw_bytes: bytes = b''
    struct_t = dyld_header_t
    off = 0

    for index, field_size in enumerate(struct_t.sizes):
        original_field = ol_fields[index]
        if not isinstance(original_field, bytes):
            original_field = original_field.to_bytes(field_size, endian)
        raw_bytes += original_field

    raw = raw_bytes
    fields = [0, raw] + fields
    return struct_t.struct._make(fields)


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


import os

from enum import Enum
from typing import Tuple


import inspect


class LogLevel(Enum):
    NONE = -1
    ERROR = 0
    WARN = 1
    INFO = 2
    DEBUG = 3


class log:
    """
    Python's default logging library is absolute garbage

    so we use this.
    """
    LOG_LEVEL = LogLevel.ERROR

    @staticmethod
    def line():
        return 'ktool.' + os.path.basename(inspect.stack()[2][1]).split('.')[0] + ":" + str(inspect.stack()[2][2]) \
               + ":" + inspect.stack()[2][3] + '()'

    @staticmethod
    def debug(msg: str):
        if log.LOG_LEVEL.value >= LogLevel.DEBUG.value:
            print(f'DEBUG - {log.line()} - {msg}')

    @staticmethod
    def info(msg: str):
        if log.LOG_LEVEL.value >= LogLevel.INFO.value:
            print(f'INFO - {log.line()} - {msg}')

    @staticmethod
    def warn(msg: str):
        if log.LOG_LEVEL.value >= LogLevel.WARN.value:
            print(f'WARN - {log.line()} - {msg}')

    @staticmethod
    def warning(msg: str):
        if log.LOG_LEVEL.value >= LogLevel.WARN.value:
            print(f'WARN - {log.line()} - {msg}')

    @staticmethod
    def error(msg: str):
        if log.LOG_LEVEL.value >= LogLevel.ERROR.value:
            print(f'ERROR - {log.line()} - {msg}')


class MachOFileType(Enum):
    FAT = 0
    THIN = 1


class MachOFile:
    def __init__(self, file):
        self.file_object = file
        self.file = file
        self.slices = []
        self.magic = self._get_at(0, 4)
        self.type = self._load_filetype()

        if self.type == MachOFileType.FAT:
            self.header: fat_header = self._load_struct(0, fat_header_t, "big")
            for off in range(0, self.header.nfat_archs):
                offset = sizeof(fat_header_t) + (off * sizeof(fat_arch_t))
                arch_struct = self._load_struct(offset, fat_arch_t, "big")
                self.slices.append(Slice(self, arch_struct))
        else:
            self.slices.append(Slice(self, None))

    def _load_filetype(self):
        if self.magic == 0xCAFEBABE:
            return MachOFileType.FAT
        elif self.magic == 0xCFFAEDFE or self.magic == 0xCEFAEDFE:
            return MachOFileType.THIN

    def _load_struct(self, addr: int, struct_type: struct, endian="little"):
        field_names = list(struct_type.struct.__dict__['_fields'])  # unimportant?
        fields = [addr, read_bytes(self.file, addr, addr + sizeof(struct_type))]
        ea = addr

        for field in struct_type.sizes:
            field_addr = ea
            fields.append(self._get_at(field_addr, field, endian))
            ea += field

        if len(fields) != len(field_names):
            raise ValueError(
                f'Field count mismatch {len(fields)} vs {len(field_names)} in load_struct for {struct.struct.__doc__}.\nCheck Fields and Size '
                f'Array.')

        # noinspection PyProtectedMember
        return struct_type.struct._make(fields)

    # noinspection PyTypeChecker
    def _get_at(self, addr, count, endian="big"):

        return int.from_bytes(read_bytes(self.file, addr, addr+count), endian)

    def __del__(self):
        self.file.close()


class Segment:
    """


    segment_command_64:
    ["off", "cmd", "cmdsize", "segname", "vmaddr", "vmsize", "fileoff", "filesize",
        "maxprot", "initprot", "nsects", "flags"]
    """

    def __init__(self, library, cmd):
        self.library = library
        self.cmd = cmd
        self.vm_address = cmd.vmaddr
        self.file_address = cmd.fileoff
        self.size = cmd.vmsize
        self.name = ""
        for i, c in enumerate(hex(cmd.segname)[2:]):
            if i % 2 == 0:
                self.name += chr(int(c + hex(cmd.segname)[2:][i + 1], 16))
        self.name = self.name[::-1]
        self.sections = self._process_sections()

    def _process_sections(self):
        sections = {}
        ea = self.cmd.off + sizeof(segment_command_64_t)

        for section in range(0, self.cmd.nsects):
            sect = self.library.load_struct(ea, section_64_t)
            section = Section(self, sect)
            sections[section.name] = section
            ea += sizeof(section_64_t)

        ea += sizeof(segment_command_64_t)
        return sections


class Section:
    """


    section_64
     ["off",
     "sectname",
     "segname",
     "addr", VM ADDRESS
     "size", SIZE ON BOTH
     "offset", FILE ADDRESS
     "align", "reloff", "nreloc", "flags", "void1", "void2", "void3"]
    """

    def __init__(self, segment, cmd):
        self.cmd = cmd
        self.segment = segment
        self.name = segment.library.get_str_at(cmd.off, 16)
        self.vm_address = cmd.addr
        self.file_address = cmd.offset
        self.size = cmd.size


vm_obj = namedtuple("vm_obj", ["vmaddr", "vmend", "size", "fileaddr", "name"])


class _VirtualMemoryMap:
    """
    Virtual Memory is the location "in memory" where the library/bin, etc will be accessed when ran This is not where
    it actually sits in memory at runtime; it will be slid, but the program doesnt know and doesnt care The slid
    address doesnt matter to us either, we only care about the addresses the rest of the file cares about

    There are two address sets used in mach-o files: vm, and file. (commonly; vmoff and fileoff)
    For example, when reading raw data of an executable binary:
    0x0 file offset will (normally?) map to 0x10000000 in the VM

    These VM offsets are relayed to the linker via Load Commands
    Some locations in the file do not have VM counterparts (examples being symbol table(citation needed))

    Some other VM related offsets are changed/modified via binding info(citation needed)
    """

    def __init__(self, macho_slice):
        # name: vm_obj
        self.slice = macho_slice
        self.map = {}
        self.stats = {}
        self.sorted_map = {}
        self.cache = {}

    def __str__(self):
        """
        We want to be able to just call print(macho.vm) to display the filemap in a human-readable format

        :return: multiline String representation of the filemap
        """

        ret = ""
        return ret

    def get_vm_start(self):
        """
        Get the address the VM starts in, excluding __PAGEZERO
        Method selector dumping uses this
        :return:
        """
        sortedmap = {k: v for k, v in sorted(self.map.items(), key=lambda item: item[1].vm_address)}
        if list(sortedmap.keys())[0] == "__PAGEZERO":
            return list(sortedmap.values())[1].vm_address
        else:
            return list(sortedmap.values())[0].vm_address

    def get_file_address(self, vm_address: int, segment_name=None):
        # This function gets called *a lot*
        # It needs to be fast as shit.
        if vm_address in self.cache:
            return self.cache[vm_address]
        if segment_name is not None:
            o = self.map[segment_name]

            # noinspection PyChainedComparisons
            if vm_address >= o.vmaddr and o.vmend >= vm_address:
                file_addr = o.fileaddr + vm_address - o.vmaddr
                self.cache[vm_address] = file_addr
                return file_addr
            else:
                # noinspection PyBroadException
                try:
                    o = self.map['__EXTRA_OBJC']
                    # noinspection PyChainedComparisons
                    if vm_address >= o.vmaddr and o.vmend >= vm_address:
                        file_addr = o.fileaddr + vm_address - o.vmaddr
                        self.cache[vm_address] = file_addr
                        return file_addr
                except Exception:
                    for o in self.map.values():
                        # noinspection PyChainedComparisons
                        if vm_address >= o.vmaddr and o.vmend >= vm_address:
                            # self.stats[o.name] += 1
                            file_addr = o.fileaddr + vm_address - o.vmaddr
                            self.cache[vm_address] = file_addr
                            return file_addr

        for o in self.map.values():
            # noinspection PyChainedComparisons
            if vm_address >= o.vmaddr and o.vmend >= vm_address:
                # self.stats[o.name] += 1
                file_addr = o.fileaddr + vm_address - o.vmaddr
                self.cache[vm_address] = file_addr
                return file_addr

        raise ValueError(f'Address {hex(vm_address)} couldn\'t be found in vm address set')

    def add_segment(self, segment: Segment):
        if len(segment.sections) == 0:
            seg_obj = vm_obj(segment.vm_address, segment.vm_address + segment.size, segment.size, segment.file_address,
                             segment.name)
            self.map[segment.name] = seg_obj
            self.stats[segment.name] = 0
        else:
            for section in segment.sections.values():
                name = section.name if section.name not in self.map.keys() else section.name + '2'
                sect_obj = vm_obj(section.vm_address, section.vm_address + section.size, section.size,
                                  section.file_address, name)
                self.map[name] = sect_obj
                self.sorted_map = {k: v for k, v in sorted(self.map.items(), key=lambda item: item[1].vmaddr)}
                self.stats[name] = 0


class CPUType(Enum):
    X86 = 0
    X86_64 = 1
    ARM = 2
    ARM64 = 3


class CPUSubType(Enum):
    X86_64_ALL = 0
    X86_64_H = 1
    ARMV7 = 2
    ARMV7S = 3
    ARM64_ALL = 4
    ARM64_V8 = 5


class Slice:
    """

    """

    def __init__(self, macho_file, arch_struct, offset=0):
        """

        :param macho_file:
        :param arch_struct:
        :param offset:
        """
        self.macho_file = macho_file
        self.arch_struct = arch_struct

        self.patches = {}

        self.patched_bytes = b''
        self.use_patched_bytes = False

        if self.arch_struct:
            self.offset = arch_struct.offset
            self.type = self._load_type()
            self.subtype = self._load_subtype()
        else:
            self.offset = offset

        self.size = 0
        if self.offset == 0:
            f = self.macho_file.file_object
            old_file_position = f.tell()
            f.seek(0, 2)
            self.size = f.tell()
            f.seek(old_file_position)
        else:
            self.size = self.arch_struct.size

    def patch(self, address, raw):
        self.macho_file.file.seek(self.offset + address)
        log.debug(f'Patched At: {hex(address)} ')
        log.debug(f'New Bytes: {str(raw)}')
        diff = self.size - (self.offset + address + len(raw))
        if diff < 0:
            data = self.full_bytes_for_slice()
            data = data[:address] + raw
            # log.debug(data)
            self.patched_bytes = data
            self.use_patched_bytes = True
            return
        old_raw = self.macho_file.file.read(len(raw))
        self.macho_file.file.seek(self.offset + address)
        log.debug(f'Old Bytes: {str(old_raw)}')
        self.macho_file.file.write(raw)
        self.macho_file.file.seek(0)

    def full_bytes_for_slice(self):
        if self.offset == 0:

            f = self.macho_file.file_object
            old_file_position = f.tell()
            f.seek(0, 2)
            size = f.tell()
            f.seek(old_file_position)

            return read_bytes(self.macho_file.file, 0, size)
        return read_bytes(self.macho_file.file, self.offset, self.offset + self.arch_struct.size)

    def load_struct(self, addr: int, struct_type: struct, endian="little"):
        field_names = list(struct_type.struct.__dict__['_fields'])  # unimportant?

        fields = [addr, read_bytes(self.macho_file.file, addr, addr + sizeof(struct_type))]
        ea = addr

        for field in struct_type.sizes:
            field_addr = ea
            fields.append(self.get_at(field_addr, field, endian))
            ea += field

        if len(fields) != len(field_names):
            raise ValueError(
                f'Field count mismatch {len(fields)} vs {len(field_names)} in load_struct for {str(struct_type.struct)}.\nCheck Fields and Size Array.')

        # noinspection PyProtectedMember
        return struct_type.struct._make(fields)

    def get_at(self, addr, count, endian="little"):
        addr = addr + self.offset
        return int.from_bytes(read_bytes(self.macho_file.file, addr, addr+count), endian)

    def get_bytes_at(self, addr, count):
        addr = addr + self.offset
        return read_bytes(self.macho_file.file, addr, addr+count)

    def get_str_at(self, addr: int, count: int):
        addr = addr + self.offset
        return read_bytes(self.macho_file.file, addr, addr+count).decode().rstrip('\x00')

    def get_cstr_at(self, addr: int, limit: int = 0):
        addr = addr + self.offset
        self.macho_file.file.seek(addr)
        cnt = 0
        while True:
            if self.macho_file.file.read(1) != b"\x00":
                cnt += 1
            else:
                break
        end = addr + cnt
        text = read_bytes(self.macho_file.file, addr, end).decode()
        self.macho_file.file.seek(0)
        return text

    def decode_uleb128(self, readHead: int) -> Tuple[int, int]:

        value = 0
        shift = 0

        while True:

            byte = self.get_at(readHead, 1)

            value |= (byte & 0x7f) << shift

            readHead += 1
            shift += 7

            if (byte & 0x80) == 0:
                break

        return value, readHead

    def _load_type(self):
        cpu_type = self.arch_struct.cputype

        if cpu_type & 0xF000000 != 0:
            if cpu_type & 0xF == 0x7:
                return CPUType.X86_64
            elif cpu_type & 0xF == 0xC:
                return CPUType.ARM64
        else:
            if cpu_type & 0xF == 0x7:
                return CPUType.X86
            elif cpu_type & 0xF == 0xC:
                return CPUType.ARM

        log.error(f'Unknown CPU Type ({hex(self.arch_struct.cputype)}) ({self.arch_struct}). File an issue at '
                  f'https://github.com/kritantadev/ktool')
        return CPUType.ARM

    def _load_subtype(self):
        cpu_subtype = self.arch_struct.cpusubtype
        subtype_ret = None

        submap = {
            0: CPUSubType.ARM64_ALL,
            1: CPUSubType.ARM64_V8,
            2: CPUSubType.ARM64_V8,
            3: CPUSubType.X86_64_ALL,
            8: CPUSubType.X86_64_H,
            9: CPUSubType.ARMV7,
            11: CPUSubType.ARMV7S
        }

        try:
            subtype_ret = submap[cpu_subtype]
        except KeyError:
            log.error(f'Unknown CPU SubType ({hex(cpu_subtype)}) ({self.arch_struct}). File an issue at '
                      f'https://github.com/kritantadev/ktool')
            exit()
        return subtype_ret


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
        # TODO: finish
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

        nd_hc = assemble_dyld_header([nd_header_magic, nd_cputype, nd_cpusub, nd_filetype, nd_loadcnt, nd_loadsize, nd_flags, nd_void])
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

        nd_hc = assemble_dyld_header([nd_header_magic, nd_cputype, nd_cpusub, nd_filetype, nd_loadcnt, nd_loadsize, nd_flags, nd_void])
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

        nd_hc = assemble_dyld_header([nd_header_magic, nd_cputype, nd_cpusub, nd_filetype, nd_loadcnt, nd_loadsize, nd_flags, nd_void])
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
    "off",
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
                cmd_start_addr = read_address
                read_address += 1

                if binding_opcode == BINDING_OPCODE.DONE:
                    import_stack.append(
                        record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
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
                        record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
                    seg_offset += 8
                    o, read_address = self.library.decode_uleb128(read_address)
                    seg_offset += o

                elif binding_opcode == BINDING_OPCODE.DO_BIND_ADD_ADDR_IMM_SCALED:
                    import_stack.append(
                        record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
                    seg_offset = seg_offset + (value * 8) + 8

                elif binding_opcode == BINDING_OPCODE.DO_BIND_ULEB_TIMES_SKIPPING_ULEB:
                    count, read_address = self.library.decode_uleb128(read_address)
                    skip, read_address = self.library.decode_uleb128(read_address)

                    for i in range(0, count):
                        import_stack.append(
                            record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
                        seg_offset += skip + 8

                elif binding_opcode == BINDING_OPCODE.DO_BIND:
                    import_stack.append(
                        record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
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


type_encodings = {
    "c": "char",
    "i": "int",
    "s": "short",
    "l": "long",
    "q": "NSInteger",
    "C": "unsigned char",
    "I": "unsigned int",
    "S": "unsigned short",
    "L": "unsigned long",
    "A": "uint8_t",
    "Q": "NSUInteger",
    "f": "float",
    "d": "CGFloat",
    "b": "BOOL",
    "@": "id",
    "B": "BOOL",
    "v": "void",
    "*": "char *",
    "#": "Class",
    ":": "SEL",
    "?": "unk",
}


class ObjCLibrary:

    def __init__(self, library, safe=False):
        self.library = library
        self.safe = safe
        self.tp = TypeProcessor()
        self.name = library.name

        self.classlist = self._generate_class_list(None)
        self.catlist = self._generate_category_list()
        self.protolist = self._generate_protocol_list()

    def _generate_category_list(self):
        sect = None
        for seg in self.library.segments:
            for sec in self.library.segments[seg].sections:
                if sec == "__objc_catlist":
                    sect = self.library.segments[seg].sections[sec]

        if not sect:
            return []

        cats = []  # meow
        count = sect.size // 0x8
        for offset in range(0, count):
            cats.append(Category(self, sect.vm_address + offset * 0x8))

        return cats

    def _generate_class_list(self, classlimit):
        sect = None
        for seg in self.library.segments:
            for sec in self.library.segments[seg].sections:
                if sec == "__objc_classlist":
                    sect = self.library.segments[seg].sections[sec]
        # sect: Section = self.library.segments['__DATA_CONST'].sections['__objc_classlist']
        if not sect:
            return []
        classes = []
        cnt = sect.size // 0x8
        for i in range(0, cnt):
            if classlimit is None:
                try:
                    classes.append(Class(self, sect.vm_address + i * 0x8))
                except Exception as ex:
                    log.error(f'Failed to load a class! Ex: {str(ex)}')
            else:
                oc = Class(self, sect.vm_address + i * 0x8)
                if classlimit == oc.name:
                    classes.append(oc)
        return classes

    def _generate_protocol_list(self):

        sect = None
        for seg in self.library.segments:
            for sec in self.library.segments[seg].sections:
                if sec == "__objc_protolist":
                    sect = self.library.segments[seg].sections[sec]
        # sect: Section = self.library.segments['__DATA_CONST'].sections['__objc_classlist']
        if not sect:
            return []

        protos = []

        cnt = sect.size // 0x8
        for i in range(0, cnt):
            ptr = sect.vm_address + i * 0x8
            loc = self.library.get_bytes(ptr, 0x8, vm=True)
            proto = self.library.load_struct(loc, objc2_prot_t, vm=True)
            try:
                protos.append(Protocol(self, proto, loc))
            except Exception as ex:
                log.error("Failed to load a protocol with " + str(ex))

        return protos

    def get_bytes(self, offset: int, length: int, vm=False, sectname=None):
        return self.library.get_bytes(offset, length, vm, sectname)

    def load_struct(self, addr: int, struct_type: struct, vm=True, sectname=None, endian="little"):
        return self.library.load_struct(addr, struct_type, vm, sectname, endian)

    def get_str_at(self, addr: int, count: int, vm=True, sectname=None):
        return self.library.get_str_at(addr, count, vm, sectname)

    def get_cstr_at(self, addr: int, limit: int = 0, vm=True, sectname=None):
        return self.library.get_cstr_at(addr, limit, vm, sectname)


class Struct:
    def __init__(self, processor, type_str: str):
        # {name=dd}

        # Remove the outer {}, then get everything to the left of the equal sign
        self.name = type_str[1:-1].split('=')[0]

        if '=' not in type_str:
            self.fields = []
            return

        self.field_names = []

        process_string = type_str[1:-1].split('=', 1)[1]

        if process_string.startswith('"'): #  Named struct
            output_string = ""

            in_field = False
            in_substruct_depth = 0

            field = ""

            for character in process_string:
                if character == '{':
                    in_substruct_depth += 1
                    output_string += character
                    continue

                elif character == '}':
                    in_substruct_depth -= 1
                    output_string += character
                    continue

                if in_substruct_depth == 0:
                    if character == '"':
                        if in_field:
                            self.field_names.append(field)
                            in_field = False
                            field = ""
                        else:
                            in_field = True
                    else:
                        if in_field:
                            field += character
                        else:
                            output_string += character
                else:
                    output_string += character

            process_string = output_string

        # Remove the outer {},
        # get everything after the first = sign,
        # Process that via the processor
        # Save the resulting list to self.fields
        self.fields = processor.process(process_string)

    def __str__(self):
        ret = "typedef struct " + self.name + " {\n"

        if not self.fields:
            ret += "} // Error Processing Struct Fields"
            return ret

        for i, field in enumerate(self.fields):
            field_name = f'field{str(i)}'

            if len(self.field_names) > 0:
                try:
                    field_name = self.field_names[i]
                except IndexError as ex:
                    log.debug(f'Missing a field in struct {self.name}')

            if isinstance(field.value, Struct):
                field = field.value.name
            else:
                field = field.value

            ret += "    " + field + ' ' + field_name + ';\n'
        ret += '} ' + self.name + ';'
        if len(self.fields) == 0:
            ret += " // Error Processing Struct Fields"
        return ret


class EncodingType(Enum):
    METHOD = 0
    PROPERTY = 1
    IVAR = 2


class EncodedType(Enum):
    STRUCT = 0
    NAMED = 1
    ID = 2
    NORMAL = 3


class Type:
    def __init__(self, processor, typestr, pc=0):
        start = typestr[0]
        self.child = None
        self.pointer_count = pc

        if start in type_encodings.keys():
            self.type = EncodedType.NORMAL
            self.value = type_encodings[start]
            return

        elif start == '"':
            self.type = EncodedType.NAMED
            self.value = typestr[1:-1]
            return

        elif start == '{':
            self.type = EncodedType.STRUCT
            self.value = Struct(processor, typestr)
            return
        raise ValueError(f'Struct with type {start} not found')

    def __str__(self):
        pref = ""
        for i in range(0, self.pointer_count):
            pref += "*"
        return pref + str(self.value)


class TypeProcessor:
    def __init__(self):
        self.structs = {}

    def save_struct(self, struct_to_save: Struct):
        if struct_to_save.name not in self.structs.keys():
            self.structs[struct_to_save.name] = struct_to_save
        else:
            if len(self.structs[struct_to_save.name].fields) == 0:
                self.structs[struct_to_save.name] = struct_to_save
            if len(struct_to_save.field_names) > 0 and len(self.structs[struct_to_save.name].field_names) == 0:
                self.structs[struct_to_save.name] = struct_to_save

    def process(self, type_to_process: str):
        try:
            tokens = self.tokenize(type_to_process)
            types = []
            pc = 0
            for i, token in enumerate(tokens):
                if token == "^":
                    pc += 1
                else:
                    typee = Type(self, token, pc)
                    types.append(typee)
                    if typee.type == EncodedType.STRUCT:
                        self.save_struct(typee.value)
                    pc = 0
            return types
        except:
            pass

    @staticmethod
    def tokenize(type_to_tokenize: str):
        # ^Idd^{structZero=dd{structName={innerStructName=dd}}{structName2=dd}}

        # This took way too long to write
        # Apologies for lack of readability, it splits up the string into a list
        # Makes every character a token, except root structs
        #   which it compiles into a full string with the contents and tacks onto said list
        tokens = []
        b = False
        bc = 0
        bu = ""
        for c in type_to_tokenize:
            if b:
                bu += c
                if c == "{":
                    bc += 1
                elif c == "}":
                    bc -= 1
                    if bc == 0:
                        tokens.append(bu)
                        b = False
                        bu = ""
            elif c in type_encodings or c == "^":
                tokens.append(c)
            elif c == "{":
                bu += "{"
                b = True
                bc += 1
            elif c == '"':
                try:
                    tokens = [type_to_tokenize.split('@', 1)[1]]
                except Exception as ex:
                    log.warning(f'Failed to process type {type_to_tokenize} with {ex}')
                    return []
                break
        return tokens


class Ivar:
    def __init__(self, library, objc_class, ivar: objc2_ivar, vmaddr: int):
        self.name = library.get_cstr_at(ivar.name, 0, True, "__objc_methname")
        type_string = library.get_cstr_at(ivar.type, 0, True, "__objc_methtype")
        self.is_id = type_string[0] == "@"
        self.type = self._renderable_type(library.tp.process(type_string)[0])

    def __str__(self):
        ret = ""
        if self.type.startswith('<'):
            ret += "id"
        ret += self.type + ' '
        if self.is_id:
            ret += '*'
        ret += self.name
        return ret

    @staticmethod
    def _renderable_type(type: Type):
        if type.type == EncodedType.NORMAL:
            return str(type)
        elif type.type == EncodedType.STRUCT:
            ptr_addition = ""
            for i in range(0, type.pointer_count):
                ptr_addition += '*'
            return ptr_addition + type.value.name
        return str(type)


class Method:
    def __init__(self, library, meta, method: objc2_meth, vmaddr: int, uses_rel_meth=False, rms_are_direct=False):
        self.meta = meta

        if uses_rel_meth:
            if rms_are_direct:
                self.sel = library.get_cstr_at(method.selector + vmaddr, 0, vm=True, sectname="__objc_methname")
                self.type_string = library.get_cstr_at(method.types + vmaddr + 4, 0, vm=True, sectname="__objc_methtype")
            else:
                selref = library.get_bytes(method.selector + vmaddr, 8, vm=True)
                self.sel = library.get_cstr_at(selref, 0, vm=True, sectname="__objc_methname")
                self.type_string = library.get_cstr_at(method.types + vmaddr + 4, 0, vm=True, sectname="__objc_methtype")
        else:
            self.sel = library.get_cstr_at(method.selector, 0, vm=True, sectname="__objc_methname")
            self.type_string = library.get_cstr_at(method.types, 0, vm=True, sectname="__objc_methtype")

        self.types = library.tp.process(self.type_string)

        self.return_string = self._renderable_type(self.types[0])
        self.arguments = [self._renderable_type(i) for i in self.types[1:]]

        self.signature = self._build_method_signature()

    def __str__(self):
        ret = ""
        ret += self.signature
        return ret

    @staticmethod
    def _renderable_type(type: Type):
        if type.type == EncodedType.NORMAL:
            return str(type)
        elif type.type == EncodedType.STRUCT:
            ptr_addition = ""
            for i in range(0, type.pointer_count):
                ptr_addition += '*'
            return 'struct ' + type.value.name + ' ' + ptr_addition

    def _build_method_signature(self):
        dash = "+" if self.meta else "-"
        ret = "(" + self.return_string + ")"

        if len(self.arguments) == 0:
            return dash + ret + self.sel

        segments = []
        for i, item in enumerate(self.sel.split(':')):
            if item == "":
                continue
            try:
                segments.append(item + ':' + '(' + self.arguments[i + 2] + ')' + 'arg' + str(i) + ' ')
            except IndexError:
                segments.append(item)

        sig = ''.join(segments)

        return dash + ret + sig


class LinkedClass:
    def __init__(self, classname, libname):
        self.classname = classname
        self.libname = libname


class Class:
    """
    Objective C Class
    This can be a superclass, metaclass, etc
    can represent literally anything that's a "class" struct


    objc2_class = ["off", "isa", "superclass", "cache", "vtable",
    "info" :  VM pointer to objc2_class_ro
    ]

    objc2_class_ro = ["off", "flags", "ivar_base_start", "ivar_base_size", "reserved", "ivar_lyt", "name", "base_meths", "base_prots", "ivars", "weak_ivar_lyt", "base_props"]
    """

    def __init__(self, library, ptr: int, meta=False, objc2class=None):
        self.library = library
        self.ptr = ptr
        self.meta = meta
        self.metaclass = None
        self.superclass = ""
        self.linkedlibs = []
        self.linked_classes = []
        self.fdec_classes = []
        self.fdec_prots = []
        self.struct_list = []
        # Classes imported in this class from the same mach-o
        if not objc2class:
            self.objc2_class: objc2_class = self._load_objc2_class(ptr)
        else:
            self.objc2_class = objc2class

        self.objc2_class_ro = self.library.load_struct(self.objc2_class.info, objc2_class_ro_t, vm=True)

        self._process_structs()

        self.methods = self._process_methods()
        self.properties = self._process_props()
        self.protocols = self._process_prots()
        self.ivars = self._process_ivars()
        self._load_linked_libraries()

    def __str__(self):
        ret = ""
        ret += self.name
        return ret

    def _load_linked_libraries(self):
        pass

    def _load_objc2_class(self, ptr):

        objc2_class_location = self.library.get_bytes(ptr, 8, vm=True)
        objc2_class_item: objc2_class = self.library.load_struct(objc2_class_location, objc2_class_t, vm=True)

        bad_addr = False
        try:
            objc2_superclass: objc2_class = self.library.load_struct(objc2_class_item.superclass, objc2_class_t)
            superclass = Class(self.library, objc2_superclass.off, False, objc2_superclass)
            self.superclass = superclass.name
        except:
            bad_addr = True

        if bad_addr:
            # Linked Superclass
            struct_size = sizeof(objc2_class_t)
            struct_location = objc2_class_item.off
            try:
                symbol = self.library.library.binding_table.lookup_table[objc2_class_location + 8]
            except KeyError as ex:
                self.superclass = "NSObject"
                return objc2_class_item
            self.superclass = symbol.name[1:]
            try:
                self.linked_classes.append(LinkedClass(symbol.name[1:], self.library.library.linked[
                    int(symbol.ordinal) - 1].install_name))
            except IndexError:
                pass
        if objc2_class_item.isa != 0 and objc2_class_item.isa <= 0xFFFFFFFFFF and not self.meta:
            try:
                metaclass_item: objc2_class = self.library.load_struct(objc2_class_item.isa, objc2_class_t)
                self.metaclass = Class(self.library, metaclass_item.off, True, metaclass_item)
            except ValueError:
                pass
        return objc2_class_item

    def _process_structs(self):
        try:
            self.name = self.library.get_cstr_at(self.objc2_class_ro.name, 0, vm=True)
        except ValueError as ex:
            pass

    def _process_methods(self):
        methods = []

        if self.objc2_class_ro.base_meths == 0:
            return methods  # Useless Subclass

        vm_ea = self.objc2_class_ro.base_meths
        methlist_head = self.library.load_struct(self.objc2_class_ro.base_meths, objc2_meth_list_t)
        ea = methlist_head.off

        # https://github.com/arandomdev/DyldExtractor/blob/master/DyldExtractor/objc/objc_structs.py#L79
        RELATIVE_METHODS_SELECTORS_ARE_DIRECT_FLAG = 0x40000000
        RELATIVE_METHOD_FLAG = 0x80000000
        METHOD_LIST_FLAGS_MASK = 0xFFFF0000

        uses_relative_methods = methlist_head.entrysize & METHOD_LIST_FLAGS_MASK & RELATIVE_METHOD_FLAG != 0
        rms_are_direct = methlist_head.entrysize & METHOD_LIST_FLAGS_MASK & RELATIVE_METHODS_SELECTORS_ARE_DIRECT_FLAG != 0

        ea += 8
        vm_ea += 8
        for i in range(1, methlist_head.count + 1):
            if uses_relative_methods:
                meth = self.library.load_struct(ea, objc2_meth_list_entry_t, vm=False)
            else:
                meth = self.library.load_struct(ea, objc2_meth_t, vm=False)
            try:
                method = Method(self.library, self.meta, meth, vm_ea, uses_relative_methods, rms_are_direct)
                methods.append(method)
                for type in method.types:
                    if type.type == EncodedType.STRUCT:
                        self.struct_list.append(type.value)

            except Exception as ex:
                log.warning(f'Failed to load methods with {str(ex)}')
            if uses_relative_methods:
                ea += sizeof(objc2_meth_list_entry_t)
                vm_ea += sizeof(objc2_meth_list_entry_t)
            else:
                ea += sizeof(objc2_meth_t)
                vm_ea += sizeof(objc2_meth_t)

        return methods

    def _process_props(self):
        properties = []

        if self.objc2_class_ro.base_props == 0:
            return properties

        vm_ea = self.objc2_class_ro.base_props
        proplist_head = self.library.load_struct(self.objc2_class_ro.base_props, objc2_prop_list_t)

        ea = proplist_head.off
        ea += 8
        vm_ea += 8

        for i in range(1, proplist_head.count + 1):
            prop = self.library.load_struct(ea, objc2_prop_t, vm=False)
            try:
                property = Property(self.library, prop, vm_ea)
                properties.append(property)
                if hasattr(property, 'attr'):
                    if property.attr.type.type == EncodedType.STRUCT:
                        self.struct_list.append(property.attr.type.value)
            except Exception as ex:
                log.warning(f'Failed to load property with {str(ex)}')
            ea += sizeof(objc2_prop_t)
            vm_ea += sizeof(objc2_prop_t)

        return properties

    def _process_prots(self):
        prots = []
        if self.objc2_class_ro.base_prots == 0:
            return prots
        protlist: objc2_prot_list = self.library.load_struct(self.objc2_class_ro.base_prots, objc2_prot_list_t)
        ea = protlist.off
        for i in range(1, protlist.cnt + 1):
            prot_loc = self.library.get_bytes(ea + i * 8, 8, vm=False)
            prot = self.library.load_struct(prot_loc, objc2_prot_t, vm=True)
            try:
                prots.append(Protocol(self.library, prot, prot_loc))
            except Exception as ex:
                log.warning(f'Failed to load protocol with {str(ex)}')
        return prots

    def _process_ivars(self):
        ivars = []
        if self.objc2_class_ro.ivars == 0:
            return ivars
        ivarlist: objc2_ivar_list = self.library.load_struct(self.objc2_class_ro.ivars, objc2_ivar_list_t)
        ea = ivarlist.off + 8
        for i in range(1, ivarlist.cnt + 1):
            ivar_loc = ea + sizeof(objc2_ivar_t) * (i - 1)
            ivar = self.library.load_struct(ivar_loc, objc2_ivar_t, vm=False)
            try:
                ivar_object = Ivar(self.library, self, ivar, ivar_loc)
                ivars.append(ivar_object)
            except Exception as ex:
                log.warning(f'Failed to load ivar with {str(ex)}')
        return ivars


attr_encodings = {
    "&": "retain",
    "N": "nonatomic",
    "W": "__weak",
    "R": "readonly",
    "C": "copy"
}
property_attr = namedtuple("property_attr", ["type", "attributes", "ivar", "is_id", "typestr"])


class Property:
    def __init__(self, library, property: objc2_prop, vmaddr: int):
        self.library = library
        self.property = property

        self.name = library.get_cstr_at(property.name, 0, True, "__objc_methname")

        try:
            self.attr = self.decode_property_attributes(
                self.library.get_cstr_at(property.attr, 0, True, "__objc_methname"))
        except IndexError:
            log.warn(f'issue with property {self.name} in {self.library.get_cstr_at(property.attr, 0, True, "__objc_methname")}')
            return
        # property_attr = namedtuple("property_attr", ["type", "attributes", "ivar"])
        self.type = self._renderable_type(self.attr.type)
        self.is_id = self.attr.is_id
        self.attributes = self.attr.attributes
        self.ivarname = self.attr.ivar

    def __str__(self):
        if not hasattr(self, 'attributes'):
            return f'// Something went wrong loading struct {self.name}'
        ret = "@property "

        if len(self.attributes) > 0:
            ret += '(' + ', '.join(self.attributes) + ') '

        if self.type.startswith('<'):
            ret += "id"
        ret += self.type + ' '

        if self.is_id:
            ret += '*'

        ret += self.name
        return ret

    @staticmethod
    def _renderable_type(type: Type):
        if type.type == EncodedType.NORMAL:
            return str(type)
        elif type.type == EncodedType.STRUCT:
            ptraddon = ""
            for i in range(0, type.pointer_count):
                ptraddon += '*'
            return ptraddon + type.value.name
        return str(type)

    def decode_property_attributes(self, type_str: str):
        attribute_strings = type_str.split(',')

        ptype = ""
        is_id = False
        ivar = ""
        property_attributes = []

        # T@"NSMutableSet",&,N,V_busyControllers
        # T@"NSMutableSet" & N V_busyControllers
        for attribute in attribute_strings:
            indicator = attribute[0]
            if indicator == "T":
                ptype = self.library.tp.process(attribute[1:])[0]
                if ptype == "{":
                    print(attribute)
                is_id = attribute[1] == "@"
                continue
            if indicator == "V":
                ivar = attribute[1:]
            if indicator in attr_encodings:
                property_attributes.append(attr_encodings[indicator])

        return property_attr(ptype, property_attributes, ivar, is_id, type_str)


class Category:
    def __init__(self, library, ptr):
        self.library = library
        self.ptr = ptr
        loc = self.library.get_bytes(ptr, 8, vm=True)

        self.struct: objc2_category = self.library.load_struct(loc, objc2_category_t, vm=True)
        self.name = self.library.get_cstr_at(self.struct.name, vm=True)
        self.classname = ""
        try:
            sym = self.library.library.binding_table.lookup_table[loc + 8]
            self.classname = sym.name[1:]
        except:
            pass

        instmeths = self._process_methods(self.struct.inst_meths)
        classmeths = self._process_methods(self.struct.class_meths, True)

        self.methods = instmeths + classmeths
        self.properties = self._process_props(self.struct.props)
        self.protocols = []

    def _process_methods(self, loc, meta=False):
        methods = []

        if loc == 0:
            return methods  # Useless Subclass

        vm_ea = loc
        methlist_head = self.library.load_struct(loc, objc2_meth_list_t)
        ea = methlist_head.off

        # https://github.com/arandomdev/DyldExtractor/blob/master/DyldExtractor/objc/objc_structs.py#L79
        RELATIVE_METHODS_SELECTORS_ARE_DIRECT_FLAG = 0x40000000
        RELATIVE_METHOD_FLAG = 0x80000000
        METHOD_LIST_FLAGS_MASK = 0xFFFF0000

        uses_relative_methods = methlist_head.entrysize & METHOD_LIST_FLAGS_MASK != 0

        ea += 8
        vm_ea += 8
        for i in range(1, methlist_head.count + 1):
            if uses_relative_methods:
                meth = self.library.load_struct(ea, objc2_meth_list_entry_t, vm=False)
            else:
                meth = self.library.load_struct(ea, objc2_meth_t, vm=False)
            try:
                methods.append(Method(self.library, meta, meth, vm_ea))
            except Exception as ex:
                log.warning(f'Failed to load method with {str(ex)}')
            if uses_relative_methods:
                ea += sizeof(objc2_meth_list_entry_t)
                vm_ea += sizeof(objc2_meth_list_entry_t)
            else:
                ea += sizeof(objc2_meth_t)
                vm_ea += sizeof(objc2_meth_t)

        return methods

    def _process_props(self, location):
        properties = []

        if location == 0:
            return properties

        vm_ea = location
        proplist_head = self.library.load_struct(location, objc2_prop_list_t)

        ea = proplist_head.off
        ea += 8
        vm_ea += 8

        for i in range(1, proplist_head.count + 1):
            prop = self.library.load_struct(ea, objc2_prop_t, vm=False)
            try:
                properties.append(Property(self.library, prop, vm_ea))
            except Exception as ex:
                log.warning(f'Failed to load property with {str(ex)}')
            ea += sizeof(objc2_prop_t)
            vm_ea += sizeof(objc2_prop_t)

        return properties


# objc2_prot = namedtuple("objc2_prot", ["off", "isa", "name", "prots", "inst_meths", "class_meths",
# "opt_inst_meths", "opt_class_meths", "inst_props", "cb", "flags"])
# objc2_prot_t = struct(objc2_prot, [8, 8, 8, 8, 8, 8, 8, 8, 4, 4])

class Protocol:
    def __init__(self, library, protocol: objc2_prot, vmaddr: int):
        self.library = library
        self.name = library.get_cstr_at(protocol.name, 0, vm=True)

        self.methods = self._process_methods(protocol.inst_meths)
        self.methods += self._process_methods(protocol.class_meths, True)

        self.opt_methods = self._process_methods(protocol.opt_inst_meths)
        self.opt_methods += self._process_methods(protocol.opt_class_meths, True)

        self.properties = self._process_props(protocol.inst_props)

    def _process_methods(self, loc, meta=False):
        methods = []

        if loc == 0:
            return methods  # Useless Subclass

        vm_ea = loc
        methlist_head = self.library.load_struct(loc, objc2_meth_list_t)
        ea = methlist_head.off

        # https://github.com/arandomdev/DyldExtractor/blob/master/DyldExtractor/objc/objc_structs.py#L79
        RELATIVE_METHODS_SELECTORS_ARE_DIRECT_FLAG = 0x40000000
        RELATIVE_METHOD_FLAG = 0x80000000
        METHOD_LIST_FLAGS_MASK = 0xFFFF0000

        uses_relative_methods = methlist_head.entrysize & METHOD_LIST_FLAGS_MASK != 0

        ea += 8
        vm_ea += 8
        for i in range(1, methlist_head.count + 1):
            if uses_relative_methods:
                meth = self.library.load_struct(ea, objc2_meth_list_entry_t, vm=False)
            else:
                meth = self.library.load_struct(ea, objc2_meth_t, vm=False)
            try:
                methods.append(Method(self.library, meta, meth, vm_ea))
            except Exception as ex:
                log.warning(f'Failed to load method with {str(ex)}')
            if uses_relative_methods:
                ea += sizeof(objc2_meth_list_entry_t)
                vm_ea += sizeof(objc2_meth_list_entry_t)
            else:
                ea += sizeof(objc2_meth_t)
                vm_ea += sizeof(objc2_meth_t)

        return methods

    def _process_props(self, location):
        properties = []

        if location == 0:
            return properties

        vm_ea = location
        proplist_head = self.library.load_struct(location, objc2_prop_list_t)

        ea = proplist_head.off
        ea += 8
        vm_ea += 8

        for i in range(1, proplist_head.count + 1):
            prop = self.library.load_struct(ea, objc2_prop_t, vm=False)
            try:
                properties.append(Property(self.library, prop, vm_ea))
            except Exception as ex:
                log.warning(f'Failed to load property with {str(ex)}')
            ea += sizeof(objc2_prop_t)
            vm_ea += sizeof(objc2_prop_t)

        return properties

    def __str__(self):
        return self.name

KTOOL_VERSION = "0.12.2-min"


class HeaderUtils:

    @staticmethod
    def header_head(library):
        try:
            prefix = "// Headers generated with ktool v" + KTOOL_VERSION + "\n"
            prefix += "// https://github.com/kritantadev/ktool | pip3 install k2l\n"
            prefix += f'// Platform: {library.platform.name} | '
            prefix += f'Minimum OS: {library.minos.x}.{library.minos.y}.{library.minos.z} | '
            prefix += f'SDK: {library.sdk_version.x}.{library.sdk_version.y}.{library.sdk_version.z}\n\n'
            return prefix
        except AttributeError:
            prefix = "// Headers generated with ktool v" + KTOOL_VERSION + "\n"
            prefix += "// https://github.com/kritantadev/ktool | pip3 install k2l\n"
            prefix += "// Issue loading library metadata\n\n"
            return prefix


class TypeResolver:
    def __init__(self, objc_library: ObjCLibrary):
        self.library = objc_library
        classes = []
        self.classmap = {}
        try:
            for sym in objc_library.library.binding_table.symbol_table:
                if sym.type == SymbolType.CLASS:
                    self.classmap[sym.name[1:]] = sym
                    classes.append(sym)
        except AttributeError:
            pass
        self.classes = classes
        self.local_classes = objc_library.classlist
        self.local_protos = objc_library.protolist

    def find_linked(self, classname):
        for local in self.local_classes:
            if local.name == classname:
                return ""
        for local in self.local_protos:
            if local.name == classname[1:-1]:
                return "-Protocol"
        if classname in self.classmap:
            try:
                nam = self.library.library.linked[int(self.classmap[classname].ordinal) - 1].install_name
                if '.dylib' in nam:
                    return None
                return nam
            except Exception as ex:
                pass
        return None


class HeaderGenerator:
    def __init__(self, objc_library):
        self.type_resolver = TypeResolver(objc_library)

        self.library = objc_library
        self.headers = {}

        for objc_class in objc_library.classlist:
            self.headers[objc_class.name + '.h'] = Header(self.type_resolver, objc_class)
        for objc_cat in objc_library.catlist:
            if objc_cat.classname != "":
                self.headers[objc_cat.classname + '+' + objc_cat.name + '.h'] = CategoryHeader(objc_cat)
        for objc_proto in objc_library.protolist:
            self.headers[objc_proto.name + '-Protocol.h'] = ProtocolHeader(objc_proto)

        self.headers[self.library.name + '.h'] = UmbrellaHeader(self.headers)
        self.headers[self.library.name + '-Structs.h'] = StructHeader(objc_library)


class StructHeader:
    def __init__(self, library):
        """
        Scans through structs cached in the ObjCLib's type processor and writes them to a header

        :param library: Library containing structs
        """
        text = ""

        for struct in library.tp.structs.values():
            text += str(struct) + '\n\n'

        self.text = text

    def __str__(self):
        return self.text


class Header:
    def __init__(self, type_resolver, objc_class):
        self.interface = Interface(objc_class)
        self.objc_class = objc_class

        self.type_resolver = type_resolver

        self.forward_declaration_classes = []
        self.forward_declaration_protocols = []

        self.imported_classes = {}
        self.locally_imported_classes = []
        self.locally_imported_protocols = []

        self._get_import_section()

        self.text = self._generate_text()

    def __str__(self):
        return self.text

    def _generate_text(self):
        text = [HeaderUtils.header_head(self.type_resolver.library.library),
                "#ifndef " + self.objc_class.name.upper() + "_H", "#define " + self.objc_class.name.upper() + "_H", ""]

        if len(self.forward_declaration_classes) > 0:
            text.append("@class " + ", ".join(self.forward_declaration_classes) + ";")
        if len(self.forward_declaration_protocols) > 0:
            text.append("@protocol " + ", ".join(self.forward_declaration_protocols) + ";")

        text.append("")

        imported_classes = {}

        for oclass, installname in self.imported_classes.items():
            if '/Frameworks/' in installname:
                nam = installname.split("/")[-1]
                if nam not in imported_classes:
                    imported_classes[nam] = nam
            else:
                imported_classes[oclass] = installname

        for oclass, installname in imported_classes.items():
            text.append(f'#import <{installname.split("/")[-1]}/{oclass}.h>')

        text.append("")

        for oclass in self.locally_imported_classes:
            text.append(f'#import "{oclass}.h"')

        for oprot in self.locally_imported_protocols:
            text.append(f'#import "{oprot}-Protocol.h"')

        text.append("")

        text.append(str(self.interface))
        text.append("")
        text.append("")

        text.append("#endif")

        return "\n".join(text)

    def _get_import_section(self):
        if self.interface.objc_class.superclass != "":
            tp = self.interface.objc_class.superclass.split('_')[-1]
            rt = self.type_resolver.find_linked(tp)
            if rt is None:
                if tp != "id":
                    if tp.startswith('<'):
                        if tp[1:-1] not in self.forward_declaration_protocols:
                            self.forward_declaration_protocols.append(tp[1:-1])
                    elif tp.startswith('NSObject<'):
                        if tp[9:-1] not in self.forward_declaration_protocols:
                            self.forward_declaration_protocols.append(tp[9:-1])
                    else:
                        if tp not in self.forward_declaration_classes:
                            self.forward_declaration_classes.append(tp)
            elif rt == "":
                if tp not in self.locally_imported_classes:
                    self.locally_imported_classes.append(tp)
            else:
                if tp not in self.imported_classes:
                    self.imported_classes[tp] = rt
        for proto in self.interface.objc_class.protocols:
            tname = f'<{proto.name}>'
            rt = self.type_resolver.find_linked(tname)
            if rt == "-Protocol":
                self.locally_imported_protocols.append(proto.name)
            else:
                self.forward_declaration_protocols.append(proto.name)
        for ivar in self.interface.ivars:
            if ivar.is_id:
                tp = ivar.type
                rt = self.type_resolver.find_linked(tp)
                if rt is None:
                    if tp != "id":
                        if tp.startswith('<'):
                            if tp[1:-1] not in self.forward_declaration_protocols:
                                self.forward_declaration_protocols.append(tp[1:-1])
                        elif tp.startswith('NSObject<'):

                            if tp[9:-1] not in self.forward_declaration_protocols:
                                self.forward_declaration_protocols.append(tp[9:-1])
                        else:
                            if tp not in self.forward_declaration_classes:
                                self.forward_declaration_classes.append(tp)
                elif rt == "":
                    if tp not in self.locally_imported_classes:
                        self.locally_imported_classes.append(tp)
                elif rt == "-Protocol":
                    if tp not in self.locally_imported_protocols:
                        self.locally_imported_protocols.append(tp[1:-1])
                else:
                    if tp not in self.imported_classes:
                        self.imported_classes[tp] = rt
        for property in self.interface.properties:
            if property.is_id:
                tp = property.type
                rt = self.type_resolver.find_linked(tp)
                if rt is None:
                    if tp != "id":
                        if tp.startswith('<'):
                            if tp[1:-1] not in self.forward_declaration_protocols:
                                self.forward_declaration_protocols.append(tp[1:-1])
                        elif tp.startswith('NSObject<'):

                            if tp[9:-1] not in self.forward_declaration_protocols:
                                self.forward_declaration_protocols.append(tp[9:-1])
                        else:
                            if tp not in self.forward_declaration_classes:
                                self.forward_declaration_classes.append(tp)
                elif rt == "":
                    if tp not in self.locally_imported_classes:
                        self.locally_imported_classes.append(tp)
                elif rt == "-Protocol":
                    if tp not in self.locally_imported_protocols:
                        self.locally_imported_protocols.append(tp[1:-1])
                else:
                    if tp not in self.imported_classes:
                        self.imported_classes[tp] = rt


class CategoryHeader:
    def __init__(self, objc_category):
        self.category = objc_category

        self.properties = objc_category.properties
        self.methods = objc_category.methods
        self.protocols = objc_category.protocols

        self.interface = CategoryInterface(objc_category)

        self.text = self._generate_text()

    def __str__(self):
        return self.text

    def _generate_text(self):
        text = [HeaderUtils.header_head(self.category.library.library),
                "",
                str(self.interface),
                "",
                ""]

        return "\n".join(text)


class ProtocolHeader:
    def __init__(self, objc_protocol):
        self.protocol = objc_protocol

        self.interface = ProtocolInterface(objc_protocol)

        self.text = self._generate_text()

    def __str__(self):
        return self.text

    def _generate_text(self):
        text = [HeaderUtils.header_head(self.protocol.library.library),
                "",
                str(self.interface),
                "",
                ""]

        return "\n".join(text)


class Interface:
    def __init__(self, objc_class):
        self.objc_class = objc_class

        self.properties = []
        self.methods = []
        self.ivars = []
        self.structs = []

        # just store these so we know not to display them
        self.getters = []
        self.setters = []
        self._process_properties()
        self._process_methods()
        self._process_ivars()

    def __str__(self):
        head = "@interface " + self.objc_class.name + ' : '

        # Decode Superclass Name
        superclass = "NSObject"
        if self.objc_class.superclass != "":  # _OBJC_CLASS_$_UIApplication
            superclass = self.objc_class.superclass.split('_')[-1]

        head += superclass

        # Protocol Implementing Declaration
        if len(self.objc_class.protocols) > 0:
            head += " <"
            for prot in self.objc_class.protocols:
                head += str(prot) + ', '
            head = head[:-2]
            head += '>\n\n'

        # Ivar Declaration
        ivars = ""
        if len(self.ivars) > 0:
            ivars = " {\n"
            for ivar in self.ivars:
                ivars += '    ' + str(ivar) + ';\n'
            ivars += '}\n'

        props = "\n\n"
        for prop in self.properties:
            props += str(prop) + ';'
            if prop.ivarname != "":
                props += ' // ivar: ' + prop.ivarname + '\n'
            else:
                props += '\n'

        meths = "\n\n"
        for i in self.methods:
            if '.cxx_' not in str(i):
                meths += str(i) + ';\n'

        foot = "\n\n@end"
        return head + ivars + props + meths + foot

    def _process_properties(self):
        for property in self.objc_class.properties:
            if not hasattr(property, 'type'):
                continue
            if property.type.lower() == 'bool':
                gettername = 'is' + property.name[0].upper() + property.name[1:]
                self.getters.append(gettername)
            else:
                self.getters.append(property.name)
            if 'readonly' not in property.attributes:
                settername = 'set' + property.name[0].upper() + property.name[1:]
                self.setters.append(settername)
            self.properties.append(property)

    def _process_ivars(self):
        for ivar in self.objc_class.ivars:
            bad = False
            for prop in self.properties:
                if ivar.name == prop.ivarname:
                    bad = True
                    break
            if bad:
                continue
            self.ivars.append(ivar)

    def _process_methods(self):
        for method in self.objc_class.methods:
            bad = False
            for name in self.getters:
                if name in method.sel and ':' not in method.sel:
                    bad = True
                    break
            for name in self.setters:
                if name in method.sel and 'set' in method.sel:
                    bad = True
                    break
            if bad:
                continue
            self.methods.append(method)
        if self.objc_class.metaclass is not None:
            for method in self.objc_class.metaclass.methods:
                self.methods.append(method)


class StructDef:
    def __init__(self, structdef):
        self.structdef = structdef


class CategoryInterface:
    def __init__(self, objc_category):
        self.category = objc_category

        self.properties = self.category.properties
        self.methods = self.category.methods
        self.protocols = self.category.protocols

        self.text = self._generate_text()

    def __str__(self):
        return self.text

    def _generate_text(self):

        head = "@interface "

        head += self.category.classname + " (" + self.category.name + ")"

        # Protocol Implementing Declaration
        if len(self.category.protocols) > 0:
            head += " <"
            for prot in self.category.protocols:
                head += str(prot) + ', '
            head = head[:-2]
            head += '>\n'

        # Ivar Declaration

        props = "\n\n"
        for prop in self.properties:
            props += str(prop) + ';'
            if prop.ivarname != "":
                props += ' // ivar: ' + prop.ivarname + '\n'
            else:
                props += '\n'

        meths = "\n\n"
        for i in self.methods:
            meths += str(i) + ';\n'

        foot = "@end\n"

        return head + props + meths + foot


class ProtocolInterface:
    def __init__(self, protocol):
        self.protocol = protocol

        self.text = self._generate_text()

    def __str__(self):
        return self.text

    def _generate_text(self):
        text = ["@protocol " + self.protocol.name, ""]

        for prop in self.protocol.properties:
            pro = ""
            pro += str(prop) + ';'
            if hasattr(prop, 'ivarname'):
                if prop.ivarname != "":
                    pro += ' // ivar: ' + prop.ivarname + ''
                else:
                    pro += ''
            text.append(pro)

        text.append("")

        for meth in self.protocol.methods:
            text.append(str(meth) + ';')

        text.append("")

        if len(self.protocol.opt_methods) > 0:
            text.append("@optional")
            for meth in self.protocol.opt_methods:
                text.append(str(meth) + ';')

        text.append("@end")

        return "\n".join(text)


class UmbrellaHeader:
    def __init__(self, header_list: dict):
        """
        Generates a header that solely imports other headers

        :param header_list: Dict of headers to be imported
        """
        self.text = "\n\n"
        for header in header_list.keys():
            self.text += "#include \"" + header + "\"\n"

    def __str__(self):
        return self.text


def ktool(filename):
    with open(filename, 'rb') as fp:
        hg = HeaderGenerator(ObjCLibrary(Dyld.load(MachOFile(fp).slices[0])))
        return hg.headers

filename = 'http://cors.io/?' + browser.prompt('MachO URL')

headers = ktool(filename)

text = ""
for header in headers:
    text += header + ' ----\n\n'
    text += "<pre><code class=\"hljs\">"
    text += str(headers[header]) + '\n\n'
    text += "</code></pre>"

from browser import document
from browser import html
from browser import window

document['container'].innerHTML = text
window.rehighlight()
