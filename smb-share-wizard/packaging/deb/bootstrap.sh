#!/bin/sh
# One-line install: curl -fsSL <raw-url-to-this-file> | sh
#
# Downloads the current Kelpie source from GitHub, builds the .deb fresh,
# and runs the normal install.sh - this only automates *fetching* the
# files, it doesn't skip install.sh's own preview/confirmation step.
set -e

REPO_URL="https://github.com/listercreative/Kelpie.git"
TARBALL_URL="https://github.com/listercreative/Kelpie/archive/refs/heads/main.tar.gz"

if ! command -v git >/dev/null 2>&1 && ! command -v curl >/dev/null 2>&1; then
    echo "Need either git or curl installed to download Kelpie." >&2
    exit 1
fi

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

echo "Downloading Kelpie..."
if command -v git >/dev/null 2>&1; then
    git clone --depth 1 "$REPO_URL" "$TMPDIR/Kelpie" >/dev/null 2>&1
    REPO_DIR="$TMPDIR/Kelpie"
else
    curl -fsSL "$TARBALL_URL" | tar -xz -C "$TMPDIR"
    REPO_DIR="$TMPDIR/Kelpie-main"
fi

cd "$REPO_DIR/smb-share-wizard/packaging/deb"
./build.sh

# < /dev/tty explicitly: this script may itself have been invoked as
# `curl | sh`, in which case stdin is the piped script source, not the
# terminal - install.sh needs the real terminal for its preview screen and
# y/N prompt, same reason postinst redirects the same way.
./install.sh < /dev/tty > /dev/tty 2> /dev/tty
