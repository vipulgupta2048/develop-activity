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
import mimetypes
from exceptions import *

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
        
    def load_object(self, fullPath, filename):
        if self.set_to_page_like(fullPath):
            return
        page = GtkSourceview2Page(fullPath)
        label = filename
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
        replaced = False
        if use_regex and issubclass(type(ftext),basestring):
            ftext = re.compile(ftext)
        multifile = (s_where == S_WHERE.multifile)
        if multifile and replace_all:
            for n in range(self.get_n_pages()):
                page = self.get_nth_page(n)
                replaced = page.replace(ftext, rtext, 
                                False, use_regex, replace_all) or replaced
            return (replaced, False) #not found-again
        
        page = self._get_page()
        if page:
            selection = s_where == S_WHERE.selection
            replaced = page.replace(ftext, rtext, selection, 
                    use_regex, replace_all)
            if replace_all:
                return (replaced, False)
            elif not selection:
                found = self.find_next(ftext,stay=False,multifile=multifile, 
                        selection=selection,use_regex=use_regex,page=page)
                return (replaced, found)
            else:
                #for replace-in-selection, leave selection unmodified
                return (replaced, replaced)
        
    def find_next(self, ftext, stay=True, multifile=False, selection=False, 
                use_regex = False, page=None, forward = True):
        if page==None:
            page = self._get_page()
        if page:
            if use_regex and issubclass(type(ftext),basestring):
                ftext = re.compile(ftext)
            if page.find_next(ftext,stay,selection,use_regex,wrap=not multifile,forward=forward):
                return True
            else:
                if multifile:
                    current_page = self.get_current_page()
                    n_pages = self.get_n_pages() 
                    for i in range(1,n_pages):
                        page = self.get_nth_page((current_page + i) % n_pages)
                        if isinstance(page,SearchablePage):
                            if page.find_next(ftext,stay,selection, use_regex,
                                        wrap = True,forward=forward):
                                self.set_current_page((current_page + i) % 
                                        n_pages)
                                return True
                    return False
                else:
                    return False #first file failed, not multifile
        else:
            return False #no open pages

    def get_all_filenames(self):
        for i in range(self.get_n_pages()):
            page = self.get_nth_page(i)
            if isinstance(page,GtkSourceview2Page):
                yield page.fullPath

    def save_all(self):
        self.activity._logger.info('save all %i' % self.get_n_pages())
        if self.activity._foreign_dir:
            self.activity._logger.info('save all aborting, still viewing in place')
            return
        for i in range(self.get_n_pages()):
            page = self.get_nth_page(i)
            if isinstance(page,GtkSourceview2Page):
                self.activity._logger.info('%s' % page.fullPath)
                page.save()
    
    def reroot(self,olddir, newdir):
        self.activity._logger.info('reroot from %s to %s' % (olddir,newdir))
        for i in range(self.get_n_pages()):
            page = self.get_nth_page(i)
            if isinstance(page,GtkSourceview2Page):
                if page.reroot(olddir, newdir): 
                    self.activity._logger.info('rerooting page %s failed' % 
                            page.fullPath)
                else:
                    self.activity._logger.info('rerooting page %s succeeded' % 
                            page.fullPath)
        
    def get_selected(self):
        return self._get_page().get_selected()

