# Linux packaging — building the installer tarball

This directory builds `kelpie-linux-installer.tar.gz`: a self-contained
bundle you can host anywhere (e.g. your website) for people to download
and run on Ubuntu/Debian. It contains `install.sh`, `preview.py`, the built
`.deb`, and a short `README.txt` — nothing else is needed, and there's no
bare `.deb` for someone to accidentally `dpkg -i` directly (which would
skip the preview/confirmation screen).

## Prerequisites

Just `dpkg-deb`, which is part of the base `dpkg` package on any
Debian/Ubuntu system — nothing extra to install. Building must be done on
Linux (or WSL); it isn't cross-buildable from macOS/Windows.

## Build

From this directory:

```sh
./dist.sh
```

This rebuilds the `.deb` from current source (`build.sh`) and then bundles
it into `kelpie-linux-installer.tar.gz` in this same directory. That one
file is what you upload to your website.

## What downloaders actually do

```sh
tar -xzf kelpie-linux-installer.tar.gz
cd kelpie-installer
./install.sh
```

`install.sh` shows a preview of what will be installed (curses UI if
there's a real terminal, plain text otherwise), asks for confirmation,
then installs `kelpie` + `samba` via `apt`. It also removes and cleanly
reinstalls automatically if Kelpie is already present, so re-running it
against a newer tarball works as an update path.

## Releasing an update

**Bump the version before rebuilding**, in two places:

- `kelpie/DEBIAN/control` — the `Version:` field
- `dist.sh` — the `VERSION` variable (cosmetic, only used in the bundled
  `README.txt`'s text)

This isn't optional cosmetics — `apt` compares versions to decide whether
there's anything to do. If you rebuild with the **same** version number,
`apt install` on a machine that already has Kelpie installed will report
"already the newest version" and silently do nothing, even though the
package's file contents changed. `install.sh`'s `apt install --reinstall`
covers the *install* side of that gap (forces a reinstall of a
same-version package), but a real version bump is still what makes the
change show up as an actual upgrade rather than a same-version reinstall,
and is expected practice for any package intended for real distribution.

Also note `build.sh`/`dist.sh` currently hardcode the filename
`kelpie_0.1.0_all.deb` — if you bump the version, update that filename
references in both scripts to match (or the build will look for/produce a
file under the old name).

## Files in this directory

| File | Purpose |
|---|---|
| `build.sh` | Rebuilds `kelpie_0.1.0_all.deb` from `../../src/*.py` |
| `dist.sh` | Runs `build.sh`, then bundles the distributable tarball |
| `install.sh` | What end users run — preview, confirm, `apt install` |
| `preview.py` | The pre-install curses preview screen (self-contained, no imports from `src/`, so the tarball needs only these files) |
| `kelpie/` | The `.deb`'s staged file tree (`DEBIAN/control`, `postinst`, etc.) |
