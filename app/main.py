#!/usr/bin/env python3
"""Instagram profile archiver - download posts of one person.

Manual CLI tool: you run it, it logs in, downloads the target profile's posts,
then exits. No bot, no scheduler, no background triggers.

Highlights:
* **Saved login** - store credentials once (``--save-login``) so you don't sign
  in every time. Order: flags > env vars > config.json > prompt.
* **Memory** - remembers the newest post downloaded per profile, so rerunning
  two weeks later only grabs the new posts (use ``--full`` to ignore memory).
* Files go to ``<out>/@<username>/posts_<username>_<date>_<time>/``.

Usage:
    python -m app.main <username> --login-user you [--limit N] [--full]
"""
from __future__ import annotations

import argparse
import getpass
import logging
import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import store
from app.igclient import InstagramArchiver

try:
    from launcher import ui_theme
except Exception:
    ui_theme = None

log = logging.getLogger("ig")

# Default Windows archive root (override with --out on macOS/Linux).
DEFAULT_OUT = r"G:\Instagram\Users"


def _status(msg):
    if ui_theme is not None:
        ui_theme.print_check("info", msg)
    else:
        print(f"[i] {msg}")


def build_parser():
    p = argparse.ArgumentParser(
        prog="instagram-bulk-downloader",
        description="Download posts of a single Instagram profile (manual, no triggers).",
    )
    p.add_argument("username", nargs="?", help="target profile to download (without @)")
    p.add_argument("--login-user", default=os.environ.get("IG_USERNAME"),
                   help="your Instagram login (or set IG_USERNAME, or save it)")
    p.add_argument("--login-pass", default=os.environ.get("IG_PASSWORD"),
                   help="your password (or set IG_PASSWORD; prompted if omitted)")
    p.add_argument("--2fa", dest="two_factor", default="",
                   help="2FA verification code, if your account uses it")
    p.add_argument("--totp-seed", dest="totp_seed", default="",
                   help="2FA TOTP secret/seed to auto-generate codes every login")
    p.add_argument("--save-login", action="store_true",
                   help="save the login to config.json so you don't sign in again")
    p.add_argument("--out", default=DEFAULT_OUT,
                   help=f"output root (default: {DEFAULT_OUT})")
    p.add_argument("--limit", type=int, default=0,
                   help="max posts to download (0 = all, default)")
    p.add_argument("--full", action="store_true",
                   help="ignore memory and (re)download all posts")
    p.add_argument("--session", default="",
                   help="session file path (default: ./sessions/<login-user>.json)")
    p.add_argument("--no-banner", action="store_true", help="disable the themed banner")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if ui_theme is not None and not args.no_banner:
        ui_theme.print_banner(
            "Instagram Profile Archiver",
            "Download a person's posts - manual, no triggers",
        )

    username = args.username
    if not username:
        try:
            username = input("Enter target Instagram username to download (without @): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.", file=sys.stderr)
            return 1
        if not username:
            print("ERROR: Target username is required.", file=sys.stderr)
            return 2
    args.username = username

    # --- resolve login: flags > env > saved config > prompt -----------------
    cfg = store.load_config()
    login_user = args.login_user or cfg.get("login_user")
    login_pass = args.login_pass or cfg.get("login_pass")
    two_factor = args.two_factor or cfg.get("two_factor", "")
    totp_seed = args.totp_seed or cfg.get("totp_seed", "")

    if not login_user:
        # Check if there are any session JSON files in the sessions folder
        sessions_dir = REPO_ROOT / "sessions"
        session_files = []
        if sessions_dir.exists() and sessions_dir.is_dir():
            session_files = sorted(
                [f for f in sessions_dir.glob("*.json") if f.is_file()],
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
        
        if session_files:
            # Use the username from the most recently modified session file
            login_user = session_files[0].stem
            _status(f"Found existing session file for user: @{login_user}")
        else:
            _status("No saved login or active sessions found.")
            try:
                login_user = input("Enter your Instagram login username (or set IG_USERNAME): ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nAborted.", file=sys.stderr)
                return 1
            if not login_user:
                print("ERROR: Login username is required.", file=sys.stderr)
                return 2
    if args.save_login and not login_pass:
        try:
            login_pass = getpass.getpass(f"Instagram password for @{login_user} (to save): ")
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.", file=sys.stderr)
            return 1

    if args.save_login:
        store.save_config({
            "login_user": login_user,
            "login_pass": login_pass,
            "two_factor": two_factor,
            "totp_seed": totp_seed,
        })
        _status("saved login to config.json (plaintext, gitignored - keep it private)")

    session = args.session or str(REPO_ROOT / "sessions" / f"{login_user}.json")

    try:
        arch = InstagramArchiver(session)
    except ModuleNotFoundError as e:
        print(f"ERROR: Missing dependency: {e}", file=sys.stderr)
        print("Please install the required packages by running:", file=sys.stderr)
        print(f"    python -m pip install -r {REPO_ROOT}/app/requirements.txt", file=sys.stderr)
        return 3

    def ask_2fa():
        try:
            return input("Enter the 6-digit 2FA code from your authenticator app/SMS: ").strip()
        except EOFError:
            return ""

    def ask_password():
        try:
            return getpass.getpass(f"Instagram password for @{login_user}: ")
        except (KeyboardInterrupt, EOFError):
            return ""

    try:
        arch.login(login_user, login_pass, verification_code=two_factor,
                   totp_seed=totp_seed, on_need_2fa=ask_2fa,
                   on_need_password=ask_password)
    except Exception as e:
        print(f"ERROR: login failed: {e}", file=sys.stderr)
        if "challenge" in str(e).lower() or "step_name" in str(e).lower():
            print("\n[TIP] Instagram has triggered a security verification (checkpoint challenge) for your account.", file=sys.stderr)
            print("To resolve this, please open the Instagram app on your phone or log in to instagram.com in a web browser.", file=sys.stderr)
            print("Complete the verification there (e.g., tap 'This was me' or enter the verification code), then run the script again.", file=sys.stderr)
        return 1

    # --- memory: only fetch posts newer than last run (unless --full) -------
    state = store.load_state(args.username)
    since_ts = 0.0 if args.full else float(state.get("last_taken_ts", 0.0) or 0.0)
    if since_ts:
        _status(f"memory: last run reached {state.get('last_taken_at', '?')}; "
                f"fetching only newer posts (use --full to override).")

    try:
        result = arch.download_all(
            args.username, args.out, limit=args.limit,
            on_status=_status, since_ts=since_ts,
        )
    except Exception as e:
        print(f"ERROR: download failed: {e}", file=sys.stderr)
        return 1

    # --- update memory with the newest post we saw --------------------------
    new_ts = max(result.get("newest_ts", 0.0), since_ts)
    if new_ts:
        store.save_state(
            args.username, new_ts,
            listed=result.get("listed", 0),
            downloaded=result.get("downloaded", 0),
        )

    head = f"{result['downloaded']} file(s) from @{result['target']}"
    if result.get("skipped"):
        head += f" (skipped {result['skipped']} already-downloaded)"
    if ui_theme is not None:
        ui_theme.print_check("pass" if result["complete"] else "warn", head, result["out_dir"])
        if result["failed"]:
            ui_theme.print_check("warn", f"{len(result['failed'])} item(s) failed")
    else:
        print(f"[OK] {head} -> {result['out_dir']}")
        if result["failed"]:
            print(f"[!] {len(result['failed'])} item(s) failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
