#!/bin/bash

# ======================================================================
# Multiboot Selector - BusyBox Compatible Version
# ======================================================================
#
# This script lets you manage and switch Multiboot images by updating
# the STARTUP file on supported Enigma2 devices.
#
# It auto-detects available STARTUP / STARTUP_* files and validates
# images by mounting their corresponding root devices.
#
# Behavior:
#   • If a slot has no '/usr/lib/enigma.conf' file in its root device, one is
#     automatically created with the detected default image information.
#
# Usage:
#   • No parameters
#       → Starts an interactive menu to choose a slot. No reboot.
#
#   • list
#       → Prints the list of available slots. For automation.
#
#   • <slot_number>
#       → Changes the boot image to the given slot by copying its
#         STARTUP file to /boot/STARTUP.  No reboot.
#
#   • rename <slot_number> <new_name>
#       → Sets a custom display name for the slot (writes to /usr/lib/enigma.conf).
#
#   • rename <slot_number>
#       → Resets the slot name to default (deletes /usr/lib/enigma.conf).
#
# ======================================================================

echo "Multiboot Selector - Starting..."

declare -A known_distros=(
    ["beyonwiz"]="Beyonwiz"
    ["blackhole"]="Black Hole"
    ["egami"]="EGAMI"
    ["openatv"]="OpenATV"
    ["openbh"]="OpenBH"
    ["opendroid"]="OpenDroid"
    ["openeight"]="OpenEight"
    ["openhdf"]="OpenHDF"
    ["opennfr"]="OpenNFR"
    ["openpli"]="OpenPLi"
    ["openspa"]="OpenSpa"
    ["openvision"]="Open Vision"
    ["openvix"]="OpenViX"
    ["sif"]="Sif"
    ["teamblue"]="teamBlue"
    ["vti"]="VTi"
    ["newnigma2"]="Newnigma2"
    ["pure2"]="PurE2"
    ["dreambox"]="DreamOS"
    ["opendreambox"]="OpenDreambox"
    ["gp"]="GeminiProject"
    ["unknown"]="Unknown Distro"
)

detect_multiboot() {
    # chkroot - special multiboot machines
    if grep -q -E "dm820|dm7080|dm900|dm920" /proc/stb/info/model 2>/dev/null || grep -q -E "beyonwizu4|et11000|sf4008" /proc/stb/info/boxtype 2>/dev/null; then
        BOOT="/dev/mmcblk0boot1"
        MB_TYPE="chkroot"
    # chkroot - emmc multiboot machines
    else
        for i in /sys/block/mmcblk0/mmcblk0p*; do
            if [ -f "$i/uevent" ]; then
                partname=$(grep '^PARTNAME=' "$i/uevent" | cut -d '=' -f 2)
                devname=$(grep DEVNAME "$i/uevent" | cut -d '=' -f 2)
                case "$partname" in
                    others|startup)
                        BOOT="/dev/$devname"
                        MB_TYPE="chkroot"
                        ;;
                    other2)
                        BOOT="/dev/mmcblk0boot1"
                        MB_TYPE="chkroot"
                        ;;
                esac
            fi
        done
    fi
    # kexec - multiboot machines
    if [ -z "$BOOT" ]; then
        if grep -q 'kexec=1' /proc/cmdline; then
            for dev in /dev/mmcblk0p{4,7,9}; do
                type=$(blkid -s TYPE -o value "$dev" 2>/dev/null)
                if [ -n "$type" ]; then
                    BOOT="$dev"
                    MB_TYPE="kexec"
                    break
                fi
            done
        fi
    fi
    # gpt - multiboot machines
    if grep -q -E "one|two" /proc/stb/info/model 2>/dev/null && [ -z "$BOOT" ]; then
        BOOT=$(blkid | awk -F: '/LABEL="dreambox-data"/ {print $1}' | grep '/dev/mmcblk0p') && { MB_TYPE="gpt"; BOOTFS_TYPE="ext4"; }
    fi
    # oem - multiboot machines
    if [ -z "$BOOT" ]; then
        BOOT=$(blkid | awk -F: '/TYPE="vfat"/ {print $1}' | grep '/dev/mmcblk0p') && MB_TYPE="oem"
    fi
    # chkroot - ubifs multiboot machines
    if [ -z "$BOOT" ]; then
        for dev in /dev/sd[a-d]1; do
            label_type=$(blkid -s LABEL -s TYPE -o value "$dev" 2>/dev/null)
            if [[ "$label_type" == *STARTUP* ]]; then
                BOOT="$dev"
                MB_TYPE="chkroot"
                break
            fi
            if [[ "$label_type" == *vfat* ]]; then
                BOOT="$dev"
                MB_TYPE="chkroot"
                break
            fi
        done
    fi
}

