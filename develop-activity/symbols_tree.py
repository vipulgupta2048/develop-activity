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

from gi.repository import Gtk
from gi.repository import GdkPixbuf
from gi.repository import GObject


class SymbolsTree(Gtk.TreeView):

    __gsignals__ = {'symbol-selected': (GObject.SignalFlags.RUN_FIRST, None, [int])}

    def __init__(self):
        GObject.GObject.__init__(self)

        self._model = Gtk.TreeStore(GdkPixbuf.Pixbuf, str, int)
        self.set_model(self._model)

        column = Gtk.TreeViewColumn('Symbols')
        icon_cell = Gtk.CellRendererPixbuf()
        column.pack_start(icon_cell, False)
        column.add_attribute(icon_cell, 'pixbuf', 0)

        name_cell = Gtk.CellRendererText()
        column.pack_start(name_cell, True)
        column.add_attribute(name_cell, 'text', 1)

        line_cell = Gtk.CellRendererText()
        line_cell.props.visible = False
        column.pack_start(line_cell, False)
        column.add_attribute(line_cell, 'text', 2)
        self.append_column(column)

        self.connect('cursor-changed', self._symbol_selected_cb)

    def _add_class(self, name, line):
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size('icons/class.png', 24,
                                                      24)
        parent = self._model.append(None, (pixbuf, name, line))
        return parent

    def _add_method(self, name, line, parent=None):
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size('icons/function.png',
                                                      24, 24)
        self._model.append(parent, (pixbuf, name, line))

    def _add_attribute(self, name, line, parent=None):
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size('icons/attribute.png',
                                                      24, 24)
        self._model.append(parent, (pixbuf, name, line))

    def _symbol_selected_cb(self, widget):
        selection = self.get_selection()
        model, iter = selection.get_selected()
        if iter is not None:
            line = model.get_value(iter, 2)
            if line is 0:
                return
            self.emit('symbol-selected', line)

    def load_symbols(self, data):
        self._model.clear()
        if 'attributes' in data:
            attributes = data['attributes']
            for attribute in attributes.keys():
                self._add_attribute(attribute, attributes[attribute])

        if 'methods' in data:
            methods = data['methods']
            for method in methods.keys():
                self._add_method(method, methods[method])

        if 'classes' in data:
            classes = data['classes']
            for _class in classes.keys():
                class_dict = classes[_class][1]
                parent = self._add_class(_class, classes[_class][0])
                for key in class_dict.keys():
                    if key == 'attributes':
                        attributes_dict = class_dict[key]
                        for attribute in attributes_dict.keys():
                            self._add_attribute(attribute,
                                                attributes_dict[attribute],
                                                parent)
                    if key == 'functions':
                        methods_dict = class_dict[key]
                        for method in methods_dict:
                            self._add_method(method,
                                             methods_dict[method],
                                             parent)
