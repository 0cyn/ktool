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

import os
from collections import namedtuple
from enum import Enum
from io import BytesIO
from typing import Tuple, Dict, Union

from kmacho import *
from kmacho.structs import *
from ktool.exceptions import *
from ktool.util import log
mmap = None


class MachOFileType(Enum):
    FAT = 0
    THIN = 1


class MachOFile:
    def __init__(self, file, use_mmaped_io=True, from_base=0):
        self.file_object = file

        self.uses_mmaped_io = use_mmaped_io

        if hasattr(file, 'name'):
            self.filename = os.path.basename(file.name)
        else:
            self.filename = ''

        if use_mmaped_io:
            assert not isinstance(file, BytesIO)
            global mmap
            import mmap
            try:
                self.file = mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_COPY)
                self._get_bytes_at = self._mmaped_get_bytes_at
                self._get_at = self._mmaped_get_at
            except:
                log.warning("mmap Failed - Swapped to fallback IO method")
                self.uses_mmaped_io = False
                log.debug_tm("mmapped IO disabled")
                self.file = file

                self.file_data = bytearray(file.read())
                log.debug_tm("BIO Buffer Size: " + hex(len(self.file_data)))
                self._get_bytes_at = self._bio_get_bytes_at
                self._get_at = self._bio_get_at

        else:
            log.debug_tm("mmapped IO disabled")
            self.file = file

            self.file_data = bytearray(file.read())
            log.debug_tm("BIO Buffer Size: " + hex(len(self.file_data)))
            self._get_bytes_at = self._bio_get_bytes_at
            self._get_at = self._bio_get_at

        self.slices = []
        # noinspection PyTypeChecker
        self.magic = self._get_at(0, 4)
        self.type = self._load_filetype()

        if self.type == MachOFileType.FAT:
            self.header: fat_header = self._load_struct(0, fat_header, "big")
            for off in range(0, self.header.nfat_archs):
                offset = fat_header.SIZE + (off * fat_arch.SIZE)
                arch_struct = self._load_struct(offset, fat_arch, "big")
                log.debug_more(arch_struct)
                self.slices.append(Slice(self, arch_struct))
        else:
            self.slices.append(Slice(self, None))

    def _load_filetype(self) -> MachOFileType:
        if self.magic == FAT_MAGIC or self.magic == FAT_CIGAM:
            return MachOFileType.FAT
        elif self.magic == MH_MAGIC or self.magic == MH_CIGAM or self.magic == MH_MAGIC_64 or self.magic == MH_CIGAM_64:
            return MachOFileType.THIN
        else:
            log.debug(f'Bad Magic: {hex(self.magic)}')
            raise UnsupportedFiletypeException

    def _load_struct(self, address: int, struct_type, endian="little"):
        size = struct_type.SIZE
        data = self._get_bytes_at(address, size)

        struct = Struct.create_with_bytes(struct_type, data, endian)
        struct.off = address

        return struct

    def _bio_get_bytes_at(self, address: int, count: int):
        return bytes(self.file_data[address:address + count])

    def _mmaped_get_bytes_at(self, address: int, count: int):
        return self.file[address: address + count]

    def _bio_get_at(self, address: int, count: int, endian="big"):
        return int.from_bytes(self._bio_get_bytes_at(address, count), endian)

    # noinspection PyTypeChecker
    def _mmaped_get_at(self, address: int, count: int, endian="big") -> int:
        return int.from_bytes(self.file[address:address + count], endian)

    def __del__(self):
        self.file.close()


class Section:
    """

    """

    def __init__(self, segment, cmd):
        self.cmd = cmd
        self.segment = segment
        self.name = cmd.sectname
        self.vm_address = cmd.addr
        self.file_address = cmd.offset
        self.size = cmd.size


class Segment:
    """

    """

    def __init__(self, image, cmd):
        self.image = image
        self.is64 = isinstance(cmd, segment_command_64)
        self.cmd = cmd
        self.vm_address = cmd.vmaddr
        self.file_address = cmd.fileoff
        self.size = cmd.vmsize
        self.name = cmd.segname

        self.sections: Dict[str, Section] = self._process_sections()

        self.type = SectionType(S_FLAGS_MASKS.SECTION_TYPE & self.cmd.flags)

    def __str__(self):
        return f'Segment {self.name} at {hex(self.vm_address)}\n'

    def _process_sections(self) -> Dict[str, Section]:
        sections = {}
        ea = self.cmd.off + self.cmd.SIZE

        for sect in range(0, self.cmd.nsects):
            sect = self.image.load_struct(ea, section_64 if self.is64 else section)
            sect = Section(self, sect)
            sections[sect.name] = sect
            ea += section_64.SIZE if self.is64 else section.SIZE

        return sections


