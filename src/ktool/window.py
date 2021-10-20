#
#  ktool | ktool
#  window.py
#
#  This file houses Command Line GUI rendering code. A lot of it.
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
# TODO: Fix attributed string wrapping
#
# CURRENT FEATURE TO-DO LIST:::
# TODO: Hex View
#
# # # # #

import curses

from ktool import MachOFile, Dyld, ObjCLibrary, HeaderGenerator

VERT_LINE = '│'
WINDOW_NAME = 'ktool'

SIDEBAR_WIDTH = 40

MAIN_TEXT = """ktool ------

This is a *very* pre-release version of the GUI Tool, and it has a long ways to go. 

Stay Updated with `python3 -m pip install --upgrade k2l` !

Mouse support is a WIP; quite a few things support mouse interaction already.

Navigate the sidebar with arrow keys (use left/right to expand and collapse submenus)

Hit tab to swap between the sidebar context and main context. Scroll the main context with up/down keys.

Backspace to exit (or click the X in the top right corner).
"""

PANIC_STRING = ""


class Attribute:
    HIGHLIGHTED = curses.A_STANDOUT
    UNDERLINED = curses.A_UNDERLINE


class AttributedString:
    def __init__(self, string: str):
        self.string = string
        self.attrs = []

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


class PresentDebugMenuException(Exception):
    """Raise this within the runloop to present the debug menu
    """


class PresentTitleMenuException(Exception):
    """Raise this within the runloop to invoke or destroy the Title Bar Menu Rendering code
    """


