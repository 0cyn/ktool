
from .structs import *

class Protocol:
    def __init__(self, library, objc_class, protocol: objc2_prot, vmaddr: int):
        self.name = library.get_cstr_at(protocol.name, 0, vm=True)

    def __str__(self):
        return self.name