#!/bin/sh

# A simple script which uses uploadserver to enable easily and securely sharing
# files directly between two devices using https. It is useful for sharing
# files with devices you can't or don't want to install file sharing software
# on, such as game consoles or smart appliances.

# The script creates a temporary directory, generates a new certificate,
# displays the fingerprints of the certificate and your local IP and starts an
# instance of uploadserver. Run the script, then open https://192.168.0.2:9062
# on your other device with 192.168.0.2 replaced with your local IP and 9062
# replaced with the port, both of which the script will display. Opening this
# URL on the device should result in a security warning. Most browsers will
# have a button to the left of the location bar which can be used to view the
# page's certificate. Verify that the fingerprint(s) displayed in the
# certificate's properties match the fingerprints displayed by the script then,
# once you're sure they match, select to ignore the warning. With that done,
# the page will allow you to upload/download files to/from the server. Files to
# be shared go in $UPLOADSERVERTEMPDIR/www so place/look for shared files
# there.

# Requires: python, openssl and
#           uploadserver (https://pypi.org/project/uploadserver)

PORT="${PORT:-9062}"
UPLOADSERVERTEMPDIR="${UPLOADSERVERTEMPDIR:-"/tmp/uploadservertemp"}"

mkdir -p "$UPLOADSERVERTEMPDIR/www"
pushd "$UPLOADSERVERTEMPDIR"
openssl req -x509 -out server.pem -keyout server.pem -newkey rsa:2048 -nodes -sha256 -subj '/CN=server'
printf '\n\nCertificate Fingerprint:\n'
openssl x509 -fingerprint -sha256 -noout -in server.pem
printf '\n\nPublic Key Fingerprint:\n'
openssl pkey -pubin -in server.pem | sed '1d;$d' | base64 -d | openssl sha256
type firewall-cmd >/dev/null 2>/dev/null && firewall-cmd --add-port=$PORT/tcp
cd www
printf '\n\nLocal IP:\n'
ip addr | grep inet
python3 -m uploadserver $PORT --server-certificate ../server.pem
# type firewall-cmd >/dev/null 2>/dev/null && firewall-cmd --reload
popd
