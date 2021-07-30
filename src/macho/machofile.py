import mmap
from enum import Enum

from .slice import Slice
from .structs import *

"""
MachO  

CA FE BA BE - FAT Magic
FE ED FA CE - Mach Header Magic
CF FA ED FE 
CE FA ED FE - Little Endian Mach Header Magic

"""


class MachOFileType(Enum):
    FAT = 0
    THIN = 1


class MachOFile:
    def __init__(self, file):
        self.file = mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ)
        self.slices = []
        self.magic = self._get_at(0, 4)
        self.type = self._load_filetype()

        if self.type == MachOFileType.FAT:
            self.header: fat_header = self._load_struct(0, fat_header_t, "big")
            for off in range(0, self.header.nfat_archs):
                offset = sizeof(fat_header_t) + (off * sizeof(fat_arch_t))
                arch_struct = self._load_struct(offset, fat_arch_t, "big")
                self.slices.append(Slice(self, arch_struct))
        else:
            self.slices.append(Slice(self, None))

    def _load_filetype(self):
        if self.magic == 0xCAFEBABE:
            return MachOFileType.FAT
        elif self.magic == 0xCFFAEDFE or self.magic == 0xCEFAEDFE:
            return MachOFileType.THIN

    def _load_struct(self, addr: int, struct_type: struct, endian="little"):
        sizeOf = sum(struct_type.sizes)
        fieldNames = list(struct_type.struct.__dict__['_fields'])  # unimportant?
        fields = [addr]
        ea = addr

        for field in struct_type.sizes:
            field_addr = ea
            fields.append(self._get_at(field_addr, field, endian))
            ea += field

        if len(fields) != len(fieldNames):
            raise ValueError(
                f'Field-Fieldname count mismatch in load_struct for {struct.struct.__doc__}.\nCheck Fields and Size Array.')

        return struct_type.struct._make(fields)

    # noinspection PyTypeChecker
    def _get_at(self, addr, count, endian="big"):
        return int.from_bytes(self.file[addr:addr + count], endian)

    def __del__(self):
        self.file.close()
