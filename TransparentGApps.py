__doc__ = """

# TransparentGApps

TransparentGApps is an easy to read and audit, single-file build script which builds a GApps OTA package using only files directly downloaded from Google. Docker is the only prerequisite for running TransparentGApps. TransparentGApps builds packages using files extracted from Google's official factory images. Exact disk usage will vary depending on the image you select but expect to need at least 8 GB of disk space free while building, though the final GApps package will only be about 120 MB.

By design, packages will only install on devices that match the factory image they were built from. TransparentGApps is designed to be a quick, easy and transparent way for you to build a GApps package for your own device. Please do not distribute packages built with TransparentGApps and please do not use any packages built TransparentGApps that you did not build yourself. If you are looking for prebuilt GApps packages, there are other, more mature projects which offer those such as MindTheGapps and [OpenGApps](https://opengapps.org).

## Usage

1. Download or checkout TransparentGApps.py then create a folder somewhere where you want your GApps package output

2. Run `docker run -v /path/to/mylocalfolder:/workspace -v /path/to/TransparentGApps.py:/TransparentGApps.py:ro --rm -it archlinux /bin/sh -c "pacman -Syu --noconfirm --needed python jre-openjdk p7zip;bash"` to open a shell with the required programs installed. Replace /path/to/mylocalfolder with your folder from the last step and /path/to/TransparentGApps.py with the path where you download or checked out TransparentGApps.py.

3. Go to https://developers.google.com/android/images and copy the download URL and checksum of the image that corresponds to your device.

4. Run the build script with `python /TransparentGApps.py https://dl.google.com/dl/android/aosp/husky-ud1a.230803.022.a3-factory-a95417f6.zip a95417f6ace90bb3ed39f86966bf9f32aad0505c29d5698dc19dddb9739f37bc /workspace/gapps.zip --clean`. Replace the URL and checksum with the ones you copied earlier.

5. Exit the shell when you are done. Your package will be in the local folder you created in step 1. If you encounter any issues, use the shell to debug them. You can rerun the script while omitting the `--clean` flag to avoid having the script delete files when it is done with them, however, note that this can use about 20 to 30 GB of disk space. You can run `python /TransparentGApps.py --help` to read the script's documentation.

6. (Optional but Recommended) Run `docker system prune --all` to remove all unused images and reclaim disk space that may have been used if an image was pulled when you opened the shell in Docker

## Notes

TransparentGApps is contained within a single Python script. This script can be run outside of Docker on any OS as long as you have Python, Java, 7Zip and libconscrypt installed.

TransparentGApps downloads three files from Google: the factory image you specify, a pre-built copy of signapk and a pre-built copy of libconscrypt. If you'd prefer, you may download or build these files yourself rather than letting the script handle it for you.

 - The factory images can be found at https://developers.google.com/android/images.
 - Pre-built copies of signapk can be found at https://android.googlesource.com/platform/prebuilts/sdk/+/refs/heads/main/tools/lib/signapk.jar and its source can be found at https://android.googlesource.com/platform/build/+/refs/heads/main/tools/signapk.
 - Linux builds of libconscrypt are at https://android.googlesource.com/platform/prebuilts/sdk/+/refs/heads/main/tools/linux/lib64. MacOS builds are at https://android.googlesource.com/platform/prebuilts/sdk/+/refs/heads/main/tools/darwin/lib64. If you are building outside of Docker on MacOS, you must manually download libconscrypt and use `--local-libconscrypt` (see below). The script will only automatically download the Linux version of libconscrypt. The source is at https://github.com/google/conscrypt. Google does not distribute pre-built Windows copies of libconscrypt. If you are on Windows, your easiest option is to just use Docker but you may also build conscrypt from source or download it from Maven per the documentation in the Github link.

The arguments `--local-signapk`, `--local-libconscrypt` and `--local-factory-image` can be used to skip downloading files and have the script use a local path instead. The factory image URL is a required argument, however, it will be ignored when `--local-factory-image` is specified. Below is an example of building a GApps package using pre-downloaded files for everything. This command will not make any connections to the internet:

    python /TransparentGApps.py None a95417f6ace90bb3ed39f86966bf9f32aad0505c29d5698dc19dddb9739f37bc /workspace/gapps.zip --clean --local-factory-image /workspace/factoryimg.zip --local-signapk /workspace/signapk.jar --local-libconscrypt /workspace/libconscrypt_openjdk_jni.so

For the sake of future-proofing, these instructions use Arch Linux as OpenJDK is a mainline package in Arch but is not in Alpine Linux. If you'd prefer to use Alpine, start the shell in step 2 with `docker run -v /path/to/mylocalfolder:/workspace -v /path/to/TransparentGApps.py:/TransparentGApps.py:ro --rm -it alpine /bin/sh -c "apk add --no-cache bash python3 openjdk17-jre p7zip;bash"` instead.

## Additional Packages

TransparentGApps builds packages with only the core packages needed to get the Google Services Framework and Play Store up and running. These packages are installed as privileged system apps. Other Google packages can be installed as needed as regular apps via the Play Store. Use the links below on your device to install any apps or services you need.

 - Google Search: https://play.google.com/store/apps/details?id=com.google.android.googlequicksearchbox
 - Google Maps: https://play.google.com/store/apps/details?id=com.google.android.apps.maps
 - Google Assistant: https://play.google.com/store/apps/details?id=com.google.android.apps.googleassistant
 - Android Auto: https://play.google.com/store/apps/details?id=com.google.android.projection.gearhead
 - AR Core: https://play.google.com/store/apps/details?id=com.google.ar.core
 - Google Play Games: https://play.google.com/store/apps/details?id=com.google.android.play.games
 - Google Fit: https://play.google.com/store/apps/details?id=com.google.android.apps.fitness
 - Google Docs: https://play.google.com/store/apps/details?id=com.google.android.apps.docs.editors.docs

"""

