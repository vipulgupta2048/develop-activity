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
import os
import shutil
import logging

from sugar.activity import activity


def class_template(name):
    name = name.replace(' ', '')
    return '%s_app' % name.lower(), '%sActivity' % name


def activity_info_template(name, web_activity=False):
    bundle_id = 'org.sugarlabs.%s' % name.replace(' ', '')
    if web_activity:
        exec_line = 'sugar-activity-web'
    else:
        exec_line = 'sugar-activity activity.HelloWorldActivity'

    return """[Activity]
name = %s
bundle_id = %s
icon = activity-helloworld
exec = %s
activity_version = 1
show_launcher = yes
""" % (name, bundle_id, exec_line)


def create_activity(name, base_path, skeleton):
    path = os.path.expanduser(os.path.join(base_path,
                              '%s.activity' % name.replace(' ', '')))
    os.makedirs(path)
    activity_path = os.path.join(path, 'activity')
    os.mkdir(activity_path)

    # copy all the files in the skeleton directory
    skeleton_path = os.path.join(activity.get_bundle_path(), 'skeletons',
                                 skeleton)
    for cur, dirs, files in os.walk(skeleton_path):
        destination_path = os.path.join(path, cur[len(skeleton_path) + 1:])
        for directory in dirs:
            directory_path = os.path.join(destination_path, directory)
            try:
                os.mkdir(directory_path)
            except:
                logging.error('Error trying to create %s', directory_path)

        for file_name in files:
            shutil.copyfile(os.path.join(cur, file_name),
                            os.path.join(destination_path, file_name))

    # create activity.info file
    activity_info_path = os.path.join(activity_path, 'activity.info')
    with open(activity_info_path, 'w') as activity_info_file:
        activity_info_file.write(activity_info_template(name,
                                                        (skeleton == 'Web')))

    return path
