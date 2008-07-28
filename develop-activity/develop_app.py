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
from __future__ import with_statement
import gtk
import logging
logging.getLogger().setLevel(0)
import pango
import os, os.path, shutil
import gobject

from gettext import gettext as _

from developableactivity import ViewSourceActivity, OPENFILE_SEPARATOR
from sugar import profile
#from sugar.activity.activity import Activity
#from sugar.activity import activity
from activity import Activity
import activity
     #import ActivityToolbox, \
    #     EditToolbar, get_bundle_name, get_bundle_path
from sugar.graphics.toolbutton import ToolButton
from sugar.graphics.menuitem import MenuItem
from sugar.graphics.alert import ConfirmationAlert, TimeoutAlert
from sugar.graphics import iconentry, notebook
from sugar.datastore import datastore
#from sugar.bundle.activitybundle import ActivityBundle
from activitybundle import ActivityBundle
import logviewer
import sourceview_editor
S_WHERE = sourceview_editor.S_WHERE
import activity_model

DEBUG_FILTER_LEVEL = 1

SERVICE = "org.laptop.Develop"
IFACE = SERVICE
PATH = "/org/laptop/Develop"
WORKING_SOURCE_DIR = 'source'

SEARCH_ICONS = {False:{S_WHERE.selection:"search-in-selection",
                        S_WHERE.file:"system-search",
                        S_WHERE.multifile:"multi-search",
                        },
                True:{S_WHERE.selection:"regex-in-selection",
                        S_WHERE.file:"regex",
                        S_WHERE.multifile:"multi-regex",
                        }}
CAP_ICONS = {False:"use-caps",
            True:"ignore-caps"}
REPLACE_ICONS = {False:"replace-and-find",
            True:"multi-replace"}

TOOLBAR_SEARCH = 2

class Options:
    def __init__(self, template = None, **kw):
        if template:
            self.__dict__ = template.__dict__.copy()
        else:
            self.__dict__ = {}
        self.__dict__.update(kw)

class SearchOptions(Options):
    pass
    

