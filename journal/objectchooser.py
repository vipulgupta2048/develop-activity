# Copyright (C) 2007, One Laptop Per Child
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

from gettext import gettext as _

import gobject
import gtk

from sugar.graphics import style

from listview import ListView

class ObjectChooser(gtk.Window):

    __gtype_name__ = 'ObjectChooser'

    __gsignals__ = {
        'response': (gobject.SIGNAL_RUN_FIRST,
                     gobject.TYPE_NONE,
                     ([int]))
    }

    def __init__(self, parent=None):
        gtk.Window.__init__(self)
        self.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
        #self.set_decorated(False)

        self._selected_object_id = None

        if parent is not None:
            self.connect('realize', self.__realize_cb, parent)
        self.connect('delete-event', self.__delete_event_cb)
        self.connect('key-press-event', self.__key_press_event_cb)

        vbox = gtk.VBox()
        self.add(vbox)
        vbox.show()

        list_view = ListView(allow_resume=False)
        list_view.connect('entry-activated', self.__entry_activated_cb)
        vbox.pack_start(list_view)
        list_view.show()

        entries_per_screen = self.get_screen().get_height() / style.GRID_CELL_SIZE
        height = (entries_per_screen - 1) * style.GRID_CELL_SIZE
        width = self.get_screen().get_width() * 7 / 8
        self.set_default_size(width, height)

    def __realize_cb(self, chooser, parent):
        self.window.set_transient_for(parent)
        # TODO: Should we disconnect the signal here?

    def __entry_activated_cb(self, list_view, entry):
        self._selected_object_id = entry.jobject.object_id
        self.emit('response', gtk.RESPONSE_ACCEPT)

    def __delete_event_cb(self, chooser, event):
        self.emit('response', gtk.RESPONSE_DELETE_EVENT)

    def __key_press_event_cb(self, widget, event):
        keyname = gtk.gdk.keyval_name(event.keyval)
        if keyname == 'Escape':
            self.emit('response', gtk.RESPONSE_DELETE_EVENT)
        
    def get_selected_object_id(self):
        return self._selected_object_id

