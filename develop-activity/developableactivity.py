#

try:
    from sugar.activity.activity import INSTANCE_DIR
    from sugar.activity.activity import Activity
    from sugar.activity import activity
except ImportError:
    from activity import Activity
    import activity
from sugar.datastore import datastore
from sugar import profile
from gettext import gettext as _
try:
    from sugar.activity.bundlebuilder import Bundlebuilder, extract_bundle
except ImportError:
    from bundlebuilder import Bundlebuilder

OPENFILE_SEPARATOR = u"@@"

class ViewSourceActivity(Activity):
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
    
    def save_source_jobject(self, activity_dir, file_path, filenames = None):
        if not activity_dir:
            raise NotImplementedError
        
        if not file_path:
            file_path
        #create bundle
        builder = Bundlebuilder(activity_dir)
        name_version = builder.cmd_dist(storage_directory=file_path)
        
        #set up datastore object
        jobject = datastore.create()
        if self._shared_activity is not None:
            icon_color = self._shared_activity.props.color
        else:
            icon_color = profile.get_color().to_string()

        metadata = {
            'title': _('%s Bundle') % builder._get_activity_name(),
            'title_set_by_user': '1',
            'suggested_filename': name_version or (bundlename._get_activity_name() + '.xo'),
            'icon-color': icon_color,
            'mime_type': 'application/vnd.olpc-sugar',
            'activity' : self.get_bundle_id(),
            'activity_id' : self.get_id(),
            'share-scope' : activity.SCOPE_PRIVATE,
            'preview' : '',
            'source' : activity_dir,
            }
        for k,v in metadata.items():
            jobject.metadata[k] = v # dict.update method is missing =(
        if filenames:
            jobject.metadata['open_filenames'] = filenames
        jobject.file_path = file_path
        #datastore.write(jobject)
        #jobject.destroy()
        return jobject
        
    def view_source(self):
        """Implement the 'view source' key by saving a .xo bundle to the
        datastore, and then telling the Journal to view it."""
        if self.__source_object_id is None:
            from sugar.datastore import datastore
            from sugar.activity.activity import get_activity_root, get_bundle_path
            jobject = save_source_jobject(get_bundle_path(),get_activity_root())
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


