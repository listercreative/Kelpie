import sys
import os

if __name__ == "__main__":
    # A PyInstaller --windowed build has no console, so sys.stdout/stderr are
    # None; core.py logs via bare print(), which would crash without this.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")


    def run_tui_then_basic():
        try:
            from tui import TUIWizard
            TUIWizard().run()
        except Exception as e:
            print(f"Terminal UI unavailable ({e}); falling back to the basic prompt-based wizard.")
            from cli import CLIWizard
            CLIWizard().start()

    # Each of these is a relaunch target for SMBWizard._elevated_relaunch():
    # the flag matches what elevate_and_*() passed as arg_flag, and the
    # value is the *_from_file() entry point that consumes the temp JSON
    # payload written before elevation.
    RELAUNCH_HANDLERS = {
        "--apply": "apply_from_file",
        "--delete-share": "delete_share_from_file",
        "--add-user": "add_user_to_share_from_file",
        "--revoke-user": "revoke_share_access_from_file",
        "--delete-user": "delete_user_from_file",
        "--delete-group": "delete_group_from_file",
        "--assign-group": "assign_user_to_group_from_file",
        "--revoke-group": "revoke_group_membership_from_file",
    }

    try:
        if len(sys.argv) >= 3 and sys.argv[1] in RELAUNCH_HANDLERS:
            from core import SMBWizard
            getattr(SMBWizard, RELAUNCH_HANDLERS[sys.argv[1]])(sys.argv[2])
        elif "--cli" in sys.argv:
            run_tui_then_basic()
        else:
            try:
                from gui import GUIWizard
                GUIWizard().run()
            except Exception as e:
                print(f"GUI unavailable ({e}); falling back to the terminal wizard.")
                run_tui_then_basic()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(0)
