#
#  ktool | ktool_macho
#  structs.py
#
#
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) 0cyn 2021.
#

from lib0cyn.structs import *


class fat_header(Struct):
    """
    First 8 Bytes of a FAT MachO File

    Attributes:
        self.magic: FAT MachO Magic

        self.nfat_archs: Number of Fat Arch entries after these bytes
    """
    _FIELDNAMES = ['magic', 'nfat_archs']
    _SIZES = [uint32_t, uint32_t]
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class fat_arch(Struct):
    """
    Struct representing a slice in a FAT MachO

    Attribs:
        cpu_type:
    """
    _FIELDNAMES = ['cpu_type', 'cpu_subtype', 'offset', 'size', 'align']
    _SIZES = [uint32_t, uint32_t, uint32_t, uint32_t, uint32_t]
    SIZE = 20

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cpu_type = 0
        self.cpu_subtype = 0
        self.offset = 0
        self.size = 0
        self.align = 0


class mach_header(Struct):
    _FIELDNAMES = ['magic', 'cpu_type', 'cpu_subtype', 'filetype', 'loadcnt', 'loadsize', 'flags']
    _SIZES = [uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t]
    SIZE = 28

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.magic = 0
        self.cpu_type = 0
        self.cpu_subtype = 0
        self.filetype = 0
        self.loadcnt = 0
        self.loadsize = 0
        self.flags = 0


class mach_header_64(Struct):
    _FIELDNAMES = ['magic', 'cpu_type', 'cpu_subtype', 'filetype', 'loadcnt', 'loadsize', 'flags', 'reserved']
    _SIZES = [uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t]
    SIZE = 32

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.magic = 0
        self.cpu_type = 0
        self.cpu_subtype = 0
        self.filetype = 0
        self.loadcnt = 0
        self.loadsize = 0
        self.flags = 0
        self.reserved = 0


class unk_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize']
    _SIZES = [uint32_t, uint32_t]
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0


class segment_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'segname', 'vmaddr', 'vmsize', 'fileoff', 'filesize', 'maxprot', 'initprot',
                   'nsects', 'flags']
    _SIZES = [uint32_t, uint32_t, char_t[16], uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t,
              uint32_t]
    SIZE = 56

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.segname = 0
        self.vmaddr = 0
        self.vmsize = 0
        self.fileoff = 0
        self.filesize = 0
        self.maxprot = 0
        self.initprot = 0
        self.nsects = 0
        self.flags = 0


class segment_command_64(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'segname', 'vmaddr', 'vmsize', 'fileoff', 'filesize', 'maxprot', 'initprot',
                   'nsects', 'flags']
    _SIZES = [uint32_t, uint32_t, char_t[16], uint64_t, uint64_t, uint64_t, uint64_t, uint32_t, uint32_t, uint32_t,
              uint32_t]
    SIZE = 72

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.segname = 0
        self.vmaddr = 0
        self.vmsize = 0
        self.fileoff = 0
        self.filesize = 0
        self.maxprot = 0
        self.initprot = 0
        self.nsects = 0
        self.flags = 0


class section(Struct):
    _FIELDNAMES = ['sectname', 'segname', 'addr', 'size', 'offset', 'align', 'reloff', 'nreloc', 'flags', 'reserved1',
                   'reserved2']
    _SIZES = [char_t[16], char_t[16], uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t,
              uint32_t]
    SIZE = 68

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.sectname = 0
        self.segname = 0
        self.addr = 0
        self.size = 0
        self.offset = 0
        self.align = 0
        self.reloff = 0
        self.nreloc = 0
        self.flags = 0
        self.reserved1 = 0
        self.reserved2 = 0


class section_64(Struct):
    _FIELDNAMES = ['sectname', 'segname', 'addr', 'size', 'offset', 'align', 'reloff', 'nreloc', 'flags', 'reserved1',
                   'reserved2', 'reserved3']
    _SIZES = [char_t[16], char_t[16], uint64_t, uint64_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t,
              uint32_t, uint32_t]
    SIZE = 80

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.sectname = 0
        self.segname = 0
        self.addr = 0
        self.size = 0
        self.offset = 0
        self.align = 0
        self.reloff = 0
        self.nreloc = 0
        self.flags = 0
        self.reserved1 = 0
        self.reserved2 = 0
        self.reserved3 = 0


class symtab_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'symoff', 'nsyms', 'stroff', 'strsize']
    _SIZES = [uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t]
    SIZE = 4 * 6

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.symoff = 0
        self.nsyms = 0
        self.stroff = 0
        self.strsize = 0


