#########################################
#                                       #
#   Basic Multiboot for Enigma2         #
#   Support: No Support                 #
#   Made by: Token & WXbet              #
#                                       #
#########################################

try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen
from os.path import isfile
from subprocess import Popen, PIPE
from re import match, escape
from collections import namedtuple
from ssl import _create_unverified_context as unverified_ssl
from json import loads as json_loads, dumps as json_dumps

try:
    from Components.SystemInfo import BoxInfo
    PLUGIN_LOAD = BoxInfo.getItem("HasChkrootMultiboot") is None
except (ImportError, AttributeError):
    PLUGIN_LOAD = True
from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.Label import Label
from Components.MenuList import MenuList
from Components.Pixmap import Pixmap
from Plugins.Plugin import PluginDescriptor
from Screens.Console import Console
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Standby import TryQuitMainloop
from Tools.Directories import fileExists, resolveFilename, SCOPE_SKIN_IMAGE
from twisted.web.client import downloadPage

from . import PV, PN, PD

slotEntry = namedtuple("SlotEntry", ["index", "label"])
slotCmd = "/usr/bin/multiboot-selector.sh"
updateUrl = "https://api.github.com/repos/oe-alliance/MultiBootSelectorPlugin/releases/latest"
pkgSearchName = "enigma2-plugin-extensions-multibootselector_%s-r0_all"


def Plugins(**kwargs):
    return [
        PluginDescriptor(name=PN, icon="plugin.png", description=_(PD), where=[PluginDescriptor.WHERE_PLUGINMENU, PluginDescriptor.WHERE_EXTENSIONSMENU], fnc=main),
        PluginDescriptor(name=PN, description=_(PD), where=[PluginDescriptor.WHERE_MENU], fnc=menuHook)
    ] if PLUGIN_LOAD else []


