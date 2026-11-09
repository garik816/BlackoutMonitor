#!/bin/sh
# One-time personal feed subscription for OpenWrt 25.12 x86_64.
set -eu
BASE='https://garik816.github.io/BlackoutMonitor'
KEY='/etc/apk/keys/blackout-monitor.pem'
FEED='/etc/apk/repositories.d/blackout-monitor.list'
command -v apk >/dev/null 2>&1 || { echo 'Requires OpenWrt 25.12+ with apk' >&2; exit 1; }
arch="$(apk --print-arch)"
[ "$arch" = x86_64 ] || { echo "Only x86_64 is published (detected $arch)" >&2; exit 1; }
mkdir -p /etc/apk/keys /etc/apk/repositories.d /lib/upgrade/keep.d
tmp="/tmp/blackout-monitor-pubkey.$$"
trap 'rm -f "$tmp"' EXIT HUP INT TERM
wget -q -O "$tmp" "$BASE/keys/blackout-monitor.pem"
[ -s "$tmp" ] || { echo 'Public key download failed' >&2; exit 1; }
cp "$tmp" "$KEY"
chmod 0644 "$KEY"
printf '%s\n' "$BASE/releases/25.12/$arch/packages.adb" > "$FEED"
cat > /lib/upgrade/keep.d/blackout-monitor-feed <<'KEEP'
/etc/apk/keys/blackout-monitor.pem
/etc/apk/repositories.d/blackout-monitor.list
KEEP
apk update
echo 'Ready: install luci-app-blackout-monitor via LuCI > System > Software.'
