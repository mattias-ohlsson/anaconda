#
# autopart_type.py: Allows the user to choose how they want to partition
#
# Copyright (C) 2005, 2006  Red Hat, Inc.  All rights reserved.
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): Jeremy Katz <katzj@redhat.com>
#

import gtk
import gobject
import math

from pyanaconda.constants import *
from pyanaconda import gui
from partition_ui_helpers_gui import *
from pixmapRadioButtonGroup_gui import pixmapRadioButtonGroup

from iw_gui import *
from pyanaconda.flags import flags
from pyanaconda.storage.deviceaction import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

def whichToShrink(storage, intf):
    def getActive(combo):
        act = combo.get_active_iter()
        return combo.get_model().get_value(act, 1)

    def comboCB(combo, shrinkSB):
        # partition to resize changed, let's update our spinbutton
        newSize = shrinkSB.get_value_as_int()

        part = getActive(combo)
        (reqlower, requpper) = getResizeMinMax(part)

        adj = shrinkSB.get_adjustment()
        adj.lower = max(1,reqlower)
        adj.upper = requpper
        adj.set_value(reqlower)


    (dxml, dialog) = gui.getGladeWidget("autopart.glade", "shrinkDialog")

    store = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)
    combo = dxml.get_widget("shrinkPartCombo")
    combo.set_model(store)
    crt = gtk.CellRendererText()
    combo.pack_start(crt, True)
    combo.set_attributes(crt, text = 0)
    combo.connect("changed", comboCB, dxml.get_widget("shrinkSB"))

    biggest = -1
    for part in storage.partitions:
        if not part.exists:
            continue

        entry = None
        if part.resizable and part.format.resizable:
            entry = ("%s (%s, %d MB)" % (part.name,
                                         part.format.name,
                                         math.floor(part.format.size)),
                     part)

        if entry:
            i = store.append(None)
            store[i] = entry
            combo.set_active_iter(i)

            if biggest == -1:
                biggest = i
            else:
                current = store.get_value(biggest, 1)
                if part.format.targetSize > current.format.targetSize:
                    biggest = i

    if biggest > -1:
        combo.set_active_iter(biggest)

    if len(store) == 0:
        dialog.destroy()
        intf.messageWindow(_("Error"),
                           _("No partitions are available to resize.  Only "
                             "physical partitions with specific filesystems "
                             "can be resized."),
                             type="warning", custom_icon="error")
        return (gtk.RESPONSE_CANCEL, [])

    gui.addFrame(dialog)
    dialog.show_all()
    runResize = True

    while runResize:
        rc = dialog.run()
        if rc != gtk.RESPONSE_OK:
            dialog.destroy()
            return (rc, [])

        request = getActive(combo)
        sb = dxml.get_widget("shrinkSB")
        sb.update()
        newSize = sb.get_value_as_int()
        actions = []

        try:
            actions.append(ActionResizeFormat(request, newSize))
        except ValueError as e:
            intf.messageWindow(_("Resize FileSystem Error"),
                               _("%(device)s: %(msg)s")
                                 % {'device': request.format.device,
                                    'msg': e.message},
                               type="warning", custom_icon="error")
            continue

        try:
            actions.append(ActionResizeDevice(request, newSize))
        except ValueError as e:
            intf.messageWindow(_("Resize Device Error"),
                               _("%(name)s: %(msg)s")
                                 % {'name': request.name, 'msg': e.message},
                               type="warning", custom_icon="error")
            continue
        else:
            # aligning the new partition end sector may have changed its size
            if request.targetSize != request.format.targetSize:
                request.format.targetSize = request.targetSize

        runResize = False

    dialog.destroy()
    return (rc, actions)

