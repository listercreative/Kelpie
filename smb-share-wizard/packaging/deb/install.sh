#!/bin/sh
# Shows Kelpie's own terminal UI (banner + arrow-key menu) to explain what's
# about to be installed, BEFORE apt is invoked at all - this is the only
# way to run our UI ahead of apt's own dependency-resolution summary, since
# no .deb-internal hook (preinst included) fires before apt starts.
set -e

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
