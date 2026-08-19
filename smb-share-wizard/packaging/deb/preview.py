"""Pre-install preview screen: shows what Kelpie will install before apt
touches the system. Intentionally self-contained (no import from src/) so
this file + install.sh + the .deb are a fully relocatable install bundle -
a user only needs these three files, not the whole source tree."""
import curses
import sys

# Big block-letter "KELPIE" wordmark shown above the horse banner - width
# matched to the logo (65 vs 63 columns) so they read as one unit. Keep in
# sync with src/tui.py's copy (this file is intentionally self-contained,
# see the module docstring).
KELPIE_TITLE = [
    '88      a8P  88888888888 88          88888888ba  88 88888888888  ',
    '88    ,88\'   88          88          88      "8b 88 88           ',
    '88  ,88"     88          88          88      ,8P 88 88           ',
    "88,d88'      88aaaaa     88          88aaaaaa8P' 88 88aaaaa      ",
    '8888"88,     88"""""     88          88""""""\'   88 88"""""      ',
    '88P   Y8b    88          88          88          88 88           ',
    '88     "88,  88          88          88          88 88           ',
    '88       Y8b 88888888888 88888888888 88          88 88888888888  ',
]

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

KELPIE_LOGO_COLORS_8 = [
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

EXPLANATION = [
    "This will install:",
    "",
    "  - kelpie   (this wizard)",
    "  - samba    (the SMB/CIFS file-sharing server)",
    "",
    "Each time you create a share afterward, with your permission",
    "at that point, Kelpie will also create a dedicated Linux user",
    "and a Unix group per share, write to /etc/samba/smb.conf, and",
    "restart the Samba services.",
]


def init_colors():
    color_ok, color_mode, pair_256 = False, "mono", {}
    try:
        curses.start_color()
        try:
            curses.use_default_colors()
            bg = -1
        except curses.error:
            bg = curses.COLOR_BLACK

        if curses.COLORS >= 256:
            used = sorted({v for row in KELPIE_LOGO_COLORS_256 for v in row if v})
            for pair_num, color_idx in enumerate(used, start=1):
                if pair_num >= curses.COLOR_PAIRS:
                    break
                curses.init_pair(pair_num, color_idx, bg)
                pair_256[color_idx] = pair_num
            color_mode = "256"
        else:
            curses.init_pair(1, curses.COLOR_GREEN, bg)
            curses.init_pair(2, curses.COLOR_CYAN, bg)
            color_mode = "8"
        color_ok = True
    except curses.error:
        pass
    return color_ok, color_mode, pair_256


def banner_attr(color_ok, color_mode, pair_256, idx8, idx256):
    if not color_ok:
        return curses.A_BOLD
    if color_mode == "256":
        pair = pair_256.get(idx256)
        return curses.color_pair(pair) if pair is not None else curses.A_BOLD
    pair = curses.color_pair(1 if idx8 in (0, 1) else 2)
    return pair | curses.A_BOLD if idx8 in (1, 3) else pair


def main(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    color_ok, color_mode, pair_256 = init_colors()

    title = "Kelpie needs to install a few things"
    footer = "Up/Down: move  Enter: select  Esc/q: cancel"
    options = ["Continue with install", "Cancel"]
    idx = 0
    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        show_banner = bool(
            h >= len(KELPIE_TITLE) + 1 + len(KELPIE_LOGO) + len(options) + len(EXPLANATION) + 6
            and w >= max(len(l) for l in KELPIE_LOGO) + 4
        )

        # Block-center the whole thing: one shared left margin (col) so the
        # banner/text keep their internal alignment, and the block as a
        # whole sits centered both horizontally and vertically instead of
        # pinned to the top-left corner.
        content_width = max(
            [len(title)]
            + ([max(len(l) for l in KELPIE_TITLE + KELPIE_LOGO)] if show_banner else [])
            + [len(l) for l in EXPLANATION]
            + [len(opt) + 2 for opt in options]
        )
        content_width = min(content_width, w - 4)
        col = max(2, (w - content_width) // 2)

        content_rows = (
            ((len(KELPIE_TITLE) + 1 + len(KELPIE_LOGO) + 1) if show_banner else 0)
            + 2  # title
            + len(EXPLANATION) + 1
            + len(options)
        )
        row = max(0, (h - content_rows - 2) // 2)

        if show_banner:
            for line in KELPIE_TITLE:
                try:
                    stdscr.addstr(row, col, line[:w - col - 2], curses.A_BOLD)
                except curses.error:
                    pass
                row += 1
            row += 1

            for li, line in enumerate(KELPIE_LOGO):
                c8 = KELPIE_LOGO_COLORS_8[li]
                c256 = KELPIE_LOGO_COLORS_256[li]
                for ci, ch in enumerate(line[:w - col - 2]):
                    try:
                        stdscr.addch(row, col + ci, ch, banner_attr(color_ok, color_mode, pair_256, c8[ci], c256[ci]))
                    except curses.error:
                        pass
                row += 1
            row += 1

        try:
            stdscr.addstr(row, col, title[:w - col - 2], curses.A_BOLD)
        except curses.error:
            pass
        row += 2

        for line in EXPLANATION:
            if row >= h - len(options) - 3:
                break
            try:
                stdscr.addstr(row, col, line[:w - col - 2])
            except curses.error:
                pass
            row += 1
        row += 1

        for i, opt in enumerate(options):
            opt_row = row + i
            if opt_row >= h - 1:
                break
            marker = ">" if i == idx else " "
            attr = curses.A_REVERSE if i == idx else curses.A_NORMAL
            try:
                stdscr.addstr(opt_row, col, f"{marker} {opt}"[:w - col - 2], attr)
            except curses.error:
                pass
        try:
            footer_col = max(0, (w - len(footer)) // 2)
            stdscr.addstr(h - 1, footer_col, footer[:w - footer_col - 1], curses.A_DIM)
        except curses.error:
            pass
        stdscr.refresh()

        key = stdscr.getch()
        if key in (curses.KEY_UP, ord('k')):
            idx = (idx - 1) % len(options)
        elif key in (curses.KEY_DOWN, ord('j')):
            idx = (idx + 1) % len(options)
        elif key in (curses.KEY_ENTER, 10, 13):
            return idx == 0
        elif key in (27, ord('q')):
            return False


if __name__ == "__main__":
    try:
        proceed = curses.wrapper(main)
    except curses.error as e:
        print(f"Terminal UI unavailable ({e}); this preview needs a real terminal.", file=sys.stderr)
        sys.exit(2)
    sys.exit(0 if proceed else 1)
