import unittest

from ktool.dyld import Dyld
from ktool.macho import MachOFile
from ktool.objc import ObjCLibrary
from ktool.generator import *

class KDumpTestCase(unittest.TestCase):
    def test_kdump(self):

        fd = open('bins/PreferencesUI', 'rb')
        machofile = MachOFile(fd)
        library = Dyld.load(machofile.slices[0])
        objc_lib = ObjCLibrary(library)
        objc_class = objc_lib.classlist[0]
        header = Header(objc_lib, objc_class)
        #print(header)
        for sym in library.symbol_table.ext:
            print(sym.name)
        #print(library.allowed_clients)
        fd.close()


if __name__ == '__main__':
    unittest.main()
