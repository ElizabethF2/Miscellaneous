#!/bin/sh

# Superseded by https://github.com/termux/termux-docker
# podman run -it --name termux docker.io/termux/termux-docker:latest
# or
# podman run -it --name termux --arch=aarch64 docker.io/termux/termux-docker:aarch64

export PREFIX="/data/data/com.termux/files/usr"
export HOME="/data/data/com.termux/files/home"
export TMPDIR="$PREFIX/tmp"
export PATH="$PREFIX/bin"

export ANDROID_DATA="/data"
export EXTERNAL_STORAGE="/sdcard"

export TMUX_TMPDIR="$PREFIX/var/run"
export TERMUX_IS_DEBUGGABLE_BUILD="0"
export TERMUX_MAIN_PACKAGE_FORMAT="debian"
export TERMUX_VERSION=0.118.1
export TERMUX_API_VERSION=0.50.1
export TERMUX_APK_RELEASE=F_DROID

export SHELL="$PREFIX/bin/bash"
export HISTCONTROL="ignoreboth"
export LANG=en_US.UTF-8
export USER="$(whoami)"
export LOGNAME="$USER"

bootstrap ()
{
  mkdir -p "$PREFIX"
  mkdir -p "$HOME"
  mkdir -p "$EXTERNAL_STORAGE"

  ln -s /bin "$PREFIX/bin"
  ln -s /lib "$PREFIX/lib"
  ln -s /opt "$PREFIX/opt"
  ln -s /etc "$PREFIX/etc"
  ln -s /var "$PREFIX/var"
  ln -s /tmp "$TMPDIR"
  ln -s /usr/share "$PREFIX/share"
  ln -s /usr/include "$PREFIX/include"
}

# termux-am                     termux-dialog                 termux-notification-channel   termux-saf-stat               termux-torch
# termux-am-socket              termux-download               termux-notification-list      termux-saf-write              termux-tts-engines
# termux-api-start              termux-fingerprint            termux-notification-remove    termux-sensor                 termux-tts-speak
# termux-api-stop               termux-fix-shebang            termux-open                   termux-setup-package-manager  termux-usb
# termux-audio-info             termux-info                   termux-open-url               termux-setup-storage          termux-vibrate
# termux-backup                 termux-infrared-frequencies   termux-reload-settings        termux-share                  termux-volume
# termux-battery-status         termux-infrared-transmit      termux-reset                  termux-sms-inbox              termux-wake-lock
# termux-brightness             termux-job-scheduler          termux-restore                termux-sms-list               termux-wake-unlock
# termux-call-log               termux-keystore               termux-saf-create             termux-sms-send               termux-wallpaper
# termux-camera-info            termux-location               termux-saf-dirs               termux-speech-to-text         termux-wifi-connectioninfo
# termux-camera-photo           termux-media-player           termux-saf-ls                 termux-storage-get            termux-wifi-enable
# termux-change-repo            termux-media-scan             termux-saf-managedir          termux-telephony-call         termux-wifi-scaninfo
# termux-clipboard-get          termux-microphone-record      termux-saf-mkdir              termux-telephony-cellinfo
# termux-clipboard-set          termux-nfc                    termux-saf-read               termux-telephony-deviceinfo
# termux-contact-list           termux-notification           termux-saf-rm                 termux-toast
#


# libexec
