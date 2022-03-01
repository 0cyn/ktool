#!/usr/bin/env python3

#
#  ktool | MAIN SCRIPT
#  ktool
#
#  This file is the main command-line script providing utilities for using ktool.
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2021.
#

import json
import os
import os.path
import shutil
import sys
import threading
import urllib.request
from argparse import ArgumentParser
from collections import namedtuple
from enum import Enum
from typing import Union
from kimg4.img4 import IM4P

# noinspection PyProtectedMember
from pkg_resources import packaging

from kmacho import LOAD_COMMAND

from ktool import (
    MachOFileType,
    KTOOL_VERSION,
    ignore,
    log,
    LogLevel,
    Table,
    LD64
)

from ktool.swift import *

from ktool.exceptions import *
from ktool.generator import FatMachOGenerator
from ktool.util import opts, version_output, ktool_print
from ktool.window import KToolScreen, external_hard_fault_teardown

UPDATE_AVAILABLE = False
MAIN_PARSER = None
MMAP_ENABLED = True

# noinspection PyShadowingBuiltins
print = ktool_print


def get_terminal_size():
    # We use this instead of shutil.get_terminal_size, because when output is being piped, it returns column width 80
    # We want to make sure if output is being piped (for example, to grep), that no wrapping occurs, so greps will
    # always display all relevant info on a single line. This also helps if it's being piped into a file,
    # for processing purposes among everything else.
    try:
        return os.get_terminal_size()
    except OSError:
        return shutil.get_terminal_size()


def handle_version(version: str):
    """ Used by check_for_update """
    return packaging.version.parse(version)


def check_for_update():
    endpoint = "https://pypi.org/pypi/k2l/json"
    # noinspection PyBroadException
    try:
        with urllib.request.urlopen(endpoint, timeout=1) as url:
            data = json.loads(url.read().decode(), strict=False)
        new_version = data.get('info').get('version')
        if handle_version(KTOOL_VERSION) < handle_version(new_version):
            global UPDATE_AVAILABLE
            UPDATE_AVAILABLE = True
    except Exception:
        pass


class KToolError(Enum):
    ArgumentError = 1
    FiletypeError = 2
    MalformedMachOError = 3
    ProcessingError = 4


def exit_with_error(error: KToolError, msg):
    print(f'Encountered an Error ({error.name}):\n' + f"{msg}", file=sys.stderr)
    exit(error.value)


# noinspection PyProtectedMember
def arg_dest_to_name(parser: Union[None, ArgumentParser], dest):
    """
    Convert dest (an argument destination variable name) to the actual flag used to set it (do_headers -> --headers)

    Uses internal properties from argparse, this also iterates through all subparsers

    :param parser: main argument parser to pull the original flag from
    :param dest: destination variable name
    :return:
    """
    args = {}

    for k, v in parser._option_string_actions.items():
        # parser here is an instance of ArgumentParser
        args[str(v.dest)] = k

    for parser_name, sparser in parser._subparsers._group_actions[0].choices.items():
        # if a parser has subparsers, you'll be able to get an instance of ArgumentParser representing them at
        # _subparsers._group_actions[0].choices, which is a Dict[str, ArgumentParser] containing all registered
        # subparsers.
        for k, v in sparser._option_string_actions.items():
            args[str(v.dest)] = k

    if dest not in args:
        raise AttributeError(f'{dest} destination not in any arguments.')

    return args[dest]


def require_args(args, always=None, one_of=None):
    """
    This is a quick macro to enforce argument requirements for different commands.

    If a check fails, it'll print usage for the subcommand and exit the program.

    :param args: Parsed argument object
    :param always: Arguments that *must* be passed
    :param one_of: At least one of these arguments must be passed, and must evaluate as True
    :return:
    """

    if always:
        missing = []
        for i in always:
            if not hasattr(args, i):
                missing.append(i)
            elif not getattr(args, i):
                missing.append(i)

        if len(missing) > 0:
            print(args.func.__doc__)
            if len(missing) == 1:
                error_str = f'Missing required argument {arg_dest_to_name(MAIN_PARSER, missing[0])}'
                exit_with_error(KToolError.ArgumentError, error_str)
            else:
                error_str = 'Missing required arguments: '
                error_str += ', '.join([arg_dest_to_name(MAIN_PARSER, i) for i in missing])
                exit_with_error(KToolError.ArgumentError, error_str)

    if one_of:
        found_one = False
        for i in one_of:
            if hasattr(args, i):
                if getattr(args, i):
                    found_one = True
                    break
        if not found_one:
            print(args.func.__doc__)
            missing_args = ", ".join([arg_dest_to_name(MAIN_PARSER, i) for i in one_of])
            exit_with_error(KToolError.ArgumentError, f'Missing one of {missing_args}')


