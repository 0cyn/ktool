#
#  ktool | ktool
#  objc.py
#
#  This file contains utilities for parsing objective C classes within a MachO binary
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2021.
#

from enum import Enum

from .util import log
from .structs import *

type_encodings = {
    "c": "char",
    "i": "int",
    "s": "short",
    "l": "long",
    "q": "NSInteger",
    "C": "unsigned char",
    "I": "unsigned int",
    "S": "unsigned short",
    "L": "unsigned long",
    "A": "uint8_t",
    "Q": "NSUInteger",
    "f": "float",
    "d": "CGFloat",
    "b": "BOOL",
    "@": "id",
    "B": "BOOL",
    "v": "void",
    "*": "char *",
    "#": "Class",
    ":": "SEL",
    "?": "unk",
}


class ObjCLibrary:

    def __init__(self, library, safe=False):
        self.library = library
        self.safe = safe
        self.tp = TypeProcessor()
        self.name = library.name

        self.classlist = self._generate_class_list(None)
        self.catlist = self._generate_category_list()
        self.protolist = self._generate_protocol_list()

    def _generate_category_list(self):
        sect = None
        for seg in self.library.segments:
            for sec in self.library.segments[seg].sections:
                if sec == "__objc_catlist":
                    sect = self.library.segments[seg].sections[sec]

        if not sect:
            return []

        cats = []  # meow
        count = sect.size // 0x8
        for offset in range(0, count):
            cats.append(Category(self, sect.vm_address + offset * 0x8))

        return cats

    def _generate_class_list(self, classlimit):
        sect = None
        for seg in self.library.segments:
            for sec in self.library.segments[seg].sections:
                if sec == "__objc_classlist":
                    sect = self.library.segments[seg].sections[sec]
        # sect: Section = self.library.segments['__DATA_CONST'].sections['__objc_classlist']
        if not sect:
            return []
        classes = []
        cnt = sect.size // 0x8
        for i in range(0, cnt):
            if classlimit is None:
                try:
                    classes.append(Class(self, sect.vm_address + i * 0x8))
                except Exception as ex:
                    log.error(f'Failed to load a class! Ex: {str(ex)}')
            else:
                oc = Class(self, sect.vm_address + i * 0x8)
                if classlimit == oc.name:
                    classes.append(oc)
        return classes

    def _generate_protocol_list(self):

        sect = None
        for seg in self.library.segments:
            for sec in self.library.segments[seg].sections:
                if sec == "__objc_protolist":
                    sect = self.library.segments[seg].sections[sec]
        # sect: Section = self.library.segments['__DATA_CONST'].sections['__objc_classlist']
        if not sect:
            return []

        protos = []

        cnt = sect.size // 0x8
        for i in range(0, cnt):
            ptr = sect.vm_address + i * 0x8
            loc = self.library.get_bytes(ptr, 0x8, vm=True)
            proto = self.library.load_struct(loc, objc2_prot_t, vm=True)
            try:
                protos.append(Protocol(self, proto, loc))
            except Exception as ex:
                log.error("Failed to load a protocol with " + str(ex))

        return protos

    def get_bytes(self, offset: int, length: int, vm=False, sectname=None):
        return self.library.get_bytes(offset, length, vm, sectname)

    def load_struct(self, addr: int, struct_type: struct, vm=True, sectname=None, endian="little"):
        return self.library.load_struct(addr, struct_type, vm, sectname, endian)

    def get_str_at(self, addr: int, count: int, vm=True, sectname=None):
        return self.library.get_str_at(addr, count, vm, sectname)

    def get_cstr_at(self, addr: int, limit: int = 0, vm=True, sectname=None):
        return self.library.get_cstr_at(addr, limit, vm, sectname)


