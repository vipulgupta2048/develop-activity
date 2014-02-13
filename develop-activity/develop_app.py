# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received  a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

"""Develop Activity: A programming activity."""
import logging
import os
import os.path
import simplejson
from gettext import gettext as _

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject

from sugar3 import profile
from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.graphics.toolbarbox import ToolbarButton
from sugar3.graphics.radiotoolbutton import RadioToolButton
from sugar3.activity.widgets import ActivityToolbarButton
from sugar3.activity.widgets import EditToolbar
from sugar3.activity.widgets import StopButton
from sugar3.activity.bundlebuilder import XOPackager, Config, Builder
from sugar3.activity import activity
from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.combobox import ComboBox
from sugar3.graphics.alert import ConfirmationAlert
from sugar3.graphics.alert import Alert
from sugar3.graphics import iconentry, notebook
from sugar3.graphics.icon import Icon
from sugar3.graphics import style
from sugar3.datastore import datastore
from sugar3.bundle.activitybundle import ActivityBundle

from jarabe.model import bundleregistry
from sugar3.activity import activityfactory

import logviewer
import sourceview_editor
S_WHERE = sourceview_editor.S_WHERE
import new_activity
from symbols_tree import SymbolsTree

SEARCH_ICONS = {False: {S_WHERE.selection: "search-in-selection",
                        S_WHERE.file: "system-search",
                        S_WHERE.multifile: "multi-search",
                        },
                True: {S_WHERE.selection: "regex-in-selection",
                       S_WHERE.file: "regex",
                       S_WHERE.multifile: "multi-regex",
                       }}
#CAP_ICONS = {False: "use-caps", True: "ignore-caps"}
#REPLACE_ICONS = {False: "replace-and-find", True: "multi-replace"}

_EXCLUDE_EXTENSIONS = ('.pyc', '.pyo', '.so', '.o', '.a', '.la', '.mo', '~',
                       '.xo', '.tar', '.bz2', '.zip', '.gz')
_EXCLUDE_NAMES = ['.deps', '.libs']


class SearchOptions:

    def __init__(self, template=None, **kw):
        if template:
            self.__dict__ = template.__dict__.copy()
        else:
            self.__dict__ = {}
        self.__dict__.update(kw)