def main():
    parser = ArgumentParser(description="ktool")

    parser.add_argument('--bench', dest='bench', action='store_true')
    parser.add_argument('--membench', dest='membench', action='store_true')
    parser.add_argument('-v', dest='logging_level', type=int)
    parser.add_argument('-f', dest='force_load', action='store_true')
    parser.add_argument('-V', dest='get_vers', action='store_true')
    parser.add_argument('--no-mmap', dest='no_mmap', action='store_true', help='Disable mmaped IO')
    parser.set_defaults(func=help_prompt, bench=False, membench=False, force_load=False, no_mmap=False, logging_level=1,
                        get_vers=False)

    subparsers = parser.add_subparsers(help='sub-command help')

    # open command: opens the main GUI
    parser_open = subparsers.add_parser('open', help='open ktool GUI and browse file')

    parser_open.add_argument('filename', nargs='?', default='')
    parser_open.add_argument('--hard-fail', dest='hard_fail', action='store_true')

    parser_open.set_defaults(func=_open, hard_fail=False)

    # insert command: optool replacement
    parser_insert = subparsers.add_parser('insert', help='Insert data into MachO Binary')

    parser_insert.add_argument('filename', nargs='?', default='')
    parser_insert.add_argument('--lc', dest='lc', help="Type of Load Command to insert")
    parser_insert.add_argument('--payload', dest='payload', help="Payload (if required) for insertion")
    parser_insert.add_argument('--out', dest='out', help="Output file destination for patches")

    parser_insert.set_defaults(func=insert, out=None, lc=None, payload=None)

    # edit command: install-name-tool replacement
    parser_edit = subparsers.add_parser('edit', help='Edit attributes of the MachO')

    parser_edit.add_argument('filename', nargs='?', default='')
    parser_edit.add_argument('--iname', dest='iname', help='Modify the Install Name of a image')
    parser_edit.add_argument('--apad', dest='apad',
                             help='Add MachO Header Padding (not yet implemented, ignore this flag please)')
    parser_edit.add_argument('--out', dest='out', help="Output file destination for patches")

    parser_edit.set_defaults(func=edit, out=None, iname=None, apad=None)

    # lipo command: you will never guess which macos cli tool the lipo command replaces
    parser_lipo = subparsers.add_parser('lipo', help='Extract/Combine slices')

    parser_lipo.add_argument('--extract', dest='extract', type=str, help='Extract a slice (--extract arm64)')
    parser_lipo.add_argument('--out', dest='out', help="Output File")
    parser_lipo.add_argument('--create', dest='combine', action='store_true',
                             help="Combine files to create a fat mach-o image")
    parser_lipo.add_argument('filename', nargs='*', default='')

    parser_lipo.set_defaults(func=lipo, out="", combine=False)

    # img4 command: because why not. wrote an img4 library for iBootLoader and it can definitely be useful elsewhere.
    parser_img4 = subparsers.add_parser('img4', help='img4/IM4P parsing utilities')

    parser_img4.add_argument('filename', nargs='?', default='')

    parser_img4.add_argument('--kbag', dest='get_kbag', action='store_true', help="Decode keybags in an im4p file")
    parser_img4.add_argument('--dec', dest='do_decrypt', action='store_true', help="Decrypt an im4p file with iv/key")
    parser_img4.add_argument('--iv', dest='aes_iv', type=str, help='IV for decryption')
    parser_img4.add_argument('--key', dest='aes_key', type=str, help='Key for decryption')
    parser_img4.add_argument('--out', dest='out', help="Output file destination for decryption")

    parser_img4.set_defaults(func=img4, get_kbag=False, do_decrypt=False, aes_iv=None, aes_key=None, out=None)

    # file command: super basic info about a file (thin/fat, and if fat, what slices are contained)
    #               replaces the relevant usage of the `file` command on macos
    parser_file = subparsers.add_parser('file', help='Print File Type (thin/fat MachO)')

    parser_file.add_argument('filename', nargs='?', default='')

    parser_file.set_defaults(func=_file)

    # info command: prints the VM map (this is honestly just for me when debugging shit)
    parser_info = subparsers.add_parser('info', help='Print Info about a MachO image')

    parser_info.add_argument('--slice', dest='slice_index', type=int,
                             help="Specify Index of Slice (in FAT MachO) to examine")
    parser_info.add_argument('--vm', dest='get_vm', action='store_true', help="Print VM Mapping for MachO image")
    parser_info.add_argument('filename', nargs='?', default='')

    parser_info.set_defaults(func=info, get_vm=False, get_lcs=False, slice_index=0)

    # dump command: for dumping headers/tbds from an image
    parser_dump = subparsers.add_parser('dump', help='Dump items (headers) from binary')

    parser_dump.add_argument('--slice', dest='slice_index', type=int,
                             help="Specify Index of Slice (in FAT MachO) to examine")
    parser_dump.add_argument('--headers', dest='do_headers', action='store_true')
    parser_dump.add_argument('--class', dest='get_class')
    parser_dump.add_argument('--use-stab-for-sel', dest='usfs', action='store_true')
    parser_dump.add_argument('--hard-fail', dest='hard_fail', action='store_true')
    parser_dump.add_argument('--sorted', dest='sort_headers', action='store_true')
    parser_dump.add_argument('--tbd', dest='do_tbd', action='store_true')
    parser_dump.add_argument('--out', dest='outdir', help="Directory to dump headers into")
    parser_dump.add_argument('filename', nargs='?', default='')

    parser_dump.set_defaults(func=dump, do_headers=False, usfs=False, sort_headers=False, do_tbd=False, slice_index=0,
                             hard_fail=False, get_class=None)

    # list command: Lists lists of things contained in lists in the image.
    parser_list = subparsers.add_parser('list', help='Print various lists')

    parser_list.add_argument('--slice', dest='slice_index', type=int,
                             help="Specify Index of Slice (in FAT MachO) to examine")
    parser_list.add_argument('--classes', dest='get_classes', action='store_true', help='Print class list')
    parser_list.add_argument('--protocols', dest='get_protos', action='store_true', help='Print Protocol list')
    parser_list.add_argument('--stypes', dest='get_swift_types', action='store_true', help='Print Swift Types')
    parser_list.add_argument('--linked', dest='get_linked', action='store_true', help='Print list of linked libraries')
    parser_list.add_argument('--cmds', dest='get_lcs', action='store_true', help="Print Load Commands")
    parser_list.add_argument('--funcs', dest='get_fstarts', action='store_true', help="Print Function Starts")
    parser_list.add_argument('filename', nargs='?', default='')

    parser_list.set_defaults(func=_list, get_lcs=False, get_classes=False, get_protos=False, get_linked=False,
                             slice_index=0, get_swift_types=False)

    # symbol command: prints various symbol tables
    parser_symbols = subparsers.add_parser('symbols', help='Print various symbols')

    parser_symbols.add_argument('--imports', dest='get_imports', action='store_true', help='Print Imports')
    parser_symbols.add_argument('--imp-acts', dest='get_actions', action='store_true', help='Print Raw Binding Imports')
    parser_symbols.add_argument('--symtab', dest='get_symtab', action='store_true', help='Print out the symtab')
    parser_symbols.add_argument('--exports', dest='get_exports', action='store_true', help='Print exports')
    parser_symbols.add_argument('--slice', dest='slice_index', type=int,
                                help="Specify Index of Slice (in FAT MachO) to examine")
    parser_symbols.add_argument('filename', nargs='?', default='')

    parser_symbols.set_defaults(func=symbols, get_imports=False, get_actions=False, get_exports=False, get_symtab=False,
                                slice_index=0)

    # process the arguments the user passed us.
    # it is worth noting i set the default for `func` on each command parser to a function named without ();
    # this means when that command is used, calling args.func() will branch off to that function.
    parser.print_help = help_prompt
    args = parser.parse_args()

    global MAIN_PARSER
    MAIN_PARSER = parser

    if 'KTOOL_NO_UPDATE_CHECK' not in os.environ:
        # set this off on a separate thread before we do anything else
        # it should have time to complete by the time the rest of our code is finished
        download_thread = threading.Thread(target=check_for_update, name="UpdateChecker")
        download_thread.start()

    if args.get_vers:
        version_output()
        exit()

    if not hasattr(args, 'filename'):
        # this is our default function, bc it has no .filename attribute default set
        # They typed no command or anything, so print the program usage.
        help_prompt()
        exit()

    if not args.filename or args.filename == '':
        # if it has the .filename attribute, but its not set, then they've passed a command but with no filename
        #   so, print the usage for that command.
        print(args.func.__doc__)
        exit()

    # we minmax to -1 (show absolutely nothing) and 5 (print so much it slows down by 10x)
    log.LOG_LEVEL = LogLevel(max(min(args.logging_level, 5), -1))

    if args.force_load:
        # kind of a hack using a class attribute in ktool.util but it works.
        ignore.MALFORMED = True

    if args.no_mmap:
        global MMAP_ENABLED
        MMAP_ENABLED = False

    if args.membench:
        import tracemalloc
        tracemalloc.start(10)

        args.func(args)

        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')

        print("[ Top 10 ]")
        for stat in top_stats[:10]:
            print(stat)

    elif args.bench:
        # This will run the program as normal, but with profiling enabled
        # It will print what are arguably the 10 routines contributing the most to slowdowns.
        import cProfile
        import pstats

        profile = cProfile.Profile()
        profile.runcall(args.func, args)
        ps = pstats.Stats(profile)
        ps.sort_stats('time', 'cumtime')  # who named this
        ps.print_stats(10)

    else:
        try:
            args.func(args)
        except UnsupportedFiletypeException:
            exit_with_error(KToolError.FiletypeError, f'{args.filename} is not a valid MachO Binary')
        except FileNotFoundError:
            exit_with_error(KToolError.ArgumentError, f'{args.filename} does not exist')
        except MalformedMachOException:
            exit_with_error(KToolError.MalformedMachOError,
                            f'Malformed MachO. Pass -f to force loading whatever possible')

    if UPDATE_AVAILABLE:
        print(f'\n\nUpdate Available ---')
        print(f'run `pip3 install --upgrade k2l` to fetch the latest update')
        print(f'set the envar KTOOL_NO_UPDATE_CHECK to disable update checks')

    exit(0)


