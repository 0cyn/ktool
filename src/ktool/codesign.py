#
#  ktool | ktool
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
from typing import List

from kmacho.base import Constructable
from kmacho.structs import linkedit_data_command
from kmacho.codesign import *
from ktool.util import log


def swap_32(value: int):
    value = ((value >>  8) & 0x00ff00ff) | ((value <<  8) & 0xff00ff00)
    value = ((value >> 16) & 0x0000ffff) | ((value << 16) & 0xffff0000)
    return value


class CodesignInfo(Constructable):
    @classmethod
    def from_image(cls, image, codesign_cmd: linkedit_data_command):
        superblob: SuperBlob = image.load_struct(codesign_cmd.dataoff, SuperBlob)
        slots: List[BlobIndex] = []
        off = codesign_cmd.dataoff + SuperBlob.SIZE

        req_dat = None

        entitlements = ""
        requirements = ""
        for i in range(swap_32(superblob.count)):
            blob_index = image.load_struct(off, BlobIndex)
            blob_index.type = swap_32(blob_index.type)
            blob_index.offset = swap_32(blob_index.offset)
            slots.append(blob_index)
            off += BlobIndex.SIZE

        for blob in slots:
            if blob.type == CSSLOT_ENTITLEMENTS:
                start = superblob.off + blob.offset
                ent_blob = image.load_struct(start, Blob)
                ent_blob.magic = swap_32(ent_blob.magic)
                ent_blob.length = swap_32(ent_blob.length)
                ent_size = ent_blob.length
                entitlements = image.get_str_at(start+Blob.SIZE, ent_size-Blob.SIZE)

            elif blob.type == CSSLOT_REQUIREMENTS:
                start = superblob.off + blob.offset
                req_blob = image.load_struct(start, Blob)
                req_blob.magic = swap_32(req_blob.magic)
                req_blob.length = swap_32(req_blob.length)
                req_dat = image.get_bytes_at(start+Blob.SIZE, req_blob.length - Blob.SIZE)

        return cls(superblob, slots, entitlements=entitlements, req_dat=req_dat)

    @classmethod
    def from_values(cls, *args, **kwargs):
        pass

    def raw_bytes(self):
        pass

    def __init__(self, superblob, slots, entitlements=None, req_dat=None):
        self.superblob = superblob
        self.slots = slots
        self.entitlements = entitlements
        self.req_dat = req_dat
