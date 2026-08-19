import curses
import os

from core import SMBWizard

KELPIE_LOGO = [
    '                                                 -# :.',
    '                                           .:..:*@@=#',
    '                                        -*%**%@@@@@@@+',
    '                                      *@@*+@@@@@@@@@+%@.',
    '                                     %@@+*@@@@@+@@@@@@@@+',
    '                                    *@@%=@@@@@@*+%@%%@@@@%=',
    '                                    @@@=%@@@@@@+    .-+@@@*',
    '                     .=*+=-.       -@@@-@@@@@@@=       .:',
    '                       :@@%%#*-   .+*#@-@@@@@@@@.',
    '                        @@%%@#*#+     .-#@@@@@@@@.',
    '                      =%@%@@#*@#+@=     +@@@@@@@@@.',
    '                      #%#*==**-*+:**-.--#@@@@@@@@@%',
    '                 ...-+#%@@@@@@@@@@@@@@%#@@@@@@@@@@@-',
    '             :+*++#@@@%*++=-+*%@@%#***%@@@@@@@@@@@@=',
    '  .....:-+*%@#=:**+======------====+**=--+#@@@%#***+*##*+++=-:.',
    ' .:-+*****+===++==---------===-..:--------=++*###****+===:.',
    '        ..::---:::::::--==========+++++**#*+++++++++--:',
    '                    ..:::--========-::..:-==++===-:',
]

# Per-cell xterm-256 color index, sampled from the real logo's RGB.
# Used when the terminal supports 256 colors.
KELPIE_LOGO_COLORS_256 = [
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 72, 72, 0, 24, 60],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 66, 66, 66, 72, 72, 72, 66, 72, 65, 24],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 66, 66, 66, 66, 72, 72, 72, 72, 72, 71, 71, 72, 72, 72],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 66, 66, 66, 66, 72, 72, 72, 72, 66, 29, 72, 72, 72, 65, 65, 65, 72, 72],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 66, 66, 66, 66, 72, 72, 72, 66, 24, 30, 66, 66, 72, 72, 72, 66, 72, 72, 72, 72],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 66, 66, 66, 66, 66, 72, 72, 66, 24, 66, 30, 66, 24, 66, 66, 66, 30, 24, 30, 66, 72, 66, 66],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 66, 66, 66, 66, 66, 66, 66, 24, 24, 66, 66, 66, 0, 0, 0, 0, 60, 24, 24, 24, 66, 66, 66],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 66, 66, 66, 66, 66, 66, 66, 0, 0, 0, 0, 0, 0, 0, 66, 66, 66, 66, 66, 66, 66, 66, 24, 30, 66, 71, 66, 0, 0, 0, 0, 0, 0, 0, 59, 24],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 66, 66, 66, 66, 66, 66, 66, 66, 0, 0, 0, 66, 66, 66, 66, 66, 66, 66, 66, 66, 24, 24, 66, 71, 71, 71],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 66, 66, 66, 66, 66, 66, 66, 66, 66, 0, 0, 0, 0, 0, 66, 66, 66, 66, 66, 24, 24, 30, 66, 71, 71, 71],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 0, 0, 0, 0, 0, 66, 66, 66, 30, 24, 24, 66, 71, 71, 107, 107],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 24, 24, 30, 66, 107, 107, 107],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 30, 24, 24, 24, 66, 107, 107, 107, 107],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 66, 66, 66, 66, 66, 66, 66, 24, 24, 24, 23, 59, 59, 59, 23, 23, 23, 24, 24, 24, 30, 66, 66, 66, 66, 66, 66, 66, 66, 30, 24, 24, 24, 66, 71, 107, 107, 107, 107],
    [0, 0, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 30, 23, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 60, 24, 24, 24, 23, 60, 59, 59, 23, 24, 24, 65, 65, 107, 107, 107, 107, 107, 107, 71, 65, 65, 65, 65, 65, 65, 65, 65, 65, 102],
    [0, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 72, 107, 107, 107, 107, 107, 107, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 65, 107, 107, 107, 71, 71, 71, 65, 65, 65, 66, 66, 66, 66, 66, 66, 66, 66, 66],
    [0, 0, 0, 0, 0, 0, 0, 0, 108, 107, 108, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 71, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 72, 107, 107, 107],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 107, 101, 65, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 101, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107],
]

