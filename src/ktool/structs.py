#
#  ktool | ktool
#  structs.py
#
#  This file contains objc2 structs conforming to the ktool_macho struct system.
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) 0cyn 2021.
#

from lib0cyn.structs import *


class objc2_class(Struct):
    FIELDS = {
        'isa': uintptr_t,
        'superclass': uintptr_t,
        'cache': uintptr_t,
        'vtable': uintptr_t,
        'info': uintptr_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.isa = 0
        self.superclass = 0
        self.cache = 0
        self.vtable = 0
        self.info = 0


class objc2_class_ro(Struct):
    FIELDS = {
        'flags': uint32_t,
        'ivar_base_start': uint32_t,
        'ivar_base_size': uint32_t,
        'reserved': pad_for_64_bit_only(4),
        'ivar_lyt': uintptr_t,
        'name': uintptr_t,
        'base_meths': uintptr_t,
        'base_prots': uintptr_t,
        'ivars': uintptr_t,
        'weak_ivar_lyt': uintptr_t,
        'base_props': uintptr_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
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
    FIELDS = {
        'selector': uintptr_t,
        'types': uintptr_t,
        'imp': uintptr_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.selector = 0
        self.types = 0
        self.imp = 0


class objc2_meth_list_entry(Struct):
    FIELDS = {
        'selector': uint32_t,
        'types': uint32_t,
        'imp': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.selector = 0
        self.types = 0
        self.imp = 0


class objc2_meth_list(Struct):
    FIELDS = {
        'entrysize': uint32_t,
        'count': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.entrysize = 0
        self.count = 0


class objc2_prop_list(Struct):
    FIELDS = {
        'entrysize': uint32_t,
        'count': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.entrysize = 0
        self.count = 0


class objc2_prop(Struct):
    FIELDS = {
        'name': uintptr_t,
        'attr': uintptr_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)

        self.name = 0
        self.attr = 0


class objc2_prot_list(Struct):
    FIELDS = {
        'cnt': uint64_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.cnt = 0


class objc2_prot(Struct):
    FIELDS = {
        'isa': uintptr_t,
        'name': uintptr_t,
        'prots': uintptr_t,
        'inst_meths': uintptr_t,
        'class_meths': uintptr_t,
        'opt_inst_meths': uintptr_t,
        'opt_class_meths': uintptr_t,
        'inst_props': uintptr_t,
        'cb': uint32_t,
        'flags': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
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
    FIELDS = {
        'entrysize': uint32_t,
        'cnt': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.entrysize = 0
        self.cnt = 0


class objc2_ivar(Struct):
    FIELDS = {
        'offs': uintptr_t,
        'name': uintptr_t,
        'type': uintptr_t,
        'align': uint32_t,
        'size': uint32_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.offs = 0
        self.name = 0


class objc2_category(Struct):
    FIELDS = {
        'name': uintptr_t,
        's_class': uintptr_t,
        'inst_meths': uintptr_t,
        'class_meths': uintptr_t,
        'prots': uintptr_t,
        'props': uintptr_t
    }

    def __init__(self, byte_order="little"):
        super().__init__(byte_order=byte_order)
        self.name = 0
        self.s_class = 0
        self.inst_meths = 0
        self.class_meths = 0
        self.prots = 0
        self.props = 0
