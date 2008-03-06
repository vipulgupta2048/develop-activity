# Copyright 2008 Paul Swartz
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
      
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

def class_template(name):
    name = name.replace(' ', '')
    return '%s_app' % name.lower(), '%sActivity' % name

def activity_info_template(name):
    bundle_id = 'org.laptop.%s' % name.replace(' ', '')
    return """[Activity]
name = %s
bundle_id = %s
service_name = %s
icon = activity-default
class = %s.%s
activity_version = 1
show_launcher = yes
""" % ((name, bundle_id, bundle_id) + class_template(name))

def base_file_template(name):
    filen, classn = class_template(name)
    return """from sugar.activity import activity

class %s(activity.Activity):
    '''
    The base class for the %s activity.
    '''
    
    def __init__(self, handle):
        activity.Activity.__init__(self, handle)
        
    def write_file(self, file_path):
        '''
        Implement this method to save your activity's state.
        '''
        raise NotImplementedError
    
    def read_file(self, file_path):
        '''
        Implement this method to resume state saved in write_file().
        '''
        raise NotImplementedError
""" % (classn, name)

def new_activity(name):
    import os
    path = os.path.expanduser('~/Activities/%s.activity' % name.replace(' ', ''))
    os.mkdir(path)
    activityPath = os.path.join(path, 'activity')
    os.mkdir(activityPath)
    filen, classn = class_template(name)
    _file = file(os.path.join(path, filen + '.py'), 'w')
    _file.write(base_file_template(name))
    _file.close()
    
    _file = file(os.path.join(activityPath, 'activity.info'), 'w')
    _file.write(activity_info_template(name))
    _file.close()
    
    _file = file(os.path.join(path, 'NEWS'), 'w')
    _file.close()
    
    _file = file(os.path.join(path, 'MANIFEST'), 'w')
    _file.write('''activity/activity.info
activity/activity-default.svg
%s.py
NEWS
MANIFEST''' % filen)
    _file.close()

    icon_path = os.path.join(os.path.dirname(__file__), 'activity',
        'activity-default.svg')
    import shutil
    shutil.copy(icon_path, activityPath)

    return path
