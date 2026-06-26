"""Local persistence for the downloader.

Two things live on disk, both inside the repo and both gitignored:

* ``config.json`` - your saved login (so you don't sign in every time).
* ``state/<username>.json`` - per-profile MEMORY: the timestamp of the newest
  post we've already downloaded, so a later run only grabs newer posts.

No network, no triggers - just JSON files.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config.json"
STATE_DIR = REPO_ROOT / "state"


# --- saved login ------------------------------------------------------------
def load_config():
    """Return the saved-login dict (or {} if none)."""
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_config(cfg):
    """Persist login info to config.json (best-effort 0600 perms)."""
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    try:
        CONFIG_PATH.chmod(0o600)
    except Exception:
        pass
    return CONFIG_PATH


# --- per-profile memory -----------------------------------------------------
def _state_path(username):
    return STATE_DIR / f"{username}.json"


def load_state(username):
    """Return the memory dict for ``username`` (or {} if first run)."""
    p = _state_path(username)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(username, last_taken_ts, listed=0, downloaded=0):
    """Record the newest downloaded post's timestamp for next time."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    iso = ""
    if last_taken_ts:
        iso = datetime.fromtimestamp(last_taken_ts, tz=timezone.utc).isoformat()
    state = {
        "username": username,
        "last_taken_ts": float(last_taken_ts or 0.0),
        "last_taken_at": iso,
        "last_run": datetime.now(tz=timezone.utc).isoformat(),
        "last_listed": listed,
        "last_downloaded": downloaded,
    }
    _state_path(username).write_text(json.dumps(state, indent=2), encoding="utf-8")
    return _state_path(username)
