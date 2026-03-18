#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════════════
#  PyLingo  —  Duolingo XP / Gem / Streak / Practice Automation
#  Requires: requests, questionary, playwright (auto-installed on first run)
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations
import os, sys, json, time, base64, threading, signal, random, re, subprocess
import urllib.parse
from datetime import datetime, timezone
from typing import Optional

# ── Dependency bootstrap ───────────────────────────────────────────────────────
_REQUIRED = ["requests", "questionary"]

def _ensure_deps():
    import importlib.util
    missing = [p for p in _REQUIRED if importlib.util.find_spec(p) is None]
    if missing:
        print(f"\n  Installing: {', '.join(missing)}")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", "--user", *missing],
        )

_ensure_deps()

import requests
import questionary
from questionary import Style as QStyle

# ── Version ────────────────────────────────────────────────────────────────────
VERSION = "1.0.0"

BANNER = r"""
  ██████╗ ██╗   ██╗██╗     ██╗███╗   ██╗  ██████╗  ██████╗
  ██╔══██╗╚██╗ ██╔╝██║     ██║████╗  ██║ ██╔════╝ ██╔═══██╗
  ██████╔╝ ╚████╔╝ ██║     ██║██╔██╗ ██║ ██║  ███╗██║   ██║
  ██╔═══╝   ╚██╔╝  ██║     ██║██║╚██╗██║ ██║   ██║██║   ██║
  ██║        ██║   ███████╗██║██║ ╚████║ ╚██████╔╝╚██████╔╝
  ╚═╝        ╚═╝   ╚══════╝╚═╝╚═╝  ╚═══╝ ╚═════╝  ╚═════╝
"""

# ── ANSI ───────────────────────────────────────────────────────────────────────
def _c(t, code): return f"\033[{code}m{t}\033[0m"
def green(t):    return _c(t, "92")
def yellow(t):   return _c(t, "93")
def red(t):      return _c(t, "91")
def blue(t):     return _c(t, "94")
def cyan(t):     return _c(t, "96")
def magenta(t):  return _c(t, "95")
def bold(t):     return _c(t, "1")
def dim(t):      return _c(t, "2")
def _strip(t):   return re.sub(r'\033\[[0-9;]*m', '', str(t))

def cls():
    os.system("cls" if os.name == "nt" else "clear")

def tw() -> int:
    try:    return os.get_terminal_size().columns
    except: return 96

def hr(color="34"):
    return _c("─" * tw(), color)

