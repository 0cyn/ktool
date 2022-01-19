#
#  ktool | ktool
#  window.py
#
#  This file houses Command Line GUI rendering code. A lot of it.
#  If you're looking to contribute to this right now, and are lost, please hit me up;
#       this file is a slight mess, and the entire UI framework is custom.
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2021.
#

# # # # #
#
# Comments:::
#   I'm not a huge fan of python-curses' cryptic, C-style abstractions, so I abstracted them out myself with a proper
#       OOP approach, which also serves to fix the curses (Y, X) coordinate handling crap.
#
# CURRENT TO-DO LIST:::
# TODO: Properly Abstract out Mouse Clicks / clean up mouse handler code
#
# CURRENT FEATURE TO-DO LIST:::
# TODO: Implement the title bar menu actions
#
# # # # #

import concurrent.futures
import curses
import os
from datetime import datetime
from math import ceil

from pygments import highlight
from pygments.formatters.terminal import TerminalFormatter
from pygments.formatters.terminal256 import Terminal256Formatter
from pygments.lexers.objective import ObjectiveCLexer

from kmacho import LOAD_COMMAND

from ktool.macho import MachOFile
from ktool.dyld import Dyld
from ktool.objc import ObjCImage
from ktool.headers import HeaderGenerator
from ktool.util import Table, THREAD_COUNT

VERT_LINE = '│'
WINDOW_NAME = 'ktool'

BOX_CHARS = ['┦', '─', '━', '│', '┃', '┄', '┅', '┆', '┇', '┈', '┉', '┊', '┋', '┌', '┍', '┎', '┏', '┐', '┑', '┒', '┓', '└', '┕', '┖', '┗', '┘', '┙', '┚', '┛', '├', '┝', '┞', '┟', '┠', '┡', '┢', '┣', '┤', '┥', '┦', '┧', '┨', '┩', '┪', '┫', '┬', '┭', '┮', '┯', '┰', '┱', '┲', '┳', '┴', '┵', '┶', '┷', '┸', '┹', '┺', '┻', '┼', '┽', '┾', '┿', '╀', '╁', '╂', '╃', '╄', '╅', '╆', '╇', '╈', '╉', '╊', '╋', '╌', '╍', '╎', '╏', '═', '║', '╒', '╓', '╔', '╕', '╖', '╗', '╘', '╙', '╚', '╛', '╜', '╝', '╞', '╟', '╠', '╡', '╢', '╣', '╤', '╥', '╦', '╧', '╨', '╩', '╪', '╫', '╬', '╭', '╮', '╯', '╰', '╱', '╲', '╳', '╴', '╵', '╶', '╷', '╸', '╹', '╺', '╻', '╼', '╽', '╾', '╿']

SIDEBAR_WIDTH = 40

MAIN_TEXT = """ktool ------

This is a *very* pre-release version of the GUI Tool, and it has a long ways to go. 

Stay Updated with `python3 -m pip install --upgrade k2l` !

Mouse support is a WIP; quite a few things support mouse interaction already.

Navigate the sidebar with arrow keys or mouse. You can use left/right arrow, or spacebar, to expand/collapse submenus.

Hit tab to swap between the sidebar context and main context. Scroll the main context with up/down keys.

Backspace to exit (or click the X in the top right corner).
"""

PANIC_STRING = ""


def panic(msg):
    global PANIC_STRING
    PANIC_STRING = msg
    raise PanicException


ATTR_STRING_DEBUG = False


class ColorRep:
    def __init__(self, n):
        self.n = n

    def get_attr(self):
        return curses.color_pair(self.n)


# somewhat unused
class Attribute:
    HIGHLIGHTED = curses.A_STANDOUT
    UNDERLINED = curses.A_UNDERLINE
    COLOR_1 = ColorRep(1)
    COLOR_2 = ColorRep(2)
    COLOR_3 = ColorRep(3)
    COLOR_4 = ColorRep(4)
    COLOR_5 = ColorRep(5)
    COLOR_6 = ColorRep(6)
    COLOR_7 = ColorRep(7)


class AttributedString:
    def __init__(self, string: str):
        self.string = string
        self.attrs = []

    @staticmethod
    def ansi_to_attrstr(ansi_str):
        """This function translates ansi escaped strings (or manually specified ones, by replacing the "escape[" with §),
                to our Attributed String Format.

        :param ansi_str:
        :return:
        """
        pos = 0
        ansi_str = list(ansi_str)

        while pos < len(ansi_str):
            if ord(ansi_str[pos]) == 27:
                ansi_str[pos] = "§"
            pos += 1

        ansi_str = "".join(ansi_str)
        ansi_str = ansi_str.replace('§[', '§')

        if ATTR_STRING_DEBUG:
            return ansi_str

        pos = 0
        bland_pos = 0
        attr_str = AttributedString(ansi_str)
        bland_str = ""
        attr_start = 0
        attr_end = 0
        attr_color = 0
        while pos < len(ansi_str):
            if ansi_str[pos] == "§":
                ansi_escape_code = ""
                pos += 1
                while ansi_str[pos] != 'm':
                    ansi_escape_code += ansi_str[pos]
                    pos += 1
                ansi_list = ansi_escape_code.split(';')

                is_reset = False
                first_item = ansi_list[0]
                if first_item == '38':
                    attr_color = AttributedString.fix_256_code(int(ansi_list[2]))
                elif first_item == '39':
                    is_reset = True
                elif 30 <= int(first_item) <= 37:
                    attr_color = int(first_item) - 30 + 8

                if is_reset:
                    attr_end = bland_pos
                    attr_str.set_attr(attr_start, attr_end, curses.color_pair(attr_color))
                else:
                    attr_start = bland_pos
                    attr_str.set_attr(attr_end, attr_start, curses.A_NORMAL)

                pos += 1
            else:
                bland_str += ansi_str[pos]
                bland_pos += 1
                pos += 1
        attr_str.string = bland_str
        return attr_str

    @staticmethod
    def fix_256_code(code):
        """Pygments 256 formatter sucks.

        :param code:
        :return:
        """
        if code == 125:
            return 168
        if code == 21:
            return 151
        if code == 28:
            return 118
        return code

    def set_attr(self, start, end, attr):
        self.attrs.append([[start, end], attr])

    def __str__(self):
        return self.string


# # # # #
#
# Custom Exceptions:::
# Almost all of these are handled internally.
#
# # # # #


class ExitProgramException(Exception):
    """Raise this within the run-loop to cleanly exit the program
    """

    def __init__(self):
        pass


class RebuildAllException(Exception):
    """Raise this to invoke a rebuild
    """


class PresentDebugMenuException(Exception):
    """Raise this within the runloop to present the debug menu
    """


class PresentTitleMenuException(Exception):
    """Raise this within the runloop to invoke the Title Bar Menu Rendering code
    """


class FileBrowserOpenNewFileException(Exception):
    """

    """


class DestroyTitleMenuException(Exception):
    """Raise this to destroy the menu overlay
    """


class PanicException(Exception):
    """Raise this within the program and set the global PANIC_STRING to panic the window,
            and print the string after cleaning up the window display.
    """


class HexDumpTable(Table):
    """
    Subclass of table, just set the .hex value to a bytearray and it'll handle rendering it.

    """

    def __init__(self):
        super().__init__()
        self.titles = ['Raw Data', 'ASCII']
        self.hex = bytearray(b'')

    def fetch(self, row_start, row_count, screen_width):

        col_count = 2
        self.rows = []

        stack = ""
        decode_stack = ""
        stack_div = ""
        decode_stack_div = ""

        for i, byte in enumerate(self.hex[row_start*8:row_start*8+row_count*8]):
            stack_div += hex(byte)[2:].rjust(2, '0')
            decode_stack_div += byte.to_bytes(1, 'big').decode('ascii') + ' ' if byte in range(32, 127) else '. '
            if len(stack_div) >= 8:
                stack += stack_div + '  '
                decode_stack += decode_stack_div + '  '
                stack_div = ""
                decode_stack_div = ""
            if len(stack) >= 10 * col_count:
                self.rows.append([stack, decode_stack])
                stack = ""
                decode_stack = ""

        self.rows.append([stack, decode_stack])

        if not len(self.column_maxes) > 0:
            self.preheat()

        fetched = super().fetch(0, row_count, screen_width)

        self.rendered_row_cache = {}

        return fetched

