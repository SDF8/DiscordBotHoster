import os
import queue
import re
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from app import config, theme
from app.bot_manager import BotManager, ERR, OUT, PIP, SYSTEM, WARN
from app.templates import TEMPLATES, invite_url, pretty_permissions

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
SPEC_RE = re.compile(r"^([A-Za-z0-9_.-]+)")

STATUS_STYLES = {
    "Stopped": ("#9ea7b3", "● Stopped"),
    "Offline": ("#9ea7b3", "● Offline"),
    "Starting": ("#d29922", "● Starting"),
    "Running": ("#2ea043", "● Running"),
    "Restarting...": ("#d29922", "● Restarting"),
    "Crashed": ("#f85149", "● Crashed"),
}

LEGACY_THEMES = theme.LEGACY_THEMES
LEGACY_ACCENTS = theme.LEGACY_ACCENTS


def format_uptime(seconds):
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def spec_package_name(spec):
    match = SPEC_RE.match(spec.strip())
    return match.group(1).lower() if match else ""


class LogPanel(ctk.CTkFrame):
    def __init__(self, master, title, var=None, locked=False, show_autoscroll=True):
        super().__init__(master, fg_color=theme.P("panel"), corner_radius=12)
        self.locked = locked
        self.autoscroll = var if var is not None else tk.BooleanVar(value=True)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(header, text=title, font=ctk.CTkFont("Segoe UI", 14, "bold")).pack(side="left")
        if show_autoscroll and not locked:
            ctk.CTkCheckBox(
                header, text="Auto-scroll", variable=self.autoscroll, checkbox_width=18, checkbox_height=18,
                font=ctk.CTkFont("Segoe UI", 12),
            ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            header, text="Clear", width=64, height=28,
            fg_color=theme.P("soft"), hover_color=theme.P("border"), text_color=theme.P("text"),
            font=ctk.CTkFont("Segoe UI", 12), command=self.clear,
        ).pack(side="right")

        self.body = ctk.CTkFrame(self, fg_color=theme.P("input"), corner_radius=8)
        self.body.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        self.text = tk.Text(
            self.body, bg=theme.P("input"), fg=theme.P("log_out"), insertbackground=theme.P("text"),
            relief="flat", wrap="word", padx=10, pady=10, font=("Consolas", 12),
            state="disabled", highlightthickness=1, highlightbackground=theme.P("border"),
        )
        scrollbar = ctk.CTkScrollbar(self.body, command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        self.text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y", padx=(0, 6), pady=6)

        self.restyle()

    def set_font(self, font):
        self.text.configure(font=font)

    def restyle(self):
        self.configure(fg_color=theme.P("panel"))
        self.body.configure(fg_color=theme.P("input"))
        self.text.configure(
            bg=theme.P("input"), fg=theme.P("log_out"), insertbackground=theme.P("text"),
            highlightbackground=theme.P("border"),
        )
        for tag, color in theme.log_colors().items():
            self.text.tag_config(tag, foreground=color)

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def append(self, text, stream=OUT):
        self.text.configure(state="normal")
        line = ANSI_RE.sub("", text)
        self.text.insert("end", line + "\n", stream)
        if self.locked or self.autoscroll.get():
            self.text.see("end")
        self.text.configure(state="disabled")


class InviteDialog(ctk.CTkToplevel):
    def __init__(self, master, token):
        super().__init__(master)
        self._vars = []
        self.title("Invite Link Generator")
        self.geometry("400x520")
        self.resizable(False, False)
        self.transient(master)
        self.attributes("-topmost", True)
        self.grab_set()

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(16, 4))
        ctk.CTkLabel(header, text="Permissions", font=ctk.CTkFont("Segoe UI", 16, "bold")).pack(side="left")
        if not token:
            ctk.CTkLabel(header, text_color=theme.P("log_err"), text="No token set", font=ctk.CTkFont("Segoe UI", 12)).pack(side="right")

        frame = ctk.CTkScrollableFrame(self, fg_color="transparent", height=330)
        frame.pack(fill="x", padx=18, pady=8)
        for name, bit in pretty_permissions():
            var = tk.BooleanVar(value=(bit & (1 << 17)) != 0)
            self._vars.append((name, bit, var))
            ctk.CTkCheckBox(
                frame, text=name, variable=var, width=200, checkbox_width=18, checkbox_height=18,
                font=ctk.CTkFont("Segoe UI", 13),
            ).pack(anchor="w", pady=4)

        self.result = ctk.CTkEntry(self, font=ctk.CTkFont("Segoe UI", 12), height=32, fg_color=theme.P("input"), border_color=theme.accent())
        self.result.pack(fill="x", padx=18, pady=6)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=18, pady=(0, 16))
        ctk.CTkButton(buttons, text="Generate", command=lambda: self._generate(token), width=110).pack(side="left")
        ctk.CTkButton(buttons, text="Copy", command=self._copy, width=90, fg_color=theme.P("soft"), hover_color=theme.P("border")).pack(side="left", padx=8)
        ctk.CTkButton(buttons, text="Close", command=self.destroy, width=90, fg_color=theme.P("soft"), hover_color=theme.P("border")).pack(side="right")

        self._generate(token)

    def _generate(self, token):
        selected = [bit for _, bit, var in self._vars if var.get()]
        url = invite_url(token, selected)
        self.result.delete(0, "end")
        self.result.insert(0, url or "(set a token first)")

    def _copy(self):
        url = self.result.get()
        if url:
            self.clipboard_clear()
            self.clipboard_append(url)
            self.result.delete(0, "end")
            self.result.insert(0, "Copied to clipboard!")
            self.after(1200, lambda: self.result.insert(0, url))


class HosterApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Discord Bot Hoster")
        self.geometry("1280x820")
        self.minsize(1140, 700)
        self.configure(fg_color=theme.P("bg"))

        self.cfg = config.load()
        self.manager = BotManager()
        self.profile = self.cfg.get("active_profile", "Default")
        self.current_font_size = self.cfg.get("editor_font_size", 12)
        self._accent_buttons = []
        self._accent_entries = []
        self._listboxes = []
        self._log_panels = []

        self.autoscroll_var = tk.BooleanVar(value=self.cfg.get("autoscroll", True))
        self._build_palette = dict(theme._current)
        saved_accent = self.cfg.get("accent", theme.DEFAULT_ACCENT)
        saved_accent = LEGACY_ACCENTS.get(saved_accent, saved_accent)
        if saved_accent in theme.ACCENTS:
            theme.set_accent(saved_accent)
        self._build_header()
        self._build_tabs()
        self._build_footer()
        self._load_profile(initial=True)
        self._apply_fonts()
        self.apply_accent()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll)
        self._tick()

        if self.cfg.get("autostart") and self.editor_code().strip():
            self.start_bot()

    def _project_dir(self):
        return os.path.dirname(config.requirements_path())

    def _interp(self):
        value = self.cfg.get("interpreter", "python")
        return str(value).strip() or "python"

    def editor_code(self):
        return self.code.get("1.0", "end-1c")

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=theme.P("panel"), corner_radius=0, height=66)
        header.pack(fill="x")
        header.pack_propagate(False)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", padx=18, pady=10)
        ctk.CTkLabel(left, text="Discord Bot Hoster", font=ctk.CTkFont("Segoe UI", 22, "bold")).pack(anchor="w")
        ctk.CTkLabel(left, text="Write, run and monitor your Discord bots", text_color=theme.P("muted"), font=ctk.CTkFont("Segoe UI", 12)).pack(anchor="w")

        self.status_pill = ctk.CTkLabel(
            header, text="● Offline", corner_radius=14, padx=16, fg_color=theme.P("soft"),
            text_color=theme.P("muted"), font=ctk.CTkFont("Segoe UI", 13, "bold"),
        )
        self.status_pill.pack(side="right", padx=20)

    def _build_tabs(self):
        self.tabs = ctk.CTkTabview(
            self, command=self._on_tab_changed, fg_color="transparent",
            segmented_button_fg_color=theme.P("panel"),
            segmented_button_selected_color=theme.accent(),
            segmented_button_selected_hover_color=theme.hover_of(theme.accent()),
            segmented_button_unselected_color=theme.P("soft"),
            segmented_button_unselected_hover_color=theme.P("border"),
            text_color=theme.P("muted"), text_color_disabled=theme.P("muted"), corner_radius=10,
        )
        self.tabs.pack(fill="both", expand=True, padx=12, pady=(10, 4))
        self._build_bot_tab(self.tabs.add("Bot"))
        self._build_settings_tab(self.tabs.add("Settings"))
        self._build_libraries_tab(self.tabs.add("Libraries"))

    def _build_bot_tab(self, master):
        master.grid_columnconfigure(0, weight=3, uniform="cols")
        master.grid_columnconfigure(1, weight=2, uniform="cols")
        master.grid_rowconfigure(0, weight=1)
        self._build_editor_panel(master)
        self._build_log_panel(master)

    def _accent_button(self, master, **kwargs):
        button = ctk.CTkButton(
            master, fg_color=theme.accent(), hover_color=theme.hover_of(theme.accent()), **kwargs
        )
        self._accent_buttons.append(button)
        return button

    def _build_editor_panel(self, master):
        panel = ctk.CTkFrame(master, fg_color=theme.P("panel"), corner_radius=12)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        bar = ctk.CTkFrame(panel, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        ctk.CTkLabel(bar, text="BOT SCRIPT", font=ctk.CTkFont("Segoe UI", 14, "bold")).pack(side="left")
        ctk.CTkLabel(bar, text="token via DISCORD_BOT_TOKEN env", text_color=theme.P("muted"), font=ctk.CTkFont("Segoe UI", 11)).pack(side="right")

        self.code = ctk.CTkTextbox(
            panel, font=("Consolas", self.current_font_size), wrap="word",
            fg_color=theme.P("input"), text_color=theme.P("text"),
            border_color=theme.accent(), border_width=1, corner_radius=8, padx=12, pady=10,
        )
        self.code.grid(row=1, column=0, sticky="nsew", padx=14)

        token_row = ctk.CTkFrame(panel, fg_color="transparent")
        token_row.grid(row=2, column=0, sticky="ew", padx=14, pady=(10, 2))
        ctk.CTkLabel(token_row, text="Bot Token", width=80, anchor="w", font=ctk.CTkFont("Segoe UI", 12)).pack(side="left")
        self.token_var = tk.StringVar()
        token_entry = ctk.CTkEntry(token_row, textvariable=self.token_var, show="•", height=32, font=ctk.CTkFont("Segoe UI", 12), fg_color=theme.P("input"), border_color=theme.accent())
        token_entry.pack(side="left", fill="x", expand=True, padx=8)
        self._accent_entries.append(token_entry)

        run_row = ctk.CTkFrame(panel, fg_color="transparent")
        run_row.grid(row=3, column=0, sticky="ew", padx=14, pady=8)
        self.btn_start = self._accent_button(run_row, text="▶  Start", command=self.start_bot, font=ctk.CTkFont("Segoe UI", 14, "bold"), height=38)
        self.btn_start.pack(side="left", expand=True, fill="x")
        self.btn_restart = ctk.CTkButton(run_row, text="↻  Restart", command=self.restart_bot, fg_color="#9e6a03", hover_color="#d29922", font=ctk.CTkFont("Segoe UI", 14, "bold"), height=38, state="disabled")
        self.btn_restart.pack(side="left", expand=True, fill="x", padx=6)
        self.btn_stop = ctk.CTkButton(run_row, text="■  Stop", command=self.stop_bot, fg_color="#b62324", hover_color="#f85149", font=ctk.CTkFont("Segoe UI", 14, "bold"), height=38, state="disabled")
        self.btn_stop.pack(side="left", expand=True, fill="x")

        profiles = ctk.CTkFrame(panel, fg_color="transparent")
        profiles.grid(row=4, column=0, sticky="ew", padx=14, pady=(2, 4))
        ctk.CTkLabel(profiles, text="Profile", width=60, anchor="w", font=ctk.CTkFont("Segoe UI", 12)).pack(side="left")
        self.profile_menu = ctk.CTkOptionMenu(profiles, values=list(self.cfg["profiles"].keys()), command=self._on_profile_selected, font=ctk.CTkFont("Segoe UI", 12), width=150, fg_color=theme.P("input"), button_color=theme.accent(), button_hover_color=theme.hover_of(theme.accent()), text_color=theme.P("text"))
        self.profile_menu.pack(side="left", padx=8)
        ctk.CTkButton(profiles, text="＋  New", width=64, height=30, fg_color=theme.P("soft"), hover_color=theme.P("border"), font=ctk.CTkFont("Segoe UI", 12), command=self.new_profile).pack(side="left", padx=2)
        self._accent_button(profiles, text="Save", width=64, height=30, font=ctk.CTkFont("Segoe UI", 12), command=self.save_profile).pack(side="left", padx=2)
        ctk.CTkButton(profiles, text="Delete", width=64, height=30, fg_color=theme.P("soft"), hover_color="#f85149", font=ctk.CTkFont("Segoe UI", 12), command=self.delete_profile).pack(side="left", padx=2)

        tools = ctk.CTkFrame(panel, fg_color="transparent")
        tools.grid(row=5, column=0, sticky="ew", padx=14, pady=(4, 10))
        self._accent_button(tools, text="Invite Link", height=30, command=self.show_invite).pack(side="left")
        self.template_var = tk.StringVar(value=list(TEMPLATES.keys())[0])
        ctk.CTkOptionMenu(tools, variable=self.template_var, values=list(TEMPLATES.keys()), width=170, height=30, font=ctk.CTkFont("Segoe UI", 12), fg_color=theme.P("input"), button_color=theme.accent(), button_hover_color=theme.hover_of(theme.accent()), text_color=theme.P("text")).pack(side="left", padx=6)
        ctk.CTkButton(tools, text="Insert Template", height=30, fg_color=theme.P("soft"), hover_color=theme.P("border"), font=ctk.CTkFont("Segoe UI", 12), command=self.insert_template).pack(side="left", padx=(4, 0))

    def _build_log_panel(self, master):
        wrap = ctk.CTkFrame(master, fg_color="transparent")
        wrap.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_rowconfigure(1, weight=0)

        self.log_panel = LogPanel(wrap, "LIVE OUTPUT", var=self.autoscroll_var)
        self.log_panel.grid(row=0, column=0, sticky="nsew")
        self._log_panels.append(self.log_panel)

        stats = ctk.CTkFrame(wrap, fg_color=theme.P("panel"), corner_radius=12)
        stats.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.uptime_label = ctk.CTkLabel(stats, text="Uptime 00:00:00", font=ctk.CTkFont("Segoe UI", 12), text_color=theme.P("muted"))
        self.uptime_label.pack(side="left", padx=14, pady=10)
        self.restart_label = ctk.CTkLabel(stats, text="Restarts 0", font=ctk.CTkFont("Segoe UI", 12), text_color=theme.P("muted"))
        self.restart_label.pack(side="left", padx=14, pady=10)

        self.autostart_var = tk.BooleanVar(value=self.cfg.get("autostart", False))
        ctk.CTkCheckBox(stats, text="Auto-start on launch", variable=self.autostart_var, checkbox_width=18, checkbox_height=18, border_color=theme.P("border"), font=ctk.CTkFont("Segoe UI", 12)).pack(side="right", padx=14)

    def _build_settings_tab(self, master):
        master.grid_columnconfigure(0, weight=3, uniform="s")
        master.grid_columnconfigure(1, weight=2, uniform="s")
        master.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(master, fg_color=theme.P("panel"), corner_radius=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="APPEARANCE", font=ctk.CTkFont("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(14, 2))

        theme_names = theme.palette_names()
        saved_theme = self.cfg.get("theme", theme.DEFAULT_PALETTE)
        saved_theme = LEGACY_THEMES.get(saved_theme, saved_theme)
        if saved_theme not in theme_names:
            saved_theme = theme.DEFAULT_PALETTE

        def row(master, label, widget):
            frame = ctk.CTkFrame(master, fg_color="transparent")
            frame.pack(fill="x", padx=16, pady=6)
            ctk.CTkLabel(frame, text=label, width=130, anchor="w", font=ctk.CTkFont("Segoe UI", 12)).pack(side="left")
            widget(frame)
            return frame

        self.theme_var = tk.StringVar(value=saved_theme)
        self.theme_var.trace_add("write", self._on_theme_change)
        row(left, "Theme", lambda f: ctk.CTkOptionMenu(
            f, variable=self.theme_var, values=theme_names, width=160, font=ctk.CTkFont("Segoe UI", 12),
            fg_color=theme.P("input"), button_color=theme.accent(), button_hover_color=theme.hover_of(theme.accent()), text_color=theme.P("text"),
        ).pack(side="left"))

        saved_accent = self.cfg.get("accent", theme.DEFAULT_ACCENT)
        saved_accent = LEGACY_ACCENTS.get(saved_accent, saved_accent)
        if saved_accent not in theme.accent_names():
            saved_accent = theme.DEFAULT_ACCENT
        self.accent_var = tk.StringVar(value=saved_accent)
        self.accent_var.trace_add("write", self._on_accent_change)
        row(left, "Accent color", lambda f: ctk.CTkOptionMenu(
            f, variable=self.accent_var, values=theme.accent_names(), width=160, font=ctk.CTkFont("Segoe UI", 12),
            fg_color=theme.P("input"), button_color=theme.accent(), button_hover_color=theme.hover_of(theme.accent()), text_color=theme.P("text"),
        ).pack(side="left"))

        self.scale_var = tk.IntVar(value=int(self.cfg.get("widget_scaling", 1.0) * 100))

        def scale_widget(f):
            ctk.CTkSlider(f, from_=80, to=130, number_of_steps=50, variable=self.scale_var, command=self._on_scale_change, width=140, fg_color=theme.P("input"), progress_color=theme.accent(), button_color=theme.accent(), button_hover_color=theme.hover_of(theme.accent())).pack(side="left", fill="x", expand=True, padx=8)
            self.scale_label = ctk.CTkLabel(f, text=f"{self.scale_var.get()}%", width=46, font=ctk.CTkFont("Segoe UI", 12))
            self.scale_label.pack(side="left")

        row(left, "Widget size", scale_widget)

        def font_widget(f):
            ctk.CTkSlider(f, from_=10, to=18, number_of_steps=16, variable=tk.IntVar(value=self.current_font_size), command=self._on_font_change, width=140, fg_color=theme.P("input"), progress_color=theme.accent(), button_color=theme.accent(), button_hover_color=theme.hover_of(theme.accent())).pack(side="left", fill="x", expand=True, padx=8)
            self.font_label = ctk.CTkLabel(f, text=str(self.current_font_size), width=46, font=ctk.CTkFont("Segoe UI", 12))
            self.font_label.pack(side="left")

        row(left, "Editor font size", font_widget)

        ctk.CTkLabel(left, text="Theme and accent apply live.", text_color=theme.P("muted"), font=ctk.CTkFont("Segoe UI", 11)).pack(anchor="w", padx=16, pady=(10, 14))

        right = ctk.CTkFrame(master, fg_color=theme.P("panel"), corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="RUNTIME", font=ctk.CTkFont("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(14, 2))

        interp_row = ctk.CTkFrame(right, fg_color="transparent")
        interp_row.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(interp_row, text="Python", width=110, anchor="w", font=ctk.CTkFont("Segoe UI", 12)).pack(side="left")
        self.interp_var = tk.StringVar(value=self._interp())
        interp_entry = ctk.CTkEntry(interp_row, textvariable=self.interp_var, width=180, height=30, font=ctk.CTkFont("Segoe UI", 12), fg_color=theme.P("input"), border_color=theme.accent())
        interp_entry.pack(side="left")
        self._accent_entries.append(interp_entry)
        ctk.CTkButton(interp_row, text="Detect", width=64, height=30, fg_color=theme.P("soft"), hover_color=theme.P("border"), font=ctk.CTkFont("Segoe UI", 12), command=self._detect_interpreter).pack(side="left", padx=6)

        restarts_row = ctk.CTkFrame(right, fg_color="transparent")
        restarts_row.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(restarts_row, text="Max restarts", width=110, anchor="w", font=ctk.CTkFont("Segoe UI", 12)).pack(side="left")
        self.restarts_var = tk.StringVar(value=str(self.cfg.get("max_restarts", 5)))
        restarts_entry = ctk.CTkEntry(restarts_row, textvariable=self.restarts_var, width=80, height=30, font=ctk.CTkFont("Segoe UI", 12), fg_color=theme.P("input"), border_color=theme.accent())
        restarts_entry.pack(side="left")
        self._accent_entries.append(restarts_entry)

        delay_row = ctk.CTkFrame(right, fg_color="transparent")
        delay_row.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(delay_row, text="Restart delay (s)", width=110, anchor="w", font=ctk.CTkFont("Segoe UI", 12)).pack(side="left")
        self.delay_var = tk.StringVar(value=str(self.cfg.get("restart_delay", 3)))
        delay_entry = ctk.CTkEntry(delay_row, textvariable=self.delay_var, width=80, height=30, font=ctk.CTkFont("Segoe UI", 12), fg_color=theme.P("input"), border_color=theme.accent())
        delay_entry.pack(side="left")
        self._accent_entries.append(delay_entry)

        ctk.CTkLabel(right, text="BEHAVIOR", font=ctk.CTkFont("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(14, 2))
        self.save_token_var = tk.BooleanVar(value=self.cfg.get("save_token", True))
        ctk.CTkCheckBox(right, text="Save bot token with profiles", variable=self.save_token_var, checkbox_width=18, checkbox_height=18, border_color=theme.P("border"), font=ctk.CTkFont("Segoe UI", 12)).pack(anchor="w", padx=22, pady=4)

        action_row = ctk.CTkFrame(master, fg_color="transparent")
        action_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self._accent_button(action_row, text="Save Settings", width=130, height=34, font=ctk.CTkFont("Segoe UI", 13, "bold"), command=self.save_settings).pack(side="left")
        ctk.CTkButton(action_row, text="Restore Defaults", width=130, height=34, fg_color=theme.P("soft"), hover_color=theme.P("border"), font=ctk.CTkFont("Segoe UI", 13), command=self.restore_defaults).pack(side="left", padx=8)
        self.settings_hint = ctk.CTkLabel(action_row, text="", text_color=theme.P("log_pip"), font=ctk.CTkFont("Segoe UI", 12))
        self.settings_hint.pack(side="left", padx=10)

    def _build_libraries_tab(self, master):
        master.grid_columnconfigure(0, weight=1)
        master.grid_columnconfigure(1, weight=1)
        master.grid_rowconfigure(1, weight=1)
        master.grid_rowconfigure(2, weight=1)

        install_row = ctk.CTkFrame(master, fg_color=theme.P("panel"), corner_radius=12)
        install_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ctk.CTkLabel(install_row, text="Library", width=56, anchor="w", font=ctk.CTkFont("Segoe UI", 12)).pack(side="left", padx=14)
        self.lib_spec_var = tk.StringVar()
        lib_entry = ctk.CTkEntry(install_row, textvariable=self.lib_spec_var, height=34, placeholder_text="name or name==version   e.g. aiohttp==3.9.0", font=ctk.CTkFont("Segoe UI", 12), fg_color=theme.P("input"), border_color=theme.accent())
        lib_entry.pack(side="left", fill="x", expand=True, padx=6)
        self._accent_entries.append(lib_entry)
        self._accent_button(install_row, text="Install", width=90, height=34, font=ctk.CTkFont("Segoe UI", 12, "bold"), command=self.install_lib_now).pack(side="left", padx=4)
        self._accent_button(install_row, text="Save to list", width=100, height=34, font=ctk.CTkFont("Segoe UI", 12), command=self.save_lib_to_list).pack(side="left", padx=4)
        ctk.CTkButton(install_row, text="Install requirements.txt", width=160, height=34, fg_color=theme.P("soft"), hover_color=theme.P("border"), font=ctk.CTkFont("Segoe UI", 12), command=self.install_requirements).pack(side="left", padx=(4, 14))

        saved_frame = ctk.CTkFrame(master, fg_color=theme.P("panel"), corner_radius=12)
        saved_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=(0, 8))
        saved_frame.grid_columnconfigure(0, weight=1)
        saved_frame.grid_rowconfigure(1, weight=1)

        saved_head = ctk.CTkFrame(saved_frame, fg_color="transparent")
        saved_head.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
        ctk.CTkLabel(saved_head, text="MY LIBRARIES", font=ctk.CTkFont("Segoe UI", 14, "bold")).pack(side="left")
        ctk.CTkLabel(saved_head, text="persists", text_color=theme.P("muted"), font=ctk.CTkFont("Segoe UI", 11)).pack(side="left", padx=6)
        self._accent_button(saved_head, text="Install All", width=84, height=28, command=self.install_all_saved).pack(side="right")
        ctk.CTkButton(saved_head, text="Remove", width=70, height=28, fg_color=theme.P("soft"), hover_color="#f85149", font=ctk.CTkFont("Segoe UI", 12), command=self.remove_saved_lib).pack(side="right", padx=6)

        self.saved_list = self._listbox(saved_frame, row=1)
        self._refresh_saved_list()

        installed_frame = ctk.CTkFrame(master, fg_color=theme.P("panel"), corner_radius=12)
        installed_frame.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=(0, 8))
        installed_frame.grid_columnconfigure(0, weight=1)
        installed_frame.grid_rowconfigure(1, weight=1)

        installed_head = ctk.CTkFrame(installed_frame, fg_color="transparent")
        installed_head.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
        ctk.CTkLabel(installed_head, text="INSTALLED PACKAGES", font=ctk.CTkFont("Segoe UI", 14, "bold")).pack(side="left")
        ctk.CTkButton(installed_head, text="Refresh", width=70, height=28, fg_color=theme.P("soft"), hover_color=theme.P("border"), font=ctk.CTkFont("Segoe UI", 12), command=self.refresh_packages).pack(side="right")
        ctk.CTkButton(installed_head, text="Uninstall", width=84, height=28, fg_color="#b62324", hover_color="#f85149", font=ctk.CTkFont("Segoe UI", 12), command=self.uninstall_package).pack(side="right", padx=6)

        self.installed_list = self._listbox(installed_frame, row=1)

        self.pip_console = LogPanel(master, "PIP OUTPUT", var=self.autoscroll_var, locked=True, show_autoscroll=False)
        self.pip_console.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(0, 8))
        self._log_panels.append(self.pip_console)
        self.pip_console.append("Library manager ready. Output from pip appears here.", SYSTEM)

    def _listbox(self, frame, row):
        body = ctk.CTkFrame(frame, fg_color="transparent")
        body.grid(row=row, column=0, sticky="nsew", padx=14, pady=(0, 12))
        listbox = tk.Listbox(
            body, bg=theme.P("input"), fg=theme.P("text"), selectbackground=theme.accent(), selectforeground="#ffffff",
            relief="flat", highlightthickness=1, highlightbackground=theme.P("border"),
            font=("Consolas", 11), activestyle="none", exportselection=False,
        )
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar = ctk.CTkScrollbar(body, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y", padx=(6, 0))
        self._listboxes.append(listbox)
        return listbox

    def _build_footer(self):
        footer = ctk.CTkFrame(self, fg_color=theme.P("panel"), corner_radius=0, height=30)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        self.footer_var = tk.StringVar(value="Ready")
        ctk.CTkLabel(footer, textvariable=self.footer_var, text_color=theme.P("muted"), font=ctk.CTkFont("Segoe UI", 11)).pack(side="left", padx=14, pady=6)
        ctk.CTkLabel(footer, text=f"profile: {self.profile}", text_color=theme.P("muted"), font=ctk.CTkFont("Segoe UI", 11)).pack(side="right", padx=14, pady=6)

    def apply_accent(self):
        accent = theme.accent()
        hover = theme.hover_of(accent)
        for button in self._accent_buttons:
            button.configure(fg_color=accent, hover_color=hover)
        for entry in self._accent_entries:
            entry.configure(border_color=accent)
        for listbox in self._listboxes:
            listbox.configure(selectbackground=accent)
        self.tabs.configure(
            segmented_button_selected_color=accent,
            segmented_button_selected_hover_color=hover,
        )
        try:
            self.code.configure(border_color=accent)
        except Exception:
            pass

    def restyle(self):
        old = dict(self._build_palette)
        keys = ["bg", "panel", "card", "input", "border", "text", "muted", "soft", "log_out", "log_err", "log_warn", "log_sys", "log_pip"]

        def visit(widget):
            if isinstance(widget, (tk.Text, tk.Listbox)):
                widget.configure(bg=theme.P("input"), fg=theme.P("text"), highlightbackground=theme.P("border"))
                return
            try:
                fg = widget.cget("fg_color")
                for key in keys:
                    if fg == old[key]:
                        widget.configure(fg_color=theme.P(key))
                        break
            except Exception:
                pass
            try:
                text = widget.cget("text_color")
                for key in keys:
                    if text == old[key]:
                        widget.configure(text_color=theme.P(key))
                        break
            except Exception:
                pass
            for child in widget.winfo_children():
                visit(child)

        self.configure(fg_color=theme.P("bg"))
        for child in self.winfo_children():
            visit(child)
        for panel in self._log_panels:
            panel.restyle()
        for listbox in self._listboxes:
            listbox.configure(selectbackground=theme.accent())
        self._build_palette = dict(theme._current)

    def _apply_fonts(self):
        font = ("Consolas", self.current_font_size)
        self.code.configure(font=font)
        for panel in self._log_panels:
            panel.set_font(font)

    def _on_theme_change(self, *_):
        name = self.theme_var.get()
        if not theme.palette_of(name):
            return
        theme.set_palette(name)
        self.restyle()
        self.apply_accent()
        self.settings_hint.configure(text=f"Theme changed to {name}.", text_color=theme.P("log_pip"))

    def _on_accent_change(self, *_):
        accent = self.accent_var.get()
        if accent not in theme.accent_names():
            return
        theme.set_accent(accent)
        self.apply_accent()
        self.settings_hint.configure(text=f"Accent changed to {accent}.", text_color=theme.P("log_pip"))

    def _on_scale_change(self, value):
        percent = int(value)
        self.scale_label.configure(text=f"{percent}%")
        ctk.set_widget_scaling(percent / 100.0)

    def _on_font_change(self, value):
        self.current_font_size = int(value)
        self.font_label.configure(text=str(self.current_font_size))
        self._apply_fonts()

    def _detect_interpreter(self):
        found = shutil.which("python") or shutil.which("python3") or "python"
        self.interp_var.set(found)
        self.footer_var.set(f"Interpreter: {found}")

    def _on_tab_changed(self, name):
        if name == "Libraries":
            self.refresh_packages()

    def _persist(self):
        self.cfg["active_profile"] = self.profile
        self.cfg["interpreter"] = self.interp_var.get().strip() or "python"
        try:
            self.cfg["max_restarts"] = abs(int(self.restarts_var.get()))
        except ValueError:
            self.cfg["max_restarts"] = 5
        try:
            self.cfg["restart_delay"] = abs(int(self.delay_var.get())) or 1
        except ValueError:
            self.cfg["restart_delay"] = 3
        self.cfg["autoscroll"] = self.autoscroll_var.get()
        self.cfg["autostart"] = self.autostart_var.get()
        self.cfg["save_token"] = self.save_token_var.get()
        self.cfg["theme"] = self.theme_var.get()
        self.cfg["accent"] = self.accent_var.get()
        try:
            self.cfg["widget_scaling"] = float(self.scale_var.get()) / 100.0
        except (TypeError, ValueError):
            self.cfg["widget_scaling"] = 1.0
        self.cfg["editor_font_size"] = self.current_font_size
        self.cfg["custom_libraries"] = list(self.saved_list.get(0, "end"))
        self.cfg["profiles"].setdefault(self.profile, {"code": "", "token": ""})
        self.cfg["profiles"][self.profile]["code"] = self.editor_code()
        if self.cfg.get("save_token", True):
            self.cfg["profiles"][self.profile]["token"] = self.token_var.get()
        config.save(self.cfg)

    def save_settings(self):
        self._persist()
        self.settings_hint.configure(text="Settings saved.", text_color=theme.P("log_pip"))
        self.footer_var.set("Settings saved.")

    def restore_defaults(self):
        for key in config.DEFAULTS:
            if key in ("profiles", "active_profile"):
                continue
            self.cfg[key] = config.DEFAULTS[key]
        self.theme_var.set(theme.DEFAULT_PALETTE)
        self.accent_var.set(theme.DEFAULT_ACCENT)
        self.scale_var.set(int(config.DEFAULTS["widget_scaling"] * 100))
        self.current_font_size = config.DEFAULTS["editor_font_size"]
        self.font_label.configure(text=str(self.current_font_size))
        self.interp_var.set(config.DEFAULTS["interpreter"])
        self.restarts_var.set(str(config.DEFAULTS["max_restarts"]))
        self.delay_var.set(str(config.DEFAULTS["restart_delay"]))
        self.autostart_var.set(config.DEFAULTS["autostart"])
        self.autoscroll_var.set(config.DEFAULTS["autoscroll"])
        self.save_token_var.set(config.DEFAULTS["save_token"])
        theme.set_palette(theme.DEFAULT_PALETTE)
        ctk.set_widget_scaling(config.DEFAULTS["widget_scaling"])
        self.restyle()
        self.apply_accent()
        self._apply_fonts()
        self._refresh_saved_list()
        config.save(self.cfg)
        self.settings_hint.configure(text="Defaults restored.", text_color=theme.P("log_pip"))

    def _refresh_saved_list(self):
        self.saved_list.delete(0, "end")
        for spec in self.cfg.get("custom_libraries", []):
            self.saved_list.insert("end", spec)

    def _guard_stdlib(self, spec):
        name = spec_package_name(spec)
        if name and theme.is_stdlib(name):
            self.pip_console.append(
                f"'{name}' is a core Python built-in module - it is always available and cannot (and should not) be installed via pip. Just use 'import {name}' in your bot code.",
                SYSTEM,
            )
            self.footer_var.set(f"'{name}' is built-in - no install needed.")
            return True
        return False

    def install_lib_now(self):
        spec = self.lib_spec_var.get().strip()
        if not spec:
            messagebox.showwarning("Empty", "Type a package name first.")
            return
        if self._guard_stdlib(spec):
            return
        self.manager.run_command([self._interp(), "-m", "pip", "install", spec], cwd=self._project_dir(), label="pip install")
        self.footer_var.set(f"Installing '{spec}'...")

    def save_lib_to_list(self):
        spec = self.lib_spec_var.get().strip()
        if not spec:
            messagebox.showwarning("Empty", "Type a package name first.")
            return
        if self._guard_stdlib(spec):
            return
        libs = list(self.cfg.get("custom_libraries", []))
        if spec not in libs:
            libs.append(spec)
            self.cfg["custom_libraries"] = libs
            self.saved_list.insert("end", spec)
            config.save(self.cfg)
        self.lib_spec_var.set("")
        self.footer_var.set(f"Saved '{spec}' to My Libraries")

    def remove_saved_lib(self):
        selection = self.saved_list.curselection()
        if not selection:
            return
        idx = int(selection[0])
        libs = list(self.cfg.get("custom_libraries", []))
        if 0 <= idx < len(libs):
            libs.pop(idx)
            self.cfg["custom_libraries"] = libs
            config.save(self.cfg)
            self._refresh_saved_list()

    def install_all_saved(self):
        libs = list(self.cfg.get("custom_libraries", []))
        if not libs:
            messagebox.showinfo("Empty", "No saved libraries to install.")
            return
        for spec in list(libs):
            if self._guard_stdlib(spec):
                libs.remove(spec)
        if not libs:
            self.footer_var.set("All saved libraries are built-in modules - nothing to install.")
            return
        self.manager.run_command([self._interp(), "-m", "pip", "install", *libs], cwd=self._project_dir(), label="bulk install")
        self.footer_var.set("Installing all saved libraries...")

    def install_requirements(self):
        self.manager.run_command(
            [self._interp(), "-m", "pip", "install", "-r", config.requirements_path()],
            cwd=self._project_dir(), label="requirements install",
        )
        self.footer_var.set("Installing requirements.txt...")

    def refresh_packages(self):
        command = [self._interp(), "-m", "pip", "list", "--format=freeze"]
        threading.Thread(target=self._collect_packages, args=(command,), daemon=True).start()

    def _collect_packages(self, command):
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=60)
            lines = [line for line in result.stdout.splitlines() if line.strip()]
        except Exception as exc:
            lines = [f"(failed to list packages: {exc})"]
        self.manager.events.put({"kind": "packages", "data": lines})

    def uninstall_package(self):
        selection = self.installed_list.curselection()
        if not selection:
            return
        name = self.installed_list.get(int(selection[0])).split("==")[0].strip()
        if not name:
            return
        if not messagebox.askyesno("Uninstall", f"Uninstall '{name}'?"):
            return
        self.manager.run_command([self._interp(), "-m", "pip", "uninstall", "-y", name], cwd=self._project_dir(), label="pip uninstall")
        self.footer_var.set(f"Uninstalling '{name}'...")

    def _load_profile(self, initial=False):
        data = self.cfg["profiles"].get(self.profile, {})
        self.code.delete("1.0", "end")
        self.code.insert("1.0", data.get("code", ""))
        self.token_var.set(data.get("token", ""))
        self.profile_menu.set(self.profile)
        if not initial:
            self.footer_var.set(f"Loaded profile '{self.profile}'")

    def _on_profile_selected(self, name):
        if self.manager.running:
            self._persist()
            messagebox.showwarning("Bot running", "Stop the bot before switching profiles.")
            self.profile_menu.set(self.profile)
            self._load_profile()
            return
        self._persist()
        self.profile = name
        self.cfg["active_profile"] = name
        self._load_profile()

    def new_profile(self):
        if self.manager.running:
            messagebox.showwarning("Bot running", "Stop the bot before creating a profile.")
            return
        dialog = ctk.CTkInputDialog(text="Profile name:", title="New Profile")
        name = dialog.get_input()
        if not name or not name.strip():
            return
        name = name.strip()
        if name in self.cfg["profiles"]:
            messagebox.showwarning("Exists", f"Profile '{name}' already exists.")
            return
        self._persist()
        self.profile = name
        self.cfg["profiles"][name] = {"code": "", "token": ""}
        self.cfg["active_profile"] = name
        self.profile_menu.configure(values=list(self.cfg["profiles"].keys()))
        self._load_profile()

    def save_profile(self):
        self._persist()
        self.footer_var.set(f"Saved profile '{self.profile}'")

    def delete_profile(self):
        if len(self.cfg["profiles"]) <= 1:
            messagebox.showinfo("Cannot delete", "At least one profile is required.")
            return
        if self.manager.running:
            messagebox.showwarning("Bot running", "Stop the bot before deleting a profile.")
            return
        if not messagebox.askyesno("Delete profile", f"Delete '{self.profile}'?"):
            return
        del self.cfg["profiles"][self.profile]
        self.profile = next(iter(self.cfg["profiles"]))
        self.cfg["active_profile"] = self.profile
        self.profile_menu.configure(values=list(self.cfg["profiles"].keys()))
        self._load_profile()

    def _syntax_error(self, code):
        try:
            compile(code, "<bot>", "exec")
            return None
        except (SyntaxError, IndentationError, ValueError) as exc:
            return exc

    def _report_syntax_error(self, error, code):
        lines = code.splitlines()
        lineno = getattr(error, "lineno", None) or 1
        self.log_panel.clear()
        self.log_panel.append(f"[PRE-LAUNCH CHECK FAILED]", ERR)
        self.log_panel.append(f"{type(error).__name__}: {getattr(error, 'msg', str(error))}", ERR)
        if lineno:
            self.log_panel.append(f"On line {lineno}:", ERR)
            for number in range(max(1, lineno - 2), min(len(lines), lineno + 2) + 1):
                marker = "   >> " if number == lineno else "      "
                self.log_panel.append(f"{marker}{number:>4} | {lines[number - 1]}{' <-' if number == lineno else ''}", ERR)
            self.log_panel.append("Fix the indentation/spacing and try again. Tip: remove any stray leading spaces.", WARN)
        self._set_status("Crashed")
        self.footer_var.set(f"Syntax error - bot not started (line {lineno}).")

    def _write_and_check(self, code):
        script_file = config.runtime_file(self.profile)
        try:
            with open(script_file, "w", encoding="utf-8") as f:
                f.write(code)
        except OSError as exc:
            messagebox.showerror("Error", f"Could not write script: {exc}")
            return None
        error = self._syntax_error(code)
        if error:
            self._report_syntax_error(error, code)
            return None
        return script_file

    def start_bot(self):
        code = self.editor_code()
        if not code.strip():
            messagebox.showwarning("Empty script", "Write some bot code first.")
            return
        script_file = self._write_and_check(code)
        if not script_file:
            return
        self._persist()
        self.log_panel.clear()
        self.footer_var.set(f"Starting profile '{self.profile}'...")
        self.manager.start(
            script_file,
            self.cfg["max_restarts"],
            self.cfg["restart_delay"],
            self.cfg["interpreter"],
            self.token_var.get(),
        )

    def stop_bot(self):
        self.manager.stop()
        self.footer_var.set("Stop requested.")

    def restart_bot(self):
        if not self.manager.running:
            return
        script_file = self._write_and_check(self.editor_code())
        if not script_file:
            self.stop_bot()
            return
        self.log_panel.append("Manual restart requested.", SYSTEM)
        self._persist()
        self.manager.restart(
            script_file,
            self.cfg["max_restarts"],
            self.cfg["restart_delay"],
            self.cfg["interpreter"],
            self.token_var.get(),
        )

    def insert_template(self):
        code = self.editor_code()
        template = TEMPLATES[self.template_var.get()]
        if code.strip():
            code = code.rstrip() + "\n\n# -------\n\n" + template
            self.code.delete("1.0", "end")
            self.code.insert("1.0", code)
        else:
            self.code.delete("1.0", "end")
            self.code.insert("1.0", template)
        self.footer_var.set(f"Inserted template '{self.template_var.get()}'")

    def show_invite(self):
        InviteDialog(self, self.token_var.get())

    def _set_status(self, text):
        color, label = STATUS_STYLES.get(text, ("#9ea7b3", f"● {text}"))
        self.status_pill.configure(text=label, fg_color=color, text_color="#ffffff")
        running = text == "Running"
        self.btn_start.configure(state="disabled" if running else "normal")
        self.btn_stop.configure(state="normal" if running else "disabled")
        self.btn_restart.configure(state="normal" if running else "disabled")

    def _handle_event(self, ev):
        kind = ev["kind"]
        if kind == "log":
            payload = ev["payload"]
            self.log_panel.append(payload["text"], payload["stream"])
            if payload["stream"] == PIP:
                self.pip_console.append(payload["text"], PIP)
        elif kind == "status":
            self._set_status(ev["payload"])
        elif kind == "packages":
            self._populate_packages(ev["data"])

    def _populate_packages(self, lines):
        self.installed_list.delete(0, "end")
        for line in lines:
            self.installed_list.insert("end", line)
        self.footer_var.set(f"{len(lines)} packages installed.")

    def _poll(self):
        try:
            while True:
                self._handle_event(self.manager.events.get_nowait())
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _tick(self):
        self.uptime_label.configure(text="Uptime " + format_uptime(self.manager.uptime))
        self.restart_label.configure(text="Restarts " + str(getattr(self.manager, "restart_count", 0)))
        self.after(1000, self._tick)

    def _on_close(self):
        self._persist()
        if self.manager.running:
            self.manager.stop(grace=3.0)
        self.destroy()