#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2006, Red Hat, Inc.
# Copyright (C) 2011, One Laptop Per Child
# Copyright (C) 2009, Tomeu Vizoso, Simon Schampijer
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#,
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
from gi.repository import Gtk, Gdk
from gi.repository import GObject
from gettext import gettext as _

from sugar3.activity.widgets import EditToolbar
from sugar3.graphics import iconentry
from sugar3.graphics.toolbutton import ToolButton

import sourceview_editor
S_WHERE = sourceview_editor.S_WHERE
SEARCH_ICONS = {False: {S_WHERE.selection: "search-in-selection",
                        S_WHERE.file: "system-search",
                        S_WHERE.multifile: "multi-search",
                        },
                True: {S_WHERE.selection: "regex-in-selection",
                       S_WHERE.file: "regex",
                       S_WHERE.multifile: "multi-regex",
                       }}
from sourceview_editor import FONT_CHANGE_STEP, DEFAULT_FONT_SIZE


class DevelopViewToolbar(Gtk.Toolbar):
    __gsignals__ = {
        'theme-changed': (GObject.SIGNAL_RUN_FIRST, None,
                         (str,)),
        'font-size-changed': (GObject.SIGNAL_RUN_FIRST, None,
                             (int,)),
    }

    def __init__(self, _activity):
        GObject.GObject.__init__(self)

        self._activity = _activity
        self.theme_state = "light"
        self.font_size = DEFAULT_FONT_SIZE

        self.theme_toggler = ToolButton('dark-theme')
        self.theme_toggler.connect('clicked', self._toggled_theme)
        self.theme_toggler.set_tooltip('Switch to Dark Theme')
        self.insert(self.theme_toggler, -1)
        self.theme_toggler.show()

        sep = Gtk.SeparatorToolItem()
        self.insert(sep, -1)
        sep.show()

        self.font_plus = ToolButton('gtk-add')
        self.font_plus.connect('clicked', self._font_size_increase)
        self.font_plus.set_tooltip('Increase Font Size')
        self.insert(self.font_plus, -1)
        self.font_plus.show()

        self.font_minus = ToolButton('gtk-remove')
        self.font_minus.connect('clicked', self._font_size_decrease)
        self.font_minus.set_tooltip('Decrease Font Size')
        self.insert(self.font_minus, -1)
        self.font_minus.show()

        self.show()

    def _font_size_increase(self, button):
        self.font_size += FONT_CHANGE_STEP
        self.emit('font-size-changed', self.font_size)

    def _font_size_decrease(self, button):
        self.font_size -= FONT_CHANGE_STEP
        self.emit('font-size-changed', self.font_size)

    def _toggled_theme(self, button):
        if self.theme_state == "dark":
            self.theme_state = "light"
            self.theme_toggler.set_icon_name('dark-theme')
            self.theme_toggler.set_tooltip('Switch to Dark Theme')
        elif self.theme_state == "light":
            self.theme_state = "dark"
            self.theme_toggler.set_icon_name('light-theme')
            self.theme_toggler.set_tooltip('Switch to Light Theme')

        self.emit('theme-changed', self.theme_state)


class DevelopEditToolbar(EditToolbar):

    def __init__(self, _activity):
        EditToolbar.__init__(self)

        self._activity = _activity
        self._activity.editor.connect('changed', self._changed_cb)
        self._changed_cb(None)

        self.undo.connect('clicked', self._undo_cb)
        self.redo.connect('clicked', self._redo_cb)
        self.copy.connect('clicked', self._copy_cb)
        self.paste.connect('clicked', self._paste_cb)

    def _changed_cb(self, _buffer):
        can_undo, can_redo = self._activity.editor.can_undo_redo()
        self.undo.set_sensitive(can_undo)
        self.redo.set_sensitive(can_redo)

    def _undo_cb(self, button):
        self._activity.editor.undo()
        self._changed_cb(None)

    def _redo_cb(self, button):
        self._activity.editor.redo()
        self._changed_cb(None)

    def _copy_cb(self, button):
        self._activity.editor.copy()

    def _paste_cb(self, button):
        self._activity.editor.paste()


class SearchOptions:

    def __init__(self, template=None, **kw):
        if template:
            self.__dict__ = template.__dict__.copy()
        else:
            self.__dict__ = {}
        self.__dict__.update(kw)


