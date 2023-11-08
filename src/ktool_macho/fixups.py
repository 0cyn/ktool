#
#  ktool | ktool_macho
#  fixups.py
#
#
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) 0cyn 2021.
#

from enum import Enum

from ktool_macho.structs import *


class dyld_chained_fixups_header(Struct):
    _FIELDNAMES = ['fixups_version', 'starts_offset', 'imports_offset', 'symbols_offset', 'imports_count',
                   'imports_format', 'symbols_format']
    _SIZES = [4, 4, 4, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class dyld_chained_starts_in_image(Struct):
    _FIELDNAMES = ['seg_count', 'seg_info_offset']
    _SIZES = [4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class dyld_chained_starts_in_segment(Struct):
    _FIELDNAMES = ['size', 'page_size', 'pointer_format', 'segment_offset', 'max_valid_pointer', 'page_count',
                   'page_starts']
    _SIZES = [4, 2, 2, 8, 4, 2, 2]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


DYLD_CHAINED_PTR_START_NONE = 0xFFFF
DYLD_CHAINED_PTR_START_MULTI = 0x8000
DYLD_CHAINED_PTR_START_LAST = 0x8000


class dyld_chained_start_offsets(Struct):
    _FIELDNAMES = ['pointer_format', 'starts_count', 'chain_starts']
    _SIZES = [2, 2, 2]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


"""
enum {
    DYLD_CHAINED_PTR_ARM64E                 =  1,    // stride 8, unauth target is vmaddr
    DYLD_CHAINED_PTR_64                     =  2,    // target is vmaddr
    DYLD_CHAINED_PTR_32                     =  3,
    DYLD_CHAINED_PTR_32_CACHE               =  4,
    DYLD_CHAINED_PTR_32_FIRMWARE            =  5,
    DYLD_CHAINED_PTR_64_OFFSET              =  6,    // target is vm offset
    DYLD_CHAINED_PTR_ARM64E_OFFSET          =  7,    // old name
    DYLD_CHAINED_PTR_ARM64E_KERNEL          =  7,    // stride 4, unauth target is vm offset
    DYLD_CHAINED_PTR_64_KERNEL_CACHE        =  8,
    DYLD_CHAINED_PTR_ARM64E_USERLAND        =  9,    // stride 8, unauth target is vm offset
    DYLD_CHAINED_PTR_ARM64E_FIRMWARE        = 10,    // stride 4, unauth target is vmaddr
    DYLD_CHAINED_PTR_X86_64_KERNEL_CACHE    = 11,    // stride 1, x86_64 kernel caches
    there is apparently a 12. it is not in xnu source. i found it in an arm64e userland (Console.app M1) bin, so we're assuming its
                                                        like, 1 I guess. 
};"""


class dyld_chained_ptr_format(Enum):
    DYLD_CHAINED_PTR_ARM64E = 1
    DYLD_CHAINED_PTR_64 = 2
    DYLD_CHAINED_PTR_32 = 3
    DYLD_CHAINED_PTR_32_CACHE = 4
    DYLD_CHAINED_PTR_32_FIRMWARE = 5
    DYLD_CHAINED_PTR_64_OFFSET = 6
    DYLD_CHAINED_PTR_ARM64E_OFFSET = 7
    DYLD_CHAINED_PTR_ARM64E_KERNEL = 7
    DYLD_CHAINED_PTR_64_KERNEL_CACHE = 8
    DYLD_CHAINED_PTR_ARM64E_USERLAND = 9
    DYLD_CHAINED_PTR_ARM64E_FIRMWARE = 10
    DYLD_CHAINED_PTR_x86_64_KERNEL_CACHE = 11
    DYLD_CHAINED_PTR_ARM64E_USERLAND24 = 12


class dyld_chained_import_format(Enum):
    DYLD_CHAINED_IMPORT = 1
    DYLD_CHAINED_IMPORT_ADDEND = 2
    DYLD_CHAINED_IMPORT_ADDEND64 = 3


class ChainedFixupPointerGeneric(Enum):
    GenericArm64eFixupFormat = 0
    Generic64FixupFormat = 1
    Generic32FixupFormat = 2
    Firmware32FixupFormat = 3
    Error = 4


class dyld_chained_import(Struct):
    _FIELDS = {"value": Bitfield(
        {'lib_ordinal': 8,
         'weak_import': 1,
         'name_offset': 23}
    )}
    SIZE = uint32_t

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_chained_import_addend(Struct):
    _FIELDS = {"value": Bitfield(
        {'lib_ordinal': 8,
         'weak_import': 1,
         'name_offset': 23}
    ),
    "addend": int32_t}
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_chained_import_addend64(Struct):
    _FIELDS = {"value": Bitfield(
        {'lib_ordinal': 16,
         'weak_import': 1,
         'reserved': 15,
         'name_offset': 32}
    ),
    "addend": uint64_t}
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_chained_ptr(Struct):
    _FIELDNAMES = ['ptr']
    _SIZES = [8]
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class dyld_chained_ptr_arm64e(Struct):
    _FIELDS = {"reserved": Bitfield({'reserved': 62, 'bind': 1, 'auth': 1})}
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)
        self.bind = 0
        self.auth = 0


class dyld_chained_ptr_arm64e_rebase(Struct):
    _FIELDS = {'target': Bitfield({'target': 43, 'high8': 8, 'next': 11, 'bind': 1, 'auth': 1})}
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_chained_ptr_arm64e_bind(Struct):
    _FIELDS = {'ordinal': Bitfield({'ordinal': 16, 'zero': 16, 'addend': 19, 'next': 11, 'bind': 1, 'auth': 1})}
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_chained_ptr_arm64e_auth_rebase(Struct):
    _FIELDS = {
        'target': Bitfield({'target': 32, 'diversity': 16, 'addrDiv': 1, 'key': 2, 'next': 11, 'bind': 1, 'auth': 1})}
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_chained_ptr_arm64e_auth_bind(Struct):
    _FIELDS = {'value': Bitfield(
        {'ordinal': 16, 'zero': 16, 'diversity': 16, 'addrDiv': 1, 'key': 2, 'next': 11, 'bind': 1, 'auth': 1})}
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_chained_ptr_64(Struct):
    _FIELDS = {'value': Bitfield({'reserved': 63, 'bind': 1})}
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_chained_ptr_64_rebase(Struct):
    _FIELDS = {'value': Bitfield({'target': 36, 'high8': 8, 'reserved': 7, 'next': 12, 'bind': 1})}
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_chained_ptr_64_bind(Struct):
    _FIELDS = {'value': Bitfield({'ordinal': 24, 'addend': 8, 'reserved': 19, 'next': 12, 'bind': 1})}
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_chained_ptr_arm64e_bind24(Struct):
    _FIELDS = {'value': Bitfield({'ordinal': 24, 'zero': 8, 'addend': 19, 'next': 11, 'bind': 1, 'auth': 1, })}
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_chained_ptr_arm64e_auth_bind24(Struct):
    _FIELDS = {'value': Bitfield(
        {'ordinal': 24, 'zero': 8, 'diversity': 16, 'addrDiv': 1, 'key': 2, 'next': 11, 'bind': 1, 'auth': 1, })}
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_chained_ptr_32_rebase(Struct):
    _FIELDS = {'value': Bitfield({'target': 26, 'next': 5, 'bind': 1})}
    SIZE = 4

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_chained_ptr_32_bind(Struct):
    _FIELDS = {'value': Bitfield({'ordinal': 20, 'addend': 6, 'next': 5, 'bind': 1})}
    SIZE = 4

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_chained_ptr_32_cache_rebase(Struct):
    _FIELDS = {'value': Bitfield({'target': 30, 'next': 2})}
    SIZE = 4

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_chained_ptr_32_firmware_rebase(Struct):
    _FIELDS = {'value': Bitfield({'target': 26, 'next': 6})}
    SIZE = 4

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class ChainedPointerArm64E(StructUnion):
    SIZE = 8

    def __init__(self):
        super().__init__(uint64_t, [dyld_chained_ptr_arm64e_auth_rebase, dyld_chained_ptr_arm64e_auth_bind,
            dyld_chained_ptr_arm64e_rebase, dyld_chained_ptr_arm64e_bind, dyld_chained_ptr_arm64e_bind24,
            dyld_chained_ptr_arm64e_auth_bind24, ])


class ChainedPointerGeneric64(StructUnion):
    SIZE = 8

    def __init__(self):
        super().__init__(uint64_t, [dyld_chained_ptr_64_rebase, dyld_chained_ptr_64_bind, ])


class ChainedPointerGeneric32(StructUnion):
    SIZE = 8

    def __init__(self):
        super().__init__(uint64_t, [dyld_chained_ptr_32_rebase, dyld_chained_ptr_32_bind,
                                    dyld_chained_ptr_32_firmware_rebase])


class ChainedFixupPointer64Union(StructUnion):
    SIZE = 8

    def __init__(self):
        super().__init__(uint64_t, [ChainedPointerArm64E, ChainedPointerGeneric64])


class ChainedFixupPointer32(Struct):
    _FIELDS = {'generic32': ChainedPointerGeneric32}
    SIZE = 4

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class ChainedFixupPointer64(Struct):
    _FIELDS = {'generic64': ChainedFixupPointer64Union}
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)
