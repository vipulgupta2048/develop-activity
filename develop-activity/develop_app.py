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
import gtk
import logging
import os
import os.path
import shutil
import gobject
import simplejson

from gettext import gettext as _

from sugar import profile
from sugar.graphics.toolbarbox import ToolbarBox
from sugar.activity.widgets import ActivityToolbarButton
from sugar.graphics.toolbarbox import ToolbarButton
from sugar.graphics.radiotoolbutton import RadioToolButton
from sugar.activity.widgets import StopButton
from sugar.activity.bundlebuilder import XOPackager, Config, Builder
from sugar.activity import activity
from sugar.graphics.toolbutton import ToolButton
from sugar.graphics.menuitem import MenuItem
from sugar.graphics.combobox import ComboBox
from sugar.graphics.alert import ConfirmationAlert
from sugar.graphics.alert import Alert
from sugar.graphics import iconentry, notebook
from sugar.datastore import datastore
from sugar.bundle.activitybundle import ActivityBundle

import logviewer
import sourceview_editor
S_WHERE = sourceview_editor.S_WHERE
import activity_model
import new_activity

from symbols_tree import SymbolsTree

DEBUG_FILTER_LEVEL = 1

SERVICE = "org.laptop.Develop"
IFACE = SERVICE
PATH = "/org/laptop/Develop"
WORKING_SOURCE_DIR = 'source'

SEARCH_ICONS = {False: {S_WHERE.selection: "search-in-selection",
                        S_WHERE.file: "system-search",
                        S_WHERE.multifile: "multi-search",
                        },
                True: {S_WHERE.selection: "regex-in-selection",
                       S_WHERE.file: "regex",
                       S_WHERE.multifile: "multi-regex",
                       }}
CAP_ICONS = {False: "use-caps", True: "ignore-caps"}
REPLACE_ICONS = {False: "replace-and-find", True: "multi-replace"}

TOOLBAR_SEARCH = 2

OPENFILE_SEPARATOR = u"@ @"


class Options:

    def __init__(self, template=None, **kw):
        if template:
            self.__dict__ = template.__dict__.copy()
        else:
            self.__dict__ = {}
        self.__dict__.update(kw)


class SearchOptions(Options):
    pass


