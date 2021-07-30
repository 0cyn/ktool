__all__ = ['Segment', 'Section']

from .structs import *

class Segment:
    """


    segment_command_64:
    ["off", "cmd", "cmdsize", "segname", "vmaddr", "vmsize", "fileoff", "filesize",
        "maxprot", "initprot", "nsects", "flags"]
    """
    def __init__(self, library, cmd):
        self.library = library
        self.cmd = cmd
        self.vmaddr = cmd.vmaddr
        self.fileaddr = cmd.fileoff
        self.size = cmd.vmsize
        self.name = ""
        for i, c in enumerate(hex(cmd.segname)[2:]):
            if i % 2 == 0:
                self.name += chr(int(c + hex(cmd.segname)[2:][i+1], 16))
        self.name = self.name[::-1]
        self.sections = self._process_sections()

    def _process_sections(self):
        sections = {}
        ea = self.cmd.off + sizeof(segment_command_64_t)

        for section in range(0, self.cmd.nsects):
            sect = self.library.load_struct(ea, section_64_t)
            section = Section(self, sect)
            sections[section.name] = section
            ea += sizeof(section_64_t)

        ea += sizeof(segment_command_64_t)
        return sections


class Section:
    """


    section_64
     ["off",
     "sectname",
     "segname",
     "addr", VM ADDRESS
     "size", SIZE ON BOTH
     "offset", FILE ADDRESS
     "align", "reloff", "nreloc", "flags", "void1", "void2", "void3"]
    """
    def __init__(self, segment, cmd):
        self.cmd = cmd
        self.segment = segment
        self.name = segment.library.get_str_at(cmd.off, 16)
        self.vmaddr = cmd.addr
        self.fileaddr = cmd.offset
        self.size = cmd.size