class Struct:
    def __init__(self, processor, type_str: str):
        # {name=dd}

        # Remove the outer {}, then get everything to the left of the equal sign
        self.name = type_str[1:-1].split('=')[0]

        if '=' not in type_str:
            self.fields = []
            return

        self.field_names = []

        process_string = type_str[1:-1].split('=', 1)[1]

        if process_string.startswith('"'): #  Named struct
            output_string = ""

            in_field = False
            in_substruct_depth = 0

            field = ""

            for character in process_string:
                if character == '{':
                    in_substruct_depth += 1
                    output_string += character
                    continue

                elif character == '}':
                    in_substruct_depth -= 1
                    output_string += character
                    continue

                if in_substruct_depth == 0:
                    if character == '"':
                        if in_field:
                            self.field_names.append(field)
                            in_field = False
                            field = ""
                        else:
                            in_field = True
                    else:
                        if in_field:
                            field += character
                        else:
                            output_string += character
                else:
                    output_string += character

            process_string = output_string

        # Remove the outer {},
        # get everything after the first = sign,
        # Process that via the processor
        # Save the resulting list to self.fields
        self.fields = processor.process(process_string)

    def __str__(self):
        ret = "typedef struct " + self.name + " {\n"

        if not self.fields:
            ret += "} // Error Processing Struct Fields"
            return ret

        for i, field in enumerate(self.fields):
            field_name = f'field{str(i)}'

            if len(self.field_names) > 0:
                try:
                    field_name = self.field_names[i]
                except IndexError as ex:
                    log.debug(f'Missing a field in struct {self.name}')

            if isinstance(field.value, Struct):
                field = field.value.name
            else:
                field = field.value

            ret += "    " + field + ' ' + field_name + ';\n'
        ret += '} ' + self.name + ';'
        if len(self.fields) == 0:
            ret += " // Error Processing Struct Fields"
        return ret


class EncodingType(Enum):
    METHOD = 0
    PROPERTY = 1
    IVAR = 2


class EncodedType(Enum):
    STRUCT = 0
    NAMED = 1
    ID = 2
    NORMAL = 3


class Type:
    def __init__(self, processor, typestr, pc=0):
        start = typestr[0]
        self.child = None
        self.pointer_count = pc

        if start in type_encodings.keys():
            self.type = EncodedType.NORMAL
            self.value = type_encodings[start]
            return

        elif start == '"':
            self.type = EncodedType.NAMED
            self.value = typestr[1:-1]
            return

        elif start == '{':
            self.type = EncodedType.STRUCT
            self.value = Struct(processor, typestr)
            return
        raise ValueError(f'Struct with type {start} not found')

    def __str__(self):
        pref = ""
        for i in range(0, self.pointer_count):
            pref += "*"
        return pref + str(self.value)


class TypeProcessor:
    def __init__(self):
        self.structs = {}

    def save_struct(self, struct_to_save: Struct):
        if struct_to_save.name not in self.structs.keys():
            self.structs[struct_to_save.name] = struct_to_save
        else:
            if len(self.structs[struct_to_save.name].fields) == 0:
                self.structs[struct_to_save.name] = struct_to_save
            if len(struct_to_save.field_names) > 0 and len(self.structs[struct_to_save.name].field_names) == 0:
                self.structs[struct_to_save.name] = struct_to_save

    def process(self, type_to_process: str):
        try:
            tokens = self.tokenize(type_to_process)
            types = []
            pc = 0
            for i, token in enumerate(tokens):
                if token == "^":
                    pc += 1
                else:
                    typee = Type(self, token, pc)
                    types.append(typee)
                    if typee.type == EncodedType.STRUCT:
                        self.save_struct(typee.value)
                    pc = 0
            return types
        except:
            pass

    @staticmethod
    def tokenize(type_to_tokenize: str):
        # ^Idd^{structZero=dd{structName={innerStructName=dd}}{structName2=dd}}

        # This took way too long to write
        # Apologies for lack of readability, it splits up the string into a list
        # Makes every character a token, except root structs
        #   which it compiles into a full string with the contents and tacks onto said list
        tokens = []
        b = False
        bc = 0
        bu = ""
        for c in type_to_tokenize:
            if b:
                bu += c
                if c == "{":
                    bc += 1
                elif c == "}":
                    bc -= 1
                    if bc == 0:
                        tokens.append(bu)
                        b = False
                        bu = ""
            elif c in type_encodings or c == "^":
                tokens.append(c)
            elif c == "{":
                bu += "{"
                b = True
                bc += 1
            elif c == '"':
                try:
                    tokens = [type_to_tokenize.split('@', 1)[1]]
                except Exception as ex:
                    log.warning(f'Failed to process type {type_to_tokenize} with {ex}')
                    return []
                break
        return tokens


