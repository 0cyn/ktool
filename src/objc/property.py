
from .structs import *
from .type import *

from collections import namedtuple

attr_encodings = {
    "&": "retain",
    "N": "nonatomic",
    "R": "readonly",
    "C": "copy"
}

property_attr = namedtuple("property_attr", ["type", "attributes", "ivar", "is_id", "typestr"])

class Property:
    def __init__(self, library, objc_class, property: objc2_prop, vmaddr: int):
        self.library = library
        self.property = property

        self.name = library.get_cstr_at(property.name, 0, True, "__objc_methname")

        self.attr = self.decode_property_attributes(self.library.get_cstr_at(property.attr, 0, True, "__objc_methname"))
        # property_attr = namedtuple("property_attr", ["type", "attributes", "ivar"])
        self.type = self._renderable_type(self.attr.type)
        self.is_id = self.attr.is_id
        self.attributes = self.attr.attributes
        self.ivarname = self.attr.ivar

    def __str__(self):
        ret = "@property "

        if len(self.attributes) > 0:
            ret += '(' + ', '.join(self.attributes) + ') '

        ret += self.type + ' '

        if self.is_id:
            ret += '*'

        ret += self.name
        return ret

    @staticmethod
    def _renderable_type(type: Type):
        if type.type == EncodedType.NORMAL:
            return str(type)
        elif type.type == EncodedType.STRUCT:
            ptraddon = ""
            for i in range(0, type.pointer_count):
                ptraddon += '*'
            return ptraddon + type.value.name
        return str(type)

    def decode_property_attributes(self, type_str: str):
        attribute_strings = type_str.split(',')

        ptype = ""
        is_id = False
        ivar = ""
        property_attributes = []

        # T@"NSMutableSet",&,N,V_busyControllers
        # T@"NSMutableSet" & N V_busyControllers
        for attribute in attribute_strings:
            indicator = attribute[0]
            if indicator == "T":
                ptype = self.library.tp.process(attribute[1:])[0]
                if ptype == "{":
                    print(attribute)
                is_id = attribute[1] == "@"
                continue
            if indicator == "V":
                ivar = attribute[1:]
            if indicator in attr_encodings:
                property_attributes.append(attr_encodings[indicator])

        return property_attr(ptype, property_attributes, ivar, is_id, type_str)
