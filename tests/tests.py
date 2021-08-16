import logging
import sys
import unittest
import os.path

# We need to be in the right directory so we can find the bins
scriptdir = os.path.dirname(os.path.realpath(__file__))

sys.path.extend([f'{scriptdir}/../src'])

import ktool.macho
from ktool.dyld import Dyld
from ktool.generator import TBDGenerator
from ktool.headers import HeaderGenerator
from ktool.macho import MachOFile
from ktool.objc import ObjCLibrary
from ktool.util import TapiYAMLWriter, log, LogLevel

log.LOG_LEVEL = LogLevel.DEBUG

class SymTabTestCase(unittest.TestCase):
    def test_bin(self):
        with open(scriptdir + '/bins/testbin1', 'rb') as file:
            machofile = MachOFile(file)
            library = Dyld.load(machofile.slices[0])
            self.assertEqual(len(library.symbol_table.table), 23)


class TBDTestCase(unittest.TestCase):
    def test_tapi_dump(self):
        with open(scriptdir + '/bins/PreferencesUI.dyldex', 'rb') as file:
            machofile = MachOFile(file)
            library = Dyld.load(machofile.slices[0])
            tbd_dict = TBDGenerator(library).dict
            print(TapiYAMLWriter.write_out(tbd_dict))


class FileLoadTestCase(unittest.TestCase):
    def test_fat_load(self):
        with open(scriptdir + '/bins/testbin1_fat', 'rb') as file:
            macho_file = ktool.macho.MachOFile(file)
            self.assertEqual(macho_file.type, ktool.macho.MachOFileType.FAT)
            self.assertEqual(len(macho_file.slices), 2)

    def test_thin_load(self):
        with open(scriptdir + '/bins/testbin1', 'rb') as file:
            macho_file = ktool.macho.MachOFile(file)
            self.assertEqual(macho_file.type, ktool.macho.MachOFileType.THIN)


class FrameworksTestCase(unittest.TestCase):

    def test_coherence(self):
        with open(scriptdir + '/bins/Coherence.dyldex', 'rb') as fd:
            HeaderGenerator(ObjCLibrary(Dyld.load(MachOFile(fd).slices[0])))

    def test_safari_shared(self):
        with open(scriptdir + '/bins/SafariShared.dyldex', 'rb') as fd:
            HeaderGenerator(ObjCLibrary(Dyld.load(MachOFile(fd).slices[0])))

    def test_ktrace(self):
        with open(scriptdir + '/bins/ktrace.dyldex', 'rb') as fd:
            ObjCLibrary(Dyld.load(MachOFile(fd).slices[0]))

    def test_pfui(self):
        with open(scriptdir + '/bins/PreferencesUI', 'rb') as fd:
            ObjCLibrary(Dyld.load(MachOFile(fd).slices[0]))

    def test_pfui2(self):
        with open(scriptdir + '/bins/PreferencesUI.dyldex', 'rb') as fd:
            ObjCLibrary(Dyld.load(MachOFile(fd).slices[0]))

    def test_search(self):
        with open(scriptdir + '/bins/Search', 'rb') as fd:
            ObjCLibrary(Dyld.load(MachOFile(fd).slices[0]))

    def test_sbh(self):
        with open(scriptdir + '/bins/SpringBoardHome', 'rb') as fd:
            objc_lib = ObjCLibrary(Dyld.load(MachOFile(fd).slices[0]))
            self.assertGreater(len(objc_lib.classlist), 1)
            self.assertGreater(len(objc_lib.catlist), 1)
            self.assertGreater(len(objc_lib.classlist[0].methods), 4)


if __name__ == '__main__':
    unittest.main()