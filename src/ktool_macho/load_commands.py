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
#  Copyright (c) 0cyn 2022.
#
from typing import Union

from ktool_macho import segment_command, segment_command_64, section_64, section, SectionType, S_FLAGS_MASKS, Struct, \
    symtab_command, LOAD_COMMAND
from ktool_macho.base import Constructable


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

        ea = command.off + command.size()

        for sect in range(command.nsects):
            sect = image.read_struct(ea, section_64 if lc.is64 else section)
            _section = Section(sect)
            lc.sections[sect.name] = _section
            ea += section_64.size() if lc.is64 else section.size()

        return lc

    @classmethod
    def from_values(cls, is_64, name, vm_addr, vm_size, file_addr, file_size, maxprot, initprot, flags, sections):
        lc = SegmentLoadCommand()

        assert len(name) <= 16

        command_type = segment_command_64 if is_64 else segment_command
        section_type = section_64 if is_64 else section
        cmd = 0x19 if is_64 else 0x1

        cmdsize = command_type.size()
        cmdsize += (len(sections) * section_type.size())

        command = Struct.create_with_values(command_type,
                                            [cmd, cmdsize, name, vm_addr, vm_size, file_addr, file_size, maxprot,
                                             initprot, len(sections), flags])

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


class SymtabLoadCommand(LoadCommand):
    @classmethod
    def from_image(cls, command: symtab_command):
        lc = SymtabLoadCommand()

        lc.cmd = command

        lc.symtab_offset = command.symoff
        lc.symtab_entry_count = command.nsyms
        lc.string_table_offset = command.stroff
        lc.string_table_size = command.strsize

        return lc

    @classmethod
    def from_values(cls, symtab_offset, symtab_size, string_table_offset, string_table_size):
        cmd = Struct.create_with_values(symtab_command, [LOAD_COMMAND.SYMTAB.value, symtab_command.size(), symtab_offset,
                                                         symtab_size, string_table_offset, string_table_size])

        return cls.from_image(cmd)

    def __init__(self):
        self.cmd = None

        self.symtab_offset = 0
        self.symtab_entry_count = 0
        self.string_table_offset = 0
        self.string_table_size = 0

    def raw_bytes(self):
        return self.cmd.raw

# TODO: Constructable wrapper for dylinker_command, build_version_command
