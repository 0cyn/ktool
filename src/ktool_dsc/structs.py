#
#  ktool | ktool_dsc
#  structs.py
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

from lib0cyn.structs import *


class dyld_cache_header(Struct):
    _FIELDS = \
        {
            "magic": char_t[16],
            "mappingOffset": uint32_t,
            "mappingCount": uint32_t,
            "imagesOffsetOld": uint32_t,
            "imagesCountOld": uint32_t,
            "dyldBaseAddress": uint64_t,
            "codeSignatureOffset": uint64_t,
            "codeSignatureSize": uint64_t,
            "slideInfoOffsetUnused": uint64_t,
            "slideInfoSizeUnused": uint64_t,
            "localSymbolsOffset": uint64_t,
            "localSymbolsSize": uint64_t,
            "uuid": bytes_t[16],
            "cacheType": uint64_t,
            "branchPoolsOffset": uint32_t,
            "branchPoolsCount": uint32_t,
            "accelerateInfoAddr": uint64_t,
            "accelerateInfoSize": uint64_t,
            "imagesTextOffset": uint64_t,
            "imagesTextCount": uint64_t,
            "patchInfoAddr": uint64_t,
            "patchInfoSize": uint64_t,
            "otherImageGroupAddrUnused": uint64_t,
            "otherImageGroupAddrSizeUnuzed": uint64_t,
            "progClosuresAddr": uint64_t,
            "progClosuresSize": uint64_t,
            "progClosuresTrieAddr": uint64_t,
            "progClosuresTrieSize": uint64_t,
            "platform": uint32_t,
            "FormatVersionBitField": Bitfield({
                "formatVersion": 8,
                "dylibsExpectedOnDisk": 1,
                "simulator": 1,
                "locallyBuiltCache": 1,
                "builtFromChainedFixups": 1,
                "padding": 20
            }),
            "sharedRegionStart": uint64_t,
            "sharedRegionSize": uint64_t,
            "maxSize": uint64_t,
            "dylibsImageArrayAddr": uint64_t,
            "dylibsImageArraySize": uint64_t,
            "dylibsTrieAddr": uint64_t,
            "dylibsTrieSize": uint64_t,
            "otherImageArrayAddr": uint64_t,
            "otherImageArraySize": uint64_t,
            "otherTrieAddr": uint64_t,
            "otherTrieSize": uint64_t,
            "mappingWithSlideOffset": uint32_t,
            "mappingWithSlideCount": uint32_t,
            "dylibsPBLStateArrayAddrUnused": uint64_t,
            "dylibsPBLSetAddr": uint64_t,
            "programsPBLSetPoolAddr": uint64_t,
            "programsPBLSetPoolSize": uint64_t,
            "programTrieAddr": uint64_t,
            "programTrieSize": uint32_t,
            "osVersion": uint32_t,
            "altPlatform": uint32_t,
            "altOsVersion": uint32_t,
            "swiftOptsOffset": uint64_t,
            "swiftOptsSize": uint64_t,
            "subCacheArrayOffset": uint32_t,
            "subCacheArrayCount": uint32_t,
            "symbolFileUUID": bytes_t[16],
            "rosettaReadOnlyAddr": uint64_t,
            "rosettaReadOnlySize": uint64_t,
            "rosettaReadWriteAddr": uint64_t,
            "rosettaReadWriteSize": uint64_t,
            "imagesOffset": uint32_t,
            "imagesCount": uint32_t,
        }
    SIZE = 456

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_cache_mapping_info(Struct):

    _FIELDS = \
        {
            "address": uint64_t,
            "size": uint64_t,
            "fileOffset": uint64_t,
            "maxProt": uint32_t,
            "initProt": uint32_t
        }
    SIZE = 32

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)
        
        
class dyld_cache_mapping_and_slide_info(Struct):
    _FIELDS = \
        {
            "address": uint64_t,
            "size": uint64_t,
            "fileOffset": uint64_t,
            "slideInfoFileOffset": uint64_t,
            "slideInfoFileSize": uint64_t,
            "flags": uint64_t,
            "maxProt": uint32_t,
            "initProt": uint32_t
        }
    SIZE = 56

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_cache_image_info(Struct):
    _FIELDS = \
        {
            "address": uint64_t,
            "modTime": uint64_t,
            "inode": uint64_t,
            "pathFileOffset": uint32_t,
            "pad": uint32_t,
        }
    SIZE = 32

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_cache_image_info_extra(Struct):
    _FIELDS = \
        {
            "exportsTrieAddr": uint64_t,
            "weakBindingsAddr": uint64_t,
            "exportsTrieSize": uint32_t,
            "weakBindingsSize": uint32_t,
            "dependentsStartArrayIndex": uint32_t,
            "reExportsStartArrayIndex": uint32_t
        }
    SIZE = 32

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_cache_accelerator_info(Struct):
    _FIELDS = \
        {
            "version": uint32_t,
            "imageExtrasCount": uint32_t,
            "imagesExtrasOffset": uint32_t,
            "bottomUpListOffset": uint32_t,
            "dylibTrieOffset": uint32_t,
            "dylibTrieSize": uint32_t,
            "initializersOffset": uint32_t,
            "initializersCount": uint32_t,
            "dofSectionsOffset": uint32_t,
            "dofSectionsCount": uint32_t,
            "reExportListOffset": uint32_t,
            "reExportCount": uint32_t,
            "depListOffset": uint32_t,
            "depListCount": uint32_t,
            "rangeTableOffset": uint32_t,
            "rangeTableCount": uint32_t,
            "dyldSectionAddr": uint64_t
        }
    SIZE = sum(_FIELDS.values())

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_cache_accelerator_initializer(Struct):
    _FIELDS = \
        {
            "functionOffset": uint32_t,
            "imageIndex": uint32_t,
        }
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_cache_range_entry(Struct):
    _FIELDS = \
        {
            "startAddress": uint64_t,
            "size": uint32_t,
            "imageIndex": uint32_t
        }
    SIZE = 16

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_cache_accelerator_dof(Struct):
    _FIELDS = \
        {
            "sectionAddress": uint64_t,
            "sectionSize": uint32_t,
            "imageIndex": uint32_t
        }
    SIZE = 16

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_cache_image_text_info(Struct):
    _FIELDS = \
        {
            "uuid": bytes_t[16],
            "loadAddress": uint64_t,
            "textSegmentSize": uint32_t,
            "pathOffset": uint32_t,
        }
    SIZE = 32

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_cache_slide_info(Struct):
    _FIELDS = \
        {
            "version": uint32_t,
            "toc_offset": uint32_t,
            "toc_count": uint32_t,
            "entries_offset": uint32_t,
            "entries_count": uint32_t,
            "entries_size": uint32_t
        }
    SIZE = 24

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_cache_slide_info2(Struct):
    _FIELDS = \
        {
            "version": uint32_t,
            "page_size": uint32_t,
            "page_starts_offset": uint32_t,
            "page_starts_count": uint32_t,
            "page_extras_offset": uint32_t,
            "page_extras_count": uint32_t,
            "delta_mask": uint64_t,
            "value_add": uint64_t
        }
    SIZE = 40

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_cache_slide_info3(Struct):
    _FIELDS = \
        {
            "version": uint32_t,
            "page_size": uint32_t,
            "page_starts_count": uint32_t,
            "auth_value_add": uint64_t
        }
    SIZE = 20

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_cache_slide_info4(Struct):
    _FIELDS = \
        {
            "version": uint32_t,
            "page_size": uint32_t,
            "page_starts_offset": uint32_t,
            "page_starts_count": uint32_t,
            "page_extras_offset": uint32_t,
            "page_extras_count": uint32_t,
            "delta_mask": uint32_t,
            "value_add": uint32_t
        }
    SIZE = 32

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_cache_local_symbols_info(Struct):
    _FIELDS = \
        {
            "nlistOffset": uint32_t,
            "nlistCount": uint32_t,
            "stringsOffset": uint32_t,
            "stringsSize": uint32_t,
            "entriesOffset": uint32_t,
            "entriesCount": uint32_t
        }
    SIZE = 24

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_cache_local_symbols_entry(Struct):
    _FIELDS = \
        {
            "dylibOffset": uint32_t,
            "nlistStartIndex": uint32_t,
            "nlistCount": uint32_t
        }
    SIZE = 12

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_cache_local_symbols_entry_64(Struct):
    _FIELDS = \
        {
            "dylibOffset": uint64_t,
            "nlistStartIndex": uint32_t,
            "nlistCount": uint32_t
        }
    SIZE = 16

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_cache_patch_info(Struct):
    _FIELDS = \
        {
            "patchTableArrayAddr": uint64_t,
            "patchTableArrayCount": uint64_t,
            "patchExportArrayAddr": uint64_t,
            "patchExportArrayCount": uint64_t,
            "patchLocationArrayAddr": uint64_t,
            "patchLocationArrayCount": uint64_t,
            "patchExportNamesAddr": uint64_t,
            "patchExportNamesSize": uint64_t
        }
    SIZE = 64

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_cache_image_patches(Struct):
    _FIELDS = \
        {
            "patchExportsStartIndex": uint32_t,
            "patchExportsCount": uint32_t
        }
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_cache_patchable_export(Struct):
    _FIELDS = \
        {
            "cacheOffsetOfImpl": uint32_t,
            "patchLocationStartIndex": uint32_t,
            "patchLocationsCount": uint32_t,
            "exportNameOffset": uint32_t
        }
    SIZE = 16

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_subcache_entry(Struct):
    _FIELDS = \
        {
            "uuid": bytes_t[16],
            "cacheVMOffset": uint64_t,
        }
    SIZE = 24

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)


class dyld_subcache_entry2(Struct):
    _FIELDS = \
        {
            "uuid": bytes_t[16],
            "cacheVMOffset": uint64_t,
            "fileExtension": char_t[32]
        }
    SIZE = 56

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDS.keys(), sizes=self._FIELDS.values(), byte_order=byte_order)
