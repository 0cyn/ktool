from enum import Enum
from typing import Tuple

from .library import Library
from .structs import *


class CPUType(Enum):
    X86 = 0
    X86_64 = 1
    ARM = 2
    ARM64 = 3


class CPUSubType(Enum):
    X86_64_ALL = 0
    X86_64_H = 1
    ARMV7 = 2
    ARMV7S = 3
    ARM64_ALL = 4
    ARM64_V8 = 5


class Slice:
    def __init__(self, macho_file, arch_struct: fat_arch, offset=0):
        self.macho_file = macho_file
        self.arch_struct = arch_struct

        if self.arch_struct:
            self.offset = arch_struct.offset
            self.type = self._load_type()
            self.subtype = self._load_subtype()
        else:
            self.offset = offset

        self.library = self.load_library()
    def load_library(self):
        return Library(self)

    def load_struct(self, addr: int, struct_type: struct, endian="little"):
        sizeOf = sum(struct_type.sizes)
        fieldNames = list(struct_type.struct.__dict__['_fields'])  # unimportant?
        fields = [addr]
        ea = addr

        for field in struct_type.sizes:
            field_addr = ea
            fields.append(self.get_at(field_addr, field, endian))
            ea += field

        if len(fields) != len(fieldNames):
            raise ValueError(
                f'Field-Fieldname count mismatch in load_struct for {struct.struct.__doc__}.\nCheck Fields and Size Array.')
        return struct_type.struct._make(fields)

    def get_at(self, addr, count, endian="little"):
        addr = addr + self.offset
        return int.from_bytes(self.macho_file.file[addr:addr + count], endian)

    def get_str_at(self, addr: int, count: int):
        addr = addr + self.offset
        return self.macho_file.file[addr:addr + count].decode().rstrip('\x00')

    def get_cstr_at(self, addr: int, limit: int = 0):
        addr = addr + self.offset
        ret = ""
        ea: int = addr
        try:
            while True:
                if limit != 0:
                    if ea - addr >= limit:
                        break
                if ea - addr >= 20000:
                    print(f'Endless String fallback; addr={addr}')
                    print(ret)
                    raise ValueError("Endless String Possibly Detected")
                char = self.macho_file.file[ea:ea + 1].decode()
                if char == '\x00':
                    if len(ret) > 0:
                        break
                    else:
                        ea += 1
                else:
                    ret = ret + char
                    ea += 1
        except UnicodeError as ex:
            raise UnicodeError(f'Bad string; addr={hex(addr)} limit={limit} ea={hex(ea)} ret={ret}')

        return ret

    def decode_uleb128(self, readHead: int) -> Tuple[int, int]:
        """Read a Uleb128 value.
        Args:
            buffer: The data source.
            readHead: The initial offset to read from.
        Returns:
            A tuple containing the result and the new read head.
        """

        value = 0
        shift = 0

        while True:

            byte = self.get_at(readHead, 1)

            value |= (byte & 0x7f) << shift

            readHead += 1
            shift += 7

            if (byte & 0x80) == 0:
                break

        return (value, readHead)

    def _load_type(self):
        type = self.arch_struct.cputype

        if type & 0xF0000000 != 0:
            if type & 0xF == 0x7:
                return CPUType.X86_64
            elif type & 0xF == 0xC:
                return CPUType.ARM64
        else:
            if type & 0xF == 0x7:
                return CPUType.X86
            elif type & 0xF == 0xC:
                return CPUType.ARM

        raise ValueError(f'Unknown CPU Type ({hex(self.arch_struct.cputype)}) ({self.arch_struct})')

    def _load_subtype(self):
        type = self.arch_struct.cpusubtype

        if type == 3:
            return CPUSubType.X86_64_ALL
        elif type == 8:
            return CPUSubType.X86_64_H
        elif type == 9:
            return CPUSubType.ARMV7
        elif type == 11:
            return CPUSubType.ARMV7S
        elif type == 0:
            return CPUSubType.ARM64_ALL
        elif type == 1:
            return CPUSubType.ARM64_V8

        raise ValueError(f'Unknown CPU SubType ({hex(type)})')
