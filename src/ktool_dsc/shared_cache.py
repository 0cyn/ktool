#
#  ktool | ktool_dsc
#  shared_cache.py
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
from typing import List, Dict, Tuple

from lib0cyn.log import log
from ktool_dsc.file import *
from ktool_dsc.structs import *
from ktool_macho import symtab_command, symtab_entry, symtab_entry_32
from ktool.exceptions import VMAddressingError, MachOAlignmentError
from ktool.image import VM, Image, _fakeseg, vm_obj
from ktool.loader import Symbol, SymbolType


class DyldSharedCacheImageEntry:
    def __init__(self, base_dsc: MemoryCappedBufferedFileReader, dcii: dyld_cache_image_info):
        self.install_name = base_dsc.read_null_term_string(dcii.pathFileOffset)
        self.info = dcii

    def __repr__(self):
        return f'<DSCImage: {self.install_name}>'


class Malleable:
    def __init__(self):
        pass


class DyldSharedCacheImageSliceAdapter:
    def __init__(self, dsc, filename):
        self.dsc = dsc
        self.macho_file = Malleable()
        setattr(self.macho_file, 'filename', filename)

    def get_cstr_at(self, addr, limit=0):
        return self.dsc.base_dsc.read_null_term_string(addr)

    def load_struct(self, addr, struct_type, vm=False, endian="little"):
        return self.dsc._load_struct(self.dsc.base_dsc, addr, struct_type)

    def get_uint_at(self, addr, count, vm=False, endian="little"):
        return self.dsc._get_uint_at(self.dsc.base_dsc, addr, count, endian)

    def get_bytes_at(self, addr, count, vm=False):
        return self.dsc._get_bytes_at(self.dsc.base_dsc, addr, count)

    def decode_uleb128(self, readHead: int) -> Tuple[int, int]:

        value = 0
        shift = 0

        while True:

            byte = self.get_uint_at(readHead, 1)

            value |= (byte & 0x7f) << shift

            readHead += 1
            shift += 7

            if (byte & 0x80) == 0:
                break

        return value, readHead


