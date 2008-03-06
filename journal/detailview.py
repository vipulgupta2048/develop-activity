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

import logging
from gettext import gettext as _

import gobject
import gtk
import hippo

from sugar.graphics import style
from sugar.graphics.icon import CanvasIcon
from sugar.graphics.toolbutton import ToolButton
from sugar.datastore import datastore

from expandedentry import ExpandedEntry
from keepicon import KeepIcon

class DetailView(gtk.VBox):
    def __init__(self):
        gtk.VBox.__init__(self)

        self._jobject = None
        self._expanded_entry = None

        canvas = hippo.Canvas()
        self.pack_start(canvas)
        canvas.show()
        
        self._root = hippo.CanvasBox()
        self._root.props.background_color = style.COLOR_PANEL_GREY.get_int()
        canvas.set_root(self._root)

    def _fav_icon_activated_cb(self, fav_icon):
        keep = not self._expanded_entry.get_keep()
        self._expanded_entry.set_keep(keep)
        fav_icon.props.keep = keep

    def _update_view(self):
        if self._expanded_entry:
            self._root.remove(self._expanded_entry)

            # Work around pygobject bug #479227
            self._expanded_entry.remove_all()
            import gc
            gc.collect()
        if self._jobject:
            self._expanded_entry = ExpandedEntry(self._jobject.object_id)
            self._root.append(self._expanded_entry, hippo.PACK_EXPAND)

    def set_jobject(self, jobject):
        self._jobject = jobject
        self._update_view()

    def refresh(self):
        logging.debug('DetailView.refresh')
        if self._jobject:
            self._jobject = datastore.get(self._jobject.object_id)
            self._update_view()
