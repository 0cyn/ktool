#
#  ktool | ktool
#  util.py
#
#  This file contains miscellaneous utilities used around ktool
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) 0cyn 2021.
#
import concurrent.futures
import inspect
import os
import sys
import time
from enum import Enum
from typing import List, Union
import re

from ktool_macho import Struct, FAT_CIGAM, FAT_MAGIC, MH_CIGAM, MH_CIGAM_64, MH_MAGIC, MH_MAGIC_64
from ktool.exceptions import *

import pkg_resources

import lib0cyn.log as log

try:
    KTOOL_VERSION = pkg_resources.get_distribution('k2l').version
except pkg_resources.DistributionNotFound:
    KTOOL_VERSION = '1.0.0'
THREAD_COUNT = os.cpu_count() - 1

OUT_IS_TTY = sys.stdout.isatty()

MY_DIR = __file__


def version_output():
    if OUT_IS_TTY:
        pass

    print(f'ktool v{KTOOL_VERSION}. by cynder. gh/0cyn')


class ignore:
    MALFORMED = False
    OBJC_ERRORS = True


class opts:
    USE_SYMTAB_INSTEAD_OF_SELECTORS = False
    OBJC_LOAD_ERRORS_SEND_TO_DEBUG = False


class QueueItem:
    def __init__(self):
        self.args = []
        self.func = None


class Queue:
    def __init__(self):
        self.items: List[QueueItem] = []
        self.returns: List = []
        self.multithread = False

    def process_item(self, item: QueueItem):
        try:
            return item.func(*item.args)
        except Exception as ex:
            if not ignore.OBJC_ERRORS:
                raise ex
            log.log.error("Queueitem failed to process for some unhandled reason.")
            return None

    def go(self):
        if self.multithread:
            futures = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_COUNT) as executor:
                for item in self.items:
                    futures.append(executor.submit(item.func, *item.args))
            self.returns = [f.result() for f in futures]
        else:
            self.returns = [self.process_item(item) for item in self.items]


def macho_is_malformed():
    """Raise MalformedMachOException *if* we dont want to ignore bad mach-os

    :return:
    """
    if not ignore.MALFORMED:
        raise MalformedMachOException


def uint_to_int(val, bits):
    """
    Assume an int was read from binary as an unsigned int,

    decode it as a two's compliment signed integer

    :param uint:
    :param bits:
    :return:
    """
    if (val & (1 << (bits - 1))) != 0: # if sign bit is set e.g., 8bit: 128-255
        val = val - (1 << bits)        # compute negative value
    return val

def usi32_to_si32(val):
    """
    Quick hack to read the signed val of an unsigned int (Image loads all ints from bytes as unsigned ints)

    :param val:
    :return:
    """
    bits = 32
    if (val & (1 << (bits - 1))) != 0:  # if sign bit is set e.g., 8bit: 128-255
        val = val - (1 << bits)  # compute negative value
    return val  # return positive value as is


class FileType(Enum):
    MachOFileType = 0
    FatMachOFileType = 1
    KCacheFileType = 2
    IMG4FileType = 64
    SharedCacheFileType = 128
    UnknownFileType = 512


def detect_filetype(fp) -> FileType:
    magic = fp.read(4)
    if magic in [FAT_MAGIC, FAT_CIGAM]:
        return FileType.FatMachOFileType
    elif magic in [MH_MAGIC, MH_CIGAM, MH_MAGIC_64, MH_CIGAM_64]:
        first1k = fp.read(0x1000)
        fp.seek(0)
        if b'__BOOTDATA\x00\x00\x00\x00\x00\x00' in first1k:
            return FileType.KCacheFileType
        else:
            return FileType.MachOFileType

    elif magic == b'dyld':
        return FileType.SharedCacheFileType


