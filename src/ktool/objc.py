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
from collections import namedtuple
from enum import Enum
from typing import List, Dict, Optional

from kmacho.base import Constructable
from .dyld import Image
from .structs import *
from .util import log, ignore, usi32_to_si32, opts, Queue, QueueItem

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
    "T": "unk"
}

# https://github.com/arandomdev/DyldExtractor/blob/master/DyldExtractor/objc/objc_structs.py#L79
RELATIVE_METHODS_SELECTORS_ARE_DIRECT_FLAG = 0x40000000
RELATIVE_METHOD_FLAG = 0x80000000
METHOD_LIST_FLAGS_MASK = 0xFFFF0000


class ObjCImage(Constructable):
    @classmethod
    def from_image(cls, image: Image):

        objc_image = ObjCImage(image)

        cat_prot_queue = Queue()
        class_queue = Queue()

        if not image.slice.macho_file.uses_mmaped_io:
            cat_prot_queue.multithread = False
            class_queue.multithread = False

        sect = None
        for seg in image.segments:
            for sec in image.segments[seg].sections:
                if sec == "__objc_catlist":
                    sect = image.segments[seg].sections[sec]

        # cats = []  # meow
        if sect is not None:
            count = sect.size // 0x8
            for offset in range(0, count):
                try:
                    item = QueueItem()
                    item.func = Category.from_image
                    item.args = [objc_image, sect.vm_address + offset * 0x8]
                    cat_prot_queue.items.append(item)
                except Exception as ex:
                    if not ignore.OBJC_ERRORS:
                        raise ex
                    log.error(f'Failed to load a category! Ex: {str(ex)}')

        sect = None
        for seg in image.segments:
            for sec in image.segments[seg].sections:
                if sec == "__objc_classlist":
                    sect = image.segments[seg].sections[sec]

        if sect is not None:
            cnt = sect.size // 0x8
            for i in range(0, cnt):
                try:
                    # c = Class.from_image(objc_image, sect.vm_address + i * 0x8)
                    item = QueueItem()
                    item.func = Class.from_image
                    item.args = [objc_image, sect.vm_address + i * 0x8]
                    class_queue.items.append(item)
                except Exception as ex:
                    if not ignore.OBJC_ERRORS:
                        raise ex
                    log.error(f'Failed to load a class! Ex: {str(ex)}')

        sect = None
        for seg in image.segments:
            for sec in image.segments[seg].sections:
                if sec == "__objc_protolist":
                    sect = image.segments[seg].sections[sec]

        if sect is not None:
            cnt = sect.size // 0x8
            for i in range(0, cnt):
                ptr = sect.vm_address + i * 0x8
                if objc_image.vm_check(ptr):
                    loc = image.get_int_at(ptr, 0x8, vm=True)
                    try:
                        proto = image.load_struct(loc, objc2_prot, vm=True)
                        item = QueueItem()
                        item.func = Protocol.from_image
                        item.args = [objc_image, proto, loc]
                        cat_prot_queue.items.append(item)
                    except Exception as ex:
                        if not ignore.OBJC_ERRORS:
                            raise ex
                        log.error("Failed to load a protocol with " + str(ex))

        cat_prot_queue.go()

        for val in cat_prot_queue.returns:
            if val:
                if isinstance(val, Protocol):
                    objc_image.protolist.append(val)
                    objc_image.prot_map[val.loc] = val
                else:
                    objc_image.catlist.append(val)
                    objc_image.cat_map[val.loc] = val

        class_queue.go()

        for val in class_queue.returns:
            if val:
                objc_image.classlist.append(val)
                objc_image.class_map[val.loc] = val

        return objc_image

    @classmethod
    def from_values(cls, image, name, classlist, catlist, protolist, type_processor=None):
        objc_image = cls(image, type_processor)
        objc_image.name = name

        objc_image.classlist = classlist
        objc_image.catlist = catlist
        objc_image.protolist = protolist

        return objc_image

    def raw_bytes(self):
        pass

    def __init__(self, image, type_processor=None):
        if type_processor is None:
            type_processor = TypeProcessor()
        self.image = image
        if image:
            self.name = image.name
        else:
            self.name = ""
        self.tp = type_processor

        self.classlist = []
        self.catlist = []
        self.protolist = []

        self.class_map: Dict[int, 'Class'] = {}
        self.cat_map: Dict[int, 'Category'] = {}
        self.prot_map: Dict[int, 'Protocol'] = {}

    def vm_check(self, address):
        return self.image.vm.vm_check(address)

    def get_int_at(self, offset: int, length: int, vm=False, sectname=None):
        return self.image.get_int_at(offset, length, vm, sectname)

    def load_struct(self, addr: int, struct_type, vm=True, sectname=None, endian="little"):
        return self.image.load_struct(addr, struct_type, vm, sectname, endian)

    def get_str_at(self, addr: int, count: int, vm=True, sectname=None):
        return self.image.get_str_at(addr, count, vm, sectname)

    def get_cstr_at(self, addr: int, limit: int = 0, vm=True, sectname=None):
        return self.image.get_cstr_at(addr, limit, vm, sectname)


