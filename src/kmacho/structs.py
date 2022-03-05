#
#  ktool | kmacho
#  structs.py
#
#  Custom Struct implementation reflecting behavior of named tuples while also handling behind-the-scenes packing/unpacking.
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2021.
#

uint8_t = 1
uint16_t = 2
uint32_t = 4
uint64_t = 8

int8_t = -1
int16_t = -2
int32_t = -4
int64_t = -8


def uint_to_int(uint, bits):
    """
    Assume an int was read from binary as an unsigned int,

    decode it as a two's compliment signed integer

    :param uint:
    :param bits:
    :return:
    """
    if (uint & (1 << (bits - 1))) != 0:  # if sign bit is set e.g., 8bit: 128-255
        uint = uint - (1 << bits)  # compute negative value
    return uint  # return positive value as is


# noinspection PyUnresolvedReferences
class Struct:
    """
    Custom namedtuple-esque Struct representation. Can be unpacked from bytes or manually created with existing
        field values

    Subclassed and passed `fields` and `sizes` values.

    Fields are exposed as read-write attributes, and when written to, will update the backend
        byte representation of the struct, accessible via the .raw attribute

    """

    # noinspection PyProtectedMember
    @staticmethod
    def create_with_bytes(struct_class, raw, byte_order="little"):
        """
        Unpack a struct from raw bytes

        :param struct_class: Struct subclass
        :param raw: Bytes
        :param byte_order: Little/Big Endian Struct Unpacking
        :return: struct_class Instance
        """
        instance: Struct = struct_class(byte_order)
        current_off = 0
        raw = bytearray(raw)
        inst_raw = bytearray()

        for field in instance._fields:
            size = instance._field_sizes[field]
            signed = False

            if size < 0:
                size = abs(size)
                signed = True

            data = raw[current_off:current_off + size]

            field_value = int.from_bytes(data, byte_order)

            if signed:
                field_value = uint_to_int(field_value, size * 8)

            setattr(instance, field, field_value)
            inst_raw += data
            current_off += size

        instance.raw = inst_raw

        instance.pre_init()
        instance.initialized = True
        instance.post_init()

        return instance

    @staticmethod
    def create_with_values(struct_class, values, byte_order="little"):
        """
        Pack/Create a struct given field values

        :param byte_order:
        :param struct_class: Struct subclass
        :param values: List of values
        :return: struct_class Instance
        """

        instance: Struct = struct_class(byte_order)

        # noinspection PyProtectedMember
        for i, field in enumerate(instance._fields):
            instance.__setattr__(field, values[i])

        instance._rebuild_raw()
        instance.pre_init()
        instance.initialized = True
        instance.post_init()
        return instance

    def typename(self):
        return self.__class__.__name__

    def desc(self):
        return ""

    def __str__(self):
        text = f'{self.__class__.__name__}('
        for field in self._fields:
            field_item = self.__getattribute__(field) if isinstance(self.__getattribute__(field), bytearray) else hex(
                self.__getattribute__(field))
            text += f'{field}={field_item}, '
        return text[:-2] + ')'

    def __init__(self, fields=None, sizes=None, byte_order="little", no_patch=False):

        if sizes is None:
            raise AssertionError(
                "Do not use the bare Struct class; it must be implemented in an actual type; Missing Sizes")

        if fields is None:
            raise AssertionError(
                "Do not use the bare Struct class; it must be implemented in an actual type; Missing Fields")

        self.initialized = False
        self.no_patch = False

        self.super = super()
        self._fields = fields
        self.byte_order = byte_order

        self._field_sizes = {}

        for index, i in enumerate(fields):
            self._field_sizes[i] = sizes[index]

        self.off = 0
        self.raw = bytearray()

    def pre_init(self):
        """stub for subclasses. gets called before patch code is enabled"""
        pass

    def post_init(self):
        """stub for subclasses. gets called *after* patch code is enabled"""
        pass

    def _rebuild_raw(self):
        raw = bytearray()
        for field in self._fields:
            size = self._field_sizes[field]

            field_dat = self.__getattribute__(field)

            data = None

            if isinstance(field_dat, int):
                data = field_dat.to_bytes(size, byteorder=self.byte_order)
            elif isinstance(field_dat, bytearray) or isinstance(field_dat, bytes):
                data = self.__getattribute__(field)

            assert data is not None

            raw += bytearray(data)

        self.raw = raw

    def __setattr__(self, key, value):
        super().__setattr__(key, value)
        if not self.initialized:
            return
        if self.no_patch:
            return
        if key in self._fields:
            if self.initialized:
                self._rebuild_raw()


