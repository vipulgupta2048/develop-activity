# Copyright (C) 2006-2007 Red Hat, Inc.
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
"""bundlebuilder is a module. 

bundlebuilder.Bundlebuilder is a class. Each instance performs functions
on a given root activity directory, set in __init__.

bundlebuilder.bundlebuilder is an instance, initialized to the current
working directory when the module bundlebuilder was first loaded.

In general, 
bundlebuilder.function() 
is equivalent to 
bundlebuilder.bundlebuilder.function() #really a method here.

bundlebuilder.bundlebuilder is callable. bundlebuilder.start just calls it
using the arguments from sys.argv[]
"""
import sys
import os
import zipfile
import shutil
import subprocess
import re
import gettext

from sugar import env
from sugar.bundle.activitybundle import ActivityBundle

manifest = 'MANIFEST'

######### These four list classes use the current working directory 
class _SvnFileList(list):
    def __init__(self):
        f = os.popen('svn list -R')
        for line in f.readlines():
            filename = line.strip()
            if os.path.isfile(filename):
                self.append(filename)
        f.close()

class _GitFileList(list):
    def __init__(self):
        f = os.popen('git-ls-files')
        for line in f.readlines():
            filename = line.strip()
            if not filename.startswith('.'):
                self.append(filename)
        f.close()

class _DefaultFileList(list):
    def __init__(self):
        for name in os.listdir('activity'):
            if name.endswith('.svg'):
                self.append(os.path.join('activity', name))

        self.append('activity/activity.info')

        if os.path.isfile(os.path.join(os.getcwd(),'NEWS')):
            self.append('NEWS')

class _ManifestFileList(_DefaultFileList):
    def __init__(self):
        _DefaultFileList.__init__(self)
        self.append(manifest)

        f = open(manifest,'r')
        for line in f.readlines():
            stripped_line = line.strip()
            if stripped_line and not stripped_line in self:
                self.append(stripped_line)
        f.close()

def extract_bundle(source_file, dest_dir):
    dest_dir = (dest_dir if os.path.isabs(dest_dir) else 
                    os.path.join(self.path,dest_dir))
    if not os.path.exists(dest_dir):
        os.mkdir(dest_dir)

    if not os.path.isabs(source_file):
        source_file = os.path.join(os.getcwd(),source_file)
    zf = zipfile.ZipFile(source_file)

    namelist = zf.namelist()
    for name in namelist:
        path = os.path.join(dest_dir, name)
        
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))

        outfile = open(path, 'wb')
        outfile.write(zf.read(name))
        outfile.flush()
        outfile.close()
    return os.path.join(dest_dir,os.path.commonprefix(namelist))
        
######### Main Bundlebuilder class

