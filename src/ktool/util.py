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

import os
import inspect

from enum import Enum

import pkg_resources

KTOOL_VERSION = pkg_resources.get_distribution('k2l').version


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


class log:
    """
    Python's default logging library is absolute garbage

    so we use this.
    """
    LOG_LEVEL = LogLevel.ERROR

    @staticmethod
    def line():
        return 'ktool.' + os.path.basename(inspect.stack()[2][1]).split('.')[0] + ":" + str(inspect.stack()[2][2]) \
               + ":" + inspect.stack()[2][3] + '()'

    @staticmethod
    def debug(msg: str):
        if log.LOG_LEVEL.value >= LogLevel.DEBUG.value:
            print(f'DEBUG - {log.line()} - {msg}')

    @staticmethod
    def info(msg: str):
        if log.LOG_LEVEL.value >= LogLevel.INFO.value:
            print(f'INFO - {log.line()} - {msg}')

    @staticmethod
    def warn(msg: str):
        if log.LOG_LEVEL.value >= LogLevel.WARN.value:
            print(f'WARN - {log.line()} - {msg}')

    @staticmethod
    def warning(msg: str):
        if log.LOG_LEVEL.value >= LogLevel.WARN.value:
            print(f'WARN - {log.line()} - {msg}')

    @staticmethod
    def error(msg: str):
        if log.LOG_LEVEL.value >= LogLevel.ERROR.value:
            print(f'ERROR - {log.line()} - {msg}')
