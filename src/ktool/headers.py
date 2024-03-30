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
#  Copyright (c) 0cyn 2021.
#

from typing import List, Dict

from ktool.loader import SymbolType, Image
from ktool.objc import ObjCImage, Class, Category, Protocol, Property, Method, Ivar

from ktool.util import KTOOL_VERSION

from pygments import highlight
from pygments.formatters.terminal import TerminalFormatter
try:
    from pygments.lexers.objective import ObjectiveCLexer
except ImportError:
    ObjectiveCLexer = None


class HeaderUtils:

    @staticmethod
    def header_head_html(image: Image) -> str:
        """
        This is the prefix comments at the very top of the headers generated

        :param image: MachO Image
        :return: Newline delimited string to be placed at the top of the header.
        """
        try:
            prefix = """
<div class="highlight"><pre><span></span><span class="c1">// Headers generated with ktool v{}</span>
<span class="c1">// <a href="https://github.com/0cyn/ktool">https://github.com/0cyn/ktool</a> | pip3 install k2l</span>
<span class="c1">// Platform: {} | Minimum OS: {} | SDK: {}</span>""".format(KTOOL_VERSION, image.platform.name,
                                                                            f'{image.minos.x}.{image.minos.y}.{image.minos.z}',
                                                                             f'{image.sdk_version.x}.{image.sdk_version.y}.{image.sdk_version.z}')
        except AttributeError:
            prefix = """
<div class="highlight"><pre><span></span><span class="c1">// Headers generated with ktool v{}</span>
<span class="c1">// https://github.com/0cyn/ktool | pip3 install k2l</span>
<span class="c1">// Issue loading image metadata""".format(KTOOL_VERSION)
        return prefix




    @staticmethod
    def header_head(image: Image) -> str:
        """
        This is the prefix comments at the very top of the headers generated

        :param image: MachO Image
        :return: Newline delimited string to be placed at the top of the header.
        """
        try:
            prefix = "// Headers generated with ktool v" + KTOOL_VERSION + "\n"
            prefix += "// https://github.com/cxnder/ktool | pip3 install k2l\n"
            prefix += f'// Platform: {image.platform.name} | '
            prefix += f'Minimum OS: {image.minos.x}.{image.minos.y}.{image.minos.z} | '
            prefix += f'SDK: {image.sdk_version.x}.{image.sdk_version.y}.{image.sdk_version.z}\n\n' 
            return prefix
        except AttributeError:
            prefix = "// Headers generated with ktool v" + KTOOL_VERSION + "\n"
            prefix += "// https://github.com/cxnder/ktool | pip3 install k2l\n"
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
            for sym in objc_image.image.imports:
                if sym.dec_type == SymbolType.CLASS:
                    self.classmap[sym.name[1:]] = sym
                    classes.append(sym)
        except AttributeError:
            pass
        self.classes = classes
        self.local_classes = objc_image.classlist
        self.local_protos = objc_image.protolist

        self._linked_cache = {'NSObject': '/System/Library/Frameworks/Foundation'}

    # noinspection PyTypeChecker
    def find_linked(self, classname: str):
        """
        given a classname, return install name of a framework if that class was imported from it.

        :param classname:
        :return:
        """

        if classname in self._linked_cache:
            return self._linked_cache[classname]

        for local in self.local_classes:
            if local.name == classname:
                self._linked_cache[classname] = ""
                return ""
        for local in self.local_protos:
            if local.name == classname[1:-1]:
                self._linked_cache[classname] = "-Protocol"
                return "-Protocol"
        if classname in self.classmap:
            try:
                name = self.objc_image.image.linked_images[int(self.classmap[classname].ordinal) - 1].install_name
                if '.dylib' in name:
                    self._linked_cache[classname] = None
                    return None
                self._linked_cache[classname] = name
                return name
            except IndexError:
                pass

        self._linked_cache[classname] = None
        return None