def help_prompt():
    """Usage: ktool <global flags> [command] <flags> [filename]

Commands:

GUI (Still in active development) ---
    ktool open [filename] - Open the ktool command line GUI and browse a file

MachO Editing ---
    insert - Utils for inserting load commands into MachO Binaries
    edit - Utils for editing MachO Binaries
    lipo - Utilities for combining/separating slices in fat MachO files.

MachO Analysis ---
    dump - Tools to reconstruct certain files (headers, .tbds) from compiled MachOs
    list - Print various lists (ObjC Classes, etc.)
    symbols - Print various tables (Symbols, imports, exports)
    info - Print misc info about the target mach-o

Misc Utilities ---
    file - Print very basic info about the MachO
    img4 - IMG4 Utilities

Run `ktool [command]` for info/examples on using that command

Global Flags:
    -f - Force Load (ignores malformations in the MachO and tries to load whatever it can)
    -v [-1 through 5] - Log verbosiy. -1 completely silences logging.
        """
    print(help_prompt.__doc__)


def process_patches(image) -> 'Image':
    try:
        return ktool.reload_image(image)
    except MalformedMachOException:
        exit_with_error(KToolError.ProcessingError, "Reloading MachO after patch failed. This is an issue with "
                                                    "my patch code. Please file an issue on "
                                                    "https://github.com/kritantadev/ktool.")


