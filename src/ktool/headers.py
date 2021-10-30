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

from .dyld import SymbolType
from .objc import ObjCLibrary

from .util import KTOOL_VERSION


class HeaderUtils:

    @staticmethod
    def header_head(library):
        try:
            prefix = "// Headers generated with ktool v" + KTOOL_VERSION + "\n"
            prefix += "// https://github.com/kritantadev/ktool | pip3 install k2l\n"
            prefix += f'// Platform: {library.platform.name} | '
            prefix += f'Minimum OS: {library.minos.x}.{library.minos.y}.{library.minos.z} | '
            prefix += f'SDK: {library.sdk_version.x}.{library.sdk_version.y}.{library.sdk_version.z}\n\n'
            return prefix
        except AttributeError:
            prefix = "// Headers generated with ktool v" + KTOOL_VERSION + "\n"
            prefix += "// https://github.com/kritantadev/ktool | pip3 install k2l\n"
            prefix += "// Issue loading library metadata\n\n"
            return prefix


class TypeResolver:
    def __init__(self, objc_library: ObjCLibrary):
        self.library = objc_library
        classes = []
        self.classmap = {}
        try:
            for sym in objc_library.library.binding_table.symbol_table:
                if sym.type == SymbolType.CLASS:
                    self.classmap[sym.name[1:]] = sym
                    classes.append(sym)
        except AttributeError:
            pass
        self.classes = classes
        self.local_classes = objc_library.classlist
        self.local_protos = objc_library.protolist

    def find_linked(self, classname):
        for local in self.local_classes:
            if local.name == classname:
                return ""
        for local in self.local_protos:
            if local.name == classname[1:-1]:
                return "-Protocol"
        if classname in self.classmap:
            try:
                nam = self.library.library.linked[int(self.classmap[classname].ordinal) - 1].install_name
                if '.dylib' in nam:
                    return None
                return nam
            except Exception as ex:
                pass
        return None


class HeaderGenerator:
    def __init__(self, objc_library):
        self.type_resolver = TypeResolver(objc_library)

        self.library = objc_library
        self.headers = {}

        for objc_class in objc_library.classlist:
            self.headers[objc_class.name + '.h'] = Header(self.type_resolver, objc_class)
        for objc_cat in objc_library.catlist:
            if objc_cat.classname != "":
                self.headers[objc_cat.classname + '+' + objc_cat.name + '.h'] = CategoryHeader(objc_cat)
        for objc_proto in objc_library.protolist:
            self.headers[objc_proto.name + '-Protocol.h'] = ProtocolHeader(objc_proto)

        self.headers[self.library.name + '.h'] = UmbrellaHeader(self.headers)
        self.headers[self.library.name + '-Structs.h'] = StructHeader(objc_library)


class StructHeader:
    def __init__(self, library):
        """
        Scans through structs cached in the ObjCLib's type processor and writes them to a header

        :param library: Library containing structs
        """
        text = ""

        for struct in library.tp.structs.values():
            text += str(struct) + '\n\n'

        self.text = text

    def __str__(self):
        return self.text


