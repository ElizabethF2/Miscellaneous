#!/bin/sh

# Check for a flag file and, if found, reboot to another OS
# Enables simulating a change to the BootOrder efi var on systems where the var
# can't be modified by the OS

mount /dev/disk/by-partlabel/BOOT /efi
if [ -f /efi/proxy_to_windows.flag ]; then
  next="$(efibootmgr | grep -oP '\d+(?=.+?Windows\t)')"
  efibootmgr --bootnext "$next"
  reboot
fi