class PartitionTypeWindow(InstallWindow):
    def __init__(self, ics):
        InstallWindow.__init__(self, ics)
        ics.setTitle("Automatic Partitioning")
        ics.setNextEnabled(True)

    def getNext(self):
        if self.storage.checkNoDisks():
            raise gui.StayOnScreen

        self.storage.clearPartChoice = self.buttonGroup.getCurrent()

        if self.buttonGroup.getCurrent() == "custom":
            self.dispatch.skip_steps("autopartitionexecute")
            self.dispatch.request_steps_gently("cleardiskssel")
            self.dispatch.request_steps("partition")
            self.dispatch.request_steps_gently("bootloader")
            self.storage.config.clearPartType = CLEARPART_TYPE_NONE
        else:
            if self.buttonGroup.getCurrent() == "shrink":
                # we need to store this information so that it can survive
                # storage.reset since it may get called going between
                # the partitioning screen and the cleardisks screen when users
                # elect to do autopart w/ review and go back and forth
                (rc, actions) = whichToShrink(self.storage, self.intf)
                if rc == gtk.RESPONSE_OK:
                    for action in actions:
                        path = action.device.path
                        size = action.device.targetSize
                        self.storage.shrinkPartitions[path] = size
                        action.cancel()
                else:
                    raise gui.StayOnScreen

                # we're not going to delete any partitions in the resize case
                self.storage.config.clearPartType = CLEARPART_TYPE_NONE
            elif self.buttonGroup.getCurrent() == "all":
                self.storage.config.clearPartType = CLEARPART_TYPE_ALL
            elif self.buttonGroup.getCurrent() == "replace":
                self.storage.config.clearPartType = CLEARPART_TYPE_LINUX
            elif self.buttonGroup.getCurrent() == "freespace":
                self.storage.config.clearPartType = CLEARPART_TYPE_NONE

            self.dispatch.request_steps("autopartitionexecute")
            # cleardiskssel is skipped for upgrades:
            self.dispatch.request_steps_gently("cleardiskssel")

            if self.lvmButton.get_active():
                self.storage.autoPartType = AUTOPART_TYPE_LVM
            else:
                self.storage.autoPartType = AUTOPART_TYPE_PLAIN

            if self.encryptButton.get_active():
                self.storage.encryptedAutoPart = True
            else:
                self.storage.encryptionPassphrase = ""
                self.storage.retrofitPassphrase = False
                self.storage.encryptedAutoPart = False

            self.storage.doAutoPart = True

            self.dispatch.step_data("parttype")["review_checked"] = self.reviewButton.get_active()
            if self.reviewButton.get_active():
                self.dispatch.request_steps("partition")
                # with kickstart bootloader is already scheduled to be skipped:
                self.dispatch.request_steps_gently("bootloader")
            else:
                self.dispatch.skip_steps("partition")
                self.dispatch.skip_steps("bootloader")

        return None

    def getPrev(self):
        # Save the user's selection and restore system selection
        if self.storage.config.clearPartType is not None:
            self.anaconda.clearPartTypeSelection = self.storage.config.clearPartType
        self.storage.config.clearPartType = self.anaconda.clearPartTypeSystem

    def typeChanged(self, *args):
        if self.buttonGroup.getCurrent() == "custom":
            if not self.prevrev:
                self.prevrev = self.reviewButton.get_active()

            self.reviewButton.set_active(True)
            self.reviewButton.set_sensitive(False)
            self.encryptButton.set_sensitive(False)
            self.lvmButton.set_sensitive(False)
        else:
            if self.prevrev:
                self.reviewButton.set_active(self.prevrev)
                self.prevrev = None

            self.reviewButton.set_sensitive(True)
            self.encryptButton.set_sensitive(True)
            self.lvmButton.set_sensitive(True)

    def getScreen(self, anaconda):
        self.anaconda = anaconda
        self.storage = anaconda.storage
        self.intf = anaconda.intf
        self.dispatch = anaconda.dispatch

        if self.anaconda.dir == DISPATCH_FORWARD:
            # Save system's partition type setting and restore user's
            self.anaconda.clearPartTypeSystem = self.storage.config.clearPartType
            if self.anaconda.clearPartTypeSelection is not None:
                self.storage.config.clearPartType = self.anaconda.clearPartTypeSelection

        (self.xml, vbox) = gui.getGladeWidget("autopart.glade", "parttypeTable")
        self.encryptButton = self.xml.get_widget("encryptButton")
        self.reviewButton = self.xml.get_widget("reviewButton")
        self.lvmButton = self.xml.get_widget("lvmButton")
        self.table = self.xml.get_widget("parttypeTable")

        self.prevrev = None

        step_data = self.dispatch.step_data("parttype")
        self.reviewButton.set_active(
            step_data.get("review_checked", self.dispatch.step_enabled("partition")))
        self.encryptButton.set_active(self.storage.encryptedAutoPart)
        self.lvmButton.set_active(self.storage.autoPartType == AUTOPART_TYPE_LVM)

        self.buttonGroup = pixmapRadioButtonGroup()
        self.buttonGroup.addEntry("all", _("Use _All Space"),
                                  pixmap=gui.readImageFromFile("partscheme-all.png"),
                                  descr=_("Removes all partitions on the selected "
                                          "device(s).  This includes partitions "
                                          "created by other operating systems.\n\n"
                                          "<b>Tip:</b> This option will remove "
                                          "data from the selected device(s).  Make "
                                          "sure you have backups."))
        self.buttonGroup.addEntry("replace", _("Replace Existing _Linux System(s)"),
                                  pixmap=gui.readImageFromFile("partscheme-replace.png"),
                                  descr=_("Removes all Linux partitions on the "
                                          "selected device(s). This does "
                                          "not remove other partitions you may have "
                                          "on your storage device(s) (such as VFAT or "
                                          "FAT32).\n\n"
                                          "<b>Tip:</b> This option will remove "
                                          "data from the selected device(s).  Make "
                                          "sure you have backups."))
        self.buttonGroup.addEntry("shrink", _("_Shrink Current System"),
                                  pixmap=gui.readImageFromFile("partscheme-shrink.png"),
                                  descr=_("Shrinks existing partitions to create free "
                                          "space for the default layout."))
        self.buttonGroup.addEntry("freespace", _("Use _Free Space"),
                                  pixmap=gui.readImageFromFile("partscheme-freespace.png"),
                                  descr=_("Retains your current data and partitions and "
                                          "uses only the unpartitioned space on the "
                                          "selected device(s), assuming you have enough "
                                          "free space available."))
        self.buttonGroup.addEntry("custom", _("Create _Custom Layout"),
                                  pixmap=gui.readImageFromFile("partscheme-custom.png"),
                                  descr=_("Manually create your own custom layout on "
                                          "the selected device(s) using our partitioning "
                                          "tool."))

        self.buttonGroup.setToggleCallback(self.typeChanged)

        widget = self.buttonGroup.render()
        self.table.attach(widget, 0, 1, 1, 2)

        # if not set in ks, use UI default
        if self.storage.clearPartChoice:
            self.buttonGroup.setCurrent(self.storage.clearPartChoice)
        else:
            if self.storage.config.clearPartType in (None, CLEARPART_TYPE_LINUX):
                self.buttonGroup.setCurrent("replace")
            elif self.storage.config.clearPartType == CLEARPART_TYPE_NONE:
                self.buttonGroup.setCurrent("freespace")
            elif self.storage.config.clearPartType == CLEARPART_TYPE_ALL:
                self.buttonGroup.setCurrent("all")

        if self.buttonGroup.getCurrent() == "custom":
            # make sure reviewButton is active and not sensitive
            if self.prevrev == None:
                self.prevrev = self.reviewButton.get_active()

            self.reviewButton.set_active(True)
            self.reviewButton.set_sensitive(False)
            self.encryptButton.set_sensitive(False)
            self.lvmButton.set_sensitive(False)

        return vbox
