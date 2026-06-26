#!/usr/bin/env python3
"""Apply the CDN download-timeout + retry fix to instagram-bulk-downloader.

What it changes (only app/igclient.py):
  1. Adds REQUEST_TIMEOUT / DOWNLOAD_RETRIES / DOWNLOAD_RETRY_WAIT constants.
  2. Sets self.cl.request_timeout in __init__ (instagrapi default is 1s!).
  3. Sets self.cl.request_timeout again when the client is rebuilt on a
     stale-session fallback inside login().
  4. Wraps each item download in a small retry loop for transient CDN errors.

Safe by design:
  * Makes a timestamped backup zip of the whole repo before writing.
  * Idempotent - re-running is a no-op ("already applied").
  * All-or-nothing per file: if a REQUIRED anchor is missing it ABORTS without
    writing anything; edit 4 (retry loop) is OPTIONAL and skipped if your
    download loop differs.
  * py_compile check after writing; restores the original on failure.

Usage:
  python apply_timeout_fix.py --target .            # backup + apply
  python apply_timeout_fix.py --target . --check     # rc0 applied / rc1 not
  python apply_timeout_fix.py --target . --dry-run    # show plan, write nothing
  python apply_timeout_fix.py --target . --no-backup  # skip the backup zip
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import py_compile
import sys
import zipfile
from pathlib import Path


# ----------------------------------------------------------------------------
# Edit definitions. Each edit: (id, old, new, marker, required)
#   old      - exact text that must be found (None => insertion handled by new)
#   new      - replacement text
#   marker   - if already in the file, the edit is considered applied (skip)
#   required - if True and `old` is missing (and marker absent), ABORT the file
# ----------------------------------------------------------------------------

IGCLIENT = "app/igclient.py"

_CONST_OLD = "WAIT_TICK = 15        # how often (s) to refresh the wait countdown\n"
_CONST_NEW = (
    "WAIT_TICK = 15        # how often (s) to refresh the wait countdown\n"
    "REQUEST_TIMEOUT = 20  # seconds for API + media/CDN downloads "
    "(instagrapi default is 1!)\n"
    "DOWNLOAD_RETRIES = 3  # attempts per media item on transient download errors\n"
    "DOWNLOAD_RETRY_WAIT = 5  # seconds between download retries\n"
)

_INIT_OLD = (
    "        self.cl = Client()\n"
    "        self.cl.delay_range = list(delay_range)\n"
)
_INIT_NEW = (
    "        self.cl = Client()\n"
    "        self.cl.delay_range = list(delay_range)\n"
    "        self.cl.request_timeout = REQUEST_TIMEOUT\n"
)

_RESET_OLD = (
    "                self.cl = Client()\n"
    "                self.cl.delay_range = [2, 5]\n"
)
_RESET_NEW = (
    "                self.cl = Client()\n"
    "                self.cl.delay_range = [2, 5]\n"
    "                self.cl.request_timeout = REQUEST_TIMEOUT\n"
)

_DL_OLD = (
    "                try:\n"
    "                    for p in download_one(self.cl, media, str(post_dir)):\n"
    "                        if p:\n"
    "                            files.append(str(p))\n"
    "                    if ts > newest_ts:\n"
    "                        newest_ts = ts\n"
    "                except Exception as item_err:\n"
    "                    pk = getattr(media, \"pk\", \"?\")\n"
    "                    log.warning(f\"failed item {pk}: {item_err}\")\n"
    "                    failed.append(str(pk))\n"
)
_DL_NEW = (
    "                saved = None\n"
    "                for attempt in range(1, DOWNLOAD_RETRIES + 1):\n"
    "                    try:\n"
    "                        saved = [str(p) for p in "
    "download_one(self.cl, media, str(post_dir)) if p]\n"
    "                        break\n"
    "                    except Exception as item_err:\n"
    "                        pk = getattr(media, \"pk\", \"?\")\n"
    "                        if attempt < DOWNLOAD_RETRIES:\n"
    "                            status(f\"item {pk} failed (attempt "
    "{attempt}/{DOWNLOAD_RETRIES}): {item_err}; \"\n"
    "                                   f\"retrying in {DOWNLOAD_RETRY_WAIT}s ...\")\n"
    "                            time.sleep(DOWNLOAD_RETRY_WAIT)\n"
    "                        else:\n"
    "                            log.warning(f\"failed item {pk} after "
    "{DOWNLOAD_RETRIES} tries: {item_err}\")\n"
    "                            failed.append(str(pk))\n"
    "                if saved is not None:\n"
    "                    files.extend(saved)\n"
    "                    if ts > newest_ts:\n"
    "                        newest_ts = ts\n"
)

EDITS = [
    ("timeout-consts", _CONST_OLD, _CONST_NEW, "REQUEST_TIMEOUT = 20", True),
    ("init-timeout", _INIT_OLD, _INIT_NEW,
     "list(delay_range)\n        self.cl.request_timeout = REQUEST_TIMEOUT", True),
    ("reset-timeout", _RESET_OLD, _RESET_NEW,
     "[2, 5]\n                self.cl.request_timeout = REQUEST_TIMEOUT", True),
    ("download-retry", _DL_OLD, _DL_NEW, "for attempt in range(1, DOWNLOAD_RETRIES", False),
]


def _plan(text):
    """Return (new_text, results) where results is list of (id, status)."""
    results = []
    abort = False
    for eid, old, new, marker, required in EDITS:
        if marker and marker in text:
            results.append((eid, "present"))
            continue
        if old in text:
            text = text.replace(old, new, 1)
            results.append((eid, "apply"))
        else:
            results.append((eid, "MISSING" if required else "skip (optional)"))
            if required:
                abort = True
    return text, results, abort


def _backup(root: Path):
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = root.parent / f"{root.name}-backup-{ts}.zip"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for p in root.rglob("*"):
            if any(part in ("__pycache__", ".git") for part in p.parts):
                continue
            if p.is_file():
                z.write(p, p.relative_to(root.parent))
    return dest


def main(argv=None):
    ap = argparse.ArgumentParser(description="Apply CDN download-timeout fix.")
    ap.add_argument("--target", default=".", help="repo root (contains app/)")
    ap.add_argument("--check", action="store_true", help="report status only")
    ap.add_argument("--dry-run", action="store_true", help="show plan, write nothing")
    ap.add_argument("--no-backup", action="store_true", help="skip backup zip")
    args = ap.parse_args(argv)

    root = Path(args.target).resolve()
    fpath = root / IGCLIENT
    print(f"Target: {root}\n")
    if not fpath.exists():
        print(f"ERROR: {IGCLIENT} not found under {root}.", file=sys.stderr)
        print("Run this from your repo root, or pass --target <repo path>.", file=sys.stderr)
        return 2

    original = fpath.read_text()
    new_text, results, abort = _plan(original)

    print(f"  {IGCLIENT}")
    for eid, st in results:
        print(f"    - {eid}: {st}")
    print()

    fully_applied = all(st == "present" for _, st in results)

    if args.check:
        if fully_applied:
            print("STATUS: already applied.")
            return 0
        print("STATUS: not (fully) applied.")
        return 1

    if abort:
        print("ABORT: a required anchor was not found - your file differs from the")
        print("expected baseline. Nothing was changed. Apply by hand using APPLY.md.")
        return 3

    if new_text == original:
        print("Nothing to do - the fix is already applied.")
        return 0

    if args.dry_run:
        print("DRY RUN: the above edits would be applied. No files written.")
        return 0

    if not args.no_backup:
        dest = _backup(root)
        print(f"Backup written: {dest}\n")

    fpath.write_text(new_text)
    try:
        py_compile.compile(str(fpath), doraise=True)
    except py_compile.PyCompileError as e:
        fpath.write_text(original)
        print(f"ERROR: patched file failed to compile, reverted: {e}", file=sys.stderr)
        return 4

    print(f"DONE. Edited: {IGCLIENT}")
    print("Verify with the steps in QUALITY_GATE.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