class Struct_Representation:
    def __init__(self, processor: 'TypeProcessor', type_str: str):
        # {name=dd}

        # Remove the outer {}, then get everything to the left of the equal sign
        self.name: str = type_str[1:-1].split('=')[0]

        if '=' not in type_str:
            self.fields = []
            return

        self.field_names = []

        process_string = type_str[1:-1].split('=', 1)[1]

        if process_string.startswith('"'):  # Named struct
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
                except IndexError:
                    log.debug(f'Missing a field in struct {self.name}')

            if isinstance(field.value, Struct_Representation):
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
    def __init__(self, processor, type_string, pc=0):
        start = type_string[0]
        self.child = None
        self.pointer_count = pc

        if start in type_encodings.keys():
            self.type = EncodedType.NORMAL
            self.value = type_encodings[start]
            return

        elif start == '"':
            self.type = EncodedType.NAMED
            self.value = type_string[1:-1]
            return

        elif start == '{':
            self.type = EncodedType.STRUCT
            self.value = Struct_Representation(processor, type_string)
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
        self.type_cache = {}

    def save_struct(self, struct_to_save: Struct_Representation):
        if struct_to_save.name not in self.structs.keys():
            self.structs[struct_to_save.name] = struct_to_save
        else:
            if len(self.structs[struct_to_save.name].fields) == 0:
                self.structs[struct_to_save.name] = struct_to_save
            # If the struct being saved has more field names than the one we already have saved,
            #   save this one instead.
            if len(struct_to_save.field_names) > 0 and len(self.structs[struct_to_save.name].field_names) == 0:
                self.structs[struct_to_save.name] = struct_to_save

    def process(self, type_to_process: str):
        if type_to_process in self.type_cache:
            return self.type_cache[type_to_process]
        # noinspection PyBroadException
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
            self.type_cache[type_to_process] = types
            return types
        except Exception:
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


class Ivar(Constructable):

    @classmethod
    def from_image(cls, objc_image: ObjCImage, ivar: objc2_ivar):
        name: str = objc_image.get_cstr_at(ivar.name, 0, True, "__objc_methname")
        type_string: str = objc_image.get_cstr_at(ivar.type, 0, True, "__objc_methtype")
        return cls(name, type_string, objc_image.tp)

    @classmethod
    def from_values(cls, name, type_encoding, type_processor=None):
        if not type_processor:
            type_processor = TypeProcessor()
        return cls(name, type_encoding, type_processor)

    def raw_bytes(self):
        pass

    def __init__(self, name, type_encoding, type_processor):
        self.name: str = name
        type_string: str = type_encoding
        self.is_id: bool = type_string[0] == "@"
        try:
            self.type: str = self._renderable_type(type_processor.process(type_string)[0])
        except IndexError:
            self.type: str = '?'

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
    def _renderable_type(ivar_type: Type) -> str:
        if ivar_type.type == EncodedType.NORMAL:
            return str(ivar_type)
        elif ivar_type.type == EncodedType.STRUCT:
            ptr_addition = ""
            for i in range(0, ivar_type.pointer_count):
                ptr_addition += '*'
            return ptr_addition + ivar_type.value.name
        return str(ivar_type)


