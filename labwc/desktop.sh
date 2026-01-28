#!/bin/sh
apk add labwc swaybg wayvnc fuzzel

export XDG_RUNTIME_DIR=/run/user/$USER
mkdir -p "$XDG_RUNTIME_DIR"
chmod 0700 "$XDG_RUNTIME_DIR"

mkdir -p ~/.config/labwc
cat > ~/.config/labwc/autostart <<EOF
swaybg -c '#113344' >/dev/null 2>&1 &
waybar >/dev/null 2>&1 &
EOF

cp "$(dirname "$0")"/menu.xml ~/.config/labwc/menu.xml

mkdir -p ~/.config/wayvnc
cat > ~/.config/wayvnc/config <<EOF
address=10.0.2.15
EOF

WLR_BACKENDS=headless WLR_RENDERER_ALLOW_SOFTWARE=1 WLR_LIBINPUT_NO_DEVICES=1 labwc &
labwc_pid=$!
sleep 5
WAYLAND_DISPLAY=wayland-0 wayvnc --log-level debug &
wait $labwc_pid
