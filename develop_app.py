# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
      
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

"""Develop Activity: A simple Python programming activity ."""
import gtk
import logging
logging.getLogger().setLevel(0)
import pango
import os, os.path
import gobject

from gettext import gettext as _

from activity import ViewSourceActivity
from sugar import profile
from sugar.activity.activity import ActivityToolbox, \
     EditToolbar
from sugar.graphics.toolbutton import ToolButton
from sugar.graphics.menuitem import MenuItem
from sugar.graphics.alert import ConfirmationAlert
from sugar.graphics import iconentry, notebook
from sugar.datastore import datastore

import logviewer
import sourceview_editor
import activity_model

SERVICE = "org.laptop.Develop"
IFACE = SERVICE
PATH = "/org/laptop/Develop"

class DevelopActivity(ViewSourceActivity):
    """Develop Activity as specified in activity.info"""
        
    def __init__(self, handle):
        """Set up the Develop activity."""
        ViewSourceActivity.__init__(self, handle)

        self._logger = logging.getLogger('develop-activity')
        self._logger.setLevel(0)
        self._logger.info(repr(handle.get_dict()))
        # Source buffer
        self.editor = sourceview_editor.GtkSourceview2Editor(self)

        # Top toolbar with share and close buttons:
        toolbox = ActivityToolbox(self)
        self.set_toolbox(toolbox)
        toolbox.show()
        
        self.edittoolbar = DevelopEditToolbar(self)
        toolbox.add_toolbar(_("Edit"), self.edittoolbar)
        self.edittoolbar.show()

        filetoolbar = DevelopFileToolbar(self)
        toolbox.add_toolbar(_("File"), filetoolbar)
        filetoolbar.show()

        # Main layout.
        hbox = gtk.HPaned()
        vbox = gtk.VBox()

        
        #The treeview and selected pane reflect each other.
        self.numb = False
        
        # The sidebar
        sidebar = gtk.VBox()
        self.treenotebook = notebook.Notebook(can_close_tabs=False)
        sidebar.pack_start(self.treenotebook)
        
        self.model = gtk.TreeStore(gobject.TYPE_PYOBJECT, gobject.TYPE_STRING)
        self.treeview = gtk.TreeView(self.model)
        cellrenderer = gtk.CellRendererText()
        self.treecolumn = gtk.TreeViewColumn(_("Activities"), cellrenderer, text=1)
        self.treeview.append_column(self.treecolumn)
        self.treeview.set_size_request(220, 900)

        # Create scrollbars around the tree view.
        scrolled = gtk.ScrolledWindow()
        scrolled.set_placement(gtk.CORNER_TOP_RIGHT)
        scrolled.add(self.treeview)
        self.treenotebook.add_page(_("Activity"),scrolled)
        hbox.pack1(sidebar, resize=True, shrink=True)
        sidebar.show()
            
        self._logger.info('finished check')
        vbox.pack_start(self.editor)
        self.editor.show()
        self._logger.info('editor')
        hbox.pack2(vbox, resize=True, shrink=True)
        vbox.show()
        self._logger.info('vbox')
        self.set_canvas(hbox)
        hbox.show()
        self._logger.critical('finished initialization')
        self.activity_dir = None
        self.show()
     
        if not handle.object_id or not self.metadata.get('source'):
            self._show_welcome()
      
    def _show_welcome(self):
        import welcome_dialog
        dialog = welcome_dialog.WelcomeDialog(self)
        reply = dialog.run()
        if reply == welcome_dialog.RESPONSE_OPEN:
            self._pick_existing_activity()
        elif reply == welcome_dialog.RESPONSE_NEW:
            self._create_new_activity()
        else:
            self.close()

    def _create_new_activity(self):
        dialog = gtk.Dialog(_("Name your Activity"), parent=self, flags=gtk.DIALOG_MODAL)
        vbox = dialog.vbox
        entry = gtk.Entry()
        vbox.add(entry)
        entry.show()
        dialog.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        dialog.add_button(gtk.STOCK_NEW, gtk.RESPONSE_OK)
        if dialog.run() == gtk.RESPONSE_OK:
            import new_activity
            activityDir = new_activity.new_activity(entry.get_text().strip())
            self.open_activity(activityDir)
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
            self.open_activity(activity_dir)
        else:
            chooser.destroy()
            self.destroy()
        del chooser
 
    def open_activity(self, activity_dir):
        self._logger.info('opening %s' % activity_dir)
        self.activity_dir = activity_dir + '/'
        name = os.path.basename(activity_dir)
        self.treecolumn.set_title(name)
        self.metadata['title'] = name
        import activity_model
        self.model = activity_model.DirectoryAndExtraModel(self.activity_dir)
        self.treeview.set_model(self.model)
        self.treeview.get_selection().connect("changed", self.selection_cb)
        self.logview = logviewer.LogMinder(self,name.split(".")[0])
        self._logger.info('done opening %s' % activity_dir)

        
    def refresh_files(self):
        self.model = activity_model.DirectoryAndExtraModel(self.activity_dir)
        self.treeview.set_model(self.model)

    def load_file(self, fullPath):
        filename = fullPath[len(self.activity_dir):]
        query = {'activity':SERVICE, 'source':fullPath}
        objects, count = datastore.find(query, sorting=['mtime'])
        if not count: # no objects found
            import mimetypes
            mime_type = mimetypes.guess_type(filename)[0]
            if mime_type is None:
                mime_type = ''
            dso = datastore.create()
            dso.metadata['title'] = '%s: %s' % (self.metadata['title'], filename)
            dso.metadata['activity'] = SERVICE
            dso.metadata['mime_type'] = mime_type
            dso.metadata['icon-color'] = profile.get_color().to_string()
            dso.metadata['filename'] = filename
            dso.metadata['source'] = fullPath
            dso.file_path = fullPath
        else:
            for object in objects:
                self._logger.info(str(object.metadata['mtime']))
            dso = objects[-1]
            dso.metadata['filename'] = dso.metadata['source'][len(self.activity_dir):]
        self.editor.load_object(dso)

    def selection_cb(self, column):
        if self.numb:
            #Choosing in the notebook selects in the list, and vice versa. Avoid infinite recursion.
            return
        self.save()
        path = activity_model.get_selected_file_path(self.treeview)
        self._logger.debug("clicked! %s" % path)
        if path and not os.path.isdir(path):
            self.numb = True
            self.load_file(path)
            self.numb = False
    
    def write_file(self, file_path):
        if not self.activity_dir:
            raise NotImplementedError
        self._logger.info('write file %s' % file_path)
        self.editor.save_all()
        filenames = '\x00'.join(self.editor.get_all_filenames())
        self.metadata['source'] = self.activity_dir[:-1]
        f = file(file_path, 'w')
        f.write(filenames)
        f.close()
        self._logger.info(repr(file(file_path).read()))
    
    def read_file(self, file_path):
        self._logger.info('read_file: %s' % file_path)
        if not self.metadata['source']:
            self._show_welcome()
            return
        self.open_activity(self.metadata['source'])
        if not os.path.exists(file_path):
            self._logger.critical('tried to read %s but failed' % file_path)
            return
        for filename in file(file_path).read().split('\x00'):
            if filename:
                self.load_file(filename)
                
    def update_sidebar_to_page(self, page):
        if self.numb:
            #avoid infinite recursion
            return
        if isinstance(page,sourceview_editor.GtkSourceview2Page):
            source = page.object.metadata['source']
            tree_iter = self.model.get_iter_from_filepath(source)
            if tree_iter:
                tree_selection = self.treeview.get_selection()
                tree_selection.unselect_all()
                self.numb = True
                tree_selection.select_iter(tree_iter)
                self.numb = False
  
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

        # make expanded non-drawn visible separator to make the search stuff right-align
        separator = gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        self.insert(separator, -1)
        separator.show()

        # setup the search options
        self._search_entry = iconentry.IconEntry()
        self._search_entry.set_icon_from_name(iconentry.ICON_ENTRY_PRIMARY,
                                              'system-search')
        self._search_entry.connect('activate', self._search_entry_activated_cb)
        self._search_entry.connect('changed', self._search_entry_changed_cb)
        self._search_entry.add_clear_button();
        self._add_widget(self._search_entry, expand=True)

        self._findprev = ToolButton('go-previous')
        self._findprev.set_tooltip(_('Find previous'))
        self.insert(self._findprev, -1)
        self._findprev.show()
        self._findprev.connect('clicked', self._findprev_cb);

        self._findnext = ToolButton('go-next')
        self._findnext.set_tooltip(_('Find next'))
        self.insert(self._findnext, -1)
        self._findnext.show()
        self._findnext.connect('clicked', self._findnext_cb);
                               
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

    def _search_entry_activated_cb(self, entry):
        text = self._search_entry.props.text
        if text:
            self._findnext_cb(None)       

    def _search_entry_changed_cb(self, entry):
        text = self._search_entry.props.text
        if not text:
            self._findprev.set_sensitive(False)
            self._findnext.set_sensitive(False)
        else:
            self._findprev.set_sensitive(True)
            self._findnext.set_sensitive(True)
            self._activity.editor.find_next(text)
            
    def _findprev_cb(self, button):
        text = self._search_entry.props.text
        if text:
            self._activity.editor.find_prev(text)
                        
    def _findnext_cb(self, button):
        text = self._search_entry.props.text
        if text:
            self._activity.editor.find_next(text, False)
            
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
        insert.connect('clicked', self._add_blank_cb)
        
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
        open.set_tooltip(_('Open an external file...'))
        open.connect('clicked', self._open_file_cb)
        open.show()
        
        self.insert(open, -1)
        
    def _add_blank_cb(self, menu):
        chooser = gtk.FileChooserDialog(_('Name your new file...'), 
            self.activity, gtk.FILE_CHOOSER_ACTION_SAVE,
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                    gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        chooser.set_current_folder(self.activity.activity_dir)
        if chooser.run() ==  gtk.RESPONSE_OK:
            filename = chooser.get_filename()
            chooser.destroy()
            if not os.path.exists(filename):
                file(filename, 'w').close()
            self.activity.refresh_files()
        else:
            chooser.destroy()
        del chooser
    
    def _add_dir_cb(self,menu):
        chooser = gtk.FileChooserDialog(_('Name your new directory...'), 
            self.activity, gtk.FILE_CHOOSER_ACTION_CREATE_FOLDER,
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                    gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        chooser.set_current_folder(self.activity.activity_dir)
        if chooser.run() ==  gtk.RESPONSE_OK:
            chooser.destroy()
            self.activity.refresh_files()
        else:
            chooser.destroy()
        del chooser

    def _erase_file_cb(self, menu):
        chooser = gtk.FileChooserDialog(_('Pick the file to erase...'), 
            self.activity, gtk.FILE_CHOOSER_ACTION_OPEN,
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                    gtk.STOCK_DELETE, gtk.RESPONSE_OK))
        chooser.set_current_folder(self.activity.activity_dir)
        if chooser.run() ==  gtk.RESPONSE_OK:
            filename = chooser.get_filename()
            chooser.destroy()
            os.unlink(filename)
            self.activity.refresh_files()
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
                alert.props.title=_('Are you sure you want to erase %s?')%name
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
            self.activity.refresh_files()

    def _open_file_cb(self, button):
        chooser = gtk.FileChooserDialog(_('Pick the file to open...'), self.activity, 
            gtk.FILE_CHOOSER_ACTION_OPEN,
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                    gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        chooser.set_current_folder(self.activity.activity_dir)
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
