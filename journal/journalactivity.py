# Copyright (C) 2006, Red Hat, Inc.
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
import sys
import traceback 
import uuid

import gobject
import gtk
import dbus

from sugar.activity import activity
from sugar.activity.registry import get_registry as get_activity_registry
from sugar.bundle.bundle import ZipExtractException, RegistrationException
from sugar.datastore import datastore

from journaltoolbox import MainToolbox, DetailToolbox
from listview import ListView
from detailview import DetailView
from volumestoolbar import VolumesToolbar
import backup
import misc
from journalentrybundle import JournalEntryBundle
from objectchooser import ObjectChooser

DS_DBUS_SERVICE = 'org.laptop.sugar.DataStore'
DS_DBUS_INTERFACE = 'org.laptop.sugar.DataStore'
DS_DBUS_PATH = '/org/laptop/sugar/DataStore'

J_DBUS_SERVICE = 'org.laptop.Journal'
J_DBUS_INTERFACE = 'org.laptop.Journal'
J_DBUS_PATH = '/org/laptop/Journal'

UPDATE_INTERVAL = 300000

class JournalActivityDBusService(dbus.service.Object):
    def __init__(self, parent):
        self._parent = parent
        session_bus = dbus.SessionBus()
        bus_name = dbus.service.BusName(J_DBUS_SERVICE,
            bus=session_bus, replace_existing=False, allow_replacement=False)
        logging.debug('bus_name: %r', bus_name)
        dbus.service.Object.__init__(self, bus_name, J_DBUS_PATH)

    @dbus.service.method(J_DBUS_INTERFACE,
        in_signature='a{sv}', out_signature='')
    def FocusSearch(self, search_dict):
        """Set search parameters and grab focus
        search_dict can contain:
            -query: string
            -activity: string that can contain bundle id
            -mimetype: list of strings
            -mtime: a dict of the form:
                 {'start': 1193917107.9856629, 'end': 1193917107.9856629}
            """
        self._parent.present()
        self._parent._show_main_view()
        self._parent.set_search(search_dict)
        self._parent.search_grab_focus()

    @dbus.service.method(J_DBUS_INTERFACE,
        in_signature='s', out_signature='')
    def ShowObject(self, object_id):
        """Pop-up journal and show object with object_id"""

        logging.debug('Trying to show object %s', object_id)

        if self._parent.show_object(object_id):
            self._parent.present()

    def _chooser_response_cb(self, chooser, response_id, chooser_id):
        logging.debug('JournalActivityDBusService._chooser_response_cb')
        if response_id == gtk.RESPONSE_ACCEPT:
            object_id = chooser.get_selected_object_id()
            self.ObjectChooserResponse(chooser_id, object_id)
        else:
            self.ObjectChooserCancelled(chooser_id)
        chooser.destroy()

    @dbus.service.method(J_DBUS_INTERFACE, in_signature='i', out_signature='s')
    def ChooseObject(self, parent_xid):
        chooser_id = uuid.uuid4().hex
        if parent_xid > 0:
            parent = gtk.gdk.window_foreign_new(parent_xid)
        else:
            parent = None
        chooser = ObjectChooser(parent)
        chooser.connect('response', self._chooser_response_cb, chooser_id)
        chooser.show()

        return chooser_id

    @dbus.service.signal(J_DBUS_INTERFACE, signature="ss")
    def ObjectChooserResponse(self, chooser_id, object_id):
        pass

    @dbus.service.signal(J_DBUS_INTERFACE, signature="s")
    def ObjectChooserCancelled(self, chooser_id):
        pass

