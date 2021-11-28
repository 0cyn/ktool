import os
import sys
import unittest

from ktool import (
    log,
    Dyld,
    LogLevel,
    TBDGenerator,
    HeaderGenerator,
    MachOFile,
    MachOFileType,
    ObjCImage,
    TapiYAMLWriter,
)


# We need to be in the right directory so we can find the bins
scriptdir = os.path.dirname(os.path.realpath(__file__))

sys.path.extend([f'{scriptdir}/../src'])
log.LOG_LEVEL = LogLevel.WARN


class SymTabTestCase(unittest.TestCase):
    def test_bin(self):
        with open(scriptdir + '/bins/testbin1', 'rb') as file:
            machofile = MachOFile(file)
            image = Dyld.load(machofile.slices[0])
            self.assertEqual(len(image.symbol_table.table), 23)


class TBDTestCase(unittest.TestCase):
    def test_tapi_dump(self):
        with open(scriptdir + '/bins/PreferencesUI.dyldex', 'rb') as file:
            machofile = MachOFile(file)
            image = Dyld.load(machofile.slices[0])
            tbd_dict = TBDGenerator(image).dict
            print(TapiYAMLWriter.write_out(tbd_dict))


class FileLoadTestCase(unittest.TestCase):
    def test_fat_load(self):
        with open(scriptdir + '/bins/testbin1_fat', 'rb') as file:
            macho_file = MachOFile(file)
            self.assertEqual(macho_file.type, MachOFileType.FAT)
            self.assertEqual(len(macho_file.slices), 2)

    def test_thin_load(self):
        with open(scriptdir + '/bins/testbin1', 'rb') as file:
            macho_file = MachOFile(file)
            self.assertEqual(macho_file.type, MachOFileType.THIN)


class FrameworksTestCase(unittest.TestCase):

    def test_coherence(self):
        with open(scriptdir + '/bins/Coherence.dyldex', 'rb') as fd:
            HeaderGenerator(ObjCImage(Dyld.load(MachOFile(fd).slices[0])))

    def test_safari_shared(self):
        with open(scriptdir + '/bins/SafariShared.dyldex', 'rb') as fd:
            HeaderGenerator(ObjCImage(Dyld.load(MachOFile(fd).slices[0])))

    def test_external_accesory(self):
        with open(scriptdir + '/bins/ExternalAccessory.dyldex', 'rb') as fd:
            HeaderGenerator(ObjCImage(Dyld.load(MachOFile(fd).slices[0])))

    def test_soundanalysis(self):
        with open(scriptdir + '/bins/SoundAnalysis', 'rb') as fd:
            HeaderGenerator(ObjCImage(Dyld.load(MachOFile(fd).slices[0])))

    def test_ktrace(self):
        with open(scriptdir + '/bins/ktrace.dyldex', 'rb') as fd:
            ObjCImage(Dyld.load(MachOFile(fd).slices[0]))

    def test_pfui(self):
        with open(scriptdir + '/bins/PreferencesUI', 'rb') as fd:
            print(Dyld.load(MachOFile(fd).slices[0]).macho_header.flags)

    def test_pfui2(self):
        with open(scriptdir + '/bins/PreferencesUI.dyldex', 'rb') as fd:
            ObjCImage(Dyld.load(MachOFile(fd).slices[0]))

    def test_search(self):
        with open(scriptdir + '/bins/Search', 'rb') as fd:
            ObjCImage(Dyld.load(MachOFile(fd).slices[0]))

    def test_sbh(self):
        with open(scriptdir + '/bins/SpringBoardHome', 'rb') as fd:
            objc_lib = ObjCImage(Dyld.load(MachOFile(fd).slices[0]))
            self.assertGreater(len(objc_lib.classlist), 1)
            self.assertGreater(len(objc_lib.catlist), 1)
            self.assertGreater(len(objc_lib.classlist[0].methods), 4)


if __name__ == '__main__':
    unittest.main()