# Fallback for basic 8-/16-color terminals: 0/1 = dim/bold green
# (head+neck), 2/3 = dim/bold cyan (mane/tail/waves).
KELPIE_LOGO_COLORS = [
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 2, 2],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 1, 1, 1, 2, 3, 2, 2],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 3, 1, 1, 3, 2, 2, 3, 3, 3, 2, 2, 2, 1, 3],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 3, 3, 3, 2, 2, 2, 2, 2, 3, 3, 3, 2, 3, 3, 3, 3],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 3, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 2, 2],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 3, 2, 2, 2, 2, 2, 2, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 0, 0, 0, 0, 0, 0, 0, 2, 2],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 3, 1, 1, 1],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 1, 1, 1],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1],
    [0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 0, 1, 1, 1, 1, 1, 1, 1, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
    [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
]


class TUIWizard:
    """Curses-based terminal UI: arrow-key menus and a crude directory
    picker, for headless boxes with no display but a real TTY. Data
    collection happens entirely inside curses; the actual privileged
    apply step runs after curses tears down, so pkexec/sudo prompts and
    plain status prints behave normally."""

    def __init__(self):
        self.wizard = SMBWizard()
        self._color_ok = False
        self._color_mode = "mono"
        self._pair_256 = {}

    def run(self):
        os.environ.setdefault("ESCDELAY", "25")
        result = {}
        curses.wrapper(self._main, result)
        share_data = result.get("share_data")
        if share_data:
            self._apply_outside_curses(share_data)

    def _init_colors(self):
        self._color_mode = "mono"
        self._pair_256 = {}
        try:
            curses.start_color()
            try:
                curses.use_default_colors()
                bg = -1
            except curses.error:
                bg = curses.COLOR_BLACK

            if curses.COLORS >= 256:
                # One curses color pair per distinct xterm-256 color actually
                # used in the logo (~15), matched to the real PNG's RGB.
                used = sorted({v for row in KELPIE_LOGO_COLORS_256 for v in row if v})
                for pair_num, color_idx in enumerate(used, start=1):
                    if pair_num >= curses.COLOR_PAIRS:
                        break
                    curses.init_pair(pair_num, color_idx, bg)
                    self._pair_256[color_idx] = pair_num
                self._color_mode = "256"
            else:
                curses.init_pair(1, curses.COLOR_GREEN, bg)
                curses.init_pair(2, curses.COLOR_CYAN, bg)
                self._color_mode = "8"
            self._color_ok = True
        except curses.error:
            self._color_ok = False
            self._color_mode = "mono"

    def _banner_attr(self, color_idx_8, color_idx_256=None):
        if not self._color_ok:
            return curses.A_BOLD
        if self._color_mode == "256" and color_idx_256 is not None:
            pair = self._pair_256.get(color_idx_256)
            if pair is not None:
                return curses.color_pair(pair)
            return curses.A_BOLD
        pair = curses.color_pair(1 if color_idx_8 in (0, 1) else 2)
        return pair | curses.A_BOLD if color_idx_8 in (1, 3) else pair

    def _apply_outside_curses(self, share_data):
        self.wizard.share_name = share_data["name"]
        self.wizard.share_path = share_data["path"]
        self.wizard.users = share_data["users"]
        print(f"\n--- Applying configuration for '{share_data['name']}' ---")
        if self.wizard.has_admin_privileges():
            self.wizard.dispatch_execution()
        else:
            self.wizard.elevate_and_apply(share_data)

    def _main(self, stdscr, result):
        curses.curs_set(0)
        self._init_colors()
        while True:
            choice = self._menu(
                stdscr, "Kelpie", ["Create New Share", "Manage Existing Shares", "Exit"],
                banner=KELPIE_LOGO, banner_colors=KELPIE_LOGO_COLORS, banner_colors_256=KELPIE_LOGO_COLORS_256
            )
            if choice is None or choice == 2:
                return
            if choice == 0:
                share_data = self._create_share_flow(stdscr)
                if share_data:
                    result["share_data"] = share_data
                    return
            elif choice == 1:
                self._manage_shares_flow(stdscr)

    # ---- generic widgets ----

    def _menu(self, stdscr, title, options, subtitle=None, banner=None, banner_colors=None,
              banner_colors_256=None, body=None):
        idx = 0
        curses.curs_set(0)
        stdscr.keypad(True)
        while True:
            stdscr.erase()
            h, w = stdscr.getmaxyx()

            show_banner = bool(
                banner and h >= len(banner) + len(options) + 8
                and w >= max(len(l) for l in banner) + 4
            )

            row = 0
            if show_banner:
                for li, line in enumerate(banner):
                    colors = banner_colors[li] if banner_colors else None
                    colors256 = banner_colors_256[li] if banner_colors_256 else None
                    if colors:
                        for ci, ch in enumerate(line[:w - 4]):
                            c256 = colors256[ci] if colors256 else None
                            try:
                                stdscr.addch(row, 2 + ci, ch, self._banner_attr(colors[ci], c256))
                            except curses.error:
                                pass
                    else:
                        try:
                            stdscr.addstr(row, 2, line[:w - 4], curses.A_BOLD)
                        except curses.error:
                            pass
                    row += 1
                row += 1

            try:
                stdscr.addstr(row, 2, title[:w - 4], curses.A_BOLD)
            except curses.error:
                pass
            row += 1
            if subtitle:
                try:
                    stdscr.addstr(row, 2, subtitle[:w - 4])
                except curses.error:
                    pass
                row += 1
            row += 1  # blank line before body/options

            if body:
                for line in body:
                    if row >= h - len(options) - 3:
                        break
                    try:
                        stdscr.addstr(row, 2, line[:w - 4])
                    except curses.error:
                        pass
                    row += 1
                row += 1  # blank line before options

            for i, opt in enumerate(options):
                opt_row = row + i
                if opt_row >= h - 1:
                    break
                marker = ">" if i == idx else " "
                attr = curses.A_REVERSE if i == idx else curses.A_NORMAL
                try:
                    stdscr.addstr(opt_row, 2, f"{marker} {opt}"[:w - 4], attr)
                except curses.error:
                    pass
            try:
                stdscr.addstr(h - 1, 2, "Up/Down: move  Enter: select  Esc/q: cancel"[:w - 4], curses.A_DIM)
            except curses.error:
                pass
            stdscr.refresh()

            key = stdscr.getch()
            if key in (curses.KEY_UP, ord('k')):
                idx = (idx - 1) % len(options)
            elif key in (curses.KEY_DOWN, ord('j')):
                idx = (idx + 1) % len(options)
            elif key in (curses.KEY_ENTER, 10, 13):
                return idx
            elif key in (27, ord('q')):
                return None

    def _text_input(self, stdscr, prompt, password=False):
        curses.curs_set(1)
        stdscr.keypad(True)
        buf = []
        while True:
            stdscr.erase()
            h, w = stdscr.getmaxyx()
            stdscr.addstr(0, 2, prompt[:w - 4], curses.A_BOLD)
            shown = ("*" * len(buf)) if password else "".join(buf)
            try:
                stdscr.addstr(2, 2, shown[:w - 4])
                stdscr.addstr(h - 1, 2, "Enter: confirm  Esc: cancel"[:w - 4], curses.A_DIM)
            except curses.error:
                pass
            stdscr.move(2, min(2 + len(shown), w - 2))
            stdscr.refresh()

            key = stdscr.getch()
            if key in (curses.KEY_ENTER, 10, 13):
                curses.curs_set(0)
                return "".join(buf)
            elif key == 27:
                curses.curs_set(0)
                return None
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                if buf:
                    buf.pop()
            elif 32 <= key <= 126:
                buf.append(chr(key))

    def _message(self, stdscr, text):
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        for i, line in enumerate(text.split("\n")):
            if i + 1 < h:
                try:
                    stdscr.addstr(i + 1, 2, line[:w - 4])
                except curses.error:
                    pass
        try:
            stdscr.addstr(h - 1, 2, "Press any key to continue..."[:w - 4], curses.A_DIM)
        except curses.error:
            pass
        stdscr.refresh()
        stdscr.getch()

    # ---- directory picker ----

    def _directory_picker(self, stdscr, start_path):
        current = start_path if os.path.isdir(start_path) else self.wizard._real_home()
        while True:
            try:
                entries = sorted(
                    (e for e in os.listdir(current) if os.path.isdir(os.path.join(current, e)) and not e.startswith('.')),
                    key=str.lower
                )
            except (PermissionError, FileNotFoundError):
                entries = []

            options = [f"[Select this folder]", ".. (up one level)"] + [f"{e}/" for e in entries]
            idx = self._menu(stdscr, "Select a folder", options, subtitle=current)
            if idx is None:
                return None
            if idx == 0:
                return current
            elif idx == 1:
                parent = os.path.dirname(current.rstrip('/'))
                current = parent if parent else current
            else:
                current = os.path.join(current, entries[idx - 2])

    # ---- create-share flow ----

    def _manage_users(self, stdscr):
        users = []
        while True:
            options = [f"{u['username']}  (select to remove)" for u in users] + ["+ Add User", "Done"]
            idx = self._menu(stdscr, "Users", options, subtitle=f"{len(users)} configured")
            if idx is None or idx == len(options) - 1:
                return users
            if idx == len(options) - 2:
                username = self._text_input(stdscr, "Username:")
                if not username:
                    continue
                password = self._text_input(stdscr, f"Password for {username}:", password=True)
                if not password:
                    continue
                users.append({"username": username, "password": password})
            else:
                del users[idx]

    def _create_share_flow(self, stdscr):
        name = self._text_input(stdscr, "1. Share name:")
        if not name:
            return None

        default_path = self.wizard.default_share_path(name)
        choice = self._menu(stdscr, "2. Share path", [
            f"Use default: {default_path}",
            "Browse for a folder (cursor keys)",
            "Type a path manually",
        ])
        if choice is None:
            return None
        if choice == 0:
            path = default_path
        elif choice == 1:
            picked = self._directory_picker(stdscr, self.wizard._real_home())
            if not picked:
                return None
            path = picked
        else:
            path = self._text_input(stdscr, "3. Path:")
            if not path:
                return None

        users = self._manage_users(stdscr)
        if not users:
            self._message(stdscr, "At least one user is required.\nShare not created.")
            return None

        self.wizard.save_config({
            "name": name,
            "path": path,
            "users": [{"username": u["username"]} for u in users]
        })

        self._message(stdscr, f"Saved '{name}'.\nNow applying to the system (leaving this screen)...")
        return {"name": name, "path": path, "users": users}

    def _manage_shares_flow(self, stdscr):
        while True:
            shares = self.wizard.load_config()
            if not shares:
                self._message(stdscr, "No existing shares found.")
                return
            options = [f"{s['name']}  ({s.get('path', 'Unknown')})" for s in shares] + ["Back"]
            idx = self._menu(stdscr, "Manage Shares", options, subtitle="Select a share to delete")
            if idx is None or idx == len(options) - 1:
                return
            removed = self.wizard.delete_share(idx)
            if removed:
                self._message(stdscr, f"Removed share: {removed['name']}")


def main():
    TUIWizard().run()


if __name__ == "__main__":
    main()