# # # # #
#
# Lower Level Display Abstraction
#
# # # # #


class RootBox:
    """
    The Root Box is an abstraction of the regular box, with no bounds/x-y coordinates

    It represents the entire terminal window itself and handles actually writing to/from the curses standard screen.
    """

    def __init__(self, stdscr):
        self.stdscr = stdscr

    def coord_translate(self, x, y):
        return x, y

    def write(self, x, y, string, attr):
        try:
            self.stdscr.addstr(y, x, string, attr)
        except curses.error:
            global PANIC_STRING
            PANIC_STRING = f'Rendering Error while writing {string} @ {x}, {y}\nScreen Bounds: {curses.COLS}x{curses.LINES}\nProgram Panicked'
            raise PanicException


class Box:
    """
    A Box is an abstraction of an area on the screen to write to.

    It's defined with a standard set of coords/dimensions, and writes to it are relative from those defined dimensions
    """

    def __init__(self, parent, x, y, width, height):
        self.parent = parent

        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def coord_translate(self, x, y):
        px, py = self.parent.coord_translate(self.x, self.y)
        return x - px, y - py

    def write(self, x, y, string, attr):
        self.parent.write(self.x + x, self.y + y, string, attr)

    def is_click_inbounds(self, x, y):
        min_x = self.x
        max_x = self.x + self.width

        min_y = self.y
        max_y = self.y + self.width

        if min_x <= x <= max_x:
            if min_y <= y <= max_y:
                return True

        return False


class ScrollingDisplayBuffer:
    """
    A ScrollingDisplayBuffer is a text-rendering abstraction to be placed within a standard Box.

    Set its `.lines` attribute, call .draw_lines(), and it will render those lines, cleanly wrapping them and
        implementing scrolling logic to move up and down the rendered buffer.
    """

    def __init__(self, parent, x, y, width, height):
        self.box = Box(parent, x, y + 1, width, height)
        self.scrollcursor = 0
        self.parent = parent
        self.x = parent.x
        self.y = parent.y
        self.width = width
        self.height = height

        self.render_attr = curses.A_NORMAL

        self.lines = []
        self.processed_lines = []
        self.pinned_lines = []

        self.wrap = True
        self.clean_wrap = True

        self.filled_line_count = 0

    @staticmethod
    def find_clean_breakpoint(text, maxwidth):
        """Find a clean place to wrap a line, if one exists

        :param text:
        :param maxwidth:
        :return:
        """
        if isinstance(text, AttributedString):
            text = text.string
        max_text = text[:maxwidth]
        max_text = max_text.strip()
        break_index = maxwidth
        for bindex, c in enumerate(max_text[::-1]):
            if c == ' ':
                break_index = maxwidth - bindex
                break
        if break_index == maxwidth:
            # we didn't find a space breakpoint, look for a / one
            for bindex, c in enumerate(max_text[::-1]):
                if c == '/':
                    break_index = maxwidth - bindex - 1
                    break
        return break_index

    def process_lines(self):
        """Process raw lines into a cleanly wrapped version that fits within our buffer's bounds.

        This method is intensive, *do not!* call it on every redraw, it will destroy performance. Call it as little
            as possible

        :return:
        """
        self.pinned_lines = []
        if self.wrap:
            wrapped_lines = []
            for line in self.lines:
                if isinstance(line, Table):
                    wrapped_lines.append(line)
                    self.filled_line_count = -1
                    continue
                if not isinstance(line, AttributedString):
                    line = AttributedString(line)
                max_size = self.width
                indent_size = 10
                indenting = False
                lines = []
                curs = 0

                while True:
                    slice_size = max_size if not indenting else max_size - indent_size
                    slice_size = min(slice_size, len(line.string) - curs)
                    if len(line.string) + 10 - curs > max_size:
                        slice_size = self.find_clean_breakpoint(line.string[curs:curs + slice_size], slice_size)
                    text = line.string[curs:curs + slice_size]
                    if indenting:
                        text = ' ' * 10 + text
                    lines.append(text)
                    curs += slice_size
                    if len(line.string) + 10 - curs <= max_size:
                        text = line.string[curs:]
                        if text.strip() == "":
                            break
                        text = ' ' * 10 + text
                        lines.append(text)
                        break
                    indenting = True

                if lines[-1] == "" and len(lines) > 1:
                    lines.pop()

                if len(line.attrs) > 0:
                    attributes = line.attrs
                    curs = 0
                    alines = []
                    indenting = False
                    for wline in lines:
                        if len(wline) > self.width:
                            global PANIC_STRING
                            PANIC_STRING = "Line wrapping code failed sanity check: String width was larger than window size"
                            raise PanicException
                        attr_str = AttributedString(wline)
                        for attr in attributes:
                            attr_start = max(attr[0][0] - curs, 0)
                            attr_end = attr[0][1] - curs
                            if attr_end > 0:
                                if indenting:
                                    attr_start += 10
                                    attr_end += 10
                                attr_str.set_attr(attr_start, attr_end, attr[1])
                        alines.append(attr_str)
                        curs += len(wline)
                        indenting = True
                    lines = alines

                wrapped_lines += lines

            if not self.filled_line_count == -1:
                self.filled_line_count = len(wrapped_lines)
            self.processed_lines = wrapped_lines

        else:
            trunc_lines = []
            for line in self.lines:
                if not isinstance(line, AttributedString):
                    line = AttributedString(line)
                if len(line.string) > self.width:
                    slice_size = self.width
                    line.string = line.string[0:slice_size - 3] + "..."
                    trunc_lines.append(line)
                else:
                    trunc_lines.append(line)

            self.filled_line_count = len(self.lines)
            self.processed_lines = trunc_lines

    def draw_lines(self):
        """Update the internal representation of lines to be displayed.

        :return:
        """
        x = 0

        display_lines = self.rendered_lines_from(self.processed_lines, self.scrollcursor)
        for y, line in enumerate(display_lines):
            if isinstance(line, AttributedString):
                text = line.string
                self.box.write(x, y, text, self.render_attr)
                for attribute in line.attrs:
                    attr_start = attribute[0][0]
                    if attr_start < 0:
                        continue
                    attr_end = max(attribute[0][1], self.box.width)
                    attr = attribute[1]
                    try:
                        self.box.write(x + attr_start, y, text[attr_start:attr_end - 1], attr)
                    except PanicException:
                        pass
                # DEBUG: self.box.write(x, y, str(line.attrs), self.render_attr)
            else:
                self.box.write(x, y, line.ljust(self.width, ' '), self.render_attr)

    def rendered_lines_from(self, lines, start_line):
        """Return slice of lines based on window height

        :param lines: Full set of lines
        :param start_line: Line start
        :return: Slice of lines
        """
        end_line = start_line + self.height - 1
        pincount = 0
        pins = []

        prop_lines = [*lines]

        for line in lines:
            if isinstance(line, Table):
                prop_lines = []
                table_lines = [i[0:self.width] for i in
                               line.fetch(start_line, int(self.height), self.width - (20 if ATTR_STRING_DEBUG else 1)).split('\n')]
                table_attr_lines = []

                for _line in table_lines:
                    procline = ""
                    grey = False
                    for character in _line:
                        if character in BOX_CHARS:
                            if not grey:
                                procline += '§31m'
                            grey = True
                        else:
                            if grey:
                                procline += '§39m'
                            grey = False
                        procline += character
                    _line = procline + ' §39m'
                    table_attr_lines.append(AttributedString.ansi_to_attrstr(_line))
                prop_lines += table_attr_lines
                start_line = 0
                end_line = self.height - 1

        return pins + prop_lines[start_line + pincount:end_line]


# # # # #
#
# View Level Abstraction:::
# These classes represent (usually) interactive views, all of which sit on/in Display Boxes
#
# # # # #