class VM:
    """
    New Virtual Address translation based on actual VM -> physical pages

    """

    def __init__(self, page_size):
        self.page_size = page_size
        self.page_size_bits = (self.page_size - 1).bit_length()
        self.page_table = {}
        self.tlb = {}
        self.vm_base_addr = None
        self.dirty = False

        self.fallback: Union[None, MisalignedVM] = None

        self.detag_kern_64 = False
        self.detag_64 = False

    def vm_check(self, address):
        try:
            self.translate(address)
            return True
        except ValueError:
            return False

    def add_segment(self, segment: Segment):
        if segment.name == '__PAGEZERO':
            return

        self.fallback.add_segment(segment)

        if self.vm_base_addr is None:
            self.vm_base_addr = segment.vm_address
        if self.dirty or segment.vm_address % self.page_size != 0:
            self.dirty = True
            log.warn(f'MachO File could not be aligned.')
            raise MachOAlignmentError
        self.map_pages(segment.file_address, segment.vm_address, segment.size)

    def translate(self, address) -> int:

        l_addr = address

        if self.detag_kern_64:
            address = address | (0xFFFF << 12*4)

        if self.detag_64:
            address = address & 0xFFFFFFFFF

        try:
            return self.tlb[address]
        except KeyError:
            pass

        page_offset = address & self.page_size - 1
        page_location = address >> self.page_size_bits
        try:
            phys_page = self.page_table[page_location]
            physical_location = phys_page + page_offset
            self.tlb[address] = physical_location
            return physical_location
        except KeyError:

            log.info(f'Address {hex(address)} not mapped, attempting fallback')

            try:
                return self.fallback.translate(address)
            except ValueError:
                raise ValueError(f'Address {hex(address)} ({hex(l_addr)}) not in VA Table or fallback map. (page: {hex(page_location)})')

    def map_pages(self, physical_addr, virtual_addr, size):
        for i in range(size // self.page_size):
            self.page_table[virtual_addr + (i * self.page_size) >> self.page_size_bits] = physical_addr + (
                        i * self.page_size)


vm_obj = namedtuple("vm_obj", ["vmaddr", "vmend", "size", "fileaddr", "name"])


class MisalignedVM:
    """
    This is the manual backup if the image cant be mapped to 16/4k segments
    """

    def __init__(self, macho_slice):
        self.slice = macho_slice

        self.detag_kern_64 = False
        self.detag_64 = False

        self.map = {}
        self.stats = {}
        self.vm_base_addr = 0
        self.sorted_map = {}
        self.cache = {}

    def vm_check(self, vm_address):
        try:
            self.translate(vm_address)
            return True
        except ValueError:
            return False

    def translate(self, vm_address: int) -> int:

        if self.detag_kern_64:
            vm_address = vm_address | (0xFFFF << 12*4)

        if self.detag_64:
            vm_address = vm_address & 0xFFFFFFFFF

        if vm_address in self.cache:
            return self.cache[vm_address]

        for o in self.map.values():
            # noinspection PyChainedComparisons
            if vm_address >= o.vmaddr and o.vmend >= vm_address:
                file_addr = o.fileaddr + vm_address - o.vmaddr
                self.cache[vm_address] = file_addr
                return file_addr

        raise ValueError(f'Address {hex(vm_address)} couldn\'t be found in vm address set')

    def add_segment(self, segment: Segment):
        if segment.file_address == 0 and segment.size != 0:
            self.vm_base_addr = segment.vm_address

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
    def __init__(self, macho_file: MachOFile, arch_struct: fat_arch = None, offset=0):
        self.macho_file: MachOFile = macho_file
        self.arch_struct: fat_arch = arch_struct

        if macho_file.uses_mmaped_io:
            self.get_int_at = self._mmap_get_int_at
            self.get_bytes_at = self._mmap_get_bytes_at
            self.get_str_at = self._mmap_get_str_at
            self.get_cstr_at = self._mmap_get_cstr_at
            self.find = self._mmap_find
        else:
            self.get_int_at = self._bio_get_int_at
            self.get_bytes_at = self._bio_get_bytes_at
            self.get_str_at = self._bio_get_str_at
            self.get_cstr_at = self._bio_get_cstr_at
            self.find = self._bio_find

        self.patches = {}

        self.patched_bytes = b''
        self.use_patched_bytes = False

        if self.arch_struct:
            self.offset = arch_struct.offset
            self.type = self._load_type()
            self.subtype = self._load_subtype(self.type)
        else:
            self.offset = offset
            hdr = Struct.create_with_bytes(mach_header, self.get_bytes_at(0, 28))
            self.arch_struct = Struct.create_with_values(fat_arch, [hdr.cpu_type, hdr.cpu_subtype, 0, 0, 0])
            self.type = self._load_type()
            self.subtype = self._load_subtype(self.type)

        self.size = 0

        if self.offset == 0:
            f = self.macho_file.file_object
            old_file_position = f.tell()
            f.seek(0, os.SEEK_END)
            self.size = f.tell()
            f.seek(old_file_position)
        else:
            self.size = self.arch_struct.size

        # noinspection PyArgumentList
        self.byte_order = "little" if self.get_int_at(0, 4, "little") in [MH_MAGIC, MH_MAGIC_64] else "big"

        self._cstring_cache = {}

    def patch(self, address: int, raw: bytes):
        if self.macho_file.uses_mmaped_io:
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
        else:
            self.patches[address] = raw

    def full_bytes_for_slice(self):
        if self.macho_file.uses_mmaped_io:
            if self.offset == 0:
                return self.macho_file.file[0:self.size]
            return self.macho_file.file[self.offset:self.offset + self.arch_struct.size]

        else:
            data = self.macho_file.file_data[self.offset:self.offset+self.size]
            for patch_loc in self.patches:
                i = 0
                patch_data = self.patches[patch_loc]
                for byte in patch_data:
                    data[patch_loc + i] = byte
                    i += 1
            return data

    def _mmap_find(self, pattern: Union[str, bytes]):
        if isinstance(pattern, str):
            pattern = pattern.encode('utf-8')
        addr = self.macho_file.file[self.offset:self.offset+self.size].find(pattern)
        if addr == -1:
            return -1
        return addr + self.offset

    def _bio_find(self, pattern: Union[str, bytes]):
        addr = self.macho_file.file_data[self.offset:self.offset+self.size].find(pattern)
        if addr == -1:
            return -1
        return addr + self.offset

    def load_struct(self, addr: int, struct_type, endian="little"):
        size = struct_type.SIZE
        data = self.get_bytes_at(addr, size)

        struct = Struct.create_with_bytes(struct_type, data, endian)
        struct.off = addr

        return struct

    def _mmap_get_int_at(self, addr: int, count: int, endian="little"):
        addr = addr + self.offset

        return int.from_bytes(self.macho_file.file[addr:addr + count], endian)

    def _bio_get_int_at(self, addr: int, count: int, endian="little"):
        return int.from_bytes(self._bio_get_bytes_at(addr, count), endian)

    def _mmap_get_bytes_at(self, addr: int, count: int):
        addr = addr + self.offset

        return self.macho_file.file[addr:addr + count]

    # noinspection PyUnusedLocal
    def _bio_get_bytes_at(self, addr: int, count: int, endian="little"):
        addr = addr + self.offset

        return self.macho_file.file_data[addr:addr + count]

    def _mmap_get_str_at(self, addr: int, count: int) -> str:
        addr = addr + self.offset

        return self.macho_file.file[addr:addr + count].decode().rstrip('\x00')

    def _bio_get_str_at(self, addr: int, count: int):
        addr = addr + self.offset

        self.macho_file.file.seek(addr)
        data = self.macho_file.file.read(count)

        return data.decode().rstrip('\x00')

    # noinspection PyUnusedLocal
    def _mmap_get_cstr_at(self, addr: int, limit: int = 0) -> str:
        addr = addr + self.offset

        if addr in self._cstring_cache:
            return self._cstring_cache[addr]

        try:
            self.macho_file.file.seek(addr)
        except ValueError as ex:
            log.error(f'OOB Seek to {hex(addr)} in slice {hex(self.offset)} size:{hex(self.size)}')
            raise ex

        try:
            text = self.macho_file.file[addr:self.macho_file.file.find(b"\x00")].decode()
        except Exception as ex:
            log.debug(f'Failed to decode CString at raw {hex(addr)} off {hex(addr - self.offset)}')
            raise ex

        self.macho_file.file.seek(0)
        self._cstring_cache[addr] = text

        return text

    # noinspection PyUnusedLocal
    def _bio_get_cstr_at(self, addr: int, limit: int = 0):
        # this function will likely be a bit slower than the mmaped one, and will probably bottleneck things, oh well.
        # I'm unsure if there's any possible faster approach than this.
        ea = addr + self.offset

        if addr in self._cstring_cache:
            return self._cstring_cache[addr]

        cnt = 0
        while True:
            try:
                if self.macho_file.file_data[ea] != 0:
                    cnt += 1
                    ea += 1
                else:
                    break

            except IndexError as ex:
                log.error(f'ea: {hex(ea)} // buffer len: {hex(len(self.macho_file.file_data))}')
                raise ex

        text = self._bio_get_bytes_at(addr, cnt).decode()

        self._cstring_cache[addr] = text

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

    def _load_type(self) -> CPUType:
        cpu_type = self.arch_struct.cpu_type

        return CPUType(cpu_type)

    def _load_subtype(self, cputype: CPUType):
        cpu_subtype = self.arch_struct.cpu_subtype
        cpu_subtype = cpu_subtype & 0xFFFF

        try:
            sub = CPU_SUBTYPES[cputype]
            return sub(cpu_subtype)

        except KeyError:
            log.error(f'Unknown CPU SubType ({hex(cpu_subtype)}) ({self.arch_struct}). File an issue at '
                      f'https://github.com/cxnder/ktool')

            return CPUSubTypeARM64.ALL