class MethodList:
    def __init__(self, image: ObjCImage, methlist_head, base_meths, class_meta, class_name):
        self.objc_image = image
        self.methlist_head = methlist_head
        self.meta = class_meta
        self.name = class_name
        self.load_errors = []
        self.methods = []

        self.struct_list = []
        if base_meths != 0:
            self.methods = self._process_methlist(base_meths)

    def _process_methlist(self, base_meths):
        methods = []

        ea = self.methlist_head.off
        vm_ea = base_meths

        uses_relative_methods = self.methlist_head.entrysize & METHOD_LIST_FLAGS_MASK & RELATIVE_METHOD_FLAG != 0
        rms_are_direct = self.methlist_head.entrysize & METHOD_LIST_FLAGS_MASK & RELATIVE_METHODS_SELECTORS_ARE_DIRECT_FLAG != 0

        ea += objc2_meth_list.SIZE
        vm_ea += objc2_meth_list.SIZE

        for i in range(1, self.methlist_head.count + 1):
            if uses_relative_methods:
                sel = self.objc_image.get_int_at(ea, 4, vm=False)
                types = self.objc_image.get_int_at(ea + 4, 4, vm=False)
            else:
                sel = self.objc_image.get_int_at(ea, 8, vm=False)
                types = self.objc_image.get_int_at(ea + 8, 8, vm=False)

            try:
                method = Method.from_image(self.objc_image, sel, types, self.meta, vm_ea, uses_relative_methods,
                                           rms_are_direct)
                methods.append(method)
                for method_type in method.types:
                    if method_type.type == EncodedType.STRUCT:
                        self.struct_list.append(method_type.value)

            except Exception as ex:
                if not ignore.OBJC_ERRORS:
                    raise ex
                log.warning(f'Failed to load method in {self.name} with {str(ex)}')
                self.load_errors.append(f'Failed to load a method with {str(ex)}')

            if uses_relative_methods:
                ea += objc2_meth_list_entry.SIZE
                vm_ea += objc2_meth_list_entry.SIZE
            else:
                ea += objc2_meth.SIZE
                vm_ea += objc2_meth.SIZE

        return methods


