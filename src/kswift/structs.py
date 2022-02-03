#
#  ktool | kswift
#  structs.py
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


"""
struct _NominalTypeDescriptor {
    var property1: Int32
    var property2: Int32
    var mangledName: Int32
    var property4: Int32
    var numberOfFields: Int32
    var fieldOffsetVector: Int32
}"""
import enum

from kmacho.structs import *

"""
struct _FieldDescriptor {
    var mangledTypeNameOffset: Int32
    var superClassOffset: Int32
    var fieldDescriptorKind: FieldDescriptorKind
    var fieldRecordSize: Int16
    var numFields: Int32
}
"""


class FieldDescriptor(Struct):
    _FIELDNAMES = ['mangledTypeNameOffset', 'superClassOffset', 'fieldDescriptorKind', 'fieldRecordSize', 'numFields']
    _SIZES = [int32_t, int32_t, uint16_t, int16_t, int32_t]
    SIZE = 16

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order, no_patch=True)


"""
    var fieldRecordFlags: Int32
    var mangledTypeNameOffset: Int32
    var fieldNameOffset: Int32"""


class FieldRecord(Struct):
    _FIELDNAMES = ['Flags', 'Type', 'Name']
    _SIZES = [uint32_t, int32_t, int32_t]
    SIZE = 0xc

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order, no_patch=True)


class NominalTypeDescriptor(Struct):
    _FIELDNAMES = ['property1', 'property2', 'mangledName', 'property4', 'Fields', 'fieldOffsetVector']
    _SIZES = [uint32_t, int32_t, int32_t, int32_t, int32_t, int32_t]
    SIZE = 24

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order, no_patch=True)


class NominalClassDescriptor(Struct):
    _FIELDNAMES = ['Flags', 'Parent', 'Name', 'AccessFunctionPtr', 'Fields', 'SuperclassType',
                   'MetadataNegativeSizeInWords', 'MetadataPositiveSizeInWords', 'NumImmediateMembers',
                   'NumFields', 'FieldOffsetVectorOffset']
    _SIZES = [4, -4, -4, -4, -4, -4, 4, 4, 4, 4, 4]
    SIZE = 44

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order, no_patch=True)


class ClassMethodListTable(Struct):
    _FIELDNAMES = ['VTableOffset', 'VTableSize']
    _SIZES = [4, 4]
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order, no_patch=True)


class TargetMethodDescriptor(Struct):
    _FIELDNAMES = ['Flags', 'Impl']
    _SIZES = [uint32_t, int32_t]
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order, no_patch=True)


class ContextDescriptorKind(enum.Enum):
    Module = 0
    Extension = 1
    Anonymous = 2
    SwiftProtocol = 3
    OpaqueType = 4
    Class = 16
    Struct = 17
    Enum = 18
    Type_Last = 31
