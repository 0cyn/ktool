from ktool.dyld import SymbolType
from ktool.objc import Class, ObjCLibrary, Category

_KTOOL_VERSION = "0.3.3"


class TBDGenerator:
    def __init__(self, library, general=True, objclib=None):
        self.library = library
        self.objclib = objclib
        self.general = general
        self.dict = self._generate_dict()

    def _generate_dict(self):
        tbd = {}
        if self.general:
            tbd['archs'] = ['armv7', 'armv7s', 'arm64', 'arm64e']
            tbd['platform'] = '(null)'
            tbd['install-name'] = self.library.dylib.install_name
            tbd['current-version'] = 1
            tbd['compatibility-version'] = 1

            exports = []
            export_dict = {'archs': ['armv7', 'armv7s', 'arm64', 'arm64e']}

            if len(self.library.allowed_clients) > 0:
                export_dict['allowed-clients'] = self.library.allowed_clients

            syms = []
            classes = []
            ivars = []

            for item in self.library.symbol_table.ext:
                if item.type == SymbolType.FUNC:
                    syms.append(item.name)
            if self.objclib:
                objc_library = self.objclib
            else:
                objc_library = ObjCLibrary(self.library)
            for objc_class in objc_library.classlist:
                classes.append('_' + objc_class.name)
                for ivar in objc_class.ivars:
                    ivars.append('_' + objc_class.name + '.' + ivar.name)
            export_dict['symbols'] = syms
            export_dict['objc-classes'] = classes
            export_dict['objc-ivars'] = ivars

            tbd['exports'] = [export_dict]
        return tbd


class HeaderGenerator:
    def __init__(self, library):
        self.library = library
        self.headers = {}

        for objc_class in library.classlist:
            self.headers[objc_class.name + '.h'] = Header(library, objc_class)

        for objc_cat in library.catlist:
            self.headers[objc_cat.classname + '+' + objc_cat.name + '.h'] = CategoryHeader(library, objc_cat)

        self.umbrella = UmbrellaHeader(self.headers)
        self.headers[self.library.name + '.h'] = self.umbrella
        self.headers[self.library.name + '-Structs.h'] = StructHeader(library)


class UmbrellaHeader:
    def __init__(self, header_list: dict):
        self.text = "\n\n"
        for header in header_list.keys():
            self.text += "#include \"" + header + "\"\n"

    def __str__(self):
        return self.text


class StructHeader:
    def __init__(self, library):
        text = ""

        for struct in library.tp.structs.values():
            text += str(struct) + '\n\n'

        self.text = text

    def __str__(self):
        return self.text


class CategoryHeader:
    def __init__(self, library, category: Category):
        self.library = library
        self.category = category

        self.properties = category.properties
        self.methods = category.methods
        self.protocols = category.protocols

        self.text = self._generate_text()

    def __str__(self):
        return self.text

    def _generate_text(self):

        prefix = "// Headers generated with ktool v" + _KTOOL_VERSION + "\n"
        prefix += "// https://github.com/kritantadev/ktool | pip3 install k2l\n"
        prefix += f'// Platform: {self.library.library.platform.name} | '
        prefix += f'Minimum OS: {self.library.library.minos.x}.{self.library.library.minos.y}.{self.library.library.minos.z} | '
        prefix += f'SDK: {self.library.library.sdk_version.x}.{self.library.library.sdk_version.y}.{self.library.library.sdk_version.z}\n\n'

        imports = ""

        ifndef = "#IFNDEF " + self.category.classname.upper() + "_" + self.category.name.upper() + "_" + "H"

        head = "@interface "

        head += self.category.classname + " (" + self.category.name + ")"

        # Protocol Implementing Declaration
        if len(self.category.protocols) > 0:
            head += " <"
            for prot in self.category.protocols:
                head += str(prot) + ', '
            head = head[:-2]
            head += '>'

        # Ivar Declaration

        props = ""
        for prop in self.properties:
            props += str(prop) + ';'
            if prop.ivarname != "":
                props += ' // ivar: ' + prop.ivarname + '\n'
            else:
                props += '\n'

        meths = ""
        for i in self.methods:
            meths += str(i) + ';\n'

        foot = "@end"

        endif = "#endif"
        return prefix + ifndef + '\n\n' + '\n\n' + imports + '\n\n' + head +  '\n\n' + props + '\n\n' + meths + '\n\n' + foot + '\n\n' + endif




