# Discord Bot Hoster

A modern, desktop application for writing, hosting, running, and monitoring Discord bots. Built with Python and `customtkinter`, it bundles a code editor, a live log console, a process manager with automatic crash recovery, a library manager, and deep UI customization - all in one window.

![App tabs](docs/screenshot.png)

> Screenshot placeholder - replace `docs/screenshot.png` with a real screenshot before publishing.

## Features

### Bot management
- Built-in code editor for your bot script with dark-syntax styling
- Start, Stop, and Restart controls with live status pill
- Auto-restart on crash with configurable retry limit and delay
- Uptime and restart counters
- Token field (passed to the bot via the `DISCORD_BOT_TOKEN` environment variable - never written into your code)
- Pre-launch syntax check that pinpoints the exact error line before the bot starts
- Multiple named bot profiles - save, switch, and duplicate configurations

### Live log
- Real-time, color-coded console output (stdout, errors, warnings, system, pip)
- Auto-scroll toggle and ANSI escape handling
- Dedicated output streams for the process and the library manager

### Library manager
- Install any pip package by name or pinned version (`name==version`)
- Persistent "My Libraries" list with bulk install
- Installed packages browser with refresh and uninstall
- Built-in module protection - warns when you try to "install" `os`, `sys`, etc.
- Discovers your `requirements.txt` automatically

### Customization
- 6 themes: Dark, Light, Midnight, Graphite, Forest, Sunrise - applied live
- 11 accent colors applied live across buttons, tabs, and selections
- Widget scaling (80-130%) and editor font size (10-18)
- Configurable Python interpreter (auto-detect button)

### Extras
- Discord invite link generator with permission calculator
- Ready-to-use bot templates (prefix commands, slash commands, moderation)

## Requirements

- Python 3.10 or newer (Python 3.14 recommended)
- Windows / macOS / Linux

## Quick start

1. Install the dependencies:

```bash
pip install -r requirements.txt
```

2. Run the app:

```bash
python main.py
```

3. Pick a template from the **Bot** tab (or write your own bot), paste your bot token, and press **Start**.

Your bot receives the token through the `DISCORD_BOT_TOKEN` environment variable, so latest templates reference it with `os.getenv("DISCORD_BOT_TOKEN")`.

## Build a standalone executable

Run the provided build script (Windows):

```bat
build_exe.bat
```

The build uses [PyInstaller](https://pyinstaller.org) and produces a single-file executable at `dist\DiscordBotHoster.exe`. You can upload that file to a GitHub Release.

On other platforms, run the equivalent PyInstaller command:

```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --collect-all customtkinter --name DiscordBotHoster main.py
```

## Usage guide

The app is organized into three tabs.

### Bot tab
- Write your bot's code in the editor.
- Enter your bot token (stored with the profile if "Save token" is enabled in Settings).
- **Start / Restart / Stop** to control the process.
- Manage multiple profiles with the profile dropdown and the New / Save / Delete buttons.
- Generate an invite link or insert a template.

### Settings tab
- **Appearance**: theme, accent color, widget size, and editor font size. All changes apply live.
- **Runtime**: Python interpreter (with automatic detection), max restarts, restart delay.
- **Behavior**: auto-start on launch, auto-scroll logs, save token with profiles.

### Libraries tab
- Install any pip package immediately or save it to "My Libraries" for later bulk install.
- Browse currently installed packages and uninstall them.
- Pip output streams into its own console and the main Live Log.

## How it works

- The bot runs as a separate Python subprocess, so a crashing bot can never take down the hoster.
- `app/bot_manager.py` supervises the subprocess, captures stdout/stderr, and implements the auto-restart policy (graceful stop via `CTRL_BREAK_EVENT`, hard kill as fallback).
- Logs and status updates flow from worker threads into a queue consumed by the Tk main loop.
- Configuration, profiles, tokens, and settings are stored in JSON at `~/.discord_bot_hoster/config.json`.

## Project structure

```
.
|-- main.py                 # Application entry point
|-- app/
|   |-- ui.py               # GUI (tabs, panels, dialogs)
|   |-- bot_manager.py      # Subprocess supervisor + auto-restart
|   |-- config.py           # Persistence layer
|   |-- theme.py            # Theme palettes, accent colors, helpers
|   |-- templates.py        # Bot code templates + invite link generator
|-- requirements.txt        # Python dependencies
|-- build_exe.bat           # Windows EXE build script
|-- dist/                   # Built executable (gitignored)
```

## Configuration file

All settings live in:

```
~/.discord_bot_hoster/config.json
```

Profiles, bot tokens, interpreter path, restart policy, theme, accent, scaling, and the saved library list are stored there. Delete the file to reset the app to default settings.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is open source. Add a license of your choice (for example MIT) before publishing.

## Disclaimer

Use responsibly. This is a hosting tool for bots that comply with Discord's Terms of Service. The author is not responsible for misuse of the software.