def _open(args):
    try:
        log.LOG_LEVEL = LogLevel.DEBUG
        screen = KToolScreen(args.hard_fail)
        log.LOG_FUNC = screen.ktool_dbg_print_func
        log.LOG_ERR = screen.ktool_dbg_print_err_func
        screen.load_file(args.filename)
    except KeyboardInterrupt:
        external_hard_fault_teardown()
        print('Hard Faulted. This was likely due to a curses error causing a freeze while rendering.')
        exit(64)
    except Exception as ex:
        external_hard_fault_teardown()
        print('Hard fault in GUI due to uncaught exception:')
        raise ex

    # should probably just always do this, just in case.
    external_hard_fault_teardown()


def symbols(args):
    """
----------
List symbol imports/exports

Print the list of imported symbols
> ktool symbols --imports [filename]

Print the list of exported symbols
> ktool symbols --exports [filename]

Print the symbol table
> ktool symbols --symtab [filename]
    """

    require_args(args, one_of=['get_imports', 'get_actions', 'get_exports', 'get_symtab'])

    if args.get_exports:
        with open(args.filename, 'rb') as fd:
            image = ktool.load_image(fd, args.slice_index, load_symtab=False, load_imports=False,
                                     use_mmaped_io=MMAP_ENABLED)

            table = Table()
            table.titles = ['Address', 'Symbol']

            for symbol in image.exports:
                table.rows.append([hex(symbol.address), symbol.fullname])

            print(table.fetch_all(get_terminal_size().columns))

    if args.get_symtab:
        with open(args.filename, 'rb') as fd:
            image = ktool.load_image(fd, args.slice_index, load_imports=False, load_exports=False,
                                     use_mmaped_io=MMAP_ENABLED)

            table = Table()
            table.titles = ['Address', 'Name']

            for sym in image.symbol_table.table:
                table.rows.append([hex(sym.address), sym.fullname])

            print(table.fetch_all(get_terminal_size().columns - 1))

    if args.get_imports:
        with open(args.filename, 'rb') as fd:
            image = ktool.load_image(fd, args.slice_index, load_exports=False, load_symtab=False,
                                     use_mmaped_io=MMAP_ENABLED)

            import_symbols = {}
            symbol = namedtuple('symbol', ['addr', 'name', 'image', 'from_table'])

            for addr, sym in image.import_table.items():
                try:
                    import_symbols[sym.fullname] = symbol(hex(addr), sym.fullname,
                                                          image.linked_images[int(sym.ordinal) - 1].install_name,
                                                          sym.attr)
                except IndexError:
                    import_symbols[sym.fullname] = symbol(hex(addr), sym.fullname, "ordinal: " + str(int(sym.ordinal)),
                                                          sym.attr)

            table = Table()
            table.titles = ['Addr', 'Symbol', 'Image', 'Binding']

            for _, sym in import_symbols.items():
                table.rows.append([sym.addr, sym.name, sym.image, sym.from_table])

            print(table.fetch_all(get_terminal_size().columns))

    elif args.get_actions:
        with open(args.filename, 'rb') as fd:
            image = ktool.load_image(fd, args.slice_index, use_mmaped_io=MMAP_ENABLED)

            print('\nBinding Info'.ljust(60, '-') + '\n')
            for sym in image.binding_table.symbol_table:
                try:
                    print(
                        f'{hex(sym.address).ljust(15, " ")} | '
                        f'{image.linked_images[int(sym.ordinal) - 1].install_name} | '
                        f'{sym.name.ljust(20, " ")} | {sym.dec_type}')
                except IndexError:
                    pass
            print('\nWeak Binding Info'.ljust(60, '-') + '\n')
            for sym in image.weak_binding_table.symbol_table:
                try:
                    print(
                        f'{hex(sym.address).ljust(15, " ")} | '
                        f'{image.linked_images[int(sym.ordinal) - 1].install_name} | '
                        f'{sym.name.ljust(20, " ")} | {sym.dec_type}')
                except IndexError:
                    pass
            print('\nLazy Binding Info'.ljust(60, '-') + '\n')
            for sym in image.lazy_binding_table.symbol_table:
                try:
                    print(
                        f'{hex(sym.address).ljust(15, " ")} | '
                        f'{image.linked_images[int(sym.ordinal) - 1].install_name} | '
                        f'{sym.name.ljust(20, " ")} | '
                        f'{sym.dec_type}')
                except IndexError:
                    pass