class dysymtab_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'ilocalsym', 'nlocalsym', 'iextdefsym', 'nextdefsym', 'iundefsym', 'nundefsym',
                   'tocoff', 'ntoc', 'modtaboff', 'nmodtab', 'extrefsymoff', 'nextrefsyms', 'indirectsymoff',
                   'nindirectsyms', 'extreloff', 'nextrel', 'locreloff', 'nlocrel']
    _SIZES = [uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t,
              uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t]
    SIZE = 80

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.ilocalsym = 0
        self.nlocalsym = 0
        self.iextdefsym = 0
        self.nextdefsym = 0
        self.iundefsym = 0
        self.nundefsym = 0
        self.tocoff = 0
        self.ntoc = 0
        self.modtaboff = 0
        self.nmodtab = 0
        self.extrefsymoff = 0
        self.nextrefsyms = 0
        self.indirectsymoff = 0
        self.nindirectsyms = 0
        self.extreloff = 0
        self.nextrel = 0
        self.locreloff = 0
        self.nlocrel = 0


class dylib(Struct):
    _FIELDNAMES = ['name', 'timestamp', 'current_version', 'compatibility_version']
    _SIZES = [uint32_t, uint32_t, uint32_t, uint32_t]
    SIZE = 16

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.name = 0
        self.timestamp = 0
        self.current_version = 0
        self.compatibility_version = 0


class dylib_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'dylib']
    _SIZES = [uint32_t, uint32_t, dylib]
    SIZE = 24

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.dylib = 0


class dylinker_command(Struct):
    _FIELDNAMES = ["cmd", "cmdsize", "name"]
    _SIZES = [uint32_t, uint32_t, uint32_t]
    SIZE = 12

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.name = 0


class sub_client_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'offset']
    _SIZES = [uint32_t, uint32_t, uint32_t]
    SIZE = 12

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.offset = 0


class uuid_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'uuid']
    _SIZES = [uint32_t, uint32_t, type_bytes | 16]
    SIZE = 24

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.uuid = 0


class build_version_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'platform', 'minos', 'sdk', 'ntools']
    _SIZES = [uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t]
    SIZE = 24

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.platform = 0
        self.minos = 0
        self.sdk = 0
        self.ntools = 0


class entry_point_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'entryoff', 'stacksize']
    _SIZES = [uint32_t, uint32_t, uint64_t, uint64_t]
    SIZE = 24

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.entryoff = 0
        self.stacksize = 0


class rpath_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'path']
    _SIZES = [uint32_t, uint32_t, uint32_t]
    SIZE = 12

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.path = 0


class source_version_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'version']
    _SIZES = [uint32_t, uint32_t, uint64_t]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.version = 0


class linkedit_data_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'dataoff', 'datasize']
    _SIZES = [uint32_t, uint32_t, uint32_t, uint32_t]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.dataoff = 0
        self.datasize = 0


class dyld_info_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'rebase_off', 'rebase_size', 'bind_off', 'bind_size', 'weak_bind_off',
                   'weak_bind_size', 'lazy_bind_off', 'lazy_bind_size', 'export_off', 'export_size']
    _SIZES = [uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t,
              uint32_t, uint32_t]
    SIZE = 48

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdisze = 0
        self.rebase_off = 0
        self.rebase_size = 0
        self.bind_off = 0
        self.bind_size = 0
        self.weak_bind_off = 0
        self.weak_bind_size = 0
        self.lazy_bind_off = 0
        self.lazy_bind_size = 0
        self.export_off = 0
        self.export_size = 0


class symtab_entry_32(Struct):
    _FIELDNAMES = ["str_index", "type", "sect_index", "desc", "value"]
    _SIZES = [uint32_t, uint8_t, uint8_t, uint16_t, uint32_t]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.str_index = 0
        self.type = 0
        self.sect_index = 0
        self.desc = 0
        self.value = 0


class symtab_entry(Struct):
    _FIELDNAMES = ["str_index", "type", "sect_index", "desc", "value"]
    _SIZES = [uint32_t, uint8_t, uint8_t, uint16_t, uint64_t]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.str_index = 0
        self.type = 0
        self.sect_index = 0
        self.desc = 0
        self.value = 0


class version_min_command(Struct):
    _FIELDNAMES = ["cmd", "cmdsize", "version", "reserved"]
    _SIZES = [uint32_t, uint32_t, uint32_t, uint32_t]
    SIZE = 16

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.version = 0
        self.reserved = 0


class encryption_info_command(Struct):
    _FIELDNAMES = ["cmd", "cmdsize", "cryptoff", "cryptsize", "cryptid"]
    _SIZES = [uint32_t, uint32_t, uint32_t, uint32_t, uint32_t]
    SIZE = 20

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.cryptoff = 0
        self.cryptsize = 0
        self.cryptid = 0


class encryption_info_command_64(Struct):
    _FIELDNAMES = ["cmd", "cmdsize", "cryptoff", "cryptsize", "cryptid", "pad"]
    _SIZES = [uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.cryptoff = 0
        self.cryptsize = 0
        self.cryptid = 0
        self.pad = 0


class thread_command(Struct):
    _FIELDNAMES = ["cmd", "cmdsize", "flavor", "count"]
    _SIZES = [uint32_t, uint32_t, uint32_t, uint32_t]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.flavor = 0
        self.count = 0