class DevelopActivity(activity.Activity):
    """Develop Activity as specified in activity.info"""
    external_working_dir = False

    def __init__(self, handle):
        """Set up the Develop activity."""
        self.dirty = False
        super(DevelopActivity, self).__init__(handle)
        self.max_participants = 1

        logging.info(repr(handle.get_dict()))

        # Source buffer
        self.editor = sourceview_editor.GtkSourceview2Editor(self)

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

        """
        filetoolbar = DevelopFileToolbar(self)
        toolbox.add_toolbar(_("File"), filetoolbar)
        filetoolbar.show()
        """
        toolbarbox.toolbar.insert(gtk.SeparatorToolItem(), -1)

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
        show_symbols_btn.connect('clicked', self.explore_code)

        show_log_btn = RadioToolButton()
        show_log_btn.props.icon_name = 'logs'
        show_log_btn.props.group = show_files_btn
        show_log_btn.set_active(False)
        show_log_btn.set_tooltip(_('Show log files'))
        toolbarbox.toolbar.insert(show_log_btn, -1)
        show_log_btn.connect('clicked', self._change_treenotebook_page, 2)

        toolbarbox.toolbar.insert(gtk.SeparatorToolItem(), -1)

        separator = gtk.SeparatorToolItem()
        separator.set_draw(False)
        separator.set_expand(True)
        toolbarbox.toolbar.insert(separator, -1)

        stopbtn = StopButton(self)
        toolbarbox.toolbar.insert(stopbtn, -1)

        save_bundle_btn = ToolButton('save-as-bundle')
        activity_button.get_page().insert(save_bundle_btn, -1)
        save_bundle_btn.connect('clicked', self.save_bundle)
        save_bundle_btn.show()

        toolbarbox.show_all()

        # Main layout.
        hbox = gtk.HPaned()
        vbox = gtk.VBox()

        #The treeview and selected pane reflect each other.
        self.numb = False

        #Wait to save until first change, but save an unchanged
        #backup copy when that happens.
        self.save_unchanged = False

        # The sidebar
        sidebar = gtk.VBox()
        self.treenotebook = notebook.Notebook(can_close_tabs=False)
        self.treenotebook.set_show_tabs(False)
        sidebar.pack_start(self.treenotebook)

        self.model = gtk.TreeStore(gobject.TYPE_PYOBJECT, gobject.TYPE_STRING)
        self.treeview = gtk.TreeView(self.model)
        cellrenderer = gtk.CellRendererText()
        self.treecolumn = gtk.TreeViewColumn(_("Activities"), cellrenderer,
                                             text=1)
        self.treeview.append_column(self.treecolumn)
        self.treeview.set_size_request(gtk.gdk.screen_width() / 4, -1)

        # Create scrollbars around the tree view.
        scrolled = gtk.ScrolledWindow()
        scrolled.add(self.treeview)
        scrolled.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        self.treenotebook.add_page(_("Activity"), scrolled)

        # Symbols tree
        self._symbolstree = SymbolsTree()
        self._symbolstree.connect('symbol-selected',
                                  self.editor.symbol_selected_cb)
        scrolled = gtk.ScrolledWindow()
        scrolled.add(self._symbolstree)
        scrolled.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        self.treenotebook.add_page(_('Symbols Tree'), scrolled)

        hbox.pack1(sidebar, resize=True, shrink=True)
        sidebar.show()

        logging.info('finished check')
        vbox.pack_start(self.editor)
        self.editor.show()
        hbox.pack2(vbox, resize=True, shrink=True)
        vbox.show()
        self.set_canvas(hbox)
        hbox.show()
        logging.critical('finished initialization')
        self.activity_dir = None
        self.show()

        if not handle.object_id or not self.metadata.get('source'):
            gobject.timeout_add(100, self._show_welcome)

    def _change_treenotebook_page(self, button, page):
        self.treenotebook.set_current_page(page)

    def explore_code(self, btn, switch_page=True):
        from ninja import introspection
        text = self.editor.get_text()
        path = self.editor.get_file_path()
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

    def debug_msg(self, text, title=_("debug alert"), level=0):
        """debug_msg(text, level=x): log text, and maybe show dialog.
        """
        logging.debug(text)
        if level >= DEBUG_FILTER_LEVEL:
            self.show_msg(text, title)

    def alert_cb(self, alert, response_id):
        self.remove_alert(alert)

    def _show_welcome(self):
        """_show_welcome: when opened without a bundle, ask open/new/cancel
        """
        vbox = gtk.VBox()
        welcome_label = gtk.Label(
            _('<span weight="bold" size="larger">'
              'What would you like to do?</span>\n\n'
              'Choose "Edit one activity" to open an existing activity. '
              'You can modify the activity, and if there are errors the '
              'activity can stop working. If you are not sure, clone the '
              'activity to have a backup. To test the activity you wrote, '
              'just click on it in the journal.'))
        welcome_label.set_use_markup(True)
        welcome_label.set_line_wrap(True)
        vbox.pack_start(welcome_label, expand=False, fill=True, padding=10)

        hbox = gtk.HBox()
        hbox_edit = gtk.HBox()
        edit_btn = gtk.Button(_('Edit one activity'))
        hbox_edit.pack_start(edit_btn, expand=False, fill=False, padding=10)
        hbox_edit.pack_start(gtk.Label(_('Select the activity')))
        activity_name_combo = ComboBox()
        self._load_activities_installed_combo(activity_name_combo)
        edit_btn.connect('clicked', self._pick_existing_activity,
                         activity_name_combo)
        hbox_edit.pack_start(activity_name_combo, expand=True, fill=True,
                             padding=10)
        hbox.pack_start(hbox_edit, expand=False, fill=False)
        vbox.pack_start(hbox, expand=False, fill=False, padding=10)

        hbox = gtk.HBox()
        hbox_create = gtk.HBox()
        create_btn = gtk.Button(_('Create a new activity'))
        hbox_create.pack_start(create_btn, expand=False, fill=False,
                               padding=10)
        hbox_create.pack_start(gtk.Label(_('Name the activity')))
        activity_name_entry = gtk.Entry()
        create_btn.connect('clicked', self._create_new_activity,
                           activity_name_entry)
        hbox_create.pack_start(activity_name_entry, expand=True, fill=True,
                               padding=10)
        hbox.pack_start(hbox_create, expand=False, fill=False)
        vbox.pack_start(hbox, expand=False, fill=False, padding=10)

        vbox.show_all()
        self.editor.append_page(vbox, gtk.Label(_('Start')))
        return False

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

    def _create_new_activity(self, button, name_entry):
        """create and open a new activity in working dir
        """
        if name_entry.get_text() == '':
            self._show_alert(_('You must type the name for the new activity'))
        else:
            activity_name = name_entry.get_text().strip()
            activities_path = os.path.join(os.path.expanduser("~"),
                                           "Activities")
            activityDir = new_activity.new_activity(activity_name,
                                                    activities_path)
            self.first_open_activity(activityDir)
            # remove the welcome tab
            self.editor.remove_page(0)

    def _show_alert(self, message, title=None):
        alert = Alert()
        if title is None:
            title = _('Atention')
        alert.props.title = title
        alert.props.msg = message
        alert.add_button(gtk.RESPONSE_OK, _('Ok'))
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
        name = os.path.basename(activity_dir)
        self.treecolumn.set_title(name)
        self.metadata['title'] = 'Develop %s' % name
        self.refresh_files()
        self.treeview.get_selection().connect("changed", self.selection_cb)
        return name

    def first_open_activity(self, activity_dir):
        """Open an activity for the first time.
           Subsequently, use open_activity.
        """
        self.open_activity(activity_dir)
        namefilter = ActivityBundle(activity_dir).get_bundle_id()
        self.logview = logviewer.LogMinder(self, namefilter)
        self.set_dirty(False)

    def refresh_files(self):
        """Refresh the treeview of activity files.
        """
        self.bundle = ActivityBundle(self.activity_dir)
        self.model = activity_model.DirectoryAndExtraModel(
            self.activity_dir,
            nodefilter=activity_model.inmanifestfn(self.bundle))
        self.treeview.set_model(self.model)

    def load_file(self, fullPath):
        """Load one activity subfile into the editor view.
        """
        logging.error('load_file fullPath %s', fullPath)
        logging.error('load_file self.activity_dir %s', self.activity_dir)

        if fullPath.startswith(self.activity_dir):
            filename = fullPath[len(self.activity_dir):]
        else:
            filename = fullPath
            fullPath = os.path.join(self.activity_dir, fullPath)
        logging.error('load_file filename %s', filename)
        self.editor.load_object(fullPath, filename)

    def selection_cb(self, column):
        """User selected an item in the treeview. Load it.
        """
        if self.numb:
            #Choosing in the notebook selects in the list, and vice versa.
            #Avoid infinite recursion.
            return
        path = activity_model.get_selected_file_path(self.treeview)
        if path and not os.path.isdir(path):
            self.save()
            self.numb = True
            self.load_file(path)
            self.numb = False

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
        if self.activity_dir is None:
            return
        if not self.save_unchanged:
            self.editor.save_all()
        filenames = OPENFILE_SEPARATOR.join(self.editor.get_all_filenames())
        self.debug_msg('activity_dir %s, file_path %s, filenames %s' %
                       (self.activity_dir, file_path, len(filenames)))
        self._jobject = self.save_source_jobject(
            self.activity_dir, file_path, filenames)
        self.metadata['source'] = self.activity_dir
        self.set_dirty(False)

    def read_file(self, file_path):
        self.activity_dir = self.metadata['source']
        logging.error('read_file self.activity_dir %s', self.activity_dir)
        self.first_open_activity(self.activity_dir)

        f = open(file_path, 'r')
        try:
            session_data = simplejson.load(f)
            for filename in \
                    session_data['open_filenames'].split(OPENFILE_SEPARATOR):
                if filename:
                    logging.info('opening : %s', filename)
                    self.load_file(filename)
        finally:
            f.close()

        self.set_dirty(False)

    def is_dirty(self):
        return self.dirty

    def set_dirty(self, dirty):
        self.debug_msg("Setting dirty to %s; activity_dir is %s" %
                       (str(dirty), str(self.activity_dir)))
        self.dirty = dirty
        if dirty:
            self.save_unchanged = True
            try:
                self.debug_msg("Saving a pristine copy for safety")
                self.save()
            finally:
                self.save_unchanged = False
                self.dirty = dirty

    def update_sidebar_to_page(self, page):
        if self.numb:
            #avoid infinite recursion
            return
        if isinstance(page, sourceview_editor.GtkSourceview2Page):
            source = page.fullPath
            tree_iter = self.model.get_iter_from_filepath(source)
            if tree_iter:
                tree_selection = self.treeview.get_selection()
                tree_selection.unselect_all()
                self.numb = True
                tree_selection.select_iter(tree_iter)
                self.numb = False


