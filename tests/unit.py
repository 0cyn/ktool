#
#  ktool | tests
#  unit.py
#
#
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2022.
#
import math
import os
import sys
import unittest
from io import BytesIO
import random

from ktool.loader import MachOImageHeader

import ktool
from ktool.headers import *
from ktool.macho import *
from ktool.objc import *
from ktool.util import *
from ktool.image import *

# We need to be in the right directory so we can find the bins
scriptdir = os.path.dirname(os.path.realpath(__file__))

sys.path.extend([f'{scriptdir}/../src'])
log.LOG_LEVEL = LogLevel.WARN

error_buffer = ""


def diff_byte_array_set_assertion(old: bytearray, new: bytearray):
    if old != new:
        diff = "        Old       New\n"
        for index in range(0, len(old), 4):
            old_bytes = old[index:index+4]
            new_bytes = new[index:index+4]
            set_is_diff = False
            for sub_index, byte in enumerate(old_bytes):
                if byte != new_bytes[sub_index]:
                    set_is_diff = True
            if set_is_diff:
                diff += hex(index).ljust(8)
                diff += old_bytes.hex() + '  '
                diff += new_bytes.hex() + '  '
                diff += "\n"
        print(diff, file=sys.stderr)
        raise AssertionError


def error_remap(msg):
    global error_buffer
    error_buffer += msg + '\n'


def enable_error_capture():
    log.LOG_ERR = error_remap
    global error_buffer
    error_buffer = ""


def assert_error_printed(msg):
    assert msg in error_buffer


def disable_error_capture():
    log.LOG_ERR = print_err


#  ---------
#  To make testing easier, we use "scratch files"; base mach-os (testbin1, testbin1.fat) that we modify and reset
#      in reliable ways. The underlying file should not matter whatsoever, we just need *any* mach-o.
#  Tests should be written in a way entirely independent of the underlying file, manually writing the values we're going to test.
#  ---------

class ScratchFile:
    def __init__(self, fp):
        self.scratch = BytesIO()
        self.backup = BytesIO()
        self.fp = fp
        data = fp.read()
        self.fp.close()
        self.backup.write(data)
        self.backup.seek(0)
        self.scratch.write(data)
        self.scratch.seek(0)

    def get(self):
        copy = BytesIO()
        copy.write(self.scratch.read(self.scratch.getbuffer().nbytes))
        copy.seek(0)
        return copy

    def read(self, location, count):
        self.scratch.seek(location)
        data = self.scratch.read(count)
        self.scratch.seek(0)
        return data

    def write(self, location, data):
        if isinstance(data, int):
            data = data.to_bytes(4, 'big')
        self.scratch.seek(location)
        self.scratch.write(data)
        self.scratch.seek(0)

    def reset(self):
        self.scratch = BytesIO()
        self.scratch.write(self.backup.read())
        self.backup.seek(0)
        self.scratch.seek(0)