class Method(Constructable):
    @classmethod
    def from_image(cls, objc_image: ObjCImage, sel_addr, types_addr, is_meta, vm_addr, rms, rms_are_direct):
        if rms:
            if rms_are_direct:
                try:
                    if opts.USE_SYMTAB_INSTEAD_OF_SELECTORS:
                        raise AssertionError
                    sel = objc_image.get_cstr_at(sel_addr + vm_addr, 0, vm=True, sectname="__objc_methname")

                except Exception as ex:
                    try:
                        imp = objc_image.get_int_at(vm_addr + 8, 4, vm=True)
                        imp = usi32_to_si32(imp) + vm_addr + 8
                        if imp in objc_image.image.symbols:
                            sel = objc_image.image.symbols[imp].fullname.split(" ")[-1][:-1]
                        else:
                            raise ex
                    except Exception:
                        raise ex
                type_string = objc_image.get_cstr_at(types_addr + vm_addr + 4, 0, vm=True,
                                                     sectname="__objc_methtype")
            else:
                selector_pointer = objc_image.get_int_at(sel_addr + vm_addr, 8, vm=True)
                try:
                    if opts.USE_SYMTAB_INSTEAD_OF_SELECTORS:
                        raise AssertionError
                    sel = objc_image.get_cstr_at(selector_pointer, 0, vm=True, sectname="__objc_methname")
                except Exception as ex:
                    try:
                        imp = objc_image.get_int_at(vm_addr + 8, 4, vm=True)
                        # no idea if this is correct
                        imp = usi32_to_si32(imp) + vm_addr + 8
                        if imp in objc_image.image.symbols:
                            sel = objc_image.image.symbols[imp].fullname.split(" ")[-1][:-1]
                        else:
                            raise ex
                    except Exception:
                        raise ex
                type_string = objc_image.get_cstr_at(types_addr + vm_addr + 4, 0, vm=True,
                                                     sectname="__objc_methtype")
        else:
            sel = objc_image.get_cstr_at(sel_addr, 0, vm=True, sectname="__objc_methname")
            type_string = objc_image.get_cstr_at(types_addr, 0, vm=True, sectname="__objc_methtype")
        return cls(is_meta, sel, type_string, objc_image.tp)

    @classmethod
    def from_values(cls, sel, type_string, is_meta=False, type_processor=None):
        if not type_processor:
            type_processor = TypeProcessor()
        return cls(is_meta, sel, type_string, type_processor)

    def raw_bytes(self):
        pass

    def __init__(self, meta, sel, type_string, type_processor):
        self.meta = meta
        self.sel = sel
        self.type_string = type_string
        self.types = type_processor.process(type_string)

        self.return_string = self._renderable_type(self.types[0])
        self.arguments = [self._renderable_type(i) for i in self.types[1:]]

        self.signature = self._build_method_signature()

    def __str__(self):
        ret = ""
        ret += self.signature
        return ret

    @staticmethod
    def _renderable_type(method_type: Type):
        if method_type.type == EncodedType.NORMAL:
            return str(method_type)
        elif method_type.type == EncodedType.STRUCT:
            ptr_addition = ""
            for i in range(0, method_type.pointer_count):
                ptr_addition += '*'
            return 'struct ' + method_type.value.name + ' ' + ptr_addition

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


