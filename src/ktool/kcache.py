#
#  ktool | ktool
#  kcache.py
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
import ktool
from ktool import MachOFile, Image

from kmacho.structs import *
from ktool.dyld import ImageHeader, Dyld


class kmod_info_64(Struct):
    """
    """
    _FIELDNAMES = ['next_addr', 'info_version', 'id', 'name', 'version', 'reference_count', 'reference_list_addr',
                   'address', 'size', 'hdr_size', 'start_addr', 'stop_addr']
    _SIZES = [uint64_t, int32_t, uint32_t, uint8_t*64, uint8_t*64, int32_t, uint64_t,
              uint64_t, uint64_t, uint64_t, uint64_t, uint64_t]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class Kext:
    def __init__(self, image: Image, kmod_info, start_addr):

        self.backing_image = image
        self.backing_slice = image.slice
        self.backing_file = self.backing_slice.macho_file.file

        is64 = image.macho_header.is64
        self.name = image.get_cstr_at(kmod_info.off + (0x10 if is64 else 0x8), vm=False)
        self.version = image.get_cstr_at(kmod_info.off + 64 + (0x10 if is64 else 0x8), vm=False)
        self.start_addr = start_addr
        self.info = kmod_info

        file_base_addr = image.vm.get_file_address(start_addr)

        # cool. we have a basic set of stuff in place, lets bootstrap up an Image from it.

        self.mach_header = ImageHeader.from_image(self.backing_slice, file_base_addr)
        self.image = Image(self.backing_slice)
        self.image.macho_header = self.mach_header

        # noinspection PyProtectedMember
        Dyld._parse_load_commands(self.image)
        Dyld._process_image(self.image)

        for segment in image.segments.values():
            segment.vm_address = segment.vm_address | 0xffff000000000000


class KernelCache:

    def __init__(self, macho_file: MachOFile):
        self.mach_kernel_file = macho_file
        self.mach_kernel = ktool.load_image(macho_file)

        self.kexts = []

        # there is (that i know of, anyways) no official name for the old/new kext styles, so we're going with
        # 'normal' (pre ios 12) and 'merged' (post ios 12), per bazad's old blog post.

        self._process_merged_kexts()

    def _process_merged_kexts(self):
        kext_starts = []
        kmod_start_sect = self.mach_kernel.segments['__PRELINK_INFO'].sections['__kmod_start']

        ptr_size = 8 if self.mach_kernel.macho_header.is64 else 4

        for i in range(kmod_start_sect.file_address, kmod_start_sect.file_address + kmod_start_sect.size, ptr_size):
            kext_starts.append(self.mach_kernel.get_int_at(i, ptr_size, vm=False))

        kmod_info_locations = []
        kmod_info_sect = self.mach_kernel.segments['__PRELINK_INFO'].sections['__kmod_info']

        for i in range(kmod_info_sect.file_address, kmod_info_sect.file_address + kmod_info_sect.size, ptr_size):
            kmod_info_locations.append(self.mach_kernel.get_int_at(i, ptr_size, vm=False))

        # start processing kmod info
        for i, info_loc in enumerate(kmod_info_locations):
            info = self.mach_kernel.load_struct(info_loc, kmod_info_64, vm=True)

            start_addr = kext_starts[i]
            kext = Kext(self.mach_kernel, info, start_addr)
            self.kexts.append(kext)







