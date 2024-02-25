#
#  ktool | ktool_macho
#  structs.py
#
#  the __init__ defs here are unnecessary and only required for my IDE (pycharm) to recognize and autocomplete
#   the struct attributes
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) 0cyn 2021.
#
import ktool_macho
from lib0cyn.structs import *


def os_tuple_composer(struct: Struct, field: str):
    value = struct.__getattribute__(field)
    x = (value >> 16) & 0xFFFF
    y = (value >> 8) & 0xFF
    z = value & 0xff
    dot = Struct.t_token('.')
    return f'{Struct.t_base(x)}{dot}{Struct.t_base(y)}{dot}{Struct.t_base(z)}'


def cmd_composer(struct: Struct, field: str):
    value = struct.__getattribute__(field)
    return f'{Struct.t_base(ktool_macho.LOAD_COMMAND(value).name)} {Struct.t_token("(")}{Struct.t_base(hex(value))}{Struct.t_token(")")}'


class fat_header(Struct):
    """
    First 8 Bytes of a FAT MachO File

    Attributes:
        self.magic: FAT MachO Magic

        self.nfat_archs: Number of Fat Arch entries after these bytes
    """
    FIELDS = {
        'magic': uint32_t,
        'nfat_archs': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.magic = 0
        self.nfat_archs = 0


class fat_arch(Struct):
    """
    Struct representing a slice in a FAT MachO

    Attribs:
        cpu_type:
    """
    FIELDS = {
        'cpu_type': uint32_t,
        'cpu_subtype': uint32_t,
        'offset': uint32_t,
        'size': uint32_t,
        'align': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.cpu_type = 0
        self.cpu_subtype = 0
        self.offset = 0
        self.size = 0
        self.align = 0


class mach_header(Struct):
    FIELDS = {
        'magic': uint32_t,
        'cpu_type': uint32_t,
        'cpu_subtype': uint32_t,
        'filetype': uint32_t,
        'loadcnt': uint32_t,
        'loadsize': uint32_t,
        'flags': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.magic = 0
        self.cpu_type = 0
        self.cpu_subtype = 0
        self.filetype = 0
        self.loadcnt = 0
        self.loadsize = 0
        self.flags = 0


class mach_header_64(Struct):
    FIELDS = {
        'magic': uint32_t,
        'cpu_type': uint32_t,
        'cpu_subtype': uint32_t,
        'filetype': uint32_t,
        'loadcnt': uint32_t,
        'loadsize': uint32_t,
        'flags': uint32_t,
        'reserved': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.magic = 0
        self.cpu_type = 0
        self.cpu_subtype = 0
        self.filetype = 0
        self.loadcnt = 0
        self.loadsize = 0
        self.flags = 0
        self.reserved = 0


class unk_command(Struct):
    FIELDS = {
        'cmd': uint32_t,
        'cmdsize': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.cmd = 0
        self.add_field_composer('cmd', cmd_composer)
        self.cmdsize = 0


class segment_command(Struct):
    FIELDS = {
        'cmd': uint32_t,
        'cmdsize': uint32_t,
        'segname': char_t[16],
        'vmaddr': uint32_t,
        'vmsize': uint32_t,
        'fileoff': uint32_t,
        'filesize': uint32_t,
        'maxprot': uint32_t,
        'initprot': uint32_t,
        'nsects': uint32_t,
        'flags': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.cmd = 0
        self.add_field_composer('cmd', cmd_composer)
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
    FIELDS = {
        'cmd': uint32_t,
        'cmdsize': uint32_t,
        'segname': char_t[16],
        'vmaddr': uint64_t,
        'vmsize': uint64_t,
        'fileoff': uint64_t,
        'filesize': uint64_t,
        'maxprot': uint32_t,
        'initprot': uint32_t,
        'nsects': uint32_t,
        'flags': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.cmd = 0
        self.add_field_composer('cmd', cmd_composer)
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
    FIELDS = {
        'sectname': char_t[16],
        'segname': char_t[16],
        'addr': uint32_t,
        'size': uint32_t,
        'offset': uint32_t,
        'align': uint32_t,
        'reloff': uint32_t,
        'nreloc': uint32_t,
        'flags': uint32_t,
        'reserved1': uint32_t,
        'reserved2': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
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
    FIELDS = {
        'sectname': char_t[16],
        'segname': char_t[16],
        'addr': uint64_t,
        'size': uint64_t,
        'offset': uint32_t,
        'align': uint32_t,
        'reloff': uint32_t,
        'nreloc': uint32_t,
        'flags': uint32_t,
        'reserved1': uint32_t,
        'reserved2': uint32_t,
        'reserved3': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
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
    FIELDS = {
        'cmd': uint32_t,
        'cmdsize': uint32_t,
        'symoff': uint32_t,
        'nsyms': uint32_t,
        'stroff': uint32_t,
        'strsize': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.cmd = 0
        self.add_field_composer('cmd', cmd_composer)
        self.cmdsize = 0
        self.symoff = 0
        self.nsyms = 0
        self.stroff = 0
        self.strsize = 0


class dysymtab_command(Struct):
    FIELDS = {
        'cmd': uint32_t,
        'cmdsize': uint32_t,
        'ilocalsym': uint32_t,
        'nlocalsym': uint32_t,
        'iextdefsym': uint32_t,
        'nextdefsym': uint32_t,
        'iundefsym': uint32_t,
        'nundefsym': uint32_t,
        'tocoff': uint32_t,
        'ntoc': uint32_t,
        'modtaboff': uint32_t,
        'nmodtab': uint32_t,
        'extrefsymoff': uint32_t,
        'nextrefsyms': uint32_t,
        'indirectsymoff': uint32_t,
        'nindirectsyms': uint32_t,
        'extreloff': uint32_t,
        'nextrel': uint32_t,
        'locreloff': uint32_t,
        'nlocrel': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.cmd = 0
        self.add_field_composer('cmd', cmd_composer)
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
    FIELDS = {
        'name': uint32_t,
        'timestamp': uint32_t,
        'current_version': uint32_t,
        'compatibility_version': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.name = 0
        self.timestamp = 0
        self.current_version = 0
        self.compatibility_version = 0
        self.add_field_composer('current_version', os_tuple_composer)
        self.add_field_composer('compatibility_version', os_tuple_composer)


class dylib_command(Struct):
    FIELDS = {
        'cmd': uint32_t,
        'cmdsize': uint32_t,
        'dylib': dylib
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.cmd = 0
        self.add_field_composer('cmd', cmd_composer)
        self.cmdsize = 0
        self.dylib = 0


class dylinker_command(Struct):
    FIELDS = {
        'cmd': uint32_t,
        'cmdsize': uint32_t,
        'name': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.cmd = 0
        self.add_field_composer('cmd', cmd_composer)
        self.cmdsize = 0
        self.name = 0


class sub_client_command(Struct):
    FIELDS = {
        'cmd': uint32_t,
        'cmdsize': uint32_t,
        'offset': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.cmd = 0
        self.add_field_composer('cmd', cmd_composer)
        self.cmdsize = 0
        self.offset = 0


class uuid_command(Struct):
    FIELDS = {
        'cmd': uint32_t,
        'cmdsize': uint32_t,
        'uuid': bytes_t[16]
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.cmd = 0
        self.add_field_composer('cmd', cmd_composer)
        self.cmdsize = 0
        self.uuid = 0
        self.add_field_composer('uuid', uuid_command.uuid_field_composer)

    @staticmethod
    def uuid_field_composer(struct, field):
        assert field == "uuid"
        byte_array = struct.uuid
        return Struct.t_base(f'"{byte_array[0]:02x}{byte_array[1]:02x}{byte_array[2]:02x}{byte_array[3]:02x}-' \
           f'{byte_array[4]:02x}{byte_array[5]:02x}-' \
           f'{byte_array[6]:02x}{byte_array[7]:02x}-' \
           f'{byte_array[8]:02x}{byte_array[9]:02x}-' \
           f'{byte_array[10]:02x}{byte_array[11]:02x}{byte_array[12]:02x}{byte_array[13]:02x}{byte_array[14]:02x}{byte_array[15]:02x}"')


class build_version_command(Struct):
    FIELDS = {
        'cmd': uint32_t,
        'cmdsize': uint32_t,
        'platform': uint32_t,
        'minos': uint32_t,
        'sdk': uint32_t,
        'ntools': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.cmd = 0
        self.add_field_composer('cmd', cmd_composer)
        self.cmdsize = 0
        self.platform = 0
        self.minos = 0
        self.sdk = 0
        self.ntools = 0
        self.add_field_composer('minos', os_tuple_composer)
        self.add_field_composer('sdk', os_tuple_composer)


class entry_point_command(Struct):
    FIELDS = {
        'cmd': uint32_t,
        'cmdsize': uint32_t,
        'entryoff': uint64_t,
        'stacksize': uint64_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.cmd = 0
        self.add_field_composer('cmd', cmd_composer)
        self.cmdsize = 0
        self.entryoff = 0
        self.stacksize = 0


class rpath_command(Struct):
    FIELDS = {
        'cmd': uint32_t,
        'cmdsize': uint32_t,
        'path': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.cmd = 0
        self.add_field_composer('cmd', cmd_composer)
        self.cmdsize = 0
        self.path = 0


class source_version_command(Struct):
    FIELDS = {
        'cmd': uint32_t,
        'cmdsize': uint32_t,
        'version': uint64_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.cmd = 0
        self.add_field_composer('cmd', cmd_composer)
        self.cmdsize = 0
        self.version = 0
        self.add_field_composer('version', os_tuple_composer)


class linkedit_data_command(Struct):
    FIELDS = {
        'cmd': uint32_t,
        'cmdsize': uint32_t,
        'dataoff': uint32_t,
        'datasize': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.cmd = 0
        self.add_field_composer('cmd', cmd_composer)
        self.cmdsize = 0
        self.dataoff = 0
        self.datasize = 0


class dyld_info_command(Struct):
    FIELDS = {
        'cmd': uint32_t,
        'cmdsize': uint32_t,
        'rebase_off': uint32_t,
        'rebase_size': uint32_t,
        'bind_off': uint32_t,
        'bind_size': uint32_t,
        'weak_bind_off': uint32_t,
        'weak_bind_size': uint32_t,
        'lazy_bind_off': uint32_t,
        'lazy_bind_size': uint32_t,
        'export_off': uint32_t,
        'export_size': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.cmd = 0
        self.add_field_composer('cmd', cmd_composer)
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
    FIELDS = {
        'str_index': uint32_t,
        'type': uint8_t,
        'sect_index': uint8_t,
        'desc': uint16_t,
        'value': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.str_index = 0
        self.type = 0
        self.sect_index = 0
        self.desc = 0
        self.value = 0


class symtab_entry(Struct):
    FIELDS = {
        'str_index': uint32_t,
        'type': uint8_t,
        'sect_index': uint8_t,
        'desc': uint16_t,
        'value': uint64_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.str_index = 0
        self.type = 0
        self.sect_index = 0
        self.desc = 0
        self.value = 0


class version_min_command(Struct):
    FIELDS = {
        'cmd': uint32_t,
        'cmdsize': uint32_t,
        'version': uint32_t,
        'reserved': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.cmd = 0
        self.add_field_composer('cmd', cmd_composer)
        self.cmdsize = 0
        self.version = 0
        self.reserved = 0
        self.add_field_composer('version', os_tuple_composer)


class encryption_info_command(Struct):
    FIELDS = {
        'cmd': uint32_t,
        'cmdsize': uint32_t,
        'cryptoff': uint32_t,
        'cryptsize': uint32_t,
        'cryptid': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.cmd = 0
        self.add_field_composer('cmd', cmd_composer)
        self.cmdsize = 0
        self.cryptoff = 0
        self.cryptsize = 0
        self.cryptid = 0


class encryption_info_command_64(Struct):
    FIELDS = {
        'cmd': uint32_t,
        'cmdsize': uint32_t,
        'cryptoff': uint32_t,
        'cryptsize': uint32_t,
        'cryptid': uint32_t,
        'pad': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.cmd = 0
        self.add_field_composer('cmd', cmd_composer)
        self.cmdsize = 0
        self.cryptoff = 0
        self.cryptsize = 0
        self.cryptid = 0
        self.pad = 0


class thread_command(Struct):
    FIELDS = {
        'cmd': uint32_t,
        'cmdsize': uint32_t,
        'flavor': uint32_t,
        'count': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.cmd = 0
        self.add_field_composer('cmd', cmd_composer)
        self.cmdsize = 0
        self.flavor = 0
        self.count = 0