class Class(Constructable):
    """
    """

    @classmethod
    def from_image(cls, objc_image: ObjCImage, class_ptr: int, meta=False) -> Optional['Class']:
        if class_ptr in objc_image.class_map:
            return objc_image.class_map[class_ptr]

        load_errors = []
        struct_list = []

        if not objc_image.vm_check(class_ptr):
            objc2_class_location = objc_image.get_int_at(class_ptr, 8, vm=False)
        else:
            objc2_class_location = objc_image.get_int_at(class_ptr, 8, vm=True)

        if objc2_class_location == 0 or not objc_image.vm_check(objc2_class_location):
            log.error("Loading a class failed")
            return None

        objc2_class_item: objc2_class = objc_image.load_struct(objc2_class_location, objc2_class, vm=True)

        superclass = None

        if not meta:
            if objc2_class_location + 8 in objc_image.image.import_table:
                symbol = objc_image.image.import_table[objc2_class_location + 8]
                superclass_name = symbol.name[1:]
            elif objc2_class_item.superclass in objc_image.image.export_table:
                symbol = objc_image.image.export_table[objc2_class_item.superclass]
                superclass_name = symbol.name[1:]
            else:
                if objc_image.vm_check(objc2_class_item.superclass):
                    # noinspection PyBroadException
                    try:
                        superclass = Class.from_image(objc_image, objc2_class_location + 8)
                    except Exception:
                        pass
                if superclass is not None:
                    superclass_name = superclass.name
                else:
                    if objc2_class_item.superclass in objc_image.image.import_table:
                        symbol = objc_image.image.import_table[objc2_class_item.superclass]
                        superclass_name = symbol.name[1:]
                    else:
                        superclass_name = 'NSObject'
        else:
            superclass_name = ''
        objc2_class_ro_item = objc_image.load_struct(objc2_class_item.info, objc2_class_ro, vm=True)
        if not meta:
            name = objc_image.get_cstr_at(objc2_class_ro_item.name, 0, vm=True)
        else:
            name = ""

        methods = []
        properties = []

        if objc2_class_ro_item.base_props != 0:
            proplist_head = objc_image.load_struct(objc2_class_ro_item.base_props, objc2_prop_list)
            ea = proplist_head.off
            ea += objc2_prop_list.SIZE

            for i in range(1, proplist_head.count + 1):
                prop = objc_image.load_struct(ea, objc2_prop, vm=False)

                try:
                    property = Property.from_image(objc_image, prop)
                    properties.append(property)
                    if hasattr(property, 'attr'):
                        if property.attr.type.type == EncodedType.STRUCT:
                            struct_list.append(property.attr.type.value)

                except Exception as ex:
                    if not ignore.OBJC_ERRORS:
                        raise ex
                    log.warning(f'Failed to load a property in {name} with {ex.__class__.__name__}: {str(ex)}')
                    load_errors.append(f'Failed to load a property with {ex.__class__.__name__}: {str(ex)}')

                ea += objc2_prop.SIZE

        if objc2_class_ro_item.base_meths != 0:
            methlist_head = objc_image.load_struct(objc2_class_ro_item.base_meths, objc2_meth_list)

            methlist = MethodList(objc_image, methlist_head, objc2_class_ro_item.base_meths, meta, name)

            load_errors += methlist.load_errors
            struct_list += methlist.struct_list
            methods += methlist.methods

        if objc2_class_item.isa != 0 and objc2_class_item.isa <= 0xFFFFFFFFFF and not meta:
            metaclass = Class.from_image(objc_image, objc2_class_item.off, meta=True)
            if metaclass:
                methods += metaclass.methods

        prots = []
        if objc2_class_ro_item.base_prots != 0:
            protlist: objc2_prot_list = objc_image.load_struct(objc2_class_ro_item.base_prots, objc2_prot_list)
            ea = protlist.off
            for i in range(1, protlist.cnt + 1):
                prot_loc = objc_image.get_int_at(ea + i * 8, 8, vm=False)
                if prot_loc in objc_image.prot_map:
                    prots.append(objc_image.prot_map[prot_loc])
                else:
                    prot = objc_image.load_struct(prot_loc, objc2_prot, vm=True)
                    try:
                        p = Protocol.from_image(objc_image, prot, prot_loc)
                        prots.append(p)
                        objc_image.prot_map[prot_loc] = p
                    except Exception as ex:
                        if not ignore.OBJC_ERRORS:
                            raise ex
                        log.warning(f'Failed to load protocol with {str(ex)}')
                        load_errors.append(f'Failed to load a protocol with {str(ex)}')

        ivars = []
        if objc2_class_ro_item.ivars != 0:
            ivarlist: objc2_ivar_list = objc_image.load_struct(objc2_class_ro_item.ivars, objc2_ivar_list)
            ea = ivarlist.off + 8
            for i in range(1, ivarlist.cnt + 1):
                ivar_loc = ea + objc2_ivar.SIZE * (i - 1)
                ivar = objc_image.load_struct(ivar_loc, objc2_ivar, vm=False)
                try:
                    ivar_object = Ivar.from_image(objc_image, ivar)
                    ivars.append(ivar_object)
                except Exception as ex:
                    if not ignore.OBJC_ERRORS:
                        raise ex
                    log.warning(f'Failed to load ivar with {str(ex)}')
                    load_errors.append(f'Failed to load an ivar with {str(ex)}')

        return cls(name, meta, superclass_name, methods, properties, ivars, prots, load_errors, struct_list,
                   loc=objc2_class_location)

    @classmethod
    def from_values(cls, name, superclass_name, methods: List[Method], properties: List['Property'],
                    ivars: List['Ivar'],
                    protocols: List['Protocol'], load_errors=None, structs=None):
        return cls(name, False, superclass_name, methods, properties, ivars, protocols, load_errors, structs)

    def raw_bytes(self):
        pass

    def __init__(self, name, is_meta, superclass_name, methods, properties, ivars, protocols, load_errors=None,
                 structs=None, loc=0):
        if structs is None:
            structs = []
        if load_errors is None:
            load_errors = []
        self.name = name
        self.meta = is_meta
        self.superclass = superclass_name
        self.loc = loc

        self.load_errors = load_errors
        self.struct_list = structs

        self.linkedlibs = []
        self.linked_classes = []
        self.fdec_classes = []
        self.fdec_prots = []
        self.struct_list = []
        # Classes imported in this class from the same mach-o

        self.methods = methods
        self.properties = properties
        self.protocols = protocols
        self.ivars = ivars

    def __str__(self):
        ret = ""
        ret += self.name
        return ret

    def _load_linked_libraries(self):
        pass