class Ivar:
    def __init__(self, library, objc_class, ivar: objc2_ivar, vmaddr: int):
        self.name = library.get_cstr_at(ivar.name, 0, True, "__objc_methname")
        type_string = library.get_cstr_at(ivar.type, 0, True, "__objc_methtype")
        self.is_id = type_string[0] == "@"
        self.type = self._renderable_type(library.tp.process(type_string)[0])

    def __str__(self):
        ret = ""
        if self.type.startswith('<'):
            ret += "id"
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
            ptr_addition = ""
            for i in range(0, type.pointer_count):
                ptr_addition += '*'
            return ptr_addition + type.value.name
        return str(type)


class Method:
    def __init__(self, library, meta, method: objc2_meth, vmaddr: int):
        self.meta = meta
        try:
            self.sel = library.get_cstr_at(method.selector, 0, vm=True, sectname="__objc_methname")
            type_string = library.get_cstr_at(method.types, 0, vm=True, sectname="__objc_methtype")
        except ValueError as ex:
            try:
                selref = library.get_bytes(method.selector + vmaddr, 8, vm=True)
                self.sel = library.get_cstr_at(selref, 0, vm=True, sectname="__objc_methname")
                type_string = library.get_cstr_at(method.types + vmaddr + 4, 0, vm=True, sectname="__objc_methtype")
            except ValueError as ex:
                self.sel = library.get_cstr_at(method.selector + vmaddr, 0, vm=True, sectname="__objc_methname")
                type_string = library.get_cstr_at(method.types + vmaddr + 4, 0, vm=True, sectname="__objc_methtype")
        except Exception as ex:
            raise ex

        self.type_string = type_string
        self.types = library.tp.process(type_string)
        if len(self.types) == 0:
            raise ValueError("Empty Typestr")

        self.return_string = self._renderable_type(self.types[0])
        self.arguments = [self._renderable_type(i) for i in self.types[1:]]

        self.signature = self._build_method_signature()

    def __str__(self):
        ret = ""
        ret += self.signature
        return ret

    @staticmethod
    def _renderable_type(type: Type):
        if type.type == EncodedType.NORMAL:
            return str(type)
        elif type.type == EncodedType.STRUCT:
            ptr_addition = ""
            for i in range(0, type.pointer_count):
                ptr_addition += '*'
            return ptr_addition + type.value.name

    def _build_method_signature(self):
        dash = "+" if self.meta else "-"
        ret = "(" + self.return_string + ")"

        if len(self.arguments) == 0:
            return dash + ret + self.sel

        segments = []
        for i, item in enumerate(self.sel.split(':')):
            if item == "":
                continue
            try:
                segments.append(item + ':' + '(' + self.arguments[i + 2] + ')' + 'arg' + str(i) + ' ')
            except IndexError:
                segments.append(item)

        sig = ''.join(segments)

        return dash + ret + sig


class LinkedClass:
    def __init__(self, classname, libname):
        self.classname = classname
        self.libname = libname


