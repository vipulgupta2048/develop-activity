#
from gettext import gettext as _
import os.path

#TODO: get dirty, use sugar.activity.activity
#from sugar.activity.activity import Activity
#from sugar.activity import activity

from activity import Activity
import activity

from sugar.datastore import datastore
from sugar import profile
try:
    from sugar.activity.bundlebuilder import XOPackager, Config
except ImportError:
    from bundlebuilder import XOPackager

OPENFILE_SEPARATOR = u"@ @"

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
        
        #create bundle
        dist_dir, dist_name = os.path.split(file_path)
        builder = XOPackager(Config(activity_dir, dist_dir, dist_name))
        builder.package()
        
        #set up datastore object
        jobject = datastore.create()
        if self._shared_activity is not None:
            icon_color = self._shared_activity.props.color
        else:
            icon_color = profile.get_color().to_string()

        metadata = {
            'title': _('%s Bundle') % builder.config.activity_name,
            'title_set_by_user': '1',
            'suggested_filename': '%s-%d.xo' % (builder.config.bundle_name, 
                                                builder.config.version),
            'icon-color': icon_color,
            'mime_type': 'application/vnd.olpc-sugar',
            'activity' : self.get_bundle_id(),
            'activity_id' : self.get_id(),
            'share-scope' : activity.SCOPE_PRIVATE,
            'preview' : '',
            'source' : activity_dir,
            }
        for k, v in metadata.items():
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
            jobject = self.save_source_jobject(activity.get_bundle_path(),
                                          activity.get_activity_root())
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


