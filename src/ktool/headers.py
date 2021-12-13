#
#  ktool | ktool
#  headers.py
#
#  This file contains the utilities used to create ObjC Header File dumps
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2021.
#

from typing import List, Dict

from .dyld import SymbolType, Image
from .objc import ObjCImage, Class, Category, Protocol, Property, Method, Ivar

from .util import KTOOL_VERSION


class HeaderUtils:

    @staticmethod
    def header_head(image: Image) -> str:
        """
        This is the prefix comments at the very top of the headers generated

        :param image: MachO Image
        :return: Newline delimited string to be placed at the top of the header.
        """
        try:
            prefix = "// Headers generated with ktool v" + KTOOL_VERSION + "\n"
            prefix += "// https://github.com/kritantadev/ktool | pip3 install k2l\n"
            prefix += f'// Platform: {image.platform.name} | '
            prefix += f'Minimum OS: {image.minos.x}.{image.minos.y}.{image.minos.z} | '
            prefix += f'SDK: {image.sdk_version.x}.{image.sdk_version.y}.{image.sdk_version.z}\n\n' 
            return prefix
        except AttributeError:
            prefix = "// Headers generated with ktool v" + KTOOL_VERSION + "\n"
            prefix += "// https://github.com/kritantadev/ktool | pip3 install k2l\n"
            prefix += "// Issue loading image metadata\n\n"
            return prefix


class TypeResolver:
    """
    the Type Resolver is just in charge of figuring out where imports came from.

    Initialize it with an objc image, then pass it a type name, and it'll try to figure out which
        framework that class should be imported from (utilizing the image's imports)
    """
    def __init__(self, objc_image: ObjCImage):

        self.objc_image = objc_image
        classes = []
        self.classmap = {}
        try:
            for sym in objc_image.image.binding_table.symbol_table:
                if sym.type == SymbolType.CLASS:
                    self.classmap[sym.name[1:]] = sym
                    classes.append(sym)
        except AttributeError:
            pass
        self.classes = classes
        self.local_classes = objc_image.classlist
        self.local_protos = objc_image.protolist

    def find_linked(self, classname: str):
        """
        given a classname, return install name of a framework if that class was imported from it.

        :param classname:
        :return:
        """
        for local in self.local_classes:
            if local.name == classname:
                return ""
        for local in self.local_protos:
            if local.name == classname[1:-1]:
                return "-Protocol"
        if classname in self.classmap:
            try:
                name = self.objc_image.image.linked[int(self.classmap[classname].ordinal) - 1].install_name
                if '.dylib' in name:
                    return None
                return name
            except IndexError:
                pass
        return None


class HeaderGenerator:
    def __init__(self, objc_image: ObjCImage):
        self.type_resolver: TypeResolver = TypeResolver(objc_image)

        self.objc_image: ObjCImage = objc_image
        self.headers = {}

        for objc_class in objc_image.classlist:
            self.headers[objc_class.name + '.h'] = Header(self.type_resolver, objc_class)
        for objc_cat in objc_image.catlist:
            if objc_cat.classname != "":
                self.headers[objc_cat.classname + '+' + objc_cat.name + '.h'] = CategoryHeader(objc_cat)
        for objc_proto in objc_image.protolist:
            self.headers[objc_proto.name + '-Protocol.h'] = ProtocolHeader(objc_proto)

        if self.objc_image.name == "":
            image_name = self.objc_image.image.slice.macho_file.filename
        else:
            image_name = self.objc_image.name

        self.headers[image_name + '.h'] = UmbrellaHeader(self.headers)
        self.headers[image_name + '-Structs.h'] = StructHeader(objc_image)


class StructHeader:
    def __init__(self, objc_image: ObjCImage):
        """
        Scans through structs cached in the ObjCLib's type processor and writes them to a header

        :param objc_image: image containing structs
        """
        text = ""

        for struct in objc_image.tp.structs.values():
            text += str(struct) + '\n\n'

        self.text = text

    def __str__(self):
        return self.text


