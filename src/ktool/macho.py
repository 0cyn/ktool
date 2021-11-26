#
#  ktool | ktool
#  macho.py
#
#  This file contains utilities for basic parsing of MachO File headers and such.
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2021.
#

import mmap
import os
from collections import namedtuple
from enum import Enum
from typing import Tuple

from kmacho import *
from kmacho.structs import *
from .exceptions import *
from .util import log


class MachOFileType(Enum):
    FAT = 0
    THIN = 1


class MachOFile:
    def __init__(self, file):
        self.file_object = file
        self.file = mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_COPY)
        self.slices = []
        self.magic = self._get_at(0, 4)
        self.type = self._load_filetype()

        if self.type == MachOFileType.FAT:
            self.header: fat_header = self._load_struct(0, fat_header, "big")
            for off in range(0, self.header.nfat_archs):
                offset = fat_header.SIZE + (off * fat_arch.SIZE)
                arch_struct = self._load_struct(offset, fat_arch, "big")
                self.slices.append(Slice(self, arch_struct))
        else:
            self.slices.append(Slice(self, None))

    def _load_filetype(self):
        if self.magic == FAT_MAGIC or self.magic == FAT_CIGAM:
            return MachOFileType.FAT
        elif self.magic == MH_MAGIC or self.magic == MH_FILETYPE or self.magic == MH_MAGIC_64 or self.magic == MH_CIGAM_64:
            return MachOFileType.THIN
        else:
            raise UnsupportedFiletypeException

    def _load_struct(self, addr: int, struct_type, endian="little"):
        size = struct_type.SIZE
        data = self._get_bytes_at(addr, size)

        struct = Struct.create_with_bytes(struct_type, data, endian)
        struct.off = addr

        return struct

    def _get_bytes_at(self, addr, count):
        return self.file[addr: addr + count]

    # noinspection PyTypeChecker
    def _get_at(self, addr, count, endian="big"):
        return int.from_bytes(self.file[addr:addr + count], endian)

    def __del__(self):
        self.file.close()


class Segment:
    """

    """

    def __init__(self, library, cmd):
        self.library = library
        self.cmd = cmd
        self.vm_address = cmd.vmaddr
        self.file_address = cmd.fileoff
        self.size = cmd.vmsize
        self.name = ""
        for i, c in enumerate(hex(cmd.segname)[2:]):
            if i % 2 == 0:
                self.name += chr(int(c + hex(cmd.segname)[2:][i + 1], 16))
        self.name = self.name[::-1]
        self.sections = self._process_sections()

        self.type = SectionType(S_FLAGS_MASKS.SECTION_TYPE & self.cmd.flags)

    def _process_sections(self):
        sections = {}
        ea = self.cmd.off + segment_command_64.SIZE

        for section in range(0, self.cmd.nsects):
            sect = self.library.load_struct(ea, section_64)
            section = Section(self, sect)
            sections[section.name] = section
            ea += section_64.SIZE

        ea += segment_command_64.SIZE
        return sections


class Section:
    """

    """

    def __init__(self, segment, cmd):
        self.cmd = cmd
        self.segment = segment
        self.name = segment.library.get_str_at(cmd.off, 16)
        self.vm_address = cmd.addr
        self.file_address = cmd.offset
        self.size = cmd.size


vm_obj = namedtuple("vm_obj", ["vmaddr", "vmend", "size", "fileaddr", "name"])


