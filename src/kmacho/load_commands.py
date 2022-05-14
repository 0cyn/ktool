#
#  ktool | ktool
#  load_commands.py
#
#
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2022.
#
from typing import Union

from kmacho import segment_command, segment_command_64, section_64, section, SectionType, S_FLAGS_MASKS, Struct
from kmacho.base import Constructable


class LoadCommand(Constructable):
    @classmethod
    def from_image(cls, *args, **kwargs):
        pass

    @classmethod
    def from_values(cls, *args, **kwargs):
        pass

    def raw_bytes(self):
        pass


class Section:
    """

    """

    def __init__(self, cmd):
        self.cmd = cmd
        self.name = cmd.sectname
        self.vm_address = cmd.addr
        self.file_address = cmd.offset
        self.size = cmd.size

    def serialize(self):
        return {
            'command': self.cmd.serialize(),
            'name': self.name,
            'vm_address': self.vm_address,
            'file_address': self.file_address,
            'size': self.size
        }


class SegmentLoadCommand(LoadCommand):

    @classmethod
    def from_image(cls, image, command: Union[segment_command, segment_command_64]) -> 'SegmentLoadCommand':
        lc = SegmentLoadCommand()

        lc.cmd = command

        lc.vm_address = command.vmaddr
        lc.file_address = command.fileoff
        lc.size = command.vmsize
        lc.name = command.segname
        lc.type = SectionType(S_FLAGS_MASKS.SECTION_TYPE & command.flags)
        lc.is64 = isinstance(command, segment_command_64)

        ea = command.off + command.SIZE

        for sect in range(command.nsects):
            sect = image.load_struct(ea, section_64 if lc.is64 else section)
            _section = Section(sect)
            lc.sections[sect.name] = _section
            ea += section_64.SIZE if lc.is64 else section.SIZE

        return lc

    @classmethod
    def from_values(cls, is_64, name, vm_addr, vm_size, file_addr, file_size, maxprot, initprot, flags, sections):
        lc = SegmentLoadCommand()

        assert len(name) <= 16

        command_type = segment_command_64 if is_64 else segment_command
        section_type = section_64 if is_64 else section
        cmd = 0x19 if is_64 else 0x1

        cmdsize = command_type.SIZE
        cmdsize += (len(sections) * section_type.SIZE)

        command = Struct.create_with_values(command_type, [cmd, cmdsize, name, vm_addr, vm_size, file_addr, file_size, maxprot, initprot, len(sections), flags])

        lc.cmd = command

        lc.vm_address = command.vmaddr
        lc.file_address = command.fileoff
        lc.size = command.vmsize
        lc.name = command.segname
        lc.type = SectionType(S_FLAGS_MASKS.SECTION_TYPE & command.flags)
        lc.is64 = isinstance(command, segment_command_64)

        lc.sections = {_section.name: _section for _section in sections}

        return lc

    def raw_bytes(self):
        
        data = bytearray()
        data += bytearray(self.cmd.raw)
        for _section in self.sections.values():
            data += bytearray(_section.cmd.raw)

        return data

    def __init__(self):

        self.cmd = None

        self.is64 = False

        self.vm_address = 0
        self.file_address = 0
        self.size = 0
        self.name = ""
        self.type = None

        self.sections = {}

# TODO: Constructable wrapper for dylinker_command, build_version_command
