#!/bin/sh
# Shows Kelpie's own terminal UI (banner + arrow-key menu) to explain what's
# about to be installed, BEFORE apt is invoked at all - this is the only
# way to run our UI ahead of apt's own dependency-resolution summary, since
# no .deb-internal hook (preinst included) fires before apt starts.
set -e

# This installer only actually has one real package built: the .deb (see
# build.sh). Detect the distro via /etc/os-release (the standard, portable
# way - present on virtually every modern Linux distro) and refuse cleanly
# on anything outside the Debian/Ubuntu family, rather than blindly running
# `apt`/`dpkg` on a system that may not even have them and failing with a
# confusing error partway through.
DISTRO_ID=""
DISTRO_LIKE=""
if [ -f /etc/os-release ]; then
    DISTRO_ID=$(. /etc/os-release && echo "$ID")
    DISTRO_LIKE=$(. /etc/os-release && echo "$ID_LIKE")
fi
case " $DISTRO_ID $DISTRO_LIKE " in
    *" debian "*|*" ubuntu "*) ;;
    *)
        echo "This installer only supports Debian/Ubuntu-family distros (it installs a .deb via apt)." >&2
        echo "Detected: ${DISTRO_ID:-unknown}${DISTRO_LIKE:+ (like: $DISTRO_LIKE)}" >&2
        echo "Kelpie isn't packaged for this distro yet - see ../../src/main.py to run it directly with Python 3." >&2
        exit 1
        ;;
esac

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
DEB_PATH="$SCRIPT_DIR/kelpie_0.1.0_all.deb"

if [ ! -f "$DEB_PATH" ]; then
    echo "Could not find $DEB_PATH — build it first: $SCRIPT_DIR/build.sh" >&2
    exit 1
fi

if [ -t 0 ] && [ -t 1 ] && command -v python3 >/dev/null 2>&1; then
    python3 "$SCRIPT_DIR/preview.py"
    status=$?
else
    status=2
fi

if [ "$status" = 1 ]; then
    echo "Cancelled. Nothing was installed."
    exit 0
fi

if [ "$status" = 2 ]; then
    echo
    echo "=== Kelpie installer ==="
    echo
    echo "This will install:"
    echo "  - kelpie   (the SMB share wizard itself)"
    echo "  - samba    (the SMB/CIFS file-sharing server, pulled in automatically)"
    echo
    echo "Each time you create a share through Kelpie, it will also, on this"
    echo "machine, with your permission at that point:"
    echo "  - create a dedicated Linux system user per configured Samba user"
    echo "  - create a dedicated Unix group for that share"
    echo "  - write a new share block into /etc/samba/smb.conf"
    echo "  - restart the Samba services"
    echo
    printf 'Continue with installing kelpie and samba? [y/N] '
    read -r answer
    case "$answer" in
        [yY]|[yY][eE][sS]) ;;
        *) echo "Cancelled. Nothing was installed."; exit 0 ;;
    esac
fi

if dpkg -s kelpie >/dev/null 2>&1; then
    echo
    echo "Kelpie is already installed - removing it first for a clean reinstall..."
    sudo apt-get remove -y kelpie
    # apt won't remove this directory itself if anything untracked (like
    # Python's __pycache__) got left in it after install - clear it so the
    # reinstall below starts from nothing rather than picking up stale files.
    sudo rm -rf /usr/lib/kelpie
fi

# apt's download sandbox runs as the unprivileged _apt user, which can't
# read into an arbitrary user's home directory if it's not world-traversable
# (e.g. a `750` $HOME, which is a perfectly reasonable thing to have) - apt
# falls back to fetching as root when that happens, but that fallback can
# still hit the same permission wall and fail outright ("pkgAcquire::Run
# (13: Permission denied)"). Stage the .deb somewhere universally readable
# instead of asking anyone to loosen their home directory just to install
# this.
STAGE_DEB=$(mktemp /tmp/kelpie-install-XXXXXX.deb)
cp "$DEB_PATH" "$STAGE_DEB"
chmod 644 "$STAGE_DEB"
trap 'rm -f "$STAGE_DEB"' EXIT

sudo apt install --reinstall -y "$STAGE_DEB"
