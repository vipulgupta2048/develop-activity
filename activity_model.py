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
import os, os.path
import logging
unwantedPaths = [
    '.*', # hidden files
    '*~', # emacs backups
    '*.pyc', # compiled python
    'CVS', # CVS repository info
    ]

def _filterNodes(nodes):
    for node in nodes:
        import fnmatch
        matched = False
        for path in unwantedPaths:
            if fnmatch.fnmatch(node.filename, path):
                matched = True
                break
        if not matched:
            yield node
            
class ActivityModel(gtk.GenericTreeModel):

    columns = (gobject.TYPE_PYOBJECT, gobject.TYPE_STRING)
    
    def __init__(self, root):
        self.root = root
        self.refresh()
        gtk.GenericTreeModel.__init__(self)
    
    def refresh(self):
        self.files = list(_filterNodes(ActivityNode(filename, self, None) for filename in sorted(os.listdir(self.root))))

    def on_get_flags(self):
        return 0
    
    def on_get_n_columns(self):
        return len(self.columns)
    
    def on_get_column_type(self, n):
        return self.columns[n]
    
    def on_get_iter(self, path):
        x = self.files
        for part in path:
            x = x[part]
        return x
    
    def on_get_path(self, rowref):
        return rowref.getPath()
    
    def on_get_value(self, rowref, n):
        if n == 0:
            return {'name': rowref.filename,
                    'path': rowref.path}
        else:
            return rowref.filename
    
    def on_iter_next(self, rowref):
        if rowref.parent is not None:
            files = rowref.parent
        else:
            files = self.files
        index = files.index(rowref) + 1
        if index < len(files):
            return files[index]
    
    def on_iter_has_child(self, rowref):
        if rowref is not None:
            return rowref.isDirectory
        else:
            return bool(len(self.files))
    
    def on_iter_n_chilren(self, rowref):
        logging.critical('n children: %s' % rowref)
        if rowref is not None:
            if rowref.isDirectory:
                logging.critical('res: %i' % len(rowref))
                return len(rowref)
            else:
                return
        else:
            return len(self.files)
    
    def on_iter_nth_child(self, rowref, n):
        if rowref is not None:
            if not rowref.isDirectory:
                return
            files = rowref
        else:
            files = self.files
        if n < len(files):
            return files[n]
        
    def on_iter_parent(self, child):
        return child.parent
                 
    def on_iter_children(self, rowref):
        if rowref is not None:
            if rowref.isDirectory:
                return rowref[0]
            else:
                return
        else:
            return self.files[0]
            
class ActivityNode(object):

    def __init__(self, filename, model, parent):
        self.filename = filename
        self.model = model
        if parent is not None:
            self.path = os.path.join(parent.path, filename)
        else:
            self.path = os.path.join(model.root, filename)
        self.parent = parent
        self.isDirectory = os.path.isdir(self.path)
        self._files = None
    
    def _get_files(self):
        if not self.isDirectory:
            return None
        if self._files is None:
            files = sorted(os.listdir(self.path))
            self._files = list(_filterNodes(ActivityNode(filename, self.model, self) for filename in files))
        return self._files
    files = property(_get_files)
    
    def __eq__(self, other):
        if not isinstance(other, ActivityNode):
            return False
        return self.path == other.path
        
    def __len__(self):
        return len(self.files)
    
    def index(self, item):
        return self.files.index(item)
            
    def __getitem__(self, n):
        return self.files[n]

    def getPath(self):
        if self.parent is None:
            return (self.model.files.index(self),)
        parentPath = self.parent.getPath()
        return parentPath + (self.parent.files.index(self),)
    
    def __hash__(self):
        return hash(self.path)

    def __str__(self):
        return '<ActivityNode %s>' % self.path
        
    __repr__ = __str__
