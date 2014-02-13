#!/usr/bin/env python

# Copyright (C) 2006-2007, Eduardo Silva <edsiper@gmail.com>,2008 Jameson Quinn
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA


import os
import os.path
import logging
from gettext import gettext as _

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import Gio
from gi.repository import GObject

from sugar3.graphics import style
from sugar3 import env


def _get_filename_from_path(path):
    return os.path.split(path)[-1]


class LogFilesViewer(Gtk.ScrolledWindow):
    __gtype_name__ = 'LogFileViewer'

    __gsignals__ = {
        'file-selected': (GObject.SignalFlags.RUN_FIRST,
                          None,
                          ([str])),
    }

    def __init__(self, namefilter):

        self._openlogs = []

        logging.info('creating LogFilesViewer namefilter %s', namefilter)
        self._path = env.get_logs_path()
        logging.error('LOGS PATH %s', self._path)

        self._extra_files = [os.path.join(self._path, 'shell.log')]
        self._namefilter = namefilter

        Gtk.ScrolledWindow.__init__(self)

        self.props.hscrollbar_policy = Gtk.PolicyType.AUTOMATIC
        self.props.vscrollbar_policy = Gtk.PolicyType.AUTOMATIC
        self.set_size_request(style.GRID_CELL_SIZE * 3, -1)

        self._tree_view = Gtk.TreeView()
        self._tree_view.connect('cursor-changed', self.__cursor_changed_cb)
        self.add(self._tree_view)
        self._tree_view.show()

        self._tree_view.props.headers_visible = False
        selection = self._tree_view.get_selection()
        selection.connect('changed', self.__selection_changed_cb)

        cell = Gtk.CellRendererText()
        self._column = Gtk.TreeViewColumn()
        self._column.pack_start(cell, True)
        self._column.add_attribute(cell, 'text', 0)
        self._tree_view.append_column(self._column)
        self._tree_view.set_search_column(0)

        # Configuration
        self.set_title(_("Sugar logs"))
        self.init_logs(self._filter_by_name)
        self._monitors = []

        self._configure_watcher()

    def _configure_watcher(self):
        logging.error('Monitor directory %s', self._path)
        directory = Gio.File.new_for_path(self._path)
        dir_monitor = directory.monitor_directory(
            flags=Gio.FileMonitorFlags.NONE, cancellable=None)
        dir_monitor.set_rate_limit(2000)
        dir_monitor.connect('changed', self._log_file_changed_cb)
        self._monitors.append(dir_monitor)
        for f in self._extra_files:
            logging.error('Monitor file %s', f)
            gio_file = Gio.File.new_for_path(f)
            file_monitor = gio_file.monitor_file(
                Gio.FileMonitorFlags.NONE, None)
            file_monitor.set_rate_limit(2000)
            file_monitor.connect('changed', self._log_file_changed_cb)
            self._monitors.append(file_monitor)

    def _log_file_changed_cb(self, monitor, path1, path2, event):
        if event == Gio.FileMonitorEvent.CHANGED:
            for log in self._openlogs:
                if path1.get_path() == log.full_path:
                    logging.debug('updating logfile %s', path1.get_path())
                    log.update()
        elif (event == Gio.FileMonitorEvent.DELETED
                or event == Gio.FileMonitorEvent.CREATED):
            self.load_model()

    def _filter_by_name(self, filename):
        return self._namefilter in filename or filename in self._extra_files

    def init_logs(self, filter_function):
        self._filter_function = filter_function
        self.load_model()

    def load_model(self):
        self._tree_view.set_model(Gtk.TreeStore(str, str))
        self._model = self._tree_view.get_model()
        self._add_dir_to_model(self._path, self._filter_function)

    def _add_dir_to_model(self, dir_path, filter_function, parent=None):
        for f in os.listdir(dir_path):
            full_path = os.path.join(dir_path, f)
            if os.path.isdir(full_path):
                new_iter = self._model.append(parent, [f, full_path])
                self._add_dir_to_model(full_path, filter_function, new_iter)
            else:
                if filter_function(full_path):
                    self._model.append(parent, [f, full_path])

    def __selection_changed_cb(self, selection):
        model, tree_iter = selection.get_selected()
        if tree_iter is None:
            file_path = None
        else:
            file_path = model.get_value(tree_iter, 1)
        self.emit('file-selected', file_path)

    def __cursor_changed_cb(self, treeview):
        selection = treeview.get_selection()
        store, iter_ = selection.get_selected()
        if iter_ is None:
            # Nothing selected. This happens at startup
            return
        if store.iter_has_child(iter_):
            path = store.get_path(iter_)
            if treeview.row_expanded(path):
                treeview.collapse_row(path)
            else:
                treeview.expand_row(path, False)

    def set_title(self, title):
        self._column.set_title(title)

    def remove_logview(self, logview):
        try:
            self._openlogs.remove(logview)
        except ValueError:
            logging.debug("_remove_logview failed")