class JournalActivity(activity.Activity):
    def __init__(self, handle):
        activity.Activity.__init__(self, handle, create_jobject=False)

        self.set_title(_('Journal'))

        self._update_timer = None
        self.iconify()

        self._setup_main_view()
        self._setup_secondary_view()

        self.add_events(gtk.gdk.VISIBILITY_NOTIFY_MASK)
        self.connect('visibility-notify-event', self.__visibility_notify_event_cb)
        self.connect('key-press-event', self._key_press_event_cb)
        self.connect('focus-in-event', self._focus_in_event_cb)

        bus = dbus.SessionBus()
        data_store = dbus.Interface(
            bus.get_object(DS_DBUS_SERVICE, DS_DBUS_PATH), DS_DBUS_INTERFACE)
        data_store.connect_to_signal('Created', self._data_store_created_cb)
        data_store.connect_to_signal('Updated', self._data_store_updated_cb)

        self._dbus_service = JournalActivityDBusService(self)        

    def can_close(self):
        return False

    def _setup_main_view(self):
        self._main_toolbox = MainToolbox()
        self._main_view = gtk.VBox()

        self._list_view = ListView()
        self._list_view.connect('entry-activated', self._entry_activated_cb)
        self._main_view.pack_start(self._list_view)
        self._list_view.show()

        volumes_toolbar = VolumesToolbar()
        volumes_toolbar.connect('volume-changed', self._volume_changed_cb)
        self._main_view.pack_start(volumes_toolbar, expand=False)

        search_toolbar = self._main_toolbox.search_toolbar
        search_toolbar.connect('query-changed', self._query_changed_cb)
        search_toolbar.set_volume_id(datastore.mounts()[0]['id'])

    def _setup_secondary_view(self):
        self._secondary_view = gtk.VBox()

        self._detail_toolbox = DetailToolbox()
        entry_toolbar = self._detail_toolbox.entry_toolbar
        entry_toolbar.connect('entry-erased', self._entry_erased_cb)
        entry_toolbar.connect('go-back-clicked', self._go_back_clicked_cb)

        self._detail_view = DetailView()
        self._secondary_view.pack_end(self._detail_view)
        self._detail_view.show()

    def _key_press_event_cb(self, widget, event):
        keyname = gtk.gdk.keyval_name(event.keyval)
        logging.info(keyname)
        logging.info(event.state)
        if keyname == 'Escape':
            self._show_main_view()

        if event.state & gtk.gdk.MOD1_MASK:
            if gtk.gdk.keyval_name(event.keyval) == 'b':
                backup.start()

    def _entry_activated_cb(self, list_view, entry):
        self._show_secondary_view(entry.jobject)
    
    def _go_back_clicked_cb(self, detail_view):
        self._show_main_view()

    def _query_changed_cb(self, toolbar, query):
        self._list_view.update_with_query(query)
        self._show_main_view()

    def _show_main_view(self):
        if self.toolbox != self._main_toolbox:
            self.set_toolbox(self._main_toolbox)
            self._main_toolbox.show()

        if self.canvas != self._main_view:
            self.set_canvas(self._main_view)
            self._main_view.show()

    def _show_secondary_view(self, jobject):
        try:
            self._detail_toolbox.entry_toolbar.set_jobject(jobject)
        except Exception, e:
            logging.error('Exception while displaying entry:\n' + \
                ''.join(traceback.format_exception(*sys.exc_info())))

        self.set_toolbox(self._detail_toolbox)
        self._detail_toolbox.show()

        try:
            self._detail_view.set_jobject(jobject)
        except Exception, e:
            logging.error('Exception while displaying entry:\n' + \
                ''.join(traceback.format_exception(*sys.exc_info())))

        self.set_canvas(self._secondary_view)
        self._secondary_view.show()

    def show_object(self, object_id):
        jobject = datastore.get(object_id)
        if jobject is None:
            return False
        else:
            self._show_secondary_view(jobject)
            return True

    def _entry_erased_cb(self, toolbar):
        self._show_main_view()

    def _volume_changed_cb(self, volume_toolbar, volume_id):
        logging.debug('Selected volume: %r.' % volume_id)
        self._main_toolbox.search_toolbar.set_volume_id(volume_id)
        self._main_toolbox.set_current_toolbar(0)

    def _data_store_created_cb(self, uid):
        jobject = datastore.get(uid)
        if jobject is None:
            return
        try:
            self._check_for_bundle(jobject)
        finally:
            jobject.destroy()
        self._main_toolbox.search_toolbar.refresh_filters()
        
    def _data_store_updated_cb(self, uid):
        jobject = datastore.get(uid)
        if jobject is None:
            return
        try:
            self._check_for_bundle(jobject)
        finally:
            jobject.destroy()

    def _focus_in_event_cb(self, window, event):
        self.search_grab_focus()
        self._list_view.update_dates()

    def _check_for_bundle(self, jobject):
        bundle = misc.get_bundle(jobject)
        if bundle is None:
            return

        if bundle.is_installed():
            return
        try:
            bundle.install()
        except (ZipExtractException, RegistrationException), e:
            logging.warning('Could not install bundle %s: %r' %
                            (jobject.file_path, e))
            return

        if jobject.metadata['mime_type'] == JournalEntryBundle.MIME_TYPE:
            datastore.delete(jobject.object_id)

    def set_search(self, search_dict):
        search_toolbar = self._main_toolbox.search_toolbar
        if 'query' in search_dict:
            search_toolbar._search_entry.set_text(search_dict['query'])
            
    def search_grab_focus(self):
        search_toolbar = self._main_toolbox.search_toolbar
        search_toolbar._search_entry.grab_focus()

    def __update_timer_cb(self):
        self._list_view.update_dates()
        return True

    def __visibility_notify_event_cb(self, window, event):
        if event.state == gtk.gdk.VISIBILITY_FULLY_OBSCURED:
            if self._update_timer is not None:
                gobject.source_remove(self._update_timer)
                self._update_timer = None
        else:
            if self._update_timer is None:
                self._update_timer = gobject.timeout_add(UPDATE_INTERVAL,
                                                         self.__update_timer_cb)

    def take_screenshot(self):
        # Don't take any screenshot. Only makes the system slower.
        pass