class Class:
    """
    Objective C Class
    This can be a superclass, metaclass, etc
    can represent literally anything that's a "class" struct


    objc2_class = ["off", "isa", "superclass", "cache", "vtable",
    "info" :  VM pointer to objc2_class_ro
    ]

    objc2_class_ro = ["off", "flags", "ivar_base_start", "ivar_base_size", "reserved", "ivar_lyt", "name", "base_meths", "base_prots", "ivars", "weak_ivar_lyt", "base_props"]
    """

    def __init__(self, library, ptr: int, meta=False, objc2class=None):
        self.library = library
        self.ptr = ptr
        self.meta = meta
        self.metaclass = None
        self.superclass = ""
        self.linkedlibs = []
        self.linked_classes = []
        self.fdec_classes = []
        self.fdec_prots = []
        self.struct_list = []
        # Classes imported in this class from the same mach-o
        if not objc2class:
            self.objc2_class: objc2_class = self._load_objc2_class(ptr)
        else:
            self.objc2_class = objc2class

        self.objc2_class_ro = self.library.load_struct(self.objc2_class.info, objc2_class_ro_t, vm=True)

        self._process_structs()

        self.methods = self._process_methods()
        self.properties = self._process_props()
        self.protocols = self._process_prots()
        self.ivars = self._process_ivars()
        self._load_linked_libraries()

    def __str__(self):
        ret = ""
        ret += self.name
        return ret

    def _load_linked_libraries(self):
        pass

    def _load_objc2_class(self, ptr):

        objc2_class_location = self.library.get_bytes(ptr, 8, vm=True)
        objc2_class_item: objc2_class = self.library.load_struct(objc2_class_location, objc2_class_t, vm=True)

        bad_addr = False
        try:
            objc2_superclass: objc2_class = self.library.load_struct(objc2_class_item.superclass, objc2_class_t)
        except:
            bad_addr = True

        if bad_addr:
            # Linked Superclass
            struct_size = sizeof(objc2_class_t)
            struct_location = objc2_class_item.off
            try:
                symbol = self.library.library.binding_table.lookup_table[objc2_class_location + 8]
            except KeyError as ex:
                self.superclass = "NSObject"
                return objc2_class_item
            self.superclass = symbol.name[1:]
            try:
                self.linked_classes.append(LinkedClass(symbol.name[1:], self.library.library.linked[
                    int(symbol.ordinal) - 1].install_name))
            except IndexError:
                pass
        if objc2_class_item.isa != 0 and objc2_class_item.isa <= 0xFFFFFFFFFF and not self.meta:
            try:
                metaclass_item: objc2_class = self.library.load_struct(objc2_class_item.isa, objc2_class_t)
                self.metaclass = Class(self.library, metaclass_item.off, True, metaclass_item)
            except ValueError:
                pass
        return objc2_class_item

    def _process_structs(self):
        try:
            self.name = self.library.get_cstr_at(self.objc2_class_ro.name, 0, vm=True)
        except ValueError as ex:
            pass

    def _process_methods(self):
        methods = []

        if self.objc2_class_ro.base_meths == 0:
            return methods  # Useless Subclass

        vm_ea = self.objc2_class_ro.base_meths
        methlist_head = self.library.load_struct(self.objc2_class_ro.base_meths, objc2_meth_list_t)
        ea = methlist_head.off

        # https://github.com/arandomdev/DyldExtractor/blob/master/DyldExtractor/objc/objc_structs.py#L79
        RELATIVE_METHODS_SELECTORS_ARE_DIRECT_FLAG = 0x40000000
        RELATIVE_METHOD_FLAG = 0x80000000
        METHOD_LIST_FLAGS_MASK = 0xFFFF0000

        uses_relative_methods = methlist_head.entrysize & METHOD_LIST_FLAGS_MASK != 0

        ea += 8
        vm_ea += 8
        for i in range(1, methlist_head.count + 1):
            if uses_relative_methods:
                meth = self.library.load_struct(ea, objc2_meth_list_entry_t, vm=False)
            else:
                meth = self.library.load_struct(ea, objc2_meth_t, vm=False)
            try:
                method = Method(self.library, self.meta, meth, vm_ea)
                methods.append(method)
                for type in method.types:
                    if type.type == EncodedType.STRUCT:
                        self.struct_list.append(type.value)

            except Exception as ex:
                pass
            if uses_relative_methods:
                ea += sizeof(objc2_meth_list_entry_t)
                vm_ea += sizeof(objc2_meth_list_entry_t)
            else:
                ea += sizeof(objc2_meth_t)
                vm_ea += sizeof(objc2_meth_t)

        return methods

    def _process_props(self):
        properties = []

        if self.objc2_class_ro.base_props == 0:
            return properties

        vm_ea = self.objc2_class_ro.base_props
        proplist_head = self.library.load_struct(self.objc2_class_ro.base_props, objc2_prop_list_t)

        ea = proplist_head.off
        ea += 8
        vm_ea += 8

        for i in range(1, proplist_head.count + 1):
            prop = self.library.load_struct(ea, objc2_prop_t, vm=False)
            try:
                property = Property(self.library, prop, vm_ea)
                properties.append(property)
                if hasattr(property, 'attr'):
                    if property.attr.type.type == EncodedType.STRUCT:
                        self.struct_list.append(property.attr.type.value)
            except Exception as ex:
                log.warning(f'Failed to load property with {str(ex)}')
            ea += sizeof(objc2_prop_t)
            vm_ea += sizeof(objc2_prop_t)

        return properties

    def _process_prots(self):
        prots = []
        if self.objc2_class_ro.base_prots == 0:
            return prots
        protlist: objc2_prot_list = self.library.load_struct(self.objc2_class_ro.base_prots, objc2_prot_list_t)
        ea = protlist.off
        for i in range(1, protlist.cnt + 1):
            prot_loc = self.library.get_bytes(ea + i * 8, 8, vm=False)
            prot = self.library.load_struct(prot_loc, objc2_prot_t, vm=True)
            try:
                prots.append(Protocol(self.library, prot, prot_loc))
            except Exception as ex:
                log.warning(f'Failed to load protocol with {str(ex)}')
        return prots

    def _process_ivars(self):
        ivars = []
        if self.objc2_class_ro.ivars == 0:
            return ivars
        ivarlist: objc2_ivar_list = self.library.load_struct(self.objc2_class_ro.ivars, objc2_ivar_list_t)
        ea = ivarlist.off + 8
        for i in range(1, ivarlist.cnt + 1):
            ivar_loc = ea + sizeof(objc2_ivar_t) * (i - 1)
            ivar = self.library.load_struct(ivar_loc, objc2_ivar_t, vm=False)
            try:
                ivar_object = Ivar(self.library, self, ivar, ivar_loc)
                ivars.append(ivar_object)
            except Exception as ex:
                log.warning(f'Failed to load ivar with {str(ex)}')
        return ivars


