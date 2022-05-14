#
#  ktool | ktool
#  loader.py
#
#  This file includes a lot of utilities, classes, and abstractions
#  designed for replicating certain functionality within dyld.
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2021.
#
from collections import namedtuple
from typing import List, Union, Dict

from kmacho import (
    MH_FLAGS,
    MH_FILETYPE,
    LOAD_COMMAND,
    BINDING_OPCODE,
    LOAD_COMMAND_MAP,
    BIND_SUBOPCODE_THREADED_SET_BIND_ORDINAL_TABLE_SIZE_ULEB,
    BIND_SUBOPCODE_THREADED_APPLY, MH_MAGIC_64, CPUType, CPUSubTypeARM64, MH_MAGIC
)
from kmacho.base import Constructable
from kmacho.fixups import *
from ktool.codesign import CodesignInfo
from ktool.macho import Segment, Slice, MachOImageHeader, PlatformType
from ktool.util import log, macho_is_malformed, ignore, bytes_to_hex
from ktool.image import Image, os_version, LinkedImage


class MachOImageLoader:
    """
    This class takes our initialized "Image" object, parses through the raw data behind it, and fills out its properties.

    """

    @classmethod
    def load(cls, macho_slice: Slice, load_symtab=True, load_imports=True, load_exports=True) -> Image:
        """
        Take a slice of a macho file and process it using the dyld functions

        :param load_exports: Load Exports
        :param load_imports: Load Imports
        :param load_symtab: Load Symbol Table
        :param macho_slice: Slice to load. If your image is not fat, that'll be MachOFile.slices[0]
        :type macho_slice: Slice
        :return: Processed image object
        :rtype: Image
        """
        log.info("Loading image")
        image = Image(macho_slice)

        log.info("Processing Load Commands")
        MachOImageLoader._parse_load_commands(image, load_symtab, load_imports, load_exports)

        log.info("Processing Image")
        MachOImageLoader._process_image(image)
        return image

    @classmethod
    def _parse_load_commands(cls, image: Image, load_symtab=True, load_imports=True, load_exports=True) -> None:
        # noinspection PyUnusedLocal
        fixups = None
        log.info(f'registered {len(image.macho_header.load_commands)} Load Commands')
        for cmd in image.macho_header.load_commands:
            try:
                load_command = LOAD_COMMAND(cmd.cmd)
            except ValueError:
                continue

            if load_command == LOAD_COMMAND.SEGMENT_64 or load_command == LOAD_COMMAND.SEGMENT:
                log.debug_tm("Loading Segment")
                segment = Segment(image, cmd)

                log.info(f'Loaded Segment {segment.name}')
                image.vm.add_segment(segment)
                image.segments[segment.name] = segment

            elif load_command in [LOAD_COMMAND.THREAD, LOAD_COMMAND.UNIXTHREAD]:
                thread_state = []
                for i in range(cmd.count):
                    off = cmd.off + 16 + (i * 4)
                    val = image.get_int_at(off, 4)
                    thread_state.append(val)

                image.thread_state = thread_state

            elif load_command == LOAD_COMMAND.CODE_SIGNATURE:
                image._codesign_cmd = cmd
                image.codesign_info = CodesignInfo.from_image(image, cmd)

            elif load_command == LOAD_COMMAND.MAIN:
                image._entry_off = cmd.entryoff

            elif load_command == LOAD_COMMAND.DYLD_INFO_ONLY:
                image.info = cmd

                if load_imports:
                    log.info("Loading Binding Info")
                    image.binding_table = BindingTable(image, cmd.bind_off, cmd.bind_size)
                    image.weak_binding_table = BindingTable(image, cmd.weak_bind_off, cmd.weak_bind_size)
                    image.lazy_binding_table = BindingTable(image, cmd.lazy_bind_off, cmd.lazy_bind_size)

                if load_exports:
                    log.info("Loading Export Trie")
                    image.export_trie = ExportTrie.from_image(image, cmd.export_off, cmd.export_size)

            elif load_command == LOAD_COMMAND.FUNCTION_STARTS:
                fs_start = cmd.dataoff
                fs_size = cmd.datasize
                read_head = fs_start

                fs_addr = image.vm.vm_base_addr

                while read_head < fs_start + fs_size:
                    fs_r_addr, read_head = image.decode_uleb128(read_head)
                    fs_addr += fs_r_addr
                    image.function_starts.append(fs_addr)

            elif load_command == LOAD_COMMAND.LC_DYLD_EXPORTS_TRIE:
                log.info("Loading Export Trie")
                image.export_trie = ExportTrie.from_image(image, cmd.dataoff, cmd.datasize)

            elif load_command == LOAD_COMMAND.LC_DYLD_CHAINED_FIXUPS:
                if load_imports:
                    image.chained_fixups = ChainedFixups.from_image(image, cmd)

            elif load_command == LOAD_COMMAND.SYMTAB:
                if load_symtab:
                    log.info("Loading Symbol Table")
                    image.symbol_table = SymbolTable(image, cmd)

            elif load_command == LOAD_COMMAND.DYSYMTAB:
                pass

            elif load_command == LOAD_COMMAND.UUID:
                image.uuid = cmd.uuid
                log.info(f'image UUID: {image.uuid}')

            elif load_command == LOAD_COMMAND.SUB_CLIENT:
                string = image.get_cstr_at(cmd.off + cmd.offset)
                image.allowed_clients.append(string)
                log.debug(f'Loaded Subclient "{string}"')

            elif load_command == LOAD_COMMAND.RPATH:
                string = image.get_cstr_at(cmd.off + cmd.path)
                image.rpath = string
                log.info(f'image Resource Path: {string}')

            elif load_command == LOAD_COMMAND.BUILD_VERSION:
                image.platform = PlatformType(cmd.platform)
                image.minos = os_version(x=image.get_int_at(cmd.off + 14, 2), y=image.get_int_at(cmd.off + 13, 1),
                                         z=image.get_int_at(cmd.off + 12, 1))
                image.sdk_version = os_version(x=image.get_int_at(cmd.off + 18, 2),
                                               y=image.get_int_at(cmd.off + 17, 1),
                                               z=image.get_int_at(cmd.off + 16, 1))
                log.info(f'Loaded platform {image.platform.name} | '
                         f'Minimum OS {image.minos.x}.{image.minos.y}'
                         f'.{image.minos.z} | SDK Version {image.sdk_version.x}'
                         f'.{image.sdk_version.y}.{image.sdk_version.z}')

            elif isinstance(cmd, version_min_command):
                # Only override this if it wasn't set by build_version
                if image.platform == PlatformType.UNK:
                    if load_command == LOAD_COMMAND.VERSION_MIN_MACOSX:
                        image.platform = PlatformType.MACOS
                    elif load_command == LOAD_COMMAND.VERSION_MIN_IPHONEOS:
                        image.platform = PlatformType.IOS
                    elif load_command == LOAD_COMMAND.VERSION_MIN_TVOS:
                        image.platform = PlatformType.TVOS
                    elif load_command == LOAD_COMMAND.VERSION_MIN_WATCHOS:
                        image.platform = PlatformType.WATCHOS

                    image.minos = os_version(x=image.get_int_at(cmd.off + 10, 2),
                                             y=image.get_int_at(cmd.off + 9, 1),
                                             z=image.get_int_at(cmd.off + 8, 1))

            elif load_command == LOAD_COMMAND.ID_DYLIB:
                image.dylib = LinkedImage(image, cmd)
                log.debug(f'Loaded local dylib_command with install_name {image.dylib.install_name}')

            elif isinstance(cmd, dylib_command):
                # noinspection PyTypeChecker
                external_dylib = LinkedImage(image, cmd)

                image.linked_images.append(external_dylib)
                log.debug(f'Loaded linked dylib_command with install name {external_dylib.install_name}')

    @staticmethod
    def _process_image(image: Image) -> None:
        """
        Once all load commands have been processed, process the results.
        This is mainly for things which need to be done once *all* lcs have been processed.

        :param image:
        :return:
        """
        if image.dylib is not None:
            image.name = image.dylib.install_name.split('/')[-1]
            image.base_name = image.dylib.install_name.split('/')[-1]
            image.install_name = image.dylib.install_name
        else:
            image.name = ""
            image.base_name = image.slice.file.name
            image.install_name = ""

        if image.export_trie:
            for symbol in image.export_trie.symbols:
                image.exports.append(symbol)
                image.export_table[symbol.address] = symbol

        if image.binding_table:
            for symbol in image.binding_table.symbol_table:
                symbol.attr = ''
                image.imports.append(symbol)
                image.import_table[symbol.address] = symbol
            for symbol in image.weak_binding_table.symbol_table:
                symbol.attr = 'Weak'
                image.imports.append(symbol)
                image.import_table[symbol.address] = symbol
            for symbol in image.lazy_binding_table.symbol_table:
                symbol.attr = 'Lazy'
                image.imports.append(symbol)
                image.import_table[symbol.address] = symbol

        if image.chained_fixups:
            for symbol in image.chained_fixups.symbols:
                symbol.attr = ''
                image.imports.append(symbol)
                image.import_table[symbol.address] = symbol

        if image.symbol_table:
            for symbol in image.symbol_table.table:
                image.symbols[symbol.address] = symbol

        # noinspection PyProtectedMember
        if len(image.thread_state) > 0:
            image.entry_point = image.thread_state[-4] if image.macho_header.is64 else image.thread_state[-2]

        elif image._entry_off > 0:
            # noinspection PyProtectedMember
            image.entry_point = image.vm.vm_base_addr + image._entry_off