class Header:
    def __init__(self, type_resolver: TypeResolver, objc_class: Class):
        self.interface: Interface = Interface(objc_class)
        self.objc_class: Class = objc_class

        self.type_resolver: TypeResolver = type_resolver

        self.forward_declaration_classes: List[str] = []
        self.forward_declaration_protocols: List[str] = []

        self.imported_classes: Dict[str, str] = {}
        self.locally_imported_classes: List[str] = []
        self.locally_imported_protocols: List[str] = []

        self._process_import_section()

        self.text = self._generate_text()

    def __str__(self):
        return self.text

    def _generate_text(self) -> str:
        """
        Generates the header text based on the processed and configured properties

        :return: the header text
        """
        text = [HeaderUtils.header_head(self.type_resolver.objc_image.image),
                "#ifndef " + self.objc_class.name.upper() + "_H",
                "#define " + self.objc_class.name.upper() + "_H",
                ""]

        for i in self.objc_class.load_errors:
            text.append(f'// {i}')

        if len(self.objc_class.load_errors) > 0:
            text.append('')

        if len(self.forward_declaration_classes) > 0:
            text.append("@class " + ", ".join(self.forward_declaration_classes) + ";")
        if len(self.forward_declaration_protocols) > 0:
            text.append("@protocol " + ", ".join(self.forward_declaration_protocols) + ";")

        text.append("")

        imported_classes = {}

        for objc_class, install_name in self.imported_classes.items():
            if '/Frameworks/' in install_name:
                nam = install_name.split("/")[-1]
                if nam not in imported_classes:
                    imported_classes[nam] = nam
            else:
                imported_classes[objc_class] = install_name

        for objc_class, install_name in imported_classes.items():
            text.append(f'#import <{install_name.split("/")[-1]}/{objc_class}.h>')

        text.append("")

        for objc_class in self.locally_imported_classes:
            text.append(f'#import "{objc_class}.h"')

        for objc_protocol in self.locally_imported_protocols:
            text.append(f'#import "{objc_protocol}-Protocol.h"')

        text.append("")

        text.append(str(self.interface))
        text.append("")
        text.append("")

        text.append("#endif")

        return "\n".join(text)

    def _process_import_section(self):
        if self.interface.objc_class.superclass != "":
            type_name = self.interface.objc_class.superclass.split('_')[-1]
            resolved_type = self.type_resolver.find_linked(type_name)
            if resolved_type is None:
                if type_name != "id":
                    if type_name.startswith('<'):
                        if type_name[1:-1] not in self.forward_declaration_protocols:
                            self.forward_declaration_protocols.append(type_name[1:-1])
                    elif type_name.startswith('NSObject<'):
                        if type_name[9:-1] not in self.forward_declaration_protocols:
                            self.forward_declaration_protocols.append(type_name[9:-1])
                    else:
                        if type_name not in self.forward_declaration_classes:
                            self.forward_declaration_classes.append(type_name)
            elif resolved_type == "":
                if type_name not in self.locally_imported_classes:
                    self.locally_imported_classes.append(type_name)
            else:
                if type_name not in self.imported_classes:
                    self.imported_classes[type_name] = resolved_type
        for protocol in self.interface.objc_class.protocols:
            type_name = f'<{protocol.name}>'
            resolved_type = self.type_resolver.find_linked(type_name)
            if resolved_type == "-Protocol":
                self.locally_imported_protocols.append(protocol.name)
            else:
                self.forward_declaration_protocols.append(protocol.name)
        for ivar in self.interface.ivars:
            if ivar.is_id:
                type_name = ivar.type
                resolved_type = self.type_resolver.find_linked(type_name)
                if resolved_type is None:
                    if type_name != "id":
                        if type_name.startswith('<'):
                            if type_name[1:-1] not in self.forward_declaration_protocols:
                                self.forward_declaration_protocols.append(type_name[1:-1])
                        elif type_name.startswith('NSObject<'):

                            if type_name[9:-1] not in self.forward_declaration_protocols:
                                self.forward_declaration_protocols.append(type_name[9:-1])
                        else:
                            if type_name not in self.forward_declaration_classes:
                                self.forward_declaration_classes.append(type_name)
                elif resolved_type == "":
                    if type_name not in self.locally_imported_classes:
                        self.locally_imported_classes.append(type_name)
                elif resolved_type == "-Protocol":
                    if type_name not in self.locally_imported_protocols:
                        self.locally_imported_protocols.append(type_name[1:-1])
                else:
                    if type_name not in self.imported_classes:
                        self.imported_classes[type_name] = resolved_type
        for property in self.interface.properties:
            if property.is_id:
                type_name = property.type
                resolved_type = self.type_resolver.find_linked(type_name)
                if resolved_type is None:
                    if type_name != "id":
                        if type_name.startswith('<'):
                            if type_name[1:-1] not in self.forward_declaration_protocols:
                                self.forward_declaration_protocols.append(type_name[1:-1])
                        elif type_name.startswith('NSObject<'):

                            if type_name[9:-1] not in self.forward_declaration_protocols:
                                self.forward_declaration_protocols.append(type_name[9:-1])
                        else:
                            if type_name not in self.forward_declaration_classes:
                                self.forward_declaration_classes.append(type_name)
                elif resolved_type == "":
                    if type_name not in self.locally_imported_classes:
                        self.locally_imported_classes.append(type_name)
                elif resolved_type == "-Protocol":
                    if type_name not in self.locally_imported_protocols:
                        self.locally_imported_protocols.append(type_name[1:-1])
                else:
                    if type_name not in self.imported_classes:
                        self.imported_classes[type_name] = resolved_type