attr_encodings = {
    "&": "retain",
    "N": "nonatomic",
    "W": "__weak",
    "R": "readonly",
    "C": "copy"
}

property_attr = namedtuple("property_attr", ["type", "attributes", "ivar", "is_id", "typestr"])


class Property(Constructable):

    @classmethod
    def from_image(cls, objc_image: ObjCImage, property: objc2_prop):
        name = objc_image.get_cstr_at(property.name, 0, True, "__objc_methname")
        attr_string = objc_image.get_cstr_at(property.attr, 0, True, "__objc_methname")
        return cls(name, attr_string, objc_image.tp)

    @classmethod
    def from_values(cls, name, attr_string, type_processor=None):
        if not type_processor:
            type_processor = TypeProcessor()
        return cls(name, attr_string, type_processor)

    def raw_bytes(self):
        pass

    def __init__(self, name, attr_string, type_processor):
        self.name = name

        try:
            self.attr = self.decode_property_attributes(type_processor, attr_string)
        except IndexError:
            log.warn(
                f'issue with property {self.name} attr {attr_string}')
            self.type = None
            self.is_id = False
            self.attributes = []
            self.ivarname = ""

        self.type = self._renderable_type(self.attr.type)
        self.is_id = self.attr.is_id
        self.attributes = self.attr.attributes
        self.ivarname = self.attr.ivar

    def __str__(self):
        if not hasattr(self, 'attributes'):
            return f'// Something went wrong loading property {self.name}'
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
    def _renderable_type(_type: Type):
        if _type.type == EncodedType.NORMAL:
            return str(_type)
        elif _type.type == EncodedType.STRUCT:
            ptraddon = ""
            for i in range(0, _type.pointer_count):
                ptraddon += '*'
            return ptraddon + _type.value.name
        return str(_type)

    @staticmethod
    def decode_property_attributes(type_processor, type_str: str):
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
                ptype = type_processor.process(attribute[1:])[0]
                if ptype == "{":
                    print(attribute)
                is_id = attribute[1] == "@"
                continue
            if indicator == "V":
                ivar = attribute[1:]
            if indicator in attr_encodings:
                property_attributes.append(attr_encodings[indicator])

        return property_attr(ptype, property_attributes, ivar, is_id, type_str)