class DSCVM(VM):

    def __init__(self, page_size):
        super().__init__(page_size)
        self.page_file_mapping = {}

    def __str__(self):
        v = ""
        for seg in self.fallback.map.values():
            seg: vm_obj = seg
            addr, file = self.translate_and_get_file(seg.vmaddr)
            v += f'{hex(seg.vmaddr)}-{hex(seg.vmaddr + seg.size)} -> {hex(seg.fileaddr)}-{hex(seg.fileaddr + seg.size)} - {file.filename}\n'
        return v

    def vm_check(self, address):
        try:
            self.translate(address)
            return True
        except ValueError:
            return False

    def translate_and_get_file(self, address) -> Tuple[int, MemoryCappedBufferedFileReader]:
        l_addr = address

        if self.detag_kern_64:
            address = address | (0xFFFF << 12 * 4)

        if self.detag_64:
            address = address & 0xFFFFFFFFF

        page_location = address >> self.page_size_bits

        try:
            return self.tlb[address], self.page_file_mapping[page_location]
        except KeyError:
            pass

        page_offset = address & self.page_size - 1
        try:
            phys_page = self.page_table[page_location]
            physical_location = phys_page + page_offset
            self.tlb[address] = physical_location
            return physical_location, self.page_file_mapping[page_location]
        except KeyError:
            log.info(f'Address {hex(address)} not mapped, attempting fallback')
            raise VMAddressingError(
                f'Address {hex(address)} ({hex(l_addr)}) not in VA Table or fallback map. (page: {hex(page_location)})')

    def de_translate(self, file_address):
        """
        This method is slow, and should only be used for introspection, and not things that need to be fast.

        :param file_address:
        :return:
        """
        return self.fallback.de_translate(file_address)

    def map_pages(self, physical_addr, virtual_addr, size, file=None):
        log.debug_more(f'Mapping {hex(virtual_addr)}+{hex(size)} to {hex(physical_addr)}+{hex(size)}')
        if physical_addr % self.page_size != 0 or virtual_addr % self.page_size != 0 or size % self.page_size != 0:
            raise MachOAlignmentError(f'Tried to map {hex(virtual_addr)}+{hex(size)} to {hex(physical_addr)}')
        seg = _fakeseg(vm_address=virtual_addr, file_address=physical_addr, size=size)
        self.fallback.add_segment(seg)
        for i in range(size // self.page_size):
            self.page_table[virtual_addr + (i * self.page_size) >> self.page_size_bits] = physical_addr + (
                    i * self.page_size)
            self.page_file_mapping[virtual_addr + (i * self.page_size) >> self.page_size_bits] = file


class DSCSymbol(Symbol):
    """
    This class can represent several types of symbols.

    """

    @classmethod
    def from_image(cls, dsc, file, cmd, entry):
        fullname = dsc._get_cstr_at(file, entry.str_index + cmd.stroff)
        addr = entry.value

        symbol = cls.from_values(fullname, addr)

        N_STAB = 0xe0
        N_PEXT = 0x10
        N_TYPE = 0x0e
        N_EXT = 0x01

        type_masked = N_TYPE & entry.type
        for name, flag in {'N_UNDF': 0x0, 'N_ABS': 0x2, 'N_SECT': 0xe, 'N_PBUD': 0xc, 'N_INDR': 0xa}.items():
            if type_masked & flag:
                symbol.types.append(name)

        if entry.type & N_EXT:
            symbol.external = True

        return symbol

    @classmethod
    def from_values(cls, fullname, value, external=False, ordinal=0):
        if '_$_' in fullname:
            if fullname.startswith('_OBJC_CLASS_$'):
                dec_type = SymbolType.CLASS
            elif fullname.startswith('_OBJC_METACLASS_$'):
                dec_type = SymbolType.METACLASS
            elif fullname.startswith('_OBJC_IVAR_$'):
                dec_type = SymbolType.IVAR
            else:
                dec_type = SymbolType.UNK
            name = fullname.split('$')[1]
        else:
            name = fullname
            dec_type = SymbolType.FUNC

        return cls(fullname, name=name, dec_type=dec_type, external=external, value=value, ordinal=ordinal)

    def raw_bytes(self):
        pass

    def serialize(self):
        return {'name': self.fullname, 'address': self.address, 'external': self.external, 'ordinal': self.ordinal}

    def __init__(self, fullname=None, name=None, dec_type=None, external=False, value=0, ordinal=0):
        super().__init__(fullname, name, dec_type, external, value, ordinal)


class DSCSymbolTable:
    """
    This class represents the symbol table declared in the MachO File

    .table contains the symbol table

    .ext contains exported symbols, i think?

    This class is incomplete

    """

    def __init__(self, image: Image, cmd: symtab_command):
        self.image: Image = image
        self.cmd: symtab_command = cmd

        self.ext: List[Symbol] = []
        self.table: List[Symbol] = self._load_symbol_table()

    def _load_symbol_table(self) -> List[Symbol]:
        symbol_table = []
        read_address = self.cmd.symoff
        linkedit_vm = self.image.segments['__LINKEDIT'].vm_address
        vm: DSCVM = self.image.vm.fallback
        addr, file = vm.translate_and_get_file(linkedit_vm)
        typing = symtab_entry if self.image.macho_header.is64 else symtab_entry_32
        for i in range(0, self.cmd.nsyms):
            entry = self.image._dsc._load_struct(file, read_address + typing.SIZE * i, typing)
            symbol = DSCSymbol.from_image(self.image._dsc, file, self.cmd, entry)
            symbol_table.append(symbol)

            if symbol.external:
                self.ext.append(symbol)

            log.debug_tm(f'Symbol Table: Loaded symbol:{symbol.name} ordinal:{symbol.ordinal} type:{symbol.dec_type}')
            log.debug_tm(str(entry))

        return symbol_table


class DyldSharedCache:
    def __init__(self, path):
        self.path = path
        self.header = None
        self.base_dsc = MemoryCappedBufferedFileReader(open(path, 'rb'), mbs=100)
        self.subcache_files = []

        self.images: Dict[str, DyldSharedCacheImageEntry] = {}
        self.vm: DSCVM = DSCVM(0x4000)
        self.current_base_cache = self.base_dsc
        self._cstring_cache = {}

    def load_struct(self, addr, struct_type, vm=False, endian="little", force_reload=False):
        file = self.current_base_cache
        if vm:
            addr, file = self.vm.translate_and_get_file(addr)
        return self._load_struct(file, addr, struct_type)

    def get_cstr_at(self, addr, limit=0, vm=False):
        vm_addr = addr
        file = self.current_base_cache
        if vm:
            addr, file = self.vm.translate_and_get_file(addr)
        try:
            return self._get_cstr_at(file, addr, 0)
        except IndexError as ex:
            print(hex(vm_addr))
            print(hex(addr))
            raise ex

    def get_uint_at(self, addr, count, vm=False, endian="little"):
        file = self.current_base_cache
        if vm:
            addr, file = self.vm.translate_and_get_file(addr)
        return self._get_uint_at(file, addr, count, endian)

    def get_bytes_at(self, addr, count, vm=False):
        file = self.current_base_cache
        if vm:
            addr, file = self.vm.translate_and_get_file(addr)
        return self._get_bytes_at(file, addr, count)

    def get_str_at(self, addr, count, vm=False):
        file = self.current_base_cache
        if vm:
            addr, file = self.vm.translate_and_get_file(addr)
        return self._get_str_at(file, addr, count, False)

    def _get_str_at(self, file, addr: int, count: int, force=False) -> str:
        if force:
            data = file.fp[addr:addr + count]
            string = ""

            for ch in data:
                try:
                    string += bytes(ch).decode()
                except UnicodeDecodeError:
                    string += "?"
            return string

        return file.fp[addr:addr + count].decode().rstrip('\x00')

    def _get_cstr_at(self, file, addr, limit=0):
        ea = addr

        if addr in self._cstring_cache:
            return self._cstring_cache[addr]

        count = 0
        while True:
            if file.fp[ea] != 0:
                count += 1
                ea += 1
            else:
                break

        text = self._get_str_at(file, addr, count)

        self._cstring_cache[addr] = text

        return text

    def _load_struct(self, file, addr: int, struct_type, endian="little"):
        size = struct_type.SIZE
        data = self._get_bytes_at(file, addr, size)
        struct = Struct.create_with_bytes(struct_type, data, endian)
        struct.off = addr

        return struct

    def _get_uint_at(self, file: MemoryCappedBufferedFileReader, addr: int, count: int, endian="little"):
        return int.from_bytes(file.fp[addr:addr + count], endian)

    def _get_bytes_at(self, file: MemoryCappedBufferedFileReader, addr: int, count: int):
        return bytes(file.fp[addr:addr + count])