class Header:
    def __init__(self, type_resolver, objc_class):
        self.interface = Interface(objc_class)
        self.objc_class = objc_class

        self.type_resolver = type_resolver

        self.forward_declaration_classes = []
        self.forward_declaration_protocols = []

        self.imported_classes = {}
        self.locally_imported_classes = []
        self.locally_imported_protocols = []

        self._get_import_section()

        self.text = self._generate_text()

    def __str__(self):
        return self.text

    def _generate_text(self):
        text = [HeaderUtils.header_head(self.type_resolver.library.library),
                "#ifndef " + self.objc_class.name.upper() + "_H", "#define " + self.objc_class.name.upper() + "_H", ""]

        if len(self.forward_declaration_classes) > 0:
            text.append("@class " + ", ".join(self.forward_declaration_classes) + ";")
        if len(self.forward_declaration_protocols) > 0:
            text.append("@protocol " + ", ".join(self.forward_declaration_protocols) + ";")

        text.append("")

        imported_classes = {}

        for oclass, installname in self.imported_classes.items():
            if '/Frameworks/' in installname:
                nam = installname.split("/")[-1]
                if nam not in imported_classes:
                    imported_classes[nam] = nam
            else:
                imported_classes[oclass] = installname

        for oclass, installname in imported_classes.items():
            text.append(f'#import <{installname.split("/")[-1]}/{oclass}.h>')

        text.append("")

        for oclass in self.locally_imported_classes:
            text.append(f'#import "{oclass}.h"')

        for oprot in self.locally_imported_protocols:
            text.append(f'#import "{oprot}-Protocol.h"')

        text.append("")

        text.append(str(self.interface))
        text.append("")
        text.append("")

        text.append("#endif")

        return "\n".join(text)

    def _get_import_section(self):
        if self.interface.objc_class.superclass != "":
            tp = self.interface.objc_class.superclass.split('_')[-1]
            rt = self.type_resolver.find_linked(tp)
            if rt is None:
                if tp != "id":
                    if tp.startswith('<'):
                        if tp[1:-1] not in self.forward_declaration_protocols:
                            self.forward_declaration_protocols.append(tp[1:-1])
                    elif tp.startswith('NSObject<'):
                        if tp[9:-1] not in self.forward_declaration_protocols:
                            self.forward_declaration_protocols.append(tp[9:-1])
                    else:
                        if tp not in self.forward_declaration_classes:
                            self.forward_declaration_classes.append(tp)
            elif rt == "":
                if tp not in self.locally_imported_classes:
                    self.locally_imported_classes.append(tp)
            else:
                if tp not in self.imported_classes:
                    self.imported_classes[tp] = rt
        for proto in self.interface.objc_class.protocols:
            tname = f'<{proto.name}>'
            rt = self.type_resolver.find_linked(tname)
            if rt == "-Protocol":
                self.locally_imported_protocols.append(proto.name)
            else:
                self.forward_declaration_protocols.append(proto.name)
        for ivar in self.interface.ivars:
            if ivar.is_id:
                tp = ivar.type
                rt = self.type_resolver.find_linked(tp)
                if rt is None:
                    if tp != "id":
                        if tp.startswith('<'):
                            if tp[1:-1] not in self.forward_declaration_protocols:
                                self.forward_declaration_protocols.append(tp[1:-1])
                        elif tp.startswith('NSObject<'):

                            if tp[9:-1] not in self.forward_declaration_protocols:
                                self.forward_declaration_protocols.append(tp[9:-1])
                        else:
                            if tp not in self.forward_declaration_classes:
                                self.forward_declaration_classes.append(tp)
                elif rt == "":
                    if tp not in self.locally_imported_classes:
                        self.locally_imported_classes.append(tp)
                elif rt == "-Protocol":
                    if tp not in self.locally_imported_protocols:
                        self.locally_imported_protocols.append(tp[1:-1])
                else:
                    if tp not in self.imported_classes:
                        self.imported_classes[tp] = rt
        for property in self.interface.properties:
            if property.is_id:
                tp = property.type
                rt = self.type_resolver.find_linked(tp)
                if rt is None:
                    if tp != "id":
                        if tp.startswith('<'):
                            if tp[1:-1] not in self.forward_declaration_protocols:
                                self.forward_declaration_protocols.append(tp[1:-1])
                        elif tp.startswith('NSObject<'):

                            if tp[9:-1] not in self.forward_declaration_protocols:
                                self.forward_declaration_protocols.append(tp[9:-1])
                        else:
                            if tp not in self.forward_declaration_classes:
                                self.forward_declaration_classes.append(tp)
                elif rt == "":
                    if tp not in self.locally_imported_classes:
                        self.locally_imported_classes.append(tp)
                elif rt == "-Protocol":
                    if tp not in self.locally_imported_protocols:
                        self.locally_imported_protocols.append(tp[1:-1])
                else:
                    if tp not in self.imported_classes:
                        self.imported_classes[tp] = rt


class CategoryHeader:
    def __init__(self, objc_category):
        self.category = objc_category

        self.properties = objc_category.properties
        self.methods = objc_category.methods
        self.protocols = objc_category.protocols

        self.interface = CategoryInterface(objc_category)

        self.text = self._generate_text()

    def __str__(self):
        return self.text

    def _generate_text(self):
        text = [HeaderUtils.header_head(self.category.library.library),
                "",
                str(self.interface),
                "",
                ""]

        return "\n".join(text)


class ProtocolHeader:
    def __init__(self, objc_protocol):
        self.protocol = objc_protocol

        self.interface = ProtocolInterface(objc_protocol)

        self.text = self._generate_text()

    def __str__(self):
        return self.text

    def _generate_text(self):
        text = [HeaderUtils.header_head(self.protocol.library.library),
                "",
                str(self.interface),
                "",
                ""]

        return "\n".join(text)


class Interface:
    def __init__(self, objc_class):
        self.objc_class = objc_class

        self.properties = []
        self.methods = []
        self.ivars = []
        self.structs = []

        # just store these so we know not to display them
        self.getters = []
        self.setters = []
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
            for prot in self.objc_class.protocols:
                head += str(prot) + ', '
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
                gettername = 'is' + property.name[0].upper() + property.name[1:]
                self.getters.append(gettername)
            else:
                self.getters.append(property.name)
            if 'readonly' not in property.attributes:
                settername = 'set' + property.name[0].upper() + property.name[1:]
                self.setters.append(settername)
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
    def __init__(self, structdef):
        self.structdef = structdef


class CategoryInterface:
    def __init__(self, objc_category):
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
            for prot in self.category.protocols:
                head += str(prot) + ', '
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
    def __init__(self, protocol):
        self.protocol = protocol

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
