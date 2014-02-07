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

import gtk
import gio

import activity_model
from sourceview_editor import TabLabel

#does not import develop_app, but references internals from the activity,
# as passed to init.
#In other words, needs refactoring.


def _get_filename_from_path(path):
    return os.path.split(path)[-1]


class LogMinder(gtk.VBox):
    def __init__(self, activity, namefilter, path=None, extra_files=None):
        self.activity = activity
        self._openlogs = []

        logging.info('creating MultiLogView')
        if not path:
            # Main path to watch: ~/.sugar/someuser/logs...
            path = os.path.join(os.path.expanduser("~"), ".sugar", "default",
                                "logs")

        if not extra_files:
            # extra files to watch in logviewer
            extra_files = []
            extra_files.append("/var/log/Xorg.0.log")
            extra_files.append("/var/log/syslog")
            extra_files.append("/var/log/messages")

        self._logs_path = path + '/'
        self._active_log = None
        self._extra_files = extra_files
        self._namefilter = namefilter

        # Creating Main treeview with Actitivities list
        self._tv_menu = gtk.TreeView()
        self._tv_menu.connect('cursor-changed', self._load_log)
        self._tv_menu.set_rules_hint(True)
        cellrenderer = gtk.CellRendererText()
        self.treecolumn = gtk.TreeViewColumn(_("Sugar logs"), cellrenderer,
                                             text=1)
        self._tv_menu.append_column(self.treecolumn)
        self._tv_menu.set_size_request(220, 900)

        # Create scrollbars around the tree view.
        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled.add(self._tv_menu)

        # the internals of the treeview
        self._model = activity_model.DirectoryAndExtraModel(
            path, extra_files, self._filter_by_name)

        self._tv_menu.set_model(self._model)

        self._logs = {}
        self._monitors = []

        # Activities menu
        self.activity.treenotebook.add_page(_("Log"), scrolled)

        self._configure_watcher()

    def _configure_watcher(self):
        logging.error('Monitor directory %s', self._logs_path)
        dir_monitor = gio.File(self._logs_path).monitor_directory()
        dir_monitor.set_rate_limit(2000)
        dir_monitor.connect('changed', self._log_file_changed_cb)
        self._monitors.append(dir_monitor)

        for f in self._extra_files:
            logging.error('Monitor file %s', f)
            file_monitor = gio.File(f).monitor_file()
            file_monitor.set_rate_limit(2000)
            file_monitor.connect('changed', self._log_file_changed_cb)
            self._monitors.append(file_monitor)

    def _log_file_changed_cb(self, monitor, path1, path2, event):
        _directory, logfile = os.path.split(str(path1))

        if event == gio.FILE_MONITOR_EVENT_CHANGED:
            for log in self._openlogs:
                if logfile in log.full_path:
                    log.update()
        elif (event == gio.FILE_MONITOR_EVENT_DELETED
                or event == gio.FILE_MONITOR_EVENT_CREATED):
            self._model.refresh()
            #If the log is open, just leave it that way

    # Load the log information in View (text_view)
    def _load_log(self, treeview):
        node = activity_model.get_selected_file(self._tv_menu)
        print node
        path = node["path"]

        if os.path.isdir(path):
            #do not try to open folders
            logging.debug("Cannot open a folder as text :)")
            return

        if not path:
            #DummyActivityNode
            return

        # Set buffer and scroll down
        if self.activity.editor.set_to_page_like(path):
            return
        newlogview = LogView(path, self)

        scrollwnd = gtk.ScrolledWindow()
        scrollwnd.set_policy(gtk.POLICY_AUTOMATIC,
                             gtk.POLICY_AUTOMATIC)
        scrollwnd.add(newlogview)
        scrollwnd.page = newlogview
        tablabel = TabLabel(newlogview, label=node["name"])
        tablabel.connect(
            'tab-close',
            lambda widget, child: self.activity.editor.remove_page(
                self.activity.editor.page_num(child)))
        self.activity.editor.append_page(scrollwnd, tablabel)
        self._active_log = newlogview
        self.activity.editor.show_all()
        self.activity.editor.set_current_page(-1)

    def _filter_by_name(self, node):
        return (self._namefilter in node.filename) or node.isDirectory

    # Insert a Row in our TreeView
    def _insert_row(self, store, parent, name):
        iter = store.insert_before(parent, None)
        index = 0
        store.set_value(iter, index, name)

        return iter

    def _remove_logview(self, logview):
        try:
            self._openlogs.remove(logview)
        except ValueError:
            logging.debug("_remove_logview failed")


class LogBuffer(gtk.TextBuffer):
    def __init__(self, logfile, tagtable):
        gtk.TextBuffer.__init__(self, table=tagtable)

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


class LogView(gtk.TextView):

    def __init__(self, full_path, logminder):
        gtk.TextView.__init__(self)

        self.logminder = logminder
        self.full_path = full_path
        self.logminder._openlogs.append(self)

        self.set_wrap_mode(gtk.WRAP_WORD)

        # Tags for search
        tagtable = gtk.TextTagTable()
        hilite_tag = gtk.TextTag('search-hilite')
        hilite_tag.props.background = '#FFFFB0'
        tagtable.add(hilite_tag)
        select_tag = gtk.TextTag('search-select')
        select_tag.props.background = '#B0B0FF'
        tagtable.add(select_tag)

        newbuffer = self._create_log_buffer(full_path, tagtable)
        if newbuffer:
            self.set_buffer(newbuffer)
            self.text_buffer = newbuffer

        # Set background color
        bgcolor = gtk.gdk.color_parse("#EEEEEE")
        self.modify_base(gtk.STATE_NORMAL, bgcolor)

        self.set_editable(False)

        self.show()

    def remove(self):
        self.logminder._remove_logview(self)

    def _create_log_buffer(self, path, tagtable):
        self._written = False
        if os.path.isdir(path):
            return False

        if not os.path.exists(path):
            logging.error("ERROR: %s don't exists", path)
            return False

        if not os.access(path, os.R_OK):
            logging.error("ERROR: I can't read '%s' file", path)
            return False

        self.filename = _get_filename_from_path(path)

        self._logbuffer = logbuffer = LogBuffer(path, tagtable)

        self._written = logbuffer._written

        return logbuffer

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
            next_found = text_iter.forward_search(text, 0)
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

        if direction == 'forward':
            text_iter = _buffer.get_iter_at_mark(_buffer.get_insert())
            text_iter.forward_char()
        else:
            text_iter = _buffer.get_iter_at_mark(_buffer.get_insert())

        if direction == 'backward':
            return text_iter.backward_search(self.search_text, 0)
        else:
            return text_iter.forward_search(self.search_text, 0)

    def search_next(self, direction):
        next_found = self.get_next_result(direction)
        if next_found:
            _buffer = self.get_buffer()

            start, end = _buffer.get_bounds()
            _buffer.remove_tag_by_name('search-select', start, end)
            start, end = next_found
            _buffer.apply_tag_by_name('search-select', start, end)
            _buffer.place_cursor(start)

            self.scroll_to_iter(start, 0.1)
            self.scroll_to_iter(end, 0.1)
