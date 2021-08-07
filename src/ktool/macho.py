import mmap
from collections import namedtuple
from enum import Enum
from typing import Tuple

from ktool.structs import fat_header, fat_header_t, fat_arch_t, segment_command_64_t, section_64_t, sizeof, struct


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
        field_names = list(struct_type.struct.__dict__['_fields'])  # unimportant?
        fields = [addr]
        ea = addr

        for field in struct_type.sizes:
            field_addr = ea
            fields.append(self._get_at(field_addr, field, endian))
            ea += field

        if len(fields) != len(field_names):
            raise ValueError(
                f'Field-Fieldname count mismatch in load_struct for {struct.struct.__doc__}.\nCheck Fields and Size '
                f'Array.')

        return struct_type.struct._make(fields)

    # noinspection PyTypeChecker
    def _get_at(self, addr, count, endian="big"):
        return int.from_bytes(self.file[addr:addr + count], endian)

    def __del__(self):
        self.file.close()


class Segment:
    """


    segment_command_64:
    ["off", "cmd", "cmdsize", "segname", "vmaddr", "vmsize", "fileoff", "filesize",
        "maxprot", "initprot", "nsects", "flags"]
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

    def _process_sections(self):
        sections = {}
        ea = self.cmd.off + sizeof(segment_command_64_t)

        for section in range(0, self.cmd.nsects):
            sect = self.library.load_struct(ea, section_64_t)
            section = Section(self, sect)
            sections[section.name] = section
            ea += sizeof(section_64_t)

        ea += sizeof(segment_command_64_t)
        return sections


class Section:
    """


    section_64
     ["off",
     "sectname",
     "segname",
     "addr", VM ADDRESS
     "size", SIZE ON BOTH
     "offset", FILE ADDRESS
     "align", "reloff", "nreloc", "flags", "void1", "void2", "void3"]
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
    Virtual Memory is the location "in memory" where the library/bin, etc will be accessed when ran
    This is not where it actually sits in memory at runtime; it will be slid, but the program doesnt know and doesnt care
    The slid address doesnt matter to us either, we only care about the addresses the rest of the file cares about

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
            ret += f'{key.ljust(16)}  ||  Start: 0x{hex(obj.vmaddr)[2:].zfill(9)}  |  End: 0x{hex(obj.vmend)[2:].zfill(9)}  |  Size: 0x{hex(obj.size)[2:].zfill(9)}  |  Slice ' \
                   f'Offset:  0x{hex(obj.fileaddr)[2:].zfill(9)}  ||  File Offset: 0x{hex(obj.fileaddr + self.slice.offset)[2:].zfill(9)}\n '
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
        if vm_address in self.cache:
            return self.cache[vm_address]
        if segment_name is not None:
            o = self.map[segment_name]

            # noinspection PyChainedComparisons
            if vm_address >= o.vmaddr and o.vmend >= vm_address:
                faddr = o.fileaddr + vm_address - o.vmaddr
                self.cache[vm_address] = faddr
                return faddr
            else:
                try:
                    o = self.map['__EXTRA_OBJC']
                    # noinspection PyChainedComparisons
                    if vm_address >= o.vmaddr and o.vmend >= vm_address:
                        faddr = o.fileaddr + vm_address - o.vmaddr
                        self.cache[vm_address] = faddr
                        return faddr
                except:
                    for o in self.map.values():
                        # noinspection PyChainedComparisons
                        if vm_address >= o.vmaddr and o.vmend >= vm_address:
                            # self.stats[o.name] += 1
                            faddr = o.fileaddr + vm_address - o.vmaddr
                            self.cache[vm_address] = faddr
                            return faddr

        for o in self.map.values():
            # noinspection PyChainedComparisons
            if vm_address >= o.vmaddr and o.vmend >= vm_address:
                # self.stats[o.name] += 1
                faddr = o.fileaddr + vm_address - o.vmaddr
                self.cache[vm_address] = faddr
                return faddr

        raise ValueError(f'Address {hex(vm_address)} couldn\'t be found in vm address set')

    def add_segment(self, segment: Segment):
        if len(segment.sections) == 0:
            seg_obj = vm_obj(segment.vm_address, segment.vm_address + segment.size, segment.size, segment.file_address,
                             segment.name)
            self.map[segment.name] = seg_obj
            self.stats[segment.name] = 0
        else:
            for section in segment.sections.values():
                name = section.name if section.name not in self.map.keys() else section.name + '2'
                sect_obj = vm_obj(section.vm_address, section.vm_address + section.size, section.size, section.file_address, name)
                self.map[name] = sect_obj
                self.sorted_map = {k: v for k, v in sorted(self.map.items(), key=lambda item: item[1].vmaddr)}
                self.stats[name] = 0


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

        if self.arch_struct:
            self.offset = arch_struct.offset
            self.type = self._load_type()
            self.subtype = self._load_subtype()
        else:
            self.offset = offset

    def load_struct(self, addr: int, struct_type: struct, endian="little"):
        field_names = list(struct_type.struct.__dict__['_fields'])  # unimportant?
        fields = [addr]
        ea = addr

        for field in struct_type.sizes:
            field_addr = ea
            fields.append(self.get_at(field_addr, field, endian))
            ea += field

        if len(fields) != len(field_names):
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
                if ea - addr >= 0x20000:
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
        cputype = self.arch_struct.cputype

        if cputype & 0xF0000000 != 0:
            if cputype & 0xF == 0x7:
                return CPUType.X86_64
            elif cputype & 0xF == 0xC:
                return CPUType.ARM64
        else:
            if cputype & 0xF == 0x7:
                return CPUType.X86
            elif cputype & 0xF == 0xC:
                return CPUType.ARM

        raise ValueError(f'Unknown CPU Type ({hex(self.arch_struct.cputype)}) ({self.arch_struct})')

    def _load_subtype(self):
        cpusubtype = self.arch_struct.cpusubtype

        if cpusubtype == 3:
            return CPUSubType.X86_64_ALL
        elif cpusubtype == 8:
            return CPUSubType.X86_64_H
        elif cpusubtype == 9:
            return CPUSubType.ARMV7
        elif cpusubtype == 11:
            return CPUSubType.ARMV7S
        elif cpusubtype == 0:
            return CPUSubType.ARM64_ALL
        elif cpusubtype == 1:
            return CPUSubType.ARM64_V8
        elif cpusubtype == 2:
            return CPUSubType.ARM64_V8

        raise ValueError(f'Unknown CPU SubType ({hex(cpusubtype)})')
