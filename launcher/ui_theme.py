"""Dependency-free terminal theming: ANSI banners and status lines.

No third-party packages. Colors auto-disable when stdout is not a TTY or when
NO_COLOR is set. Unicode glyphs fall back to ASCII when the console encoding
is not UTF-8. Pick a palette with the UITHEME_THEME env var
(cyber | matrix | sunset | ice | mono).
"""
from __future__ import annotations

import os
import sys

_USE_COLOR = bool(getattr(sys.stdout, "isatty", lambda: False)()) and os.environ.get("NO_COLOR") is None

RESET = "\033[0m" if _USE_COLOR else ""
BOLD = "\033[1m" if _USE_COLOR else ""
DIM = "\033[90m"

_PALETTES = {
    "cyber": ["\033[38;5;201m", "\033[38;5;165m", "\033[38;5;99m", "\033[38;5;45m"],
    "matrix": ["\033[38;5;46m", "\033[38;5;40m", "\033[38;5;34m", "\033[38;5;28m"],
    "sunset": ["\033[38;5;214m", "\033[38;5;208m", "\033[38;5;203m", "\033[38;5;198m"],
    "ice": ["\033[38;5;51m", "\033[38;5;45m", "\033[38;5;39m", "\033[38;5;33m"],
    "mono": ["\033[97m", "\033[37m", "\033[90m", "\033[37m"],
}

_ICONS = {
    "pass": ("\u2714", "[OK]"),
    "warn": ("\u26a0", "[!]"),
    "fail": ("\u2718", "[X]"),
    "info": ("\u2139", "[i]"),
}
_ICON_COLOR = {
    "pass": "\033[92m",
    "warn": "\033[93m",
    "fail": "\033[91m",
    "info": "\033[96m",
}


def _palette():
    name = os.environ.get("UITHEME_THEME", "cyber").lower()
    return _PALETTES.get(name, _PALETTES["cyber"])


def _c(code):
    return code if _USE_COLOR else ""


def colorize(text, code):
    return _c(code) + str(text) + RESET


def gradient(text):
    if not _USE_COLOR:
        return text
    pal = _palette()
    n = max(len(text) - 1, 1)
    out = []
    for i, ch in enumerate(text):
        idx = int(i / n * (len(pal) - 1))
        out.append(pal[idx] + ch)
    return "".join(out) + RESET


def _supports_unicode():
    enc = (getattr(sys.stdout, "encoding", "") or "").lower()
    return "utf" in enc


def print_check(status, label, detail=""):
    glyph_u, glyph_a = _ICONS.get(status, _ICONS["info"])
    glyph = glyph_u if _supports_unicode() else glyph_a
    color = _ICON_COLOR.get(status, _ICON_COLOR["info"])
    line = _c(color) + glyph + RESET + " " + BOLD + str(label) + RESET
    if detail:
        line += "  " + colorize(detail, DIM)
    print(line)


def print_banner(title, subtitle=""):
    bar = "=" * (len(title) + 8)
    print(gradient(bar))
    print(gradient("==  " + title + "  =="))
    print(gradient(bar))
    if subtitle:
        print(colorize(subtitle, DIM))
    print()


if __name__ == "__main__":
    print_banner("UI Theme Demo", "dependency-free ANSI banners + status lines")
    print_check("pass", "Login", "session reused")
    print_check("info", "Listing", "page 3, 120 so far")
    print_check("warn", "Rate limited", "resuming in 300s")
    print_check("fail", "Item failed", "pk 123")
