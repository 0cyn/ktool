import unittest

from dyld.dyld import Dyld
from macho.machofile import MachOFile
from objc.objc_library import ObjCLibrary
from ktool.headers import *

class KDumpTestCase(unittest.TestCase):
    def test_kdump(self):

        fd = open('bins/PreferencesUI', 'rb')
        machofile = MachOFile(fd)
        library = Dyld.load(machofile.slices[0])
        objc_lib = ObjCLibrary(library)
        objc_class = objc_lib.classlist[0]
        header = Header(objc_lib, objc_class)
        print(header)
        for sym in library.symtab.table:
            print(sym.name)
        fd.close()


if __name__ == '__main__':
    unittest.main()