class Bundlebuilder:
    def __init__(self,path):
        if not os.path.isdir(path):
            raise ValueError("Bundlebuilder: %s is not a valid path" % path)
        self.path = path

    def _get_source_path(self, extra_path=None):
        if extra_path:
            return os.path.join(self.path, extra_path)
        else:
            return self.path

    def _get_bundle_dir(self):
        bundle_name = os.path.basename(self._get_source_path())
        return bundle_name + '.activity'    

    def _get_install_dir(self, prefix):
        return os.path.join(prefix, 'share/activities')

    def _get_package_name(self, bundle_name = None):
        bundle = ActivityBundle(self._get_source_path())
        zipname = '%s-%d.xo' % (bundle_name or bundle.get_name(), bundle.get_activity_version())
        return zipname

    def _delete_backups(self, arg, dirname, names):
        if not os.path.isabs(dirname):
            dirname = os.path.join(self.path,dirname)
        for name in names:
            if name.endswith('~') or name.endswith('pyc'):
                os.remove(os.path.join(dirname, name))

    def _get_bundle_id(self):
        bundle = ActivityBundle(self._get_source_path())
        return bundle.get_bundle_id()

    def cmd_help(self):
        print 'Usage: \n\
    setup.py dev                 - setup for development \n\
    setup.py dist                - create a bundle package \n\
    setup.py install   [dirname] - install the bundle \n\
    setup.py uninstall [dirname] - uninstall the bundle \n\
    setup.py genpot              - generate the gettext pot file \n\
    setup.py genl10n             - generate localization files \n\
    setup.py clean               - clean the directory \n\
    setup.py release             - do a new release of the bundle \n\
    setup.py help                - print this message \n\
    '

    def cmd_dev(self):
        bundle_path = env.get_user_activities_path()
        if not os.path.isdir(bundle_path):
            os.mkdir(bundle_path)
        bundle_path = os.path.join(bundle_path, self._get_bundle_dir())
        try:
            os.symlink(self._get_source_path(), bundle_path)
        except OSError:
            if os.path.islink(bundle_path):
                print 'ERROR - The bundle has been already setup for development.'
            else:
                print 'ERROR - A bundle with the same name is already installed.'    

    def _get_file_list(self):
        #the various list commands fundamentally depend on being
        # in the directory. Just go there and come back after.
        #TODO: figure out if there are optional arguments to os.popen() to avoiod this
        cwd = os.getcwd()
        os.chdir(self.path)
        try:
            if os.path.isfile(manifest):
                return _ManifestFileList()
            elif os.path.isdir('.git'):
                return _GitFileList()
            elif os.path.isdir('.svn'):
                return _SvnFileList()
            else:
                return _DefaultFileList()
        finally:
            os.chdir(cwd)

    def _get_po_list(self):
        file_list = {}

        po_regex = re.compile("po/(.*)\.po$")
        for file_name in self._get_file_list():
            match = po_regex.match(file_name)
            if match:
                file_list[match.group(1)] = file_name

        return file_list

    def _get_l10n_list(self):
        l10n_list = []

        for lang in self._get_po_list().keys():
            filename = self._get_bundle_id() + '.mo'
            l10n_list.append(os.path.join('locale', lang, 'LC_MESSAGES', filename))
            l10n_list.append(os.path.join('locale', lang, 'activity.linfo'))

        return l10n_list

    def _get_activity_name(self):
        info_path = os.path.join(self._get_source_path(), 'activity', 'activity.info')
        f = open(info_path,'r')
        info = f.read()
        f.close()
        match = re.search('^name\s*=\s*(.*)$', info, flags = re.MULTILINE)
        return match.group(1)

    def cmd_dist(self, bundle_name = None, storage_directory = None):
        if not bundle_name:
            bundle = ActivityBundle(self._get_source_path())
            bundle_name = bundle.get_name()
            assert(bundle_name)
        self.cmd_genl10n(bundle_name)
        file_list = self._get_file_list()

        name_version = self._get_package_name(bundle_name)
        if not storage_directory:
            storage_directory = self.path
        elif not os.path.isdir(storage_directory): #includes file name
            zippath = storage_directory
        else:
            zippath = os.path.join(storage_directory,name_version)
        bundle_zip = zipfile.ZipFile(zippath, 'w', zipfile.ZIP_DEFLATED)
        base_dir = bundle_name + '.activity'
        
        for filename in file_list:
            bundle_zip.write(os.path.join(self.path,filename), #real absolute path
                os.path.join(base_dir, filename)) #path in zip file

        for filename in self._get_l10n_list():
            bundle_zip.write(os.path.join(self.path,filename), #real absolute path
                os.path.join(base_dir, filename)) #path in zip file

        bundle_zip.close()
        return name_version

    def cmd_install(self, bundle_name, prefix):
        self.cmd_dist(bundle_name)
        self.cmd_uninstall(prefix)

        extract_bundle(self._get_package_name(bundle_name),
                        self._get_install_dir(prefix))

    def cmd_uninstall(self, prefix):
        path = os.path.join(self._get_install_dir(prefix), self._get_bundle_dir())
        if os.path.isdir(path):
            shutil.rmtree(path)

    def cmd_genpot(self, bundle_name):
        po_path = os.path.join(self._get_source_path(), 'po')
        if not os.path.isdir(po_path):
            os.mkdir(po_path)

        python_files = []
        file_list = self._get_file_list()
        for file_name in file_list:
            if file_name.endswith('.py'):
                python_files.append(file_name)

        # First write out a stub .pot file containing just the translated
        # activity name, then have xgettext merge the rest of the
        # translations into that. (We can't just append the activity name
        # to the end of the .pot file afterwards, because that might
        # create a duplicate msgid.)
        pot_file = os.path.join(self.path,'po', '%s.pot' % bundle_name)
        activity_name = self._get_activity_name()
        escaped_name = re.sub('([\\\\"])', '\\\\\\1', activity_name)
        f = open(pot_file, 'w')
        f.write('#: activity/activity.info:2\n')
        f.write('msgid "%s"\n' % escaped_name)
        f.write('msgstr ""\n')
        f.close()

        args = [ 'xgettext', '--join-existing', '--language=Python',
                 '--keyword=_', '--add-comments=TRANS:', '--output=%s' % pot_file ]

        args += python_files
        cwd = os.getcwd()
        os.chdir(self.path)
        try:
            retcode = subprocess.call(args)
        finally:
            os.chdir(cwd)
        if retcode:
            print 'ERROR - xgettext failed with return code %i.' % retcode


    def cmd_genl10n(self, bundle_name):
        source_path = self._get_source_path()
        activity_name = self._get_activity_name()

        po_list = self._get_po_list()
        for lang in po_list.keys():
            file_name = po_list[lang]

            localedir = os.path.join(source_path, 'locale', lang)
            mo_path = os.path.join(localedir, 'LC_MESSAGES')
            if not os.path.isdir(mo_path):
                os.makedirs(mo_path)

            mo_file = os.path.join(mo_path, "%s.mo" % self._get_bundle_id())
            args = ["msgfmt", "--output-file=%s" % mo_file, file_name]
            retcode = subprocess.call(args)
            if retcode:
                print 'ERROR - msgfmt failed with return code %i.' % retcode

            cat = gettext.GNUTranslations(open(mo_file, 'r'))
            translated_name = cat.gettext(activity_name)
            linfo_file = os.path.join(localedir, 'activity.linfo')
            f = open(linfo_file, 'w')
            f.write('[Activity]\nname = %s\n' % translated_name)
            f.close()

    def cmd_release(self, bundle_name):
        if not os.path.isdir(os.path.join(self.path,'.git')):
            print 'ERROR - this command works only for git repositories'

        cwd = os.getcwd()
        os.chdir(self.path)
        try:
            retcode = subprocess.call(['git', 'pull'])
        finally:
            os.chdir(cwd)
        if retcode:
            print 'ERROR - cannot pull from git'

        print 'Bumping activity version...'

        info_path = os.path.join(self._get_source_path(), 'activity', 'activity.info')
        f = open(info_path,'r')
        info = f.read()
        f.close()

        exp = re.compile('activity_version\s?=\s?([0-9]*)')
        match = re.search(exp, info)
        version = int(match.group(1)) + 1
        info = re.sub(exp, 'activity_version = %d' % version, info)

        f = open(info_path, 'w')
        f.write(info)
        f.close()

        news_path = os.path.join(self._get_source_path(), 'NEWS')

        if os.environ.has_key('SUGAR_NEWS'):
            print 'Update NEWS.sugar...'

            sugar_news_path = os.environ['SUGAR_NEWS']
            if os.path.isfile(sugar_news_path):
                f = open(sugar_news_path,'r')
                sugar_news = f.read()
                f.close()
            else:
                sugar_news = ''

            sugar_news += '%s - %d\n\n' % (bundle_name, version)

            f = open(news_path,'r')
            for line in f.readlines():
                if len(line.strip()) > 0:
                    sugar_news += line
                else:
                    break
            f.close()

            sugar_news += '\n'

            f = open(sugar_news_path, 'w')
            f.write(sugar_news)
            f.close()

        print 'Update NEWS...'

        f = open(news_path,'r')
        news = f.read()
        f.close()

        news = '%d\n\n' % version + news

        f = open(news_path, 'w')
        f.write(news)
        f.close()

        print 'Committing to git...'

        changelog = 'Release version %d.' % version
        retcode = subprocess.call(['git', 'commit', '-a', '-m % s' % changelog])
        if retcode:
            print 'ERROR - cannot commit to git'

        retcode = subprocess.call(['git', 'push'])
        if retcode:
            print 'ERROR - cannot push to git'

        print 'Creating the bundle...'
        self.cmd_dist(bundle_name)

        print 'Done.'

    def cmd_clean(self):
        os.path.walk(self.path, _delete_backups, None)

    def sanity_check(self):
        if not os.path.isfile(self._get_source_path('NEWS')):
            print 'WARNING: NEWS file is missing.'


    def __call__(self,bundle_name, arg1, arg2 = None):
        self.sanity_check()

        if arg1 == 'build':
            pass
        elif arg1 == 'dev':
            self.cmd_dev()
        elif arg1 == 'dist':
            self.cmd_dist(bundle_name)
        elif arg1 == 'install' and arg2:
            self.cmd_install(bundle_name, arg2)
        elif arg1 == 'uninstall' and arg2:
            self.cmd_uninstall(arg2)
        elif arg1 == 'genpot':
            self.cmd_genpot(bundle_name)
        elif arg1 == 'genl10n':
            self.cmd_genl10n(bundle_name)
        elif arg1 == 'clean':
            self.cmd_clean()
        elif arg1 == 'release':
            self.cmd_release(bundle_name)
        else:
            self.cmd_help()
            
##### Create the default bundlebuilder instance
bundlebuilder = Bundlebuilder(os.getcwd())

#Export the bound methods of the default instance as module functions.
for a in bundlebuilder.__dict__:
    if callable(bundlebuilder.__dict__[a]) and isinstance(a,basestring):
        exec("global "+a+"\n"+a + "=bundlebuilder."+a) #stuff it into module globals
        

def start(bundle_name):
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        cmd_help()
    else:
        bundlebuilder(bundle_name, sys.argv[1],
            sys.argv[2] if len(sys.argv) == 3 else None)
        
if __name__ == '__main__':
    start("UNNAMED")
