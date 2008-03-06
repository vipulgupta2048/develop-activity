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
import StringIO

import hippo
import cairo
import gobject
import gtk
import json

from sugar.graphics import style
from sugar.graphics.icon import CanvasIcon
from sugar.graphics.xocolor import XoColor
from sugar.graphics.entry import CanvasEntry
from sugar.graphics.combobox import ComboBox
from sugar import activity
from sugar.datastore import datastore

from tagbox import TagBox
from keepicon import KeepIcon
import misc

class Separator(hippo.CanvasBox, hippo.CanvasItem):
    def __init__(self, orientation):
        hippo.CanvasBox.__init__(self,
                                 background_color=style.COLOR_PANEL_GREY.get_int())

        if orientation == hippo.ORIENTATION_VERTICAL:
            self.props.box_width = style.LINE_WIDTH
        else:
            self.props.box_height = style.LINE_WIDTH

class CanvasTextView(hippo.CanvasWidget):
    def __init__(self, text, **kwargs):
        hippo.CanvasWidget.__init__(self, **kwargs)
        self.text_view_widget = gtk.TextView()
        self.text_view_widget.props.buffer.props.text = text
        self.text_view_widget.show()
        
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_shadow_type(gtk.SHADOW_OUT)
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(self.text_view_widget)
        
        self.props.widget = scrolled_window

class BuddyList(hippo.CanvasBox):
    def __init__(self, model):
        hippo.CanvasBox.__init__(self, xalign=hippo.ALIGNMENT_START)

        for buddy in model:
            nick, color = buddy
            hbox = hippo.CanvasBox(orientation=hippo.ORIENTATION_HORIZONTAL)
            icon = CanvasIcon(icon_name='computer-xo',
                              xo_color=XoColor(color),
                              size=style.STANDARD_ICON_SIZE)
            hbox.append(icon)
            
            label = hippo.CanvasText(text=nick,
                                     font_desc=style.FONT_NORMAL.get_pango_desc())
            hbox.append(label)
            
            self.append(hbox)