class HeaderGenerator:
    def __init__(self, objc_image: ObjCImage, forward_declare_private_includes=False):
        self.type_resolver: TypeResolver = TypeResolver(objc_image)

        self.objc_image: ObjCImage = objc_image
        self.headers = {}

        for objc_class in objc_image.classlist:
            self.headers[objc_class.name + '.h'] = Header(self.objc_image, self.type_resolver, objc_class, forward_declare_private_includes)
        for objc_cat in objc_image.catlist:
            if objc_cat.classname != "":
                self.headers[f'{objc_cat.classname}+{objc_cat.name}.h'] = CategoryHeader(self.objc_image, objc_cat)
        for objc_proto in objc_image.protolist:
            self.headers[objc_proto.name + '-Protocol.h'] = ProtocolHeader(self.objc_image, objc_proto)

        if self.objc_image.name == "":
            image_name = self.objc_image.image.slice.macho_file.filename
        else:
            image_name = self.objc_image.name

        if image_name + '.h' in self.headers:
            self.headers[image_name + '-Umbrella.h'] = UmbrellaHeader(self.headers)
        else:
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
    def __init__(self, objc_image: 'ObjCImage', type_resolver, objc_class: Class, forward_declare_private_imports):
        self.interface: Interface = Interface(objc_class)
        self.objc_image = objc_image
        self.objc_class: Class = objc_class

        self.type_resolver: TypeResolver = type_resolver

        self.forward_declare_private_imports = forward_declare_private_imports

        self.forward_declaration_classes: List[str] = []
        self.forward_declaration_protocols: List[str] = []

        self.imported_classes: Dict[str, str] = {}
        self.locally_imported_classes: List[str] = []
        self.locally_imported_protocols: List[str] = []

        self._process_import_section()

        self.text = self._generate_text()
        self.highlighted_text = None

    def __str__(self):
        return self.text

    def generate_highlighted_text(self):
        if ObjectiveCLexer is None:
            return self.text
        if self.highlighted_text:
            return self.highlighted_text

        formatter = TerminalFormatter()
        self.highlighted_text = highlight(self.text, ObjectiveCLexer(), formatter)

        return self.highlighted_text

    def generate_html(self, generate_address_links=False):
        text = [HeaderUtils.header_head_html(self.objc_image.image)]
        for i in self.objc_class.load_errors:
            text.append(f'<span class="c1">// err: {i}</span>')
        if len(self.objc_class.load_errors) > 0:
            text.append('')
        if len(self.forward_declaration_classes) > 0:
            text.append(f'<span class="k">@class</span> ' + ', '.join(self.forward_declaration_classes) + ';')
        if len(self.forward_declaration_protocols) > 0:
            text.append(f'<span class="k">@protocol</span> ' + ', '.join(self.forward_declaration_protocols) + ';')
        text.append('')
        imported_classes = {}
        for objc_class, install_name in self.imported_classes.items():
            if '/Frameworks/' in install_name:
                nam = install_name.split("/")[-1]
                if nam not in imported_classes:
                    imported_classes[nam] = nam
            else:
                if self.forward_declare_private_imports:
                    text.append(f'<span class="k">@class</span> {objc_class};')
                else:
                    imported_classes[objc_class] = install_name
        for objc_class, install_name in imported_classes.items():
            text.append(f'<span class="k">#import</span> &lt;{install_name.split("/")[-1]}/{objc_class}.h&gt;')
        text.append('')
        if self.forward_declare_private_imports:
            for objc_class in self.locally_imported_classes:
                text.append(f'<span class="k">@class</span> {objc_class};')
            for objc_protocol in self.locally_imported_protocols:
                text.append(f'<span class="k">@protocol</span> {objc_protocol};')
        else:
            for objc_class in self.locally_imported_classes:
                objc_class_text = f'&quot;{objc_class}.h&quot;'
                text.append(f'<span class="cp">#import {objc_class_text}</span>')
            for objc_protocol in self.locally_imported_protocols:
                objc_proto_text = f'&quot;{objc_protocol}-Protocol.h&quot;'
                text.append(f'<span class="cp">#import {objc_proto_text}</span>')

        text.append('')
        text.append(self.interface.generate_html(generate_address_links))
        text.append('')
        return '\n'.join(text)

    def _generate_text(self) -> str:
        """
        Generates the header text based on the processed and configured properties

        :return: the header text
        """
        text = [HeaderUtils.header_head(self.objc_image.image),
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
                if self.forward_declare_private_imports:
                    text.append(f'@class {objc_class};')
                else:
                    imported_classes[objc_class] = install_name

        for objc_class, install_name in imported_classes.items():
            text.append(f'#import <{install_name.split("/")[-1]}/{objc_class}.h>')

        text.append("")

        if self.forward_declare_private_imports:
            for objc_class in self.locally_imported_classes:
                text.append(f'@class {objc_class};')
            for objc_protocol in self.locally_imported_protocols:
                text.append(f'@protocol {objc_protocol};')
        else:
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
        for objc_property in self.interface.properties:
            if objc_property.is_id:
                type_name = objc_property.type
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
    def __init__(self, objc_image, objc_category: Category):
        self.objc_image = objc_image
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
        text = [HeaderUtils.header_head(self.objc_image.image),
                "",
                str(self.interface),
                "",
                ""]

        return "\n".join(text)


class ProtocolHeader:
    def __init__(self, objc_image, objc_protocol: Protocol):
        self.objc_image = objc_image
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
        text = [HeaderUtils.header_head(self.objc_image.image),
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

    def generate_html(self, generate_address_links=False):
        if generate_address_links:
            head = f'<span class="k">@interface</span> <span class="k"><a href="addr/{self.objc_class.loc}">{self.objc_class.name}</a></span>'
        else:
            head = f'<span class="k">@interface</span> <span class="k">{self.objc_class.name}</span>'
        superclass = "NSObject"
        if self.objc_class.superclass != "":
            superclass = self.objc_class.superclass.split('_')[-1]
        head += f' : <span class="bp">{superclass}</span>'
        if len(self.objc_class.protocols) > 0:
            head += '<span class="o">&lt;</span>'
            for protocol in self.objc_class.protocols:
                head += f'<span class="n">{protocol}</span><span class="p">,</span> '
            head = head[:-len('<span class="p">,</span> ')]
            head += '<span class="o">&gt;</span>'

        ivars = ""
        if len(self.ivars) > 0:
            ivars = "<span class='o'>{</span>\n"
            for ivar in self.ivars:
                ptr_count = ivar.type.count('*')
                type_text = ivar.type.replace("*", "")
                if generate_address_links:
                    type_text = f'<a href="type/{type_text}">{type_text}</a>'
                ivars += f'\t<span class="bp">{type_text}</span>'
                for i in range(ptr_count):
                    ivars += '<span class="o">*</span>'
                ivar_name = ivar.name
                if generate_address_links:
                    ivar_name = f'<a href="ivar/{self.objc_class.name}/{ivar_name}">{ivar_name}</a>'
                ivars += f' <span class="n">{ivar_name}</span><span class="p">;</span>\n'
            ivars += '<span class="o">}</span>'

        props = ""
        for prop in self.properties:
            props += f'<span class="k">@property</span> '

            if len(prop.attributes):
                props += '<span class="p">(</span>'
                for attr in prop.attributes:
                    props += f'<span class="p">{attr}</span>, '
                props = props[:-2]
                props += '<span class="k">)</span> '

            prop_type = prop.type
            if generate_address_links:
                prop_type = f'<a href="type/{prop_type}">{prop_type}</a>'
            props += f'<span class="bp">{prop_type}</span> '
            for i in range(prop.type.count('*')):
                props += '<span class="o">*</span>'
            if prop.is_id:
                props += '<span class="o">*</span>'
            props += f'<span class="n">{prop.name}</span><span class="p">;</span>'

            if generate_address_links or prop.ivarname != "":
                props += '<span class="c1"> // '

            if generate_address_links:
                getter = prop.attr.getter
                if getter == "" or getter is None:
                    getter = prop.name
                setter = prop.attr.setter
                if setter == "" or setter is None:
                    setter = f'set{prop.name[0].upper()}{prop.name[1:]}:'
                getter = f'<a href="meth/{self.objc_class.name}/{getter}">Getter</a>'
                setter = f'<a href="meth/{self.objc_class.name}/{setter}">Setter</a>'
                props += f'{getter} | '
                if 'readonly' not in prop.attributes:
                    props += f'{setter} | '
            if prop.ivarname != "":
                ivarname = prop.ivarname
                if generate_address_links:
                    ivarname = f'<a href="ivar/{self.objc_class.name}/{ivarname}">{ivarname}</a>'
                props += f' ivar: {ivarname}'
            else:
                props = props[:-3]
            if generate_address_links or prop.ivarname != "":
                props += '</span>'
            props += '\n'

        meths = ""
        for meth in self.methods:
            if meth.sel.strip() != "":
                meths += f'<span class="p">{"+" if meth.meta else "-"}</span> '
                meths += f'<span class="p">(</span>'
                meths += f'<span class="p">{meth.return_string}</span>'
                meths += f'<span class="p">)</span> '
                if generate_address_links:
                    meths += f'<a href="addr/{meth.imp}">'
                if len(meth.arguments) == 0:
                    meths += f'<span class="nf">{meth.sel}</span> '
                else:
                    segments = []
                    for i, item in enumerate(meth.sel.split(':')):
                        if item == "":
                            continue
                        try:
                            segments.append(f'<span class="nf">{item}:</span>' + '<span class="p">(</span>'
                                            + f'<span class="nv">{meth.arguments[i + 2]}</span>' + '<span class="p">)</span>'
                                            + 'arg' + str(i) + ' ')
                        except IndexError:
                            segments.append(item)

                    sig = ''.join(segments)
                    meths += sig
                meths += f'<span class="p">;</span>\n'
                if generate_address_links:
                    meths += '</a>'

        foot = "<span class='k'>@end</span>"
        return '\n'.join([head, ivars, props, meths, foot])

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
            if i.sel.strip() != "":
                if '(unk)' in str(i):
                    meths += f'// {str(i)} ;\n'
                elif '.cxx_' not in str(i):
                    meths += str(i) + ';\n'

        foot = "\n\n@end"
        return head + ivars + props + meths + foot

    def _process_properties(self):
        for objc_property in self.objc_class.properties:
            if not hasattr(objc_property, 'type'):
                continue
            self.getters.append(objc_property.getter)
            self.setters.append(objc_property.setter)
            self.properties.append(objc_property)

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


