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
#  Copyright (c) 0cyn 2022.
#
import unittest

import json
import random

import ktool
from ktool_macho.fixups import ChainedPointerArm64E
from ktool.macho import *
from ktool.util import *
from ktool.image import *
from lib0cyn.log import log, LogLevel

# We need to be in the right directory so we can find the bins
scriptdir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.abspath(f'{scriptdir}/../src'))

log.LOG_LEVEL = LogLevel.WARN

error_buffer = ""


def diff_byte_array_set_assertion(old: bytearray, new: bytearray):
    if old != new:
        diff = "        Old       New\n"
        for index in range(0, len(old), 4):
            old_bytes = old[index:index + 4]
            new_bytes = new[index:index + 4]
            set_is_diff = False
            for sub_index, byte in enumerate(old_bytes):
                try:
                    if byte != new_bytes[sub_index]:
                        set_is_diff = True
                except IndexError:
                    set_is_diff = True
            if set_is_diff:
                diff += hex(index).ljust(8)
                diff += old_bytes.hex() + '  '
                diff += new_bytes.hex() + '  '
                diff += "\n"
        print(diff)
        raise AssertionError


def error_remap(msg):
    global error_buffer
    error_buffer += msg + '\n'


def enable_error_capture():
    log.LOG_ERR = error_remap
    global error_buffer
    error_buffer = ""


def assert_error_printed(msg):
    assert msg in error_buffer, "Error buffer didn't have '{}', has '{}'".format(msg, error_buffer)


def disable_error_capture():
    log.LOG_ERR = print_err


# ---------
# To make testing easier, we use "scratch files"; base mach-os (testbin1, testbin1.fat) that we modify and
# reset in reliable ways. The underlying file should not matter whatsoever, we just need *any* mach-o. Tests should
# be written in a way entirely independent of the underlying file, manually writing the values we're going to test.
# ---------

class ScratchFile:
    def __init__(self, fp):
        self.scratch = BytesIO()
        self.backup = BytesIO()
        self.fp = fp
        data = fp.read()
        if hasattr(self.fp, 'close'):
            self.fp.close()
        self.backup.write(data)
        self.backup.seek(0)
        self.scratch.write(data)
        self.scratch.seek(0)

    def copy(self):
        fp = self.get()
        new = ScratchFile(fp)
        new.scratch = BytesIO()
        new.scratch.write(self.scratch.read())
        self.scratch.seek(0)
        return new

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


class sunion_test(Struct):
    _FIELDNAMES = ['field']
    _SIZES = [ChainedPointerArm64E]
    SIZE = uint64_t

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class StructTestCase(unittest.TestCase):
    def test_equality_check(self):
        s1 = Struct.create_with_values(linkedit_data_command, [0x34 | LC_REQ_DYLD, 0x10, 0xc000, 0xd0], "little")
        s2 = Struct.create_with_values(linkedit_data_command, [0x34 | LC_REQ_DYLD, 0x10, 0xc000, 0xd0], "little")
        s3 = Struct.create_with_values(linkedit_data_command, [0x34 | LC_REQ_DYLD, 0x10, 0xc000, 0xe0], "little")
        assert s1 == s2
        assert s1 != s3

    def test_union(self):
        #                       |16     |24     |32                             |64
        tval = 0b0101101010101010111111110010010000000000000000000000000000000011
        tval = int('{:08b}'.format(tval)[::-1], 2)
        tval_raw = tval.to_bytes(8, "little")
        stc = Struct.create_with_bytes(sunion_test, tval_raw)
        # print(bin(stc.field.dyld_chained_ptr_arm64e_auth_rebase.target))
        assert stc.field.dyld_chained_ptr_arm64e_auth_rebase.target == int(
            '{:08b}'.format(0b01011010101010101111111100100100)[::-1], 2)


