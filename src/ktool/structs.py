#
#  ktool | ktool
#  structs.py
#
#  This file contains objc2 structs conforming to the kmacho struct system.
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2021.
#

from kmacho.structs import Struct


class objc2_class(Struct):
    _FIELDNAMES = ['isa', 'superclass', 'cache', 'vtable', 'info']
    _SIZES = [8, 8, 8, 8, 8]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.isa = 0
        self.superclass = 0
        self.cache = 0
        self.vtable = 0
        self.info = 0


class objc2_class_ro(Struct):
    _FIELDNAMES = ['flags', 'ivar_base_start', 'ivar_base_size', 'reserved', 'ivar_lyt',
                   'name', 'base_meths', 'base_prots', 'ivars', 'weak_ivar_lyt', 'base_props']
    _SIZES = [4, 4, 4, 4, 8, 8, 8, 8, 8, 8, 8]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.flags = 0
        self.ivar_base_start = 0
        self.ivar_base_size = 0
        self.reserved = 0
        self.ivar_lyt = 0
        self.name = 0
        self.base_meths = 0
        self.base_prots = 0
        self.ivars = 0
        self.weak_ivar_lyt = 0
        self.base_props = 0


class objc2_meth(Struct):
    _FIELDNAMES = ['selector', 'types', 'imp']
    _SIZES = [8, 8, 8]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.selector = 0
        self.types = 0
        self.imp = 0


class objc2_meth_list_entry(Struct):
    _FIELDNAMES = ['selector', 'types', 'imp']
    _SIZES = [4, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.selector = 0
        self.types = 0
        self.imp = 0


class objc2_meth_list(Struct):
    _FIELDNAMES = ['entrysize', 'count']
    _SIZES = [4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.entrysize = 0
        self.count = 0


class objc2_prop_list(Struct):
    _FIELDNAMES = ['entrysize', 'count']
    _SIZES = [4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.entrysize = 0
        self.count = 0


class objc2_prop(Struct):
    _FIELDNAMES = ['name', 'attr']
    _SIZES = [8, 8]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)

        self.name = 0
        self.attr = 0

class objc2_prot_list(Struct):
    _FIELDNAMES = ['cnt']
    _SIZES = [8]
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.cnt = 0


class objc2_prot(Struct):
    _FIELDNAMES = ['isa', 'name', 'prots', 'inst_meths', 'class_meths', 'opt_inst_meths', 'opt_class_meths',
                   'inst_props', 'cb', 'flags']
    _SIZES = [8, 8, 8, 8, 8, 8, 8, 8, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.isa = 0
        self.name = 0
        self.prots = 0
        self.inst_meths = 0
        self.class_meths = 0
        self.opt_inst_meths = 0
        self.opt_class_meths = 0
        self.inst_props = 0
        self.cb = 0
        self.flags = 0


class objc2_ivar_list(Struct):
    _FIELDNAMES = ['entrysize', 'cnt']
    _SIZES = [4, 4]
    SIZE = 8

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.entrysize = 0
        self.cnt = 0


class objc2_ivar(Struct):
    _FIELDNAMES = ['offs', 'name', 'type', 'align', 'size']
    _SIZES = [8, 8, 8, 4, 4]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.offs = 0
        self.name = 0


class objc2_category(Struct):
    _FIELDNAMES = ['name', 's_class', 'inst_meths', 'class_meths', 'prots', 'props']
    _SIZES = [8, 8, 8, 8, 8, 8]
    SIZE = sum(_SIZES)

    def __init__(self, byte_order="little"):
        super().__init__(fields=self._FIELDNAMES, sizes=self._SIZES, byte_order=byte_order)
        self.name = 0
        self.s_class = 0
        self.inst_meths = 0
        self.class_meths = 0
        self.prots = 0
        self.props = 0
