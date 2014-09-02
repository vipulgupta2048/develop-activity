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
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
import logging
import os
import os.path
from gettext import gettext as _

from gi.repository import Gtk
from gi.repository import GObject

from sugar3.activity import activity
from sugar3.graphics import style
from sugar3.graphics.combobox import ComboBox
from sugar3.graphics.icon import Icon

import new_activity

_EXCLUDE_EXTENSIONS = ('.pyc', '.pyo', '.so', '.o', '.a', '.la', '.mo', '~',
                       '.xo', '.tar', '.bz2', '.zip', '.gz')
_EXCLUDE_NAMES = ['.deps', '.libs']

try:
    activities_path = os.environ['SUGAR_ACTIVITIES_PATH']
except KeyError:
    activities_path = os.path.join(os.path.expanduser("~"), "Activities")


class TabLabel(Gtk.HBox):
    __gtype_name__ = 'BrowseTabLabel'

    __gsignals__ = {
        'tab-close': (GObject.SignalFlags.RUN_FIRST,
                      None,
                      ([object])),
    }

    def __init__(self, child, label=""):
        GObject.GObject.__init__(self)

        self._child = child
        self._label = Gtk.Label(label=label)
        self._label.set_alignment(0, 0.5)
        self.pack_start(self._label, True, True, 0)
        self._label.show()

        #self.modify_base(Gtk.StateType.NORMAL, Gdk.Color(0, 0, 0, 1))

        close_tab_icon = Icon(icon_name='close-tab')
        button = Gtk.Button()
        button.props.relief = Gtk.ReliefStyle.NONE
        button.props.focus_on_click = False
        icon_box = Gtk.HBox()
        icon_box.pack_start(close_tab_icon, True, False, 0)
        button.add(icon_box)
        button.connect('clicked', self.__button_clicked_cb)
        button.set_name('browse-tab-close')
        self.pack_start(button, False, True, 0)
        close_tab_icon.show()
        icon_box.show()
        button.show()
        self._close_button = button

    def set_text(self, title):
        self._label.set_text(title)

    def update_size(self, size):
        self.set_size_request(size, -1)

    def hide_close_button(self):
        self._close_button.hide()

    def show_close_button(self):
        self._close_button.show()

    def __button_clicked_cb(self, button):
        self.emit('tab-close', self._child)


