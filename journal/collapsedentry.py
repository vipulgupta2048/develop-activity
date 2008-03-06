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
import pango
import json

from sugar.graphics.icon import CanvasIcon
from sugar.graphics.xocolor import XoColor
from sugar.graphics import style
from sugar.datastore import datastore
from sugar.graphics.roundbox import CanvasRoundBox

from keepicon import KeepIcon
import misc

class BuddyList(hippo.CanvasBox):
    def __init__(self, model, width):
        hippo.CanvasBox.__init__(self,
                orientation=hippo.ORIENTATION_HORIZONTAL,
                box_width=width,
                xalign=hippo.ALIGNMENT_START)
        self.set_model(model)

    def set_model(self, model):
        for item in self.get_children():
            self.remove(item)

        for buddy in model[0:3]:
            nick, color = buddy
            icon = CanvasIcon(icon_name='computer-xo',
                              xo_color=XoColor(color),
                              cache=True)
            self.append(icon)

class CollapsedEntry(hippo.CanvasBox):
    __gtype_name__ = 'CollapsedEntry'

    __gsignals__ = {
        'entry-activated': (gobject.SIGNAL_RUN_FIRST,
                            gobject.TYPE_NONE,
                            ([]))
    }

    _DATE_COL_WIDTH     = style.GRID_CELL_SIZE * 3
    _BUDDIES_COL_WIDTH  = style.GRID_CELL_SIZE * 3
    _PROGRESS_COL_WIDTH = style.GRID_CELL_SIZE * 5

    def __init__(self, jobject, allow_resume=True):
        hippo.CanvasBox.__init__(self, spacing=style.DEFAULT_SPACING,
                                 padding_top=style.DEFAULT_PADDING,
                                 padding_bottom=style.DEFAULT_PADDING,
                                 padding_left=style.DEFAULT_PADDING * 2,
                                 padding_right=style.DEFAULT_PADDING * 2,
                                 box_height=style.GRID_CELL_SIZE,
                                 orientation=hippo.ORIENTATION_HORIZONTAL)
        
        self._jobject = None
        self._allow_resume = allow_resume
        self._is_selected = False

        self._frame = CanvasRoundBox()
        self._frame.connect_after('button-release-event', self._frame_button_release_event_cb)
        self.append(self._frame, hippo.PACK_EXPAND)

        self._keep_icon = self._create_keep_icon()
        self._frame.append(self._keep_icon)

        self._icon = self._create_icon()
        self._frame.append(self._icon)

        self._title = self._create_title()
        self._frame.append(self._title, hippo.PACK_EXPAND)

        self._buddies_list = self._create_buddies_list()
        self._frame.append(self._buddies_list)

        self._date = self._create_date()
        self._frame.append(self._date)

        self._resume_button = self._create_resume_button()
        self._frame.append(self._resume_button)
        if not self._allow_resume:
            self._frame.set_child_visible(self._resume_button, False)

        # Progress controls
        self._progress_bar = self._create_progress_bar()
        self._frame.append(self._progress_bar)

        self._cancel_button = self._create_cancel_button()
        self._frame.append(self._cancel_button)

        self.set_jobject(jobject)

    def _create_keep_icon(self):
        keep_icon = KeepIcon(False)
        keep_icon.connect('button-release-event',
                          self._keep_icon_button_release_event_cb)
        return keep_icon
    
    def _create_date(self):
        date = hippo.CanvasText(text='',
                                xalign=hippo.ALIGNMENT_START,
                                font_desc=style.FONT_NORMAL.get_pango_desc(),
                                box_width=self._DATE_COL_WIDTH)
        return date
    
    def _create_icon(self):
        icon = CanvasIcon(size=style.STANDARD_ICON_SIZE, cache=True)
        if self._allow_resume:
            icon.connect_after('button-release-event',
                               self._icon_button_release_event_cb)
        return icon

    def _create_title(self):
        title = hippo.CanvasText(text='',
                                 xalign=hippo.ALIGNMENT_START,
                                 font_desc=style.FONT_BOLD.get_pango_desc(),
                                 size_mode=hippo.CANVAS_SIZE_WRAP_WORD)
        return title

    def _create_buddies_list(self):
        return BuddyList([], self._BUDDIES_COL_WIDTH)

    def _create_resume_button(self):
        button = CanvasIcon(icon_name='activity-start',
                            size=style.SMALL_ICON_SIZE,
                            box_width=style.GRID_CELL_SIZE,
                            fill_color=style.COLOR_BUTTON_GREY.get_svg(),
                            stroke_color=style.COLOR_BUTTON_GREY.get_svg())
        button.connect('button-release-event',
                       self._resume_button_release_event_cb)
        return button

    def _create_progress_bar(self):
        progress_bar = gtk.ProgressBar()
        return hippo.CanvasWidget(widget=progress_bar,
                                  yalign=hippo.ALIGNMENT_CENTER,
                                  box_width=self._PROGRESS_COL_WIDTH)

    def _create_cancel_button(self):
        button = CanvasIcon(icon_name='activity-stop',
                            size=style.SMALL_ICON_SIZE,
                            box_width=style.GRID_CELL_SIZE)
        button.connect('button-release-event', self._cancel_button_release_event_cb)
        return button

    def _decode_buddies(self):
        if self.jobject.metadata.has_key('buddies') and \
           self.jobject.metadata['buddies']:
            # json cannot read unicode strings
            buddies_str = self.jobject.metadata['buddies'].encode('utf8')
            buddies = json.read(buddies_str).values()
        else:
            buddies = []
        return buddies

    def _format_title(self):
        if self.jobject.metadata.has_key('title'):
            return '%s' % self.jobject.metadata['title']
        else:
            return '%s' % _('Untitled')

    def _update_visibility(self):
        in_process = self._is_in_progress()

        self._buddies_list.set_visible(not in_process)
        self._date.set_visible(not in_process)
        self._resume_button.set_visible(not in_process and self._allow_resume)

        self._progress_bar.set_visible(in_process)
        self._cancel_button.set_visible(in_process)

    def _update_color(self):
        if self._is_in_progress():
            self._frame.props.background_color = style.COLOR_WHITE.get_int()
            self._frame.props.border = style.LINE_WIDTH
            self._frame.props.border_color = style.COLOR_TOOLBAR_GREY.get_int()
        else:
            self._frame.props.background_color = style.COLOR_TEXT_FIELD_GREY.get_int()
            self._frame.props.border = 0

    def _is_in_progress(self):
        return self._jobject.metadata.has_key('progress') and \
                int(self._jobject.metadata['progress']) < 100

    def get_keep(self):
        return self._jobject.metadata.has_key('keep') and \
               self._jobject.metadata['keep'] == 1

    def _keep_icon_button_release_event_cb(self, button, event):
        logging.debug('_keep_icon_button_release_event_cb')
        jobject = datastore.get(self._jobject.object_id)
        try:
            if self.get_keep():
                jobject.metadata['keep'] = 0
            else:
                jobject.metadata['keep'] = 1
            datastore.write(jobject, update_mtime=False)
        finally:
            jobject.destroy()

        self._keep_icon.props.keep = self.get_keep()
        self._update_color()
        
        return True

    def _icon_button_release_event_cb(self, button, event):
        logging.debug('_icon_button_release_event_cb')
        self._jobject.resume()
        return True

    def _resume_button_release_event_cb(self, button, event):
        logging.debug('_resume_button_release_event_cb')
        self._jobject.resume()
        return True

    def _cancel_button_release_event_cb(self, button, event):
        logging.debug('_cancel_button_release_event_cb')
        datastore.delete(self._jobject.object_id)
        return True

    def set_selected(self, is_selected):
        self._is_selected = is_selected
        self._update_color()

    def _frame_button_release_event_cb(self, frame, event):
        logging.debug('_frame_button_release_event_cb')
        if not self._is_in_progress():
            self.emit('entry-activated')

    def set_jobject(self, jobject):
        self._jobject = jobject
        self._is_selected = False

        self._keep_icon.props.keep = self.get_keep()

        self._date.props.text = misc.get_date(jobject)

        self._icon.props.file_name = misc.get_icon_name(jobject)
        if jobject.is_activity_bundle():
            self._icon.props.fill_color=style.COLOR_TRANSPARENT.get_svg()
            self._icon.props.stroke_color=style.COLOR_BLACK.get_svg()
            self._title.props.text = self._format_title() + _(' Activity')
        else:    
            if jobject.metadata.has_key('icon-color') and \
                   jobject.metadata['icon-color']:
                self._icon.props.xo_color = XoColor( \
                    jobject.metadata['icon-color'])
            else:
                self._icon.props.xo_color = None        
            self._title.props.text = self._format_title()

        self._buddies_list.set_model(self._decode_buddies())

        if jobject.metadata.has_key('progress'):
            self._progress_bar.props.widget.props.fraction = \
                int(jobject.metadata['progress']) / 100.0

        self._update_visibility()
        self._update_color()

    def get_jobject(self):
        return self._jobject

    jobject = property(get_jobject, set_jobject)

    def update_date(self):
        self._date.props.text = misc.get_date(self._jobject)