class BitFieldStruct(Struct):

    def __str__(self):
        text = f'{self.__class__.__name__}('
        for field in self._BITFIELDS:
            field_item = self.__getattribute__(field) if isinstance(self.__getattribute__(field), bytearray) else hex(
                self.__getattribute__(field))
            text += f'{field}={field_item}, '
        return text[:-2] + ')'

    def pre_init(self):

        assert sum(self._BF_SIZES) == self.SIZE * 8

        value = self.value

        cur = 0
        for i, bf_name in enumerate(self._BITFIELDS):
            bf_size = self._BF_SIZES[i]

            # TODO: THIS IS SO BAD
            # TODO: SERIOUSLY
            mask = int('1' * bf_size, 2)
            # TODO: ^^^^^^^^^^^^^^

            self.super.__setattr__(bf_name, (value >> cur) & mask)
            # print(f'{bf_name} = {value} >> {cur} & {mask}')
            cur += bf_size


class fat_header(Struct):
    """
    First 8 Bytes of a FAT MachO File

    Attributes:
        self.magic: FAT MachO Magic

        self.nfat_archs: Number of Fat Arch entries after these bytes
    """
    _FIELDNAMES = ['magic', 'nfat_archs']
    _SIZES = [4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class fat_arch(Struct):
    """
    Struct representing a slice in a FAT MachO

    Attribs:
        cpu_type:
    """
    _FIELDNAMES = ['cpu_type', 'cpu_subtype', 'offset', 'size', 'align']
    _SIZES = [4, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cpu_type = 0
        self.cpu_subtype = 0
        self.offset = 0
        self.size = 0
        self.align = 0


class dyld_header(Struct):
    _FIELDNAMES = ['magic', 'cpu_type', 'cpu_subtype', 'filetype', 'loadcnt', 'loadsize', 'flags']
    _SIZES = [4, 4, 4, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.magic = 0
        self.cpu_type = 0
        self.cpu_subtype = 0
        self.filetype = 0
        self.loadcnt = 0
        self.loadsize = 0
        self.flags = 0


class dyld_header_64(Struct):
    _FIELDNAMES = ['magic', 'cpu_type', 'cpu_subtype', 'filetype', 'loadcnt', 'loadsize', 'flags', 'reserved']
    _SIZES = [4, 4, 4, 4, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.magic = 0
        self.cpu_type = 0
        self.cpu_subtype = 0
        self.filetype = 0
        self.loadcnt = 0
        self.loadsize = 0
        self.flags = 0
        self.reserved = 0


class unk_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize']
    _SIZES = [4, 4]
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0


class segment_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'segname', 'vmaddr', 'vmsize', 'fileoff', 'filesize', 'maxprot',
                   'initprot', 'nsects', 'flags']
    _SIZES = [4, 4, 16, 4, 4, 4, 4, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
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
    _FIELDNAMES = ['cmd', 'cmdsize', 'segname', 'vmaddr', 'vmsize', 'fileoff', 'filesize', 'maxprot',
                   'initprot', 'nsects', 'flags']
    _SIZES = [4, 4, 16, 8, 8, 8, 8, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
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
    _FIELDNAMES = ['sectname', 'segname', 'addr', 'size', 'offset', 'align', 'reloff',
                   'nreloc', 'flags', 'reserved1', 'reserved2']
    _SIZES = [16, 16, 4, 4, 4, 4, 4, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
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
    _FIELDNAMES = ['sectname', 'segname', 'addr', 'size', 'offset', 'align', 'reloff',
                   'nreloc', 'flags', 'reserved1', 'reserved2', 'reserved3']
    _SIZES = [16, 16, 8, 8, 4, 4, 4, 4, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
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
    _FIELDNAMES = ['cmd', 'cmdsize', 'symoff', 'nsyms', 'stroff', 'strsize']
    _SIZES = [4, 4, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.symoff = 0
        self.nsyms = 0
        self.stroff = 0
        self.strsize = 0


class dysymtab_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'ilocalsym', 'nlocalsym', 'iextdefsym', 'nextdefsym',
                   'iundefsym', 'nundefsym', 'tocoff', 'ntoc', 'modtaboff', 'nmodtab',
                   'extrefsymoff', 'nextrefsyms', 'indirectsymoff', 'nindirectsyms',
                   'extreloff', 'nextrel', 'locreloff', 'nlocrel']
    _SIZES = [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
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
    _FIELDNAMES = ['name', 'timestamp', 'current_version', 'compatibility_version']
    _SIZES = [4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.name = 0
        self.timestamp = 0
        self.current_version = 0
        self.compatibility_version = 0


class dylib_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'dylib']
    _SIZES = [4, 4, 16]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.dylib = 0


class dylinker_command(Struct):
    _FIELDNAMES = ["cmd", "cmdsize", "name"]
    _SIZES = [4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.name = 0


class sub_client_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'offset']
    _SIZES = [4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.offset = 0


class uuid_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'uuid']
    _SIZES = [4, 4, 16]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.uuid = 0


class build_version_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'platform', 'minos', 'sdk', 'ntools']
    _SIZES = [4, 4, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.platform = 0
        self.minos = 0
        self.sdk = 0
        self.ntools = 0


class entry_point_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'entryoff', 'stacksize']
    _SIZES = [4, 4, 8, 8]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.entryoff = 0
        self.stacksize = 0


class rpath_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'path']
    _SIZES = [4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.path = 0


class source_version_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'version']
    _SIZES = [4, 4, 8]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.version = 0


class linkedit_data_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'dataoff', 'datasize']
    _SIZES = [4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.dataoff = 0
        self.datasize = 0


class dyld_info_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'rebase_off', 'rebase_size', 'bind_off', 'bind_size',
                   'weak_bind_off', 'weak_bind_size', 'lazy_bind_off', 'lazy_bind_size',
                   'export_off', 'export_size']
    _SIZES = [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
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
    _FIELDNAMES = ["str_index", "type", "sect_index", "desc", "value"]
    _SIZES = [4, 1, 1, 2, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.str_index = 0
        self.type = 0
        self.sect_index = 0
        self.desc = 0
        self.value = 0


class symtab_entry(Struct):
    _FIELDNAMES = ["str_index", "type", "sect_index", "desc", "value"]
    _SIZES = [4, 1, 1, 2, 8]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.str_index = 0
        self.type = 0
        self.sect_index = 0
        self.desc = 0
        self.value = 0


class version_min_command(Struct):
    _FIELDNAMES = ["cmd", "cmdsize", "version", "reserved"]
    _SIZES = [4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.version = 0
        self.reserved = 0


class encryption_info_command(Struct):
    _FIELDNAMES = ["cmd", "cmdsize", "cryptoff", "cryptsize", "cryptid"]
    _SIZES = [4, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.cryptoff = 0
        self.cryptsize = 0
        self.cryptid = 0


class encryption_info_command_64(Struct):
    _FIELDNAMES = ["cmd", "cmdsize", "cryptoff", "cryptsize", "cryptid", "pad"]
    _SIZES = [4, 4, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.cryptoff = 0
        self.cryptsize = 0
        self.cryptid = 0
        self.pad = 0


class thread_command(Struct):
    _FIELDNAMES = ["cmd", "cmdsize", "flavor", "count"]
    _SIZES = [4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cmd = 0
        self.cmdsize = 0
        self.flavor = 0
        self.count = 0