class SymbolType(Enum):
    CLASS = 0
    METACLASS = 1
    IVAR = 2
    FUNC = 3
    UNK = 4


class Symbol(Constructable):
    """
    This class can represent several types of symbols.

    """

    @classmethod
    def from_image(cls, image, cmd, entry):
        fullname = image.get_cstr_at(entry.str_index + cmd.stroff)
        addr = entry.value

        symbol = cls.from_values(fullname, addr)

        N_STAB = 0xe0
        N_PEXT = 0x10
        N_TYPE = 0x0e
        N_EXT = 0x01

        type_masked = N_TYPE & entry.type
        for name, flag in {'N_UNDF': 0x0, 'N_ABS': 0x2, 'N_SECT': 0xe, 'N_PBUD': 0xc, 'N_INDR': 0xa}.items():
            if type_masked & flag:
                symbol.types.append(name)

        if entry.type & N_EXT:
            symbol.external = True

        return symbol

    @classmethod
    def from_values(cls, fullname, value, external=False, ordinal=0):
        if '_$_' in fullname:
            if fullname.startswith('_OBJC_CLASS_$'):
                dec_type = SymbolType.CLASS
            elif fullname.startswith('_OBJC_METACLASS_$'):
                dec_type = SymbolType.METACLASS
            elif fullname.startswith('_OBJC_IVAR_$'):
                dec_type = SymbolType.IVAR
            else:
                dec_type = SymbolType.UNK
            name = fullname.split('$')[1]
        else:
            name = fullname
            dec_type = SymbolType.FUNC

        return cls(fullname, name=name, dec_type=dec_type, external=external, value=value, ordinal=ordinal)

    def raw_bytes(self):
        pass

    def serialize(self):
        return {
            'name': self.fullname,
            'address': self.address,
            'external': self.external,
            'ordinal': self.ordinal
        }

    def __init__(self, fullname=None, name=None, dec_type=None, external=False, value=0, ordinal=0):
        self.fullname = fullname
        self.name = name
        self.dec_type = dec_type

        self.address = value

        self.entry = None
        self.ordinal = ordinal

        self.types = []
        self.external = external

        self.attr = None


