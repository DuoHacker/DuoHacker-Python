#!/usr/bin/env python3
import os, sys, json, time, base64, threading, http.client, urllib.parse
import signal, math, random, re
from datetime import datetime, timezone

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich import box as rbox

_con = Console(highlight=False)
_print_raw = print
print = _con.print

VERSION = "1.0.0"

BANNER_ART = r"""
  ██████╗ ██╗   ██╗██╗     ██╗███╗   ██╗  ██████╗  ██████╗
  ██╔══██╗╚██╗ ██╔╝██║     ██║████╗  ██║ ██╔════╝ ██╔═══██╗
  ██████╔╝ ╚████╔╝ ██║     ██║██╔██╗ ██║ ██║  ███╗██║   ██║
  ██╔═══╝   ╚██╔╝  ██║     ██║██║╚██╗██║ ██║   ██║██║   ██║
  ██║        ██║   ███████╗██║██║ ╚████║ ╚██████╔╝╚██████╔╝
  ╚═╝        ╚═╝   ╚══════╝╚═╝╚═╝  ╚═══╝ ╚═════╝  ╚═════╝
"""

def cls():
    os.system("cls" if os.name == "nt" else "clear")

def _plain(text):
    return re.sub(r'\033\[[0-9;]*m', '', text)

def term_width():
    try:    return os.get_terminal_size().columns
    except: return 100

_log_lock = threading.Lock()

def log(msg, level="info"):
    ts = datetime.now().strftime("%H:%M:%S")
    cfg = {
        "info":    ("dim",          "·"),
        "success": ("bright_green", "✓"),
        "warning": ("yellow",       "!"),
        "error":   ("bright_red",   "✗"),
        "farm":    ("cyan",         "◆"),
        "stat":    ("steel_blue1",  "▸"),
    }
    color, icon = cfg.get(level, ("white", "·"))
    with _log_lock:
        print(f"  [dim]{ts}[/]  [{color}]{icon}[/]  {msg}")

def log_stat(label, value, unit=""):
    u = f" [dim]{unit}[/]" if unit else ""
    print(f"  [dim]│[/] [dim]{label}:[/]  [bold]{value}[/]{u}")

def farm_progress(label, color, endless=False):
    cols = [
        SpinnerColumn(spinner_name="dots", style=f"bold {color}"),
        TextColumn(f"[bold {color}]{label}[/]"),
        BarColumn(bar_width=32, style=color, complete_style=f"bold {color}"),
        TextColumn("[bold white]{task.completed:,}[/]" + ("" if endless else f"[dim] / {{task.total:,}}[/]")),
        TimeElapsedColumn(),
    ]
    return Progress(*cols, console=_con, transient=False)

def title_bar():
    ts = datetime.now().strftime("%H:%M")
    print(f"\n  [bold bright_white]Py[/][bold cyan]Lingo[/]  [dim]{VERSION}[/]  [dim]·[/]  [dim]{ts}[/]")

def arrow_menu(title, options, subtitle=""):
    items = []
    for o in options:
        if isinstance(o, (list, tuple)) and len(o) >= 2:
            items.append((str(o[0]), str(o[1])))
        else:
            items.append((str(o), ""))

    cls()
    title_bar()
    print()

    if subtitle:
        print(f"  [dim]{subtitle}[/]")
        print()

    KEY_COLORS = [
        "bright_yellow", "bright_cyan", "sandy_brown",
        "medium_purple1", "bright_green", "pink1",
        "steel_blue1",    "bright_white",
    ]

    for i, (label, desc) in enumerate(items):
        key_color = KEY_COLORS[i % len(KEY_COLORS)]
        num = str(i + 1)
        is_last = (i == len(items) - 1)
        if is_last:
            line = f"  [dim]{num}. {label}[/]"
        else:
            desc_part = f"  [dim]{desc}[/]" if desc else ""
            line = f"  [{key_color}]{num}.[/] [bold white]{label}[/]{desc_part}"
        print(line)
        if i == len(items) - 2:
            print()

    print()
    try:
        v = _con.input("  [dim]>[/] ").strip()
        if v in ('0', 'q', 'Q', ''):
            return -1
        if v.isdigit():
            idx = int(v) - 1
            if 0 <= idx < len(items):
                return idx
        return -1
    except (ValueError, KeyboardInterrupt):
        return -1

def box(lines, title="", color="cyan", width=None):
    from rich.panel import Panel
    from rich.text import Text
    body = "\n".join(lines)
    _con.print(Panel(body, title=f"[bold {color}]{title}[/]" if title else None, border_style=color, padding=(0, 1)))

def hr(char="─", color="dim"):
    print(f"[{color}]{char * min(term_width(), 72)}[/]")

def center(text, fill=" "):
    return text

# ─── ANSI compat shims (for legacy call sites) ───────────────────
def _r(t, code): return f"\033[{code}m{t}\033[0m"
def green(t):    return f"[bright_green]{t}[/]"
def yellow(t):   return f"[yellow]{t}[/]"
def red(t):      return f"[bright_red]{t}[/]"
def blue(t):     return f"[steel_blue1]{t}[/]"
def cyan(t):     return f"[cyan]{t}[/]"
def magenta(t):  return f"[medium_purple1]{t}[/]"
def bold(t):     return f"[bold]{t}[/]"
def dim(t):      return f"[dim]{t}[/]"
def white(t):    return f"[white]{t}[/]"
def _green_bold(t): return f"[bold bright_green]{t}[/]"
def _cyan_bold(t):  return f"[bold cyan]{t}[/]"
def _plain(t):
    import re
    return re.sub(r"\033\[[0-9;]*m", "", re.sub(r"\[/?[a-z_ 0-9]*\]", "", str(t)))
def _rpad(text, width):
    pad = width - len(_plain(str(text)))
    return str(text) + " " * max(0, pad)

# ─── HTTP helper (stdlib only) ────────────────────────────────────
USER_AGENTS = [
    "Duolingo/5.158.4 (iPhone; iOS 17.4; Scale/3.00)",
    "Duolingo/5.157.0 (Android; Build/12; Model/Pixel 7)",
    "Duolingo/5.156.2 (iPhone; iOS 16.7; Scale/2.00)",
    "Duolingo/5.158.1 (Android; Build/13; Model/Samsung Galaxy S23)",
]

def random_ua():
    return random.choice(USER_AGENTS)

def make_headers(jwt, sub=None):
    return {
        "Content-Type":"application/json",
        "Accept":"application/json",
        "Authorization": f"Bearer {jwt}",
        "User-Agent": random_ua(),
        "x-amzn-trace-id": f"User={sub}" if sub else"User=0",
        "Cookie": f"jwt_token={jwt}",
        "Origin":"https://www.duolingo.com",
        "Referer":"https://www.duolingo.com/",
        "Host":"www.duolingo.com",
        "Accept-Encoding":"identity",
    }

def http_request(method, host, path, headers=None, body=None, use_ssl=True, timeout=30):
    import gzip as _gzip, zlib as _zlib
    try:
        conn_cls = http.client.HTTPSConnection if use_ssl else http.client.HTTPConnection
        conn = conn_cls(host, timeout=timeout)
        body_bytes = json.dumps(body).encode() if body else None
        conn.request(method, path, body=body_bytes, headers=headers or {})
        resp = conn.getresponse()
        raw = resp.read()
        enc = resp.getheader("Content-Encoding", "")
        try:
            if "gzip" in enc:
                raw = _gzip.decompress(raw)
            elif "deflate" in enc:
                raw = _zlib.decompress(raw)
        except Exception:
            pass
        try:
            text = raw.decode("utf-8")
        except Exception:
            text = raw.decode("latin-1")
        return resp.status, text
    except Exception as e:
        return 0, str(e)
    finally:
        try: conn.close()
        except: pass

def duo_get(path, jwt, sub=None):
    status, text = http_request("GET","www.duolingo.com", path, make_headers(jwt, sub))
    return status, _try_json(text)

def duo_post(path, jwt, sub=None, body=None):
    status, text = http_request("POST","www.duolingo.com", path, make_headers(jwt, sub), body)
    return status, _try_json(text)

def duo_put(path, jwt, sub=None, body=None):
    status, text = http_request("PUT","www.duolingo.com", path, make_headers(jwt, sub), body)
    return status, _try_json(text)

def duo_patch(path, jwt, sub=None, body=None):
    status, text = http_request("PATCH","www.duolingo.com", path, make_headers(jwt, sub), body)
    return status, _try_json(text)

def _try_json(text):
    try: return json.loads(text)
    except: return {}

# ─── JWT helpers ──────────────────────────────────────────────────
def decode_jwt(token):
    try:
        parts = token.split(".")
        if len(parts) < 2:
            raise ValueError("Invalid JWT")
        payload = parts[1]
        # Fix base64 padding
        payload +="=" * (4 - len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception as e:
        raise ValueError(f"Cannot decode JWT: {e}")

def jwt_sub(token):
    v = decode_jwt(token).get("sub")
    return str(v) if v is not None else None

def jwt_expired(token):
    try:
        data = decode_jwt(token)
        exp = data.get("exp")
        if not exp: return False
        return time.time() > exp
    except:
        return True

def jwt_expires_at(token):
    try:
        exp = decode_jwt(token).get("exp")
        if exp:
            return datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M")
        return"unknown"
    except:
        return"unknown"

# ─── Config ───────────────────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

_DEFAULT_CONFIG = {
    "delay_ms":    1500,
    "debug":       False,
    "gem_batch":   3,
}

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                data = json.load(f)
                return {**_DEFAULT_CONFIG, **data}
        except Exception:
            pass
    return dict(_DEFAULT_CONFIG)

def save_config(cfg: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

CFG = load_config()

# ─── Account store (accounts.json) ───────────────────────────────
ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__),"accounts.json")

def load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE) as f:
                return json.load(f)
        except:
            pass
    return []

def save_accounts(accounts):
    with open(ACCOUNTS_FILE,"w") as f:
        json.dump(accounts, f, indent=2)

# ─── Duolingo API ─────────────────────────────────────────────────
FIELDS = (
    "id,username,fromLanguage,learningLanguage,streak,totalXp,level,"
    "numFollowers,numFollowing,gems,creationDate,streakData,picture,"
    "hasPlus,trackingProperties,"
    "currentCourse{pathSectioned{units{levels{pathLevelMetadata{skillId}}}}}"
)

def get_user_info(jwt, sub):
    if jwt_expired(jwt):
        raise ValueError("JWT token has expired — please re-link your account")
    path = f"/2017-06-30/users/{sub}?fields={urllib.parse.quote(FIELDS)}"
    status, data = duo_get(path, jwt, sub)
    if status == 403:
        raise PermissionError("JWT rejected by Duolingo (403) — token may be expired or revoked")
    if status != 200:
        raise ConnectionError(f"Failed to fetch user info (HTTP {status})")
    if not data or not isinstance(data, dict):
        raise ConnectionError("Duolingo returned empty response")
    tp = data.get("trackingProperties") or {}
    if tp.get("creation_date_new"):
        data["creationDate"] = tp["creation_date_new"]
    elif isinstance(data.get("creationDate"), (int, float)):
        data["creationDate"] = datetime.fromtimestamp(data["creationDate"] / 1000).isoformat()
    if not data.get("username"):
        data["username"] = (
            tp.get("username")
            or tp.get("user_id")
            or str(data.get("id") or sub)
        )
    return data

def extract_skill_id(current_course):
    try:
        for section in (current_course or {}).get("pathSectioned", []):
            for unit in section.get("units", []):
                for level in unit.get("levels", []):
                    sk = (level.get("pathLevelMetadata") or {}).get("skillId")
                    if sk: return sk
                    sk = (level.get("pathLevelClientData") or {}).get("skillId")
                    if sk: return sk
    except:
        pass
    return None

