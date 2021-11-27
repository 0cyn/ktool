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


class LogLevel(Enum):
    NONE = -1
    ERROR = 0
    WARN = 1
    INFO = 2
    DEBUG = 3
    DEBUG_MORE = 4
    # if this isn't being piped to a file it will be ridiculous
    DEBUG_TOO_MUCH = 5


class log:
    """
    Python's default logging library is absolute garbage

    so we use this.
    """
    LOG_LEVEL = LogLevel.ERROR
    LOG_FUNC = print

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
            log.LOG_FUNC(f'WARN - {log.line()} - {msg}')

    @staticmethod
    def warning(msg: str):
        if log.LOG_LEVEL.value >= LogLevel.WARN.value:
            log.LOG_FUNC(f'WARN - {log.line()} - {msg}')

    @staticmethod
    def error(msg: str):
        if log.LOG_LEVEL.value >= LogLevel.ERROR.value:
            log.LOG_FUNC(f'ERROR - {log.line()} - {msg}')