def center(text: str) -> str:
    pad = max(0, (tw() - len(_strip(text))) // 2)
    return " " * pad + text

def box(lines: list, title: str = "", color: str = "34", width: int = 0) -> str:
    w = width or min(tw() - 4, 82)
    tl, tr, bl, br, h, v = "╭","╮","╰","╯","─","│"
    out = []
    if title:
        raw  = f"  {title}  "
        inner = w - 2
        lp   = (inner - len(_strip(raw))) // 2
        rp   = inner - lp - len(_strip(raw))
        out.append(_c(tl + h * lp, color) + bold(raw) + _c(h * rp + tr, color))
    else:
        out.append(_c(tl + h * (w - 2) + tr, color))
    for line in lines:
        pad = w - 2 - len(_strip(line))
        out.append(_c(v, color) + " " + line + " " * max(0, pad - 1) + _c(v, color))
    out.append(_c(bl + h * (w - 2) + br, color))
    return "\n".join(out)

# ── Logging ────────────────────────────────────────────────────────────────────
_log_lock = threading.Lock()
_LEVELS = {
    "info":    (dim,     "  "),
    "success": (green,   "OK"),
    "warning": (yellow,  "WR"),
    "error":   (red,     "ER"),
    "farm":    (magenta, ">>"),
    "stat":    (blue,    "--"),
}

def log(msg: str, level: str = "info"):
    ts = datetime.now().strftime("%H:%M:%S")
    fn, tag = _LEVELS.get(level, (dim, "  "))
    with _log_lock:
        print(f"  {dim(ts)}  {fn(tag)}  {msg}")

# ── questionary theme ──────────────────────────────────────────────────────────
_Q = QStyle([
    ("qmark",       "fg:#5f87ff bold"),
    ("question",    "bold"),
    ("answer",      "fg:#5fffaf bold"),
    ("pointer",     "fg:#5f87ff bold"),
    ("highlighted", "fg:#5fffaf bold"),
    ("selected",    "fg:#5fffaf"),
    ("separator",   "fg:#4e4e4e"),
    ("instruction", "fg:#4e4e4e"),
    ("disabled",    "fg:#4e4e4e italic"),
])

def ask_select(prompt: str, choices: list) -> Optional[str]:
    try:    return questionary.select(prompt, choices=choices, style=_Q).ask()
    except KeyboardInterrupt: return None

def ask_text(prompt: str, default: str = "") -> Optional[str]:
    try:    return questionary.text(prompt, default=default, style=_Q).ask()
    except KeyboardInterrupt: return None

def ask_confirm(prompt: str, default: bool = False) -> bool:
    try:    return questionary.confirm(prompt, default=default, style=_Q).ask() or False
    except KeyboardInterrupt: return False

def ask_password(prompt: str) -> Optional[str]:
    try:    return questionary.password(prompt, style=_Q).ask()
    except KeyboardInterrupt: return None

# ── HTTP ───────────────────────────────────────────────────────────────────────
_UAS = [
    "Duolingo/5.158.4 (iPhone; iOS 17.4; Scale/3.00)",
    "Duolingo/5.157.0 (Android; Build/12; Model/Pixel 7)",
    "Duolingo/5.156.2 (iPhone; iOS 16.7; Scale/2.00)",
    "Duolingo/5.159.0 (Android; Build/14; Model/OnePlus 12)",
]
BASE = "https://www.duolingo.com"

def _ua(): return random.choice(_UAS)

def _headers(jwt: str, sub: str = None) -> dict:
    return {
        "Content-Type":    "application/json",
        "Accept":          "application/json",
        "Authorization":   f"Bearer {jwt}",
        "User-Agent":      _ua(),
        "x-amzn-trace-id": f"User={sub}" if sub else "User=0",
        "Cookie":          f"jwt_token={jwt}",
        "Origin":          "https://www.duolingo.com",
        "Referer":         "https://www.duolingo.com/",
        "Host":            "www.duolingo.com",
        "Accept-Encoding": "identity",
    }

def _rjson(r: requests.Response) -> dict:
    try:    return r.json()
    except: return {}

def _get(path: str, jwt: str, sub=None):
    try:
        r = requests.get(BASE + path, headers=_headers(jwt, sub), timeout=30)
        return r.status_code, _rjson(r)
    except: return 0, {}

def _post(path: str, jwt: str, sub=None, body=None):
    try:
        r = requests.post(BASE + path, headers=_headers(jwt, sub), json=body, timeout=30)
        return r.status_code, _rjson(r)
    except: return 0, {}

def _put(path: str, jwt: str, sub=None, body=None):
    try:
        r = requests.put(BASE + path, headers=_headers(jwt, sub), json=body, timeout=30)
        return r.status_code, _rjson(r)
    except: return 0, {}

def _patch(path: str, jwt: str, sub=None, body=None):
    try:
        r = requests.patch(BASE + path, headers=_headers(jwt, sub), json=body, timeout=30)
        return r.status_code, _rjson(r)
    except: return 0, {}

# ── JWT ────────────────────────────────────────────────────────────────────────
def decode_jwt(token: str) -> dict:
    try:
        p = token.split(".")[1]
        p += "=" * (4 - len(p) % 4)
        return json.loads(base64.urlsafe_b64decode(p))
    except Exception as e:
        raise ValueError(f"Invalid JWT: {e}")

def jwt_sub(token: str) -> Optional[str]:
    return decode_jwt(token).get("sub")

def jwt_expired(token: str) -> bool:
    try:
        exp = decode_jwt(token).get("exp")
        return bool(exp and time.time() > exp)
    except: return True

def jwt_expires_at(token: str) -> str:
    try:
        exp = decode_jwt(token).get("exp")
        return datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M") if exp else "unknown"
    except: return "unknown"

# ── Accounts ───────────────────────────────────────────────────────────────────
_ACCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accounts.json")

def load_accounts() -> list:
    if os.path.exists(_ACCS):
        try:
            with open(_ACCS) as f: return json.load(f)
        except: pass
    return []

def save_accounts(data: list):
    with open(_ACCS, "w") as f: json.dump(data, f, indent=2)

# ── Duolingo API ───────────────────────────────────────────────────────────────
_FIELDS = (
    "id,username,fromLanguage,learningLanguage,streak,totalXp,gems,lingots,"
    "creationDate,streakData,trackingProperties,"
    "currentCourse{pathSectioned{units{levels{"
    "pathLevelMetadata{skillId},pathLevelClientData{skillId}"
    "}}}}"
)

def get_user_info(jwt: str, sub: str) -> dict:
    if jwt_expired(jwt):
        raise ValueError("JWT expired — please re-link your account")
    path = f"/2017-06-30/users/{sub}?fields={urllib.parse.quote(_FIELDS)}"
    st, data = _get(path, jwt, sub)
    if st == 403: raise PermissionError("JWT rejected (403) — token expired or revoked")
    if st != 200: raise ConnectionError(f"API error HTTP {st}")
    tp = data.get("trackingProperties", {})
    if tp.get("creation_date_new"):
        data["creationDate"] = tp["creation_date_new"]
    elif isinstance(data.get("creationDate"), (int, float)):
        data["creationDate"] = datetime.fromtimestamp(data["creationDate"] / 1000).isoformat()
    return data

def extract_skill_id(course: dict) -> Optional[str]:
    try:
        for sec in (course or {}).get("pathSectioned", []):
            for unit in sec.get("units", []):
                for level in unit.get("levels", []):
                    for key in ("pathLevelMetadata", "pathLevelClientData"):
                        sk = (level.get(key) or {}).get("skillId")
                        if sk: return sk
    except: pass
    return None

def streak_done_today(sd: dict) -> bool:
    try:
        upd = sd.get("updatedAt") or (sd.get("currentStreak") or {}).get("endDate")
        if not upd: return False
        dt = (datetime.fromtimestamp(upd / 1000, tz=timezone.utc)
              if isinstance(upd, (int, float))
              else datetime.fromisoformat(str(upd).replace("Z", "+00:00")))
        return dt.date() >= datetime.now(tz=timezone.utc).date()
    except: return False

# ── Farm primitives ────────────────────────────────────────────────────────────
def _farm_stories(jwt: str, sub: str, info: dict) -> int:
    now = int(time.time())
    body = {
        "awardXp": True, "completedBonusChallenge": True,
        "fromLanguage": info["fromLanguage"], "learningLanguage": info["learningLanguage"],
        "hasXpBoost": False, "illustrationFormat": "svg",
        "isFeaturedStoryInPracticeHub": True, "isLegendaryMode": True,
        "isV2Redo": False, "isV2Story": False, "masterVersion": True,
        "maxScore": 0, "score": 0, "happyHourBonusXp": 469,
        "startTime": now, "endTime": now + random.randint(300, 420),
    }
    try:
        r = requests.post(
            "https://stories.duolingo.com/api2/stories/fr-en-le-passeport/complete",
            headers={
                "Content-Type": "application/json", "Authorization": f"Bearer {jwt}",
                "User-Agent": _ua(), "Cookie": f"jwt_token={jwt}",
                "Origin": "https://stories.duolingo.com", "Host": "stories.duolingo.com",
            },
            json=body, timeout=30,
        )
        return r.status_code
    except: return 0

def _farm_unit(jwt: str, sub: str, info: dict, skill_id: str) -> tuple:
    body = {"challengeTypes": [], "fromLanguage": info["fromLanguage"],
            "learningLanguage": info["learningLanguage"],
            "type": "UNIT_TEST", "skillIds": [skill_id]}
    st, session = _post("/2017-06-30/sessions", jwt, sub, body)
    if st != 200 or not session.get("id"): return False, 0
    t = int(time.time())
    update = {
        "id": session["id"], "metadata": session.get("metadata", {}),
        "type": "UNIT_TEST",
        "fromLanguage": info["fromLanguage"], "learningLanguage": info["learningLanguage"],
        "challenges": [], "adaptiveChallenges": [], "sessionExperimentRecord": [],
        "experiments_with_treatment_contexts": [], "adaptiveInterleavedChallenges": [],
        "sessionStartExperiments": [], "trackingProperties": [], "ttsAnnotations": [],
        "heartsLeft": 0, "startTime": t, "enableBonusPoints": True,
        "endTime": t + 60, "failed": False, "maxInLessonStreak": 9,
        "shouldLearnThings": True, "hasBoost": True, "happyHourBonusXp": 10,
        "pathLevelSpecifics": {"unitIndex": 0},
    }
    st2, data = _put(f"/2017-06-30/sessions/{session['id']}", jwt, sub, update)
    if st2 == 200:
        return True, data.get("awardedXp") or data.get("xpGain") or 110
    return False, 0

def _farm_gem(jwt: str, sub: str, info: dict) -> tuple:
    rid  = "SKILL_COMPLETION_BALANCED-dd2495f4_d44e_3fc3_8ac8_94e2191506f0-2-GEMS"
    body = {"consumed": True, "learningLanguage": info["learningLanguage"],
            "fromLanguage": info["fromLanguage"]}
    st, _ = _patch(f"/2023-05-23/users/{sub}/rewards/{rid}", jwt, sub, body)
    return st == 200, 30 if st == 200 else 0

_CT = [
    "assist","characterIntro","characterMatch","characterPuzzle","characterSelect",
    "characterTrace","characterWrite","completeReverseTranslation","definition",
    "dialogue","extendedMatch","extendedListenMatch","form","freeResponse","gapFill",
    "judge","listen","listenComplete","listenMatch","match","name","listenComprehension",
    "listenIsolation","listenSpeak","listenTap","orderTapComplete","partialListen",
    "partialReverseTranslate","patternTapComplete","radioBinary","radioImageSelect",
    "radioListenMatch","radioListenRecognize","radioSelect","readComprehension",
    "reverseAssist","sameDifferent","select","selectPronunciation","selectTranscription",
    "svgPuzzle","syllableTap","syllableListenTap","speak","tapCloze","tapClozeTable",
    "tapComplete","tapCompleteTable","tapDescribe","translate","transliterate",
    "transliterationAssist","typeCloze","typeClozeTable","typeComplete",
    "typeCompleteTable","writeComprehension",
]

def _farm_session(jwt: str, sub: str, info: dict, t0: int, t1: int) -> bool:
    body = {"challengeTypes": _CT, "fromLanguage": info["fromLanguage"],
            "isFinalLevel": False, "isV2": True, "juicy": True,
            "learningLanguage": info["learningLanguage"],
            "smartTipsVersion": 2, "type": "GLOBAL_PRACTICE"}
    st, session = _post("/2023-05-23/sessions", jwt, sub, body)
    if st != 200 or not session.get("id"): return False
    update = {**session, "heartsLeft": 0, "startTime": t0, "enableBonusPoints": False,
              "endTime": t1, "failed": False, "maxInLessonStreak": 9, "shouldLearnThings": True}
    st2, _ = _put(f"/2023-05-23/sessions/{session['id']}", jwt, sub, update)
    return st2 == 200

# ── Farm state ─────────────────────────────────────────────────────────────────
class _State:
    def __init__(self):
        self.running = False; self.xp = 0; self.gems = 0
        self.streaks = 0; self.errors = 0; self.calls = 0
        self.t0 = None

    def reset(self): self.__init__()

    def elapsed(self) -> str:
        s = int(time.time() - self.t0) if self.t0 else 0
        return f"{s//60:02d}:{s%60:02d}"

    def rate(self, v: int) -> float:
        return v / max(1, time.time() - self.t0) * 3600 if self.t0 else 0

S = _State()
_SP = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]