def streak_done_today(streak_data):
    try:
        upd = streak_data.get("updatedAt") or streak_data.get("currentStreak", {}).get("endDate")
        if not upd: return False
        if isinstance(upd, (int, float)):
            upd_dt = datetime.fromtimestamp(upd/1000, tz=timezone.utc)
        else:
            upd_dt = datetime.fromisoformat(str(upd).replace("Z","+00:00"))
        now = datetime.now(tz=timezone.utc)
        return upd_dt.date() >= now.date()
    except:
        return False

# ─── Farming functions ────────────────────────────────────────────

def farm_xp_once_stories(jwt, sub, user_info):
    """Stories API — up to 499 XP per call."""
    now = int(time.time())
    dur = random.randint(300, 420)
    body = {
        "awardXp": True,
        "completedBonusChallenge": True,
        "fromLanguage": user_info.get("fromLanguage","en"),
        "learningLanguage": user_info.get("learningLanguage","fr"),
        "hasXpBoost": False,
        "illustrationFormat":"svg",
        "isFeaturedStoryInPracticeHub": True,
        "isLegendaryMode": True,
        "isV2Redo": False,
        "isV2Story": False,
        "masterVersion": True,
        "maxScore": 0,
        "score": 0,
        "happyHourBonusXp": 469,
        "startTime": now,
        "endTime": now + dur,
    }
    headers = make_headers(jwt, sub)
    headers["Host"] ="stories.duolingo.com"
    headers["Origin"] ="https://stories.duolingo.com"
    status, _ = http_request(
        "POST","stories.duolingo.com",
        "/api2/stories/fr-en-le-passeport/complete",
        headers, body
    )
    return status

def farm_xp_once_unit(jwt, sub, user_info, skill_id):
    """UNIT_TEST session — ~110 XP per call."""
    # Step 1: Create session
    body = {
        "challengeTypes": [],
        "fromLanguage": user_info.get("fromLanguage","en"),
        "learningLanguage": user_info.get("learningLanguage","fr"),
        "type":"UNIT_TEST",
        "skillIds": [skill_id],
    }
    status, session = duo_post("/2017-06-30/sessions", jwt, sub, body)
    if status != 200 or not session.get("id"):
        return False, 0

    start = int(time.time())
    update_body = {
        "id": session["id"],
        "metadata": session.get("metadata", {}),
        "type":"UNIT_TEST",
        "fromLanguage": user_info.get("fromLanguage","en"),
        "learningLanguage": user_info.get("learningLanguage","fr"),
        "challenges": [],
        "adaptiveChallenges": [],
        "sessionExperimentRecord": [],
        "experiments_with_treatment_contexts": [],
        "adaptiveInterleavedChallenges": [],
        "sessionStartExperiments": [],
        "trackingProperties": [],
        "ttsAnnotations": [],
        "heartsLeft": 0,
        "startTime": start,
        "enableBonusPoints": True,
        "endTime": start + 60,
        "failed": False,
        "maxInLessonStreak": 9,
        "shouldLearnThings": True,
        "hasBoost": True,
        "happyHourBonusXp": 10,
        "pathLevelSpecifics": {"unitIndex": 0},
    }
    status2, data2 = duo_put(f"/2017-06-30/sessions/{session['id']}", jwt, sub, update_body)
    if status2 == 200:
        earned = data2.get("awardedXp") or data2.get("xpGain") or 110
        return True, earned
    return False, 0

def farm_gem_once(jwt, sub, user_info):
    """Claim gem reward."""
    reward_id ="SKILL_COMPLETION_BALANCED-dd2495f4_d44e_3fc3_8ac8_94e2191506f0-2-GEMS"
    path = f"/2023-05-23/users/{sub}/rewards/{reward_id}"
    body = {
        "consumed": True,
        "learningLanguage": user_info.get("learningLanguage","fr"),
        "fromLanguage": user_info.get("fromLanguage","en"),
    }
    status, _ = duo_patch(path, jwt, sub, body)
    return status == 200, 30 if status == 200 else 0

# ─── Progress bar ─────────────────────────────────────────────────
def progress_bar(current, total, width=30, label=""):
    if total <= 0: total = 1
    pct = min(current / total, 1.0)
    filled = int(width * pct)
    bar = green("█" * filled) + dim("░" * (width - filled))
    pct_str = f"{pct*100:.1f}%"
    return f" [{bar}] {bold(pct_str)} {dim(label)}"

def spinner_char(tick):
    return ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"][tick % 10]

# ─── Farm session state ───────────────────────────────────────────
class FarmState:
    def __init__(self):
        self.running = False
        self.xp_earned = 0
        self.gem_earned= 0
        self.streak_farmed = 0
        self.errors = 0
        self.start_time= None
        self.calls = 0

    def reset(self):
        self.running = False
        self.xp_earned = 0
        self.gem_earned = 0
        self.streak_farmed = 0
        self.errors = 0
        self.start_time = None
        self.calls = 0

    def elapsed(self):
        if not self.start_time: return"00:00"
        secs = int(time.time() - self.start_time)
        return f"{secs//60:02d}:{secs%60:02d}"

state = FarmState()

# ─── XP Farm ─────────────────────────────────────────────────────
def farm_xp(jwt, sub, user_info, delay_ms, use_stories=True):
    """Smart XP loop: Stories 499 first, fallback to UNIT_TEST 110."""
    state.running = True
    state.start_time = time.time()
    skill_id = extract_skill_id(user_info.get("currentCourse"))
    consecutive_429 = 0
    fallback_errors = 0
    MAX_429 = 2
    MAX_ERR = 5
    tick = 0

    print()
    log(f"Starting XP farm — [bold]Stories 499 XP[/bold] mode (auto-fallback to 110 XP)","farm")
    log(f"Delay: {delay_ms}ms | Skill ID: {green(skill_id) if skill_id else red('none')}","info")
    print()

    while state.running:
        tick += 1
        if use_stories and consecutive_429 < MAX_429:
            status = farm_xp_once_stories(jwt, sub, user_info)
            if status == 200:
                consecutive_429 = 0; fallback_errors = 0
                state.xp_earned += 499; state.calls += 1
                _xp_tick(499, tick)
            elif status == 429:
                consecutive_429 += 1
                log(f"Stories rate-limited (429) [{consecutive_429}/{MAX_429}]","warning")
                if consecutive_429 >= MAX_429:
                    log("Switching to UNIT_TEST fallback (110 XP)","info")
                time.sleep(delay_ms / 1000 * 2)
                continue
            else:
                log(f"Stories returned {status}, switching to UNIT_TEST","warning")
                use_stories = False
        else:
            if not skill_id:
                log("No skill ID — cannot use UNIT_TEST fallback. Stopping.","error")
                break
            ok, earned = farm_xp_once_unit(jwt, sub, user_info, skill_id)
            if ok:
                fallback_errors = 0
                state.xp_earned += earned; state.calls += 1
                _xp_tick(earned, tick)
            else:
                fallback_errors += 1
                state.errors += 1
                log(f"UNIT_TEST error ({fallback_errors}/{MAX_ERR})","warning")
                if fallback_errors >= MAX_ERR:
                    log("Too many errors — stopping farm.","error")
                    break
                time.sleep(delay_ms / 1000 * 3)
                continue

        time.sleep(delay_ms / 1000)

    state.running = False
    _farm_summary("XP", state.xp_earned,"XP")

def _xp_tick(earned, tick):
    rate = state.xp_earned / max(1, time.time() - state.start_time) * 3600
    print(f"\r {spinner_char(tick)} {green(f'+{earned} XP')} │"
          f"Total: {bold(str(state.xp_earned))} XP │"
          f"Rate: {cyan(f'{rate:.0f} XP/hr')} │"
          f"Time: {dim(state.elapsed())}", end="", flush=True)

# ─── Gem Farm ─────────────────────────────────────────────────────
def farm_gems(jwt, sub, user_info, delay_ms, batch=3):
    state.running = True
    state.start_time = time.time()
    consecutive_errors = 0
    MAX_ERRORS = 5
    tick = 0

    print()
    log(f"Starting Gem farm — batch={bold(str(batch))} | delay={bold(f'{delay_ms}ms')}","farm")
    print()

    while state.running:
        tick += 1
        ok_count = 0
        for _ in range(batch):
            ok, earned = farm_gem_once(jwt, sub, user_info)
            if ok:
                ok_count += 1
                state.gem_earned += earned
            time.sleep(0.15)

        if ok_count > 0:
            consecutive_errors = 0
            state.calls += ok_count
            _gem_tick(ok_count * 30, tick)
        else:
            consecutive_errors += 1
            state.errors += 1
            if consecutive_errors >= MAX_ERRORS:
                log("\nToo many errors — stopping gem farm.","error")
                break
            time.sleep(delay_ms / 1000 * 3)
            continue

        time.sleep(delay_ms / 1000)

    state.running = False
    _farm_summary("Gems", state.gem_earned,"")

def _gem_tick(earned, tick):
    rate = state.gem_earned / max(1, time.time() - state.start_time) * 3600
    print(f"\r {spinner_char(tick)} {cyan(f'+{earned}')} │"
          f"Total: {bold(str(state.gem_earned))} gems │"
          f"Rate: {green(f'{rate:.0f}/hr')} │"
          f"Time: {dim(state.elapsed())}", end="", flush=True)

def _farm_summary(mode, total, unit):
    elapsed = state.elapsed()
    calls = state.calls
    errs = state.errors
    print("\n")
    box([
        f" [bold]Farm complete![/bold]",
        f" Mode : {bold(mode)}",
        f" Total : {green(str(total))} {unit}",
        f" Calls : {blue(str(calls))}",
        f" Errors : {yellow(str(errs))}",
        f" Runtime : {cyan(elapsed)}",
    ], title=" Session Summary", color="bright_green")
    print()

# ─── Streak Farm ─────────────────────────────────────────────────
# Source: farmStreakSafe / farmStreakNormal from DuoHacker userscript
# Uses GLOBAL_PRACTICE sessions with back-dated timestamps

_STREAK_CHALLENGE_TYPES = [
    "assist","characterIntro","characterMatch","characterPuzzle","characterSelect",
    "characterTrace","characterWrite","completeReverseTranslation","definition",
    "dialogue","extendedMatch","extendedListenMatch","form","freeResponse",
    "gapFill","judge","listen","listenComplete","listenMatch","match","name",
    "listenComprehension","listenIsolation","listenSpeak","listenTap",
    "orderTapComplete","partialListen","partialReverseTranslate","patternTapComplete",
    "radioBinary","radioImageSelect","radioListenMatch","radioListenRecognize",
    "radioSelect","readComprehension","reverseAssist","sameDifferent","select",
    "selectPronunciation","selectTranscription","svgPuzzle","syllableTap",
    "syllableListenTap","speak","tapCloze","tapClozeTable","tapComplete",
    "tapCompleteTable","tapDescribe","translate","transliterate",
    "transliterationAssist","typeCloze","typeClozeTable","typeComplete",
    "typeCompleteTable","writeComprehension",
]

def _streak_session_once(jwt, sub, user_info, start_ts, end_ts):
    """POST /2023-05-23/sessions (GLOBAL_PRACTICE) + PUT to complete.
    Mirrors farmSessionOnce from DuoHacker userscript."""
    session_body = {
        "challengeTypes": _STREAK_CHALLENGE_TYPES,
        "fromLanguage": user_info.get("fromLanguage","en"),
        "isFinalLevel": False,
        "isV2": True,
        "juicy": True,
        "learningLanguage": user_info.get("learningLanguage","fr"),
        "smartTipsVersion": 2,
        "type":"GLOBAL_PRACTICE",
    }
    status, session = duo_post("/2023-05-23/sessions", jwt, sub, session_body)
    if status != 200 or not session.get("id"):
        return False

    update_body = {
        **session,
        "heartsLeft": 0,
        "startTime": start_ts,
        "enableBonusPoints": False,
        "endTime": end_ts,
        "failed": False,
        "maxInLessonStreak": 9,
        "shouldLearnThings": True,
    }
    status2, _ = duo_put(f"/2023-05-23/sessions/{session['id']}", jwt, sub, update_body)
    return status2 == 200

