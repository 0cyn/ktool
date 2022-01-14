#
#  ktool | kmacho
#  mach_header.py
#
#
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2021.
#


from enum import IntEnum

from .structs import *

MH_MAGIC = 0xFEEDFACE
MH_CIGAM = 0xCEFAEDFE
MH_MAGIC_64 = 0xFEEDFACF
MH_CIGAM_64 = 0xCFFAEDFE
FAT_MAGIC = 0xCAFEBABE
FAT_CIGAM = 0xBEBAFECA


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
    UNK = 0
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
    SUB_image = 0x15
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
    LC_DYLD_EXPORTS_TRIE = 0x33 | LC_REQ_DYLD
    LC_DYLD_CHAINED_FIXUPS = 0x34 | LC_REQ_DYLD


LOAD_COMMAND_MAP = {
    LOAD_COMMAND.SEGMENT: segment_command,
    LOAD_COMMAND.SYMTAB: symtab_command,
    LOAD_COMMAND.DYSYMTAB: dysymtab_command,
    LOAD_COMMAND.LOAD_DYLIB: dylib_command,
    LOAD_COMMAND.ID_DYLIB: dylib_command,
    LOAD_COMMAND.LOAD_DYLINKER: dylinker_command,
    LOAD_COMMAND.SUB_CLIENT: sub_client_command,
    LOAD_COMMAND.LOAD_WEAK_DYLIB: dylib_command,
    LOAD_COMMAND.SEGMENT_64: segment_command_64,
    LOAD_COMMAND.UUID: uuid_command,
    LOAD_COMMAND.CODE_SIGNATURE: linkedit_data_command,
    LOAD_COMMAND.SEGMENT_SPLIT_INFO: linkedit_data_command,
    LOAD_COMMAND.SOURCE_VERSION: source_version_command,
    LOAD_COMMAND.DYLD_INFO_ONLY: dyld_info_command,
    LOAD_COMMAND.FUNCTION_STARTS: linkedit_data_command,
    LOAD_COMMAND.DATA_IN_CODE: linkedit_data_command,
    LOAD_COMMAND.BUILD_VERSION: build_version_command,
    LOAD_COMMAND.MAIN: entry_point_command,
    LOAD_COMMAND.RPATH: rpath_command,
    LOAD_COMMAND.VERSION_MIN_MACOSX: version_min_command,
    LOAD_COMMAND.VERSION_MIN_IPHONEOS: version_min_command,
    LOAD_COMMAND.VERSION_MIN_TVOS: version_min_command,
    LOAD_COMMAND.VERSION_MIN_WATCHOS: version_min_command,
    LOAD_COMMAND.LC_DYLD_EXPORTS_TRIE: linkedit_data_command,
    LOAD_COMMAND.LC_DYLD_CHAINED_FIXUPS: linkedit_data_command
}


class S_FLAGS_MASKS(IntEnum):
    SECTION_TYPE = 0x000000ff
    SECTION_ATTRIBUTES = 0xffffff00
    SECTION_ATTRIBUTES_USR = 0xff000000
    SECTION_ATTRIBUTES_SYS = 0x00ffff00