class TapiYAMLWriter:

    @staticmethod
    def write_out(tapi_dict: dict):
        text = ["---", "archs:".ljust(23) + TapiYAMLWriter.serialize_list(tapi_dict['archs']),
                "platform:".ljust(23) + tapi_dict['platform'], "install-name:".ljust(23) + tapi_dict['install-name'],
                "current-version:".ljust(23) + str(tapi_dict['current-version']),
                "compatibility-version: " + str(tapi_dict['compatibility-version']), "exports:"]
        for arch in tapi_dict['exports']:
            text.append(TapiYAMLWriter.serialize_export_arch(arch))
        text.append('...')
        return '\n'.join(text)

    @staticmethod
    def serialize_export_arch(export_dict):
        text = ['  - ' + 'archs:'.ljust(22) + TapiYAMLWriter.serialize_list(export_dict['archs'])]
        if 'allowed-clients' in export_dict:
            text.append(
                '    ' + 'allowed-clients:'.ljust(22) + TapiYAMLWriter.serialize_list(export_dict['allowed-clients']))
        if 'symbols' in export_dict:
            text.append('    ' + 'symbols:'.ljust(22) + TapiYAMLWriter.serialize_list(export_dict['symbols']))
        if 'objc-classes' in export_dict:
            text.append('    ' + 'objc-classes:'.ljust(22) + TapiYAMLWriter.serialize_list(export_dict['objc-classes']))
        if 'objc-ivars' in export_dict:
            text.append('    ' + 'objc-ivars:'.ljust(22) + TapiYAMLWriter.serialize_list(export_dict['objc-ivars']))
        return '\n'.join(text)

    @staticmethod
    def serialize_list(slist):
        text = "[ "
        wraplen = 55
        lpad = 28
        stack = []
        for item in slist:
            if len(', '.join(stack)) + len(item) > wraplen and len(stack) > 0:
                text += ', '.join(stack) + ',\n' + ''.ljust(lpad)
                stack = []
            stack.append(item)
        text += ', '.join(stack) + " ]"
        return text


