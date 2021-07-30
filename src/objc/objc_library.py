from macho.library import Library

from .structs import *
from .type import TypeProcessor

from .objcclass import Class
from macho.segment import Segment, Section


class ObjCLibrary:
    def __init__(self, library):
        self.library = library
        self.tp = TypeProcessor()
        self.name = library.name

        self.classlist = self._generate_classlist(None)

    def _generate_classlist(self, classlimit):
        sect: Section = self.library.segments['__DATA_CONST'].sections['__objc_classlist']
        classes = []
        cnt = sect.size // 0x8
        for i in range(0, cnt):
            if classlimit is None:
                classes.append(Class(self, sect.vmaddr + i * 0x8))
            else:
                oc = Class(self, sect.vmaddr + i * 0x8)
                if classlimit == oc.name:
                    classes.append(oc)
        return classes

    def get_bytes(self, offset: int, length: int, vm=False, sectname=None):
        return self.library.get_bytes(offset, length, vm, sectname)

    def load_struct(self, addr: int, struct_type: struct, vm=True, sectname=None, endian="little"):
        return self.library.load_struct(addr, struct_type, vm, sectname, endian)

    def get_str_at(self, addr: int, count: int, vm=True, sectname=None):
        return self.library.get_str_at(addr, count, vm, sectname)

    def get_cstr_at(self, addr: int, limit: int = 0, vm=True, sectname=None):
        return self.library.get_cstr_at(addr, limit, vm, sectname)
