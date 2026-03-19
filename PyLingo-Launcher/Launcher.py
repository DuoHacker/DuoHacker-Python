#!/usr/bin/env python3
from __future__ import annotations
import os, sys, json, time, hashlib, re, importlib.util, threading, subprocess
from pathlib import Path
from datetime import datetime

RAW_BASE         = "https://raw.githubusercontent.com/not2pixel/PyLingo/main/PyLingo"
RAW_URL          = f"{RAW_BASE}/pylingo.py"
RAW_REQ_URL      = f"{RAW_BASE}/requirements.txt"
CACHE_DIR        = Path(__file__).parent / ".pylingo_cache"
CACHE_FILE       = CACHE_DIR / "pylingo.py"
REQ_FILE         = CACHE_DIR / "requirements.txt"
META_FILE        = CACHE_DIR / "meta.json"
TIMEOUT          = 12
LAUNCHER_VERSION = "1.0.0"

def _c(t, code): return f"\033[{code}m{t}\033[0m"
def green(t):   return _c(t, "92")
def yellow(t):  return _c(t, "93")
def red(t):     return _c(t, "91")
def cyan(t):    return _c(t, "96")
def bold(t):    return _c(t, "1")
def dim(t):     return _c(t, "2")

def tw():
    try:    return os.get_terminal_size().columns
    except: return 96

def cls():
    os.system("cls" if os.name == "nt" else "clear")

def ln(): print()

BANNER = """
  \u2588\u2588\u2588\u2588\u2588\u2588\u2563 \u2588\u2588\u2557   \u2588\u2588\u2557\u2588\u2588\u2557     \u2588\u2588\u2557\u2588\u2588\u2588\u2557   \u2588\u2588\u2557  \u2588\u2588\u2588\u2588\u2588\u2588\u2563  \u2588\u2588\u2588\u2588\u2588\u2588\u2563
  \u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2563\u255a\u2588\u2588\u2557 \u2588\u2588\u2554\u255d\u2588\u2588\u2551     \u2588\u2588\u2551\u2588\u2588\u2588\u2588\u2557  \u2588\u2588\u2551 \u2588\u2588\u2554\u2550\u2550\u2550\u2550\u255d \u2588\u2588\u2554\u2550\u2550\u2550\u2588\u2588\u2563
  \u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d \u255a\u2588\u2588\u2588\u2588\u2554\u255d \u2588\u2588\u2551     \u2588\u2588\u2551\u2588\u2588\u2554\u2588\u2588\u2557 \u2588\u2588\u2551 \u2588\u2588\u2551  \u2588\u2588\u2588\u2563\u2588\u2588\u2551   \u2588\u2588\u2551
  \u2588\u2588\u2554\u2550\u2550\u2550\u255d   \u255a\u2588\u2588\u2554\u255d  \u2588\u2588\u2551     \u2588\u2588\u2551\u2588\u2588\u2551\u255a\u2588\u2588\u2557\u2588\u2588\u2551 \u2588\u2588\u2551   \u2588\u2588\u2551\u2588\u2588\u2551   \u2588\u2588\u2551
  \u2588\u2588\u2551        \u2588\u2588\u2551   \u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2588\u2588\u2551\u2588\u2588\u2551 \u255a\u2588\u2588\u2588\u2588\u2551 \u255a\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d\u255a\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d
  \u255a\u2550\u255d        \u255a\u2550\u255d   \u255a\u2550\u2550\u2550\u2550\u2550\u2550\u255d\u255a\u2550\u255d\u255a\u2550\u255d  \u255a\u2550\u2550\u2550\u255d  \u255a\u2550\u2550\u2550\u2550\u2550\u255d  \u255a\u2550\u2550\u2550\u2550\u2550\u255d
"""

SPIN_FRAMES = ["\u280b","\u2819","\u2839","\u2838","\u283c","\u2834","\u2826","\u2827","\u2807","\u280f"]

class Spinner:
    def __init__(self):
        self._stop   = threading.Event()
        self._thread = None
        self._msg    = ""
        self._status = ""
        self._lock   = threading.Lock()

    def _run(self):
        i = 0
        while not self._stop.is_set():
            with self._lock:
                msg    = self._msg
                status = self._status
            frame = SPIN_FRAMES[i % len(SPIN_FRAMES)]
            line  = f"  {_c(frame, '96')} {msg}"
            if status:
                line += f"  {status}"
            print(f"\r{line:<72}", end="", flush=True)
            time.sleep(0.08)
            i += 1

    def start(self, msg):
        self._msg = msg
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def update(self, msg, status=""):
        with self._lock:
            self._msg    = msg
            self._status = status

    def ok(self, msg):
        self._stop.set()
        if self._thread: self._thread.join()
        print(f"\r  {green('v')} {msg:<70}")

    def warn(self, msg):
        self._stop.set()
        if self._thread: self._thread.join()
        print(f"\r  {yellow('!')} {msg:<70}")

    def fail(self, msg):
        self._stop.set()
        if self._thread: self._thread.join()
        print(f"\r  {red('x')} {msg:<70}")


def _task(label, status=""):
    plain = re.sub(r'\033\[[0-9;]*m', '', status)
    pad   = tw() - len(label) - len(plain) - 6
    bar   = dim("." * max(pad, 1))
    print(f"  {dim('[')} {label} {bar} {status} {dim(']')}")

def _section(title):
    w   = tw()
    pad = (w - len(title) - 4) // 2
    print(_c("-" * pad + "  " + title + "  " + "-" * (w - pad - len(title) - 4), "34"))

