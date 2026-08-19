#!/bin/sh
# Rebuild kelpie_0.1.0_all.deb from current source. Run from anywhere;
# paths are resolved relative to this script's location.
#
# Requires: dpkg-deb (part of the base `dpkg` package on any Debian/Ubuntu
# system - nothing extra to install).
set -e

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PROJECT_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
SRC="$PROJECT_ROOT/src"
PKG="$SCRIPT_DIR/kelpie"
PKGLIB="$PKG/usr/lib/kelpie"

cp "$SRC/main.py" "$SRC/core.py" "$SRC/cli.py" "$SRC/gui.py" "$SRC/tui.py" "$SRC/kelpie_icon.png" "$PKGLIB/"
cp "$PROJECT_ROOT/assets/kelpie_icon.png" "$PKG/usr/share/pixmaps/kelpie.png"

find "$PKG" -type d -exec chmod 755 {} \;
chmod 644 "$PKGLIB"/*.py "$PKGLIB/kelpie_icon.png"
chmod 755 "$PKG/DEBIAN/postinst" "$PKG/usr/bin/kelpie"
chmod 644 "$PKG/DEBIAN/control" \
          "$PKG/usr/share/applications/kelpie.desktop" \
          "$PKG/usr/share/doc/kelpie/copyright" \
          "$PKG/usr/share/pixmaps/kelpie.png"
chmod +x "$SCRIPT_DIR/install.sh"
chmod 644 "$SCRIPT_DIR/preview.py"

dpkg-deb --build --root-owner-group "$PKG" "$SCRIPT_DIR/kelpie_0.1.0_all.deb"
echo "Built $SCRIPT_DIR/kelpie_0.1.0_all.deb"
