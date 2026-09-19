import json
import os
import threading

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".discord_bot_hoster")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
RUNTIME_DIR = os.path.join(CONFIG_DIR, "runtime")

DEFAULTS = {
    "active_profile": "Default",
    "interpreter": "python",
    "max_restarts": 5,
    "restart_delay": 3,
    "autoscroll": True,
    "save_token": True,
    "autostart": False,
    "theme": "Dark",
    "accent": "Blue",
    "widget_scaling": 1.0,
    "editor_font_size": 12,
    "custom_libraries": [],
    "profiles": {},
}

_lock = threading.RLock()


def _ensure_dirs():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(RUNTIME_DIR, exist_ok=True)


def load():
    _ensure_dirs()
    with _lock:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cfg = dict(DEFAULTS)
                cfg.update({k: v for k, v in data.items() if k in DEFAULTS})
                if not isinstance(cfg["profiles"], dict):
                    cfg["profiles"] = {}
                if not isinstance(cfg["custom_libraries"], list):
                    cfg["custom_libraries"] = []
                try:
                    cfg["widget_scaling"] = float(cfg["widget_scaling"])
                except (TypeError, ValueError):
                    cfg["widget_scaling"] = 1.0
                try:
                    cfg["editor_font_size"] = int(cfg["editor_font_size"])
                except (TypeError, ValueError):
                    cfg["editor_font_size"] = 12
                if cfg["active_profile"] not in cfg["profiles"]:
                    cfg["active_profile"] = "Default"
                cfg["profiles"].setdefault("Default", {"code": "", "token": ""})
                return cfg
            except Exception:
                pass
        cfg = dict(DEFAULTS)
        cfg["profiles"]["Default"] = {"code": "", "token": ""}
        save(cfg)
        return cfg


def save(cfg):
    _ensure_dirs()
    with _lock:
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_FILE)


def runtime_file(profile_name):
    _ensure_dirs()
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in profile_name) or "bot"
    return os.path.join(RUNTIME_DIR, safe + ".py")


def requirements_path():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    return os.path.join(root, "requirements.txt")