class BackingFileTestCase(unittest.TestCase):
    def test_with_mmaped_and_actual_file_pointer(self):
        # Rest of our tests use this class but only with our scratch files (which dont invoke binaryIO or mmaped io)
        fp = open(scriptdir + '/bins/testbin1', 'rb')
        bf = BackingFile(fp, use_mmaped_io=True)
        self.assertNotEqual(bf.size, 0)
        bf.write(0, b'\xde\xad\xbe\xef')
        self.assertEqual(bf.read_bytes(0, 4), b'\xde\xad\xbe\xef')
        fp.close()


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

        self.assertEqual(macho_slice.full_bytes_for_slice(), bytes(
            bytearray(self.fat.get().read())[macho_slice.offset:macho_slice.offset + macho_slice.size]))

    def test_find(self):
        self.thin.reset()
        self.fat.reset()

        macho = ktool.load_macho_file(self.thin.get())
        macho_slice = macho.slices[0]

        size = macho_slice.size

        loadsize = macho_slice.read_uint(20, 4) + 32
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

        loadsize = macho_slice.read_uint(20, 4) + 32
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
        loadsize = macho_slice.read_uint(20, 4) + 32

        random_location = random.randint(loadsize, size)

        write = b'\xDE\xAD\xBE\xEF'

        self.thin.write(random_location, write)

        macho = ktool.load_macho_file(self.thin.get())
        macho_slice = macho.slices[0]

        readout = macho_slice.read_bytearray(random_location, 4)
        self.assertEqual(write, readout)

    def test_get_str(self):
        self.thin.reset()
        self.fat.reset()

        macho = ktool.load_macho_file(self.thin.get())
        macho_slice = macho.slices[0]
        size = macho_slice.size
        loadsize = macho_slice.read_uint(20, 4) + 32
        random_location = random.randint(loadsize, size)

        write = b'Decode a printable string.'

        self.thin.write(random_location, write)

        macho = ktool.load_macho_file(self.thin.get())
        macho_slice = macho.slices[0]

        readout = macho_slice.read_fixed_len_str(random_location, len(write))
        self.assertEqual(write.decode('utf-8'), readout)

    def test_get_cstr(self):
        self.thin.reset()
        self.fat.reset()

        macho = ktool.load_macho_file(self.thin.get())
        macho_slice = macho.slices[0]
        size = macho_slice.size
        loadsize = macho_slice.read_uint(20, 4) + 32
        random_location = random.randint(loadsize, size)

        write = b'Decode a printable string.\x00'

        self.thin.write(random_location, write)

        macho = ktool.load_macho_file(self.thin.get())
        macho_slice = macho.slices[0]

        readout = macho_slice.read_cstr(random_location)
        self.assertEqual(write[:-1].decode('utf-8'), readout)

    def test_decode_uleb128(self):
        self.thin.reset()

        value = 624485
        encoded = b'\xe5\x8e&'

        macho = ktool.load_macho_file(self.thin.get())
        macho_slice = macho.slices[0]
        size = macho_slice.size
        loadsize = macho_slice.read_uint(20, 4) + 32
        random_location = random.randint(loadsize, size)

        self.thin.write(random_location, encoded)

        macho = ktool.load_macho_file(self.thin.get())
        macho_slice = macho.slices[0]
        decoded_value, _ = macho_slice.read_uleb128(random_location)

        self.assertEqual(value, decoded_value)


