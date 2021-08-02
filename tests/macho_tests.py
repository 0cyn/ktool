import unittest

import ktool.macho


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

if __name__ == '__main__':
    unittest.main()
