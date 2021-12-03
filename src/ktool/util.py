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

import inspect
import os
import sys
from enum import Enum

from .exceptions import *

import pkg_resources

KTOOL_VERSION = pkg_resources.get_distribution('k2l').version


class ignore:
    MALFORMED = False


def macho_is_malformed():
    """Raise MalformedMachOException *if* we dont want to ignore bad mach-os

    :return:
    """
    if not ignore.MALFORMED:
        raise MalformedMachOException


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

    def __init__(self):
        self.titles = []
        self.rows = []

    def render(self, width):
        if len(self.rows) == 0:
            return ""

        # Initialize an array with zero for each column
        column_maxes = [0 for i in self.rows[0]]

        # Iterate through each row,
        for row in self.rows:
            # And in each row, iterate through each column
            for index, col in enumerate(row):
                # Check the length of this column; if it's larger than the length in the array,
                #   set the max to the new one
                column_maxes[index] = max(len(col), column_maxes[index])

        # If the titles are longer than any of the items in that column, account for those too
        for i, title in enumerate(self.titles):
            column_maxes[i] = max(column_maxes[i], len(title))

        # Add two to the column maxes, to account for padding
        column_maxes = [i + 2 for i in column_maxes]

        # Minimum Column Size
        col_min = min(column_maxes)

        # Iterate through column maxes, subtracting one from each until they fit within the passed width arg
        while sum(column_maxes) + (len(column_maxes) * 2) >= width:
            for index, i, in enumerate(column_maxes):
                column_maxes[index] = max(col_min, column_maxes[index] - 1)

        title_row = ''
        for i, title in enumerate(self.titles):
            title_row += title.ljust(column_maxes[i], ' ')

        rows = []

        # bit complex, this just wraps strings within their columns, to create the illusion of 'cells'
        for row_i, row in enumerate(self.rows):
            # cols is going to be an array of columns in this row
            # each column is going to be an array of lines
            cols = []

            max_line_count_in_row = 0
            for col_i, col in enumerate(row):
                lines = []
                column_width = column_maxes[col_i] - 2
                string_cursor = 0
                while len(col) - string_cursor > column_width:
                    lines.append(col[string_cursor:string_cursor + column_width])
                    string_cursor += column_width
                lines.append(col[string_cursor:len(col)])
                max_line_count_in_row = max(len(lines), max_line_count_in_row)
                cols.append(lines)

            # if any other columns in this row have more than one line,
            #   add empty lines to this column to even them out
            for col in cols:
                while len(col) < max_line_count_in_row:
                    col.append('')
            rows.append(cols)

        lines = title_row + '\n'

        for row in rows:
            row_lines = []
            column_count = len(row[0])
            for i in range(0, column_count):
                line = ""
                for j, col in enumerate(row):
                    line += col[i].ljust(column_maxes[j], ' ')
                row_lines.append(line)
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