def farm_streak_safe(jwt, sub, user_info, delay_ms):
    """Farm streak up to account age limit — safe mode.
    Mirrors farmStreakSafe from DuoHacker userscript."""
    creation = user_info.get("creationDate")
    if not creation:
        log("Cannot determine account creation date.","error")
        return

    try:
        if isinstance(creation, (int, float)):
            creation_dt = datetime.fromtimestamp(creation / 1000)
        else:
            creation_dt = datetime.fromisoformat(str(creation).split("T")[0])
        if (datetime.now() - creation_dt).days > 5500:
            raise ValueError("Suspiciously large account age")
    except Exception as e:
        log(f"Cannot parse creation date: {e}","error")
        return

    now_dt = datetime.now()
    account_age_days= (now_dt - creation_dt).days
    current_streak = user_info.get("streak", 0)
    max_safe = account_age_days

    print()
    log(f"Account created : {green(creation_dt.strftime('%Y-%m-%d'))}","stat")
    log(f"Account age : {green(str(account_age_days))} days","stat")
    log(f"Current streak : {yellow(str(current_streak))} days","stat")
    log(f"Max safe streak : {green(str(max_safe))} days","stat")
    print()

    if current_streak >= max_safe:
        log(f"Already at max safe streak ({current_streak}/{max_safe})!","success")
        return

    to_farm = max_safe - current_streak
    box([
        f" Will farm {bold(green(str(to_farm)))} streak days",
        f" {current_streak} → {max_safe}",
        f" [dim]Ctrl+C to stop anytime[/dim]",
    ], title=" Safe Streak Farm", color="bright_green")
    print()
    if _con.input(f" [yellow]Confirm? (y/N):[/yellow]").strip().lower() !="y":
        log("Cancelled.","info")
        return

    state.running = True
    state.start_time = time.time()
    farm_ts = int(creation_dt.timestamp())
    end_ts = int(now_dt.timestamp())
    farmed = 0
    tick = 0

    print()
    while state.running and farm_ts <= end_ts and farmed < to_farm:
        tick += 1
        ok = _streak_session_once(jwt, sub, user_info, farm_ts, farm_ts + 60)
        if ok:
            farm_ts += 86400
            farmed += 1
            state.streak_farmed += 1
            current_streak += 1
            state.calls += 1
            pct = farmed / to_farm
            bar = green("█" * int(30 * pct)) + dim("░" * (30 - int(30 * pct)))
            print(f"\r {spinner_char(tick)} [{bar}]"
                  f"{bold(f'{farmed}/{to_farm}')} {bold(str(current_streak))} days"
                  f"Time: {dim(state.elapsed())}", end="", flush=True)
        else:
            state.errors += 1
            time.sleep(1)
            continue
        time.sleep(delay_ms / 1000)

    state.running = False
    print()
    _farm_summary("Streak (Safe)", state.streak_farmed," days")

def farm_streak_normal(jwt, sub, user_info, delay_ms):
    """Farm streak backwards from current streak start — normal mode (higher risk).
    Mirrors farmStreakNormal from DuoHacker userscript."""
    print()
    log(f"[bright_red]WARNING:[/bright_red] Normal mode has higher ban risk!","warning")
    if _con.input(f" [yellow]Confirm? (y/N):[/yellow]").strip().lower() !="y":
        log("Cancelled.","info")
        return

    streak_data = user_info.get("streakData", {})
    has_streak = bool(streak_data.get("currentStreak"))
    if has_streak:
        start_date = streak_data["currentStreak"].get("startDate", datetime.now().isoformat())
        start_ts = int(datetime.fromisoformat(str(start_date).split("T")[0]).timestamp())
        farm_ts = start_ts - 86400
    else:
        farm_ts = int(datetime.now().timestamp())

    state.running = True
    state.start_time = time.time()
    tick = 0

    print()
    while state.running:
        tick += 1
        ok = _streak_session_once(jwt, sub, user_info, farm_ts, farm_ts + 60)
        if ok:
            farm_ts -= 86400
            state.streak_farmed += 1
            state.calls += 1
            current = user_info.get("streak", 0) + state.streak_farmed
            print(f"\r {spinner_char(tick)} Streak: {bold(str(current))} │"
                  f"Farmed: {bold(str(state.streak_farmed))} │"
                  f"Time: {dim(state.elapsed())}", end="", flush=True)
        else:
            state.errors += 1
        time.sleep(delay_ms / 1000)

    print()
    _farm_summary("Streak (Normal)", state.streak_farmed," days")

# ─── Mixed Farm ──────────────────────────────────────────────────
def farm_mixed(jwt, sub, user_info, delay_ms):
    """Farm XP + Gems simultaneously in alternating calls."""
    state.running = True
    state.start_time = time.time()
    skill_id = extract_skill_id(user_info.get("currentCourse"))
    tick = 0
    use_stories = True
    consecutive_429 = 0

    print()
    log("Starting MIXED farm — XP + Gems alternating","farm")
    print()

    while state.running:
        tick += 1
        # XP call
        if use_stories:
            status = farm_xp_once_stories(jwt, sub, user_info)
            if status == 200:
                state.xp_earned += 499
            elif status == 429:
                consecutive_429 += 1
                if consecutive_429 >= 2: use_stories = False
            else:
                use_stories = False
        elif skill_id:
            ok, earned = farm_xp_once_unit(jwt, sub, user_info, skill_id)
            if ok: state.xp_earned += earned

        # Gem call
        ok, earned = farm_gem_once(jwt, sub, user_info)
        if ok: state.gem_earned += earned

        state.calls += 1
        xp_rate = state.xp_earned / max(1, time.time()-state.start_time) * 3600
        gem_rate = state.gem_earned / max(1, time.time()-state.start_time) * 3600
        print(f"\r {spinner_char(tick)}"
              f"XP: {green(str(state.xp_earned))} ({cyan(f'{xp_rate:.0f}/hr')}) │"
              f"Gems: {cyan(str(state.gem_earned))} ({green(f'{gem_rate:.0f}/hr')}) │"
              f"Time: {dim(state.elapsed())}", end="", flush=True)

        time.sleep(delay_ms / 1000)

    print()
    state.running = False
    _farm_summary("Mixed (XP+Gems)", f"{state.xp_earned} XP | {state.gem_earned} Gems","")

# ─── Auto Daily Quest ─────────────────────────────────────────────
# Source: runAutoCompleteQuests / bruteForceQuests from DuoHacker userscript
# Endpoint: goals-api.duolingo.com

GOALS_API ="https://goals-api.duolingo.com"

def _goals_headers(jwt, sub):
    return {
        "Content-Type":"application/json",
        "Accept":"application/json; charset=UTF-8",
        "Authorization": f"Bearer {jwt}",
        "x-requested-with":"XMLHttpRequest",
        "x-amzn-trace-id": f"User={sub}",
    }

def _get_quest_schema(jwt, sub):
    headers = _goals_headers(jwt, sub)
    tz ="UTC"
    try:
        import time as _t
        tz_offset = -(_t.timezone if _t.daylight == 0 else _t.altzone) // 60
        sign ="+" if tz_offset >= 0 else"-"
        tz = f"UTC{sign}{abs(tz_offset)//60:02d}:{abs(tz_offset)%60:02d}"
    except:
        pass
    status, data = duo_get(f"/schema?ui_language=en&_={int(time.time()*1000)}", jwt, sub)
    # goals-api is a different host — use http_request directly
    status, text = http_request("GET","goals-api.duolingo.com",
                                f"/schema?ui_language=en&_={int(time.time()*1000)}",
                                headers)
    try:
        return json.loads(text)
    except:
        return None

def _get_quest_progress(jwt, sub):
    headers = _goals_headers(jwt, sub)
    try:
        import time as _t
        tz_offset = -(_t.timezone if _t.daylight == 0 else _t.altzone) // 60
        sign ="+" if tz_offset >= 0 else"-"
        tz = f"UTC{sign}{abs(tz_offset)//60:02d}:{abs(tz_offset)%60:02d}"
    except:
        tz ="UTC"
    path = f"/users/{sub}/progress?timezone={urllib.parse.quote(tz)}&ui_language=en"
    status, text = http_request("GET","goals-api.duolingo.com", path, headers)
    try:
        return json.loads(text)
    except:
        return None

def _brute_force_quests(jwt, sub, metrics):
    """POST /users/{id}/progress/batch with quantity=2000 for each metric."""
    headers = _goals_headers(jwt, sub)
    try:
        tz_offset = -(time.timezone if time.daylight == 0 else time.altzone) // 60
        sign ="+" if tz_offset >= 0 else"-"
        tz = f"UTC{sign}{abs(tz_offset)//60:02d}:{abs(tz_offset)%60:02d}"
    except:
        tz ="UTC"
    updates = [{"metric": m,"quantity": 2000} for m in metrics]
    updates.append({"metric":"QUESTS","quantity": 1})
    payload = {
        "metric_updates": updates,
        "timezone": tz,
        "timestamp": datetime.now().isoformat(),
    }
    status, text = http_request(
        "POST","goals-api.duolingo.com",
        f"/users/{sub}/progress/batch",
        headers, payload
    )
    return status in (200, 201)

def auto_daily_quest(jwt, sub, user_info):
    """Complete all pending daily quests in one batch call.
    Source: runAutoCompleteQuests from DuoHacker userscript."""
    log("Fetching quest schema & progress...","info")
    schema = _get_quest_schema(jwt, sub)
    progress = _get_quest_progress(jwt, sub)

    if not schema or not progress:
        log("Failed to fetch quest data.","error")
        return False

    earned = set(progress.get("badges", {}).get("earned", []))
    metrics = set()
    for goal in schema.get("goals", []):
        is_daily ="DAILY" in (goal.get("category") or"")
        done = goal.get("badgeId") in earned or goal.get("goalId") in earned
        if is_daily and not done and goal.get("metric"):
            metrics.add(goal["metric"])

    if not metrics:
        log("All daily quests already completed!","success")
        return True

    log(f"Found {len(metrics)} quest(s) to complete: {','.join(metrics)}","info")
    ok = _brute_force_quests(jwt, sub, list(metrics))
    if ok:
        log("Daily quests completed!","success")
    else:
        log("Quest batch failed — you may need to complete some manually.","warning")
    return ok

# ─── Auto League ──────────────────────────────────────────────────
# Source: farmLeague from DuoHacker userscript
# Fetches leaderboard, farms XP until Rank 1 gap > 1000 XP

LEADERBOARD_URL = ("https://duolingo-leaderboards-prod.duolingo.com"
                   "/leaderboards/7d9f5dd1-8423-491a-91f2-2532052038ce")

def _get_league_rank(jwt, sub):
    """Returns (rank, my_score, gap_to_top) or None on error."""
    headers = make_headers(jwt, sub)
    headers["Host"] ="duolingo-leaderboards-prod.duolingo.com"
    status, text = http_request(
        "GET","duolingo-leaderboards-prod.duolingo.com",
        f"/leaderboards/7d9f5dd1-8423-491a-91f2-2532052038ce"
        f"/users/{sub}?client_unlocked=true&_={int(time.time()*1000)}",
        headers
    )
    try:
        data = json.loads(text)
        rankings = data.get("active", {}).get("cohort", {}).get("rankings", [])
        if not rankings:
            return None
        my_data = next((u for u in rankings if str(u.get("user_id")) == str(sub)), None)
        if not my_data:
            return None
        rank = rankings.index(my_data) + 1
        my_score= my_data["score"]
        gap = (rankings[0]["score"] - my_score) if rank > 1 else (my_score - rankings[1]["score"] if len(rankings) > 1 else 9999)
        return rank, my_score, gap
    except:
        return None

