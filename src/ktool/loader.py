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
#  Copyright (c) 0cyn 2021.
#
from collections import namedtuple
from typing import List, Union, Dict

from ktool_macho import (MH_FLAGS, MH_FILETYPE, LOAD_COMMAND, BINDING_OPCODE, LOAD_COMMAND_MAP,
                    BIND_SUBOPCODE_THREADED_SET_BIND_ORDINAL_TABLE_SIZE_ULEB, BIND_SUBOPCODE_THREADED_APPLY,
                    MH_MAGIC_64, CPUType, CPUSubTypeARM64, MH_MAGIC)
from ktool_macho.base import Constructable
from ktool_macho.fixups import *
from ktool.codesign import CodesignInfo
from ktool.exceptions import MachOAlignmentError
from ktool.macho import Segment, Slice, MachOImageHeader, PlatformType
from lib0cyn.log import log
from ktool.util import macho_is_malformed, ignore, bytes_to_hex
from ktool.image import Image, os_version, LinkedImage, MisalignedVM


class MachOImageLoader:
    """
    This class takes our initialized "Image" object, parses through the raw data behind it, and fills out its properties.

    """

    SYMTAB_LOADER = None

    @classmethod
    def load(cls, macho_slice: Slice, load_symtab=True, load_imports=True, load_exports=True,
             force_misaligned_vm=False) -> Image:
        """
        Take a slice of a macho file and process it using the dyld functions

        :param force_misaligned_vm:
        :param load_exports: Load Exports
        :param load_imports: Load Imports
        :param load_symtab: Load Symbol Table
        :param macho_slice: Slice to load. If your image is not fat, that'll be MachOFile.slices[0]
        :type macho_slice: Slice
        :return: Processed image object
        :rtype: Image
        """

        MachOImageLoader.SYMTAB_LOADER = SymbolTable

        log.info("Loading image")
        image = Image(macho_slice, force_misaligned_vm)

        if force_misaligned_vm:
            image.vm = MisalignedVM()

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
                try:
                    image.vm.add_segment(segment)
                except MachOAlignmentError:
                    image.vm = image.vm.fallback
                    image.vm.add_segment(segment)
                image.segments[segment.name] = segment

            elif load_command in [LOAD_COMMAND.THREAD, LOAD_COMMAND.UNIXTHREAD]:
                thread_state = []
                for i in range(cmd.count):
                    off = cmd.off + 16 + (i * 4)
                    val = image.read_uint(off, 4)
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
                    fs_r_addr, read_head = image.read_uleb128(read_head)
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
                    image.symbol_table = MachOImageLoader.SYMTAB_LOADER(image, cmd)

            elif load_command == LOAD_COMMAND.DYSYMTAB:
                pass

            elif load_command == LOAD_COMMAND.UUID:
                image.uuid = cmd.uuid
                log.info(f'image UUID: {image.uuid}')

            elif load_command == LOAD_COMMAND.SUB_CLIENT:
                string = image.read_cstr(cmd.off + cmd.offset)
                image.allowed_clients.append(string)
                log.debug(f'Loaded Subclient "{string}"')

            elif load_command == LOAD_COMMAND.RPATH:
                string = image.read_cstr(cmd.off + cmd.path)
                image.rpath = string
                log.info(f'image Resource Path: {string}')

            elif load_command == LOAD_COMMAND.BUILD_VERSION:
                image.platform = PlatformType(cmd.platform)
                image.minos = os_version(x=image.read_uint(cmd.off + 14, 2), y=image.read_uint(cmd.off + 13, 1),
                                         z=image.read_uint(cmd.off + 12, 1))
                image.sdk_version = os_version(x=image.read_uint(cmd.off + 18, 2), y=image.read_uint(cmd.off + 17, 1),
                                               z=image.read_uint(cmd.off + 16, 1))
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

                    image.minos = os_version(x=image.read_uint(cmd.off + 10, 2), y=image.read_uint(cmd.off + 9, 1),
                                             z=image.read_uint(cmd.off + 8, 1))

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
        fullname = image.read_cstr(entry.str_index + cmd.stroff)
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
        return {'name': self.fullname, 'address': self.address, 'external': self.external, 'ordinal': self.ordinal}

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
            entry = self.image.read_struct(read_address + typing.size() * i, typing)
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

        syms = []
        rebases = {}

        fixup_header = image.read_struct(chained_fixup_cmd.dataoff, dyld_chained_fixups_header)
        log.debug_tm(f'{fixup_header.render_indented()}')

        if fixup_header.fixups_version > 0:
            log.error("Unknown Fixup Format")
            return cls([])

        import_table_size = fixup_header.imports_count * dyld_chained_import.size()
        if import_table_size > chained_fixup_cmd.datasize:
            log.error("Chained fixup import table is larger than chained fixup linkedit region")
            return cls([])

        if fixup_header.imports_format != dyld_chained_import_format.DYLD_CHAINED_IMPORT.value:
            log.error("Unknown or unhandled import format")

        imports_address = fixup_header.off + fixup_header.imports_offset
        symbols_address = fixup_header.off + fixup_header.symbols_offset
        import_entry_t = namedtuple("import_entry_t", ["ord", "weak", "name"])
        import_table = []
        for i in range(0, fixup_header.imports_count):
            i_addr = (i * 4) + imports_address
            i_entry = image.read_struct(i_addr, dyld_chained_import)
            lib_ord = i_entry.lib_ordinal
            is_weak = i_entry.weak_import
            name_addr = symbols_address + i_entry.name_offset
            sym_name = image.read_cstr(name_addr)
            entry = import_entry_t(lib_ord, is_weak, sym_name)
            import_table.append(entry)
            log.debug_tm(f'ChFx:ImportTable: {sym_name} @ ord {lib_ord}')

        fixup_starts_address = chained_fixup_cmd.dataoff + fixup_header.starts_offset
        segment_count = image.read_uint(fixup_starts_address, 4)
        seg_info_offsets = []
        cursor = fixup_starts_address + 4
        for i in range(0, segment_count):
            seg_info_offsets.append(image.read_uint(cursor, 4))
            cursor += 4

        for off in seg_info_offsets:
            if off == 0:
                continue
            segstarts_addr = fixup_starts_address + off
            starts = image.read_struct(segstarts_addr, dyld_chained_starts_in_segment, endian="little")

            stride_size: int = 0
            ptr_format: ChainedFixupPointerGeneric = ChainedFixupPointerGeneric.Error

            log.debug_tm(f"Pointer Format: {ptr_format.name}")
            if starts.pointer_format in [dyld_chained_ptr_format.DYLD_CHAINED_PTR_ARM64E.value,
                                         dyld_chained_ptr_format.DYLD_CHAINED_PTR_ARM64E_USERLAND.value,
                                         dyld_chained_ptr_format.DYLD_CHAINED_PTR_ARM64E_USERLAND24.value]:
                stride_size = 8
                ptr_format = ChainedFixupPointerGeneric.GenericArm64eFixupFormat
            elif starts.pointer_format == dyld_chained_ptr_format.DYLD_CHAINED_PTR_ARM64E_KERNEL.value:
                stride_size = 4
                ptr_format = ChainedFixupPointerGeneric.GenericArm64eFixupFormat
            elif starts.pointer_format in [dyld_chained_ptr_format.DYLD_CHAINED_PTR_64.value,
                                           dyld_chained_ptr_format.DYLD_CHAINED_PTR_64_OFFSET.value,
                                           dyld_chained_ptr_format.DYLD_CHAINED_PTR_64_KERNEL_CACHE.value]:
                stride_size = 4
                ptr_format = ChainedFixupPointerGeneric.Generic64FixupFormat
            elif starts.pointer_format in [dyld_chained_ptr_format.DYLD_CHAINED_PTR_32.value,
                                           dyld_chained_ptr_format.DYLD_CHAINED_PTR_32_CACHE.value]:
                stride_size = 4
                ptr_format = ChainedFixupPointerGeneric.Generic32FixupFormat
            elif starts.pointer_format == dyld_chained_ptr_format.DYLD_CHAINED_PTR_32_FIRMWARE.value:
                stride_size = 4
                ptr_format = ChainedFixupPointerGeneric.Generic64FixupFormat
            elif starts.pointer_format == dyld_chained_ptr_format.DYLD_CHAINED_PTR_x86_64_KERNEL_CACHE.value:
                stride_size = 1
                ptr_format = ChainedFixupPointerGeneric.Generic64FixupFormat
            else:
                log.error(f"Unsupported Pointer Format {starts.pointer_format}")
                log.error(f'{hex(fixup_header.off)} @ {fixup_header.render_indented()}')
                log.error(f"{starts.render_indented()}")
                return cls([])
            log.debug_tm(f"Stride Size: {stride_size}")

            page_start_offsets: List[List[int]] = []
            for i in range(0, starts.page_count):
                page_start_table_start_address = segstarts_addr + 22
                i_addr = page_start_table_start_address + (2 * i)
                start = image.read_uint(i_addr, 2)
                if (start & DYLD_CHAINED_PTR_START_MULTI) and (start != DYLD_CHAINED_PTR_START_NONE):
                    overflow_index = start & ~DYLD_CHAINED_PTR_START_MULTI
                    page_start_sub_starts: List[int] = []
                    cursor = page_start_table_start_address + (overflow_index * 2)
                    done = False
                    while not done:
                        sub_page_start = image.read_uint(cursor, 2)
                        cursor += 2
                        if sub_page_start & DYLD_CHAINED_PTR_START_LAST:
                            page_start_sub_starts.append(sub_page_start & ~DYLD_CHAINED_PTR_START_LAST)
                            done = True
                        else:
                            page_start_sub_starts.append(sub_page_start)
                    page_start_offsets.append(page_start_sub_starts)
                else:
                    page_start_offsets.append([start])

            i = -1
            for page_starts in page_start_offsets:
                i += 1
                page_addr = starts.segment_offset + (i * starts.page_size)
                for start in page_starts:
                    if start == DYLD_CHAINED_PTR_START_NONE:
                        continue
                    chain_entry_address = page_addr + start
                    fixups_done = False
                    while not fixups_done:
                        cursor = chain_entry_address
                        mapped_cursor = image.vm.de_translate(cursor)
                        pointer32: ChainedFixupPointer32 = None
                        pointer64: ChainedFixupPointer64 = None

                        if ptr_format in [ChainedFixupPointerGeneric.Generic32FixupFormat,
                                          ChainedFixupPointerGeneric.Firmware32FixupFormat]:
                            pointer32 = image.read_struct(cursor, ChainedFixupPointer32)
                        else:
                            pointer64 = image.read_struct(cursor, ChainedFixupPointer64)

                        bind: bool = False
                        next_entry_stride_count = 0
                        if ptr_format == ChainedFixupPointerGeneric.Generic32FixupFormat:
                            bind = pointer32.generic32.dyld_chained_ptr_32_bind.bind != 0
                            next_entry_stride_count = pointer32.generic32.dyld_chained_ptr_32_rebase.next
                        elif ptr_format == ChainedFixupPointerGeneric.Generic64FixupFormat:
                            bind = pointer64.generic64.ChainedPointerGeneric64.dyld_chained_ptr_64_bind.bind != 0
                            next_entry_stride_count = pointer64.generic64.ChainedPointerGeneric64.dyld_chained_ptr_64_rebase.next
                        elif ptr_format == ChainedFixupPointerGeneric.GenericArm64eFixupFormat:
                            bind = pointer64.generic64.ChainedPointerArm64E.dyld_chained_ptr_arm64e_bind.bind != 0
                            next_entry_stride_count = pointer64.generic64.ChainedPointerArm64E.dyld_chained_ptr_arm64e_bind.next
                        elif ptr_format == ChainedFixupPointerGeneric.Firmware32FixupFormat:
                            bind = False
                            next_entry_stride_count = pointer32.generic32.dyld_chained_ptr_32_firmware_rebase
                        else:
                            log.error("unreachable")
                            return cls([])

                        if bind:
                            ordinal = 0
                            if starts.pointer_format in [dyld_chained_ptr_format.DYLD_CHAINED_PTR_64.value,
                                dyld_chained_ptr_format.DYLD_CHAINED_PTR_64_OFFSET.value]:
                                ordinal = pointer64.generic64.ChainedPointerGeneric64.dyld_chained_ptr_64_bind.ordinal
                            elif starts.pointer_format in [  # i swear this looks better in c++
                                dyld_chained_ptr_format.DYLD_CHAINED_PTR_ARM64E.value,
                                dyld_chained_ptr_format.DYLD_CHAINED_PTR_ARM64E_USERLAND.value,
                                dyld_chained_ptr_format.DYLD_CHAINED_PTR_ARM64E_KERNEL.value]:
                                if (pointer64.generic64.ChainedPointerArm64E.dyld_chained_ptr_arm64e_bind.auth != 0):
                                    ordinal = pointer64.generic64.ChainedPointerArm64E.dyld_chained_ptr_arm64e_auth_bind24.ordinal if starts.pointer_format == dyld_chained_ptr_format.DYLD_CHAINED_PTR_ARM64E_USERLAND24 else pointer64.generic64.ChainedPointerArm64E.dyld_chained_ptr_arm64e_auth_bind.ordinal
                                else:
                                    ordinal = pointer64.generic64.ChainedPointerArm64E.dyld_chained_ptr_arm64e_bind24.ordinal if starts.pointer_format == dyld_chained_ptr_format.DYLD_CHAINED_PTR_ARM64E_USERLAND24 else pointer64.generic64.ChainedPointerArm64E.dyld_chained_ptr_arm64e_bind.ordinal
                            elif starts.pointer_format == dyld_chained_ptr_format.DYLD_CHAINED_PTR_32.value:
                                ordinal = pointer32.generic32.dyld_chained_ptr_32_bind.ordinal

                            else:
                                log.error("Unknown bind pointer format")
                                return cls([])

                            if ordinal < len(import_table):
                                entry = import_table[ordinal]
                                target_addr = mapped_cursor
                                sym = Symbol.from_values(entry.name, target_addr, external=True, ordinal=entry.ord)
                                syms.append(sym)

                        else: #rebase
                            entry_offset = 0
                            if starts.pointer_format in [dyld_chained_ptr_format.DYLD_CHAINED_PTR_ARM64E,
                                                         dyld_chained_ptr_format.DYLD_CHAINED_PTR_ARM64E_KERNEL,
                                                         dyld_chained_ptr_format.DYLD_CHAINED_PTR_ARM64E_USERLAND,
                                                         dyld_chained_ptr_format.DYLD_CHAINED_PTR_ARM64E_USERLAND24]:
                                if pointer64.generic64.ChainedPointerArm64E.dyld_chained_ptr_arm64e_auth_rebase.auth == 1:
                                    entry_offset = pointer64.generic64.ChainedPointerArm64E.dyld_chained_ptr_arm64e_auth_rebase.target
                                else:
                                    entry_offset = pointer64.generic64.ChainedPointerArm64E.dyld_chained_ptr_arm64e_rebase.target

                                if starts.pointer_format != dyld_chained_ptr_format.DYLD_CHAINED_PTR_ARM64E or pointer64.generic64.ChainedPointerArm64E.dyld_chained_ptr_arm64e_auth_rebase.auth:
                                    entry_offset += image.vm.vm_base_addr
                            elif starts.pointer_format == dyld_chained_ptr_format.DYLD_CHAINED_PTR_64:
                                entry_offset = pointer64.generic64.ChainedPointerGeneric64.dyld_chained_ptr_64_rebase.target
                            elif starts.pointer_format == dyld_chained_ptr_format.DYLD_CHAINED_PTR_64_OFFSET:
                                entry_offset = pointer64.generic64.ChainedPointerGeneric64.dyld_chained_ptr_64_rebase.target + image.vm.vm_base_addr
                            #elif starts.pointer_format == dyld_chained_ptr_format.DYLD_CHAINED_PTR_64_KERNEL_CACHE or \
                            #    starts.pointer_format == dyld_chained_ptr_format.DYLD_CHAINED_PTR_X86_64_KERNEL_CACHE:
                            #    entry_offset = pointer64.
                            elif starts.pointer_format == dyld_chained_ptr_format.DYLD_CHAINED_PTR_32 or starts.pointer_format == dyld_chained_ptr_format.DYLD_CHAINED_PTR_32_CACHE:
                                entry_offset = pointer32.generic32.dyld_chained_ptr_32_rebase.target
                            elif starts.pointer_format == dyld_chained_ptr_format.DYLD_CHAINED_PTR_32_CACHE:
                                entry_offset = pointer32.generic32.dyld_chained_ptr_32_firmware_rebase.target

                            rebases[pointer64.off] = entry_offset

                        chain_entry_address += next_entry_stride_count * stride_size
                        if (chain_entry_address > page_addr + starts.page_size):
                            log.error("Pointer left page, bailing fixup processing, binary is malformed")
                            fixups_done = True
                        if next_entry_stride_count == 0:
                            fixups_done = True

        return cls(syms, rebases)

    @classmethod
    def from_values(cls, *args, **kwargs):
        pass

    def raw_bytes(self):
        pass

    def __init__(self, symbols, rebases=None):
        if rebases is None:
            rebases = {}
        self.symbols = symbols
        self.rebases = rebases


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
        trie.raw = image.read_bytearray(export_start, export_size)

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
        terminal_size, cursor = image.read_uleb128(cursor)
        results = []
        log.debug_tm(f'@ {hex(start)} node: {hex(terminal_size)} current_symbol: {string}')
        child_start = cursor + terminal_size
        if terminal_size != 0:
            log.debug_tm(f'TERM: 0')
            size, cursor = image.read_uleb128(cursor)
            flags = image.read_uint(cursor, 1)
            cursor += 1
            offset, cursor = image.read_uleb128(cursor)
            results.append(export_node(string, offset, flags))
        cursor = child_start
        branches = image.read_uint(cursor, 1)
        log.debug_tm(f'BRAN {branches}')
        for i in range(0, branches):
            if i == 0:
                cursor += 1
            proc_str = image.read_cstr(cursor)
            cursor += len(proc_str) + 1
            offset, cursor = image.read_uleb128(cursor)
            log.debug_tm(f'({i}) string: {string + proc_str} next_node: {hex(trie_start + offset)}')
            results += ExportTrie.read_node(image, trie_start, string + proc_str, trie_start + offset, endpoint)

        return results