class CategoryHeader:
    def __init__(self, objc_category: Category):
        self.category = objc_category

        self.properties = objc_category.properties
        self.methods = objc_category.methods
        self.protocols = objc_category.protocols

        self.interface = CategoryInterface(objc_category)

        self.text = self._generate_text()

    def __str__(self):
        return self.text

    def _generate_text(self):
        """
        Generate Category text

        :return: category text
        """
        text = [HeaderUtils.header_head(self.category.objc_image.image),
                "",
                str(self.interface),
                "",
                ""]

        return "\n".join(text)


class ProtocolHeader:
    def __init__(self, objc_protocol: Protocol):
        self.protocol: Protocol = objc_protocol

        self.interface = ProtocolInterface(objc_protocol)

        self.text = self._generate_text()

    def __str__(self):
        return self.text

    def _generate_text(self):
        """
        Generate Protocol Header text

        :return:
        """
        text = [HeaderUtils.header_head(self.protocol.objc_image.image),
                "",
                str(self.interface),
                "",
                ""]

        return "\n".join(text)


class Interface:
    """
    The Interface class represents the "main body" of the header (not including the import section)

    """
    def __init__(self, objc_class: Class):
        self.objc_class = objc_class

        self.properties: List[Property] = []
        self.methods: List[Method] = []
        self.ivars: List[Ivar] = []
        self.structs = []

        # just store these so we know not to display them
        self.getters: List[str] = []
        self.setters: List[str] = []
        self._process_properties()
        self._process_methods()
        self._process_ivars()

    def __str__(self):
        head = "@interface " + self.objc_class.name + ' : '

        # Decode Superclass Name
        superclass = "NSObject"
        if self.objc_class.superclass != "":  # _OBJC_CLASS_$_UIApplication
            superclass = self.objc_class.superclass.split('_')[-1]

        head += superclass

        # Protocol Implementing Declaration
        if len(self.objc_class.protocols) > 0:
            head += " <"
            for protocol in self.objc_class.protocols:
                head += str(protocol) + ', '
            head = head[:-2]
            head += '>\n\n'

        # Ivar Declaration
        ivars = ""
        if len(self.ivars) > 0:
            ivars = " {\n"
            for ivar in self.ivars:
                ivars += '    ' + str(ivar) + ';\n'
            ivars += '}\n'

        props = "\n\n"
        for prop in self.properties:
            props += str(prop) + ';'
            if prop.ivarname != "":
                props += ' // ivar: ' + prop.ivarname + '\n'
            else:
                props += '\n'

        meths = "\n\n"
        for i in self.methods:
            if '.cxx_' not in str(i):
                meths += str(i) + ';\n'

        foot = "\n\n@end"
        return head + ivars + props + meths + foot

    def _process_properties(self):
        for property in self.objc_class.properties:
            if not hasattr(property, 'type'):
                continue
            if property.type.lower() == 'bool':
                getter_name = 'is' + property.name[0].upper() + property.name[1:]
                self.getters.append(getter_name)
            else:
                self.getters.append(property.name)
            if 'readonly' not in property.attributes:
                setter_name = 'set' + property.name[0].upper() + property.name[1:]
                self.setters.append(setter_name)
            self.properties.append(property)

    def _process_ivars(self):
        for ivar in self.objc_class.ivars:
            bad = False
            for prop in self.properties:
                if ivar.name == prop.ivarname:
                    bad = True
                    break
            if bad:
                continue
            self.ivars.append(ivar)

    def _process_methods(self):
        for method in self.objc_class.methods:
            bad = False
            for name in self.getters:
                if name in method.sel and ':' not in method.sel:
                    bad = True
                    break
            for name in self.setters:
                if name in method.sel and 'set' in method.sel:
                    bad = True
                    break
            if bad:
                continue
            self.methods.append(method)
        if self.objc_class.metaclass is not None:
            for method in self.objc_class.metaclass.methods:
                self.methods.append(method)


