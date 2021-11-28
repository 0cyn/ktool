#
#  ktool | ktool
#  generator.py
#
#  Holds some miscellaneous generators for certain filetypes
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2021.
#

import os
from collections import namedtuple

from kmacho.structs import *
from . import log
from .dyld import Dyld, SymbolType
from .macho import Slice
from .objc import ObjCImage


class TBDGenerator:
    def __init__(self, image, general=True, objc_lib=None):
        """
        The TBD Generator is a generator that creates TAPI formatted text based stubs for libraries.

        It is currently fairly incomplete, although its output should still be perfectly functional in an SDK.

        After processing, its .dict attribute can be dumped by a TAPI YAML serializer (located in ktool.util) to
            produce a functional .tbd

        :param image: image being processed
        :type image: image
        :param general: Should the generator create a .tbd for usage in SDKs?
        :type general: bool
        :param objc_lib: Pass an objc image to the generator. If none is passed it will generate its own
        """
        self.image = image
        self.objc_lib = objc_lib
        self.general = general
        self.dict = self._generate_dict()

    def _generate_dict(self):
        """
        This function simply parses through the image and creates the tbd dict

        :return: The text-based-stub dictionary representation
        """
        tbd = {}
        if self.general:
            tbd['archs'] = ['armv7', 'armv7s', 'arm64', 'arm64e']
            tbd['platform'] = '(null)'
            tbd['install-name'] = self.image.dylib.install_name
            tbd['current-version'] = 1
            tbd['compatibility-version'] = 1

            export_dict = {'archs': ['armv7', 'armv7s', 'arm64', 'arm64e']}

            if len(self.image.allowed_clients) > 0:
                export_dict['allowed-clients'] = self.image.allowed_clients

            symbols = []
            classes = []
            ivars = []

            for sym in self.image.exports.symbols:
                if sym.type == SymbolType.FUNC:
                    symbols.append(sym.name)
                elif sym.type == SymbolType.CLASS:
                    classes.append(sym.name)
                elif sym.type == SymbolType.IVAR:
                    ivars.append(sym.name)

            export_dict['symbols'] = symbols
            export_dict['objc-classes'] = classes
            export_dict['objc-ivars'] = ivars

            tbd['exports'] = [export_dict]
        return tbd


fat_arch_for_slice = namedtuple("fat_arch_for_slice", [
    "slice",
    "cputype",
    "cpusubtype",
    "offset",
    "size",
    "align"
])


class FatMachOGenerator:
    """

    """

    def __init__(self, slices):
        self.slices = slices
        self.fat_archs = []
        pfa = None
        for fat_slice in slices:
            fat_arch_item = self._fat_arch_for_slice(fat_slice, pfa)
            pfa = fat_arch_item
            self.fat_archs.append(fat_arch_item)

        fat_head = bytearray()

        fh = Struct.create_with_values(fat_header, [b'\xCA\xFE\xBA\xBE', len(self.fat_archs)], "big")

        fat_head += fh.raw

        for fat_arch_item in self.fat_archs:
            fa = Struct.create_with_values(fat_arch,
                                           [fat_arch_item.cputype, fat_arch_item.cpusubtype, fat_arch_item.offset,
                                            fat_arch_item.size, fat_arch_item.align], "big")
            fat_head += fa.raw

        self.fat_head = fat_head

    @staticmethod
    def _fat_arch_for_slice(fat_slice: Slice, previous_fat_arch):
        """
        :param fat_slice: Fat slice
        :type fat_slice: Slice
        :param previous_fat_arch: Previous item returned by this func, or None if first.
        :type previous_fat_arch: fat_arch_for_slice
        :return: fat_arch_for_slice item.
        :rtype: fat_arch_for_slice
        """
        lib = Dyld.load(fat_slice)
        cputype = lib.macho_header.dyld_header.cputype
        cpu_subtype = lib.macho_header.dyld_header.cpu_subtype

        if len(fat_slice.macho_file.slices) > 1:
            size = fat_slice.arch_struct.size
            align = pow(2, fat_slice.arch_struct.align)
            align_directive = fat_slice.arch_struct.align
        else:
            f = fat_slice.macho_file.file_object
            old_file_position = f.tell()
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(old_file_position, os.SEEK_SET)

            if cputype == 16777228:
                align = pow(2, 0xe)
                align_directive = 0xe
            elif cputype == 16777223:
                align = pow(2, 0xc)
                align_directive = 0xc
            else:
                # TODO: implement other alignment directives and stuff
                print(cputype)
                raise AssertionError("not yet implemented")
        if previous_fat_arch is None:
            offset = align
        else:
            offset = 0
            while True:
                offset += align
                if offset > previous_fat_arch.offset + previous_fat_arch.size:
                    break

        log.debug(f'Create arch with offset {hex(offset)} and size {hex(size)}')

        return fat_arch_for_slice(fat_slice, cputype, cpu_subtype, offset, size, align_directive)
