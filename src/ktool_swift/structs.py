#
#  ktool | ktool_swift
#  structs.py
#
#  https://knight.sc/reverse%20engineering/2019/07/17/swift-metadata.html
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) 0cyn 2022.
#

import enum
from lib0cyn.structs import *

"""
struct _NominalTypeDescriptor {
    var property1: Int32
    var property2: Int32
    var mangledName: Int32
    var property4: Int32
    var numberOfFields: Int32
    var fieldOffsetVector: Int32
}"""

"""
type FieldRecord struct {
    Flags           uint32
    MangledTypeName int32
    FieldName       int32
}

type FieldDescriptor struct {
    MangledTypeName int32
    Superclass      int32
    Kind            uint16
    FieldRecordSize uint16
    NumFields       uint32
    FieldRecords    []FieldRecord
}
"""


class ProtocolDescriptor(Struct):
    _FIELDS = {
        'Flags': uint32_t,
        'Parent': int32_t,
        'Name': int32_t,
        'NumRequirementsInSignature': uint32_t,
        'NumRequirements': uint32_t,
        'AssociatedTypeNames': int32_t
    }
    SIZE = 24

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class ProtocolConformanceDescriptor(Struct):
    _FIELDS = {
        'ProtocolDescriptor': int32_t,
        'NominalTypeDescriptor': int32_t,
        'ProtocolWitnessTable': int32_t,
        'ConformanceFlags': uint32_t
    }
    SIZE = 16 
    
    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class EnumDescriptor(Struct):
    _FIELDS = {
        'Flags': uint32_t,
        'Parent': int32_t,
        'Name': int32_t,
        'AccessFunction': int32_t,
        'FieldDescriptor': int32_t,
        'NumPayloadCasesAndPayloadSizeOffset': uint32_t,
        'NumEmptyCases': uint32_t
    }
    SIZE = 28

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class StructDescriptor(Struct):
    _FIELDS = {
        'Flags': uint32_t,
        'Parent': int32_t,
        'Name': int32_t,
        'AccessFunction': int32_t,
        'FieldDescriptor': int32_t,
        'NumFields': uint32_t,
        'FieldOffsetVectorOffset': uint32_t
    }
    SIZE = 28

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class ClassDescriptor(Struct):
    _FIELDS = {
        'Flags': uint32_t,
        'Parent': int32_t,
        'Name': int32_t,
        'AccessFunction': int32_t,
        'FieldDescriptor': int32_t,
        'SuperclassType': int32_t,
        'MetadataNegativeSizeInWords': uint32_t,
        'MetadataPositiveSizeInWords': uint32_t,
        'NumImmediateMembers': uint32_t,
        'NumFields': uint32_t
    }
    SIZE = 4 * len(_FIELDS.values())

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class FieldDescriptor(Struct):
    _FIELDNAMES = ['MangledTypeName',
                   'Superclass',
                   'Kind',
                   'FieldRecordSize',
                   'NumFields']
    _SIZES = [int32_t, int32_t, uint16_t, int16_t, int32_t]
    SIZE = 16

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class FieldRecord(Struct):
    _FIELDNAMES = ['Flags', 'MangledTypeName', 'FieldName']
    _SIZES = [uint32_t, int32_t, int32_t]
    SIZE = 0xc

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class AssociatedTypeRecord(Struct):
    _FIELDS = {
        'Name': int32_t,
        'SubstitutedTypename': int32_t
    }
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class AssociatedTypeDescriptor(Struct):
    _FIELDS = {
        'ConformingTypeName': int32_t,
        'ProtocolTypeName': int32_t,
        'NumAssociatedTypes': uint32_t,
        'AssociatedTypeRecordSize': uint32_t
    }
    SIZE = 16

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class BuiltinTypeDescriptor(Struct):
    _FIELDS = {
        'TypeName': int32_t,
        'Size': uint32_t,
        'AlignmentAndFlags': uint32_t,
        'Stride': uint32_t,
        'NumExtraInhabitants': uint32_t
    }
    SIZE = 20

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class CaptureTypeRecord(Struct):
    _FIELDS = {
        'MangledTypeName': int32_t
    }
    SIZE = 4

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class MetadataSourceRecord(Struct):
    _FIELDS = {
        'MangledTypeName': int32_t,
        'MangledMetadataSource': int32_t
    }
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class CaptureDescriptor(Struct):
    _FIELDS = {
        'NumCaptureTypes': uint32_t,
        'NumMetadataSources': uint32_t,
        'NumBindings': uint32_t
    }
    SIZE = 12

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class Replacement(Struct):
    _FIELDS = {
        'ReplacedFunctionKey': int32_t,
        'NewFunction': int32_t,
        'Replacement': int32_t,
        'Flags': uint32_t
    }
    SIZE = 16

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class ReplacementScope(Struct):
    _FIELDS = {
        'Flags': uint32_t,
        'NumReplacements': uint32_t
    }
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class AutomaticReplacements(Struct):
    _FIELDS = {
        'Flags': uint32_t,
        'NumReplacements': uint32_t,
        'Replacements': int32_t
    }
    SIZE = 12

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class OpaqueReplacement(Struct):
    _FIELDS = {
        'Original': int32_t,
        'Replacement': int32_t
    }
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class OpaqueAutomaticReplacement(Struct):
    _FIELDS = {
        'Flags': uint32_t,
        'NumReplacements': uint32_t,
    }
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class ClassMethodListTable(Struct):
    _FIELDNAMES = ['VTableOffset', 'VTableSize']
    _SIZES = [4, 4]
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class TargetMethodDescriptor(Struct):
    _FIELDNAMES = ['Flags', 'Impl']
    _SIZES = [uint32_t, int32_t]
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


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