class PanicException(Exception):
    """Raise this within the program and set the global PANIC_STRING to panic the window,
            and print the string after cleaning up the window display.
    """


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

    def write(self, x, y, string, attr):
        try:
            self.stdscr.addstr(y, x, string, attr)
        except curses.error:
            global PANIC_STRING
            PANIC_STRING = f'Rendering Error while writing {string} @ {x}, {y}\nProgram Panicked'
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
        wrapped_lines = []
        for line in self.lines:
            attrs = []
            current_buffer = line
            if isinstance(line, AttributedString):
                current_buffer = line.string
                attrs = line.attrs
            indent = False
            x_string_offset = 0
            while True:
                stacksize = self.width if not indent else self.width - 10
                if len(current_buffer) > stacksize:
                    if indent:
                        break_index = self.find_clean_breakpoint(current_buffer, self.width - 10)
                        text = current_buffer[:break_index]
                        for attr in attrs:
                            if attr[0][0] <= x_string_offset <= attr[0][1]:
                                text = AttributedString(text)
                                text.set_attr(10, len(text.string) - 10, attr[1])
                            attr[0][0] -= break_index
                            attr[0][1] -= break_index
                        current_buffer = current_buffer[break_index:]
                        if isinstance(text, AttributedString):
                            text.string = '          ' + text.string
                        else:
                            text = '          ' + text
                    else:
                        break_index = self.find_clean_breakpoint(current_buffer, self.width)
                        text = current_buffer[:break_index]
                        for attr in attrs:
                            if attr[0][0] <= x_string_offset <= attr[0][1]:
                                text = AttributedString(text)
                                text.set_attr(0, len(text.string), attr[1])
                            attr[0][0] -= break_index
                            attr[0][1] -= break_index

                        current_buffer = current_buffer[break_index:]
                    wrapped_lines.append(text)
                    indent = True
                else:
                    text = current_buffer

                    if indent:
                        if current_buffer.strip() == "":
                            break

                        for attr in attrs:
                            if attr[0][0] <= x_string_offset <= attr[0][1]:
                                text = AttributedString(text)
                                text.set_attr(10, len(text.string) - 10, attr[1])

                        if isinstance(text, AttributedString):
                            text.string = '          ' + text.string
                        else:
                            text = '          ' + text
                    else:
                        for attr in attrs:
                            if attr[0][0] <= x_string_offset <= attr[0][1]:
                                text = AttributedString(text)
                                text.set_attr(0, len(text.string), attr[1])
                    wrapped_lines.append(text)
                    break

        self.filled_line_count = len(wrapped_lines)
        self.processed_lines = wrapped_lines

    def draw_lines(self):
        """Update the internal representation of lines to be displayed.

        :return:
        """
        x = 0

        display_lines = self.rendered_lines_from(self.processed_lines, self.scrollcursor)
        for y, line in enumerate(display_lines):
            if isinstance(line, AttributedString):
                text = line.string
                for attribute in line.attrs:
                    attr_start = attribute[0][0]
                    attr_end = attribute[0][1]
                    attr = attribute[1]
                    self.box.write(x + attr_start, y, text[attr_start:attr_end], attr)
            else:
                self.box.write(x, y, line.ljust(self.width, ' '), self.render_attr)

    def rendered_lines_from(self, lines, start_line):
        """Return slice of lines based on window height

        :param lines: Full set of lines
        :param start_line: Line start
        :return: Slice of lines
        """
        end_line = start_line + self.height - 1
        return lines[start_line:end_line]


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
        self.draw = True

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
        raise ExitProgramException

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

        self.add_menu_item(FileMenuItem())
        self.add_menu_item(EditMenuItem())
        self.add_menu_item(DumpMenuItem())

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

        self.box.write(0, 0, '╒' + '═'.ljust(curses.COLS - 3, '═') + '╕', curses.A_NORMAL)
        self.box.write(2, 0, f' {WINDOW_NAME} ', curses.A_NORMAL)
        self.box.write(0, 1, '┟' + ''.ljust(curses.COLS - 3, '━') + '┦', curses.A_NORMAL)
        self.box.write(TitleBar.MENUS_START, 0, '╤', curses.A_NORMAL)
        self.box.write(TitleBar.MENUS_START, 1, '┸', curses.A_NORMAL)
        self.box.write(self.box.width - 10, 0, '═ Exit ═', curses.A_NORMAL)

        x = TitleBar.MENUS_START + 3
        for item in self.menu_items:
            self.box.write(x, 0, item.rend_text, curses.A_NORMAL)
            self.box.write(x + 1, 0, item.rend_text[1], curses.A_UNDERLINE)
            x += item.rend_width + 2

    def handle_mouse(self, x, y):
        handle = False

        if y < 1:
            handle = True
            if -1 <= x - self.box.width + 5 <= 1:
                raise ExitProgramException

            if x < 10:
                raise PresentDebugMenuException

            for item, coords in self.menu_item_xy_map.items():
                if coords[0] <= x <= coords[0] + item.rend_width:
                    self.pres_menu_item = (item, coords[0])
                    raise PresentTitleMenuException

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

    def redraw(self):
        self.box.write(0, 0, '╘' + '═'.ljust(curses.COLS - 3, '═') + '╛', curses.A_NORMAL)
        self.box.write(FooterBar.MENUS_START, 0, '╧', curses.A_NORMAL)

        if self.show_debug:
            self.box.write(self.box.width - len(self.debug_text) - 5, 0, self.debug_text, curses.A_NORMAL)


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

    @staticmethod
    def item_list_with_children(menu_item, depth=1):
        """
        Recursive function that returns a single, non-nested, ordered list of items and their children for display.

        :param depth:
        :param menu_item: Root item to recurse through children of.
        :return: List of items generated
        """
        # TODO: Implement Sidebar Indents Here! -depth func arg = 0
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
            self.box.write(0, index, VERT_LINE, curses.A_NORMAL)
            self.box.write(Sidebar.WIDTH, index, VERT_LINE, curses.A_NORMAL)
        self.box.write(SIDEBAR_WIDTH, 0, '┰', curses.A_NORMAL)

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
            self.box.write(width, index, VERT_LINE, curses.A_NORMAL)

        # Redraw the text
        self.scroll_view_text_buffer.draw_lines()

        width = curses.COLS - Sidebar.WIDTH - 3
        # Clear and Redraw the Info Box bar
        self.info_box.write(-1, 1, '╞' + ''.ljust(width, '═') + '╡', curses.A_NORMAL)
        self.info_box.write(2, 1, f'╡ {self.tabname.strip()} ╞',
                            curses.A_NORMAL if not self.highlighted else curses.A_STANDOUT)

    def handle_key_press(self, key):
        if key == curses.KEY_UP:
            self.scroll_view_text_buffer.scrollcursor = max(0, self.scroll_view_text_buffer.scrollcursor - 1)
        elif key == curses.KEY_DOWN:
            self.scroll_view_text_buffer.scrollcursor = min(
                self.scroll_view_text_buffer.filled_line_count - self.scroll_view_text_buffer.height + 1,
                self.scroll_view_text_buffer.scrollcursor + 1)

        self.scroll_view_text_buffer.draw_lines()


