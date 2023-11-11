#
#  ktool | lib0cyn
#  structs.py
#
#  Custom Struct implementation reflecting behavior of named tuples while also handling behind-the-scenes
#    packing/unpacking
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) 0cyn 2022.
#
from typing import List

# At a glance this looks insane for python,
# But size calc is *very* hot code, and if we can reduce the computation of sizes to bit manipulation,
#   it provides a sizable speedup.
type_mask = 0xffff0000
size_mask = 0xffff

type_uint = 0
type_sint = 0x10000
type_str = 0x20000
type_bytes = 0x30000

uint8_t = 1
uint16_t = 2
uint32_t = 4
uint64_t = 8

int8_t = type_sint | 1
int16_t = type_sint | 2
int32_t = type_sint | 4
int64_t = type_sint | 8

# "wtf is going on here?"
# this is a bit cursed, but makes it possible to specify an arbitrary length of characters/bytes in a field
#   by passing, e.g. char_t[16] for the size. This is just making an array of size values with a str type
#   and size between 1 and 64
#   if you need more than 64 just pass `(type_str | n)` where `n` is your size, as the size.
char_t = [type_str | i for i in range(65)]
bytes_t = [type_bytes | i for i in range(65)]
# can you tell I miss C


class uintptr_t:
    pass


class pad_for_64_bit_only:
    """ Sometimes, arm64/x64 variations of structures may differ from 32 bit ones only in variables to pad
        things out for the sake of byte-aligned reads. This allows us to account for that without having to make
        a separate 64 and 32 bit struct.

        This acts as a variable length field, and will have a size of 0 if ptr_size passed to struct code isn't 8
    """
    def __init__(self, size=4):
        self.size = size


class Bitfield:
    """ Horrible class for decoding bitfields. This basically just exists for chained fixups do not write anything
        that uses this because I hardly understand what i've even wrote.

        Initialize with dict of field name to size in bits.
        Load fields with ``myBitfieldInstance.decode_bitfield(myProperlySizedBytearray)``
        Access by myBitfieldInstance.field_name
    """

    def __init__(self, fields: dict):
        self.fields = fields
        self.size = sum(self.fields.values()) // 8
        self.size_bits = sum(self.fields.values())
        self.decoded_fields = {}

    def decode_bitfield(self, value):
        # welcom to my night mare
        int_value = int.from_bytes(value, 'little')
        # print(bin(int_value))
        bit_pos = 0
        for field_name, bit_size in self.fields.items():
            mask = (1 << bit_size) - 1
            # print(f'{field_name} - {bin((int_value >> bit_pos) & mask)} {bin(mask)}')
            self.decoded_fields[field_name] = (int_value >> bit_pos) & mask
            setattr(self, field_name, self.decoded_fields[field_name])
            bit_pos += bit_size


class StructUnion:
    """ This class is a horrible one;
        This struct code was not written with Unions in mind, or much in mind in general;

        This implementation of unions has a couple of rules:
        * It can only contain structs or other unions
        * It will implicitly assume all types are the same size and probably die horribly if that isn't true.

        Create one like:
            class MySubClass(StructUnion):
            def __init__(): #    |size   | list of Struct types like `mach_header`, etc
                super().__init__(8,      [my_struct_1, my_structtype_2])

        Use like:
            unionInst = MySubClass()
            unionInst.load_from_bytes(my_epic_bytearray_that_is_properly_sized)
            valueIWant = unionInst.my_struct_1.someFieldInIt

    """

    def __init__(self, size: int, types: List[object]):
        self.size = size
        self.types = types

    def load_from_bytes(self, data):
        for t in self.types:
            if issubclass(t, Struct):
                setattr(self, t.__name__, Struct.create_with_bytes(t, data, "little"))
            elif issubclass(t, StructUnion):
                setattr(self, t.__name__, t())
                getattr(self, t.__name__).load_from_bytes(data)

    def __int__(self):
        return self.__class__.size()


def _bytes_to_hex(data) -> str:
    return data.hex()


