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

from gettext import gettext as _
import gettext
import logging
import time
import traceback
import sys
import os

import gtk

from sugar import activity
from sugar import mime
from sugar.bundle.activitybundle import ActivityBundle
from sugar.bundle.contentbundle import ContentBundle
from sugar.bundle.bundle import MalformedBundleException, \
     ZipExtractException, RegistrationException
from sugar.util import LRU

from journalentrybundle import JournalEntryBundle

def _get_icon_file_name(icon_name):
    icon_theme = gtk.icon_theme_get_default()
    info = icon_theme.lookup_icon(icon_name, gtk.ICON_SIZE_LARGE_TOOLBAR, 0)
    if not info:
        # display standard icon when icon for mime type is not found
        info = icon_theme.lookup_icon('application-octet-stream',
                                      gtk.ICON_SIZE_LARGE_TOOLBAR, 0)
    fname = info.get_filename()
    del info
    return fname

_icon_cache = LRU(50)

def get_icon_name(jobject):

    cache_key = (jobject.object_id, jobject.metadata.get('timestamp', None))
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    file_name = None

    if jobject.is_activity_bundle() and jobject.file_path:
        try:
            bundle = ActivityBundle(jobject.file_path)
            file_name = bundle.get_icon()
        except:
            logging.warning('Could not read bundle:\n' + \
                ''.join(traceback.format_exception(*sys.exc_info())))
            file_name = _get_icon_file_name('application-octet-stream')

    if not file_name and jobject.metadata['activity']:
        service_name = jobject.metadata['activity']
        activity_info = activity.get_registry().get_activity(service_name)
        if activity_info:
            file_name = activity_info.icon

    mime_type = jobject.metadata['mime_type']
    if not file_name and mime_type:
        icon_name = mime.get_mime_icon(mime_type)
        if icon_name:
            file_name = _get_icon_file_name(icon_name)

    if not file_name or not os.path.exists(file_name):
        file_name = _get_icon_file_name('application-octet-stream')

    _icon_cache[cache_key] = file_name

    return file_name

# TRANS: Relative dates (eg. 1 month and 5 days).
units = [['%d year',   '%d years',   356 * 24 * 60 * 60],
         ['%d month',  '%d months',  30 * 24 * 60 * 60],
         ['%d week',   '%d weeks',   7 * 24 * 60 * 60],
         ['%d day',    '%d days',    24 * 60 * 60],
         ['%d hour',   '%d hours',   60 * 60],
         ['%d minute', '%d minutes', 60]]

AND = _(' and ')
COMMA = _(', ')
RIGHT_NOW = _('Right now')

# Explanation of the following hack:
# The xgettext utility extracts plural forms by reading the strings included as
# parameters of ngettext(). As our plurals are not passed to ngettext()
# straight away because there needs to be a calculation before we know which
# strings need to be used, then we need to call ngettext() in a fake way so
# xgettext will pick them up as plurals.

def ngettext(singular, plural, n): pass

ngettext('%d year',   '%d years',   1)
ngettext('%d month',  '%d months',  1)
ngettext('%d week',   '%d weeks',   1)
ngettext('%d day',    '%d days',    1)
ngettext('%d hour',   '%d hours',   1)
ngettext('%d minute', '%d minutes', 1)

del ngettext

# End of plurals hack

def _get_elapsed_string(timestamp, max_levels=2):
    levels = 0
    result = ''
    elapsed_seconds = int(time.time() - timestamp)
    for name_singular, name_plural, factor in units:
        elapsed_units = elapsed_seconds / factor
        if elapsed_units > 0:

            if levels > 0:
                if max_levels - levels == 1:
                    result += AND
                else:
                    result += COMMA

            result += gettext.ngettext(name_singular, name_plural,
                    elapsed_units) % elapsed_units

            elapsed_seconds -= elapsed_units * factor
            levels += 1
            
            if levels == max_levels:
                break

    if levels == 0:
        return RIGHT_NOW

    return result

def get_date(jobject):
    """ Convert from a string in iso format to a more human-like format. """
    if jobject.metadata.has_key('timestamp'):
        return _get_elapsed_string(jobject.metadata['timestamp'])
    elif jobject.metadata.has_key('mtime'):
        ti = time.strptime(jobject.metadata['mtime'], "%Y-%m-%dT%H:%M:%S")
        return _get_elapsed_string(time.mktime(ti))
    else:
        return _('No date')

def get_bundle(jobject):
    if jobject.file_path == '':
        # Probably a download-in-progress
        return None

    try:
        if jobject.is_activity_bundle():
            return ActivityBundle(jobject.file_path)
        elif jobject.is_content_bundle():
            return ContentBundle(jobject.file_path)
        elif jobject.metadata['mime_type'] == JournalEntryBundle.MIME_TYPE:
            return JournalEntryBundle(jobject.file_path)
        else:
            return None
    except MalformedBundleException, e:
        logging.warning('Incorrect bundle: %r' % e)
        return None