def farm_league(jwt, sub, user_info, delay_ms):
    """Farm XP until Rank 1 with a gap > 1000 XP.
    Source: farmLeague from DuoHacker userscript."""
    log("Starting Auto League — targeting Rank 1...","info")
    state.running = True
    state.start_time = time.time()
    tick = 0

    print()
    while state.running:
        tick += 1
        result = _get_league_rank(jwt, sub)
        if result is None:
            log("Could not fetch leaderboard. Are you in a league?","error")
            break

        rank, my_score, gap = result

        if rank == 1:
            if gap > 1000:
                log(f" Rank 1 secured! Gap: {gap} XP — stopping.","success")
                break
            else:
                print(f"\r {spinner_char(tick)} Rank: [bold]1[/bold]"
                      f"Gap above #2: {yellow(str(gap))} XP"
                      f"Score: {blue(str(my_score))}"
                      f"Time: {dim(state.elapsed())}", end="", flush=True)
        else:
            print(f"\r {spinner_char(tick)} Rank: {red(str(rank))}"
                  f"Gap to #1: {yellow(str(gap))} XP"
                  f"Score: {blue(str(my_score))}"
                  f"Time: {dim(state.elapsed())}", end="", flush=True)

        # Farm one stories XP cycle
        status = farm_xp_once_stories(jwt, sub, user_info)
        if status == 200:
            state.xp_earned += 499
            state.calls += 1
        elif status == 429:
            time.sleep(60)
        else:
            state.errors += 1

        time.sleep(delay_ms / 1000)

    print()
    state.running = False
    _farm_summary("Auto League", state.xp_earned,"XP")

# ─── Shop Items ───────────────────────────────────────────────────
# Source: getShopItems / buyItem / categorizeItems from DuoHacker userscript
# GET /2023-05-23/shop-items → item list
# POST /2017-06-30/users/{id}/shop-items → buy

_SHOP_ICONS = {
    "Streak Freezes":"",
    "XP Boosts":"",
    "Hearts":"",
    "Gems":"",
    "Outfits":"",
    "Free Trials":"⭐",
    "Misc":"",
}

_FREE_SUPER_TRIAL = {
    "id":"immersive_subscription",
    "name":"Free 3-Day Super Trial",
    "currencyType":"XGM",
    "type":"subscription",
}

def _format_item_name(item_id, name):
    if name:
        return name
    return"".join(
        w.upper() if w =="xp" else w.capitalize()
        for w in item_id.split("_")
    )

def _categorize_item(item):
    i = item.get("id","")
    cat ="Misc"
    if"streak_freeze" in i: cat ="Streak Freezes"
    elif"xp_boost" in i: cat ="XP Boosts"
    elif"health" in i or"heart" in i: cat ="Hearts"
    elif"gem" in i: cat ="Gems"
    elif item.get("type") =="outfit": cat ="Outfits"
    elif"free_taste" in i or"immersive" in i: cat ="Free Trials"
    return cat

def _get_shop_items(jwt, sub):
    """GET /2023-05-23/shop-items — mirrors getShopItems from DuoHacker userscript.
    Uses credentials=include equivalent: sends jwt_token cookie + Authorization header."""
    headers = {
        "Accept":"application/json",
        "Authorization": f"Bearer {jwt}",
        "Content-Type":"application/json",
        "Cookie": f"jwt_token={jwt}",
        "Host":"www.duolingo.com",
        "User-Agent": random_ua(),
        "x-amzn-trace-id": f"User={sub}",
        "Referer":"https://www.duolingo.com/",
        "Origin":"https://www.duolingo.com",
    }
    status, text = http_request("GET","www.duolingo.com",
                                "/2023-05-23/shop-items", headers)
    try:
        data = json.loads(text)
        # Response is {"shopItems": [...] } — same as DuoHacker: data.shopItems || []
        if isinstance(data, dict):
            raw_items = data.get("shopItems", [])
        elif isinstance(data, list):
            # Fallback: some versions return a bare array
            raw_items = data
        else:
            raw_items = []
    except:
        raw_items = []

    # Debug: log how many raw items came back
    log(f"Shop API returned {len(raw_items)} raw item(s) (status {status})","info")

    # Always include Free Super Trial (same as DuoHacker)
    result = [_FREE_SUPER_TRIAL]

    for item in raw_items:
        # DuoHacker filter: currencyType ==="XGM" && !id.includes("gift")
        if item.get("currencyType") !="XGM":
            continue
        if"gift" in item.get("id",""):
            continue
        item_id = item.get("id","")
        name = _format_item_name(item_id, item.get("name"))
        cat = _categorize_item(item)
        # XP Boost: append minute count from id suffix (e.g. xp_boost_15 →"15 min")
        if"xp_boost" in item_id:
            m = re.search(r"\d+$", item_id)
            if m:
                name += f" ({m.group()} min)"
        # Health Refill Partial: rename with heart count
        if"health" in item_id and"partial" in item_id:
            n = re.search(r"\d$", item_id)
            if n:
                name = f"Health Refill Partial ({n.group()} Heart)"
        result.append({**item,"displayName": name,"category": cat})

    # Sort: Streak Freezes → XP Boosts → Hearts → Gems → Outfits → Free Trials → Misc
    cat_order = ["Streak Freezes","XP Boosts","Hearts","Gems","Outfits","Free Trials","Misc"]
    result.sort(key=lambda x: (
        cat_order.index(x.get("category","Misc"))
        if x.get("category","Misc") in cat_order else 99
    ))
    return result

def _buy_item(jwt, sub, user_info, item_id, display_name):
    """POST /2017-06-30/users/{id}/shop-items — mirrors buyItem from DuoHacker."""
    headers = make_headers(jwt, sub)
    headers["Host"] ="www.duolingo.com"
    url = f"https://www.duolingo.com/2017-06-30/users/{sub}/shop-items"

    # Free super trial needs two product IDs to try
    if item_id in ("immersive_subscription",) or"free_taste" in item_id:
        product_ids = [
            "com.duolingo.immersive_free_trial_subscription",
            "com.duolingo.super_free_trial_subscription",
        ]
        for prod in product_ids:
            payload = {
                "itemName": item_id,
                "isFree": True,
                "consumed": True,
                "fromLanguage": user_info.get("fromLanguage","en"),
                "learningLanguage": user_info.get("learningLanguage","fr"),
                "productId": prod,
            }
            status, text = http_request("POST","www.duolingo.com",
                                        f"/2017-06-30/users/{sub}/shop-items",
                                        headers, payload)
            if status == 200:
                return True
        return False

    payload = {
        "itemName": item_id,
        "isFree": True,
        "consumed": True,
        "fromLanguage": user_info.get("fromLanguage","en"),
        "learningLanguage": user_info.get("learningLanguage","fr"),
    }
    status, text = http_request("POST","www.duolingo.com",
                                f"/2017-06-30/users/{sub}/shop-items",
                                headers, payload)
    return status == 200

def shop_items_menu(acc):
    """Browse and buy shop items for a given account."""
    cls()
    jwt = acc["jwt"]
    sub = acc["sub"]
    user_info = acc.get("info", {})

    log("Loading shop items from /2023-05-23/shop-items ...","info")
    items = _get_shop_items(jwt, sub)

    # If only the free trial fallback came back, show raw debug info
    if len(items) <= 1:
        log("Only 1 item returned — showing raw API response for debug:","warning")
        headers = {
            "Accept":"application/json",
            "Authorization": f"Bearer {jwt}",
            "Content-Type":"application/json",
            "Cookie": f"jwt_token={jwt}",
            "Host":"www.duolingo.com",
            "User-Agent": random_ua(),
            "x-amzn-trace-id": f"User={sub}",
        }
        status, text = http_request("GET","www.duolingo.com",
                                    "/2023-05-23/shop-items", headers)
        log(f"HTTP {status}","info")
        # Show first 800 chars of raw response
        preview = text[:800].replace("\n","")
        print(f"\n {dim(preview)}\n")
        _con.input(f" [dim]Press Enter to continue anyway...[/dim]")

    if not items:
        log("No shop items available.","warning")
        _con.input(f"\n [dim]Press Enter...[/dim]")
        return

    # Group by category
    from collections import OrderedDict
    groups = OrderedDict()
    for item in items:
        cat = item.get("category","Misc")
        groups.setdefault(cat, []).append(item)

    while True:
        cls()
        account_name = user_info.get("username", sub)
        box([
            f" Account : {bold(green(account_name))}",
            f" Gems : {bold(cyan(str(user_info.get('gems','?'))))}",
            f" [dim]Items are acquired free (isFree=True) — no gems deducted[/dim]",
        ], title=" Shop Items", color="yellow")
        print()

        # List all items with numbering
        all_items = []
        current_cat = None
        idx = 1
        for cat, cat_items in groups.items():
            icon = _SHOP_ICONS.get(cat,"")
            if cat != current_cat:
                print(f" {bold(yellow(f'{icon} {cat}'))}")
                current_cat = cat
            for item in cat_items:
                name = item.get("displayName") or item.get("name") or item.get("id","?")
                print(f" {bold(str(idx)+'.')} {name}")
                all_items.append(item)
                idx += 1

        print()
        print(f" [bold]a.[/bold] [bright_green]Buy ALL items[/bright_green]")
        print(f" [bold]0.[/bold] [dim]← Back[/dim]")
        print()
        choice = _con.input(f" [cyan]Item # or (a)ll or 0:[/cyan]").strip().lower()

        if choice =="0":
            return
        elif choice =="a":
            print()
            log(f"Buying all {len(all_items)} items...","info")
            ok = fail = 0
            for item in all_items:
                iid = item.get("id","")
                name = item.get("displayName") or item.get("name") or iid
                success = _buy_item(jwt, sub, user_info, iid, name)
                if success:
                    log(f" {name}","success"); ok += 1
                else:
                    log(f" {name}","error"); fail += 1
                time.sleep(0.5)
            log(f"Done — {ok} success, {fail} failed","success" if fail == 0 else"warning")
            _con.input(f"\n [dim]Press Enter...[/dim]")
        else:
            try:
                item_idx = int(choice) - 1
                if 0 <= item_idx < len(all_items):
                    item = all_items[item_idx]
                    iid = item.get("id","")
                    name = item.get("displayName") or item.get("name") or iid
                    log(f"Purchasing {bold(name)}...","info")
                    ok = _buy_item(jwt, sub, user_info, iid, name)
                    if ok:
                        log(f" {name} acquired!","success")
                    else:
                        log(f" Failed to acquire {name}.","error")
                    _con.input(f"\n [dim]Press Enter...[/dim]")
                else:
                    log("Invalid selection.","error")
            except ValueError:
                log("Invalid input.","error")

# ─── Generate Account ─────────────────────────────────────────────
# Flow based on DuoXPy Dex CLI source:
# 1. POST android-api-cf.duolingo.com/2023-05-23/users → unclaimed guest + JWT
# 2. POST android-api-cf.duolingo.com/2017-06-30/batch → claim (email/user/pass)
# 3. POST www.duolingo.com/2017-06-30/sessions → create lesson session
# 4. PUT www.duolingo.com/2017-06-30/sessions/{id} → complete lesson (+15 XP)
# 5. POST stories.duolingo.com/.../complete ×10 → farm stories XP
# No external API needed — random email used, stdlib urllib only.

import urllib.request, urllib.error, ssl as _ssl

GENERATE_ANDROID_HOST ="android-api-cf.duolingo.com"
GENERATE_WEB_HOST ="www.duolingo.com"
GENERATE_STORIES_HOST ="stories.duolingo.com"
GENERATE_FIXED_NAME ="DuoHacker Service"
GENERATED_FILE = os.path.join(os.path.dirname(__file__),"generated_accounts.json")

