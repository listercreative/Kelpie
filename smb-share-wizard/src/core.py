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


class SMBWizard:
    """Platform detection, persistence, privilege elevation, and the actual
    per-OS commands that create/apply an SMB share. No UI code lives here —
    cli.py and gui.py both drive this class."""

    def __init__(self):
        self.system = platform.system()
        self.share_name = ""
        self.share_path = ""
        self.users = []
        self.config_path = os.path.join(self._real_home(), ".config", "kelpie", "shares_config.json")

    def _real_home(self):
        # Root via `sudo` (e.g. the postinst-launched wizard) has HOME=/root;
        # resolve the actual invoking user's home so config/defaults land
        # somewhere they'll actually see them again.
        sudo_user = os.environ.get("SUDO_USER")
        if sudo_user and sudo_user != "root":
            try:
                import pwd
                return pwd.getpwnam(sudo_user).pw_dir
            except (KeyError, ImportError):
                pass
        return os.path.expanduser("~")

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading config: {e}")
        return []

    def save_config(self, new_share):
        shares = self.load_config()
        shares.append(new_share)
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(shares, f, indent=4)

    def delete_share(self, index):
        shares = self.load_config()
        if 0 <= index < len(shares):
            removed = shares.pop(index)
            with open(self.config_path, 'w') as f:
                json.dump(shares, f, indent=4)
            return removed
        return None

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

    def dispatch_execution(self):
        if self.system == "Windows": self.run_windows()
        elif self.system == "Linux": self.run_linux()
        elif self.system == "Darwin": self.run_macos()

    def elevate_and_apply(self, share_data):
        print("Administrator/root privileges are required. Requesting elevation...")
        fd, tmp_path = tempfile.mkstemp(prefix="smbwizard_", suffix=".json")
        os.close(fd)
        try:
            os.chmod(tmp_path, 0o600)
        except Exception:
            pass

        try:
            with open(tmp_path, 'w') as f:
                json.dump(share_data, f)

            if getattr(sys, 'frozen', False):
                relaunch_target = sys.executable
                relaunch_args = ["--apply", tmp_path]
            else:
                relaunch_target = sys.executable
                script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
                relaunch_args = [script, "--apply", tmp_path]

            if self.system == "Windows":
                arg_str = " ".join(f'\\"{a}\\"' for a in relaunch_args)
                cmd = (
                    f"Start-Process -FilePath '{relaunch_target}' "
                    f"-ArgumentList '{arg_str}' "
                    f"-Verb RunAs -Wait"
                )
                subprocess.run(["powershell", "-Command", cmd], check=True)

            elif self.system == "Darwin":
                quoted_args = " ".join(f'"{a}"' for a in relaunch_args)
                apply_cmd = f'{relaunch_target} {quoted_args}'
                escaped = apply_cmd.replace('\\', '\\\\').replace('"', '\\"')
                osa_cmd = f'do shell script "{escaped}" with administrator privileges'
                subprocess.run(["osascript", "-e", osa_cmd], check=True)

            else:  # Linux
                if shutil.which("pkexec"):
                    subprocess.run(["pkexec", relaunch_target, *relaunch_args], check=True)
                else:
                    print("No GUI privilege helper (pkexec) found; falling back to a terminal sudo prompt.")
                    subprocess.run(["sudo", relaunch_target, *relaunch_args], check=True)

            print("Elevated configuration completed.")
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
        wizard.share_name = data['name']
        wizard.share_path = data['path']
        wizard.users = data['users']
        wizard.dispatch_execution()

    def _ps_quote(self, s):
        # Escape for embedding inside a PowerShell single-quoted string.
        return s.replace("'", "''")

    def _windows_group_name(self, share_name):
        cleaned = re.sub(r'[\"/\\\[\]:;|=,+*?<>@\x00-\x1f]', '_', share_name).strip()
        return f"Kelpie_{cleaned or 'Share'}"[:64]

    def _ensure_windows_group(self, group_name):
        escaped = self._ps_quote(group_name)
        cmd = f"if (-not (Get-LocalGroup -Name '{escaped}' -ErrorAction SilentlyContinue)) {{ New-LocalGroup -Name '{escaped}' }}"
        subprocess.run(["powershell", "-Command", cmd], check=True, capture_output=True, text=True)

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
        subprocess.run(["powershell", "-Command", cmd], check=True, capture_output=True, text=True, env=env)

    def _add_windows_user_to_group(self, username, group_name):
        cmd = f"Add-LocalGroupMember -Group '{self._ps_quote(group_name)}' -Member '{self._ps_quote(username)}' -ErrorAction SilentlyContinue"
        subprocess.run(["powershell", "-Command", cmd], check=True, capture_output=True, text=True)

    def _grant_windows_ntfs_permissions(self, share_path, group_name):
        # icacls is invoked directly (no shell), so no PowerShell quoting needed.
        subprocess.run(["icacls", share_path, "/grant", f"{group_name}:(OI)(CI)M"], check=True, capture_output=True, text=True)

    def run_windows(self):
        print(f"[Windows] Executing configuration for '{self.share_name}'...")
        try:
            print(f"  - Ensuring directory exists: {self.share_path}")
            subprocess.run(["powershell", "-Command", f"New-Item -Path '{self._ps_quote(self.share_path)}' -ItemType Directory -Force"], check=True, capture_output=True, text=True)

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
            subprocess.run(["powershell", "-Command", cmd], check=True, capture_output=True, text=True)

            print("[Windows] Success.")
        except subprocess.CalledProcessError as e:
            print(f"[Windows] Error during execution: {e.stderr if e.stderr else e}")
        except Exception as e:
            print(f"[Windows] An unexpected error occurred: {e}")

    def _ensure_samba_installed_linux(self):
        if shutil.which("smbd"):
            return True
        print("[Linux] Samba not found. Attempting installation...")
        try:
            if shutil.which("apt-get"):
                subprocess.run(["apt-get", "update"], check=True, capture_output=True, text=True)
                subprocess.run(["apt-get", "install", "-y", "samba"], check=True, capture_output=True, text=True)
            elif shutil.which("dnf"):
                subprocess.run(["dnf", "install", "-y", "samba"], check=True, capture_output=True, text=True)
            elif shutil.which("yum"):
                subprocess.run(["yum", "install", "-y", "samba"], check=True, capture_output=True, text=True)
            elif shutil.which("pacman"):
                subprocess.run(["pacman", "-S", "--noconfirm", "samba"], check=True, capture_output=True, text=True)
            else:
                print("[Linux] No supported package manager found (tried apt-get/dnf/yum/pacman). Please install Samba manually.")
                return False
        except subprocess.CalledProcessError as e:
            print(f"[Linux] Failed to install Samba: {e.stderr if e.stderr else e}")
            return False
        return shutil.which("smbd") is not None

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
        exists = subprocess.run(["id", username], capture_output=True, text=True).returncode == 0
        if not exists:
            print(f"[Linux] Creating system user '{username}'...")
            subprocess.run(["useradd", "-M", "-s", "/usr/sbin/nologin", username], check=True, capture_output=True, text=True)

        print(f"[Linux] Setting Samba password for '{username}'...")
        proc = subprocess.run(
            ["smbpasswd", "-a", "-s", username],
            input=f"{password}\n{password}\n", capture_output=True, text=True
        )
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, "smbpasswd", output=proc.stdout, stderr=proc.stderr)
        subprocess.run(["smbpasswd", "-e", username], check=True, capture_output=True, text=True)

    def _share_group_name(self, share_name):
        slug = re.sub(r'[^a-z0-9_-]', '_', share_name.lower()).strip('_-') or "share"
        return f"smbshare_{slug}"[:32]

    def _ensure_group(self, group_name):
        exists = subprocess.run(["getent", "group", group_name], capture_output=True, text=True).returncode == 0
        if not exists:
            print(f"[Linux] Creating group '{group_name}'...")
            subprocess.run(["groupadd", group_name], check=True, capture_output=True, text=True)

    def _add_user_to_group(self, username, group_name):
        subprocess.run(["usermod", "-aG", group_name, username], check=True, capture_output=True, text=True)

    def _expose_share_directory(self, share_path, group_name):
        # smb.conf's "read only = no" only governs the SMB protocol layer;
        # smbd still enforces real Unix permissions when it impersonates the
        # authenticated user's UID, so the directory itself must actually be
        # writable by that user's group. setgid (02770) makes new files
        # inherit the share's group too, instead of each writer's primary
        # group.
        print(f"[Linux] Granting group '{group_name}' read/write on '{share_path}'...")
        shutil.chown(share_path, group=group_name)
        os.chmod(share_path, 0o2770)

    def _restart_samba_service(self):
        print("[Linux] Restarting Samba services...")
        for services in (["smbd", "nmbd"], ["smb", "nmb"]):
            try:
                for svc in services:
                    subprocess.run(["systemctl", "restart", svc], check=True, capture_output=True, text=True)
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
            os.makedirs(self.share_path, exist_ok=True)

            self._add_samba_share_config(self.share_name, self.share_path, [u['username'] for u in self.users])

            group_name = self._share_group_name(self.share_name)
            self._ensure_group(group_name)

            for user in self.users:
                self._configure_linux_user(user['username'], user['password'])
                self._add_user_to_group(user['username'], group_name)

            self._expose_share_directory(self.share_path, group_name)

            self._restart_samba_service()

            print("[Linux] Success.")
        except subprocess.CalledProcessError as e:
            print(f"[Linux] Error during execution: {e.stderr if e.stderr else e}")
        except Exception as e:
            print(f"[Linux] An unexpected error occurred: {e}")

    def _configure_macos_user(self, username, password):
        exists = subprocess.run(["dscl", ".", "-read", f"/Users/{username}"], capture_output=True, text=True).returncode == 0
        if not exists:
            print(f"[macOS] Creating user '{username}'...")
            subprocess.run(["sysadminctl", "-addUser", username, "-password", password], check=True, capture_output=True, text=True)
        else:
            print(f"[macOS] Setting password for existing user '{username}'...")
            subprocess.run(["dscl", ".", "-passwd", f"/Users/{username}", password], check=True, capture_output=True, text=True)
        subprocess.run(["dseditgroup", "-o", "edit", "-a", username, "-t", "user", "com.apple.access_smb"], check=True, capture_output=True, text=True)

    def _macos_group_name(self, share_name):
        slug = re.sub(r'[^a-zA-Z0-9_-]', '_', share_name).strip('_-') or 'share'
        return f"kelpie_{slug}"

    def _ensure_macos_group(self, group_name):
        exists = subprocess.run(["dscl", ".", "-read", f"/Groups/{group_name}"], capture_output=True, text=True).returncode == 0
        if not exists:
            print(f"[macOS] Creating group '{group_name}'...")
            subprocess.run(["dseditgroup", "-o", "create", group_name], check=True, capture_output=True, text=True)

    def _add_macos_user_to_group(self, username, group_name):
        subprocess.run(["dseditgroup", "-o", "edit", "-a", username, "-t", "user", group_name], check=True, capture_output=True, text=True)

    def _expose_macos_share_directory(self, share_path, group_name):
        # Same underlying issue as Linux: macOS filesystem permissions are
        # POSIX, and smbd still enforces them when impersonating the
        # authenticated user - the share's own settings don't override that.
        print(f"[macOS] Granting group '{group_name}' read/write on '{share_path}'...")
        subprocess.run(["chgrp", group_name, share_path], check=True, capture_output=True, text=True)
        os.chmod(share_path, 0o2770)

    def _create_macos_share(self, share_name, share_path):
        print(f"[macOS] Creating share '{share_name}' at '{share_path}'...")
        subprocess.run(["sharing", "-a", share_path, "-S", share_name, "-s", "001"], check=True, capture_output=True, text=True)

    def _enable_macos_smb_sharing(self):
        print("[macOS] Enabling SMB file sharing service...")
        subprocess.run(["launchctl", "enable", "system/com.apple.smbd"], check=True, capture_output=True, text=True)
        subprocess.run(["launchctl", "kickstart", "-k", "system/com.apple.smbd"], check=True, capture_output=True, text=True)

    def run_macos(self):
        print(f"[macOS] Executing configuration for '{self.share_name}'...")
        try:
            print(f"  - Ensuring directory exists: {self.share_path}")
            os.makedirs(self.share_path, exist_ok=True)

            group_name = self._macos_group_name(self.share_name)
            self._ensure_macos_group(group_name)

            for user in self.users:
                self._configure_macos_user(user['username'], user['password'])
                self._add_macos_user_to_group(user['username'], group_name)

            self._expose_macos_share_directory(self.share_path, group_name)

            self._create_macos_share(self.share_name, self.share_path)
            self._enable_macos_smb_sharing()

            print("[macOS] Success.")
        except subprocess.CalledProcessError as e:
            print(f"[macOS] Error during execution: {e.stderr if e.stderr else e}")
        except Exception as e:
            print(f"[macOS] An unexpected error occurred: {e}")
