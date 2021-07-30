
from .structs import *
from .type import *


class Method:
    def __init__(self, library, objc_class, method: objc2_meth, vmaddr: int):
        self.objc_class = objc_class

        try:
            self.sel = library.get_cstr_at(method.selector, 0, vm=True, sectname="__objc_methname")
            typestr = library.get_cstr_at(method.types, 0, vm=True, sectname="__objc_methtype")
        except ValueError as ex:
            selref = library.get_bytes(method.selector+vmaddr, 8, vm=True)
            self.sel = library.get_cstr_at(selref, 0, vm=True, sectname="__objc_methname")
            typestr = library.get_cstr_at(method.types+vmaddr+4, 0, vm=True, sectname="__objc_methtype")
        except Exception as ex:
            raise ex

        self.typestr = typestr
        self.types = library.tp.process(typestr)
        if len(self.types) == 0:
            raise ValueError("Empty Typestr")

        self.return_string = self._renderable_type(self.types[0])
        self.arguments = [self._renderable_type(i) for i in self.types[1:]]

        self.signature = self._build_method_signature()

    def __str__(self):
        ret = ""
        ret += self.signature
        return ret

    @staticmethod
    def _renderable_type(type: Type):
        if type.type == EncodedType.NORMAL:
            return str(type)
        elif type.type == EncodedType.STRUCT:
            ptraddon = ""
            for i in range(0, type.pointer_count):
                ptraddon += '*'
            return ptraddon + type.value.name

    def _build_method_signature(self):
        dash = "+" if self.objc_class.meta else "-"
        ret = "(" + self.return_string + ")"

        if len(self.arguments) == 0:
            return dash + ret + self.sel

        segs = []
        for i, item in enumerate(self.sel.split(':')):
            if item == "":
                continue
            try:
                segs.append(item + ':' + '(' + self.arguments[i+2] + ')' + 'arg' + str(i) + ' ')
            except IndexError:
                segs.append(item)

        sig = ''.join(segs)

        return dash + ret + sig
