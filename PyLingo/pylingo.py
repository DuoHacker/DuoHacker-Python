#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════
# PyLingo — Duolingo XP / Gem / Streak Farming Tool
# Pure Python stdlib only · Terminal UI with ANSI
# ═══════════════════════════════════════════════════════════════════

import os, sys, json, time, base64, threading, http.client, urllib.parse
import signal, math, random, re
from datetime import datetime, timezone

VERSION ="1.0.0"
BANNER_ART = r"""
  ██████╗ ██╗ ██╗██╗ ██╗███╗ ██╗ ██████╗ ██████╗
  ██╔══██╗╚██╗ ██╔╝██║ ██║████╗ ██║██╔════╝ ██╔═══██╗
  ██████╔╝ ╚████╔╝ ██║ ██║██╔██╗ ██║██║ ███╗██║ ██║
  ██╔═══╝ ╚██╔╝ ██║ ██║██║╚██╗██║██║ ██║██║ ██║
  ██║ ██║ ███████╗██║██║ ╚████║╚██████╔╝╚██████╔╝
  ╚═╝ ╚═╝ ╚══════╝╚═╝╚═╝ ╚═══╝ ╚═════╝ ╚═════╝
"""

# ─── ANSI color helpers ───────────────────────────────────────────
R ="\033[0m"
B ="\033[1m"
DIM="\033[2m"

def c(text, code): return f"\033[{code}m{text}{R}"
def green(t): return c(t,"92")
def yellow(t): return c(t,"93")
def red(t): return c(t,"91")
def blue(t): return c(t,"94")
def cyan(t): return c(t,"96")
def magenta(t): return c(t,"95")
def bold(t): return c(t,"1")
def dim(t): return c(t,"2")
def white(t): return c(t,"97")

def cls():
    os.system("cls" if os.name =="nt" else"clear")

def term_width():
    try:
        return os.get_terminal_size().columns
    except:
        return 80

def hr(char="─", color="94"):
    w = term_width()
    return c(char * w, color)

