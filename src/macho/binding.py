from enum import IntEnum

from collections import namedtuple

action = namedtuple("action", ["vmaddr", "libname", "item"])
record = namedtuple("record",
                    ["seg_index", "seg_offset", "lib_ordinal", "type", "flags", "name", "addend", "special_dylib"])


class BindingProcessor:
    """
    This doesn't do a whole lot at the moment;

    It simply parses through the binding info in the library, and then creates a list of actions specified in the
        binding info.
    """

    def __init__(self, lib):
        self.lib = lib
        self.import_stack = self._load_binding_info()
        self.actions = self._create_action_list()

    def _create_action_list(self):
        actions = []
        for bind_command in self.import_stack:
            segment = list(self.lib.segments.values())[bind_command.seg_index]
            vm_addr = segment.vmaddr + bind_command.seg_offset
            try:
                lib = self.lib.linked[bind_command.lib_ordinal - 1].install_name
            except IndexError:
                lib = str(bind_command.lib_ordinal)
            item = bind_command.name
            actions.append(action(vm_addr & 0xFFFFFFFFF, lib, item))
        return actions

    def _load_binding_info(self):
        lib = self.lib
        ea = lib.info.bind_off
        import_stack = []
        while True:
            # print(hex(ea))
            if ea - lib.info.bind_size >= lib.info.bind_off:
                break
            seg_index = 0x0
            seg_offset = 0x0
            lib_ordinal = 0x0
            btype = 0x0
            flags = 0x0
            name = ""
            addend = 0x0
            special_dylib = 0x1
            while True:
                # There are 0xc opcodes total
                # Bitmask opcode byte with 0xF0 to get opcode, 0xF to get value
                OP = self.lib.get_bytes(ea, 1) & 0xF0
                VALUE = self.lib.get_bytes(ea, 1) & 0x0F
                ea += 1
                if OP == OPCODE.BIND_OPCODE_DONE:
                    import_stack.append(
                        record(seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
                    break
                elif OP == OPCODE.BIND_OPCODE_SET_DYLIB_ORDINAL_IMM:
                    lib_ordinal = VALUE
                elif OP == OPCODE.BIND_OPCODE_SET_DYLIB_ORDINAL_ULEB:
                    lib_ordinal, bump = self.lib.decode_uleb128(ea)
                    ea = bump
                elif OP == OPCODE.BIND_OPCODE_SET_DYLIB_SPECIAL_IMM:
                    special_dylib = 0x1
                    lib_ordinal = VALUE
                elif OP == OPCODE.BIND_OPCODE_SET_SYMBOL_TRAILING_FLAGS_IMM:
                    flags = VALUE
                    name = self.lib.get_cstr_at(ea)
                    ea += len(name)
                    ea += 1
                elif OP == OPCODE.BIND_OPCODE_SET_TYPE_IMM:
                    btype = VALUE
                elif OP == OPCODE.BIND_OPCODE_SET_ADDEND_SLEB:
                    ea += 1
                elif OP == OPCODE.BIND_OPCODE_SET_SEGMENT_AND_OFFSET_ULEB:
                    seg_index = VALUE
                    number, head = self.lib.decode_uleb128(ea)
                    seg_offset = number
                    ea = head
                elif OP == OPCODE.BIND_OPCODE_ADD_ADDR_ULEB:
                    o, bump = self.lib.decode_uleb128(ea)
                    seg_offset += o
                    ea = bump
                elif OP == OPCODE.BIND_OPCODE_DO_BIND_ADD_ADDR_ULEB:
                    import_stack.append(
                        record(seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
                    seg_offset += 8
                    o, bump = self.lib.decode_uleb128(ea)
                    seg_offset += o
                    ea = bump

                elif OP == OPCODE.BIND_OPCODE_DO_BIND_ADD_ADDR_IMM_SCALED:
                    import_stack.append(
                        record(seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
                    seg_offset = seg_offset + (VALUE * 8) + 8
                elif OP == OPCODE.BIND_OPCODE_DO_BIND_ULEB_TIMES_SKIPPING_ULEB:
                    t, bump = self.lib.decode_uleb128(ea)
                    count = t
                    ea = bump
                    s, bump = self.lib.decode_uleb128(ea)
                    skip = s
                    ea = bump
                    for i in range(0, count):
                        import_stack.append(
                            record(seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
                        seg_offset += skip + 8
                elif OP == OPCODE.BIND_OPCODE_DO_BIND:
                    import_stack.append(
                        record(seg_index, seg_offset, lib_ordinal, btype, flags, name, addend, special_dylib))
                    seg_offset += 8
                else:
                    assert 0 == 1

        return import_stack


class OPCODE(IntEnum):
    BIND_OPCODE_DONE = 0x0
    BIND_OPCODE_SET_DYLIB_ORDINAL_IMM = 0x10
    BIND_OPCODE_SET_DYLIB_ORDINAL_ULEB = 0x20
    BIND_OPCODE_SET_DYLIB_SPECIAL_IMM = 0x30
    BIND_OPCODE_SET_SYMBOL_TRAILING_FLAGS_IMM = 0x40
    BIND_OPCODE_SET_TYPE_IMM = 0x50
    BIND_OPCODE_SET_ADDEND_SLEB = 0x60
    BIND_OPCODE_SET_SEGMENT_AND_OFFSET_ULEB = 0x70
    BIND_OPCODE_ADD_ADDR_ULEB = 0x80
    BIND_OPCODE_DO_BIND = 0x90
    BIND_OPCODE_DO_BIND_ADD_ADDR_ULEB = 0xa0
    BIND_OPCODE_DO_BIND_ADD_ADDR_IMM_SCALED = 0xb0
    BIND_OPCODE_DO_BIND_ULEB_TIMES_SKIPPING_ULEB = 0xc0
