import unittest

from ktool.dyld import Dyld
from ktool.macho import MachOFile


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





if __name__ == '__main__':
    unittest.main()