import sys, os, stat, base64, subprocess, hashlib, shutil, tempfile, zipfile, argparse, urllib.request

SIGNAPK_B64_URL = 'https://android.googlesource.com/platform/prebuilts/sdk/+/f615932a54ebd86546eabd569a168cf438395839/tools/lib/signapk.jar?format=TEXT'
SIGNAPK_HASH = 'a69eb22eee762489f8f96d3e62ecd1bf3b87aa2ac6db03fd504aca6a6a4b9a85'

LIBCONSCRYPT_B64_URL = 'https://android.googlesource.com/platform/prebuilts/sdk/+/f615932a54ebd86546eabd569a168cf438395839/tools/linux/lib64/libconscrypt_openjdk_jni.so?format=TEXT'
LIBCONSCRYPT_HASH = 'bce5119a499302cfd4279a77f66b0859f65d5d92cfe5289b935dd39d53956ef4'

# From https://android.googlesource.com/platform/build/+/refs/heads/main/target/product/security/testkey.pk8
# Converted from binary to base64
TESTKEY_PK8 = """
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDWkxkE3sYLJLHtx2Lg2dglPj7NbOs
d4v8GjKjovKjNa9N4bqcKp2zmDrsPmTVZ/9k+d6lD5+g9S2S45P6i0+ZW8eJnqBu/sjC1eMIEQ75Mch
i4RvUhFYbwOKFOicK+OH+Ovs+PysPaHuMwyeqT0KfD3ErzUCINUAgHMuCAlxfuagUzWeamlOwss/KEo
KRmyHqU2DsxCTpnNy4vZBLAbm1C8VgY3/4DgcwM1ETabN3DuCRYGUgBsyVkE0+/3pjJKHdI2/VnalQN
gVTIu8oHueJHVTMRxGua92/e7MyOaefIotCOeCYglD+Zcn08BP5ymR2Z35uuOKCyF3+jHVtq/ukfAgE
DAoIBAQCPDLtYlIQHbcvz2kHrO+VuKX8znfIT7KoEXcXwfcXeR+JQScSxxPNECdIKZiORVTt++nDX7/
Ao3O3QmKnB4pmPS+xFGr0qdssjpdatgn7doWXQL04WDln1exY0W9cpev+0fzUKhy08FJd12/G34G/X6
DH3isFeNVqvd0BVug/0RXWihnmONcUztAJ25E5YNqHadWSt+vU4pJOpvxDyE6ZXrBIpHBvlaZf8atJ7
maf8iXfSZUzrqnx1O5zaTGRnGo7o/UdrfuLDfpVXnXBEHm+rk6QTq2ZKyZj6JZQ/K1LB+cXqZO9KG8o
BSecXohQBeJYIDEikB9xHdsvelr1MoYR7AoGBAOrAmRccm5UnjAe/npdFGIVXkXaep7Ur9rqT4NaoSM
SnDRim6Kii2lNoZ2szvvKYuxRNmvi1u60iRvQsLM10duqyG+FKdx+S5632ALWTKvdH97l3VYcRCrDYA
yMYdotYavF8bcT9QKgYHoWHb18KLL27A4afIXmrVXCnWXp1e2GbAoGBAOn+9xk0qK83mecSq5edXgJ1
lq2NaRVmSZYc5KKtCC8YYiQ0TSuIiRSpzJ3tR28wLtxO5lvqd72R8vBMPzS6CbY5RCj7tOBVW8bPTuw
OYUN+AAN87csZvlmPsUsXMmBNQTYycvo0Keh/ZR0RIoFmN37SyagZC1ybj90t4cUCkUDNAoGBAJyAZg
9oZ7jFCAUqabouEFjlC6RpxSNypHxileRwMIMaCLsZ8HBskYzwRPIif0xl0g2JEfsj0nNsL01yyIj4T
0chZ+uG+hUMmnP5Vc5iHKTapSZPjloLXHXlV2y6+bI68fZS89io1cVlaa5aSj9cHdPSAlm/a6ZyOPXE
5lGjp5ZnAoGBAJv/T2YjGx96ZpoMcmUTlAGjuckI8Lju27lomGxzWsoQQW14M3JbBg3GiGlI2kogHz2
J7ufxpSkL90rdf3h8Bnl7gsX9I0A459nfifK0QNepVVeonodmfuZfy4dkzEAzgM7MTKbNcUWqQ2i2Fw
Duz6nh28VmB5MSX+jJQS4BtiszAoGAYyqt2RrdpGLZlaZyYlsFzalGIfTpWXPuj5ot63Ghwawb0xoN1
qKJdYcbanvrblVhtKEsYKOkae96d1grNcf4Vbm3bMrPwHdIRf6pRS+x46mMBfuap1JoGcXESY4Nwdsb
pYo71PuBgykeNHaO2nq0BYcm/RyNFHuJZd+PFfOevDc=
"""

