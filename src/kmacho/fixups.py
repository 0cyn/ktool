#
#  ktool | kmacho
#  fixups.py
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

from enum import Enum

from kmacho.structs import *


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
    _SIZES = [4, 1, 1, 4, 2, 1, 1]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


DYLD_CHAINED_PTR_START_NONE = 0xFFFF
DYLD_CHAINED_PTR_START_MULTI = 0x8000
DYLD_CHAINED_PTR_START_LAST = DYLD_CHAINED_PTR_START_MULTI


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
    DYLD_CHAINED_PTR_NOIDEA = 12


class dyld_chained_import_format(Enum):
    DYLD_CHAINED_IMPORT = 1
    DYLD_CHAINED_IMPORT_ADDEND = 2
    DYLD_CHAINED_IMPORT_ADDEND64 = 3


class dyld_chained_ptr(Struct):
    _FIELDNAMES = ['ptr']
    _SIZES = [8]
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


def ptr_arm64e_type(ptr: 'dyld_chained_ptr_arm64e'):
    if ptr.auth:
        if ptr.bind:
            return dyld_chained_ptr_arm64e_auth_bind
        else:
            return dyld_chained_ptr_arm64e_auth_rebase
    else:
        if ptr.bind:
            return dyld_chained_ptr_arm64e_bind
        else:
            return dyld_chained_ptr_arm64e_rebase


def ptr_arm64_type(ptr: 'dyld_chained_ptr'):
    if ptr.bind:
        return dyld_chained_ptr_64_bind
    return dyld_chained_ptr_64_rebase


DYLD_CHAINED_PTR_FMATS = {
    dyld_chained_ptr_format.DYLD_CHAINED_PTR_ARM64E: ptr_arm64e_type,
    dyld_chained_ptr_format.DYLD_CHAINED_PTR_64: ptr_arm64_type,
    dyld_chained_ptr_format.DYLD_CHAINED_PTR_NOIDEA: ptr_arm64e_type
}


class dyld_chained_ptr_arm64e(BitFieldStruct):
    _FIELDNAMES = ['value']
    _BITFIELDS = ['reserved', 'bind', 'auth']
    _SIZES = [8]
    _BF_SIZES = [62, 1, 1]
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.bind = 0
        self.auth = 0


class dyld_chained_ptr_arm64e_rebase(BitFieldStruct):
    _FIELDNAMES = ['value']
    _BITFIELDS = ['target', 'high8', 'next', 'bind', 'auth']
    _SIZES = [8]
    _BF_SIZES = [43, 8, 11, 1, 1]
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class dyld_chained_ptr_arm64e_bind(BitFieldStruct):
    _FIELDNAMES = ['value']
    _BITFIELDS = ['ordinal', 'zero', 'addend', 'next', 'bind', 'auth']
    _SIZES = [uint64_t]
    _BF_SIZES = [16, 16, 19, 11, 1, 1]
    SIZE = uint64_t

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class dyld_chained_ptr_arm64e_auth_rebase(BitFieldStruct):
    _FIELDNAMES = ['value']
    _BITFIELDS = ['target', 'diversity', 'addrDiv', 'key', 'next', 'bind', 'auth']
    _SIZES = [uint64_t]
    _BF_SIZES = [32, 16, 1, 2, 11, 1, 1]
    SIZE = uint64_t

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class dyld_chained_ptr_arm64e_auth_bind(BitFieldStruct):
    _FIELDNAMES = ['value']
    _BITFIELDS = ['ordinal', 'zero', 'diversity', 'addrDiv', 'key', 'next', 'bind', 'auth']
    _SIZES = [uint64_t]
    _BF_SIZES = [16, 16, 16, 1, 2, 11, 1, 1]
    SIZE = uint64_t

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class dyld_chained_ptr_64(BitFieldStruct):
    _FIELDNAMES = ['value']
    _BITFIELDS = ['reserved', 'bind']
    _SIZES = [8]
    _BF_SIZES = [63, 1]
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class dyld_chained_ptr_64_rebase(BitFieldStruct):
    _FIELDNAMES = ['value']
    _BITFIELDS = ['target', 'high8', 'reserved', 'next', 'bind']
    _SIZES = [8]
    _BF_SIZES = [36, 8, 7, 12, 1]
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class dyld_chained_ptr_64_bind(BitFieldStruct):
    _FIELDNAMES = ['value']
    _BITFIELDS = ['ordinal', 'addend', 'reserved', 'next', 'bind']
    _SIZES = [uint64_t]
    _BF_SIZES = [24, 8, 19, 12, 1]
    SIZE = uint64_t

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class dyld_chained_import(Struct):
    _FIELDNAMES = ['_import']
    _SIZES = [4]
    SIZE = 4

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class dyld_chained_import_addend(Struct):
    _FIELDNAMES = ['import', 'addend']
    _SIZES = [4, 4]
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class dyld_chained_import_addend64(Struct):
    _FIELDNAMES = ['import', 'addend']
    _SIZES = [8, 8]
    SIZE = 16

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


DYLD_CHAINED_PTR_BASE = {
    dyld_chained_ptr_format.DYLD_CHAINED_PTR_ARM64E: dyld_chained_ptr_arm64e,
    dyld_chained_ptr_format.DYLD_CHAINED_PTR_NOIDEA: dyld_chained_ptr_arm64e,
    dyld_chained_ptr_format.DYLD_CHAINED_PTR_64: dyld_chained_ptr_64
}