def insert(args):
    """
----------
Utils for inserting load commands into mach-o binaries

insert a LOAD_DYLIB command
> ktool insert --lc load --payload /Dylib/Install/Name/Here.dylib --out <output filename> [filename]

commands currently supported:
    load: LOAD_DYLIB
    load-weak: LOAD_WEAK_DYLIB
    lazy-load: LAZY_LOAD_DYLIB
    load-upward: LOAD_UPWARD_DYLIB
    """

    require_args(args, always=['lc'])

    lc = None
    if args.lc == "load":
        lc = LOAD_COMMAND.LOAD_DYLIB
    elif args.lc == "load-weak" or args.lc == "load_weak":
        lc = LOAD_COMMAND.LOAD_WEAK_DYLIB
    elif args.lc in ["load_lazy", "load-lazy", "lazy-load", "lazy_load"]:
        lc = LOAD_COMMAND.LAZY_LOAD_DYLIB
    elif args.lc == "load-upward" or args.lc == "load_upward":
        lc = LOAD_COMMAND.LOAD_UPWARD_DYLIB

    patched_libraries = []

    with open(args.filename, 'rb') as fp:
        macho_file = ktool.load_macho_file(fp, use_mmaped_io=MMAP_ENABLED)
        for macho_slice in macho_file.slices:

            image = ktool.load_image(macho_slice)

            last_dylib_command_index = -1
            for i, cmd in enumerate(image.macho_header.load_commands):
                if isinstance(cmd, dylib_command):
                    last_dylib_command_index = i + 1

            dylib_item = Struct.create_with_values(dylib, [0x18, 0x2, 0x010000, 0x010000])

            LD64.insert_load_cmd_with_str(image, lc, [dylib_item.raw], args.payload, last_dylib_command_index)

            log.info("Reloading MachO Slice to verify integrity")
            image = process_patches(image)
            patched_libraries.append(image)

    with open(args.out, 'wb') as fd:
        if len(patched_libraries) > 1:
            slices = [image.slice for image in patched_libraries]
            fat_generator = FatMachOGenerator(slices)
            fd.write(fat_generator.fat_head)
            for arch in fat_generator.fat_archs:
                fd.seek(arch.offset)
                fd.write(arch.slice.full_bytes_for_slice())
        else:
            fd.write(patched_libraries[0].slice.full_bytes_for_slice())


