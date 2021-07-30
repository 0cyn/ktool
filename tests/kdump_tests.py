import unittest

from macho.machofile import MachOFile
from objc.objc_library import ObjCLibrary
from kdump.headers import *

class KDumpTestCase(unittest.TestCase):
    def test_kdump(self):

        fd = open('bins/testbin1_fat', 'rb')
        machofile = MachOFile(fd)
        library = machofile.slices[0].library
        objc_lib = ObjCLibrary(library)
        objc_class = objc_lib.classlist[0]
        header = Header(objc_lib, objc_class)
        print(header)

        fd.close()


if __name__ == '__main__':
    unittest.main()
