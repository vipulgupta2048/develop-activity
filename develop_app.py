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
import json
from gettext import gettext as _

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject

from sugar3 import profile
from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.graphics.toolbarbox import ToolbarButton
from sugar3.graphics.radiotoolbutton import RadioToolButton
from sugar3.activity.widgets import ActivityToolbarButton

from sugar3.activity.widgets import StopButton
from sugar3.activity.bundlebuilder import XOPackager, Config, Builder
from sugar3.activity import activity
from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.alert import ConfirmationAlert
from sugar3.graphics.alert import Alert
from sugar3.graphics import notebook
from sugar3.graphics.icon import Icon
from sugar3.graphics import style
from sugar3.datastore import datastore
from sugar3.bundle.activitybundle import ActivityBundle

from jarabe.model import bundleregistry
from sugar3.activity import activityfactory

import logviewer
import sourceview_editor
S_WHERE = sourceview_editor.S_WHERE
from symbols_tree import SymbolsTree
from toolbars import DevelopEditToolbar, DevelopSearchToolbar
from toolbars import DevelopViewToolbar
from widgets import FileViewer, WelcomePage

SEARCH_ICONS = {False: {S_WHERE.selection: "search-in-selection",
                        S_WHERE.file: "system-search",
                        S_WHERE.multifile: "multi-search",
                        },
                True: {S_WHERE.selection: "regex-in-selection",
                       S_WHERE.file: "regex",
                       S_WHERE.multifile: "multi-regex",
                       }}
# CAP_ICONS = {False: "use-caps", True: "ignore-caps"}
# REPLACE_ICONS = {False: "replace-and-find", True: "multi-replace"}

_config_file_path = os.path.join(activity.get_activity_root(), 'data',
                                 'config.json')


class DevelopActivity(activity.Activity):
    """Develop Activity as specified in activity.info"""
    external_working_dir = False

    def __init__(self, handle):
        """Set up the Develop activity."""
        self._dirty = False
        super(DevelopActivity, self).__init__(handle)
        self.max_participants = 1

        self.current_theme = "light"

        logging.info(repr(handle.get_dict()))

        # Source buffer
        self.editor = sourceview_editor.GtkSourceview2Editor()
        self.editor.connect('tab-changed', self.__editor_tab_changed_cb)
        self.editor.connect('changed', self.__editor_changed_cb)
        # Show tabs after Welcome Page
        self.editor.set_show_tabs(False)

        toolbarbox = ToolbarBox()
        activity_button = ActivityToolbarButton(self)
        toolbarbox.toolbar.insert(activity_button, 0)
        self.set_toolbar_box(toolbarbox)

        view_btn = ToolbarButton()
        view_toolbar = DevelopViewToolbar(self)
        view_btn.props.page = view_toolbar
        view_btn.props.icon_name = 'toolbar-view'
        view_btn.props.label = _('View')
        view_toolbar.connect('theme-changed',
                             self.editor.theme_changed_cb)
        view_toolbar.connect('font-size-changed',
                             self.editor.font_changed_cb)
        toolbarbox.toolbar.insert(view_btn, -1)
        self.view_toolbar = view_toolbar

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

        # The treeview and selected pane reflect each other.
        self.numb = False

        # Wait to save until first change, but save an unchanged
        # backup copy when that happens.
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
        # Show sidebar after welcome page ends
        # sidebar.show()
        self.sidebar = sidebar

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
        welcome_page = WelcomePage()
        welcome_page.connect('open-activity', self.__welcome_open_activity_cb)
        welcome_page.connect('show-alert', self.__welcome_show_alert_cb)

        self.editor.append_page(welcome_page, Gtk.Label(label=_('Start')))

    def __welcome_open_activity_cb(self, welcome_page, activity_dir):
        # remove the welcome tab
        self.editor.remove_page(0)
        self.first_open_activity(activity_dir)

        # Show hidden stuff
        self._show_hidden_ui()
        self._load_config()

    def __welcome_show_alert_cb(self, welcome_page, message):
        self._show_alert(message)

    def _show_hidden_ui(self):
        self.sidebar.show()
        self.editor.set_show_tabs(True)

    def __run_actvity_cb(self, run_button):
        if self.save_unchanged:
            self.editor.save_all()

        registry = bundleregistry.get_registry()
        bundle = registry.get_bundle(self.bundle.get_bundle_id())
        activityfactory.create(bundle)

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

    def first_open_activity(self, activity_dir):
        """Open an activity for the first time.
           Subsequently, use open_activity.
        """
        logging.info('opening %s', activity_dir)
        if not activity_dir.endswith('/'):
            activity_dir = activity_dir + '/'
        self.activity_dir = activity_dir
        self.activity_tree_view.connect('file_selected',
                                        self.__file_selected_cb)
        self.refresh_files()
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
            # Choosing in the notebook selects in the list, and vice versa.
            # Avoid infinite recursion.
            return
        if path and not os.path.isdir(path):
            self.numb = True
            self.load_file(path)
            self.numb = False

    def __log_file_selected_cb(self, log_files_viewer, path):
        if not path:
            return

        if os.path.isdir(path):
            # do not try to open folders
            return

        # Set buffer and scroll down
        if self.editor.set_to_page_like(path):
            return

        self.editor.load_log_file(path, log_files_viewer)

    def save_bundle(self, btn):
        # create bundle
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
            # 'suggested_filename': '%s-%s.xo' % (builder.config.bundle_name,
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
            json.dump(dev_session_data, f)
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
        self._store_config()

    def read_file(self, file_path):
        self.activity_dir = self.metadata['source']
        logging.error('read_file self.activity_dir %s', self.activity_dir)
        self.first_open_activity(self.activity_dir)

        f = open(file_path, 'r')
        try:
            session_data = json.load(f)
            logging.error('read_file session_data %s', session_data)
            for filename in session_data['open_filenames']:
                if filename:
                    logging.info('opening : %s', filename)
                    self.load_file(filename)
        finally:
            f.close()

        self._show_hidden_ui()

        self._set_dirty(False)

        self._load_config()

    def _store_config(self):
        theme = self.editor.get_theme()
        font_size = self.editor.get_font_size()

        with open(_config_file_path, "w") as f:
            f.write(json.dumps((theme, font_size)))

    def _load_config(self):
        with open(_config_file_path, "r") as f:
            theme, font_size = json.loads(f.read())
            self.view_toolbar.set_theme(theme)
            self.view_toolbar.set_font_size(font_size)

    def _set_dirty(self, dirty):
        logging.debug("Setting dirty to %s; activity_dir is %s" %
                      (str(dirty), str(self.activity_dir)))
        self._dirty = dirty
        if dirty:
            self.save_unchanged = True

    def __editor_tab_changed_cb(self, editor, new_full_path):
        if self.numb:
            # avoid infinite recursion
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

        # HACK
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
