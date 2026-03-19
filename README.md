```
  ██████╗ ██╗   ██╗██╗     ██╗███╗   ██╗  ██████╗  ██████╗
  ██╔══██╗╚██╗ ██╔╝██║     ██║████╗  ██║ ██╔════╝ ██╔═══██╗
  ██████╔╝ ╚████╔╝ ██║     ██║██╔██╗ ██║ ██║  ███╗██║   ██║
  ██╔═══╝   ╚██╔╝  ██║     ██║██║╚██╗██║ ██║   ██║██║   ██║
  ██║        ██║   ███████╗██║██║ ╚████║ ╚██████╔╝╚██████╔╝
  ╚═╝        ╚═╝   ╚══════╝╚═╝╚═╝  ╚═══╝ ╚═════╝  ╚═════╝
```

# PyLingo

Duolingo automation tool — XP farming, gem farming, streak farming, practice auto-solving, and daily quest completion. Professional terminal UI powered by `rich`.

---

## Requirements

- Python 3.8 or higher
- Internet connection

All Python dependencies are installed automatically on first run via the launcher.

| Package | Purpose | Auto-installed |
|---|---|---|
| `rich` | Terminal UI, progress bars, tables | Yes |

---

## Installation

```bash
git clone []()
cd PyLingo
```

No manual `pip install` needed. The launcher handles everything.

---

## Usage

### Recommended — always use the Launcher

```bash
python Launcher.py
```

The launcher fetches the latest `pylingo.py` and `requirements.txt` from GitHub, installs any new dependencies, caches locally, then runs. You always get the most recent version automatically.

### Run directly (skip update check)

```bash
python pylingo.py
```

---

## Launcher

`Launcher.py` is a zero-dependency auto-updater (pure Python stdlib). Every launch fetches the latest script and requirements from GitHub.

```
  PyLingo Launcher  v1.0.0

  ⠹ Fetching pylingo.py
  ⠼ Fetching requirements.txt
  ✓ Up to date  1.0.0
  ✓ Dependencies up to date
```

### Launcher options

```
python Launcher.py [options]

  --offline    Run from cache, skip update and dependency check
  --help       Show this help
```

### Cache structure

```
PyLingo/
├── Launcher.py
├── pylingo.py
├── accounts.json          ← created on first account add
├── config.json            ← created on first settings change
└── .pylingo_cache/
    ├── pylingo.py         ← cached script from GitHub
    ├── requirements.txt   ← cached requirements from GitHub
    └── meta.json          ← version, hash, timestamps
```

---

## Getting your JWT token

JWT is the authentication token from your active Duolingo browser session.

**Desktop (Chrome / Firefox / Edge)**

1. Go to [duolingo.com](https://www.duolingo.com) and log in
2. Open DevTools — `Ctrl+Shift+I` on Windows/Linux, `Cmd+Option+I` on Mac
3. Go to the **Console** tab
4. Paste and run:
   ```js
   document.cookie.match(/jwt_token=([^;]+)/)[1]
   ```
5. Copy the output and paste it into PyLingo when prompted

**Mobile**

- iOS: [Web Inspector]()
- Android: [Kiwi Browser]() with DevTools enabled

> JWT tokens expire after roughly 30 days or when you log out. PyLingo warns you when a token has 3 days or less remaining. If you receive a 403 error, get a fresh token and re-add the account.

---

## Features

### XP Farm

Calls the Stories API endpoint for 499 XP per request. Falls back to UNIT_TEST sessions (~110 XP) when rate-limited. Displays live progress with a rich progress bar.

```
  ● XP  ████████████░░░░░░░░  4,970  0:00:03
```

### Gem Farm

Calls the reward endpoint in configurable batches of 30 gems per call. Stops automatically after 5 consecutive errors.

```
  ● gems  ████████████░░░░░░░░  720  0:00:03
```

### Streak Farm — Safe mode

Calculates your account age in days, then farms GLOBAL_PRACTICE sessions backwards from your streak start date. The streak is capped to the number of days your account has existed — cannot exceed a realistic value.

```
  ╭──────────── Streak Farm — Safe Mode ────────────╮
  │  Created          2022-03-15                     │
  │  Account age      1,098 days                     │
  │  Current streak   0 days                         │
  │  Safe target      1,098 days                     │
  ╰──────────────────────────────────────────────────╯

  ● streak days  ████████░░░░░░░░░░  440/1098  0:01:22
```

### Streak Farm — Normal mode

No cap. Goes backwards from your current streak start date. Higher detection risk — confirm prompt required.

### Mixed Farm

Alternates one XP call and one gem call per iteration. Maximises both simultaneously with a single delay setting.

### Auto Daily Quest

Completes all pending daily quests instantly via the Goals API. No delay required — runs once and exits.

### Auto League

Farms XP in a loop until your score is 1000 XP ahead of rank 2 in the current league. Stops automatically when the gap is achieved.

---

## Terminal UI

Navigation uses number keys — type the number and press Enter. All menus display per-category color coding.

```
  PyLingo  1.0.0  ·  14:32

  3 accounts — 1 expiring soon

  1. Farm            XP / Gems / Streak / Mixed / Quest / League
  2. Account Manager  Add, remove, and view saved accounts
  3. Shop Items       Browse and buy Duolingo shop items
  4. Generate Account Auto-generate new Duolingo accounts
  5. Streak Status    Check streak status across all accounts
  6. Settings         Configure PyLingo options

  0. Exit

  > _
```

---

## Multi-account support

Add as many accounts as needed. Each account stores its JWT token, user ID, and cached profile in `accounts.json`. The account selector shows username, streak, XP, and token expiry status.

JWT expiry warnings appear automatically:
- **3 days or less remaining** — yellow warning in main menu subtitle and farm menu
- **Expired** — red label, blocked from farming

---

## Config

Settings are stored in `config.json` (created automatically on first change).

| Key | Default | Description |
|---|---|---|
| `delay_ms` | `1500` | Default delay between farm requests (ms) |
| `debug` | `false` | Print raw API responses |

Editable via **Settings** in the main menu or directly in the JSON file.

---

## Settings menu

- **Default delay** — change the farm request delay (minimum 200 ms)
- **Debug mode** — toggle raw API response logging
- **Clear all accounts** — wipe `accounts.json`
- **Show accounts file** — print paths to `accounts.json` and `config.json`

---

## File structure

```
PyLingo/
├── Launcher.py        Auto-updater and entry point
├── pylingo.py         Main tool
├── accounts.json      Saved accounts (auto-created)
├── config.json        Settings (auto-created)
├── README.md
└── .pylingo_cache/
    ├── pylingo.py     Cached version from GitHub
    ├── requirements.txt
    └── meta.json      Update metadata
```

---

## Security

- JWT tokens are stored in `accounts.json` in plain text. Keep this file private and do not commit it to version control.
- PyLingo makes HTTPS requests only to `www.duolingo.com` and `stories.duolingo.com`.
- The launcher fetches scripts only from `raw.githubusercontent.com/not2pixel/PyLingo`.
- No data is sent to any third-party service.

Add these to your `.gitignore`:

```
accounts.json
config.json
.pylingo_cache/
```

---

## Credits

- API endpoints and session payloads referenced from [DuoXPy]()
- Browser automation approach inspired by [DuoHacker]()

---

## Disclaimer

This project is for educational and research purposes. Automating Duolingo activity may violate their [Terms of Service](https://www.duolingo.com/terms). Use at your own risk. The authors are not responsible for any account actions taken by Duolingo.

---

## License

MIT
