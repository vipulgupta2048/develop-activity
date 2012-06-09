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
#import gnomevfs

import activity_model

from sourceview_editor import SearchablePage

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
            path = os.path.join(self.activity._get_user_path(),
                                ".sugar", "default", "logs")
            #env.get_profile_path(), 'logs')

        if not extra_files:
            # extra files to watch in logviewer
            extra_files = []
            extra_files.append("/var/log/Xorg.0.log")
            extra_files.append("/var/log/syslog")
            extra_files.append("/var/log/messages")

        self._logs_path = path
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
        self._model = activity_model.DirectoryAndExtraModel(path, extra_files,
                self._filter_by_name)
        self._tv_menu.set_model(self._model)

        self._add_column(self._tv_menu, 'Sugar logs', 0)
        self._logs = {}

        # Activities menu
        self.activity.treenotebook.add_page(_("Log"), scrolled)

        # TODO: gnomevfs is deprecated
        #self._configure_watcher()

    def _configure_watcher(self):
        gnomevfs.monitor_add('file://' + self._logs_path,
                                gnomevfs.MONITOR_DIRECTORY,
                                self._log_file_changed_cb)

        for f in self._extra_files:
            gnomevfs.monitor_add('file://' + f,
                                gnomevfs.MONITOR_FILE,
                                self._log_file_changed_cb)

    def _log_file_changed_cb(self, monitor_uri, info_uri, event):
        path = info_uri.split('file://')[-1]
        dir, logfile = os.path.split(path)

        if event == gnomevfs.MONITOR_EVENT_CHANGED:
            for log in self._openlogs:
                if logfile in log.logpath:
                    log.update()
        elif (event == gnomevfs.MONITOR_EVENT_DELETED
                or event == gnomevfs.MONITOR_EVENT_CREATED):
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
        self.activity.editor.add_page(node["name"], newlogview)
        self.activity.editor.set_current_page(-1)
        self._active_log = newlogview

    def _filter_by_name(self, node):
        return (self._namefilter in node.filename) or node.isDirectory

    # Add a new column to the main treeview, (code from Memphis)
    def _add_column(self, treeview, column_name, index):
        cell = gtk.CellRendererText()
        col_tv = gtk.TreeViewColumn(column_name, cell, text=index)
        col_tv.set_resizable(True)
        col_tv.set_property('clickable', True)

        treeview.append_column(col_tv)

        # Set the last column index added
        self.last_col_index = index

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
    def __init__(self, logfile):
        gtk.TextBuffer.__init__(self)

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


class LogView(SearchablePage):

    def __init__(self, logpath, logminder):
        gtk.ScrolledWindow.__init__(self)

        self.logminder = logminder
        self.logpath = logpath
        self.logminder._openlogs.append(self)
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        self.text_view = gtk.TextView()
        self.text_view.set_wrap_mode(gtk.WRAP_WORD)

        newbuffer = self._create_log_buffer(logpath)
        if newbuffer:
            self.text_view.set_buffer(newbuffer)
            self.text_buffer = newbuffer
        # Set background color
        bgcolor = gtk.gdk.color_parse("#FFFFFF")
        self.text_view.modify_base(gtk.STATE_NORMAL, bgcolor)

        self.text_view.set_editable(False)

        self.add(self.text_view)
        self.text_view.show()

    def remove(self):
        self.logminder._remove_logview(self)

    def _create_log_buffer(self, path):
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

        self._logbuffer = logbuffer = LogBuffer(path)

        self._written = logbuffer._written

        return logbuffer

    def __eq__(self, other):
        return  other == self.logpath or other == self.filename

    def replace(self, *args, **kw):
        return (False, False)

    def update(self):
        self._logbuffer.update()