def _uint_to_int(uint, bits):
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

    @classmethod
    def size(cls, ptr_size=None):
        if not hasattr(cls, 'FIELDS'):
            return cls.SIZE
        if not hasattr(cls, '___SIZE'):
            size = 0
            for _, value in cls.FIELDS.items():
                if isinstance(value, int):
                    size += value & size_mask
                elif isinstance(value, Bitfield):
                    size += value.size
                elif isinstance(value, pad_for_64_bit_only):
                    if ptr_size is None:
                        from lib0cyn.log import log
                        err = "Trying to get size on variable (ptr) sized type directly without a ptr_size! This is programmer error!"
                        print(err)
                        log.error(err)
                        import traceback
                        traceback.print_stack()
                        print(err)
                        log.error(err)
                        log.error("Exiting now. Go fix this.")
                        exit(404)
                    if ptr_size == 8:
                        size += value.size
                elif issubclass(value, uintptr_t):
                    if ptr_size is None:
                        from lib0cyn.log import log
                        err = "Trying to get size on variable (ptr) sized type directly without a ptr_size! This is programmer error!"
                        print(err)
                        log.error(err)
                        import traceback
                        traceback.print_stack()
                        print(err)
                        log.error(err)
                        log.error("Exiting now. Go fix this.")
                        exit(404)
                    size += ptr_size
                    setattr(cls, '___VARIABLE_SIZE', True)
                elif issubclass(value, StructUnion):
                    size += value.size
                elif issubclass(value, Struct):
                    if value == cls:
                        raise AssertionError(f"Recursive type definition on {cls.__name__}")
                    if hasattr(value, 'FIELDS'):
                        size += value.size(ptr_size=ptr_size)
                    else:
                        size += value.size(ptr_size=ptr_size)
            if not hasattr(cls, '___VARIABLE_SIZE'):
                setattr(cls, "___SIZE", size)
            return size
        else:
            return getattr(cls, "___SIZE")

    # noinspection PyProtectedMember
    @staticmethod
    def create_with_bytes(struct_class, raw, byte_order="little", ptr_size=8):
        """
        Unpack a struct from raw bytes

        :param struct_class: Struct subclass
        :param raw: Bytes
        :param ptr_size:
        :param byte_order: Little/Big Endian Struct Unpacking
        :return: struct_class Instance
        """
        instance: Struct = struct_class(byte_order)
        current_off = 0
        raw = bytearray(raw)
        inst_raw = bytearray()

        # I *Genuinely* cannot figure out where in the program the size mismatch is happening. This should hotfix?
        raw = raw[:struct_class.size(ptr_size=ptr_size)]

        for field in instance._fields:
            value = instance._field_sizes[field]
            instance._field_offsets[field] = current_off

            field_value = None

            if isinstance(value, int):
                field_type = type_mask & value
                size = size_mask & value

                data = raw[current_off:current_off + size]

                if field_type == type_str:
                    field_value = data.decode('utf-8').replace('\x00', '')

                elif field_type == type_bytes:
                    field_value = bytes(data)

                elif field_type == type_uint:
                    field_value = int.from_bytes(data, byte_order)

                elif field_type == type_sint:
                    field_value = int.from_bytes(data, byte_order)
                    field_value = _uint_to_int(field_value, size * 8)

            elif isinstance(value, Bitfield):
                size = value.size
                data = raw[current_off:current_off + size]
                assert len(data) == size
                value.decode_bitfield(data)
                for f, fv in value.decoded_fields.items():
                    setattr(instance, f, fv)
                field_value = None

            elif isinstance(value, pad_for_64_bit_only):
                size = value.size if ptr_size == 8 else 0
                if size != 0:
                    data = raw[current_off:current_off + size]
                    field_value = int.from_bytes(data, byte_order)
                else:
                    data = bytearray()
                    field_value = 0

            elif issubclass(value, uintptr_t):
                size = ptr_size
                data = raw[current_off:current_off + size]
                field_value = int.from_bytes(data, byte_order)

            elif issubclass(value, StructUnion):
                data = raw[current_off:current_off + value.SIZE]
                size = value.SIZE
                field_value = value()
                field_value.load_from_bytes(data)

            elif issubclass(value, Struct):
                size = value.size(ptr_size=ptr_size)
                data = raw[current_off:current_off + size]
                field_value = Struct.create_with_bytes(value, data)

            else:
                raise AssertionError

            if field_value is not None:
                setattr(instance, field, field_value)
            inst_raw += data
            current_off += size

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
            setattr(instance, field, values[i])

        instance.pre_init()
        instance.initialized = True
        instance.post_init()
        return instance

    @property
    def type_name(self):
        return self.__class__.__name__

    @property
    def description(self):
        return ""

    @property
    def raw(self):
        raw = bytearray()
        for field in self._fields:
            size = self._field_sizes[field]

            field_dat = getattr(self, field)

            data = None

            if isinstance(field_dat, int):
                data = field_dat.to_bytes(size, byteorder=self.byte_order)
            elif isinstance(field_dat, bytearray) or isinstance(field_dat, bytes):
                data = field_dat
            elif isinstance(field_dat, str):
                data = field_dat.encode('utf-8')
                pad_size = size & size_mask
                if len(data) < pad_size:
                    data += b'\x00' * (pad_size - len(data))
            elif issubclass(size, Struct):
                data = field_dat.raw

            assert data is not None

            raw += bytearray(data)

        return raw

    def __eq__(self, other):
        try:
            for field in self._fields:
                if getattr(self, field) != getattr(other, field):
                    return False
        except AttributeError:
            return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return str(self)

    def __str__(self):
        text = f'{self.__class__.__name__}('
        for field in self._fields:
            field_item = None
            try:
                attr = getattr(self, field)
            except AttributeError:
                attr = self._field_sizes[field]
            if isinstance(attr, str):
                field_item = attr
            elif isinstance(attr, bytearray) or isinstance(attr, bytes):
                field_item = attr
            elif isinstance(attr, int):
                field_item = hex(attr)
            elif isinstance(attr, Bitfield):
                attr: Bitfield = attr
                field_item = ''
                for subfield in attr.fields:
                    field_item += subfield + '=' + str(getattr(self, subfield)) + ', '
            elif issubclass(attr.__class__, Struct):
                field_item = str(attr)
            text += f'{field}={field_item}, '
        return text[:-2] + ')'

    def render_indented(self, indent_size=2) -> str:
        text = f'{self.__class__.__name__}\n'
        for field in self._fields:
            try:
                attr = getattr(self, field)
            except AttributeError:
                attr = self._field_sizes[field]
            field_item = None
            if isinstance(attr, str):
                field_item = attr
            elif isinstance(attr, bytearray) or isinstance(attr, bytes):
                field_item = attr
            elif isinstance(attr, int):
                field_item = hex(attr)
            elif isinstance(attr, Bitfield):
                attr: Bitfield = attr
                field_item = '\n'
                for subfield in attr.fields:
                    field_item += " " * (indent_size + 2) + subfield + '=' + str(getattr(self, subfield)) + '\n'
            elif issubclass(attr.__class__, Struct):
                field_item = '\n' + " " * (indent_size + 2) + attr.render_indented(indent_size + 2)
            text += f'{" " * indent_size}{field}={field_item}\n'
        return text

    def serialize(self):
        struct_dict = {'type': self.__class__.__name__}

        for field in self._fields:
            field_item = None
            if isinstance(getattr(self, field), str):
                field_item = getattr(self, field)
            elif isinstance(getattr(self, field), bytearray) or isinstance(getattr(self, field), bytes):
                field_item = _bytes_to_hex(getattr(self, field))
            elif isinstance(getattr(self, field), int):
                field_item = getattr(self, field)
            elif issubclass(getattr(self, field).__class__, Struct):
                field_item = getattr(self, field).serialize()
            struct_dict[field] = field_item

        return struct_dict

    def __init__(self, fields=None, sizes=None, byte_order="little"):
        if hasattr(self.__class__, 'FIELDS'):
            # new method
            fields = list(self.__class__.FIELDS.keys())
            sizes = list(self.__class__.FIELDS.values())
        else:
            if sizes is None:
                raise AssertionError(
                    "Do not use the bare Struct class; it must be implemented in an actual type; Missing Sizes")

            if fields is None:
                raise AssertionError(
                    "Do not use the bare Struct class; it must be implemented in an actual type; Missing Fields")

            fields = list(fields)
            sizes = list(sizes)

        self.initialized = False

        self.super = super()
        self._fields = fields
        self.byte_order = byte_order

        self._field_sizes = {}
        self._field_offsets = {}

        for index, i in enumerate(fields):
            self._field_sizes[i] = sizes[index]

        self.off = 0

    def pre_init(self):
        """stub for subclasses. gets called before patch code is enabled"""
        pass

    def post_init(self):
        """stub for subclasses. gets called *after* patch code is enabled"""
        pass
