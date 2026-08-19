import getpass

from rich.console import Console
from rich.panel import Panel

from core import SMBWizard

console = Console()


class CLIWizard(SMBWizard):
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
            username = console.input("   Username: ").strip()
            if not username: break
            password = getpass.getpass(f"   Password for {username}: ")
            self.users.append({'username': username, 'password': password})

        if not self.users:
            console.print("[red]Error: At least one user must be configured.[/red]")
            return False

        share_data = {
            "name": self.share_name,
            "path": self.share_path,
            "users": [{"username": u["username"]} for u in self.users]
        }
        self.save_config(share_data)
        console.print("\n[green]Share configuration saved to persistent storage.[/green]")
        return True

    def manage_shares(self):
        shares = self.load_config()
        if not shares:
            print("\nNo existing shares found.")
            return

        print("\n--- Existing Shares ---")
        for i, share in enumerate(shares):
            print(f"{i}. {share['name']} ({share.get('path', 'Unknown')})")

        choice = input("\nEnter number to delete, or press Enter to return: ").strip()
        if choice.isdigit():
            removed = self.delete_share(int(choice))
            if removed:
                print(f"Removed share: {removed['name']}")
            else:
                print("Invalid index.")

    def start(self):
        while True:
            print("\n=== Kelpie Menu ===")
            print("1. Create New Share")
            print("2. Manage Existing Shares")
            print("3. Exit")
            choice = input("Select an option: ").strip()

            if choice == '1':
                if self.collect_user_input():
                    if self.has_admin_privileges():
                        self.dispatch_execution()
                    else:
                        self.elevate_and_apply({
                            "name": self.share_name,
                            "path": self.share_path,
                            "users": self.users
                        })
            elif choice == '2':
                self.manage_shares()
            elif choice == '3':
                print("Goodbye!")
                break
            else:
                print("Invalid option.")
