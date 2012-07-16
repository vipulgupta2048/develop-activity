# -*- coding: utf-8 -*-

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

import gtk
import gobject

from gettext import gettext as _


class SymbolsTree(gtk.TreeView):

    __gsignals__ = {'symbol-selected': (gobject.SIGNAL_RUN_FIRST, None, [int])}

    def __init__(self):
        gtk.TreeView.__init__(self)

        self._model = gtk.TreeStore(str, str)
        self.set_model(self._model)

        column = gtk.TreeViewColumn('Symbols')
        name_cell = gtk.CellRendererText()
        column.pack_start(name_cell, True)
        column.add_attribute(name_cell, 'text', 0)

        line_cell = gtk.CellRendererText()
        line_cell.props.visible = False
        column.pack_start(line_cell, False)
        column.add_attribute(line_cell, 'text', 1)
        self.append_column(column)

        self.connect('cursor-changed', self._symbol_selected_cb)

    def _add_class(self, name, line, create_attrs=False, create_methods=False):
        parent = self._model.append(self._classes, (name, line))
        _return = [parent]
        if create_attrs:
            attributes = self._model.append(parent, (_('Attributes'), 0))
            _return.append(attributes)
        if create_methods:
            methods = self._model.append(parent, (_('Methods'), 0))
            _return.append(methods)
        return _return

    def _add_method(self, name, line, parent=None):
        if not parent:
            self._model.append(self._methods, (name, line))
        else:
            self._model.append(parent, (name, line))

    def _add_attribute(self, name, line, parent=None):
        if not parent:
            self._model.append(self._attributes, (name, line))
        else:
            self._model.append(parent, (name, line))

    def _symbol_selected_cb(self, widget):
        selection = self.get_selection()
        model, _iter = selection.get_selected()
        line = int(model.get_value(_iter, 1))
        if line is 0:
            return
        self.emit('symbol-selected', line)

    def load_symbols(self, data):
        self._model.clear()
        if 'attributes' in data:
            self._attributes = self._model.append(None, (_('Attributes'), 0))
            attributes = data['attributes']
            for attribute in attributes.keys():
                self._add_attribute(attribute, attributes[attribute])

        if 'methods' in data:
            methods = data['methods']
            self._methods = self._model.append(None, (_('Methods'), 0))
            for method in methods.keys():
                self._add_method(method, methods[method])

        if 'classes' in data:
            classes = data['classes']
            self._classes = self._model.append(None, (_('Classes'), 0))
            for _class in classes.keys():
                class_dict = classes[_class][1]
                parents = self._add_class(_class, classes[_class][0],
                                         'attributes' in class_dict,
                                         'functions' in class_dict)
                for key in class_dict.keys():
                    if key == 'attributes':
                        attributes_dict = class_dict[key]
                        for attribute in attributes_dict.keys():
                            self._add_attribute(attribute,
                                               attributes_dict[attribute],
                                               parents[1])
                    if key == 'functions':
                        methods_dict = class_dict[key]
                        for method in methods_dict:
                            self._add_method(method,
                                            methods_dict[method],
                                            parents[2])