class View:
    """
    Base View Class - Used for views that don't require too much complex functionality to render.
    """

    def __init__(self):
        self.box = None
        self.children = []
        self.draw = True

    def add_subview(self, view):
        if view not in self.children:
            self.children.append(view)

    def coord_translate(self, x, y):
        return self.box.coord_translate(x, y)

    def redraw(self):
        """
        The .redraw() method is called by the view controller and should be implemented by subclasses to
            re-update the self.box property with its contents. This is how all Views should handle updating/changing
            their content.

        :return:
        """
        pass

    def handle_key_press(self, key):
        """
        This method is called by the View Controller and is passed key-press events.

        key-press events are passed if the View Controller or higher-priority views dont absorb the keypress event.
        If this view decides it should handle it (by returning True), the key-press will be "handled" and not passed
            to any other Views.

        :param key: Key ordinal
        :return: True or False; whether the keypress was handled by this View
        """
        return False

    def handle_mouse(self, x, y):
        """
        This method is called by the View Controller and is passed mouse events.

        Mouse events are passed if the VC itself or higher-priority views dont absorb the mouse event.
        If this view decides it should handle it (by returning True), the mouse event will be "handled" and not passed
            to any other Views.

        :param x: X coordinate of the mouse-press
        :param y: Y coordinate of the mouse-press
        :return: True or False; whether the keypress was handled by this View
        """
        for child in self.children:
            if child.handle_mouse(x, y):
                return True
        return False


class ScrollView(View):
    """
    ScrollView - Used for views which may display text/lists that require scrolling functionality
    """

    def __init__(self):
        super().__init__()
        self.scroll_view = None
        self.scroll_view_text_buffer = None

        # TODO: Implement
        self.scroll_cursor = 0


class Button(View):
    def __init__(self, parent, x, y, height):
        super().__init__()
        self.text = ""
        self.box = Box(parent.box, x, y, 0, height)

    def set_text(self, text):
        self.text = text
        self.box.width = len(text)

    def redraw(self):
        self.box.write(0, 0, self.text, curses.A_NORMAL)

    def handle_mouse(self, x, y):
        tx, ty = self.box.coord_translate(x, y)
        if 0 <= tx <= self.box.width:
            if 0 <= ty <= self.box.height:
                self.action()
                return True
        return False

    def action(self):
        pass


# # # # #
#
# Title Bar:::
# Handles the Title Bar and the Menus it provides
#
# # # # #


class TitleBarMenuItem:
    def __init__(self, text):
        self.text = text
        self.rend_text = f' {text} '
        self.rend_width = len(self.rend_text)
        self.menu_items = []


class FileMenuItem(TitleBarMenuItem):
    def __init__(self):
        super().__init__("File")
        self.menu_items.append(("Open", self.open))
        self.menu_items.append(("Save Edits", self.save))

    def open(self):
        raise FileBrowserOpenNewFileException

    def save(self):
        pass


class EditMenuItem(TitleBarMenuItem):
    def __init__(self):
        super().__init__("Edit")
        self.menu_items.append(("Delete Item", self.delete))

    def delete(self):
        pass


class DumpMenuItem(TitleBarMenuItem):
    def __init__(self):
        super().__init__("Dump")
        self.menu_items.append(("Dump Headers", self.headers))
        self.menu_items.append(("Dump TAPI stub", self.tbd))

    def headers(self):
        pass

    def tbd(self):
        pass


class TitleBar(View):
    """
    The Title Bar represents the top 1st line of the window.
    It's responsible for displaying the window title and menus
    """
    MENUS_START = 10

    def __init__(self):
        super().__init__()

        self.menu_items = []
        self.menu_item_xy_map = {}

        self.pres_menu_item = None
        self.pres_menu_item_index = -1

        self.add_menu_item(FileMenuItem())
        self.add_menu_item(EditMenuItem())
        self.add_menu_item(DumpMenuItem())

        self.exit_button = Button(self, 0, 0, 1)
        self.exit_button.set_text(" Exit ")
        self.exit_button.action = self.exit

        self.add_subview(self.exit_button)

    def exit(self):
        raise ExitProgramException

    def add_menu_item(self, item):
        if len(self.menu_items) > 0:
            top_item = self.menu_items[-1]
            start_x = self.menu_item_xy_map[top_item][0] + top_item.rend_width + 2
        else:
            start_x = TitleBar.MENUS_START + 3
        self.menu_items.append(item)
        self.menu_item_xy_map[item] = [start_x, 0]

    def redraw(self):

        if not self.box:
            return

        self.box.write(0, 0, '╒' + '═'.ljust(curses.COLS - 3, '═') + '╕', curses.color_pair(9))
        self.box.write(2, 0, f' {WINDOW_NAME} ', curses.A_NORMAL)
        self.box.write(0, 1, '┟' + ''.ljust(curses.COLS - 3, '━') + '┦', curses.color_pair(9))
        self.box.write(TitleBar.MENUS_START, 0, '╤', curses.color_pair(9))
        self.box.write(TitleBar.MENUS_START, 1, '┸', curses.color_pair(9))

        x = TitleBar.MENUS_START + 3
        for item in self.menu_items:
            self.box.write(x, 0, item.rend_text, curses.A_NORMAL)
            self.box.write(x + 1, 0, item.rend_text[1], curses.A_UNDERLINE)
            x += item.rend_width + 2

        for child in self.children:
            child.redraw()

    def handle_key_press(self, key):
        if self.pres_menu_item_index < 0:
            return False
        if key == curses.KEY_LEFT:
            if self.pres_menu_item_index > 0:
                n_ind = self.pres_menu_item_index - 1
                n_item = self.menu_items[n_ind]
                coords = self.menu_item_xy_map[n_item]
                self.pres_menu_item = (n_item, coords[0])
                self.pres_menu_item_index = n_ind
                raise PresentTitleMenuException

        elif key == curses.KEY_RIGHT:
            if not self.pres_menu_item_index + 1 >= len(self.menu_items):
                n_ind = self.pres_menu_item_index + 1
                n_item = self.menu_items[n_ind]
                coords = self.menu_item_xy_map[n_item]
                self.pres_menu_item = (n_item, coords[0])
                self.pres_menu_item_index = n_ind
                raise PresentTitleMenuException

        return False

    def handle_mouse(self, x, y):
        handle = False

        if y < 1:
            if super().handle_mouse(x, y):
                return True

            handle = True

            if x < 10:
                raise PresentDebugMenuException
            i = 0
            for item, coords in self.menu_item_xy_map.items():
                if coords[0] <= x <= coords[0] + item.rend_width:
                    self.pres_menu_item = (item, coords[0])
                    self.pres_menu_item_index = i
                    raise PresentTitleMenuException
                i += 1

        return handle


# # # # #
#
# Footer Bar:::
# Mainly just holds debug info at the moment. Maybe it will get used later.
#
# # # # #


class FooterBar(View):
    MENUS_START = 40

    def __init__(self):
        super().__init__()
        self.show_debug = False
        self.debug_text = ''

        self.hi_text = ''

        self.now = datetime.now().time()
        graveyard = 'hope your night is going well'
        morning = 'good morning! :)'
        afternoon = 'good afternoon'
        evening = 'good evening ~'
        msgmap = {
            (22, 24): graveyard,
            (0, 4): graveyard,
            (5, 11): morning,
            (12, 16): afternoon,
            (17, 21): evening
        }
        for key, val in msgmap.items():
            if self.now.hour in range(key[0], key[1] + 1):
                self.hi_text = f' {val} '

    def redraw(self):
        self.box.write(0, 0, '╘' + '═'.ljust(curses.COLS - 3, '═') + '╛', curses.color_pair(9))
        self.box.write(FooterBar.MENUS_START, 0, '╧', curses.color_pair(9))

        if self.show_debug:
            self.box.write(self.box.width - len(self.debug_text) - 5, 0, self.debug_text, curses.A_NORMAL)
        else:
            self.box.write(self.box.width - len(self.hi_text) - 5, 0, self.hi_text, curses.color_pair(9))


# # # # #
#
# SideBar:::
# True backbone of the screen; Sidebar is responsible for displaying the various
#   contexts available to be shown on the Main Menu
#
# # # # #