def center(text, fill=""):
    w = term_width()
    plain = re.sub(r'\033\[[0-9;]*m','', text)
    pad = max(0, (w - len(plain)) // 2)
    return fill * pad + text

def box(lines, title="", color="94", width=None):
    w = width or min(term_width() - 2, 72)
    tl,tr,bl,br ="╭","╮","╰","╯"
    h,v ="─","│"
    out = []
    if title:
        t = f" {title}"
        inner = w - 2
        left = (inner - len(re.sub(r'\033\[[0-9;]*m','',t))) // 2
        right = inner - left - len(re.sub(r'\033\[[0-9;]*m','',t))
        out.append(c(tl + h*left, color) + bold(t) + c(h*right + tr, color))
    else:
        out.append(c(tl + h*(w-2) + tr, color))
    for line in lines:
        plain_len = len(re.sub(r'\033\[[0-9;]*m','',line))
        pad = w - 2 - plain_len
        out.append(c(v,color) +"" + line +"" * max(0,pad-1) + c(v,color))
    out.append(c(bl + h*(w-2) + br, color))
    return"\n".join(out)

# ─── Logging ──────────────────────────────────────────────────────
_log_lock = threading.Lock()

def log(msg, level="info"):
    ts = datetime.now().strftime("%H:%M:%S")
    icons = {"info":"ℹ","success":"","warning":"","error":"","farm":"","stat":"◈"}
    colors= {"info":cyan,"success":green,"warning":yellow,"error":red,"farm":magenta,"stat":blue}
    icon = icons.get(level,"·")
    color = colors.get(level, white)
    with _log_lock:
        print(f" {dim(ts)} {color(icon)} {msg}")

def log_stat(label, value, unit=""):
    print(f" {dim('·')} {dim(label+':')} {bold(str(value))}{dim(''+unit) if unit else''}")


# ─── Arrow-key menu (curses, stdlib only) ─────────────────────────
import curses as _curses

def arrow_menu(title, options, subtitle=""):
    """Interactive arrow-key menu. Returns selected index or -1 on ESC/q.
    options: list of (label, description) tuples or list of strings.
    Works on Windows (curses via windows-curses) and Unix.
    Falls back to numbered prompt if curses unavailable."""

    items = []
    for o in options:
        if isinstance(o, (list, tuple)) and len(o) >= 2:
            items.append((str(o[0]), str(o[1])))
        else:
            items.append((str(o), ""))

    result = [-1]

    def _run(stdscr):
        _curses.curs_set(0)
        try:
            _curses.start_color()
            _curses.use_default_colors()
            _curses.init_pair(1, _curses.COLOR_CYAN,   -1)  # title / border
            _curses.init_pair(2, _curses.COLOR_WHITE,  -1)  # normal
            _curses.init_pair(3, _curses.COLOR_BLACK,  _curses.COLOR_CYAN)  # selected
            _curses.init_pair(4, _curses.COLOR_YELLOW, -1)  # description
            _curses.init_pair(5, _curses.COLOR_GREEN,  -1)  # subtitle
        except Exception:
            pass

        sel = 0
        while True:
            stdscr.erase()
            h, w = stdscr.getmaxyx()
            row = 1

            # Title bar
            t = f"  {title}  "
            stdscr.addstr(row, max(0, (w - len(t)) // 2), t[:w],
                          _curses.color_pair(1) | _curses.A_BOLD)
            row += 1

            if subtitle:
                s = f"  {subtitle}"
                stdscr.addstr(row, max(0, (w - len(s)) // 2), s[:w],
                              _curses.color_pair(5))
                row += 1

            sep = chr(0x2500) * w
            try:
                stdscr.addstr(row, 0, sep[:w], _curses.color_pair(1))
            except _curses.error:
                pass
            row += 1

            for i, (label, desc) in enumerate(items):
                if row >= h - 2:
                    break
                prefix = " > " if i == sel else "   "
                line   = f"{prefix}{label}"
                if i == sel:
                    attr = _curses.color_pair(3) | _curses.A_BOLD
                    try:
                        stdscr.addstr(row, 0, (line + " " * w)[:w], attr)
                    except _curses.error:
                        pass
                    if desc and row + 1 < h - 2:
                        row += 1
                        try:
                            stdscr.addstr(row, 0, f"     {desc}"[:w],
                                          _curses.color_pair(4))
                        except _curses.error:
                            pass
                else:
                    try:
                        stdscr.addstr(row, 0, line[:w], _curses.color_pair(2))
                    except _curses.error:
                        pass
                row += 1

            hint = "  [Up/Down] Navigate   [Enter] Select   [q/ESC] Back"
            try:
                stdscr.addstr(h - 1, 0, hint[:w])
            except _curses.error:
                pass
            stdscr.refresh()

            key = stdscr.getch()
            if key in (_curses.KEY_UP, ord('k')):
                sel = (sel - 1) % len(items)
            elif key in (_curses.KEY_DOWN, ord('j')):
                sel = (sel + 1) % len(items)
            elif key in (10, 13, _curses.KEY_ENTER):
                result[0] = sel
                return
            elif key in (27, ord('q'), ord('Q')):
                result[0] = -1
                return

    try:
        _curses.wrapper(_run)
    except Exception:
        # Plain fallback (e.g. in IDE / redirected stdin)
        cls()
        print(box([], title=title, color="94"))
        print()
        for i, (label, desc) in enumerate(items):
            suffix = f"  {dim(desc)}" if desc else ""
            print(f"  {bold(str(i+1)+'.')} {label}{suffix}")
        print(f"  {bold('0.')} {dim('Back')}")
        print()
        try:
            v = input(f"  {cyan('Select:')} ").strip()
            result[0] = int(v) - 1 if v.isdigit() and v != '0' else -1
        except (ValueError, KeyboardInterrupt):
            result[0] = -1

    return result[0]

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
        "Accept-Encoding":"gzip, deflate, br",
    }

def http_request(method, host, path, headers=None, body=None, use_ssl=True, timeout=30):
    """Pure stdlib HTTP request. Returns (status_code, response_text)."""
    try:
        conn_cls = http.client.HTTPSConnection if use_ssl else http.client.HTTPConnection
        conn = conn_cls(host, timeout=timeout)
        body_bytes = json.dumps(body).encode() if body else None
        conn.request(method, path, body=body_bytes, headers=headers or {})
        resp = conn.getresponse()
        # Read raw — handle gzip gracefully
        raw = resp.read()
        try:
            text = raw.decode("utf-8")
        except:
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
    return decode_jwt(token).get("sub")

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
    "id,username,fromLanguage,learningLanguage,streak,totalXp,gems,lingots,"
    "creationDate,streakData,trackingProperties,"
    "currentCourse{pathSectioned{units{levels{"
    "pathLevelMetadata{skillId},pathLevelClientData{skillId}"
    "}}}}"
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
    # Normalize creation date
    tp = data.get("trackingProperties", {})
    if tp.get("creation_date_new"):
        data["creationDate"] = tp["creation_date_new"]
    elif isinstance(data.get("creationDate"), (int, float)):
        data["creationDate"] = datetime.fromtimestamp(data["creationDate"]/1000).isoformat()
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
    log(f"Starting XP farm — {bold('Stories 499 XP')} mode (auto-fallback to 110 XP)","farm")
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
    print(box([
        f" {bold('Farm complete!')}",
        f" Mode : {bold(mode)}",
        f" Total : {green(str(total))} {unit}",
        f" Calls : {blue(str(calls))}",
        f" Errors : {yellow(str(errs))}",
        f" Runtime : {cyan(elapsed)}",
    ], title=" Session Summary", color="92"))
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
    print(box([
        f" Will farm {bold(green(str(to_farm)))} streak days",
        f" {current_streak} → {max_safe}",
        f" {dim('Ctrl+C to stop anytime')}",
    ], title=" Safe Streak Farm", color="92"))
    print()
    if input(f" {yellow('Confirm? (y/N):')}").strip().lower() !="y":
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
    log(f"{red('WARNING:')} Normal mode has higher ban risk!","warning")
    if input(f" {yellow('Confirm? (y/N):')}").strip().lower() !="y":
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
                print(f"\r {spinner_char(tick)} Rank: {bold('1')}"
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
        input(f" {dim('Press Enter to continue anyway...')}")

    if not items:
        log("No shop items available.","warning")
        input(f"\n {dim('Press Enter...')}")
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
        print(box([
            f" Account : {bold(green(account_name))}",
            f" Gems : {bold(cyan(str(user_info.get('gems','?'))))}",
            f" {dim('Items are acquired free (isFree=True) — no gems deducted')}",
        ], title=" Shop Items", color="93"))
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
        print(f" {bold('a.')} {green('Buy ALL items')}")
        print(f" {bold('0.')} {dim('← Back')}")
        print()
        choice = input(f" {cyan('Item # or (a)ll or 0:')}").strip().lower()

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
            input(f"\n {dim('Press Enter...')}")
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
                    input(f"\n {dim('Press Enter...')}")
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
            print(f"\n {red('')} Thread-{tid}: {dim(str(e))}")
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
    print(box([
        " Auto-generate Duolingo accounts.",
        f" {dim('Flow: guest → batch claim → lesson → stories XP')}",
        f" {dim('No API key needed — results saved to generated_accounts.json')}",
        "",
        f" {yellow('Based on DuoXPy Dex CLI source')}",
    ], title=" Generate Account", color="95"))
    print()

    # count
    try:
        v = input(f" {cyan('How many accounts? [default=1]:')}").strip()
        count = int(v) if v else 1
        if count < 1 or count > 500:
            log("Count must be 1–500.","error")
            input(f"\n {dim('Press Enter...')}")
            return
    except ValueError:
        log("Invalid number.","error")
        input(f"\n {dim('Press Enter...')}")
        return

    # threads
    try:
        v = input(f" {cyan('Threads (parallel, 1–10) [default=1]:')}").strip()
        threads = max(1, min(10, int(v) if v else 1))
    except ValueError:
        threads = 1

    # delay
    try:
        v = input(f" {cyan('Delay per thread (ms) [default=2000]:')}").strip()
        delay_ms = max(0, int(v) if v else 2000)
    except ValueError:
        delay_ms = 2000

    # farm stories option
    farm_stories = True
    v = input(f" {cyan('Farm stories XP after creation? (Y/n) [default=Y]:')}").strip().lower()
    if v =="n":
        farm_stories = False

    story_count = 10
    if farm_stories:
        try:
            v = input(f" {cyan('Story runs per account [default=10]:')}").strip()
            story_count = max(1, min(50, int(v) if v else 10))
        except ValueError:
            story_count = 10

    print()
    print(box([
        f" Accounts : {bold(green(str(count)))}",
        f" Threads : {bold(cyan(str(threads)))}",
        f" Delay : {bold(yellow(str(delay_ms)))} ms / thread",
        f" Farm stories : {bold(green('Yes') if farm_stories else dim('No'))}",
        f" Story runs : {bold(str(story_count)) if farm_stories else dim('—')}",
        f" Output : {dim('generated_accounts.json')}",
    ], title=" Config", color="96"))
    print()
    if input(f" {yellow('Start? (y/N):')}").strip().lower() !="y":
        log("Cancelled.","info")
        input(f"\n {dim('Press Enter...')}")
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
    print(box([
        f" {bold('Done!')}",
        f" Requested : {bold(str(count))}",
        f" {green('')} Success : {bold(green(str(len(final_ok))))}",
        f" {red('')} Failed : {(red(str(final_fail))) if final_fail else dim('0')}",
        f" Runtime : {cyan(f'{elapsed_total:.1f}s')}",
        f" Saved to : {dim(GENERATED_FILE)}",
    ], title=" Summary", color="92"))
    print()

    if final_ok and input(f" {cyan('Show accounts? (y/N):')}").strip().lower() =="y":
        print()
        for i, a in enumerate(final_ok, 1):
            print(box([
                f" {bold(f'#{i}')}",
                f" User ID : {dim(str(a['_id']))}",
                f" Username : {green(a['username'])}",
                f" Email : {cyan(a['email'])}",
                f" Password : {yellow(a['password'])}",
                f" XP : {blue(str(a.get('xp',0)))}",
                f" JWT : {dim(a['jwt'][:48] +'...')}",
            ], title=f"Account {i}", color="95", width=70))
            print()

    input(f" {dim('Press Enter to continue...')}")


# ─── Account management ───────────────────────────────────────────
def add_account():
    cls()
    print(box([
        " Paste your Duolingo JWT token below.",
        f" {dim('Get it from browser console:')}",
        f" {yellow('document.cookie.match(/jwt_token=([^;]+)/)[1]')}",
    ], title=" Add Account", color="94"))
    print()
    jwt = input(f" {cyan('JWT Token:')}").strip().strip("'\"")
    if not jwt:
        log("No token entered.","warning")
        return

    if jwt_expired(jwt):
        log("This JWT token is already expired!","error")
        return

    try:
        sub = jwt_sub(jwt)
    except ValueError as e:
        log(str(e),"error")
        return

    if not sub:
        log("Cannot extract user ID from token.","error")
        return

    log("Fetching account info...","info")
    try:
        info = get_user_info(jwt, sub)
    except Exception as e:
        log(str(e),"error")
        return

    accounts = load_accounts()
    # Check duplicate
    for acc in accounts:
        if acc.get("sub") == str(sub):
            acc["jwt"] = jwt
            acc["info"] = info
            save_accounts(accounts)
            log(f"Updated account: {bold(green(info.get('username','?')))}","success")
            return

    accounts.append({"sub": str(sub),"jwt": jwt,"info": info,"added": datetime.now().isoformat()})
    save_accounts(accounts)
    print()
    log(f"Account added: {bold(green(info.get('username','?')))}","success")
    log(f"Streak: {yellow(str(info.get('streak',0)))} | XP: {blue(str(info.get('totalXp',0)))} | Gems: {cyan(str(info.get('gems',0)))}","stat")
    log(f"Token expires: {dim(jwt_expires_at(jwt))}","info")
    input(f"\n {dim('Press Enter to continue...')}")

def list_accounts():
    accounts = load_accounts()
    if not accounts:
        log("No accounts saved. Use'Add Account' to add one.","warning")
        return
    print()
    for i, acc in enumerate(accounts, 1):
        info = acc.get("info", {})
        exp = jwt_expired(acc.get("jwt",""))
        status_icon = red(" expired") if exp else green(" active")
        print(f" {bold(str(i))}. {bold(green(info.get('username','?')))}")
        print(f" {dim('ID:')} {acc.get('sub','?')} │ {status_icon}")
        print(f" {yellow(str(info.get('streak',0)))} streak"
              f"│ {blue(str(info.get('totalXp',0)))} XP"
              f"│ {cyan(str(info.get('gems',0)))} gems")
        print(f" {dim('Expires:')} {dim(jwt_expires_at(acc.get('jwt','')))}")
        print()

def remove_account():
    accounts = load_accounts()
    if not accounts:
        log("No accounts saved.","warning")
        return
    list_accounts()
    try:
        idx = int(input(f" {cyan('Account number to remove:')}")) - 1
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
        idx = int(input(f" {cyan('Select account:')}")) - 1
        return accounts[idx]
    except (ValueError, IndexError):
        log("Invalid selection.","error")
        return None

# ─── Info / Status ────────────────────────────────────────────────
def show_account_info(acc):
    info = acc.get("info", {})
    jwt = acc.get("jwt","")
    cls()
    exp = jwt_expired(jwt)
    username = info.get("username","?")
    lines = [
        f" {bold(green(username))}",
        f" {dim('ID:')} {acc.get('sub','?')}",
        "",
        f" Streak : {bold(yellow(str(info.get('streak',0))))} days",
        f" Total XP: {bold(blue(str(info.get('totalXp',0))))}",
        f" Gems : {bold(cyan(str(info.get('gems',0))))}",
        f" Learning: {info.get('fromLanguage','?')} → {info.get('learningLanguage','?')}",
        "",
        f" Token : {red('EXPIRED') if exp else green('valid')}",
        f" ⏳ Expires : {dim(jwt_expires_at(jwt))}",
        f" Account : {dim(str(info.get('creationDate','?'))[:10])}",
    ]
    print(box(lines, title=f" {username}", color="94", width=60))
    print()
    input(f" {dim('Press Enter to continue...')}")

# ─── UI menus ─────────────────────────────────────────────────────
def get_delay():
    try:
        val = int(input(f" {cyan('Delay between requests (ms) [default=1500]:')}") or"1500")
        return max(200, val)
    except ValueError:
        return 1500

def farm_menu():
    cls()
    acc = select_account()
    if not acc: return
    if jwt_expired(acc.get("jwt","")):
        log("JWT expired. Please re-add this account.","error")
        input(f"\n {dim('Press Enter...')}")
        return

    print()
    log(f"Refreshing account info for {bold(acc.get('info',{}).get('username','?'))}...","info")
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
        input(f"\n  {dim('Press Enter to continue...')}")

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
            input(f"\n  {dim('Press Enter...')}")
        elif choice == 2:
            cls()
            remove_account()
            input(f"\n  {dim('Press Enter...')}")
        elif choice == 3:
            acc = select_account()
            if acc:
                show_account_info(acc)
        elif choice in (-1, 4):
            return

def settings_menu():
    OPTS = [
        ("Clear all accounts", "Delete every saved account from disk"),
        ("Show accounts file", "Print the path to accounts.json"),
        ("Back",               ""),
    ]
    while True:
        choice = arrow_menu("Settings", OPTS, subtitle=f"File: {ACCOUNTS_FILE}")
        if choice == 0:
            cls()
            confirm = input(f"  {red('Type YES to confirm delete all accounts:')} ").strip()
            if confirm == "YES":
                save_accounts([])
                log("All accounts cleared.", "success")
            else:
                log("Cancelled.", "info")
            input(f"  {dim('Press Enter...')}")
        elif choice == 1:
            log(f"Accounts file: {ACCOUNTS_FILE}", "info")
            input(f"  {dim('Press Enter...')}")
        elif choice in (-1, 2):
            return

        input(f" {dim('Press Enter...')}")

def check_streak_status():
    """Check & auto-protect streak for all accounts."""
    cls()
    accounts = load_accounts()
    if not accounts:
        log("No accounts saved.","warning")
        input(f"\n {dim('Press Enter...')}")
        return

    print(box([" Checking streak status for all accounts..."], title=" Streak Status", color="93"))
    print()

    for acc in accounts:
        info = acc.get("info", {})
        username = info.get("username", acc.get("sub","?"))
        if jwt_expired(acc.get("jwt","")):
            log(f"{username}: {red('JWT expired')}","error")
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

    input(f"\n {dim('Press Enter to continue...')}")

# ─── Main menu ────────────────────────────────────────────────────
def main_menu():
    OPTS = [
        ("Farm",             "XP / Gems / Streak / Mixed / Quest / League"),
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
        if n_acc:
            sub_line = (f"{n_acc} account(s) — {n_exp} expired"
                        if n_exp else f"{n_acc} account(s) — all active")
        else:
            sub_line = "No accounts saved — add one first"

        cls()
        print(center(magenta(BANNER_ART)))
        print(center(f"{bold('PyLingo')}  {dim('v'+VERSION)}  {dim('─')}  {dim('Duolingo farming tool')}"))
        print()

        idx = arrow_menu("Main Menu", OPTS, subtitle=sub_line)

        if idx == 0:
            farm_menu()
        elif idx == 1:
            accounts_menu()
        elif idx == 2:
            acc = select_account()
            if acc:
                shop_items_menu(acc)
        elif idx == 3:
            generate_accounts_menu()
        elif idx == 4:
            check_streak_status()
        elif idx == 5:
            settings_menu()
        elif idx in (6, -1):
            cls()
            print(center(f"\n  {bold(green('Goodbye!'))}  {dim('PyLingo v'+VERSION)}\n"))
            sys.exit(0)

# ─── Entry point ─────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print()
        log("Interrupted. Goodbye.", "info")
        sys.exit(0)