class ExpandedEntry(hippo.CanvasBox):
    def __init__(self, object_id):
        hippo.CanvasBox.__init__(self)
        self.props.orientation = hippo.ORIENTATION_HORIZONTAL
        self.props.background_color = style.COLOR_WHITE.get_int()
        self.props.spacing = style.DEFAULT_SPACING
        self.props.padding = style.DEFAULT_PADDING

        self._jobject = datastore.get(object_id)
        self._update_title_sid = None

        # Create three columns
        first_column = hippo.CanvasBox(orientation=hippo.ORIENTATION_VERTICAL,
                                       padding=style.DEFAULT_PADDING,
                                       spacing=style.DEFAULT_SPACING)
        self.append(first_column)

        second_column = hippo.CanvasBox(orientation=hippo.ORIENTATION_VERTICAL,
                                        padding_right=style.GRID_CELL_SIZE,
                                        padding=style.DEFAULT_PADDING,
                                        spacing=style.DEFAULT_SPACING)
        self.append(second_column, hippo.PACK_EXPAND)

        self.append(Separator(hippo.ORIENTATION_VERTICAL))
        
        third_column = hippo.CanvasBox(orientation=hippo.ORIENTATION_VERTICAL,
                                       box_width=style.GRID_CELL_SIZE * 4)
        self.append(third_column)

        # First column        
        self._keep_icon = self._create_keep_icon()
        first_column.append(self._keep_icon)

        # Second column
        header = hippo.CanvasBox(orientation=hippo.ORIENTATION_HORIZONTAL,
                                 spacing=style.DEFAULT_SPACING)
        second_column.append(header)
        
        self._icon = self._create_icon()
        header.append(self._icon)

        self._title = self._create_title()
        header.append(self._title, hippo.PACK_EXPAND)

        hbox = hippo.CanvasBox(orientation=hippo.ORIENTATION_HORIZONTAL)
        second_column.append(hbox)
        
        self._preview = self._create_preview()
        hbox.append(self._preview)

        self._buddy_list = self._create_buddy_list()
        hbox.append(self._buddy_list)

        description_box, self._description = self._create_description()
        second_column.append(description_box)

        tags_box, self._tags = self._create_tags()
        second_column.append(tags_box)

        # Third column
        self._version_list = self._create_version_list()
        third_column.append(self._version_list)

    def _create_keep_icon(self):
        keep = self._jobject.metadata.has_key('keep') and \
               self._jobject.metadata['keep'] == 1
        keep_icon = KeepIcon(keep)
        keep_icon.connect('activated', self._keep_icon_activated_cb)
        return keep_icon

    def _create_icon(self):
        icon = CanvasIcon(file_name=misc.get_icon_name(self._jobject))
        icon.connect_after('button-release-event', self._icon_button_release_event_cb)

        if self._jobject.is_activity_bundle():
            icon.props.fill_color=style.COLOR_TRANSPARENT.get_svg()
            icon.props.stroke_color=style.COLOR_BLACK.get_svg()
        else:
            if self._jobject.metadata.has_key('icon-color') and \
                   self._jobject.metadata['icon-color']:
                icon.props.xo_color = XoColor( \
                    self._jobject.metadata['icon-color'])
            
        return icon

    def _create_title(self):
        title = CanvasEntry()
        title.set_background(style.COLOR_WHITE.get_html())

        text = self._jobject.metadata.get('title', _('Untitled'))
        if self._jobject.is_activity_bundle():
            title.props.text = text + _(' Activity')
        else:    
            title.props.text = text
            
        title.props.widget.connect('focus-out-event',
                                   self._title_focus_out_event_cb)
        return title

    def _create_preview(self):
        width = style.zoom(320)
        height = style.zoom(240)
        box = hippo.CanvasBox()

        if self._jobject.metadata.has_key('preview') and \
                len(self._jobject.metadata['preview']) > 4:
            
            if self._jobject.metadata['preview'][1:4] == 'PNG':
                preview_data = self._jobject.metadata['preview']
            else:
                import base64
                preview_data = base64.b64decode(self._jobject.metadata['preview'])
            

            png_file = StringIO.StringIO(preview_data)
            try:
                surface = cairo.ImageSurface.create_from_png(png_file)
                has_preview = True
            except Exception, e:
                logging.error('Error while loading the preview: %r' % e)
                has_preview = False
        else:
            has_preview = False

        if has_preview:
            preview_box = hippo.CanvasImage(image=surface,
                                            border=style.LINE_WIDTH,
                                            border_color=style.COLOR_BUTTON_GREY.get_int(),
                                            xalign=hippo.ALIGNMENT_CENTER,
                                            yalign=hippo.ALIGNMENT_CENTER,
                                            scale_width=width,
                                            scale_height=height)
        else:
            preview_box = hippo.CanvasText(text=_('No preview'),
                                           font_desc=style.FONT_NORMAL.get_pango_desc(),
                                           xalign=hippo.ALIGNMENT_CENTER,
                                           yalign=hippo.ALIGNMENT_CENTER,
                                           border=style.LINE_WIDTH,
                                           border_color=style.COLOR_BUTTON_GREY.get_int(),
                                           box_width=width,
                                           box_height=height)
        box.append(preview_box)
        return box

    def _create_buddy_list(self):
        if self._jobject.metadata.has_key('buddies') and \
                self._jobject.metadata['buddies']:
            # json cannot read unicode strings
            buddies_str = self._jobject.metadata['buddies'].encode('utf8')
            buddies = json.read(buddies_str).values()
            return BuddyList(buddies)
        else:
            return BuddyList([])

    def _create_description(self):
        vbox = hippo.CanvasBox()
        #vbox.props.spacing = style.DEFAULT_SPACING
        vbox.append(hippo.CanvasText(text=_('Description:'),
                                     xalign=hippo.ALIGNMENT_START,
                                     font_desc=style.FONT_NORMAL.get_pango_desc()))
        
        description = self._jobject.metadata.get('description', '')
        text_view = CanvasTextView(description, box_height=style.GRID_CELL_SIZE * 2)
        vbox.append(text_view, hippo.PACK_EXPAND)

        text_view.text_view_widget.props.accepts_tab = False
        text_view.text_view_widget.connect('focus-out-event',
                                           self._description_focus_out_event_cb)

        return vbox, text_view

    def _create_tags(self):
        vbox = hippo.CanvasBox()
        #vbox.props.spacing = style.DEFAULT_SPACING
        vbox.append(hippo.CanvasText(text=_('Tags:'),
                                     xalign=hippo.ALIGNMENT_START,
                                     font_desc=style.FONT_NORMAL.get_pango_desc()))
        
        tags = self._jobject.metadata.get('tags', '')
        text_view = CanvasTextView(tags, box_height=style.GRID_CELL_SIZE * 2)
        vbox.append(text_view, hippo.PACK_EXPAND)

        text_view.text_view_widget.props.accepts_tab = False
        text_view.text_view_widget.connect('focus-out-event',
                                           self._tags_focus_out_event_cb)

        return vbox, text_view

    def _create_version_list(self):
        vbox = hippo.CanvasBox()
        vbox.props.spacing = style.DEFAULT_SPACING
        # TODO: Enable again when we have versions in the DS
        """
        jobjects, count = datastore.find({'uid': self._jobject.object_id},
                                         sorting=['-mtime'])
        for jobject in jobjects:
            hbox = hippo.CanvasBox(orientation=hippo.ORIENTATION_HORIZONTAL)
            hbox.props.spacing = style.DEFAULT_SPACING

            icon = CanvasIcon(file_name=misc.get_icon_name(jobject),
                              size=style.SMALL_ICON_SIZE)
            if jobject.metadata.has_key('icon-color') and \
                    jobject.metadata['icon-color']:
                icon.props.xo_color = XoColor(jobject.metadata['icon-color'])
            hbox.append(icon)
            
            date = hippo.CanvasText(text=misc.get_date(jobject),
                                    xalign=hippo.ALIGNMENT_START,
                                    font_desc=style.FONT_NORMAL.get_pango_desc())
            hbox.append(date)
            
            vbox.append(hbox)
        """
        return vbox

    def _title_notify_text_cb(self, entry, pspec):
        if not self._update_title_sid:
            self._update_title_sid = gobject.timeout_add(1000, self._update_title_cb)

    def _datastore_write_cb(self):
        pass

    def _datastore_write_error_cb(self, error):
        logging.error('ExpandedEntry._datastore_write_error_cb: %r' % error)

    def _title_focus_out_event_cb(self, entry, event):
        self._update_entry()

    def _description_focus_out_event_cb(self, text_view, event):
        self._update_entry()

    def _tags_focus_out_event_cb(self, text_view, event):
        self._update_entry()

    def _update_entry(self):
        needs_update = False

        old_title = self._jobject.metadata.get('title', None)
        if old_title != self._title.props.text:
            self._jobject.metadata['title'] = self._title.props.text
            self._jobject.metadata['title_set_by_user'] = '1'
            needs_update = True

        old_tags = self._jobject.metadata.get('tags', None)
        new_tags = self._tags.text_view_widget.props.buffer.props.text
        if old_tags != new_tags:
            self._jobject.metadata['tags'] = new_tags
            needs_update = True

        old_description = self._jobject.metadata.get('description', None)
        new_description = self._description.text_view_widget.props.buffer.props.text
        if old_description != new_description:
            self._jobject.metadata['description'] = new_description
            needs_update = True

        if needs_update:
            datastore.write(self._jobject, update_mtime=False,
                            reply_handler=self._datastore_write_cb,
                            error_handler=self._datastore_write_error_cb)
 
        self._update_title_sid = None
 
    def get_keep(self):
        return self._jobject.metadata.has_key('keep') and \
               self._jobject.metadata['keep'] == 1

    def _keep_icon_activated_cb(self, keep_icon):
        if self.get_keep():
            self._jobject.metadata['keep'] = 0
        else:
            self._jobject.metadata['keep'] = 1
        datastore.write(self._jobject, update_mtime=False)

        keep_icon.props.keep = self.get_keep()

    def _icon_button_release_event_cb(self, button, event):
        logging.debug('_icon_button_release_event_cb')
        self._jobject.resume()
        return True

