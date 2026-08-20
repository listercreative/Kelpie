import os
import platform
import re
import sys
import subprocess
import json
import shutil
import tempfile

try:
    import tkinter as tk
    from tkinter import filedialog
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False


def _run(args, **kwargs):
    # A --windowed PyInstaller build has no console of its own, so any
    # child process without CREATE_NO_WINDOW gets a brand-new one that
    # flashes open and closes on screen - Windows-only, the flag doesn't
    # exist on other platforms.
    if platform.system() == "Windows":
        kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
    return subprocess.run(args, **kwargs)


class SMBWizard:
    """Platform detection, persistence, privilege elevation, and the actual
    per-OS commands that create/apply an SMB share. No UI code lives here —
    cli.py and gui.py both drive this class."""

    def __init__(self):
        self.system = platform.system()
        self.share_name = ""
        self.share_path = ""
        self.users = []
        # Set only when this instance was rebuilt inside an elevated
        # relaunch (see _elevated_relaunch/apply_from_file) - the explicit
        # identity of whoever originally requested the operation, captured
        # before elevation. Takes priority over SUDO_USER sniffing, which
        # only works when the elevation happened to go through `sudo`
        # (pkexec and osascript's admin-privileges prompt don't set it).
        self._invoking_user_override = None

    def _real_home(self):
        # Root via `sudo` (e.g. the postinst-launched wizard) has HOME=/root;
        # resolve the actual invoking user's home so defaults land somewhere
        # they'll actually see them again.
        username = self._real_username()
        if username:
            try:
                import pwd
                return pwd.getpwnam(username).pw_dir
            except (KeyError, ImportError):
                pass
        return os.path.expanduser("~")

    def _real_username(self):
        if self._invoking_user_override:
            return self._invoking_user_override
        sudo_user = os.environ.get("SUDO_USER")
        if sudo_user and sudo_user != "root":
            return sudo_user
        return None

    def list_shares(self):
        # Kelpie is just a helper for Samba/NTFS sharing - it doesn't keep
        # its own record of what shares exist, because that copy can drift
        # from reality (a share that failed to apply would still show up as
        # "created"; a share removed some other way would linger forever).
        # This always reads the live configuration instead.
        if self.system == "Linux":
            return self._list_shares_linux()
        elif self.system == "Darwin":
            return self._list_shares_macos()
        elif self.system == "Windows":
            return self._list_shares_windows()
        return []

    def delete_share(self, name):
        # Requires root. Callers not already elevated should go through
        # remove_share() instead, which handles that.
        if self.system == "Linux":
            return self._delete_share_linux(name)
        elif self.system == "Darwin":
            return self._delete_share_macos(name)
        elif self.system == "Windows":
            return self._delete_share_windows(name)
        return False

    def remove_share(self, name):
        if self.has_admin_privileges():
            return self.delete_share(name)
        return self.elevate_and_delete(name)

    def add_user_to_share(self, share_name, username, password):
        # Requires root. Callers not already elevated should go through
        # grant_share_access() instead, which handles that.
        if self.system == "Linux":
            return self._add_user_to_share_linux(share_name, username, password)
        elif self.system == "Darwin":
            return self._add_user_to_share_macos(share_name, username, password)
        elif self.system == "Windows":
            return self._add_user_to_share_windows(share_name, username, password)
        return False

    def grant_share_access(self, share_name, username, password):
        if self.has_admin_privileges():
            return self.add_user_to_share(share_name, username, password)
        return self.elevate_and_grant_access(share_name, username, password)

    def remove_user_from_share(self, share_name, username):
        # Requires root. Revokes access to one share only (valid-users entry
        # + group membership) - the account itself, and its access to any
        # other share, is left alone. Callers not already elevated should go
        # through revoke_share_access() instead.
        if self.system == "Linux":
            return self._remove_user_from_share_linux(share_name, username)
        elif self.system == "Darwin":
            return self._remove_user_from_share_macos(share_name, username)
        elif self.system == "Windows":
            return self._remove_user_from_share_windows(share_name, username)
        return False

    def revoke_share_access(self, share_name, username):
        if self.has_admin_privileges():
            return self.remove_user_from_share(share_name, username)
        return self.elevate_and_revoke_access(share_name, username)

    def delete_user(self, username):
        # Requires root. Deletes the account entirely - everywhere, not just
        # one share. Refuses to delete yourself or root, so this can't be
        # used to accidentally lock the invoking user out the way the
        # original path-permission bug did.
        if username == "root" or username == (self._real_username() or ""):
            print(f"Refusing to delete '{username}': that's you, or a protected account.")
            return False
        if self.system == "Linux":
            return self._delete_user_linux(username)
        elif self.system == "Darwin":
            return self._delete_user_macos(username)
        elif self.system == "Windows":
            return self._delete_user_windows(username)
        return False

    def remove_user(self, username):
        if self.has_admin_privileges():
            return self.delete_user(username)
        return self.elevate_and_delete_user(username)

    def delete_group(self, group_name):
        # Requires root. Refuses to delete a group a live share still
        # depends on for filesystem access - that share's directory would
        # keep the now-nonexistent group as its owner, silently breaking
        # access for everyone using it. Delete the share(s) first.
        in_use_by = next((g["shares"] for g in self.list_groups() if g["name"] == group_name and g["shares"]), None)
        if in_use_by:
            print(f"Refusing to delete group '{group_name}': still used by share(s) {', '.join(in_use_by)}.")
            return False
        if self.system == "Linux":
            return self._delete_group_linux(group_name)
        elif self.system == "Darwin":
            return self._delete_group_macos(group_name)
        elif self.system == "Windows":
            return self._delete_group_windows(group_name)
        return False

    def remove_group(self, group_name):
        if self.has_admin_privileges():
            return self.delete_group(group_name)
        return self.elevate_and_delete_group(group_name)

    def add_user_to_group(self, username, group_name):
        # Requires root. Assigns an existing user to an existing group
        # directly - no password change, no share/smb.conf edit, just group
        # membership (decoupled from "Add User to Share", which does all of
        # that as one bundled operation). Callers not already elevated
        # should go through assign_user_to_group() instead.
        if self.system == "Linux":
            return self._add_user_to_group_linux(username, group_name)
        elif self.system == "Darwin":
            return self._add_user_to_group_macos(username, group_name)
        elif self.system == "Windows":
            return self._add_user_to_group_windows(username, group_name)
        return False

    def assign_user_to_group(self, username, group_name):
        if self.has_admin_privileges():
            return self.add_user_to_group(username, group_name)
        return self.elevate_and_assign_group(username, group_name)

    def remove_user_from_group(self, username, group_name):
        # Requires root. Direct inverse of add_user_to_group(): removes
        # group membership only, nothing else - doesn't touch any share's
        # valid-users line (that's revoke_share_access()'s job) or delete
        # the account. Callers not already elevated should go through
        # revoke_group_membership() instead.
        if self.system == "Linux":
            return self._remove_user_from_group_linux(username, group_name)
        elif self.system == "Darwin":
            return self._remove_user_from_group_macos(username, group_name)
        elif self.system == "Windows":
            return self._remove_user_from_group_windows(username, group_name)
        return False

    def revoke_group_membership(self, username, group_name):
        if self.has_admin_privileges():
            return self.remove_user_from_group(username, group_name)
        return self.elevate_and_revoke_group(username, group_name)

    # Prefix Kelpie gives the group it creates per share, so groups it
    # manages can be recognized even if a share block referencing them was
    # since removed (an orphaned group left over from a deleted share is
    # still worth surfacing, not silently hidden).
    _MANAGED_GROUP_PREFIX = {"Linux": "smbshare_", "Darwin": "kelpie_"}

    def list_groups(self):
        # Linux and macOS are both POSIX: the same grp-database read works
        # unchanged on either, no OS-specific logic needed here.
        if self.system in ("Linux", "Darwin"):
            return self._list_groups_posix()
        elif self.system == "Windows":
            return self._list_groups_windows()
        return []

    def list_users(self):
        # Every regular user account, not just ones already tied to a share
        # or group - otherwise a user with no access yet (or one just
        # removed from their last share/group) would simply disappear from
        # view instead of being visible to assign. Samba's own user
        # database (passdb.tdb) is root-only and can't be queried
        # unprivileged just to populate a list, so this reads the OS
        # account list instead - see _list_regular_usernames().
        shares = self.list_shares()
        groups = self.list_groups()

        user_shares = {}
        for share in shares:
            for u in share.get("users", []):
                user_shares.setdefault(u["username"], set()).add(share["name"])

        user_groups = {}
        for g in groups:
            for member in g["members"]:
                user_groups.setdefault(member, set()).add(g["name"])

        usernames = set(user_shares) | set(user_groups) | self._list_regular_usernames()
        return [
            {
                "username": u,
                "shares": sorted(user_shares.get(u, set())),
                "groups": sorted(user_groups.get(u, set())),
            }
            for u in sorted(usernames)
        ]

    def _list_regular_usernames(self):
        # Regular (non-system/service) local accounts, platform-appropriate:
        # Ubuntu/Debian's useradd defaults to UID_MIN=1000; macOS's regular
        # accounts start at 501 (Apple's own convention, distinct from
        # Linux's). This is what Kelpie's own _configure_linux_user/
        # _configure_macos_user create accounts as, so it naturally includes
        # every user Kelpie could plausibly manage.
        if self.system in ("Linux", "Darwin"):
            import pwd
            min_uid = 1000 if self.system == "Linux" else 500
            return {p.pw_name for p in pwd.getpwall() if min_uid <= p.pw_uid < 65534}
        elif self.system == "Windows":
            cmd = "Get-LocalUser | Select-Object Name | ConvertTo-Json -Compress"
            proc = _run(["powershell", "-Command", cmd], capture_output=True, text=True)
            if proc.returncode != 0 or not proc.stdout.strip():
                return set()
            try:
                data = json.loads(proc.stdout)
            except json.JSONDecodeError:
                return set()
            if isinstance(data, dict):
                data = [data]
            builtin = {"Administrator", "Guest", "DefaultAccount", "WDAGUtilityAccount"}
            return {d["Name"] for d in data if d.get("Name") not in builtin}
        return set()

    def _list_groups_posix(self):
        import grp
        shares = self.list_shares()
        group_to_shares = {}
        for share in shares:
            group = share.get("group")
            if group:
                group_to_shares.setdefault(group, []).append(share["name"])

        prefix = self._MANAGED_GROUP_PREFIX.get(self.system)
        groups = []
        for g in grp.getgrall():
            if g.gr_name in group_to_shares or (prefix and g.gr_name.startswith(prefix)):
                groups.append({
                    "name": g.gr_name,
                    "members": sorted(g.gr_mem),
                    "shares": sorted(group_to_shares.get(g.gr_name, [])),
                })
        return sorted(groups, key=lambda x: x["name"])

    def _group_for_path(self, path):
        # Shared by the Linux/macOS list_shares implementations: the group
        # that actually enforces filesystem access is whichever Unix group
        # owns the share directory right now - not a name recomputed from
        # the share's name, which could have drifted from reality.
        if not path or not os.path.isdir(path):
            return None
        try:
            import grp
            return grp.getgrgid(os.stat(path).st_gid).gr_name
        except (OSError, KeyError):
            return None

    def gui_available(self):
        # Windows/macOS are desktop-first platforms - if tkinter imported,
        # assume a display exists. Linux is routinely run headless (servers,
        # containers, SSH-only boxes), so check for an actual display server
        # too - a Linux install with no desktop environment must not offer
        # to launch one.
        if not TKINTER_AVAILABLE:
            return False
        if self.system == "Linux":
            return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        return True

    def select_directory(self):
        if not TKINTER_AVAILABLE:
            return None
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        directory = filedialog.askdirectory(title="Select Folder to Share")
        root.destroy()
        return directory

    def default_share_path(self, share_name=None):
        folder = self._sanitize_folder_name(share_name) if share_name else 'SMB_Share'
        if self.system == 'Windows':
            return 'C:\\' + folder
        return os.path.join(self._real_home(), folder)

    def _sanitize_folder_name(self, name):
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip().strip('.')
        return cleaned or 'SMB_Share'

    def has_admin_privileges(self):
        try:
            if self.system == "Windows":
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            return os.geteuid() == 0
        except Exception:
            return False

    def elevation_needs_terminal(self):
        # Already privileged: no elevation at all. Windows UAC (Start-Process
        # -Verb RunAs) and macOS's "with administrator privileges" osascript
        # dialog are both their own separate graphical prompts - neither
        # needs our terminal. pkexec is the same on Linux; only the bare
        # `sudo` fallback (no pkexec available) genuinely needs real
        # terminal I/O for its password prompt, which is incompatible with
        # something else (like curses) holding the terminal at the same time.
        if self.has_admin_privileges():
            return False
        if self.system == "Linux":
            return not shutil.which("pkexec")
        return False

    def _unsafe_share_paths(self):
        # Directories we must never chown/chmod/hand to Samba, even if the
        # user (or a buggy picker default) selects them: doing so as root -
        # e.g. from the postinst-launched wizard - can lock the real user
        # out of their own home directory.
        system_paths = {
            "Linux": ["/", "/root", "/home", "/etc", "/usr", "/bin", "/sbin", "/boot", "/lib", "/lib64", "/var", "/opt"],
            "Darwin": ["/", "/System", "/Users", "/etc", "/usr", "/bin", "/sbin", "/Library"],
            "Windows": ["C:\\", "C:\\Windows", "C:\\Users", "C:\\Program Files", "C:\\Program Files (x86)"],
        }
        paths = {os.path.abspath(self._real_home())}
        paths.update(os.path.abspath(p) for p in system_paths.get(self.system, []))
        return paths

    def _validate_share_path(self):
        resolved = os.path.abspath(os.path.expanduser(self.share_path))
        if resolved in self._unsafe_share_paths():
            print(
                f"Refusing to use '{self.share_path}' as a share path: it resolves to "
                f"'{resolved}', a home or system directory. Choose (or create) a subfolder instead."
            )
            return False
        return True

    def dispatch_execution(self):
        if not self._validate_share_path():
            return
        if self.system == "Windows": self.run_windows()
        elif self.system == "Linux": self.run_linux()
        elif self.system == "Darwin": self.run_macos()

    def _prepare_relaunch(self, arg_flag, payload):
        # Shared by _elevated_relaunch and _elevated_relaunch_capturing:
        # writes the payload to a temp file the elevated child reads back,
        # and builds the argv to relaunch this program with.
        fd, tmp_path = tempfile.mkstemp(prefix="smbwizard_", suffix=".json")
        os.close(fd)
        try:
            os.chmod(tmp_path, 0o600)
        except Exception:
            pass

        # Capture who's *actually* asking, right now, before elevation - not
        # via SUDO_USER, since pkexec/osascript's admin-privileges prompt
        # don't set it. The elevated process reads this back out of the
        # payload (see apply_from_file/delete_share_from_file) so it knows
        # who to hand ownership of new files/directories to.
        import getpass
        payload = dict(payload)
        payload["_invoking_user"] = self._real_username() or getpass.getuser()

        with open(tmp_path, 'w') as f:
            json.dump(payload, f)

        if getattr(sys, 'frozen', False):
            relaunch_target = sys.executable
            relaunch_args = [arg_flag, tmp_path]
        else:
            relaunch_target = sys.executable
            script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
            relaunch_args = [script, arg_flag, tmp_path]

        return tmp_path, relaunch_target, relaunch_args

    def _elevated_relaunch(self, arg_flag, payload):
        print("Administrator/root privileges are required. Requesting elevation...")
        tmp_path, relaunch_target, relaunch_args = self._prepare_relaunch(arg_flag, payload)

        try:
            if self.system == "Windows":
                arg_str = " ".join(f'\\"{a}\\"' for a in relaunch_args)
                cmd = (
                    f"Start-Process -FilePath '{relaunch_target}' "
                    f"-ArgumentList '{arg_str}' "
                    f"-Verb RunAs -Wait"
                )
                _run(["powershell", "-Command", cmd], check=True)

            elif self.system == "Darwin":
                quoted_args = " ".join(f'"{a}"' for a in relaunch_args)
                apply_cmd = f'{relaunch_target} {quoted_args}'
                escaped = apply_cmd.replace('\\', '\\\\').replace('"', '\\"')
                osa_cmd = f'do shell script "{escaped}" with administrator privileges'
                _run(["osascript", "-e", osa_cmd], check=True)

            else:  # Linux
                if shutil.which("pkexec"):
                    _run(["pkexec", relaunch_target, *relaunch_args], check=True)
                else:
                    print("No GUI privilege helper (pkexec) found; falling back to a terminal sudo prompt.")
                    _run(["sudo", relaunch_target, *relaunch_args], check=True)

            print("Elevated operation completed.")
            return True
        except subprocess.CalledProcessError:
            print("Elevation was cancelled or failed.")
            return False
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def _elevated_relaunch_capturing(self, arg_flag, payload):
        # Like _elevated_relaunch, but captures the elevated child's output
        # instead of inheriting our stdout/stderr, and returns (success,
        # output) instead of printing directly - for callers (the TUI) that
        # need to run this while something else (curses) owns the terminal.
        # subprocess output normally bypasses Python's sys.stdout entirely
        # (it's OS-level file descriptor inheritance), so redirect_stdout
        # alone can't capture it the way it captures in-process print()
        # calls - capture_output=True is what actually does that here.
        #
        # Only valid when elevation_needs_terminal() is False - i.e. the
        # pkexec/UAC/osascript graphical-prompt paths below, never the raw
        # `sudo` fallback, which still needs real terminal I/O and must go
        # through _elevated_relaunch() outside curses instead.
        tmp_path, relaunch_target, relaunch_args = self._prepare_relaunch(arg_flag, payload)
        try:
            if self.system == "Windows":
                arg_str = " ".join(f'\\"{a}\\"' for a in relaunch_args)
                cmd = (
                    f"Start-Process -FilePath '{relaunch_target}' "
                    f"-ArgumentList '{arg_str}' "
                    f"-Verb RunAs -Wait"
                )
                proc = _run(["powershell", "-Command", cmd], capture_output=True, text=True)
            elif self.system == "Darwin":
                quoted_args = " ".join(f'"{a}"' for a in relaunch_args)
                apply_cmd = f'{relaunch_target} {quoted_args}'
                escaped = apply_cmd.replace('\\', '\\\\').replace('"', '\\"')
                osa_cmd = f'do shell script "{escaped}" with administrator privileges'
                proc = _run(["osascript", "-e", osa_cmd], capture_output=True, text=True)
            else:  # Linux - caller guarantees pkexec is available
                proc = _run(
                    ["pkexec", relaunch_target, *relaunch_args], capture_output=True, text=True
                )
            output = (proc.stdout or "") + (proc.stderr or "")
            return proc.returncode == 0, output
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def elevate_and_apply(self, share_data):
        return self._elevated_relaunch("--apply", share_data)

    def elevate_and_delete(self, name):
        return self._elevated_relaunch("--delete-share", {"name": name})

    def elevate_and_grant_access(self, share_name, username, password):
        return self._elevated_relaunch(
            "--add-user", {"share": share_name, "username": username, "password": password}
        )

    def elevate_and_revoke_access(self, share_name, username):
        return self._elevated_relaunch("--revoke-user", {"share": share_name, "username": username})

    def elevate_and_delete_user(self, username):
        return self._elevated_relaunch("--delete-user", {"username": username})

    def elevate_and_delete_group(self, group_name):
        return self._elevated_relaunch("--delete-group", {"name": group_name})

    def elevate_and_assign_group(self, username, group_name):
        return self._elevated_relaunch("--assign-group", {"username": username, "group": group_name})

    def elevate_and_revoke_group(self, username, group_name):
        return self._elevated_relaunch("--revoke-group", {"username": username, "group": group_name})

    @staticmethod
    def apply_from_file(path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

        wizard = SMBWizard()
        wizard._invoking_user_override = data.get('_invoking_user')
        wizard.share_name = data['name']
        wizard.share_path = data['path']
        wizard.users = data['users']
        wizard.dispatch_execution()

    @staticmethod
    def delete_share_from_file(path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

        wizard = SMBWizard()
        wizard._invoking_user_override = data.get('_invoking_user')
        wizard.delete_share(data['name'])

    @staticmethod
    def add_user_to_share_from_file(path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

        wizard = SMBWizard()
        wizard._invoking_user_override = data.get('_invoking_user')
        wizard.add_user_to_share(data['share'], data['username'], data['password'])

    @staticmethod
    def revoke_share_access_from_file(path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

        wizard = SMBWizard()
        wizard._invoking_user_override = data.get('_invoking_user')
        wizard.remove_user_from_share(data['share'], data['username'])

    @staticmethod
    def delete_user_from_file(path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

        wizard = SMBWizard()
        wizard._invoking_user_override = data.get('_invoking_user')
        wizard.delete_user(data['username'])

    @staticmethod
    def delete_group_from_file(path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

        wizard = SMBWizard()
        wizard._invoking_user_override = data.get('_invoking_user')
        wizard.delete_group(data['name'])

    @staticmethod
    def assign_user_to_group_from_file(path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

        wizard = SMBWizard()
        wizard._invoking_user_override = data.get('_invoking_user')
        wizard.add_user_to_group(data['username'], data['group'])

    @staticmethod
    def revoke_group_membership_from_file(path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

        wizard = SMBWizard()
        wizard._invoking_user_override = data.get('_invoking_user')
        wizard.remove_user_from_group(data['username'], data['group'])

    def _ps_quote(self, s):
        # Escape for embedding inside a PowerShell single-quoted string.
        return s.replace("'", "''")

    def _windows_group_name(self, share_name):
        cleaned = re.sub(r'[\"/\\\[\]:;|=,+*?<>@\x00-\x1f]', '_', share_name).strip()
        return f"Kelpie_{cleaned or 'Share'}"[:64]

    def _ensure_windows_group(self, group_name):
        escaped = self._ps_quote(group_name)
        cmd = f"if (-not (Get-LocalGroup -Name '{escaped}' -ErrorAction SilentlyContinue)) {{ New-LocalGroup -Name '{escaped}' }}"
        _run(["powershell", "-Command", cmd], check=True, capture_output=True, text=True)

    def _configure_windows_user(self, username, password):
        # Password travels via an env var, never interpolated into the
        # PowerShell command string, so a crafted password can't break out
        # and inject commands.
        escaped_user = self._ps_quote(username)
        cmd = (
            f"$pw = ConvertTo-SecureString $env:KELPIE_TEMP_PW -AsPlainText -Force; "
            f"if (-not (Get-LocalUser -Name '{escaped_user}' -ErrorAction SilentlyContinue)) {{ "
            f"New-LocalUser -Name '{escaped_user}' -Password $pw -PasswordNeverExpires -AccountNeverExpires "
            f"}} else {{ Set-LocalUser -Name '{escaped_user}' -Password $pw }}"
        )
        env = dict(os.environ)
        env["KELPIE_TEMP_PW"] = password
        _run(["powershell", "-Command", cmd], check=True, capture_output=True, text=True, env=env)

    def _add_windows_user_to_group(self, username, group_name):
        cmd = f"Add-LocalGroupMember -Group '{self._ps_quote(group_name)}' -Member '{self._ps_quote(username)}' -ErrorAction SilentlyContinue"
        _run(["powershell", "-Command", cmd], check=True, capture_output=True, text=True)

    def _grant_windows_ntfs_permissions(self, share_path, group_name):
        # icacls is invoked directly (no shell), so no PowerShell quoting needed.
        _run(["icacls", share_path, "/grant", f"{group_name}:(OI)(CI)M"], check=True, capture_output=True, text=True)

    def run_windows(self):
        print(f"[Windows] Executing configuration for '{self.share_name}'...")
        try:
            print(f"  - Ensuring directory exists: {self.share_path}")
            _run(["powershell", "-Command", f"New-Item -Path '{self._ps_quote(self.share_path)}' -ItemType Directory -Force"], check=True, capture_output=True, text=True)

            group_name = self._windows_group_name(self.share_name)
            print(f"  - Ensuring local group '{group_name}'...")
            self._ensure_windows_group(group_name)

            for user in self.users:
                username = user['username']
                print(f"  - Configuring local user '{username}'...")
                self._configure_windows_user(username, user['password'])
                self._add_windows_user_to_group(username, group_name)

            print(f"  - Granting NTFS permissions to '{group_name}' on '{self.share_path}'...")
            self._grant_windows_ntfs_permissions(self.share_path, group_name)

            print(f"  - Creating share '{self.share_name}' with FullAccess for '{group_name}'...")
            cmd = f"New-SmbShare -Name '{self._ps_quote(self.share_name)}' -Path '{self._ps_quote(self.share_path)}' -FullAccess '{self._ps_quote(group_name)}' -ErrorAction SilentlyContinue"
            _run(["powershell", "-Command", cmd], check=True, capture_output=True, text=True)

            print("[Windows] Success.")
        except subprocess.CalledProcessError as e:
            print(f"[Windows] Error during execution: {e.stderr if e.stderr else e}")
        except Exception as e:
            print(f"[Windows] An unexpected error occurred: {e}")

    @staticmethod
    def _as_list(value):
        # PowerShell's ConvertTo-Json collapses a single-element array/
        # property down to a bare scalar (or omits it as $null) instead of
        # a one-item array - normalize so callers can always iterate.
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    def _list_shares_windows(self):
        # One PowerShell process for every share (Get-SmbShareAccess) added
        # up to a very visible multi-second stall as share count grew, since
        # each powershell.exe launch (SMB cmdlets go through CIM, which is
        # even slower) costs several hundred ms on its own. Do the whole
        # per-share access lookup inside a single PowerShell invocation
        # instead of one process per share.
        cmd = (
            "Get-SmbShare | Where-Object { $_.Name -notin @('ADMIN$','C$','IPC$','print$') } "
            "| ForEach-Object { "
            "[PSCustomObject]@{ Name = $_.Name; Path = $_.Path; "
            "Access = (Get-SmbShareAccess -Name $_.Name | Select-Object -ExpandProperty AccountName) } "
            "} | ConvertTo-Json -Compress -Depth 4"
        )
        proc = _run(["powershell", "-Command", cmd], capture_output=True, text=True)
        if proc.returncode != 0 or not proc.stdout.strip():
            return []
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return []
        if isinstance(data, dict):
            data = [data]

        shares = []
        for s in data:
            share = {"name": s["Name"], "path": s.get("Path", ""), "users": [], "group": None}
            # run_windows() only ever grants FullAccess to the one
            # Kelpie-created group (individual users are members of it, not
            # granted directly), so the share's access is entirely
            # represented by that one group - same shape as the
            # Linux/macOS "group" field.
            for account in self._as_list(s.get("Access")):
                name = account.split("\\")[-1]
                if name.startswith("Kelpie_"):
                    share["group"] = name
                    break
            shares.append(share)
        return shares

    def _list_groups_windows(self):
        # Same fix as _list_shares_windows: one PowerShell process for the
        # group list, one for every group's membership, plus a full second
        # pass through _list_shares_windows()'s own per-share loop - batch
        # groups+members into a single call, and reuse one shares fetch.
        cmd = (
            "Get-LocalGroup | Where-Object { $_.Name -like 'Kelpie_*' } "
            "| ForEach-Object { "
            "[PSCustomObject]@{ Name = $_.Name; "
            "Members = (Get-LocalGroupMember -Group $_.Name | Select-Object -ExpandProperty Name) } "
            "} | ConvertTo-Json -Compress -Depth 4"
        )
        proc = _run(["powershell", "-Command", cmd], capture_output=True, text=True)
        if proc.returncode != 0 or not proc.stdout.strip():
            return []
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return []
        if isinstance(data, dict):
            data = [data]

        group_to_shares = {}
        for share in self._list_shares_windows():
            group = share.get("group")
            if group:
                group_to_shares.setdefault(group, []).append(share["name"])

        groups = []
        for g in data:
            name = g.get("Name")
            if not name:
                continue
            members = sorted(m.split("\\")[-1] for m in self._as_list(g.get("Members")))
            groups.append({
                "name": name,
                "members": members,
                "shares": sorted(group_to_shares.get(name, [])),
            })
        return sorted(groups, key=lambda x: x["name"])

    def _delete_share_windows(self, name):
        cmd = f"Remove-SmbShare -Name '{self._ps_quote(name)}' -Force -ErrorAction Stop"
        proc = _run(["powershell", "-Command", cmd], capture_output=True, text=True)
        return proc.returncode == 0

    def _add_user_to_share_windows(self, share_name, username, password):
        shares = {s["name"]: s for s in self._list_shares_windows()}
        share = shares.get(share_name)
        if not share:
            print(f"[Windows] No such share: '{share_name}'")
            return False

        self._configure_windows_user(username, password)

        group_name = share.get("group") or self._windows_group_name(share_name)
        self._ensure_windows_group(group_name)
        self._add_windows_user_to_group(username, group_name)

        print(f"[Windows] Added '{username}' to share '{share_name}'.")
        return True

    def _remove_user_from_share_windows(self, share_name, username):
        shares = {s["name"]: s for s in self._list_shares_windows()}
        share = shares.get(share_name)
        if not share:
            print(f"[Windows] No such share: '{share_name}'")
            return False
        group_name = share.get("group")
        if group_name:
            cmd = (
                f"Remove-LocalGroupMember -Group '{self._ps_quote(group_name)}' "
                f"-Member '{self._ps_quote(username)}' -ErrorAction SilentlyContinue"
            )
            _run(["powershell", "-Command", cmd], capture_output=True, text=True)
        print(f"[Windows] Removed '{username}' from share '{share_name}'.")
        return True

    def _delete_user_windows(self, username):
        cmd = f"Remove-LocalUser -Name '{self._ps_quote(username)}' -ErrorAction Stop"
        proc = _run(["powershell", "-Command", cmd], capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"[Windows] Failed to delete user '{username}': {proc.stderr.strip()}")
            return False
        print(f"[Windows] Deleted user '{username}'.")
        return True

    def _delete_group_windows(self, group_name):
        cmd = f"Remove-LocalGroup -Name '{self._ps_quote(group_name)}' -ErrorAction Stop"
        proc = _run(["powershell", "-Command", cmd], capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"[Windows] Failed to delete group '{group_name}': {proc.stderr.strip()}")
            return False
        print(f"[Windows] Deleted group '{group_name}'.")
        return True

    def _add_user_to_group_windows(self, username, group_name):
        cmd = (
            f"Add-LocalGroupMember -Group '{self._ps_quote(group_name)}' "
            f"-Member '{self._ps_quote(username)}' -ErrorAction Stop"
        )
        proc = _run(["powershell", "-Command", cmd], capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"[Windows] Failed to add '{username}' to group '{group_name}': {proc.stderr.strip()}")
            return False
        print(f"[Windows] Added '{username}' to group '{group_name}'.")
        return True

    def _remove_user_from_group_windows(self, username, group_name):
        cmd = (
            f"Remove-LocalGroupMember -Group '{self._ps_quote(group_name)}' "
            f"-Member '{self._ps_quote(username)}' -ErrorAction Stop"
        )
        proc = _run(["powershell", "-Command", cmd], capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"[Windows] Failed to remove '{username}' from group '{group_name}': {proc.stderr.strip()}")
            return False
        print(f"[Windows] Removed '{username}' from group '{group_name}'.")
        return True

    def _ensure_samba_installed_linux(self):
        if shutil.which("smbd"):
            self._ensure_netbios_enabled_linux()
            return True
        print("[Linux] Samba not found. Attempting installation...")
        try:
            if shutil.which("apt-get"):
                _run(["apt-get", "update"], check=True, capture_output=True, text=True)
                _run(["apt-get", "install", "-y", "samba"], check=True, capture_output=True, text=True)
            elif shutil.which("dnf"):
                _run(["dnf", "install", "-y", "samba"], check=True, capture_output=True, text=True)
            elif shutil.which("yum"):
                _run(["yum", "install", "-y", "samba"], check=True, capture_output=True, text=True)
            elif shutil.which("pacman"):
                _run(["pacman", "-S", "--noconfirm", "samba"], check=True, capture_output=True, text=True)
            else:
                print("[Linux] No supported package manager found (tried apt-get/dnf/yum/pacman). Please install Samba manually.")
                return False
        except subprocess.CalledProcessError as e:
            print(f"[Linux] Failed to install Samba: {e.stderr if e.stderr else e}")
            return False
        installed = shutil.which("smbd") is not None
        if installed:
            self._ensure_netbios_enabled_linux()
        return installed

    def _ensure_netbios_enabled_linux(self):
        # Debian/Ubuntu's stock smb.conf ships with "disable netbios = yes".
        # That's not just inert config - /usr/share/samba/is-configured (the
        # ExecCondition nmbd.service checks on every start) explicitly reads
        # this setting and refuses to let nmbd start at all when it's set,
        # so shares end up completely invisible to any client that
        # discovers servers via NetBIOS/workgroup browsing (as opposed to a
        # direct \\host\share path), even though the share itself works
        # fine. Fix it once, system-wide, rather than per-share.
        proc = _run(
            ["testparm", "-s", "--parameter-name=disable netbios"],
            capture_output=True, text=True
        )
        if proc.stdout.strip().lower() != "yes":
            return

        smb_conf = "/etc/samba/smb.conf"
        if not os.path.exists(smb_conf):
            return
        with open(smb_conf, 'r') as f:
            lines = f.readlines()

        out = []
        for raw_line in lines:
            bare = raw_line.strip().split('#', 1)[0].split(';', 1)[0].strip()
            if '=' in bare and bare.split('=', 1)[0].strip().lower() == 'disable netbios':
                out.append("   disable netbios = no\n")
            else:
                out.append(raw_line)

        with open(smb_conf, 'w') as f:
            f.writelines(out)

        print("[Linux] NetBIOS was disabled in smb.conf (Ubuntu's default) - enabled it so this "
              "server's name/workgroup is visible to browsing clients.")
        try:
            _run(["systemctl", "restart", "nmbd"], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError:
            try:
                _run(["systemctl", "restart", "nmb"], check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                print(f"[Linux] Enabled NetBIOS but failed to start the name-service daemon: {e.stderr if e.stderr else e}")

    def _add_samba_share_config(self, share_name, share_path, usernames):
        smb_conf = "/etc/samba/smb.conf"
        existing = ""
        if os.path.exists(smb_conf):
            with open(smb_conf, 'r') as f:
                existing = f.read()
        if f"[{share_name}]" in existing:
            print(f"[Linux] Share block for '{share_name}' already exists in {smb_conf}, skipping.")
            return
        block = (
            f"\n[{share_name}]\n"
            f"    path = {share_path}\n"
            f"    browsable = yes\n"
            f"    read only = no\n"
            f"    guest ok = no\n"
            f"    valid users = {' '.join(usernames)}\n"
        )
        with open(smb_conf, 'a') as f:
            f.write(block)
        print(f"[Linux] Appended share definition to {smb_conf}")

    def _configure_linux_user(self, username, password):
        exists = _run(["id", username], capture_output=True, text=True).returncode == 0
        if not exists:
            print(f"[Linux] Creating system user '{username}'...")
            _run(["useradd", "-M", "-s", "/usr/sbin/nologin", username], check=True, capture_output=True, text=True)

        print(f"[Linux] Setting Samba password for '{username}'...")
        proc = _run(
            ["smbpasswd", "-a", "-s", username],
            input=f"{password}\n{password}\n", capture_output=True, text=True
        )
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, "smbpasswd", output=proc.stdout, stderr=proc.stderr)
        _run(["smbpasswd", "-e", username], check=True, capture_output=True, text=True)

    def _share_group_name(self, share_name):
        slug = re.sub(r'[^a-z0-9_-]', '_', share_name.lower()).strip('_-') or "share"
        return f"smbshare_{slug}"[:32]

    def _ensure_group(self, group_name):
        exists = _run(["getent", "group", group_name], capture_output=True, text=True).returncode == 0
        if not exists:
            print(f"[Linux] Creating group '{group_name}'...")
            _run(["groupadd", group_name], check=True, capture_output=True, text=True)

    def _add_user_to_group(self, username, group_name):
        _run(["usermod", "-aG", group_name, username], check=True, capture_output=True, text=True)

    def _repair_group_if_orphaned(self, path, group_name):
        # If path's current group doesn't correspond to any real group
        # anymore (a stale/orphaned GID - e.g. this exact share's group got
        # deleted and recreated; group names are reused but a fresh
        # groupadd gets a new GID, and a lingering directory never gets
        # re-synced to it), that's unambiguous evidence this is stale
        # bookkeeping from Kelpie itself, not some unrelated directory, so
        # it's safe to repair. Returns True if a repair happened. Called
        # both when a share's directory already existed at creation time,
        # and whenever a user is granted access later - group membership
        # alone doesn't help someone if the directory itself is still
        # tagged with a GID nobody belongs to.
        import grp
        current_gid = os.stat(path).st_gid
        try:
            grp.getgrgid(current_gid)
            return False
        except KeyError:
            pass
        print(f"'{path}''s group (gid {current_gid}) no longer exists - refreshing it to '{group_name}'...")
        if self.system == "Darwin":
            _run(["chgrp", group_name, path], check=True, capture_output=True, text=True)
        else:
            shutil.chown(path, group=group_name)
        os.chmod(path, 0o2770)
        return True

    def _grant_traversal_acl(self, share_path, group_name):
        # The share directory itself can be perfectly configured (correct
        # owner/group/mode) and still be completely unreachable: smbd has to
        # traverse every ancestor directory too when impersonating a
        # non-owner user, and chmod alone can't grant that without loosening
        # an ancestor (e.g. a private $HOME) for literally everyone. A POSIX
        # ACL entry scoped to just this share's group grants exactly the
        # traversal needed - nothing else changes for anyone else. Only
        # touches ancestors that don't already allow traversal; idempotent,
        # so safe to call again for every later "add user" too.
        if self.system != "Linux":
            return
        if not shutil.which("setfacl"):
            print(
                "[Linux] 'setfacl' not found (install the 'acl' package) - if users other than "
                "you can't reach this share, a parent directory may be blocking them and needs "
                "either the 'acl' package or a manual permission fix."
            )
            return
        current = os.path.dirname(os.path.abspath(share_path))
        while True:
            try:
                st = os.stat(current)
            except OSError:
                break
            if not (st.st_mode & 0o001):  # "other" execute/traversal bit not already set
                print(f"[Linux] Granting group '{group_name}' traversal-only access through '{current}'...")
                _run(
                    ["setfacl", "-m", f"g:{group_name}:--x", current], capture_output=True, text=True
                )
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent

    def _expose_share_directory(self, share_path, group_name, path_existed_before):
        # smb.conf's "read only = no" only governs the SMB protocol layer;
        # smbd still enforces real Unix permissions when it impersonates the
        # authenticated user's UID, so the directory itself must actually be
        # writable by that user's group. setgid (02770) makes new files
        # inherit the share's group too, instead of each writer's primary
        # group.
        #
        # Only ever do this to a directory we just created ourselves: forcing
        # chown+chmod onto a pre-existing directory means overwriting
        # permissions we don't understand the purpose of, on a path that
        # could turn out to be a shared system location (this is what caused
        # a prior lockout - see incident notes). If it already existed,
        # leave it alone and tell the user how to grant access themselves -
        # unless its group turns out to be orphaned (see
        # _repair_group_if_orphaned), which is safe to auto-fix.
        if path_existed_before:
            if self._repair_group_if_orphaned(share_path, group_name):
                return
            print(
                f"[Linux] '{share_path}' already existed - leaving its ownership/permissions "
                f"as-is. To grant the share group access yourself, run:\n"
                f"    sudo chgrp {group_name} '{share_path}' && sudo chmod 2770 '{share_path}'"
            )
            return
        print(f"[Linux] Granting group '{group_name}' read/write on '{share_path}'...")
        # When run as root (postinst, or an elevated relaunch), a freshly
        # created directory is root-owned by default - which would leave the
        # real invoking user locked out of a folder inside their own home.
        # Hand ownership back to them; the group is what actually grants
        # Samba access.
        owner = self._real_username()
        shutil.chown(share_path, user=owner, group=group_name)
        os.chmod(share_path, 0o2770)

    def _restart_samba_service(self):
        print("[Linux] Restarting Samba services...")
        for services in (["smbd", "nmbd"], ["smb", "nmb"]):
            try:
                for svc in services:
                    _run(["systemctl", "restart", svc], check=True, capture_output=True, text=True)
                return
            except subprocess.CalledProcessError:
                continue
        raise RuntimeError("Could not restart Samba services (tried smbd/nmbd and smb/nmb service names).")

    def run_linux(self):
        print(f"[Linux] Executing configuration for '{self.share_name}'...")
        try:
            if not self._ensure_samba_installed_linux():
                print("[Linux] Aborting: Samba is not installed and could not be installed automatically.")
                return

            print(f"  - Ensuring directory exists: {self.share_path}")
            path_existed_before = os.path.isdir(self.share_path)
            os.makedirs(self.share_path, exist_ok=True)

            self._add_samba_share_config(self.share_name, self.share_path, [u['username'] for u in self.users])

            group_name = self._share_group_name(self.share_name)
            self._ensure_group(group_name)

            for user in self.users:
                self._configure_linux_user(user['username'], user['password'])
                self._add_user_to_group(user['username'], group_name)

            self._expose_share_directory(self.share_path, group_name, path_existed_before)
            self._grant_traversal_acl(self.share_path, group_name)

            self._restart_samba_service()

            print("[Linux] Success.")
        except subprocess.CalledProcessError as e:
            print(f"[Linux] Error during execution: {e.stderr if e.stderr else e}")
        except Exception as e:
            print(f"[Linux] An unexpected error occurred: {e}")

    _RESERVED_SMB_SECTIONS = {"global", "printers", "print$", "homes", "netlogon", "profiles"}
    # See _rewrite_valid_users: written in place of a genuinely empty "valid
    # users" list, since Samba treats that as unset (no restriction at all)
    # rather than "nobody". Filtered back out wherever shares are read, so
    # it never surfaces as a phantom user in the UI.
    _NO_USERS_PLACEHOLDER = "__no_users__"

    def _list_shares_linux(self):
        smb_conf = "/etc/samba/smb.conf"
        if not os.path.exists(smb_conf):
            return []
        shares = []
        current = None

        def flush():
            if current and current["name"].lower() not in self._RESERVED_SMB_SECTIONS:
                shares.append(current)

        with open(smb_conf, 'r') as f:
            for raw_line in f:
                line = raw_line.split('#', 1)[0].split(';', 1)[0].strip()
                if not line:
                    continue
                if line.startswith('[') and line.endswith(']'):
                    flush()
                    current = {"name": line[1:-1].strip(), "path": "", "users": []}
                    continue
                if current is None or '=' not in line:
                    continue
                key, _, value = line.partition('=')
                key = key.strip().lower()
                value = value.strip()
                if key == 'path':
                    current["path"] = value
                elif key == 'valid users':
                    current["users"] = [
                        {"username": u} for u in value.split() if u != self._NO_USERS_PLACEHOLDER
                    ]
        flush()
        for share in shares:
            share["group"] = self._group_for_path(share.get("path"))
        return shares

    def _delete_share_linux(self, name):
        smb_conf = "/etc/samba/smb.conf"
        if not os.path.exists(smb_conf):
            return False
        with open(smb_conf, 'r') as f:
            lines = f.readlines()

        target = f"[{name}]".lower()
        out = []
        skipping = False
        removed = False
        for raw_line in lines:
            stripped = raw_line.strip()
            if stripped.startswith('[') and stripped.endswith(']'):
                skipping = stripped.lower() == target
                if skipping:
                    removed = True
                    continue
            if skipping:
                continue
            out.append(raw_line)

        if not removed:
            return False

        with open(smb_conf, 'w') as f:
            f.writelines(out)

        try:
            self._restart_samba_service()
        except Exception as e:
            print(f"[Linux] Removed '{name}' from smb.conf but failed to restart Samba: {e}")
        return True

    def _rewrite_valid_users(self, share_name, mutate):
        # Rewrites just the target share's "valid users" line in place via
        # mutate(existing_usernames) -> new_usernames - leaves every other
        # line (including the rest of that share's block) untouched.
        smb_conf = "/etc/samba/smb.conf"
        if not os.path.exists(smb_conf):
            return
        with open(smb_conf, 'r') as f:
            lines = f.readlines()

        target = f"[{share_name}]".lower()
        out = []
        in_target = False
        updated = False
        for raw_line in lines:
            stripped = raw_line.strip()
            if stripped.startswith('[') and stripped.endswith(']'):
                in_target = stripped.lower() == target
                out.append(raw_line)
                continue
            if in_target and not updated:
                bare = stripped.split('#', 1)[0].split(';', 1)[0].strip()
                if '=' in bare and bare.split('=', 1)[0].strip().lower() == 'valid users':
                    existing = bare.split('=', 1)[1].split()
                    new_users = mutate(existing)
                    if not new_users:
                        # A "valid users" line with nothing after it is not
                        # the same as "nobody can access this" - Samba
                        # treats an empty/absent value as unset, which means
                        # NO restriction: every Samba user on the box, not
                        # just none of them. Keep the share genuinely
                        # inaccessible with an unmatchable placeholder
                        # instead of accidentally opening it to everyone.
                        new_users = [self._NO_USERS_PLACEHOLDER]
                    out.append(f"    valid users = {' '.join(new_users)}\n")
                    updated = True
                    continue
            out.append(raw_line)

        with open(smb_conf, 'w') as f:
            f.writelines(out)

    def _add_valid_user_to_smb_conf(self, share_name, username):
        def mutate(users):
            users = [u for u in users if u != self._NO_USERS_PLACEHOLDER]
            return users if username in users else users + [username]
        self._rewrite_valid_users(share_name, mutate)

    def _remove_valid_user_from_smb_conf(self, share_name, username):
        self._rewrite_valid_users(share_name, lambda users: [u for u in users if u != username])

    def _add_user_to_share_linux(self, share_name, username, password):
        shares = {s["name"]: s for s in self._list_shares_linux()}
        share = shares.get(share_name)
        if not share:
            print(f"[Linux] No such share: '{share_name}'")
            return False

        self._configure_linux_user(username, password)

        group_name = share.get("group") or self._share_group_name(share_name)
        self._ensure_group(group_name)
        self._add_user_to_group(username, group_name)

        # Retroactively repairs shares created before these existed - both
        # are idempotent, so safe to run every time.
        path = share.get("path")
        if path:
            self._repair_group_if_orphaned(path, group_name)
            self._grant_traversal_acl(path, group_name)

        self._add_valid_user_to_smb_conf(share_name, username)

        try:
            self._restart_samba_service()
        except Exception as e:
            print(f"[Linux] Added '{username}' but failed to restart Samba: {e}")

        print(f"[Linux] Added '{username}' to share '{share_name}'.")
        return True

    def _remove_user_from_share_linux(self, share_name, username):
        shares = {s["name"]: s for s in self._list_shares_linux()}
        share = shares.get(share_name)
        if not share:
            print(f"[Linux] No such share: '{share_name}'")
            return False

        self._remove_valid_user_from_smb_conf(share_name, username)

        group_name = share.get("group")
        if group_name:
            # Not an error if they weren't a member (e.g. added to the
            # share's valid-users line by hand, never actually in the
            # group) - just make sure they aren't now.
            _run(["gpasswd", "-d", username, group_name], capture_output=True, text=True)

        try:
            self._restart_samba_service()
        except Exception as e:
            print(f"[Linux] Revoked '{username}' but failed to restart Samba: {e}")

        print(f"[Linux] Removed '{username}' from share '{share_name}'.")
        return True

    def _delete_user_linux(self, username):
        # smb.conf's valid-users entries are independent of Linux group
        # membership - strip this user from every share that lists them, not
        # just the one they were most recently added to, so deleting the
        # account doesn't leave dangling references to a user that no longer
        # exists.
        for share in self._list_shares_linux():
            if any(u["username"] == username for u in share.get("users", [])):
                self._remove_valid_user_from_smb_conf(share["name"], username)

        _run(["smbpasswd", "-x", username], capture_output=True, text=True)
        proc = _run(["userdel", username], capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"[Linux] Failed to delete user '{username}': {proc.stderr.strip()}")
            return False

        try:
            self._restart_samba_service()
        except Exception as e:
            print(f"[Linux] Deleted '{username}' but failed to restart Samba: {e}")

        print(f"[Linux] Deleted user '{username}'.")
        return True

    def _delete_group_linux(self, group_name):
        proc = _run(["groupdel", group_name], capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"[Linux] Failed to delete group '{group_name}': {proc.stderr.strip()}")
            return False
        print(f"[Linux] Deleted group '{group_name}'.")
        return True

    def _add_user_to_group_linux(self, username, group_name):
        if _run(["id", username], capture_output=True, text=True).returncode != 0:
            print(f"[Linux] No such user: '{username}'")
            return False
        if _run(["getent", "group", group_name], capture_output=True, text=True).returncode != 0:
            print(f"[Linux] No such group: '{group_name}'")
            return False
        self._add_user_to_group(username, group_name)
        print(f"[Linux] Added '{username}' to group '{group_name}'.")
        return True

    def _remove_user_from_group_linux(self, username, group_name):
        proc = _run(["gpasswd", "-d", username, group_name], capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"[Linux] Failed to remove '{username}' from group '{group_name}': {proc.stderr.strip()}")
            return False
        print(f"[Linux] Removed '{username}' from group '{group_name}'.")
        return True

    def _configure_macos_user(self, username, password):
        exists = _run(["dscl", ".", "-read", f"/Users/{username}"], capture_output=True, text=True).returncode == 0
        if not exists:
            print(f"[macOS] Creating user '{username}'...")
            _run(["sysadminctl", "-addUser", username, "-password", password], check=True, capture_output=True, text=True)
        else:
            print(f"[macOS] Setting password for existing user '{username}'...")
            _run(["dscl", ".", "-passwd", f"/Users/{username}", password], check=True, capture_output=True, text=True)
        _run(["dseditgroup", "-o", "edit", "-a", username, "-t", "user", "com.apple.access_smb"], check=True, capture_output=True, text=True)

    def _macos_group_name(self, share_name):
        slug = re.sub(r'[^a-zA-Z0-9_-]', '_', share_name).strip('_-') or 'share'
        return f"kelpie_{slug}"

    def _ensure_macos_group(self, group_name):
        exists = _run(["dscl", ".", "-read", f"/Groups/{group_name}"], capture_output=True, text=True).returncode == 0
        if not exists:
            print(f"[macOS] Creating group '{group_name}'...")
            _run(["dseditgroup", "-o", "create", group_name], check=True, capture_output=True, text=True)

    def _add_macos_user_to_group(self, username, group_name):
        _run(["dseditgroup", "-o", "edit", "-a", username, "-t", "user", group_name], check=True, capture_output=True, text=True)

    def _expose_macos_share_directory(self, share_path, group_name, path_existed_before):
        # Same underlying issue as Linux: macOS filesystem permissions are
        # POSIX, and smbd still enforces them when impersonating the
        # authenticated user - the share's own settings don't override that.
        # Only touch permissions on a directory we just created, unless its
        # current group is an orphaned GID - see _repair_group_if_orphaned.
        if path_existed_before:
            if self._repair_group_if_orphaned(share_path, group_name):
                return
            print(
                f"[macOS] '{share_path}' already existed - leaving its ownership/permissions "
                f"as-is. To grant the share group access yourself, run:\n"
                f"    sudo chgrp {group_name} '{share_path}' && sudo chmod 2770 '{share_path}'"
            )
            return
        print(f"[macOS] Granting group '{group_name}' read/write on '{share_path}'...")
        # See the matching comment in _expose_share_directory: hand ownership
        # of a freshly created directory back to the real invoking user, not
        # whichever privileged context created it.
        owner = self._real_username()
        if owner:
            _run(["chown", owner, share_path], check=True, capture_output=True, text=True)
        _run(["chgrp", group_name, share_path], check=True, capture_output=True, text=True)
        os.chmod(share_path, 0o2770)

    def _create_macos_share(self, share_name, share_path):
        print(f"[macOS] Creating share '{share_name}' at '{share_path}'...")
        _run(["sharing", "-a", share_path, "-S", share_name, "-s", "001"], check=True, capture_output=True, text=True)

    def _enable_macos_smb_sharing(self):
        print("[macOS] Enabling SMB file sharing service...")
        _run(["launchctl", "enable", "system/com.apple.smbd"], check=True, capture_output=True, text=True)
        _run(["launchctl", "kickstart", "-k", "system/com.apple.smbd"], check=True, capture_output=True, text=True)

    def run_macos(self):
        print(f"[macOS] Executing configuration for '{self.share_name}'...")
        try:
            print(f"  - Ensuring directory exists: {self.share_path}")
            path_existed_before = os.path.isdir(self.share_path)
            os.makedirs(self.share_path, exist_ok=True)

            group_name = self._macos_group_name(self.share_name)
            self._ensure_macos_group(group_name)

            for user in self.users:
                self._configure_macos_user(user['username'], user['password'])
                self._add_macos_user_to_group(user['username'], group_name)

            self._expose_macos_share_directory(self.share_path, group_name, path_existed_before)

            self._create_macos_share(self.share_name, self.share_path)
            self._enable_macos_smb_sharing()

            print("[macOS] Success.")
        except subprocess.CalledProcessError as e:
            print(f"[macOS] Error during execution: {e.stderr if e.stderr else e}")
        except Exception as e:
            print(f"[macOS] An unexpected error occurred: {e}")

    def _list_shares_macos(self):
        proc = _run(["sharing", "-l"], capture_output=True, text=True)
        if proc.returncode != 0:
            return []
        shares = []
        name = None
        path = None
        for raw_line in proc.stdout.splitlines():
            line = raw_line.strip()
            if line.startswith("name:"):
                if name:
                    shares.append({"name": name, "path": path or "", "users": []})
                name = line.split(":", 1)[1].strip()
                path = None
            elif line.startswith("path:"):
                path = line.split(":", 1)[1].strip()
        if name:
            shares.append({"name": name, "path": path or "", "users": []})
        for share in shares:
            share["group"] = self._group_for_path(share.get("path"))
        return shares

    def _delete_share_macos(self, name):
        proc = _run(["sharing", "-r", name], capture_output=True, text=True)
        return proc.returncode == 0

    def _add_user_to_share_macos(self, share_name, username, password):
        shares = {s["name"]: s for s in self._list_shares_macos()}
        share = shares.get(share_name)
        if not share:
            print(f"[macOS] No such share: '{share_name}'")
            return False

        self._configure_macos_user(username, password)

        group_name = share.get("group") or self._macos_group_name(share_name)
        self._ensure_macos_group(group_name)
        self._add_macos_user_to_group(username, group_name)

        print(f"[macOS] Added '{username}' to share '{share_name}'.")
        return True

    def _remove_user_from_share_macos(self, share_name, username):
        shares = {s["name"]: s for s in self._list_shares_macos()}
        share = shares.get(share_name)
        if not share:
            print(f"[macOS] No such share: '{share_name}'")
            return False
        group_name = share.get("group")
        if group_name:
            _run(
                ["dseditgroup", "-o", "edit", "-d", username, "-t", "user", group_name],
                capture_output=True, text=True
            )
        print(f"[macOS] Removed '{username}' from share '{share_name}'.")
        return True

    def _delete_user_macos(self, username):
        _run(
            ["dseditgroup", "-o", "edit", "-d", username, "-t", "user", "com.apple.access_smb"],
            capture_output=True, text=True
        )
        proc = _run(["sysadminctl", "-deleteUser", username], capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"[macOS] Failed to delete user '{username}': {proc.stderr.strip()}")
            return False
        print(f"[macOS] Deleted user '{username}'.")
        return True

    def _delete_group_macos(self, group_name):
        proc = _run(["dseditgroup", "-o", "delete", group_name], capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"[macOS] Failed to delete group '{group_name}': {proc.stderr.strip()}")
            return False
        print(f"[macOS] Deleted group '{group_name}'.")
        return True

    def _add_user_to_group_macos(self, username, group_name):
        if _run(["dscl", ".", "-read", f"/Users/{username}"], capture_output=True, text=True).returncode != 0:
            print(f"[macOS] No such user: '{username}'")
            return False
        if _run(["dscl", ".", "-read", f"/Groups/{group_name}"], capture_output=True, text=True).returncode != 0:
            print(f"[macOS] No such group: '{group_name}'")
            return False
        _run(
            ["dseditgroup", "-o", "edit", "-a", username, "-t", "user", group_name],
            check=True, capture_output=True, text=True
        )
        print(f"[macOS] Added '{username}' to group '{group_name}'.")
        return True

    def _remove_user_from_group_macos(self, username, group_name):
        proc = _run(
            ["dseditgroup", "-o", "edit", "-d", username, "-t", "user", group_name],
            capture_output=True, text=True
        )
        if proc.returncode != 0:
            print(f"[macOS] Failed to remove '{username}' from group '{group_name}': {proc.stderr.strip()}")
            return False
        print(f"[macOS] Removed '{username}' from group '{group_name}'.")
        return True