class DevelopActivity(activity.Activity):
    """Develop Activity as specified in activity.info"""
    external_working_dir = False

    def __init__(self, handle):
        """Set up the Develop activity."""
        self._dirty = False
        super(DevelopActivity, self).__init__(handle)
        self.max_participants = 1

        logging.info(repr(handle.get_dict()))

        # Source buffer
        self.editor = sourceview_editor.GtkSourceview2Editor()
        self.editor.connect('tab-changed', self.__editor_tab_changed_cb)
        self.editor.connect('changed', self.__editor_changed_cb)

        toolbarbox = ToolbarBox()
        activity_button = ActivityToolbarButton(self)
        toolbarbox.toolbar.insert(activity_button, 0)
        self.set_toolbar_box(toolbarbox)

        edit_btn = ToolbarButton()
        edit_btn.props.page = DevelopEditToolbar(self)
        edit_btn.props.icon_name = 'toolbar-edit'
        edit_btn.props.label = _('Edit')
        toolbarbox.toolbar.insert(edit_btn, -1)

        search_btn = ToolbarButton()
        search_btn.props.page = DevelopSearchToolbar(self)
        search_btn.props.icon_name = 'search'
        search_btn.props.label = _('Search')
        toolbarbox.toolbar.insert(search_btn, -1)

        toolbarbox.toolbar.insert(Gtk.SeparatorToolItem(), -1)

        show_files_btn = RadioToolButton()
        show_files_btn.props.icon_name = 'sources'
        show_files_btn.props.group = show_files_btn
        show_files_btn.set_active(True)
        show_files_btn.set_tooltip(_('Show source files'))
        toolbarbox.toolbar.insert(show_files_btn, -1)
        show_files_btn.connect('clicked', self._change_treenotebook_page, 0)

        show_symbols_btn = RadioToolButton()
        show_symbols_btn.props.icon_name = 'symbols'
        show_symbols_btn.props.group = show_files_btn
        show_symbols_btn.set_active(False)
        show_symbols_btn.set_tooltip(_('Show file symbols'))
        toolbarbox.toolbar.insert(show_symbols_btn, -1)
        show_symbols_btn.connect('clicked', self._explore_code)

        show_log_btn = RadioToolButton()
        show_log_btn.props.icon_name = 'logs'
        show_log_btn.props.group = show_files_btn
        show_log_btn.set_active(False)
        show_log_btn.set_tooltip(_('Show log files'))
        toolbarbox.toolbar.insert(show_log_btn, -1)
        show_log_btn.connect('clicked', self._change_treenotebook_page, 2)

        toolbarbox.toolbar.insert(Gtk.SeparatorToolItem(), -1)

        create_file_btn = ToolButton('text-x-generic')
        create_file_btn.set_tooltip(_('Create empty file'))
        toolbarbox.toolbar.insert(create_file_btn, -1)
        create_file_btn.show()
        create_file_btn.connect('clicked', self.__create_empty_file_cb)

        erase_btn = ToolButton('erase')
        erase_btn.set_tooltip(_('Remove file'))
        toolbarbox.toolbar.insert(erase_btn, -1)
        erase_btn.show()
        erase_btn.connect('clicked', self.__remove_file_cb)

        toolbarbox.toolbar.insert(Gtk.SeparatorToolItem(), -1)

        run_btn = ToolButton('activity-start')
        run_btn.set_tooltip(_('Run activity'))
        toolbarbox.toolbar.insert(run_btn, -1)
        run_btn.connect('clicked', self.__run_actvity_cb)

        separator = Gtk.SeparatorToolItem()
        separator.set_draw(False)
        separator.set_expand(True)
        toolbarbox.toolbar.insert(separator, -1)

        stopbtn = StopButton(self)
        toolbarbox.toolbar.insert(stopbtn, -1)

        save_bundle_btn = ToolButton('save-as-bundle')
        save_bundle_btn.set_tooltip(_('Create bundle (.xo file)'))
        activity_button.get_page().insert(save_bundle_btn, -1)
        save_bundle_btn.connect('clicked', self.save_bundle)
        save_bundle_btn.show()

        toolbarbox.show_all()

        # Main layout.
        hbox = Gtk.HPaned()

        #The treeview and selected pane reflect each other.
        self.numb = False

        #Wait to save until first change, but save an unchanged
        #backup copy when that happens.
        self.save_unchanged = False

        # The sidebar
        sidebar = Gtk.VBox()
        self.treenotebook = notebook.Notebook(can_close_tabs=False)
        self.treenotebook.set_show_tabs(False)
        sidebar.pack_start(self.treenotebook, True, True, 0)

        self.activity_tree_view = FileViewer()
        self.treenotebook.add_page(_("Activity"), self.activity_tree_view)
        self.treenotebook.set_size_request(Gdk.Screen.width() / 5, -1)

        # Symbols tree
        self._symbolstree = SymbolsTree()
        self._symbolstree.connect('symbol-selected',
                                  self.editor.symbol_selected_cb)
        scrolled = Gtk.ScrolledWindow()
        scrolled.add(self._symbolstree)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.treenotebook.add_page(_('Symbols Tree'), scrolled)

        hbox.pack1(sidebar, resize=True, shrink=False)
        sidebar.show()

        logging.info('finished check')
        self.editor.show()
        hbox.pack2(self.editor, resize=True, shrink=True)
        self.set_canvas(hbox)
        hbox.show()
        logging.critical('finished initialization')
        self.activity_dir = None
        self.show()

        if not handle.object_id or not self.metadata.get('source'):
            GObject.timeout_add(10, self._show_welcome)

    def _change_treenotebook_page(self, button, page):
        self.treenotebook.set_current_page(page)

    def _explore_code(self, btn, switch_page=True):
        from ninja import introspection
        text = self.editor.get_text()
        path = self.editor.get_file_path()
        logging.error('Analyzing %s', path)
        symbols = introspection.obtain_symbols(text, filename=path)
        self._symbolstree.load_symbols(symbols)
        if switch_page:
            self._change_treenotebook_page(None, 1)
        self._symbolstree.expand_all()

    def show_msg(self, text, title=""):
        """show_msg(text) shows text in a drop-down alert message.
        """
        alert = ConfirmationAlert()
        alert.props.title = title
        alert.props.msg = text
        alert.connect('response', self.alert_cb)
        self.add_alert(alert)
        alert.show()

    def create_confirmation_alert(self, text, title=""):
        alert = ConfirmationAlert()
        alert.props.title = title
        alert.props.msg = text
        self.add_alert(alert)
        return alert

    def alert_cb(self, alert, response_id):
        self.remove_alert(alert)

    def _show_welcome(self):
        """_show_welcome: when opened without a bundle, ask open/new/cancel
        """
        vbox = Gtk.VBox()

        edit_label = Gtk.Label(
            _('<span weight="bold" size="larger">'
              'Edit a installed activity</span>\n\n'
              'You can modify a activity, and if there are errors the '
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

        vbox.show_all()
        self.editor.append_page(vbox, Gtk.Label(label=_('Start')))
        return False

    def __run_actvity_cb(self, run_button):
        if self.save_unchanged:
            self.editor.save_all()

        registry = bundleregistry.get_registry()
        bundle = registry.get_bundle(self.bundle.get_bundle_id())
        activityfactory.create(bundle)

    def _load_activities_installed_combo(self, activities_combo):
        activities_path = os.path.join(os.path.expanduser("~"), "Activities")
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
            self._show_alert(_('You must type the name for the new activity'))
            return
        if combo_skeletons.get_active() == -1:
            self._show_alert(_('You must select the project type'))
            return

        activity_name = name_entry.get_text().strip()
        activities_path = os.path.join(os.path.expanduser("~"),
                                       "Activities")
        skel_iter = combo_skeletons.get_active_iter()
        skeleton = combo_skeletons.get_model().get_value(skel_iter, 1)

        activityDir = new_activity.create_activity(activity_name,
                                                   activities_path, skeleton)
        self.first_open_activity(activityDir)
        # remove the welcome tab
        self.editor.remove_page(0)

    def _show_alert(self, message, title=None):
        alert = Alert()
        if title is None:
            title = _('Atention')
        alert.props.title = title
        alert.props.msg = message
        alert.add_button(Gtk.ResponseType.OK, _('Ok'))
        self.add_alert(alert)
        alert.connect('response', self._alert_response_cb)

    def _alert_response_cb(self, alert, response_id):
        self.remove_alert(alert)

    def _pick_existing_activity(self, button, combo_activities):
        if combo_activities.get_active() == -1:
            self._show_alert(_('You must select the activity'))
        else:
            activities_path = os.path.join(os.path.expanduser("~"),
                                           "Activities")
            selected = combo_activities.get_active_iter()
            activity_name = combo_activities.get_model().get_value(selected, 1)
            logging.error('Activity selected %s', activity_name)
            activity_dir = os.path.join(activities_path,
                                        "%s.activity" % activity_name)
            self.first_open_activity(activity_dir)
            # remove the welcome tab
            self.editor.remove_page(0)

    def open_activity(self, activity_dir):
        logging.info('opening %s', activity_dir)
        if not activity_dir.endswith('/'):
            activity_dir = activity_dir + '/'
        self.activity_dir = activity_dir
        self.refresh_files()
        self.activity_tree_view.connect('file_selected',
                                        self.__file_selected_cb)

    def first_open_activity(self, activity_dir):
        """Open an activity for the first time.
           Subsequently, use open_activity.
        """
        self.open_activity(activity_dir)
        self.bundle = ActivityBundle(self.activity_dir)
        name = self.bundle.get_name()
        self.activity_tree_view.set_title(name)
        self.metadata['title'] = _('Develop %s') % name
        namefilter = self.bundle.get_bundle_id()
        self._log_files_viewer = logviewer.LogFilesViewer(namefilter)
        self._log_files_viewer.connect('file-selected',
                                       self.__log_file_selected_cb)
        self.treenotebook.add_page(_("Log"), self._log_files_viewer)

        self._set_dirty(False)

    def refresh_files(self):
        """Refresh the treeview of activity files.
        """
        self.bundle = ActivityBundle(self.activity_dir)
        self.activity_tree_view.load_activity(self.activity_dir, self.bundle)

    def load_file(self, full_path):
        """Load one activity subfile into the editor view.
        """
        logging.error('load_file full_path %s', full_path)
        logging.error('load_file self.activity_dir %s', self.activity_dir)

        if full_path.startswith(self.activity_dir):
            filename = full_path[len(self.activity_dir):]
        else:
            filename = full_path
            full_path = os.path.join(self.activity_dir, full_path)
        logging.error('load_file filename %s', filename)
        self.editor.load_object(full_path, filename)

    def __file_selected_cb(self, file_viewer, path):
        """User selected an item in the treeview. Load it.
        """
        if self.numb:
            #Choosing in the notebook selects in the list, and vice versa.
            #Avoid infinite recursion.
            return
        if path and not os.path.isdir(path):
            self.numb = True
            self.load_file(path)
            self.numb = False

    def __log_file_selected_cb(self, log_files_viewer, path):
        if not path:
            return

        if os.path.isdir(path):
            #do not try to open folders
            return

        # Set buffer and scroll down
        if self.editor.set_to_page_like(path):
            return

        self.editor.load_log_file(path, log_files_viewer)

    def save_bundle(self, btn):
        #create bundle
        builder = XOPackager(Builder(Config(self.activity_dir, '/tmp')))
        builder.package()
        logging.error('Packaging %s', builder.package_path)
        jobject = datastore.create()
        icon_color = profile.get_color().to_string()

        metadata = {
            'title': '%s-%s.xo' % (builder.config.bundle_name,
                                   builder.config.version),
            'title_set_by_user': '1',
            'suggested_filename': '%s-%s.xo' % (builder.config.bundle_name,
                                                builder.config.version),
            'icon-color': icon_color,
            'mime_type': 'application/vnd.olpc-sugar',
            'activity': self.get_bundle_id(),
            'activity_id': self.get_id(),
            'share-scope': activity.SCOPE_PRIVATE,
            'preview': '',
            'source': self.activity_dir, }

        for k, v in metadata.items():
            jobject.metadata[k] = v
        jobject.file_path = builder.package_path
        datastore.write(jobject)
        jobject.destroy()
        self._show_alert(_('The bundle has been saved in the journal.'),
                         _('Success'))

    def save_source_jobject(self, activity_dir, file_path, filenames=None):
        if not activity_dir:
            raise NotImplementedError

        # fix up datastore object
        # FIXME: some of this is overkill,
        # legacy from when I created a new jobject each save
        jobject = self._jobject
        icon_color = profile.get_color().to_string()

        metadata = {
            'title': self.metadata['title'],
            'title_set_by_user': '1',
            #'suggested_filename': '%s-%s.xo' % (builder.config.bundle_name,
            #                                    builder.config.version),
            'icon-color': icon_color,
            'mime_type': 'application/develop-session',
            'activity': self.get_bundle_id(),
            'activity_id': self.get_id(),
            'share-scope': activity.SCOPE_PRIVATE,
            'preview': '',
            'source': activity_dir, }

        for k, v in metadata.items():
            jobject.metadata[k] = v  # dict.update method is missing =(
        dev_session_data = {}

        if filenames:
            dev_session_data['open_filenames'] = filenames

        f = open(file_path, 'w')
        try:
            simplejson.dump(dev_session_data, f)
        finally:
            f.close()
        jobject.file_path = file_path
        datastore.write(jobject)
        jobject.destroy()
        return jobject

    def write_file(self, file_path):
        """Wrap up the activity as a bundle and save it to journal.
        """
        logging.error('WRITE_FILE')
        if self.activity_dir is None:
            return
        if self.save_unchanged:
            self.editor.save_all()
        filenames = self.editor.get_all_filenames()
        logging.debug('activity_dir %s, file_path %s, filenames %s' %
                      (self.activity_dir, file_path, filenames))
        self._jobject = self.save_source_jobject(
            self.activity_dir, file_path, filenames)
        self.metadata['source'] = self.activity_dir
        self._set_dirty(False)
        self.save_unchanged = False

    def read_file(self, file_path):
        self.activity_dir = self.metadata['source']
        logging.error('read_file self.activity_dir %s', self.activity_dir)
        self.first_open_activity(self.activity_dir)

        f = open(file_path, 'r')
        try:
            session_data = simplejson.load(f)
            logging.error('read_file session_data %s', session_data)
            for filename in session_data['open_filenames']:
                if filename:
                    logging.info('opening : %s', filename)
                    self.load_file(filename)
        finally:
            f.close()

        self._set_dirty(False)

    def _set_dirty(self, dirty):
        logging.debug("Setting dirty to %s; activity_dir is %s" %
                      (str(dirty), str(self.activity_dir)))
        self._dirty = dirty
        if dirty:
            self.save_unchanged = True

    def __editor_tab_changed_cb(self, editor, new_full_path):
        if self.numb:
            #avoid infinite recursion
            return
        self.numb = True
        self.activity_tree_view.select_by_file_path(new_full_path)
        logging.error('new tab %s', new_full_path)
        self.numb = False

        # TODO: change by a constant
        if self.treenotebook.get_current_page() == 1:  # symbols
            GObject.idle_add(self._explore_code, None)

    def __editor_changed_cb(self, editor):
        logging.error('Editor text changed')
        self._set_dirty(True)

    def __create_empty_file_cb(self, button):
        alert = Alert()
        alert.props.title = _('Create new file')
        alert.props.msg = _('Select the name of the file')

        #HACK
        alert._hbox.remove(alert._buttons_box)
        alert.entry = Gtk.Entry()
        alert._hbox.pack_start(alert.entry, True, True, 0)

        alert._buttons_box = Gtk.HButtonBox()
        alert._buttons_box.set_layout(Gtk.ButtonBoxStyle.END)
        alert._buttons_box.set_spacing(style.DEFAULT_SPACING)
        alert._hbox.pack_start(alert._buttons_box, True, True, 0)

        icon = Icon(icon_name='dialog-cancel')
        alert.add_button(Gtk.ResponseType.CANCEL, _('Cancel'), icon)

        icon = Icon(icon_name='dialog-ok')
        alert.add_button(Gtk.ResponseType.OK, _('Ok'), icon)
        alert.show_all()
        #

        self.add_alert(alert)
        alert.connect('response', self.__create_file_alert_cb)

    def __create_file_alert_cb(self, alert, response_id):
        if response_id is Gtk.ResponseType.OK:
            file_name = alert.entry.get_text()
            try:
                path = os.path.dirname(self.editor.get_file_path())
            except:
                path = self.activity_dir

            file_path = os.path.join(path, file_name)
            with open(file_path, 'w') as new_file:
                new_file.write('')

            self.refresh_files()
            self.editor.load_object(file_path, file_name)

        self.remove_alert(alert)

    def __remove_file_cb(self, button):
        file_path = self.editor.get_file_path()
        title = _('WARNING: The action you will do can not be reverted.')
        msg = _('Do you want remove the file %s?') % file_path
        alert = self.create_confirmation_alert(msg, title)
        alert.show()
        alert.connect('response', self.__remove_file_alert_cb, file_path)

    def __remove_file_alert_cb(self, alert, response_id, file_path):
        if response_id is Gtk.ResponseType.OK:
            if os.path.isfile(file_path):
                os.unlink(file_path)
                self.refresh_files()
                self.editor.close_page()
        self.remove_alert(alert)


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

        if file_name:
            path = os.path.join(activity_path, file_name)
            if os.path.exists(path):
                logging.error('INITIAL_FILENAME %s', path)
                self._initial_filename = path

    def set_title(self, title):
        self._column.set_title(title)

    def _is_web_activity(self, activity_bundle):
        return activity_bundle.get_command() == 'sugar-activity-web'


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
