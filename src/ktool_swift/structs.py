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


class ProtocolDescriptor(Struct):
    FIELDS = {
        'Flags': uint32_t,
        'Parent': int32_t,
        'Name': int32_t,
        'NumRequirementsInSignature': uint32_t,
        'NumRequirements': uint32_t,
        'AssociatedTypeNames': int32_t
    }


class ProtocolConformanceDescriptor(Struct):
    FIELDS = {
        'ProtocolDescriptor': int32_t,
        'NominalTypeDescriptor': int32_t,
        'ProtocolWitnessTable': int32_t,
        'ConformanceFlags': uint32_t
    }


class EnumDescriptor(Struct):
    FIELDS = {
        'Flags': uint32_t,
        'Parent': int32_t,
        'Name': int32_t,
        'AccessFunction': int32_t,
        'FieldDescriptor': int32_t,
        'NumPayloadCasesAndPayloadSizeOffset': uint32_t,
        'NumEmptyCases': uint32_t
    }


class StructDescriptor(Struct):
    FIELDS = {
        'Flags': uint32_t,
        'Parent': int32_t,
        'Name': int32_t,
        'AccessFunction': int32_t,
        'FieldDescriptor': int32_t,
        'NumFields': uint32_t,
        'FieldOffsetVectorOffset': uint32_t
    }


class ClassDescriptor(Struct):
    FIELDS = {
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


class FieldDescriptor(Struct):
    FIELDS = {
        'MangledTypeName': int32_t,
        'Superclass': int32_t,
        'Kind': uint16_t,
        'FieldRecordSize': int16_t,
        'NumFields': int32_t
    }


class FieldRecord(Struct):
    FIELDS = {
        'Flags': uint32_t,
        'MangledTypeName': int32_t,
        'FieldName': int32_t
    }


class AssociatedTypeRecord(Struct):
    FIELDS = {
        'Name': int32_t,
        'SubstitutedTypename': int32_t
    }


class AssociatedTypeDescriptor(Struct):
    FIELDS = {
        'ConformingTypeName': int32_t,
        'ProtocolTypeName': int32_t,
        'NumAssociatedTypes': uint32_t,
        'AssociatedTypeRecordSize': uint32_t
    }


class BuiltinTypeDescriptor(Struct):
    FIELDS = {
        'TypeName': int32_t,
        'Size': uint32_t,
        'AlignmentAndFlags': uint32_t,
        'Stride': uint32_t,
        'NumExtraInhabitants': uint32_t
    }


class CaptureTypeRecord(Struct):
    FIELDS = {
        'MangledTypeName': int32_t
    }


class MetadataSourceRecord(Struct):
    FIELDS = {
        'MangledTypeName': int32_t,
        'MangledMetadataSource': int32_t
    }


class CaptureDescriptor(Struct):
    FIELDS = {
        'NumCaptureTypes': uint32_t,
        'NumMetadataSources': uint32_t,
        'NumBindings': uint32_t
    }


class Replacement(Struct):
    FIELDS = {
        'ReplacedFunctionKey': int32_t,
        'NewFunction': int32_t,
        'Replacement': int32_t,
        'Flags': uint32_t
    }


class ReplacementScope(Struct):
    FIELDS = {
        'Flags': uint32_t,
        'NumReplacements': uint32_t
    }


class AutomaticReplacements(Struct):
    FIELDS = {
        'Flags': uint32_t,
        'NumReplacements': uint32_t,
        'Replacements': int32_t
    }


class OpaqueReplacement(Struct):
    FIELDS = {
        'Original': int32_t,
        'Replacement': int32_t
    }


class OpaqueAutomaticReplacement(Struct):
    FIELDS = {
        'Flags': uint32_t,
        'NumReplacements': uint32_t,
    }


class ClassMethodListTable(Struct):
    FIELDS = {
        'VTableOffset': uint32_t,
        'VTableSize': uint32_t
    }


class TargetMethodDescriptor(Struct):
    FIELDS = {
        'Flags': uint32_t,
        'Impl': int32_t
    }


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