# From https://android.googlesource.com/platform/build/+/refs/heads/main/target/product/security/testkey.x509.pem
TESTKEY_X509_PEM = """
-----BEGIN CERTIFICATE-----
MIIEqDCCA5CgAwIBAgIJAJNurL4H8gHfMA0GCSqGSIb3DQEBBQUAMIGUMQswCQYD
VQQGEwJVUzETMBEGA1UECBMKQ2FsaWZvcm5pYTEWMBQGA1UEBxMNTW91bnRhaW4g
VmlldzEQMA4GA1UEChMHQW5kcm9pZDEQMA4GA1UECxMHQW5kcm9pZDEQMA4GA1UE
AxMHQW5kcm9pZDEiMCAGCSqGSIb3DQEJARYTYW5kcm9pZEBhbmRyb2lkLmNvbTAe
Fw0wODAyMjkwMTMzNDZaFw0zNTA3MTcwMTMzNDZaMIGUMQswCQYDVQQGEwJVUzET
MBEGA1UECBMKQ2FsaWZvcm5pYTEWMBQGA1UEBxMNTW91bnRhaW4gVmlldzEQMA4G
A1UEChMHQW5kcm9pZDEQMA4GA1UECxMHQW5kcm9pZDEQMA4GA1UEAxMHQW5kcm9p
ZDEiMCAGCSqGSIb3DQEJARYTYW5kcm9pZEBhbmRyb2lkLmNvbTCCASAwDQYJKoZI
hvcNAQEBBQADggENADCCAQgCggEBANaTGQTexgskse3HYuDZ2CU+Ps1s6x3i/waM
qOi8qM1r03hupwqnbOYOuw+ZNVn/2T53qUPn6D1LZLjk/qLT5lbx4meoG7+yMLV4
wgRDvkxyGLhG9SEVhvA4oU6Jwr44f46+z4/Kw9oe4zDJ6pPQp8PcSvNQIg1QCAcy
4ICXF+5qBTNZ5qaU7Cyz8oSgpGbIepTYOzEJOmc3Li9kEsBubULxWBjf/gOBzAzU
RNps3cO4JFgZSAGzJWQTT7/emMkod0jb9WdqVA2BVMi7yge54kdVMxHEa5r3b97s
zI5p58ii0I54JiCUP5lyfTwE/nKZHZnfm644oLIXf6MdW2r+6R8CAQOjgfwwgfkw
HQYDVR0OBBYEFEhZAFY9JyxGrhGGBaR0GawJyowRMIHJBgNVHSMEgcEwgb6AFEhZ
AFY9JyxGrhGGBaR0GawJyowRoYGapIGXMIGUMQswCQYDVQQGEwJVUzETMBEGA1UE
CBMKQ2FsaWZvcm5pYTEWMBQGA1UEBxMNTW91bnRhaW4gVmlldzEQMA4GA1UEChMH
QW5kcm9pZDEQMA4GA1UECxMHQW5kcm9pZDEQMA4GA1UEAxMHQW5kcm9pZDEiMCAG
CSqGSIb3DQEJARYTYW5kcm9pZEBhbmRyb2lkLmNvbYIJAJNurL4H8gHfMAwGA1Ud
EwQFMAMBAf8wDQYJKoZIhvcNAQEFBQADggEBAHqvlozrUMRBBVEY0NqrrwFbinZa
J6cVosK0TyIUFf/azgMJWr+kLfcHCHJsIGnlw27drgQAvilFLAhLwn62oX6snb4Y
LCBOsVMR9FXYJLZW2+TcIkCRLXWG/oiVHQGo/rWuWkJgU134NDEFJCJGjDbiLCpe
+ZTWHdcwauTJ9pUbo8EvHRkU3cYfGmLaLfgn9gP+pWA7LFQNvXwBnDa6sppCccEX
31I828XzgXpJ4O+mDL1/dBd+ek8ZPUP0IgdyZm5MTYPhvVqGCHzzTy3sIeJFymwr
sBbmg2OAUNLEMO6nwmocSdN2ClirfxqCzJOLSDE4QyS9BAH6EhY6UFcOaE0=
-----END CERTIFICATE-----
"""

