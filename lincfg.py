#!/usr/bin/env python3

desired_username = 'Liz'
desired_wheel_users = ('Liz',)

tasks = []
@tasks.append
def ensure_user_exists():
  if is_termux():
    return
  if not os.path.exists(fixpath(f'~{desired_username}')):
    subprocess.run(['useradd', '-m', desired_username])
    if desired_username in desired_wheel_users:
      subprocess.run(['usermod', '-aG', 'wheel', desired_username])

get_lincfg_bin_path = lambda: fixpath('$PREFIX/bin/lincfg' if is_termux() else '~root/.local/bin/lincfg')

flag_def = [
  ('--scan',        '-s', 'Run virus, rootkit and health scanners'),
  ('--interact',    '-i', 'Run config steps which require interaction'),
  ('--undesired',   '-r', 'Interactly removes any undesired packages.'),
  ('--bundle',      '-b', 'Generate a bundle which can be copied to a thumb drive.'), # TODO
  ('--fpoverrides', '-f', 'Reset non-lincfg system-level flatpak permission'),
  ('--offline',     '-o', 'Skips any sections that require the internet'),
  ('--init',        '-n', 'Interactive initial setup to format a drive, pacstrap, etc'), # TODO
  ('--help',        '-h', 'Show this help screen'),
]

past_pacman_packages = '''
  gamescope packagekit-qt6 maliit-keyboard squeekboard linux-zen ydotool yasm nasm powertop d-spy alsa-utils openrgb
  qjackctl cmake ninja gcc clang rust nano rsync gnome-boxes libvirt python-pyusb xorg-xeyes ydotool tk efitools
  sof-firmware jami-qt filelight gdu meld linux linux-docs atop
'''.split()

common_pacman_packages = '''
  bash micro less tmux podman grub which sudo lynx
  python python-cryptography python-requests python-pillow python-docs python-qtpy python-pyqt6
  linux-firmware git flatpak flatpak-kcm plasma-workspace kate konsole dolphin sddm ntp grub rclone
  rkhunter lynis arch-audit lsof clamav ed noto-fonts-cjk noto-fonts-emoji noto-fonts iwd networkmanager
  partitionmanager arch-install-scripts bluez vulkan-radeon spectacle dosfstools baobab efibootmgr amd-ucode fwupd
  btrfs-progs sbsigntools sbsigntools parted base tpm2-tools plasma-meta plasma-sdk xdg-desktop-portal-gtk man-db
  bsd-games words busybox openssh firewalld xdotool libappindicator-gtk3 gst-plugin-pipewire chntpw
  power-profiles-daemon ollama-rocm fcitx5 fcitx5-qt fcitx5-configtool fcitx5-mozc nethogs htop btop bind
  amdgpu_top nvtop sshfs archiso aspell aspell-en sbctl zip unzip powertop trash-cli kscreen kdeplasma-addons ark
  pacman-contrib python-lsp-server scrcpy bluez-utils bluez-obex vorbis-tools time lshw inxi ntfs-3g usbutils
  alsa-utils qemu-user-static-binfmt qemu-system-x86 qemu-img edk2-ovmf dos2unix patch mkinitcpio imagemagick linux
'''.split()

temporarily_pinned_pacman_packages = '''
  swtpm openfortivpn fluxbox qemu-desktop python-lz4 pypy3 zbar
'''.split()

container_pacman_packages = '''
  tigervnc xorg-server xorg-xrandr xorg-server-xvfb xorg-xinit supervisor firefox gnome-mahjongg poppler
'''.split()

pacman_cmd_prefix = 'pacman -Syu --needed --noconfirm'.split()

postmarketos_packages = '''
  python3 python3-doc micro micro-doc tmux tmux-doc bsd-games bsd-games-doc busybox-doc flatpak flatpak-doc
  rclone rclone-doc man-db man-pages networkmanager-doc alpine-doc aspell aspell-en aspell-doc bash-doc
  sudo sudo-doc !doas-sudo-shim curl curl-doc baobab baobab-doc cryptsetup-doc findutils findutils-doc
  flashrom flashrom-doc waydroid iptables-doc iproute2-minimal ufw ufw-doc iproute2-ss sshfs sshfs-doc py3-cryptography
  bash scrcpy redsocks htop clamav
'''.split()

personal_postmarketos_packages = '''
  podman podman-doc passt passt-doc py3-lsp-server tpm2-tools tpm2-tools-doc tpm2-tss-dev xmessage xmessage-doc
  vlc-qt vlc-doc git git-doc lynis lynis-doc
'''.split()

termux_packages = '''
  python python-cryptography micro tmux busybox rclone bsd-games termux-api qemu-system-x86-64-headless qemu-utils man
  lynx wasmer ncdu
'''.split()

def get_desired_packages(include_aur = False):
  if is_arch_linux():
    if in_container():
      packages = common_pacman_packages + container_pacman_packages
    else:
      packages = common_pacman_packages + temporarily_pinned_pacman_packages
    if include_aur:
      packages += [p[0] for p in aur_packages] + \
                  aur_packages_installed_via_aur_helper
  if is_postmarketos():
    packages = postmarketos_packages
    if not is_parent_pc():
      packages += personal_postmarketos_packages
  return packages

packages_before_update = []
@tasks.append
def install_or_update_packages():
  if not packages_before_update:
    packages_before_update.extend(get_installed_packages())
  if flags('offline'):
    return
  if is_arch_linux():
    subprocess.check_call(pacman_cmd_prefix + get_desired_packages())
  if is_postmarketos():
    subprocess.check_call(('apk', 'update'))
    subprocess.run(['apk', 'add'] + get_desired_packages(),
                   check = True,
                   input = b'Y\n')
    subprocess.run(('apk', 'upgrade'), check = True, input = b'Y\nY\n')

desired_timezone = 'US/Pacific'
# desired_timezone = 'US/Arizona'
# desired_timezone = 'US/Eastern'
zoneinfo_root = '/usr/share/zoneinfo'
localtime_path = '/etc/localtime'
desired_parent_timezone = 'US/Arizona'

@tasks.append
def ensure_correct_timezone_set():
  if is_termux():
    return
  if is_parent_pc():
    zoneinfo = os.path.join(zoneinfo_root, desired_parent_timezone)
  else:
    zoneinfo = os.path.join(zoneinfo_root, desired_timezone)
  if get_link_target(localtime_path) != zoneinfo:
    subprocess.run(['ln', '-sf', zoneinfo, localtime_path])

locales_to_uncomment = ['en_US.UTF-8']
@tasks.append
def ensure_correct_locales_generated():
  if not is_arch_linux():
    return
  p, locale_gen = read_config('/etc/locale.gen')
  if any((('#'+l) in locale_gen for l in locales_to_uncomment)):
    for locale in locales_to_uncomment:
      locale_gen = locale_gen.replace('#'+locale, locale)
    write_config(p, locale_gen)
    subprocess.run('locale-gen')

target_lang = 'en_US.UTF-8'
@tasks.append
def ensure_correct_language_set():
  if is_termux():
    return
  p, locale_conf = read_config('/etc/locale.conf', default_contents='LANG=None')
  current_lang = get_config_var(locale_conf, 'LANG')
  if current_lang != target_lang:
    if current_lang is None:
      write_config(p, locale_conf + '\nLANG='+target_lang+'\n')
    else:
      write_config(p, locale_conf.replace('LANG='+current_lang, 'LANG='+target_lang))

target_keymap = 'us'
@tasks.append
def ensure_correct_keymap_set():
  if is_termux():
    return
  p, vconsole_conf = read_config('/etc/vconsole.conf', default_contents='')
  current_keymap = get_config_var(vconsole_conf, 'KEYMAP')
  if current_keymap != target_keymap:
    if current_keymap is None:
      write_config(p, vconsole_conf + '\nKEYMAP='+target_keymap+'\n')
    else:
      write_config(p, vconsole_conf.replace('KEYMAP='+current_keymap, 'KEYMAP='+target_keymap))

esp_mountpoint = '/efi'
@tasks.append
def ensure_esp_mountpoint_exists():
  if is_termux() or is_postmarketos():
    return
  try:
    os.mkdir(esp_mountpoint)
  except FileExistsError:
    pass

desired_shell = 'bash'
@tasks.append
def ensure_desired_shell_set():
  shell = which(desired_shell)
  users = {desired_username, 'root'}
  for p in pwd.getpwall():
    if p.pw_name in users and p.pw_shell != shell:
      subprocess.check_call(('chsh', '-s', shell, p.pw_name))

bashrc_skel_path = '/etc/skel/.bashrc'
user_bashrc_path = f'~{desired_username}/.bashrc'
desired_user_bashrc_suffix = '''
export PATH=$PATH:$HOME/.local/bin
export LESS=-i
export PYTHONPYCACHEPREFIX=~/.cache/pycache
export ASPELL_CONF="home-dir $HOME/GDrive/Projects/Linux/config"

bind -s 'set completion-ignore-case on'

(prbsync notify &)
'''

old_user_bashrc_suffix = r'''
export PYTHONPATH=~/.local/state/pythonpkgs

alias wboot="sudo /usr/bin/python3 -I /root/.local/bin/boot_windows"
alias dt="do_all_the_things"

alias bync="prbsync sync"
alias bquery="prbsync query"
alias bclean="sudo /usr/bin/bash -i -c bclean"

charmctl () {
  pushd ~/.local/share/charonrmm >/dev/null
  python charmctl.py "$@"
  popd>/dev/null
}

chupdate () {
  pushd ~/.local/share/charonrmm >/dev/null
  python update.py "$@"
  popd>/dev/null
}
'''

import sys, os, subprocess, shlex, shutil, tempfile, re, urllib.request, base64
import textwrap, inspect, json, stat, socket, hashlib, configparser, site, glob
import pprint, errno, time, functools, pwd

small_scripts = {}

small_scripts[f'~{desired_username}/.local/bin/rlog'] = r'''
#!/usr/bin/env python3
import sys, os, shutil, subprocess
try:
  with open('/proc/self/comm', 'r+') as f:
    f.write('rlog')
except (FileNotFoundError, PermissionError):
  pass
LOG_DIR = os.path.expanduser(
  os.path.join(*'~/OneDrive/Projects/ResultsLogger/Logs'.split('/')))
logs = sorted(os.listdir(LOG_DIR),
              key=lambda i: os.path.getmtime(os.path.join(LOG_DIR,i)),
              reverse=True)
print('Please pick a log:' + chr(10))
for idx, name in enumerate(logs[:9]):
  print(str(idx+1) + ') ' + name)
try:
  log_path = os.path.join(LOG_DIR, logs[int(input(chr(10) + '> '))-1])
except (ValueError, IndexError, KeyboardInterrupt, EOFError):
  print(chr(10) + 'Not a valid selection. Aborting...' + chr(10))
  sys.exit(-1)
less = shutil.which('less')
subprocess.run(([less, '+G'] if less else [shutil.which('more')]) + [log_path])
'''.lstrip()

small_scripts['~root/.local/bin/maxfan'] = r'''
#!/bin/sh
export HWMONROOT="$(dirname "$(echo /sys/class/hwmon/*/pwm4)")"
echo "HWMONROOT = '$HWMONROOT'"
[ "x$HWMONROOT" = "x" ] && exit 1
exec busybox sh <<EOF
  echo MAXFAN > /proc/$$/comm
  while true ; do
    echo 255 > $HWMONROOT/pwm1
    echo 255 > $HWMONROOT/pwm2
    echo 255 > $HWMONROOT/pwm3
    echo 255 > $HWMONROOT/pwm4
    sleep 40
  done
EOF
'''.lstrip()

small_scripts[f'~{desired_username}/.local/bin/maxfan'] = r'''
#!/bin/sh
echo maxfan MaxFan > /proc/$$/comm
sudo ~root/.local/bin/maxfan
'''.lstrip()

small_scripts[f'~{desired_username}/.local/bin/shellcheck'] = r'''
#!/bin/sh
# Fake shellcheck to keep Konsole's Quick Commands plugin from raising warnings
exit 0
'''.lstrip()

small_scripts[f'/root/.local/bin/psnooze'] = fr'''
#!/bin/sh
duration='5 hours'
systemd-run --unit=psnooze \
  --on-calendar="@$(date -d "now + $duration" +%s)" \
  --timer-property=AccuracySec=100ms /root/.local/bin/pwake || exit $?
# systemctl stop Sessen  # Handled by own PerfM entry
systemctl stop MissionControlLite
'''.lstrip()

small_scripts[f'/root/.local/bin/pwake'] = r'''
#!/bin/sh
# systemctl start Sessen
systemctl start MissionControlLite
systemctl stop psnooze.timer
'''.lstrip()

small_scripts[f'~{desired_username}/.local/bin/ptm'] = '''
#!/bin/sh
sudo ptaskrunner Minimal || exit $?
kill -HUP $PPID || exit $?
'''

small_scripts[f'~{desired_username}/.local/bin/ptr'] = '''
#!/bin/sh
exec python ~/.local/share/ptaskrunner/task_router.py
'''

small_scripts[f'~{desired_username}/.local/bin/sd'] = '''
#!/bin/sh
echo ScreenDoc > /proc/$$/comm
sleep 8
exec kscreen-doctor --dpms off
'''

@tasks.append
def make_and_update_small_scripts():
  for path, code in small_scripts.items():
    p, existing_code = read_config(path, default_contents = '')
    if existing_code != code:
      u = desired_username if path.startswith(f'~{desired_username}') else None
      write_config(p, code, user = u)
      os.chmod(p, OWNER_CAN_RWX)

@functools.cache
def get_bashrc_skel():
  d = None if is_arch_linux() else ''
  _, bashrc_skel = read_config(bashrc_skel_path, default_contents = d)
  return bashrc_skel

def get_desired_user_bashrc():
  return get_bashrc_skel() + desired_user_bashrc_suffix

@tasks.append
def ensure_bashrc_is_correct():
  d = None if is_arch_linux() else ''
  p, user_bashrc = read_config(user_bashrc_path, default_contents = d)
  if user_bashrc != get_desired_user_bashrc():
    write_config(p, get_desired_user_bashrc(), user = desired_username)

@tasks.append
def ensure_xdg_local_bin_exists():
  makedirs(f'~{desired_username}/.local/bin', user = desired_username)

common_bwrap_command = '''
bwrap \\
  --dev /dev \\
  --proc /proc \\
  --tmpfs /tmp \\
  --dir /var \\
  --unshare-all \\
  --ro-bind-try /bin /bin \\
  --ro-bind-try /usr /usr \\
  --ro-bind-try /lib /lib  \\
  --ro-bind-try /lib64 /lib64 \\
  --ro-bind-try /etc /etc \\
'''.strip()

common_bwrap_command_with_results_logger = f'''
{common_bwrap_command}
  --share-net \\
  --ro-bind-try ~/.local/share/results_logger ~/.local/share/results_logger \\
  --ro-bind-try ~/.config/prbsync.toml ~/.config/prbsync.toml \\
  --bind-try ~/.config/rclone ~/.config/rclone \\
  --bind-try ~/.cache/rclone ~/.cache/rclone \\
  --bind-try ~/.local/state/prbsync ~/.local/state/prbsync \\
  --bind-try ~/.local/share/snapshots ~/.local/share/snapshots \\
  --bind-try ~/OneDrive ~/OneDrive \\
  --bind-try ~/GDrive ~/GDrive \\
'''.strip()

user_shell_shims = {



'sdxl': '''
#!/bin/sh
printf SDXL > /proc/$$/comm
podman start -ai sdxls "$@"
''',

'of': '''
#!/bin/sh
printf Ollama Fav 1 > /proc/$$/comm
ollama run taozhiyuai/llama-3-uncensored-lumi-tess-gradient:70b-q5_k_m
''',

'og': '''
#!/bin/sh
printf Ollama Fav 2 > /proc/$$/comm
ollama run gemma3:27b
''',

'os': '''
#!/bin/sh
printf Ollama Serve > /proc/$$/comm
OLLAMA_KEEP_ALIVE=-1 ollama serve
''',

'podcast_downloader': f'''
#!/bin/sh
echo Podcast DL > /proc/$$/comm
mkdir -p ~/Downloads/Unscanned/Podcasts
{common_bwrap_command}
  --share-net \\
  --ro-bind-try ~/GDrive/Projects/podcast_downloader.py ~/GDrive/Projects/podcast_downloader.py \
  --bind-try ~/Downloads/Unscanned/Podcasts ~/Downloads/Unscanned/Podcasts \
  python ~/GDrive/Projects/podcast_downloader.py
''',

'bwshell_onedrive': f'''
echo BWS:OneDrive > /proc/$$/comm
mkdir -p ~/Downloads/Unscanned/bwshell_onedrive
{common_bwrap_command}
  --bind-try \\
    ~/Downloads/Unscanned/bwshell_onedrive \\
    ~/Downloads/Unscanned/bwshell_onedrive \\
  --bind-try ~/OneDrive ~/OneDrive \\
  --setenv PS1 '(BWS:OneDrive \\W)\\$ ' \\
  --chdir ~/OneDrive \\
  bash
''',

'bwshell_gdrive': f'''
echo BWS:GDrive > /proc/$$/comm
mkdir -p ~/Downloads/Unscanned/bwshell_gdrive
{common_bwrap_command}
  --bind-try \\
    ~/Downloads/Unscanned/bwshell_gdrive \\
    ~/Downloads/Unscanned/bwshell_gdrive \\
  --bind-try ~/GDrive ~/GDrive \\
  --setenv PS1 '(BWS:GDrive \\W)\\$ ' \\
  --chdir ~/GDrive \\
  bash
''',

'charmctl': r'''
#!/bin/sh
cd ~/.local/share/charonrmm
exec python charmctl.py "$@"
''',

'chupdate': r'''
#!/bin/sh
cd ~/.local/share/charonrmm
exec python update.py "$@"
''',

'lincfg': r'''
#!/bin/sh
echo lincfg > /proc/$$/comm
sudo /usr/bin/python3 -I /root/.local/bin/lincfg "$@"
exit $?
''',

'wboot': r'''
#!/bin/sh
echo wboot > /proc/$$/comm
sudo /usr/bin/python3 -I /root/.local/bin/boot_windows "$@"
exit $?
''',

'dt': r'''
#!/bin/sh
exec do_all_the_things "$@"
''',

'dn': r'''
#!/bin/sh
exec do_all_the_things --next "$@"
''',

'bync': r'''
#!/bin/sh
exec prbsync sync "$@"
''',

'bquery': r'''
#!/bin/sh
exec prbsync query "$@"
''',

'bclean': r'''
#!/bin/sh
echo bclean > /proc/$$/comm
sudo /usr/bin/bash -i -c bclean "$@"
exit $?
''',



'kr': r'''
#!/bin/sh
kwin_wayland --replace || exit $?
systemctl restart --user plasma-plasmashell || exit $?
exec systemctl restart --user plasma-powerdevil
''',
}

@tasks.append
def ensure_shell_shims_exist():
  for name, desired_shim_code in user_shell_shims.items():
    desired_shim_code = desired_shim_code.lstrip()
    p, shim_code = read_config(f'~{desired_username}/.local/bin/'+name,
                              default_contents='')
    if shim_code != desired_shim_code:
      write_config(p, desired_shim_code, user = desired_username)
      os.chmod(p, OWNER_CAN_RWX)

desired_root_bashrc_suffix = """
export LESS=-i
export PATH=$PATH:$HOME/.local/bin

bind -s 'set completion-ignore-case on'

alias wboot="boot_windows"
alias bclean="HOME=/home/Liz prbsync clean"
alias bt_dualboot="python -m bt_dualboot"
"""

def get_desired_root_bashrc():
  return get_bashrc_skel() + desired_root_bashrc_suffix

@tasks.append
def ensure_root_bashrc_is_correct():
  if is_termux():
    return
  d = None if is_arch_linux() else ''
  p, root_bashrc = read_config('~root/.bashrc', default_contents = d)
  if root_bashrc != get_desired_root_bashrc():
    write_config(p, get_desired_root_bashrc())

sudo_drop_in = f'''
Defaults env_keep += "IGNORE_IF_ON_BATTERY"
# %wheel ALL=(root) NOPASSWD: /usr/bin/systemctl start rustdesk
# %wheel ALL=(root) NOPASSWD: /usr/bin/systemctl stop rustdesk
%wheel ALL=(root) NOPASSWD: /usr/bin/systemctl start Sessen
%wheel ALL=(root) NOPASSWD: /usr/bin/systemctl stop Sessen
%wheel ALL=(root) NOPASSWD: /usr/bin/systemctl restart Sessen
%wheel ALL=(root) NOPASSWD: /usr/bin/systemctl start MissionControlLite
%wheel ALL=(root) NOPASSWD: /usr/bin/systemctl restart MissionControlLite
%wheel ALL=(root) NOPASSWD: /bin/sh /root/.local/bin/psnooze
%wheel ALL=(root) NOPASSWD: /bin/sh /root/.local/bin/pwake
%wheel ALL=(root) NOPASSWD: /usr/bin/ptaskrunner MCLite
%wheel ALL=(root) NOPASSWD: /usr/bin/ptaskrunner Network
%wheel ALL=(root) NOPASSWD: /usr/bin/ptaskrunner Minimal
%wheel ALL=(root) NOPASSWD: /usr/bin/ptaskrunner --reset
%wheel ALL=(root) NOPASSWD: /usr/bin/python3 -I /root/.local/bin/boot_windows
%wheel ALL=(root) NOPASSWD: /usr/bin/python3 -I /root/.local/bin/boot_windows --nosync
%wheel ALL=(root) NOPASSWD: /usr/bin/python3 -I /root/.local/bin/lincfg
%wheel ALL=(root) NOPASSWD: /usr/bin/python3 -I /root/.local/bin/lincfg -o
%wheel ALL=(root) NOPASSWD: /root/.local/bin/maxfan
%wheel ALL=(root) NOPASSWD: /usr/bin/bash -i -c bclean
%wheel ALL=(root) NOPASSWD: /usr/bin/python3 -I /root/.local/bin/auto_tpm_encrypt --ensure_no_os_are_unsealed
%wheel ALL=(root) NOPASSWD: /usr/bin/python3 -I /root/.local/bin/auto_tpm_encrypt --ensure_booted_os_is_sealed
{desired_username} ALL=(root) NOPASSWD: /usr/bin/python3 -I /root/.local/bin/persistent_tmux {desired_username}
{desired_username} ALL=(root) NOPASSWD: /usr/bin/systemd-run -- /usr/bin/alt_os_util switch_gpu_inner {desired_username}
'''.lstrip()

@tasks.append
def ensure_sudo_is_configured_correctly():
  if is_termux():
    return
  sudo = which('sudo')
  if sudo:
    sudoers_line_to_uncomment = '%wheel ALL=(ALL:ALL) ALL'
    p, sudoers = read_config('/etc/sudoers')
    if '# '+sudoers_line_to_uncomment in sudoers:
      write_config(p, sudoers.replace('# '+sudoers_line_to_uncomment,
                                      sudoers_line_to_uncomment))
    p, f = read_config('/etc/sudoers.d/sudo_drop_in', default_contents = '')
    if f != sudo_drop_in:
      write_config(p, sudo_drop_in)

common_desired_plasma_vars = '''
export ASPELL_CONF="home-dir $HOME/GDrive/Projects/Linux/config"
export PATH=$PATH:$HOME/.local/bin
'''.lstrip()

arch_linux_desired_plasma_vars = '''
export KWIN_DRM_NO_AMS=1
'''.lstrip()

def get_desired_plasma_vars():
  v = common_desired_plasma_vars
  if is_arch_linux():
    v += arch_linux_desired_plasma_vars
  return v

@tasks.append
def ensure_plasma_vars_are_set_correctly():
  desired_plasma_vars = get_desired_plasma_vars()
  p, plasma_vars = read_config(f'~{desired_username}/.config/plasma-workspace/env/vars.sh',
                               default_contents = '')
  if plasma_vars != desired_plasma_vars:
    write_config(p, desired_plasma_vars, user = desired_username)

rc_values_to_ensure = {
  f'~{desired_username}/.config/kwinrc': (
    ('[Plugins]', 'magiclampEnabled', 'true'),
  ),

  f'~{desired_username}/.config/konsolerc': (
    ('[Desktop Entry]', 'DefaultProfile', 'Default.profile'),
  ),

  f'~{desired_username}/.config/katerc': (
    ('[General]', 'Last Session', 'Default'),
    ('[General]', 'Startup Session', 'last'),
    ('[KTextEditor View]', 'Show Word Count', 'true'),
    ('[KTextEditor View]', 'Show Line Count', 'true'),
    ('[KTextEditor View]', 'Statusbar Line Column Compact Mode', 'false'),
    ('[KTextEditor Document]', 'Remove Spaces', '0'),
  ),

  f'~{desired_username}/.config/dolphinrc': (
    ('[General]', 'OpenExternallyCalledFolderInNewTab', 'true'),
  ),

  f'~{desired_username}/.config/plasma-localerc': (
    ('[Formats]', 'LC_TIME', 'en_US.UTF-8'),
  ),
}