action = namedtuple("action", ["vmaddr", "libname", "item"])
record = namedtuple("record", ["off", "seg_index", "seg_offset", "lib_ordinal", "type", "flags", "name", "addend",
    "special_dylib"])


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
                binding_opcode = self.image.read_uint(read_address, 1) & 0xF0
                value = self.image.read_uint(read_address, 1) & 0x0F
                log.debug_tm(f'{BINDING_OPCODE(binding_opcode).name}: {hex(value)}')
                cmd_start_addr = read_address
                read_address += 1

                if binding_opcode == BINDING_OPCODE.THREADED:
                    if value == BIND_SUBOPCODE_THREADED_SET_BIND_ORDINAL_TABLE_SIZE_ULEB:
                        a_table_size, read_address = self.image.read_uleb128(read_address)
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
                    lib_ordinal, read_address = self.image.read_uleb128(read_address)

                elif binding_opcode == BINDING_OPCODE.SET_DYLIB_SPECIAL_IMM:
                    special_dylib = 0x1
                    lib_ordinal = value

                elif binding_opcode == BINDING_OPCODE.SET_SYMBOL_TRAILING_FLAGS_IMM:
                    flags = value
                    name = self.image.read_cstr(read_address)
                    read_address += len(name) + 1

                elif binding_opcode == BINDING_OPCODE.SET_TYPE_IMM:
                    btype = value

                elif binding_opcode == BINDING_OPCODE.SET_ADDEND_SLEB:
                    addend, read_address = self.image.read_uleb128(read_address)

                elif binding_opcode == BINDING_OPCODE.SET_SEGMENT_AND_OFFSET_ULEB:
                    seg_index = value
                    seg_offset, read_address = self.image.read_uleb128(read_address)

                elif binding_opcode == BINDING_OPCODE.ADD_ADDR_ULEB:
                    o, read_address = self.image.read_uleb128(read_address)
                    seg_offset += o

                elif binding_opcode == BINDING_OPCODE.DO_BIND_ADD_ADDR_ULEB:
                    import_stack.append(
                        record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend,
                               special_dylib))
                    seg_offset += self.image.ptr_size
                    o, read_address = self.image.read_uleb128(read_address)
                    seg_offset += o

                elif binding_opcode == BINDING_OPCODE.DO_BIND_ADD_ADDR_IMM_SCALED:
                    import_stack.append(
                        record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend,
                               special_dylib))
                    seg_offset = seg_offset + (value * self.image.ptr_size) + self.image.ptr_size

                elif binding_opcode == BINDING_OPCODE.DO_BIND_ULEB_TIMES_SKIPPING_ULEB:
                    count, read_address = self.image.read_uleb128(read_address)
                    skip, read_address = self.image.read_uleb128(read_address)

                    for i in range(0, count):
                        import_stack.append(
                            record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend,
                                   special_dylib))
                        seg_offset += skip + self.image.ptr_size

                elif binding_opcode == BINDING_OPCODE.DO_BIND:
                    if not uses_threaded_bind:
                        import_stack.append(
                            record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend,
                                   special_dylib))
                        seg_offset += self.image.ptr_size
                    else:
                        threaded_stack.append(
                            record(cmd_start_addr, seg_index, seg_offset, lib_ordinal, btype, flags, name, addend,
                                   special_dylib))
                        seg_offset += self.image.ptr_size

        return import_stack
