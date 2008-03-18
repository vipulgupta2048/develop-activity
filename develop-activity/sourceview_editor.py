# Copyright 2008 Paul Swartz
#
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

import gtk, gobject
import pango
from sugar.graphics import notebook
import gtksourceview2
import os.path
import re

class S_WHERE:
    selection, file, multifile = range(3) #an enum
    
class GtkSourceview2Editor(notebook.Notebook):
    __gsignals__ = {
        'changed': (gobject.SIGNAL_RUN_FIRST, None, [])
    }

    def __init__(self, activity):
        notebook.Notebook.__init__(self, can_close_tabs=True)
        self.activity = activity
        self.set_size_request(900, 350)
        self.connect('page-removed', self._page_removed_cb)
        self.connect('switch-page', self._switch_page_cb)

    def _page_removed_cb(self, notebook, page, n):
        page.remove()
    
    def _switch_page_cb(self, notebook, page_gptr, page_num):
        self.activity.update_sidebar_to_page(self.get_nth_page(page_num))
        
    def set_to_page_like(self,eq_to_page):
        for n in range(self.get_n_pages()):
            page = self.get_nth_page(n)
            if page == eq_to_page:
                self.set_current_page(n)
                return True
        return False
        
    def load_object(self, dsObject):
        if self.set_to_page_like(dsObject.metadata['source']):
            return
        page = GtkSourceview2Page(dsObject)
        label = dsObject.metadata['filename']
        page.text_buffer.connect('changed', self._changed_cb)
        self.add_page(label, page)
        self.set_current_page(-1)
        self._changed_cb(page.text_buffer)

    def _changed_cb(self, buffer):
        if not buffer.can_undo():
            buffer.set_modified(False)
        elif not self.activity.dirty:
            self.activity.set_dirty(True)
        self.emit('changed')

    def _get_page(self):
        n = self.get_current_page()
        return self.get_nth_page(n)
  
    def can_undo_redo(self):
        page = self._get_page()
        if page is None:
            return (False, False)
        else:
            return page.can_undo_redo()

    def undo(self):
        page = self._get_page()
        if page:
            page.undo()

    def redo(self):
        page = self._get_page()
        if page:
            page.redo()

    def copy(self):
        page = self._get_page()
        if page:
            page.copy()

    def paste(self):
        page = self._get_page()
        if page:
            page.paste()

    def replace(self, ftext, rtext, s_where, use_regex, replace_all):
        success = False
        if use_regex and issubclass(type(ftext),basestring):
            ftext = re.compile(ftext)
        multifile = s_where == S_WHERE.multifile
        if multifile and replace_all:
            for n in range(self.get_n_pages()):
                page = self.get_nth_page(n)
                success |= success or page.replace(self, ftext, rtext, 
                                false, use_regex, replace_all)
            return success
        
        page = self._get_page()
        if page:
            selection = s_where == S_WHERE.selection
            success = page.replace(self, ftext, rtext, selection, 
                    use_regex, replace_all)
            if replace_all:
                return success
            elif not selection:
                self.find_next(ftext,stay=False,multifile=multifile, 
                        selection=selection,use_regex=use_regex,page=page)
                return success
            else:
                #for replace-in-selection, leave selection unmodified
                return success
        
    def find_next(self, ftext, stay=True, multifile=False, selection=False, 
                use_regex = False, page=None):
        if page==None:
            page = self._get_page()
        if page:
            if use_regex and issubclass(type(ftext),basestring):
                ftext = re.compile(ftext)
            if page.find_next(ftext,False,selection,use_regex,wrap=not multifile):
                return true
            else:
                if multifile:
                    current_page = self.get_current_page()
                    n_pages = self.get_n_pages() 
                    for i in range(n_pages):
                        page = self.get_nth_page((current_page + i) % n_pages)
                        if isinstance(page,GtkSourceview2Page):
                            if page.find_next(ftext,False,selection, use_regex,wrap = True):
                                self.set_current_page((current_page + i) % n_pages)
                                return True
                    return False
                else:
                    return False #first file failed, not multifile
        else:
            return False #no open pages

    def find_prev(self, text):
        page = self._get_page()
        if page:
            return page.find_prev(text)

    def get_all_filenames(self):
        for i in range(self.get_n_pages()):
            page = self.get_nth_page(i)
            if isinstance(page,GtkSourceview2Page):
                yield page.object.metadata['filename']

    def save_all(self):
        self.activity._logger.info('save all %i' % self.get_n_pages())
        for i in range(self.get_n_pages()):
            page = self.get_nth_page(i)
            if isinstance(page,GtkSourceview2Page):
                self.activity._logger.info('%s' % page.object.metadata['filename'])
                page.save()
    
    def reroot(self,olddir, newdir):
        self.activity._logger.info('reroot from %s to %s' % (olddir,newdir))
        for i in range(self.get_n_pages()):
            page = self.get_nth_page(i)
            if isinstance(page,GtkSourceview2Page):
                if page.reroot(olddir, newdir): 
                    self.activity._logger.info('rerooting page %s failed' % 
                            page.object.file_path)
                else:
                    self.activity._logger.info('rerooting page %s succeeded' % 
                            page.object.file_path)
        

