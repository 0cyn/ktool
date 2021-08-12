from ktool.dyld import SymbolType
from ktool.objc import ObjCLibrary


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