class SectionType(IntEnum):
    S_REGULAR = 0x00  # Regular section
    S_ZEROFILL = 0x01  # Zero fill on demand section.
    S_CSTRING_LITERALS = 0x02  # Section with literal C strings
    S_4BYTE_LITERALS = 0x03  # Section with 4 byte literals.
    S_8BYTE_LITERALS = 0x04  # Section with 8 byte literals.
    S_LITERAL_POINTERS = 0x05  # Section with pointers to literals.
    S_NON_LAZY_SYMBOL_POINTERS = 0x06  # Section with non-lazy symbol pointers.
    S_LAZY_SYMBOL_POINTERS = 0x07  # Section with lazy symbol pointers.
    S_SYMBOL_STUBS = 0x08  # Section with symbol stubs, byte size of stub in the Reserved2 field.
    S_MOD_INIT_FUNC_POINTERS = 0x09  # Section with only function pointers for initialization.
    S_MOD_TERM_FUNC_POINTERS = 0x0A  # Section with only function pointers for initialization.
    S_COALESCED = 0x0B  # Section contains symbols that are to be coalesced.
    S_GB_ZEROFILL = 0x0C  # Zero fill on demand section (that can be larger than 4 gigabytes).
    S_INTERPOSING = 0x0D  # Section with only pairs of function pointers for interposing.
    S_16BYTE_LITERALS = 0x0E  # Section with only 16 byte literals.
    S_DTRACE_DOF = 0x0F  # Section contains DTrace Object Format.
    S_LAZY_DYLIB_SYMBOL_POINTERS = 0x10  # Section with lazy symbol pointers to lazy loaded dylibs.
    S_THREAD_LOCAL_REGULAR = 0x11  # Thread local data section.
    S_THREAD_LOCAL_ZEROFILL = 0x12  # Thread local zerofill section.
    S_THREAD_LOCAL_VARIABLES = 0x13  # Section with thread local variable structure data.
    S_THREAD_LOCAL_VARIABLE_POINTERS = 0x14  # Section with pointers to thread local structures.
    S_THREAD_LOCAL_INIT_FUNCTION_POINTERS = 0x15  # Section with thread local variable initialization pointers to functions.


class SectionAttributesUser(IntEnum):
    S_ATTR_PURE_INSTRUCTIONS = 0x80000000  # Section contains only true machine instructions.
    S_ATTR_NO_TOC = 0x40000000  # Section contains coalesced symbols that are not to be in a ranlib table of contents.
    S_ATTR_STRIP_STATIC_SYMS = 0x20000000  # Ok to strip static symbols in this section in files with the MY_DYLDLINK flag.
    S_ATTR_NO_DEAD_STRIP = 0x10000000  # No dead stripping.
    S_ATTR_LIVE_SUPPORT = 0x08000000  # Blocks are live if they reference live blocks.
    S_ATTR_SELF_MODIFYING_CODE = 0x04000000  # Used with i386 code stubs written on by
    S_ATTR_DEBUG = 0x02000000  # A debug section.


class SectionAttributesSys(IntEnum):
    S_ATTR_SOME_INSTRUCTIONS = 0x00000400
    S_ATTR_EXT_RELOC = 0x00000200
    S_ATTR_LOC_RELOC = 0x00000100


CPU_ARCH_MASK = 0xff000000  # Mask for architecture bits
CPU_ARCH_ABI64 = 0x01000000


class CPUType(IntEnum):
    ANY = -1
    X86 = 7
    X86_64 = X86 | CPU_ARCH_ABI64
    MC98000 = 10
    ARM = 12
    ARM64 = ARM | CPU_ARCH_ABI64
    SPARC = 14
    POWERPC = 18
    POWERPC64 = POWERPC | CPU_ARCH_ABI64


class CPUSubTypeX86(IntEnum):
    ALL = 3
    ARCH1 = 4


class CPUSubTypeX86_64(IntEnum):
    ALL = 3
    H = 8


class CPUSubTypeARM(IntEnum):
    ALL = 0
    V4T = 5
    V6 = 6
    V5 = 7
    V5TEJ = 7
    XSCALE = 8
    V7 = 9
    ARM_V7F = 10
    V7S = 11
    V7K = 12
    V6M = 14
    V7M = 15
    V7EM = 16


class CPUSubTypeARM64(IntEnum):
    ALL = 0
    ARM64E = 2
    ARM64E2 = 0x80000002


class CPUSubTypeSPARC(IntEnum):
    ALL = 0


class CPUSubTypePowerPC(IntEnum):
    ALL = 0
    _601 = 1
    _602 = 2
    _603 = 3
    _603e = 4
    _603ev = 5
    _604 = 6
    _604e = 7
    _620 = 8
    _750 = 9
    _7400 = 10
    _7450 = 11
    _970 = 100


CPU_SUBTYPES = {
    CPUType.X86: CPUSubTypeX86,
    CPUType.X86_64: CPUSubTypeX86_64,
    CPUType.POWERPC: CPUSubTypePowerPC,
    CPUType.ARM: CPUSubTypeARM,
    CPUType.ARM64: CPUSubTypeARM64,
    CPUType.SPARC: CPUSubTypeSPARC
}
