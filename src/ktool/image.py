from collections import namedtuple
from enum import Enum
from typing import List, Dict, Union

from kmacho import LOAD_COMMAND, dylib_command, dyld_info_command, Struct, CPUSubTypeARM64, CPUType, segment_command_64
from kmacho.base import Constructable
from ktool.codesign import CodesignInfo
from ktool.exceptions import VMAddressingError, MachOAlignmentError
from ktool.util import bytes_to_hex
from katlib.log import log
from ktool.macho import Slice, SlicedBackingFile, MachOImageHeader, Segment, PlatformType, ToolType


os_version = namedtuple("os_version", ["x", "y", "z"])
_fakeseg = namedtuple("_fakeseg", ["vm_address", "file_address", "size"])


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

        self.fallback: MisalignedVM = MisalignedVM()

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

    def detranslate(self, file_address):
        """
        This method is slow, and should only be used for introspection, and not things that need to be fast.

        :param file_address:
        :return:
        """
        return self.fallback.detranslate(file_address)

    def map_pages(self, physical_addr, virtual_addr, size):
        if physical_addr % self.page_size != 0 or virtual_addr % self.page_size != 0 or size % self.page_size != 0:
            raise MachOAlignmentError(f'Tried to map {hex(virtual_addr)}+{hex(size)} to {hex(physical_addr)}')
        for i in range(size // self.page_size):
            self.page_table[virtual_addr + (i * self.page_size) >> self.page_size_bits] = physical_addr + (
                        i * self.page_size)

        seg = _fakeseg(vm_address=virtual_addr, file_address=physical_addr, size=size)
        self.fallback.add_segment(seg)


vm_obj = namedtuple("vm_obj", ["vmaddr", "vmend", "size", "fileaddr"])


class MisalignedVM:
    """
    This is the manual backup if the image can't be mapped to 16/4k segments
    """

    def __init__(self):
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

    def detranslate(self, file_address):
        """
        This method is slow, and should only be used for introspection, and not things that need to be fast.

        :param file_address:
        :return:
        """
        for o in self.map.values():
            file_start = o.fileaddr
            file_end = o.fileaddr + o.size
            if file_start <= file_address <= file_end:
                return o.vmaddr + (file_address - file_start)
        raise VMAddressingError("Could not detranslate address")

    def add_segment(self, segment: Union[Segment, _fakeseg]):
        if segment.file_address == 0 and segment.size != 0:
            self.vm_base_addr = segment.vm_address

        seg_obj = vm_obj(segment.vm_address, segment.vm_address + segment.size, segment.size, segment.file_address)
        log.info(str(seg_obj))
        self.map[segment.file_address] = seg_obj


class LinkedImage:
    def __init__(self, source_image: 'Image', cmd):
        self.cmd = cmd
        self.source_image = source_image

        self.install_name = self._get_name(cmd)
        self.weak = cmd.cmd == LOAD_COMMAND.LOAD_WEAK_DYLIB.value
        self.local = cmd.cmd == LOAD_COMMAND.ID_DYLIB.value

    def serialize(self):
        return {
            'install_name': self.install_name,
            'load_command': LOAD_COMMAND(self.cmd.cmd).name
        }

    def _get_name(self, cmd) -> str:
        read_address = cmd.off + dylib_command.SIZE
        return self.source_image.get_cstr_at(read_address)


class Image:
    """
    This class represents the Mach-O Binary as a whole.

    It's the root object in the massive tree of information we're going to build up about the binary

    This class on its own does not handle populating its fields.
    The Dyld class set is responsible for loading in and processing the raw values to it.
    """

    def __init__(self, macho_slice: Slice, force_misaligned_vm=False):
        """
        Create a MachO image

        :param macho_slice: MachO Slice being processed
        :type macho_slice: MachO Slice
        """
        self.slice: Slice = macho_slice

        self.vm = None

        if self.slice:
            self.macho_header: MachOImageHeader = MachOImageHeader.from_image(macho_slice=macho_slice)

            if force_misaligned_vm:
                self.vm = MisalignedVM()
            else:
                self.vm_realign()

        self.base_name = ""  # copy of self.name
        self.install_name = ""

        self.linked_images: List[LinkedImage] = []

        self.segments: Dict[str, Segment] = {}

        self.info: Union[dyld_info_command, None] = None
        self.dylib: Union[LinkedImage, None] = None
        self.uuid = None
        self.codesign_info: Union[CodesignInfo, None] = None

        self._codesign_cmd = None

        self.platform: PlatformType = PlatformType.UNK

        self.allowed_clients: List[str] = []

        self.rpath: Union[str, None] = None

        self.minos = os_version(0, 0, 0)
        self.sdk_version = os_version(0, 0, 0)

        self.imports: List['Symbol'] = []
        self.exports: List['Symbol'] = []

        self.symbols: Dict[int, 'Symbol'] = {}
        self.import_table: Dict[int, 'Symbol'] = {}
        self.export_table: Dict[int, 'Symbol'] = {}

        self.entry_point = 0

        self.function_starts: List[int] = []

        self.thread_state: List[int] = []
        self._entry_off = 0

        self.binding_table = None
        self.weak_binding_table = None
        self.lazy_binding_table = None
        self.export_trie = None

        self.chained_fixups = None

        self.symbol_table = None

        self.struct_cache: Dict[int, Struct] = {}

    def serialize(self):
        image_dict = {
            'macho_header': self.macho_header.serialize()
        }

        if self.install_name != "":
            image_dict['install_name'] = self.install_name

        linked = []
        for ext_dylib in self.linked_images:
            linked.append(ext_dylib.serialize())

        image_dict['linked'] = linked

        segments = {}

        for seg_name, seg in self.segments.items():
            segments[seg_name] = seg.serialize()

        image_dict['segments'] = segments
        if self.uuid:
            image_dict['uuid'] = bytes_to_hex(self.uuid)

        image_dict['platform'] = self.platform.name

        image_dict['allowed-clients'] = self.allowed_clients

        if self.rpath:
            image_dict['rpath'] = self.rpath

        image_dict['imports'] = [sym.serialize() for sym in self.imports]
        image_dict['exports'] = [sym.serialize() for sym in self.exports]
        image_dict['symbols'] = [sym.serialize() for sym in self.symbols.values()]

        image_dict['entry_point'] = self.entry_point

        image_dict['function_starts'] = self.function_starts

        image_dict['thread_state'] = self.thread_state

        image_dict['minos'] = f'{self.minos.x}.{self.minos.y}{self.minos.z}'
        image_dict['sdk_version'] = f'{self.sdk_version.x}.{self.sdk_version.y}.{self.sdk_version.z}'

        return image_dict

    def vm_realign(self, yell_about_misalignment=True):

        align_by = 0x4000
        aligned = False

        detag_64 = False

        segs = []
        for cmd in self.macho_header.load_commands:
            if cmd.cmd in [LOAD_COMMAND.SEGMENT.value, LOAD_COMMAND.SEGMENT_64.value]:
                segs.append(cmd)
            if cmd.cmd == LOAD_COMMAND.LC_DYLD_CHAINED_FIXUPS:
                detag_64 = True

        if self.slice.type == CPUType.ARM64 and self.slice.subtype == CPUSubTypeARM64.ARM64E:
            detag_64 = True

        while not aligned:
            aligned = True
            for cmd in segs:
                cmd: segment_command_64 = cmd
                if cmd.vmaddr % align_by != 0:
                    if align_by == 0x4000:
                        align_by = 0x1000
                        aligned = False
                        break
                    else:
                        align_by = 0
                        aligned = True
                        break

        if align_by != 0:
            log.info(f'Aligned to {hex(align_by)} pages')
            self.vm: VM = VM(page_size=align_by)
            self.vm.detag_64 = detag_64
        else:
            if yell_about_misalignment:
                log.info("MachO cannot be aligned to 16k or 4k pages. Swapping to fallback mapping.")
            self.vm: MisalignedVM = MisalignedVM()
            self.vm.detag_64 = detag_64

    def vm_check(self, address):
        return self.vm.vm_check(address)

    def get_int_at(self, offset: int, length: int, vm=False, section_name=None):
        """
        Get a sequence of bytes (as an int) from a location

        :param offset: Offset within the image
        :param length: Amount of bytes to get
        :param vm: Is `offset` a VM address
        :param section_name: Section Name if vm==True (improves translation time slightly)
        :return: `length` Bytes at `offset`
        """
        if vm:
            offset = self.vm.translate(offset)
        return self.slice.get_int_at(offset, length)

    def get_bytes_at(self, offset: int, length: int, vm=False, section_name=None):
        """
        Get a sequence of bytes from a location

        :param offset: Offset within the image
        :param length: Amount of bytes to get
        :param vm: Is `offset` a VM address
        :param section_name: Section Name if vm==True (improves translation time slightly)
        :return: `length` Bytes at `offset`
        """
        if vm:
            offset = self.vm.translate(offset)
        return self.slice.get_bytes_at(offset, length)

    def load_struct(self, address: int, struct_type, vm=False, section_name=None, endian="little", force_reload=False):
        """
        Load a struct (struct_type_t) from a location and return the processed object

        :param address: Address to load struct from
        :param struct_type: type of struct (e.g. dyld_header)
        :param vm:  Is `address` a VM address?
        :param section_name: if `vm==True`, the section name (slightly improves translation speed)
        :param endian: Endianness of bytes to read.
        :return: Loaded struct
        """
        if address not in self.struct_cache or force_reload:
            if vm:
                address = self.vm.translate(address)
            struct = self.slice.load_struct(address, struct_type, endian)
            self.struct_cache[address] = struct
            return struct

        return self.struct_cache[address]

    def get_str_at(self, address: int, count: int, vm=False, section_name=None, force=False):
        """
        Get string with set length from location (to be used essentially only for loading segment names)

        :param address: Address of string start
        :param count: Length of string
        :param vm: Is `address` a VM address?
        :param section_name: if `vm==True`, the section name (unused here, really)
        :return: The loaded string.
        """
        if vm:
            address = self.vm.translate(address)
        return self.slice.get_str_at(address, count, force=force)

    def get_cstr_at(self, address: int, limit: int = 0, vm=False, section_name=None):
        """
        Load a C style string from a location, stopping once a null byte is encountered.

        :param address: Address to load string from
        :param limit: Limit of the length of bytes, 0 = unlimited
        :param vm: Is `address` a VM address?
        :param section_name: if `vm==True`, the section name (vastly improves VM lookup time)
        :return: The loaded C string
        """
        if vm:
            address = self.vm.translate(address)
        return self.slice.get_cstr_at(address, limit)

    def decode_uleb128(self, readHead: int):
        """
        Decode a uleb128 integer from a location

        :param readHead: Start location
        :return: (end location, value)
        """
        return self.slice.decode_uleb128(readHead)