def edit(args):
    """
----------
Utils for editing MachO Binaries

Modify the install name of a image
> ktool edit --iname [Desired Install Name] --out <Output Filename> [filename]
    """

    require_args(args, one_of=['iname', 'apad'])

    patched_libraries = []

    if args.iname:

        new_iname = args.iname

        with open(args.filename, 'rb') as fp:
            macho_file = ktool.load_macho_file(fp, use_mmaped_io=MMAP_ENABLED)
            for macho_slice in macho_file.slices:
                image = ktool.load_image(macho_slice)
                id_dylib_index = -1

                for i, cmd in enumerate(image.macho_header.load_commands):
                    if cmd.cmd == 0xD:
                        id_dylib_index = i
                        break

                dylib_item = Struct.create_with_values(dylib, [0x18, 2, 0, 0])
                LD64.remove_load_command(image, id_dylib_index)

                image = process_patches(image)

                LD64.insert_load_cmd_with_str(image, LOAD_COMMAND.ID_DYLIB, [dylib_item.raw], new_iname, id_dylib_index)

                image = process_patches(image)

                patched_libraries.append(image)

        with open(args.out, 'wb') as fd:
            if len(patched_libraries) > 1:
                slices = [image.slice for image in patched_libraries]
                fat_generator = FatMachOGenerator(slices)
                fd.write(fat_generator.fat_head)
                for arch in fat_generator.fat_archs:
                    fd.seek(arch.offset)
                    fd.write(arch.slice.full_bytes_for_slice())
            else:
                fd.write(patched_libraries[0].slice.full_bytes_for_slice())


def img4(args):
    """
----------
IMG4 Utilities

Getting keybags
> ktool img4 --kbag <filename>

Decrypting an im4p
> ktool img4 --dec --iv AES_IV --key AES_KEY [--out <output-filename>] <filename>
    """

    require_args(args, one_of=['get_kbag', 'do_decrypt'])

    if args.get_kbag:
        with open(args.filename, 'rb') as fp:
            im4p = IM4P(fp.read())
            for bag in im4p.kbag.keybags:
                print(f'{bag.iv.hex()}{bag.key.hex()}')

    if args.do_decrypt:
        require_args(args, always=['aes_key', 'aes_iv'])

        out = args.out
        if not out:
            out = args.filename + '.dec'
        with open(args.filename, 'rb') as fp:
            with open(out, 'wb') as out_fp:
                im4p = IM4P(fp.read())
                out_fp.write(im4p.decrypt_data(args.aes_iv, args.aes_key))

        print(f'Attempted decrypt of data with key/iv and saved to {out}')