UPDATE_BINARY_TEMPLATE = """
#!/sbin/sh

EDIFYFD="/proc/self/fd/RD_2"
OTAZIP=RD_3

ui_print() {
  echo "ui_print RD_1
    ui_print" >> RD_EDIFYFD
}

teardown() {
  rm -rf "RD_WORKSPACEDIR"
}

die() {
  ui_print "RD_1"
  teardown
  exit 1
}

DEVICE=RD_(getprop ro.build.product)
if REPL_DEVICE_CHECK_EXPRESSION ; then
  die "Device model mismatch! Expected: REPL_DEVICES, Found: RD_DEVICE"
fi

# TODO: Handle cases where system_ext and product aren't present or aren't mounted
#       For now, we can assume they're present since they're in the factory image
#       and we already checked that the device matches the factory image

ui_print " -= Debug Partitions =- "
if [ -d "/system/product" ]; then
  ui_print "/system/product exists"
else
  ui_print "/system/product does not exist"
fi
mount "/system/product"
if [ RD_? -eq 0 ]; then
  ui_print "/system/product is a mount point"
else
  ui_print "/system/product is not a mount point"
fi
if [ -d "/system/system_ext" ]; then
  ui_print "/system/system_ext exists"
else
  ui_print "/system/system_ext does not exist"
fi
mount "/system/system_ext"
if [ RD_? -eq 0 ]; then
  ui_print "/system/system_ext is a mount point"
else
  ui_print "/system/system_ext is not a mount point"
fi
exit 1

ui_print "Creating temporary workspace"
WORKSPACEDIR=/tmp/ws
mkdir -p "RD_WORKSPACEDIR"

ui_print "Unzipping OTA package to workspace"
unzip "RD_OTAZIP" -d "RD_WORKSPACEDIR"

ui_print "Setting permissions"
REPL_SET_PERMS_CODE

ui_print "Setting up addon.d script"
REPL_ADDOND_CODE

if REPL_HAS_PRODUCT_PARTITION; then
  ui_print "Moving files to product partition"
  mv "RD_{WORKSPACEDIR}/system/product/*" "/system/product"
  rmdir "RD_{WORKSPACEDIR}/system/product"
fi

if REPL_HAS_SYSTEM_EXT_PARTITION; then
  ui_print "Moving files to system_ext partition"
  mv "RD_{WORKSPACEDIR}/system_ext/*" "/system/system_ext"
  rmdir "RD_{WORKSPACEDIR}/system/system_ext"
fi

ui_print "Moving files to system partition"
mv "RD_{WORKSPACEDIR}/system/*" "/system"

ui_print "Done!"
teardown
exit 0
"""


