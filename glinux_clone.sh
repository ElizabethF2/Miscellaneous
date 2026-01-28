#!/bin/sh

if [ "x$container" = "x" ] ; then
  echo "No container detected"
  echo "Attempting to create a basic container"
  echo "Note: For best results, create your own container with whatever name,"
  echo "      hostname, ports, etc that you want and run this script within"
  echo "      the container."
  echo "You can force the script to avoid checking if it's in a container by"
  echo "setting the 'container' environment variable to a non-empty value."

  [ -z "$CONTAINERENGINE" ] && CONTAINERENGINE=$(type -p podman)
  [ -z "$CONTAINERENGINE" ] && CONTAINERENGINE=$(type -p docker)
  [ -z "$CONTAINERENGINE" ] && \
    echo "Set CONTAINERENGINE to your container engine or install podman or docker" && \
    exit 1

  $CONTAINERENGINE container create --init -it \
    --name glinux-clone "docker.io/library/debian:testing" /bin/bash

  cat "$0" | $CONTAINERENGINE start -ai glinux-clone
  exit $?
fi

if [ "x$(type apt 2>/dev/null)" = "x" ] ; then
  echo "apt is required to use this script"
  exit 1
fi

if [ "x$(type apt-get 2>/dev/null)" = "x" ] ; then
  echo "apt-get is required to use this script"
  exit 1
fi

if ! cat /etc/os-release | grep 'PRETTY_NAME=.*/sid' >/dev/null ; then
  if [ "x$IGNORE_NOT_TESTING" = "x" ] ; then
    echo "must be run on Debian Testing"
    echo "set IGNORE_NOT_TESTING to suppress this error"
    exit 1
  fi
fi

apt update
apt-get -y install dpkg debsums systemd systemd-boot systemd-boot-efi grub2   \
                   gnome pulseaudio-utils onboard less which curl wget        \
                   busybox moreutils sudo vim nano cronutils tmpreaper fdisk  \
                   7zip git git-secrets cvs rsyslog rtkit quota               \
                   openssh-server mosh telnet iputils-ping iputils-tracepath  \
                   iptables iproute2 traceroute tcpdump bind9-dnsutils        \
                   net-tools screen libnss3-tools nftables cron at sweeper    \
                   exfatprogs btrfs-progs samba-libs cryptsetup lvm2 keyutils \
                   sbsigntool tpm2-tools tpm-udev libyubikey-udev opensc      \
                   pm-utils puppet puppet-agent hiera build-essential gcc g++ \
                   clang cmake gdb-minimal golang python3 python3-pip         \
                   python3-lib2to3 perl default-jdk protobuf-compiler         \
                   libprotobuf-c1 libprotobuf-lite32 npm inxi hwdata socat    \
                   expect pigz imagemagick dvipng ffmpeg gnustep-base-runtime \
                   libxml2-utils rng-tools5 cups-bsd duplicity crudini        \
                   graphviz seahorse hexchat aspell-en hunspell-en-us         \
                   wamerican csh fish tcsh zsh xvfb xterm zutty aha xclip     \
                   gettext whiptail vlc juk libkrb5-dev libxkbfile-dev        \
                   libsecret-1-dev tasksel texinfo info sysnews               \
                   libarchive-zip-perl debhelper auditd python3-mutagen       \
                   mariadb-server-core mariadb-client-core

mkdir -p /tmp/google_gpg_home
GNUPGHOME=/tmp/google_gpg_home gpg \
  --keyserver hkps://keyserver.ubuntu.com \
  --recv-keys EB4C1BFD4F042F6DDDCCEC917721F63BD38B4796 \
              4CCA1EAF950CEE4AB83976DCA040830F7FAC5991
GNUPGHOME=/tmp/google_gpg_home gpg \
  --output /usr/share/keyrings/google-chrome.gpg \
  --export linux-packages-keymaster@google.com
rm -r /tmp/google_gpg_home

mkdir -p /tmp/google_gpg_home
GNUPGHOME=/tmp/google_gpg_home gpg \
  --keyserver hkps://keyserver.ubuntu.com \
  --recv-keys 35BAA0B33E9EB396F59CA838C0BA5CE6DC6315A3
