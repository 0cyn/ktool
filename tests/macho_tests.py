import unittest

from macho import machofile


class FileLoadTestCase(unittest.TestCase):
    def test_fat_load(self):
        with open('bins/testbin1_fat', 'rb') as file:
            macho_file = machofile.MachOFile(file)
            self.assertEqual(macho_file.type, machofile.MachOFileType.FAT)
            self.assertEqual(len(macho_file.slices), 2)

    def test_thin_load(self):
        with open('bins/testbin1', 'rb') as file:
            macho_file = machofile.MachOFile(file)
            self.assertEqual(macho_file.type, machofile.MachOFileType.THIN)

if __name__ == '__main__':
    unittest.main()
