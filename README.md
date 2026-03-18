```
  ██████╗ ██╗   ██╗██╗     ██╗███╗   ██╗  ██████╗  ██████╗
  ██╔══██╗╚██╗ ██╔╝██║     ██║████╗  ██║ ██╔════╝ ██╔═══██╗
  ██████╔╝ ╚████╔╝ ██║     ██║██╔██╗ ██║ ██║  ███╗██║   ██║
  ██╔═══╝   ╚██╔╝  ██║     ██║██║╚██╗██║ ██║   ██║██║   ██║
  ██║        ██║   ███████╗██║██║ ╚████║ ╚██████╔╝╚██████╔╝
  ╚═╝        ╚═╝   ╚══════╝╚═╝╚═╝  ╚═══╝ ╚═════╝  ╚═════╝
```

# PyLingo

Duolingo automation tool — XP farming, gem farming, streak farming, and practice auto-solving via browser automation. Professional terminal UI with arrow-key navigation.

---

## Requirements

- Python 3.8 or higher
- Internet connection (for GitHub auto-update and Duolingo API)

All Python dependencies are installed automatically on first run.

| Package | Purpose | Auto-installed |
|---|---|---|
| `requests` | HTTP client for Duolingo API | Yes |
| `questionary` | Interactive terminal select menus | Yes |
| `playwright` | Browser automation for Practice Farm | Yes, on demand |

---

## Installation

```bash
git clone https://github.com/not2pixel/PyLingo.git
cd PyLingo
```

No manual `pip install` needed. The launcher handles everything.

---

## Usage

### Recommended — always use the Launcher

```bash
python Launcher.py
```

The launcher fetches the latest `pylingo.py` from GitHub, caches it locally, then executes it. You always run the most recent version without doing anything manually.

### Run directly (no update check)

```bash
python pylingo.py
```

---

## Launcher

`Launcher.py` is a standalone auto-updater. It has zero external dependencies and runs on pure Python stdlib.

```
  ██████╗ ██╗   ██╗██╗     ██╗███╗   ██╗  ██████╗  ██████╗
  ...

  PyLingo Launcher  v1.0.0
  ────────────────────────────────────────────────────────
  09:14:22  OK  Cache is fresh (312s old) — skipping update check
  09:14:22  OK  Already up to date (2.0.0)
  09:14:22  >>  Launching PyLingo 2.0.0...
```

### Launcher options

```
python Launcher.py [options]

  --update        Force re-download from GitHub, then run
  --offline       Run from cache without checking for updates
  --check         Check for update and exit (no launch)
  --cache-info    Print cache metadata and exit
  --help          Show this help
```

### How caching works

The launcher stores a local copy of `pylingo.py` in `.pylingo_cache/`. It re-checks GitHub at most once per hour using SHA-256 hash comparison — if the file has not changed, nothing is downloaded. On a failed network request, it falls back to the cached version silently.

```
PyLingo/
├── Launcher.py
├── pylingo.py
├── accounts.json          ← created on first account add
└── .pylingo_cache/
    ├── pylingo.py         ← cached script from GitHub
    └── meta.json          ← version, hash, timestamps
```

---

## Getting your JWT token

JWT is the authentication token from your active Duolingo browser session.

**Desktop (Chrome / Firefox / Edge)**