class Header:
    def __init__(self, library, objcclass: Class):
        self.library = library
        self.objc_class = objcclass
        self.classlist = library.classlist

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

        self.self_importing_classnames = self._process_self_imports()
        # self.self_importing_classnames.append(self.library.name + '-Structs')
        self.text = self._generate_text()

    def __str__(self):
        return self.text

    def _generate_text(self):

        prefix = "// Headers generated with ktool v" + _KTOOL_VERSION + "\n"
        prefix += "// https://github.com/kritantadev/ktool | pip3 install k2l\n"
        prefix += f'// Platform: {self.library.library.platform.name} | '
        prefix += f'Minimum OS: {self.library.library.minos.x}.{self.library.library.minos.y}.{self.library.library.minos.z} | '
        prefix += f'SDK: {self.library.library.sdk_version.x}.{self.library.library.sdk_version.y}.{self.library.library.sdk_version.z}\n\n'

        imports = ""
        for linked_class in self.objc_class.linked_classes:
            if 'libobjc.A.dylib' in linked_class.libname:
                binname = 'Foundation'
                classname = 'Foundation'
            else:
                binname = linked_class.libname.split('/')[-1]
                classname = linked_class.classname
            imports += '#include <' + binname + '/' + classname + '.h>\n'

        if len(self.self_importing_classnames) > 0:
            imports += "\n"
            for classname in self.self_importing_classnames:
                imports += '#include "' + classname + '.h"\n'

        ifndef = "#ifndef " + self.objc_class.name.upper() + "_H\n"
        ifndef += "#define " + self.objc_class.name.upper() + "_H\n"

        foward_decs = ""
        if len(self.objc_class.fdec_classes) > 0:
            foward_decs += "@class "
            foward_decs += ', '.join(self.objc_class.fdec_classes)
            foward_decs += ";\n"
        if len(self.objc_class.fdec_prots) > 0:
            foward_decs += "@protocol "
            foward_decs += ', '.join(self.objc_class.fdec_prots)
            foward_decs += ";\n"

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
            head += '>'

        # Ivar Declaration
        ivars = ""
        if len(self.ivars) > 0:
            ivars = " {\n"
            for ivar in self.ivars:
                ivars += '    ' + str(ivar) + ';\n'
            ivars += '}\n'

        props = ""
        for prop in self.properties:
            props += str(prop) + ';'
            if prop.ivarname != "":
                props += ' // ivar: ' + prop.ivarname + '\n'
            else:
                props += '\n'

        meths = ""
        for i in self.methods:
            meths += str(i) + ';\n'

        foot = "@end"

        endif = "#endif"
        return prefix + ifndef + '\n\n' + foward_decs + '\n\n' + imports + '\n\n' + head + ivars + '\n\n' + props + '\n\n' + meths + '\n\n' + foot + '\n\n' + endif

    def _process_self_imports(self):
        self_import_classes = []
        for property in self.properties:
            for objc_class in self.classlist:
                if objc_class.name == property.type:
                    if objc_class.name not in self_import_classes:
                        self_import_classes.append(objc_class.name)
                        break
        for property in self.ivars:
            for objc_class in self.classlist:
                if objc_class.name == property.type:
                    if objc_class.name not in self_import_classes:
                        self_import_classes.append(objc_class.name)
                        break
        return self_import_classes

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
                if name in method.sel:
                    bad = True
                    break
            for name in self.setters:
                if name in method.sel:
                    bad = True
                    break
            if bad:
                continue
            self.methods.append(method)
        if self.objc_class.metaclass is not None:
            for method in self.objc_class.metaclass.methods:
                self.methods.append(method)
