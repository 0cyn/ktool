#
#  ktool | kmacho
#  codesign.py
#
#
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2022.
#

from kmacho.structs import Struct, uint32_t

CSMAGIC_REQUIREMENT = 0xfade0c00
CSMAGIC_REQUIREMENTS           = 0xfade0c01
CSMAGIC_CODEDIRECTORY          = 0xfade0c02
CSMAGIC_EMBEDDED_SIGNATURE     = 0xfade0cc0
CSMAGIC_EMBEDDED_SIGNATURE_OLD = 0xfade0b02
CSMAGIC_EMBEDDED_ENTITLEMENTS  = 0xfade7171
CSMAGIC_EMBEDDED_DERFORMAT     = 0xfade7172
CSMAGIC_DETACHED_SIGNATURE     = 0xfade0cc1
CSMAGIC_BLOBWRAPPER            = 0xfade0b01

CSSLOT_CODEDIRECTORY = 0x00000
CSSLOT_INFOSLOT      = 0x00001
CSSLOT_REQUIREMENTS  = 0x00002
CSSLOT_RESOURCEDIR   = 0x00003
CSSLOT_APPLICATION   = 0x00004
CSSLOT_ENTITLEMENTS  = 0x00005
CSSLOT_REPSPECIFIC   = 0x00006
CSSLOT_DERFORMAT     = 0x00007
CSSLOT_ALTERNATE     = 0x01000


class BlobIndex(Struct):
    _FIELDNAMES = ["type", "offset"]
    _SIZES = [uint32_t, uint32_t]
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.type = 0
        self.offset = 0


class Blob(Struct):
    _FIELDNAMES = ["magic", "length"]
    _SIZES = [uint32_t, uint32_t]
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.magic = 0
        self.length = 0


class SuperBlob(Struct):
    _FIELDNAMES = ["blob", "count"]
    _SIZES = [Blob, uint32_t]
    SIZE = 12

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.blob = 0
        self.count = 0