class DebugMenu(ScrollView):
    def __init__(self):
        super().__init__()
        self.draw = False

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
        width = 20
        height = len(self.active_render_menu.menu_items) + 2

        self.active_render_subbox = Box(None, start[0], start[1], width, height)

        for line in range(start[1], start[1] + height):
            self.box.write(start[0], line, ' ' * width, curses.color_pair(1))

        for linen, item in enumerate([i[0] for i in self.active_render_menu.menu_items]):
            self.box.write(start[0] + 1, start[1] + 1 + linen, f'{item}', curses.color_pair(1))

    def handle_mouse(self, x, y):
        if not self.draw or not self.active_render_menu:
            return False

        if self.active_render_subbox.is_click_inbounds(x, y):
            # x = x - self.active_render_subbox.x
            y = y - self.active_render_subbox.y - 1
            if y < 0:
                return False
            if y > len(self.active_render_menu.menu_items):
                raise PresentTitleMenuException
            if y == len(self.active_render_menu.menu_items):
                return False
            item_tup = self.active_render_menu.menu_items[y]
            item_tup[1]()
            return True

        raise PresentTitleMenuException


# # # # #
#
# File Loaders:::
# Handles creating Sidebar and MainMenuContent items for a given file
#
# # # # #


class KToolMachOLoader:

    @staticmethod
    def parent_count(item):
        count = 0
        item = item
        while item.parent is not None:
            count += 1
            item = item.parent
        return count

    @staticmethod
    def contents_for_file(fd):
        machofile = MachOFile(fd)
        items = []
        for macho_slice in machofile.slices:
            items.append(KToolMachOLoader.slice_item(macho_slice))
        return items

    @staticmethod
    def slice_item(macho_slice):
        loaded_library = Dyld.load(macho_slice)
        if hasattr(macho_slice, 'type'):
            slice_nick = macho_slice.type.name + " Slice"
        else:
            slice_nick = "Thin MachO"
        slice_item = SidebarMenuItem(f'{slice_nick}', None, None)
        slice_item.content = KToolMachOLoader._file(loaded_library, slice_item).content
        slice_item.children = [KToolMachOLoader.linked(loaded_library, slice_item),
                               KToolMachOLoader.symtab(loaded_library, slice_item),
                               KToolMachOLoader.binding_items(loaded_library, slice_item),
                               KToolMachOLoader.vm_map(loaded_library, slice_item),
                               KToolMachOLoader.load_cmds(loaded_library, slice_item)]
        slice_item.children += KToolMachOLoader.objc_items(loaded_library, slice_item)
        slice_item.show_children = True
        return slice_item

    @staticmethod
    def _file(lib, parent=None):
        file_content_item = MainMenuContentItem()

        file_content_item.lines.append(f'Name: {lib.name}')
        file_content_item.lines.append(f'Filetype: {lib.macho_header.filetype.name}')
        file_content_item.lines.append(f'Flags: {", ".join([i.name for i in lib.macho_header.flags])}')
        file_content_item.lines.append(f'UUID: {lib.uuid.hex().upper()}')
        file_content_item.lines.append(f'Platform: {lib.platform.name}')
        file_content_item.lines.append(f'Minimum OS: {lib.minos.x}.{lib.minos.y}.{lib.minos.z}')
        file_content_item.lines.append(f'SDK Version: {lib.sdk_version.x}.{lib.sdk_version.y}.{lib.sdk_version.z}')

        menuitem = SidebarMenuItem("File Info", file_content_item, parent)

        return menuitem

    @staticmethod
    def linked(lib, parent=None):
        linked_libs_item = MainMenuContentItem()
        for exlib in lib.linked:
            linked_libs_item.lines.append('(Weak) ' + exlib.install_name if exlib.weak else '' + exlib.install_name)

        menuitem = SidebarMenuItem("Linked Libraries", linked_libs_item, parent)
        return menuitem

    @staticmethod
    def load_cmds(lib, parent=None):
        load_cmds = MainMenuContentItem()

        lines = [f'Load Command Count: {len(lib.macho_header.load_commands)}']

        load_cmds.lines = lines

        menuitem = SidebarMenuItem("Load Commands", load_cmds, parent)

        for cmd in lib.macho_header.load_commands:
            mmci = MainMenuContentItem()
            mmci.lines = cmd.desc(lib).split('\n')
            lc_menu_item = SidebarMenuItem(str(cmd), mmci, menuitem)
            menuitem.children.append(lc_menu_item)

        return menuitem

    @staticmethod
    def symtab(lib, parent=None):
        mmci = MainMenuContentItem()

        for sym in lib.symbol_table.table:
            mmci.lines.append(f' Name: {sym.fullname} | Address: {hex(sym.addr)} ')

        menuitem = SidebarMenuItem("Symbol Table", mmci, parent)

        return menuitem

    @staticmethod
    def vm_map(lib, parent=None):
        mmci = MainMenuContentItem()

        mmci.lines = str(lib.vm).split('\n')

        menuitem = SidebarMenuItem("VM Memory Map", mmci, parent)

        return menuitem

    @staticmethod
    def objc_items(lib, parent=None):
        objc_lib = ObjCLibrary(lib)

        return [KToolMachOLoader.objc_headers(objc_lib, parent)]

    @staticmethod
    def binding_items(lib, parent=None):

        mmci = MainMenuContentItem()

        for sym in lib.binding_table.symbol_table:
            try:
                mmci.lines.append(
                    f'{sym.name.ljust(20, " ")} | {hex(sym.addr).ljust(15, " ")} | {lib.linked[int(sym.ordinal) - 1].install_name} | | {sym.type}')
            except AttributeError:
                pass

        menuitem = SidebarMenuItem("Binding Info", mmci, parent)

        return menuitem

    @staticmethod
    def objc_headers(objc_lib, parent=None):
        generator = HeaderGenerator(objc_lib)
        hnci = MainMenuContentItem
        hnci.lines = generator.headers.keys()
        menuitem = SidebarMenuItem("ObjC Headers", hnci, parent)

        for header_name, header in generator.headers.items():
            mmci = MainMenuContentItem()
            mmci.lines = header.text.split('\n')
            h_menu_item = SidebarMenuItem(header_name, mmci, menuitem)
            menuitem.children.append(h_menu_item)

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
    def __init__(self):

        self.supports_color = False

        self.stdscr = self.setup()

        self.root = RootBox(self.stdscr)

        self.filename = ""

        self.titlebar = TitleBar()
        self.sidebar = Sidebar()
        self.mainscreen = MainScreen()
        self.footerbar = FooterBar()
        self.debug_menu = DebugMenu()

        self.title_menu_overlay = MenuOverlayRenderingView()
        self.is_showing_menu_overlay = False

        self.active_key_handler = self.sidebar
        self.key_handlers = []
        self.mouse_handlers = []
        self.last_mouse_event = ""

        self.render_group = [self.titlebar, self.sidebar, self.mainscreen, self.footerbar, self.title_menu_overlay,
                             self.debug_menu]

        self.rebuild_all()

        self.stdscr.refresh()

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
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)

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

    def load_file(self, filename):
        """
        Load a file by filename into the GUI.

        :param filename:
        :return:
        """
        try:
            self.mainscreen.scroll_view_text_buffer.lines = [f'Loading {filename}...']
            self.redraw_all()

            fd = open(filename, 'rb')

            self.mainscreen.set_tab_name(filename)

            self.sidebar.add_menu_item(SidebarMenuItem(f'{filename}', MainMenuContentItem(MAIN_TEXT.split('\n')), None))

            for item in KToolMachOLoader.contents_for_file(fd):
                self.sidebar.add_menu_item(item)

            self.active_key_handler = self.sidebar
            self.key_handlers = [self.sidebar, self.mainscreen]
            self.mouse_handlers = [self.sidebar, self.titlebar, self.title_menu_overlay, self.debug_menu]

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

        # Rebuild all of our contexts so they're drawn with updated screen width/height
        self.titlebar.box = Box(self.root, 0, 0, curses.COLS, 1)

        self.sidebar.box = Box(self.root, 0, 1, Sidebar.WIDTH, curses.LINES - 2)

        self.sidebar.scroll_view = Box(self.root, 1, 2, Sidebar.WIDTH - 2, curses.LINES - 4)
        self.sidebar.scroll_view_text_buffer = ScrollingDisplayBuffer(self.sidebar.scroll_view, 1, 0, Sidebar.WIDTH - 5,
                                                                      curses.LINES - 5)

        width = curses.COLS - Sidebar.WIDTH - 2
        self.mainscreen.box = Box(self.root, Sidebar.WIDTH, 1, width, curses.LINES - 2)
        self.mainscreen.info_box = Box(self.root, Sidebar.WIDTH + 1, 1, width - 1, 1)

        self.mainscreen.scroll_view = Box(self.root, Sidebar.WIDTH + 2, 3, width - 6, curses.LINES - 4)
        self.mainscreen.scroll_view_text_buffer = ScrollingDisplayBuffer(self.mainscreen.scroll_view, 1, 0, width - 8,
                                                                         curses.LINES - 5)

        self.debug_menu.box = Box(self.root, 5, 5, curses.COLS - 10, curses.LINES - 10)
        self.debug_menu.scroll_view = Box(self.root, 6, 6, curses.COLS - 12, curses.LINES - 12)
        self.debug_menu.scroll_view_text_buffer = ScrollingDisplayBuffer(self.debug_menu.scroll_view, 0, 0,
                                                                         curses.COLS - 22, curses.LINES - 12)
        self.debug_menu.scroll_view_text_buffer.render_attr = curses.color_pair(1)

        self.mainscreen.tabname = ""
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

    def handle_present_menu_exception(self):
        if self.is_showing_menu_overlay:
            self.title_menu_overlay.draw = False
            self.is_showing_menu_overlay = False
        else:
            self.title_menu_overlay.draw = True
            self.title_menu_overlay.active_render_menu = self.titlebar.pres_menu_item[0]
            self.title_menu_overlay.active_menu_start_x = self.titlebar.pres_menu_item[1]
            self.is_showing_menu_overlay = True

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
        if c == curses.KEY_EXIT or c == curses.KEY_BACKSPACE:
            raise ExitProgramException

        elif c == curses.KEY_RESIZE:
            # Curses passes this weird keypress whenever the window gets resized
            # So, rebuild our contexts here with the new screen size.
            self.rebuild_all()
            return

        if c == curses.KEY_MOUSE:
            _, mx, my, _, _ = curses.getmouse()
            self.handle_mouse(mx, my)

        # TAB
        elif c == 9:
            if self.active_key_handler == self.sidebar:
                self.active_key_handler = self.mainscreen
                self.mainscreen.highlighted = True
            else:
                self.active_key_handler = self.sidebar
                self.mainscreen.highlighted = False

        else:
            self.active_key_handler.handle_key_press(c)

    def program_loop(self):
        """
        Main Program Loop.

        1. Get a keypress ("keypress" includes mouse events because curses)
        2. Send the keypress to the handler, which will update object models, etc.
        3. Redraw all of the views to update the contents of them.

        :return:
        """
        self.rebuild_all()

        while True:
            try:
                c = self.stdscr.getch()

                self.handle_key_press(c)

                self.redraw_all()

            except PresentTitleMenuException:
                self.handle_present_menu_exception()
                self.redraw_all()

            except PresentDebugMenuException:
                self.debug_menu.draw = True
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