ADDOND_SCRIPT_PATH = '/system/addon.d/31-gapps.sh'

ADDOND_SCRIPT_START = """
#!/sbin/sh
#
# ADDOND_VERSION=3
#
# /system/addon.d/31-gapps.sh
#

. /tmp/backuptool.functions

list_files() {
cat <<EOF
"""

# addon.d Script Reference:
#  https://github.com/LineageOS/android_vendor_lineage/tree/lineage-20.0/prebuilt/common/bin
#  C=/tmp/backupdir
#  S=SYSMOUNT/system

ADDOND_SCRIPT_END = """
EOF
}

case "RD_1" in
  backup)
    list_files | while read FILEPATH UNUSED; do
      backup_file RD_S/RD_FILEPATH
    done
  ;;
  restore)
    list_files | while read FILEPATH UNUSED; do
      [ -f "RD_C/RD_S/RD_FILEPATH" ] && restore_file RD_S/RD_FILEPATH
    done
  ;;
  pre-backup)
    # NOP
  ;;
  post-backup)
    # NOP
  ;;
  pre-restore)
    # NOP
  ;;
  post-restore)
    for i in RD_(list_files); do
      f=RD_(get_output_path "RD_S/RD_i")
      chown root:root RD_f
      chmod 0644 RD_f
      chmod 0755 RD_(dirname RD_f)
    done
  ;;
esac
"""

UPDATE_SCRIPT_TEMPLATE = '# See update-binary'

# TODO: Populate this
# (keys are a device name from a factory image, values are a list of device names for devices compatible with that image)
COMPATIBLE_IMAGES = {

}

# Newline, stored as a variable since unescaped backslashes can't be used in a heredoc
nl = chr(10)