def _spin(n): return _SP[n % len(_SP)]

def _summary(mode: str, val: int, unit: str):
    print("\n")
    print(box([
        f"  {'Mode':<14}  {bold(mode)}",
        f"  {'Total':<14}  {green(str(val))} {unit}",
        f"  {'API calls':<14}  {blue(str(S.calls))}",
        f"  {'Errors':<14}  {yellow(str(S.errors))}",
        f"  {'Runtime':<14}  {cyan(S.elapsed())}",
    ], title="Session Summary", color="34"))
    print()

# ── Farm runners ───────────────────────────────────────────────────────────────
def run_xp(jwt, sub, info, delay_ms):
    S.running = True; S.t0 = time.time()
    stories = True; c429 = fberr = tick = 0
    skill   = extract_skill_id(info.get("currentCourse"))
    print()
    log(f"XP Farm  |  Stories 499 XP  (fallback UNIT_TEST 110 XP)", "farm")
    log(f"skill_id: {bold(skill) if skill else red('none')}", "info")
    print()
    while S.running:
        tick += 1
        if stories:
            st = _farm_stories(jwt, sub, info)
            if st == 200:
                c429 = fberr = 0; S.xp += 499; S.calls += 1
                print(f"\r  {_spin(tick)}  +499 XP   total={bold(str(S.xp))}   "
                      f"rate={cyan(f'{S.rate(S.xp):,.0f}/hr')}   {dim(S.elapsed())}     ",
                      end="", flush=True)
            elif st == 429:
                c429 += 1
                if c429 >= 2: log("\n  Rate-limited — switching to UNIT_TEST", "warning"); stories = False
                time.sleep(delay_ms / 1000 * 2); continue
            else:
                log(f"\n  Stories {st} — switching to UNIT_TEST", "warning"); stories = False
        else:
            if not skill: log("No skill ID — cannot continue.", "error"); break
            ok, earned = _farm_unit(jwt, sub, info, skill)
            if ok:
                fberr = 0; S.xp += earned; S.calls += 1
                print(f"\r  {_spin(tick)}  +{earned} XP   total={bold(str(S.xp))}   "
                      f"rate={cyan(f'{S.rate(S.xp):,.0f}/hr')}   {dim(S.elapsed())}     ",
                      end="", flush=True)
            else:
                fberr += 1; S.errors += 1
                if fberr >= 5: log("\n  Too many errors — stopping.", "error"); break
                time.sleep(delay_ms / 1000 * 3); continue
        time.sleep(delay_ms / 1000)
    print(); S.running = False; _summary("XP Farm", S.xp, "XP")

