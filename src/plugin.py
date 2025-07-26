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
from collections import namedtuple


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
    </screen>"""

    def __init__(self, session, args=None):
        Screen.__init__(self, session)
        self.title = "Select Boot Slot - Version %s" % PV
        self["header"] = Label(_("Boot device not found!"))
        self.session = session
        self.SlotEntry = namedtuple("SlotEntry", ["index", "label"])
        self.cmd = "/usr/bin/multiboot-selector.sh"
        self.slist = []
        self.currentIndex = 0
        self.output_lines = []
        self.reload_list()
        self["list"] = MenuList([entry.label for entry in self.slist])
        if hasattr(self["list"].l, "setItemHeight"):
            self["list"].l.setItemHeight(30)

        self["key_red"] = Button(_("Cancel"))
        self["key_red_pixmap"] = Pixmap()
        self["key_green"] = Button(_("Restart"))
        self["key_green_pixmap"] = Pixmap()
        self["key_yellow"] = Button(_("Reset"))
        self["key_yellow_pixmap"] = Pixmap()

        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "ok": self.greenPressed,
            "cancel": self.redPressed,
            "red": self.redPressed,
            "green": self.greenPressed,
            "yellow": self.yellowPressed,
        }, -1)

        self.updateButtons()
        self["list"].onSelectionChanged.append(self.updateButtons)
        self.onLayoutFinish.append(self.onLayoutFinished)

    def run(self):
        slot_name = self["list"].getCurrent()
        slot_idx = next((str(s.index) for s in self.slist if s.label == slot_name), "-1")
        if slot_name is None or slot_idx == "-1":
            return
        slot_cmd = "%s %s" % (self.cmd, slot_idx)

        def finished_run(result=None):
            self.session.open(TryQuitMainloop, 2)

        self.session.openWithCallback(finished_run, Console, slot_name, cmdlist=[slot_cmd], closeOnSuccess=True)

    def reload_list(self):
        try:
            if not isfile(self.cmd):
                self.slist = [self.SlotEntry(-1, "Error: File '%s' is not available!" % self.cmd)]
            else:
                process = Popen([self.cmd, "list"], stdout=PIPE, stderr=PIPE, universal_newlines=True)
                stdout, stderr = process.communicate()

                for line in stdout.splitlines():
                    line = line.rstrip()
                    if match(r'^\s*BOOT.*?:', line):
                        self["header"].setText(_(line))
                    elif match(r'^.*\)\ Slot', line):
                        entries = line.split()
                        image = " ".join(entries[2:])
                        idx = entries[0].split(")")[0]
                        label = "%s '%s' %s" % (entries[1], idx, image)
                        idx = idx if "Empty" not in image else "-1"
                        self.slist.append(self.SlotEntry(idx, label))
                        if line.endswith("Current"):
                            self.currentIndex = len(self.slist) - 1
                    self.output_lines.append(line)

                if not self.slist:
                    self.slist = [self.SlotEntry(-1, "Error: %s" % self.output_lines[-1])]
        except Exception as e:
            self.slist = [self.SlotEntry(-1, "Error: %s" % e)]

    def onLayoutFinished(self):
        try:
            # select current running image in the list
            self["list"].moveToIndex(self.currentIndex)
            # reload button images
            self.reloadButton(["red", "green", "yellow"])
        except Exception:
            pass

    def reloadButton(self, colors):
        if isinstance(colors, str):
            colors = [colors]

        skin_paths = [
            "skin_default/buttons/{}.png",
            "nn2_default/buttons/{}.png",
            "skin_default/buttons/{}.svg"
        ]

        for color in colors:
            pixmap = self.get("key_{}_pixmap".format(color))
            if not pixmap:
                continue
            for path_template in skin_paths:
                path = resolveFilename(SCOPE_SKIN_IMAGE, path_template.format(color))
                if fileExists(path):
                    pixmap.instance.setPixmapFromFile(path)
                    break

    def updateButtons(self):
        current = self["list"].getCurrent() or ""
        func = "hide" if not current or any(x in current for x in ("Empty", "Error:")) else "show"
        for widget in ("key_green", "key_green_pixmap"):
            getattr(self[widget], func)()

    def redPressed(self):
        self.close()

    def greenPressed(self):
        self.run()

    def yellowPressed(self):
        self.session.open(MessageBox, _("Please boot into the root image and use the provided MultiBoot Manager."), type=MessageBox.TYPE_INFO, timeout=5)