_GEN_TIMEZONES = [
    "America/New_York","America/Los_Angeles","America/Chicago","America/Denver",
    "Europe/London","Europe/Paris","Europe/Berlin","Asia/Tokyo","Asia/Shanghai",
    "Asia/Singapore","Asia/Ho_Chi_Minh","Australia/Sydney","America/Sao_Paulo",
]

_GEN_MOBILE_UA = [
    "Duodroid/6.26.2 Dalvik/2.1.0 (Linux; U; Android 14; Pixel 8 Build/UP1A.231005.007)",
    "Duodroid/6.26.2 Dalvik/2.1.0 (Linux; U; Android 13; SM-S918B Build/TP1A.220624.014)",
    "Duodroid/6.26.2 Dalvik/2.1.0 (Linux; U; Android 13; SM-G998B Build/TP1A.220624.014)",
    "Duodroid/6.26.2 Dalvik/2.1.0 (Linux; U; Android 15; Pixel 9 Build/AP3A.240905.015)",
    "Duolingo/5.158.4 (iPhone; iOS 17.4; Scale/3.00)",
    "Duolingo/5.157.0 (Android; Build/12; Model/Pixel 7)",
]

_GEN_WEB_UA = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/129.0.0.0 Safari/537.36",
]

_GEN_ADJ = ["swift","bright","cool","dark","eager","fresh","glad","happy",
             "icy","jolly","keen","lively","merry","neat","prime","quick","rapid","sunny"]
_GEN_NOUN = ["alex","blake","casey","dana","ellis","finley","gray","harper",
             "indigo","jordan","kai","lane","morgan","nova","parker","quinn","reese","sage"]

_gen_lock = threading.Lock()

def _gen_mobile_ua(): return random.choice(_GEN_MOBILE_UA)
def _gen_web_ua(): return random.choice(_GEN_WEB_UA)
def _gen_tz(): return random.choice(_GEN_TIMEZONES)
def _gen_username():
    import string as _s
    base = f"{random.choice(_GEN_ADJ)}{random.choice(_GEN_NOUN)}{random.randint(100,9999)}"
    return base[:16]
def _gen_password():
    import string as _s
    chars = _s.ascii_letters + _s.digits +"!@#$%^&*"
    return"".join(random.choices(chars, k=12))
def _gen_email(u):
    domains = ["gmail.com","yahoo.com","outlook.com","hotmail.com","proton.me","icloud.com"]
    return f"{u}{random.randint(10,999)}@{random.choice(domains)}"

# ── SSL context (ignore cert for stdlib urllib) ───────────────────
def _ssl_ctx():
    ctx = _ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = _ssl.CERT_NONE
    return ctx

def _urllib_request(method, url, headers, body=None):
    """urllib-based HTTP request. Returns (status, dict, jwt_header)."""
    try:
        body_bytes = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
        with urllib.request.urlopen(req, context=_ssl_ctx(), timeout=30) as resp:
            raw = resp.read()
            text = raw.decode("utf-8", errors="replace")
            jwt_h = resp.getheader("jwt") or resp.getheader("Jwt") or resp.getheader("JWT") or""
            return resp.status, _try_json(text), jwt_h
    except urllib.error.HTTPError as e:
        raw = e.read()
        text = raw.decode("utf-8", errors="replace")
        jwt_h = e.headers.get("jwt") or e.headers.get("Jwt") or""
        return e.code, _try_json(text), jwt_h
    except Exception as ex:
        return 0, {},""

# ── Step 1: Create unclaimed guest account ────────────────────────
def _gen_create_unclaimed():
    """POST /2023-05-23/users → guest account. Returns (duo_id, jwt, creation_date)."""
    import uuid as _uuid
    headers = {
        "accept":"application/json",
        "connection":"Keep-Alive",
        "content-type":"application/json",
        "host": GENERATE_ANDROID_HOST,
        "user-agent": _gen_mobile_ua(),
        "x-amzn-trace-id":"User=0",
    }
    payload = {
        "currentCourseId":"DUOLINGO_FR_EN",
        "distinctId": str(_uuid.uuid4()),
        "fromLanguage":"en",
        "timezone":"Asia/Saigon",
        "zhTw": False,
    }
    url = (f"https://{GENERATE_ANDROID_HOST}/2023-05-23/users"
           "?fields=id,creationDate,fromLanguage,courses,currentCourseId,"
           "username,health,zhTw,hasPlus,joinedClassroomIds,observedClassroomIds,roles")
    for attempt in range(3):
        status, data, jwt_h = _urllib_request("POST", url, headers, payload)
        if status in (200, 201) and data.get("id"):
            jwt = jwt_h or data.get("jwt","")
            if not jwt:
                raise RuntimeError("No JWT in response headers")
            return data["id"], jwt, data.get("creationDate","")
        if status == 429:
            time.sleep(5 + attempt * 3)
            continue
        if attempt < 2:
            time.sleep(2)
    raise RuntimeError(f"Create unclaimed failed (HTTP {status}): {data}")

# ── Step 2: Claim account via batch (matches DuoXPy Dex source) ───
def _gen_claim_batch(duo_id, jwt, email, username, password):
    """POST /2017-06-30/batch with PATCH inside — exact flow from DuoXPy Dex."""
    headers = {
        "accept":"application/json",
        "authorization": f"Bearer {jwt}",
        "connection":"Keep-Alive",
        "content-type":"application/json",
        "cookie": f"jwt_token={jwt}",
        "host": GENERATE_ANDROID_HOST,
        "user-agent": _gen_mobile_ua(),
        "x-amzn-trace-id": f"User={duo_id}",
    }
    batch_payload = {
        "requests": [{
            "body": json.dumps({
                "age": str(random.randint(18, 50)),
                "distinctId": f"UserId(id={duo_id})",
                "email": email,
                "emailPromotion": True,
                "name": GENERATE_FIXED_NAME,
                "firstName": GENERATE_FIXED_NAME,
                "lastName": GENERATE_FIXED_NAME,
                "username": username,
                "password": password,
                "pushPromotion": True,
                "timezone":"Asia/Saigon",
            }),
            "bodyContentType":"application/json",
            "method":"PATCH",
            "url": f"/2023-05-23/users/{duo_id}?fields=id,email,name",
        }]
    }
    url = f"https://{GENERATE_ANDROID_HOST}/2017-06-30/batch?fields=responses"
    for attempt in range(3):
        status, data, _ = _urllib_request("POST", url, headers, batch_payload)
        if status == 200:
            return data
        if status == 403:
            raise RuntimeError(f"Batch claim 403 — JWT rejected: {data}")
        if status == 429:
            time.sleep(5 + attempt * 3)
            continue
        if attempt < 2:
            time.sleep(2)
    raise RuntimeError(f"Batch claim failed (HTTP {status}): {data}")

# ── Step 3+4: Complete initial lesson (+15 XP) ────────────────────
def _gen_complete_lesson(duo_id, jwt):
    """Create session + PUT complete. Mirrors DuoXPy Dex completeInitialLesson."""
    import uuid as _uuid
    lesson_headers = {
        "Authorization": f"Bearer {jwt}",
        "Content-Type":"application/json; charset=UTF-8",
        "Accept":"application/json; charset=UTF-8",
        "User-Agent": _gen_web_ua(),
        "Origin":"https://www.duolingo.com",
        "Referer":"https://www.duolingo.com/lesson",
        "host": GENERATE_WEB_HOST,
        "cookie": f"jwt_token={jwt}",
        "x-amzn-trace-id": f"User={duo_id}",
    }
    session_payload = {
        "challengeTypes": [
            "assist","characterIntro","characterMatch","characterPuzzle","characterSelect",
            "characterTrace","characterWrite","completeReverseTranslation","definition",
            "dialogue","extendedMatch","extendedListenMatch","form","freeResponse",
            "gapFill","judge","listen","listenComplete","listenMatch","match","name",
            "listenComprehension","listenIsolation","listenSpeak","listenTap",
            "orderTapComplete","partialListen","partialReverseTranslate","patternTapComplete",
            "radioBinary","radioImageSelect","radioListenMatch","radioListenRecognize",
            "radioSelect","readComprehension","reverseAssist","sameDifferent","select",
            "selectPronunciation","selectTranscription","svgPuzzle","syllableTap",
            "syllableListenTap","speak","tapCloze","tapClozeTable","tapComplete",
            "tapCompleteTable","tapDescribe","translate","transliterate",
            "transliterationAssist","typeCloze","typeClozeTable","typeComplete",
            "typeCompleteTable","writeComprehension",
        ],
        "fromLanguage":"en",
        "isFinalLevel": False,
        "isV2": True,
        "juicy": True,
        "learningLanguage":"fr",
        "shakeToReportEnabled": True,
        "smartTipsVersion": 2,
        "isCustomIntroSkill": False,
        "isGrammarSkill": False,
        "levelIndex": 0,
        "pathExperiments": [],
        "showGrammarSkillSplash": False,
        "skillId":"fc5f14f4f4d2451e18f3f03725a5d5b1",
        "type":"LESSON",
        "levelSessionIndex": 0,
    }
    url_session = f"https://{GENERATE_WEB_HOST}/2017-06-30/sessions"
    status, session_data, _ = _urllib_request("POST", url_session, lesson_headers, session_payload)
    if status != 200 or not session_data.get("id"):
        return False # non-fatal, skip lesson

    session_id = session_data["id"]
    time.sleep(2)

    complete_headers = dict(lesson_headers)
    complete_headers["Idempotency-Key"] = session_id
    complete_headers["X-Requested-With"] ="XMLHttpRequest"
    complete_headers["User"] = str(duo_id)

    session_data["failed"] = False
    session_data["xpGain"] = 15
    now_ts = time.time()
    tp = session_data.setdefault("trackingProperties", {})
    tp["sum_time_taken"] = 45 + (now_ts % 15)
    tp["xp_gained"] = 15
    if not tp.get("activity_uuid"):
        tp["activity_uuid"] = str(_uuid.uuid4())

    url_complete = f"https://{GENERATE_WEB_HOST}/2017-06-30/sessions/{session_id}"
    _urllib_request("PUT", url_complete, complete_headers, session_data)
    return True

# ── Step 5: Farm stories XP ×N ────────────────────────────────────
def _gen_farm_stories(duo_id, jwt, count=10):
    """POST stories complete ×count — mirrors DuoXPy Dex farmStoriesXP."""
    headers = {
        "accept":"application/json",
        "authorization": f"Bearer {jwt}",
        "content-type":"application/json",
        "host": GENERATE_STORIES_HOST,
        "origin":"https://stories.duolingo.com",
        "user-agent": _gen_mobile_ua(),
        "x-amzn-trace-id": f"User={duo_id}",
    }
    url = f"https://{GENERATE_STORIES_HOST}/api2/stories/fr-en-le-passeport/complete"
    total_xp = 0
    for i in range(count):
        now = time.time()
        payload = {
            "awardXp": True,
            "completedBonusChallenge": True,
            "fromLanguage":"en",
            "hasXpBoost": False,
            "illustrationFormat":"svg",
            "isFeaturedStoryInPracticeHub": True,
            "isLegendaryMode": True,
            "isV2Redo": False,
            "isV2Story": False,
            "learningLanguage":"fr",
            "masterVersion": True,
            "maxScore": 0,
            "score": 0,
            "happyHourBonusXp": random.randint(0, 465),
            "startTime": now,
            "endTime": now + random.randint(300, 420),
        }
        retry = 0
        while retry < 5:
            status, data, _ = _urllib_request("POST", url, headers, payload)
            if status == 200:
                total_xp += data.get("xpEarned", 499)
                time.sleep(2)
                break
            elif status == 429:
                time.sleep(60)
                retry += 1
            else:
                time.sleep(2)
                break
    return total_xp

# ── Full account creation worker ──────────────────────────────────
class _GenResult:
    def __init__(self):
        self.lock = threading.Lock()
        self.ok = []
        self.failed = 0
        self.done = 0