class GtkSourceview2Page(gtk.ScrolledWindow):

    def __init__(self, dsObject):
        """
        Do any initialization here.
        """
        gtk.ScrolledWindow.__init__(self)

        self.object = dsObject

        self.text_buffer = gtksourceview2.Buffer()
        self.text_view = gtksourceview2.View(self.text_buffer)
       
        self.text_view.set_size_request(900, 350)
        self.text_view.set_editable(True)
        self.text_view.set_cursor_visible(True)
        self.text_view.set_show_line_numbers(True)
        self.text_view.set_insert_spaces_instead_of_tabs(True)
        if hasattr(self.text_view, 'set_tabs_width'):
            self.text_view.set_tabs_width(4)
        else:
            self.text_view.set_tab_width(4)
        self.text_view.set_auto_indent(True)

        self.text_view.set_wrap_mode(gtk.WRAP_CHAR)
        self.text_view.modify_font(pango.FontDescription("Monospace 9"))

        # We could change the color theme here, if we want to.
        #mgr = gtksourceview2.style_manager_get_default()
        #style_scheme = mgr.get_scheme('kate')
        #self.text_buffer.set_style_scheme(style_scheme)

        self.set_policy(gtk.POLICY_AUTOMATIC,
                      gtk.POLICY_AUTOMATIC)
        self.add(self.text_view)
        self.text_view.show()
        self.load_text()
        self.show()

    def __del__(self):
        self.object.destroy()
        del self.object

    def load_text(self, offset=None):
        """
        Load the text, and optionally scroll to the given offset in the file.
        """
        self.text_buffer.begin_not_undoable_action()
        _file = file(self.object.file_path)
        self.text_buffer.set_text(_file.read())
        _file.close()
        if offset is not None:
            self._scroll_to_offset(offset)
        
        if hasattr(self.text_buffer, 'set_highlight'):
            self.text_buffer.set_highlight(False)
        else:
            self.text_buffer.set_highlight_syntax(False)
        mime_type = self.object.metadata.get('mime_type', '')
        if mime_type:
            lang_manager = gtksourceview2.language_manager_get_default()
            if hasattr(lang_manager, 'list_languages'):
               langs = lang_manager.list_languages()
            else:
                lang_ids = lang_manager.get_language_ids()
                langs = [lang_manager.get_language(i) for i in lang_ids]
            for lang in langs:
                for m in lang.get_mime_types():
                    if m == mime_type:
                        self.text_buffer.set_language(lang)
                        if hasattr(self.text_buffer, 'set_highlight'):
                            self.text_buffer.set_highlight(True)
                        else:
                            self.text_buffer.set_highlight_syntax(True)
        self.text_buffer.end_not_undoable_action()
        self.text_buffer.set_modified(False)
        self.text_view.grab_focus()
   
    def remove(self):
        self.save()
   
    def save(self):
        #from sugar.datastore import datastore
        names = (self.object.file_path,)#, self.object.metadata['source']))
        text = self.get_text()
        for name in names:
            _file = file(name, 'w')
            try:
                _file.write(text)
            except (IOError, OSError):
                pass
            _file.close()
        # I wanted to actually use datastore objects,
        # but I couldn't think of how to do resuming
        # properly without a hack in develop_app.  I
        # still may do that hack, but not right now.    
        #datastore.write(self.object, transfer_ownership=True)

    def get_text(self):
        """
        Return the text that's currently being edited.
        """
        start, end = self.text_buffer.get_bounds()
        return self.text_buffer.get_text(start, end)
        
    def get_offset(self):
        """
        Return the current character position in the currnet file.
        """
        insert = self.text_buffer.get_insert()
        _iter = self.text_buffer.get_iter_at_mark(insert)
        return _iter.get_offset()
    
    def copy(self):
        """
        Copy the currently selected text to the clipboard.
        """
        self.text_buffer.copy_clipboard(gtk.Clipboard())
    
    def paste(self):
        """
        Paste from the clipboard into the current file.
        """
        self.text_buffer.paste_clipboard(gtk.Clipboard(), None, True)
        
    def can_undo_redo(self):
        """
        Returns a two-tuple (can_undo, can_redo) with Booleans of those abilities.
        """
        return (self.text_buffer.can_undo(), self.text_buffer.can_redo())
        
    def undo(self):
        """
        Undo the last change in the file.  If we can't do anything, ignore.
        """
        self.text_buffer.undo()
        
    def redo(self):
        """
        Redo the last change in the file.  If we can't do anything, ignore.
        """
        self.text_buffer.redo()
        
    def _getRtLmatchlist(buffertext,fpat,use_regex,offset):
        if use_regex:
            match = fpat.search(buffertext)
            if match:
                start,end = match.span()
                return (self._getRtLmatchlist(buffertext[end:],fpat,use_regex,offset+end) + 
                        [(start+offset,end+offset,match)]) 
            else:
                return []
        else:
            match = buffertext.rfind(fpat)
            if match >= 0:
                return ([(match+offset,match+offset+len(fpat),None)] + 
                        self._getRtLmatchlist(buffertext[:match],fpat,use_regex,offset))
            else:
                return []
    
    def replace(self, ftext, rtext, selection, 
                    use_regex, replace_all):
        if replace_all:
            result = False
            self.text_buffer.begin_user_action()
            if selection:
                try:
                    selstart, selend = self.text_buffer.get_selection_bounds()
                except ValueError,TypeError:
                    return False
                offsetadd = selstart.getoffset()
                buffertext = self.text_buffer.get_slice(start,end)
            else:
                offsetadd = 0
                buffertext = self.get_text()
            for start, end, match in self._getRtLmatchlist(buffertext,ftext,
                                            use_regex,offsetadd):
                start = self.text_buffer.get_iter_at_offset(start+offsetadd)
                end = self.text_buffer.get_iter_at_offset(end+offsetadd)
                self.text_buffer.delete(start,end)
                self.text_buffer.insert(start, self.makereplace(rtext,match,use_regex))
                result = True
            self.text_buffer.end_user_action()
            return result
        else: #replace, the &find part handled by caller
            try:
                start,end = self.text_buffer.get_selection_bounds()
            except TypeError:
                return False
            match = self._match(ftext,
                        self.text_buffer.get_slice(start,end),
                        use_regex)
            if match:
                self.text_buffer.delete(start, end)
                rtext = self.makereplace(rtext,match,use_regex)
                self.text_buffer.insert(start, rtext)
                return self.text_buffer.set_modified
                
    def makereplace(self, rpat, match, use_regex):
        if use_regex:
            return match.expand(rpat)
        else:
            return rpat
        
    def _find_in(self, text, fpat, offset, use_regex, offset_add = 0):
        if use_regex:
            match = fpat.search(text[offset:])
            if match:
                start,end = match.span
                return (start+offset, end+offset)
            else:
                return ()
        else:
            match = text.find(fpat,offset)
            if match >= 0:
                return (match, match + len(fpat))
            else:
                return ()
            
    def find_next(self, ftext, stay=True, selection=False,use_regex = False, wrap = True):
        """
        Scroll to the next place where the string text appears.
        If stay is True and text is found at the current position, stay where we are.
        """
        if selection:
            try:
                selstart, selend = self.text_buffer.get_selection_bounds()
            except ValueError,TypeError:
                return False
            offsetadd = selstart.getoffset()
            buffertext = self.text_buffer.get_slice(start,end)
            return self._find_in(buffertext,ftext,0,use_regex,offsetadd)
        else:
            offset = self.get_offset() + (not stay) #add 1 if not stay.
            text = self.get_text()
            try:
                start,end = self._find_in(text,ftext,offset,use_regex)
            except ValueError,TypeError:
                #find failed.
                if wrap:
                    try:
                        start,end = self._find_in(text,ftext,offset,use_regex)
                    except ValueError,TypeError:
                        return False
                else:
                    return False
            self._scroll_to_offset(start,end)

    def find_prev(self, text):
        """
        Scroll to the previous place where the string text appears.
        """
        offset = self.get_offset()
        new_offset = self.get_text().rfind(text, 0, offset)
        if new_offset != -1:
            self._scroll_to_offset(new_offset,new_offset + len(text))

    def _scroll_to_offset(self, offset, bound):
        _iter = self.text_buffer.get_iter_at_offset(offset)
        _iter2 = self.text_buffer.get_iter_at_offset(bound)
        self.text_buffer.select_range(_iter,_iter2)
        self.text_view.scroll_mark_onscreen(self.text_buffer.get_insert())
        
    def __eq__(self,other):
        if isinstance(other,GtkSourceview2Page):
            return self.object.metadata['source'] == other.object.metadata['source']
        #elif isinstance(other,type(self.object)):
        #    other = other.metadata['source']
        if isinstance(other,basestring):
            return other == self.object.metadata['source']
        else:
            return False

    def reroot(self,olddir,newdir):
        """Returns False if it works"""
        oldpath = self.object.file_path
        if oldpath.startswith(olddir):
            self.object.file_path = os.path.join(newdir, oldpath[len(olddir):])
            return False
        else:
            return True