GNUPGHOME=/tmp/google_gpg_home gpg \
  --output /usr/share/keyrings/google-cloud.gpg \
  --export artifact-registry-repository-signer@google.com
rm -r /tmp/google_gpg_home

echo deb "[arch=$(dpkg --print-architecture)" \
         "signed-by=/usr/share/keyrings/google-chrome.gpg]" \
         "https://dl.google.com/linux/chrome/deb/ stable main" | \
  tee /etc/apt/sources.list.d/google-chrome.list

echo deb "[arch=$(dpkg --print-architecture)" \
         "signed-by=/usr/share/keyrings/google-chrome.gpg]" \
         "https://dl.google.com/linux/chrome-remote-desktop/deb/ stable main" | \
  tee /etc/apt/sources.list.d/chrome-remote-desktop.list

echo deb "[arch=$(dpkg --print-architecture)" \
         "signed-by=/usr/share/keyrings/google-cloud.gpg]" \
         "https://packages.cloud.google.com/apt cloud-sdk main" | \
  tee /etc/apt/sources.list.d/google-cloud.list

echo deb "[arch=$(dpkg --print-architecture)" \
         "signed-by=/usr/share/keyrings/debian-archive-keyring.gpg]" \
         "http://deb.debian.org/debian testing non-free non-free-firmware" \
  >> /etc/apt/sources.list.d/non-free.list

echo deb "[arch=$(dpkg --print-architecture)" \
         "signed-by=/usr/share/keyrings/debian-archive-keyring.gpg]" \
         "http://deb.debian.org/debian testing utils" \
  >> /etc/apt/sources.list.d/utils.list

apt update
apt-get -y install google-chrome-stable iucode-tool \
                   intel-microcode amd64-microcode firmware-amd-graphics \
                   firmware-nvidia-graphics firmware-linux firmware-linux-free

apt-get -y install vbetool

mkdir -p /tmp/crd_tmp_ws
pushd /tmp/crd_tmp_ws
apt-get download chrome-remote-desktop
dpkg-deb -x *.deb pkg
dpkg-deb --control *.deb pkg/DEBIAN
sed 's/policykit-1, //' 'pkg/DEBIAN/control' | tee 'pkg/DEBIAN/control'
dpkg -b pkg fixed.deb
apt-get -y install ./fixed.deb

apt upgrade

npm install -g @bazel/bazelisk
bazel

rm /usr/lib/python*/EXTERNALLY-MANAGED
PIP_ROOT_USER_ACTION=ignore pip install -U gcl jsonnet future
ln -sf "$(type -p gcl-print)" /usr/bin/gcl

