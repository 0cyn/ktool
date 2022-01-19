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
#  Copyright (c) kat 2021.
#
import concurrent.futures
import inspect
import os
import sys
from enum import Enum
from typing import List

from .exceptions import *

import pkg_resources

KTOOL_VERSION = pkg_resources.get_distribution('k2l').version
THREAD_COUNT = os.cpu_count() - 1


class ignore:
    MALFORMED = False
    OBJC_ERRORS = True


class opts:
    USE_SYMTAB_INSTEAD_OF_SELECTORS = False


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
        return item.func(*item.args)

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


class TapiYAMLWriter:

    @staticmethod
    def write_out(tapi_dict: dict):
        text = ["---",
                "archs:".ljust(23) + TapiYAMLWriter.serialize_list(tapi_dict['archs']),
                "platform:".ljust(23) + tapi_dict['platform'],
                "install-name:".ljust(23) + tapi_dict['install-name'],
                "current-version:".ljust(23) + str(tapi_dict['current-version']),
                "compatibility-version: " + str(tapi_dict['compatibility-version']),
                "exports:"]
        for arch in tapi_dict['exports']:
            text.append(TapiYAMLWriter.serialize_export_arch(arch))
        text.append('...')
        return '\n'.join(text)

    @staticmethod
    def serialize_export_arch(export_dict):
        text = ['  - ' + 'archs:'.ljust(22) + TapiYAMLWriter.serialize_list(export_dict['archs'])]
        if 'allowed-clients' in export_dict:
            text.append \
                ('    ' + 'allowed-clients:'.ljust(22) + TapiYAMLWriter.serialize_list(export_dict['allowed-clients']))
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
    Renderable Table
    .titles = a list of titles for each column
    .rows is a list of lists, each "sublist" representing each column, .e.g self.rows.append(['col1thing', 'col2thing'])

    This can be used with and without curses;
        you just need to set the max width it can be rendered at on the render call.
        (shutil.get_terminal_size)
    """

    def __init__(self, dividers=False):
        self.titles = []
        self.rows = []
        self.dividers = dividers
        self.column_pad = 3 if dividers else 2

        self.column_maxes = []
        self.most_recent_adjusted_maxes = []

        self.rendered_row_cache = {}
        self.header_cache = {}

    def preheat(self):

        self.column_maxes = [0 for _ in self.titles]
        self.most_recent_adjusted_maxes = [*self.column_maxes]

        # Iterate through each row,
        for row in self.rows:
            # And in each row, iterate through each column
            for index, col in enumerate(row):
                # Check the length of this column; if it's larger than the length in the array,
                #   set the max to the new one
                col_size = max([len(i)+self.column_pad for i in col.split('\n')])
                self.column_maxes[index] = max(col_size, self.column_maxes[index])

        # If the titles are longer than any of the items in that column, account for those too
        for i, title in enumerate(self.titles):
            self.column_maxes[i] = max(self.column_maxes[i], len(title) + 1 + len(self.titles))

    def fetch_all(self, screen_width):
        # This function effectively replaces the previous usage of .render() and does it all in one go.
        return self.fetch(0, len(self.rows), screen_width)

    def fetch(self, row_start, row_count, screen_width):
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
            sep_line = sep_line[:-self.column_pad].ljust(screen_width - 1, '━')[:-self.column_pad] + '━━━┦'

            rows_text = rows_text[:-len(sep_line)]  # Use our calculated sep_line length to cut off the last one
            rows_text += sep_line.replace('┠', '└').replace('╀', '┸').replace('┦', '┘')

        if screen_width in self.header_cache:
            rows_text = self.header_cache[screen_width] + rows_text
        else:
            title_row = ''
            for i, title in enumerate(self.titles):
                if self.dividers:
                    title_row += '│ ' + title.ljust(self.most_recent_adjusted_maxes[i], ' ')[:-(self.column_pad - 1)]
                else:
                    try:
                        title_row += ' ' + title.ljust(self.most_recent_adjusted_maxes[i], ' ')[:-(self.column_pad - 1)]
                    except IndexError:
                        # I have no idea what causes this
                        title_row = ""
            header_text = ""
            if self.dividers:
                header_text += sep_line.replace('┠', '┌').replace('╀', '┬').replace('┦', '┐') + '\n'
            header_text += title_row.ljust(screen_width-1)[:-1] + ' │\n' if self.dividers else title_row + '\n'
            if self.dividers:
                header_text += sep_line + '\n'
            self.header_cache[screen_width] = header_text
            rows_text = header_text + rows_text

        return rows_text

    def render(self, _rows, width, row_start):

        width -= 1

        if len(_rows) == 0:
            return ""

        if not len(self.column_maxes) > 0:
            self.preheat()

        column_maxes = [*self.column_maxes]

        # Minimum Column Size
        col_min = min(column_maxes)

        #while sum(column_maxes) < width:
        #    column_maxes = [i + 1 for i in column_maxes]

        # Iterate through column maxes, subtracting one from each until they fit within the passed width arg
        last_sum = 0
        while sum(column_maxes) >= width:
            for index, i, in enumerate(column_maxes):
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
                lines = []
                column_width = column_maxes[col_i] - self.column_pad
                string_cursor = 0
                while len(col) - string_cursor > column_width:
                    first_line_of_column = col[string_cursor:string_cursor + column_width].split('\n')[0]
                    lines.append(first_line_of_column)
                    string_cursor += len(first_line_of_column)
                    if col[string_cursor] == '\n':
                        string_cursor += 1
                while string_cursor <= len(col):
                    first_line_of_column = col[string_cursor:len(col)].split('\n')[0]
                    lines.append(first_line_of_column)
                    string_cursor += len(first_line_of_column)
                    if string_cursor == len(col):
                        break
                    if col[string_cursor] == '\n':
                        string_cursor += 1
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
                    line = '│ ' + line[:-self.column_pad].ljust(width, ' ')[:-self.column_pad] + ' │ '
                else:
                    line = ' ' + line[:-self.column_pad].ljust(width, ' ')[:-self.column_pad] + (' ' * self.column_pad)
                row_lines.append(line)

            if self.dividers:
                row_lines.append(sep_line)

            self.rendered_row_cache[width + 1][str(row_index + row_start)] = '\n'.join(row_lines)
            lines += '\n'.join(row_lines)
            lines += '\n'
        return lines


class LogLevel(Enum):
    NONE = -1
    ERROR = 0
    WARN = 1
    INFO = 2
    DEBUG = 3
    DEBUG_MORE = 4
    # if this isn't being piped to a file it will be ridiculous
    # it will also likely slow down the processor a shit-ton if it's being output to term.
    DEBUG_TOO_MUCH = 5


def print_err(msg):
    print(msg, file=sys.stderr)


class log:
    """
    Python's default logging image is absolute garbage

    so we use this.
    """

    LOG_LEVEL = LogLevel.ERROR
    # Should be a function name, without ()
    # We make this dynamically changeable for the sake of being able to redirect output in GUI tools.
    LOG_FUNC = print
    LOG_ERR = print_err

    @staticmethod
    def get_class_from_frame(fr):
        fr: inspect.FrameInfo = fr
        if 'self' in fr.frame.f_locals:
            return type(fr.frame.f_locals["self"]).__name__
        elif 'cls' in fr.frame.f_locals:
            return fr.frame.f_locals['cls'].__name__

        return None

    @staticmethod
    def line():
        stack_frame = inspect.stack()[2]
        filename = os.path.basename(stack_frame[1]).split('.')[0]
        line_name = f'L#{stack_frame[2]}'
        cn = log.get_class_from_frame(stack_frame)
        call_from = cn + ':' if cn is not None else ""
        call_from += stack_frame[3]
        return 'ktool.' + filename + ":" + line_name + ":" + call_from + '()'

    @staticmethod
    def debug(msg: str):
        if log.LOG_LEVEL.value >= LogLevel.DEBUG.value:
            log.LOG_FUNC(f'DEBUG - {log.line()} - {msg}')

    @staticmethod
    def debug_more(msg: str):
        if log.LOG_LEVEL.value >= LogLevel.DEBUG_MORE.value:
            log.LOG_FUNC(f'DEBUG-2 - {log.line()} - {msg}')

    @staticmethod
    def debug_tm(msg: str):
        if log.LOG_LEVEL.value >= LogLevel.DEBUG_TOO_MUCH.value:
            log.LOG_FUNC(f'DEBUG-3 - {log.line()} - {msg}')

    @staticmethod
    def info(msg: str):
        if log.LOG_LEVEL.value >= LogLevel.INFO.value:
            log.LOG_FUNC(f'INFO - {log.line()} - {msg}')

    @staticmethod
    def warn(msg: str):
        if log.LOG_LEVEL.value >= LogLevel.WARN.value:
            log.LOG_ERR(f'WARN - {log.line()} - {msg}')

    @staticmethod
    def warning(msg: str):
        if log.LOG_LEVEL.value >= LogLevel.WARN.value:
            log.LOG_ERR(f'WARN - {log.line()} - {msg}')

    @staticmethod
    def error(msg: str):
        if log.LOG_LEVEL.value >= LogLevel.ERROR.value:
            log.LOG_ERR(f'ERROR - {log.line()} - {msg}')