class Category(Constructable):

    @classmethod
    def from_image(cls, objc_image: ObjCImage, category_ptr):
        loc = objc_image.get_int_at(category_ptr, 8, vm=True)
        struct: objc2_category = objc_image.load_struct(loc, objc2_category, vm=True)
        name = objc_image.get_cstr_at(struct.name, vm=True)
        classname = ""
        try:
            sym = objc_image.image.import_table[loc + 8]
            classname = sym.name[1:]
        except KeyError:
            pass

        methods = []
        properties = []
        load_errors = []
        struct_list = []

        if struct.inst_meths != 0:
            methlist_head = objc_image.load_struct(struct.inst_meths, objc2_meth_list)
            methlist = MethodList(objc_image, methlist_head, struct.inst_meths, False, f'{classname}+{name}')

            load_errors += methlist.load_errors
            struct_list += methlist.struct_list
            methods += methlist.methods

        if struct.class_meths != 0:
            methlist_head = objc_image.load_struct(struct.class_meths, objc2_meth_list)
            methlist = MethodList(objc_image, methlist_head, struct.class_meths, True, f'{classname}+{name}')

            load_errors += methlist.load_errors
            struct_list += methlist.struct_list
            methods += methlist.methods

        if struct.props != 0:
            proplist_head = objc_image.load_struct(struct.props, objc2_prop_list)

            ea = proplist_head.off
            ea += 8

            for i in range(1, proplist_head.count + 1):
                prop = objc_image.load_struct(ea, objc2_prop, vm=False)
                try:
                    properties.append(Property.from_image(objc_image, prop))
                except Exception as ex:
                    log.warning(f'Failed to load property with {str(ex)}')
                ea += objc2_prop.SIZE

        return cls(classname, name, methods, properties, loc=loc)

    @classmethod
    def from_values(cls, classname, name, methods, properties, load_errors=None, struct_list=None):
        return cls(classname, name, methods, properties, load_errors, struct_list)

    def raw_bytes(self):
        pass

    def __init__(self, classname, name, methods, properties, load_errors=None, struct_list=None, loc=0):
        if load_errors is None:
            load_errors = []
        if struct_list is None:
            struct_list = []
        self.name = name
        self.classname = classname
        self.loc = loc

        self.load_errors = load_errors
        self.struct_list = struct_list

        self.methods = methods
        self.properties = properties
        self.protocols = []


class Protocol(Constructable):

    @classmethod
    def from_image(cls, objc_image: 'ObjCImage', protocol: objc2_prot, loc):
        if loc in objc_image.prot_map:
            return objc_image.prot_map[loc]

        name = objc_image.get_cstr_at(protocol.name, 0, vm=True)
        load_errors = []
        struct_list = []

        methods = []
        opt_methods = []

        properties = []

        methlist = Protocol.load_methods(objc_image, name, protocol.inst_meths)
        load_errors += methlist.load_errors
        struct_list += methlist.struct_list
        methods += methlist.methods

        methlist = Protocol.load_methods(objc_image, name, protocol.class_meths, True)
        load_errors += methlist.load_errors
        struct_list += methlist.struct_list
        methods += methlist.methods

        methlist = Protocol.load_methods(objc_image, name, protocol.opt_inst_meths)
        load_errors += methlist.load_errors
        struct_list += methlist.struct_list
        opt_methods += methlist.methods

        methlist = Protocol.load_methods(objc_image, name, protocol.opt_class_meths, True)
        load_errors += methlist.load_errors
        struct_list += methlist.struct_list
        opt_methods += methlist.methods

        if protocol.inst_props != 0:
            proplist_head = objc_image.load_struct(protocol.inst_props, objc2_prop_list)

            ea = proplist_head.off
            ea += 8

            for i in range(1, proplist_head.count + 1):
                prop = objc_image.load_struct(ea, objc2_prop, vm=False)
                try:
                    properties.append(Property.from_image(objc_image, prop))
                except Exception as ex:
                    log.warning(f'Failed to load property with {str(ex)}')
                ea += objc2_prop.SIZE

        return cls(name, methods, opt_methods, properties, load_errors, struct_list, loc=loc)

    @classmethod
    def load_methods(cls, objc_image, name, loc, meta=False):
        vm_ea = loc
        if loc != 0:
            methlist_head = objc_image.load_struct(loc, objc2_meth_list)
        else:
            methlist_head = None

        methlist = MethodList(objc_image, methlist_head, vm_ea, meta, name)

        return methlist

    @classmethod
    def from_values(cls, name, methods, opt_methods, properties, load_errors=None, struct_list=None):
        return cls(name, methods, opt_methods, properties, load_errors, struct_list)

    def raw_bytes(self):
        pass

    def __init__(self, name, methods, opt_methods, properties, load_errors=None, struct_list=None, loc=0):
        if struct_list is None:
            struct_list = []
        if load_errors is None:
            load_errors = []

        self.name = name
        self.loc = loc

        self.load_errors = load_errors
        self.struct_list = struct_list

        self.methods = methods

        self.opt_methods = opt_methods

        self.properties = properties

    def __str__(self):
        return self.name
