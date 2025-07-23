#########################################
#                                       #
#   Basic Multiboot for Enigma2         #
#   Support: No Support                 #
#   Made by: Token & WXbet              #
#                                       #
#########################################

from . import PV, PN, PD
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.Console import Console
from Plugins.Plugin import PluginDescriptor
from Components.MenuList import MenuList
from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.Label import Label
from Screens.Standby import TryQuitMainloop

try:
	from Components.SystemInfo import BoxInfo
	PLUGIN_LOAD = BoxInfo.getItem("HasChkrootMultiboot") is None
except:
	PLUGIN_LOAD = True

from os.path import join, isfile
from subprocess import PIPE, Popen
from time import time, sleep
from re import match

def Plugins(**kwargs):
	return [
		PluginDescriptor(name=PN, icon="plugin.png", description=_(PD), where=[PluginDescriptor.WHERE_PLUGINMENU, PluginDescriptor.WHERE_EXTENSIONSMENU], fnc=main),
		PluginDescriptor(name=PN, description=_(PD), where=[PluginDescriptor.WHERE_MENU], fnc=menuHook)
	] if PLUGIN_LOAD else []


def menuHook(menuid, **kwargs):
	if menuid == "shutdown":
		return [(_(PN), main, "multiboot_slots", 12)]
	return []


def main(session, **kwargs):
	session.open(Scripts)


class Scripts(Screen):
	skin = """
	<screen position="center,center" size="660,500" title="MultiBoot Selector">
		<widget name="header" position="10,0" size="640,30" font="Regular;22" halign="center" />
		<widget name="list" position="10,35" size="640,415" scrollbarMode="showOnDemand" />
		<widget name="key_red" position="10,470" size="150,30" backgroundColor="red" foregroundColor="white" font="Regular;20" halign="center" />
		<widget name="key_green" position="170,470" size="150,30" backgroundColor="green" foregroundColor="white" font="Regular;20" halign="center" />
		<widget name="key_yellow" position="330,470" size="150,30" backgroundColor="yellow" foregroundColor="white" font="Regular;20" halign="center" />
		<widget name="key_blue" position="490,470" size="150,30" backgroundColor="blue" foregroundColor="white" font="Regular;20" halign="center" />
	</screen>"""

	def __init__(self, session, args=None):
		Screen.__init__(self, session)
		self.title = "Select Boot Slot - Version %s" % PV
		self["header"] = Label(_("Boot device not found!"))
		self.session = session
		self.cmd = "/usr/bin/multiboot-selector.sh"
		self.slist = []
		self.currentIndex = 0
		self.output_lines = []
		self.reload_list()
		self["list"] = MenuList([item[1] for item in self.slist])
		self["list"].l.setItemHeight(35)

		# colored buttons labels
		self["key_red"] = Label(_("Cancel"))
		self["key_green"] = Label(_("Restart"))
		self["key_yellow"] = Label(_("Reset"))
		self["key_blue"] = Label(_("tbd"))
		self["key_blue"].hide()

		self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
			"ok": self.run,
			"cancel": self.close,
			"red": self.redPressed,
			"green": self.greenPressed,
			"yellow": self.yellowPressed,
			"blue": self.bluePressed
		}, -1)

		self.updateButtons()
		self["list"].onSelectionChanged.append(self.updateButtons)
		self.onLayoutFinish.append(self.selectCurrentLine)


	def run(self):
		slot_name = self["list"].getCurrent()
		slot_idx = next((str(sublist[0]) for sublist in self.slist if sublist[1] == slot_name), -1)
		if slot_name is None or slot_idx == "-1":
			return
		slot_cmd = "%s %s" % (self.cmd, slot_idx)

		def finished_run(result=None):
			self.session.open(TryQuitMainloop, 2)

		self.session.openWithCallback(finished_run, Console, slot_name, cmdlist=[slot_cmd], closeOnSuccess=True)


	def reload_list(self):
		try:
			if not isfile(self.cmd):
				self.slist = [[-1, "Error: File '%s' is not available!" % self.cmd]]
			else:
				# call cmd process
				process = Popen([self.cmd, "list"], stdout=PIPE, stderr=PIPE, universal_newlines=True)
				stdout, stderr = process.communicate()

				for line in stdout.splitlines():
					line = line.rstrip()
					if match(r'^BOOT.*:', line):
						self["header"].setText(_(line))
					elif match(r'^.*\)\ Slot', line):
						entries = line.split()
						image = " ".join(entries[2:])
						self.slist.append([entries[0].split(")")[0] if "Empty" not in image else "-1" , "%s '%s' %s" % (entries[1], entries[0].split(")")[0], image)])
						if line.endswith("Current"):
							self.currentIndex = len(self.slist) - 1
					self.output_lines.append(line)

				if not self.slist:
					self.slist = [[-1, "Error: %s" % self.output_lines[-1]]]
		except Exception as e:
			self.slist = [[-1, "Error: %s" % e]]


	def selectCurrentLine(self):
		self["list"].moveToIndex(self.currentIndex)


	def updateButtons(self):
		"""Hide green button completely if current entry contains 'Empty'."""
		current = self["list"].getCurrent()
		if current and "Empty" in current:
			self["key_green"].hide()
		else:
			self["key_green"].show()


	def redPressed(self):
		self.close()


	def greenPressed(self):
		self.run()


	def yellowPressed(self):
		self.session.open(MessageBox, _("Not implemented yet!"), type=MessageBox.TYPE_INFO, timeout=5)


	def bluePressed(self):
		pass
