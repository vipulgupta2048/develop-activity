# Copyright (C) 2006, Red Hat, Inc.
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

import gobject

from sugar.graphics.icon import CanvasIcon
from sugar.graphics import style
from sugar import profile

class KeepIcon(CanvasIcon):
    __gproperties__ = {
        'keep' : (bool, None, None, False,
                  gobject.PARAM_READWRITE)
    }

    def __init__(self, keep):
        CanvasIcon.__init__(self, icon_name='emblem-favorite',
                            box_width=style.GRID_CELL_SIZE,
                            size=0.75*style.STANDARD_ICON_SIZE)
        self._keep = None
        self._set_keep(keep)

    def _set_keep(self, keep):
        if keep == self._keep:
            return

        self._keep = keep
        if keep:
            self.props.xo_color = profile.get_color()
        else:
            self.props.stroke_color = style.COLOR_BUTTON_GREY.get_svg()
            self.props.fill_color = style.COLOR_WHITE.get_svg()

    def do_set_property(self, pspec, value):
        if pspec.name == 'keep':
            self._set_keep(value)
        else:
            CanvasIcon.do_set_property(self, pspec, value)

    def do_get_property(self, pspec):
        if pspec.name == 'keep':
            return self._keep
        else:
            return CanvasIcon.do_get_property(self, pspec)

