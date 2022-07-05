#
#  ktool | kdsc
#  loader.py
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
import ktool.ktool
from katlib.log import LogLevel

from kdsc.file import *
from kdsc.structs import *
from kdsc.shared_cache import *
import os.path as path

from kmacho.structs import *
from ktool.macho import MachOImageHeader, Segment
from ktool.image import MisalignedVM, Image
from ktool.objc import MethodList, ObjCImage
from ktool.loader import MachOImageLoader


class DyldSharedCacheLoader:
    @classmethod
    def load_dsc(cls, path):
        dsc = DyldSharedCache(path)
        header = dsc.load_struct(0, dyld_cache_header)
        isV2Cache = header.cacheType == 2

        dsc.header = header
        map_off = header.mappingOffset
        map_cnt = header.mappingCount

        if map_off < header._field_offsets['imagesOffset']:
            img_off = header.imagesOffsetOld
            img_cnt = header.imagesCountOld
        else:
            img_off = header.imagesOffset
            img_cnt = header.imagesCount
        for off in range(img_off, img_off + (img_cnt * dyld_cache_image_info.SIZE), dyld_cache_image_info.SIZE):
            info = dsc.load_struct(off, dyld_cache_image_info)
            img = DyldSharedCacheImageEntry(dsc.base_dsc, info)
            dsc.images[img.install_name] = img
        for off in range(map_off, map_off + map_cnt * dyld_cache_mapping_info.SIZE, dyld_cache_mapping_info.SIZE):
            mapping = dsc.load_struct(off, dyld_cache_mapping_info)
            dsc.vm.map_pages(mapping.fileOffset, mapping.address & 0xFFFFFFFFF, mapping.size, file=dsc.base_dsc)
        if map_off > header._field_offsets['subCacheArrayOffset']:
            sca_off = header.subCacheArrayOffset
            sca_cnt = header.subCacheArrayCount

            sub_cache_entry_type = dyld_subcache_entry2 if isV2Cache else dyld_subcache_entry

            subcaches: List[sub_cache_entry_type] = []

            for off in range(sca_off, sca_off + (sub_cache_entry_type.SIZE * sca_cnt), sub_cache_entry_type.SIZE):
                subcaches.append(dsc.load_struct(off, sub_cache_entry_type))
            for i, subcache in enumerate(subcaches):
                suffix = f'.{i+1}' if not isV2Cache else subcache.fileExtension
                file = MemoryCappedBufferedFileReader(open(path + suffix, 'rb'))
                dsc.subcache_files.append(file)
                subheader = dsc._load_struct(file, 0, dyld_cache_header)
                map_off = subheader.mappingOffset
                map_cnt = subheader.mappingCount
                for off in range(map_off, map_off + map_cnt * dyld_cache_mapping_info.SIZE,
                                 dyld_cache_mapping_info.SIZE):
                    mapping = dsc._load_struct(file, off, dyld_cache_mapping_info)
                    dsc.vm.map_pages(mapping.fileOffset, mapping.address & 0xFFFFFFFFF, mapping.size, file=file)
            try:
                file = MemoryCappedBufferedFileReader(open(path+f'.symbols', 'rb'))
            except FileNotFoundError:
                return dsc
            dsc.subcache_files.append(file)
            subheader = dsc._load_struct(file, 0, dyld_cache_header)
            map_off = subheader.mappingOffset
            map_cnt = subheader.mappingCount
            for off in range(map_off, map_off + map_cnt * dyld_cache_mapping_info.SIZE,
                             dyld_cache_mapping_info.SIZE):
                mapping = dsc._load_struct(file, off, dyld_cache_mapping_info)
                dsc.vm.map_pages(mapping.fileOffset, mapping.address, mapping.size, file=file)

        dsc.vm.detag_64 = True
        return dsc

    @classmethod
    def load_image_from_basename(cls, dsc, basename):
        dsc_image = None
        for k, v in dsc.images.items():
            if path.basename(k) == basename:
                dsc_image = v
                break
        img = dsc_image
        header = dsc.load_struct(img.info.address & 0xFFFFFFFFF, mach_header_64, vm=True)
        addr, file = dsc.vm.translate_and_get_file(img.info.address & 0xFFFFFFFFF)
        dsc.vm.detag_64 = True
        dsc.current_base_cache = file
        macho_header = MachOImageHeader.from_image(dsc, addr)
        image = Image(None)
        image.macho_header = macho_header
        setattr(image, '_dsc', dsc)
        image.vm = MisalignedVM()
        image.vm.fallback = dsc.vm
        image.vm.detag_64 = True
        image.slice = DyldSharedCacheImageSliceAdapter(dsc, basename)
        image.load_struct = dsc.load_struct
        image.get_uint_at = dsc.get_uint_at
        image.get_bytes_at = dsc.get_bytes_at
        image.get_cstr_at = dsc.get_cstr_at
        MachOImageLoader.SYMTAB_LOADER = DSCSymbolTable
        MachOImageLoader._parse_load_commands(image)

        return image
