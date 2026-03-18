#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════════════
#  PyLingo Launcher
#  Fetches the latest pylingo.py from GitHub, caches it locally,
#  then executes it. Always stays up to date.
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations
import os, sys, json, time, hashlib, subprocess, re, importlib.util
from pathlib import Path
from datetime import datetime

# ── Config ─────────────────────────────────────────────────────────────────────
RAW_URL   = "https://raw.githubusercontent.com/not2pixel/PyLingo/main/PyLingo/pylingo.py"
CACHE_DIR = Path(__file__).parent / ".pylingo_cache"
CACHE_FILE= CACHE_DIR / "pylingo.py"
META_FILE = CACHE_DIR / "meta.json"
MAX_AGE_S = 3600          # re-check GitHub every 1 hour
TIMEOUT   = 12            # HTTP timeout seconds
LAUNCHER_VERSION = "1.0.0"

# ── ANSI (minimal, no deps) ────────────────────────────────────────────────────
def _c(t, code): return f"\033[{code}m{t}\033[0m"
def green(t):  return _c(t, "92")
def yellow(t): return _c(t, "93")
def red(t):    return _c(t, "91")
def cyan(t):   return _c(t, "96")
def bold(t):   return _c(t, "1")
def dim(t):    return _c(t, "2")

def _strip(t): return re.sub(r'\033\[[0-9;]*m', '', str(t))

def tw() -> int:
    try:    return os.get_terminal_size().columns
    except: return 96

def hr():    print(_c("─" * tw(), "34"))
def ln():    print()

def log(msg: str, level: str = "info"):
    ts = datetime.now().strftime("%H:%M:%S")
    cfg = {
        "info":    (dim,    "  "),
        "success": (green,  "OK"),
        "warning": (yellow, "WR"),
        "error":   (red,    "ER"),
    }
    fn, tag = cfg.get(level, (dim, "  "))
    print(f"  {dim(ts)}  {fn(tag)}  {msg}")

BANNER = r"""
  ██████╗ ██╗   ██╗██╗     ██╗███╗   ██╗  ██████╗  ██████╗
  ██╔══██╗╚██╗ ██╔╝██║     ██║████╗  ██║ ██╔════╝ ██╔═══██╗
  ██████╔╝ ╚████╔╝ ██║     ██║██╔██╗ ██║ ██║  ███╗██║   ██║
  ██╔═══╝   ╚██╔╝  ██║     ██║██║╚██╗██║ ██║   ██║██║   ██║
  ██║        ██║   ███████╗██║██║ ╚████║ ╚██████╔╝╚██████╔╝
  ╚═╝        ╚═╝   ╚══════╝╚═╝╚═╝  ╚═══╝ ╚═════╝  ╚═════╝
"""

# ── Meta helpers ───────────────────────────────────────────────────────────────
def load_meta() -> dict:
    if META_FILE.exists():
        try:
            return json.loads(META_FILE.read_text())
        except:
            pass
    return {}

def save_meta(data: dict):
    META_FILE.write_text(json.dumps(data, indent=2))

def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]

def cache_age_s() -> float:
    meta = load_meta()
    if not meta.get("checked_at"):
        return float("inf")
    return time.time() - meta["checked_at"]

# ── Network fetch (stdlib only — no requests needed for launcher) ──────────────
def fetch_raw(url: str) -> tuple[int, str]:
    import http.client, urllib.parse
    parsed = urllib.parse.urlsplit(url)
    try:
        conn = http.client.HTTPSConnection(parsed.netloc, timeout=TIMEOUT)
        conn.request("GET", parsed.path + (f"?{parsed.query}" if parsed.query else ""),
                     headers={"User-Agent": "PyLingo-Launcher/1.0"})
        resp = conn.getresponse()
        body = resp.read().decode("utf-8", errors="replace")
        return resp.status, body
    except Exception as e:
        return 0, str(e)
    finally:
        try: conn.close()
        except: pass

# ── Core update logic ──────────────────────────────────────────────────────────
def ensure_cache_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # Keep cache hidden on Unix
    gitignore = CACHE_DIR / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n")

def check_update(force: bool = False) -> bool:
    """
    Returns True if cache was refreshed.
    Returns False if already up-to-date or update failed.
    """
    ensure_cache_dir()
    meta = load_meta()
    age  = cache_age_s()

    if not force and age < MAX_AGE_S and CACHE_FILE.exists():
        log(f"Cache is fresh ({int(age)}s old, limit {MAX_AGE_S}s)  —  skipping update check", "info")
        return False

    log("Checking for updates...", "info")
    status, body = fetch_raw(RAW_URL)

    if status != 200:
        if CACHE_FILE.exists():
            log(f"Update check failed (HTTP {status}) — using cached version", "warning")
            # Still update checked_at so we don't spam failed requests
            meta["checked_at"] = time.time()
            meta["last_error"] = f"HTTP {status}"
            save_meta(meta)
            return False
        else:
            print()
            log(f"Cannot reach GitHub (HTTP {status}) and no cache exists.", "error")
            log("Check your internet connection and try again.", "error")
            sys.exit(1)

    new_hash = hashlib.sha256(body.encode()).hexdigest()[:16]
    old_hash = meta.get("hash", "")

    if new_hash != old_hash:
        old_ver = _extract_version(CACHE_FILE.read_text() if CACHE_FILE.exists() else "")
        new_ver = _extract_version(body)
        CACHE_FILE.write_text(body)
        meta.update({
            "hash":        new_hash,
            "checked_at":  time.time(),
            "updated_at":  time.time(),
            "version":     new_ver,
            "last_error":  None,
        })
        save_meta(meta)
        if old_ver and old_ver != new_ver:
            log(f"Updated  {dim(old_ver)}  ->  {green(new_ver)}", "success")
        else:
            log(f"Downloaded latest version {green(new_ver)}", "success")
        return True
    else:
        meta["checked_at"] = time.time()
        save_meta(meta)
        log(f"Already up to date  ({green(meta.get('version','?'))})", "success")
        return False