class StructDef:
    def __init__(self, struct_definition):
        self.struct_definition = struct_definition


class CategoryInterface:
    def __init__(self, objc_category: Category):
        self.category = objc_category

        self.properties = self.category.properties
        self.methods = self.category.methods
        self.protocols = self.category.protocols

        self.text = self._generate_text()

    def __str__(self):
        return self.text

    def _generate_text(self):

        head = "@interface "

        head += self.category.classname + " (" + self.category.name + ")"

        # Protocol Implementing Declaration
        if len(self.category.protocols) > 0:
            head += " <"
            for protocol in self.category.protocols:
                head += str(protocol) + ', '
            head = head[:-2]
            head += '>\n'

        # Ivar Declaration

        props = "\n\n"
        for prop in self.properties:
            props += str(prop) + ';'
            if prop.ivarname != "":
                props += ' // ivar: ' + prop.ivarname + '\n'
            else:
                props += '\n'

        meths = "\n\n"
        for i in self.methods:
            meths += str(i) + ';\n'

        foot = "@end\n"

        return head + props + meths + foot


class ProtocolInterface:
    def __init__(self, protocol: Protocol):
        self.protocol: Protocol = protocol

        self.text = self._generate_text()

    def __str__(self):
        return self.text

    def _generate_text(self):
        text = ["@protocol " + self.protocol.name, ""]

        for prop in self.protocol.properties:
            pro = ""
            pro += str(prop) + ';'
            if hasattr(prop, 'ivarname'):
                if prop.ivarname != "":
                    pro += ' // ivar: ' + prop.ivarname + ''
                else:
                    pro += ''
            text.append(pro)

        text.append("")

        for meth in self.protocol.methods:
            text.append(str(meth) + ';')

        text.append("")

        if len(self.protocol.opt_methods) > 0:
            text.append("@optional")
            for meth in self.protocol.opt_methods:
                text.append(str(meth) + ';')

        text.append("@end")

        return "\n".join(text)


class UmbrellaHeader:
    def __init__(self, header_list: dict):
        """
        Generates a header that solely imports other headers

        :param header_list: Dict of headers to be imported
        """
        self.text = "\n\n"
        for header in header_list.keys():
            self.text += "#include \"" + header + "\"\n"

    def __str__(self):
        return self.text
