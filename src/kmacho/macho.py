from enum import Enum, IntEnum


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
    SEGMENT                  = 0x1
    SYMTAB                   = 0x2
    SYMSEG                   = 0x3
    THREAD                   = 0x4
    UNIXTHREAD               = 0x5
    LOADFVMLIB               = 0x6
    IDFVMLIB                 = 0x7
    IDENT                    = 0x8
    FVMFILE                  = 0x9
    PREPAGE                  = 0xA
    DYSYMTAB                 = 0xB
    LOAD_DYLIB               = 0xC
    ID_DYLIB                 = 0xD
    LOAD_DYLINKER            = 0xE
    ID_DYLINKER              = 0xF
    PREBOUND_DYLIB           = 0x10
    ROUTINES                 = 0x11
    SUB_FRAMEWORK            = 0x12
    SUB_UMBRELLA             = 0x13
    SUB_CLIENT               = 0x14
    SUB_LIBRARY              = 0x15
    TWOLEVEL_HINTS           = 0x16
    PREBIND_CKSUM            = 0x17
    LOAD_WEAK_DYLIB          = 0x18 | LC_REQ_DYLD
    SEGMENT_64               = 0x19
    ROUTINES_64              = 0x1a
    UUID                     = 0x1b
    RPATH                    = 0x1C | LC_REQ_DYLD
    CODE_SIGNATURE           = 0x1D
    SEGMENT_SPLIT_INFO       = 0x1E
    REEXPORT_DYLIB           = 0x1F | LC_REQ_DYLD
    LAZY_LOAD_DYLIB          = 0x20
    ENCRYPTION_INFO          = 0x21
    DYLD_INFO                = 0x22
    DYLD_INFO_ONLY           = 0x22 | LC_REQ_DYLD
    LOAD_UPWARD_DYLIB        = 0x23 | LC_REQ_DYLD
    VERSION_MIN_MACOSX       = 0x24
    VERSION_MIN_IPHONEOS     = 0x25
    FUNCTION_STARTS          = 0x26
    DYLD_ENVIRONMENT         = 0x27
    MAIN                     = 0x28 | LC_REQ_DYLD
    DATA_IN_CODE             = 0x29
    SOURCE_VERSION           = 0x2A
    DYLIB_CODE_SIGN_DRS      = 0x2B
    ENCRYPTION_INFO_64       = 0x2C
    LINKER_OPTION            = 0x2D
    LINKER_OPTIMIZATION_HINT = 0x2E
    VERSION_MIN_TVOS         = 0x2F
    VERSION_MIN_WATCHOS      = 0x30
    NOTE                     = 0x31
    BUILD_VERSION            = 0x32




