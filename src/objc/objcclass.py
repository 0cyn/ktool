from .structs import *
from .method import Method
from .property import Property
from .protocol import Protocol
from .ivar import Ivar

class Class:
    """
    Objective C Class
    This can be a superclass, metaclass, etc
    can represent literally anything that's a "class" struct


    objc2_class = ["off", "isa", "superclass", "cache", "vtable",
    "info" :  VM pointer to objc2_class_ro
    ]

    objc2_class_ro = ["off", "flags", "ivar_base_start", "ivar_base_size", "reserved", "ivar_lyt", "name", "base_meths", "base_prots", "ivars", "weak_ivar_lyt", "base_props"]
    """

    def __init__(self, library, ptr: int, meta=False, objc2class=None):
        self.library = library
        self.ptr = ptr
        self.meta = meta
        self.metaclass = None
        self.superclass = ""
        self.linkedlibs = []
        # Classes imported in this class from the same mach-o
        if not objc2class:
            self.objc2_class: objc2_class = self._load_objc2_class(ptr)
        else:
            self.objc2_class = objc2class

        self.objc2_class_ro = self.library.load_struct(self.objc2_class.info, objc2_class_ro_t, vm=True)

        self._process_structs()

        self.methods = self._process_methods()
        self.properties = self._process_props()
        self.protocols = self._process_prots()
        self.ivars = self._process_ivars()
        self._load_linked_libraries()


    def __str__(self):
        ret = ""
        ret += self.name
        return ret

    def _load_linked_libraries(self):
        pass

    def _load_objc2_class(self, ptr):

        objc2_class_location = self.library.get_bytes(ptr, 8, vm=True)
        objc2_class_item: objc2_class = self.library.load_struct(objc2_class_location, objc2_class_t, vm=True)

        bad_addr = False
        try:
            objc2_superclass: objc2_class = self.library.load_struct(objc2_class_item.superclass, objc2_class_t)
        except:
            bad_addr = True

        if objc2_class_item.isa != 0 and objc2_class_item.isa <= 0xFFFFFFFFFF and not self.meta:
            try:
                metaclass_item: objc2_class = self.library.load_struct(objc2_class_item.isa, objc2_class_t)
                self.metaclass = Class(self.library, metaclass_item.off, True, metaclass_item)
            except ValueError:
                pass
        return objc2_class_item

    def _process_structs(self):
        try:
            self.name = self.library.get_cstr_at(self.objc2_class_ro.name, 0, vm=True)
        except ValueError as ex:
            pass

    def _process_methods(self):
        methods = []

        if self.objc2_class_ro.base_meths == 0:
            return methods # Useless Subclass

        vm_ea = self.objc2_class_ro.base_meths
        methlist_head = self.library.load_struct(self.objc2_class_ro.base_meths, objc2_meth_list_t)
        ea = methlist_head.off

        # https://github.com/arandomdev/DyldExtractor/blob/master/DyldExtractor/objc/objc_structs.py#L79
        RELATIVE_METHODS_SELECTORS_ARE_DIRECT_FLAG = 0x40000000
        RELATIVE_METHOD_FLAG = 0x80000000
        METHOD_LIST_FLAGS_MASK = 0xFFFF0000

        uses_relative_methods = methlist_head.entrysize & METHOD_LIST_FLAGS_MASK != 0

        ea += 8
        vm_ea += 8
        for i in range(1, methlist_head.count+1):
            if uses_relative_methods:
                meth = self.library.load_struct(ea, objc2_meth_list_entry_t, vm=False)
            else:
                meth = self.library.load_struct(ea, objc2_meth_t, vm=False)
            try:
                methods.append(Method(self.library, self, meth, vm_ea))
            except Exception as ex:
                continue
            if uses_relative_methods:
                ea += sizeof(objc2_meth_list_entry_t)
                vm_ea += sizeof(objc2_meth_list_entry_t)
            else:
                ea += sizeof(objc2_meth_t)
                vm_ea += sizeof(objc2_meth_t)

        return methods

    def _process_props(self):
        properties = []

        if self.objc2_class_ro.base_props == 0:
            return properties

        vm_ea = self.objc2_class_ro.base_props
        proplist_head = self.library.load_struct(self.objc2_class_ro.base_props, objc2_prop_list_t)

        ea = proplist_head.off
        ea += 8
        vm_ea += 8

        for i in range(1, proplist_head.count+1):
            prop = self.library.load_struct(ea, objc2_prop_t, vm=False)
            try:
                properties.append(Property(self.library, self, prop, vm_ea))
            except ValueError as ex:
                # continue
                raise ex
            ea += sizeof(objc2_prop_t)
            vm_ea += sizeof(objc2_prop_t)

        return properties

    def _process_prots(self):
        prots = []
        if self.objc2_class_ro.base_prots == 0:
            return prots
        protlist: objc2_prot_list = self.library.load_struct(self.objc2_class_ro.base_prots, objc2_prot_list_t)
        ea = protlist.off
        for i in range(1, protlist.cnt+1):
            prot_loc = self.library.get_bytes(ea + i*8, 8, vm=True)
            prot = self.library.load_struct(prot_loc, objc2_prot_t)
            prots.append(Protocol(self.library, self, prot, prot_loc))
        return prots

    def _process_ivars(self):
        ivars = []
        if self.objc2_class_ro.ivars == 0:
            return ivars
        ivarlist: objc2_ivar_list = self.library.load_struct(self.objc2_class_ro.ivars, objc2_ivar_list_t)
        ea = ivarlist.off + 8
        for i in range(1, ivarlist.cnt+1):
            ivar_loc = ea + sizeof(objc2_ivar_t)*(i-1)
            ivar = self.library.load_struct(ivar_loc, objc2_ivar_t)
            ivars.append(Ivar(self.library, self, ivar, ivar_loc))
        return ivars
