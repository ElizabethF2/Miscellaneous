# https://github.com/Ilya114/Box64Droid
# https://hongchai.medium.com/building-your-own-termux-with-a-custom-package-name-4b2de0c09fac

# TODO check for arch and podman
podman run --name custom_termux -it docker.io/termux/termux-docker:latest
podman run --name custom_termux -it alpine sh

export WORKSPACE=/srv/ws
export NAMESPACE=steamcustom
SDK_VERSION=11076708
SDK_HASH="2d2d50857e4eb553af5a6dc3ad507a17adf43d115264b1afc116f95c92e5e258"

# TODO check for pkg and ensure pkgs installed, apk fallback, error if no apk
apk add git gradle
mkdir "$WORKSPACE"
# TODO option to use hashed release instead of git
git clone https://github.com/termux/termux-app "$WORKSPACE/termux-app"
rm -r "$WORKSPACE/termux-app/.git"
find "$WORKSPACE/termux-app/" -type f -exec sed -i "s/com\.termux/com.termux_$NAMESPACE/" {} \;
find "$WORKSPACE/termux-app/" -type f -exec sed -i "s/com_termux/com_termux_$NAMESPACE/" {} \;

i="$(grep -n 'checksum !' "$WORKSPACE/termux-app/app/build.gradle" | cut -d : -f 1)"
i="$(expr $i - 1)"
j="$(wc -l < "$WORKSPACE/termux-app/app/build.gradle")"
j="$(expr $j - $i)"
head -n $i "$WORKSPACE/termux-app/app/build.gradle" > "$WORKSPACE/buf"
printf '\n    def proc = "%s".execute()' "$WORKSPACE/bstrap.sh" >> "$WORKSPACE/buf"
printf '\n    proc.waitForProcessOutput(System.out, System.err)' >> "$WORKSPACE/buf"
printf '\n' >> "$WORKSPACE/buf"
tail -n $j "$WORKSPACE/termux-app/app/build.gradle" >> "$WORKSPACE/buf"
mv "$WORKSPACE/buf" "$WORKSPACE/termux-app/app/build.gradle"

echo '#!/bin/sh' > "$WORKSPACE/bstrap.sh"
chmod +x "$WORKSPACE/bstrap.sh"

# TODO check if ANDROID_SDK_ROOT set
# URL from https://developer.android.com/studio/index.html#command-line-tools-only
wget \
  "https://dl.google.com/android/repository/commandlinetools-linux-"$SDK_VERSION"_latest.zip" \
  -O "$WORKSPACE/sdk.zip"

sha256sum "$WORKSPACE/sdk.zip" | cut -d ' ' -f 1
# TODO enforce verification

mkdir "$WORKSPACE/sdkroot"
unzip "$WORKSPACE/sdk.zip" -d "$WORKSPACE/sdkroot"
rm "$WORKSPACE/sdk.zip"
mv "$WORKSPACE/sdkroot/cmdline-tools" "$WORKSPACE/sdkroot/latest"
mkdir "$WORKSPACE/sdkroot/cmdline-tools"
mv "$WORKSPACE/sdkroot/latest" "$WORKSPACE/sdkroot/cmdline-tools"
export ANDROID_SDK_ROOT="$WORKSPACE/sdkroot"
"$WORKSPACE/sdkroot/cmdline-tools/latest/bin/sdkmanager" --install platform-tools "ndk;28.0.12674087" "build-tools;30.0.3"
export ANDROID_HOME="$ANDROID_SDK_ROOT"
export ANDROID_NDK_VERSION="28.0.12674087"
export ANDROID_NDK_HOME="$ANDROID_SDK_ROOT/ndk/$ANDROID_NDK_VERSION"
export JITPACK_NDK_VERSION="$ANDROID_NDK_VERSION"
# TODO direct dl w/o sdkmanager

# https://github.com/termux/termux-app/blob/master/.github/workflows/debug_build.yml
cd "$WORKSPACE/termux-app"
sed -i "s/22.1.7171670/$ANDROID_NDK_VERSION/" "$WORKSPACE/termux-app/gradle.properties"
gradle assembleDebug