1. Go to [duolingo.com](https://www.duolingo.com) and log in
2. Open DevTools — `Ctrl+Shift+I` on Windows/Linux, `Cmd+Option+I` on Mac
3. Go to the **Console** tab
4. Run:
   ```js
   document.cookie.match(/jwt_token=([^;]+)/)[1]
   ```
5. Copy the output

**Mobile**

- iOS: [Web Inspector](https://apps.apple.com/us/app/web-inspector/id1584825745)
- Android: [Kiwi Browser](https://play.google.com/store/apps/details?id=com.kiwibrowser.browser) with DevTools enabled

> JWT tokens expire after roughly 30 days or when you log out. If you receive a 403 error, get a fresh token and re-add the account.

---

## Features

### XP Farm

Calls the Stories API endpoint for 499 XP per request. Automatically falls back to UNIT_TEST sessions (~110 XP) if rate-limited (HTTP 429). Displays live XP/hr rate in the terminal.

```
  09:14:23  >>  XP Farm  |  Stories 499 XP  (fallback UNIT_TEST 110 XP)
  09:14:23      skill_id: abc123...

  >> +499 XP   total=4,970   rate=87,400/hr   00:03
```

### Gem Farm

Calls the reward endpoint in configurable batches. Each successful call yields 30 gems. Automatically stops after 5 consecutive errors.

```
  >> +90 gems   total=720   rate=12,600/hr   00:03
```

### Streak Farm — Safe mode

Calculates your account age in days, then farms GLOBAL_PRACTICE sessions from your account creation date forward. The streak is capped to the number of days your account has existed — it cannot exceed a realistic value.

```
  ╭───────────────── Streak Farm — Safe Mode ─────────────────╮
  │   Created          2022-03-15                              │
  │   Account age      1,098 days                             │
  │   Current streak   0 days                                 │
  │   Safe target      1,098 days                             │
  │   To farm          1,098 days                             │
  ╰────────────────────────────────────────────────────────────╯

  >> [████████████░░░░░░░░░░░░░░░░░░]  440/1098   streak=440   01:22
```

### Streak Farm — Normal mode

No cap. Goes backwards from your current streak start date. Higher ban risk — confirm prompt required.

### Mixed Farm

Alternates one XP call and one gem call per loop iteration. Maximises both simultaneously with a single delay setting.

```
  >> XP=14,970 (86,400/hr)   gems=420 (2,430/hr)   00:10
```

### Practice Farm

Browser automation via Playwright (Chromium). Navigates to `/practice`, solves challenges automatically (word bank, radio choices, text input), and loops for a configurable number of sessions. Supports headless and headed mode.

Playwright is not pre-installed. The first time you select Practice Farm you will be prompted to install it (~150 MB, one-time).

```
  09:14:40  >>  Practice Farm  |  loops=20  headless=True
  09:14:40      Launching browser...

  >> Practice: 7/20   errors=0   00:48
```

---

## Terminal UI

Navigation is done with arrow keys and Enter — no number typing. All menus are rendered using `questionary` with a consistent blue/green color scheme.

```
  Main Menu
  > Farm
    Account Manager
    Streak Status
    Settings
    Exit
```

---

## Multi-account support

Add as many accounts as needed. Each account stores its JWT token, user ID, and cached profile info in `accounts.json`. The account selector shows username, streak, XP, and expiry status.

```
  Select account
  > 1.  Alice   streak=847  xp=124500
    2.  Bob     streak=12   xp=8300
    3.  Charlie   [EXPIRED]  streak=0  xp=200
    Cancel
```

---

## Settings

Accessible from the main menu. Available options:

- Clear all saved accounts
- Install or reinstall Playwright
- Show the path to `accounts.json`

---

## File structure

```
PyLingo/
├── Launcher.py        Auto-updater and entry point
├── pylingo.py         Main tool
├── accounts.json      Saved accounts (created automatically)
├── README.md
└── .pylingo_cache/
    ├── pylingo.py     Cached version from GitHub
    └── meta.json      Update metadata
```

---

## Security

- JWT tokens are stored locally in `accounts.json` in plain text. Keep this file private and do not commit it to version control.
- PyLingo makes HTTPS requests only to `www.duolingo.com` and `stories.duolingo.com`.
- The launcher fetches scripts only from `raw.githubusercontent.com/not2pixel/PyLingo`.
- No data is sent to any third-party service.

Add `accounts.json` to your `.gitignore`:

```
accounts.json
.pylingo_cache/
```

---

## Disclaimer

This project is for educational and research purposes. Automating Duolingo activity may violate their [Terms of Service](https://www.duolingo.com/terms). Use at your own risk. The authors are not responsible for any account actions taken by Duolingo.

---

## Credits

API endpoints and session payloads referenced from [DuoXPy](https://github.com/DuoXPy/DuoXPy-Bot) and the DuoHacker userscript.

---

## License

MIT