class DevelopSearchToolbar(Gtk.Toolbar):

    def __init__(self, _activity):
        GObject.GObject.__init__(self)

        self._activity = _activity

        # setup the search options
        self.s_opts = SearchOptions(
            where=S_WHERE.multifile,
            use_regex=False,
            ignore_caps=True,
            replace_all=False,
            #defaults to avoid creating
            #a new SearchOptions object for normal searches
            #should never be changed, just make a copy like:
            #SearchOptions(self.s_opts, forward=False)
            forward=True,
            stay=False)

        self.safe_to_replace = False

        self._search_entry = iconentry.IconEntry()
        self._search_entry.set_icon_from_name(
            iconentry.ICON_ENTRY_PRIMARY,
            SEARCH_ICONS[self.s_opts.use_regex][self.s_opts.where])

        self._search_entry.add_clear_button()
        self._search_entry.connect('activate', self._search_entry_activated_cb)
        self._search_entry.connect('changed', self._search_entry_changed_cb)
        self._add_widget(self._search_entry, expand=True)

        self._findprev = ToolButton('go-previous')
        self._findprev.set_tooltip(_('Find previous'))
        self.insert(self._findprev, -1)
        self._findprev.show()
        self._findprev.connect('clicked', self._findprev_cb)

        self._findnext = ToolButton('go-next')
        self._findnext.set_tooltip(_('Find next'))
        self.insert(self._findnext, -1)
        self._findnext.show()
        self._findnext.connect('clicked', self._findnext_cb)

        """
        self._settings = ToolButton(CAP_ICONS[self.s_opts.ignore_caps])
        self._settings.set_tooltip(_('Search settings'))
        self.insert(self._settings, -1)
        self._settings.show()
        self._settings.connect('clicked', self._settings_cb)

        # Search settings menu
        # This menu should attach to something else beside findnext -
        #location is temporary.
        palette = self._settings.get_palette()
        sswo = self._set_where_options
        ssho = self._set_how_options
        ssco = self._set_cap_options
        #TODO: move data structure to a member and the logic to a function
        for name, function, options, icon in (
                (_('Ignore capitalization'), ssco, True, "ignore-caps"),
                (_('Match capitalization'), ssco, False, "use-caps"),
                (None, None, None, None),
                (_('Search in selection'), sswo, S_WHERE.selection,
                    "search-in-selection"),
                (_('Search in current file'), sswo, S_WHERE.file,
                    "system-search"),
                (_('Search in all open files'), sswo, S_WHERE.multifile,
                    "multi-search"),
                (None, None, None, None),
                (_('Simple search'), ssho, False, "system-search"),
                (_('Advanced search'), ssho, True, "regex"),
                ):
            if not name:
                menuitem = Gtk.SeparatorMenuItem()
            else:
                menuitem = MenuItem(name, icon)
                menuitem.connect('activate', function, options)
            palette.menu.append(menuitem)
            menuitem.show()

        # make expanded non-drawn visible separator to make the replace
        #stuff right-align
        separator = Gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        self.insert(separator, -1)
        separator.show()

        # replace entry
        self._replace_entry = iconentry.IconEntry()
        self._replace_entry.set_icon_from_name(iconentry.ICON_ENTRY_PRIMARY,
                                              'system-replace')
        self._replace_entry.connect('changed', self._replace_entry_changed_cb)
        self._replace_entry.add_clear_button()
        self._add_widget(self._replace_entry, expand=True)

        #replace button
        self._replace_button = ToolButton(REPLACE_ICONS[
                                                self.s_opts.replace_all])
        self._replace_button.set_tooltip(_('Replace'))
        self.insert(self._replace_button, -1)
        self._replace_button.show()
        self._replace_button.connect('clicked', self._replace_cb)

        palette = self._replace_button.get_palette()
        ssro = self._set_replace_options
        #TODO: move data structure to a member and the logic to a function
        for name, function, options, icon in (
                (_('Replace one'), ssro, False, "replace-and-find"),
                (_('Replace all'), ssro, True, "multi-replace"),
                ):
            if not name:
                menuitem = Gtk.SeparatorMenuItem()
            else:
                menuitem = MenuItem(name, icon)
                menuitem.connect('activate', function, options)
            palette.menu.append(menuitem)
            menuitem.show()
        """

        self._activity.editor.connect('changed', self._changed_cb)

        self._activity.connect('key_press_event', self._on_key_press_event)

    def _on_key_press_event(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        if "F5" <= keyname and keyname <= "F8":
            if keyname == "F5":
                self._go_to_search_entry_cb()
            elif keyname == "F6":
                self._findprev_cb()
            elif keyname == "F7":
                self._findnext_cb()
            elif keyname == "F8":
                self._replace_or_go_to_replace_entry_cb()
            return True

    def _go_to_search_entry_cb(self):
        entry = self._search_entry
        text = self._activity.editor.get_selected()
        entry.grab_focus()
        if text:
            entry.delete_text(0, -1)
            entry.insert_text(text)
            entry.select_region(0, -1)
        else:
            entry.delete_text(0, 0)
            entry.set_position(-1)
            #for some reason, grab_focus doesn't work otherwise

    def _replace_or_go_to_replace_entry_cb(self):
        if self.safe_to_replace:
            self._replace_cb()
        else:
            self._replace_entry.select_region(0, -1)
            self._replace_entry.grab_focus()

    def _reset_search_icons(self):
        self._search_entry.set_icon_from_name(
            iconentry.ICON_ENTRY_PRIMARY,
            SEARCH_ICONS[self.s_opts.use_regex][self.s_opts.where])
        #self._settings.set_icon(CAP_ICONS[self.s_opts.ignore_caps])
        #self._replace_button.set_icon(REPLACE_ICONS[self.s_opts.replace_all])
        self._reset_replace_sensitivity()

    def _reset_replace_sensitivity(self):
        pass
        """
        self._replace_button.set_sensitive(
            self.s_opts.where == S_WHERE.selection or self.s_opts.replace_all)
        """

    def _set_where_options(self, menu, option):
        self.s_opts.where = option  # IGNORE:W0201
        self._reset_search_icons()

    def _set_how_options(self, menu, option):
        self.s_opts.use_regex = option  # IGNORE:W0201
        self._reset_search_icons()

    def _set_cap_options(self, menu, option):
        self.s_opts.ignore_caps = option  # IGNORE:W0201
        self._reset_search_icons()

    def _set_replace_options(self, menu, option):
        self.s_opts.replace_all = option  # IGNORE:W0201
        if option and self.s_opts.where == S_WHERE.multifile:
            self.s_opts.where = S_WHERE.file  # for safety:
            #do not replace all in multifile except explicitly
        self._reset_search_icons()

    def _changed_cb(self, _buffer):
        self._reset_replace_sensitivity()
        #if self.s_opts.where == S_WHERE.selection:
        #    self._set_where_options(None, S_WHERE.file)

    def _settings_cb(self, button):
        self._set_cap_options(None, not self.s_opts.ignore_caps)

    def _replace_cb(self, button=None):
        pass
        """
        ftext = self._search_entry.props.text
        rtext = self._replace_entry.props.text
        __replaced, found = self._activity.editor.replace(ftext, rtext,
                                                          self.s_opts)
        if found:
            self._replace_button.set_sensitive(True)
        """

    def _search_entry_activated_cb(self, entry):
        text = self._search_entry.props.text
        if text:
            self._findnext_cb(None)

    def _search_entry_changed_cb(self, entry):
        self.safe_to_replace = False
        text = self._search_entry.props.text
        if not text:
            self._findprev.set_sensitive(False)
            self._findnext.set_sensitive(False)
        else:
            self._findprev.set_sensitive(True)
            self._findnext.set_sensitive(True)
            if not self.s_opts.use_regex:
                #do not do partial searches for regex
                if self._activity.editor.find_next(text):
                    #no multifile, or focus gets grabbed
                    pass
                    #self._replace_button.set_sensitive(True)

    def _replace_entry_changed_cb(self, entry):
        if self._replace_entry.props.text:
            self.safe_to_replace = True

    def _findprev_cb(self, button=None):
        ftext = self._search_entry.props.text
        if ftext:
            if self._activity.editor.find_next(ftext, direction='backward'):
                pass
                #self._replace_button.set_sensitive(True)

    def _findnext_cb(self, button=None):
        ftext = self._search_entry.props.text
        if ftext:
            if self._activity.editor.find_next(ftext, direction='forward'):
                pass
                #self._replace_button.set_sensitive(True)

    # bad paul! this function was copied from sugar's activity.py via Write
    def _add_widget(self, widget, expand=False):
        tool_item = Gtk.ToolItem()
        tool_item.set_expand(expand)

        tool_item.add(widget)
        widget.show()

        self.insert(tool_item, -1)
        tool_item.show()
