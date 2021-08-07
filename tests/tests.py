import unittest

import ktool.macho
from ktool.dyld import Dyld
from ktool.generator import Header, TBDGenerator
from ktool.macho import MachOFile
from ktool.objc import ObjCLibrary
from ktool.util import TapiYAMLWriter


class SymTabTestCase(unittest.TestCase):
    def test_pfui(self):
        with open('bins/PreferencesUI', 'rb') as file:
            machofile = MachOFile(file)
            library = Dyld.load(machofile.slices[0])
            self.assertEqual(len(library.symbol_table.table), 1279)

    def test_bin(self):
        with open('bins/testbin1', 'rb') as file:
            machofile = MachOFile(file)
            library = Dyld.load(machofile.slices[0])
            self.assertEqual(len(library.symbol_table.table), 23)


class KDumpTestCase(unittest.TestCase):
    def test_kdump(self):

        fd = open('bins/SpringBoardHome', 'rb')
        machofile = MachOFile(fd)
        library = Dyld.load(machofile.slices[0])
        objc_lib = ObjCLibrary(library)
        objc_class = objc_lib.classlist[0]
        header = Header(objc_lib, objc_class)
        #print(header)
        #for sym in library.symbol_table.ext:
        #    print(sym.name)
        #print(library.allowed_clients)
        fd.close()

    def test_tapi_dump(self):
        with open('bins/PreferencesUI.dyldex', 'rb') as file:
            machofile = MachOFile(file)
            library = Dyld.load(machofile.slices[0])
            tbd_dict = TBDGenerator(library).dict
            print(TapiYAMLWriter.write_out(tbd_dict))


class FileLoadTestCase(unittest.TestCase):
    def test_fat_load(self):
        with open('bins/testbin1_fat', 'rb') as file:
            macho_file = ktool.macho.MachOFile(file)
            self.assertEqual(macho_file.type, ktool.macho.MachOFileType.FAT)
            self.assertEqual(len(macho_file.slices), 2)

    def test_thin_load(self):
        with open('bins/testbin1', 'rb') as file:
            macho_file = ktool.macho.MachOFile(file)
            self.assertEqual(macho_file.type, ktool.macho.MachOFileType.THIN)


class ObjCLoadTestCase(unittest.TestCase):
    def test_objc_load(self):
        fd = open('bins/SpringBoardHome', 'rb')
        machofile = MachOFile(fd)
        library = Dyld.load(machofile.slices[0])
        objc_lib = ObjCLibrary(library)
        self.assertGreater(len(objc_lib.classlist), 1)
        self.assertGreater(len(objc_lib.catlist), 1)
        self.assertGreater(len(objc_lib.classlist[0].methods), 4)
        fd.close()


if __name__ == '__main__':
    unittest.main()