attr_encodings = {
    "&": "retain",
    "N": "nonatomic",
    "W": "__weak",
    "R": "readonly",
    "C": "copy"
}
property_attr = namedtuple("property_attr", ["type", "attributes", "ivar", "is_id", "typestr"])


class Property:
    def __init__(self, library, property: objc2_prop, vmaddr: int):
        self.library = library
        self.property = property

        self.name = library.get_cstr_at(property.name, 0, True, "__objc_methname")

        try:
            self.attr = self.decode_property_attributes(
                self.library.get_cstr_at(property.attr, 0, True, "__objc_methname"))
        except IndexError:
            log.warn(f'issue with property {self.name} in {self.library.get_cstr_at(property.attr, 0, True, "__objc_methname")}')
            return
        # property_attr = namedtuple("property_attr", ["type", "attributes", "ivar"])
        self.type = self._renderable_type(self.attr.type)
        self.is_id = self.attr.is_id
        self.attributes = self.attr.attributes
        self.ivarname = self.attr.ivar

    def __str__(self):
        if not hasattr(self, 'attributes'):
            return f'// Something went wrong loading struct {self.name}'
        ret = "@property "

        if len(self.attributes) > 0:
            ret += '(' + ', '.join(self.attributes) + ') '

        if self.type.startswith('<'):
            ret += "id"
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


class Category:
    def __init__(self, library, ptr):
        self.library = library
        self.ptr = ptr
        loc = self.library.get_bytes(ptr, 8, vm=True)

        self.struct: objc2_category = self.library.load_struct(loc, objc2_category_t, vm=True)
        self.name = self.library.get_cstr_at(self.struct.name, vm=True)
        self.classname = ""
        try:
            sym = self.library.library.binding_table.lookup_table[loc + 8]
            self.classname = sym.name[1:]
        except:
            pass

        instmeths = self._process_methods(self.struct.inst_meths)
        classmeths = self._process_methods(self.struct.class_meths, True)

        self.methods = instmeths + classmeths
        self.properties = self._process_props(self.struct.props)
        self.protocols = []

    def _process_methods(self, loc, meta=False):
        methods = []

        if loc == 0:
            return methods  # Useless Subclass

        vm_ea = loc
        methlist_head = self.library.load_struct(loc, objc2_meth_list_t)
        ea = methlist_head.off

        # https://github.com/arandomdev/DyldExtractor/blob/master/DyldExtractor/objc/objc_structs.py#L79
        RELATIVE_METHODS_SELECTORS_ARE_DIRECT_FLAG = 0x40000000
        RELATIVE_METHOD_FLAG = 0x80000000
        METHOD_LIST_FLAGS_MASK = 0xFFFF0000

        uses_relative_methods = methlist_head.entrysize & METHOD_LIST_FLAGS_MASK != 0

        ea += 8
        vm_ea += 8
        for i in range(1, methlist_head.count + 1):
            if uses_relative_methods:
                meth = self.library.load_struct(ea, objc2_meth_list_entry_t, vm=False)
            else:
                meth = self.library.load_struct(ea, objc2_meth_t, vm=False)
            try:
                methods.append(Method(self.library, meta, meth, vm_ea))
            except Exception as ex:
                log.warning(f'Failed to load method with {str(ex)}')
            if uses_relative_methods:
                ea += sizeof(objc2_meth_list_entry_t)
                vm_ea += sizeof(objc2_meth_list_entry_t)
            else:
                ea += sizeof(objc2_meth_t)
                vm_ea += sizeof(objc2_meth_t)

        return methods

    def _process_props(self, location):
        properties = []

        if location == 0:
            return properties

        vm_ea = location
        proplist_head = self.library.load_struct(location, objc2_prop_list_t)

        ea = proplist_head.off
        ea += 8
        vm_ea += 8

        for i in range(1, proplist_head.count + 1):
            prop = self.library.load_struct(ea, objc2_prop_t, vm=False)
            try:
                properties.append(Property(self.library, prop, vm_ea))
            except Exception as ex:
                log.warning(f'Failed to load property with {str(ex)}')
            ea += sizeof(objc2_prop_t)
            vm_ea += sizeof(objc2_prop_t)

        return properties