@tasks.append
def ensure_rc_values_set():
  if is_termux():
    return
  for path, values in rc_values_to_ensure.items():
    ensure_rc_values(path, values, user = desired_username)

plasma_applet_src_path = f'~{desired_username}/.config/plasma-org.kde.plasma.desktop-appletsrc'
clock_rc_values = {
  'dateFormat': 'custom',
  'customDateFormat': 'yyyy/MM/dd',
  'selectedTimeZones': 'America/Los_Angeles,US/Arizona,US/Eastern,Local',
  'lastSelectedTimezone': 'Local',
}

@tasks.append
def ensure_clock_setup():
  p, src = read_config(plasma_applet_src_path, default_contents = '')
  clock_section = None
  for line in src.splitlines():
    if line.startswith('['):
      section = line
    elif line == 'plugin=org.kde.plasma.digitalclock':
      clock_section = section
  if clock_section:
    ensure_rc_values(p, ((clock_section + '[Configuration][Appearance]', *i)
                         for i in clock_rc_values.items()))

user_files_with_exact_contents = {}

user_files_with_exact_contents[
  f'~{desired_username}/.local/share/konsole/Default.profile'] = '''
[Appearance]
ColorScheme=GreenOnBlack

[General]
Name=Profile 1
Parent=FALLBACK/
'''.lstrip()

user_files_with_exact_contents[
  f'~{desired_username}/.local/share/konsole/GreenOnBlack.colorscheme'] = '''
[Background]
Color=0,0,0

[BackgroundFaint]
Color=0,0,0

[BackgroundIntense]
Color=0,0,0

[Color0]
Color=0,0,0

[Color0Faint]
Color=24,24,24

[Color0Intense]
Color=104,104,104

[Color1]
Color=250,75,75

[Color1Faint]
Color=101,25,25

[Color1Intense]
Color=255,84,84

[Color2]
Color=24,178,24

[Color2Faint]
Color=0,101,0

[Color2Intense]
Color=84,255,84

[Color3]
Color=178,104,24

[Color3Faint]
Color=101,74,0

[Color3Intense]
Color=255,255,84

[Color4]
Color=24,24,178

[Color4Faint]
Color=0,0,101

[Color4Intense]
Color=84,84,255

[Color5]
Color=225,30,225

[Color5Faint]
Color=95,5,95

[Color5Intense]
Color=255,84,255

[Color6]
Color=24,178,178

[Color6Faint]
Color=0,101,101

[Color6Intense]
Color=84,255,255

[Color7]
Color=178,178,178

[Color7Faint]
Color=101,101,101

[Color7Intense]
Color=255,255,255

[Foreground]
Color=24,240,24

[ForegroundFaint]
Color=18,200,18

[ForegroundIntense]
Color=24,240,24

[General]
Anchor=0.5,0.5
Blur=false
ColorRandomization=false
Description=Green on Black
FillStyle=Tile
Opacity=0.75
Wallpaper=
WallpaperFlipType=NoFlip
WallpaperOpacity=1
'''.lstrip()

local_cloud_drive_path = f'~{desired_username}/GDrive'
cloud_drive_name = 'gdrive'
cloud_drive_type = 'drive'

prbsync_install_path = '$PREFIX/usr/bin/prbsync'
prbsync_cloud_path = '/Projects/PRBSync/prbsync.py'

common_desired_executables = {
  # prbsync_install_path: {
  #   'src': local_cloud_drive_path + prbsync_cloud_path,
  # },
  # '$PREFIX/bin/hashexec': {
  #   'src': f'~{desired_username}/GDrive/Projects/PRBSync/hashexec.py',
  #   'user': desired_username,
  # },
  # f'~{desired_username}/.local/bin/perfm': {
  #   'src': f'~{desired_username}/GDrive/Projects/PerfM/perfm',
  #   'user': desired_username,
  # },
}

arch_linux_desired_executables = {
  # '~root/.local/bin/auto_tpm_encrypt': {
  #   'src': f'~{desired_username}/GDrive/Projects/Linux/auto_tpm_encrypt.py',
  # },
  # '~root/.local/bin/boot_windows': {
  #   'src': f'~{desired_username}/GDrive/Projects/Linux/boot_windows.py'
  # },
}

@tasks.append
def ensure_desired_executables_exist_but_do_not_update_any_that_already_exist():
  executables = common_desired_executables
  if is_arch_linux():
    executables |= arch_linux_desired_executables
  for dst, meta in executables.items():
    install_executable_if_missing(meta['src'], dst, user = meta.get('user'))

# install_executable_if_missing(
#   f'~{desired_username}/GDrive/Projects/Linux/lincfg.py',
#   '~root/.local/bin/lincfg')

lincfg_cloud_path = f'~{desired_username}/GDrive/Projects/Linux/lincfg.py'

@lambda f: tasks.insert(0, f)
def ensure_lincfg_is_current():
  if not which('diffcp'):
    return
  src = fixpath(lincfg_cloud_path)
  if not os.path.isfile(src):
    src = sys.argv[0]
  lincfg_bin = fixpath(get_lincfg_bin_path())
  rc = diffcp_copy(
    'lincfg',
    lincfg_bin,
    sources = (src,),
    mode = OWNER_CAN_RWX,
  )
  if rc == 0:
    sys.exit(subprocess.run([lincfg_bin] + sys.argv[1:]).returncode)

rmtfs_var_path = '/var/lib/rmtfs'
rmtfs_service_paths = [
  '/usr/lib/systemd/system/rmtfs.service',
  '/usr/lib/systemd/system/rmtfs.service.d/10-msm-cros-efs-loader.conf',
]

# @lambda f: tasks.insert(1, f)
# def fix_msm_efs():
#   loader = which('msm-cros-efs-loader')
#   if loader and not os.path.isdir(rmtfs_var_path):
#     subprocess.check_call(loader)
#   if rmtfs:= which('rmtfs'):
#     desired_start = 'ExecStart=' + \
#       shlex.join((rmtfs, '-r', '-s', '-o', rmtfs_var_path))
#     changed = False
#     for rmtfs_service_path in rmtfs_service_paths:
#       p, rmtfs_service = read_config(rmtfs_service_path)
#       if desired_start not in rmtfs_service:
#         write_config(p, re.sub(r'ExecStart=.+', desired_start, rmtfs_service))
#         changed = True
#     if changed:
#       subprocess.check_call(('systemctl', 'daemon-reload'))
#       subprocess.check_call(('systemctl', 'restart', 'rmtfs'))
#       if not flags('offline') and (nm_online := which('nm-online')):
#         print('Fixed rmtfs, waiting for a conneciton...')
#         subprocess.check_call((nm_online, '-t', '600'))
#         time.sleep(30)

desired_tm_code = '''
#!/bin/sh
sudo /usr/bin/python3 -I /root/.local/bin/persistent_tmux "$USER"
tmux a -t persist
'''.lstrip()

@tasks.append
def ensure_tm_is_setup_and_up_to_date():
  p, tm_code = read_config(f'~{desired_username}/.local/bin/tm',
                          default_contents='')
  if tm_code != desired_tm_code:
    write_config(p, desired_tm_code, user = desired_username)
    os.chmod(p, 0o755)

@tasks.append
def ensure_user_files_with_exact_contents_are_correct():
  for path, desired_contents in user_files_with_exact_contents.items():
    path = fixpath(path)
    try:
      with open(path, 'r') as f:
        current_contents = f.read()
    except FileNotFoundError:
      current_contents = None
    if current_contents != desired_contents:
      write_config(path, desired_contents, user = desired_username)

arch_linux_prbsync_paths_to_hydrate = {'GDrive', 'OneDrive'}
postmarketos_prbsync_paths_to_hydrate = {'GDriveProjects', 'OneDriveProjects'}
termux_prbsync_paths_to_hydrate = {'GDriveProjects', 'OneDriveProjects'}

paths_to_bundle = {
  'full': (
    local_cloud_drive_path,
    f'~{desired_username}/OneDrive',
  ),
  'minimal': (
    os.path.join(local_cloud_drive_path, 'Projects'),
    f'~{desired_username}/OneDrive/Projects/Sessen',
    f'~{desired_username}/OneDrive/Projects/Game_Release_Checker',
  ),
}

@tasks.append
def handle_bundle_related_operations():
  bundle_root = os.path.abspath(os.path.join(__file__, '../../../..'))
  bundle_install_script = os.path.join(bundle_root, 'install_lincfg_bundle.sh')
  if os.path.isfile(bundle_install_script):
    print('Running bundle install script:', bundle_install_script)
    subprocess.check_call((get_shell(), bundle_install_script))
    import tomllib
    prbsync_config = tomllib.loads(prbsync_config_data)
    if is_arch_linux():
      paths_to_hydrate = arch_linux_prbsync_paths_to_hydrate
    elif is_postmarketos():
      paths_to_hydrate = postmarketos_prbsync_paths_to_hydrate
    elif is_termux():
      paths_to_hydrate = termux_prbsync_paths_to_hydrate
    btrfs_progs = which('btrfs-progs')
    for path_name in paths_to_hydrate:
      path = prbsync_config['syncable_paths'][path_name]
      subvolume = path.get('subvolume', True)
      local_path = path['local_path']
      if not local_path.startswith('~/'):
        raise RuntimeError(f'Unexpected path: {local_path}')
      bundle_path = os.path.join(bundle_root, local_path[2:])
      local_path = os.path.join(fixpath(f'~{desired_username}/'),
                                local_path[2:])
      if os.path.exists(local_path):
        continue
      if btrfs_progs and subvolume:
        subprocess.check_call((btrfs_progs, 'subvolume', 'create', local_path))
      else:
        os.mkdir(local_path)
      shutil.copytree(bundle_path, local_path, dirs_exist_ok = True)
  if flags('bundle'):
    k = 'LINCFG_BUNDLE_DEST'
    dest = os.environ.get(k)
    if not dest:
      raise KeyError(f'Set {k} to the destination for your bundle')
    bundle_size = (
      os.environ.get('LINCFG_BUNDLE_SIZE', 'minimal').lower().strip()
    )
    pfx = f'~{desired_username}/'
    bundle_root = os.path.join(dest, 'lincfg_bundle')
    os.mkdir(bundle_root)
    for path in paths_to_bundle[bundle_size]:
      if not path.startswith(pfx):
        raise RuntimeError(f'Unexpected path: {path}')
      dest = os.path.join(bundle_root, path[len(pfx):])
      src = fixpath(path)
      shutil.copytree(src, dest)
    make_bundle_script = fixpath('~/.local/share/lincfg/make_bundle.sh')
    subprocess.check_call((get_shell(), make_bundle_script),
                           env = dict(os.environ) | {
                             'LINCFG_BUNDLE_ROOT': bundle_root,
                             'LINCFG_BUNDLE_SIZE': bundle_size,
                           })

user_files_with_exact_contents[f'~{desired_username}/.config/perfm.toml'] = '''
# [actions.RustDesk]
# check_cmd = 'systemctl is-active --quiet rustdesk'
# enter_cmd = 'sudo systemctl stop rustdesk'
# exit_cmd = 'sudo systemctl start rustdesk'

[actions.Sessen]
check_cmd = 'systemctl is-active --quiet Sessen'
# enter_cmd = 'sh -c "exec ~/.local/share/sessen/snooze.sh"'
enter_cmd = 'sudo systemctl stop Sessen'
exit_cmd = 'sudo systemctl start Sessen'

[actions.PSnooze]
enter_cmd = 'sudo /bin/sh /root/.local/bin/psnooze'
exit_cmd = 'sudo /bin/sh /root/.local/bin/pwake'
'''.lstrip()

prbsync_config_data = '''
create_snapshots = true
log_level = 'all'
pager = 'less +G'
lock_in_state_dir = true
stable_wait_iterations = 25
retries_sleep = 180

[syncable_paths.GDrive]
local_path = '~/GDrive'
remote_path = 'gdrive:'
auto_sync_filter = [
  '+ Documents/ptaskrunner_workspace/*',
  '- *',
]

[syncable_paths.OneDrive]
local_path = '~/OneDrive'
remote_path = 'OneDrive:'
no_check_updated = true
# wait_until_stable_before_sync = true
min_time_between_syncs = 360
auto_sync_filter = [
  '+ Projects/ResultsLogger/**/*.txt',
  '+ Projects/Game_Release_Checker/*.{txt,json,csv}',
  '+ Projects/Sessen/Extensions/Readyr/**.json',
  '+ Downloads/**.txt',
  '+ Documents/Links for Mom and Dad.txt',
  '+ Documents/Scratch.txt',
  '+ Documents/Untrusted Notes.txt',
  '+ Projects/**.db',
  '+ Projects/**.log',
  '- *',
]
pre_sync_cmds = [
  # """
  # systemctl is-active --quiet Sessen && \
  # touch /tmp/sessen_restart_due.flag && \
  # sudo systemctl stop Sessen || true \
  # """,
]
post_sync_cmds = [
  # """
  # rm /tmp/sessen_restart_due.flag && \
  # sudo systemctl start Sessen || true \
  # """
  'systemctl is-active --quiet Sessen && sudo systemctl restart Sessen || true'
]

[syncable_paths.GDriveDownloads]
local_path = '~/GDrive/Downloads'
remote_path = 'gdrive:/Downloads'
subvolume = false

[syncable_paths.GDriveProjects]
local_path = '~/GDrive/Projects'
remote_path = 'gdrive:/Projects'
subvolume = false

[syncable_paths.GDriveTempws]
local_path = '~/GDrive/tempws'
remote_path = 'gdrive:/tempws'
subvolume = false

[syncable_paths.GDriveTrogdor]
local_path = '~/GDrive/tempws/trogdor'
remote_path = 'gdrive:/tempws/trogdor'
subvolume = false

[syncable_paths.OneDriveDocuments]
local_path = '~/OneDrive/Documents'
remote_path = 'OneDrive:/Documents'
auto_sync_filter = [
  '+ Links for Mom and Dad.txt',
  '+ Scratch.txt',
  '+ Untrusted Notes.txt',
  '- *',
]
subvolume = false

[syncable_paths.OneDriveDownloads]
local_path = '~/OneDrive/Downloads'
remote_path = 'OneDrive:/Downloads'
subvolume = false

[syncable_paths.OneDriveGames]
local_path = '~/OneDrive/Games'
remote_path = 'OneDrive:/Games'
subvolume = false

[syncable_paths.OneDriveNesbox]
local_path = '~/OneDrive/.nesbox'
remote_path = 'OneDrive:/.nesbox'
subvolume = false

[syncable_paths.OneDrivePictures]
local_path = '~/OneDrive/Pictures'
remote_path = 'OneDrive:/Pictures'
subvolume = false

[syncable_paths.OneDriveProjects]
local_path = '~/OneDrive/Projects'
remote_path = 'OneDrive:/Projects'
subvolume = false
'''.lstrip()

user_files_with_exact_contents[f'~{desired_username}/.config/prbsync.toml'] = prbsync_config_data

user_files_with_exact_contents[f'~{desired_username}/.config/healthcheck.toml'] = '''
log_path = '~/.local/state/healthcheck.log'

[entities.nodea]
class = 'apt'

[entities.nodec]
class = 'apt'

[entities.archserver]
class = 'pacman'

[entities.ReflectiveNAS]
class = 'external'
cwd = '~/.local/share/reflectivenas'
cmd = 'python healthcheck.py'

# TODO implement
[entities.CharonRMM]
class = 'external'
cwd = '~/.local/share/charonrmm'
cmd = 'python healthcheck.py'
'''.lstrip()

user_files_with_exact_contents[f'~{desired_username}/.config/git_mirror_sync.toml'] = r'''


# state_path = ''
# log_path = ''
# cache_dir = ''

kept_paths = ['LICENSE']

[git_config]
'core.pager' = 'less -iR'
'core.editor' = 'micro'
'user.name' = 'Liz'
'user.email' = '<>'

[substitutions]
'(?s)#\s*GIT_MIRROR_SYNC_EXCLUDE_BEGIN.+?GIT_MIRROR_SYNC_EXCLUDE_END' = ''
'(?is)rem\s*GIT_MIRROR_SYNC_EXCLUDE_BEGIN.+?GIT_MIRROR_SYNC_EXCLUDE_END' = ''

[repos.Gamepadify]
source = '~/GDrive/Projects/Gamepadify'
excluded_paths = ['old']
destination = '~/.local/share/git_mirrors/Gamepadify'
url = 'git@github.com:ElizabethF2/Gamepadify.git'

[repos.Gamepadify.renames]
mygamepad = 'examples/comprehensive_config.py'

[repos.MissionControlLite]
source = '~/GDrive/Projects/MissionControlLite'
excluded_paths = ['MissionControlLite.service']
destination = '~/.local/share/git_mirrors/MissionControlLite'
url = 'git@github.com:ElizabethF2/MissionControlLite.git'

[repos.PRBSync]
source = '~/GDrive/Projects/PRBSync'
destination = '~/.local/share/git_mirrors/PRBSync'
url = 'git@github.com:ElizabethF2/PRBSync.git'

[repos.Virtuator]
source = '~/GDrive/Projects/Virtuator'
destination = '~/.local/share/git_mirrors/Virtuator'
url = 'git@github.com:ElizabethF2/Virtuator.git'

[repos.Lockdown]
source = '~/GDrive/Projects/Lockdown'
excluded_paths = ['**old', '**.txt']
destination = '~/.local/share/git_mirrors/OS-Lockdown'
url = 'git@github.com:ElizabethF2/OS-Lockdown.git'

[repos.Sessen]
source = '~/OneDrive/Projects/Sessen'
excluded_paths = ['**.pem', '**.txt', '**.json', '**.db', '**.log', '**.pyc', '**__pycache__',
                  '**hello_world*', '**nas_helper*', 'sessen_quickstart_android.py',
                  'Extensions/Readyr', 'Extensions/EncryptedNAS', 'Extensions/MissionControl',
                  'Disabled Extensions', 'dev/old/test.py', 'dev/old/winpipe.py',
                  'sandboxpy', '**r1*', '**r2*', '**v1*', '**v2*']
destination = '~/.local/share/git_mirrors/Sessen'
url = 'git@github.com:ElizabethF2/Sessen.git'

[repos.SandboxPy]
source = '~/OneDrive/Projects/Sessen/sandboxpy'
excluded_paths = ['**__pycache__']
destination = '~/.local/share/git_mirrors/SandboxPy'
url = 'git@github.com:ElizabethF2/SandboxPy.git'

[repos.Readyr]
source = '~/OneDrive/Projects/Sessen/Extensions/Readyr'

destination = '~/.local/share/git_mirrors/Readyr'
url = 'git@github.com:ElizabethF2/Readyr.git'

[repos.MissionControl]
source = '~/OneDrive/Projects/Sessen/Extensions/MissionControl'
excluded_paths = ['__pycache__', '*.json', 'client_config.js']
destination = '~/.local/share/git_mirrors/MissionControl'
url = 'git@github.com:ElizabethF2/MissionControl.git'

[repos.CharonRMM]
source = '~/GDrive/Projects/CharonRMM'
excluded_paths = ['**.pem', '**.toml', '**scratch*', 'fix_rustdesk_key.py',
                  'wincfg.py']
destination = '~/.local/share/git_mirrors/CharonRMM'
url = 'git@github.com:ElizabethF2/CharonRMM.git'

[repos.MinecraftGravity]
source = '~/OneDrive/Projects/Mods/Minecraft/GravityJS'
excluded_paths = ['**-r1*', '*.mcpack']
destination = '~/.local/share/git_mirrors/MinecraftGravity'
url = 'git@github.com:ElizabethF2/MinecraftGravity.git'

[repos.PettyJSOS]
source = '~/OneDrive/Projects/PettyJSOS'
excluded_paths = ['**v1*']
destination = '~/.local/share/git_mirrors/PettyJSOS'
url = 'git@github.com:ElizabethF2/PettyJSOS.git'

[repos.pTaskRunner]
source = '~/GDrive/Projects/PerfM'
destination = '~/.local/share/git_mirrors/pTaskRunner'
url = 'git@github.com:ElizabethF2/pTaskRunner.git'

[repos.NPP_on_Kate]
source = '~/OneDrive/Projects/NPP on Kate'
excluded_paths = ['**r1*', '*.txt']
destination = '~/.local/share/git_mirrors/NPP_on_Kate'
url = 'git@github.com:ElizabethF2/NPP-on-Kate.git'

[repos.GiantCursor]
source = '~/OneDrive/Projects/GiantCursor'
excluded_paths = ['**.txt', '**.exe', '**.cur', 'bin', 'old']
destination = '~/.local/share/git_mirrors/GiantCursor'
url = 'git@github.com:ElizabethF2/GiantCursor.git'

[repos.ReflectiveNAS]
source = '~/OneDrive/Projects/ReflectiveNAS'

destination = '~/.local/share/git_mirrors/ReflectiveNAS'
url = 'git@github.com:ElizabethF2/ReflectiveNAS.git'

[repos.EncryptedNasBase]
source = '~/OneDrive/Projects/ReflectiveNAS/EncryptedNAS'

destination = '~/.local/share/git_mirrors/EncryptedNAS/base'

[repos.EncryptedNasExtension]
source = '~/OneDrive/Projects/Sessen/Extensions/EncryptedNAS'
excluded_paths = ['__pycache__', '**.json']
destination = '~/.local/share/git_mirrors/EncryptedNAS/extension'

[repos.EncryptedNasReadme]
source = '~/OneDrive/Projects/ReflectiveNAS/EncryptedNAS/README.md'
destination = '~/.local/share/git_mirrors/EncryptedNAS/README.md'

[repos.EncryptedNAS]
destination = '~/.local/share/git_mirrors/EncryptedNAS'
url = 'git@github.com:ElizabethF2/EncryptedNAS.git'

[repos.RedundantNAS]
source = '~/OneDrive/Projects/RedundantNAS'

destination = '~/.local/share/git_mirrors/RedundantNAS'
url = 'git@github.com:ElizabethF2/RedundantNAS.git'

[repos.StorageMinder]
source = '~/OneDrive/Projects/StorageMinder'
destination = '~/.local/share/git_mirrors/StorageMinder'
url = 'git@github.com:ElizabethF2/StorageMinder.git'

[repos.KnickKnack]
source = '~/OneDrive/Projects/KnickKnack'
excluded_paths = ['**.txt', '**.exe', '**.nds', '**.elf', 'nds/build']
destination = '~/.local/share/git_mirrors/KnickKnack'
url = 'git@github.com:ElizabethF2/KnickKnack.git'

[repos.MarionetteAPI]
source = '~/OneDrive/Projects/marionette'
excluded_paths = ['__pycache__']
destination = '~/.local/share/git_mirrors/marionette_api'
url = 'git@github.com:ElizabethF2/marionette_wrapper.git'

[repos.ResultsLogger]
source = '~/OneDrive/Projects/ResultsLogger'
excluded_paths = ['__pycache__', 'Logs', 'PublicLogs']
destination = '~/.local/share/git_mirrors/ResultsLogger'
url = 'git@github.com:ElizabethF2/ResultsLogger.git'

[repos.PowerNotifier]
source = '~/OneDrive/Projects/PowerNotifier'
excluded_paths = ['bin']
destination = '~/.local/share/git_mirrors/PowerNotifier'
url = 'git@github.com:ElizabethF2/PowerNotifier.git'

[repos.RNG]
source = '~/GDrive/Projects/rng.py'
destination = '~/.local/share/git_mirrors/Miscellaneous/rng.py'

[repos.PodcastDownloader]
source = '~/GDrive/Projects/podcast_downloader.py'
destination = '~/.local/share/git_mirrors/Miscellaneous/podcast_downloader.py'

[repos.UrlBulkOpener]
source = '~/GDrive/Projects/url_bulk_opener.htm'
destination = '~/.local/share/git_mirrors/Miscellaneous/url_bulk_opener.htm'

[repos.TransparentGApps]
source = '~/OneDrive/Projects/TransparentGApps.py'
destination = '~/.local/share/git_mirrors/Miscellaneous/TransparentGApps.py'

[repos.AlarmClock]
source = '~/OneDrive/Projects/Alarm Clock.htm'
destination = '~/.local/share/git_mirrors/Miscellaneous/Alarm Clock.htm'

[repos.Miscellaneous]
source = '~/GDrive/Projects/Linux'
excluded_paths = ['config', '*.yml', '*.tar.gz', 'mount_encrypted_drives.sh',
                  'prbsync*', 'snapshot_tool.py', ]
kept_paths = ['rng.py', 'podcast_downloader.py', 'url_bulk_opener.htm',
              'TransparentGApps.py', 'Alarm Clock.htm', ]
destination = '~/.local/share/git_mirrors/Miscellaneous'
url = 'git@github.com:ElizabethF2/Miscellaneous.git'

[repos.Miscellaneous.renames]
'miscellaneous.md' = 'README.md'

# no_pull = true
# branch = ''
# commands = []
# scripts = []
# procfile = 'ci.Procfile'
# procfile_process_type = 'release'
# sandbox = true
# sandbox_networking = false
# sandbox_read_only_paths = []
# sandbox_read_write_paths = []

'''.lstrip()