class SymbolTable:
    """
    This class represents the symbol table declared in the MachO File

    .table contains the symbol table

    .ext contains exported symbols, i think?

    This class is incomplete

    """

    def __init__(self, image: Image, cmd: symtab_command):
        self.image: Image = image
        self.cmd: symtab_command = cmd

        self.ext: List[Symbol] = []
        self.table: List[Symbol] = self._load_symbol_table()

    def _load_symbol_table(self) -> List[Symbol]:
        symbol_table = []
        read_address = self.cmd.symoff
        typing = symtab_entry if self.image.macho_header.is64 else symtab_entry_32

        for i in range(0, self.cmd.nsyms):
            entry = self.image.load_struct(read_address + typing.SIZE * i, typing)
            symbol = Symbol.from_image(self.image, self.cmd, entry)
            symbol_table.append(symbol)

            if symbol.external:
                self.ext.append(symbol)

            log.debug_tm(f'Symbol Table: Loaded symbol:{symbol.name} ordinal:{symbol.ordinal} type:{symbol.dec_type}')
            log.debug_tm(str(entry))

        return symbol_table


class ChainedFixups(Constructable):
    @classmethod
    def from_image(cls, image: Image, chained_fixup_cmd: linkedit_data_command):

        symbols = []

        import struct

        fixup_hdr_addr = chained_fixup_cmd.dataoff
        fixup_hdr = image.load_struct(fixup_hdr_addr, dyld_chained_fixups_header, vm=False)

        imports_format = dyld_chained_import_format(fixup_hdr.imports_format)

        segs_addr = fixup_hdr_addr + fixup_hdr.starts_offset
        seg_count = image.get_int_at(segs_addr, 4, vm=False)
        imports_addr = fixup_hdr_addr + fixup_hdr.imports_offset

        syms_addr = fixup_hdr_addr + fixup_hdr.symbols_offset

        segs = []
        for i in range(seg_count):
            s = image.get_int_at((i * 4) + segs_addr + 4, 4)  # read
            segs.append(s)

        for i in range(seg_count):
            if segs[i] == 0:
                continue
            starts_addr = (
                    segs_addr + segs[i]
            )

            starts_in_segment_data = image.get_bytes_at(starts_addr, 24)

            starts_in_segment = struct.unpack("<IHHQIHH", starts_in_segment_data)

            page_count = starts_in_segment[5]
            page_size = starts_in_segment[1]
            segment_offset = starts_in_segment[3]
            pointer_type = starts_in_segment[2]

            PTR_STRUCT_TYPE_BASE = DYLD_CHAINED_PTR_BASE[dyld_chained_ptr_format(pointer_type)]
            PTR_STRUCT_TYPE_FUNC = DYLD_CHAINED_PTR_FMATS[dyld_chained_ptr_format(pointer_type)]

            page_starts_data = image.get_bytes_at(starts_addr + 22, page_count * 2)
            page_starts = struct.unpack("<" + ("H" * page_count), page_starts_data)

            for (j, start) in enumerate(page_starts):
                if start == DYLD_CHAINED_PTR_START_NONE:
                    continue

                chain_entry_addr = (
                        segment_offset + (j * page_size) + start
                )

                j += 1
                while True:
                    content = image.get_int_at(chain_entry_addr, 8)
                    item = image.load_struct(chain_entry_addr, PTR_STRUCT_TYPE_BASE, vm=False)
                    item = image.load_struct(chain_entry_addr, PTR_STRUCT_TYPE_FUNC(item), vm=False, force_reload=True)

                    offset = content & 0xFFFFFFFF
                    nxt = (content >> 50) & 2047
                    bind = (content >> 62) & 1
                    if bind == 1:
                        import_entry = image.get_int_at(imports_addr + offset * 4, 4)
                        ordinal = import_entry & 0xFF
                        sym_name_offset = import_entry >> 9
                        sym_name_addr = syms_addr + sym_name_offset

                        sym_name = image.get_cstr_at(
                            sym_name_addr)
                        sym = Symbol.from_values(sym_name, sym_name_addr, True, ordinal)
                        symbols.append(sym)

                    else:
                        pass

                    # next tells us how many u32 until the next chain entry
                    skip = nxt * 4
                    chain_entry_addr += skip
                    # if skip == 0, chain is done
                    if skip == 0:
                        break

        return cls(symbols)

    @classmethod
    def from_values(cls, *args, **kwargs):
        pass

    def raw_bytes(self):
        pass

    def __init__(self, symbols):
        self.symbols = symbols


