from sugar.activity import activity

class ViewSourceActivity(activity.Activity):
    """Activity subclass which handles the 'view source' key."""
    def __init__(self, handle, **kw):
        super(ViewSourceActivity, self).__init__(handle, **kw)
        self.__source_object_id = None # XXX: persist this across invocations?
        self.connect('key-press-event', self._key_press_cb)
    def _key_press_cb(self, widget, event):
        import gtk
        if gtk.gdk.keyval_name(event.keyval) == 'XF86Start':
            self.view_source()
            return True
        return False
    def view_source(self):
        """Implement the 'view source' key by saving pippy_app.py to the
        datastore, and then telling the Journal to view it."""
        if self.__source_object_id is None:
            from sugar import profile
            from sugar.datastore import datastore
            from sugar.activity.activity import get_bundle_name, get_bundle_path
            from gettext import gettext as _
            import os.path
            jobject = datastore.create()
            metadata = {
                'title': _('%s Source') % get_bundle_name(),
                'title_set_by_user': '1',
                'suggested_filename': 'pippy_app.py',
                'icon-color': profile.get_color().to_string(),
                'mime_type': 'text/x-python',
                }
            for k,v in metadata.items():
                jobject.metadata[k] = v # dict.update method is missing =(
            jobject.file_path = os.path.join(get_bundle_path(), 'pippy_app.py')
            datastore.write(jobject)
            self.__source_object_id = jobject.object_id
            jobject.destroy()
        self.journal_show_object(self.__source_object_id)
    def journal_show_object(self, object_id):
        """Invoke journal_show_object from sugar.activity.activity if it
        exists."""
        try:
            from sugar.activity.activity import show_object_in_journal
            show_object_in_journal(object_id)
        except ImportError:
            pass # no love from sugar.


