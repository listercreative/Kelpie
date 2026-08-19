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

    try:
        if len(sys.argv) >= 3 and sys.argv[1] == "--apply":
            from core import SMBWizard
            SMBWizard.apply_from_file(sys.argv[2])
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