class MachOLoaderTestCase(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.thin = ScratchFile(open(scriptdir + '/bins/testbin1', 'rb'))
        self.fat = ScratchFile(open(scriptdir + '/bins/testbin1.fat', 'rb'))

    def test_thin_type(self):
        self.thin.reset()
        macho = ktool.load_macho_file(self.thin.get())
        assert macho.type == MachOFileType.THIN

    def test_fat_type(self):
        self.fat.reset()
        macho = ktool.load_macho_file(self.fat.get())
        assert macho.type == MachOFileType.FAT

    def test_bad_magic(self):
        self.thin.reset()
        self.thin.write(0, 0xDEADBEEF)

        enable_error_capture()
        with self.assertRaises(UnsupportedFiletypeException) as context:
            ktool.load_macho_file(self.thin.get())
        disable_error_capture()

    def test_bad_fat_offset(self):
        self.fat.reset()
        macho = ktool.load_macho_file(self.fat.get())

        # corrupt the second offset
        header: fat_header = macho._load_struct(0, fat_header, "big")
        for off in range(1, header.nfat_archs):
            offset = fat_header.SIZE + (off * fat_arch.SIZE)
            arch_struct: fat_arch = macho._load_struct(offset, fat_arch, "big")
            arch_struct.offset = 0xDEADBEEF
            self.fat.write(arch_struct.off, arch_struct.raw)

        enable_error_capture()

        macho = ktool.load_macho_file(self.fat.get())
        # Verify we correctly show the error
        self.assertIn("has bad magic 0x0", error_buffer)

        disable_error_capture()

        # Verify the slice wasn't loaded
        self.assertLess(len(macho.slices), 2)

    def test_slice_count(self):
        self.fat.reset()

        macho = ktool.load_macho_file(self.fat.get())
        header: fat_header = macho._load_struct(0, fat_header, "big")
        slice_count = header.nfat_archs
        self.assertEqual(slice_count, len(macho.slices))


class VMTestCase(unittest.TestCase):
    def test_good_16k_page_vm_map(self):
        vm = VM(0x4000)

        vm_base = random.randint(100, 200) * 0x4000
        file_base = random.randint(1, 100) * 0x4000
        diff = vm_base - file_base
        size = 0x4000 * 2

        vm.map_pages(file_base, vm_base, size)

        for address in range(vm_base, vm_base + size, 4):
            correct_address = address - diff
            translated_address = vm.translate(address)
            self.assertEqual(correct_address, translated_address)

    def test_bad_16k_page_vm_map(self):
        vm = VM(0x4000)

        vm_base = random.randint(100, 200) * 0x4000
        file_base = random.randint(1, 100) * 0x4000
        vm_base -= 1

        with self.assertRaises(MachOAlignmentError) as context:
            vm.map_pages(vm_base, file_base, 0x4000)

        vm_base += 1
        file_base -= 1

        with self.assertRaises(MachOAlignmentError) as context:
            vm.map_pages(vm_base, file_base, 0x4000)

        file_base += 1

        with self.assertRaises(MachOAlignmentError) as context:
            vm.map_pages(vm_base, file_base, 0x3999)


class SliceTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.thin = ScratchFile(open(scriptdir + '/bins/testbin1', 'rb'))
        self.fat = ScratchFile(open(scriptdir + '/bins/testbin1.fat', 'rb'))

    def test_patch(self):
        self.thin.reset()
        self.fat.reset()

        macho = ktool.load_macho_file(self.thin.get())
        macho_slice = macho.slices[0]
        macho_slice.patch(0x0, b'\xDE\xAD\xBE\xEF')
        self.thin.write(0x0, 0xDEADBEEF)

        self.assertEqual(macho_slice.full_bytes_for_slice(), self.thin.get().read())
        self.thin.reset()
        self.assertNotEqual(macho_slice.full_bytes_for_slice(), self.thin.get().read())

        macho = ktool.load_macho_file(self.fat.get())
        macho_slice = macho.slices[1]
        macho_slice.patch(0x0, b'\xDE\xAD\xBE\xEF')
        self.fat.write(macho_slice.offset, 0xDEADBEEF)

        self.assertEqual(macho_slice.full_bytes_for_slice(), bytes(bytearray(self.fat.get().read())[macho_slice.offset:macho_slice.offset+macho_slice.size]))

    def test_find(self):
        self.thin.reset()
        self.fat.reset()

        macho = ktool.load_macho_file(self.thin.get())
        macho_slice = macho.slices[0]

        size = macho_slice.size

        loadsize = macho_slice.get_int_at(20, 4) + 32
        random_location = random.randint(loadsize, size)

        needle = b'\xDE\xAD\xBE\xEF\xDE\xAD\xBE\xEF\xDE\xAD\xBE\xEF'

        self.thin.write(random_location, needle)

        macho = ktool.load_macho_file(self.thin.get())
        macho_slice = macho.slices[0]

        location = macho_slice.find(needle)

        self.assertEqual(location, random_location)

        macho = ktool.load_macho_file(self.fat.get())
        macho_slice = macho.slices[1]
        slice_base = macho_slice.offset
        size = macho_slice.size

        loadsize = macho_slice.get_int_at(20, 4) + 32
        random_location = random.randint(loadsize, size)

        self.fat.write(slice_base + random_location, needle)

        macho = ktool.load_macho_file(self.fat.get())
        macho_slice = macho.slices[1]

        location = macho_slice.find(needle)

        self.assertEqual(location, random_location)

    def test_get_bytes(self):
        self.thin.reset()
        self.fat.reset()

        macho = ktool.load_macho_file(self.thin.get())
        macho_slice = macho.slices[0]
        size = macho_slice.size
        loadsize = macho_slice.get_int_at(20, 4) + 32
        random_location = random.randint(loadsize, size)

        write = b'\xDE\xAD\xBE\xEF'

        self.thin.write(random_location, write)

        macho = ktool.load_macho_file(self.thin.get())
        macho_slice = macho.slices[0]

        readout = macho_slice.get_bytes_at(random_location, 4)
        self.assertEqual(write, readout)

    def test_get_str(self):
        self.thin.reset()
        self.fat.reset()

        macho = ktool.load_macho_file(self.thin.get())
        macho_slice = macho.slices[0]
        size = macho_slice.size
        loadsize = macho_slice.get_int_at(20, 4) + 32
        random_location = random.randint(loadsize, size)

        write = b'Decode a printable string.'

        self.thin.write(random_location, write)

        macho = ktool.load_macho_file(self.thin.get())
        macho_slice = macho.slices[0]

        readout = macho_slice.get_str_at(random_location, len(write))
        self.assertEqual(write.decode('utf-8'), readout)

    def test_get_cstr(self):
        self.thin.reset()
        self.fat.reset()

        macho = ktool.load_macho_file(self.thin.get())
        macho_slice = macho.slices[0]
        size = macho_slice.size
        loadsize = macho_slice.get_int_at(20, 4) + 32
        random_location = random.randint(loadsize, size)

        write = b'Decode a printable string.\x00'

        self.thin.write(random_location, write)

        macho = ktool.load_macho_file(self.thin.get())
        macho_slice = macho.slices[0]

        readout = macho_slice.get_cstr_at(random_location)
        self.assertEqual(write[:-1].decode('utf-8'), readout)

    def test_decode_uleb128(self):
        self.thin.reset()

        value = 624485
        encoded = b'\xe5\x8e&'

        macho = ktool.load_macho_file(self.thin.get())
        macho_slice = macho.slices[0]
        size = macho_slice.size
        loadsize = macho_slice.get_int_at(20, 4) + 32
        random_location = random.randint(loadsize, size)

        self.thin.write(random_location, encoded)

        macho = ktool.load_macho_file(self.thin.get())
        macho_slice = macho.slices[0]
        decoded_value, _ = macho_slice.decode_uleb128(random_location)

        self.assertEqual(value, decoded_value)


class ImageHeaderTestCase(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.thin = ScratchFile(open(scriptdir + '/bins/testbin1', 'rb'))

    def test_constructable(self):
        self.thin.reset()

        # Test whether deserialized metadata pulled from a real image can be re-serialized properly

        image = ktool.load_image(self.thin.get())
        image_header = image.macho_header

        old_image_header_raw = image.macho_header.raw_bytes()

        flags = image_header.flags
        filetype = image_header.filetype
        cpu_type = image.slice.type
        cpu_subtype = image.slice.subtype

        load_command_items = []

        for command in image.macho_header.load_commands:
            if isinstance(command, segment_command) or isinstance(command, segment_command_64):
                load_command_items.append(Segment(image, command))
            elif isinstance(command, dylib_command):
                suffix = image.get_cstr_at(command.off + command.__class__.SIZE)
                encoded = suffix.encode('utf-8') + b'\x00'
                while (len(encoded) + command.__class__.SIZE) % 8 != 0:
                    encoded += b'\x00'
                load_command_items.append(command)
                load_command_items.append(encoded)
            elif command.__class__ in [dylinker_command, build_version_command]:
                load_command_items.append(command)
                actual_size = command.cmdsize
                dat = image.get_bytes_at(command.off + command.SIZE, actual_size - command.SIZE)
                load_command_items.append(dat)
            else:
                load_command_items.append(command)

        new_image_header = MachOImageHeader.from_values(image.macho_header.is64, cpu_type, cpu_subtype, filetype, flags, load_command_items)

        self.thin.write(0, new_image_header.raw_bytes())

        new_image_header_raw = new_image_header.raw_bytes()

        diff_byte_array_set_assertion(bytearray(old_image_header_raw), bytearray(new_image_header_raw))

        ktool.load_image(self.thin.get())

    def test_bad_load_command(self):
        self.thin.reset()

        image = ktool.load_image(self.thin.get())
        image_header = image.macho_header

        flags = image_header.flags
        filetype = image_header.filetype
        cpu_type = image.slice.type
        cpu_subtype = image.slice.subtype

        load_command_items = []

        for command in image.macho_header.load_commands:
            if isinstance(command, segment_command) or isinstance(command, segment_command_64):
                load_command_items.append(Segment(image, command))
            elif isinstance(command, dylib_command):
                suffix = image.get_cstr_at(command.off + command.__class__.SIZE)
                encoded = suffix.encode('utf-8') + b'\x00'
                while (len(encoded) + command.__class__.SIZE) % 8 != 0:
                    encoded += b'\x00'
                load_command_items.append(command)
                load_command_items.append(encoded)
            elif command.__class__ == dyld_info_command:
                command.cmd = 0x99
                load_command_items.append(command)
            elif command.__class__ in [dylinker_command, build_version_command]:
                load_command_items.append(command)
                actual_size = command.cmdsize
                dat = image.get_bytes_at(command.off + command.SIZE, actual_size - command.SIZE)
                load_command_items.append(dat)
            else:
                load_command_items.append(command)

        new_image_header = MachOImageHeader.from_values(image.macho_header.is64, cpu_type, cpu_subtype, filetype, flags, load_command_items)

        self.thin.write(0, new_image_header.raw_bytes())

        enable_error_capture()
        ktool.load_image(self.thin.get())
        disable_error_capture()

        assert_error_printed("Bad Load Command ")
        assert_error_printed("0x99 - 0x30")


class DyldTestCase(unittest.TestCase):
    """
    This operates primarily on the "Image" class, but Image doesn't handle loading its values in, Dyld does
    we will test the cyclomatically complex portions of the Image class elsewhere.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.thin = ScratchFile(open(scriptdir + '/bins/testbin1', 'rb'))
        self.thin_lib = ScratchFile(open(scriptdir + '/bins/testlib1.dylib', 'rb'))

    def test_install_name(self):
        self.thin_lib.reset()

        image = ktool.load_image(self.thin_lib.get())

        self.assertEqual("bins/testlib1.dylib", image.install_name)

    def test_linked_images(self):
        self.thin_lib.reset()

        image = ktool.load_image(self.thin_lib.get())

        self.assertEqual(len(image.linked_images), 3)
        self.assertEqual(image.linked_images[0].install_name,
                         "/System/Library/Frameworks/Foundation.framework/Versions/C/Foundation")
        self.assertEqual(image.linked_images[1].install_name, "/usr/lib/libSystem.B.dylib")
        self.assertEqual(image.linked_images[2].install_name, "/usr/lib/libobjc.A.dylib")


if __name__ == '__main__':
    ignore.OBJC_ERRORS = False

    unittest.main()
