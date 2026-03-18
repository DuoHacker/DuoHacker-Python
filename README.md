# PyLingo

> **Duolingo XP / Gem / Streak farming tool — pure Python, terminal UI**

```
  ██████╗ ██╗   ██╗██╗     ██╗███╗   ██╗ ██████╗  ██████╗
  ██╔══██╗╚██╗ ██╔╝██║     ██║████╗  ██║██╔════╝ ██╔═══██╗
  ██████╔╝ ╚████╔╝ ██║     ██║██╔██╗ ██║██║  ███╗██║   ██║
  ██╔═══╝   ╚██╔╝  ██║     ██║██║╚██╗██║██║   ██║██║   ██║
  ██║        ██║   ███████╗██║██║ ╚████║╚██████╔╝╚██████╔╝
  ╚═╝        ╚═╝   ╚══════╝╚═╝╚═╝  ╚═══╝ ╚═════╝  ╚═════╝
                                                   v1.0.0
```

---

## ✨ Features

| Feature | Description |
|---|---|
| ⚡ **XP Farm** | Stories API (499 XP/call) with auto-fallback to UNIT_TEST (110 XP/call) |
| 💎 **Gem Farm** | Reward endpoint batch farming ~30 gems/call |
| 🔥 **Streak Farm (Safe)** | Farm streaks capped to account age — low ban risk |
| 🔥 **Streak Farm (Normal)** | Unlimited streak farming — use with care |
| ✨ **Mixed Farm** | XP + Gems alternating in one session |
| 🗄️ **Multi-account** | Store and manage multiple JWT-authenticated accounts |
| 🔑 **JWT tools** | Auto-detect expiry, decode payload, expiry date display |
| 📊 **Live stats** | Real-time XP/hr, gems/hr, elapsed time, spinner |
| 🖥️ **Terminal UI** | Full ANSI box-drawing, color, progress bars — no external deps |

---

## 🚀 Requirements

- Python **3.8+**
- **No external libraries** — pure stdlib only (`http.client`, `json`, `base64`, `threading`, etc.)

---

## 📦 Installation

```bash
git clone https://github.com/yourname/pylingo.git
cd pylingo
python3 pylingo.py
```

That's it. No `pip install`, no virtualenv needed.

---

## 🔑 Getting Your JWT Token

Your JWT token authenticates your Duolingo session. Get it from your browser:

### Desktop (Chrome/Firefox/Edge)
1. Go to [duolingo.com](https://www.duolingo.com) and log in
2. Open DevTools → `Ctrl+Shift+I` (Windows/Linux) or `Cmd+Option+I` (Mac)
3. Go to the **Console** tab
4. Paste and run:
```js
document.cookie.match(/jwt_token=([^;]+)/)[1]
```
5. Copy the output — that's your JWT token

### Mobile
- **iOS**: Use [Web Inspector](https://apps.apple.com/us/app/web-inspector/id1584825745)
- **Android**: Use [Kiwi Browser](https://play.google.com/store/apps/details?id=com.kiwibrowser.browser) with DevTools enabled

> ⚠️ **JWT tokens expire.** If you get a 403 error, get a fresh token and re-add your account.

---

## 🎮 Usage

### Main Menu

```
  1. ⚡ Farm              XP / Gems / Streak / Mixed
  2. 🗄️  Account Manager   Add / remove / view accounts
  3. 🔥 Streak Status     Check all accounts streak today
  4. ⚙️  Settings
  0. Exit
```

### Adding an Account

1. Select **Account Manager → Add Account**
2. Paste your JWT token
3. PyLingo fetches your profile and saves it locally to `accounts.json`

### XP Farm

Automatically tries the **Stories API** (499 XP per call) first. If rate-limited (429), switches to **UNIT_TEST** sessions (110 XP per call).

```
⚡ +499 XP  │  Total: 4,990 XP  │  Rate: 89,820 XP/hr  │  Time: 00:03
```

### Gem Farm

Calls the reward endpoint in batches of 3 (~30 gems per successful call).

```
💎 +90 💎  │  Total: 630 gems  │  Rate: 11,340/hr  │  Time: 00:02
```

### Streak Farm — Safe Mode

Calculates your account age in days, then farms streak days from your account creation date forward. **Streak is capped to account age** — cannot exceed a realistic value.

```
[████████████████░░░░░░░░░░░░░░] 800/1200  🔥 Streak: 1200  Time: 04:12
```

### Streak Farm — Normal Mode

Goes backwards from your current streak start date. No cap. Higher ban risk — use responsibly.

### Mixed Farm

Alternates XP calls and Gem calls in the same loop — maximize both simultaneously.

```
✨  XP: 14,970 (87,320/hr)  │  Gems: 420 (2,450/hr)  │  Time: 00:10
```

---

## ⚙️ Configuration

| Setting | Where | Default |
|---|---|---|
| Request delay | Prompted at farm start | 1500ms |
| Accounts storage | `accounts.json` (auto-created) | — |

Adjust delay to control rate. Lower = faster but higher ban risk. Recommended: **1000–2000ms**.

---

## 📁 File Structure

```
pylingo/
├── pylingo.py       # Main tool (single file, all features)
├── accounts.json    # Auto-created, stores your accounts
```

---

## 🔒 Security Notes

- JWT tokens are stored **locally** in `accounts.json`. Keep this file private.
- PyLingo makes HTTPS requests only to `www.duolingo.com` and `stories.duolingo.com`.
- No data is sent anywhere else.

---

## ⚠️ Disclaimer

This tool is for educational purposes. Use at your own risk. Automating Duolingo activity may violate their Terms of Service and result in account suspension.

---

## 🤝 Credits

Inspired by [DuoXPy](https://github.com/DuoXPy/DuoXPy-Bot) and the DuoHacker userscript. API endpoints and session payloads reverse-engineered from public Duolingo web traffic.

---

## 📜 License

MIT
