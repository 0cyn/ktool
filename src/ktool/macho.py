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
from typing import Tuple, Dict, Union, BinaryIO

from kmacho import *
from kmacho.structs import *
from ktool.exceptions import *
from ktool.util import log
mmap = None


class MachOFileType(Enum):
    FAT = 0
    THIN = 1


class BackingFile:
    def __init__(self, fp: Union[BinaryIO, BytesIO], use_mmaped_io=True):
        self.fp = fp
        if isinstance(fp, BytesIO):
            use_mmaped_io = False
            assert fp.getbuffer().nbytes > 0

        if hasattr(fp, 'name'):
            self.name = os.path.basename(fp.name)
        else:
            self.name = ''
        if use_mmaped_io:
            # noinspection PyBroadException
            try:
                assert not isinstance(fp, BytesIO)
                global mmap
                import mmap
                self.file = mmap.mmap(fp.fileno(), 0, access=mmap.ACCESS_COPY)
            except Exception:
                use_mmaped_io = False
            f = fp
            old_file_position = f.tell()
            f.seek(0, os.SEEK_END)
            self.size = f.tell()
            f.seek(old_file_position)

        if not use_mmaped_io:
            fp.seek(0)
            data = fp.read()
            self.file = bytearray(data)
            assert len(self.file) > 0
            self.size = len(self.file)

    def read_bytes(self, location, count):
        return bytes(self.file[location:location+count])

    def read_int(self, location, count):
        return int.from_bytes(self.read_bytes(location, count), "big")

    def write(self, location, data: bytes):
        data = bytearray(data)

        if isinstance(self.file, bytearray):
            count = len(data)
            for i in range(count):
                self.file[location+i] = data[i]

        else:
            # noinspection PyUnresolvedReferences
            assert isinstance(self.file, mmap.mmap)
            self.file.seek(location)
            self.file.write(data)
            self.file.seek(0)

    def close(self):
        self.fp.close()


class SlicedBackingFile:
    def __init__(self, backing_file: BackingFile, offset, size):
        self.file = bytearray(backing_file.read_bytes(offset, size))
        self.size = size
        self.name = backing_file.name

    def read_bytes(self, location, count):
        return bytes(self.file[location:location+count])

    def read_int(self, location, count):
        return int.from_bytes(self.read_bytes(location, count), "big")

    def write(self, location, data: bytes):
        count = len(data)
        for i in range(count):
            self.file[location + i] = data[i]


