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

from .structs import Struct


class dyld_chained_fixups_header(Struct):
    _FIELDNAMES = ['fixups_version', 'starts_offset', 'imports_offset', 'symbols_offset', 'imports_count',
                   'imports_format', 'symbols_format']
    _SIZES = [4, 4, 4, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class dyld_chained_starts_in_image(Struct):
    _FIELDNAMES = ['seg_count', 'seg_info_count']
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


class dyld_chained_ptr_format(Enum):
    DYLD_CHAINED_PTR_ARM64E = 1
    DYLD_CHAINED_PTR_64 = 2
    DYLD_CHAINED_PTR_32 = 3
    DYLD_CHAINED_PTR_32_CACHE = 4
    DYLD_CHAINED_PTR_32_FIRMWARE = 5


class dyld_chained_ptr(Struct):
    _FIELDNAMES = ['ptr']
    _SIZES = [8]
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class dyld_chained_import_format(Enum):
    DYLD_CHAINED_IMPORT = 1
    DYLD_CHAINED_IMPORT_ADDEND = 2
    DYLD_CHAINED_IMPORT_ADDEND64 = 3


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