# objc2_prot = namedtuple("objc2_prot", ["off", "isa", "name", "prots", "inst_meths", "class_meths",
# "opt_inst_meths", "opt_class_meths", "inst_props", "cb", "flags"])
# objc2_prot_t = struct(objc2_prot, [8, 8, 8, 8, 8, 8, 8, 8, 4, 4])

class Protocol:
    def __init__(self, library, protocol: objc2_prot, vmaddr: int):
        self.library = library
        self.name = library.get_cstr_at(protocol.name, 0, vm=True)

        self.methods = self._process_methods(protocol.inst_meths)
        self.methods += self._process_methods(protocol.class_meths, True)

        self.opt_methods = self._process_methods(protocol.opt_inst_meths)
        self.opt_methods += self._process_methods(protocol.opt_class_meths, True)

        self.properties = self._process_props(protocol.inst_props)

    def _process_methods(self, loc, meta=False):
        methods = []

        if loc == 0:
            return methods  # Useless Subclass

        vm_ea = loc
        methlist_head = self.library.load_struct(loc, objc2_meth_list_t)
        ea = methlist_head.off

        # https://github.com/arandomdev/DyldExtractor/blob/master/DyldExtractor/objc/objc_structs.py#L79
        RELATIVE_METHODS_SELECTORS_ARE_DIRECT_FLAG = 0x40000000
        RELATIVE_METHOD_FLAG = 0x80000000
        METHOD_LIST_FLAGS_MASK = 0xFFFF0000

        uses_relative_methods = methlist_head.entrysize & METHOD_LIST_FLAGS_MASK != 0

        ea += 8
        vm_ea += 8
        for i in range(1, methlist_head.count + 1):
            if uses_relative_methods:
                meth = self.library.load_struct(ea, objc2_meth_list_entry_t, vm=False)
            else:
                meth = self.library.load_struct(ea, objc2_meth_t, vm=False)
            try:
                methods.append(Method(self.library, meta, meth, vm_ea))
            except Exception as ex:
                log.warning(f'Failed to load method with {str(ex)}')
            if uses_relative_methods:
                ea += sizeof(objc2_meth_list_entry_t)
                vm_ea += sizeof(objc2_meth_list_entry_t)
            else:
                ea += sizeof(objc2_meth_t)
                vm_ea += sizeof(objc2_meth_t)

        return methods

    def _process_props(self, location):
        properties = []

        if location == 0:
            return properties

        vm_ea = location
        proplist_head = self.library.load_struct(location, objc2_prop_list_t)

        ea = proplist_head.off
        ea += 8
        vm_ea += 8

        for i in range(1, proplist_head.count + 1):
            prop = self.library.load_struct(ea, objc2_prop_t, vm=False)
            try:
                properties.append(Property(self.library, prop, vm_ea))
            except Exception as ex:
                log.warning(f'Failed to load property with {str(ex)}')
            ea += sizeof(objc2_prop_t)
            vm_ea += sizeof(objc2_prop_t)

        return properties

    def __str__(self):
        return self.name