def _gen_worker(result, delay_ms, tid, farm_stories=True, story_count=10):
    """Full flow: unclaimed → claim → lesson → stories."""
    try:
        username = _gen_username()
        password = _gen_password()
        email = _gen_email(username)

        # Step 1
        duo_id, jwt, created = _gen_create_unclaimed()
        time.sleep(2)

        # Step 2
        _gen_claim_batch(duo_id, jwt, email, username, password)
        time.sleep(2)

        # Step 3+4
        _gen_complete_lesson(duo_id, jwt)
        time.sleep(2)

        # Step 5 (optional)
        total_xp = 0
        if farm_stories:
            total_xp = _gen_farm_stories(duo_id, jwt, story_count)

        acc = {
            "_id": duo_id,
            "username": username,
            "email": email,
            "password": password,
            "jwt": jwt,
            "name": GENERATE_FIXED_NAME,
            "timezone":"Asia/Saigon",
            "xp": total_xp,
            "type":"unverified",
            "createdAt": str(created),
            "savedAt": datetime.now().isoformat(),
        }
        with result.lock:
            result.ok.append(acc)
            result.done += 1
    except Exception as e:
        with result.lock:
            result.failed += 1
            result.done += 1
        with _gen_lock:
            print(f"\n [bright_red][/bright_red] Thread-{tid}: {dim(str(e))}")
    if delay_ms > 0:
        time.sleep(delay_ms / 1000)

def _save_generated(accs):
    existing = []
    if os.path.exists(GENERATED_FILE):
        try:
            with open(GENERATED_FILE) as f:
                existing = json.load(f)
        except:
            pass
    existing.extend(accs)
    with open(GENERATED_FILE,"w") as f:
        json.dump(existing, f, indent=2)

# ── Menu ──────────────────────────────────────────────────────────
def generate_accounts_menu():
    cls()
    box([
        " Auto-generate Duolingo accounts.",
        f" [dim]Flow: guest → batch claim → lesson → stories XP[/dim]",
        f" [dim]No API key needed — results saved to generated_accounts.json[/dim]",
        "",
        f" [yellow]Based on DuoXPy Dex CLI source[/yellow]",
    ], title=" Generate Account", color="medium_purple1")
    print()

    # count
    try:
        v = _con.input(f" [cyan]How many accounts? [default=1]:[/cyan]").strip()
        count = int(v) if v else 1
        if count < 1 or count > 500:
            log("Count must be 1–500.","error")
            _con.input(f"\n [dim]Press Enter...[/dim]")
            return
    except ValueError:
        log("Invalid number.","error")
        _con.input(f"\n [dim]Press Enter...[/dim]")
        return

    # threads
    try:
        v = _con.input(f" [cyan]Threads (parallel, 1–10) [default=1]:[/cyan]").strip()
        threads = max(1, min(10, int(v) if v else 1))
    except ValueError:
        threads = 1

    # delay
    try:
        v = _con.input(f" [cyan]Delay per thread (ms) [default=2000]:[/cyan]").strip()
        delay_ms = max(0, int(v) if v else 2000)
    except ValueError:
        delay_ms = 2000

    # farm stories option
    farm_stories = True
    v = _con.input(f" [cyan]Farm stories XP after creation? (Y/n) [default=Y]:[/cyan]").strip().lower()
    if v =="n":
        farm_stories = False

    story_count = 10
    if farm_stories:
        try:
            v = _con.input(f" [cyan]Story runs per account [default=10]:[/cyan]").strip()
            story_count = max(1, min(50, int(v) if v else 10))
        except ValueError:
            story_count = 10

    print()
    box([
        f" Accounts : {bold(green(str(count)))}",
        f" Threads : {bold(cyan(str(threads)))}",
        f" Delay : {bold(yellow(str(delay_ms)))} ms / thread",
        f" Farm stories : {bold(green('Yes') if farm_stories else dim('No'))}",
        f" Story runs : {bold(str(story_count)) if farm_stories else dim('—')}",
        f" Output : [dim]generated_accounts.json[/dim]",
    ], title=" Config", color="cyan")
    print()
    if _con.input(f" [yellow]Start? (y/N):[/yellow]").strip().lower() !="y":
        log("Cancelled.","info")
        _con.input(f"\n [dim]Press Enter...[/dim]")
        return

    # run
    result = _GenResult()
    pending = list(range(count))
    active = []
    tick = 0
    start_ts = time.time()
    stop = [False]

    def _sig(s, f):
        stop[0] = True
        log("Stopping…","warning")
    signal.signal(signal.SIGINT, _sig)

    print()
    log(f"Generating {count} account(s) — {threads} thread(s), {delay_ms}ms delay","info")
    if farm_stories:
        log(f"Will farm {story_count} story run(s) per account (~{story_count*499} XP each)","info")
    print()

    while (pending or active) and not stop[0]:
        tick += 1
        while len(active) < threads and pending and not stop[0]:
            tid = count - len(pending) + 1
            t = threading.Thread(
                target=_gen_worker,
                args=(result, delay_ms, tid, farm_stories, story_count),
                daemon=True,
            )
            pending.pop(0)
            t.start()
            active.append(t)
        active = [t for t in active if t.is_alive()]

        with result.lock:
            n_ok, n_fail, n_done = len(result.ok), result.failed, result.done

        elapsed = time.time() - start_ts
        rate = n_ok / max(1, elapsed) * 60
        pct = n_done / max(1, count)
        bar = green("█" * int(24*pct)) + dim("░" * (24 - int(24*pct)))
        print(
            f"\r {spinner_char(tick)} [{bar}]"
            f"{bold(str(n_ok))}/{count}"
            f"{green(f'+{n_ok} ok')}"
            f"{(red(f'{n_fail} fail')) if n_fail else dim('0 fail')}"
            f"{dim(f'{elapsed:.0f}s')}"
            f"{cyan(f'{rate:.1f}/min')}",
            end="", flush=True,
        )
        time.sleep(0.3)

    for t in active:
        t.join(timeout=120)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    print()
    print()

    with result.lock:
        final_ok, final_fail = list(result.ok), result.failed

    if final_ok:
        _save_generated(final_ok)

    elapsed_total = time.time() - start_ts
    box([
        f" [bold]Done![/bold]",
        f" Requested : {bold(str(count))}",
        f" [bright_green][/bright_green] Success : {bold(green(str(len(final_ok))))}",
        f" [bright_red][/bright_red] Failed : {(red(str(final_fail))) if final_fail else dim('0')}",
        f" Runtime : {cyan(f'{elapsed_total:.1f}s')}",
        f" Saved to : {dim(GENERATED_FILE)}",
    ], title=" Summary", color="bright_green")
    print()

    if final_ok and _con.input(f" [cyan]Show accounts? (y/N):[/cyan]").strip().lower() =="y":
        print()
        for i, a in enumerate(final_ok, 1):
            box([
                f" {bold(f'#{i}')}",
                f" User ID : {dim(str(a['_id']))}",
                f" Username : {green(a['username'])}",
                f" Email : {cyan(a['email'])}",
                f" Password : {yellow(a['password'])}",
                f" XP : {blue(str(a.get('xp',0)))}",
                f" JWT : {dim(a['jwt'][:48] +'...')}",
            ], title=f"Account {i}", color="medium_purple1", width=70)
            print()

    _con.input(f" [dim]Press Enter to continue...[/dim]")

# ─── Account management ───────────────────────────────────────────
def add_account():
    import traceback
    cls()
    box([
        " Paste your Duolingo JWT token below.",
        " [dim]Get it from browser console:[/dim]",
        " [yellow]document.cookie.match(/jwt_token=([^;]+)/)[1][/yellow]",
    ], title=" Add Account", color="steel_blue1")
    print()
    jwt_raw = _con.input(" [cyan]JWT Token:[/cyan] ").strip().strip("'\"")
    if not jwt_raw:
        log("No token entered.", "warning")
        _con.input("\n [dim]Press Enter...[/dim] ")
        return

    if jwt_expired(jwt_raw):
        log("This JWT token is already expired!", "error")
        _con.input("\n [dim]Press Enter...[/dim] ")
        return

    try:
        sub = jwt_sub(jwt_raw)
    except ValueError as e:
        log(f"Invalid token format: {e}", "error")
        _con.input("\n [dim]Press Enter...[/dim] ")
        return

    if not sub:
        log("Cannot extract user ID from token.", "error")
        _con.input("\n [dim]Press Enter...[/dim] ")
        return

    log(f"Fetching info for sub [bold]{sub}[/bold]...", "info")
    try:
        info = get_user_info(jwt_raw, sub)
    except Exception as e:
        log(f"Failed to fetch account info: {e}", "error")
        print(f"\n[dim]{traceback.format_exc()}[/dim]")
        _con.input("\n [dim]Press Enter...[/dim] ")
        return

    if not info.get("username"):
        info["username"] = str(sub)

    accounts = load_accounts()
    for acc in accounts:
        if acc.get("sub") == str(sub):
            acc["jwt"] = jwt_raw
            acc["info"] = info
            save_accounts(accounts)
            log(f"Updated: [bold bright_green]{info['username']}[/bold bright_green]", "success")
            _con.input("\n [dim]Press Enter...[/dim] ")
            return

    accounts.append({"sub": str(sub), "jwt": jwt_raw, "info": info, "added": datetime.now().isoformat()})
    save_accounts(accounts)
    print()
    log(f"Account added: [bold bright_green]{info['username']}[/bold bright_green]", "success")
    log(f"Streak [yellow]{info.get('streak',0)}[/yellow]  XP [steel_blue1]{info.get('totalXp',0)}[/steel_blue1]  Gems [cyan]{info.get('gems',0)}[/cyan]", "stat")
    log(f"Token expires: [dim]{jwt_expires_at(jwt_raw)}[/dim]", "info")
    _con.input("\n [dim]Press Enter...[/dim] ")

def list_accounts():
    accounts = load_accounts()
    if not accounts:
        log("No accounts saved. Use 'Add Account' to add one.", "warning")
        return
    t = Table(box=rbox.SIMPLE, show_header=True, header_style="dim", padding=(0, 1))
    t.add_column("#",       style="dim",           width=3)
    t.add_column("username",style="bold white",     min_width=16)
    t.add_column("streak",  style="yellow",         width=8)
    t.add_column("xp",      style="steel_blue1",    width=10)
    t.add_column("gems",    style="cyan",           width=8)
    t.add_column("status",  width=8)
    for i, acc in enumerate(accounts, 1):
        info   = acc.get("info", {})
        exp    = jwt_expired(acc.get("jwt",""))
        status = "[bright_red]expired[/]" if exp else "[bright_green]active[/]"
        t.add_row(
            str(i),
            info.get("username","?"),
            str(info.get("streak", 0)),
            f"{info.get('totalXp', 0):,}",
            str(info.get("gems", 0)),
            status,
        )
    print()
    _con.print(t)

def remove_account():
    accounts = load_accounts()
    if not accounts:
        log("No accounts saved.","warning")
        return
    list_accounts()
    try:
        idx = int(_con.input(f" [cyan]Account number to remove:[/cyan]")) - 1
        removed = accounts.pop(idx)
        save_accounts(accounts)
        log(f"Removed: {bold(removed.get('info',{}).get('username','?'))}","success")
    except (ValueError, IndexError):
        log("Invalid selection.","error")

def refresh_account(acc):
    """Re-fetch user info for an account."""
    try:
        info = get_user_info(acc["jwt"], acc["sub"])
        acc["info"] = info
        accounts = load_accounts()
        for a in accounts:
            if a["sub"] == acc["sub"]:
                a["info"] = info
        save_accounts(accounts)
        log("Account info refreshed.","success")
        return info
    except Exception as e:
        log(f"Refresh failed: {e}","error")
        return acc.get("info", {})

