#!/usr/bin/python
#
# Copyright (C) 2010  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: Chris Lumens <clumens@redhat.com>
import unittest

# Verify that each kickstart command in anaconda uses the correct version of
# that command as provided by pykickstart.  That is, if there's an FC3 and an
# F10 version of a command, make sure anaconda >= F10 uses the F10 version.
class CommandVersionTestCase(unittest.TestCase):
    def setUp(self):
        import kickstart
        import pykickstart.version

        self.handler = pykickstart.version.makeVersion(kickstart.ver)

    def runTest(self):
        for (commandName, commandObj) in kickstart.commandMap.iteritems():
            baseClass = commandObj().__class__.__bases__[0]
            pykickstartClass = self.handler.commands[commandName].__class__
            self.assertEqual(baseClass.__name__, pykickstartClass.__name__)

# Do the same thing as CommandVersionTestCase, but for data objects.
class DataVersionTestCase(unittest.TestCase):
    def setUp(self):
        import kickstart
        import pykickstart.version

        self.handler = pykickstart.version.makeVersion(kickstart.ver)

    def runTest(self):
        for (dataName, dataObj) in kickstart.dataMap.iteritems():
            baseClass = dataObj().__class__.__bases__[0]

            # pykickstart does not expose data objects a mapping the way it
            # does command objects.
            pykickstartClass = eval("self.handler.%s" % dataName)

            self.assertEqual(baseClass.__name__, pykickstartClass.__name__)
def suite():
    suite = unittest.TestSuite()
    suite.addTest(CommandVersionTestCase())
    suite.addTest(DataVersionTestCase())
    return suite

s = suite()
unittest.TextTestRunner(verbosity=2).run(s)