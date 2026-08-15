# -*- coding: utf-8 -*-
#########################################
#                                       #
#   Basic Multiboot for Enigma2         #
#   Support: No Support                 #
#   Made by: WXbet & Token              #
#                                       #
#########################################

try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen
from os import path, environ
from subprocess import Popen, PIPE
from re import match, escape, search, sub
from collections import namedtuple
from ssl import _create_unverified_context as unverified_ssl
from json import loads as json_loads, dumps as json_dumps
from datetime import datetime
from time import localtime

try:
    from Components.SystemInfo import BoxInfo
    PLUGIN_LOAD = True if "MBSP_FORCE_LOAD" in environ else not BoxInfo.getItem("canMultiBoot")
except (ImportError, AttributeError):
    PLUGIN_LOAD = True
from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.Label import Label
from Components.Input import Input
from Components.MenuList import MenuList
from Components.Pixmap import Pixmap
from Plugins.Plugin import PluginDescriptor
from Screens.Console import Console
from Screens.InputBox import InputBox
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
    <screen position="center,center" size="900,560" title="MultiBoot Selector">
        <widget name="header" position="10,10" size="880,40" font="Regular;22" halign="center" valign="center" foregroundColor="#00e0ff" />
        <widget name="list" position="10,60" size="880,415" scrollbarMode="showOnDemand" />

        <widget name="key_red_pixmap" pixmap="skin_default/buttons/red.png" position="10,510" size="210,40" scale="stretch" alphatest="on" />
        <widget name="key_red" position="10,510" size="210,40" font="Regular;20" zPosition="1" halign="center" valign="center" transparent="1" shadowColor="black" shadowOffset="-2,-2" />

        <widget name="key_green_pixmap" pixmap="skin_default/buttons/green.png" position="233,510" size="210,40" scale="stretch" alphatest="on" />
        <widget name="key_green" position="233,510" size="210,40" font="Regular;20" zPosition="1" halign="center" valign="center" transparent="1" shadowColor="black" shadowOffset="-2,-2" />

        <widget name="key_yellow_pixmap" pixmap="skin_default/buttons/yellow.png" position="456,510" size="210,40" scale="stretch" alphatest="on" />
        <widget name="key_yellow" position="456,510" size="210,40" font="Regular;20" zPosition="1" halign="center" valign="center" transparent="1" shadowColor="black" shadowOffset="-2,-2" />

        <widget name="key_blue_pixmap" pixmap="skin_default/buttons/blue.png" position="679,510" size="210,40" scale="stretch" alphatest="on" />
        <widget name="key_blue" position="679,510" size="210,40" font="Regular;20" zPosition="1" halign="center" valign="center" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
    </screen>
    """

    def __init__(self, session, args=None):
        Screen.__init__(self, session)
        self.title = "Select Boot Slot - Version %s" % PV
        self["header"] = Label(_("Boot device not found!"))
        self.session = session
        self.jsonRelease = None
        self.newVersion = PV
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
        self["key_yellow"] = Button(_("Rename"))
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

        self["list"].onSelectionChanged.append(self.updateButtons)
        self.onLayoutFinish.append(self.onLayoutFinished)

    def bootSelectedSlot(self):
        slot_name = self["list"].getCurrent()
        slot_idx = next((str(s.index) for s in self.slist if s.label == slot_name), "-1")
        if slot_name is None or slot_idx == "-1":
            return
        slot_cmd = "%s %s" % (slotCmd, slot_idx)

        self.session.openWithCallback(lambda *args: self.restartGUI(mode=2, result=args[0] if args else None), Console, slot_name, cmdlist=[slot_cmd], closeOnSuccess=True)

    def reload_list(self):
        self.slist = []
        output_lines = []

        try:
            if not path.isfile(slotCmd):
                self.slist = [slotEntry(-1, _("Error: File '%s' is not available!") % slotCmd)]
            else:
                process = Popen([slotCmd, "list"], stdout=PIPE, universal_newlines=True)
                stdout = process.communicate()[0]

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

                if not self.slist:
                    error_msg = output_lines[-1] if output_lines else "No slots found"
                    self.slist = [slotEntry(-1, "Error: %s" % error_msg)]
        except Exception as e:  # pylint: disable=broad-except
            self.slist = [slotEntry(-1, "Error: %s" % e)]

    def onLayoutFinished(self):
        # select current running image in the list
        self["list"].moveToIndex(self.currentIndex)
        # reload button images
        self.reloadButton(["red", "green", "yellow", "blue"])
        # show/hide buttons
        self.updateButtons()

    def reloadButton(self, colors):
        if isinstance(colors, str):
            colors = [colors]

        skin_paths = [
            "skin_default/buttons/{}.png",
            "nn2_default/buttons/{}.png",
            "skin_default/buttons/{}.svg"
        ]

        for color in colors:
            pixmap = self.get("key_{}_pixmap".format(color), None)
            if not pixmap:
                continue
            for path_template in skin_paths:
                resolved_path = resolveFilename(SCOPE_SKIN_IMAGE, path_template.format(color))
                if fileExists(resolved_path):
                    pixmap.instance.setPixmapFromFile(resolved_path)
                    break

    def updateButtons(self, result=None):
        current = self["list"].getCurrent() or ""
        func = "hide" if not current or any(x in current for x in ("Empty", "Error:")) else "show"
        for widget in ("key_green", "key_green_pixmap", "key_yellow", "key_yellow_pixmap"):
            getattr(self[widget], func)()

    def restartGUI(self, mode=None, result=None):
        if result or result is None:
            self.session.open(TryQuitMainloop, mode)

    def onEditSlotName(self, new_slot_name):  # pylint: disable=too-many-branches
        if new_slot_name is None:
            return
        new_slot_name = new_slot_name.strip()

        current_label = self["list"].getCurrent()
        slot = next((s for s in self.slist if s.label == current_label), None)
        if not slot:
            return

        # Validate slot index
        try:
            slot_index = int(slot.index)
            if slot_index < 0:
                raise ValueError("Invalid slot index")
        except (ValueError, TypeError):
            self.session.open(MessageBox, _("Invalid slot index"), MessageBox.TYPE_ERROR)
            return

        # Replace only text between ':' and '(' — keep everything else unchanged
        updated_label = sub(r"(:\s*)(.*?)(\s*\()", r"\1%s\3" % new_slot_name, slot.label)
        updated_entry = slotEntry(slot.index, updated_label)
        idx = self.slist.index(slot)
        self.slist[idx] = updated_entry

        rename_success = True
        try:
            if path.isfile(slotCmd):
                # Use list form to avoid shell injection
                process = Popen(
                    [slotCmd, "rename", str(slot_index), new_slot_name],
                    stdout=PIPE,
                    universal_newlines=True
                )
                stdout = process.communicate()[0]

                if process.returncode != 0:
                    rename_success = False
                    error_msg = stdout.strip() or "Unknown error (exit code %d)" % process.returncode
                    self.session.open(MessageBox, _("Error while renaming slot:\n%s") % error_msg, MessageBox.TYPE_ERROR)
        except Exception as e:  # pylint: disable=broad-except
            rename_success = False
            self.session.open(MessageBox, _("Rename failed:\n%s") % e, MessageBox.TYPE_ERROR)

        # Reload slot list from the system if rename succeeded
        if rename_success:
            try:
                self.slist = []  # clear old list to avoid duplication
                self.reload_list()

                # Bounds check for index
                if self.slist:
                    new_idx = min(idx, len(self.slist) - 1)
                else:
                    new_idx = 0

                self["list"].setList([s.label for s in self.slist])
                self["list"].moveToIndex(new_idx)

                if not new_slot_name:
                    self.session.open(MessageBox, _("Slot name was reset to default."), MessageBox.TYPE_INFO, timeout=3)
            except Exception as e:  # pylint: disable=broad-except
                self.session.open(MessageBox, _("Slot renamed but reload failed:\n%s") % e, MessageBox.TYPE_WARNING)
        else:
            # Fallback: keep local updated label if rename failed
            self["list"].setList([s.label for s in self.slist])
            self["list"].moveToIndex(idx)

    def redPressed(self):
        self.close()

    def greenPressed(self):
        self.bootSelectedSlot()

    def yellowPressed(self):
        current = self["list"].getCurrent()
        if not current or "Error" in current or "Empty" in current:
            return

        m = search(r"Slot\s+'([^']+)'\s+([\w\-]+):\s*(.*?)\s*\(", current)
        if not m:
            self.session.open(MessageBox, _("No valid slot entry found."), MessageBox.TYPE_ERROR)
            return

        slot_num, slot_type, slot_name = m.groups()
        slot_name = slot_name.strip()

        title_text = _("Enter new name for Slot '%s' %s (leave empty to reset):") % (slot_num, slot_type)

        self.session.openWithCallback(
            self.onEditSlotName,
            InputBox,
            title=title_text,
            text=slot_name,
            type=Input.TEXT
        )

    def bluePressed(self):
        def format_date(date_str, out_fmt="%Y-%m-%d %H:%M:%S"):
            # parse the UTC time
            utc_dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
            # convert to timestamp
            timestamp = (utc_dt - datetime(1970, 1, 1)).total_seconds()
            # convert to local time struct, handles Daylight Saving Time (DST)
            local_struct = localtime(timestamp)
            # convert back to datetime and format
            return datetime(*local_struct[:6]).strftime(out_fmt)

        def onDownloadError(error):
            message = error.getErrorMessage() if hasattr(error, "getErrorMessage") else str(error)
            self.session.open(MessageBox, message, MessageBox.TYPE_ERROR)

        def doPluginUpdate(result=None):
            def onDownloadSuccess(result):
                cmd = "%s %s" % (installer["cmd"], local_path)
                self.session.openWithCallback(
                    self.updateDone,
                    Console,
                    _("Updating %s plugin to version %s..." % (PN, self.newVersion)),
                    cmdlist=["echo %s" % cmd, cmd],
                    closeOnSuccess=False
                )

            if result:
                downloadPage(target_url.encode("utf-8"), local_path).addCallbacks(
                    callback=onDownloadSuccess,
                    errback=onDownloadError
                )

        try:
            if not self["key_blue"].instance.isVisible():
                return
            target_url = None
            self.jsonRelease = json_loads(urlopen(updateUrl, context=unverified_ssl()).read().decode("utf-8"))
            self.newVersion = str(self.jsonRelease.get("name"))
            prerelease = str(self.jsonRelease.get("prerelease", "false")).lower() == "true"
            assets = self.jsonRelease.get("assets", [])
            installer = {"cmd": "dpkg -i --force-downgrade", "ext": "deb"} if fileExists("/usr/bin/apt") else {"cmd": "opkg install --force-reinstall", "ext": "ipk"}
            pkgName = pkgSearchName % self.newVersion

            filtered_assets = [
                {
                    "name": asset.get("name", ""),
                    "size": asset.get("size", 0),
                    "digest": asset.get("digest", ""),
                    "download_count": asset.get("download_count", 0),
                    "updated_at": asset.get("updated_at", ""),
                    "browser_download_url": asset.get("browser_download_url", "")
                }
                for asset in assets
            ]
            for asset in filtered_assets:
                pattern = r"^%s\.%s$" % (escape(pkgName), escape(installer["ext"]))
                if match(pattern, asset.get("name", "")):
                    target_url = str(asset.get("browser_download_url"))
                    release_info = {
                        "release": "pre-" if prerelease else "",
                        "file_date": format_date(str(asset.get("updated_at"))),
                        "file_size": round(float(asset.get("size")) / 1024, 2),
                        "file_downloads": str(asset.get("download_count")),
                        "sha": str(asset.get("digest")).split(":")
                    }
                    break
            print("[%s] Found version %s at %s" % (PN, self.newVersion, target_url))  # pylint: disable=superfluous-parens

            if not target_url:
                onDownloadError(_("No suitable %s package found!" % installer["ext"]) + "\n\n%s.%s\n%s" % (pkgName, installer["ext"], str(json_dumps(filtered_assets, indent=2))))
                return

            local_path = "/tmp/%s" % target_url.rsplit("/", 1)[-1]

            self.session.openWithCallback(
                doPluginUpdate,
                MessageBox,
                _(
                    "Do you want to update to latest %srelease version %s?\n\n"
                    "Release date: %s\n"
                    "Package size: %.2f KB\n"
                    "GitHub downloads: %s\n\n"
                    "URL:\n%s\n\n"
                    "Checksum (%s):\n%s"
                ) % (
                    release_info["release"],
                    self.newVersion,
                    release_info["file_date"],
                    release_info["file_size"],
                    release_info["file_downloads"],
                    target_url,
                    release_info["sha"][0],
                    release_info["sha"][-1]
                ),
                type=MessageBox.TYPE_YESNO,
                timeout=15,
                default=True
            )
        except Exception as e:  # pylint: disable=broad-except
            print("[%s] Download error %s at %s" % (PN, repr(e), target_url))  # pylint: disable=superfluous-parens
            onDownloadError(_("Update check failed: ") + str(e) + "\n\nURLs: %s, %s" % (updateUrl, str(target_url)))

    def updateDone(self, result=None):
        self.session.openWithCallback(
            lambda *args: self.restartGUI(mode=3, result=args[0] if args else None),
            MessageBox,
            _("Do you want to restart the GUI?"),
            type=MessageBox.TYPE_YESNO,
            timeout=10
        )