export_node = namedtuple("export_node", ['text', 'offset', 'flags'])


class ExportTrie(Constructable):
    @classmethod
    def from_image(cls, image: Image, export_start: int, export_size: int) -> 'ExportTrie':
        trie = ExportTrie()

        endpoint = export_start + export_size
        nodes = ExportTrie.read_node(image, export_start, '', export_start, endpoint)
        symbols = []

        for node in nodes:
            if node.text:
                symbols.append(Symbol.from_values(node.text, node.offset, False))

        trie.nodes = nodes
        trie.symbols = symbols
        trie.raw = image.get_bytes_at(export_start, export_size)

        return trie

    @classmethod
    def from_values(cls, *args, **kwargs):
        pass

    def raw_bytes(self):
        return self.raw

    def __init__(self):
        self.raw = bytearray()
        self.nodes: List[export_node] = []
        self.symbols: List[Symbol] = []

    @classmethod
    def read_node(cls, image: Image, trie_start: int, string: str, cursor: int, endpoint: int) -> List[export_node]:

        if cursor > endpoint:
            log.error("Node offset greater than size of export trie")
            macho_is_malformed()

        start = cursor
        byte = image.get_int_at(cursor, 1)
        results = []
        log.debug_tm(f'@ {hex(start)} node: {hex(byte)} current_symbol: {string}')
        if byte == 0:
            cursor += 1
            branches = image.get_int_at(cursor, 1)
            log.debug_tm(f'BRAN {branches}')
            for i in range(0, branches):
                if i == 0:
                    cursor += 1
                proc_str = image.get_cstr_at(cursor)
                cursor += len(proc_str) + 1
                offset, cursor = image.decode_uleb128(cursor)
                log.debug_tm(f'({i}) string: {string + proc_str} next_node: {hex(trie_start + offset)}')
                results += ExportTrie.read_node(image, trie_start, string + proc_str, trie_start + offset, endpoint)
        else:
            log.debug_tm(f'TERM: 0')
            size, cursor = image.decode_uleb128(cursor)
            flags = image.get_int_at(cursor, 1)
            cursor += 1
            offset, cursor = image.decode_uleb128(cursor)
            results.append(export_node(string, offset, flags))

        return results


