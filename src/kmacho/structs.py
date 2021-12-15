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
            data = raw[current_off:current_off + size]

            instance.super.__setattr__(field, int.from_bytes(data, byte_order))
            inst_raw += data
            current_off += size

        instance.super.__setattr__('raw', inst_raw)
        instance.super.__setattr__('initialized', True)
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
        instance.initialized = True
        return instance

    def typename(self):
        return self.__class__.__name__

    def desc(self):
        return ""

    def __str__(self):
        text = f'{self.__class__.__name__}('
        for field in self._fields:
            field_item = self.__getattribute__(field) if isinstance(self.__getattribute__(field), bytearray) else hex(self.__getattribute__(field))
            text += f'{field}={field_item}, '
        return text[:-2] + ')'

    def __init__(self, fields=None, sizes=None, byte_order="little"):

        # We have to use the underlying superclass' __setattr__ to avoid using our own
        # Our custom one checks whether a list contains something, which during init gets called
        #   6 times. This exponentially multiplies how slow loading files with a shitload of
        #   structs. Doing this saves about 5-10% off load times on larger files.

        if sizes is None:
            raise AssertionError(
                "Do not use the bare Struct class; it must be implemented in an actual type; Missing Sizes")

        if fields is None:
            raise AssertionError(
                "Do not use the bare Struct class; it must be implemented in an actual type; Missing Fields")

        super().__setattr__('super', super())
        super().__setattr__('_fields', fields)

        super().__setattr__('byte_order', byte_order)
        super().__setattr__('initialized', False)

        super().__setattr__('_field_sizes', {})

        for index, i in enumerate(fields):
            self._field_sizes[i] = sizes[index]

        super().__setattr__('off', 0)
        super().__setattr__('raw', bytearray(b''))

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
        if key in self._fields:
            super().__setattr__(key, value)
            if self.initialized:
                self._rebuild_raw()
        else:
            super().__setattr__(key, value)


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


class dyld_header(Struct):
    _FIELDNAMES = ['magic', 'cpu_type', 'cpu_subtype', 'filetype', 'loadcnt', 'loadsize', 'flags', 'void']
    _SIZES = [4, 4, 4, 4, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class unk_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize']
    _SIZES = [4, 4]
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class segment_command_64(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'segname', 'vmaddr', 'vmsize', 'fileoff', 'filesize', 'maxprot',
                   'initprot', 'nsects', 'flags']
    _SIZES = [4, 4, 16, 8, 8, 8, 8, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class section_64(Struct):
    _FIELDNAMES = ['sectname', 'segname', 'addr', 'size', 'offset', 'align', 'reloff',
                   'nreloc', 'flags', 'reserved1', 'reserved2', 'reserved3']
    _SIZES = [16, 16, 8, 8, 4, 4, 4, 4, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class symtab_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'symoff', 'nsyms', 'stroff', 'strsize']
    _SIZES = [4, 4, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class dysymtab_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'ilocalsym', 'nlocalsym', 'iextdefsym', 'nextdefsym',
                   'iundefsym', 'nundefsym', 'tocoff', 'ntoc', 'modtaboff', 'nmodtab',
                   'extrefsymoff', 'nextrefsyms', 'indirectsymoff', 'nindirectsyms',
                   'extreloff', 'nextrel', 'locreloff', 'nlocrel']
    _SIZES = [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class dylib(Struct):
    _FIELDNAMES = ['name', 'timestamp', 'current_version', 'compatibility_version']
    _SIZES = [4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class dylib_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'dylib']
    _SIZES = [4, 4, 16]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class dylinker_command(Struct):
    _FIELDNAMES = ["cmd", "cmdsize", "name"]
    _SIZES = [4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class sub_client_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'offset']
    _SIZES = [4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class uuid_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'uuid']
    _SIZES = [4, 4, 16]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class build_version_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'platform', 'minos', 'sdk', 'ntools']
    _SIZES = [4, 4, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class entry_point_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'entryoff', 'stacksize']
    _SIZES = [4, 4, 8, 8]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class rpath_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'path']
    _SIZES = [4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class source_version_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'version']
    _SIZES = [4, 4, 8]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class linkedit_data_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'dataoff', 'datasize']
    _SIZES = [4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class dyld_info_command(Struct):
    _FIELDNAMES = ['cmd', 'cmdsize', 'rebase_off', 'rebase_size', 'bind_off', 'bind_size',
                   'weak_bind_off', 'weak_bind_size', 'lazy_bind_off', 'lazy_bind_size',
                   'export_off', 'export_size']
    _SIZES = [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class symtab_entry(Struct):
    _FIELDNAMES = ["str_index", "type", "sect_index", "desc", "value"]
    _SIZES = [4, 1, 1, 2, 8]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)


class version_min_command(Struct):
    _FIELDNAMES = ["cmd", "cmdsize", "version", "reserved"]
    _SIZES = [4, 4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