class Table:
    """
    ASCII Table Renderer
    .titles = a list of titles for each column
    .rows is a list of lists, each "sublist" representing each column, .e.g self.rows.append(['col1thing', 'col2thing'])

    .column_pad (default is 2 (without dividers))

    This can be used with and without curses;
        you just need to set the max width it can be rendered at on the render call.
        (shutil.get_terminal_size)
    """

    def __init__(self, dividers=False, avoid_wrapping_titles=False):
        self.titles = []
        self.rows = []
        self.size_pinned_columns = []

        self.dividers = dividers
        self.avoid_wrapping_titles = avoid_wrapping_titles
        self.ansi_borders = True

        self.column_pad = 3 if dividers else 2

        # Holds the maximum length of the fields within the seperate columns
        self.column_maxes = []
        # Most recently calculated maxes (not thread safe)
        self.most_recent_adjusted_maxes = []

        # width-based caches for loaded and rendered columns
        self.rendered_row_cache = {}
        self.header_cache = {}

    def preheat(self):
        """
        Call this whenever there's a second to do so, to pre-run a few width-independent calculations

        :return:
        """
        self.column_maxes = [0 for _ in self.titles]
        self.most_recent_adjusted_maxes = [*self.column_maxes]

        # Iterate through each row,
        for row in self.rows:
            # And in each row, iterate through each column
            for index, col in enumerate(row):
                # Check the length of this column; if it's larger than the length in the array,
                #   set the max to the new one
                col_size = max([len(i) + self.column_pad for i in col.split('\n')])
                self.column_maxes[index] = max(col_size, self.column_maxes[index])

        # If the titles are longer than any of the items in that column, account for those too
        for i, title in enumerate(self.titles):
            self.column_maxes[i] = max(self.column_maxes[i], len(title) + 1 + len(self.titles))

    def fetch_all(self, screen_width):
        """
        Render the entirety of the table for a screen width

        (avoid calling this in GUI, only use it in CLI)

        :param screen_width:
        :return:
        """
        # This function effectively replaces the previous usage of .render() and does it all in one go.
        return self.fetch(0, len(self.rows), screen_width)

    def fetch(self, row_start, row_count, screen_width):
        """
        Cache-based batch processing and rendering

        Will spit out a generated table for screen_width containing row_count rows.

        :param row_start: Start index to load
        :param row_count: Amount from index to load
        :param screen_width: Screen width
        :return:
        """

        cgrey = '\33[38;5;242m'
        cwhite = '\33[37m'
        cend = '\33[39m'

        if row_count == 0:
            return ""
        rows = []
        if screen_width in self.rendered_row_cache:
            for i in range(row_start, row_start + row_count):
                if str(i) in self.rendered_row_cache[screen_width]:
                    rows.append(self.rendered_row_cache[screen_width][str(i)])
                else:
                    break
        else:
            self.rendered_row_cache[screen_width] = {}
        r_row_count = row_count - len(rows)
        r_start = row_start + len(rows)
        rows_text = ''.join([i + '\n' for i in rows])
        sep_line = ""

        rows_text += self.render(self.rows[r_start:r_start + r_row_count], screen_width, r_start)

        if self.dividers:
            rows_text = rows_text[:-1]  # cut off the "\n"
            sep_line = '┠━'
            for size in self.most_recent_adjusted_maxes:
                sep_line += ''.ljust(size - 2, '━') + '╀━'
            sep_line = cgrey + sep_line[:-self.column_pad].ljust(screen_width - 1, '━')[
                               :-self.column_pad] + '━━━┦' + cend

            rows_text = rows_text[:-(len(sep_line))]  # Use our calculated sep_line length to cut off the last one
            rows_text += sep_line.replace('┠', '└').replace('╀', '┸').replace('┦', '┘')

        if screen_width in self.header_cache:
            rows_text = self.header_cache[screen_width] + rows_text
        else:
            title_row = ''
            for i, title in enumerate(self.titles):
                if self.dividers:
                    try:
                        title_row += cgrey + '│ ' + cwhite + title.ljust(self.most_recent_adjusted_maxes[i], ' ')[
                                                             :-(self.column_pad - 1)]
                    except IndexError:
                        # I have no idea what causes this
                        title_row = ""
                else:
                    try:
                        title_row += ' ' + title.ljust(self.most_recent_adjusted_maxes[i], ' ')[:-(self.column_pad - 1)]
                    except IndexError:
                        title_row = ""
            header_text = ""
            if self.dividers:
                header_text += cgrey + sep_line.replace('┠', '┌').replace('╀', '┬').replace('┦', '┐') + cwhite + '\n'
            header_text += title_row.ljust(screen_width - 1)[
                           :-1] + cgrey + '  │\n' + cwhite if self.dividers else title_row + '\n'
            if self.dividers:
                header_text += sep_line + '\n'
            self.header_cache[screen_width] = header_text
            rows_text = header_text + rows_text

        rows_text = rows_text.replace('┠', cgrey + '┠').replace('┦', '┦' + cend)
        return rows_text

    # noinspection PyUnreachableCode
    def render(self, _rows, width, row_start):
        """
        Render a list of rows for screen_width

        :param _rows: list of rows to be rendered
        :param width: Screen width
        :param row_start: Starting index of rows (for the sake of cacheing)
        :return:
        """

        width -= 1

        if len(_rows) == 0:
            return ""

        if not len(self.column_maxes) > 0:
            self.preheat()

        column_maxes = [*self.column_maxes]

        # Minimum Column Size
        col_min = min(column_maxes)

        # Iterate through column maxes, subtracting one from each until they fit within the passed width arg
        last_sum = 0
        while sum(column_maxes) >= width:
            for index, i, in enumerate(column_maxes):
                if index in self.size_pinned_columns:
                    continue
                if self.avoid_wrapping_titles:
                    column_maxes[index] = max(col_min, column_maxes[index] - 1, len(self.titles[index]) + 3)
                else:
                    column_maxes[index] = max(col_min, column_maxes[index] - 1)
            if sum(column_maxes) == last_sum:
                return 'Width too small to render table'
            last_sum = sum(column_maxes)

        self.most_recent_adjusted_maxes = [*column_maxes]

        rows = []

        # bit complex, this just wraps strings within their columns, to create the illusion of 'cells'
        for row_i, row in enumerate(_rows):
            # cols is going to be an array of columns in this row
            # each column is going to be an array of lines
            cols = []

            max_line_count_in_row = 0
            for col_i, col in enumerate(row):
                if chr(27) in col:
                    col = col
                    print(str(col))
                lines = []
                column_width = column_maxes[col_i] - self.column_pad
                string_cursor = 0
                while len(col) - string_cursor > column_width:
                    first_line_of_column = str(col)[string_cursor:string_cursor + column_width].split('\n')[0]
                    lines.append(first_line_of_column)
                    string_cursor += len(first_line_of_column)
                    if str(col)[string_cursor] == '\n':
                        string_cursor += 1
                while string_cursor <= len(col):
                    first_line_of_column = str(col)[string_cursor:len(col)].split('\n')[0]
                    lines.append(first_line_of_column)
                    string_cursor += len(first_line_of_column)
                    if string_cursor == len(col):
                        break
                    if str(col)[string_cursor] == '\n':
                        string_cursor += 1

                if 1 == 0:
                    print(col.attrs)
                    string_cursor = 0
                    rehighlighted_lines = []
                    for line in lines:
                        line_colors = []
                        re_line = ""
                        for attr in col.attrs:
                            if attr[0][0] <= string_cursor + len(line):
                                if not attr[0][1] <= string_cursor:
                                    line_colors.append(attr)
                        for attr in line_colors:
                            if attr[0][0] <= string_cursor:
                                re_line += f'\33[{attr[1]}m'

                        for index, c in enumerate(line):
                            for attr in line_colors:
                                if index + string_cursor == attr[0][1]:
                                    re_line = f'\33[0m'
                            for attr in line_colors:
                                if index + string_cursor == attr[0][0]:
                                    re_line += f'\33[{attr[1]}m'
                            re_line += c
                        rehighlighted_lines.append(re_line + f'\33[0m')
                        string_cursor += len(line)
                    lines = rehighlighted_lines
                max_line_count_in_row = max(len(lines), max_line_count_in_row)
                cols.append(lines)

            # if any other columns in this row have more than one line,
            #   add empty lines to this column to even them out
            for col in cols:
                while len(col) < max_line_count_in_row:
                    col.append('')
            rows.append(cols)

        lines = ""
        sep_line = ""

        cgrey = '\33[38;5;242m'
        cwhite = '\33[37m'
        cend = '\33[39m'

        if self.dividers:
            sep_line = '┠━'
            for size in column_maxes:
                sep_line += ''.ljust(size - 2, '━') + '╀━'
            sep_line = sep_line[:-self.column_pad].ljust(width, '━')[:-self.column_pad] + '━━━┦'

        if self.dividers:
            lines += sep_line + '\n'

        for row_index, row in enumerate(rows):
            row_lines = []
            column_count = len(row[0])
            for i in range(0, column_count):
                line = ""
                for j, col in enumerate(row):
                    line += col[i].ljust(column_maxes[j], ' ')
                    if self.dividers:
                        line = line[:-self.column_pad] + ' │ '
                if self.dividers:
                    line = cgrey + '│ ' + cwhite + line.ljust(width, ' ')[:-self.column_pad] + cgrey + ' │ ' + cend
                    line = line.replace('│', cgrey + '│' + cwhite)
                else:
                    line = ' ' + line[:-self.column_pad].ljust(width, ' ')[:-self.column_pad] + (' ' * self.column_pad)
                row_lines.append(line)

            if self.dividers:
                row_lines.append(cgrey + sep_line + cend)

            self.rendered_row_cache[width + 1][str(row_index + row_start)] = '\n'.join(row_lines)
            lines += '\n'.join(row_lines)
            lines += '\n'
        return lines


ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')


def strip_ansi(msg):
    return ansi_escape.sub('', msg)


def bytes_to_hex(data: Union[bytes, bytearray]) -> str:
    return data.hex()


def ktool_print(msg, file=sys.stdout):
    if file.isatty():
        print(msg, file=file)
    else:
        print(strip_ansi(msg), file=file)


def print_err(msg):
    print(msg, file=sys.stderr)
