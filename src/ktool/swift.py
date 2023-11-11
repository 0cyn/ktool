#
#  ktool | ktool
#  swift.py
#
#  Swift type processing
#
#  Comments here are currently from me reverse engineering type ser
#
#  I have a habit of REing things that are technically publicly available,
#       because this is the way I like to write these parsers, it's far less boring,
#       and gives me a better initial understanding/foothold.
#
#  So please note that comments, etc may be inaccurate until I eventually get around to
#       diving into the swift compiler.
#
#  https://belkadan.com/blog/2020/09/Swift-Runtime-Type-Metadata/
#  https://knight.sc/reverse%20engineering/2019/07/17/swift-metadata.html
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) 0cyn 2021.
#

from ktool_macho.base import Constructable
from ktool_swift.structs import *
from ktool_swift.demangle import demangle

from ktool.loader import Image
from ktool.macho import Section
from ktool.objc import Class
from lib0cyn.log import log
from ktool.util import uint_to_int


class Field:
    def __init__(self, flags, type_name, name):
        self.flags = flags
        self.type_name = type_name
        self.name = name

    def __str__(self):
        return f'{self.name} : {self.type_name} ({hex(self.flags)})'


class _FieldDescriptor(Constructable):

    @classmethod
    def from_image(cls, objc_image, location):
        image = objc_image.image
        fields = []

        fd = image.read_struct(location, FieldDescriptor, vm=True)

        for i in range(fd.NumFields):
            ea = location + FieldDescriptor.size() + (i * 0xc)
            record = image.read_struct(ea, FieldRecord, vm=True, force_reload=True)

            flags = record.Flags
            type_name_loc = ea + 4 + record.MangledTypeName
            name_loc = ea + 8 + record.FieldName
            try:
                name = image.read_cstr(name_loc, vm=True)
            except ValueError:
                name = ""
            except IndexError:
                name = ""
            try:
                type_name = image.read_cstr(type_name_loc, vm=True)
            except ValueError:
                type_name = ""
            except IndexError:
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


class SwiftStruct(Constructable):

    @classmethod
    def from_image(cls, objc_image: 'ObjCImage', type_location):
        image = objc_image.image
        struct_desc = image.read_struct(type_location, StructDescriptor, vm=True)
        name = image.read_cstr(type_location + 8 + struct_desc.Name, vm=True)

        #
        field_desc = _FieldDescriptor.from_image(objc_image, type_location + (4*4) + struct_desc.FieldDescriptor)

        return cls(name, field_desc)

    @classmethod
    def from_values(cls, *args, **kwargs):
        pass

    def raw_bytes(self):
        pass

    def __init__(self, name, field_desc: _FieldDescriptor):
        self.name = name
        self.field_desc = field_desc
        self.fields = field_desc.fields


class SwiftClass(Constructable):

    @classmethod
    def from_image(cls, image: Image, objc_image: 'ObjCImage', type_location):
        class_descriptor = image.read_struct(type_location, ClassDescriptor, vm=True)
        name = image.read_cstr(type_location + 8 + class_descriptor.Name, vm=True)
        fd_loc = class_descriptor.FieldDescriptor + type_location + 16
        field_descriptor = _FieldDescriptor.from_image(objc_image, fd_loc)
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


class SwiftEnum(Constructable):

    @classmethod
    def from_image(cls, objc_image, type_location):
        image = objc_image.image
        enum_descriptor = image.read_struct(type_location, EnumDescriptor, vm=True)
        name = image.read_cstr(type_location + 8 + enum_descriptor.Name, vm=True)
        field_desc = None
        if enum_descriptor.FieldDescriptor != 0:
            field_desc = _FieldDescriptor.from_image(objc_image, type_location + (4*4) + enum_descriptor.FieldDescriptor)

        return cls(name, field_desc)

    @classmethod
    def from_values(cls, *args, **kwargs):
        pass

    def raw_bytes(self):
        pass

    def __init__(self, name, field_desc: _FieldDescriptor):
        self.name = name
        self.field_desc = field_desc
        self.fields = field_desc.fields if self.field_desc is not None else []


class SwiftType(Constructable):

    @classmethod
    def from_image(cls, image: Image, objc_image, type_location):
        kind = ContextDescriptorKind(image.read_uint(type_location, 1, vm=True) & 0x1f)

        if kind == ContextDescriptorKind.Class:
            return SwiftClass.from_image(image, objc_image, type_location)
        elif kind == ContextDescriptorKind.Struct:
            return SwiftStruct.from_image(objc_image, type_location)
        elif kind == ContextDescriptorKind.Enum:
            return SwiftEnum.from_image(objc_image, type_location)
        else:
            return None

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


class SwiftImage(Constructable):
    def raw_bytes(self):
        pass

    @classmethod
    def from_image(cls, objc_image: 'ObjCImage'):

        types: List[SwiftType] = []

        image = objc_image.image
        swift_type_seg_start_sect: Section = image.segments['__TEXT'].sections['__swift5_types']
        for addr in Section.SectionIterator(swift_type_seg_start_sect, vm=True, ptr_size=4):
            type_rel = image.read_int(addr, 4)
            type_off = addr + type_rel
            types.append(SwiftType.from_image(image, objc_image, type_off))

        return cls(types)

    @classmethod
    def from_values(cls):
        pass

    def __init__(self, types):
        self.types = types



