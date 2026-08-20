import getpass

from rich.console import Console
from rich.panel import Panel

from core import SMBWizard

console = Console()


class CLIWizard(SMBWizard):
    def _pick_or_type_username(self, prompt="   Username: "):
        # Existing usernames one selection away (no risk of a typo against a
        # name that already exists), but typing a new one still works -
        # this can create a brand-new user, unlike group membership which
        # requires an existing one.
        users = self.list_users()
        if not users:
            return console.input(prompt).strip()
        print("   Existing users:")
        for i, u in enumerate(users):
            print(f"     {i}. {u['username']}")
        raw = console.input(f"{prompt}(number to pick existing, or type new): ").strip()
        if raw.isdigit() and int(raw) < len(users):
            return users[int(raw)]['username']
        return raw

    def _offer_qr_code(self, share_name, username, password):
        # Only ever offered right when a password was just set (share
        # creation / add user) - Kelpie never persists plaintext passwords,
        # so this can't be regenerated later for an existing user.
        confirm = console.input("\nShow a LockNAS QR code for this user? [y/N] ").strip().lower()
        if confirm not in ('y', 'yes'):
            return
        try:
            import qrcode
        except ImportError:
            console.print("[red]The 'qrcode' package isn't installed.[/red]")
            return
        console.print(
            "[bold red]Contains this user's password in plain sight - only display "
            "it somewhere private.[/bold red]"
        )
        payload = self.build_locknas_qr_payload(share_name, username, password)
        qr = qrcode.QRCode()
        qr.add_data(payload)
        qr.make()
        qr.print_ascii(tty=True)
        console.input("\nPress Enter to continue...")

    def collect_user_input(self):
        console.print(Panel("[bold blue]New SMB Share Creation[/bold blue]", expand=False))

        self.share_name = console.input("[bold]1. Enter the name for the share: [/bold]").strip()
        if not self.share_name:
            console.print("[red]Error: Name cannot be empty.[/red]")
            return False

        default_path = self.default_share_path(self.share_name)
        console.print(f"[bold]2. Enter path (default: {default_path}) or use [D] for directory picker:[/bold]")
        path_input = console.input("[cyan]> [/cyan]").strip()

        if path_input.upper() == 'D':
            selected_dir = self.select_directory()
            self.share_path = selected_dir if selected_dir else default_path
        elif path_input:
            self.share_path = path_input
        else:
            self.share_path = default_path

        console.print("\n[bold]3. User Configuration (Enter username, then password. Empty username to finish)[/bold]")
        self.users = []
        while True:
            username = self._pick_or_type_username()
            if not username: break
            password = getpass.getpass(f"   Password for {username}: ")
            self.users.append({'username': username, 'password': password})

        return True

    def manage_shares(self):
        shares = self.list_shares()
        if not shares:
            print("\nNo existing shares found.")
            return

        print("\n--- Existing Shares ---")
        for i, share in enumerate(shares):
            users = ", ".join(u["username"] for u in share.get("users", [])) or "(none)"
            print(f"{i}. {share['name']} ({share.get('path', 'Unknown')}) - users: {users}")

        choice = input("\nEnter share number to manage, or press Enter to return: ").strip()
        if not choice.isdigit():
            return
        idx = int(choice)
        if not (0 <= idx < len(shares)):
            print("Invalid index.")
            return
        share = shares[idx]

        print(f"\n--- {share['name']} ---")
        print("1. Add user")
        print("2. Delete share")
        print("3. Back")
        sub = input("Select an option: ").strip()

        if sub == '1':
            username = self._pick_or_type_username()
            if not username:
                console.print("[red]Username cannot be empty.[/red]")
                return
            password = getpass.getpass(f"   Password for {username}: ")
            if self.grant_share_access(share['name'], username, password):
                print(f"Added '{username}' to share '{share['name']}'.")
                self._offer_qr_code(share['name'], username, password)
            else:
                print("Failed to add user (or elevation was cancelled).")
        elif sub == '2':
            if self.remove_share(share['name']):
                print(f"Removed share: {share['name']}")
            else:
                print("Failed to remove share (or elevation was cancelled).")

    def manage_users_and_groups(self):
        while True:
            print("\n=== Users & Groups ===")
            print("1. Users")
            print("2. Groups")
            print("3. Back")
            choice = input("Select an option: ").strip()
            if choice == '1':
                self._manage_users_screen()
            elif choice == '2':
                self._manage_groups_screen()
            elif choice == '3':
                return
            else:
                print("Invalid option.")

    def _manage_users_screen(self):
        while True:
            users = self.list_users()

            console.print("\n[bold]--- Users ---[/bold]")
            if not users:
                print("No users found.")
                return
            for i, u in enumerate(users):
                print(f"U{i}. {u['username']}")
                for g in u["groups"]:
                    print(f"\tgroup: {g}")
                for s in u["shares"]:
                    print(f"\tshare: {s}")

            print("\na<n> = assign to a(nother) group")
            print("g<n> = remove from a group")
            print("r<n> = revoke access to a share")
            print("d<n> = delete the user entirely")
            choice = input("Select an option, or press Enter to return: ").strip().lower()
            if not choice:
                return

            kind, rest = choice[0], choice[1:]
            if kind not in ('a', 'g', 'r', 'd') or not rest.isdigit() or not (0 <= int(rest) < len(users)):
                print("Invalid option.")
                continue
            user = users[int(rest)]

            if kind == 'a':
                groups = self.list_groups()
                if not groups:
                    print("No groups exist to assign to.")
                    continue
                print("Groups:")
                for gi, g in enumerate(groups):
                    print(f"  {gi}. {g['name']}")
                gidx = input("Which group number? ").strip()
                if not gidx.isdigit() or not (0 <= int(gidx) < len(groups)):
                    print("Invalid group number.")
                    continue
                group_name = groups[int(gidx)]['name']
                if self.assign_user_to_group(user['username'], group_name):
                    print(f"Added '{user['username']}' to group '{group_name}'.")
                else:
                    print("Failed to assign group (or elevation was cancelled).")
            elif kind == 'g':
                if not user["groups"]:
                    print(f"'{user['username']}' isn't in any group.")
                    continue
                print("Groups:")
                for gi, gname in enumerate(user["groups"]):
                    print(f"  {gi}. {gname}")
                gidx = input("Which group number to remove from? ").strip()
                if not gidx.isdigit() or not (0 <= int(gidx) < len(user["groups"])):
                    print("Invalid group number.")
                    continue
                group_name = user["groups"][int(gidx)]
                if self.revoke_group_membership(user['username'], group_name):
                    print(f"Removed '{user['username']}' from group '{group_name}'.")
                else:
                    print("Failed to remove from group (or elevation was cancelled).")
            elif kind == 'r':
                if not user["shares"]:
                    print(f"'{user['username']}' has no share access to revoke.")
                    continue
                print("Shares:")
                for si, sname in enumerate(user["shares"]):
                    print(f"  {si}. {sname}")
                sidx = input("Which share number to revoke access to? ").strip()
                if not sidx.isdigit() or not (0 <= int(sidx) < len(user["shares"])):
                    print("Invalid share number.")
                    continue
                share_name = user["shares"][int(sidx)]
                if self.revoke_share_access(share_name, user["username"]):
                    print(f"Revoked '{user['username']}''s access to '{share_name}'.")
                else:
                    print("Failed to revoke access (or elevation was cancelled).")
            else:
                confirm = input(f"Delete user '{user['username']}' entirely? [y/N] ").strip().lower()
                if confirm not in ('y', 'yes'):
                    continue
                if self.remove_user(user["username"]):
                    print(f"Deleted user '{user['username']}'.")
                else:
                    print("Failed to delete user (or elevation was cancelled).")

    def _manage_groups_screen(self):
        while True:
            groups = self.list_groups()

            console.print("\n[bold]--- Groups ---[/bold]")
            if not groups:
                print("No managed groups found.")
                return
            for i, g in enumerate(groups):
                print(f"G{i}. {g['name']}")
                for m in g["members"]:
                    print(f"\tuser: {m}")
                for s in g["shares"]:
                    print(f"\tshare: {s}")

            print("\nm<n> = add a member")
            print("v<n> = remove a member")
            print("x<n> = delete the group")
            choice = input("Select an option, or press Enter to return: ").strip().lower()
            if not choice:
                return

            kind, rest = choice[0], choice[1:]
            if kind not in ('m', 'v', 'x') or not rest.isdigit() or not (0 <= int(rest) < len(groups)):
                print("Invalid option.")
                continue
            group = groups[int(rest)]

            if kind == 'm':
                # A pick-list of existing users, not free text: adding a
                # member requires an already-existing account (unlike a
                # share's "Add user", which can create one) - the underlying
                # action validates and refuses otherwise, so free text here
                # could only ever fail.
                users = self.list_users()
                if not users:
                    print("No existing users to add. Create one via a share's 'Add user' first.")
                    continue
                print("Users:")
                for ui, u in enumerate(users):
                    print(f"  {ui}. {u['username']}")
                uidx = input("Which user number to add? ").strip()
                if not uidx.isdigit() or not (0 <= int(uidx) < len(users)):
                    print("Invalid user number.")
                    continue
                username = users[int(uidx)]['username']
                if self.assign_user_to_group(username, group['name']):
                    print(f"Added '{username}' to group '{group['name']}'.")
                else:
                    print("Failed to add member (or elevation was cancelled).")
            elif kind == 'v':
                if not group["members"]:
                    print(f"'{group['name']}' has no members.")
                    continue
                print("Members:")
                for mi, mname in enumerate(group["members"]):
                    print(f"  {mi}. {mname}")
                midx = input("Which member number to remove? ").strip()
                if not midx.isdigit() or not (0 <= int(midx) < len(group["members"])):
                    print("Invalid member number.")
                    continue
                member_name = group["members"][int(midx)]
                if self.revoke_group_membership(member_name, group['name']):
                    print(f"Removed '{member_name}' from group '{group['name']}'.")
                else:
                    print("Failed to remove member (or elevation was cancelled).")
            else:
                confirm = input(f"Delete group '{group['name']}'? [y/N] ").strip().lower()
                if confirm not in ('y', 'yes'):
                    continue
                if self.remove_group(group["name"]):
                    print(f"Deleted group '{group['name']}'.")
                else:
                    print("Failed to delete group (or elevation was cancelled).")

    def start(self):
        while True:
            options = ["Create New Share", "Manage Existing Shares", "Manage Users & Groups"]
            if self.gui_available():
                options.append("Launch Desktop UI")
            options.append("Exit")

            print("\n=== Kelpie Menu ===")
            for i, opt in enumerate(options, start=1):
                print(f"{i}. {opt}")
            choice = input("Select an option: ").strip()

            try:
                selected = options[int(choice) - 1]
            except (ValueError, IndexError):
                print("Invalid option.")
                continue

            if selected == "Create New Share":
                if self.collect_user_input():
                    if self.has_admin_privileges():
                        self.dispatch_execution()
                    else:
                        self.elevate_and_apply({
                            "name": self.share_name,
                            "path": self.share_path,
                            "users": self.users
                        })
                    # Checked against live share state, not a return value -
                    # dispatch_execution()/elevate_and_apply() don't report
                    # success directly, and this works the same regardless
                    # of which path ran.
                    if any(s['name'] == self.share_name for s in self.list_shares()):
                        for user in self.users:
                            self._offer_qr_code(self.share_name, user['username'], user['password'])
            elif selected == "Manage Existing Shares":
                self.manage_shares()
            elif selected == "Manage Users & Groups":
                self.manage_users_and_groups()
            elif selected == "Launch Desktop UI":
                try:
                    from gui import GUIWizard
                    GUIWizard().run()
                except Exception as e:
                    print(f"Could not launch the desktop UI: {e}")
            elif selected == "Exit":
                print("Goodbye!")
                break
