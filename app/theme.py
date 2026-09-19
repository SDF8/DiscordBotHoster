import sys

import customtkinter as ctk

DEFAULT_ACCENT = "Blue"
DEFAULT_PALETTE = "Dark"

LEGACY_THEMES = {"dark": "Dark", "light": "Light"}
LEGACY_ACCENTS = {"blue": "Blue", "dark-blue": "Dark Blue", "green": "Green"}

PALETTES = {
    "Dark": {
        "mode": "dark",
        "bg": "#0d1117",
        "panel": "#161b22",
        "card": "#1e222a",
        "input": "#0d1117",
        "border": "#30363d",
        "text": "#e6edf3",
        "muted": "#9ea7b3",
        "soft": "#21262d",
        "log_out": "#e6edf3",
        "log_err": "#ff7b72",
        "log_warn": "#d29922",
        "log_sys": "#58a6ff",
        "log_pip": "#7ee787",
    },
    "Light": {
        "mode": "light",
        "bg": "#f6f8fa",
        "panel": "#ffffff",
        "card": "#ffffff",
        "input": "#f9fafb",
        "border": "#d0d7de",
        "text": "#1f2328",
        "muted": "#57606a",
        "soft": "#eaeef2",
        "log_out": "#1f2328",
        "log_err": "#cf222e",
        "log_warn": "#9a6700",
        "log_sys": "#0969da",
        "log_pip": "#1a7f37",
    },
    "Midnight": {
        "mode": "dark",
        "bg": "#0a0e1a",
        "panel": "#12182b",
        "card": "#1a2240",
        "input": "#0a0e1a",
        "border": "#2a3556",
        "text": "#dfe6ff",
        "muted": "#8b93b5",
        "soft": "#1e2845",
        "log_out": "#dfe6ff",
        "log_err": "#ff6b6b",
        "log_warn": "#ffc966",
        "log_sys": "#6da4ff",
        "log_pip": "#7ee787",
    },
    "Graphite": {
        "mode": "dark",
        "bg": "#101216",
        "panel": "#17191e",
        "card": "#1e2128",
        "input": "#101216",
        "border": "#2c3038",
        "text": "#d9dce1",
        "muted": "#8b8f96",
        "soft": "#22262e",
        "log_out": "#d9dce1",
        "log_err": "#ff7b72",
        "log_warn": "#d29922",
        "log_sys": "#79c0ff",
        "log_pip": "#7ee787",
    },
    "Forest": {
        "mode": "dark",
        "bg": "#0d1310",
        "panel": "#131b17",
        "card": "#1a251f",
        "input": "#0d1310",
        "border": "#2a3a31",
        "text": "#dbe8df",
        "muted": "#86a091",
        "soft": "#1f2c24",
        "log_out": "#dbe8df",
        "log_err": "#ff8f7a",
        "log_warn": "#e3b341",
        "log_sys": "#6fc3c9",
        "log_pip": "#9ce8a0",
    },
    "Sunrise": {
        "mode": "light",
        "bg": "#fdf6ec",
        "panel": "#ffffff",
        "card": "#fff9ef",
        "input": "#fffdfa",
        "border": "#e8dcc8",
        "text": "#44341f",
        "muted": "#8a7a5c",
        "soft": "#f3ead9",
        "log_out": "#44341f",
        "log_err": "#d13438",
        "log_warn": "#9a6700",
        "log_sys": "#1f6feb",
        "log_pip": "#1a7f37",
    },
}

ACCENTS = {
    "Blue": "#1f6feb",
    "Dark Blue": "#1d4ed8",
    "Green": "#2ea044",
    "Purple": "#7c3aed",
    "Violet": "#8957e5",
    "Red": "#d1242f",
    "Orange": "#c97600",
    "Pink": "#db61a2",
    "Teal": "#0ea5a4",
    "Gold": "#b8860b",
    "Slate": "#5b6b83",
}

_current = dict(PALETTES[DEFAULT_PALETTE])
_name = DEFAULT_PALETTE
_current_accent = DEFAULT_ACCENT


def P(key):
    return _current.get(key, _current["bg"])


def accent(name=None):
    if name is not None:
        return ACCENTS.get(name, ACCENTS[DEFAULT_ACCENT])
    return ACCENTS.get(_current_accent, ACCENTS[DEFAULT_ACCENT])


def set_accent(name):
    global _current_accent
    if name in ACCENTS:
        _current_accent = name


def palette_names():
    return list(PALETTES.keys())


def accent_names():
    return list(ACCENTS.keys())


def palette_of(name):
    return name in PALETTES


def set_palette(name):
    global _current, _name
    if name not in PALETTES:
        name = DEFAULT_PALETTE
    _current.clear()
    _current.update(PALETTES[name])
    _name = name
    ctk.set_appearance_mode(_current["mode"])


def _rgb(hex_color):
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _hex(rgb):
    return "#%02x%02x%02x" % rgb


def mix(base, other, amount):
    a = _rgb(base)
    b = _rgb(other)
    return _hex(tuple(int(x + (y - x) * amount) for x, y in zip(a, b)))


def lighten(hex_color, amount):
    return mix(hex_color, "#ffffff", amount)


def darken(hex_color, amount):
    return mix(hex_color, "#000000", amount)


def hover_of(hex_color):
    return lighten(hex_color, 0.14)


def log_colors():
    return {
        "out": P("log_out"),
        "err": P("log_err"),
        "warn": P("log_warn"),
        "system": P("log_sys"),
        "pip": P("log_pip"),
    }


def is_stdlib(name):
    lowered = name.lower()
    return lowered in getattr(sys, "stdlib_module_names", set())