class _VirtualMemoryMap:
    """
    Virtual Memory is the location "in memory" where the library/bin, etc will be accessed when ran This is not where
    it actually sits in memory at runtime; it will be slid, but the program doesnt know and doesnt care The slid
    address doesnt matter to us either, we only care about the addresses the rest of the file cares about

    There are two address sets used in mach-o files: vm, and file. (commonly; vmoff and fileoff)
    For example, when reading raw data of an executable binary:
    0x0 file offset will (normally?) map to 0x10000000 in the VM

    These VM offsets are relayed to the linker via Load Commands
    Some locations in the file do not have VM counterparts (examples being symbol table(citation needed))

    Some other VM related offsets are changed/modified via binding info(citation needed)
    """

    def __init__(self, macho_slice):
        # name: vm_obj
        self.slice = macho_slice
        self.map = {}
        self.stats = {}
        self.sorted_map = {}
        self.cache = {}

    def __str__(self):
        """
        We want to be able to just call print(macho.vm) to display the filemap in a human-readable format

        :return: multiline String representation of the filemap
        """

        ret = ""
        # Sort our map by VM Address, this should already be how it is but cant hurt
        sortedmap = {k: v for k, v in sorted(self.map.items(), key=lambda item: item[1].vmaddr)}

        for (key, obj) in sortedmap.items():
            # 'string'.ljust(16) adds space padding
            # 'string'[2:].zfill(9) removes the first 2 chars and pads the string with 9 zeros
            #       then we just re-add the 0x manually.

            # this gives us a nice list with visually clear columns and rows
            ret += f'{key.ljust(16)}  ||  Start: 0x{hex(obj.vmaddr)[2:].zfill(9)}  |  ' \
                   f'End: 0x{hex(obj.vmend)[2:].zfill(9)}  |  ' \
                   f'Size: 0x{hex(obj.size)[2:].zfill(9)}  |  Slice ' \
                   f'Offset:  0x{hex(obj.fileaddr)[2:].zfill(9)}  ||' \
                   f'  File Offset: 0x{hex(obj.fileaddr + self.slice.offset)[2:].zfill(9)}\n '
        return ret

    def get_vm_start(self):
        """
        Get the address the VM starts in, excluding __PAGEZERO
        Method selector dumping uses this
        :return:
        """
        sortedmap = {k: v for k, v in sorted(self.map.items(), key=lambda item: item[1].vm_address)}
        if list(sortedmap.keys())[0] == "__PAGEZERO":
            return list(sortedmap.values())[1].vm_address
        else:
            return list(sortedmap.values())[0].vm_address

    def get_file_address(self, vm_address: int, segment_name=None):
        # This function gets called *a lot*
        # It needs to be fast as shit.
        vm_address = 0x0000FFFFFFFFF & vm_address
        if vm_address in self.cache:
            return self.cache[vm_address]
        if segment_name is not None:
            o = self.map[segment_name]

            # noinspection PyChainedComparisons
            if vm_address >= o.vmaddr and o.vmend >= vm_address:
                file_addr = o.fileaddr + vm_address - o.vmaddr
                self.cache[vm_address] = file_addr
                return file_addr
            else:
                # noinspection PyBroadException
                try:
                    o = self.map['__EXTRA_OBJC']
                    # noinspection PyChainedComparisons
                    if vm_address >= o.vmaddr and o.vmend >= vm_address:
                        file_addr = o.fileaddr + vm_address - o.vmaddr
                        self.cache[vm_address] = file_addr
                        return file_addr
                except Exception:
                    for o in self.map.values():
                        # noinspection PyChainedComparisons
                        if vm_address >= o.vmaddr and o.vmend >= vm_address:
                            # self.stats[o.name] += 1
                            file_addr = o.fileaddr + vm_address - o.vmaddr
                            self.cache[vm_address] = file_addr
                            return file_addr

        for o in self.map.values():
            # noinspection PyChainedComparisons
            if vm_address >= o.vmaddr and o.vmend >= vm_address:
                # self.stats[o.name] += 1
                file_addr = o.fileaddr + vm_address - o.vmaddr
                self.cache[vm_address] = file_addr
                return file_addr

        raise ValueError(f'Address {hex(vm_address)} couldn\'t be found in vm address set')

    def add_segment(self, segment: Segment):
        if len(segment.sections) == 0:
            seg_obj = vm_obj(segment.vm_address, segment.vm_address + segment.size, segment.size, segment.file_address,
                             segment.name)
            log.info(str(seg_obj))
            self.map[segment.name] = seg_obj
            self.stats[segment.name] = 0
        else:
            for section in segment.sections.values():
                name = section.name if section.name not in self.map.keys() else section.name + '2'
                sect_obj = vm_obj(section.vm_address, section.vm_address + section.size, section.size,
                                  section.file_address, name)
                log.info(str(sect_obj))
                self.map[name] = sect_obj
                self.sorted_map = {k: v for k, v in sorted(self.map.items(), key=lambda item: item[1].vmaddr)}
                self.stats[name] = 0


