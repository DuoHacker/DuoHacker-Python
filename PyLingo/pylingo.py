#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════
#   PyLingo — Duolingo XP / Gem / Streak Farming Tool
#   Pure Python stdlib only · Terminal UI with ANSI
# ═══════════════════════════════════════════════════════════════════

import os, sys, json, time, base64, threading, http.client, urllib.parse
import signal, math, random, re
from datetime import datetime, timezone

VERSION = "1.0.0"
BANNER_ART = r"""
  ██████╗ ██╗   ██╗██╗     ██╗███╗   ██╗ ██████╗  ██████╗
  ██╔══██╗╚██╗ ██╔╝██║     ██║████╗  ██║██╔════╝ ██╔═══██╗
  ██████╔╝ ╚████╔╝ ██║     ██║██╔██╗ ██║██║  ███╗██║   ██║
  ██╔═══╝   ╚██╔╝  ██║     ██║██║╚██╗██║██║   ██║██║   ██║
  ██║        ██║   ███████╗██║██║ ╚████║╚██████╔╝╚██████╔╝
  ╚═╝        ╚═╝   ╚══════╝╚═╝╚═╝  ╚═══╝ ╚═════╝  ╚═════╝
"""

# ─── ANSI color helpers ───────────────────────────────────────────
R  = "\033[0m"
B  = "\033[1m"
DIM= "\033[2m"

def c(text, code): return f"\033[{code}m{text}{R}"
def green(t):   return c(t, "92")
def yellow(t):  return c(t, "93")
def red(t):     return c(t, "91")
def blue(t):    return c(t, "94")
def cyan(t):    return c(t, "96")
def magenta(t): return c(t, "95")
def bold(t):    return c(t, "1")
def dim(t):     return c(t, "2")
def white(t):   return c(t, "97")

def cls():
    os.system("cls" if os.name == "nt" else "clear")

def term_width():
    try:
        return os.get_terminal_size().columns
    except:
        return 80

def hr(char="─", color="94"):
    w = term_width()
    return c(char * w, color)

def center(text, fill=" "):
    w = term_width()
    plain = re.sub(r'\033\[[0-9;]*m', '', text)
    pad = max(0, (w - len(plain)) // 2)
    return fill * pad + text

def box(lines, title="", color="94", width=None):
    w = width or min(term_width() - 2, 72)
    tl,tr,bl,br = "╭","╮","╰","╯"
    h,v = "─","│"
    out = []
    if title:
        t = f" {title} "
        inner = w - 2
        left  = (inner - len(re.sub(r'\033\[[0-9;]*m','',t))) // 2
        right = inner - left - len(re.sub(r'\033\[[0-9;]*m','',t))
        out.append(c(tl + h*left, color) + bold(t) + c(h*right + tr, color))
    else:
        out.append(c(tl + h*(w-2) + tr, color))
    for line in lines:
        plain_len = len(re.sub(r'\033\[[0-9;]*m','',line))
        pad = w - 2 - plain_len
        out.append(c(v,color) + " " + line + " " * max(0,pad-1) + c(v,color))
    out.append(c(bl + h*(w-2) + br, color))
    return "\n".join(out)

# ─── Logging ──────────────────────────────────────────────────────
_log_lock = threading.Lock()

def log(msg, level="info"):
    ts = datetime.now().strftime("%H:%M:%S")
    icons = {"info":"ℹ","success":"✓","warning":"⚠","error":"✗","farm":"⚡","stat":"◈"}
    colors= {"info":cyan,"success":green,"warning":yellow,"error":red,"farm":magenta,"stat":blue}
    icon  = icons.get(level,"·")
    color = colors.get(level, white)
    with _log_lock:
        print(f"  {dim(ts)}  {color(icon)}  {msg}")

def log_stat(label, value, unit=""):
    print(f"  {dim('·')}  {dim(label+':')}  {bold(str(value))}{dim(' '+unit) if unit else ''}")

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
        "Content-Type":    "application/json",
        "Accept":          "application/json",
        "Authorization":   f"Bearer {jwt}",
        "User-Agent":      random_ua(),
        "x-amzn-trace-id": f"User={sub}" if sub else "User=0",
        "Cookie":          f"jwt_token={jwt}",
        "Origin":          "https://www.duolingo.com",
        "Referer":         "https://www.duolingo.com/",
        "Host":            "www.duolingo.com",
        "Accept-Encoding": "gzip, deflate, br",
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
        payload += "=" * (4 - len(payload) % 4)
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
        return "unknown"
    except:
        return "unknown"

# ─── Account store (accounts.json) ───────────────────────────────
ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__), "accounts.json")