def menuHook(menuid, **kwargs):
    if menuid == "shutdown":
        return [(PN, main, "multiboot_slots", 12)]
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

        <widget name="key_blue_pixmap" pixmap="skin_default/buttons/blue.png" position="490,470" size="150,40" scale="stretch" alphatest="on" />
        <widget name="key_blue" position="490,470" size="150,40" font="Regular;20" zPosition="1" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
    </screen>"""

    def __init__(self, session, args=None):
        Screen.__init__(self, session)
        self.title = "Select Boot Slot - Version %s" % PV
        self["header"] = Label(_("Boot device not found!"))
        self.session = session
        self.slist = []
        self.currentIndex = 0
        self.reload_list()
        self["list"] = MenuList([entry.label for entry in self.slist])
        if hasattr(self["list"].l, "setItemHeight"):
            self["list"].l.setItemHeight(30)

        self["key_red"] = Button(_("Cancel"))
        self["key_red_pixmap"] = Pixmap()
        self["key_green"] = Button(_("Restart"))
        self["key_green_pixmap"] = Pixmap()
        self["key_yellow"] = Button(_("More"))
        self["key_yellow_pixmap"] = Pixmap()
        self["key_blue"] = Button(_("Update"))
        self["key_blue_pixmap"] = Pixmap()

        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "ok": self.greenPressed,
            "cancel": self.redPressed,
            "red": self.redPressed,
            "green": self.greenPressed,
            "yellow": self.yellowPressed,
            "blue": self.bluePressed,
        }, -1)

        self.updateButtons()
        self["list"].onSelectionChanged.append(self.updateButtons)
        self.onLayoutFinish.append(self.onLayoutFinished)

    def run(self):
        slot_name = self["list"].getCurrent()
        slot_idx = next((str(s.index) for s in self.slist if s.label == slot_name), "-1")
        if slot_name is None or slot_idx == "-1":
            return
        slot_cmd = "%s %s" % (slotCmd, slot_idx)

        self.session.openWithCallback(lambda *args: self.restartGUI(mode=2, result=args[0] if args else None), Console, slot_name, cmdlist=[slot_cmd], closeOnSuccess=True)

    def reload_list(self):
        output_lines = []

        try:
            if not isfile(slotCmd):
                self.slist = [slotEntry(-1, "Error: File '%s' is not available!" % slotCmd)]
            else:
                process = Popen([slotCmd, "list"], stdout=PIPE, stderr=PIPE, universal_newlines=True)
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
                        self.slist.append(slotEntry(idx, label))
                        if line.endswith("Current"):
                            self.currentIndex = len(self.slist) - 1
                    output_lines.append(line)

                if not self.slist or stderr:
                    self.slist = [slotEntry(-1, "Error: %s" % output_lines[-1])]
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.slist = [slotEntry(-1, "Error: %s" % e)]

    def onLayoutFinished(self):
        # select current running image in the list
        self["list"].moveToIndex(self.currentIndex)
        # reload button images
        self.reloadButton(["red", "green", "yellow", "blue"])

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

    def restartGUI(self, mode=None, result=None):
        if result or result is None:
            self.session.open(TryQuitMainloop, mode)

    def redPressed(self):
        self.close()

    def greenPressed(self):
        self.run()

    def yellowPressed(self):
        self.session.open(MessageBox, _("For advanced features like slot management, please boot into the root image and use the provided MultiBoot Manager."), type=MessageBox.TYPE_INFO, timeout=5, title=_("Advanced features"))

    def bluePressed(self):
        def onDownloadError(error):
            message = error.getErrorMessage() if hasattr(error, "getErrorMessage") else str(error)
            self.session.open(MessageBox, message, MessageBox.TYPE_ERROR, title=_("Update error"))

        def doPluginUpdate(result=None):
            def onDownloadSuccess(result):
                cmd = "%s %s" % (installer["cmd"], local_path)
                self.session.openWithCallback(
                    self.updateDone,
                    Console,
                    _("Updating %s plugin to version %s..." % (PN, version)),
                    cmdlist=["echo %s" % cmd, cmd],
                    closeOnSuccess=False
                )

            if result:
                downloadPage(target_url.encode("utf-8"), local_path).addCallbacks(
                    callback=onDownloadSuccess,
                    errback=onDownloadError
                )

        try:
            target_url = None
            release = json_loads(urlopen(updateUrl, context=unverified_ssl()).read().decode("utf-8"))
            version = str(release.get("tag_name"))
            assets = release.get("assets", [])
            installer = {"cmd": "dpkg -i --force-downgrade", "ext": "deb"} if fileExists("/usr/bin/apt") else {"cmd": "opkg install --force-reinstall", "ext": "ipk"}
            pkgName = pkgSearchName % version

            filtered_assets = [
                {
                    "name": asset.get("name", ""),
                    "browser_download_url": asset.get("browser_download_url")
                }
                for asset in assets
            ]
            for asset in filtered_assets:
                pattern = r"^%s\.%s$" % (escape(pkgName), escape(installer["ext"]))
                if match(pattern, asset.get("name", "")):
                    target_url = str(asset.get("browser_download_url"))
                    break
            print("%s" % PN, "%s - %s" % (version, target_url))

            if not target_url:
                onDownloadError(_("No suitable %s package found!" % installer["ext"]) + "\n\n%s.%s\n%s" % (pkgName, installer["ext"], str(json_dumps(filtered_assets, indent=2))))
                return

            local_path = "/tmp/%s" % target_url.rsplit("/", 1)[-1]

            self.session.openWithCallback(
                doPluginUpdate,
                MessageBox,
                _("Do you want to update to latest version %s?\n\nURL: %s") % (version, target_url),
                type=MessageBox.TYPE_YESNO,
                timeout=10,
                default=True,
                title=_("Update %s") % PN
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            print("%s" % PN, str(e), updateUrl)
            onDownloadError(_("Update check failed: ") + str(e) + "\n\nURLs: %s, %s" % (updateUrl, str(target_url)))

    def updateDone(self, result=None):
        self.session.openWithCallback(
            lambda *args: self.restartGUI(mode=3, result=args[0] if args else None),
            MessageBox,
            _("Do you want to restart the GUI?"),
            type=MessageBox.TYPE_YESNO,
            timeout=10,
            title=_("Update finished")
        )