strip_quotes() {
    echo "$1" | sed "s/^'//; s/'$//" | xargs
}

rename_slot() {
    local slot_number="$1"
    local new_name="$2"

    if [ -z "$slot_number" ]; then
        echo "Usage: $0 rename <slot_number> [<new_name>]"
        echo "If <new_name> is omitted, the slot name will be reset (deletes /usr/lib/enigma.conf)."
        exit 1
    fi

    local found=false
    for FILE in $(ls -v /boot/STARTUP_*); do
        [ -r "$FILE" ] || continue
        [[ "$FILE" == *DISABLE* ]] && continue

        local slot_id
        slot_id=$(basename "$FILE" | awk -F'_' '{if ($NF~/^[0-9]+$/)print $NF;else print substr($NF,1,1)}')
        [ "$slot_id" = "$slot_number" ] || continue
        found=true

        # --- extract boot parameters ---
        local ROOT="" ROOTSUBDIR="" ROOTFSTYPE=""
        while IFS= read -r line || [ -n "$line" ]; do
            ROOT=$(echo "$line" | sed -n 's/.*root=\([^ ]*\).*/\1/p')
            ROOTSUBDIR=$(echo "$line" | sed -n 's/.*rootsubdir=\([^ ]*\).*/\1/p')
            ROOTFSTYPE=$(echo "$line" | sed -n 's/.*rootfstype=\([^ ]*\).*/\1/p')
        done < "$FILE"

        # --- mount slot safely ---
        local tmpdir
        tmpdir=$(mount_slot "$ROOT" "$ROOTFSTYPE") || {
            echo "Cannot mount $ROOT – rename/reset aborted."
            exit 1
        }

        local distro_file_info="$tmpdir$ROOTSUBDIR/usr/lib/enigma.info"
        local distro_file_conf="$tmpdir$ROOTSUBDIR/usr/lib/enigma.conf"

        # --- perform reset or rename ---
        if [ -z "$new_name" ]; then
            # RESET — drop the override fields from enigma.conf and the empty marker info we own.
            sed -i '/^displaydistro=/d; /^imgversion=/d; /^imgrevision=/d; /^compiledate=/d' "$distro_file_conf" 2>/dev/null
            [ -f "$distro_file_info" ] && [ ! -s "$distro_file_info" ] && rm "$distro_file_info" 2>/dev/null
            echo "Reset name of slot $slot_number."
        else
            # RENAME — touch empty enigma.info so e2's analyzeSlot takes the isfile(infoFile) branch and merges enigma.conf as override.
            local distro="${new_name% *}"
            local version=""
            [[ "$new_name" == *" "* ]] && version="${new_name##* }"
            [ ! -f "$distro_file_info" ] && : > "$distro_file_info"
            sed -i '/^displaydistro=/d; /^imgversion=/d' "$distro_file_conf" 2>/dev/null
            echo "displaydistro='$distro'" >> "$distro_file_conf"
            echo "imgversion='$version'" >> "$distro_file_conf"
            echo "Renamed slot $slot_number to '$new_name'."
        fi

        unmount_slot "$tmpdir"
        exit 0
    done

    $found || echo "Invalid selection: $slot_number"
    exit 1
}

mount_slot() {
    # usage: mount_slot <partition> <fstype>
    local part="$1" fstype="$2" tmpdir
    tmpdir="$(mktemp -d)/"
    local opts=()
    [ "$fstype" = "ubifs" ] || [ "$fstype" = "ext4" ] && opts=(-t "$fstype")
    if mount "${opts[@]}" "$part" "$tmpdir" 2>/dev/null; then
        echo "$tmpdir"
    else
        echo ""
        rm -rf "$tmpdir"
        return 1
    fi
}

unmount_slot() {
    # usage: unmount_slot <mountpoint>
    local dir="$1"
    sync
    mountpoint -q "$dir" && umount -f "$dir" &>/dev/null
    rm -rf "$dir"
}

