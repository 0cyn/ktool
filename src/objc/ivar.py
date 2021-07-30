
from .structs import *
from .type import *

# 00000000
# 00000000 __objc2_ivar    struc ; (sizeof=0x20, align=0x8, copyof_43)

# 00000000 offs            DCQ ?  ; VM Address, stores the actual static location of the variable
# 00000008 name            DCQ ?  ; VM Address, pointer to the name string
# 00000010 type            DCQ ?  ; VM Address, String offset, `@"TypeName"0x00` style type string
# 00000018 align           DCD ?  ; Align
# 0000001C size            DCD ?  ; Size in bytes of the ivar at `offs`
# 00000020 __objc2_ivar    ends
# 00000020


class Ivar:
    def __init__(self, library, objc_class, ivar: objc2_ivar, vmaddr: int):
        self.name = library.get_cstr_at(ivar.name, 0, True, "__objc_methname")
        type_string = library.get_cstr_at(ivar.type, 0, True, "__objc_methtype")
        self.is_id = type_string[0] == "@"
        self.type = self._renderable_type(library.tp.process(type_string)[0])

    def __str__(self):
        ret = ""
        ret += self.type + ' '
        if self.is_id:
            ret += '*'
        ret += self.name
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
        return(str(type))