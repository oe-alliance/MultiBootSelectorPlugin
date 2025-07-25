# Legacy MultiBoot Selector Plugin for Enigma2

[![License: GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.html#license-text)
[![Lint Status](https://github.com/oe-alliance/MultiBootSelectorPlugin/actions/workflows/lint.yml/badge.svg)](https://github.com/oe-alliance/MultiBootSelectorPlugin/actions)
[![Build Status](https://github.com/oe-alliance/MultiBootSelectorPlugin/actions/workflows/release.yml/badge.svg)](https://github.com/oe-alliance/MultiBootSelectorPlugin/actions)
[![Plugin Version](https://img.shields.io/github/v/tag/oe-alliance/MultiBootSelectorPlugin?label=Latest%20Version&color=darkviolet)](https://github.com/oe-alliance/MultiBootSelectorPlugin/tags)
[![Latest Release](https://img.shields.io/github/release-date/oe-alliance/MultiBootSelectorPlugin?label=From&color=darkviolet)](https://github.com/oe-alliance/MultiBootSelectorPlugin/releases/latest)
[![GitHub all releases](https://img.shields.io/github/downloads/oe-alliance/MultiBootSelectorPlugin/total.svg?label=Downloads&color=darkgrey)](https://github.com/oe-alliance/MultiBootSelectorPlugin/releases)

## 📦 Overview

**Legacy MultiBoot Selector Plugin for Enigma2** is a lightweight plugin enabling users to view and select available multiboot slots directly from their Enigma2 receiver GUI. It integrates seamlessly with Images without built-in multiboot support.

---

## 🚀 Features

- Calls backend script for slot switching
- Dynamic list of available multiboot slots
- Displays current active boot slot
- Safe restart into the selected slot
- Accessible via Plugin Menu, Extensions Menu, and Shutdown Menu
- Clean and minimal user interface

---

## 🖼️ Screenshots

| OpenATV | OpenPLi | DreamOS | NewNigma2 |
|---------|---------|---------|-----------|
| ![OpenATV screenshot](screenshots/openatv.png) | ![OpenPLi screenshot](screenshots/openpli.png) | ![DreamOS screenshot](screenshots/dreamos.png) | ![NewNigma2 screenshot](screenshots/newnigma2.png) |

---

## 🛠️ Technical Details

- **Plugin Type:** Enigma2 python plugin
- **Backend Dependency:** `/usr/bin/multiboot-selector.sh` with executable permissions
- **Tested On:** several images without built-in multiboot support
- **Load Condition:** Only loads if `BoxInfo.getItem("HasChkrootMultiboot")` is `None` or unavailable (therefore it is not loaded on current OE Alliance images with integrated multiboot support)

---

### 🔧 How It Works

1. Lists slots by running:
   ```bash
   /usr/bin/multiboot-selector.sh list
2. Displays each slot in a selectable GUI list.
3. On selection, runs:
   ```bash
   /usr/bin/multiboot-selector.sh <slot_number>
4. Initiates a safe reboot to boot from the selected slot.

---

### 📂 Installation

1. Go to the [Releases](https://github.com/oe-alliance/MultiBootSelectorPlugin/releases) page and download the latest .ipk or .deb package for your image.
2. Transfer the package to your Enigma2 receiver via FTP, SCP, or USB.
3. Install it via command line:
   - For .ipk (older OpenATV, OpenPLi, etc.):
      ```bash
      opkg install /path/to/enigma2-plugin-extensions-multibootselector_*-r0_all.ipk

   - For .deb (DreamOS, NewNigma2, etc.):
      ```bash
      apt install /path/to/enigma2-plugin-extensions-multibootselector_*-r0_all.deb
4. Ensure backend script is available and executable ([current version](https://raw.githubusercontent.com/oe-alliance/oe-alliance-core/refs/heads/5.6-beta/meta-oe/recipes-kernel/chkroot/multiboot-selector/multiboot-selector.sh)):
   ```bash
   chmod +x /usr/bin/multiboot-selector.sh
5. Restart Enigma2 GUI or reboot your device.

---

### ❗ Limitations

- Requires an existing `/usr/bin/multiboot-selector.sh` script for functionality.

---

### 📜 License
This plugin is released under GPLv3. See [LICENSE](https://www.gnu.org/licenses/gpl-3.0.html#license-text) for full details.

---

### 🤝 Contributing
Pull requests are welcome for:
- Feature enhancements
- Translations
- Integration improvements

Please fork the repository, create a feature branch, and submit a Pull Request.
