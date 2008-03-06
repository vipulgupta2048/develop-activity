# Copyright (C) 2007 Red Hat, Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import os
import subprocess
import logging

import gobject

from sugar.datastore import datastore

class Backup(object):
    def __init__(self):
        self._progress_hid = None
        self._jobject = None

    def start(self):
        self._jobject = datastore.create()
        self._jobject.metadata['title'] = 'Backup'
        datastore.write(self._jobject)

        p = subprocess.Popen(["sugar-backup"], stdout=subprocess.PIPE)
        gobject.io_add_watch(p.stdout, gobject.IO_IN, self._process_output_cb)

    def _process_output_cb(self, source, condition):
        output = os.read(source.fileno(), 256)
        last_line = output.strip().split('\n')[-1]
        try:
            progress = int(last_line)
        except ValueError:
            logging.error('Invalid output from sugar-backup: %s' % progress)
            return

        # FIXME datastore should handle ints!
        self._jobject.metadata['progress'] = str(progress)
        datastore.write(self._jobject)

        return True

def start():
    backup = Backup()
    backup.start()
