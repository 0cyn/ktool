import unittest

from dyld.dyld import Dyld
from macho.machofile import MachOFile
from objc.objc_library import ObjCLibrary

class ObjCLoadTestCase(unittest.TestCase):
    def test_objc_load(self):
        fd = open('bins/PreferencesUI', 'rb')
        machofile = MachOFile(fd)
        library = Dyld.load(machofile.slices[0])
        objc_lib = ObjCLibrary(library)
        self.assertGreater(len(objc_lib.classlist), 1)
        self.assertGreater(len(objc_lib.classlist[0].methods), 4)
        fd.close()


if __name__ == '__main__':
    unittest.main()
