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

import hippo

from sugar.graphics import style

class TagBox(hippo.CanvasBox, hippo.CanvasItem):
    def __init__(self, model):
        hippo.CanvasBox.__init__(self)
        self.props.box_width = style.GRID_CELL_SIZE * 3

        self._model = model
        """
        self.append(hippo.CanvasText(text=_('Add a new tag:'),
                                     xalign=hippo.ALIGNMENT_START,
                                     font_desc=style.FONT_NORMAL.get_pango_desc()))

        self.append(Entry(), hippo.PACK_EXPAND)
        """