def run_gems(jwt, sub, info, delay_ms, batch=3):
    S.running = True; S.t0 = time.time(); cerr = tick = 0
    print(); log(f"Gem Farm  |  batch={batch}  delay={delay_ms}ms", "farm"); print()
    while S.running:
        tick += 1; ok_n = 0
        for _ in range(batch):
            ok, earned = _farm_gem(jwt, sub, info)
            if ok: ok_n += 1; S.gems += earned
            time.sleep(0.15)
        if ok_n:
            cerr = 0; S.calls += ok_n
            print(f"\r  {_spin(tick)}  +{ok_n*30} gems   total={bold(str(S.gems))}   "
                  f"rate={cyan(f'{S.rate(S.gems):,.0f}/hr')}   {dim(S.elapsed())}     ",
                  end="", flush=True)
        else:
            cerr += 1; S.errors += 1
            if cerr >= 5: log("\n  Too many errors — stopping.", "error"); break
            time.sleep(delay_ms / 1000 * 3); continue
        time.sleep(delay_ms / 1000)
    print(); S.running = False; _summary("Gem Farm", S.gems, "gems")

def run_streak_safe(jwt, sub, info, delay_ms):
    creation = info.get("creationDate")
    if not creation: log("Cannot determine account creation date.", "error"); return
    try:
        c_dt = (datetime.fromtimestamp(creation / 1000) if isinstance(creation, (int, float))
                else datetime.fromisoformat(str(creation).split("T")[0]))
    except Exception as e:
        log(f"Cannot parse creation date: {e}", "error"); return

    now_dt   = datetime.now()
    age_days = (now_dt - c_dt).days
    current  = info.get("streak", 0)
    target   = age_days
    to_farm  = max(0, target - current)

    print()
    print(box([
        f"  {'Created':<16}  {bold(c_dt.strftime('%Y-%m-%d'))}",
        f"  {'Account age':<16}  {bold(str(age_days))} days",
        f"  {'Current streak':<16}  {yellow(str(current))} days",
        f"  {'Safe target':<16}  {green(str(target))} days",
        f"  {'To farm':<16}  {bold(str(to_farm))} days",
    ], title="Streak Farm — Safe Mode", color="32"))
    print()

    if current >= target:
        log(f"Already at safe maximum ({current}/{target}).", "success"); return
    if not ask_confirm(f"  Farm {to_farm} streak days ({current} -> {target})?"):
        log("Cancelled.", "info"); return

    S.running = True; S.t0 = time.time()
    farm_ts   = int(c_dt.timestamp()); end_ts = int(now_dt.timestamp())
    farmed = tick = 0; cur = current
    print()
    while S.running and farm_ts <= end_ts and farmed < to_farm:
        tick += 1
        if _farm_session(jwt, sub, info, farm_ts, farm_ts + 60):
            farm_ts += 86400; farmed += 1; S.streaks += 1; S.calls += 1; cur += 1
            pct    = farmed / to_farm
            filled = int(30 * pct)
            bar    = green("█" * filled) + dim("░" * (30 - filled))
            print(f"\r  {_spin(tick)}  [{bar}]  {bold(f'{farmed}/{to_farm}')}   "
                  f"streak={bold(str(cur))}   {dim(S.elapsed())}     ",
                  end="", flush=True)
        else:
            S.errors += 1; time.sleep(1); continue
        time.sleep(delay_ms / 1000)
    print(); S.running = False; _summary("Streak (Safe)", S.streaks, "days")

