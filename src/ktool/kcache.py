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
from io import BytesIO

import ktool
from kmacho.structs import *
from ktool import MachOFile, Image, log
from ktool.dyld import ImageHeader, Dyld
import ktool.kplistlib as plistlib
from ktool.exceptions import UnsupportedFiletypeException


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
    def __init__(self):

        self.prelink_info = {}

        self.name = ""
        self.version = ""
        self.start_addr = 0

        self.development_region = ""
        self.executable_name = ""
        self.id = ""
        self.bundle_name = ""
        self.package_type = ""
        self.info_string = ""
        self.version_str = ""

        self.image = None


class EmbeddedKext(Kext):
    def __init__(self, image, prelink_info):
        super().__init__()
        self.start_addr = prelink_info['_PrelinkExecutableLoadAddr']
        self.size = prelink_info['_PrelinkExecutableSize']
        self.name = prelink_info['CFBundleIdentifier']
        self.version = prelink_info['CFBundleVersion']

        self.backing_file = BytesIO()
        self.backing_file.write(image.get_bytes_at(self.start_addr, self.size, vm=True))
        self.backing_file.seek(0)
        self.image = ktool.load_image(self.backing_file)


class MergedKext(Kext):
    def __init__(self, image: Image, kmod_info, start_addr):
        super().__init__()

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
        # noinspection PyProtectedMember
        Dyld._process_image(self.image)

        for segment in image.segments.values():
            segment.vm_address = segment.vm_address | 0xffff000000000000


class KernelCache:

    def __init__(self, macho_file: MachOFile):
        self.mach_kernel_file = macho_file
        self.mach_kernel = ktool.load_image(macho_file)

        self.kexts = []

        self.prelink_info = {}

        if '__info' in self.mach_kernel.segments['__PRELINK_INFO'].sections:
            self._process_prelink_info()

        self.version = self.prelink_info['com.apple.kpi.mach']['CFBundleVersion']

        # there is (that i know of, anyways) no official name for the old/new kext styles, so we're going with
        # 'normal' (pre ios 12) and 'merged' (post ios 12), per bazad's old blog post.

        if '__kmod_info' in self.mach_kernel.segments['__PRELINK_INFO'].sections:
            self._process_merged_kexts()

        if len(self.kexts) == 0:
            if '_PrelinkExecutableLoadAddr' in self.prelink_info['com.apple.kpi.mach']:
                self._process_kexts_from_prelink_info()

        self._process_kexts()

    def _process_kexts_from_prelink_info(self):
        for kext_name, kext in self.prelink_info.items():
            try:
                self.kexts.append(EmbeddedKext(self.mach_kernel, kext))
            except UnsupportedFiletypeException:
                log.debug(f'Bad Header(?) at {kext_name}')
            except KeyError:
                pass

    def _process_kexts(self):
        for kext in self.kexts:
            if kext.name in self.prelink_info.keys():
                kext.executable_name = self.prelink_info[kext.name]['CFBundleExecutable']
                kext.id = self.prelink_info[kext.name]['CFBundleIdentifier']
                kext.bundle_name = self.prelink_info[kext.name]['CFBundleName']
                kext.package_type = self.prelink_info[kext.name]['CFBundlePackageType']
                kext.info_string = self.prelink_info[kext.name]['CFBundleGetInfoString'] if 'CFBundleGetInfoString' in self.prelink_info[kext.name] else ''
                kext.version_str = self.prelink_info[kext.name]['CFBundleVersion']

                kext.prelink_info = self.prelink_info[kext.name]

    def _process_prelink_info(self):
        address = self.mach_kernel.segments['__PRELINK_INFO'].sections['__info'].vm_address
        prelink_info_str = f'<plist version="1.0">{self.mach_kernel.get_cstr_at(address, vm=True)}</plist>'
        prelink_info_dat = prelink_info_str.encode('utf-8')
        prelink_info = plistlib.readPlistFromBytes(prelink_info_dat)
        items = prelink_info['_PrelinkInfoDictionary']
        for bundle_dict in items:
            self.prelink_info[bundle_dict['CFBundleIdentifier']] = bundle_dict

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
            kext = MergedKext(self.mach_kernel, info, start_addr)
            self.kexts.append(kext)







