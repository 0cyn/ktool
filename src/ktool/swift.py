#
#  ktool | ktool
#  swift.py
#
#  Swift type processing
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2021.
#

from kmacho.structs import Struct

from .dyld import Image
from .macho import Section


class NominalClassDescriptor(Struct):
    _FIELDNAMES = ['Flags', 'Parent', 'Name', 'AccessFunctionPtr', 'Fields', 'SuperclassType',
                   'MetadataNegativeSizeInWords', 'MetadataPositiveSizeInWords', 'NumImmediateMembers',
                   'NumFields', 'FieldOffsetVectorOffset']
    _SIZES = [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class ClassMethodListTable(Struct):
    _FIELDNAMES = ['VTableOffset', 'VTableSize']
    _SIZES = [4, 4]
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


def usi32_to_si32(val):
    """
    Quick hack to read the signed val of an unsigned int (Image loads all ints from bytes as unsigned ints)

    :param val:
    :return:
    """
    bits = 32
    if (val & (1 << (bits - 1))) != 0:  # if sign bit is set e.g., 8bit: 128-255
        val = val - (1 << bits)         # compute negative value
    return val                          # return positive value as is


def load_swift_types(image: Image):
    swift_type_seg_start_sect: Section = image.segments['__TEXT'].sections['__swift5_types']
    sect_start = swift_type_seg_start_sect.vm_address
    sect_size = swift_type_seg_start_sect.size

    for ea in range(sect_start, sect_start + sect_size, 4):
        typeref = usi32_to_si32(image.get_int_at(ea, 4, vm=True))
        print(typeref)
        struct = image.load_struct(typeref, NominalClassDescriptor, vm=True)
        name_l = usi32_to_si32(struct.Name)
        print(image.get_cstr_at(typeref + 8 + name_l, vm=True))

        methref = typeref + 44
        methlist_head = image.load_struct(methref, ClassMethodListTable, vm=True)
        print(methlist_head)