class ImageHeaderTestCase(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.thin = ScratchFile(open(scriptdir + '/bins/testbin1', 'rb'))
        self.thin_lib = ScratchFile(open(scriptdir + '/bins/testlib1.dylib', 'rb'))

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
                suffix = image.read_cstr(command.off + command.__class__.size())
                encoded = suffix.encode('utf-8') + b'\x00'
                while (len(encoded) + command.__class__.size()) % 8 != 0:
                    encoded += b'\x00'
                load_command_items.append(command)
                load_command_items.append(encoded)
            elif command.__class__ in [dylinker_command, build_version_command]:
                load_command_items.append(command)
                actual_size = command.cmdsize
                dat = image.read_bytearray(command.off + command.size(), actual_size - command.size())
                load_command_items.append(dat)
            else:
                load_command_items.append(command)

        new_image_header = MachOImageHeader.from_values(image.macho_header.is64, cpu_type, cpu_subtype, filetype, flags,
                                                        load_command_items)

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
                suffix = image.read_cstr(command.off + command.__class__.size())
                encoded = suffix.encode('utf-8') + b'\x00'
                while (len(encoded) + command.__class__.size()) % 8 != 0:
                    encoded += b'\x00'
                load_command_items.append(command)
                load_command_items.append(encoded)
            elif command.__class__ == symtab_command:
                command.cmd = 0x99
                load_command_items.append(command)
            elif command.__class__ in [dylinker_command, build_version_command]:
                load_command_items.append(command)
                actual_size = command.cmdsize
                dat = image.read_bytearray(command.off + command.size(), actual_size - command.size())
                load_command_items.append(dat)
            else:
                load_command_items.append(command)

        new_image_header = MachOImageHeader.from_values(image.macho_header.is64, cpu_type, cpu_subtype, filetype, flags,
                                                        load_command_items)

        self.thin.write(0, new_image_header.raw_bytes())

        enable_error_capture()
        ktool.load_image(self.thin.get())
        disable_error_capture()

        assert_error_printed("Bad Load Command ")
        assert_error_printed("0x99 -")

    def test_readint(self):
        inp = 0xffffffac
        output = -0x54

        assert uint_to_int(inp, 32) == output

    def test_insert_cmd(self):

        self.thin.reset()

        image = ktool.load_image(self.thin.get())
        image_header = image.macho_header

        dylib_item = Struct.create_with_values(dylib, [0x18, 0x2, 0x010000, 0x010000])
        dylib_cmd = Struct.create_with_values(dylib_command, [LOAD_COMMAND.LOAD_DYLIB.value, 0, dylib_item.raw])
        new_header = image.macho_header.insert_load_command(dylib_cmd, -1, suffix="/unit/test")

        assert len(image_header.load_commands) + 1 == len(new_header.load_commands)
        assert b'/unit/test' in new_header.raw
        assert image_header.raw != new_header.raw

        self.thin.write(0, new_header.raw)

        new_image = ktool.load_image(self.thin.get())
        assert new_image.linked_images[-1].install_name == '/unit/test'

    def test_remove_cmd(self):

        self.thin.reset()

        image = ktool.load_image(self.thin.get())
        image_header = image.macho_header

        new_header = image.macho_header.remove_load_command(5)
        assert (len(image_header.load_commands) - 1 == len(new_header.load_commands))
        self.thin.write(0, new_header.raw_bytes())

        ktool.load_image(self.thin.get())

    def test_replace_load_command(self):
        self.thin_lib.reset()

        image = ktool.load_image(self.thin_lib.get())
        image_header = image.macho_header
        old_commands = [*image_header.load_commands]

        dylib_item = Struct.create_with_values(dylib, [0x18, 0x1, 0x000000, 0x000000])
        dylib_cmd = Struct.create_with_values(dylib_command, [LOAD_COMMAND.ID_DYLIB.value, 0, dylib_item])
        new_header = image.macho_header.replace_load_command(dylib_cmd, 4, suffix="/unit/test/iname")

        self.thin_lib.write(0, new_header.raw)

        new_image = ktool.load_image(self.thin_lib.get())
        assert new_image.install_name == '/unit/test/iname'

        for i, cmd in enumerate(new_header.load_commands):
            if not cmd == old_commands[i]:
                log.error(f'{str(cmd)} != {str(old_commands[i])}')
                raise AssertionError


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
            offset = fat_header.size() + (off * fat_arch.size())
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


class SegmentLCTestCase(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.thin = ScratchFile(open(scriptdir + '/bins/testbin1', 'rb'))

    def test_constructable(self):
        self.thin.reset()

        image = ktool.load_image(self.thin.get())
        image_header = image.macho_header

        old_command: segment_command_64 = image_header.load_commands[1]
        old_dat = image.read_bytearray(old_command.off, old_command.cmdsize)

        text = image.segments['__TEXT']
        cmd: segment_command = text.cmd
        text_sections = []
        for s in text.sections.values():
            text_sections.append(s)
        lc = SegmentLoadCommand.from_values(image_header.is64, '__TEXT', text.vm_address, text.size, text.file_address,
                                            text.file_size,
                                            cmd.maxprot, cmd.initprot, cmd.flags, text_sections)
        new_dat = lc.raw_bytes()

        diff_byte_array_set_assertion(bytearray(old_dat), bytearray(new_dat))


class VMTestCase(unittest.TestCase):
    def test_good_16k_page_vm_map(self):
        vm = VM(0x4000)

        vm_base = random.randint(100, 200) * 0x4000
        file_base = random.randint(1, 100) * 0x4000
        diff = vm_base - file_base
        size = 0x4000 * 2

        k_seg_start = 0xFFFFFFFFFFFF0000
        vm.map_pages(0x4000 * 300, k_seg_start, 0x4000)

        vm.map_pages(file_base, vm_base, size)

        for address in range(vm_base, vm_base + size, 4):
            correct_address = address - diff
            translated_address = vm.translate(address)
            self.assertEqual(correct_address, translated_address)
            self.assertEqual(vm.de_translate(translated_address), address)

        vm.detag_64 = True
        translated_address = vm.translate(vm_base + 0x1234000000000)
        self.assertEqual(translated_address, vm_base - diff)
        vm.detag_64 = False

        vm.detag_kern_64 = True
        tagged_k64_addr = 0x1234FFFFFFFF0008
        self.assertEqual(vm.translate(tagged_k64_addr), 0x4000 * 300 + 0x8)
        vm.detag_kern_64 = False

        self.assertFalse(vm.vm_check(-4000))
        self.assertTrue(vm.vm_check(vm_base))

        with self.assertRaises(VMAddressingError):
            vm.de_translate(-4)

    def test_fallback_vm(self):

        vm: VM = VM(0x4000)

        vm_base = random.randint(100, 200) * 0x4000
        file_base = random.randint(1, 100) * 0x4000
        diff = vm_base - file_base
        size = 0x4000 * 2

        vm.map_pages(file_base, vm_base, size)
        k_seg_start = 0xFFFFFFFFFFFF0000
        vm.map_pages(0x4000 * 300, k_seg_start, 0x4000)
        vm: MisalignedVM = vm.fallback

        for address in range(vm_base, vm_base + size, 4):
            correct_address = address - diff
            translated_address = vm.translate(address)
            self.assertEqual(correct_address, translated_address)
            self.assertEqual(vm.de_translate(translated_address), address)

        vm.detag_64 = True
        translated_address = vm.translate(vm_base + 0x1234000000000)
        self.assertEqual(translated_address, vm_base - diff)
        vm.detag_64 = False

        vm.detag_kern_64 = True
        tagged_k64_addr = 0x1234FFFFFFFF0008
        self.assertEqual(vm.translate(tagged_k64_addr), 0x4000 * 300 + 0x8)
        vm.detag_kern_64 = False

        self.assertFalse(vm.vm_check(-4000))
        self.assertTrue(vm.vm_check(vm_base))

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


class ImageTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.thin = ScratchFile(open(scriptdir + '/bins/testbin1', 'rb'))

    def test_serialization(self):
        self.thin.reset()

        img = ktool.load_image(self.thin.get())
        img.rpath = "asdf"
        img.install_name = "asdf"
        img_dict = img.serialize()
        out = json.dumps(img_dict)
        assert out
        re_in = json.loads(out)
        assert re_in

    def test_vm_realignment(self):
        self.thin.reset()

        image = ktool.load_image(self.thin.get())

        macho_header: mach_header_64 = image.macho_header.dyld_header

        macho_header.cpu_type = CPUType.ARM64.value
        macho_header.cpu_subtype = CPUSubTypeARM64.ARM64E.value

        raw = macho_header.raw

        self.thin.write(0, raw)

        image = ktool.load_image(self.thin.get())
        self.assertTrue(image.vm.detag_64)

        self.thin.reset()
        image = ktool.load_image(self.thin.get())

        dat = self.thin.read(0x80, 8)
        dat = int.from_bytes(dat, "little")
        dat += 0x1000
        self.thin.write(0x80, dat.to_bytes(8, "little"))
        dat = self.thin.read(0x88, 8)
        dat = int.from_bytes(dat, "little")
        dat -= 0x1000
        self.thin.write(0x88, dat.to_bytes(8, "little"))
        image = ktool.load_image(self.thin.get())

        self.thin.reset()
        image = ktool.load_image(self.thin.get())
        dat = self.thin.read(0x80, 8)
        dat = int.from_bytes(dat, "little")
        dat += 0x1004
        self.thin.write(0x80, dat.to_bytes(8, "little"))
        dat = self.thin.read(0x88, 8)
        dat = int.from_bytes(dat, "little")
        dat -= 0x1004
        self.thin.write(0x88, dat.to_bytes(8, "little"))
        image = ktool.load_image(self.thin.get())

    def test_rw_prims(self):
        self.thin.reset()

        str_and_cstr_test_string = 'AAAA AAAA'
        str_size = len(str_and_cstr_test_string)
        str_test_location = 0x1000
        cstr_test_location = 0x2000
        self.thin.write(str_test_location, str_and_cstr_test_string.encode("utf-8"))
        self.thin.write(cstr_test_location, str_and_cstr_test_string.encode("utf-8") + b'\0')

        image = ktool.load_image(self.thin.get())
        # we already know the slice to be functional by this point
        macho_slice = image.slice

        vm_base = image.vm.de_translate(0)

        self.assertTrue(image.vm_check(vm_base))
        self.assertEqual(image.vm.translate(vm_base), 0)

        self.assertEqual(macho_slice.read_uint(0, 4), image.read_uint(0, 4))
        self.assertEqual(macho_slice.read_uint(0, 4), image.read_uint(vm_base, 4, vm=True))

        self.assertEqual(macho_slice.read_bytearray(0, 4), image.read_bytearray(0, 4))
        self.assertEqual(macho_slice.read_bytearray(0, 4), image.read_bytearray(vm_base, 4, vm=True))

        self.assertEqual(macho_slice.read_struct(0, mach_header_64, "little"),
                         image.read_struct(0, mach_header_64, endian="little", vm=False, force_reload=True))
        self.assertEqual(macho_slice.read_struct(0, mach_header_64, "little"),
                         image.read_struct(vm_base, mach_header_64, vm=True, endian="little", force_reload=True))

        self.assertEqual(str_and_cstr_test_string, image.read_fixed_len_str(str_test_location, str_size))
        self.assertEqual(str_and_cstr_test_string,
                         image.read_fixed_len_str(image.vm.de_translate(str_test_location), str_size, vm=True))

        self.assertEqual(str_and_cstr_test_string, image.read_cstr(cstr_test_location))
        self.assertEqual(str_and_cstr_test_string,
                         image.read_cstr(image.vm.de_translate(cstr_test_location), vm=True))


class CodesignTestClass(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.signed = ScratchFile(open(scriptdir + '/bins/testbin1.signed', 'rb'))

    def test_codesigning(self):
        im = ktool.load_image(self.signed.get())
        assert len(im.codesign_info.entitlements) != 0


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
