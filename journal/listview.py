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

import os
import logging
import traceback
import sys

import hippo
import gobject
import gtk

from sugar.activity import activity
from sugar.datastore import datastore
from sugar.graphics import style
from sugar.graphics.icon import CanvasIcon

from collapsedentry import CollapsedEntry
import query

class ListView(gtk.HBox):
    __gtype_name__ = 'ListView'

    __gproperties__ = {
        'expanded'       : (bool, None, None, False,
                            gobject.PARAM_READWRITE)
    }

    __gsignals__ = {
        'entry-activated': (gobject.SIGNAL_RUN_FIRST,
                           gobject.TYPE_NONE,
                           ([object]))
    }

    def __init__(self, allow_resume=True):
        self._expanded = False
        self._allow_resume = allow_resume
        self._query = {}
        self._result_set = None
        self._entries = []
        self._page_size = 0
        self._last_value = -1
        self._reflow_sid = 0

        gtk.HBox.__init__(self)
        self.set_flags(gtk.HAS_FOCUS|gtk.CAN_FOCUS)
        self.connect('key-press-event', self._key_press_event_cb)

        self._box = hippo.CanvasBox(
                        orientation=hippo.ORIENTATION_VERTICAL,
                        background_color=style.COLOR_WHITE.get_int())

        canvas = hippo.Canvas()
        canvas.set_root(self._box)

        self.pack_start(canvas)
        canvas.show()

        self._vadjustment = gtk.Adjustment(value=0, lower=0, upper=0, 
                                           step_incr=1, page_incr=0, page_size=0)
        self._vadjustment.connect('value-changed', self._vadjustment_value_changed_cb)
        self._vadjustment.connect('changed', self._vadjustment_changed_cb)

        self._vscrollbar = gtk.VScrollbar(self._vadjustment)
        self.pack_end(self._vscrollbar, expand=False, fill=False)
        self._vscrollbar.show()
        
        self.connect('scroll-event', self._scroll_event_cb)

        # DND stuff
        self._pressed_button = None
        self._press_start_x = None
        self._press_start_y = None
        self._last_clicked_entry = None
        canvas.drag_source_set(0, [], 0)
        canvas.add_events(gtk.gdk.BUTTON_PRESS_MASK |
                          gtk.gdk.POINTER_MOTION_HINT_MASK)
        canvas.connect("motion_notify_event",
                       self._canvas_motion_notify_event_cb)
        canvas.connect("button_press_event",
                       self._canvas_button_press_event_cb)
        canvas.connect("drag_end", self._drag_end_cb)
        canvas.connect("drag_data_get", self._drag_data_get_cb)

    def _vadjustment_changed_cb(self, vadjustment):
        logging.debug('_vadjustment_changed_cb:\n \t%r\n \t%r\n \t%r\n \t%r\n \t%r\n' % \
                      (vadjustment.props.lower, vadjustment.props.page_increment, 
                      vadjustment.props.page_size, vadjustment.props.step_increment,
                      vadjustment.props.upper))
        if vadjustment.props.upper > self._page_size:
            self._vscrollbar.show()
        else:
            self._vscrollbar.hide()

    def _vadjustment_value_changed_cb(self, vadjustment):
        gobject.idle_add(self._do_scroll)

    def _do_scroll(self, force=False):
        import time
        t = time.time()

        value = int(self._vadjustment.props.value)

        if value == self._last_value and not force:
            return
        self._last_value = value

        self._result_set.seek(value)
        jobjects = self._result_set.read(self._page_size)

        if self._result_set.length != self._vadjustment.props.upper:
            self._vadjustment.props.upper = self._result_set.length
            self._vadjustment.changed()

        self._refresh_view(jobjects)
        
        logging.debug('_do_scroll %r %r\n' % (value, (time.time() - t)))
        
        return False

    def _refresh_view(self, jobjects):
        # Refresh view and create the entries if they don't exist yet.
        for i in range(0, self._page_size):
            try:
                if i < len(jobjects):
                    if i >= len(self._entries):
                        entry = CollapsedEntry(jobjects[i], self._allow_resume)
                        entry.connect('entry-activated',
                                      self._entry_activated_cb)
                        self._box.append(entry)
                        self._entries.append(entry)
                    else:
                        entry = self._entries[i]
                        entry.jobject = jobjects[i]
                        entry.set_visible(True)
                elif i < len(self._entries):
                        entry = self._entries[i]
                        entry.set_visible(False)
            except Exception, e:
                logging.error('Exception while displaying entry:\n' + \
                    ''.join(traceback.format_exception(*sys.exc_info())))

    def update_with_query(self, query):
        logging.debug('ListView.update_with_query')
        self._query = query
        if self._page_size > 0:
            self.refresh()

    def refresh(self):
        if self._result_set:
            self._result_set.destroy()
            del self._result_set
        self._result_set = query.find(self._query)
        self._result_set.connect('modified', self._result_set_modified_cb)
        self._vadjustment.props.upper = self._result_set.length
        self._vadjustment.changed()

        self._vadjustment.props.value = min(self._vadjustment.props.value,
                                            self._result_set.length - self._page_size)
        self._do_scroll(force=True)

    def do_set_property(self, pspec, value):
        if pspec.name == 'expanded':
            if self._expanded != value:
                self._expanded = value
                #self._update()

    def do_get_property(self, pspec):
        if pspec.name == 'expanded':
            return self._expanded

    def _entry_activated_cb(self, entry_view):
        self.emit('entry-activated', entry_view)

    def _scroll_event_cb(self, hbox, event):
        if event.direction == gtk.gdk.SCROLL_UP:
            if self._vadjustment.props.value > self._vadjustment.props.lower:
                self._vadjustment.props.value -= 1
        elif event.direction == gtk.gdk.SCROLL_DOWN:
            max_value = self._result_set.length - self._page_size
            if self._vadjustment.props.value < max_value:
                self._vadjustment.props.value += 1

    def do_focus(self, direction):
        if not self.is_focus():
            self.grab_focus()
            return True
        return False

    def _key_press_event_cb(self, widget, event):
        keyname = gtk.gdk.keyval_name(event.keyval)

        if keyname == 'Up':
            if self._vadjustment.props.value > self._vadjustment.props.lower:
                self._vadjustment.props.value -= 1
        elif keyname == 'Down':
            max_value = self._result_set.length - self._page_size
            if self._vadjustment.props.value < max_value:
                self._vadjustment.props.value += 1
        elif keyname == 'Page_Up' or keyname == 'KP_Page_Up':
            new_position = max(0, self._vadjustment.props.value - self._page_size)
            if new_position != self._vadjustment.props.value:
                self._vadjustment.props.value = new_position
        elif keyname == 'Page_Down' or keyname == 'KP_Page_Down':
            new_position = min(self._result_set.length - self._page_size,
                               self._vadjustment.props.value + self._page_size)
            if new_position != self._vadjustment.props.value:
                self._vadjustment.props.value = new_position
        elif keyname == 'Home' or keyname == 'KP_Home':
            new_position = 0
            if new_position != self._vadjustment.props.value:
                self._vadjustment.props.value = new_position
        elif keyname == 'End' or keyname == 'KP_End':
            new_position = max(0, self._result_set.length - self._page_size)
            if new_position != self._vadjustment.props.value:
                self._vadjustment.props.value = new_position
        else:
            return False

        return True

    def do_size_allocate(self, allocation):
        gtk.HBox.do_size_allocate(self, allocation)
        new_page_size = int(allocation.height / style.GRID_CELL_SIZE)

        logging.debug("do_size_allocate: %r" % new_page_size)
        
        if new_page_size != self._page_size:
            self._page_size = new_page_size
            self._queue_reflow()

    def _queue_reflow(self):
        if not self._reflow_sid:
            self._reflow_sid = gobject.idle_add(self._reflow_idle_cb)

    def _reflow_idle_cb(self):
        self._box.clear()
        self._entries = []

        self._vadjustment.props.page_size = self._page_size
        self._vadjustment.props.page_increment = self._page_size
        self._vadjustment.changed()

        if self._result_set is None:
            self._result_set = query.find(self._query)
            self._result_set.connect('modified', self._result_set_modified_cb)

        max_value = max(0, self._result_set.length - self._page_size)
        if self._vadjustment.props.value > max_value:
            self._vadjustment.props.value = max_value
        else:
            self._do_scroll(force=True)

        self._reflow_sid = 0

    # TODO: Dnd methods. This should be merged somehow inside hippo-canvas.
    def _canvas_motion_notify_event_cb(self, widget, event):
        if not self._pressed_button:
            return True
        
        # if the mouse button is not pressed, no drag should occurr
        if not event.state & gtk.gdk.BUTTON1_MASK:
            self._pressed_button = None
            return True

        logging.debug("motion_notify_event_cb")
                        
        if event.is_hint:
            x, y, state = event.window.get_pointer()
        else:
            x = event.x
            y = event.y
            state = event.state

        if widget.drag_check_threshold(int(self._press_start_x),
                                       int(self._press_start_y),
                                       int(x),
                                       int(y)):
            context = widget.drag_begin([('text/uri-list', 0, 0),
                                         ('journal-object-id', 0, 0)],
                                        gtk.gdk.ACTION_COPY,
                                        1,
                                        event);

        return True

    def _drag_end_cb(self, widget, drag_context):
        logging.debug("drag_end_cb")
        self._pressed_button = None
        self._press_start_x = None
        self._press_start_y = None
        self._last_clicked_entry = None

    def _drag_data_get_cb(self, widget, context, selection, targetType, eventTime):
        logging.debug("drag_data_get_cb: requested target " + selection.target)

        jobject = self._last_clicked_entry.jobject
        if selection.target == 'text/uri-list':
            selection.set(selection.target, 8, jobject.file_path)
        elif selection.target == 'journal-object-id':
            selection.set(selection.target, 8, jobject.object_id)

    def _canvas_button_press_event_cb(self, widget, event):
        logging.debug("button_press_event_cb")

        if event.button == 1 and event.type == gtk.gdk.BUTTON_PRESS:
            self._last_clicked_entry = self._get_entry_at_coords(event.x, event.y)
            if self._last_clicked_entry:
                self._pressed_button = event.button
                self._press_start_x = event.x
                self._press_start_y = event.y

        return False

    def _get_entry_at_coords(self, x, y):
        for entry in self._box.get_children():
            entry_x, entry_y = entry.get_context().translate_to_widget(entry)
            entry_width, entry_height = entry.get_allocation()

            if (x >= entry_x ) and (x <= entry_x + entry_width) and        \
                    (y >= entry_y ) and (y <= entry_y + entry_height):
                return entry
        return None

    def _result_set_modified_cb(self, result_set):
        logging.debug('_result_set_modified_cb')
        self._do_scroll(force=True)

    def update_dates(self):
        logging.debug('ListView.update_dates')
        for entry in self._entries:
            entry.update_date()