class WelcomePage(Gtk.EventBox):

    __gsignals__ = {
        'open-activity': (GObject.SignalFlags.RUN_FIRST,
                          None,
                          ([str])),
        'show-alert': (GObject.SignalFlags.RUN_FIRST,
                       None,
                       ([str])),
    }

    def __init__(self):
        Gtk.EventBox.__init__(self)

        vbox_outer = Gtk.VBox()
        vbox = Gtk.VBox()

        edit_label = Gtk.Label(
            _('<span weight="bold" size="larger">'
              'Edit an installed activity</span>\n\n'
              'You can modify an activity, and if there are errors the '
              'activity can stop working. If you are not sure, clone the '
              'activity to have a backup.'))
        edit_label.set_use_markup(True)
        edit_label.set_line_wrap(True)
        vbox.pack_start(edit_label, expand=False, fill=True, padding=10)

        hbox_edit = Gtk.HBox()
        hbox_edit.pack_start(Gtk.Label(_('Select the activity')), True,
                             True, 10)
        activity_name_combo = ComboBox()
        self._load_activities_installed_combo(activity_name_combo)
        hbox_edit.pack_start(activity_name_combo, expand=False, fill=False,
                             padding=10)
        edit_btn = Gtk.Button(_('Start'))
        edit_btn.connect('clicked', self._pick_existing_activity,
                         activity_name_combo)
        hbox_edit.pack_start(edit_btn, expand=False, fill=False,
                             padding=10)
        align = Gtk.Alignment.new(0.5, 0.5, 0, 0)
        align.add(hbox_edit)
        vbox.pack_start(align, expand=False, fill=False, padding=10)

        new_project_label = Gtk.Label(
            _('<span weight="bold" size="larger">'
              'Create a new activity</span>\n\n'
              'You can create something new, '
              'just select the type of project.'))
        new_project_label.set_use_markup(True)
        new_project_label.set_line_wrap(True)
        vbox.pack_start(new_project_label, expand=False, fill=True, padding=10)

        hbox_create = Gtk.HBox()
        hbox_create.pack_start(Gtk.Label(_('Select the type')),
                               expand=False, fill=False, padding=10)
        project_type_combo = ComboBox()
        self._load_skeletons_combo(project_type_combo)
        hbox_create.pack_start(project_type_combo, expand=False, fill=False,
                               padding=10)
        align = Gtk.Alignment.new(0.5, 0.5, 0, 0)
        align.add(hbox_create)
        vbox.pack_start(align, expand=False, fill=False, padding=10)

        hbox_name = Gtk.HBox()
        hbox_name.pack_start(Gtk.Label(_('Name the activity')), True, True, 0)
        activity_name_entry = Gtk.Entry()
        hbox_name.pack_start(activity_name_entry, expand=True, fill=True,
                             padding=10)

        create_btn = Gtk.Button(_('Start'))
        create_btn.connect('clicked', self._create_new_activity,
                           activity_name_entry, project_type_combo)
        hbox_name.pack_start(create_btn, expand=True, fill=True,
                             padding=10)
        align = Gtk.Alignment.new(0.5, 0.5, 0, 0)
        align.add(hbox_name)
        vbox.pack_start(align, expand=False, fill=False, padding=10)

        self.modify_bg(Gtk.StateType.NORMAL,
                       style.COLOR_WHITE.get_gdk_color())

        vbox_outer.pack_start(vbox, expand=True, fill=False, padding=0)
        self.add(vbox_outer)
        self.show_all()

    def _load_activities_installed_combo(self, activities_combo):
        for dir_name in sorted(os.listdir(activities_path)):
            if dir_name.endswith('.activity'):
                activity_name = dir_name[:- len('.activity')]
                # search the icon
                info_file_name = os.path.join(activities_path, dir_name,
                                              'activity/activity.info')
                try:
                    info_file = open(info_file_name, 'r')
                    icon_name = None
                    for line in info_file.readlines():
                        if line.strip().startswith('icon'):
                            icon_name = line.split()[-1]
                    info_file.close()
                    icon_file_name = None
                    if icon_name is not None:
                        icon_file_name = os.path.join(
                            activities_path, dir_name, 'activity',
                            '%s.svg' % icon_name)
                    activities_combo.append_item(0, activity_name,
                                                 file_name=icon_file_name)
                except:
                    logging.error('Error trying to read information about %s',
                                  activity_name)

    def _load_skeletons_combo(self, skeletons_combo):
        skeletons_path = os.path.join(activity.get_bundle_path(), 'skeletons')
        for dir_name in sorted(os.listdir(skeletons_path)):
            skeletons_combo.append_item(0, dir_name)

    def _create_new_activity(self, button, name_entry, combo_skeletons):
        """create and open a new activity in working dir
        """
        if name_entry.get_text() == '':
            self.emit('show-alert',
                      _('You must type the name for the new activity'))
            return
        if combo_skeletons.get_active() == -1:
            self.emit('show-alert', _('You must select the project type'))
            return

        activity_name = name_entry.get_text().strip()
        skel_iter = combo_skeletons.get_active_iter()
        skeleton = combo_skeletons.get_model().get_value(skel_iter, 1)

        activity_dir = new_activity.create_activity(activity_name,
                                                    activities_path, skeleton)
        self.emit('open-activity', activity_dir)

    def _pick_existing_activity(self, button, combo_activities):
        if combo_activities.get_active() == -1:
            self.emit('show-alert', _('You must select the activity'))
        else:
            selected = combo_activities.get_active_iter()
            activity_name = combo_activities.get_model().get_value(selected, 1)
            logging.error('Activity selected %s', activity_name)
            activity_dir = os.path.join(activities_path,
                                        "%s.activity" % activity_name)
            self.emit('open-activity', activity_dir)