class MachOFile:
    def __init__(self, file, use_mmaped_io=True):
        self.file_object = file

        self.uses_mmaped_io = use_mmaped_io

        if hasattr(file, 'name'):
            self.filename = os.path.basename(file.name)
        else:
            self.filename = ''

        self.file = BackingFile(file, use_mmaped_io)

        self.slices = []

        self.magic = self.file.read_int(0, 4)

        if self.magic in [FAT_MAGIC, FAT_CIGAM]:
            self.type = MachOFileType.FAT
        elif self.magic in [MH_MAGIC, MH_CIGAM, MH_MAGIC_64, MH_CIGAM_64]:
            self.type = MachOFileType.THIN
        else:
            log.error(f'Bad Magic: {hex(self.magic)}')
            raise UnsupportedFiletypeException

        if self.type == MachOFileType.FAT:
            self.header: fat_header = self._load_struct(0, fat_header, "big")
            for off in range(0, self.header.nfat_archs):
                offset = fat_header.SIZE + (off * fat_arch.SIZE)
                arch_struct: fat_arch = self._load_struct(offset, fat_arch, "big")

                if not self.file.read_int(arch_struct.offset, 4) in [MH_MAGIC, MH_CIGAM, MH_MAGIC_64, MH_CIGAM_64]:
                    log.error(f'Slice {off} has bad magic {hex(self.file.read_int(arch_struct.offset, 4))}')
                    continue

                sliced_backing_file = SlicedBackingFile(self.file, arch_struct.offset, arch_struct.size)
                log.debug_more(str(arch_struct))
                self.slices.append(Slice(self, sliced_backing_file, arch_struct))
        else:
            self.slices.append(Slice(self, self.file, None))

    def _load_struct(self, address: int, struct_type, endian="little"):
        size = struct_type.SIZE
        data = self.file.read_bytes(address, size)

        struct = Struct.create_with_bytes(struct_type, data, endian)
        struct.off = address

        return struct

    def __del__(self):
        if hasattr(self, 'file') and hasattr(self.file, 'close'):
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

    def serialize(self):
        return {
            'command': self.cmd.serialize(),
            'name': self.name,
            'vm_address': self.vm_address,
            'file_address': self.file_address,
            'size': self.size
        }


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

    def serialize(self):
        segment = {
            'command': self.cmd.serialize(),
            'name': self.name,
            'vm_address': self.vm_address,
            'file_address': self.file_address,
            'size': self.size,
            'type': self.type.name,
        }
        sects = {}
        for section_name, sect in self.sections.items():
            sects[section_name] = sect.serialize()
        segment['sections'] = sects
        return segment

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
            except VMAddressingError:
                raise VMAddressingError(f'Address {hex(address)} ({hex(l_addr)}) not in VA Table or fallback map. (page: {hex(page_location)})')

    def map_pages(self, physical_addr, virtual_addr, size):
        if physical_addr % self.page_size != 0 or virtual_addr % self.page_size != 0 or size % self.page_size != 0:
            raise MachOAlignmentError
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

        raise VMAddressingError(f'Address {hex(vm_address)} couldn\'t be found in vm address set')

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
    def __init__(self, macho_file, sliced_backing_file: Union[BackingFile, SlicedBackingFile], arch_struct: fat_arch=None, offset=0):
        self.file = sliced_backing_file
        self.macho_file = macho_file
        self.arch_struct: fat_arch = arch_struct

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

        self.size = sliced_backing_file.size

        # noinspection PyArgumentList
        self.byte_order = "little" if self.get_int_at(0, 4, "little") in [MH_MAGIC, MH_MAGIC_64] else "big"

        self._cstring_cache = {}

    def patch(self, address: int, raw: bytes):
        log.debug_tm(f'Wrote {str(raw)} @ {address}')
        self.file.write(address, raw)
        assert self.file.read_bytes(address, len(raw)) == raw

    def full_bytes_for_slice(self):
        return bytes(self.file.read_bytes(0, self.file.size))

    def find(self, pattern: Union[str, bytes]):
        if isinstance(pattern, str):
            pattern = pattern.encode('utf-8')

        return self.file.file.find(pattern)

    def load_struct(self, addr: int, struct_type, endian="little"):
        size = struct_type.SIZE
        data = self.get_bytes_at(addr, size)

        struct = Struct.create_with_bytes(struct_type, data, endian)
        struct.off = addr

        return struct

    def get_int_at(self, addr: int, count: int, endian="little"):
        return int.from_bytes(self.file.read_bytes(addr, count), endian)

    def get_bytes_at(self, addr: int, count: int):
        return self.file.read_bytes(addr, count)

    def get_str_at(self, addr: int, count: int, force=False) -> str:
        if force:
            data = self.file.file[addr:addr + count]
            string = ""

            for ch in data:
                try:
                    string += bytes(ch).decode()
                except UnicodeDecodeError:
                    string += "?"
            return string

        return self.file.file[addr:addr + count].decode().rstrip('\x00')

    def get_cstr_at(self, addr: int, limit: int = 0):
        ea = addr

        if addr in self._cstring_cache:
            return self._cstring_cache[addr]

        count = 0
        while True:
            if self.file.file[ea] != 0:
                count += 1
                ea += 1
            else:
                break

        text = self.get_str_at(addr, count)

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