class SidebarMenuItem:
    def __init__(self, name: str, menu_content, parent=None):
        self.name = name
        self.rend_name = name
        self.content = menu_content
        self.parent = parent
        self.children = []
        self.show_children = False
        self.selected = False

    def parse_mmc(self):
        attrib_content = []
        for item in self.content.lines:
            if isinstance(item, str):
                attrib_content.append(AttributedString.ansi_to_attrstr(item))
            else:
                attrib_content.append(item)
        self.content = MainMenuContentItem(attrib_content)

    @staticmethod
    def item_list_with_children(menu_item, depth=1):
        """
        Recursive function that returns a single, non-nested, ordered list of items and their children for display.

        :param depth:
        :param menu_item: Root item to recurse through children of.
        :return: List of items generated
        """
        items = [menu_item]
        if menu_item.show_children:
            for child in menu_item.children:
                child.rend_name = '  ' * depth + child.name
                items += SidebarMenuItem.item_list_with_children(child, depth + 1)
        return items


class Sidebar(ScrollView):
    WIDTH = SIDEBAR_WIDTH

    def __init__(self):
        super().__init__()

        self.selected_index = 0

        self.current_sidebar_item_count = 0
        self.processed_items = []

        self.items = []

    def redraw(self):
        # Redraw right-side divider
        self.update_item_listing()
        for index in range(0, curses.LINES - 2):
            self.box.write(0, index, VERT_LINE, curses.color_pair(9))
            self.box.write(Sidebar.WIDTH, index, VERT_LINE, curses.color_pair(9))
        self.box.write(SIDEBAR_WIDTH, 0, '┰', curses.color_pair(9))

    def select_item(self, index):
        """
        Update selected item index and redraw the item listing.

        :param index:
        :return:
        """
        self.selected_index = index
        self.update_item_listing()

    def update_item_listing(self):
        """
        Re-process the entire item listing to generate the content to be displayed.

        :return:
        """

        self.processed_items = []
        for item in self.items:
            self.processed_items += SidebarMenuItem.item_list_with_children(item)

        self.current_sidebar_item_count = len(self.processed_items)

        self.scroll_view_text_buffer.lines = []

        for index, item in enumerate(self.processed_items):
            name = item.rend_name.ljust(SIDEBAR_WIDTH - 6, ' ')

            if len(item.children) > 0:
                if item.show_children:
                    name = name + '-'
                else:
                    name = name + '+'
            else:
                name = name + ' '
            if self.selected_index == index:
                name = AttributedString(name)
                name.set_attr(0, len(name.string) - 1, Attribute.HIGHLIGHTED)
                self.scroll_view_text_buffer.lines.append(name)
            else:
                self.scroll_view_text_buffer.lines.append(name)

        # This chunk of code makes sure the currently selected sidebar position is always visible.
        # It scrolls as the user selection moves up/down
        # The "while" loop makes sure that, if a submenu multiple times the size of the screen height was collapsed,
        #       the scroll cursor will jump to a position where things are visible again.
        scroll_view_height = self.scroll_view_text_buffer.height
        if self.selected_index - scroll_view_height + 4 > self.scroll_view_text_buffer.scrollcursor:
            while self.selected_index - scroll_view_height + 4 > self.scroll_view_text_buffer.scrollcursor:
                self.scroll_view_text_buffer.scrollcursor += 1
        elif self.selected_index < self.scroll_view_text_buffer.scrollcursor + 2 and self.scroll_view_text_buffer.scrollcursor > 0:
            while self.selected_index < self.scroll_view_text_buffer.scrollcursor + 2 and self.scroll_view_text_buffer.scrollcursor > 0:
                self.scroll_view_text_buffer.scrollcursor -= 1

        self.scroll_view_text_buffer.process_lines()
        self.scroll_view_text_buffer.draw_lines()

    def add_menu_item(self, item):
        """
        Add a root menu item to the Sidebar and update the list.

        :param item:
        :return:
        """
        self.items.append(item)
        self.update_item_listing()

    def collapse_index(self, index):
        """
        Collapse item at index if it is open.

        :param index:
        :return:
        """
        item = self.processed_items[index]
        if len(item.children) > 0 and item.show_children:
            item.show_children = False

            self.update_item_listing()
        else:
            swap_to_index = 0
            for index, pitem in enumerate(self.processed_items):
                if pitem == item.parent:
                    swap_to_index = index
                    break
            pitem = self.processed_items[swap_to_index]
            pitem.show_children = False

            self.update_item_listing()
            self.select_item(swap_to_index)
            self.update_item_listing()

    def handle_key_press(self, key):
        if key == curses.KEY_UP:
            index = self.selected_index
            if index - 1 in range(0, self.current_sidebar_item_count):
                self.select_item(index - 1)

        elif key == curses.KEY_DOWN:
            index = self.selected_index
            if index + 1 in range(0, self.current_sidebar_item_count):
                self.select_item(index + 1)

        elif key == curses.KEY_LEFT:
            index = self.selected_index
            self.collapse_index(index)

        elif key == curses.KEY_RIGHT:
            index = self.selected_index
            item = self.processed_items[index]
            if len(item.children) > 0:
                item.show_children = True
                self.update_item_listing()

        elif key == ord(" "):
            index = self.selected_index
            item = self.processed_items[index]
            if item.show_children:
                self.collapse_index(index)
            else:
                if len(item.children) > 0:
                    item.show_children = True
                    self.update_item_listing()
        else:
            return False

        return True

    def handle_mouse(self, x, y):
        absorb = False
        if x < SIDEBAR_WIDTH and y > self.box.y:
            absorb = True
            y = y - 3
            x = x - 2

            if -1 <= x - SIDEBAR_WIDTH + 6 <= 1 and y < len(self.processed_items):
                index = y
                item = self.processed_items[index]
                if len(item.children) > 0:
                    if item.show_children:
                        self.selected_index = y
                        self.collapse_index(y)
                    else:
                        item.show_children = True
                        self.update_item_listing()
            elif y < len(self.processed_items):
                self.select_item(y)

        return absorb


# # # # #
#
# Main Screen:::
# Displays text from the current context.
#
# # # # #


class MainMenuContentItem:
    """
    Just holds the unprocessed lines to be displayed in the Main Menu.

    These are generated at the start and stored in Sidebar Menu Items, from which the View Controller pulls them out and
        displays the in the Main Screen.
    """

    def __init__(self, lines=None):
        if lines is None:
            lines = []
        self.lines = lines


class MainScreen(ScrollView):
    """
    Displays the currently relevant text from the context.
    """

    def __init__(self):
        super().__init__()
        self.info_box = None

        self.tabname = ""
        self.highlighted = False

        self.currently_displayed_index = 0

    def set_tab_name(self, name):
        """
        Update the tab name

        :param name:
        :return:
        """
        self.tabname = name

    def redraw(self):
        width = curses.COLS - Sidebar.WIDTH - 2

        for index in range(0, curses.LINES - 2):
            self.box.write(width, index, VERT_LINE, curses.color_pair(9))

        # Redraw the text
        self.scroll_view_text_buffer.draw_lines()

        width = curses.COLS - Sidebar.WIDTH - 3
        # Clear and Redraw the Info Box bar
        self.info_box.write(-1, 1, '╞' + ''.ljust(width, '═') + '╡', curses.color_pair(9))
        self.info_box.write(2, 1, f'╡ {self.tabname.strip()} ╞', curses.color_pair(9))
        self.info_box.write(3, 1, f' {self.tabname.strip()} ',
                            curses.A_NORMAL if not self.highlighted else curses.A_STANDOUT)

    def handle_key_press(self, key):
        if key == curses.KEY_UP:
            self.scroll_view_text_buffer.scrollcursor = max(0, self.scroll_view_text_buffer.scrollcursor - 1)
            self.scroll_view_text_buffer.draw_lines()
            return True
        elif key == curses.KEY_DOWN:
            if self.scroll_view_text_buffer.filled_line_count == -1:
                self.scroll_view_text_buffer.scrollcursor += 1
            else:
                self.scroll_view_text_buffer.scrollcursor = min(
                    self.scroll_view_text_buffer.filled_line_count - self.scroll_view_text_buffer.height + 1,
                    self.scroll_view_text_buffer.scrollcursor + 1)
            self.scroll_view_text_buffer.draw_lines()
            return True
        elif key == ord("d"):
            global ATTR_STRING_DEBUG
            ATTR_STRING_DEBUG = True
            raise RebuildAllException

        return False