class FileViewer(Gtk.ScrolledWindow):
    __gtype_name__ = 'ActivityFileViewer'

    __gsignals__ = {
        'file-selected': (GObject.SignalFlags.RUN_FIRST,
                          None,
                          ([str])),
    }

    def __init__(self):
        Gtk.ScrolledWindow.__init__(self)

        self.props.hscrollbar_policy = Gtk.PolicyType.AUTOMATIC
        self.props.vscrollbar_policy = Gtk.PolicyType.AUTOMATIC
        self.set_size_request(style.GRID_CELL_SIZE * 3, -1)

        self._path = None
        self._initial_filename = None

        self._tree_view = Gtk.TreeView()
        self._tree_view.connect('cursor-changed', self.__cursor_changed_cb)
        self.add(self._tree_view)
        self._tree_view.show()

        selection = self._tree_view.get_selection()
        selection.connect('changed', self.__selection_changed_cb)

        cell = Gtk.CellRendererText()
        self._column = Gtk.TreeViewColumn()
        self._column.pack_start(cell, True)
        self._column.add_attribute(cell, 'text', 0)
        self._tree_view.append_column(self._column)
        self._tree_view.set_search_column(0)
        # map between file_path and iter
        self._opened_files = {}

    def load_activity(self, path, bundle):
        self._search_initial_filename(path, bundle)
        self._path = path

        self._tree_view.set_model(Gtk.TreeStore(str, str))
        self._model = self._tree_view.get_model()
        self._add_dir_to_model(path)

    def _add_dir_to_model(self, dir_path, parent=None):
        for f in os.listdir(dir_path):
            if f.endswith(_EXCLUDE_EXTENSIONS) or f in _EXCLUDE_NAMES:
                continue

            full_path = os.path.join(dir_path, f)
            if os.path.isdir(full_path):
                new_iter = self._model.append(parent, [f, full_path])
                self._add_dir_to_model(full_path, new_iter)
            else:
                current_iter = self._model.append(parent, [f, full_path])
                self._opened_files[full_path] = current_iter
                if full_path == self._initial_filename:
                    selection = self._tree_view.get_selection()
                    selection.select_iter(current_iter)

    def __selection_changed_cb(self, selection):
        model, tree_iter = selection.get_selected()
        if tree_iter is None:
            file_path = None
        else:
            file_path = model.get_value(tree_iter, 1)
        self.emit('file-selected', file_path)

    def __cursor_changed_cb(self, tree_view):
        selection = tree_view.get_selection()
        store, iter_ = selection.get_selected()
        if iter_ is None:
            # Nothing selected. This happens at startup
            return
        if store.iter_has_child(iter_):
            path = store.get_path(iter_)
            if tree_view.row_expanded(path):
                tree_view.collapse_row(path)
            else:
                tree_view.expand_row(path, False)

    def select_by_file_path(self, file_path):
        if file_path in self._opened_files:
            tree_iter = self._opened_files[file_path]
            tree_selection = self._tree_view.get_selection()
            tree_selection.unselect_all()
            tree_selection.select_iter(tree_iter)

    def _search_initial_filename(self, activity_path, bundle):
        command = bundle.get_command()

        if self._is_web_activity(bundle):
            file_name = 'index.html'

        elif len(command.split(' ')) > 1:
            name = command.split(' ')[1].split('.')[-1]
            tmppath = command.split(' ')[1].replace('.', '/')
            file_name = tmppath[0:-(len(name) + 1)] + '.py'
        else:
            file_name = command

        if file_name:
            path = os.path.join(activity_path, file_name)
            if os.path.exists(path):
                logging.error('INITIAL_FILENAME %s', path)
                self._initial_filename = path
                self.emit('file-selected', path)

    def set_title(self, title):
        self._column.set_title(title)

    def _is_web_activity(self, activity_bundle):
        return activity_bundle.get_command() == 'sugar-activity-web'