image_info() {
    local idx=$1
    local MB_TYPE=$2
    ROOT_PARTITION="${ROOT_PARTITIONS[$idx]}"
    ROOT_SUBDIR="${ROOT_SUBDIRS[$idx]}"
    ROOTFS_TYPE="${ROOTFS_TYPES[$idx]}"
    STARTUP_FILE="${STARTUP_FILES[$idx]}"
    IMAGE_INFO_RESULT=""

    # --- mount only if changed ---
    if [ "$ROOT_PARTITION" != "$LAST_ROOT_PARTITION" ]; then
        unmount_slot "$LAST_TMPDIR"
        tmpdir=$(mount_slot "$ROOT_PARTITION" "$ROOTFS_TYPE") || return
        LAST_ROOT_PARTITION="$ROOT_PARTITION"
        LAST_TMPDIR="$tmpdir"
    else
        tmpdir="$LAST_TMPDIR"
    fi

    # --- determine slot type ---
    if [[ "$STARTUP_FILE" == *FLASH* ]] && [ "$ROOTFS_TYPE" == "ubifs" ]; then
        type="UBI"
    elif [[ "$STARTUP_FILE" == *FLASH* ]]; then
        type="FLASH"
    elif [[ "$STARTUP_FILE" == *RECOVERY* ]] && [ "$MB_TYPE" == "gpt" ]; then
        type="FLASH"
    elif [[ "$ROOT_PARTITION" == *mmcblk* ]]; then
        type="eMMC"
    elif [[ "$ROOT_PARTITION" == *mtd* ]]; then
        type="MTD"
    elif [[ "$ROOT_PARTITION" == *ubi* ]]; then
        type="UBI"
    else
        type="USB"
    fi

    # --- collect paths ---
    local enigma_file_binary="$tmpdir$ROOT_SUBDIR/usr/bin/enigma2"
    local distro_file_info="$tmpdir$ROOT_SUBDIR/usr/lib/enigma.info"
    local distro_file_conf="$tmpdir$ROOT_SUBDIR/usr/lib/enigma.conf"
    local distro_file_version="$tmpdir$ROOT_SUBDIR/etc/image-version"
    local distro_file_issue="$tmpdir$ROOT_SUBDIR/etc/issue"
    distro_file_status=$(echo "$tmpdir$ROOT_SUBDIR"/var/lib/{d,o}pkg/status)
    local distro date e2date compiledate version pkg_version
    cmp -s "/boot/STARTUP" "/boot/$STARTUP_FILE" && current=' - Current' || current=''

    # Migrate legacy plugin-written enigma.info (origin='multiboot-selector.sh') into enigma.conf and blank the info to the empty marker the override layer expects.
    if [ -f "$distro_file_info" ] && grep -q "^origin='multiboot-selector.sh'" "$distro_file_info"; then
        local mig_key mig_val
        for mig_key in displaydistro imgversion imgrevision compiledate; do
            mig_val=$(strip_quotes "$(grep "^${mig_key}=" "$distro_file_info" | cut -d '=' -f 2)")
            grep -q "^${mig_key}=" "$distro_file_conf" 2>/dev/null || echo "${mig_key}='${mig_val}'" >> "$distro_file_conf"
        done
        : > "$distro_file_info"
    fi

    if [ -f "$enigma_file_binary" ]; then
        e2date=$(strip_quotes "$(stat -c %y "$enigma_file_binary" 2>/dev/null | cut -d ' ' -f 1)")
        e2date="${e2date:-$(python -c "import os, time; print(time.strftime('%Y-%m-%d', time.localtime(os.path.getmtime('$enigma_file_binary'))))")}"
    fi

    if [ -f "$distro_file_conf" ] && grep -q '^displaydistro=' "$distro_file_conf" && grep -q '^imgversion=' "$distro_file_conf"; then
        distro=$(strip_quotes "$(grep '^displaydistro=' "$distro_file_conf" | cut -d '=' -f 2)")
        version=$(strip_quotes "$(grep '^imgversion=' "$distro_file_conf" | cut -d '=' -f 2)")
        IMAGE_INFO_RESULT="Slot $type: ${distro}${version:+ $version} ($e2date)$current"
    elif [ -f "$enigma_file_binary" ]; then
        if [ -f "$distro_file_info" ]; then
            distro=$(strip_quotes "$(grep '^displaydistro=' "$distro_file_info" | cut -d '=' -f 2)")
            version=$(strip_quotes "$(grep '^imgversion=' "$distro_file_info" | cut -d '=' -f 2)")
            compiledate=$(strip_quotes "$(grep '^compiledate=' "$distro_file_info" | cut -d '=' -f 2)")
        elif [ -f "$distro_file_version" ]; then
            distro=$(strip_quotes "$(grep '^distro=' "$distro_file_version" | cut -d '=' -f 2)")
            distro="${distro:-$(strip_quotes "$(grep "Project" "${distro_file_issue}.net" | sed 's/[*]//g' | sed 's/^ *//;s/ *$//')")}"
            # shellcheck disable=SC2001
            version=$(strip_quotes "$(echo "$distro" | sed 's/[^0-9\.]*\([0-9]\+\.[0-9]\+\).*/\1/')")
            [[ "$distro" == *Gemini* ]] && distro="gp"
        fi

        for status_file in $distro_file_status; do
            if [ -f "$status_file" ]; then
                pkg_version=$(grep -A 8 '^Package: enigma2$' "$status_file" \
                    | grep '^Version:' \
                    | sed -E 's/^Version: //; s/\+.*//; s/-r[0-9.].*//')
            fi
        done

        [ -n "$compiledate" ] && date="${compiledate:0:4}-${compiledate:4:2}-${compiledate:6:2}" || date="$e2date"
        distro="${distro:-$(strip_quotes "$(head -n 1 "$distro_file_issue" | cut -d ' ' -f 1)")}"
        distro_key=$(echo "$distro" | tr '[:upper:]' '[:lower:]')
        distro="${known_distros[$distro_key]:-$distro}"
        version="${version:-$pkg_version}"
        IMAGE_INFO_RESULT="Slot $type: $(echo "$distro" "$version" | xargs) ($date)$current"

        # Touch empty enigma.info as marker; pin derived fields in enigma.conf (override layer). Idempotent — only append keys that are missing.
        if [ ! -f "$distro_file_info" ]; then
            : > "$distro_file_info"
            grep -q '^displaydistro=' "$distro_file_conf" 2>/dev/null || echo "displaydistro='$distro'" >> "$distro_file_conf"
            grep -q '^imgversion='    "$distro_file_conf" 2>/dev/null || echo "imgversion='$version'" >> "$distro_file_conf"
            grep -q '^imgrevision='   "$distro_file_conf" 2>/dev/null || echo "imgrevision=''" >> "$distro_file_conf"
            grep -q '^compiledate='   "$distro_file_conf" 2>/dev/null || echo "compiledate='${date//-/}'" >> "$distro_file_conf"
        fi
    else
        oem=$(basename "$STARTUP_FILE" | awk -F'_' '{print $NF}')
        [[ "$oem" =~ ^[0-9]+$ ]] && distro="Empty" || distro="$oem OEM"
        IMAGE_INFO_RESULT="Slot $type: $distro$current"
    fi
}