class Slice:
    """

    """

    def __init__(self, macho_file, arch_struct, offset=0):
        """

        :param macho_file:
        :param arch_struct:
        :param offset:
        """
        self.macho_file = macho_file
        self.arch_struct = arch_struct

        self.patches = {}

        self.patched_bytes = b''
        self.use_patched_bytes = False

        if self.arch_struct:
            self.offset = arch_struct.offset
            self.type = self._load_type()
            self.subtype = self._load_subtype(self.type)
        else:
            self.offset = offset

        self.size = 0
        if self.offset == 0:
            f = self.macho_file.file_object
            old_file_position = f.tell()
            f.seek(0, os.SEEK_END)
            self.size = f.tell()
            f.seek(old_file_position)
        else:
            self.size = self.arch_struct.size

        self.byte_order = "little" if self.get_int_at(0, 4, "little") == MH_MAGIC_64 else "big"

    def patch(self, address, raw):
        self.macho_file.file.seek(self.offset + address)
        log.debug(f'Patched At: {hex(address)} ')
        log.debug(f'New Bytes: {str(raw)}')
        diff = self.size - (self.offset + address + len(raw))
        if diff < 0:
            data = self.full_bytes_for_slice()
            data = data[:address] + raw
            # log.debug(data)
            self.patched_bytes = data
            self.use_patched_bytes = True
            return
        old_raw = self.macho_file.file.read(len(raw))
        self.macho_file.file.seek(self.offset + address)
        log.debug(f'Old Bytes: {str(old_raw)}')
        self.macho_file.file.write(raw)
        self.macho_file.file.seek(0)

    def full_bytes_for_slice(self):
        if self.offset == 0:
            return self.macho_file.file[0:self.size]
        return self.macho_file.file[self.offset:+self.offset + self.arch_struct.size]

    def load_struct(self, addr: int, struct_type, endian="little"):
        size = struct_type.SIZE
        data = self.get_bytes_at(addr, size)

        struct = Struct.create_with_bytes(struct_type, data, endian)
        struct.off = addr

        return struct

    def get_int_at(self, addr, count, endian="little"):
        addr = addr + self.offset
        return int.from_bytes(self.macho_file.file[addr:addr + count], endian)

    def get_bytes_at(self, addr, count):
        addr = addr + self.offset
        return self.macho_file.file[addr:addr + count]

    def get_str_at(self, addr: int, count: int):
        addr = addr + self.offset
        return self.macho_file.file[addr:addr + count].decode().rstrip('\x00')

    def get_cstr_at(self, addr: int, limit: int = 0):
        addr = addr + self.offset
        self.macho_file.file.seek(addr)
        try:
            text = self.macho_file.file[addr:self.macho_file.file.find(b"\x00")].decode()
        except Exception as ex:
            log.debug(f'Failed to decode CString at raw {hex(addr)} off {hex(addr - self.offset)}')
            raise ex
        self.macho_file.file.seek(0)
        return text

    def decode_uleb128(self, readHead: int) -> Tuple[int, int]:

        value = 0
        shift = 0

        while True:

            byte = self.get_int_at(readHead, 1)

            value |= (byte & 0x7f) << shift

            readHead += 1
            shift += 7

            if (byte & 0x80) == 0:
                break

        return value, readHead

    def _load_type(self):
        cpu_type = self.arch_struct.cpu_type

        try:
            return CPUType(cpu_type)
        except KeyError:
            log.error(f'Unknown CPU Type ({hex(self.arch_struct.cputype)}) ({self.arch_struct}). File an issue at '
                      f'https://github.com/kritantadev/ktool')
            return CPUType.ARM

    def _load_subtype(self, cputype):
        cpu_subtype = self.arch_struct.cpu_subtype

        subtype_ret = None

        try:
            sub = CPU_SUBTYPES[cputype]
            return sub(cpu_subtype)
        except KeyError:
            log.error(f'Unknown CPU SubType ({hex(cpu_subtype)}) ({self.arch_struct}). File an issue at '
                      f'https://github.com/kritantadev/ktool')
            exit()
        return subtype_ret