def lipo(args):
    """
----------
Utilities for combining/separating slices in fat MachO files.

Extract a slice from a fat binary
> ktool lipo --extract [slice_name] [filename]

Create a fat Macho Binary from multiple thin binaries
> ktool lipo --create [--out filename] [filenames]
    """

    require_args(args, one_of=['combine', 'extract'])

    if args.combine:
        output = args.out
        if output == "":
            output = args.filename[0] + '.fat'
        slices = []
        for filename in args.filename:
            # Slice() might hold a ref preventing it from being closed? but i'm just going to let it close on exit()
            fd = open(filename, 'rb')
            macho_file = ktool.load_macho_file(fd, use_mmaped_io=MMAP_ENABLED)
            if macho_file.type != MachOFileType.THIN:
                exit_with_error(KToolError.ArgumentError, "Fat mach-o passed to --create")
            slices.append(macho_file.slices[0])

        with open(output, 'wb') as fd:
            fd.write(ktool.macho_combine(slices).read())

    elif args.extract != "":
        with open(args.filename[0], 'rb') as fd:
            macho_file = ktool.load_macho_file(fd, use_mmaped_io=MMAP_ENABLED)
            output = args.out
            if output == "":
                output = args.filename[0] + '.' + args.extract.lower()
            for macho_slice in macho_file.slices:
                if macho_slice.type.name.lower() == args.extract:
                    with open(output, 'wb') as out:
                        out.write(macho_slice.full_bytes_for_slice())
                    return
            macho_slices_list = [macho_slice.type.name.lower() for macho_slice in macho_file.slices]
            exit_with_error(KToolError.ArgumentError,
                            f'Architecture {args.extract} was not found (found: {macho_slices_list})')


def _list(args):
    """
----------
Tools for printing various lists

To print the list of classes
> ktool list --classes [filename]

To print the list of protocols
> ktool list --protocols [filename]

To print a  list of linked libraries
> ktool list --linked [filename]

To print a list of Load Commands and their data
> ktool list --cmds [filename]

Print the list of function starts
> ktool list --funcs [filename]
    """

    require_args(args, one_of=['get_classes', 'get_protos', 'get_linked', 'get_lcs', 'get_swift_types', 'get_fstarts'])

    with open(args.filename, 'rb') as fd:

        if not args.get_lcs and not args.get_linked:
            image = ktool.load_image(fd, args.slice_index, use_mmaped_io=MMAP_ENABLED)
            objc_image = ktool.load_objc_metadata(image)
        else:
            image = ktool.load_image(fd, args.slice_index, False, False, False)

        if args.get_lcs:
            table = Table(dividers=True, avoid_wrapping_titles=True)
            table.titles = ['Index', 'Load Command', 'Data']
            table.size_pinned_columns = [0, 1]
            for i, lc in enumerate(image.macho_header.load_commands):
                lc_dat = str(lc)
                if LOAD_COMMAND(lc.cmd) in [LOAD_COMMAND.LOAD_DYLIB, LOAD_COMMAND.ID_DYLIB, LOAD_COMMAND.SUB_CLIENT]:
                    lc_dat += '\n"' + image.get_cstr_at(lc.off + lc.SIZE, vm=False) + '"'
                table.rows.append([str(i), LOAD_COMMAND(lc.cmd).name.ljust(15, ' '), lc_dat])
            print(table.fetch_all(get_terminal_size().columns-5))
        elif args.get_classes:
            for obj_class in objc_image.classlist:
                print(f'{obj_class.name}')
        elif args.get_swift_types:
            load_swift_types(image)
        elif args.get_protos:
            for objc_proto in objc_image.protolist:
                print(f'{objc_proto.name}')
        elif args.get_linked:
            for extlib in image.linked_images:
                print('(Weak) ' + extlib.install_name if extlib.weak else '' + extlib.install_name)
        elif args.get_fstarts:
            for addr in image.function_starts:
                print(f'Addr: {hex(addr)} -> {image.symbols[addr].fullname if addr in image.symbols else ""}')


