#!/bin/sh

if ! [ -f /etc/is_minipc_vm ] ; then
  if ! type virtuator ; then
    rclone copy GDrive:/Projects/Virtuator/virtuator.py /tmp/virtuator
    python /tmp/virtuator system install && rm /tmp/virtuator
  fi
  mkdir -p ~/.local/share/virtuator/vmdefs
  if ! [ -f ~/.local/share/virtuator/vmdefs/minipc.vmdef ] ; then
    rclone copy GDrive:/Projects/Linux/minipc.vmdef \
                ~/.local/share/virtuator/vmdefs/minipc.vmdef
  fi
  exit $?
fi

mkdir -p ~/GDrive
mkdir -p ~/OneDrive

if ! grep OneDrive ~/.config/rclone/rclone.conf ; then
  rclone config create --non-interactive OneDrive onedrive \
  && rclone config reconnect OneDrive: \
  || echo exit $?
fi

# if ! mountpoint ~/OneDrive ; then
#   rclone mount --daemon 'OneDrive:/' ~/OneDrive || echo exit $?
# fi

if ! type prbsync ; then
  rclone copy GDrive:/Projects/PRBSync/prbsync /bin/prbsync
  chmod 0755 /bin/prbsync
fi