select_image() {
    local idx=$1
    echo "Image ${choices[$idx]} selected"
    ROOT_PARTITION="${ROOT_PARTITIONS[$idx]}"
    #KERNEL_PATH="${KERNEL_PATHS[$idx]}"
    ROOT_SUBDIR="${ROOT_SUBDIRS[$idx]}"
    ROOTFS_TYPE="${ROOTFS_TYPES[$idx]}"
    STARTUP_FILE="${STARTUP_FILES[$idx]}"
}

image_choice="$1"
images=()
choices=()
ROOT_PARTITIONS=()
KERNEL_PATHS=()
ROOT_SUBDIRS=()
STARTUP_FILES=()
BOOTFS_TYPE="vfat"

detect_multiboot
echo -e "BOOT ${MB_TYPE:-device not} found${BOOT:+: $BOOT}\n"
if [ -z "$BOOT" ]; then
    echo "MultiBoot type could not be detected!"
    exit 1
fi

(echo 0 > /sys/block/mmcblk0boot1/force_ro) 2>/dev/null
mkdir -p /boot 2>/dev/null
mount -t "$BOOTFS_TYPE" "$BOOT" /boot 2>/dev/null

# --- handle rename command early ---------------------------------------------
if [ "$1" = "rename" ]; then
    rename_slot "$2" "$3"