class SearchablePage(gtk.ScrolledWindow):
    def get_selected(self):
        start,end = self.text_buffer.get_selection_bounds()
        return self.text_buffer.get_slice(start,end)
        
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
        
    def _getMatches(self,buffertext,fpat,use_regex,offset):
        if use_regex:
            while True:
                match = fpat.search(buffertext)
                if match:
                    start,end = match.span()
                    yield (start+offset,end+offset,match)
                else:
                    return
                buffertext, offset = buffertext[end:],offset+end
        else:
            while True:
                match = buffertext.find(fpat)
                if match >= 0:
                    end = match+len(fpat)
                    yield (offset+match,offset + end,None)
                else:
                    return
                buffertext, offset = buffertext[end:], offset + end

    def _match(self, pattern, text, use_regex):
        if use_regex:
            return pattern.match(text)
        else:
            return pattern == text
    
    def _find_in(self, text, fpat, offset, use_regex, offset_add = 0, 
            forward = True):
        if forward:
            matches = self._getMatches(text[offset:],fpat,use_regex,
                    offset+offset_add)
            try:
                return matches.next()
            except StopIteration:
                return ()
        else:
            if offset != 0:
                text = text[:offset]
            matches = list(self._getMatches(text,fpat,use_regex,
                    offset_add))
            if matches:
                return matches[-1]
            else:
                return ()
            
    def find_next(self, ftext, stay=True, selection=False, use_regex=False, 
            wrap=True, forward=True):
        """
        Scroll to the next place where the string text appears.
        If stay is True and text is found at the current position, stay where we are.
        """
        if selection:
            print "find in selection"
            try:
                selstart, selend = self.text_buffer.get_selection_bounds()
            except (ValueError,TypeError):
                return False
            offsetadd = selstart.get_offset()
            buffertext = self.text_buffer.get_slice(selstart,selend)
            print buffertext
            try:
                start, end, match = self._find_in(buffertext,ftext,0,use_regex,
                        offsetadd,forward)
            except (ValueError,TypeError):
                return False
        else:
            offset = self.get_offset() + (not stay) #add 1 if not stay.
            text = self.get_text()
            try:
                start,end,match = self._find_in(text,ftext,offset,
                            use_regex,0,forward)
            except (ValueError,TypeError):
                #find failed.
                if wrap:
                    try:
                        start,end,match = self._find_in(text,ftext,0,
                                    use_regex,0,forward)
                    except (ValueError,TypeError):
                        return False
                else:
                    return False
        self._scroll_to_offset(start,end)
        return True

    def _scroll_to_offset(self, offset, bound):
        _iter = self.text_buffer.get_iter_at_offset(offset)
        _iter2 = self.text_buffer.get_iter_at_offset(bound)
        self.text_buffer.select_range(_iter,_iter2)
        self.text_view.scroll_mark_onscreen(self.text_buffer.get_insert())
        
    def __eq__(self,other):
        if isinstance(other,GtkSourceview2Page):
            return self.fullPath == other.fullPath
        #elif isinstance(other,type(self.fullPath)):
        #    other = other.metadata['source']
        if isinstance(other,basestring):
            return other == self.fullPath
        else:
            return False

class GtkSourceview2Page(SearchablePage):

    def __init__(self, fullPath):
        """
        Do any initialization here.
        """
        gtk.ScrolledWindow.__init__(self)

        self.fullPath = fullPath

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

    def load_text(self, offset=None):
        """
        Load the text, and optionally scroll to the given offset in the file.
        """
        self.text_buffer.begin_not_undoable_action()
        _file = file(self.fullPath)
        self.text_buffer.set_text(_file.read())
        _file.close()
        if offset is not None:
            self._scroll_to_offset(offset)
        
        if hasattr(self.text_buffer, 'set_highlight'):
            self.text_buffer.set_highlight(False)
        else:
            self.text_buffer.set_highlight_syntax(False)
        mime_type = mimetypes.guess_type(self.fullPath)[0]
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
        if self.text_buffer.can_undo(): #only save if there's something to save
            #note: the above is a hack. If activity._foreign_dir, we should not
            #save. currently, the above is never true when that is. This hack
            #is because we're not keeping a pointer to the activity here.
            text = self.get_text()
            _file = file(self.fullPath, 'w')
            try:
                _file.write(text)
            except (IOError, OSError):
                pass
            _file.close()

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
            
    def replace(self, ftext, rtext, selection, 
                    use_regex, replace_all):
        """returns true if replaced (succeeded)"""
        if replace_all or selection:
            result = False
            if selection:
                try:
                    selstart, selend = self.text_buffer.get_selection_bounds()
                except (ValueError,TypeError):
                    return False
                offsetadd = selstart.get_offset()
                buffertext = self.text_buffer.get_slice(selstart,selend)
            else:
                offsetadd = 0
                buffertext = self.get_text()
            results = list(self._getMatches(buffertext,ftext,
                                            use_regex,offsetadd))
            if not replace_all:
                results = [results[0]]
            else:
                results.reverse() #replace right-to-left so that 
                                #unreplaced indexes remain valid.
            self.text_buffer.begin_user_action()
            for start, end, match in results:
                start = self.text_buffer.get_iter_at_offset(start)
                end = self.text_buffer.get_iter_at_offset(end)
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
                return True
            else:
                return False
                
    def makereplace(self, rpat, match, use_regex):
        if use_regex:
            return match.expand(rpat)
        else:
            return rpat
        
    def reroot(self,olddir,newdir):
        """Returns False if it works"""
        oldpath = self.fullPath
        if oldpath.startswith(olddir):
            self.fullPath = os.path.join(newdir, oldpath[len(olddir):])
            return False
        else:
            return True