def load_meta():
    if META_FILE.exists():
        try:
            return json.loads(META_FILE.read_text("utf-8"))
        except Exception:
            pass
    return {}

def save_meta(data):
    META_FILE.write_text(json.dumps(data, indent=2), "utf-8")

def _extract_version(source):
    m = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', source)
    return m.group(1) if m else "?"

def fetch_raw(url):
    import http.client, urllib.parse
    parsed = urllib.parse.urlsplit(url)
    conn   = None
    try:
        conn = http.client.HTTPSConnection(parsed.netloc, timeout=TIMEOUT)
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        conn.request("GET", path, headers={"User-Agent": f"PyLingo-Launcher/{LAUNCHER_VERSION}"})
        resp = conn.getresponse()
        body = resp.read().decode("utf-8", errors="replace")
        return resp.status, body
    except Exception as e:
        return 0, str(e)
    finally:
        if conn:
            try: conn.close()
            except: pass

def ensure_cache_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    gi = CACHE_DIR / ".gitignore"
    if not gi.exists():
        gi.write_text("*\n")

def _parse_requirements(text):
    pkgs = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            pkgs.append(line)
    return pkgs

def _req_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]

def do_requirements(req_body):
    pkgs = _parse_requirements(req_body)
    if not pkgs:
        return

    new_hash = _req_hash(req_body)
    meta     = load_meta()
    old_hash = meta.get("req_hash", "")

    if new_hash == old_hash:
        _task("Dependencies", dim("up to date"))
        return

    spin = Spinner()
    spin.start(f"Installing {len(pkgs)} package(s): {', '.join(pkgs)}")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", *pkgs],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            spin.ok(f"Installed: {', '.join(pkgs)}")
            meta["req_hash"] = new_hash
            save_meta(meta)
        else:
            err = result.stderr.strip().splitlines()[-1][:60] if result.stderr.strip() else "unknown error"
            spin.warn(f"pip failed: {err}")
    except Exception as e:
        spin.warn(f"Could not install packages: {e}")

def do_update():
    spin = Spinner()
    ensure_cache_dir()
    meta = load_meta()

    spin.start("Fetching pylingo.py")
    status, body = fetch_raw(RAW_URL)

    if status != 200:
        if CACHE_FILE.exists():
            spin.warn(f"Fetch failed (HTTP {status or 'timeout'}) -- using cached version")
            meta["checked_at"] = time.time()
            meta["last_error"]  = f"HTTP {status}"
            save_meta(meta)
            return meta.get("version", "?")
        spin.fail(f"Cannot reach GitHub (HTTP {status}) -- no local cache")
        ln()
        sys.exit(1)

    spin.update("Fetching requirements.txt")
    req_status, req_body = fetch_raw(RAW_REQ_URL)

    new_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    old_hash = meta.get("hash", "")
    old_ver  = _extract_version(CACHE_FILE.read_text("utf-8") if CACHE_FILE.exists() else "")
    new_ver  = _extract_version(body)

    spin.update("Writing cache")
    time.sleep(0.05)
    CACHE_FILE.write_text(body, "utf-8")

    if req_status == 200:
        REQ_FILE.write_text(req_body, "utf-8")

    meta.update({
        "hash":       new_hash,
        "checked_at": time.time(),
        "updated_at": time.time(),
        "version":    new_ver,
        "last_error": None,
    })
    save_meta(meta)

    if new_hash != old_hash and old_ver and old_ver != new_ver:
        spin.ok(f"Updated  {old_ver} -> {new_ver}")
    elif new_hash != old_hash:
        spin.ok(f"Downloaded  {new_ver}")
    else:
        spin.ok(f"Up to date  {new_ver}")

    if req_status == 200:
        do_requirements(req_body)
    else:
        _task("Requirements", yellow(f"fetch failed (HTTP {req_status})"))

    return new_ver

def launch(version):
    _task("Launch", green(f"PyLingo {version}"))
    ln()
    os.chdir(CACHE_DIR)
    code = CACHE_FILE.read_text("utf-8")
    ns   = {"__name__": "__main__", "__file__": str(CACHE_FILE)}
    exec(compile(code, str(CACHE_FILE), "exec"), ns)

def main():
    args    = set(sys.argv[1:])
    offline = "--offline" in args

    if "--help" in args or "-h" in args:
        ln()
        print(f"  {bold('PyLingo Launcher')}  {dim('v'+LAUNCHER_VERSION)}")
        ln()
        print(f"  {cyan('--offline')}   Run from cache, skip update + dep check")
        print(f"  {cyan('--help')}      Show this help")
        ln()
        sys.exit(0)

    cls()
    print(_c(BANNER, "95"))
    print(f"  {bold('PyLingo Launcher')}  {dim('v'+LAUNCHER_VERSION)}")
    ln()
    _section("INIT")
    ln()

    if offline:
        ensure_cache_dir()
        if not CACHE_FILE.exists():
            print(f"  {red('x')} No cache found. Remove --offline to download.")
            sys.exit(1)
        meta    = load_meta()
        version = meta.get("version", "?")
        _task("Mode", yellow("offline"))
        _task("Cache", green(f"v{version}"))
        if REQ_FILE.exists():
            do_requirements(REQ_FILE.read_text("utf-8"))
        else:
            _task("Dependencies", dim("skipped"))
    else:
        _task("Mode", cyan("online"))
        version = do_update()

    _task("Ready", green("OK"))
    ln()
    _section("START")
    ln()

    launch(version)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        ln()
        print(f"  {dim('Interrupted.')}")
        sys.exit(0)