def run_streak_normal(jwt, sub, info, delay_ms):
    print(); log("WARNING — Normal streak mode has elevated ban risk.", "warning")
    if not ask_confirm("  Proceed?", default=False):
        log("Cancelled.", "info"); return
    sd  = info.get("streakData", {})
    cs  = (sd.get("currentStreak") or {})
    raw = cs.get("startDate", datetime.now().isoformat())
    farm_ts = int(datetime.fromisoformat(str(raw).split("T")[0]).timestamp()) - 86400
    S.running = True; S.t0 = time.time(); tick = 0; cur = info.get("streak", 0)
    print()
    while S.running:
        tick += 1
        if _farm_session(jwt, sub, info, farm_ts, farm_ts + 60):
            farm_ts -= 86400; S.streaks += 1; S.calls += 1; cur += 1
            print(f"\r  {_spin(tick)}  streak={bold(str(cur))}   "
                  f"farmed={bold(str(S.streaks))}   {dim(S.elapsed())}     ",
                  end="", flush=True)
        else:
            S.errors += 1
        time.sleep(delay_ms / 1000)
    print(); S.running = False; _summary("Streak (Normal)", S.streaks, "days")

def run_mixed(jwt, sub, info, delay_ms):
    S.running = True; S.t0 = time.time()
    skill = extract_skill_id(info.get("currentCourse"))
    stories = True; c429 = tick = 0
    print(); log("Mixed Farm  |  XP + Gems alternating", "farm"); print()
    while S.running:
        tick += 1
        if stories:
            st = _farm_stories(jwt, sub, info)
            if st == 200: S.xp += 499
            elif st == 429:
                c429 += 1
                if c429 >= 2: stories = False
            else: stories = False
        elif skill:
            ok, earned = _farm_unit(jwt, sub, info, skill)
            if ok: S.xp += earned
        ok, earned = _farm_gem(jwt, sub, info)
        if ok: S.gems += earned
        S.calls += 1
        print(f"\r  {_spin(tick)}  "
              f"XP={green(f'{S.xp:,}')} ({cyan(f'{S.rate(S.xp):,.0f}/hr')})   "
              f"gems={blue(f'{S.gems:,}')} ({cyan(f'{S.rate(S.gems):,.0f}/hr')})   "
              f"{dim(S.elapsed())}     ",
              end="", flush=True)
        time.sleep(delay_ms / 1000)
    print(); S.running = False; _summary("Mixed (XP+Gems)", S.xp, f"XP  /  {S.gems} gems")

# ── Practice Farm (Playwright) ─────────────────────────────────────────────────
def _has_playwright() -> bool:
    import importlib.util
    return importlib.util.find_spec("playwright") is not None

def _chromium_installed() -> bool:
    """Return True only if the Chromium binary actually exists on disk."""
    try:
        from playwright.sync_api import sync_playwright
        import os
        with sync_playwright() as pw:
            return os.path.exists(pw.chromium.executable_path)
    except Exception:
        return False

def _install_playwright():
    """Install the playwright package and download the Chromium browser."""
    log("Installing playwright package...", "info")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--quiet", "playwright"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    log("Downloading Chromium (this may take a few minutes)...", "info")
    ret = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"]).returncode
    if ret != 0:
        raise RuntimeError("playwright install chromium failed (exit code {ret})")
    log("Chromium installed.", "success")

