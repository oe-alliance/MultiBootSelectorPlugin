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
from Components.Pixmap import Pixmap
from Components.Button import Button
from Components.Label import Label
from Screens.Standby import TryQuitMainloop
from Tools.Directories import fileExists, resolveFilename, SCOPE_SKIN_IMAGE

try:
    from Components.SystemInfo import BoxInfo
    PLUGIN_LOAD = BoxInfo.getItem("HasChkrootMultiboot") is None
except Exception:
    PLUGIN_LOAD = True

from os.path import isfile
from subprocess import PIPE, Popen
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
    <screen position="center,center" size="660,520" title="MultiBoot Selector">
        <widget name="header" position="10,0" size="640,30" font="Regular;22" halign="center" />
        <widget name="list" position="10,35" size="640,415" scrollbarMode="showOnDemand" />

        <widget name="key_red_pixmap" pixmap="skin_default/buttons/red.png" position="10,470" size="150,40" scale="stretch" alphatest="on" />
        <widget name="key_red" position="10,470" size="150,40" font="Regular;20" zPosition="1" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />

        <widget name="key_green_pixmap" pixmap="skin_default/buttons/green.png" position="170,470" size="150,40" scale="stretch" alphatest="on" />
        <widget name="key_green" position="170,470" size="150,40" font="Regular;20" zPosition="1" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />

        <widget name="key_yellow_pixmap" pixmap="skin_default/buttons/yellow.png" position="330,470" size="150,40" scale="stretch" alphatest="on" />
        <widget name="key_yellow" position="330,470" size="150,40" font="Regular;20" zPosition="1" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />

        <widget name="key_blue_pixmap" pixmap="skin_default/buttons/blue.png" position="330,470" size="150,40" scale="stretch" alphatest="on" />
        <widget name="key_blue" position="490,470" size="150,40" font="Regular;20" zPosition="1" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
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
        self["list"].l.setItemHeight(30)

        self["key_red"] = Button(_("Cancel"))
        self["key_red_pixmap"] = Pixmap()
        self["key_green"] = Button(_("Restart"))
        self["key_green_pixmap"] = Pixmap()
        self["key_yellow"] = Button(_("Reset"))
        self["key_yellow_pixmap"] = Pixmap()
        self["key_blue"] = Button(_("tbd"))
        self["key_blue"].hide()
        self["key_blue_pixmap"] = Pixmap()
        self["key_blue_pixmap"].hide()

        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "ok": self.greenPressed,
            "cancel": self.redPressed,
            "red": self.redPressed,
            "green": self.greenPressed,
            "yellow": self.yellowPressed,
            "blue": self.bluePressed
        }, -1)

        self.updateButtons()
        self["list"].onSelectionChanged.append(self.updateButtons)
        self.onLayoutFinish.append(self.onLayoutFinished)

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
                process = Popen([self.cmd, "list"], stdout=PIPE, stderr=PIPE, universal_newlines=True)
                stdout, stderr = process.communicate()

                for line in stdout.splitlines():
                    line = line.rstrip()
                    if match(r'^BOOT.*:', line):
                        self["header"].setText(_(line))
                    elif match(r'^.*\)\ Slot', line):
                        entries = line.split()
                        image = " ".join(entries[2:])
                        self.slist.append([entries[0].split(")")[0] if "Empty" not in image else "-1", "%s '%s' %s" % (entries[1], entries[0].split(")")[0], image)])
                        if line.endswith("Current"):
                            self.currentIndex = len(self.slist) - 1
                    self.output_lines.append(line)

                if not self.slist:
                    self.slist = [[-1, "Error: %s" % self.output_lines[-1]]]
        except Exception as e:
            self.slist = [[-1, "Error: %s" % e]]

    def onLayoutFinished(self):
        try:
            # select current running image in the list
            self["list"].moveToIndex(self.currentIndex)
            # reload button images
            self.reloadButton("red")
            self.reloadButton("green")
            self.reloadButton("yellow")
            self.reloadButton("blue")
        except Exception:
            pass

    def reloadButton(self, color):
        image_png = resolveFilename(SCOPE_SKIN_IMAGE, "skin_default/buttons/%s.png" % color)
        if fileExists(image_png):
            self["key_%s_pixmap" % color].instance.setPixmapFromFile(image_png)
        image_nn2 = resolveFilename(SCOPE_SKIN_IMAGE, "nn2_default/buttons/%s.png" % color)
        if fileExists(image_nn2):
            self["key_%s_pixmap" % color].instance.setPixmapFromFile(image_nn2)
        image_svg = resolveFilename(SCOPE_SKIN_IMAGE, "skin_default/buttons/%s.svg" % color)
        if fileExists(image_svg):
            self["key_%s_pixmap" % color].instance.setPixmapFromFile(image_svg)
        return

    def updateButtons(self):
        current = self["list"].getCurrent()
        if current and "Empty" in current:
            self["key_green"].hide()
            self["key_green_pixmap"].hide()
        else:
            self["key_green"].show()
            self["key_green_pixmap"].show()

    def redPressed(self):
        self.close()

    def greenPressed(self):
        self.run()

    def yellowPressed(self):
        self.session.open(MessageBox, _("Not implemented yet!"), type=MessageBox.TYPE_INFO, timeout=5)

    def bluePressed(self):
        pass