user_files_with_exact_contents[f'~{desired_username}/.config/steamrollr.vdf'] = '''
"config"
{
  "libraries"
  {
    "fp1"
    {
      "path" "~/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps"
    }

    "b1"
    {
      "path" "~/.var/app/com.usebottles.bottles/data/bottles/bottles/Secondary/drive_c/Program Files (x86)/Steam/steamapps"
    }

    "b2"
    {
      "path" "/srv/Tertiary/BottlesDriveT/SteamLibrary/steamapps"
    }

    "w1"
    {
      "root" "/srv/Windows"
      "path" "Program Files (x86)/Steam/steamapps"
      "mount_cmd" "sudo mount /dev/disk/by-label/Windows /srv/Windows"
      "no_snapshot" "True"
    }

    "w2"
    {
      "root" "/srv/Secondary"
      "path" "SteamLibrary"
      "mount_cmd" "sudo mount /dev/disk/by-label/Secondary /srv/Secondary"
      "no_snapshot" "True"
    }

    "ul1"
    {
      "path" "/srv/Quinary/BottlesDriveU/Ubisoft"
      "kind" "basic"
    }

    "uw1"
    {
      "root" "/srv/Senary"
      "path" "Ubisoft"
      "mount_cmd" "sudo mount /dev/disk/by-label/Senary /srv/Senary"
      "no_snapshot" "True"
    }
  }

  "slugs"
  {
    "260160" "lasttinker"
  }
}
'''.lstrip()

user_files_with_exact_contents[f'~{desired_username}/.config/konsolequickcommandsconfig'] = '''
[Default][Do All The Things!]
command=do_all_the_things
name=Do All The Things!
tooltip=

[Default][PRBSync Query]
command=prbsync query
name=PRBSync Query
tooltip=

[Default][PRBSync Log]
command=prbsync log
name=PRBSync Log
tooltip=

[Default][PRBSync Sync]
command=prbsync sync
name=PRBSync Sync
tooltip=

[Default][RLog]
command=rlog
name=RLog
tooltip=
'''.lstrip()

user_files_with_exact_contents[f'~{desired_username}/.config/kate/externaltools/New%20Scratch.ini'] = '''
[General]
actionName=externaltool_NewScratch
arguments=-c 'exec python ~/.local/share/npp_on_kate/new_scratch.py'
executable=/bin/sh
name=New Scratch
output=Ignore
reload=false
save=None
trigger=None
'''.lstrip()

kate_external_tools_configs = [
  '<Action name="externaltool_NewScratch" shortcut="Ctrl+Alt+N"/>',
]
kate_external_tools_config_path = f'~{desired_username}/.local/share/kxmlgui5/externaltools/ui.rc'

@tasks.append
def ensure_kate_external_tools_setup():
  p, kate_external_tools_config = read_config(kate_external_tools_config_path, default_contents = '')
  if kate_external_tools_config:
    desired = kate_external_tools_config
    for cfg in kate_external_tools_configs:
      if cfg not in desired:
        tag = '<ActionProperties scheme="Default">'
        idx = desired.index(tag) + len(tag)
        desired = desired[:idx] + '\n  ' + cfg + desired[idx:]
    if kate_external_tools_config != desired:
      write_config(p, desired, user = desired_username)

katepart_configs = [
  '<Action name="delete_line" shortcut=""/>',
  '<Action name="edit_redo" shortcut="Ctrl+Y"/>',
  '<Action name="tools_comment" shortcut="Ctrl+K"/>',
  '<Action name="tools_scripts_duplicateLinesDown" shortcut="Ctrl+D"/>',
  '<Action name="tools_uncomment" shortcut="Ctrl+Shift+K"/>',
]
katepart_redo_tag = '<Action group="edit_operations" name="edit_redo"/>'
katepart_reload_tag = '<Action name="file_reload"/>'
katepart_config_path = f'~{desired_username}/.local/share/kxmlgui5/katepart/katepart5ui.rc'

@tasks.append
def ensure_katepart_setup():
  p, katepart_config = read_config(katepart_config_path,  default_contents = '')
  if katepart_config:
    desired = katepart_config
    for cfg in katepart_configs:
      if cfg not in desired:
        tag = '<ActionProperties>'
        desired = re.sub(r'<ActionProperties[^>]+/>',
                         tag + '</ActionProperties>',
                         desired)
        idx = desired.index(tag) + len(tag)
        desired = desired[:idx] + '\n  ' + cfg + desired[idx:]
    if katepart_reload_tag not in katepart_config:
      try:
        idx = desired.index(katepart_redo_tag)
        lidx = desired.rindex('\n', 0, idx)
        tag = ((idx - lidx) * ' ') + katepart_reload_tag
        idx += len(katepart_redo_tag)
        desired = desired[:idx] + '\n' + tag + desired[idx:]
      except IndexError:
        pass
    if katepart_config != desired:
      write_config(p, desired, user = desired_username)

konsoleui_path = f'~{desired_username}/.local/share/kxmlgui5/konsole/konsoleui.rc'
konsoleui_plugins_submenu_tag = '<ActionList name="plugin-submenu"/>'

# @tasks.append
def add_plugins_to_konsole_ui():
  if not which('konsole'):
    return
  p, konsoleui = read_config(konsoleui_path, default_contents = '')
  if not konsoleui:
    return
  idx = konsoleui.index('Main Toolbar')
  idx = konsoleui.index('<Action', idx)
  first_action = konsoleui[idx : konsoleui.index('>', idx) + 1]
  if konsoleui_plugins_submenu_tag in first_action:
    return
  indent = idx - konsoleui.rindex('\n', 0, idx) - 1
  desired_konsoleui = (
    konsoleui[:idx] +
    konsoleui_plugins_submenu_tag + '\n' +
    (indent * ' ') + konsoleui[idx:]
  )
  write_config(p, desired_konsoleui, user = desired_username)

# user_files_with_exact_contents[f'~{desired_username}/.config/hashexec.toml'] = '''
# [entrypoints.Sessen]
# cmd = 'sh Sessen.sh'
# cwd = '~/OneDrive/Projects/Sessen'
# directories_to_check = [
#   '~/OneDrive/Projects/SpamDetector/bot.py',
#   '~/OneDrive/Projects/ReflectiveNAS/',
# ]
# ignored_paths = [
#   '~/OneDrive/Projects/Sessen/Extensions/Readyr/subscriptions.db',
#   '~/OneDrive/Projects/Sessen/Extensions/Readyr/spam_detector_user_cache.json',
#   '~/OneDrive/Projects/Sessen/datastore.db',
#   '~/OneDrive/Projects/Sessen/debug.log',
#   '~/OneDrive/Projects/ReflectiveNAS/EncryptedNAS/db/files.db',
# ]
#
# [entrypoints.Game_Release_Checker]
# cmd = 'sh game_release_checker.sh'
# cwd = '~/OneDrive/Projects/Game_Release_Checker'
# ignored_paths = [
#   '~/OneDrive/Projects/Game_Release_Checker/data.json',
#   '~/OneDrive/Projects/Game_Release_Checker/deathwatch.txt',
#   '~/OneDrive/Projects/Game_Release_Checker/early_access_games.txt',
#   '~/OneDrive/Projects/Game_Release_Checker/feeds.txt',
#   '~/OneDrive/Projects/Game_Release_Checker/game_sites.txt',
#   '~/OneDrive/Projects/Game_Release_Checker/news_sites.txt',
#   '~/OneDrive/Projects/Game_Release_Checker/price_checker_release_date_cache.txt',
#   '~/OneDrive/Projects/Game_Release_Checker/price_checker_title_cache.txt',
#   '~/OneDrive/Projects/Game_Release_Checker/price_history.csv',
#   '~/OneDrive/Projects/Game_Release_Checker/released_games.txt',
#   '~/OneDrive/Projects/Game_Release_Checker/twitter_users.txt',
#   '~/OneDrive/Projects/Game_Release_Checker/unreleased_games.txt',
#   '~/OneDrive/Projects/Game_Release_Checker/untrackable_games.txt',
# ]
#
# [entrypoints.Price_Checker]
# cmd = 'sh price_checker.sh'
# cwd = '~/OneDrive/Projects/Game_Release_Checker'
# ignored_paths = [
#   '~/OneDrive/Projects/Game_Release_Checker/data.json',
#   '~/OneDrive/Projects/Game_Release_Checker/deathwatch.txt',
#   '~/OneDrive/Projects/Game_Release_Checker/early_access_games.txt',
#   '~/OneDrive/Projects/Game_Release_Checker/feeds.txt',
#   '~/OneDrive/Projects/Game_Release_Checker/game_sites.txt',
#   '~/OneDrive/Projects/Game_Release_Checker/news_sites.txt',
#   '~/OneDrive/Projects/Game_Release_Checker/price_checker_release_date_cache.txt',
#   '~/OneDrive/Projects/Game_Release_Checker/price_checker_title_cache.txt',
#   '~/OneDrive/Projects/Game_Release_Checker/price_history.csv',
#   '~/OneDrive/Projects/Game_Release_Checker/released_games.txt',
#   '~/OneDrive/Projects/Game_Release_Checker/twitter_users.txt',
#   '~/OneDrive/Projects/Game_Release_Checker/unreleased_games.txt',
#   '~/OneDrive/Projects/Game_Release_Checker/untrackable_games.txt',
# ]
#
# [entrypoints.YouTube_Mix_Scraper]
# cmd = 'sh "YouTube Mix Scraper.sh"'
# cwd = '~/OneDrive/Projects/YouTube Mix Scraper'
# ignored_paths = [
#   '~/OneDrive/Projects/YouTube Mix Scraper/ai_tracks.txt',
# ]
# '''.lstrip()

# TODO startup sync

ptaskrunner_router_path = (
  f'/home/{desired_username}/.local/share/ptaskrunner/task_router.py'
)

system_files_with_exact_contents = {
# Works with most controllers
# '/etc/udev/rules.d/99-Gamepadify.rules': '''
# ACTION=="add", KERNEL=="js*", TAG+="systemd", ENV{SYSTEMD_WANTS}="Gamepadify.service"
# '''.strip(),

# Needed for 8BitDo Pro 3
'/etc/udev/rules.d/99-Gamepadify.rules': '''
ACTION=="add", SUBSYSTEM=="input", TAG+="systemd", ENV{SYSTEMD_WANTS}="Gamepadify.service"
'''.strip(),

'/etc/ptaskrunner.toml': f'''
[profiles.MCLite]
user = '{desired_username}'
task = 'python {ptaskrunner_router_path} task'
pre_stop_cmds = ['powerprofilesctl set performance']
post_restore_cmds = ['sudo -u {desired_username} sh -c "prbsync auto ; exit"']
snooze_timeout = '5 hours'
stopped_services = [
  'display-manager',
  'systemd-journald',
  'power-profiles-daemon',
  'upower.service',
  # 'systemd-journald',
  'udisks2',
  'polkit',
  'accounts-daemon',
  'getty*.service',
  'Sessen',
]
restarted_services = ['systemd-udevd']
logout_users = true

[profiles.Network]
user = '{desired_username}'
task = 'python {ptaskrunner_router_path} task'
pre_stop_cmds = ['powerprofilesctl set performance']
post_restore_cmds = ['sudo -u {desired_username} sh -c "prbsync auto ; exit"']
snooze_timeout = '5 hours'
stopped_services = [
  'display-manager',
  'systemd-journald',
  'power-profiles-daemon',
  'upower.service',
  # 'systemd-journald',
  'udisks2',
  'polkit',
  'accounts-daemon',
  'getty*.service',
  'MissionControlLite',
  'Sessen',
]
restarted_services = ['systemd-udevd']
logout_users = true

[profiles.Minimal]
user = '{desired_username}'
task = 'python {ptaskrunner_router_path} task'
pre_stop_cmds = ['powerprofilesctl set performance']
post_restore_cmds = ['sudo -u {desired_username} sh -c "prbsync auto ; exit"']
snooze_timeout = '5 hours'
stopped_services = [
  'display-manager',
  'systemd-journald',
  'power-profiles-daemon',
  'upower.service',
  'systemd-journald',
  'udisks2',
  'polkit',
  'accounts-daemon',
  'getty*.service',
  'MissionControlLite',
  'Sessen',
  'NetworkManager',
  'firewalld.service',
  'systemd-networkd',
  'systemd-resolved',
  'systemd-timesyncd',
  'systemd-userdbd',
  #'systemd-logind',
  'systemd-udevd',
  'rtkit-daemon',
  'wpa_supplicant.service',
]
restarted_services = ['systemd-udevd']
logout_users = true
'''.rstrip(),
}

@tasks.append
def ensure_system_files_with_exact_contents_are_up_to_date():
  if is_termux() or is_postmarketos():
    return
  for path, desired_contents in system_files_with_exact_contents.items():
    p, current = read_config(path, default_contents = '')
    if current != desired_contents:
      write_config(p, desired_contents)

user_files_with_exact_contents[f'~{desired_username}/.config/libreflectivenas.toml'] = '''
keep_alive_timeout = 30

[[sites]]
address = 'Liz@192.168.0.134'
key_filename = '~/.config/ssh/node_a_Liz.pem'
path = '/srv/ReflectiveNAS'

[[sites]]
address = 'ReflectiveNAS_user@192.168.2.134'
key_filename = '~/.config/ssh/node_c_reflectivenas_user.pem'
path = '/mnt/ReflectiveNAS'

'''.lstrip()

user_files_with_exact_contents[f'~{desired_username}/.ssh/config'] = '''
# Host linux_vm
#   HostName localhost
#   Port 6022
#   User root
#   IdentitiesOnly yes
#   IdentityFile ~/.cache/linux_vm_key.pem


'''.lstrip()

# TODO
# novnc_path = '/opt/noVNC'
# novnc_vars = {'DISPLAY': ':0.0', 'DESKTOP_SESSION': 'plasma'}
# xstartup_path = fixpath(f'~{desired_username}/.vnc/xstartup')
# vnc_password_path = fixpath(f'~{desired_username}/.vnc/passwd')
#
# @tasks.append
# def setup_novnc_in_container():
#   if in_container() and not os.path.exists(novnc_path) and not flags('offline'):
#     websockify_path = os.path.join(novnc_path, 'utils', 'websockify')
#     subprocess.run(shlex.split('git clone https://github.com/kanaka/noVNC.git') + [novnc_path])
#     subprocess.run(shlex.split('git clone https://github.com/kanaka/websockify') + [websockify_path])
#
#   if in_container() and not os.path.exists(xstartup_path):
#     write_config(xstartup_path, """
#       #!/bin/sh
#       # Run a generic session
#       if [ -z "$MODE" ]
#       then
#         export XKB_DEFAULT_RULES=base &
#         export QT_XKB_CONFIG_ROOT=/usr/share/X11/xkb &
#         #export $(dbus-launch) &
#         kstart5 plasmashell & #adds a task bar to the windows
#         dbus-launch startplasma-x11  #starts the actual window + Dolphin
#       fi
#       """, user=desired_username)
#
#
# if in_container() and not os.path.exists(vnc_password_path):
#   pass_bin = subprocess.check_output(['vncpasswd', '-f'], input=b'qaz123\n')
#   with open(os.open(vnc_password_path, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, mode=0o600), 'xb') as f:
#     f.write(pass_bin)
#   subprocess.run(['chown', desired_username+':', vnc_password_path])
#
# supervisord_pidfile = '/tmp/supervisord.pid'
# if in_container():
#   supervisor_conf_path, supervisor_conf = read_config(f'~{desired_username}/.config/supervisord.conf',
#                                                       default_contents='')
#   old, current, comment = make_config_version_vars(1, supervisor_conf)
#   if old < current:
#     write_config(supervisor_conf_path, f"""
#       {comment}
#       [supervisord]
#       nodaemon=true
#       childlogdir=/tmp
#       logfile=/tmp/supervisord.log
#       pidfile={supervisord_pidfile}
#
#       [supervisorctl]
#       serverurl=unix:///tmp/supervisor.sock
#
#       [program:tigervnc]
#       command=dbus-launch /usr/sbin/vncserver :0
#       autorestart=true
#
#       [program:noVNC]
#       command={novnc_path}/utils/novnc_proxy --vnc localhost:5900 --listen 8083
#       autorestart=true
#     """)

# p, bashrc = read_config(f'~{desired_username}/.bashrc', default_contents='\n')
# if in_container() and  '# start supervisord' not in bashrc:
  # write_config(p, bashrc +
                 # '\n\n# start supervisord\n' +
                 # '\n'.join(['export '+k+'='+v for k,v in novnc_vars.items()] + ['/usr/bin/supervisord &']) +
                 # '\n\n', user = desired_username)

user_files_only_created_once = {
f'~{desired_username}/.gtkrc-2.0': '''
gtk-theme-name="Breeze"
gtk-enable-animations=1
gtk-primary-button-warps-slider=0
gtk-toolbar-style=3
gtk-menu-images=1
gtk-button-images=1
gtk-cursor-theme-size=24
gtk-cursor-theme-name="breeze_cursors"
gtk-icon-theme-name="breeze-dark"
gtk-font-name="Noto Sans,  10"
''',

f'~{desired_username}/.config/kdeglobals': '''
[KDE]
LookAndFeelPackage=org.kde.breezedark.desktop

[KFileDialog Settings]
Show hidden files=true
''',

f'~{desired_username}/.local/share/kate/sessions/Default.katesession': '''
[Open MainWindows]
Count=1
''',
}

@tasks.append
def ensure_user_files_only_created_once_have_been_created():
  for path, desired_contents in user_files_only_created_once.items():
    p, old_contents = read_config(path, default_contents = '')
    if not old_contents:
      write_config(p, desired_contents, user = desired_username)

@tasks.append
def ensure_ktrash_is_configured():
  p, ktrashrc = read_config(f'~{desired_username}/.config/ktrashrc', default_contents='')
  if ktrashrc:
    new_ktrashrc = ktrashrc \
      .replace('UseSizeLimit=true', 'UseSizeLimit=false') \
      .replace('UseTimeLimit=true', 'UseTimeLimit=false')
    if new_ktrashrc != ktrashrc:
      write_config(p, new_ktrashrc, user = desired_username)
  else:
    write_config(p, f'[{p}]\n' +
                    'UseSizeLimit=false\n' +
                    'UseTimeLimit=false\n')

@tasks.append
def ensure_dolphin_is_configured():
  desired_value = 'HiddenFilesShown=true'
  p, dolphin_props = read_config(f'~{desired_username}/.local/share/dolphin/view_properties/global/.directory', default_contents='')
  if dolphin_props and desired_value not in dolphin_props:
    current = get_config_var(dolphin_props, 'HiddenFilesShown')
    if current != 'None':
      dolphin_props.replace(current, desired_value)
    elif '[Settings]' in dolphin_props:
      dolphin_props.replace('[Settings]', '[Settings]\n'+desired_value)
    else:
      dolphin_props += '\n\n[Settings]\n'+desired_value
    write_config(p, dolphin_props, user = desired_username)

@tasks.append
def ensure_limits_conf_setup():
  if is_termux():
    return
  p, limits_conf = read_config('/etc/security/limits.conf')
  comment = '# disable core dumps'
  if comment not in limits_conf:
    write_config(p, limits_conf + '\n\n' + comment +
                    '* soft core 0\n* hard core 0\n')

login_defs_path = '/etc/login.defs'
desired_login_def_cfgs = [
  'SHA_CRYPT_MIN_ROUNDS 99999',
  'UMASK 027',
]

@tasks.append
def ensure_login_defs_setup():
  if is_termux():
    return
  rx = r'UMASK\s+022'
  p, login_defs = read_config(login_defs_path)
  if any((cfg not in login_defs for cfg in desired_login_def_cfgs)):
    desired_cfgs_by_name = {i.split()[0]: i for i in desired_login_def_cfgs}
    lines = login_defs.splitlines()
    lines_to_add = ['', '# Added via lincfg']
    for idx in range(len(lines)):
      line = lines[idx]
      if not line:
        continue
      name = line.split()[0]
      if name in desired_cfgs_by_name:
        if line not in desired_login_def_cfgs:
          lines[idx] = '# ' + line
        else:
          desired_cfgs_by_name.pop(name)
    lines_to_add.extend(desired_cfgs_by_name.values())
    write_config(p, '\n'.join(lines + lines_to_add) + '\n')

sshd_config_path = '/etc/ssh/sshd_config'
desired_sshd_config_mode = 0o600
@tasks.append
def ensure_sshd_config_has_desired_mode():
  try:
    if (os.stat(sshd_config_path).st_mode & 0o777) != desired_sshd_config_mode:
      os.chmod(sshd_config_path, desired_sshd_config_mode)
  except FileNotFoundError:
    pass

# See also: KRNL-6000 from Lynis
desired_sysctl_values = {
  'dev.tty.ldisc_autoload': 0,
  'fs.protected_fifos': 2,
  'fs.protected_regular': 2,
  'fs.suid_dumpable': 0,
  'kernel.kptr_restrict': 2,
  'kernel.perf_event_paranoid': 3,
  'kernel.unprivileged_bpf_disabled': 1,
  'net.core.bpf_jit_harden': 2,
  'net.ipv4.conf.all.accept_redirects': 0,
  'net.ipv4.conf.all.rp_filter': 1,
  'net.ipv4.conf.all.send_redirects': 0,
  'net.ipv4.conf.default.accept_redirects': 0,
  'net.ipv6.conf.all.accept_redirects': 0,
  'net.ipv6.conf.default.accept_redirects': 0,
}

def any_desired_values_not_set(cfg):
  for name, value in desired_sysctl_values.items():
    if re.findall(r'\n'+name.replace('.','\\.')+r'\s*=\s*(\d+)', cfg) != [str(value)]:
      return True
  return False

arch_linux_default_sysctl_cfg_path = '/usr/lib/sysctl.d/50-default.conf'
alpine_default_sysctl_cfg_path = '/usr/lib/sysctl.d/00-alpine.conf'

@tasks.append
def ensure_sysctl_values_set():
  if is_termux():
    return
  if is_arch_linux():
    p = arch_linux_default_sysctl_cfg_path
  if is_postmarketos():
    p = alpine_default_sysctl_cfg_path
    return # TODO actually implement this - need restore_file_from_package support
  p, sysctl_cfg = read_config(p)
  if any_desired_values_not_set(sysctl_cfg):
    restore_file_from_package('systemd', p)
    p, sysctl_cfg = read_config(p)
    if any_desired_values_not_set(sysctl_cfg):
      for name, value in desired_sysctl_values.items():
        new = re.sub(r'\n'+name.replace('.',r'\.')+r'\s*=\s*(\d+)',
                    '\n'+name+' = '+str(value),
                    sysctl_cfg)
        if new != sysctl_cfg:
          sysctl_cfg = new
        else:
          sysctl_cfg += '\n'+name+' = '+str(value)
      write_config(p, sysctl_cfg)

# See also: NETW-3200 from Lynis
target_protocols_modprobe_cfg = '''
install dccp /bin/true
install sctp /bin/true
install rds /bin/true
install tipc /bin/true
'''

@tasks.append
def ensure_uncommon_protocols_blocked():
  if is_termux():
    return
  p, protocols_modprobe_cfg = read_config('/etc/modprobe.d/block_uncommon_protocols.conf', default_contents='')
  if protocols_modprobe_cfg != target_protocols_modprobe_cfg:
    write_config(p, target_protocols_modprobe_cfg)

@tasks.append
def remove_egrep_warning():
  if not is_arch_linux():
    return
  p, egrep_script = read_config(which('egrep'))
  if 'echo' in egrep_script and 'warning' in egrep_script and '#echo' not in egrep_script:
    write_config(p, egrep_script.replace('echo', '#echo'))

desired_python_packages = {
  'https://pypi.io/packages/source/u/uploadserver/uploadserver-6.0.0.tar.gz':
    '68f078bcd3dd986f97d6b6ecef51c3866986858288ced5a474df7896796837bf',

  'https://pypi.io/packages/source/b/bt-dualboot/bt-dualboot-1.0.1.tar.gz':
    'a63cc6bcb928b50965cf2ae7c6a0c88c696904ebd43e45a9bf47a8a0252b82ff',
}

keyd_conf_path = '/etc/keyd/default.conf'
keyd_service_path = '/etc/systemd/system/keyd.service'
invert_function_keys = True
keyd_service = '''
[Unit]
Description=key remapping daemon

[Service]
Type=simple
ExecStart=/usr/bin/keyd

[Install]
WantedBy=multi-user.target
'''.lstrip()

