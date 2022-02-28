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
import enum

import ktool
from kmacho.base import Constructable
from kswift.structs import *
from kswift.demangle import demangle
from ktool import ObjCImage

from ktool.dyld import Image
from ktool.macho import Section
from ktool.objc import Class
from ktool.util import usi32_to_si32


class Field:
    def __init__(self, flags, type_name, name):
        self.flags = flags
        self.type_name = type_name
        self.name = name

    def __str__(self):
        return f'{self.name} : {self.type_name} ({hex(self.flags)})'


class _FieldDescriptor(Constructable):

    @classmethod
    def from_image(cls, image, location):

        fields = []

        fd = image.load_struct(location, FieldDescriptor, vm=True)
        ea = location

        for i in range(fd.numFields):
            ea = location + (i * 0xc)
            record = image.load_struct(ea, FieldRecord, vm=True)

            flags = record.Flags
            type_name_loc = ea + 4 + record.Type
            name_loc = ea + 8 + record.Name
            try:
                name = image.get_cstr_at(name_loc, vm=True)
            except ValueError:
                name = ""
            try:
                type_name = image.get_cstr_at(type_name_loc, vm=True)
            except ValueError:
                type_name = ""

            fields.append(Field(flags, type_name, name))

        return cls(fields, fd)

    @classmethod
    def from_values(cls, *args, **kwargs):
        pass

    def raw_bytes(self):
        pass

    def __init__(self, fields, desc):
        self.fields = fields
        self.desc = desc


class SwiftClass(Constructable):

    @classmethod
    def from_image(cls, image: Image, objc_image: ObjCImage, type_location):
        class_descriptor = image.load_struct(type_location, NominalClassDescriptor, vm=True)
        name = image.get_cstr_at(type_location + 8 + class_descriptor.Name, vm=True)
        fd_loc = class_descriptor.Fields + type_location + 16
        field_descriptor = _FieldDescriptor.from_image(image, fd_loc)
        ivars = []

        for objc_class in objc_image.classlist:
            mangled_name = objc_class.name
            project, classname = demangle(mangled_name)
            if classname == name:
                objc_backing_class: Class = objc_class
                ivars = objc_backing_class.ivars
                name = f'{project}.{name}'

        return cls(name, field_descriptor.fields, class_descriptor, field_descriptor, ivars)

    @classmethod
    def from_values(cls, *args, **kwargs):
        pass

    def raw_bytes(self):
        pass

    def __init__(self, name, fields, class_descriptor=None, field_descriptor=None, ivars=None):
        self.name = name
        self.fields = fields
        self.class_desc = class_descriptor
        self.field_desc = field_descriptor
        self.ivars = ivars


class SwiftType(Constructable):

    @classmethod
    def from_image(cls, image: Image, objc_image, type_location):

        typedesc = image.load_struct(type_location, NominalTypeDescriptor, vm=True)
        name = image.get_cstr_at(type_location + 8 + typedesc.mangledName, vm=True)
        kind = ContextDescriptorKind(image.get_int_at(typedesc.off, 1, vm=False) & 0x1f)

        if kind == ContextDescriptorKind.Class:
            return SwiftClass.from_image(image, objc_image, type_location)

        fd_loc = typedesc.Fields + type_location + 16
        field_descriptor = _FieldDescriptor.from_image(image, fd_loc)

        return cls(name, kind, typedesc, field_descriptor)

    @classmethod
    def from_values(cls, *args, **kwargs):
        pass

    def raw_bytes(self):
        pass

    def __init__(self, name, kind, typedesc=None, field_desc=None):
        self.name = name
        self.kind = kind
        self.typedesc = typedesc
        self.field_desc = field_desc


def load_swift_types(image: Image):

    objc_image = ktool.load_objc_metadata(image)

    swift_type_seg_start_sect: Section = image.segments['__TEXT'].sections['__swift5_types']
    sect_start = swift_type_seg_start_sect.vm_address
    sect_size = swift_type_seg_start_sect.size

    types = []

    for ea in range(sect_start, sect_start + sect_size, 4):
        typeref = usi32_to_si32(image.get_int_at(ea, 4, vm=True))
        type_loc = ea + typeref
        types.append(SwiftType.from_image(image, objc_image, type_loc))

    return types

