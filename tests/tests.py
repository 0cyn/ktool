#
# If you're here looking for usage examples, look elsewhere (bin/ktool is better)
# these test cases are just to make sure things work at a bare minimum, no good code to be found here,
#   and there's a solid chance i'm doing something improperly out of sheer laziness
#

import os
import sys
import unittest

import ktool
from ktool.headers import HeaderGenerator
from ktool.macho import MachOFile, MachOFileType
from ktool.objc import ObjCImage
from ktool.util import log, LogLevel, ignore


# We need to be in the right directory so we can find the bins
scriptdir = os.path.dirname(os.path.realpath(__file__))

sys.path.extend([f'{scriptdir}/../src'])
log.LOG_LEVEL = LogLevel.WARN


class SymTabTestCase(unittest.TestCase):
    def test_bin(self):
        with open(scriptdir + '/bins/testbin1', 'rb') as file:
            image = ktool.load_image(file)

            self.assertEqual(len(image.symbol_table.table), 23)


class TBDTestCase(unittest.TestCase):
    def test_tapi_dump(self):
        with open(scriptdir + '/bins/PreferencesUI.dyldex', 'rb') as file:
            image = ktool.load_image(file)
            print(ktool.generate_text_based_stub(image, True))


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
            HeaderGenerator(ObjCImage(ktool.load_image(fd)))
            ktool.generate_headers(ktool.load_objc_metadata(ktool.load_image(fd)))

    def test_no_mmaped_support(self):
        with open(scriptdir + '/bins/Coherence.dyldex', 'rb') as fp:
            macho_file = ktool.load_macho_file(fp, False)
            ktool.load_objc_metadata(ktool.load_image(macho_file))

    def test_safari_shared(self):
        with open(scriptdir + '/bins/SafariShared.dyldex', 'rb') as fd:
            ktool.generate_headers(ktool.load_objc_metadata(ktool.load_image(fd)))

    def test_external_accesory(self):
        with open(scriptdir + '/bins/ExternalAccessory.dyldex', 'rb') as fd:
            ktool.generate_headers(ktool.load_objc_metadata(ktool.load_image(fd)))

    def test_soundanalysis(self):
        with open(scriptdir + '/bins/SoundAnalysis', 'rb') as fd:
            ktool.generate_headers(ktool.load_objc_metadata(ktool.load_image(fd)))

    def test_ktrace(self):
        with open(scriptdir + '/bins/ktrace.dyldex', 'rb') as fd:
            ktool.load_objc_metadata(ktool.load_image(fd))

    def test_pfui(self):
        with open(scriptdir + '/bins/PreferencesUI', 'rb') as fd:
            print(ktool.load_image(fd).macho_header.flags)

    def test_search(self):
        with open(scriptdir + '/bins/Search', 'rb') as fd:
            ktool.load_objc_metadata(ktool.load_image(fd))

    def test_sbh(self):
        with open(scriptdir + '/bins/SpringBoardHome', 'rb') as fd:
            objc_lib = ktool.load_objc_metadata(ktool.load_image(fd))
            self.assertGreater(len(objc_lib.classlist), 1)
            self.assertGreater(len(objc_lib.catlist), 1)
            self.assertGreater(len(objc_lib.classlist[0].methods), 4)


if __name__ == '__main__':
    ignore.OBJC_ERRORS = False

    unittest.main()