def select_account():
    accounts = load_accounts()
    if not accounts:
        log("No accounts saved.","warning")
        return None
    if len(accounts) == 1:
        return accounts[0]

    print()
    list_accounts()
    try:
        idx = int(_con.input(f" [cyan]Select account:[/cyan]")) - 1
        return accounts[idx]
    except (ValueError, IndexError):
        log("Invalid selection.","error")
        return None

# ─── Info / Status ────────────────────────────────────────────────
def show_account_info(acc):
    info     = acc.get("info", {})
    jwt      = acc.get("jwt","")
    cls()
    exp      = jwt_expired(jwt)
    username = info.get("username","?")
    streak   = info.get('streak', 0)
    xp       = info.get('totalXp', 0)
    gems     = info.get('gems', 0)
    fl       = info.get('fromLanguage','?')
    ll       = info.get('learningLanguage','?')
    tok_str  = red("EXPIRED") if exp else green("active")

    from rich.panel import Panel
    _con.print(Panel(
        f"[bold bright_white]{username}[/]  [dim]{acc.get('sub','?')}[/]\n\n"
        f"  [dim]streak  [/] [yellow]{streak}[/] days\n"
        f"  [dim]total xp[/] [steel_blue1]{xp:,}[/]\n"
        f"  [dim]gems    [/] [cyan]{gems:,}[/]\n"
        f"  [dim]learning[/] {fl} [dim]→[/] {ll}\n\n"
        f"  [dim]token   [/] {tok_str}\n"
        f"  [dim]expires [/] [dim]{jwt_expires_at(jwt)}[/]",
        title="[bold cyan]account info[/]",
        border_style="cyan",
        padding=(0, 2),
        width=52,
    ))
    print()
    _con.input(f"  [dim]↵ continue[/dim] ")

# ─── UI menus ─────────────────────────────────────────────────────
def jwt_days_left(token: str) -> int:
    try:
        exp = decode_jwt(token).get("exp")
        if not exp:
            return 999
        return max(0, int((exp - time.time()) / 86400))
    except Exception:
        return 0

def check_jwt_warnings(accounts: list):
    """Print warnings for accounts with tokens expiring soon."""
    for acc in accounts:
        days = jwt_days_left(acc.get("jwt", ""))
        uname = acc.get("info", {}).get("username", acc.get("sub", "?"))
        if days == 0:
            log(f"[bold]{uname}[/bold] — token [bright_red]EXPIRED[/bright_red]", "warning")
        elif days <= 3:
            log(f"[bold]{uname}[/bold] — token expires in [yellow]{days}d[/yellow]", "warning")

def get_delay(default_ms: int = None) -> int:
    default_ms = default_ms or CFG.get("delay_ms", 1500)
    try:
        raw = _con.input(f"  [dim]delay ms[/] [dim][default={default_ms}][/] [dim]>[/] ").strip()
        val = int(raw) if raw else default_ms
        return max(200, val)
    except ValueError:
        return default_ms

def select_accounts_multi() -> list:
    """Select one or more accounts to farm. Returns list of account dicts."""
    accounts = load_accounts()
    if not accounts:
        log("No accounts saved.", "warning")
        return []
    if len(accounts) == 1:
        return accounts

    items = []
    for acc in accounts:
        info  = acc.get("info", {})
        uname = info.get("username", acc.get("sub", "?"))
        exp   = jwt_expired(acc.get("jwt", ""))
        days  = jwt_days_left(acc.get("jwt", ""))
        tag   = f"[bright_red]EXPIRED[/]" if exp else (f"[yellow]{days}d[/]" if days <= 5 else f"[dim]streak {info.get('streak',0)}[/]")
        items.append((uname, tag))

    items.append(("All accounts", ""))
    items.append(("Back", ""))

    choice = arrow_menu("Select Account(s)", items)
    if choice == -1 or choice == len(accounts) + 1:
        return []
    if choice == len(accounts):
        return [a for a in accounts if not jwt_expired(a.get("jwt", ""))]
    return [accounts[choice]]

def farm_menu():
    cls()
    accounts = load_accounts()
    check_jwt_warnings(accounts)
    acc = select_account()
    if not acc: return
    if jwt_expired(acc.get("jwt","")):
        log("JWT expired. Please re-add this account.","error")
        _con.input(f"\n [dim]Press Enter...[/dim]")
        return

    print()
    log(f"Refreshing account info for [bold]{acc.get('info',{}).get('username','?')}[/bold]...","info")
    info = refresh_account(acc)
    skill_id = extract_skill_id(info.get("currentCourse"))

    while True:
        FARM_OPTS = [
            ("XP Farm",             "Stories 499 XP, falls back to UNIT_TEST 110 XP"),
            ("Gem Farm",            "Reward endpoint, ~30 gems per call"),
            ("Mixed Farm",          "XP and Gems alternating"),
            ("Streak Farm — Safe",  "Farm streak up to account age limit"),
            ("Streak Farm — Normal","Farm streak backwards, no cap (higher risk)"),
            ("Auto Daily Quest",    "Complete all daily quests instantly via goals-api"),
            ("Auto League",         "Farm XP until Rank 1 with 1000 XP gap"),
            ("Back",                ""),
        ]
        choice = arrow_menu(
            "Farm Menu",
            FARM_OPTS,
            subtitle=(
                f"{info.get('username','?')}  |  "
                f"Streak: {info.get('streak', 0)}  |  "
                f"XP: {info.get('totalXp', 0)}  |  "
                f"Gems: {info.get('gems', 0)}"
            ),
        )

        if choice in (-1, 7):
            return

        def _sigint(sig, frame):
            state.running = False
            print()
            log("Stopping...", "warning")
        signal.signal(signal.SIGINT, _sigint)

        try:
            if choice in (3, 4, 6):
                delay = get_delay()
                state.reset()
                if choice == 3:
                    farm_streak_safe(acc["jwt"], acc["sub"], info, delay)
                elif choice == 4:
                    farm_streak_normal(acc["jwt"], acc["sub"], info, delay)
                elif choice == 6:
                    farm_league(acc["jwt"], acc["sub"], info, delay)
            elif choice == 5:
                auto_daily_quest(acc["jwt"], acc["sub"], info)
            else:
                state.reset()
                delay = get_delay()
                if choice == 0:
                    farm_xp(acc["jwt"], acc["sub"], info, delay)
                elif choice == 1:
                    farm_gems(acc["jwt"], acc["sub"], info, delay)
                elif choice == 2:
                    farm_mixed(acc["jwt"], acc["sub"], info, delay)
        except KeyboardInterrupt:
            state.running = False
            print()
            log("Stopped.", "warning")

        signal.signal(signal.SIGINT, signal.SIG_DFL)
        _con.input(f"\n  [dim]Press Enter to continue...[/dim]")

def accounts_menu():
    OPTS = [
        ("Add account",      "Link a new Duolingo account via JWT token"),
        ("List accounts",    "Show all saved accounts"),
        ("Remove account",   "Delete a saved account"),
        ("View account info","Show detailed info for an account"),
        ("Back",             ""),
    ]
    while True:
        accounts = load_accounts()
        choice = arrow_menu(
            "Account Manager",
            OPTS,
            subtitle=f"{len(accounts)} account(s) saved",
        )
        if choice == 0:
            add_account()
        elif choice == 1:
            cls()
            list_accounts()
            _con.input(f"\n  [dim]Press Enter...[/dim]")
        elif choice == 2:
            cls()
            remove_account()
            _con.input(f"\n  [dim]Press Enter...[/dim]")
        elif choice == 3:
            acc = select_account()
            if acc:
                show_account_info(acc)
        elif choice in (-1, 4):
            return

def settings_menu():
    while True:
        cfg   = load_config()
        debug = cfg.get("debug", False)
        delay = cfg.get("delay_ms", 1500)
        OPTS  = [
            ("Default delay",    f"{delay} ms"),
            ("Debug mode",       "[bright_green]ON[/]" if debug else "[dim]off[/]"),
                ("Clear all accounts", "Delete every saved account from disk"),
            ("Show accounts file", "Print the path to accounts.json"),
            ("Back",               ""),
        ]
        choice = arrow_menu("Settings", OPTS)
        if choice == 0:
            try:
                raw = _con.input(f"  [cyan]Default delay ms[/cyan] [dim][current={delay}][/dim] > ").strip()
                if raw:
                    cfg["delay_ms"] = max(200, int(raw))
                    save_config(cfg)
                    global CFG
                    CFG = cfg
                    log(f"Delay set to {cfg['delay_ms']}ms", "success")
            except ValueError:
                log("Invalid number.", "error")
            _con.input("  [dim]Press Enter...[/dim] ")
        elif choice == 1:
            cfg["debug"] = not debug
            save_config(cfg)
            CFG = cfg
            log(f"Debug mode {'enabled' if cfg['debug'] else 'disabled'}.", "success")
            _con.input("  [dim]Press Enter...[/dim] ")
        elif choice == 2:
            cls()
            confirm = _con.input("  [bright_red]Type YES to confirm:[/bright_red] ").strip()
            if confirm == "YES":
                save_accounts([])
                log("All accounts cleared.", "success")
            else:
                log("Cancelled.", "info")
            _con.input("  [dim]Press Enter...[/dim] ")
        elif choice == 3:
            log(f"accounts.json: [dim]{ACCOUNTS_FILE}[/dim]", "info")
            log(f"config.json:   [dim]{CONFIG_FILE}[/dim]", "info")
            _con.input("  [dim]Press Enter...[/dim] ")
        elif choice in (-1, 4):
            return

def check_streak_status():
    """Check & auto-protect streak for all accounts."""
    cls()
    accounts = load_accounts()
    if not accounts:
        log("No accounts saved.","warning")
        _con.input(f"\n [dim]Press Enter...[/dim]")
        return

    print(f"  [bold cyan]streak status[/]\n")
    print()

    for acc in accounts:
        info = acc.get("info", {})
        username = info.get("username", acc.get("sub","?"))
        if jwt_expired(acc.get("jwt","")):
            log(f"{username}: [bright_red]JWT expired[/bright_red]","error")
            continue
        try:
            info = get_user_info(acc["jwt"], acc["sub"])
        except Exception as e:
            log(f"{username}: {red(str(e))}","error")
            continue

        streak = info.get("streak", 0)
        streak_data = info.get("streakData", {})
        done_today = streak_done_today(streak_data)

        status = green(" done today") if done_today else yellow(" not done today")
        log(f"{bold(username)} — Streak: {yellow(str(streak))} days — {status}","stat")

    _con.input(f"\n [dim]Press Enter to continue...[/dim]")



# ─── Multi-account farm ───────────────────────────────────────────

class AccountFarmState:
    def __init__(self, username):
        self.username  = username
        self.running   = True
        self.xp        = 0
        self.gems      = 0
        self.calls     = 0
        self.errors    = 0
        self.status    = "starting"
        self.start_time= time.time()
        self._lock     = threading.Lock()

    def stop(self):
        with self._lock:
            self.running = False

    def is_running(self):
        with self._lock:
            return self.running

    def add_xp(self, n):
        with self._lock:
            self.xp += n; self.calls += 1

    def add_gems(self, n):
        with self._lock:
            self.gems += n; self.calls += 1

    def add_error(self):
        with self._lock:
            self.errors += 1

    def set_status(self, s):
        with self._lock:
            self.status = s

    def elapsed(self):
        secs = int(time.time() - self.start_time)
        return f"{secs//60:02d}:{secs%60:02d}"

    def rate_xp(self):
        elapsed = max(1, time.time() - self.start_time)
        return int(self.xp / elapsed * 3600)