class DebugMenu(ScrollView):
    def __init__(self):
        super().__init__()
        self.draw = False

    def parse_lines(self):
        attrib_content = []
        for item in self.scroll_view_text_buffer.lines:
            if isinstance(item, str):
                attrib_content.append(AttributedString.ansi_to_attrstr(item))
            else:
                attrib_content.append(item)

        self.scroll_view_text_buffer.lines = attrib_content

    def redraw(self):
        width = self.box.width - 10
        height = self.box.height
        lc = '╒'
        rc = '╕'
        div = '═'
        bl = '╘'
        br = '╛'

        bgcolor = curses.color_pair(1)

        self.box.write(0, 0, lc + ''.ljust(width - 2, div) + rc, bgcolor)

        for line in range(1, height):
            self.box.write(0, line, VERT_LINE + ''.ljust(width - 2, ' ') + VERT_LINE, bgcolor)

        self.box.write(0, height, bl + ''.ljust(width - 2, div) + br, bgcolor)

        self.scroll_view_text_buffer.process_lines()
        self.scroll_view_text_buffer.draw_lines()

    def handle_key_press(self, key):
        if key == curses.KEY_UP:
            self.scroll_view_text_buffer.scrollcursor = max(0, self.scroll_view_text_buffer.scrollcursor - 1)
            self.scroll_view_text_buffer.draw_lines()
            return True
        elif key == curses.KEY_DOWN:
            self.scroll_view_text_buffer.scrollcursor = min(
                self.scroll_view_text_buffer.filled_line_count - self.scroll_view_text_buffer.height + 1,
                self.scroll_view_text_buffer.scrollcursor + 1)
            self.scroll_view_text_buffer.draw_lines()
            return True
        return False

    def handle_mouse(self, x, y):

        x = x - self.box.x
        y = y - self.box.y

        handle = False
        if not self.draw:
            return handle

        if y == 0:
            handle = True
            if -1 <= x - self.box.width + 15 <= 1:
                self.draw = False

        return handle


class LoaderStatusView(View):
    def __init__(self):
        super().__init__()
        self.draw = False
        self.status_string = "Loading..."

    def redraw(self):
        if not self.draw:
            return
        box_width = max(40, len(self.status_string) + 10)
        start_x = ceil(self.box.width / 2 - box_width / 2)
        height = 4
        start_y = ceil(self.box.height / 2 - height / 2)

        for i in range(start_y, start_y + height + 1):
            self.box.write(start_x, i, ' ' * box_width, curses.A_STANDOUT)

        i = 0
        for line in self.status_string.split('\n'):
            self.box.write(start_x + 1, start_y + 1 + i, line, curses.A_STANDOUT)
            i += 1


class UserInputPrompt(View):
    def __init__(self):
        super().__init__()
        self.draw = False
        self.prompt_string = ""
        self.user_input_is_string = False

        self.active_render_subbox = None
        self.response = None

    def redraw(self):
        if not self.draw:
            return
        box_width = max(40, len(self.prompt_string) + 10)
        start_x = ceil(self.box.width / 2 - box_width / 2)
        height = 4
        start_y = ceil(self.box.height / 2 - height / 2)

        self.active_render_subbox = Box(None, start_x, start_y, box_width, height)

        for i in range(start_y, start_y + height + 1):
            self.box.write(start_x, i, ' ' * box_width, curses.A_STANDOUT)

        xof = 2
        for msg in ['YES', 'NO', 'CANCEL']:
            self.box.write(xof, height, msg, curses.A_STANDOUT)
            xof += len(msg) + 2

    def handle_mouse(self, x, y):
        if not self.draw:
            return False

        if self.active_render_subbox.is_click_inbounds(x, y) and y - self.active_render_subbox.y == 4:
            xof = 2
            xp = x - self.active_render_subbox.x
            height = 4
            for msg in ['YES', 'NO', 'CANCEL']:
                self.box.write(xof, height, msg, curses.A_STANDOUT)
                wid = len(msg)
                if xp in range(xof, xof + wid + 1):
                    if msg == 'YES':
                        self.response = 'y'
                    elif msg == 'NO':
                        self.response = 'n'
                    else:
                        self.response = 'c'
                    return True
                xof += len(msg) + 2

        return False


class MenuOverlayRenderingView(View):
    def __init__(self):
        super().__init__()
        self.draw = False
        self.active_render_menu = None
        self.active_menu_start_x = 0

        self.active_render_subbox = None

    def redraw(self):
        if not self.draw or not self.active_render_menu:
            return

        start = (self.active_menu_start_x + 1, 1)
        width = 30
        height = len(self.active_render_menu.menu_items) + 2

        self.active_render_subbox = Box(None, start[0], start[1], width, height)

        for line in range(start[1], start[1] + height):
            self.box.write(start[0], line, ' ' * width, curses.A_STANDOUT)

        for linen, item in enumerate([i[0] for i in self.active_render_menu.menu_items]):
            self.box.write(start[0] + 1, start[1] + 1 + linen, f'{item}', curses.A_STANDOUT)

    def handle_mouse(self, x, y):
        if not self.draw or not self.active_render_menu:
            return False

        if self.active_render_subbox.is_click_inbounds(x, y):
            # x = x - self.active_render_subbox.x
            y = y - self.active_render_subbox.y - 1
            if y < 0:
                return False
            if y > len(self.active_render_menu.menu_items):
                raise DestroyTitleMenuException
            if y == len(self.active_render_menu.menu_items):
                return False
            item_tup = self.active_render_menu.menu_items[y]
            item_tup[1]()
            return True

        raise DestroyTitleMenuException


class FileSystemBrowserOverlayView(ScrollView):
    def __init__(self):
        super().__init__()
        self.draw = False
        self.current_dir_path = os.getcwd()
        self.select_file = True
        self.callback = None

        self.selected_index = 0

    def redraw(self):
        start_x = 3
        width = self.box.width - (2 * start_x)
        start_y = start_x
        height = self.box.height - (2 * start_y)

        lc = '╒'
        rc = '╕'
        div = '═'
        bl = '╘'
        br = '╛'
        lj = '╞'
        rj = '╡'

        bgcolor = curses.A_NORMAL

        self.box.write(start_x, start_y, lc + ''.ljust(width - 2, div) + rc, bgcolor)

        for line in range(start_y + 1, start_y + height + 1):
            self.box.write(start_x, line, VERT_LINE + ''.ljust(width - 2, ' ') + VERT_LINE, bgcolor)

        self.box.write(start_x, start_y + height, bl + ''.ljust(width - 2, div) + br, bgcolor)
        self.box.write(start_x, start_y + height - 2, lj + ''.ljust(width - 2, div) + rj, bgcolor)
        self.box.write(start_x + width - 10, start_y + height - 1, ' SELECT ', curses.A_STANDOUT)

        lines = ['..'] + [i for i in os.listdir(self.current_dir_path)]
        nlines = []
        for item in lines:
            if os.path.isdir(item):
                nlines.append(f'{item}/')
            else:
                nlines.append(item)

        for index, name in enumerate(nlines):
            if self.selected_index == index:
                name = AttributedString(name)
                name.set_attr(0, len(name.string) - 1, Attribute.HIGHLIGHTED)
                self.scroll_view_text_buffer.lines.append(name)
            else:
                self.scroll_view_text_buffer.lines.append(name)

        # This chunk of code makes sure the currently selected sidebar position is always visible.
        # It scrolls as the user selection moves up/down
        # The "while" loop makes sure that, if a submenu multiple times the size of the screen height was collapsed,
        #       the scroll cursor will jump to a position where things are visible again.
        scroll_view_height = self.scroll_view_text_buffer.height
        if self.selected_index - scroll_view_height + 4 > self.scroll_view_text_buffer.scrollcursor:
            while self.selected_index - scroll_view_height + 4 > self.scroll_view_text_buffer.scrollcursor:
                self.scroll_view_text_buffer.scrollcursor += 1
        elif self.selected_index < self.scroll_view_text_buffer.scrollcursor + 2 and self.scroll_view_text_buffer.scrollcursor > 0:
            while self.selected_index < self.scroll_view_text_buffer.scrollcursor + 2 and self.scroll_view_text_buffer.scrollcursor > 0:
                self.scroll_view_text_buffer.scrollcursor -= 1

        self.scroll_view_text_buffer.process_lines()
        self.scroll_view_text_buffer.draw_lines()

    def handle_key_press(self, key):
        if not self.draw:
            return False

        if key == curses.KEY_UP:
            index = self.selected_index
            if index - 1 in range(0, len(self.scroll_view_text_buffer.lines)):
                self.selected_index -= 1
            return True

        elif key == curses.KEY_DOWN:
            index = self.selected_index
            if index + 1 in range(0, len(self.scroll_view_text_buffer.lines)):
                self.selected_index += 1
            return True

        return False