def _extract_version(source: str) -> str:
    m = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', source)
    return m.group(1) if m else "?"

# ── Bootstrap deps for pylingo ─────────────────────────────────────────────────
def ensure_pylingo_deps():
    """Install requests + questionary if missing, so pylingo.py can run."""
    needed = ["requests", "questionary"]
    missing = [p for p in needed if importlib.util.find_spec(p) is None]
    if missing:
        log(f"Installing dependencies: {', '.join(missing)}", "info")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", *missing],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        log("Dependencies installed.", "success")

# ── Launch ─────────────────────────────────────────────────────────────────────
def launch():
    if not CACHE_FILE.exists():
        log("No local cache — must download from GitHub.", "error")
        sys.exit(1)
    meta    = load_meta()
    version = meta.get("version", "?")
    log(f"Launching PyLingo {green(version)}...", "info")
    ln()
    # Execute in same process namespace so accounts.json resolves correctly
    os.chdir(CACHE_DIR)
    code = CACHE_FILE.read_text()
    exec(compile(code, str(CACHE_FILE), "exec"), {"__name__": "__main__",
                                                    "__file__": str(CACHE_FILE)})

# ── CLI args ───────────────────────────────────────────────────────────────────
def print_help():
    print()
    print(f"  {bold('PyLingo Launcher')}  {dim('v'+LAUNCHER_VERSION)}")
    print()
    print(f"  {dim('Usage:')}  python launcher.py [options]")
    print()
    print(f"  {bold('Options:')}")
    print(f"    {cyan('--update')}       Force re-download from GitHub, then run")
    print(f"    {cyan('--offline')}      Run from cache without checking for updates")
    print(f"    {cyan('--check')}        Check for update and exit (no launch)")
    print(f"    {cyan('--cache-info')}   Show cache metadata and exit")
    print(f"    {cyan('--help')}         Show this help")
    print()
    print(f"  {dim('Cache:  ')}{dim(str(CACHE_DIR))}")
    print(f"  {dim('Source: ')}{dim(RAW_URL)}")
    print()

def print_cache_info():
    meta = load_meta()
    print()
    print(f"  {bold('Cache Information')}")
    hr()
    print(f"  {'Directory':<20}  {dim(str(CACHE_DIR))}")
    print(f"  {'File':<20}  {dim(str(CACHE_FILE))}")
    print(f"  {'Exists':<20}  {green('yes') if CACHE_FILE.exists() else red('no')}")
    if meta:
        print(f"  {'Version':<20}  {green(meta.get('version','?'))}")
        print(f"  {'Hash':<20}  {dim(meta.get('hash','?'))}")
        if meta.get("checked_at"):
            print(f"  {'Last checked':<20}  {dim(datetime.fromtimestamp(meta['checked_at']).strftime('%Y-%m-%d %H:%M:%S'))}")
        if meta.get("updated_at"):
            print(f"  {'Last updated':<20}  {dim(datetime.fromtimestamp(meta['updated_at']).strftime('%Y-%m-%d %H:%M:%S'))}")
        age = cache_age_s()
        print(f"  {'Cache age':<20}  {dim(f'{int(age)}s')}  {green('(fresh)') if age < MAX_AGE_S else yellow('(stale)')}")
        if meta.get("last_error"):
            print(f"  {'Last error':<20}  {red(meta['last_error'])}")
    print()

# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    args    = set(sys.argv[1:])
    offline = "--offline" in args
    force   = "--update" in args
    check   = "--check" in args

    if "--help" in args or "-h" in args:
        print_help(); sys.exit(0)

    if "--cache-info" in args:
        print_cache_info(); sys.exit(0)

    os.system("cls" if os.name == "nt" else "clear")
    print("\033[95m" + BANNER + "\033[0m")
    print("  " + bold("PyLingo Launcher") + "  " + dim(f"v{LAUNCHER_VERSION}"))
    ln(); hr(); ln()

    if check:
        check_update(force=True)
        sys.exit(0)

    if not offline:
        check_update(force=force)
    else:
        log("Offline mode — skipping update check", "info")
        ensure_cache_dir()
        if not CACHE_FILE.exists():
            log("No cache found and offline mode is active. Cannot start.", "error")
            sys.exit(1)

    ensure_pylingo_deps()
    ln()
    launch()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        ln()
        log("Interrupted.", "info")
        sys.exit(0)
