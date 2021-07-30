
# Cell
from collections import namedtuple

from .segment import Segment, Section

# Cell
vm_obj = namedtuple("vm_obj", ["vmaddr", "vmend", "size", "fileaddr", "name"])


class _VirtualMemoryMap:
    """
    Virtual Memory is the location "in memory" where the library/bin, etc will be accessed when ran
    This is not where it actually sits in memory at runtime; it will be slid, but the program doesnt know and doesnt care
    The slid address doesnt matter to us either, we only care about the addresses the rest of the file cares about

    There are two address sets used in mach-o files: vm, and file. (commonly; vmoff and fileoff)
    For example, when reading raw data of an executable binary:
    0x0 file offset will (normally?) map to 0x10000000 in the VM

    These VM offsets are relayed to the linker via Load Commands
    Some locations in the file do not have VM counterparts (examples being symbol table(citation needed))

    Some other VM related offsets are changed/modified via binding info(citation needed)
    """

    def __init__(self, slice):
        # name: vm_obj
        self.slice = slice
        self.map = {}
        self.stats = {}

    def __str__(self):
        """
        We want to be able to just call print(macho.vm) to display the filemap in a human-readable format

        :return: multiline String representation of the filemap
        """

        ret = ""
        # Sort our map by VM Address, this should already be how it is but cant hurt
        sortedmap = {k: v for k, v in sorted(self.map.items(), key=lambda item: item[1].vmaddr)}

        for (key, obj) in sortedmap.items():
            # 'string'.ljust(16) adds space padding
            # 'string'[2:].zfill(9) removes the first 2 chars and pads the string with 9 zeros
            #       then we just re-add the 0x manually.

            # this gives us a nice list with visually clear columns and rows
            ret += f'{key.ljust(16)}  ||  Start: 0x{hex(obj.vmaddr)[2:].zfill(9)}  |  End: 0x{hex(obj.vmend)[2:].zfill(9)}  |  Size: 0x{hex(obj.size)[2:].zfill(9)}  |  Slice ' \
                   f'Offset:  0x{hex(obj.fileaddr)[2:].zfill(9)}  ||  File Offset: 0x{hex(obj.fileaddr + self.slice.offset)[2:].zfill(9)}\n'
        return ret

    def get_vm_start(self):
        """
        Get the address the VM starts in, excluding __PAGEZERO
        Method selector dumping uses this
        :return:
        """
        sortedmap = {k: v for k, v in sorted(self.map.items(), key=lambda item: item[1].vmaddr)}
        if list(sortedmap.keys())[0] == "__PAGEZERO":
            return list(sortedmap.values())[1].vmaddr
        else:
            return list(sortedmap.values())[0].vmaddr

    def get_file_address(self, vm_address: int, sname = None):
        # This function gets called hundreds of thousands of times during processing and is the main source of overhead
        if sname is not None:
            o = self.map[sname]
            if vm_address >= o.vmaddr and o.vmend >= vm_address:
                return o.fileaddr + vm_address - o.vmaddr
            else:
                try:
                    o = self.map['__EXTRA_OBJC']
                    if vm_address >= o.vmaddr and o.vmend >= vm_address:
                        return o.fileaddr + vm_address - o.vmaddr
                except:
                    for o in self.map.values():
                        if vm_address >= o.vmaddr and o.vmend >= vm_address:
                            # self.stats[o.name] += 1
                            return o.fileaddr + vm_address - o.vmaddr
        for o in self.map.values():
            if vm_address >= o.vmaddr and o.vmend >= vm_address:
                #self.stats[o.name] += 1
                return o.fileaddr + vm_address - o.vmaddr
        #print(f'VM MAPPING:')
        #print(self)
        raise ValueError(f'Address {hex(vm_address)} couldn\'t be found in vm address set')

    def add_segment(self, segment: Segment):
        if len(segment.sections) == 0:
            seg_obj = vm_obj(segment.vmaddr, segment.vmaddr+segment.size, segment.size, segment.fileaddr, segment.name)
            self.map[segment.name] = seg_obj
            self.stats[segment.name] = 0
        else:
            for section in segment.sections.values():
                name = section.name if section.name not in self.map.keys() else section.name + '2'
                sect_obj = vm_obj(section.vmaddr, section.vmaddr+section.size, section.size, section.fileaddr, name)
                self.map[name] = sect_obj
                self.smap = {k: v for k, v in sorted(self.map.items(), key=lambda item: item[1].vmaddr)}
                self.stats[name] = 0