# # # # #
#
# File Loaders:::
# Handles creating Sidebar and MainMenuContent items for a given file
#
# # # # #


class KToolMachOLoader:
    SUPPORTS_256 = False
    SUPPORTS_COLOR = True
    HARD_FAIL = False
    CUR_SL = 0
    SL_CNT = 0

    @staticmethod
    def parent_count(item):
        count = 0
        item = item
        while item.parent is not None:
            count += 1
            item = item.parent
        return count

    @staticmethod
    def contents_for_file(fd, callback):
        machofile = MachOFile(fd)
        items = []
        KToolMachOLoader.SL_CNT = len(machofile.slices)
        for macho_slice in machofile.slices:
            KToolMachOLoader.CUR_SL += 1
            try:
                items.append(KToolMachOLoader.slice_item(macho_slice, callback))
            except Exception as ex:
                raise ex
        return items

    @staticmethod
    def slice_item(macho_slice, callback):
        loaded_image = Dyld.load(macho_slice)
        if hasattr(macho_slice, 'type'):
            slice_nick = macho_slice.type.name + " Slice"
        else:
            slice_nick = "Thin MachO"
        callback(f'Slice {KToolMachOLoader.CUR_SL}/{KToolMachOLoader.SL_CNT}\nLoading MachO Image')
        slice_item = SidebarMenuItem(f'{slice_nick}', None, None)
        slice_item.content = KToolMachOLoader._file(loaded_image, slice_item, callback).content
        items = [KToolMachOLoader.load_cmds,
                 KToolMachOLoader.segments,
                 KToolMachOLoader.linked,
                 KToolMachOLoader.imports,
                 KToolMachOLoader.exports,
                 KToolMachOLoader.symtab]
        for item in items:
            try:
                slice_item.children.append(item(loaded_image, slice_item, callback))
            except Exception as ex:
                if KToolMachOLoader.HARD_FAIL:
                    raise ex
                else:
                    pass
        try:
            slice_item.children += KToolMachOLoader.objc_items(loaded_image, slice_item, callback)
        except Exception as ex:
            if KToolMachOLoader.HARD_FAIL:
                raise ex
            else:
                pass
        slice_item.show_children = True
        return slice_item

    @staticmethod
    def segments(lib, parent=None, callback=None):
        callback(f'Slice {KToolMachOLoader.CUR_SL}/{KToolMachOLoader.SL_CNT}\nLoading Segments & Generating Hexdumps')
        smmci = MainMenuContentItem()
        ssmi = SidebarMenuItem("Segments", smmci, parent)
        table = Table(True)
        table.titles = ['Segment Name', 'VM Address', 'Size', 'File Address']

        for segname, segm in lib.segments.items():

            table.rows.append([segname, hex(segm.vm_address), hex(segm.size), hex(segm.file_address)])

            segtable = Table()
            segtable.titles = ['Section Name', 'VM Address', 'Size', 'File Address']
            mmci = MainMenuContentItem()
            item = SidebarMenuItem(f'{segname} [{len(segm.sections.items())} Sections]', mmci, ssmi)
            for secname, sect in segm.sections.items():
                segtable.rows.append([secname, hex(sect.vm_address), hex(sect.size), hex(sect.file_address)])
                hextab = HexDumpTable()
                hextab.hex = lib.slice.get_bytes_at(sect.file_address, sect.size)
                itm = MainMenuContentItem()
                itm.lines.append(hextab)
                item.children.append(SidebarMenuItem(secname, itm, item))
            ssmi.children.append(item)
            mmci.lines.append(segtable)
            if len(segm.sections.items()) == 0:
                if 'PAGEZERO' not in segname:
                    hextab = HexDumpTable()
                    hextab.hex = lib.slice.get_bytes_at(segm.file_address, segm.size)
                    mmci.lines.append(hextab)

        smmci.lines.append(table)

        ssmi.parse_mmc()
        return ssmi

    # noinspection PyUnusedLocal
    @staticmethod
    def _file(lib, parent=None, callback=None):
        file_content_item = MainMenuContentItem()

        file_content_item.lines.append(f'Install Name: §35m{lib.install_name}§39m')
        file_content_item.lines.append(f'Filetype: §35m{lib.macho_header.filetype.name}§39m')
        file_content_item.lines.append(f'Flags: §35m{"§39m, §35m".join([i.name for i in lib.macho_header.flags])}§39m')
        if lib.uuid:
            file_content_item.lines.append(f'UUID: §35m{lib.uuid.hex().upper()}§39m')
        file_content_item.lines.append(f'Platform: §35m{lib.platform.name}§39m')
        file_content_item.lines.append(f'Minimum OS: §35m{lib.minos.x}.{lib.minos.y}.{lib.minos.z}§39m')
        file_content_item.lines.append(
            f'SDK Version: §35m{lib.sdk_version.x}.{lib.sdk_version.y}.{lib.sdk_version.z}§39m')

        file_content_item.lines.append('')
        file_content_item.lines.append(f'macho_header: {str(lib.macho_header.dyld_header)}')

        menuitem = SidebarMenuItem("File Info", file_content_item, parent)
        menuitem.parse_mmc()

        return menuitem

    @staticmethod
    def linked(lib, parent=None, callback=None):

        callback(f'Slice {KToolMachOLoader.CUR_SL}/{KToolMachOLoader.SL_CNT}\nLoading Linked Libs')

        linked_libs_item = MainMenuContentItem()
        for exlib in lib.linked_images:
            linked_libs_item.lines.append(
                '§31m(Weak)§39m ' + exlib.install_name if exlib.weak else '' + exlib.install_name)

        menuitem = SidebarMenuItem("Linked Libraries", linked_libs_item, parent)
        menuitem.parse_mmc()
        return menuitem

    @staticmethod
    def load_cmds(lib, parent=None, callback=None):

        callback(f'Slice {KToolMachOLoader.CUR_SL}/{KToolMachOLoader.SL_CNT}\nProcessing Load Commands')

        load_cmds = MainMenuContentItem()

        lines = [f'Load Command Count: {len(lib.macho_header.load_commands)}']

        load_cmds.lines = lines

        menuitem = SidebarMenuItem("Load Commands", load_cmds, parent)

        for cmd in lib.macho_header.load_commands:
            mmci = MainMenuContentItem()
            mmci.lines = str(cmd).split('\n')
            raw: bytes = lib.slice.get_bytes_at(cmd.off, cmd.cmdsize)
            hexdump = HexDumpTable()
            hexdump.hex = bytearray(raw)

            # noinspection PyTypeChecker
            mmci.lines.append(hexdump)

            try:
                item_name = LOAD_COMMAND(cmd.cmd).name
            except ValueError:
                item_name = str(cmd.cmd)

            lc_menu_item = SidebarMenuItem(item_name, mmci, menuitem)
            menuitem.children.append(lc_menu_item)

        menuitem.parse_mmc()
        return menuitem

    @staticmethod
    def symtab(lib, parent=None, callback=None):
        callback(f'Slice {KToolMachOLoader.CUR_SL}/{KToolMachOLoader.SL_CNT}\nProcessing Symtab')
        mmci = MainMenuContentItem()
        tab = Table(True)
        tab.titles = ['Address', 'Name']
        for sym in lib.symbol_table.table:
            tab.rows.append([hex(sym.address), sym.fullname])
        mmci.lines.append(tab)

        menuitem = SidebarMenuItem("Symbol Table", mmci, parent)

        menuitem.parse_mmc()
        return menuitem

    # noinspection PyUnusedLocal
    @staticmethod
    def vm_map(lib, parent=None, callback=None):
        mmci = MainMenuContentItem()

        mmci.lines = str(lib.vm).split('\n')

        menuitem = SidebarMenuItem("VM Memory Map", mmci, parent)

        menuitem.parse_mmc()
        return menuitem

    @staticmethod
    def objc_items(lib, parent=None, callback=None):
        objc_lib = ObjCImage.from_image(lib)

        return [KToolMachOLoader.objc_headers(objc_lib, parent, callback)]

    @staticmethod
    def imports(lib, parent=None, callback=None):
        callback(f'Slice {KToolMachOLoader.CUR_SL}/{KToolMachOLoader.SL_CNT}\nProcessing Imports')
        mmci = MainMenuContentItem()

        table = Table(True)
        table.titles = ['Address', 'Symbol', 'Binding']

        for symbol in lib.imports:
            table.rows.append(
                [hex(symbol.address), symbol.fullname, symbol.attr.ljust(8)])
        mmci.lines.append(table)

        menuitem = SidebarMenuItem("Imports", mmci, parent)

        menuitem.parse_mmc()
        return menuitem

    @staticmethod
    def exports(lib, parent=None, callback=None):
        callback(f'Slice {KToolMachOLoader.CUR_SL}/{KToolMachOLoader.SL_CNT}\nProcessing Exports')
        mmci = MainMenuContentItem()

        table = Table(True)
        table.titles = ['Address', 'Symbol']

        for symbol in lib.exports:
            table.rows.append([hex(symbol.address), symbol.fullname])

        mmci.lines.append(table)

        menuitem = SidebarMenuItem("Exports", mmci, parent)

        menuitem.parse_mmc()
        return menuitem

    @staticmethod
    def get_header_item(text, name):
        mmci = MainMenuContentItem()
        formatter = Terminal256Formatter() if KToolMachOLoader.SUPPORTS_256 else TerminalFormatter()
        text = highlight(text, ObjectiveCLexer(), formatter)
        lines = text.split('\n')
        mmci.lines = lines
        h_menu_item = SidebarMenuItem(name, mmci, None)
        return h_menu_item

    @staticmethod
    def objc_headers(objc_lib, parent=None, callback=None):
        generator = HeaderGenerator(objc_lib)
        hnci = MainMenuContentItem()
        hnci.lines = generator.headers.keys()
        menuitem = SidebarMenuItem("ObjC Headers", hnci, parent)
        count = len(generator.headers.keys())
        i = 1
        callback(
            f'Slice {KToolMachOLoader.CUR_SL}/{KToolMachOLoader.SL_CNT}\nProcessing {count} ObjC Headers\nInitial Syntax Highlighting')
        futures = []
        try:
            with concurrent.futures.ProcessPoolExecutor(max_workers=THREAD_COUNT) as executor:
                for header_name, header in generator.headers.items():
                    futures.append(executor.submit(KToolMachOLoader.get_header_item, str(header.text), str(header_name)))
                i += 1
        except ImportError:
            with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_COUNT) as executor:
                for header_name, header in generator.headers.items():
                    futures.append(executor.submit(KToolMachOLoader.get_header_item, str(header.text), str(header_name)))
                i += 1
        items = [f.result() for f in futures]
        callback(
            f'Slice {KToolMachOLoader.CUR_SL}/{KToolMachOLoader.SL_CNT}\nProcessing {count} ObjC Headers\nRendering color schema')
        for item in items:
            item.parent = menuitem
            with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_COUNT) as executor:
                futures.append(executor.submit(item.parse_mmc))

        [f.result() for f in futures]
        menuitem.children = items

        menuitem.parse_mmc()
        return menuitem