@tasks.append
def fix_keyd_config():
  pmos_generate_cros_keymap = which('pmos-generate-cros-keymap')
  if not pmos_generate_cros_keymap:
    return
  if os.path.isfile(keyd_conf_path):
    return
  if not os.path.lexists(keyd_conf_path):
    return
  os.remove(keyd_conf_path)
  subprocess.check_call([pmos_generate_cros_keymap, '-f', keyd_conf_path] +
                         (['-i'] if invert_function_keys else []))
  if not os.path.isfile(keyd_service_path):
    write_config(keyd_service_path, keyd_service)
  subprocess.check_call(('systemctl', 'enable', 'keyd', '--now'))

@tasks.append
def ensure_python_packages_updated():
  if not flags('offline'):
    for url, pkg_hash in desired_python_packages.items():
      ensure_python_package(url, pkg_hash)

# NB: Moved to container
# ensure_python_package(
#   'https://pypi.io/packages/source/m/mozrunner/mozrunner-8.3.0.tar.gz',
#   'efbe61a325d87a60d2831ac5ac0578883f5d7f305bfa278cbdcec58b1f4d9217',
#   desired_username)
#
# ensure_python_package(
#   'https://pypi.io/packages/source/m/mozlog/mozlog-8.0.0.tar.gz',
#   '26e5e9586afe2d6359a3d75aa6ea25aa2904d0062d0a158418682e44458d98e9',
#   desired_username)
#
# ensure_python_package(
#   'https://pypi.io/packages/source/m/mozversion/mozversion-2.4.0.tar.gz',
#   '5b11ceb280c519cd92f450b91a750ae8b7f7c8258f6e93c7e520592d85ffbf07',
#   desired_username)
#
# ensure_python_package(
#   'https://pypi.io/packages/source/m/marionette_driver/marionette_driver-3.4.0.tar.gz',
#   'c5f916e7215850150a717b3ce492c06febfea385d8add53f22d0da92d13dc0a9',
#   desired_username)

# site_package_dir = site.getsitepackages()[0]
# if not os.path.exists(os.path.join(site_package_dir, 'alienfx')) or True:
#   # TODO (WIP) git clone, hash, patch, etc
#   tdir = '/home/Liz/Downloads/Unscanned/AlienFX/alienfx'
#   tdir = tdir if tdir.endswith(os.sep) else (tdir + os.sep)
#   files = glob.glob(tdir+'alienfx/**', recursive = True)
#   files = set(filter(lambda f: any((f.endswith(i) for i in ('.py', '.glade'))), files))
#   for f in files:
#     dst = os.path.join(site_package_dir, f[len(tdir):])
#     makedirs(os.path.dirname(dst), )
#     shutil.copy(f, dst)
#     os.chmod(dst, 0o644)

@tasks.append
def set_firefox_policies_in_container():
  if not in_container():
    return
  p, policies = read_config('/usr/lib/firefox/distribution/policies.json',
                            default_contents='')
  if policies:
    return
  policies = {}
  unlisted_notes_url = os.environ.get('UNLISTED_NOTES_URL')
  if unlisted_notes_url:
    policies['Bookmarks'] = [{'Title':'Unlisted Notes', 'URL':unlisted_notes_url}]
  policies['DisableTelemetry'] = True
  policies['ExtensionSettings'] = {
    'uBlock0@raymondhill.net': {
      'installation_mode': 'force_installed',
      'install_url': 'https://addons.mozilla.org/firefox/downloads/latest/ublock-origin/latest.xpi'
    },
    'addon@darkreader.org': {
      'installation_mode': 'force_installed',
      'install_url': 'https://addons.mozilla.org/firefox/downloads/latest/darkreader/latest.xpi'
    },
  }
  write_config(p, json.dumps({'policies': policies}))

GITHUB_BASE_URL = 'https://github.com/'
GITHUB_RELEASES_PATH = '/releases/latest'

github_repos_used_by_aur_packages = {
  'maldet': 'rfxn/linux-malware-detect',
  # 'rustdesk': 'rustdesk/rustdesk',
}

out_of_date_aur_packages = {}

@tasks.append
def check_for_out_of_date_aur_packages():
  if not is_arch_linux():
    return
  if not flags('offline'):
    for package, repo in github_repos_used_by_aur_packages.items():
      if not which(package):
        continue
      installed_version = re.findall(package+r'\s+(.+)', subprocess.check_output(['pacman', '-Q']).decode())[0]
      url = GITHUB_BASE_URL + repo + GITHUB_RELEASES_PATH
      latest_version = re.findall('/tree/(.+?)[\'|"]',
                                  urllib.request.urlopen(url)
                                    .read().decode())[0].replace('-', '.')
      current_version = installed_version.split('-')[0]
      if current_version != latest_version:
        out_of_date_aur_packages[package] = {
          'upstream_version': latest_version,
          'installed_version': current_version,
          'upstream_url': url,
        }

AUR_PACKAGE_BASE_URL = 'https://aur.archlinux.org/packages/'
AURWEB_RPC_INFO_BASE_URL = 'https://aur.archlinux.org/rpc/v5/info?'

@tasks.append
def warn_about_outdated_aur_packages():
  if not flags('interact') and len(out_of_date_aur_packages) > 0:
    url = AURWEB_RPC_INFO_BASE_URL + '&'.join(
      (f'arg[]={p}' for p in out_of_date_aur_packages.keys()))
    aur_metadata = {
      result['Name']: {
        'version': result['Version'].split('-')[0],
        'last_modified': result['LastModified'],
      }
      for result in json.loads(urllib.request.urlopen(url).read())['results']
    }
    for interactive in (False, True):
      for name, meta in out_of_date_aur_packages.items():
        ameta = aur_metadata[name]
        if ((not interactive and ameta['version'] != meta['upstream_version'])
            or (interactive and ameta['version'] == meta['upstream_version'])):
          m = time.strftime('%Y-%m-%d', time.gmtime(ameta['last_modified']))
          alert(name + ' is out of date',
                'Upstream version: ' + meta['upstream_version'],
                'AUR version: ' + ameta['version'],
                'Installed version: ' + meta['installed_version'],
                f'AUR last modified: {m}',
                f'AUR URL: {AUR_PACKAGE_BASE_URL + name}',
                f'Upstream URL: {meta['upstream_url']}',
              interactive = interactive)

aur_packages = [
  ('maldet',
    '37ca05bee1b5ab6fb8ad843ab6cd00a9da0fb949',
    '15dd5671bb8657359c3cba3df2347a1243b79ac2204c42a08b8757fc992c04de',
    ['inetutils', 'inotify-tools', 'ed', 'base-devel', 'perl']),
]

aur_packages_installed_via_aur_helper = [
  # 'rustdesk'
]

reasons_interactive_setup_needed = []

@tasks.append
def interactively_setup_aur_packages():
  if not flags('interact') or flags('offline') or not is_arch_linux():
    return
  installed_packages = get_installed_packages(include_version = False)

  for name, commit, hash, dependencies in aur_packages:
    if name not in installed_packages:
      subprocess.run(['pacman', '-Syu', '--noconfirm', '--needed'] + dependencies)
      tdir = tempfile.mkdtemp(prefix=name+'_build_')
      subprocess.run(['git', 'clone', 'https://aur.archlinux.org/'+name+'.git', tdir])
      subprocess.run(['chown', '-R', 'nobody:', tdir])
      print('\nEntering an interactive shell:')
      print('  1) Manually verify the PKGBUILD')
      print('  2) Download sources via makepkg -o')
      print('  3) Manually verify the sources')
      print('  4) Exit the shell')
      print('The script will automatically build and install '+name.capitalize()+' when you exit')
      latest_commit = subprocess.check_output(['runuser', '-unobody', 'git', 'rev-parse', 'HEAD'],
                                              cwd=tdir).decode().strip()
      shutil.rmtree(os.path.join(tdir, '.git'))
      tdir_hash = hash_path(tdir)
      print('Latest Commit:', latest_commit)
      print('Hash:', tdir_hash)
      print('Build Directory:', tdir)
      if latest_commit != commit:
        print('A newer version of ' + name + ' is available than the one known by this script.')
        print('Re-audit the new package and update the commit and hash in the script.')
        input('...')
      elif tdir_hash != hash:
        print('The packages has did not match the known hash. Please investigate.')
        input('...')
      else:
        subprocess.run(['runuser', '-unobody', 'bash'], cwd=tdir, check=False)
        subprocess.run(['runuser', '-unobody', 'makepkg'], cwd=tdir, check=False)
        pkg = os.path.join(tdir, tuple(filter(lambda i: i.endswith('.tar.zst'), os.listdir(tdir)))[0])
        subprocess.run(['pacman', '-U', '--noconfirm', pkg])
        shutil.rmtree(tdir)

    for package in aur_packages_installed_via_aur_helper:
      # NB: package name doesn't always match command name - fix this later if/when needed
      if not which(package) or package in out_of_date_aur_packages:
        which.cache_clear()
        print('Building', package, 'in container')
        subprocess.check_call(('podman', 'pull', 'docker.io/library/archlinux'))
        subprocess.check_call(('podman', 'run', '--name', package, '-h', package+'-builder', '-itd', 'docker.io/library/archlinux', '/bin/bash'))
        cmds = """
          pacman-key --refresh-keys # slow but currently necessary
                                    # may comment out in future
          pacman -Syu --needed --noconfirm git base-devel sudo micro less tmux \
                                          busybox python pyalpm
          echo "%wheel ALL=(ALL:ALL) NOPASSWD: ALL" > /etc/sudoers.d/wheel
          useradd -m builder
          usermod -aG wheel builder
          curl -L -o /tmp/pikaur.tar.gz \
            https://github.com/actionless/pikaur/archive/refs/tags/1.32.tar.gz
          (sha256sum /tmp/pikaur.tar.gz | \
            grep d1ba2f28943f3028c530781783b0748cca93eed935e52099381ef3461c8dedc0) && \
              mkdir -p ~builder/pikaur && tar xzf /tmp/pikaur.tar.gz -C ~builder/pikaur
          mv ~builder/pikaur/pikaur-*/* ~builder/pikaur/
          chown -R builder: ~builder/pikaur
        """
        cmds = list(map(str.strip, cmds.strip().splitlines()))
        cmds.append('sudo -u builder ' +
                    'EDITOR=micro python ~builder/pikaur/pikaur.py ' +
                    '-Sw --keepbuild --keepbuilddeps ' + package)
        for cmd in cmds:
          subprocess.check_call(('podman', 'exec', '-it', package, '/bin/sh', '-c', cmd))
        pikaur_cache = '/home/builder/.cache/pikaur/pkg/'
        o = subprocess.check_output(('podman', 'exec', '-it', package, '/bin/sh', '-c', 'ls ' + pikaur_cache))
        package_fname = list(filter(
          lambda i: 'pkg.tar' in i and i.startswith(f'{package}-'),
          o.decode().split()))[0]
        container_pkg_path = pikaur_cache + package_fname
        tdir = tempfile.mkdtemp(prefix=package+'_build_')
        tdir_pkg_path = os.path.join(tdir, package_fname)
        subprocess.check_call(('podman', 'cp', package+':'+container_pkg_path, tdir_pkg_path))
        print('')
        print('Build completed')
        print('Package Name:', package)
        print('Pikaur Cache:', pikaur_cache)
        print('Package Path (Container):', container_pkg_path)
        print('Package Path (Local):', tdir_pkg_path)
        print('')
        print('An interactive shell will now be opened within the container.')
        print('Please verify the PKGBUILD, sources, artifacts, etc of all packages,')
        print('including dependencies.')
        print('Exit the shell when you are done.')
        print('')
        subprocess.check_call(('podman', 'exec', '-u', 'builder', '-it', package, '/bin/sh', '-c', 'cd;ls -halt;bash'))
        print('')
        print('Package Path (Local):', tdir_pkg_path)
        print('Enter BUILDOK to install the above package which was built in the container.')
        print('NOTE: The container will be deleted if you do. Enter anything else or abort')
        print('      the script to avoid installing the package or removing the container.')
        print('')
        inp = input('> ')
        if inp == 'BUILDOK':
          subprocess.check_call(('pacman', '-U', '--noconfirm', tdir_pkg_path))
          subprocess.check_call(('podman',
                                'exec',
                                '-it',
                                package,
                                '/bin/sh',
                                '-c',
                                'pkill -HUP sh'))
          subprocess.check_call(('podman', 'rm', package))
          shutil.rmtree(tdir)
        else:
          print('Skipping install and container removal for', package)

UNUSED_DART_INSTALL_SCRIPT = '''
# type apk && apk add dart icu-libs --repository=http://dl-cdn.alpinelinux.org/alpine/edge/testing

DART_VER=3.10.1
git clone --depth 1 --branch $DART_VER https://github.com/dart-lang/sdk.git dart-sdk
git -c core.abbrev=no -C dart-sdk archive --format tar $DART_VER | sha256sum | \
  grep c94c3dca92e9a83d8c80f5abef5dfd77eaf0338978cb75bc73a5d136fd093b79 || exit 1

DEPOT_VER=12b3e1f95e1377c0fe9cc3c84bc64193b234346b
git clone --depth 1 --revision=$DEPOT_VER https://chromium.googlesource.com/chromium/tools/depot_tools.git depot-tools
git -c core.abbrev=no -C depot-tools archive --format tar $DEPOT_VER | sha256sum | \
  grep 7de37e557d18f51ed87de52bd25b0b051ebcf2c6237468410d16939006ed2c66 || exit 1

# cat > ~/.gclient <<EOF
# solutions = [
#   {
#     "name": "sdk",
#     "url": "file://$(echo ~/dart-sdk/sdk)",
#     "deps_file": "DEPS",
#     "managed": False,
#     "custom_deps": {},
#     "custom_vars": {},
#   },
# ]
# EOF
#
# cd ~/dart-sdk/sdk
# ~/depot-tools/gclient -D \
#   --nohooks \
#   --no-history \
#   --shallow \
#   -r "${srcdir}/sdk@${_commit}"

cd ~/dart-sdk
mkdir buildtools
ln -s "$(command -v gn)" buildtools/gn
ln -s "$(command -v ninja)" buildtools/ninja
touch build/config/gclient_args.gni
python3 ./tools/build.py --mode release create_sdk
'''

UNUSED_RUSTDESK_INSTALL_SCRIPT = r'''
# References:
#   https://aur.archlinux.org/cgit/aur.git/tree/PKGBUILD?h=rustdesk
#   https://gitlab.alpinelinux.org/alpine/aports/-/blob/master/testing/dart/APKBUILD
#   https://gitlab.alpinelinux.org/alpine/aports/-/blob/master/testing/flutter/APKBUILD
WS="$(echo ~/.cache/rustdesk_ws)"
# TODO use nobody rather than builder

apk add alpine-make-rootfs
CHROOT=~builder/chroot
mkdir -p "$CHROOT/ws"
alpine-make-rootfs --branch edge --packages 'apk-tools' "$CHROOT"

echo http://dl-cdn.alpinelinux.org/alpine/edge/testing >> "$CHROOT/etc/apk/repositories"
apk update --root "$CHROOT"
apk add --root "$CHROOT" flutter-tool-developer git gcc g++ make cargo \
  glib-dev gstreamer-dev gst-plugins-base-dev gtk+3.0-dev openssl-dev \
  linux-pam-dev libvpx-dev libyuv-dev libyuv opus-dev aom-dev xdotool-dev \
  ffmpeg6-dev perl clang-libclang

# type pacman && pacman -S dart

bwrap_common() {
  bwrap \
    --die-with-parent \
    --new-session \
    --unshare-user \
    --disable-userns \
    --unshare-ipc \
    --unshare-pid \
    --unshare-all \
    --clearenv \
    --bind $CHROOT / \
    --chdir /ws \
    --proc /proc \
    --tmpfs /tmp \
    --tmpfs /run \
    --dev /dev \
    --setenv HOME /ws \
    --setenv PATH $PATH:/ws/.cargo/bin \
    --setenv VCPKG_ROOT /ws/.VCPKG_ROOT \
    --setenv RUSTFLAGS '-l dylib=opus -l dylib=vpx -l dylib=avcodec -l dylib=avutil -l dylib=avformat' \
    "$@"
}

# NB: from non-root!
bwrap_common --share-net /bin/bash

wget -O main.tar.gz https://github.com/rustdesk/rustdesk/archive/refs/tags/1.4.5.tar.gz
sha256sum main* | grep 0bf3b6f1e447bf7c24bbc005df2c6b91a60f05a873a4df8798fb1f711d22faa4 || exit 1

wget -O hbb_common.tar.gz https://github.com/rustdesk/hbb_common/archive/073403edbf1fffcb3acfe8cbe7582ee873b23398.tar.gz
sha256sum hbb* | grep 73f44cefbc27b32f259de84e19a251f196e53d096d15c747197d37d9b79e6ee5 || exit 1

wget -O bridge.tar.gz https://github.com/fzyzcjy/flutter_rust_bridge/archive/refs/tags/v1.80.1.tar.gz
sha256sum bridge* | grep 5c1494e79024de228a9f383c8e52e45b042cd0cf24f4b0f47ee4d5448938b336 || exit 1

for i in $(ls *); do
  tar xf $i
done

# cd ~/rustdesk-*/flutter
# flutter pub get --enforce-lockfile

cd ~/rustdesk-*
mv ~/hbb_common-*/* ~/rustdesk-*/libs/hbb_common
cargo fetch --locked

cd ~/flutter_rust_bridge-*
cargo fetch --locked

# NB: from non-root!
bwrap_common /bin/bash

mkdir -p ~/.VCPKG_ROOT/installed/arm64-linux/lib/include
mkdir -p ~/.VCPKG_ROOT/installed/x64-linux/lib/include

# Fix mkv build error
cd ~
sed -i '1 i\#include <cstdint>' "$(find -name mkvparser.cc)"

# Fix opus to use dylib
sed -i 's/=static/=dylib/' "$(find -path '*magnum-opus*build.rs')"

# Fix hwcodec to use dylib
sed -i 's/=static/=dylib/' "$(find -path '*hwcodec*build.rs' | head -n1)"

# Disable self-update
cd ~/rustdesk-*
sed -i 's/\!bind.isCustomClient()/false/' flutter/lib/desktop/pages/desktop_home_page.dart

# Fix vpx to use dylib
sed -i 's/=static/=dylib/' libs/scrap/build.rs

cd ~/flutter_rust_bridge-*/frb_codegen
cargo install --frozen --features "uuid" --path .

cd ~/rustdesk-*
~/.cargo/bin/flutter_rust_bridge_codegen \
  --rust-input src/flutter_ffi.rs \
  --dart-output flutter/lib/generated_bridge.dart \
  --c-output flutter/macos/Runner/bridge_generated.h

# TODO swapon before this script
cd ~/rustdesk-*
cargo build --frozen --release --lib --features flutter,hwcodec
cargo build --frozen --release --bin rustdesk --features flutter,hwcodec

cd ~/rustdesk-*/target/release
'''

LATEST_MALDET_VERSION = '1.6.6'

MALDET_SETUP_SCRIPT = r'''
# Reference: https://aur.archlinux.org/cgit/aur.git/tree/PKGBUILD?h=maldet

WS="$(mktemp -d ${TMPDIR:-/tmp}/maldet_setup_XXXXXX)"
echo "Maldet Setup Workspace: $WS"
chown nobody: "$WS"

(
cat <<EOF

cd $WS
wget -O main.tar.gz https://github.com/rfxn/linux-malware-detect/archive/1.6.6.1.tar.gz
b2sum main* | \\
  grep 67fb4daeb10e898f67f9dec6d8033c6f9ebabd4041cc55eb0e16cc5d9291a8e3114aff9444df31def6314c5add2dfb6dac7a7f3ed64ec8477ceb8ce6feed8ced || \\
  exit 1

tar xzf main*

cd linux-malware-detect-*
sed -i "files/maldet" \
    -e "s|^inspath='/usr/local/maldetect'|inspath='/usr/share/maldet'|" \
    -e 's|^intcnf="\$inspath/internals/internals.conf"|intcnf="/etc/maldet/internals.conf"|'

sed -i "files/hookscan.sh" \
    -e "s|^inspath='/usr/local/maldetect'|inspath=\"/usr/share/maldet\"|" \
    -e 's|^intcnf="$inspath/internals/internals.conf"|intcnf="/etc/maldet/internals.conf"|' \
    -e 's|hookcnf="$inspath/conf.maldet.hookscan"|hookcnf="/etc/maldet/hookscan.conf"|' \
    -e 's|$inspath/maldet|/usr/bin/maldet|' \
    -e 's|tmpdir=/var/tmp|tmpdir=/var/lib/maldet/tmp|'

sed -i "files/conf.maldet" \
     -e "s|/usr/local/maldetect/tmp|/var/lib/maldet/tmp|" \
     -e "s|/usr/local/maldetect/monitor_paths|/etc/maldet/monitor_paths|"

sed -i "files/ignore_inotify" \
    -e 's|\^/usr/local/maldetect\*|\^/var/lib/maldetect\*\n\^/usr/share/maldetect\*|'

sed -i "files/ignore_paths" \
    -e "s|/usr/local/maldetect|/var/lib/maldet\n/usr/share/maldet|" \
    -e "s|/usr/local/sbin/maldet|/usr/bin/maldet|"

sed -i "files/internals/functions" \
    -e 's|$inspath/maldet|/usr/bin/maldet|'

sed -i "files/internals/hexfifo.pl" \
    -e "s|/usr/local/maldetect/internals|/usr/share/maldetect/internals|"

sed -i "files/internals/importconf" \
    -e "s|/usr/local/maldetect/conf.maldet|/etc/maldet/maldet.conf|" \
    -e "s|/usr/local/maldetect/tmp|/var/lib/maldet/tmp|" \
    -e "s|/usr/local/maldetect/monitor_paths|/etc/maldet/monitor_paths|"

sed -i "files/internals/internals.conf" \
    -e 's|^logdir="\$inspath/logs"|logdir="/var/log/maldet"|' \
    -e 's|^inspath=/usr/local/maldetect|inspath="/usr/share/maldet"|' \
    -e 's|^intcnf="$inspath/internals/internals.conf"|intcnf="/etc/maldet/internals.conf"|' \
    -e 's|^confpath="\$inspath"|confpath="/etc/maldet"|' \
    -e 's|^cnffile="conf.maldet"|cnffile="maldet.conf"|' \
    -e 's|^varlibpath="\$inspath"|varlibpath="/var/lib/maldet"|' \
    -e 's|^tmpdir="\$inspath/tmp"|tmpdir="$varlibpath/tmp"|' \
    -e 's|^inotify_log="\$inspath/logs/inotify_log"|inotify_log="$logdir/inotify_log"|'

sed -i "files/internals/scan.etpl" \
    -e "s|/usr/local/sbin/maldet|/usr/bin/maldet|"

sed -i "files/internals/tlog" \
    -e "s|/usr/local/maldetect/tmp|/var/lib/maldet/tmp|"

EOF
) | runuser -u nobody sh || exit $?

cd "$WS/linux-malware-detect-*"
install -m 777 /dev/null /etc/maldet/hookscan.conf
install -D -m 755 "files/maldet" "/usr/bin/maldet"
install -D -m 755 "files/hookscan.sh" "/usr/bin/hookscan"
install -d "/usr/share/maldet"
cp -ar "files/"{clean,internals,VERSION,VERSION.hash} "/usr/share/maldet"
install -d "/var/lib/maldet/"{internals,quarantine,sess,sigs,clean,tmp,pub}
install -d "/var/log/maldet"
install -d "/etc/maldet"
install -m 644 "files/conf.maldet" "/etc/maldet/maldet.conf"
install -m 644 "files/conf.maldet.hookscan" "/etc/maldet/hookscan.conf"
install -m 644 "files/internals/internals.conf" "/etc/maldet/internals.conf"
install -m 644 "files/monitor_paths" "/etc/maldet/monitor_paths"
cp -ra "files/"ignore_* "/etc/maldet/"
install -d "/usr/share/man/man1/"
gzip -f9 "files/maldet.1"
install -D -m 644 "files/maldet.1.gz" "/usr/share/man/man1/maldet.1.gz"
'''

@tasks.append
def ensure_maldet_installed_and_up_to_date():
  if flags('offline'):
    return
  if maldet := which('maldet'):
    _, maldet_bin = read_config(maldet)
    current_version = re.search('ver=(.+)', maldet_bin).group(1)
    if current_version == LATEST_MALDET_VERSION:
      return
  subprocess.check_call(get_shell(), stdin = MALDET_SETUP_SCRIPT.encode())

@tasks.append
def ensure_passwords_are_setup():
  for user in (desired_username, 'root'):
    if subprocess.check_output(['passwd', '--status', user]).decode().split()[1] in ('NP','L'):
      if flags('interact'):
        print('\nSetting up password for', user)
        subprocess.run(['passwd', user])
      else:
        print(user + ' needs to have a password set')
        reasons_interactive_setup_needed.append('password for ' + user)

