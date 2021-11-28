#
#  ktool | kmacho
#  macho.py
#
#  This file contains pythonized representations of certain #defines and enums from dyld source
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2021.
#


from enum import IntEnum


class REBASE_OPCODE(IntEnum):
    DONE = 0x0
    SET_TYPE_IMM = 0x10
    SET_SEGMENT_AND_OFFSET_ULEB = 0x20
    ADD_ADDR_ULEB = 0x30
    ADD_ADDR_IMM_SCALED = 0x40
    DO_REBASE_IMM_TIMES = 0x50
    DO_REBASE_ULEB_TIMES = 0x60
    DO_REBASE_ADD_ADDR_ULEB = 0x70
    DO_REBASE_ULEB_TIMES_SKIPPING_ULEB = 0x80


class BINDING_OPCODE(IntEnum):
    DONE = 0x0
    SET_DYLIB_ORDINAL_IMM = 0x10
    SET_DYLIB_ORDINAL_ULEB = 0x20
    SET_DYLIB_SPECIAL_IMM = 0x30
    SET_SYMBOL_TRAILING_FLAGS_IMM = 0x40
    SET_TYPE_IMM = 0x50
    SET_ADDEND_SLEB = 0x60
    SET_SEGMENT_AND_OFFSET_ULEB = 0x70
    ADD_ADDR_ULEB = 0x80
    DO_BIND = 0x90
    DO_BIND_ADD_ADDR_ULEB = 0xa0
    DO_BIND_ADD_ADDR_IMM_SCALED = 0xb0
    DO_BIND_ULEB_TIMES_SKIPPING_ULEB = 0xc0
    SUBCODE_THREAED_APPLY = 0xd0