fi

idx=0
for FILE in $(ls -v /boot/STARTUP_*); do
    if [ -r "$FILE" ] && [[ ! "$FILE" == *DISABLE* ]]; then
        ROOT=""
        ROOTSUBDIR=""
        KERNEL=""

        while IFS= read -r line || [ -n "$line" ]; do
            ROOT=$(echo "$line" | sed -n 's/.*root=\([^ ]*\).*/\1/p')
            ROOTSUBDIR=$(echo "$line" | sed -n 's/.*rootsubdir=\([^ ]*\).*/\1/p')
            ROOTFSTYPE=$(echo "$line" | sed -n 's/.*rootfstype=\([^ ]*\).*/\1/p')
            KERNEL=$(echo "$line" | sed -n 's/.*kernel=\([^ ]*\).*/\1/p')
        done < "$FILE"

        choices+=("$(basename "$FILE" | awk -F'_' '{
                        if ($NF ~ /^[0-9]+$/)
                            print $NF;
                        else
                            print substr($NF, 1, 1);
        }')")
        ROOT_PARTITIONS+=("${ROOT:-OEM}")
        KERNEL_PATHS+=("$KERNEL")
        grep -q 'kexec=1' /proc/cmdline && { [[ ! "$KERNEL" == *$ROOTSUBDIR* ]] && ROOT_SUBDIRS+=("") || ROOT_SUBDIRS+=("$ROOTSUBDIR"); } || ROOT_SUBDIRS+=("$ROOTSUBDIR")
        ROOTFS_TYPES+=("$ROOTFSTYPE")
        STARTUP_FILES+=("$(basename "$FILE")")
        image_info "$idx" "$MB_TYPE"
        images+=("$IMAGE_INFO_RESULT")
        idx=$((idx + 1))
    fi
done

mountpoint -q "$LAST_TMPDIR" && umount -f "$LAST_TMPDIR" &>/dev/null && rm -rf "$LAST_TMPDIR"

if [ ${#images[@]} -eq 0 ]; then
    echo "No available images to select from!"
    umount /boot 2>/dev/null
    exit 1
fi

if [ -z "$image_choice" ] || [ "$image_choice" == "list" ]; then
    echo "Please select an image:"
    for i in "${!images[@]}"; do
        echo "${choices[$i]}) ${images[$i]}"
    done
    [ -z "$image_choice" ] && read -rp "Select an image (number): " image_choice
    [ "$image_choice" == "list" ] && exit 0
fi

valid_choice=false
for i in "${!choices[@]}"; do
    if [ "${choices[$i]}" = "$image_choice" ]; then
        choice_index="$i"
        valid_choice=true
        break
    fi
done

if ! $valid_choice; then
    echo "Invalid selection: $image_choice"
    umount /boot 2>/dev/null
    exit 1
fi

select_image "$choice_index"

if mountpoint -q "/tmp/root"; then
    echo "Unmounting /tmp/root..."
    umount /tmp/root
fi
for i in "${!choices[@]}"; do
    if [[ "${choices[$i]}" =~ ^[0-9]+$ ]]; then
        if mountpoint -q "/var/volatile/tmp/root${choices[$i]}"; then
            echo "Unmounting /var/volatile/tmp/root${choices[$i]}..."
            umount "/var/volatile/tmp/root${choices[$i]}"
        fi
    fi
done

if [ ! "$MB_TYPE" == "gpt" ]; then
    echo "Copying /boot/$STARTUP_FILE to /boot/STARTUP..."
    cp "/boot/$STARTUP_FILE" "/boot/STARTUP"
else
    if [ -f "/boot/bootconfig.txt" ]; then
        echo "Setting default=$choice_index in /boot/bootconfig.txt..."
        sed -i "s/^default=.*/default=$choice_index/" /boot/bootconfig.txt
    else
        echo "File '/boot/bootconfig.txt' for ${MB_TYPE} multiboot not found!"
        umount /boot 2>/dev/null
        exit 1
    fi
fi

echo "Selected ROOT partition: $ROOT_PARTITION"
echo "Selected ROOTSUBDIR: $ROOT_SUBDIR"
sync
echo "Script finished."

umount /boot 2>/dev/null
