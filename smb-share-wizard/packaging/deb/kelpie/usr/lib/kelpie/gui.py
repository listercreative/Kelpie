import contextlib
import io
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

from core import SMBWizard


class AddUserDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Add User")
        self.resizable(False, False)
        self.transient(parent)
        self.result = None

        ttk.Label(self, text="Username:").grid(row=0, column=0, sticky="e", padx=8, pady=6)
        self.username_entry = ttk.Entry(self)
        self.username_entry.grid(row=0, column=1, padx=8, pady=6)

        ttk.Label(self, text="Password:").grid(row=1, column=0, sticky="e", padx=8, pady=6)
        self.password_entry = ttk.Entry(self, show="*")
        self.password_entry.grid(row=1, column=1, padx=8, pady=6)

        ttk.Label(self, text="Confirm Password:").grid(row=2, column=0, sticky="e", padx=8, pady=6)
        self.confirm_entry = ttk.Entry(self, show="*")
        self.confirm_entry.grid(row=2, column=1, padx=8, pady=6)

        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=4)

        self.username_entry.focus_set()
        self.grab_set()
        self.wait_window(self)

    def _on_ok(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        confirm = self.confirm_entry.get()

        if not username:
            messagebox.showerror("Invalid input", "Username cannot be empty.", parent=self)
            return
        if not password:
            messagebox.showerror("Invalid input", "Password cannot be empty.", parent=self)
            return
        if password != confirm:
            messagebox.showerror("Invalid input", "Passwords do not match.", parent=self)
            return

        self.result = {"username": username, "password": password}
        self.destroy()


class GUIWizard:
    def __init__(self):
        self.wizard = SMBWizard()
        self.pending_users = []

        self.root = tk.Tk()
        self.root.title("Kelpie")
        self.root.geometry("560x600")

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.create_tab = ttk.Frame(notebook)
        self.manage_tab = ttk.Frame(notebook)
        notebook.add(self.create_tab, text="Create Share")
        notebook.add(self.manage_tab, text="Manage Shares")
        notebook.bind("<<NotebookTabChanged>>", lambda e: self._refresh_manage_list())

        self._build_create_tab()
        self._build_manage_tab()
        self._refresh_manage_list()

    def run(self):
        self.root.mainloop()

    def _build_create_tab(self):
        frame = self.create_tab

        form = ttk.Frame(frame)
        form.pack(fill="x", padx=8, pady=8)

        ttk.Label(form, text="Share Name:").grid(row=0, column=0, sticky="e", pady=4)
        self.name_entry = ttk.Entry(form, width=40)
        self.name_entry.grid(row=0, column=1, columnspan=2, sticky="w", pady=4)

        ttk.Label(form, text="Folder Path:").grid(row=1, column=0, sticky="e", pady=4)
        self.path_entry = ttk.Entry(form, width=32)
        self.path_entry.grid(row=1, column=1, sticky="w", pady=4)
        self.path_entry.insert(0, self.wizard.default_share_path())
        ttk.Button(form, text="Browse...", command=self._browse_path).grid(row=1, column=2, padx=4)

        users_label_frame = ttk.LabelFrame(frame, text="Users")
        users_label_frame.pack(fill="both", expand=False, padx=8, pady=8)

        self.users_list = ttk.Treeview(users_label_frame, columns=("username",), show="headings", height=5)
        self.users_list.heading("username", text="Username")
        self.users_list.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)

        users_btn_frame = ttk.Frame(users_label_frame)
        users_btn_frame.pack(side="left", fill="y", padx=4, pady=4)
        ttk.Button(users_btn_frame, text="Add User...", command=self._add_user).pack(fill="x", pady=2)
        ttk.Button(users_btn_frame, text="Remove Selected", command=self._remove_user).pack(fill="x", pady=2)

        action_frame = ttk.Frame(frame)
        action_frame.pack(fill="x", padx=8, pady=4)
        self.create_button = ttk.Button(action_frame, text="Create Share", command=self._on_create_share)
        self.create_button.pack(side="left")
        self.status_label = ttk.Label(action_frame, text="Idle")
        self.status_label.pack(side="left", padx=10)

        ttk.Label(frame, text="Log:").pack(anchor="w", padx=8)
        self.log_text = ScrolledText(frame, height=10, state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _build_manage_tab(self):
        frame = self.manage_tab

        self.shares_list = ttk.Treeview(frame, columns=("name", "path"), show="headings")
        self.shares_list.heading("name", text="Share Name")
        self.shares_list.heading("path", text="Path")
        self.shares_list.pack(fill="both", expand=True, padx=8, pady=8)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_manage_list).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Delete Selected", command=self._delete_selected_share).pack(side="left", padx=4)

    def _browse_path(self):
        selected = filedialog.askdirectory(parent=self.root, title="Select Folder to Share")
        if selected:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, selected)

    def _add_user(self):
        dialog = AddUserDialog(self.root)
        if dialog.result:
            self.pending_users.append(dialog.result)
            self.users_list.insert("", tk.END, values=(dialog.result["username"],))

    def _remove_user(self):
        selection = self.users_list.selection()
        for item in selection:
            index = self.users_list.index(item)
            del self.pending_users[index]
            self.users_list.delete(item)

    def _refresh_manage_list(self):
        for item in self.shares_list.get_children():
            self.shares_list.delete(item)
        for share in self.wizard.load_config():
            self.shares_list.insert("", tk.END, values=(share.get("name", "?"), share.get("path", "Unknown")))

    def _delete_selected_share(self):
        selection = self.shares_list.selection()
        if not selection:
            return
        index = self.shares_list.index(selection[0])
        removed = self.wizard.delete_share(index)
        if removed:
            messagebox.showinfo("Removed", f"Removed share: {removed['name']}")
        self._refresh_manage_list()

    def _append_log(self, text):
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def _on_create_share(self):
        name = self.name_entry.get().strip()
        path = self.path_entry.get().strip() or self.wizard.default_share_path()

        if not name:
            messagebox.showerror("Invalid input", "Share name cannot be empty.")
            return
        if not self.pending_users:
            messagebox.showerror("Invalid input", "At least one user must be configured.")
            return

        self.wizard.share_name = name
        self.wizard.share_path = path
        self.wizard.users = list(self.pending_users)

        self.wizard.save_config({
            "name": name,
            "path": path,
            "users": [{"username": u["username"]} for u in self.wizard.users]
        })
        self._refresh_manage_list()

        self.create_button.configure(state="disabled")
        self.status_label.configure(text="Working...")
        self._append_log(f"\n--- Creating share '{name}' ---\n")

        threading.Thread(target=self._apply_worker, daemon=True).start()

        self.name_entry.delete(0, tk.END)
        self.path_entry.delete(0, tk.END)
        self.path_entry.insert(0, self.wizard.default_share_path())
        self.pending_users = []
        for item in self.users_list.get_children():
            self.users_list.delete(item)

    def _apply_worker(self):
        buffer = io.StringIO()
        try:
            with contextlib.redirect_stdout(buffer):
                if self.wizard.has_admin_privileges():
                    self.wizard.dispatch_execution()
                else:
                    print("Not running with elevated privileges — requesting elevation via the OS's native prompt.")
                    self.wizard.elevate_and_apply({
                        "name": self.wizard.share_name,
                        "path": self.wizard.share_path,
                        "users": self.wizard.users
                    })
        except Exception as e:
            buffer.write(f"\nUnexpected error: {e}\n")

        self.root.after(0, lambda: self._apply_done(buffer.getvalue()))

    def _apply_done(self, log_output):
        self._append_log(log_output)
        self.create_button.configure(state="normal")
        self.status_label.configure(text="Idle")
        messagebox.showinfo("Done", "Configuration attempt finished — see the log for details.")


def main():
    GUIWizard().run()


if __name__ == "__main__":
    main()