@tasks.append
def setup_rclone_and_maybe_prbsync():
  if flags('offline') or \
     not flags('interact') or \
     not which('rclone') or \
     is_parent_pc():
    return
  p, rclone_cfg = read_config(f'~{desired_username}/.config/rclone/rclone.conf',
                              default_contents='')
  if f'[{cloud_drive_name}]' not in rclone_cfg.splitlines():
    print('Setting up rclone...')
    subprocess.run(['runuser', '-u'+desired_username,
                    'rclone', 'config', 'create',
                    cloud_drive_name, cloud_drive_type])
  prbsync = which('prbsync')
  if not prbsync:
    remote_path = cloud_drive_name + ':' + prbsync_cloud_path
    tdir = tempfile.mkdtemp(prefix = 'prbsync_')
    shutil.chown(tdir, user = desired_username)
    tfile = os.path.join(tdir, 'prbsync')
    print('Created temp dir: ' + tdir)
    print('Downloading prbsync...')
    subprocess.check_call(('runuser', '-u'+desired_username,
                            which('rclone'), 'copy', remote_path, tdir))
    print('PRBSync has been downloaded to a temporary path')
    print('It can be found at: ' + tfile)
    print('Press ENTER to view its source for manual verification')
    input('[Press ENTER]')
    subprocess.check_call(('less', tfile))
    print('If the file is safe type YES to install')
    print('Type anything else to abort')
    inp = input('> ')
    if inp != 'YES':
      raise Exception('Aborting due to non-YES input')
    install_executable_if_missing(tfile, prbsync_install_path)
    print('PRBSync installed!')
    which.cache_clear()
    # TODO use rclone copy to install prbsync and replace w/ prbsync hydrate
    # if not os.path.exists(fixpath(local_cloud_drive_path)):
    #   subprocess.run(['runuser', '-u'+desired_username,
    #                   'mkdir', '-p', local_cloud_drive_path])
    #   subprocess.run(['runuser', '-u'+desired_username,
    #                   'rclone', 'bisync',
    #                   '--verbose', '--resync',
    #                   local_cloud_drive_path, cloud_drive_name+':'])

@tasks.append
def check_if_interactive_setup_needed():
  if is_arch_linux():
    packages_before_update_without_versions = set((shlex.split(i)[0] for i in packages_before_update))
    if any((package not in packages_before_update_without_versions
            for package in (i[0] for i in aur_packages))):
      reasons_interactive_setup_needed.append('missing aur package')
    if any((package not in packages_before_update_without_versions
            for package in aur_packages_installed_via_aur_helper)):
      reasons_interactive_setup_needed.append('missing aur helper package')
    if not os.path.isdir(fixpath(local_cloud_drive_path)):
      reasons_interactive_setup_needed.append('cloud drive path missing')