class LogBuffer(Gtk.TextBuffer):

    def __init__(self, logfile):
        Gtk.TextBuffer.__init__(self)

        self._logfile = logfile
        self._pos = 0
        self.update()

    def update(self):
        try:
            f = open(self._logfile, 'r')
            init_pos = self._pos

            f.seek(self._pos)
            self.insert(self.get_end_iter(), f.read())
            self._pos = f.tell()
            f.close()

            self._written = (self._pos - init_pos)
        except:
            self.insert(self.get_end_iter(),
                        "Console error: can't open the file\n")
            self._written = 0


class LogView(Gtk.TextView):

    def __init__(self, full_path, log_file_viewer):
        GObject.GObject.__init__(self)

        self._log_file_viewer = log_file_viewer
        self.full_path = full_path
        self._log_file_viewer._openlogs.append(self)

        self.set_wrap_mode(Gtk.WrapMode.WORD)

        newbuffer = self._create_log_buffer(full_path)
        if newbuffer:
            self.set_buffer(newbuffer)
            self.text_buffer = newbuffer

        # Set background color
        bgcolor = Gdk.color_parse("#EEEEEE")
        self.modify_base(Gtk.StateType.NORMAL, bgcolor)

        self.set_editable(False)

        self.show()

    def remove(self):
        self._log_file_viewer.remove_logview(self)

    def _create_log_buffer(self, path):
        self._written = False
        if os.path.isdir(path):
            return False

        if not os.path.exists(path):
            logging.error("_create_log_buffer: %s don't exists", path)
            return False

        if not os.access(path, os.R_OK):
            logging.error("_create_log_buffer: I can't read '%s' file", path)
            return False

        self.filename = _get_filename_from_path(path)

        self._logbuffer = LogBuffer(path)

        # Tags for search
        tagtable = self._logbuffer.get_tag_table()
        hilite_tag = Gtk.TextTag.new('search-hilite')
        hilite_tag.props.background = '#FFFFB0'
        tagtable.add(hilite_tag)
        select_tag = Gtk.TextTag.new('search-select')
        select_tag.props.background = '#B0B0FF'
        tagtable.add(select_tag)

        self._written = self._logbuffer._written

        return self._logbuffer

    def replace(self, *args, **kw):
        return (False, False)

    def update(self):
        self._logbuffer.update()

    def set_search_text(self, text):
        self.search_text = text

        _buffer = self.get_buffer()

        start, end = _buffer.get_bounds()
        _buffer.remove_tag_by_name('search-hilite', start, end)
        _buffer.remove_tag_by_name('search-select', start, end)

        text_iter = _buffer.get_start_iter()
        while True:
            next_found = text_iter.forward_search(
                text, Gtk.TextSearchFlags.CASE_INSENSITIVE, None)
            if next_found is None:
                break
            start, end = next_found
            _buffer.apply_tag_by_name('search-hilite', start, end)
            text_iter = end

        if self.get_next_result('current'):
            self.search_next('current')
        elif self.get_next_result('backward'):
            self.search_next('backward')

        return True

    def get_next_result(self, direction):
        _buffer = self.get_buffer()
        if direction == 'current':
            text_iter = _buffer.get_iter_at_mark(_buffer.get_insert())
        elif direction == 'forward':
            text_iter = _buffer.get_iter_at_mark(_buffer.get_insert())
            text_iter.forward_char()
        else:
            text_iter = _buffer.get_iter_at_mark(_buffer.get_insert())

        if direction == 'backward':
            return text_iter.backward_search(
                self.search_text, Gtk.TextSearchFlags.CASE_INSENSITIVE, None)
        else:
            return text_iter.forward_search(
                self.search_text, Gtk.TextSearchFlags.CASE_INSENSITIVE, None)

    def search_next(self, direction):
        next_found = self.get_next_result(direction)
        if next_found:
            _buffer = self.get_buffer()

            start, end = _buffer.get_bounds()
            _buffer.remove_tag_by_name('search-select', start, end)
            start, end = next_found
            _buffer.apply_tag_by_name('search-select', start, end)
            _buffer.place_cursor(start)

            self.scroll_to_iter(start, 0.1, False, 0, 0)