action = namedtuple("action", ["vmaddr", "libname", "item"])
record = namedtuple("record", [
    "off",
    "seg_index",
    "seg_offset",
    "lib_ordinal",
    "type",
    "flags",
    "name",
    "addend",
    "special_dylib"
])


class BindingTable:
    """
    The binding table contains a ton of information related to the binding info in the image

    .lookup_table - Contains a map of address -> Symbol declarations which should be used for processing off-image
    symbol decorations

    .symbol_table - Contains a full list of symbols declared in the binding info. Avoid iterating through this for
    speed purposes.

    .actions - contains a list of, you guessed it, actions.

    .import_stack - contains a fairly raw unprocessed list of binding info commands

    """

    def __init__(self, image: Image, table_start: int, table_size: int):
        """
        Pass a image to be processed

        :param image: image to be processed
        :type image: Image
        """
        self.image = image
        self.import_stack = self._load_binding_info(table_start, table_size)
        self.actions = self._create_action_list()
        self.lookup_table = {}
        self.link_table = {}
        self.symbol_table = self._load_symbol_table()

    def _load_symbol_table(self) -> List[Symbol]:
        table = []
        for act in self.actions:
            if act.item:
                sym = Symbol.from_values(act.item, act.vmaddr, external=True, ordinal=act.libname)
                table.append(sym)
                self.lookup_table[act.vmaddr] = sym
        return table

    def _create_action_list(self) -> List[action]:
        actions = []
        for bind_command in self.import_stack:
            segment = list(self.image.segments.values())[bind_command.seg_index]
            vm_address = segment.vm_address + bind_command.seg_offset
            try:
                lib = self.image.linked_images[bind_command.lib_ordinal - 1].install_name
            except IndexError:
                lib = str(bind_command.lib_ordinal)
            item = bind_command.name
            actions.append(action(vm_address & 0xFFFFFFFFF, lib, item))
        return actions

    def _load_binding_info(self, table_start: int, table_size: int) -> List[record]:
        read_address = table_start
        import_stack = []
        threaded_stack = []
        uses_threaded_bind = False
        while True:
            if read_address - table_size >= table_start:
                break
            seg_index = 0x0
            seg_offset = 0x0
            lib_ordinal = 0x0
            btype = 0x0
            flags = 0x0
            name = ""
            addend = 0x0
            special_dylib = 0x0
            while True:
                # There are 0xc opcodes total
                # Bitmask opcode byte with 0xF0 to get opcode, 0xF to get value
                binding_opcode = self.image.get_int_at(read_address, 1) & 0xF0
                value = self.image.get_int_at(read_address, 1) & 0x0F
                log.debug_tm(f'{BINDING_OPCODE(binding_opcode).name}: {hex(value)}')
                cmd_start_addr = read_address
                read_address += 1

                if binding_opcode == BINDING_OPCODE.THREADED:
                    if value == BIND_SUBOPCODE_THREADED_SET_BIND_ORDINAL_TABLE_SIZE_ULEB:
                        a_table_size, read_address = self.image.decode_uleb128(read_address)
                        uses_threaded_bind = True
                    elif value == BIND_SUBOPCODE_THREADED_APPLY:
                        pass

                if binding_opcode == BINDING_OPCODE.DONE:
                    import_stack.append(
                        record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend,
                               special_dylib))
                    break

                elif binding_opcode == BINDING_OPCODE.SET_DYLIB_ORDINAL_IMM:
                    lib_ordinal = value

                elif binding_opcode == BINDING_OPCODE.SET_DYLIB_ORDINAL_ULEB:
                    lib_ordinal, read_address = self.image.decode_uleb128(read_address)

                elif binding_opcode == BINDING_OPCODE.SET_DYLIB_SPECIAL_IMM:
                    special_dylib = 0x1
                    lib_ordinal = value

                elif binding_opcode == BINDING_OPCODE.SET_SYMBOL_TRAILING_FLAGS_IMM:
                    flags = value
                    name = self.image.get_cstr_at(read_address)
                    read_address += len(name) + 1

                elif binding_opcode == BINDING_OPCODE.SET_TYPE_IMM:
                    btype = value

                elif binding_opcode == BINDING_OPCODE.SET_ADDEND_SLEB:
                    addend, read_address = self.image.decode_uleb128(read_address)

                elif binding_opcode == BINDING_OPCODE.SET_SEGMENT_AND_OFFSET_ULEB:
                    seg_index = value
                    seg_offset, read_address = self.image.decode_uleb128(read_address)

                elif binding_opcode == BINDING_OPCODE.ADD_ADDR_ULEB:
                    o, read_address = self.image.decode_uleb128(read_address)
                    seg_offset += o

                elif binding_opcode == BINDING_OPCODE.DO_BIND_ADD_ADDR_ULEB:
                    import_stack.append(
                        record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend,
                               special_dylib))
                    seg_offset += 8
                    o, read_address = self.image.decode_uleb128(read_address)
                    seg_offset += o

                elif binding_opcode == BINDING_OPCODE.DO_BIND_ADD_ADDR_IMM_SCALED:
                    import_stack.append(
                        record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend,
                               special_dylib))
                    seg_offset = seg_offset + (value * 8) + 8

                elif binding_opcode == BINDING_OPCODE.DO_BIND_ULEB_TIMES_SKIPPING_ULEB:
                    count, read_address = self.image.decode_uleb128(read_address)
                    skip, read_address = self.image.decode_uleb128(read_address)

                    for i in range(0, count):
                        import_stack.append(
                            record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend,
                                   special_dylib))
                        seg_offset += skip + 8

                elif binding_opcode == BINDING_OPCODE.DO_BIND:
                    if not uses_threaded_bind:
                        import_stack.append(
                            record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend,
                                   special_dylib))
                        seg_offset += 8
                    else:
                        threaded_stack.append(
                            record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend,
                                   special_dylib))
                        seg_offset += 8

        return import_stack
