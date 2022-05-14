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
from enum import Enum
from io import BytesIO
from typing import Tuple, Dict, Union, BinaryIO, List

from kmacho import *
from kmacho.base import Constructable
from kmacho.structs import *
from kmacho.load_commands import SegmentLoadCommand
from ktool.exceptions import *
from ktool.util import log, ignore

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
        self.file_size = cmd.filesize
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


class MachOImageHeader(Constructable):
    """
    This class represents the Mach-O Header
    It contains the basic header info along with all load commands within it.

    It doesn't handle complex abstraction logic, it simply loads in the load commands as their raw structs
    """

    @classmethod
    def from_image(cls, macho_slice, offset=0) -> 'ImageHeader':

        image_header = cls()

        header: mach_header = macho_slice.load_struct(offset, mach_header)

        if header.magic == MH_MAGIC_64:
            header: mach_header_64 = macho_slice.load_struct(offset, mach_header_64)
            image_header.is64 = True

        raw = header.raw

        image_header.filetype = MH_FILETYPE(header.filetype)

        for flag in MH_FLAGS:
            if header.flags & flag.value:
                image_header.flags.append(flag)

        offset += header.SIZE

        load_commands = []

        for i in range(1, header.loadcnt + 1):
            cmd = macho_slice.get_int_at(offset, 4)
            cmd_size = macho_slice.get_int_at(offset + 4, 4)

            cmd_raw = macho_slice.get_bytes_at(offset, cmd_size)
            try:
                load_cmd = Struct.create_with_bytes(LOAD_COMMAND_MAP[LOAD_COMMAND(cmd)], cmd_raw)
                load_cmd.off = offset
            except ValueError as ex:
                if not ignore.MALFORMED:
                    log.error(f'Bad Load Command at {hex(offset)} index {i-1}\n        {hex(cmd)} - {hex(cmd_size)}')

                unk_lc = macho_slice.load_struct(offset, unk_command)
                load_cmd = unk_lc
            except KeyError as ex:
                if not ignore.MALFORMED:
                    log.error()
                    log.error(f'Load Command {str(LOAD_COMMAND(cmd))} doesn\'t have a mapped struct type')
                    log.error('*Please* file an issue on the github @ https://github.com/cxnder/ktool')
                    log.error()
                    log.error(f'Run with the -f flag to hide this warning.')
                    log.error()
                unk_lc = macho_slice.load_struct(offset, unk_command)
                load_cmd = unk_lc

            load_commands.append(load_cmd)
            raw += cmd_raw
            offset += load_cmd.cmdsize

        image_header.raw = raw
        image_header.dyld_header = header
        image_header.load_commands = load_commands

        return image_header

    @classmethod
    def from_values(cls, is_64: bool,  cpu_type, cpu_subtype, filetype: MH_FILETYPE, flags: List[MH_FLAGS], load_commands: List):

        if isinstance(cpu_type, int):
            cpu_type = CPUType(cpu_type)
        if isinstance(cpu_subtype, int):
            cpu_subtype = CPU_SUBTYPES[cpu_type](cpu_subtype)
        if isinstance(filetype, int):
            filetype = MH_FILETYPE(filetype)

        image_header = cls()

        struct_type = mach_header_64 if is_64 else mach_header

        full_load_cmds_raw = bytearray()

        lcs = []

        lc_count = 0

        off = struct_type.SIZE

        for lc in load_commands:

            if issubclass(lc.__class__, Struct):
                assert len(lc.raw) == lc.__class__.SIZE
                assert hasattr(lc, 'cmdsize')
                lc.off = off
                lcs.append(lc)
                full_load_cmds_raw += bytearray(lc.raw)
                lc_count += 1
                off += lc.cmdsize

            elif isinstance(lc, bytes) or isinstance(lc, bytearray):
                full_load_cmds_raw += bytearray(lc)

            elif isinstance(lc, Segment) or isinstance(lc, SegmentLoadCommand):
                lc.cmd.off = off
                lcs.append(lc.cmd)
                dat = bytearray(lc.cmd.raw)
                lc_count += 1
                for sect in lc.sections.values():
                    dat += sect.cmd.raw
                assert len(dat) == lc.cmd.cmdsize, f'{lc.cmd}, \n[{",".join([str(i.cmd) for i in lc.sections.values()])}]'
                full_load_cmds_raw += dat
                off += lc.cmd.cmdsize

        embedded_flag = 0
        for flag in flags:
            embedded_flag |= flag.value

        if is_64:
            header = Struct.create_with_values(struct_type, [MH_MAGIC_64, cpu_type.value, cpu_subtype.value, filetype.value, lc_count, len(full_load_cmds_raw), embedded_flag, 0])
        else:
            header = Struct.create_with_values(struct_type, [MH_MAGIC, cpu_type.value, cpu_subtype.value, filetype.value, lc_count, len(full_load_cmds_raw), embedded_flag])

        image_header.dyld_header = header

        image_header.filetype = MH_FILETYPE(header.filetype)

        for flag in MH_FLAGS:
            if header.flags & flag.value:
                image_header.flags.append(flag)

        image_header.load_commands = lcs

        image_header.raw = bytearray(header.raw) + full_load_cmds_raw

        return image_header

    def __str__(self):
        return f'MachO Header - 64 bit VM: {self.is64} | File Type: {self.filetype} | Flags: {self.flags} | Load Cmd Count: {len(self.load_commands)}'

    def __init__(self):
        self.is64 = False
        self.dyld_header: Union[mach_header, mach_header_64, None] = None
        self.filetype = MH_FILETYPE(0)
        self.flags: List[MH_FLAGS] = []
        self.load_commands = []
        self.raw = bytearray()

    def serialize(self):
        return {
            'filetype': self.filetype.name,
            'flags': [flag.name for flag in self.flags],
            'is_64_bit': self.is64,
            'dyld_header': self.dyld_header.serialize(),
            'load_commands': [cmd.serialize() for cmd in self.load_commands]
        }

    def raw_bytes(self) -> bytes:
        return self.raw

    def insert_load_cmd(self, load_command, index=-1, suffix=None):
        image_header = self

        flags = image_header.flags
        filetype = image_header.filetype
        cpu_type = self.dyld_header.cpu_type
        cpu_subtype = self.dyld_header.cpu_subtype

        load_command_items = []

        current_lc_index = 0

        for command in self.load_commands:
            if current_lc_index == index:
                if isinstance(load_command, SegmentLoadCommand):
                    load_command_items.append(load_command)
                elif isinstance(load_command, dylib_command):
                    assert suffix is not None, "Inserting dylib_command requires suffix"
                    encoded = suffix.encode('utf-8') + b'\x00'
                    while (len(encoded) + load_command.__class__.SIZE) % 8 != 0:
                        encoded += b'\x00'
                    cmdsize = load_command.__class__.SIZE + len(encoded)
                    load_command.cmdsize = cmdsize
                    load_command_items.append(load_command)
                    load_command_items.append(encoded)
                elif load_command.__class__ in [dylinker_command, build_version_command]:
                    load_command_items.append(load_command)
                    assert suffix is not None, f"Inserting {load_command.__class__.__name__} currently requires a " \
                                               f"byte suffix "
                    load_command_items.append(suffix)

            if isinstance(command, segment_command) or isinstance(command, segment_command_64):
                sects = []
                sect_data = self.raw[command.off + command.__class__.SIZE:]
                struct_class = section_64 if isinstance(command, segment_command_64) else section
                for i in range(command.nsects):
                    sects.append(Section(None, Struct.create_with_bytes(struct_class, sect_data[i*struct_class.SIZE:(i+1)*struct_class.SIZE], "little")))
                seg = SegmentLoadCommand.from_values(isinstance(command, segment_command_64), command.segname,
                                                     command.vmaddr, command.vmsize, command.fileoff, command.filesize,
                                                     command.maxprot, command.initprot, command.flags, sects)
                load_command_items.append(seg)
            elif isinstance(command, dylib_command):
                _suffix = ""
                i = 0
                while self.raw[command.off + command.__class__.SIZE + i] != 0:
                    _suffix += chr(self.raw[command.off + command.__class__.SIZE + i])
                    i += 1
                encoded = _suffix.encode('utf-8') + b'\x00'
                while (len(encoded) + command.__class__.SIZE) % 8 != 0:
                    encoded += b'\x00'
                load_command_items.append(command)
                load_command_items.append(encoded)
            elif command.__class__ in [dylinker_command, build_version_command]:
                load_command_items.append(command)
                actual_size = command.cmdsize
                dat = self.raw[command.off + command.SIZE:(command.off + command.SIZE) + actual_size - command.SIZE]
                load_command_items.append(dat)
            else:
                load_command_items.append(command)
            current_lc_index += 1

        if index == -1:
            if isinstance(load_command, SegmentLoadCommand):
                load_command_items.append(load_command)
            elif isinstance(load_command, dylib_command):
                load_command_items.append(load_command)
                assert suffix is not None, "Inserting dylib_command requires suffix"
                encoded = suffix.encode('utf-8') + b'\x00'
                while (len(encoded) + load_command.__class__.SIZE) % 8 != 0:
                    encoded += b'\x00'
                cmdsize = load_command.__class__.SIZE + len(encoded)
                load_command.cmdsize = cmdsize
                load_command_items.append(encoded)
            elif load_command.__class__ in [dylinker_command, build_version_command]:
                load_command_items.append(load_command)
                assert suffix is not None, f"Inserting {load_command.__class__.__name__} currently requires a byte suffix"
                load_command_items.append(suffix)

        return MachOImageHeader.from_values(self.is64, cpu_type, cpu_subtype, filetype, flags, load_command_items)

    def remove_load_command(self, index):

        image_header = self

        flags = image_header.flags
        filetype = image_header.filetype
        cpu_type = self.dyld_header.cpu_type
        cpu_subtype = self.dyld_header.cpu_subtype

        load_command_items = []
        current_lc_index = 0

        for command in self.load_commands:
            if current_lc_index == index:
                current_lc_index += 1
                continue

            if isinstance(command, segment_command) or isinstance(command, segment_command_64):
                sects = []
                sect_data = self.raw[command.off + command.__class__.SIZE:]
                struct_class = section_64 if isinstance(command, segment_command_64) else section
                for i in range(command.nsects):
                    sects.append(Section(None, Struct.create_with_bytes(struct_class, sect_data[i*struct_class.SIZE:(i+1)*struct_class.SIZE], "little")))
                seg = SegmentLoadCommand.from_values(isinstance(command, segment_command_64), command.segname,
                                                     command.vmaddr, command.vmsize, command.fileoff, command.filesize,
                                                     command.maxprot, command.initprot, command.flags, sects)
                load_command_items.append(seg)
            elif isinstance(command, dylib_command):
                suffix = ""
                i = 0
                while self.raw[command.off + command.__class__.SIZE + i] != 0:
                    suffix += chr(self.raw[command.off + command.__class__.SIZE + i])
                    i += 1
                encoded = suffix.encode('utf-8') + b'\x00'
                while (len(encoded) + command.__class__.SIZE) % 8 != 0:
                    encoded += b'\x00'
                load_command_items.append(command)
                load_command_items.append(encoded)
            elif command.__class__ in [dylinker_command, build_version_command]:
                load_command_items.append(command)
                actual_size = command.cmdsize
                dat = self.raw[command.off + command.SIZE:(command.off + command.SIZE) + actual_size - command.SIZE]
                load_command_items.append(dat)
            else:
                load_command_items.append(command)
            current_lc_index += 1

        return MachOImageHeader.from_values(self.is64, cpu_type, cpu_subtype, filetype, flags, load_command_items)


class PlatformType(Enum):
    MACOS = 1
    IOS = 2
    TVOS = 3
    WATCHOS = 4
    BRIDGE_OS = 5
    MAC_CATALYST = 6
    IOS_SIMULATOR = 7
    TVOS_SIMULATOR = 8
    WATCHOS_SIMULATOR = 9
    DRIVER_KIT = 10
    UNK = 64


class ToolType(Enum):
    CLANG = 1
    SWIFT = 2
    LD = 3