def _ensure_playwright() -> bool:
    """
    Guarantee both the package AND the browser binary are ready.
    Returns True if ready to use, False if user declined or install failed.
    """
    if not _has_playwright():
        log("playwright package is not installed.", "warning")
        if not ask_confirm("  Install playwright now? (~150 MB, one-time setup)", default=True):
            return False
        try:
            _install_playwright()
        except Exception as e:
            log(f"Install failed: {e}", "error")
            return False

    # Package is present — now check the binary
    if not _chromium_installed():
        log("playwright is installed but Chromium browser binary is missing.", "warning")
        log("This happens after a fresh pip install or a playwright update.", "info")
        if not ask_confirm("  Download Chromium now? (~150 MB, one-time)", default=True):
            return False
        log("Running: playwright install chromium...", "info")
        ret = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"]).returncode
        if ret != 0:
            log("Browser download failed. Run manually:  playwright install chromium", "error")
            return False
        log("Chromium downloaded successfully.", "success")

    return True

def run_practice(jwt: str, headless: bool = True, loops: int = 10):
    print()
    if not _ensure_playwright():
        return

    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    print()
    log(f"Practice Farm  |  loops={loops}  headless={headless}", "farm")
    log("Launching browser...", "info")

    S.running = True; S.t0 = time.time()
    completed = tick = 0

    _SEL = {
        "word_bank":  "[data-test='challenge-tap-token-text']",
        "radio":      "[data-test='challenge-choice']",
        "input":      "textarea[data-test='challenge-translate-input']",
        "continue":   "[data-test='player-next']",
        "done":       "[data-test='player-done']",
        "skip_btn":   "[data-test='player-skip']",
    }

    def _answer(page):
        tokens = page.locator(_SEL["word_bank"]).all()
        if tokens:
            for t in tokens[:7]:
                try: t.click(timeout=700)
                except: pass
            return
        try:
            page.locator(_SEL["radio"]).first.click(timeout=1200)
            return
        except: pass
        try:
            page.locator(_SEL["input"]).first.fill("a", timeout=800)
        except: pass

    def _click(page, sel, t=2000) -> bool:
        try: page.locator(sel).first.click(timeout=t); return True
        except: return False

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless,
                                     args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        ctx  = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=_ua(),
            locale="en-US",
        )
        ctx.add_cookies([{"name": "jwt_token", "value": jwt,
                          "domain": ".duolingo.com", "path": "/",
                          "secure": True, "httpOnly": False}])
        page = ctx.new_page()
        page.goto("https://www.duolingo.com/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2500)

        for loop in range(loops):
            if not S.running: break
            tick += 1
            try:
                page.goto("https://www.duolingo.com/practice",
                          wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(1800)

                for _ in range(30):
                    if not S.running: break
                    page.wait_for_timeout(500)
                    if page.locator(_SEL["done"]).count() > 0:
                        _click(page, _SEL["done"]); page.wait_for_timeout(1500); break
                    _answer(page)
                    page.wait_for_timeout(350)
                    _click(page, _SEL["continue"], 1500)

                completed += 1; S.calls += 1
                print(f"\r  {_spin(tick)}  "
                      f"Practice: {bold(f'{completed}/{loops}')}   "
                      f"errors={yellow(str(S.errors))}   "
                      f"{dim(S.elapsed())}     ",
                      end="", flush=True)

            except PWTimeout:
                S.errors += 1; log(f"\n  Timeout loop {loop+1}", "warning")
            except Exception as e:
                S.errors += 1; log(f"\n  Error loop {loop+1}: {e}", "error"); break

        browser.close()

    print(); S.running = False; _summary("Practice Farm", completed, "sessions")

# ── Account helpers ────────────────────────────────────────────────────────────
def _acc_label(acc: dict, i: int) -> str:
    info = acc.get("info", {})
    name = info.get("username", acc.get("sub", "?"))
    tag  = "  [EXPIRED]" if jwt_expired(acc.get("jwt", "")) else ""
    return f"{i+1}.  {name}{tag}   streak={info.get('streak',0)}  xp={info.get('totalXp',0)}"

def select_account() -> Optional[dict]:
    accs = load_accounts()
    if not accs:
        log("No accounts — add one first.", "warning"); return None
    if len(accs) == 1: return accs[0]
    choices = [_acc_label(a, i) for i, a in enumerate(accs)] + ["Cancel"]
    ans = ask_select("  Select account", choices)
    if not ans or ans == "Cancel": return None
    return accs[int(ans.split(".")[0]) - 1]

def refresh_account(acc: dict) -> dict:
    try:
        info = get_user_info(acc["jwt"], acc["sub"])
        acc["info"] = info
        accs = load_accounts()
        for a in accs:
            if a["sub"] == acc["sub"]: a["info"] = info
        save_accounts(accs)
        return info
    except Exception as e:
        log(f"Refresh failed: {e}", "error")
        return acc.get("info", {})

# ── Commands ───────────────────────────────────────────────────────────────────
def cmd_add():
    cls()
    print(box([
        "  Paste your Duolingo JWT token.",
        "  From browser DevTools console:",
        "",
        f"  {dim('document.cookie.match(/jwt_token=([^;]+)/)[1]')}",
        "",
        "  Or via Tampermonkey/Violentmonkey console on duolingo.com.",
    ], title="Add Account", color="34"))
    print()
    jwt = ask_password("  JWT Token")
    if not jwt: return
    jwt = jwt.strip().strip("'\"")

    if jwt_expired(jwt):
        log("This token is already expired.", "error"); return
    try:
        sub = jwt_sub(jwt)
    except ValueError as e:
        log(str(e), "error"); return
    if not sub: log("Cannot extract user ID.", "error"); return

    log("Fetching profile...", "info")
    try:
        info = get_user_info(jwt, sub)
    except Exception as e:
        log(str(e), "error"); return

    accs = load_accounts()
    for a in accs:
        if a.get("sub") == str(sub):
            a["jwt"] = jwt; a["info"] = info; save_accounts(accs)
            log(f"Updated: {bold(info.get('username','?'))}", "success")
            input(f"\n  {dim('Enter to continue...')}"); return

    accs.append({"sub": str(sub), "jwt": jwt, "info": info, "added": datetime.now().isoformat()})
    save_accounts(accs)
    print()
    log(f"Added: {bold(green(info.get('username','?')))}   "
        f"streak={info.get('streak',0)}  xp={info.get('totalXp',0)}  "
        f"gems={info.get('gems',0)}", "success")
    log(f"Token expires: {jwt_expires_at(jwt)}", "info")
    input(f"\n  {dim('Enter to continue...')}")

def cmd_list():
    accs = load_accounts()
    if not accs: log("No accounts.", "warning"); return
    print()
    for i, a in enumerate(accs, 1):
        info = a.get("info", {}); exp = jwt_expired(a.get("jwt", ""))
        st = red("EXPIRED") if exp else green("active")
        print(f"  {bold(str(i))}.  {bold(info.get('username','?'))}  [{st}]")
        print(f"      ID       {dim(a.get('sub','?'))}")
        print(f"      Streak   {yellow(str(info.get('streak',0)))} days")
        print(f"      XP       {blue(str(info.get('totalXp',0)))}")
        print(f"      Gems     {cyan(str(info.get('gems',0)))}")
        print(f"      Expires  {dim(jwt_expires_at(a.get('jwt','')))}")
        print()

def cmd_remove():
    accs = load_accounts()
    if not accs: log("No accounts.", "warning"); return
    choices = [_acc_label(a, i) for i, a in enumerate(accs)] + ["Cancel"]
    ans = ask_select("  Remove", choices)
    if not ans or ans == "Cancel": return
    idx = int(ans.split(".")[0]) - 1
    removed = accs.pop(idx); save_accounts(accs)
    log(f"Removed: {removed.get('info',{}).get('username','?')}", "success")

def cmd_view(acc: dict):
    cls(); info = acc.get("info", {}); jwt = acc.get("jwt", ""); exp = jwt_expired(jwt)
    print(box([
        f"  {'Username':<16}  {bold(info.get('username','?'))}",
        f"  {'User ID':<16}  {dim(acc.get('sub','?'))}",
        "",
        f"  {'Streak':<16}  {yellow(str(info.get('streak',0)))} days",
        f"  {'Total XP':<16}  {blue(str(info.get('totalXp',0)))}",
        f"  {'Gems':<16}  {cyan(str(info.get('gems',0)))}",
        f"  {'Language':<16}  {info.get('fromLanguage','?')} -> {info.get('learningLanguage','?')}",
        "",
        f"  {'Token status':<16}  {red('EXPIRED') if exp else green('valid')}",
        f"  {'Expires':<16}  {dim(jwt_expires_at(jwt))}",
        f"  {'Created':<16}  {dim(str(info.get('creationDate','?'))[:10])}",
    ], title=f"Account — {info.get('username','?')}", color="34", width=64))
    print(); input(f"  {dim('Enter to continue...')}")

def cmd_streak_status():
    cls(); accs = load_accounts()
    if not accs: log("No accounts.", "warning"); input(f"\n  {dim('Enter...')}"); return
    print(box(["  Fetching streak status for all accounts..."], title="Streak Status", color="32"))
    print()
    for a in accs:
        info = a.get("info", {}); username = info.get("username", a.get("sub", "?"))
        if jwt_expired(a.get("jwt", "")): log(f"{username:<22}  JWT expired", "error"); continue
        try: info = get_user_info(a["jwt"], a["sub"])
        except Exception as e: log(f"{username:<22}  {e}", "error"); continue
        done   = streak_done_today(info.get("streakData", {}))
        status = green("done today") if done else yellow("not completed today")
        log(f"{bold(username):<26}  streak={yellow(str(info.get('streak',0)))}   {status}", "stat")
    print(); input(f"  {dim('Enter to continue...')}")

def cmd_settings():
    while True:
        cls(); pw = _has_playwright()
        print(box([
            f"  {'Accounts file':<24}  {dim(_ACCS)}",
            f"  {'playwright':<24}  {green('installed') if pw else yellow('not installed')}",
            f"  {'Python':<24}  {dim(sys.version.split()[0])}",
            f"  {'Version':<24}  {dim(VERSION)}",
        ], title="Settings", color="34"))
        print()
        ans = ask_select("  Settings", [
            "Clear all accounts",
            "Install / reinstall playwright",
            "Show accounts file path",
            "Back",
        ])
        if not ans or ans == "Back": return
        if ans == "Clear all accounts":
            if ask_confirm("  Delete ALL saved accounts? This cannot be undone.", default=False):
                save_accounts([]); log("All accounts cleared.", "success")
        elif ans == "Install / reinstall playwright":
            try:    _install_playwright()
            except Exception as e: log(f"Failed: {e}", "error")
        elif ans == "Show accounts file path":
            log(f"Path: {_ACCS}", "info")
        input(f"  {dim('Enter...')}")

# ── Farm menu ──────────────────────────────────────────────────────────────────
def _delay() -> int:
    v = ask_text("  Request delay (ms)", default="1500")
    try:    return max(200, int(v or "1500"))
    except: return 1500

def cmd_farm():
    cls(); acc = select_account()
    if not acc: return
    if jwt_expired(acc.get("jwt", "")):
        log("JWT expired — re-add this account.", "error")
        input(f"\n  {dim('Enter...')}"); return

    log(f"Refreshing: {bold(acc.get('info',{}).get('username','?'))}...", "info")
    info  = refresh_account(acc)
    skill = extract_skill_id(info.get("currentCourse"))

    while True:
        cls()
        print(box([
            f"  {'Account':<14}  {bold(green(info.get('username','?')))}",
            f"  {'Streak':<14}  {yellow(str(info.get('streak',0)))} days",
            f"  {'XP':<14}  {blue(str(info.get('totalXp',0)))}",
            f"  {'Gems':<14}  {cyan(str(info.get('gems',0)))}",
            f"  {'Skill ID':<14}  {green(skill) if skill else red('none')}",
        ], title="Farm", color="33"))
        print()

        ans = ask_select("  Farm mode", [
            "XP Farm            Stories 499 XP -> UNIT_TEST 110 XP fallback",
            "Gem Farm           ~30 gems per call",
            "Streak Safe        capped to account age",
            "Streak Normal      no cap, higher risk",
            "Mixed              XP + Gems alternating",
            "Practice Farm      browser automation (playwright)",
            "Back",
        ])
        if not ans or ans == "Back": return

        S.reset()

        def _stop(sig, frame):
            S.running = False; print(); log("Stopping...", "warning")
        signal.signal(signal.SIGINT, _stop)

        try:
            if ans.startswith("XP"):
                run_xp(acc["jwt"], acc["sub"], info, _delay())
            elif ans.startswith("Gem"):
                run_gems(acc["jwt"], acc["sub"], info, _delay())
            elif ans.startswith("Streak Safe"):
                run_streak_safe(acc["jwt"], acc["sub"], info, _delay())
            elif ans.startswith("Streak Normal"):
                run_streak_normal(acc["jwt"], acc["sub"], info, _delay())
            elif ans.startswith("Mixed"):
                run_mixed(acc["jwt"], acc["sub"], info, _delay())
            elif ans.startswith("Practice"):
                n = ask_text("  Number of practice sessions", default="20")
                loops = max(1, int(n or "20"))
                headless = ask_confirm("  Run headless (no visible browser)?", default=True)
                run_practice(acc["jwt"], headless=headless, loops=loops)
        except KeyboardInterrupt:
            S.running = False; print(); log("Farm stopped.", "warning")

        signal.signal(signal.SIGINT, signal.SIG_DFL)
        input(f"\n  {dim('Enter to continue...')}")

def cmd_accounts():
    while True:
        cls(); accs = load_accounts()
        print(box([f"  {'Saved accounts':<20}  {bold(str(len(accs)))}"],
                  title="Account Manager", color="34"))
        print()
        ans = ask_select("  Account Manager", [
            "Add account", "List accounts", "Remove account", "View account info", "Back",
        ])
        if not ans or ans == "Back": return
        if ans == "Add account":         cmd_add()
        elif ans == "List accounts":     cmd_list(); input(f"\n  {dim('Enter...')}")
        elif ans == "Remove account":    cmd_remove(); input(f"\n  {dim('Enter...')}")
        elif ans == "View account info":
            a = select_account()
            if a: cmd_view(a)

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    while True:
        cls(); accs = load_accounts()
        n, nx = len(accs), sum(1 for a in accs if jwt_expired(a.get("jwt", "")))

        print(center(magenta(BANNER)))
        print(center(f"{bold('PyLingo')}  {dim('v'+VERSION)}"))
        print()
        if n:
            status = red(f"{nx} expired") if nx else green("all active")
            print(center(f"{bold(str(n))} account(s)  —  {status}"))
        else:
            print(center(dim("No accounts — use Account Manager to add one")))
        print(); print(hr()); print()

        ans = ask_select("  Main Menu", [
            "Farm",
            "Account Manager",
            "Streak Status",
            "Settings",
            "Exit",
        ])
        if not ans or ans == "Exit":
            cls(); print(center(f"\n  {bold(green('Goodbye.'))}  {dim('PyLingo v'+VERSION)}\n"))
            sys.exit(0)
        elif ans == "Farm":            cmd_farm()
        elif ans == "Account Manager": cmd_accounts()
        elif ans == "Streak Status":   cmd_streak_status()
        elif ans == "Settings":        cmd_settings()

if __name__ == "__main__":
    try:    main()
    except KeyboardInterrupt:
        print(); log("Interrupted.", "info"); sys.exit(0)