class DevelopActivity(ViewSourceActivity):
    """Develop Activity as specified in activity.info"""
    external_working_dir = False
        
    def __init__(self, handle):
        """Set up the Develop activity."""
        super(DevelopActivity, self).__init__(handle, 
                    create_jobject=False)

        self._logger = logging.getLogger('develop-activity')
        self._logger.setLevel(0)
        self._logger.info(repr(handle.get_dict()))
        
        # Source buffer
        self.editor = sourceview_editor.GtkSourceview2Editor(self)

        # Top toolbar with share and close buttons:
        toolbox = activity.ActivityToolbox(self)
        self.set_toolbox(toolbox)
        toolbox.show()
        
        self.edittoolbar = DevelopEditToolbar(self, toolbox)
        toolbox.add_toolbar(_("Edit"), self.edittoolbar)
        self.edittoolbar.show()
        
        self.edittoolbar = DevelopSearchToolbar(self, toolbox)
        toolbox.add_toolbar(_("Search"), self.edittoolbar)
        self.edittoolbar.show()

        filetoolbar = DevelopFileToolbar(self)
        toolbox.add_toolbar(_("File"), filetoolbar)
        filetoolbar.show()

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
        sidebar.pack_start(self.treenotebook)
        
        self.model = gtk.TreeStore(gobject.TYPE_PYOBJECT, gobject.TYPE_STRING)
        self.treeview = gtk.TreeView(self.model)
        cellrenderer = gtk.CellRendererText()
        self.treecolumn = gtk.TreeViewColumn(_("Activities"), cellrenderer, 
                                             text=1)
        self.treeview.append_column(self.treecolumn)
        self.treeview.set_size_request(220, 900)

        # Create scrollbars around the tree view.
        scrolled = gtk.ScrolledWindow()
        scrolled.set_placement(gtk.CORNER_TOP_RIGHT)
        scrolled.add(self.treeview)
        self.treenotebook.add_page(_("Activity"), scrolled)
        hbox.pack1(sidebar, resize=True, shrink=True)
        sidebar.show()
            
        self._logger.info('finished check')
        vbox.pack_start(self.editor)
        self.editor.show()
        hbox.pack2(vbox, resize=True, shrink=True)
        vbox.show()
        self.set_canvas(hbox)
        hbox.show()
        self._logger.critical('finished initialization')
        self.activity_dir = None
        self.show()
     
        if not handle.object_id or not self.metadata.get('source'):
            #self._show_welcome()
            gobject.timeout_add(100,self._show_welcome)
            
    def is_foreign_dir(self):
        return not (self.external_working_dir
                    or not self.activity_dir 
                    or self.activity_dir.startswith(self.get_workingdir()))

    def show_msg(self, text, title = ""):
        alert = ConfirmationAlert()
        alert.props.title = title
        alert.props.msg = text 
        alert.connect('response', self.alert_cb)
        self.add_alert(alert)
        alert.show()
    
    def debug_msg(self, text, title = _("debug alert"), level=0):
        self._logger.debug(text)
        if level >= DEBUG_FILTER_LEVEL:
            self.show_msg(text, title)
        
    def alert_cb(self, alert, response_id):
        self.remove_alert(alert)
       
    def _show_welcome(self):
        import welcome_dialog
        dialog = welcome_dialog.WelcomeDialog(self)
        reply = dialog.run()
        if reply == welcome_dialog.RESPONSE_OPEN:
            self._pick_existing_activity()
        elif reply == welcome_dialog.RESPONSE_NEW:
            self._create_new_activity()
        else:
            self.dirty = False
            self.close()
        return False

    def _create_new_activity(self):
        dialog = gtk.Dialog(_("Name your Activity"), parent=self, 
                            flags=gtk.DIALOG_MODAL)
        vbox = dialog.vbox
        entry = gtk.Entry()
        vbox.add(entry)
        entry.show()
        dialog.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        dialog.add_button(gtk.STOCK_NEW, gtk.RESPONSE_OK)
        if dialog.run() == gtk.RESPONSE_OK:
            import new_activity
            activityDir = new_activity.new_activity(entry.get_text().strip())
            self.first_open_activity(activityDir)
            dialog.destroy()
        else:
            dialog.destroy()
            self.close()
    
    def _pick_existing_activity(self):
        root = os.path.expanduser('~/Activities')
        chooser = gtk.FileChooserDialog(_("Choose an exisiting activity"), self,
            gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
             gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        chooser.set_current_folder(root)
        if chooser.run() ==  gtk.RESPONSE_OK:
            activity_dir = chooser.get_filename()
            chooser.destroy()
            self.first_open_activity(activity_dir)
        else:
            chooser.destroy()
            self.destroy()
        del chooser
 
 
    def open_activity(self, activity_dir):
        self._logger.info('opening %s' % activity_dir)
        self.activity_dir = activity_dir + '/'
        name = os.path.basename(activity_dir)
        self.treecolumn.set_title(name)
        #self.metadata['title'] = name
        self.refresh_files()
        self.treeview.get_selection().connect("changed", self.selection_cb)
        return name

    def first_open_activity(self,activity_dir):
        name = self.open_activity(activity_dir)
        self.logview = logviewer.LogMinder(self, name.split(".")[0])
        self.set_dirty(False)
        
        
    def refresh_files(self):
        import activity_model
        self.bundle = ActivityBundle(self.activity_dir)
        self.model = activity_model.DirectoryAndExtraModel(self.activity_dir, 
                           nodefilter = activity_model.inmanifestfn(self.bundle))
        self.treeview.set_model(self.model)
        #self.treeview.redraw()
        #self.show_msg("refresh_files")

    def load_file(self, fullPath):
        if fullPath.startswith(self.activity_dir):
            filename = fullPath[len(self.activity_dir):]
        else:
            filename = fullPath
            fullPath = os.path.join(self.activity_dir, fullPath)
        self.editor.load_object(fullPath, filename)

    def selection_cb(self, column):
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
    
    def write_file(self, file_path):
        if self.is_foreign_dir():
            self.debug_msg(u'write file from %s to %s; dirty is %s' % 
                            (self.activity_dir, file_path, str(self.dirty)))
        if not self.save_unchanged:
            self.editor.save_all()
        filenames = OPENFILE_SEPARATOR.join(self.editor.get_all_filenames())
        self.debug_msg('activity_dir %s, file_path %s, filenames %s' % 
                (len(self.activity_dir), 
                len(file_path), len(filenames)))
        self._jobject = self.save_source_jobject(self.activity_dir, 
                file_path, filenames)
        self.metadata['source'] = self.activity_dir[:-1]
        self.set_dirty(False)
        
    def get_workingdir(self):
        return os.path.join(activity.get_activity_root(), activity.INSTANCE_DIR,
                            WORKING_SOURCE_DIR)
    
    def read_file(self, file_path):
        if not os.path.isfile(file_path):
            self._show_welcome()
            return
        workingdir = self.get_workingdir()
        if os.path.isdir(workingdir):
            shutil.rmtree(workingdir)
            #raise IOError("working dir already exists...")
        bundledir = ActivityBundle(file_path).unpack(workingdir)
        self.first_open_activity(os.path.join(bundledir))
        self._logger.info(u'read_file. subfiles: %s' % 
                          self.metadata['open_filenames'])
        for filename in self.metadata['open_filenames'].split(
                                                        OPENFILE_SEPARATOR):
            if filename:
                self.load_file(filename)
        self.set_dirty(False)
        
    def set_dirty(self, dirty):
        self.debug_msg("Setting dirty to %s; activity_dir is %s" %  
                (str(dirty), str(self.activity_dir)))
        self.dirty = dirty
        if dirty and self.activity_dir and self.is_foreign_dir():
            self.change_base()
            self.save_unchanged = True
            try:
                self.debug_msg("Saving a pristine copy for safety")
                self.save()
            finally:
                self.save_unchanged = False
                self.dirty = dirty
    
    def change_base(self):
        targetdir = self.get_workingdir()
        
        #if in an editable directory outside ~/Activities, edit in place
        if (not self.activity_dir.startswith(
                                    os.path.join(os.path.expanduser("~"),
                                                 "Activities"))
                            and os.access(targetdir, os.W_OK)):
            self.debug_msg("Editing files in place: "+self.activity_dir)
            self.external_working_dir = True
            return
        
        #otherwise, copy for editing
        self.debug_msg("Copying files for editing")
        if os.path.isdir(targetdir):
            shutil.rmtree(targetdir)
        olddir = self.activity_dir
        shutil.copytree(olddir, targetdir)
        self.open_activity(targetdir)
        self.editor.reroot(olddir, targetdir)
                
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


    def __init__(self, _activity, toolbox):
        activity.EditToolbar.__init__(self)

        self._toolbox = toolbox
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
    
    def __init__(self, _activity, toolbox):
        gtk.Toolbar.__init__(self)

        self._toolbox = toolbox
        self._activity = _activity

        # setup the search options
        self.s_opts = SearchOptions(where = S_WHERE.multifile,
                                    use_regex = False,
                                    ignore_caps = True,
                                    replace_all = False,
                                    
                                    #defaults to avoid creating
                                    #a new SearchOptions object for normal searches
                                    #should never be changed, just make a copy like:
                                    #SearchOptions(self.s_opts, forward=False)
                                    forward = True, 
                                    stay = False
                                    )
        self.safe_to_replace = False
        
        
        self._search_entry = iconentry.IconEntry()
        self._search_entry.set_icon_from_name(iconentry.ICON_ENTRY_PRIMARY,
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
        
        self._activity.editor.connect('changed', self._changed_cb)
        
        self._activity.connect('key_press_event', self._on_key_press_event)
      
    def _on_key_press_event(self, widget, event):
        keyname = gtk.gdk.keyval_name(event.keyval)
        if  "F5" <= keyname and keyname <= "F8":
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
        self.switch_to()
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
            self.switch_to()
    
    def switch_to(self):
        self._toolbox.set_current_toolbar(TOOLBAR_SEARCH)
                        
    def _reset_search_icons(self):
        self._search_entry.set_icon_from_name(iconentry.ICON_ENTRY_PRIMARY,
                    SEARCH_ICONS[self.s_opts.use_regex][self.s_opts.where])
        self._settings.set_icon(CAP_ICONS[self.s_opts.ignore_caps])
        self._replace_button.set_icon(REPLACE_ICONS[self.s_opts.replace_all])
        self._reset_replace_sensitivity()
    
    def _reset_replace_sensitivity(self):
        self._replace_button.set_sensitive(self.s_opts.where == 
                                                 S_WHERE.selection 
                    or self.s_opts.replace_all)
    
    def _set_where_options(self, menu, option):
        self.s_opts.where = option #IGNORE:W0201
        self._reset_search_icons()
        
    def _set_how_options(self, menu, option):
        self.s_opts.use_regex = option #IGNORE:W0201
        self._reset_search_icons()
        
    def _set_cap_options(self, menu, option):
        self.s_opts.ignore_caps = option #IGNORE:W0201
        self._reset_search_icons()
        
    def _set_replace_options(self, menu, option):
        self.s_opts.replace_all = option #IGNORE:W0201
        if option and self.s_opts.where == S_WHERE.multifile:
            self.s_opts.where = S_WHERE.file #for safety:
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
        replaced, found = self._activity.editor.replace(ftext, rtext, 
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
            if not self.s_opts.use_regex: #do not do partial searches for regex
                if self._activity.editor.find_next(text, 
                                SearchOptions(self.s_opts, 
                                              stay=True, 
                                where=(self.s_opts.where if 
                                       self.s_opts.where != S_WHERE.multifile
                                       else S_WHERE.file))):
                    #no multifile, or focus gets grabbed
                    self._replace_button.set_sensitive(True)
                    
    def _replace_entry_changed_cb(self, entry):
        if self._replace_entry.props.text:
            self.safe_to_replace = True
            
    def _findprev_cb(self, button=None):
        ftext = self._search_entry.props.text
        if ftext:
            if self._activity.editor.find_next(ftext, 
                                               SearchOptions(self.s_opts,
                                                             forward=False)):
                self._replace_button.set_sensitive(True)
                        
    def _findnext_cb(self, button=None):
        ftext = self._search_entry.props.text
        if ftext:
            if self._activity.editor.find_next(ftext, self.s_opts):
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

    def __init__(self, activity):
        gtk.Toolbar.__init__(self)
        
        self.activity = activity
        
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
        
        open = ToolButton('text-x-generic')
        open.set_tooltip(_('View an external file...'))
        open.connect('clicked', self._open_file_cb)
        
        palette = open.get_palette()
        
        dirmenu = MenuItem(_('Import an external file...'))
        dirmenu.connect('activate', self._import_file_cb)
        palette.menu.append(dirmenu)
        dirmenu.show()
        open.show()
        
        self.insert(open, -1)
        
    def _add_file_cb(self, menu, sourcepath = None):
        self.activity.set_dirty(True)
        chooser = gtk.FileChooserDialog(_('Name your new file...'), 
            self.activity, gtk.FILE_CHOOSER_ACTION_SAVE,
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                    gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        chooser.set_current_folder(self.activity.activity_dir)
        if chooser.run() ==  gtk.RESPONSE_OK:
            filename = chooser.get_filename()
            chooser.destroy()
            
            if not filename.startswith(self.activity.activity_dir):
                self.activity.show_msg(_("You cannot create a file "
                                         "outside of the activity directory."),
                                       _("Error: Outside Activity")) 
                return
            if not os.path.exists(filename):
                if sourcepath:
                    import shutil
                    shutil.copyfile(sourcepath, filename)
                else:
                    file(filename, 'w').close()
            self._show_new_file(filename)
        else:
            chooser.destroy()
        del chooser
    
    def _add_dir_cb(self, menu):
        self.activity.set_dirty(True)
        chooser = gtk.FileChooserDialog(_('Name your new directory...'), 
            self.activity, gtk.FILE_CHOOSER_ACTION_CREATE_FOLDER,
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                    gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        chooser.set_current_folder(self.activity.activity_dir)
        if chooser.run() ==  gtk.RESPONSE_OK:
            dirname = chooser.get_filename()
            chooser.destroy()
            
            if not os.path.exists(filename):
                os.mkdir(path)
                self.activity.refresh_files()
                
            if not os.path.isdir(filename):
                self.activity.debug_msg(_("Error: directory creation failed."),
                                        DEBUG_FILTER_LEVEL)  
        else:
            chooser.destroy()
        del chooser

    def _prune_manifest(self):
        act_dir = self.activity.activity_dir
        bundle = self.activity.bundle = ActivityBundle(act_dir)
        manifestlines = bundle.manifest # trim MANIFEST
        with file(os.path.join(act_dir,"MANIFEST"), "wb") as manifest:
            for line in manifestlines:
                manifest.write(line + "\n")
                
    def _show_new_file(self,filename):
        if os.path.isfile(filename):
            with file(os.path.join(self.activity.activity_dir, "MANIFEST"),
                      "a") as manifest:
                manifest.write(filename[len(os.path.join(
                            self.activity.activity_dir,"")):]+"\n")
            self.activity.refresh_files()
        else:
            self.activity.debug_msg(_("Error: file creation failed."),
                                    DEBUG_FILTER_LEVEL)
        
    def _erase_file_cb(self, menu):
        chooser = gtk.FileChooserDialog(_('Pick the file to erase...'), 
            self.activity, gtk.FILE_CHOOSER_ACTION_OPEN,
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                    gtk.STOCK_DELETE, gtk.RESPONSE_OK))
        chooser.set_current_folder(self.activity.activity_dir)
        if chooser.run() ==  gtk.RESPONSE_OK:
            filename = chooser.get_filename()
            chooser.destroy()
            if os.path.isfile(filename):
                os.unlink(filename)
                self.prune_manifest()
                self.activity.refresh_files()
            else:
                self.activity.debug_msg(_("Error: file deletion failed."),
                                        DEBUG_FILTER_LEVEL)  

        else:
            chooser.destroy()
        del chooser
    
    def _erase_dir_cb(self, menu):
        chooser = gtk.FileChooserDialog(_('Pick the directory to erase...'), 
            self.activity, gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                    gtk.STOCK_DELETE, gtk.RESPONSE_OK))
        chooser.set_current_folder(self.activity.activity_dir)
        if chooser.run() ==  gtk.RESPONSE_OK:
            filename = chooser.get_filename()
            chooser.destroy()
            if os.listdir(filename):
                alert = ConfirmationAlert()
                name = filename[len(self.activity.activity_dir):]
                alert.props.title=_('Are you sure you want to erase %s?') % name
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
            import shutil
            shutil.rmtree(filename, True)
            self.prune_manifest()
            self.activity.refresh_files()

    def _open_file_cb(self, button):
        chooser = gtk.FileChooserDialog(_('Pick the file to open...'), 
                                        self.activity, 
                                        gtk.FILE_CHOOSER_ACTION_OPEN,
                                        (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                         gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        chooser.set_current_folder(os.path.expanduser("~"))
        if chooser.run() ==  gtk.RESPONSE_OK:
            filename = chooser.get_filename()
            chooser.destroy()
            dso = datastore.create()
            dso.metadata['filename'] = os.path.basename(filename)
            dso.metadata['source'] = dso.file_path = filename
            self.activity.editor.load_object(dso)
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
        if chooser.run() ==  gtk.RESPONSE_OK:
            filename = chooser.get_filename()
            chooser.destroy()
            self._add_file_cb(None,filename)
        else:
            chooser.destroy()
        del chooser