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


