from ktool.dyld import SymbolType
from ktool.objc import Class, ObjCLibrary, Category

_KTOOL_VERSION = "0.3.5"


class TBDGenerator:
    def __init__(self, library, general=True, objclib=None):
        """
        The TBD Generator is a generator that creates TAPI formatted text based stubs for libraries.

        It is currently fairly incomplete, although its output should still be perfectly functional in an SDK.

        After processing, its .dict attribute can be dumped by a TAPI YAML serializer (located in ktool.util) to
            produce a functional .tbd

        :param library: dyld.Library object
        :param general: Should the generator create a .tbd for usage in SDKs?
        :param objclib: Pass an objc library to the genrator. If none is passed it will generate its own
        """
        self.library = library
        self.objclib = objclib
        self.general = general
        self.dict = self._generate_dict()

    def _generate_dict(self):
        """
        This function simply parses through the library and creates the tbd dict

        :return: The text-based-stub dictionary representation
        """
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
        """
        This generator takes an objc library as an argument and generates the headers for it

        It generates a header for each Class and Category

        It also generates an Umbrella header which just imports all headers in the Framework
        It also generates a [name]-Structs header which contains all struct definitions found.

        :param library: ObjCLibrary to generate headers for
        """
        self.library = library
        self.headers = {}

        for objc_class in library.classlist:
            self.headers[objc_class.name + '.h'] = Header(library, objc_class)

        structnamemap = []
        unresolved = []
        for header in self.headers:
            structs = []
            for struct in self.headers[header].structs:
                if struct.name not in structs:
                    structs.append(struct.name)
            for struct in structs:
                if struct not in structnamemap:
                    structnamemap.append(struct)
                else:
                    if struct not in unresolved:
                        unresolved.append(struct)

        for objc_cat in library.catlist:
            self.headers[objc_cat.classname + '+' + objc_cat.name + '.h'] = CategoryHeader(library, objc_cat)

        self.umbrella = UmbrellaHeader(self.headers)
        self.headers[self.library.name + '.h'] = self.umbrella
        self.headers[self.library.name + '-Structs.h'] = StructHeader(library)


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


class CategoryHeader:
    def __init__(self, library, category: Category):
        """
        This represents a header for an ObjC Category (sometimes refered to as extending, i think?)

        Generating one of these is fairly straightforward compared to a regular class header due to simpler definitions

        :param library: ObjC Library to process
        :param category: Category object to represent
        """
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
