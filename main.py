import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk

from app import config, theme

cfg = config.load()

saved_theme = cfg.get("theme", theme.DEFAULT_PALETTE)
if saved_theme not in theme.PALETTES:
    saved_theme = theme.LEGACY_THEMES.get(saved_theme, theme.DEFAULT_PALETTE)

theme.set_palette(saved_theme)

saved_accent = cfg.get("accent", theme.DEFAULT_ACCENT)
if saved_accent not in theme.ACCENTS:
    saved_accent = theme.LEGACY_ACCENTS.get(saved_accent, theme.DEFAULT_ACCENT)
theme.set_accent(saved_accent)

try:
    ctk.set_widget_scaling(float(cfg.get("widget_scaling", 1.0)))
except (TypeError, ValueError):
    ctk.set_widget_scaling(1.0)

ctk.set_default_color_theme("dark-blue")

from app.ui import HosterApp


def main():
    app = HosterApp()
    app.mainloop()


if __name__ == "__main__":
    main()