go install github.com/kubecfg/kubecfg@latest
mv ~/go/bin/* /usr/bin/
rm -r ~/go/

mkdir -p /tmp/panel_tmp_ws
pushd /tmp/panel_tmp_ws
git clone https://github.com/home-sweet-gnome/dash-to-panel.git .
make install
gnome-extensions enable "dash-to-panel@jderose9.github.com"
busctl --user call "org.gnome.Shell" "/org/gnome/Shell" "org.gnome.Shell" \
                   "Eval" "s" 'Meta.restart("Restarting")'
popd

mkdir -p /tmp/vsc_tmp_ws
pushd /tmp/vsc_tmp_ws
git clone https://github.com/VSCodium/vscodium.git .
npm install -g yarn
SHOULD_BUILD_RPM=no SHOULD_BUILD_APPIMAGE=no ./build/build.sh -p
find ./vscode -name '*.deb' -exec apt -y install {} \;
popd

# Per https://github.com/grpc/grpc/blob/master/doc/command_line_tool.md
mkdir -p /tmp/grpc_tmp_ws
pushd /tmp/grpc_tmp_ws
git clone https://github.com/grpc/grpc.git .
git submodule update --init
mkdir -p cmake/build
cd cmake/build
cmake -DgRPC_BUILD_TESTS=ON ../..
make grpc_cli
cp ./grpc_cli /usr/bin/
popd

echo "bind 'set enable-bracketed-paste on'" >> ~/.bashrc
echo "bind 'set enable-bracketed-paste on'" >> /etc/skel/.bashrc

# TODO: sudo rules


cat > /usr/bin/glinux-updater << EOF
#!/bin/sh
if [ "$UID" != "0" ]; then
  sudo "$0"
  exit $?
fi
apt update || exit $?
apt upgrade || exit $?
PIP_ROOT_USER_ACTION=ignore pip install -U gcl jsonnet future || exit $?
type npm >/dev/null 2>&1 && npm update -g
type terraform-switcher >/dev/null 2>&1 && terraform-switcher -u
EOF


cat > /usr/bin/glinux-information << EOF
#!/usr/bin/env python3
print('Gathering information about your system.')
print('Please wait. This may take a while.')

import sys, os, io, subprocess, socket, time, tarfile

try:
  dtop = subprocess.check_output(('xdg-user-dir', 'DESKTOP')).decode().strip()
except (FileNotFoundError, subprocess.CalledProcessError, UnicodeDecodeError):
  dtop = None

if not dtop or not os.path.isdir(dtop):
  dtop = os.path.expanduser(os.path.join('~', 'Desktop'))

if not os.path.isdir(dtop):
  dtop = os.path.expanduser('~')

cmds = {
  'top': ('top', '-b', '-n', '1'),
  'inxi': ('inxi', '-F'),
  'tpm_pcrs': ('tpm2_pcrread', '-V'),
  'network': ('ip', 'addr'),
  'performance': ('inxi', '-mjxxx', '-t', 'cm'),
  'journal': ('journalctl', '-b'),
  'dmesg': ('dmesg',),
}

info = {}
for name, cmd in cmds.items():
  sys.stdout.write('\r' + (80*' ') + '\r  Completed ' + str(len(info)//2) + \
                   ' of ' + str(len(cmds)) + ' tasks')
  sys.stdout.flush()
  proc = subprocess.run(cmd, capture_output = True, check = False)
  info[name+'.stdout'] = proc.stdout
  info[name+'.stderr'] = proc.stderr
print('')

while True:
  fname = time.strftime('%Y-%m-%d_%H.%M-' + socket.gethostname() + '.tgz')
  fpath = os.path.join(dtop, fname)
  try:
    with tarfile.open(fpath, 'x:gz') as tf:
      for name, data in info.items():
        buf = io.BytesIO(data)
        tinfo = tarfile.TarInfo(name = name + '.txt')
        tinfo.size = buf.getbuffer().nbytes
        tf.addfile(tinfo, buf)
    break
  except FileExistsError:
    time.sleep(15)

print('All done! Bundled logs sent to your Desktop:')
print(' ', dtop)
print('Look for a file named:')
print(' ', fname)
print('Full file path:')
print(' ', fpath)
EOF

# TODO gmenu
# Mail Spool, Forced Reboot Notice, Root Check, gMenu Settings, gLinux Configuration, Help
# gMenu Settings - refresh rate
# Bash history (recommended/enabled/disabled), Enable suspend (recommended/yes/no)
# CRD DE (recommended/gnome/xfce), default screensaver, DM (gdm3/lightdm), Grub Menu Sound (recommended/yes/no)
# Pre-reboot warning time, reboot warning notification (recommended/yes/no)
# Help - help link and collect logs button

# TODO glinux-fixme
# #!/usr/bin/env python
# run updater, close other vcons, restart wpa_suplicant, wheel, inxi, print PASSED (green), FAILED (red), check() and fix()
# forced reboot service
# import colorama

# TODO glinux-cmd404
#  - emacs
#  - vim
#  - https://cloud.google.com/bigtable/docs/cbt-overview (gcloud, cbt)
#  - lldb
#  - terraform (via terraform-switcher ; terraform-switcher -u)
#  - kubectl
#  - rclone
#  - adb
#  - cs (https://github.com/boyter/cs)

# Command can't be found, but found a package (pkgnamehere) that provides this command.
# Please confirm that you want to install this package: [Y/n]

# Command _______ not found

chmod +x /usr/bin/glinux-*