def _multi_xp_worker(acc, st, delay_ms, stagger_s):
    """XP farm thread for one account."""
    time.sleep(stagger_s)
    jwt      = acc["jwt"]
    sub      = acc["sub"]
    info     = acc.get("info", {})
    use_stories       = True
    consecutive_429   = 0
    MAX_429           = 2

    while st.is_running():
        try:
            if use_stories and consecutive_429 < MAX_429:
                status = farm_xp_once_stories(jwt, sub, info)
                if status == 200:
                    st.add_xp(499)
                    consecutive_429 = 0
                    st.set_status("ok")
                elif status == 429:
                    consecutive_429 += 1
                    st.set_status("429")
                    if consecutive_429 >= MAX_429:
                        use_stories = False
                    time.sleep(delay_ms / 1000 * 2)
                    continue
                else:
                    use_stories = False
                    st.set_status(f"err{status}")
            else:
                skill_id = extract_skill_id(info.get("currentCourse"))
                if not skill_id:
                    st.set_status("no_skill")
                    st.stop(); break
                ok, earned = farm_xp_once_unit(jwt, sub, info, skill_id)
                if ok:
                    st.add_xp(earned)
                    st.set_status("ok")
                else:
                    st.add_error()
                    st.set_status("err")
                    if st.errors >= 5:
                        st.stop(); break
                    time.sleep(delay_ms / 1000 * 3)
                    continue
        except Exception as e:
            st.add_error()
            st.set_status("exc")
            if st.errors >= 5:
                st.stop(); break
        time.sleep(delay_ms / 1000)


def _multi_gems_worker(acc, st, delay_ms, stagger_s):
    """Gem farm thread for one account."""
    time.sleep(stagger_s)
    jwt  = acc["jwt"]
    sub  = acc["sub"]
    info = acc.get("info", {})

    while st.is_running():
        try:
            ok, earned = farm_gem_once(jwt, sub, info)
            if ok:
                st.add_gems(earned)
                st.set_status("ok")
            else:
                st.add_error()
                st.set_status("err")
                if st.errors >= 5:
                    st.stop(); break
        except Exception:
            st.add_error()
            if st.errors >= 5:
                st.stop(); break
        time.sleep(delay_ms / 1000)


def _multi_mixed_worker(acc, st, delay_ms, stagger_s):
    time.sleep(stagger_s)
    jwt      = acc["jwt"]
    sub      = acc["sub"]
    info     = acc.get("info", {})
    skill_id = extract_skill_id(info.get("currentCourse"))
    use_xp   = True

    while st.is_running():
        try:
            if use_xp:
                status = farm_xp_once_stories(jwt, sub, info)
                if status == 200:
                    st.add_xp(499); st.set_status("ok")
                elif status == 429:
                    st.set_status("429")
                else:
                    if skill_id:
                        ok, earned = farm_xp_once_unit(jwt, sub, info, skill_id)
                        if ok: st.add_xp(earned); st.set_status("ok")
            else:
                ok, earned = farm_gem_once(jwt, sub, info)
                if ok: st.add_gems(earned); st.set_status("ok")
            use_xp = not use_xp
        except Exception:
            st.add_error()
            if st.errors >= 5:
                st.stop(); break
        time.sleep(delay_ms / 1000)


def _render_multi_dashboard(states, farm_type, delay_ms):
    """Render live table of all account states. Returns string."""
    lines = []
    w = min(term_width(), 90)
    lines.append(f"  [bold]Multi-Account Farm[/bold]  [dim]{farm_type}  ·  delay {delay_ms}ms  ·  Ctrl+C to stop[/dim]")
    lines.append(f"  [dim]{'─' * (w - 4)}[/dim]")
    hdr = (
        f"  [dim]{'account':<16}{'xp':>8}{'gems':>8}{'calls':>7}{'err':>5}  {'rate':>10}  {'time':>6}  status[/dim]"
    )
    lines.append(hdr)
    lines.append(f"  [dim]{'─' * (w - 4)}[/dim]")
    for st in states:
        status_color = {"ok": "bright_green", "429": "yellow",
                        "err": "bright_red", "exc": "bright_red",
                        "no_skill": "yellow", "starting": "dim"}.get(
                        st.status.split("err")[0] if "err" in st.status else st.status, "dim")
        running_icon = "[bright_green]●[/]" if st.is_running() else "[dim]○[/]"
        rate = f"{st.rate_xp():,}/hr" if st.xp > 0 else "—"
        lines.append(
            f"  {running_icon} [bold white]{st.username:<15}[/]"
            f"[yellow]{st.xp:>8,}[/]"
            f"[cyan]{st.gems:>8,}[/]"
            f"[dim]{st.calls:>7}[/]"
            f"[{'bright_red' if st.errors else 'dim'}]{st.errors:>5}[/]"
            f"  [steel_blue1]{rate:>10}[/]"
            f"  [dim]{st.elapsed():>6}[/]"
            f"  [{status_color}]{st.status}[/]"
        )
    lines.append(f"  [dim]{'─' * (w - 4)}[/dim]")
    total_xp   = sum(s.xp   for s in states)
    total_gems = sum(s.gems for s in states)
    total_calls= sum(s.calls for s in states)
    lines.append(
        f"  [dim]{'TOTAL':<17}[/dim]"
        f"[bold yellow]{total_xp:>8,}[/]"
        f"[bold cyan]{total_gems:>8,}[/]"
        f"[dim]{total_calls:>7}[/]"
    )
    return "\n".join(lines)


def multi_farm(accs, farm_type, delay_ms):
    """Run farm_type across multiple accounts with one thread each."""
    cls()
    print()

    # Stagger starts by 500ms per account to avoid burst
    states  = []
    threads = []
    worker_map = {
        "xp":    _multi_xp_worker,
        "gems":  _multi_gems_worker,
        "mixed": _multi_mixed_worker,
    }
    worker_fn = worker_map.get(farm_type, _multi_xp_worker)

    for i, acc in enumerate(accs):
        uname = acc.get("info", {}).get("username", acc.get("sub", "?"))
        st    = AccountFarmState(uname)
        states.append(st)
        t = threading.Thread(
            target=worker_fn,
            args=(acc, st, delay_ms, i * 0.5),
            daemon=True
        )
        threads.append(t)

    # Ctrl+C handler
    _stop_all = lambda: [s.stop() for s in states]
    def _sig(sig, frame):
        _stop_all()
        print()
        log("Stopping all accounts...", "warning")
    signal.signal(signal.SIGINT, _sig)

    for t in threads:
        t.start()

    # Live dashboard loop
    try:
        while any(s.is_running() for s in states):
            dashboard = _render_multi_dashboard(states, farm_type, delay_ms)
            # Clear and redraw
            lines_count = dashboard.count("\n") + 1
            print(f"\033[{lines_count}A\033[J" if hasattr(sys.stdout, "write") else "", end="")
            print(dashboard)
            time.sleep(0.5)
        # Final render
        print(_render_multi_dashboard(states, farm_type, delay_ms))
    except KeyboardInterrupt:
        _stop_all()

    for t in threads:
        t.join(timeout=3)

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    print()
    log("Multi-account farm complete.", "success")
    _con.input("\n  [dim]Press Enter...[/dim] ")


def multi_farm_menu():
    accounts = load_accounts()
    active   = [a for a in accounts if not jwt_expired(a.get("jwt", ""))]

    if not active:
        log("No active accounts.", "warning")
        _con.input("\n  [dim]Press Enter...[/dim] ")
        return

    if len(active) == 1:
        log("Only 1 active account — use regular Farm menu instead.", "warning")
        _con.input("\n  [dim]Press Enter...[/dim] ")
        return

    # Account selection
    cls()
    items = []
    for acc in active:
        info  = acc.get("info", {})
        uname = info.get("username", acc.get("sub", "?"))
        days  = jwt_days_left(acc.get("jwt", ""))
        tag   = f"[yellow]{days}d left[/]" if days <= 5 else f"[dim]streak {info.get('streak',0)}  xp {info.get('totalXp',0):,}[/]"
        items.append((uname, tag))
    items.append(("All accounts", f"[dim]{len(active)} accounts[/]"))
    items.append(("Back", ""))

    sel = arrow_menu("Multi Farm — Select Accounts", items,
                     subtitle=f"{len(active)} active account(s)")
    if sel == -1 or sel == len(active) + 1:
        return

    selected = active if sel == len(active) else [active[sel]]
    if len(selected) < 2 and sel != len(active):
        log("Select 'All accounts' or use regular Farm for single account.", "info")
        _con.input("\n  [dim]Press Enter...[/dim] ")
        return

    # Farm type
    TYPE_OPTS = [
        ("XP Farm",    "Stories 499 XP per account"),
        ("Gem Farm",   "30 gems per call per account"),
        ("Mixed Farm", "XP + Gems alternating per account"),
        ("Back",       ""),
    ]
    type_map = {0: "xp", 1: "gems", 2: "mixed"}
    t_choice = arrow_menu("Multi Farm — Type",
                          TYPE_OPTS,
                          subtitle=f"{len(selected)} account(s) selected")
    if t_choice == -1 or t_choice == 3:
        return

    delay = get_delay()

    # Refresh all selected accounts
    print()
    log(f"Refreshing {len(selected)} account(s)...", "info")
    refreshed = []
    for acc in selected:
        try:
            info = get_user_info(acc["jwt"], acc["sub"])
            acc["info"] = info
            refreshed.append(acc)
            log(f"  [bold]{info.get('username','?')}[/bold] — streak {info.get('streak',0)}  xp {info.get('totalXp',0):,}", "success")
        except Exception as e:
            log(f"  Skip {acc.get('info',{}).get('username','?')}: {e}", "warning")

    if not refreshed:
        log("No accounts could be refreshed.", "error")
        _con.input("\n  [dim]Press Enter...[/dim] ")
        return

    print()
    log(f"Starting multi-farm: [bold]{len(refreshed)} accounts[/bold]  ·  {type_map[t_choice].upper()}  ·  {delay}ms delay", "farm")
    time.sleep(0.5)

    multi_farm(refreshed, type_map[t_choice], delay)

# ─── Main menu ────────────────────────────────────────────────────
def main_menu():
    OPTS = [
        ("Farm",             "XP / Gems / Streak / Mixed / Quest / League"),
        ("Multi Farm",       "Farm multiple accounts simultaneously"),
        ("Account Manager",  "Add, remove, and view saved accounts"),
        ("Shop Items",       "Browse and buy Duolingo shop items"),
        ("Generate Account", "Auto-generate new Duolingo accounts"),
        ("Streak Status",    "Check streak status across all accounts"),
        ("Settings",         "Configure PyLingo options"),
        ("Exit",             ""),
    ]
    while True:
        accounts = load_accounts()
        n_acc    = len(accounts)
        n_exp    = sum(1 for a in accounts if jwt_expired(a.get("jwt", "")))
        n_warn   = sum(1 for a in accounts if 0 < jwt_days_left(a.get("jwt","")) <= 3)
        if n_acc:
            if n_exp:
                sub_line = f"{n_acc} account(s) — [bright_red]{n_exp} expired[/bright_red]"
            elif n_warn:
                sub_line = f"{n_acc} account(s) — [yellow]{n_warn} expiring soon[/yellow]"
            else:
                sub_line = f"{n_acc} account(s) — [bright_green]all active[/bright_green]"
        else:
            sub_line = "No accounts saved — add one first"

        idx = arrow_menu("Main Menu", OPTS, subtitle=sub_line)

        if idx == 0:
            farm_menu()
        elif idx == 1:
            multi_farm_menu()
        elif idx == 2:
            accounts_menu()
        elif idx == 3:
            acc = select_account()
            if acc:
                shop_items_menu(acc)
        elif idx == 4:
            generate_accounts_menu()
        elif idx == 5:
            check_streak_status()
        elif idx == 6:
            settings_menu()
        elif idx in (7, -1):
            cls()
            print()
            print(f"  [bold bright_white]Goodbye![/]  [dim]pylingo v{VERSION}[/]")
            print()
            sys.exit(0)

# ─── Entry point ─────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print()
        log("Interrupted. Goodbye.", "info")
        sys.exit(0)