# # # # #
#
# Main Screen:::
# Sets up, tears down, rebuilds, redraws, and controls the various views.
# Houses the Main run-loop.
# Performs root level exception handling
# Arbitrates Mouse/Keyboard events throughout the program.
#
# # # # #


class KToolScreen:
    def __init__(self, hard_fail=False):

        self.supports_color = False
        self.supported_colors = 0
        self.hard_fail = hard_fail
        KToolMachOLoader.HARD_FAIL = hard_fail

        self.stdscr = self.setup()

        self.root = RootBox(self.stdscr)

        self.filename = ""

        self.titlebar = TitleBar()
        self.sidebar = Sidebar()
        self.mainscreen = MainScreen()
        self.footerbar = FooterBar()
        self.debug_menu = DebugMenu()

        self.title_menu_overlay = MenuOverlayRenderingView()
        self.loader_status = LoaderStatusView()
        self.file_browser = FileSystemBrowserOverlayView()
        self.input_overlay = UserInputPrompt()

        self.is_showing_menu_overlay = False

        self.active_key_handler = self.sidebar
        self.key_handlers = []
        self.mouse_handlers = []
        self.last_mouse_event = ""

        self.render_group = [self.titlebar, self.sidebar, self.mainscreen, self.footerbar, self.title_menu_overlay,
                             self.debug_menu, self.loader_status, self.file_browser, self.input_overlay]

        self.rebuild_all()

        self.stdscr.refresh()

    def ktool_dbg_print_func(self, msg):
        self.debug_menu.scroll_view_text_buffer.lines.append(msg)

    def ktool_dbg_print_err_func(self, msg):
        self.debug_menu.scroll_view_text_buffer.lines.append('§32m' + msg + '§39m')

    def setup(self):
        """
        Perform the curses initialization ritual
        :return: curses standard screen instance.
        """
        stdscr = curses.initscr()
        # Disable keypresses being printed on screen
        curses.noecho()
        # Normally, tty only passes the keypress buffer after a line break/etc. Disable that
        curses.cbreak()
        # Tell curses to give us all the funky keypress events too
        stdscr.keypad(True)
        # *And* all the funky mouse events
        curses.mousemask(curses.ALL_MOUSE_EVENTS)

        # Initialize color rendering stuff
        curses.start_color()
        # Don't break default terminal colors/transparency unless we need to.
        curses.use_default_colors()

        # hide the cursor
        curses.curs_set(0)

        self.supports_color = curses.has_colors()
        for i in range(0, curses.COLORS):
            curses.init_pair(i + 1, i, -1)
            self.supported_colors += 1

        return stdscr

    def teardown(self):
        """
        Perform the exact opposite of the setup() task. Return terminal to normalcy.

        IT IS ABSOLUTELY CRITICAL THAT THIS GETS CALLED ON EXIT. DO ABSOLUTELY EVERYTHING POSSIBLE TO TRY AND MAKE THAT
            HAPPEN. NOT DOING SO WILL REALLY FUCK UP TERM DISPLAY.
        :return:
        """
        curses.echo()
        curses.nocbreak()
        self.stdscr.keypad(False)
        curses.mousemask(0)
        curses.curs_set(1)
        curses.endwin()

    def update_mainscreen_text(self):
        """
        Pull lines from currently selected sidebar item and copy them over into the Main Screen.

        :return:
        """
        if len(self.sidebar.processed_items) < 1:
            return

        item = self.sidebar.processed_items[self.sidebar.selected_index]
        self.mainscreen.scroll_view_text_buffer.lines = item.content.lines

        if self.mainscreen.currently_displayed_index != self.sidebar.selected_index:
            self.mainscreen.currently_displayed_index = self.sidebar.selected_index
            self.mainscreen.scroll_view_text_buffer.scrollcursor = 0
            self.mainscreen.scroll_view_text_buffer.process_lines()
        self.mainscreen.set_tab_name(item.name)

    def update_load_status(self, msg):
        self.loader_status.status_string = msg
        self.redraw_all()

    def load_file(self, filename):
        """
        Load a file by filename into the GUI.

        :param filename:
        :return:
        """
        try:
            # KToolMachOLoader.SUPPORTS_256 = self.supported_colors > 200
            self.loader_status.draw = True
            self.mainscreen.scroll_view_text_buffer.lines = [f'Loading {filename}...']
            self.redraw_all()

            fd = open(filename, 'rb')

            self.mainscreen.set_tab_name(filename)

            filename_base = os.path.basename(filename)

            self.sidebar.add_menu_item(
                SidebarMenuItem(f'{filename_base}', MainMenuContentItem(MAIN_TEXT.split('\n')), None))

            for item in KToolMachOLoader.contents_for_file(fd, self.update_load_status):
                self.sidebar.add_menu_item(item)

            self.active_key_handler = self.sidebar
            self.key_handlers = [self.sidebar, self.mainscreen, self.titlebar, self.file_browser]
            self.mouse_handlers = [self.sidebar, self.titlebar, self.title_menu_overlay, self.debug_menu,
                                   self.input_overlay]
            self.loader_status.draw = False
            self.input_overlay.draw = False

            self.redraw_all()

            self.program_loop()

        except Exception as ex:
            self.teardown()
            raise ex

    def rebuild_all(self):
        """
        Reconstruct all Views from the ground up (almost).

        This can be called on terminal resize to update the sizes of views/scroll buffers properly.

        Note: calls redraw_all() and refreshes the screen once finished.

        :return:
        """
        self.stdscr.clear()

        # curses doesn't update these values, so we do it manually here
        lines, cols = self.stdscr.getmaxyx()
        curses.LINES = lines
        curses.COLS = cols

        self.title_menu_overlay.box = Box(self.root, 0, 0, curses.COLS, curses.LINES)
        self.loader_status.box = Box(self.root, 0, 0, curses.COLS, curses.LINES)

        # Rebuild all of our contexts so they're drawn with updated screen width/height
        self.titlebar.box = Box(self.root, 0, 0, curses.COLS, 1)
        self.titlebar.exit_button.box.x = curses.COLS - 10
        self.titlebar.exit_button.box.parent = self.titlebar.box

        self.sidebar.box = Box(self.root, 0, 1, Sidebar.WIDTH, curses.LINES - 2)

        self.sidebar.scroll_view = Box(self.root, 1, 2, Sidebar.WIDTH - 2, curses.LINES - 4)
        self.sidebar.scroll_view_text_buffer = ScrollingDisplayBuffer(self.sidebar.scroll_view, 1, 0, Sidebar.WIDTH - 4,
                                                                      curses.LINES - 5)
        self.sidebar.scroll_view_text_buffer.wrap = False

        width = curses.COLS - Sidebar.WIDTH - 2
        self.mainscreen.box = Box(self.root, Sidebar.WIDTH, 1, width, curses.LINES - 2)
        self.mainscreen.info_box = Box(self.root, Sidebar.WIDTH + 1, 1, width - 1, 1)

        self.mainscreen.scroll_view = Box(self.root, Sidebar.WIDTH + 2, 3, width - 6, curses.LINES - 4)
        self.mainscreen.scroll_view_text_buffer = ScrollingDisplayBuffer(self.mainscreen.scroll_view, 1, 0, width - 8,
                                                                         curses.LINES - 5)

        self.debug_menu.box = Box(self.root, 5, 5, curses.COLS - 10, curses.LINES - 10)
        self.debug_menu.scroll_view = Box(self.root, 7, 6, curses.COLS - 12, curses.LINES - 12)

        ls = self.debug_menu.scroll_view_text_buffer.lines if self.debug_menu.scroll_view_text_buffer else []
        self.debug_menu.scroll_view_text_buffer = ScrollingDisplayBuffer(self.debug_menu.scroll_view, 0, 0,
                                                                         curses.COLS - 22, curses.LINES - 12)
        self.debug_menu.scroll_view_text_buffer.render_attr = curses.color_pair(1)
        self.debug_menu.scroll_view_text_buffer.lines = ls  # ?? We shouldn't need to do this
        self.debug_menu.parse_lines()

        self.file_browser.box = Box(self.root, 0, 0, curses.COLS, curses.LINES)
        self.file_browser.scroll_view = Box(self.root, 5, 4, curses.COLS - 10, curses.LINES - 8)
        self.file_browser.scroll_view_text_buffer = ScrollingDisplayBuffer(self.file_browser.scroll_view, 0, 0,
                                                                           curses.COLS - 10, curses.LINES - 10)
        self.file_browser.scroll_view_text_buffer.wrap = False

        self.mainscreen.currently_displayed_index = -1
        self.update_mainscreen_text()

        self.footerbar.box = Box(self.root, 0, curses.LINES - 1, curses.COLS, 1)

        self.redraw_all()

    def redraw_all(self):
        """
        Wipe the screen and have the views redraw their contents

        :return:
        """

        self.stdscr.erase()

        # Mainscreen always needs to be rendered after these two;
        # its title bar does out-of-bounds rendering over self.titlebar and the sidebar
        self.update_mainscreen_text()

        self.footerbar.debug_text = f'{curses.COLS}x{curses.LINES} | {self.sidebar.selected_index} | {self.last_mouse_event} | self.titlebar.pres_menu_item = {str(self.titlebar.pres_menu_item)} '

        self.debug_menu.lines = [f'•Sself.titlebar.pres_menu_item = {str(self.titlebar.pres_menu_item)}']

        for item in self.render_group:
            if item.draw:
                item.redraw()

        self.stdscr.refresh()

    def handle_present_menu_exception(self, yes):
        if not yes:
            self.title_menu_overlay.draw = False
            self.is_showing_menu_overlay = False
            self.titlebar.pres_menu_item_index = -1
            self.active_key_handler = self.sidebar
        else:
            self.title_menu_overlay.draw = True
            self.title_menu_overlay.active_render_menu = self.titlebar.pres_menu_item[0]
            self.title_menu_overlay.active_menu_start_x = self.titlebar.pres_menu_item[1]
            self.is_showing_menu_overlay = True
            self.active_key_handler = self.titlebar

    def handle_mouse(self, x, y):
        self.last_mouse_event = f'M: x={x}, y={y}'
        for handler in self.mouse_handlers[::-1]:
            if handler.handle_mouse(x, y):
                break

    def handle_key_press(self, c):
        """
        Handle 'important' keys, pass the rest to current active subview

        :param c:
        :return:
        """

        if not self.active_key_handler.draw:
            self.active_key_handler = self.sidebar

        if c == curses.KEY_EXIT or c == curses.KEY_BACKSPACE:
            raise ExitProgramException

        elif c == curses.KEY_RESIZE:
            # Curses passes this weird keypress whenever the window gets resized
            # So, rebuild our contexts here with the new screen size.
            raise RebuildAllException

        if c == curses.KEY_MOUSE:
            _, mx, my, _, _ = curses.getmouse()
            self.handle_mouse(mx, my)

        elif c == ord('d'):
            if self.footerbar.show_debug:
                self.footerbar.show_debug = False
            else:
                self.footerbar.show_debug = True

        # TAB
        elif c == 9:
            if self.active_key_handler == self.sidebar:
                self.active_key_handler = self.mainscreen
                self.mainscreen.highlighted = True
            else:
                self.active_key_handler = self.sidebar
                self.mainscreen.highlighted = False

        else:
            if not self.active_key_handler.handle_key_press(c):
                for handler in self.key_handlers[::-1]:
                    if handler.handle_key_press(c):
                        break

    def program_loop(self):
        """
        Main Program Loop.

        1. Get a keypress ("keypress" includes mouse events because curses)
        2. Send the keypress to the handler, which will update object models, etc.
        2.5 Handle any exceptions raised by the keypress event.
        3. Redraw all of the views to update the contents of them.

        :return:
        """
        self.rebuild_all()

        while True:
            try:
                c = self.stdscr.getch()

                self.handle_key_press(c)

                self.redraw_all()

            except FileBrowserOpenNewFileException:
                self.file_browser.draw = True
                self.handle_present_menu_exception(False)
                self.active_key_handler = self.file_browser
                self.redraw_all()

            except RebuildAllException:
                self.rebuild_all()

            except PresentTitleMenuException:
                self.handle_present_menu_exception(True)
                self.redraw_all()

            except DestroyTitleMenuException:
                self.handle_present_menu_exception(False)
                self.redraw_all()

            except PresentDebugMenuException:
                self.debug_menu.draw = True
                self.active_key_handler = self.debug_menu
                try:
                    self.redraw_all()
                except PanicException:
                    self.teardown()
                    print(PANIC_STRING)
                    exit(1)

            except ExitProgramException:
                break

            except KeyboardInterrupt:
                break

            except PanicException:
                self.teardown()
                print(PANIC_STRING)
                exit(1)

            except Exception as ex:
                self.teardown()
                raise ex

        self.teardown()


def external_hard_fault_teardown():
    """
    Call this from outside of this file wherever the Screen is being loaded from, if it catches an Exception
        (it should never do that, so something went very wrong, and we need to attempt to unfuck the terminal).

    :return:
    """
    curses.echo()
    curses.nocbreak()
    curses.mousemask(0)
    curses.curs_set(1)
    curses.endwin()