NO_EXECUTE_MASK = ~(stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

# See CVE-2020-23922, CVE-2021-3575, etc - see notes below
@tasks.append
def disable_risky_executables():
  for bin in ('gif2rgb', 'opj_compress', 'opj_decompress', 'opj_dump', 'heif-convert'):
    bin_path = which(bin)
    if bin_path:
      current_mode = os.stat(bin_path).st_mode
      desired_mode = current_mode & NO_EXECUTE_MASK
      if current_mode != desired_mode:
        os.chmod(bin_path, desired_mode)

# lincfg_path = shutil.which('lincfg') or default_lincfg_path
# p, lincfg = read_config(lincfg_path, default_contents='')
# sh = shutil.which('sh')
# expected_lincfg = '#!' + sh + "\n'" + sys.executable + "' '" + __file__ + "' $@\n"
# if lincfg != expected_lincfg:
#   if lincfg and \
#      (not lincfg.startswith(expected_lincfg.splitlines()[0]) or
#       len(lincfg.splitlines()) != len(expected_lincfg.splitlines())):
#     raise Exception('Unexpected lincfg. Another program may be using that name.', lincfg_path)
#   write_config(p, expected_lincfg)
#   subprocess.run(['chmod', '+x', p])

@tasks.append
def patch_rkhunter_to_use_https_for_updates():
  rkhunter = which('rkhunter')
  if not rkhunter:
    return
  p, rkhunter_script = read_config(rkhunter)
  if '#!/bin/sh' in rkhunter_script:
    write_config(p, rkhunter_script
                    .replace('#!/bin/sh', '#!/bin/bash')
                    .replace('https?', 'https')
                    .replace('http://', 'https://'))

  p, rkhunter_mirrors = read_config('/var/lib/rkhunter/db/mirrors.dat')
  if 'http:' in rkhunter_mirrors:
    write_config(p, rkhunter_mirrors.replace('http://', 'https://'))

rkhunter_dat_path = '/var/lib/rkhunter/db/rkhunter.dat'

@tasks.append
def configure_rkhunter_and_update_props_if_stale():
  rkhunter = which('rkhunter')
  if not rkhunter:
    return
  p, rkhunter_conf = read_config('/etc/rkhunter.conf')
  old, current, comment = make_config_version_vars(1, rkhunter_conf)
  if old < current:
    if old:
      restore_file_from_package('rkhunter', p)
      p, rkhunter_conf = read_config('/etc/rkhunter.conf')
    write_config(p, rkhunter_conf + '\n\n' + '\n'.join([
                    comment,
                    'IPC_SEG_SIZE=4541576',
                    'SCRIPTWHITELIST=/usr/bin/egrep',
                    'SCRIPTWHITELIST=/usr/bin/fgrep',
                    'SCRIPTWHITELIST=/usr/bin/ldd',
                    'ALLOWIPCPROC=/usr/bin/plasmashell',
                    'ALLOWIPCPROC=/usr/bin/systemsettings',
                    'ALLOWIPCPROC=/usr/lib/firefox/firefox',
                    'ALLOWIPCPROC=/usr/bin/kwin_x11', '']))
    os.remove(rkhunter_dat_path)

  if packages_before_update:
    packages_after_update = get_installed_packages()
    if packages_before_update != packages_after_update:
      os.remove(rkhunter_dat_path)

  if not os.path.exists(rkhunter_dat_path):
    out = subprocess.check_output((rkhunter, '--propupd'),
                                  stderr = subprocess.STDOUT)
    for line in out.decode().splitlines():
      if not line.startswith('grep: warning:'):
        print(line)

common_disabled_lynis_tests = [
  'FILE-6310', 'USB-1000', 'FILE-6310', 'FILE-6310',  'STRG-1846', 'NAME-4028', 'NAME-4404',
  'TOOL-5002', 'HRDN-7222', 'BANN-7126', 'FINT-4350', 'ACCT-9622', 'ACCT-9626', 'ACCT-9628',
  'AUTH-9286', 'AUTH-9286', 'AUTH-9262', 'AUTH-9282', 'LOGG-2130', 'HRDN-7220', 'PKGS-7320',
  'PKGS-7398', 'CRYP-7902', 'LOGG-2190', 'BOOT-5122', 'PKGS-7322', 'FIRE-4512', 'FIRE-4513',
  'BOOT-5264', 'KRNL-6000',
]

container_disabled_lynis_tests = [
  'KRNL-5830', 'LOGG-2138', 'LYNIS', 'BOOT-5264', 'BOOT-5104', 'NETW-3200', 'TIME-3104',
  'CRYP-8004', 'NETW-2706',
]

@tasks.append
def configure_lynis():
  if not which('lynis'):
    return
  p, lynis_profile = read_config('/etc/lynis/custom.prf', default_contents='')
  old, current, comment = make_config_version_vars(3, lynis_profile)
  if old < current:
    disabled_tests = common_disabled_lynis_tests
    if in_container():
      disabled_tests += container_disabled_lynis_tests
    p, defaults = read_config('/etc/lynis/default.prf')
    write_config(p, defaults
                    .replace(get_config_var(defaults, 'machine-role'), 'machine-role=personal') +
                    '\n\n' + comment +
                    '\n'.join(('skip-test='+i for i in disabled_tests)) + '\n')

user_downloads_dir = f'~{desired_username}/Downloads'
unscanned_downloads_dir = os.path.join(user_downloads_dir, 'Unscanned')
unscanned_downloads_subdirs = ('JDownloader', 'Firefox')
scanned_downloads_dir = os.path.join(user_downloads_dir, 'Scanned')
maldet_dirs_to_skip = ('/sys',)
maldet_scan_run_reasons = []

@tasks.append
def update_av_if_online_then_do_scans():
  if is_termux():
    return

  if not flags('offline') and which('freshclam'):
    subprocess.run(which('freshclam'))

  maldet = which('maldet') # From https://aur.archlinux.org/packages/maldet
  if maldet and not flags('offline'):
    subprocess.run([maldet, '--update-sigs'])

  if flags('scan'):
    if in_container():
      disabled_tests = ['possible_rkt_strings', 'startup_malware', 'system_configs_ssh',
                        'system_configs_syslog', 'os_specific']
    else:
      disabled_tests = []
    subprocess.run(shlex.split('rkhunter -c --sk') +
                              (['--disable', ','.join(disabled_tests)] if disabled_tests else []))

    subprocess.run(shlex.split('lynis audit system'))

    if maldet:
      for d in os.listdir('/'):
        if (p := os.path.join('/', d)) in maldet_dirs_to_skip:
          continue
        subprocess.run([maldet, '-a', p])
        maldet_scan_run_reasons.append('argument')
        check_maldet_log()

  makedirs(unscanned_downloads_dir, user = desired_username)

  if maldet and has_at_least_one_file(unscanned_downloads_dir):
    print('Beginning to scan downloads...')
    while True:
      tdir = fixpath(os.path.join(user_downloads_dir, 'being_scanned_' + os.urandom(5).hex()))
      try:
        os.mkdir(tdir)
        break
      except FileExistsError:
        continue
    print('Created temp dir:', tdir)
    for i in os.listdir(fixpath(unscanned_downloads_dir)):
      if i in unscanned_downloads_subdirs:
        continue
      shutil.move(os.path.join(fixpath(unscanned_downloads_dir), i),
                  os.path.join(tdir, i))
    for i in unscanned_downloads_subdirs:
      troot = fixpath(os.path.join(tdir, i))
      os.mkdir(troot)
      root = fixpath(os.path.join(unscanned_downloads_dir, i))
      for j in os.listdir(root):
        shutil.move(os.path.join(root, j), os.path.join(troot, j))
    while True:
      links_of_interest_by_exe = {}
      for i in filter(str.isdigit, os.listdir('/proc')):
        links = {}
        for i in ('exe', 'cwd', 'root'):
          try:
            links[i] = os.path.abspath(os.readlink(f'/proc/{i}/exe'))
          except FileNotFoundError:
            links[i] = '[None]'
        try:
          fds = os.listdir(f'/proc/{i}/fd')
        except FileNotFoundError:
          fds = []
        for j in fds:
          fd_path = f'fd/{j}'
          try:
            links[fd_path] = os.path.abspath(os.readlink(f'/proc/{i}/' + fd_path))
          except FileNotFoundError:
            links[fd_path] = '[None]'
        links_of_interest = {}
        for path, dest in links.items():
          if tdir in dest:
            links_of_interest[path] = dest
        if len(links_of_interest) > 0:
          links_of_interest_by_exe \
            .setdefault(links['exe'], {}) \
            .update(links_of_interest)
      if len(links_of_interest_by_exe) < 1:
        break
      alert(
        'Cannot safely scan downloads as some of the downloads are still open.',
        'Wait for the programs to close the files on their own or stop the',
        'affected programs:',
        pprint.pformat(links_of_interest_by_exe))

    print('Scanning downloads...')
    subprocess.check_call([maldet, '-a', tdir])
    maldet_scan_run_reasons.append('downloads')
    print('Scan complete. Moving scanned files.')
    makedirs(scanned_downloads_dir, user = desired_username)
    merge_move(tdir, scanned_downloads_dir)
    shutil.chown(fixpath(scanned_downloads_dir), desired_username)

  for i in unscanned_downloads_subdirs:
    makedirs(os.path.join(unscanned_downloads_dir, i),
             user = desired_username)

rat_message = 'Possible rootkit infection. See https://www.group-ib.com/blog/krasue-rat'
@tasks.append
def ensure_no_evidence_of_rat():
  running_pids = [int(i) for i in filter(str.isdigit, os.listdir('/proc'))]
  if 758 not in running_pids:
    try:
      os.kill(758, 64)
    except OSError as err:
      if abs(err.errno) == 0xBD:
        raise Exception(message)
  for pfx in ('auwd', 'vmware_helper'):
    tdir = tempfile.mkdtemp(prefix=pfx)
    if os.path.basename(tdir) not in os.listdir(os.path.dirname(tdir)):
      raise Exception(message, tdir)
    os.rmdir(tdir)

OWNER_CAN_RWX = 0o700
OWNER_CAN_RW  = 0o600
ANYONE_CAN_R  = 0o644
ANYONE_CAN_RX = 0o755

SYSTEM_SITE_PACKAGES = site.getsitepackages()[0]

common_locally_cached_projects = {
  'prbsync': {
    'sources': [local_cloud_drive_path + prbsync_cloud_path],
    'destination': prbsync_install_path,
    'mode': ANYONE_CAN_RX,
  },
  'diffcp': {
    'sources': [f'~{desired_username}/GDrive/Projects/PRBSync/diffcp.py'],
    'destination': f'$PREFIX/bin/diffcp',
    'mode': ANYONE_CAN_RX,
  },
  'simplemenu': {
    'sources': [f'~{desired_username}/GDrive/Projects/Linux/simplemenu.py'],
    'destination': f'~{desired_username}/.local/bin/simplemenu',
    'user': desired_username,
    'mode': OWNER_CAN_RWX,
  },
  'mission_control_lite_lib': {
    'sources': [
      f'~{desired_username}/GDrive/Projects/MissionControlLite/missioncontrollitelib.py'
    ],
    'destination':
      os.path.join(SYSTEM_SITE_PACKAGES, 'missioncontrollitelib.py'),
    'mode': ANYONE_CAN_RX,
  },
  'storage_minder_cleanup_script': {
    'sources': [
      f'~{desired_username}/OneDrive/Projects/StorageMinder/cleanup.sh'
    ],
    'destination': f'~root/.local/bin/storage_minder_cleanup',
    'mode': OWNER_CAN_RWX,
  },
}

common_personal_locally_cached_projects = {
  'sessen': {
    'cwd': f'~{desired_username}/OneDrive/Projects/Sessen',
    'source_patterns': ['*'],
    'symlink_patterns': ['*.db', '*.log', 'Extensions/Readyr',],
    'exclude_patterns': ['dev', 'Disabled Extensions', 'sandboxpy',
                         '*.md', '**.md', '*.bat',
                         '__pycache__', '**/__pycache__'],
    'destination': f'~{desired_username}/.local/share/sessen',
    'user': desired_username,
  },
  'sandboxpy': {
    'cwd': f'~{desired_username}/OneDrive/Projects/Sessen/sandboxpy',
    'source_patterns': ['*'],
    'destination': f'{SYSTEM_SITE_PACKAGES}/sandboxpy',
    'exclude_patterns': ['**.md', '__pycache__'],
    'recursive_mode': ANYONE_CAN_RX,
  },
  'upload_server': {
    'sources': [f'~{desired_username}/GDrive/Projects/Linux/upload_server.sh'],
    'destination': f'~{desired_username}/.local/bin/upload_server',
    'mode': OWNER_CAN_RWX,
    'user': desired_username,
  },
  'virtuator_lib': {
    'sources': [f'~{desired_username}/GDrive/Projects/Virtuator/virtuator.py'],
    'destination': f'{SYSTEM_SITE_PACKAGES}/virtuator.py',
    'mode': ANYONE_CAN_RX,
  },
  'virtuator_vmdefs': {
    'source_patterns': [
      f'~{desired_username}/GDrive/Projects/Virtuator/well_known_vmdefs/*'
    ],
    'destination': (
      f'~{desired_username}/.local/share/virtuator/well_known_vmdefs'
    ),
    'user': desired_username,
  },
  'mission_control_lite_client': {
    'sources': [
      f'~{desired_username}/GDrive/Projects/MissionControlLite/client.py'
    ],
    'destination': f'~{desired_username}/.local/bin/missioncontrollite-client',
    'user': desired_username,
    'mode': OWNER_CAN_RWX,
  },
  'do_all_the_things': {
    'sources': [
      f'~{desired_username}/GDrive/Projects/Linux/do_all_the_things.py'
    ],
    'destination': f'~{desired_username}/.local/bin/do_all_the_things',
    'user': desired_username,
    'mode': OWNER_CAN_RWX,
  }
}

desktop_locally_cached_projects = {
  'prbsync_kate_hook': {
    'sources': [
      f'~{desired_username}/GDrive/Projects/PRBSync/prbsync_mark_kate.ini'
    ],
    'destination':
      f'~{desired_username}/.config/kate/externaltools/' +
       'Mark%20File%20via%20PRBSync.ini',
    'user': desired_username,
  },
  'npp_on_kate_external_tools': {
    'cwd': f'~{desired_username}/OneDrive/Projects/NPP on Kate',
    'sources': ['conversion_panel.py', 'new_scratch.py', 'open_link.py'],
    'destination': f'~{desired_username}/.local/share/npp_on_kate',
    'user': desired_username,
  },
  'npp_on_kate_script': {
    'sources': [f'~{desired_username}/OneDrive/Projects/NPP on Kate/npp.js'],
    'destination':
      f'~{desired_username}/.local/share/katepart5/script/commands/npp.js',
    'user': desired_username,
  },
  'mission_control_lite_server': {
    'sources': [
      f'~{desired_username}/GDrive/Projects/MissionControlLite/server.py'
    ],
    'destination': '/srv/mclite/server',
    'mode': OWNER_CAN_RWX,
  },
  'mission_control_lite_helper': {
    'sources': [
      f'~{desired_username}/GDrive/Projects/MissionControlLite/helper.py'
    ],
    'destination': '/srv/mclite/helper',
    'mode': OWNER_CAN_RWX,
  },
  'mission_control_lite_repair': {
    'sources': [
      f'~{desired_username}/GDrive/Projects/MissionControlLite/repair.py'
    ],
    'destination': '/srv/mclite/repair',
    'mode': OWNER_CAN_RWX,
  },
  # 'prbsync_gui': {
  #   'sources': [f'~{desired_username}/GDrive/Projects/Linux/prbsync_gui'],
  #   'destination': f'~{desired_username}/.local/bin/gui_prbsync',
  #   'mode': OWNER_CAN_RWX,
  #   'user': desired_username,
  # },
  # 'prbsync_gui_shortcut': {
  #   'sources': [
  #     f'~{desired_username}/GDrive/Projects/Linux/prbsync_gui.desktop'
  #   ],
  #   'destination':
  #     f'~{desired_username}/.local/share/applications/prbsync_gui.desktop',
  #   'user': desired_username,
  # },
}

personal_desktop_locally_cached_projects = {
  'perfm': {
    'sources': [f'~{desired_username}/GDrive/Projects/PerfM/perfm.py'],
    'destination': f'~{desired_username}/.local/bin/perfm',
    'mode': OWNER_CAN_RWX,
    'user': desired_username,
  },
  'ptaskrunner': {
    'sources': [f'~{desired_username}/GDrive/Projects/PerfM/ptaskrunner.py'],
    'destination': '/usr/bin/ptaskrunner',
    'mode': ANYONE_CAN_RX,
  },
  'ptaskrunner_router': {
    'sources': [f'~{desired_username}/GDrive/Projects/PerfM/task_router.py'],
    'destination': ptaskrunner_router_path,
    'mode': OWNER_CAN_RWX,
  },
  'ptaskrunner_router_config': {
    'sources': [f'~{desired_username}/GDrive/Projects/PerfM/examples/task_router.toml'],
    'destination': f'~{desired_username}/.local/share/ptaskrunner/task_router.toml',
  },
  'ptaskrunner_ollama': {
    'sources': [f'~{desired_username}/GDrive/Projects/PerfM/examples/ollama.py'],
    'destination': f'~{desired_username}/.local/share/ptaskrunner/ollama.py',
    'mode': OWNER_CAN_RWX,
  },
  'results_logger': {
    'cwd': f'~{desired_username}/OneDrive/Projects/ResultsLogger',
    'sources': [
      'ResultsLogger.py', 'UpdatePublicLogs.py', 'PublishingRules.py',
      'Logs', 'PublicLogs',
    ],
    'destination': f'~{desired_username}/.local/share/results_logger',
    'symlink_patterns': ['Logs', 'PublicLogs'],
    'user': desired_username,
  },
  'game_release_checker': {
    'cwd': f'~{desired_username}/OneDrive/Projects/Game_Release_Checker',
    'sources': [
      'game_release_checker.sh', 'Game_Release_Checker.py', 'unreleased_games.txt',
      'early_access_games.txt', 'game_sites.txt', 'feeds.txt', 'news_sites.txt',
      'untrackable_games.txt', 'twitter_users.txt', 'data.json', 'settings.json',
    ],
    'destination': f'~{desired_username}/.local/share/game_release_checker',
    'symlink_patterns': ['*.txt', 'data.json'],
    'user': desired_username,
  },
  'price_checker': {
    'cwd': f'~{desired_username}/OneDrive/Projects/Game_Release_Checker',
    'sources': [
      'price_checker.py', 'price_checker.sh', 'price_history.csv',
      'price_checker_title_cache.txt', 'price_checker_release_date_cache.txt',
    ],
    'destination': f'~{desired_username}/.local/share/price_checker',
    'symlink_patterns': ['*.txt', '*.csv'],
    'user': desired_username,
  },
  'youtube_mix_scraper': {
    'cwd': f'~{desired_username}/OneDrive/Projects/YouTube Mix Scraper',
    'sources': [
      'YouTube_Mix_Scraper.py', 'YouTube Mix Scraper.sh', 'youtube_api_bridge.py',
      'ai_tracks.txt',
    ],
    'destination': f'~{desired_username}/.local/share/youtube_mix_scraper',
    'symlink_patterns': ['*.txt'],
    'user': desired_username,
  },
  'reflectivenas': {
    'cwd': f'~{desired_username}/OneDrive/Projects/ReflectiveNAS',
    'source_patterns': ['*'],
    'destination': f'~{desired_username}/.local/share/reflectivenas',
    'exclude_patterns': ['*.md', '*.db', '*.bat' '**.bat', '**/db',
                         'old', '**/r1', '**.r1', '**.r2', '**-r1.*',
                         '__pycache__', '**/__pycache__'],
    'user': desired_username,
  },
  'charonrmm': {
    'source_patterns': [f'~{desired_username}/GDrive/Projects/CharonRMM/*'],
    'destination': f'~{desired_username}/.local/share/charonrmm',
    'user': desired_username,
  },
  'healthcheck': {
    'source_patterns': [f'~{desired_username}/GDrive/Projects/Linux/healthcheck.py'],
    'destination': f'~{desired_username}/.local/bin/healthcheck',
    'user': desired_username,
    'mode': OWNER_CAN_RWX,
  },
  'git_mirror_sync': {
    'source_patterns': [f'~{desired_username}/GDrive/Projects/Linux/git_mirror_sync.py'],
    'destination': f'~{desired_username}/.local/bin/git_mirror_sync',
    'user': desired_username,
    'mode': OWNER_CAN_RWX,
  },
  'persistent_tmux': {
    'source_patterns': [f'~{desired_username}/GDrive/Projects/Linux/persistent_tmux.py'],
    'destination': f'/root/.local/bin/persistent_tmux',
    'mode': OWNER_CAN_RWX,
  },
}

# TODO interactively build mclite, copy cert and setup config
# TODO mclite client on termux and others?

arch_linux_locally_cached_projects = {
  'auto_tpm_encrypt': {
    'sources': [f'~{desired_username}/GDrive/Projects/Lockdown/AutoTpmEncrypt/auto_tpm_encrypt.py'],
    'destination': '~root/.local/bin/auto_tpm_encrypt',
    'mode': OWNER_CAN_RWX,
  },
  'boot_windows': {
    'sources': [f'~{desired_username}/GDrive/Projects/Lockdown/Windows/boot_windows.py'],
    'destination': '~root/.local/bin/boot_windows',
    'mode': OWNER_CAN_RWX,
  },
  'boot_windows_gui': {
    'sources': [f'~{desired_username}/GDrive/Projects/Lockdown/Windows/boot_windows_gui.sh'],
    'destination': f'~{desired_username}/.local/bin/boot_windows_gui',
    'mode': OWNER_CAN_RWX,
    'user': desired_username,
  },
  'boot_windows_gui_shortcut': {
    'sources': [
      f'~{desired_username}/GDrive/Projects/Lockdown/Windows/boot_windows_gui.desktop'
    ],
    'destination':
      f'~{desired_username}/.local/share/applications/boot_windows_gui.desktop',
    'user': desired_username,
  },
  'steamrollr': {
    'sources': [
      f'~{desired_username}/GDrive/Projects/MissionControlLite/steamrollr.py'
    ],
    'destination': '/usr/bin/steamrollr',
    'mode': ANYONE_CAN_RX,
  },
  'gamepadify_lib': {
    'cwd': f'~{desired_username}/GDrive/Projects/Gamepadify/src',
    'source_patterns': ['*'],
    'destination': os.path.join(SYSTEM_SITE_PACKAGES, 'gamepadify'),
  },
  'gamepadify_config': {
    'sources': [f'~{desired_username}/GDrive/Projects/Gamepadify/mygamepad'],
    'destination': f'~root/.local/bin/mygamepad',
    'mode': OWNER_CAN_RWX,
  },
  'lincfg_bundle_script': {
    'sources': [f'~{desired_username}/.local/share/lincfg/make_bundle.sh'],
    'destination': '~/.local/share/lincfg/make_bundle.sh',
  },
}

def diffcp_copy(name, destination, **kwargs):
  sources = [fixpath(s) for s in kwargs.get('sources', [])]
  if cwd := kwargs.get('cwd'):
    cwd = fixpath(cwd)
  for pattern in kwargs.get('source_patterns', []):
    sources += glob.glob(fixpath(pattern), root_dir = cwd)
  user = kwargs.get('user')
  if len(sources) > 1:
    makedirs(destination, user = user)
  else:
    makedirs(os.path.dirname(destination), user = user)
  cmd = [which('diffcp'), '-r', '--ternary-return-code'] + \
        sources + [fixpath(destination)]
  for pattern in kwargs.get('symlink_patterns', []):
    cmd += ['--symlink-pattern', pattern]
  for pattern in kwargs.get('exclude_patterns', []):
    cmd += ['--exclude-pattern', pattern]
  if user:
    cmd = ['runuser', '-u'+user, '--'] + cmd
  if not flags('interact'):
    cmd += ['--fail-if-different']
  proc = subprocess.run(cmd, cwd = cwd)
  if proc.returncode == 0:
    if (mode := kwargs.get('mode')) is not None:
      os.chmod(fixpath(destination), mode)
    elif (mode := kwargs.get('recursive_mode')) is not None:
      for root, dirs, files in os.walk(fixpath(destination)):
        for i in files:
          os.chmod(os.path.join(root, i), mode)
  elif proc.returncode != 2:
    if not flags('interact'):
      reasons_interactive_setup_needed.append(f'diffcp: {name}')
    else:
      proc.check_returncode()
  return proc.returncode

@tasks.append
def cache_projects_via_diffcp():
  if not (diffcp := which('diffcp')):
    return
  projects = dict(common_locally_cached_projects)
  if not is_parent_pc():
    projects |= common_personal_locally_cached_projects
  if is_arch_linux() or is_postmarketos():
    projects |= desktop_locally_cached_projects
    if not is_parent_pc():
      projects |= personal_desktop_locally_cached_projects
  if is_arch_linux():
    projects |= arch_linux_locally_cached_projects
  for project_name, project in projects.items():
    kwargs = project.copy()
    destination = kwargs.pop('destination')
    diffcp_copy(project_name, destination, **kwargs)

luks_partition_mount_root = '/srv'

pool_mount_point = '/srv/pool'



steam_library_dir_name = 'SteamLibrary'

luks_partitions_shared_with_steam = set(luks_partitions.values())

bottles_drive_folder_prefix = 'BottlesDrive'

luks_partitions_shared_with_bottles = {
  # 'T': 'Tertiary',
  # 'Q': 'Quaternary',
  # 'U': 'Quinary',
}

drives_mapped_to_each_bottle = {
  # 'Secondary': ('T', 'Q', 'U',),
  # 'Tertiary': ('T', 'Q', 'U',),
}

bottles_bottles_path = f'~{desired_username}/.var/app/com.usebottles.bottles/data/bottles/bottles'

@tasks.append
def map_drives_to_each_bottle():
  for bottle_name, drives in drives_mapped_to_each_bottle.items():
    devdir = fixpath(
      os.path.join(bottles_bottles_path, bottle_name, 'dosdevices')
    )
    if not os.path.isdir(devdir):
      continue
    for drive in drives:
      drive_path = os.path.join(devdir, drive.lower()+':')
      try:
        current_target = os.readlink(drive_path)
      except FileNotFoundError:
        current_target = None
      desired_target = os.path.join(
        luks_partition_mount_root,
        luks_partitions_shared_with_bottles[drive],
        bottles_drive_folder_prefix + drive,
      )
      if current_target != desired_target:
        os.symlink(desired_target, drive_path)

@tasks.append
def ensure_dirs_shared_with_flatpaks_exist():
  if len(set(luks_partitions.values())) != len(luks_partitions):
    raise Exception(f'Unexpected duplicate partition names: {luks_partitions}')
  for name in luks_partitions_shared_with_steam:
    root = os.path.join(luks_partition_mount_root, name)
    if not os.path.ismount(root):
      continue
    makedirs(os.path.join(root, steam_library_dir_name),
             user = desired_username)
  for drive_letter, name in luks_partitions_shared_with_bottles.items():
    root = os.path.join(luks_partition_mount_root, name)
    if not os.path.ismount(root):
      continue
    makedirs(os.path.join(root, bottles_drive_folder_prefix + drive_letter),
             user = desired_username)

potentially_missing_flatpak_dirs = [
  '/var/lib/flatpak/repo/refs/remotes',
  '/var/lib/flatpak/repo/refs/heads',
]

@tasks.append
def fix_potentially_missing_flatpak_dirs():
  if not is_postmarketos():
    return
  for d in potentially_missing_flatpak_dirs:
    makedirs(d)

default_flatpak_lib_path = '/usr/lib/flatpak'
alt_flatpak_lib_path = '/usr/libexec'
flatpak_service_path_template = '/usr/lib/systemd/user/{}.service'
flatpak_services_potentially_in_alt_lib_path = ('flatpak-portal', 'flatpak-session-helper')

@tasks.append
def fix_flatpak_services_to_use_alt_lib_path_if_nessicary():
  reload_due = False
  for i in flatpak_services_potentially_in_alt_lib_path:
    default_path = os.path.join(default_flatpak_lib_path, i)
    alt_path = os.path.join(alt_flatpak_lib_path, i)
    service_path = flatpak_service_path_template.format(i)
    p, service = read_config(service_path, default_contents = '')
    if default_path in service and \
       not os.path.exists(default_path) and \
       os.path.exists(alt_path):
      write_config(p, service.replace(default_path, alt_path))
      reload_due = True
  if reload_due:
    subprocess.check_call(('systemctl', 'daemon-reload'))

common_desired_flatpaks = {
  'io.github.webcamoid.Webcamoid', 'org.videolan.VLC', 'io.github.peazip.PeaZip',
}

personal_desired_flatpaks = {
  'org.audacityteam.Audacity',  'com.rustdesk.RustDesk', 'io.github.streetpea.Chiaki4deck',
}

arch_linux_desired_flatpaks = {
  'org.mozilla.firefox', 'com.valvesoftware.Steam',
  'org.torproject.torbrowser-launcher',
}

default_flatpak_exceptions = {
  'sockets': {'wayland', 'pulseaudio'},
}

common_browser_permissions = {
  'shared': {'network'},
  'sockets': {'pulseaudio', 'pcsc', 'cups'},
  'devices': {'all'},
  'filesystems': {
    '/run/.heim_org.h5l.kcm-socket',
    '/run/udev:ro',
  },
  'session_bus_policy': {
    'org.freedesktop.Notifications': 'talk',
    # 'org.kde.kwalletd5': 'talk',
    'org.freedesktop.FileManager1': 'talk',
    'org.freedesktop.secrets': 'talk',
    'org.freedesktop.ScreenSaver': 'talk',
    'com.canonical.AppMenu.Registrar': 'talk',
    'org.gnome.SessionManager': 'talk',
  },
}

flatpak_exceptions = {
  'com.anydesk.Anydesk': {
    'shared': {'network'},
    'sockets': {'x11'},
  },
  'com.rustdesk.RustDesk': {
    'shared': {'network'},
  },
  'org.remmina.Remmina': {
    'shared': {'network'},
  },
  'org.mozilla.firefox': common_browser_permissions | {
    'persistent': {'.mozilla'},
    'features': {'devel'},
    'filesystems': common_browser_permissions['filesystems'] |
                   {'xdg-run/speech-dispatcher:ro',
                    os.path.join(unscanned_downloads_dir, 'Firefox')},
    'session_bus_policy': common_browser_permissions['session_bus_policy'] | {
      'org.mozilla.firefox_beta.*': 'own',
      'org.mozilla.firefox.*': 'own',
      'org.mpris.MediaPlayer2.firefox.*': 'own',
      'org.a11y.Bus': 'talk',
    },
    'system_bus_policy': {
      'org.freedesktop.NetworkManager': 'talk',
    },
  },
  'org.torproject.torbrowser-launcher': common_browser_permissions | {
    'persistent': {'.mozilla'},
    'features': {'devel'},
    'filesystems': common_browser_permissions['filesystems'] |
                   {'xdg-run/speech-dispatcher:ro'},
    'session_bus_policy': common_browser_permissions['session_bus_policy'] | {
      'org.mozilla.firefox_beta.*': 'own',
      'org.mozilla.firefox.*': 'own',
      'org.mpris.MediaPlayer2.firefox.*': 'own',
      'org.a11y.Bus': 'talk',
    },
    'system_bus_policy': {
      'org.freedesktop.NetworkManager': 'talk',
    },
  },
  'com.usebottles.bottles': {
    'shared': {'network'},
    'sockets': {'x11', 'pulseaudio'},
    'devices': {'all'},
    'features': {'devel', 'per-app-dev-shm', 'multiarch'},
    'filesystems': {
      f'{pool_mount_point}/BottlesDriveP',
      f'~{desired_username}/GDrive/Documents/Saves/Symlinked/Bottles',
    },
  },
  'com.valvesoftware.Steam': {
    'shared': {'network'},
    'sockets': {'x11', 'pulseaudio'},
    'devices': {'dri', 'input',}, #{'all',},
    'persistent': {'.'},
    'features': {'devel', 'per-app-dev-shm', 'multiarch', 'bluetooth'},
    'filesystems': {
      'xdg-run/app/com.discordapp.Discord:create',
      'xdg-pictures:ro',
      'xdg-music:ro',
      f'{pool_mount_point}/SteamLibrary',
      f'~{desired_username}/GDrive/Documents/Saves/Symlinked/Steam',
    },
    'session_bus_policy': {
      'com.steampowered.*': 'own',
      'org.kde.StatusNotifierWatcher': 'talk',
      'org.freedesktop.Notifications': 'talk',
      'org.gnome.SettingsDaemon.MediaKeys': 'talk',
      'org.freedesktop.ScreenSaver': 'talk',
      'org.freedesktop.PowerManagement': 'talk',
    },
    'system_bus_policy': {
      'org.freedesktop.UPower': 'talk',
    },
  },
  'io.github.webcamoid.Webcamoid': {
    'sockets': {'pulseaudio'},
    'devices': {'all'},
    'filesystems': {'xdg-pictures', 'xdg-videos', 'xdg-config/kdeglobals:ro'},
    'session_bus_policy': {
      'com.canonical.AppMenu.Registrar': 'talk',
      'org.kde.kconfig.notify': 'talk',
    }
  },
  'org.audacityteam.Audacity': {
    'sockets': {'x11', 'pulseaudio'},
    'filesystems': {'xdg-run/pipewire-0'},
    'session_bus_policy': {
      'com.canonical.AppMenu.Registrar': 'talk',
      'org.kde.kconfig.notify': 'talk',
    }
  },
  'org.gimp.GIMP': {
    'sockets': {'x11'},
    'filesystems': {'xdg-config/GIMP', 'xdg-config/gtk-3.0'},
    'session_bus_policy': {
      'org.freedesktop.FileManager1': 'talk',
    }
  },
  'org.videolan.VLC': {
    'shared': {'network'},
    'sockets': {'x11'},
    'devices': {'dri'},
    'session_bus_policy': {
      'org.freedesktop.ScreenSaver': 'talk',
      'org.mpris.MediaPlayer2.vlc': 'own',
      'org.kde.StatusNotifierWatcher': 'talk',
      'com.canonical.AppMenu.Registrar': 'talk',
      'org.kde.kconfig.notify': 'talk',
      'org.mpris.MediaPlayer2.Player': 'talk',
    },
  },
  'org.filezillaproject.Filezilla': {
    'shared': {'network'},
  },
  'org.jdownloader.JDownloader': {
    'shared': {'network'},
    'sockets': {'x11'},
  },
  'io.mrarm.mcpelauncher': {
    'shared': {'network'},
    'devices': {'dri'},
  },
  'org.libreoffice.LibreOffice': {
    'sockets': {'x11'},
    'filesystems': {'xdg-config/fontconfig:ro', 'xdg-config/gtk-3.0'},
    'session_bus_policy': {
      'com.canonical.AppMenu.Registrar': 'talk',
      'org.libreoffice.LibreOfficeIpc0': 'own',
    }
  },
  'com.github.k4zmu2a.spacecadetpinball': {
    #'sockets': {'pulseaudio'},
  },
  'io.github.ungoogled_software.ungoogled_chromium': common_browser_permissions | {
    'persistent': {'.pki'},
    'session_bus_policy': common_browser_permissions['session_bus_policy'] | {
      'org.mpris.MediaPlayer2.chromium.*': 'own',
    },
  },
  'com.microsoft.Edge': common_browser_permissions | {
    'persistent': {'.pki'},
    'session_bus_policy': common_browser_permissions['session_bus_policy'] | {
      'org.mpris.MediaPlayer2.edge.*': 'own',
    },
    'filesystems': common_browser_permissions['filesystems'] | {
      'xdg-run/pipewire-0',
    },
  },
  'dev.stewlab.PortaWar': {
    'sockets': {'x11', 'pulseaudio'},
  },
  'io.github.peazip.PeaZip': {
    'sockets': {'x11'},
  },
  'org.gnome.Boxes': {
    'shared': {'network'},
    'devices': {'all'},
  },
  'org.DolphinEmu.dolphin-emu': {
    'sockets': {'x11'},
    'devices': {'all'},
  },
  'io.sourceforge.pysolfc.PySolFC': {
    'persistent': {'.PySolFC'},
    'sockets': {'x11'},
  },
  'gg.tesseract.Tesseract': {
    'persistent': {'.tesseract'},
    'devices': {'all'},
  },
  'net.redeclipse.RedEclipse': {
    'persistent': {'.redeclipse'},
    'devices': {'dri',},
  },
  'org.bzflag.BZFlag': {
    'persistent': {'.bzf'},
  },
  'org.speed_dreams.SpeedDreams': {
    'persistent': {'.speed-dreams-2'},
    'device': {'dri'},
  },
  'tw.ddnet.ddnet': {
    'persistent': {'.teeworlds'},
  },
  'net.sourceforge.mars-game': {
    'persistent': {'.marsshooter'},
    'sockets': {'x11'},
  },
  'org.neverball.Neverball': {
    'persistent': {'.neverball'},
  },
  'org.luanti.luanti': {
    'sockets': {'x11'},
    'shared': {'network'},
  },
  'org.gnome.NetworkDisplays': {
    'shared': {'network'},
    'devices': {'dri'},
    'system_bus_policy': {
      'org.freedesktop.NetworkManager': 'talk',
      'org.freedesktop.Avahi': 'talk',
    },
  },
  'com.viewizard.AstroMenace': {
    'devices': {'dri'},
  },
  'io.sourceforge.trigger_rally.TriggerRally': {
    'devices': {'dri'},
    'sockets': {'x11'},
  },
  'io.itch.amcsquad.amcsquad': {
    'sockets': {'x11', 'pulseaudio'},
  },
  'net.pioneerspacesim.Pioneer': {
    'persistent': {'.pioneer'},
    'devices': {'dri'},
    'sockets': {'x11'},
  },
  'org.libretro.RetroArch': {
    'devices': {'dri'},
    'shared': {'network'},
  },
  'org.ryujinx.Ryujinx':  {
    'devices': {'dri'},
    'sockets': {'x11'},
  },
  'io.mgba.mGBA': {
    'devices': {'dri', 'input'},
  },
  'io.github.unknownskl.greenlight': {
    'devices': {'all'},
    'sockets': {'x11'},
    'shared': {'network'},
    'filesystems': {'/run/udev:ro',},
  },
  'io.github.streetpea.Chiaki4deck': {
    'devices': {'dri', 'input'},
    'filesystems': {'xdg-run/pipewire-0'},
    'shared': {'network'},
    'session_bus_policy': {
      'org.freedesktop.ScreenSaver': 'talk',
    },
    'system_bus_policy': {
      'org.freedesktop.login1': 'talk',
    },
  },
  'org.mozilla.Thunderbird': {
    'shared': {'network'},
    'persistent': {'.thunderbird'},
  },
  'com.github.PintaProject.Pinta': {},
  'org.kde.kdenlive': {
    'devices': {'all'},
  },
}

def get_desired_flatpaks():
  desired_flatpaks = common_desired_flatpaks
  if not is_parent_pc():
    desired_flatpaks.update(personal_desired_flatpaks)
  if is_arch_linux():
    desired_flatpaks.update(arch_linux_desired_flatpaks)
  return desired_flatpaks

@tasks.append
def update_flatpaks_and_fix_permissions():
  if in_container() or is_termux():
    return

  installed_flatpaks = get_installed_flatpaks()

  if not flags('offline'):
    for flatpak in (get_desired_flatpaks() - installed_flatpaks):
      subprocess.run(['flatpak', 'install', '--noninteractive', flatpak])
    subprocess.check_call(['flatpak', 'update', '--assumeyes'])
    installed_flatpaks = get_installed_flatpaks()

  # NB: revokes overly permissive default permissions
  #     won't touch user assigned overrides
  # removes all potentially dangerous permissions unless they're in flatpak_exceptions
  # this applies to all flatpaks including user installed ones, not just those
  # in desired_flatpaks
  noperm2arg = {
    'shared': 'unshare', 'sockets': 'nosocket', 'devices': 'nodevice',
    'filesystems': 'nofilesystem', 'persistent': None,
    'features': 'disallow',
  }
  perm2arg = {
    'shared': 'share', 'sockets': 'socket', 'devices': 'device',
    'filesystems': 'filesystem',
  }
  bus_perm2arg = {
    ('Session', 'talk', None): 'no-talk-name',
    ('Session', 'own',  None): 'no-talk-name',
    ('System',  'talk', None): 'system-no-talk-name',
    ('System',  'own',  None): 'system-no-talk-name',
  }
  flatpak_runtimes = set(subprocess.check_output(
    ['flatpak', 'list', '--app', '--columns=runtime']).decode().splitlines())

  for flatpak in sorted(installed_flatpaks - flatpak_runtimes):
    if flags('fpoverrides') and '/' not in flatpak:
      subprocess.run(['flatpak', 'override', '--reset', flatpak])

    perms = subprocess.check_output(
            ['flatpak', 'info', '--show-permissions', flatpak]).decode()
    remove_args, add_args = [], []
    remove_map = {}
    for line in perms.splitlines():
      if not line:
        continue
      if line.startswith('[') and line.endswith(']'):
        current_section = line[1:-1]
        continue
      idx = line.index('=')
      k,v = line[:idx], set(filter(None, line[idx+1:].split(';')))
      if current_section == 'Context' and k in noperm2arg:
        to_remove = (v
                      - set(map(fixpath,
                                flatpak_exceptions
                                  .get(flatpak, {})
                                  .get(k, set())))
                      - default_flatpak_exceptions.get(k, set()))
        to_remove = {i[:i.rfind(':')] if i[i.rfind(':')+1:] in ('ro', 'create') and
                    noperm2arg[k] == 'nofilesystem'
                    else i for i in to_remove}
        if len(to_remove) > 0 and noperm2arg[k] is None:
          print('Unable to remove ' + line + ' for ' + flatpak + '\n' +
                'Either add an exception for the path or uninstall the flatpak.\n' +
                'See https://github.com/flatpak/flatpak/issues/5042')
          sys.exit(-1)
        remove_args += ['--'+noperm2arg[k]+'='+i for i in to_remove]
        remove_map.setdefault(k, set()).update(to_remove)
      elif current_section.endswith('Bus Policy'):
        v = tuple(v)[0] if len(v) == 1 else v
        sk = current_section[:-11].lower()+'_bus_policy'
        want = (flatpak_exceptions
                .get(flatpak, {})
                .get(sk, {})
                .get(k))
        if v != want:
          remove_args += ['--' + bus_perm2arg[current_section[:-11], v, want] + '=' + k]
          remove_map.setdefault(sk, set()).add(k)
      elif current_section == 'Environment':
        pass
      elif current_section == 'Context' and k in {'unset-environment'}:
        pass
      else:
        raise Exception('Unknown entry', current_section, k)
    for k, v in flatpak_exceptions.get(flatpak, {}).items():
        v = set(v.keys())if type(v) is dict else v
        to_add = v - remove_map.get(k, set())
        if len(to_add) > 0 and k in perm2arg:
          add_args += [
            '--'+perm2arg[k]+'='+(fixpath(i) if k == 'filesystems' else i)
            for i in to_add
          ]
    if len(remove_args) > 0 and '/' not in flatpak:
      cmd = ['flatpak', 'override'] + remove_args + add_args + [flatpak]
      print('Running:', shlex.join(cmd))
      subprocess.check_call(cmd)

CHROMIUM_FLAGS = """
--enable-features=UseOzonePlatform
--ozone-platform=wayland
"""

CHROMIUM_FLAG_PATHS = [
  f'~{desired_username}/.var/app/io.github.ungoogled_software.ungoogled_chromium/config/chromium-flags.conf',
  f'~{desired_username}/.var/app/com.microsoft.Edge/config/edge-flags.conf',
]

@tasks.append
def set_chromium_wayland_flags():
  for path in map(fixpath, CHROMIUM_FLAG_PATHS):
    try:
      write_config(path,
                   CHROMIUM_FLAGS.lstrip(),
                   mode = 'x',
                   user = desired_username)
    except (FileNotFoundError, FileExistsError):
      pass

pwa_shortcuts = {

f'~{desired_username}/.local/share/applications/GeForceNow.desktop': f'''
[Desktop Entry]
Type=Application
Version=1.0
Name=GeForce Now
GenericName=Cloud Gaming
Comment=Cloud Gaming
Icon=~{desired_username}/.var/app/io.github.ungoogled_software.ungoogled_chromium/config/chromium/Default/Web Applications/Manifest Resources/egmafekfmcnknbdlbfbhafbllplmjlhn/Icons/512.png
Exec=/usr/bin/flatpak run --branch=stable --command=/app/bin/chromium --file-forwarding io.github.ungoogled_software.ungoogled_chromium --app-id=egmafekfmcnknbdlbfbhafbllplmjlhn
Categories=Game;Network;
Keywords=cloud;game;gaming;nvidia;stream;steaming;steam;epic;ubisoft;
'''.lstrip(),

f'~{desired_username}/.local/share/applications/XboxCloudGaming.desktop': f'''
[Desktop Entry]
Type=Application
Version=1.0
Name=Xbox Cloud Gaming
GenericName=Cloud Gaming
Comment=Cloud Gaming
Icon=~{desired_username}/.var/app/io.github.ungoogled_software.ungoogled_chromium/config/chromium/Default/Web Applications/Manifest Resources/chcecgcbjkilfgeccdhoeaillkophnhg/Icons/512.png
Exec=/usr/bin/flatpak run --branch=stable --command=/app/bin/chromium --file-forwarding io.github.ungoogled_software.ungoogled_chromium --app-id=chcecgcbjkilfgeccdhoeaillkophnhg
Categories=Game;Network;
Keywords=cloud;game;gaming;nvidia;stream;steaming;steam;epic;ubisoft;
'''.lstrip(),

}

@tasks.append
def create_pwa_shortcuts_for_installed_pwas():
  for shortcut_path, desired_shortcut in pwa_shortcuts.items():
    original_icon_path = re.search(r'Icon=(.+)', desired_shortcut).group(1)
    icon_path = fixpath(original_icon_path)
    desired_shortcut = desired_shortcut.replace(original_icon_path, icon_path)
    p, shortcut = read_config(shortcut_path, default_contents = '')
    if os.path.exists(icon_path) and shortcut != desired_shortcut:
      write_config(p, desired_shortcut, user = desired_username)
    elif not os.path.exists(icon_path) and shortcut:
      os.remove(shortcut_path)

firefox_shortcut_path = '/usr/share/applications/firefox.desktop'

@tasks.append
def fix_firefox_file_picker():
  firefox_path = which('firefox')
  if not firefox_path:
    return
  _, firefox_bin = read_config(firefox_path)
  match = re.search(r'exec (.+?) ', firefox_bin)
  if match:
    firefox_path = match.group(1).strip()
  _, firefox_shortcut = read_config(firefox_shortcut_path)
  desired_shortcut = firefox_shortcut.replace(
    'Exec='+firefox_path,
    'Exec=env GTK_USE_PORTAL=1 '+firefox_path,
  )
  if firefox_shortcut != desired_shortcut:
    write_config(firefox_shortcut_path, desired_shortcut)

wasmer_script_path = f'~{desired_username}/.local/bin/wcontainer'
desired_wasmer_script = '''
#!/bin/sh
# Packages and args on standby:
#  --use jedisct1/minisign \
#  --use syrusakbary/cowsay \
#  --use syrusakbary/viu \
#  --use sharrattj/static-web-server \
#  --use sharrattj/wasmer-sh \
#  --use syrusakbary/figlet \
#  --use wasmer-examples/tantivy-cli-example \
#  --use hazeycode/escape-guldur \
#  --use willguimont/dashy-dango \
#  --use php/php \
#  --use wasmer/phpmyadmin \
#  --use syrusakbary/nginx \
#  --use drbh/flate \
# --use syrusakbary/lua \
#  --use fschuett/zig \
#  --use pancake/r2 \
#  --use wasmer/ffmpeg \
#  --mapdir /root/scratch::/root/scratch \

exec wasmer run \
  --net=ipv4:deny=*:*,ipv6:deny=*:*,dns:deny=*:* \
  --use python/python \
  --use clang/clang \
  --use syrusakbary/util-linux \
  --use sharrattj/coreutils \
  --use wasmer/wabt \
  --use syrusakbary/jq \
  --use curl/curl \
  --use syrusakbary/qr2text \
  sharrattj/bash "$@"
'''.lstrip()

@tasks.append
def ensure_wasmer_script_updated():
  if not which('wasmer'):
    return
  p, wasmer_script = read_config(wasmer_script_path, default_contents = '')
  if wasmer_script != desired_wasmer_script:
    write_config(p, desired_wasmer_script, user = desired_username)
    os.chmod(p, OWNER_CAN_RWX)

@tasks.append
def make_virtuator_symlink():
  project_name = 'virtuator_lib'
  project = common_personal_locally_cached_projects[project_name]
  target = project['destination']
  if not os.path.exists(target):
    return
  symlink_path = os.path.join('/usr/bin',
                              os.path.splitext(os.path.basename(target))[0])
  if not os.path.exists(symlink_path):
    os.symlink(target, symlink_path)

services = {}
disabled_services = set()

luks_partition_script_path = '~/.local/bin/consolidated_startup_script'
luks_key_path = '/etc/LUKS'

luks_partition_service_template = '''
[Unit]
Description=Consolidated Startup Script
After=multi-user.target
Wants=multi-user.target

[Service]
Type=simple
ExecStart=_SCRIPT

[Install]
WantedBy=default.target
'''.lstrip()

luks_uuids = {v:k for k,v in luks_partitions.items()}

desired_luks_partition_script = f'''
#!/bin/sh
cryptsetup open /dev/disk/by-partuuid/{luks_uuids['Tertiary']} Tertiary --key-file /etc/LUKS/Tertiary.key --perf-no_read_workqueue
cryptsetup open /dev/disk/by-partuuid/{luks_uuids['Quaternary']} Quaternary --key-file /etc/LUKS/Quaternary.key --perf-no_read_workqueue
cryptsetup open /dev/disk/by-partuuid/{luks_uuids['Quinary']} Quinary --key-file /etc/LUKS/Quinary.key --perf-no_read_workqueue
mount /dev/mapper/Tertiary {pool_mount_point}
runuser -u{desired_username} -- prbsync auto_sync
systemctl start Sessen
'''.strip()

@lambda f: services.setdefault('ConsolidatedStartupScript', f)
def get_desired_luks_partition_service():
  if not os.path.exists(pool_mount_point):
    return
  p, script = read_config(luks_partition_script_path, default_contents = '')
  if script != desired_luks_partition_script:
    write_config(p, desired_luks_partition_script)
    os.chmod(p, OWNER_CAN_RWX)
  return luks_partition_service_template.replace('_SCRIPT', p)

sessen_service_template = '''
[Unit]
Description=Sessen
After=multi-user.target
Wants=multi-user.target
StartLimitBurst=100

[Service]
Type=simple
User=_USER
ExecStart=_SCRIPT
KillSignal=SIGINT

[Install]
WantedBy=display-manager.service
'''.lstrip()

disabled_services.add('Sessen')

@lambda f: services.setdefault('Sessen', f)
def get_desired_sessen_service():
  if not is_arch_linux():
    return None
  project = common_personal_locally_cached_projects['sessen']
  root = fixpath(project['destination'])
  script = os.path.join(root, 'Sessen.sh')
  try:
    os.chmod(script, OWNER_CAN_RWX)
  except (AttributeError, FileNotFoundError):
    return None
  return (
    sessen_service_template
      .replace('_USER', desired_username)
      .replace('_SCRIPT', script)
  )

mclite_daemon_path = '/bin/missioncontrollited'
mclite_delay = 25
mclite_timeout = 60
mclite_service_template = '''
[Unit]
Description=Mission Control Lite Daemon
After=multi-user.target
Wants=multi-user.target
StartLimitIntervalSec=20
StartLimitBurst=5

[Service]
Type=simple
ExecStart=_DAEMON _DELAY _TIMEOUT _CERT _WAKER _SERVER _REPAIR
Restart=always
RestartSec=_TIMEOUT

[Install]
WantedBy=default.target
'''.lstrip()

@lambda f: services.setdefault('MissionControlLite', f)
def get_desired_mclite_service():
  if not os.path.isfile(fixpath(mclite_daemon_path)):
    return None
  code = ('import json,missioncontrollitelib as mclib;' +
          'print(json.dumps((mclib.get_config(), mclib.get_cert_path())))')
  lib = common_locally_cached_projects['mission_control_lite_lib']
  libdir = os.path.dirname(lib['destination'])
  out = subprocess.check_output((sys.executable, '-B', '-c', code),
                                cwd = libdir)
  config, cert = json.loads(out)
  if not (waker_url := config.get('waker_url')):
    waker_url = config['mcbus_url']
    if not waker_url.endswith('/'):
      waker_url += '/'
    waker_url += ('?name=' +
                  config['devices'][config['this_device']]['waker_name'])
  server = desktop_locally_cached_projects['mission_control_lite_server']
  server = server['destination']
  repair = desktop_locally_cached_projects['mission_control_lite_repair']
  repair = repair['destination']
  return (
    mclite_service_template
      .replace('_DAEMON', fixpath(mclite_daemon_path))
      .replace('_DELAY', str(round(mclite_delay)))
      .replace('_TIMEOUT', str(round(mclite_timeout)))
      .replace('_CERT', cert)
      .replace('_WAKER', waker_url)
      .replace('_SERVER', fixpath(server))
      .replace('_REPAIR', fixpath(repair))
  )

gamepadify_service_template = '''
[Unit]
Description=Gamepadify Controller Script

[Service]
Type=simple
ExecStart=_START
Restart=on-failure
'''.lstrip()

disabled_services.add('Gamepadify')

@lambda f: services.setdefault('Gamepadify', f)
def get_desired_gamepadify_service():
  cfg = arch_linux_locally_cached_projects['gamepadify_config']
  cfg = fixpath(cfg['destination'])
  if not os.path.exists(cfg):
    return None
  return gamepadify_service_template.replace('_START', cfg)

service_root = '/etc/systemd/system'

@tasks.append
def generate_services():
  if not (systemctl := which('systemctl')):
    return
  for service_name, get_desired_service in services.items():
    if not (desired_service := get_desired_service()):
      continue
    service_path = os.path.join(service_root, service_name + '.service')
    p, service = read_config(service_path, default_contents = '')
    if service != desired_service:
      write_config(p, desired_service)
      subprocess.check_call((systemctl, 'daemon-reexec'))
    if not service and service_name not in disabled_services:
      subprocess.check_call((systemctl, 'enable', os.path.basename(p)))

@tasks.append
def update_app_cache():
  kbuildsycoca = which('kbuildsycoca6')
  if not kbuildsycoca:
    return
  subprocess.check_call(('runuser', '-u'+desired_username, '--',
                         kbuildsycoca, '--noincremental'))

only_enable_baloo_temporarily = False

@tasks.append
def update_file_index():
  balooctl = which('balooctl6')
  if not balooctl:
    return
  subprocess.check_call(('runuser', '-u'+desired_username, '--',
                         balooctl, 'check'))
  subprocess.check_call(('runuser', '-u'+desired_username, '--',
                         balooctl, 'enable'))
  if only_enable_baloo_temporarily:
    last_count = None
    while True:
      out = subprocess.check_output(('runuser', '-u'+desired_username, '--',
                                    balooctl, 'status'))
      match = re.search(r'Total files indexed:\s*(\d+)', out.decode())
      count = match.group(1)
      if count == last_count:
        break
      last_count = count
      time.sleep(3)
    subprocess.check_call(('runuser', '-u'+desired_username, '--',
                           balooctl, 'disable'))

# windows_boot_manager_killer_service = """
# [Unit]
# Description=Windows Boot Manager Killer
# After=multi-user.target
# Wants=multi-user.target
#
# [Service]
# Type=oneshot
# ExecStart=efibootmgr --label 'Windows Boot Manager' --delete-bootnum
# Restart=no
#
# [Install]
# WantedBy=default.target
# """.lstrip()
#
# p, contents = read_config('/etc/systemd/system/windows_boot_manager_killer.service', default_contents='')
# if contents != windows_boot_manager_killer_service:
#   write_config(p, windows_boot_manager_killer_service)
#   subprocess.run(['systemctl', 'enable', 'windows_boot_manager_killer.service'])

# TODO
# if in_container():
#   p, pid = read_config(supervisord_pidfile, default_contents='')
#   if not pid.isdigit() or not os.path.exists('/proc/' + pid):
#     dangling_procs = ('websockify', 'dbus', 'supervisord', 'novnc')
#     [subprocess.run(['pkill', i], check=False) for i in dangling_procs]
#     envd = os.environ.copy()
#     envd.update(novnc_vars)
#     subprocess.Popen(['nohup', 'runuser', '--login', desired_username, '-c',
#                       f'/usr/bin/supervisord -c "{supervisor_conf_path}"'],
#                      stdin=subprocess.DEVNULL,
#                      stdout=subprocess.DEVNULL,
#                      stderr=subprocess.DEVNULL,
#                      preexec_fn=os.setpgrp,
#                      env=envd)

@lambda f: (tasks.insert(2, f), tasks.append(f))
def trigger_storage_minder_cleanup_script():
  project = common_locally_cached_projects['storage_minder_cleanup_script']
  script_path = fixpath(project['destination'])
  try:
    dst_st = os.stat(script_path)
    src_st = os.stat(fixpath(project['sources'][0]))
  except FileNotFoundError:
    return
  if (not stat.S_ISREG(dst_st.st_mode) or
      src_st.st_mtime > dst_st.st_mtime or
      dst_st.st_size != src_st.st_size):
    return
  subprocess.check_call((get_shell(), script_path))

def check_maldet_log():
  p, maldet_log = read_config('/var/log/maldet/event_log')
  if re.findall(r'malware hits (\d+),', maldet_log)[-1] != '0':
    raise Exception('Potential infection found via maldet')

@tasks.append
def check_av_scan_logs():
  if which('rkhunter'):
    p, rkhunter_log = read_config('/var/log/rkhunter.log')
    if any((int(i[1]) > 0 for i in re.findall(r'(Suspect files|Possible rootkits): (\d+)', rkhunter_log))):
      raise Exception('Potential infection found via rkhunter')

  if which('lynis') and flags('scan'):
    p, lynis_log = read_config('/var/log/lynis.log')
    error_count = lynis_log.count('Error:')
    warning_count = lynis_log.count('Warning:')
    exception_count = lynis_log.count('Exception:')
    suggestion_count = lynis_log.count('Suggestion:')
    if 'This release is more than' in lynis_log:
      suggestion_count -= 1
    if any((i != 0 for i in (error_count, warning_count, exception_count, suggestion_count))):
      raise Exception('Potential issue found via lynis')

  if maldet_scan_run_reasons:
    check_maldet_log()

known_issues = {
  'CVE-2023-45853',
  # Resolved by https://github.com/madler/zlib/pull/843
  # Fixed in Arch, checked minizip 1.3.1

  'CVE-2020-23922',
  # Won't Fix at https://sourceforge.net/p/giflib/bugs/151
  # If not using gif2rgb, mitigate via: chmod -x "$(type -P gif2rgb)"

  'CVE-2020-16156',
  # See https://blogs.perl.org/users/neilb/2021/11/addressing-cpan-vulnerabilities-related-to-checksums.html
  # Fixed is in Arch
  # Verify via: grep -Rnw '/usr/share/perl5' -e 'pushy_https'

  'CVE-2022-2869',
  # Resolved at https://gitlab.com/libtiff/libtiff/-/commit/07d79fcac2ead271b60e32aeb80f7b4f3be9ac8c
  # tiffcrop removed by https://gitlab.com/libtiff/libtiff/-/issues/580
  # Arch's libtiff 4.6.0-2 does not have tiffcrop
  # Verify via: type tiffcrop

  'CVE-2021-31879',
  # See https://security.archlinux.org/CVE-2021-31879
  # Also https://savannah.gnu.org/bugs/?56909
  # Only impacts using manually added Authorization headers w/o --max-redirect
  # No known dependencies with this use case
  # Still reproducible in Arch wget 1.21.4-1
  # Verify via: wget -d -S -L --header 'Authorization: Basic TOKEN_HERE' https://reader.google.com

  'CVE-2022-28734',
  # Resolved at https://git.savannah.gnu.org/gitweb/?p=grub.git&a=search&h=HEAD&st=commit&s=28734
  # Fixed in Arch, checked grub 2 2.12-1

  'CVE-2021-3695',
  # Resolved at https://git.savannah.gnu.org/gitweb/?p=grub.git&a=search&h=HEAD&st=commit&s=-3695
  # Fixed in Arch, checked grub 2 2.12-1

  'CVE-2021-3847',
  # See https://marc.info/?l=oss-security&m=163473024027378
  # and https://security.archlinux.org/CVE-2021-3847
  # Marked as Won't Fix in most distros due to it being the intended behavior of OverlayFS

  'CVE-2021-3752',
  # Resolved at https://lore.kernel.org/lkml/20211115165435.133245729@linuxfoundation.org
  # Fixed in Arch, checked linux 6.7.5.arch1-1

  'CVE-2022-2068',
  # Resolved at https://git.openssl.org/gitweb/?p=openssl.git;a=commitdiff;h=2c9c35870601b4a44d86ddbf512b38df38285cfa
  # Fixed in Arch, checked openssl 3.2.1-1

  'CVE-2021-3575',
  # Unresolved at https://github.com/uclouvain/openjpeg/issues/1347
  # If not using opj_decompress, opj_compress, opj_dump mitigate via:
  #   chmod -x "$(type -P opj_compress)"
  #   chmod -x "$(type -P opj_decompress)"
  #   chmod -x "$(type -P opj_dump)"

  'CVE-2021-36770',
  # Resolved at https://github.com/dankogai/p5-encode/commit/527e482dc70b035d0df4f8c77a00d81f8d775c74
  # Fixed in Arch, checked perl 5.38.2-1
  # Verify via: grep -Rnw '/usr/lib/perl5' -e '@INC && $INC\[-1\]'

  'CVE-2020-27748',
  # See issue and workaround at https://security.archlinux.org/CVE-2020-27748

  'CVE-2020-26555',
  # Resolved at https://github.com/torvalds/linux/commit/6d19628f539fccf899298ff02ee4c73e4bf6df3f
  # per https://lore.kernel.org/all/CAODzB9rhgj0tKE1RqMZyMmj9op3ODqSBJsDvvgdLHHy-4d9xxQ@mail.gmail.com
  # Fixed in Arch, checked linux 6.7.5.arch1-1

  'CVE-2021-43976',
  # Resolved at https://github.com/torvalds/linux/commit/04d80663f67ccef893061b49ec8a42ff7045ae84
  # per https://lore.kernel.org/all/CAODzB9rhgj0tKE1RqMZyMmj9op3ODqSBJsDvvgdLHHy-4d9xxQ@mail.gmail.com
  # Fixed in Arch, checked linux 6.7.5.arch1-1

  'CVE-2021-4095',
  # Resolved at https://lore.kernel.org/kvm/CAFcO6XOmoS7EacN_n6v4Txk7xL7iqRa2gABg3F7E3Naf5uG94g@mail.gmail.com
  # per https://security.archlinux.org/CVE-2021-4095
  # Fixed in Arch, checked linux 6.7.5.arch1-1

  'CVE-2021-4028',
  # Resolved at https://github.com/torvalds/linux/commit/bc0bdc5afaa740d782fbf936aaeebd65e5c2921d
  # per https://lore.kernel.org/all/CACOXgS9X11kXTPC+ukH2aommTWahwWSuAcuqXveZPpT2YiNBZw@mail.gmail.com
  # Fixed in Arch, checked linux 6.7.5.arch1-1

  'CVE-2021-3669',
  # Resolved at https://lore.kernel.org/all/20231012011341.111660-1-aquini@redhat.com
  # Fixed in Arch, checked linux 6.7.5.arch1-1
  # NB: Later kernel versions have made significant changes to sysvipc_find_ipc since the above post

  'CVE-2020-26559',
  # See https://kb.cert.org/vuls/id/799380
  # Impacts bluetooth mesh provisioning for profile 1.0 and 1.0.1

  'CVE-2020-35501',
  # Only impacts a rare auditing edge case
  # See mitigation steps at https://access.redhat.com/security/cve/cve-2020-35501

  'CVE-2020-26556',
  # Impacts bluetooth mesh. Mitigation steps at https://access.redhat.com/security/cve/CVE-2020-26556

  'CVE-2020-26557',
  # Impacts bluetooth mesh. Mitigation steps at https://bugzilla.redhat.com/show_bug.cgi?id=1960009

  'CVE-2021-31615',
  # See https://security.archlinux.org/CVE-2021-31615
  # and https://www.bluetooth.com/learn-about-bluetooth/key-attributes/bluetooth-security/injectable
  # Denial of service bug which only affects bluetooth le 4.0 - 5.2
  # Marked as Won't Fix in many distros due to being a protocol level flaw

  'CVE-2020-26560',
  # See https://kb.cert.org/vuls/id/799380
  # Impacts bluetooth mesh provisioning for profile 1.0 and 1.0.1

  'CVE-2022-48281',
  # See https://nvd.nist.gov/vuln/detail/CVE-2022-48281
  # tiffcrop removed by https://gitlab.com/libtiff/libtiff/-/issues/580
  # Arch's libtiff 4.6.0-2 does not have tiffcrop
  # Verify via: type tiffcrop

  'CVE-2022-28737',
  # See https://lists.gnu.org/archive/html/grub-devel/2022-06/msg00035.html
  # Fixed in Arch, checked grub 2 2.12-1

  'CVE-2022-28735',
  # See https://lists.gnu.org/archive/html/grub-devel/2022-06/msg00035.html
  # Fixed in Arch, checked grub 2 2.12-1

  'CVE-2022-28733',
  # See https://lists.gnu.org/archive/html/grub-devel/2022-06/msg00035.html
  # Fixed in Arch, checked grub 2 2.12-1

  'CVE-2022-28736',
  # See https://lists.gnu.org/archive/html/grub-devel/2022-06/msg00035.html
  # Fixed in Arch, checked grub 2 2.12-1

  'CVE-2021-3696',
  # See https://lists.gnu.org/archive/html/grub-devel/2022-06/msg00035.html
  # Fixed in Arch, checked grub 2 2.12-1

  'CVE-2021-3697',
  # See https://lists.gnu.org/archive/html/grub-devel/2022-06/msg00035.html
  # Fixed in Arch, checked grub 2 2.12-1

  'CVE-2022-1355',
  # Resolved at https://gitlab.com/libtiff/libtiff/-/commit/fb1db384959698edd6caeea84e28253d272a0f96
  # Fixed in Arch, checked libtiff 4.6.0-2

  'CVE-2022-1354',
  # Resolved at https://gitlab.com/libtiff/libtiff/-/commit/87881e093691a35c60b91cafed058ba2dd5d9807
  # Fixed in Arch, checked libtiff 4.6.0-2

  'CVE-2022-48281',
  # Resolved at https://gitlab.com/libtiff/libtiff/-/commit/d1b6b9c1b3cae2d9e37754506c1ad8f4f7b646b5
  # Also, tiffcrop removed by https://gitlab.com/libtiff/libtiff/-/issues/580
  # Arch's libtiff 4.6.0-2 does not have tiffcrop
  # Verify via: type tiffcrop

  'CVE-2022-34526',
  # Resolved at https://gitlab.com/libtiff/libtiff/-/commit/275735d0354e39c0ac1dc3c0db2120d6f31d1990
  # Fixed in Arch, checked libtiff 4.6.0-2

  'CVE-2022-3599',
  # Resolved at https://gitlab.com/libtiff/libtiff/-/commit/e813112545942107551433d61afd16ac094ff246
  # Fixed in Arch, checked libtiff 4.6.0-2

  'CVE-2022-2867',
  # See https://nvd.nist.gov/vuln/detail/CVE-2022-2867
  # tiffcrop removed by https://gitlab.com/libtiff/libtiff/-/issues/580
  # Arch's libtiff 4.6.0-2 does not have tiffcrop
  # Verify via: type tiffcrop

  'CVE-2022-2520',
  # Resolved at https://gitlab.com/libtiff/libtiff/-/merge_requests/378/commits
  # Also, tiffcrop removed by https://gitlab.com/libtiff/libtiff/-/issues/580
  # Arch's libtiff 4.6.0-2 does not have tiffcrop
  # Verify via: type tiffcrop

  'CVE-2022-2519',
  # Resolved at https://gitlab.com/libtiff/libtiff/-/merge_requests/378/commits
  # Also, tiffcrop removed by https://gitlab.com/libtiff/libtiff/-/issues/580
  # Arch's libtiff 4.6.0-2 does not have tiffcrop
  # Verify via: type tiffcrop

  'CVE-2022-1622',
  # Resolved at https://gitlab.com/libtiff/libtiff/-/commit/b4e79bfa0c7d2d08f6f1e7ec38143fc8cb11394a
  # Also, tiffcrop removed by https://gitlab.com/libtiff/libtiff/-/issues/580
  # Arch's libtiff 4.6.0-2 does not have tiffcrop
  # Verify via: type tiffcrop

  'CVE-2022-3570',
  # Resolved at https://gitlab.com/libtiff/libtiff/-/commit/bd94a9b383d8755a27b5a1bc27660b8ad10b094c
  # Fixed in Arch, checked libtiff 4.6.0-2

  'CVE-2022-3597',
  # Resolved at https://gitlab.com/libtiff/libtiff/-/commit/236b7191f04c60d09ee836ae13b50f812c841047
  # Also, tiffcrop removed by https://gitlab.com/libtiff/libtiff/-/issues/580
  # Arch's libtiff 4.6.0-2 does not have tiffcrop
  # Verify via: type tiffcrop

  'CVE-2022-2868',
  # See https://nvd.nist.gov/vuln/detail/CVE-2022-2868
  # tiffcrop removed by https://gitlab.com/libtiff/libtiff/-/issues/580
  # Arch's libtiff 4.6.0-2 does not have tiffcrop
  # Verify via: type tiffcrop

  'CVE-2022-2953',
  # Resolved at https://gitlab.com/libtiff/libtiff/-/commit/48d6ece8389b01129e7d357f0985c8f938ce3da3
  # Also, tiffcrop removed by https://gitlab.com/libtiff/libtiff/-/issues/580
  # Arch's libtiff 4.6.0-2 does not have tiffcrop
  # Verify via: type tiffcrop

  'CVE-2022-2057',
  # Resolved at https://gitlab.com/libtiff/libtiff/-/merge_requests/346
  # Also, tiffcrop removed by https://gitlab.com/libtiff/libtiff/-/issues/580
  # Arch's libtiff 4.6.0-2 does not have tiffcrop
  # Verify via: type tiffcrop

  'CVE-2022-3627',
  # Resolved at https://gitlab.com/libtiff/libtiff/-/commit/236b7191f04c60d09ee836ae13b50f812c841047
  # Also, tiffcrop removed by https://gitlab.com/libtiff/libtiff/-/issues/580
  # Arch's libtiff 4.6.0-2 does not have tiffcrop
  # Verify via: type tiffcrop

  'CVE-2022-2058',
  # Resolved at https://gitlab.com/libtiff/libtiff/-/merge_requests/346
  # Also, tiffcrop removed by https://gitlab.com/libtiff/libtiff/-/issues/580
  # Arch's libtiff 4.6.0-2 does not have tiffcrop
  # Verify via: type tiffcrop

  'CVE-2022-3970',
  # Resolved at https://gitlab.com/libtiff/libtiff/-/commit/227500897dfb07fb7d27f7aa570050e62617e3be
  # Fixed in Arch, checked libtiff 4.6.0-2

  'CVE-2022-2056',
  # Resolved at https://gitlab.com/libtiff/libtiff/-/merge_requests/346
  # Also, tiffcrop removed by https://gitlab.com/libtiff/libtiff/-/issues/580
  # Arch's libtiff 4.6.0-2 does not have tiffcrop
  # Verify via: type tiffcrop

  'CVE-2022-2521',
  # Resolved at https://gitlab.com/libtiff/libtiff/-/merge_requests/378/commits
  # Also, tiffcrop removed by https://gitlab.com/libtiff/libtiff/-/issues/580
  # Arch's libtiff 4.6.0-2 does not have tiffcrop
  # Verify via: type tiffcrop

  'CVE-2022-1623',
  # Resolved at https://gitlab.com/libtiff/libtiff/-/commit/b4e79bfa0c7d2d08f6f1e7ec38143fc8cb11394a
  # Fixed in Arch, checked libtiff 4.6.0-2

  'CVE-2020-23109',
  # See https://github.com/strukturag/libheif/issues/207#issuecomment-1289322472
  # Resolved but other, similar bugs may exist
  # Fixed in Arch, checked libheif 1.17.6
  # If not using heif-convert, mitigate via: chmod -x "$(type -P heif-convert)"

  'CVE-2017-11331',
  # See https://seclists.org/fulldisclosure/2017/Jul/80
  # Resolved in latest version of vorbis-tools
  # Verify via pacman -Qi vorbis-tools

  'CVE-2025-31115',
  # See https://security.archlinux.org/AVG-2860
  # Resolved in latest version of xz
  # Check via xz --version

  'CVE-2025-6020',
  # See https://github.com/linux-pam/linux-pam/releases/tag/v1.7.1
  # Check via pacman -Qi pam

  'CVE-2025-4598',
  # See /proc/sys/fs/suid_dumpable
  # Disabled by default
  # Check cat /proc/sys/fs/suid_dumpable

  'CVE-2021-38185',
  # See https://security.archlinux.org/CVE-2021-38185
  # Check pacman -Qi cpio

  'CVE-2025-6170',
  'CVE-2025-49794',
  'CVE-2025-49795',
  'CVE-2025-49796',
  # See https://help.puppet.com/core/current/Content/PuppetCore/PuppetReleaseNotes/release_notes_puppet_x-8-14-0.htm
  # All should be fixed by libxml2 2.14.5

  'CVE-2025-40909',
  # See https://nvd.nist.gov/vuln/detail/cve-2025-40909
  # and https://github.com/Perl/perl5/commit/918bfff86ca8d6d4e4ec5b30994451e0bd74aba9.patch
  # and https://github.com/Perl/perl5/blob/v5.42.0/sv.c
  # Fixed in v5.42.0

  'CVE-2025-20260',
  'CVE-2025-20234',
  # See https://blog.clamav.net/2025/06/clamav-143-and-109-security-patch.html
  # Fixed in 1.4.3
  # Check via pacman -Qi clamav

  'CVE-2025-4575',
  # See https://openssl-library.org/news/secadv/20250522.txt
  # Fixed in OpenSSL 3.5.1
  # Check via pacman -Qi openssl

  # 'CVE-2025-46394',
  # Still not fixed!
  # Verify using POC from:
  # https://web.archive.org/web/20241009195241/https://bugs.busybox.net/show_bug.cgi?id=16018

  # 'CVE-2025-5278',
  # Still not fixed!
  # See
  #  https://gitlab.archlinux.org/archlinux/packaging/packages/coreutils/-/blob/main/.SRCINFO?ref_type=heads
  #  https://git.savannah.gnu.org/git/coreutils.git/refs/tags
  #  https://cgit.git.savannah.gnu.org/cgit/coreutils.git/commit/?id=8c9602e3a145e9596dc1a63c6ed67865814b6633
  #  https://cgit.git.savannah.gnu.org/cgit/coreutils.git/tree/src/sort.c?id=f8f3e758110c31ed20a682841c86e54ddeb9f449
}

known_issues_with_deadlines = {
  'CVE-2025-46394': '2026-01-29',
  'CVE-2025-5278': '2026-01-29',
}

@tasks.append
def run_arch_audit():
  if not which('arch-audit') or flags('offline'):
    return

  for issue, deadline in known_issues_with_deadlines.items():
    if time.time() < time.mktime(time.strptime(deadline, '%Y-%m-%d')):
      known_issues.add(issue)

  js = json.loads(subprocess.check_output([which('arch-audit'), '--json']))
  avgs_with_unknown_issues = []
  for avg in js:
    avg['unknown_issues'] = set(avg['issues']) - known_issues
    if any(avg['unknown_issues']):
      avgs_with_unknown_issues.append(avg)

  if any(avgs_with_unknown_issues):
    pfx = 'https://security.archlinux.org/'
    for avg in avgs_with_unknown_issues:
      print(', '.join(avg['packages']), '-', avg['severity'], '-', pfx+avg['name'])
      [print('  ', pfx+i) for i in avg['unknown_issues']]
      print('')
    raise Exception('Packages with unknown issues found!')

def extract_first_graphviz_string(txt):
  m = re.search(r'".*?[^\\]"', txt)
  if not m and '""' in m:
    return ''
  return json.loads(m.group(0))

def get_package_metadata():
  meta = {}
  if is_arch_linux():
    last_key = None
    for line in filter(str.strip, subprocess.check_output(['pacman', '-Qi'])
                      .decode().splitlines()):
      idx = line.find(':')
      key = line[:idx].strip().lower()
      if key == 'name':
        current_package = line[idx+1:].strip()
        meta[current_package] = {'required_by':set()}
      elif key == 'required by':
        meta[current_package]['required_by'].update(set(line[idx+1:].split()))
        meta[current_package]['required_by'] -= {'None'}
      elif idx == -1 and last_key == 'required by':
        meta[current_package]['required_by'].update(set(line.split()))
      last_key = last_key if idx == -1 else key
  elif is_postmarketos():
    for line in subprocess.check_output(['apk', 'dot', '--installed'])\
                  .decode().splitlines():
      sp = line.split(' -> ')
      if len(sp) < 2:
        continue
      if len(sp) > 2:
        raise RuntimeError()
      current = '-'.join(extract_first_graphviz_string(sp[1]).split('-')[:-2])
      req = '-'.join(extract_first_graphviz_string(sp[0]).split('-')[:-2])
      meta.setdefault(current, {'required_by': set()})['required_by'].add(req)
  elif is_termux():
    raise NotImplementedError()
  return meta

# @tasks.append
def make_sure_no_partitions_are_unsealed():
  if not (auto_tpm_encrypt := which('auto_tpm_encrypt')):
    return
  subprocess.run((auto_tpm_encrypt, '--ensure_no_os_are_unsealed'),
                 env = os.environ | {'IGNORE_IF_ON_BATTERY': '1'},
                 capture_output = True,
                 check = True)

kate_session_file_path = f'~{desired_username}/.local/share/kate/sessions/Default.katesession'

@tasks.append
def backup_kate_session_for_debugging():
  p, current = read_config(kate_session_file_path, default_contents = '')
  if not current:
    return
  cache_dir = fixpath(f'~{desired_username}/.cache/kate_session_dbg')
  makedirs(cache_dir, user = desired_username)
  try:
    p, old = read_config(os.path.join(cache_dir,
                                      sorted(os.listdir(cache_dir))[-1]))
  except (FileNotFoundError, IndexError):
    old = None
  if current == old:
    return
  fpath = os.path.join(cache_dir, f'Default-{round(time.time())}.katesession')
  write_config(fpath, current, user = desired_username, mode = 'x')

def run_sysemctl(cmd, user = None, capture_output = False):
  if user:
    cmd = ['systemctl', '--machine='+user+'@', '--user'] + cmd
  else:
    cmd = ['systemctl'] + cmd
  return subprocess.run(cmd, check = True, capture_output = capture_output)

def get_running_services(user = None):
  proc = run_sysemctl(['show', '*.service'],
                      user = user,
                      capture_output = True)
  running = set()
  unit = {}
  for line in proc.stdout.decode().splitlines():
    k, d, v = line.partition('=')
    if d:
      unit[k] = v
    else:
      if unit.get('SubState') == 'running':
        running.add(unit['Id'][:-8])
      unit = {}
  return running

def has_proc_comm(targets):
  try:
    pids = os.listdir('/proc')
  except FileNotFoundError:
    return False
  for pid in pids:
    if not pid.isdigit():
      continue
    _, comm = read_config(os.path.join('/proc', pid, 'comm'),
                          default_contents = '')
    if comm.strip() in targets:
      return True
  return False

restartable_system_services = {
  'Sessen',
  'MissionControlLite',
  'systemd-localed',
  'systemd-udevd',
  'power-profiles-daemon',
  'accounts-daemon',
  'systemd-timesyncd',
  'systemd-resolved',
  'upower',
  'systemd-userdbd',
  'udisks2',
  'systemd-journald',
  'rtkit-daemon',
}

restartable_user_services = {
  'pipewire-pulse',
  'pipewire',
  'wireplumber',
  'plasma-kded6',
  'plasma-plasmashell',
  'plasma-ksmserver',
  'plasma-xdg-desktop-portal-kde',
  'xdg-desktop-portal-gtk',
  'plasma-polkit-agent',
  'obex',
  'drkonqi-coredump-pickup',
  'dconf',
  'plasma-kaccess',
  'plasma-powerdevil',
  'xdg-permission-store',
  'app-org.kde.discover.notifier@autostart',
  'plasma-kactivitymanagerd',
  'plasma-xembedsniproxy',
  'plasma-gmenudbusmenuproxy',
  'kde-baloo.service',

  # "Works" but breaks wake locks until programs are restarted
  # 'at-spi-dbus-bus',
}

@tasks.append
def live_soft_reboot():
  if not sys.stdin.isatty():
    return
  user_svc = set(restartable_user_services)
  if has_proc_comm(('wineserver', 'firefox-bin')):
    user_svc -= {'pipewire-pulse', 'pipewire', 'wireplumber'}
  for u, restartable in ((None, restartable_system_services),
                         (desired_username, user_svc)):
    running = get_running_services(user = u)
    needs_restart = restartable.intersection(running)
    if len(needs_restart) > 0:
      run_sysemctl(['restart'] + list(needs_restart), user = u)

@tasks.append
def remove_undesired_packages():
  if not flags('undesired'):
    return

  all_packages = set(get_installed_packages(include_version = False))
  desired_packages = set(get_desired_packages(include_aur = True))
  meta = get_package_metadata()

  while True:
    starting_length = len(desired_packages)
    for package, m in meta.items():
      if m['required_by'].intersection(desired_packages):
        desired_packages.add(package)
    if len(desired_packages) == starting_length:
      break

  undesired_packages = all_packages - desired_packages
  undesired_packages_ordered_by_requirements = []
  already_sorted_packages = set()
  while len(undesired_packages_ordered_by_requirements) != len(undesired_packages):
    starting_length = len(undesired_packages_ordered_by_requirements)
    for package in undesired_packages:
      m = meta.get(package)
      required_by = m['required_by'] if m else set()
      if package not in already_sorted_packages and \
        not (required_by - already_sorted_packages):
        undesired_packages_ordered_by_requirements.append(package)
        already_sorted_packages.add(package)
    if len(undesired_packages_ordered_by_requirements) == starting_length:
      break

  packages_with_circular_dependencies = undesired_packages - set(undesired_packages_ordered_by_requirements)

  print('Removing undesired packages:')
  print(f'{len(undesired_packages_ordered_by_requirements)} package(s) without circular dependencies will be removed')
  if len(undesired_packages_ordered_by_requirements) > 0:
    print(textwrap.fill(shlex.join(undesired_packages_ordered_by_requirements),
                        initial_indent = '  ',
                        subsequent_indent = '  '))
  print(f'{len(packages_with_circular_dependencies)} package(s) with circular dependencies will be removed')
  if len(packages_with_circular_dependencies) > 0:
    print(textwrap.fill(shlex.join(packages_with_circular_dependencies),
                        initial_indent = '  ',
                        subsequent_indent = '  '))
  packages_to_remove = undesired_packages_ordered_by_requirements + list(packages_with_circular_dependencies)
  if len(packages_to_remove) > 0:
    print('Type YES to proceed or press Ctrl + C to cancel.')
    print('Cancel if you would prefer to remove the packages manually.\n')
    if input('!!! ') == 'YES':
      if is_arch_linux():
        subprocess.check_call(shlex.split('pacman -R') + packages_to_remove)
      elif is_postmarketos():
        subprocess.check_call(shlex.split('apk del') + packages_to_remove)
      elif is_termux():
        raise NotImplementedError()
    else:
      print('Skipped package removal')
  else:
    print('Nothing to remove!')

@tasks.append
def display_done_message():
  # print('Done but manually need to pick: hostname, user and root pass, grub config, fstab, maldet, rclone')
  if not reasons_interactive_setup_needed:
    print('No additional steps are pending! B-)')
  print('Done!')
  if reasons_interactive_setup_needed:
    print('Additional steps which require user interaction are pending.')
    print('Rerun lincfg with the -i or --interact flag.')



original_maldext_size_limit_codee = \
  "'scan_max_filesize=`cat $sig_md5_file | cut -d':' -f2 | sort -n | tail -n1`"
expected_maldet_size_limit_code = 'scan_max_filesize=99999999999999999'

#? LINCFG R1
#? lincfg is a Linux setup and maintenance script
#? It will install, update and configure software and perform health checks
#?
#? Run in Podman or Docker via:
#? podman run -p 8084:8083 -it docker.io/library/archlinux /bin/sh -c "pacman -Syu --noconfirm nano tmux python ; tmux"

def in_container():
  os.environ.get('container') is not None

def alert(*msg, title = 'Alert', width = 80, interactive = True):
  msg = '\n'.join(map(str, msg))
  print('\n')
  print('--- [' + title + '] ' + ('-'*(width-(len(title)+7))))
  print('\n' + msg + '\n')
  print('-'*width)
  if interactive:
    print('Press enter to continue or Ctrl + C to abort')
  print('-'*width)
  print('')
  i = input() if interactive else None
  if i:
    raise Exception('aborting due to unexpected input')

def fixpath(p):
  if desired_username and p.startswith(f'~{desired_username}/') and is_termux():
    p = '~/' + p[len(desired_username)+2:]
  if not is_termux() and '$PREFIX' in p:
    p = p.replace('$PREFIX', '')
  return os.path.expanduser(os.path.expandvars(p))

def read_config(fname, default_contents = None):
  p = fixpath(fname)
  try:
    with open(p, 'r') as f:
      return p, f.read()
  except FileNotFoundError:
    if default_contents is not None:
      return p, default_contents
    raise

def write_config(fname, contents, user = None, mode = 'w'):
  fname = fixpath(fname)
  makedirs(os.path.dirname(fname), user = user)
  with open(fname, mode) as f:
    f.write(textwrap.dedent(contents))
  if user:
    shutil.chown(fname, user)

def get_config_var(config, name):
  return (list(
           filter(lambda i: i[0] == name and i[1],
           map(lambda i: i.strip().partition('='),
               config.splitlines()))) or ((0, 0, None),))[0][2]

def make_config_version_vars(ver, config, prefix = '# LINCFG:R ', suffix='\n'):
  old = float((tuple(filter(lambda i: i.startswith(prefix),
          config.splitlines())) or ('0',))[0].split()[-1])
  comment = prefix + str(ver) + suffix
  return old, ver, comment

def get_link_target(path):
  try:
    return os.readlink(path)
  except FileNotFoundError:
    return None

# NB: can't handle multiple keys with the same name in different sections yet
def ensure_rc_values(path, values, user = desired_username):
  p, rc = read_config(path, default_contents = '')
  for section, key, value in values:
    i = rc.find(section)
    if i == -1:
      write_config(p,
                   rc + f'\n\n{section}\n{key}={value}\n',
                   user = user)
      continue
    if f'{key}={value}' in rc:
      continue
    if key not in rc:
      write_config(p,
                   rc[:i+len(section)+1] + f'{key}={value}\n' + rc[i+len(section)+1:],
                   user = user)
      continue
    write_config(p,
                 re.sub(f'{key}=.+', f'{key}={value}', rc),
                 user = user)

@functools.cache
def get_os_name():
  try:
    with open('/etc/os-release', 'r') as f:
      osr = f.read()
  except FileNotFoundError:
    return None
  return re.search('NAME="(.+?)"', osr).group(1)

def get_standardized_os_name():
  if is_arch_linux():
    return 'archlinux'
  if is_postmarketos():
    return 'postmarketos'
  if is_termux():
    return 'termux'

def is_arch_linux():
  return get_os_name() == 'Arch Linux'

def is_postmarketos():
  return (
    get_os_name().startswith('postmarketOS ') or
    get_os_name() == 'Alpine Linux'
  )

def is_termux():
  return os.environ.get('TERMUX_VERSION') and which('pkg')

# Recursively, deterministically hashes a file or directory
# If the given path is a file, will return that files hash which should match
# the output of sha256sum.
# Does NOT check permissions or other metadata
# Account for that when auditing code and updating hashes in this script
def hash_path(path):
  hash = hashlib.sha256()
  paths = [('D' if os.path.isdir(path) else 'F', path)]
  for root, dirs, files in os.walk(path):
    for kind, names in (('D', dirs), ('F', files)):
      for i in names:
        paths.append((kind, os.path.join(root, i)))
  for kind, ipath in sorted(paths, key=lambda i: i[1]):
    assert ipath.startswith(path)
    epath = ipath[len(path):]
    if len(epath) != 0 and kind != 'F':
      hash.update((str(len(epath))+kind+epath).encode('utf8'))
    if kind == 'F':
      with open(ipath, 'rb') as f:
        while True:
          buf = f.read(4194304) # 4 MB
          if not buf: break
          hash.update(buf)
  return hash.hexdigest()

def ensure_python_package(src_url, hash, user=None):
  fname = src_url.split('/')[-1]
  pkgname = '-'.join(fname.split('-')[:-1])
  pkgver = fname.split('-')[-1][:-7]
  if user:
    cmd = ('runuser', '-u'+user, '--',
           'python', '-c' 'import site;print(site.getusersitepackages())')
    out = subprocess.check_output(cmd)
    pkgroot = out.decode().strip()
    assert(len(pkgroot) > 3)
  else:
    pkgroot = site.getsitepackages()[0]
  pkgdir = os.path.join(pkgroot, pkgname.replace('-','_'))
  latest_version = re.findall(r'\-([\d\.]+)\-',
                              urllib.request.urlopen('https://pypi.org/simple/'+pkgname)
                               .read().decode())[-1]
  if pkgver != latest_version:
    alert(f'While checking {fname} found a newer version: {latest_version}',
           'Update this script with the new url and hashes after auditing them.')
  if not os.path.exists(pkgdir):
    troot = tempfile.mkdtemp(prefix='pypkg_')
    ttar = os.path.join(troot, fname)
    subprocess.run(['curl', '-L', '-o', ttar, src_url])
    if hash_path(ttar) != hash:
      raise Exception('hash mismatch', pkgname)
    subprocess.run(['tar', 'xzf', ttar, '-C', troot])
    xdir = sorted(filter(os.path.isdir,map(lambda i: os.path.join(troot, i),
                  os.listdir(troot))))[0]
    os.makedirs(pkgroot, exist_ok=True)
    shutil.move(os.path.join(xdir, pkgname.replace('-','_')), pkgroot)
    if user:
      subprocess.run(['chown', '-R', user+':', pkgroot])

def restore_file_from_package(pkgname, fpath):
  if not is_arch_linux():
    print('ERROR: restore_file_from_package not implemented for this OS yet!!!')
    breakpoint()
  subprocess.run(['pacman', '-Sw', '--noconfirm', pkgname])
  conf = {i[0].strip():i[1].split() for i in
          map(lambda i: i.split(':'),
          subprocess.run(['pacman', '-v'], check=False, capture_output=True)
            .stdout.decode().splitlines())}
  matching_packages = set()
  for cache_dir in conf['Cache Dirs']:
    for i in os.listdir(cache_dir):
      if not i.endswith('.tar.zst'):
        continue
      if '-'.join(i.split('-')[:-3]) == pkgname:
        matching_packages.add(os.path.join(cache_dir, i))
  pkgpath = sorted(matching_packages, key=os.path.getmtime)[-1]
  tdir = tempfile.mkdtemp(prefix='restore_pkg_'+pkgname+'_')
  tarpath = os.path.join(tdir, 'pkg.tar')
  subprocess.run(['unzstd', '-d', pkgpath, '-o', tarpath])
  subprocess.run(['tar', 'xf', tarpath, '-C', tdir])
  src = os.path.join(tdir, os.path.abspath(fpath)[1:])
  shutil.move(src, fpath)

def get_installed_flatpaks():
  installed_flatpaks = set()
  r = subprocess.check_output(['flatpak', 'list', '--columns=application,ref'])
  r = sorted(map(str.split, r.decode().splitlines()), key=lambda i: i[0])
  last_flatpak, last_ref = None, None
  for flatpak, ref in r:
    installed_flatpaks.add(flatpak)
    if last_flatpak == flatpak:
      installed_flatpaks.discard(flatpak)
      installed_flatpaks.add(last_ref)
      installed_flatpaks.add(ref)
    last_flatpak, last_ref = flatpak, ref
  return installed_flatpaks

def makedirs(path, user = None, mode = 0o755):
  dirs = []
  last = None
  current = fixpath(path)
  while current != last:
    dirs.append(current)
    last = current
    current = os.path.dirname(current)
  while len(dirs) > 0:
    d = dirs.pop()
    try:
      os.mkdir(d)
      if user:
        shutil.chown(d, user = user)
      os.chmod(d, mode)
    except (FileExistsError, PermissionError):
      pass

def install_executable_if_missing(src, dst, mode = 0o755, user = None):
  dst = fixpath(dst)
  makedirs(os.path.dirname(dst), user = user)
  try:
    with open(dst, 'xb') as outf:
      with open(fixpath(src), 'rb') as inf:
        outf.write(inf.read())
    os.chmod(outf.name, mode)
    if user is not None:
      shutil.chown(outf.name, user = user)
  except FileExistsError:
    pass
  except FileNotFoundError:
    os.remove(outf.name)

# NB: assumes src and dst on same file system
def merge_move(src, dst):
  s = fixpath(src)
  d = fixpath(dst)
  if not os.path.isdir(s):
    try:
      open(d, 'x').close()
    except FileExistsError:
      i = 2
      while True:
        try:
          j, k = os.path.splitext(d)
          j = j+f'-{i}'+k
          open(j, 'x').close()
          d = j
          break
        except FileExistsError:
          i += 1
  try:
    os.replace(s, d)
    return
  except OSError as e:
    if e.errno == errno.ENOTEMPTY:
      for i in os.listdir(s):
        merge_move(os.path.join(s, i), os.path.join(d, i))
      os.rmdir(s)
    else:
      raise

def has_at_least_one_file(path):
  try:
    for i in os.listdir(fixpath(path)):
      if has_at_least_one_file(os.path.join(path, i)):
        return True
    return False
  except NotADirectoryError:
    return True

def get_installed_packages(include_version = True):
  if is_arch_linux():
    proc = subprocess.run(shlex.split('pacman -Q'), capture_output=True)
    packages = proc.stdout.decode().splitlines()
  elif is_postmarketos():
    proc = subprocess.run(shlex.split('apk list --installed'), capture_output=True)
    packages = ['-'.join(j[:-2]) + ' ' + '-'.join(j[-2:])
                for j in (i.split()[0].split('-')
                for i in proc.stdout.decode().splitlines())]
  else:
    raise NotImplementedError()
  if not include_version:
    packages = [p.split()[0] for p in packages]
  return packages

@functools.cache
def which(name):
  return shutil.which(name)

def get_shell():
  if shell := which(desired_shell):
    return shell
  if shell := which(os.environ.get('SHELL', 'sh')):
    return shell
  raise RuntimeError('Unable to find shell')

@functools.cache
def gethostname():
  return socket.gethostname()

def get_id():
  return gethostname().strip().lower().replace('-', '_')



def flags(name):
  a = '--'+name
  s = {k:v for k,v,_ in flag_def}[a][1:]
  for arg in sys.argv:
    if arg == a:
      return True
    if arg[:1] == '-' and arg[:2] != '--':
      for c in arg[1:]:
        if c == s:
          return True
  return False

def main():
  try:
    with open('/proc/' + str(os.getpid()) + '/comm', 'w') as f:
      f.write('lincfg')
  except FileNotFoundError:
    pass

  if flags('help'):
    [print(i[3:].strip()) for i in filter(lambda i: i.startswith('#?'), read_config(__file__)[1].splitlines())]
    cmd = os.path.basename(sys.argv[0])
    run_from_cmd = shutil.which(cmd) == sys.argv[0]
    print('\nUsage: ' + (cmd if run_from_cmd else f'{sys.executable} {sys.argv[0]}') + ' [FLAGS]\nFlags:')
    desired_column = min((80 - len(d[-1].splitlines()[0]) for d in flag_def))
    for d in flag_def:
      s = ' '.join((i if i else '' for i in d[:-1]))
      print('  ' + s + (' ' * max(1, (desired_column - len(s)))) + d[-1])
    return

  for idx, task in enumerate(tasks):
    print(f'[Task {idx+1}] {task.__name__}', flush = True)
    # if idx > 42: breakpoint()
    task()

if __name__ == '__main__':
  main()




