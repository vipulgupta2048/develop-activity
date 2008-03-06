# coding: UTF8

# This file is part of Develop Activity.
#
# Copyright 2006-2007 Andrew Clunis <orospakr@linux.ca>
#
# Develop is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Develop is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Develop; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import gtk
from gettext import gettext as _

RESPONSE_OPEN = 1
RESPONSE_NEW  = 2
RESPONSE_CANCEL = 3

class WelcomeDialog(object):
    
    # TODO: current iteration is very much a placeholder.  The Welcome screen
    # should display something like the below.  Wording is very important here
    # and I greatly look foward to the HIG defining some of the persistence,
    # journal, and collaboration metaphors.
    #
    # The Welcome screen is very important because it is the very first thing
    # a user sees when they start Develop.  Thus, the collaborative development
    # facility needs to be very obvious from the start.
    #
    # I don't know if I want to use the word "Activity" generically here,
    # because I want Develop to apply readily to other sorts of programs.
    #
    # I'm considering using "Project" to describe the program being worked on,
    # including the scope of all the different people who might be working
    # on it via the collaboration features.
    #
    # - Resume work on a project (default option)
    #
    # - Create a brand new project...
    #   - XO (OLPC?) Activity (to be clear, no project type metadata is
    #     persisted.  This just creates the bare Sugar activity skeleton
    #     in the new project.  After that, Develop will detect the presence
    #     of Sugar's metadata and activate Sugar-specific features on Resume)
    #   - Other (could be almost any kind of computer program)
    #
    # - Download and Resume a project... (aka, clone/branch)
    #   - a project from a friend on the Mesh.
    #   - a project on the Internet.
    #
    def __init__(self, host_activity):
        self._host_activity = host_activity
        
    def run(self):
        """Creates and displays a welcome screen."""
        self.dialogbox = gtk.Dialog(_("Welcome to Develop"),
                                    parent=self._host_activity,
                                    flags=gtk.DIALOG_MODAL)
        vbox = self.dialogbox.vbox
        welcome_hbox = gtk.HBox()
        welcome_label = gtk.Label(_('<span weight="bold" size="larger">What would you like to do?</span>\n\nMost of the UI for persistence will ultimately be handled by the Journal interface in Sugar.  For now, this dialog serves as a placeholder.\n\nThe View Source key will (eventually) instruct Develop to view or branch existing Activities written by others.\n\nFeel free to join #sugar on irc.freenode.net and ask for help.  This software is a very early prerelease.'))
        welcome_label.set_use_markup(True)
        welcome_label.set_line_wrap(True)
        welcome_image = gtk.Image()
        welcome_image.set_from_stock(gtk.STOCK_EDIT, gtk.ICON_SIZE_DIALOG)
        vbox.pack_start(welcome_hbox, expand=True, fill=True, padding=12)
        welcome_hbox.show()
        welcome_hbox.pack_start(welcome_image, expand=True, fill=False, padding=12)
        welcome_image.show()
        welcome_hbox.pack_end(welcome_label, expand=True, fill=True, padding=12)
        welcome_label.show()
        
        self.dialogbox.add_button(gtk.STOCK_OPEN, RESPONSE_OPEN)
        self.dialogbox.add_button(gtk.STOCK_NEW, RESPONSE_NEW)
        self.dialogbox.add_button(gtk.STOCK_CANCEL, RESPONSE_CANCEL)
        response = self.dialogbox.run()
        self.dialogbox.destroy()
        return response

            