def _file(args):
    """
----------

Print basic information about a file (e.g 'Thin MachO Binary')
> ktool file [filename]
    """
    with open(args.filename, 'rb') as fp:
        macho_file = ktool.load_macho_file(fp, use_mmaped_io=MMAP_ENABLED)

        table = Table()
        table.titles = ['Address', 'CPU Type', 'CPU Subtype']

        for macho_slice in macho_file.slices:
            table.rows.append([
                    f'{hex(macho_slice.offset)}',
                    f'{macho_slice.type.name}',
                    f'{macho_slice.subtype.name}'])

        print(table.fetch_all(get_terminal_size().columns))


def info(args):
    """
----------
Some misc info about the target mach-o

Print generic info about a MachO file
> ktool info [--slice n] [filename]

Print VM -> Slice -> Filename address mapping for a slice
of a MachO file
> ktool info [--slice n] --vm [filename]
    """
    with open(args.filename, 'rb') as fp:
        image = ktool.load_image(fp, args.slice_index, load_symtab=False, load_imports=False, load_exports=False,
                                 use_mmaped_io=MMAP_ENABLED)

        if args.get_vm:
            print(image.vm)

        else:
            message = (f'\033[32m{image.base_name} \33[37m--- \n'
                       f'\033[34mInstall Name: \33[37m{image.install_name}\n'
                       f'\033[34mFiletype: \33[37m{image.macho_header.filetype.name}\n' 
                       f'\033[34mFlags: \33[37m{", ".join([i.name for i in image.macho_header.flags])}\n'
                       f'\033[34mUUID: \33[37m{image.uuid.hex().upper()}\n'
                       f'\033[34mPlatform: \33[37m{image.platform.name}\n'
                       f'\033[34mMinimum OS: \33[37m{image.minos.x}.{image.minos.y}.{image.minos.z}\n'
                       f'\033[34mSDK Version: \33[37m{image.sdk_version.x}.{image.sdk_version.y}.{image.sdk_version.z}')

            print(message)


def dump(args):
    """
------
Tools to reconstruct certain files from compiled MachOs

Dump header for a single class
> ktool dump --class <classname> [filename]

To dump a full set of headers for a bin/framework
> ktool dump --headers --out <directory> [filename]

To dump .tbd files for a framework
> ktool dump --tbd [filename]
    """

    require_args(args, one_of=['do_headers', 'get_class', 'do_tbd'])

    if args.get_class:
        with open(args.filename, 'rb') as fp:
            image = ktool.load_image(fp, args.slice_index, use_mmaped_io=MMAP_ENABLED)

            if image.name == "":
                image.name = os.path.basename(args.filename)

            objc_image = ktool.load_objc_metadata(image)
            objc_headers = ktool.generate_headers(objc_image, sort_items=args.sort_headers)
            for header_name, header in objc_headers.items():
                if args.get_class == header_name[:-2]:
                    print(header.generate_highlighted_text())
                    break

    if args.do_headers:

        if args.hard_fail:
            ignore.OBJC_ERRORS = False

        if args.usfs:
            opts.USE_SYMTAB_INSTEAD_OF_SELECTORS = True

        with open(args.filename, 'rb') as fp:
            image = ktool.load_image(fp, args.slice_index, use_mmaped_io=MMAP_ENABLED)

            if image.name == "":
                image.name = os.path.basename(args.filename)

            objc_image = ktool.load_objc_metadata(image)

            objc_headers = ktool.generate_headers(objc_image, sort_items=args.sort_headers)

            for header_name, header in objc_headers.items():
                if not args.outdir:
                    print(f'\n\n{header_name}\n{header}')
                elif args.outdir == 'ndbg':
                    pass
                else:
                    os.makedirs(args.outdir, exist_ok=True)
                    with open(args.outdir + '/' + header_name, 'w') as out:
                        out.write(str(header))

                if args.bench:
                    pass
                    # pprint(image.bench_stats)

    elif args.do_tbd:
        with open(args.filename, 'rb') as fp:
            image = ktool.load_image(fp, args.slice_index, use_mmaped_io=MMAP_ENABLED)

            with open(image.name + '.tbd', 'w') as out_fp:
                out_fp.write(ktool.generate_text_based_stub(image, compatibility=True))


if __name__ == "__main__":
    main()