class DevelopEditToolbar(activity.EditToolbar):

    def __init__(self, _activity):
        activity.EditToolbar.__init__(self)

        self._activity = _activity
        self._activity.editor.connect('changed', self._changed_cb)
        self._changed_cb(None)

        self.undo.connect('clicked', self._undo_cb)
        self.redo.connect('clicked', self._redo_cb)
        self.copy.connect('clicked', self._copy_cb)
        self.paste.connect('clicked', self._paste_cb)

        # make expanded non-drawn visible separator to make
        #the search stuff right-align
        separator = gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        self.insert(separator, -1)
        separator.show()

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

    # bad paul! this function was copied from sugar's activity.py via Write
    def _add_widget(self, widget, expand=False):
        tool_item = gtk.ToolItem()
        tool_item.set_expand(expand)

        tool_item.add(widget)
        widget.show()

        self.insert(tool_item, -1)
        tool_item.show()


class DevelopSearchToolbar(gtk.Toolbar):

    def __init__(self, _activity):
        gtk.Toolbar.__init__(self)

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
                menuitem = gtk.SeparatorMenuItem()
            else:
                menuitem = MenuItem(name, icon)
                menuitem.connect('activate', function, options)
            palette.menu.append(menuitem)
            menuitem.show()

        # make expanded non-drawn visible separator to make the replace
        #stuff right-align
        separator = gtk.SeparatorToolItem()
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
                menuitem = gtk.SeparatorMenuItem()
            else:
                menuitem = MenuItem(name, icon)
                menuitem.connect('activate', function, options)
            palette.menu.append(menuitem)
            menuitem.show()
        """

        self._activity.editor.connect('changed', self._changed_cb)

        self._activity.connect('key_press_event', self._on_key_press_event)

    def _on_key_press_event(self, widget, event):
        keyname = gtk.gdk.keyval_name(event.keyval)
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
        self._settings.set_icon(CAP_ICONS[self.s_opts.ignore_caps])
        self._replace_button.set_icon(REPLACE_ICONS[self.s_opts.replace_all])
        self._reset_replace_sensitivity()

    def _reset_replace_sensitivity(self):
        self._replace_button.set_sensitive(
            self.s_opts.where == S_WHERE.selection or self.s_opts.replace_all)

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
        ftext = self._search_entry.props.text
        rtext = self._replace_entry.props.text
        __replaced, found = self._activity.editor.replace(ftext, rtext,
                                                          self.s_opts)
        if found:
            self._replace_button.set_sensitive(True)

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
                    self._replace_button.set_sensitive(True)

    def _replace_entry_changed_cb(self, entry):
        if self._replace_entry.props.text:
            self.safe_to_replace = True

    def _findprev_cb(self, button=None):
        ftext = self._search_entry.props.text
        if ftext:
            if self._activity.editor.find_next(ftext, direction='backward'):
                self._replace_button.set_sensitive(True)

    def _findnext_cb(self, button=None):
        ftext = self._search_entry.props.text
        if ftext:
            if self._activity.editor.find_next(ftext, direction='forward'):
                self._replace_button.set_sensitive(True)

    # bad paul! this function was copied from sugar's activity.py via Write
    def _add_widget(self, widget, expand=False):
        tool_item = gtk.ToolItem()
        tool_item.set_expand(expand)

        tool_item.add(widget)
        widget.show()

        self.insert(tool_item, -1)
        tool_item.show()


class DevelopFileToolbar(gtk.Toolbar):

    def __init__(self, develop_activity):
        gtk.Toolbar.__init__(self)

        self.activity = develop_activity

        insert = ToolButton('insert-image')
        insert.set_tooltip(_('Add a blank file...'))
        insert.connect('clicked', self._add_file_cb)

        palette = insert.get_palette()

        dirmenu = MenuItem(_('Add a directory...'))
        dirmenu.connect('activate', self._add_dir_cb)
        palette.menu.append(dirmenu)

        dirmenu.show()
        insert.show()

        self.insert(insert, -1)

        remove = ToolButton('erase')
        remove.set_tooltip(_('Erase a file...'))
        remove.connect('clicked', self._erase_file_cb)

        palette = remove.get_palette()

        dirmenu = MenuItem(_('Erase a directory...'))
        dirmenu.connect('activate', self._erase_dir_cb)
        palette.menu.append(dirmenu)
        dirmenu.show()
        remove.show()

        self.insert(remove, -1)

        open_btn = ToolButton('text-x-generic')
        open_btn.set_tooltip(_('View an external file...'))
        open_btn.connect('clicked', self._open_file_cb)

        palette = open_btn.get_palette()

        dirmenu = MenuItem(_('Import an external file...'))
        dirmenu.connect('activate', self._import_file_cb)
        palette.menu.append(dirmenu)
        dirmenu.show()
        open_btn.show()

        self.insert(open_btn, -1)

    def _add_file_cb(self, menu, sourcepath=None):
        self.activity.set_dirty(True)
        chooser = gtk.FileChooserDialog(
            _('Name your new file...'),
            self.activity, gtk.FILE_CHOOSER_ACTION_SAVE,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
             gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        chooser.set_current_folder(self.activity.activity_dir)
        if chooser.run() == gtk.RESPONSE_OK:
            filename = chooser.get_filename()
            chooser.destroy()

            if not filename.startswith(self.activity.activity_dir):
                self.activity.show_msg(_("You cannot create a file "
                                         "outside of the activity directory."),
                                       _("Error: Outside Activity"))
                return
            if not os.path.exists(filename):
                if sourcepath:
                    shutil.copyfile(sourcepath, filename)
                else:
                    file(filename, 'w').close()
            self._show_new_file(filename)
        else:
            chooser.destroy()
        del chooser

    def _add_dir_cb(self, menu):
        self.activity.set_dirty(True)
        chooser = gtk.FileChooserDialog(
            _('Name your new directory...'),
            self.activity, gtk.FILE_CHOOSER_ACTION_CREATE_FOLDER,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
             gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        chooser.set_current_folder(self.activity.activity_dir)
        if chooser.run() == gtk.RESPONSE_OK:
            dirname = chooser.get_filename()
            chooser.destroy()

            if not os.path.exists(dirname):
                os.mkdir(dirname)
                self.activity.refresh_files()

            if not os.path.isdir(dirname):
                self.activity.debug_msg(_("Error: directory creation failed."),
                                        DEBUG_FILTER_LEVEL)
        else:
            chooser.destroy()
        del chooser

    def _show_new_file(self, filename):
        if os.path.isfile(filename):
            self.activity.refresh_files()
        else:
            self.activity.debug_msg(_("Error: file creation failed."),
                                    DEBUG_FILTER_LEVEL)

    def _erase_file_cb(self, menu):
        chooser = gtk.FileChooserDialog(
            _('Pick the file to erase...'),
            self.activity, gtk.FILE_CHOOSER_ACTION_OPEN,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
             gtk.STOCK_DELETE, gtk.RESPONSE_OK))
        chooser.set_current_folder(self.activity.activity_dir)
        if chooser.run() == gtk.RESPONSE_OK:
            filename = chooser.get_filename()
            chooser.destroy()
            if os.path.isfile(filename):
                os.unlink(filename)
                self.activity.refresh_files()
            else:
                self.activity.debug_msg(_("Error: file deletion failed."),
                                        DEBUG_FILTER_LEVEL)
        else:
            chooser.destroy()
        del chooser

    def _erase_dir_cb(self, menu):
        chooser = gtk.FileChooserDialog(
            _('Pick the directory to erase...'),
            self.activity, gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
             gtk.STOCK_DELETE, gtk.RESPONSE_OK))
        chooser.set_current_folder(self.activity.activity_dir)
        if chooser.run() == gtk.RESPONSE_OK:
            filename = chooser.get_filename()
            chooser.destroy()
            if os.listdir(filename):
                alert = ConfirmationAlert()
                name = filename[len(self.activity.activity_dir):]
                alert.props.title = \
                    _('Are you sure you want to erase %s?') % name
                alert.connect('response', self._alert_response, filename)
                self.activity.add_alert(alert)
            else:
                self._alert_response(None, gtk.RESPONSE_OK, filename)
        else:
            chooser.destroy()
        del chooser

    def _alert_response(self, alert, response, filename):
        if alert:
            self.activity.remove_alert(alert)
        if response == gtk.RESPONSE_OK:
            shutil.rmtree(filename, True)
            self.activity.refresh_files()

    def _open_file_cb(self, button):
        chooser = gtk.FileChooserDialog(_('Pick the file to open...'),
                                        self.activity,
                                        gtk.FILE_CHOOSER_ACTION_OPEN,
                                        (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                         gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        chooser.set_current_folder(os.path.expanduser("~"))
        if chooser.run() == gtk.RESPONSE_OK:
            filename = chooser.get_filename()
            chooser.destroy()
            dso = datastore.create()
            dso.metadata['filename'] = os.path.basename(filename)
            dso.metadata['source'] = dso.file_path = filename
            self.activity.editor.load_object(filename, dso)
        else:
            chooser.destroy()
        del chooser

    def _import_file_cb(self, button):
        chooser = gtk.FileChooserDialog(_('Pick the file to import...'),
                                        self.activity,
                                        gtk.FILE_CHOOSER_ACTION_OPEN,
                                        (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                         gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        chooser.set_current_folder(os.path.expanduser("~"))
        if chooser.run() == gtk.RESPONSE_OK:
            filename = chooser.get_filename()
            chooser.destroy()
            self._add_file_cb(None, filename)
        else:
            chooser.destroy()
        del chooser