parser = argparse.ArgumentParser(description='TransparentGApps is an easy to read and audit, single-file build script which builds a GApps OTA package using only files directly downloaded from Google.' + nl +
                                             'Factory image urls and checksums can be found at https://developers.google.com/android/images '+ nl + nl +
                                             'example: python TransparentGApps.py https://dl.google.com/dl/android/aosp/husky-ud1a.230803.022.a3-factory-a95417f6.zip a95417f6ace90bb3ed39f86966bf9f32aad0505c29d5698dc19dddb9739f37bc gapps.zip' + nl,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('url', help='the URL of the factory image')
parser.add_argument('checksum', help='the expected checksum of the factory image')
parser.add_argument('output', help='the file name to use for the output OTA package')
parser.add_argument('-s', '--silent', action='store_true', help='suppresses all output from the script')
parser.add_argument('-c', '--clean', action='store_true', help='deletes temporary files as soon as they are no longer needed which uses less disk space but makes issues harder to debug')
parser.add_argument('--local-signapk', help='the path of a local copy of signapk.jar, skips downloading the file')
parser.add_argument('--local-libconscrypt', help='the path of a local copy of libconscrypt, skips downloading the file')
parser.add_argument('--local-factory-image', help='the path of a local copy of the factory image, skips downloading the file')
args = parser.parse_args()

def sprint(*a):
  if not args.silent:
    print(*a)

def hash(path):
  h = hashlib.sha256()
  with open(path, 'rb') as f:
    while True:
      buf = f.read(1024)
      if not buf:
        return h.hexdigest().lower()
      h.update(buf)

if not shutil.which('java'): raise Exception("Can't find Java")
if not shutil.which('7z'): raise Exception("Can't find 7z")
if os.path.exists(args.output): raise FileExistsError(args.output)

TROOT = tempfile.mkdtemp(prefix='transparentgapps_')
sprint('Created temporary workspace:', TROOT)

if args.local_signapk:
  sprint('Using local signapk')
  signapk_path = args.local_signapk
else:
  sprint('Downloading signapk from Google')
  req = urllib.request.urlopen(SIGNAPK_B64_URL)
  b64 = req.read()
  signapk_path = os.path.join(TROOT, 'signapk.jar')
  with open(signapk_path, 'wb') as f:
    f.write(base64.b64decode(b64))
if hash(signapk_path) != SIGNAPK_HASH:
  raise Exception('signapk.jar hash mismatch')

libconscrypt_path = os.path.join(TROOT, 'libconscrypt_openjdk_jni.so')
if args.local_libconscrypt:
  sprint('Using local libconscrypt')
  shutil.copy(args.local_libconscrypt, libconscrypt_path)
else:
  sprint('Downloading libconscrypt from Google')
  req = urllib.request.urlopen(LIBCONSCRYPT_B64_URL)
  b64 = req.read()
  with open(libconscrypt_path, 'wb') as f:
    f.write(base64.b64decode(b64))
st = os.stat(libconscrypt_path)
os.chmod(libconscrypt_path, st.st_mode | stat.S_IEXEC)
if hash(libconscrypt_path) != LIBCONSCRYPT_HASH:
  raise Exception('libconscrypt_openjdk_jni.so hash mismatch')

if args.local_factory_image:
  sprint('Using local factory image')
  factoryimg_path = args.local_factory_image
else:
  sprint('Downloading factory image')
  downloaded_bytes = 0
  chars_to_del = 0
  factoryimg_path = os.path.join(TROOT, 'factoryimg.zip')
  req = urllib.request.urlopen(args.url)
  total_bytes = int(req.getheader('content-length'))
  with open(factoryimg_path, 'xb') as f:
    while True:
      buf = req.read(1024**2)
      if not buf:
        break
      f.write(buf)
      downloaded_bytes += len(buf)
      if not args.silent:
        prog = '{} bytes of {} bytes ({:.2f}%)'.format(downloaded_bytes, total_bytes, 100*downloaded_bytes/total_bytes)
        sys.stdout.write((chr(8)*chars_to_del) + prog)
        chars_to_del = len(prog)
        sys.stdout.flush()
  if not args.silent:
    sys.stdout.write((chr(8)*chars_to_del)+(' '*chars_to_del)+(chr(8)*chars_to_del))
    sys.stdout.flush()

sprint('Verifying factory image')
if hash(factoryimg_path) != args.checksum.lower():
  raise Exception('factory image checksum mismatch')

sprint('Extracting factory image')
subprocess.run(['7z', 'x', factoryimg_path, '-o'+TROOT], check=True, capture_output=args.silent)
if args.clean and not args.local_factory_image:
  os.remove(factoryimg_path)

sprint('Extracting partition images from factory image')
factoryimg_dir = list(filter(os.path.isdir, map(lambda f: os.path.join(TROOT, f), os.listdir(TROOT))))[0]
partszip = os.path.join(factoryimg_dir, list(filter(lambda i: i.endswith('.zip'), os.listdir(factoryimg_dir)))[0])
subprocess.run(['7z', 'x', partszip, '-o'+TROOT], check=True, capture_output=args.silent)
if args.clean:
  shutil.rmtree(factoryimg_dir)

sprint('Creating output OTA package')
ota_package = zipfile.ZipFile(os.path.join(TROOT, 'ota_package.zip'), 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9)

def ensure_partition_extracted(partition_name):
  extracted_path = os.path.join(TROOT, 'extracted_'+partition_name)
  if not os.path.exists(extracted_path):
    sprint('Extracting partition:', partition_name)
    os.mkdir(extracted_path)
    partition_img = os.path.join(TROOT, partition_name+'.img')
    subprocess.run(['7z', 'x', partition_img, '-o'+extracted_path], check=True, capture_output=args.silent)
    if args.clean:
      os.remove(partition_img)
  return extracted_path

def copy_file_from_partition_to_ota_package(partition_name, source_path, destination_path):
  extracted_path = ensure_partition_extracted(partition_name)
  sprint('Copying', source_path, 'from', partition_name)
  ota_package.write(os.path.join(extracted_path, source_path), destination_path)

def has_partition(partition_name):
  partition_img = os.path.join(TROOT, partition_name+'.img')
  if os.path.exists(partition_img):
    return True
  extracted_path = os.path.join(TROOT, 'extracted_'+partition_name)
  return os.path.exists(extracted_path)

def has_path_in_partition(partition_name, path_to_test):
  if not has_partition(partition_name):
    return False
  extracted_path = ensure_partition_extracted(partition_name)
  return os.path.exists(os.path.join(extracted_path, path_to_test))

# TODO: Use has_path_in_partition to choose the appropriate files to include based on
#       the factory image. Currently only husky (Pixel 8 Pro) images are officially
#       supported. If you get a FileNotFound error around here, you're probably using
#       an incompatible image and the script will need to be updated to support your image.

sprint('Copying files from partitions to the OTA package')

# copy_file_from_partition_to_ota_package('product',
#                                         'app/MarkupGoogle/MarkupGoogle.apk',
#                                         'system/product/app/MarkupGoogle/MarkupGoogle.apk')

# copy_file_from_partition_to_ota_package('product',
#                                         'app/talkback/talkback.apk',
#                                         'system/product/app/talkback/talkback.apk')

copy_file_from_partition_to_ota_package('product',
                                        'etc/permissions/com.google.android.dialer.support.xml',
                                        'system/product/etc/permissions/com.google.android.dialer.support.xml')

copy_file_from_partition_to_ota_package('product',
                                        'etc/security/fsverity/gms_fsverity_cert.der',
                                        'system/product/etc/security/fsverity/gms_fsverity_cert.der')

copy_file_from_partition_to_ota_package('product',
                                        'etc/sysconfig/google.xml',
                                        'system/product/etc/sysconfig/google.xml')

copy_file_from_partition_to_ota_package('product',
                                        'etc/sysconfig/google_build.xml',
                                        'system/product/etc/sysconfig/google_build.xml')

copy_file_from_partition_to_ota_package('product',
                                        'framework/com.google.android.dialer.support.jar',
                                        'system/product/framework/com.google.android.dialer.support.jar')

copy_file_from_partition_to_ota_package('product',
                                        'priv-app/PrebuiltGmsCore/PrebuiltGmsCoreSc.apk',
                                        'system/product/priv-app/PrebuiltGmsCore/PrebuiltGmsCoreSc.apk')

copy_file_from_partition_to_ota_package('product',
                                        'priv-app/PrebuiltGmsCore/app_chimera/m/PrebuiltGmsCoreSc_AdsDynamite.apk',
                                        'system/product/priv-app/PrebuiltGmsCore/app_chimera/m/PrebuiltGmsCoreSc_AdsDynamite.apk')

copy_file_from_partition_to_ota_package('product',
                                        'priv-app/PrebuiltGmsCore/app_chimera/m/PrebuiltGmsCoreSc_CronetDynamite.apk',
                                        'system/product/priv-app/PrebuiltGmsCore/app_chimera/m/PrebuiltGmsCoreSc_CronetDynamite.apk')

copy_file_from_partition_to_ota_package('product',
                                        'priv-app/PrebuiltGmsCore/app_chimera/m/PrebuiltGmsCoreSc_DynamiteLoader.apk',
                                        'system/product/priv-app/PrebuiltGmsCore/app_chimera/m/PrebuiltGmsCoreSc_DynamiteLoader.apk')

copy_file_from_partition_to_ota_package('product',
                                        'priv-app/PrebuiltGmsCore/app_chimera/m/PrebuiltGmsCoreSc_DynamiteModulesA.apk',
                                        'system/product/priv-app/PrebuiltGmsCore/app_chimera/m/PrebuiltGmsCoreSc_DynamiteModulesA.apk')

copy_file_from_partition_to_ota_package('product',
                                        'priv-app/PrebuiltGmsCore/app_chimera/m/PrebuiltGmsCoreSc_DynamiteModulesC.apk',
                                        'system/product/priv-app/PrebuiltGmsCore/app_chimera/m/PrebuiltGmsCoreSc_DynamiteModulesC.apk')

copy_file_from_partition_to_ota_package('product',
                                        'priv-app/PrebuiltGmsCore/app_chimera/m/PrebuiltGmsCoreSc_GoogleCertificates.apk',
                                        'system/product/priv-app/PrebuiltGmsCore/app_chimera/m/PrebuiltGmsCoreSc_GoogleCertificates.apk')

copy_file_from_partition_to_ota_package('product',
                                        'priv-app/PrebuiltGmsCore/app_chimera/m/PrebuiltGmsCoreSc_MapsDynamite.apk',
                                        'system/product/priv-app/PrebuiltGmsCore/app_chimera/m/PrebuiltGmsCoreSc_MapsDynamite.apk')

copy_file_from_partition_to_ota_package('product',
                                        'priv-app/PrebuiltGmsCore/app_chimera/m/PrebuiltGmsCoreSc_MeasurementDynamite.apk',
                                        'system/product/priv-app/PrebuiltGmsCore/app_chimera/m/PrebuiltGmsCoreSc_MeasurementDynamite.apk')

copy_file_from_partition_to_ota_package('product',
                                        'priv-app/PrebuiltGmsCore/m/independent/AndroidPlatformServices.apk',
                                        'system/product/priv-app/PrebuiltGmsCore/m/independent/AndroidPlatformServices.apk')

copy_file_from_partition_to_ota_package('product',
                                        'priv-app/PrebuiltGmsCore/m/optional/MlkitBarcodeUIPrebuilt.apk',
                                        'system/product/priv-app/PrebuiltGmsCore/m/optional/MlkitBarcodeUIPrebuilt.apk')

copy_file_from_partition_to_ota_package('product',
                                        'priv-app/PrebuiltGmsCore/m/optional/VisionBarcodePrebuilt.apk',
                                        'system/product/priv-app/PrebuiltGmsCore/m/optional/VisionBarcodePrebuilt.apk')

copy_file_from_partition_to_ota_package('product',
                                        'priv-app/Phonesky/Phonesky.apk',
                                        'system/product/priv-app/Phonesky/Phonesky.apk')

copy_file_from_partition_to_ota_package('system_ext',
                                        'priv-app/GoogleServicesFramework/GoogleServicesFramework.apk',
                                        'system/product/priv-app/GoogleServicesFramework/GoogleServicesFramework.apk')

copy_file_from_partition_to_ota_package('system',
                                        'system/bin/toybox',
                                        'toybox')

sprint('Reading expected device name from factory image')
with open(os.path.join(TROOT, 'extracted_system/system/build.prop'), 'r') as f:
  device_name = [i[17:] for i in filter(lambda l: l.startswith('ro.build.product='), f.read().splitlines())][0]

sprint('Writing update-binary to OTA package')
addond_script = ADDOND_SCRIPT_START.lstrip() + nl.join(('/'+f for f in ota_package.namelist())) + ADDOND_SCRIPT_END
addond_script = nl.join(('echo "'+l+ ('" > ' if i == 0 else '" >> ') + ADDOND_SCRIPT_PATH for i,l in enumerate(addond_script.splitlines())))
supported_devices = [device_name] + COMPATIBLE_IMAGES.get(device_name, [])
device_check_expression = ' && '.join(('[ RD_DEVICE -ne "' + d + '" ]' for d in supported_devices))
ota_package.writestr('META-INF/com/google/android/update-binary',
                     UPDATE_BINARY_TEMPLATE
                      .replace('REPL_DEVICE_CHECK_EXPRESSION', device_check_expression)
                      .replace('REPL_DEVICES', ' or '.join(supported_devices))
                      .replace('REPL_SET_PERMS_CODE', nl.join(('RD_WORKSPACEDIR/toybox chmod 0644 RD_WORKSPACEDIR/'+f for f in ota_package.namelist())))
                      .replace('REPL_ADDOND_CODE', addond_script)
                      .replace('REPL_HAS_PRODUCT_PARTITION', 'true' if has_partition('product') else 'false')
                      .replace('REPL_HAS_SYSTEM_EXT_PARTITION', 'true' if has_partition('system_ext') else 'false')
                      .replace('RD_', chr(36)) # Dollar signs are escaped so Docker won't try to interpret them as variables in a heredoc
                      .lstrip()
                      .encode())

sprint('Writing update-script to OTA package')
ota_package.writestr('META-INF/com/google/android/update-script',
                     UPDATE_SCRIPT_TEMPLATE.encode())

sprint('Signing OTA package')
ota_package.close()
PK8_PATH = os.path.join(TROOT, 'testkey.pk8')
with open(PK8_PATH, 'wb') as f:
  f.write(base64.b64decode(''.join(TESTKEY_PK8.split())))
PEM_PATH = os.path.join(TROOT, 'testkey.x509.pem')
with open(PEM_PATH, 'w', encoding='utf8') as f:
  f.write(TESTKEY_X509_PEM.strip())
subprocess.run(['java', '-Xmx2048m', '-Djava.library.path='+os.path.dirname(libconscrypt_path),
                '-jar', signapk_path, '-w', PEM_PATH, PK8_PATH, ota_package.filename, args.output], check=True, capture_output=args.silent)

if args.clean:
  shutil.rmtree(TROOT)