def load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE) as f:
                return json.load(f)
        except:
            pass
    return []

def save_accounts(accounts):
    with open(ACCOUNTS_FILE, "w") as f:
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
        "fromLanguage": user_info["fromLanguage"],
        "learningLanguage": user_info["learningLanguage"],
        "hasXpBoost": False,
        "illustrationFormat": "svg",
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
    headers["Host"] = "stories.duolingo.com"
    headers["Origin"] = "https://stories.duolingo.com"
    status, _ = http_request(
        "POST", "stories.duolingo.com",
        "/api2/stories/fr-en-le-passeport/complete",
        headers, body
    )
    return status

def farm_xp_once_unit(jwt, sub, user_info, skill_id):
    """UNIT_TEST session — ~110 XP per call."""
    # Step 1: Create session
    body = {
        "challengeTypes": [],
        "fromLanguage": user_info["fromLanguage"],
        "learningLanguage": user_info["learningLanguage"],
        "type": "UNIT_TEST",
        "skillIds": [skill_id],
    }
    status, session = duo_post("/2017-06-30/sessions", jwt, sub, body)
    if status != 200 or not session.get("id"):
        return False, 0

    start = int(time.time())
    update_body = {
        "id": session["id"],
        "metadata": session.get("metadata", {}),
        "type": "UNIT_TEST",
        "fromLanguage": user_info["fromLanguage"],
        "learningLanguage": user_info["learningLanguage"],
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
    reward_id = "SKILL_COMPLETION_BALANCED-dd2495f4_d44e_3fc3_8ac8_94e2191506f0-2-GEMS"
    path = f"/2023-05-23/users/{sub}/rewards/{reward_id}"
    body = {
        "consumed": True,
        "learningLanguage": user_info["learningLanguage"],
        "fromLanguage": user_info["fromLanguage"],
    }
    status, _ = duo_patch(path, jwt, sub, body)
    return status == 200, 30 if status == 200 else 0

def farm_session_once(jwt, sub, user_info, start_ts, end_ts):
    """GLOBAL_PRACTICE session — used for streak farming."""
    challenge_types = [
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
    session_body = {
        "challengeTypes": challenge_types,
        "fromLanguage": user_info["fromLanguage"],
        "isFinalLevel": False,
        "isV2": True,
        "juicy": True,
        "learningLanguage": user_info["learningLanguage"],
        "smartTipsVersion": 2,
        "type": "GLOBAL_PRACTICE",
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

# ─── Progress bar ─────────────────────────────────────────────────
def progress_bar(current, total, width=30, label=""):
    if total <= 0: total = 1
    pct = min(current / total, 1.0)
    filled = int(width * pct)
    bar = green("█" * filled) + dim("░" * (width - filled))
    pct_str = f"{pct*100:.1f}%"
    return f"  [{bar}] {bold(pct_str)}  {dim(label)}"

def spinner_char(tick):
    return ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"][tick % 10]

# ─── Farm session state ───────────────────────────────────────────
class FarmState:
    def __init__(self):
        self.running   = False
        self.xp_earned = 0
        self.gem_earned= 0
        self.streak_farmed = 0
        self.errors    = 0
        self.start_time= None
        self.calls     = 0

    def reset(self):
        self.running = False
        self.xp_earned = 0
        self.gem_earned = 0
        self.streak_farmed = 0
        self.errors = 0
        self.start_time = None
        self.calls = 0

    def elapsed(self):
        if not self.start_time: return "00:00"
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
    fallback_errors  = 0
    MAX_429  = 2
    MAX_ERR  = 5
    tick = 0

    print()
    log(f"Starting XP farm — {bold('Stories 499 XP')} mode (auto-fallback to 110 XP)", "farm")
    log(f"Delay: {delay_ms}ms | Skill ID: {green(skill_id) if skill_id else red('none')}", "info")
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
                log(f"Stories rate-limited (429) [{consecutive_429}/{MAX_429}]", "warning")
                if consecutive_429 >= MAX_429:
                    log("Switching to UNIT_TEST fallback (110 XP)", "info")
                time.sleep(delay_ms / 1000 * 2)
                continue
            else:
                log(f"Stories returned {status}, switching to UNIT_TEST", "warning")
                use_stories = False
        else:
            if not skill_id:
                log("No skill ID — cannot use UNIT_TEST fallback. Stopping.", "error")
                break
            ok, earned = farm_xp_once_unit(jwt, sub, user_info, skill_id)
            if ok:
                fallback_errors = 0
                state.xp_earned += earned; state.calls += 1
                _xp_tick(earned, tick)
            else:
                fallback_errors += 1
                state.errors += 1
                log(f"UNIT_TEST error ({fallback_errors}/{MAX_ERR})", "warning")
                if fallback_errors >= MAX_ERR:
                    log("Too many errors — stopping farm.", "error")
                    break
                time.sleep(delay_ms / 1000 * 3)
                continue

        time.sleep(delay_ms / 1000)

    state.running = False
    _farm_summary("XP", state.xp_earned, "XP")

def _xp_tick(earned, tick):
    rate = state.xp_earned / max(1, time.time() - state.start_time) * 3600
    print(f"\r  {spinner_char(tick)} {green(f'+{earned} XP')}  │  "
          f"Total: {bold(str(state.xp_earned))} XP  │  "
          f"Rate: {cyan(f'{rate:.0f} XP/hr')}  │  "
          f"Time: {dim(state.elapsed())}      ", end="", flush=True)

# ─── Gem Farm ─────────────────────────────────────────────────────
def farm_gems(jwt, sub, user_info, delay_ms, batch=3):
    state.running = True
    state.start_time = time.time()
    consecutive_errors = 0
    MAX_ERRORS = 5
    tick = 0

    print()
    log(f"Starting Gem farm — batch={bold(str(batch))} | delay={bold(f'{delay_ms}ms')}", "farm")
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
                log("\nToo many errors — stopping gem farm.", "error")
                break
            time.sleep(delay_ms / 1000 * 3)
            continue

        time.sleep(delay_ms / 1000)

    state.running = False
    _farm_summary("Gems", state.gem_earned, "💎")

def _gem_tick(earned, tick):
    rate = state.gem_earned / max(1, time.time() - state.start_time) * 3600
    print(f"\r  {spinner_char(tick)} {cyan(f'+{earned} 💎')}  │  "
          f"Total: {bold(str(state.gem_earned))} gems  │  "
          f"Rate: {green(f'{rate:.0f}/hr')}  │  "
          f"Time: {dim(state.elapsed())}      ", end="", flush=True)

# ─── Streak Farm ─────────────────────────────────────────────────
def farm_streak_safe(jwt, sub, user_info, delay_ms):
    """Farm streak safely — limited to account age."""
    creation = user_info.get("creationDate")
    if not creation:
        log("Cannot determine account creation date.", "error")
        return

    try:
        if isinstance(creation, (int, float)):
            creation_dt = datetime.fromtimestamp(creation/1000)
        else:
            creation_dt = datetime.fromisoformat(str(creation).split("T")[0])
    except Exception as e:
        log(f"Cannot parse creation date: {e}", "error")
        return

    now_dt = datetime.now()
    account_age_days = (now_dt - creation_dt).days
    current_streak   = user_info.get("streak", 0)
    max_safe_streak  = account_age_days

    print()
    log(f"Account created : {green(creation_dt.strftime('%Y-%m-%d'))}", "stat")
    log(f"Account age     : {green(str(account_age_days))} days", "stat")
    log(f"Current streak  : {yellow(str(current_streak))} days", "stat")
    log(f"Max safe streak : {green(str(max_safe_streak))} days", "stat")
    print()

    if current_streak >= max_safe_streak:
        log(f"Already at max safe streak ({current_streak}/{max_safe_streak})!", "success")
        return

    to_farm = max_safe_streak - current_streak
    print(box([
        f"  Will farm {bold(green(str(to_farm)))} streak days",
        f"  {current_streak} → {max_safe_streak}",
        f"  {dim('Press Ctrl+C to stop anytime')}",
    ], title="⚡ Safe Streak Farm", color="92"))
    print()

    confirm = input(f"  {yellow('Confirm? (y/N): ')}").strip().lower()
    if confirm != "y":
        log("Cancelled.", "info")
        return

    state.running    = True
    state.start_time = time.time()
    creation_ts = int(creation_dt.timestamp())
    current_ts  = int(now_dt.timestamp())
    farm_ts     = creation_ts
    farmed      = 0
    tick        = 0

    print()
    while state.running and farm_ts <= current_ts and farmed < to_farm:
        tick += 1
        ok = farm_session_once(jwt, sub, user_info, farm_ts, farm_ts + 60)
        if ok:
            farm_ts  += 86400
            farmed   += 1
            state.streak_farmed += 1
            current_streak += 1
            state.calls += 1
            pct = farmed / to_farm
            bar = green("█" * int(30*pct)) + dim("░" * (30 - int(30*pct)))
            print(f"\r  {spinner_char(tick)} [{bar}] "
                  f"{bold(f'{farmed}/{to_farm}')}  🔥 Streak: {bold(str(current_streak))}  "
                  f"Time: {dim(state.elapsed())}      ", end="", flush=True)
        else:
            state.errors += 1
            log(f"\nSession failed at day {farmed+1}, retrying...", "warning")
            time.sleep(1)
            continue

        time.sleep(delay_ms / 1000)

    state.running = False
    print()
    _farm_summary("Streak", state.streak_farmed, "🔥 days")

def farm_streak_normal(jwt, sub, user_info, delay_ms):
    """Normal streak farm — goes backwards from current streak start."""
    print()
    log(f"{red('WARNING:')} Normal mode has higher ban risk!", "warning")
    confirm = input(f"  {yellow('Confirm? (y/N): ')}").strip().lower()
    if confirm != "y":
        log("Cancelled.", "info")
        return

    streak_data = user_info.get("streakData", {})
    has_streak  = bool(streak_data.get("currentStreak"))
    if has_streak:
        start_date = streak_data["currentStreak"].get("startDate", datetime.now().isoformat())
        start_ts = int(datetime.fromisoformat(str(start_date).split("T")[0]).timestamp())
        farm_ts  = start_ts - 86400
    else:
        farm_ts = int(datetime.now().timestamp())

    state.running = True
    state.start_time = time.time()
    tick = 0

    print()
    while state.running:
        tick += 1
        ok = farm_session_once(jwt, sub, user_info, farm_ts, farm_ts + 60)
        if ok:
            farm_ts -= 86400
            state.streak_farmed += 1
            state.calls += 1
            current = user_info.get("streak",0) + state.streak_farmed
            print(f"\r  {spinner_char(tick)} {red('🔥')} Streak: {bold(str(current))}  │  "
                  f"Farmed: {bold(str(state.streak_farmed))}  │  "
                  f"Time: {dim(state.elapsed())}      ", end="", flush=True)
        else:
            state.errors += 1

        time.sleep(delay_ms / 1000)

    print()
    _farm_summary("Streak", state.streak_farmed, "🔥 days")

def _farm_summary(mode, total, unit):
    elapsed = state.elapsed()
    calls   = state.calls
    errs    = state.errors
    print("\n")
    print(box([
        f"  {bold('Farm complete!')}",
        f"  Mode    : {bold(mode)}",
        f"  Total   : {green(str(total))} {unit}",
        f"  Calls   : {blue(str(calls))}",
        f"  Errors  : {yellow(str(errs))}",
        f"  Runtime : {cyan(elapsed)}",
    ], title="📊 Session Summary", color="92"))
    print()

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
    log("Starting MIXED farm — XP + Gems alternating", "farm")
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
        xp_rate  = state.xp_earned  / max(1, time.time()-state.start_time) * 3600
        gem_rate = state.gem_earned / max(1, time.time()-state.start_time) * 3600
        print(f"\r  {spinner_char(tick)}  "
              f"XP: {green(str(state.xp_earned))} ({cyan(f'{xp_rate:.0f}/hr')})  │  "
              f"Gems: {cyan(str(state.gem_earned))} ({green(f'{gem_rate:.0f}/hr')})  │  "
              f"Time: {dim(state.elapsed())}      ", end="", flush=True)

        time.sleep(delay_ms / 1000)

    print()
    state.running = False
    _farm_summary("Mixed (XP+Gems)", f"{state.xp_earned} XP | {state.gem_earned} Gems", "")

# ─── Account management ───────────────────────────────────────────
def add_account():
    cls()
    print(box([
        "  Paste your Duolingo JWT token below.",
        f"  {dim('Get it from browser console:')}",
        f"  {yellow('document.cookie.match(/jwt_token=([^;]+)/)[1]')}",
    ], title="➕ Add Account", color="94"))
    print()
    jwt = input(f"  {cyan('JWT Token:')} ").strip().strip("'\"")
    if not jwt:
        log("No token entered.", "warning")
        return

    if jwt_expired(jwt):
        log("This JWT token is already expired!", "error")
        return

    try:
        sub = jwt_sub(jwt)
    except ValueError as e:
        log(str(e), "error")
        return

    if not sub:
        log("Cannot extract user ID from token.", "error")
        return

    log("Fetching account info...", "info")
    try:
        info = get_user_info(jwt, sub)
    except Exception as e:
        log(str(e), "error")
        return

    accounts = load_accounts()
    # Check duplicate
    for acc in accounts:
        if acc.get("sub") == str(sub):
            acc["jwt"]  = jwt
            acc["info"] = info
            save_accounts(accounts)
            log(f"Updated account: {bold(green(info.get('username','?')))}", "success")
            return

    accounts.append({"sub": str(sub), "jwt": jwt, "info": info, "added": datetime.now().isoformat()})
    save_accounts(accounts)
    print()
    log(f"Account added: {bold(green(info.get('username','?')))}", "success")
    log(f"Streak: {yellow(str(info.get('streak',0)))} | XP: {blue(str(info.get('totalXp',0)))} | Gems: {cyan(str(info.get('gems',0)))}", "stat")
    log(f"Token expires: {dim(jwt_expires_at(jwt))}", "info")
    input(f"\n  {dim('Press Enter to continue...')}")

def list_accounts():
    accounts = load_accounts()
    if not accounts:
        log("No accounts saved. Use 'Add Account' to add one.", "warning")
        return
    print()
    for i, acc in enumerate(accounts, 1):
        info = acc.get("info", {})
        exp  = jwt_expired(acc.get("jwt",""))
        status_icon = red("✗ expired") if exp else green("✓ active")
        print(f"  {bold(str(i))}. {bold(green(info.get('username','?')))}")
        print(f"     {dim('ID:')} {acc.get('sub','?')}  │  {status_icon}")
        print(f"     🔥 {yellow(str(info.get('streak',0)))} streak  "
              f"│  ⚡ {blue(str(info.get('totalXp',0)))} XP  "
              f"│  💎 {cyan(str(info.get('gems',0)))} gems")
        print(f"     {dim('Expires:')} {dim(jwt_expires_at(acc.get('jwt','')))}")
        print()

def remove_account():
    accounts = load_accounts()
    if not accounts:
        log("No accounts saved.", "warning")
        return
    list_accounts()
    try:
        idx = int(input(f"  {cyan('Account number to remove:')} ")) - 1
        removed = accounts.pop(idx)
        save_accounts(accounts)
        log(f"Removed: {bold(removed.get('info',{}).get('username','?'))}", "success")
    except (ValueError, IndexError):
        log("Invalid selection.", "error")

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
        log("Account info refreshed.", "success")
        return info
    except Exception as e:
        log(f"Refresh failed: {e}", "error")
        return acc.get("info", {})

def select_account():
    accounts = load_accounts()
    if not accounts:
        log("No accounts saved.", "warning")
        return None
    if len(accounts) == 1:
        return accounts[0]

    print()
    list_accounts()
    try:
        idx = int(input(f"  {cyan('Select account:')} ")) - 1
        return accounts[idx]
    except (ValueError, IndexError):
        log("Invalid selection.", "error")
        return None

# ─── Info / Status ────────────────────────────────────────────────
def show_account_info(acc):
    info = acc.get("info", {})
    jwt  = acc.get("jwt", "")
    cls()
    exp  = jwt_expired(jwt)
    username = info.get("username","?")
    lines = [
        f"  👤  {bold(green(username))}",
        f"  {dim('ID:')} {acc.get('sub','?')}",
        "",
        f"  🔥 Streak  : {bold(yellow(str(info.get('streak',0))))} days",
        f"  ⚡ Total XP: {bold(blue(str(info.get('totalXp',0))))}",
        f"  💎 Gems    : {bold(cyan(str(info.get('gems',0))))}",
        f"  📚 Learning: {info.get('fromLanguage','?')} → {info.get('learningLanguage','?')}",
        "",
        f"  🔑 Token   : {red('EXPIRED') if exp else green('valid')}",
        f"  ⏳ Expires : {dim(jwt_expires_at(jwt))}",
        f"  📅 Account : {dim(str(info.get('creationDate','?'))[:10])}",
    ]
    print(box(lines, title=f"👤 {username}", color="94", width=60))
    print()
    input(f"  {dim('Press Enter to continue...')}")

# ─── UI menus ─────────────────────────────────────────────────────
def get_delay():
    try:
        val = int(input(f"  {cyan('Delay between requests (ms) [default=1500]:')} ") or "1500")
        return max(200, val)
    except ValueError:
        return 1500

def farm_menu():
    cls()
    acc = select_account()
    if not acc: return
    if jwt_expired(acc.get("jwt","")):
        log("JWT expired. Please re-add this account.", "error")
        input(f"\n  {dim('Press Enter...')}")
        return

    print()
    log(f"Refreshing account info for {bold(acc.get('info',{}).get('username','?'))}...", "info")
    info = refresh_account(acc)
    skill_id = extract_skill_id(info.get("currentCourse"))

    while True:
        cls()
        print(box([
            f"  Account: {bold(green(info.get('username','?')))}",
            f"  🔥 {yellow(str(info.get('streak',0)))} streak  │  "
            f"⚡ {blue(str(info.get('totalXp',0)))} XP  │  "
            f"💎 {cyan(str(info.get('gems',0)))} gems",
            f"  Skill ID: {green(skill_id) if skill_id else red('none')}",
        ], title="⚡ Farm Menu", color="93"))
        print()
        print(f"  {bold('1.')} {yellow('⚡ XP Farm')}         {dim('(Stories 499 XP → UNIT_TEST fallback)')}")
        print(f"  {bold('2.')} {cyan('💎 Gem Farm')}         {dim('(Reward endpoint, ~30 gems/call)')}")
        print(f"  {bold('3.')} {green('🔥 Streak Farm — Safe')}  {dim('(Capped to account age)')}")
        print(f"  {bold('4.')} {yellow('🔥 Streak Farm — Normal')} {dim('(No limit, higher risk)')}")
        print(f"  {bold('5.')} {magenta('✨ Mixed Farm')}       {dim('(XP + Gems together)')}")
        print(f"  {bold('0.')} {dim('← Back')}")
        print()
        choice = input(f"  {cyan('Choice:')} ").strip()

        if choice == "0":
            return

        state.reset()
        delay = get_delay()

        def stop_on_ctrl_c(sig, frame):
            state.running = False
            print()
            log("Stopping farm...", "warning")
        signal.signal(signal.SIGINT, stop_on_ctrl_c)

        try:
            if choice == "1":
                farm_xp(acc["jwt"], acc["sub"], info, delay)
            elif choice == "2":
                farm_gems(acc["jwt"], acc["sub"], info, delay)
            elif choice == "3":
                farm_streak_safe(acc["jwt"], acc["sub"], info, delay)
            elif choice == "4":
                farm_streak_normal(acc["jwt"], acc["sub"], info, delay)
            elif choice == "5":
                farm_mixed(acc["jwt"], acc["sub"], info, delay)
        except KeyboardInterrupt:
            state.running = False
            print()
            log("Farm stopped by user.", "warning")

        signal.signal(signal.SIGINT, signal.SIG_DFL)
        input(f"\n  {dim('Press Enter to continue...')}")

def accounts_menu():
    while True:
        cls()
        accounts = load_accounts()
        print(box([
            f"  Saved accounts: {bold(str(len(accounts)))}",
        ], title="🗄️  Account Manager", color="94"))
        print()
        print(f"  {bold('1.')} ➕ Add account (JWT token)")
        print(f"  {bold('2.')} 📋 List accounts")
        print(f"  {bold('3.')} ❌ Remove account")
        print(f"  {bold('4.')} 👤 View account info")
        print(f"  {bold('0.')} {dim('← Back')}")
        print()
        choice = input(f"  {cyan('Choice:')} ").strip()
        if choice == "1": add_account()
        elif choice == "2":
            list_accounts()
            input(f"\n  {dim('Press Enter...')}")
        elif choice == "3":
            remove_account()
            input(f"\n  {dim('Press Enter...')}")
        elif choice == "4":
            acc = select_account()
            if acc: show_account_info(acc)
        elif choice == "0":
            return

def settings_menu():
    while True:
        cls()
        print(box([
            "  PyLingo settings",
            "",
            f"  {dim('Accounts file:')} {ACCOUNTS_FILE}",
        ], title="⚙️  Settings", color="96"))
        print()
        print(f"  {bold('1.')} 🗑️  Clear all accounts")
        print(f"  {bold('2.')} 📁 Show accounts file path")
        print(f"  {bold('0.')} {dim('← Back')}")
        print()
        choice = input(f"  {cyan('Choice:')} ").strip()
        if choice == "1":
            confirm = input(f"  {red('Delete ALL accounts? (yes/N):')} ").strip().lower()
            if confirm == "yes":
                save_accounts([])
                log("All accounts cleared.", "success")
        elif choice == "2":
            log(f"File: {ACCOUNTS_FILE}", "info")
        elif choice == "0":
            return
        input(f"  {dim('Press Enter...')}")

def check_streak_status():
    """Check & auto-protect streak for all accounts."""
    cls()
    accounts = load_accounts()
    if not accounts:
        log("No accounts saved.", "warning")
        input(f"\n  {dim('Press Enter...')}")
        return

    print(box(["  Checking streak status for all accounts..."], title="🔥 Streak Status", color="93"))
    print()

    for acc in accounts:
        info = acc.get("info", {})
        username = info.get("username", acc.get("sub","?"))
        if jwt_expired(acc.get("jwt","")):
            log(f"{username}: {red('JWT expired')}", "error")
            continue
        try:
            info = get_user_info(acc["jwt"], acc["sub"])
        except Exception as e:
            log(f"{username}: {red(str(e))}", "error")
            continue

        streak = info.get("streak", 0)
        streak_data = info.get("streakData", {})
        done_today = streak_done_today(streak_data)

        status = green("✓ done today") if done_today else yellow("⚠ not done today")
        log(f"{bold(username)} — Streak: {yellow(str(streak))} days — {status}", "stat")

    input(f"\n  {dim('Press Enter to continue...')}")

# ─── Main menu ────────────────────────────────────────────────────
def main_menu():
    while True:
        cls()
        accounts = load_accounts()
        n_acc = len(accounts)
        n_exp = sum(1 for a in accounts if jwt_expired(a.get("jwt","")))

        print(center(magenta(BANNER_ART)))
        print(center(f"{bold('PyLingo')}  {dim('v'+VERSION)}  {dim('─')}  {dim('Duolingo farming tool')}"))
        print()
        if n_acc:
            print(center(f"  {green(str(n_acc))} account(s)  │  "
                         f"{(red(str(n_exp)+' expired')) if n_exp else green('all active')}"))
        else:
            print(center(dim("No accounts saved — add one first")))
        print()
        print(hr())
        print()
        print(f"  {bold('1.')} {yellow('⚡ Farm')}              {dim('XP / Gems / Streak / Mixed')}")
        print(f"  {bold('2.')} {cyan('🗄️  Account Manager')}   {dim('Add / remove / view accounts')}")
        print(f"  {bold('3.')} {green('🔥 Streak Status')}     {dim('Check all accounts streak today')}")
        print(f"  {bold('4.')} {magenta('⚙️  Settings')}")
        print(f"  {bold('0.')} {dim('Exit')}")
        print()
        print(hr())
        print()

        choice = input(f"  {cyan('Select:')} ").strip()
        if choice == "1":
            farm_menu()
        elif choice == "2":
            accounts_menu()
        elif choice == "3":
            check_streak_status()
        elif choice == "4":
            settings_menu()
        elif choice == "0":
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
