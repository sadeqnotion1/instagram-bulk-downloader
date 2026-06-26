#!/usr/bin/env python3
"""Apply the 2FA login fix to an existing instagram-bulk-downloader checkout.

This is ADDITIVE and MINIMAL. It edits only two files:
  * app/igclient.py - login() now retries with a 2FA code when Instagram asks
  * app/main.py     - adds --totp-seed and wires an on-demand 2FA prompt

It is backup-first, idempotent, and refuses to write a partial change: if any
required anchor is missing (because you changed that area yourself), it ABORTS
without touching anything and tells you to merge by hand (see APPLY.md).

Usage:
  python apply_2fa_fix.py                 # back up the repo, then apply
  python apply_2fa_fix.py --check         # report status only (rc 0 = applied)
  python apply_2fa_fix.py --dry-run       # show what would change, write nothing
  python apply_2fa_fix.py --target DIR    # repo root (default: current dir)
  python apply_2fa_fix.py --no-backup     # skip the backup zip (not advised)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import py_compile
import sys
import zipfile
from pathlib import Path

# --------------------------------------------------------------------------
# Anchored edits. Each edit: find `old`, replace with `new`. `marker` means
# "already applied" (skip). `optional` edits may be missing without aborting.
# --------------------------------------------------------------------------

OLD_LOGIN = '''    def login(self, username, password, verification_code=""):
        """Log in, reusing a saved session when it is still valid."""
        from instagrapi import Client

        used_session = False
        if self.session_path.exists():
            try:
                self.cl.load_settings(self.session_path)
                self.cl.login(username, password, verification_code=verification_code)
                self.cl.get_timeline_feed()  # validate the session
                used_session = True
                log.info("reused saved session.")
            except Exception as e:
                log.warning(f"saved session invalid ({e}); logging in fresh.")
                self.cl = Client()
                self.cl.delay_range = [2, 5]

        if not used_session:
            self.cl.login(username, password, verification_code=verification_code)
            log.info("logged in with password.")

        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        self.cl.dump_settings(self.session_path)
        return True
'''

NEW_LOGIN = '''    def _save_session(self):
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        self.cl.dump_settings(self.session_path)

    def _totp_code(self, totp_seed):
        """Generate a fresh 6-digit code from a TOTP seed (or \'\')."""
        if not totp_seed:
            return ""
        try:
            return self.cl.totp_generate_code(totp_seed)
        except Exception as e:
            log.warning(f"could not generate TOTP code from seed: {e}")
            return ""

    def login(self, username, password, verification_code="", totp_seed="",
              on_need_2fa=None):
        """Log in, reusing a saved session when valid, handling 2FA on demand.

        2FA code precedence: saved totp_seed -> verification_code ->
        on_need_2fa() callback (prompts you for the current code).
        """
        def _needs_2fa(err):
            name = type(err).__name__.lower()
            msg = str(err).lower()
            return (
                "twofactor" in name
                or "two_factor" in name
                or "two-factor" in msg
                or "two factor" in msg
                or "verification_code" in msg
                or "2fa" in msg
            )

        # A code to try on the first attempt (seed wins, else any passed code).
        first_code = self._totp_code(totp_seed) or verification_code

        # 1) Try an existing session first - usually no 2FA needed.
        if self.session_path.exists():
            try:
                self.cl.load_settings(self.session_path)
                self.cl.login(username, password, verification_code=first_code)
                self.cl.get_timeline_feed()  # validate the session
                log.info("reused saved session.")
                self._save_session()
                return True
            except Exception as e:
                log.warning(f"saved session invalid ({e}); logging in fresh.")
                from instagrapi import Client  # lazy: only needed to reset
                self.cl = Client()
                self.cl.delay_range = [2, 5]

        # 2) Fresh login, retrying once with a 2FA code if required.
        try:
            self.cl.login(username, password, verification_code=first_code)
        except Exception as e:
            if not _needs_2fa(e):
                raise
            code = self._totp_code(totp_seed)
            if not code and on_need_2fa is not None:
                code = (on_need_2fa() or "").strip()
            if not code:
                raise
            log.info("submitting 2FA verification code ...")
            self.cl.login(username, password, verification_code=code)

        log.info("logged in with password.")
        self._save_session()
        return True
'''

OLD_2FA_ARG = '''    p.add_argument("--2fa", dest="two_factor", default="",
                   help="2FA verification code, if your account uses it")
'''

NEW_2FA_ARG = '''    p.add_argument("--2fa", dest="two_factor", default="",
                   help="2FA verification code, if your account uses it")
    p.add_argument("--totp-seed", dest="totp_seed", default="",
                   help="2FA TOTP secret/seed to auto-generate codes every login")
'''

OLD_RESOLVE = '    two_factor = args.two_factor or cfg.get("two_factor", "")\n'
NEW_RESOLVE = ('    two_factor = args.two_factor or cfg.get("two_factor", "")\n'
               '    totp_seed = args.totp_seed or cfg.get("totp_seed", "")\n')

OLD_SAVE = '''            "two_factor": two_factor,
        })
'''
NEW_SAVE = '''            "two_factor": two_factor,
            "totp_seed": totp_seed,
        })
'''

OLD_LOGIN_CALL = '''    arch = InstagramArchiver(session)
    try:
        arch.login(login_user, login_pass, verification_code=two_factor)
'''
NEW_LOGIN_CALL = '''    def ask_2fa():
        try:
            return input("Enter the 6-digit 2FA code from your authenticator app/SMS: ").strip()
        except EOFError:
            return ""

    arch = InstagramArchiver(session)
    try:
        arch.login(login_user, login_pass, verification_code=two_factor,
                   totp_seed=totp_seed, on_need_2fa=ask_2fa)
'''

PLAN = {
    "app/igclient.py": [
        {"name": "login-2fa", "old": OLD_LOGIN, "new": NEW_LOGIN,
         "marker": "on_need_2fa", "optional": False},
    ],
    "app/main.py": [
        {"name": "totp-seed-arg", "old": OLD_2FA_ARG, "new": NEW_2FA_ARG,
         "marker": 'dest="totp_seed"', "optional": False},
        {"name": "resolve-totp", "old": OLD_RESOLVE, "new": NEW_RESOLVE,
         "marker": "totp_seed = args.totp_seed", "optional": False},
        {"name": "save-totp", "old": OLD_SAVE, "new": NEW_SAVE,
         "marker": '"totp_seed": totp_seed', "optional": True},
        {"name": "login-call", "old": OLD_LOGIN_CALL, "new": NEW_LOGIN_CALL,
         "marker": "on_need_2fa=ask_2fa", "optional": False},
    ],
}


def plan_file(text, edits):
    """Return (new_text, results). results: list of (name, status)."""
    results = []
    for e in edits:
        if e["marker"] in text:
            results.append((e["name"], "present"))
            continue
        if e["old"] in text:
            text = text.replace(e["old"], e["new"], 1)
            results.append((e["name"], "apply"))
        else:
            results.append((e["name"], "missing-optional" if e["optional"] else "missing"))
    return text, results


def backup(target: Path) -> Path:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    zpath = target.parent / f"{target.name}-backup-{stamp}.zip"
    skip = (".git", "__pycache__", "node_modules", "downloads", "sessions")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(target.rglob("*")):
            if p.is_dir():
                continue
            if any(part in skip for part in p.parts):
                continue
            z.write(p, p.relative_to(target.parent))
    return zpath


def main(argv=None):
    ap = argparse.ArgumentParser(description="Apply the 2FA login fix.")
    ap.add_argument("--target", default=".", help="repo root (default: current dir)")
    ap.add_argument("--check", action="store_true", help="report status only")
    ap.add_argument("--dry-run", action="store_true", help="show changes, write nothing")
    ap.add_argument("--no-backup", action="store_true", help="skip the backup zip")
    args = ap.parse_args(argv)

    target = Path(args.target).resolve()
    files = {rel: target / rel for rel in PLAN}
    for rel, path in files.items():
        if not path.exists():
            print(f"ERROR: {rel} not found under {target}. "
                  f"Run from the repo root or pass --target.", file=sys.stderr)
            return 2

    # Plan every file first (no writes yet).
    planned = {}   # rel -> (new_text, orig_text, results)
    any_apply = False
    any_missing = False
    print(f"Target: {target}\n")
    for rel, path in files.items():
        orig = path.read_text(encoding="utf-8")
        new_text, results = plan_file(orig, PLAN[rel])
        planned[rel] = (new_text, orig, results)
        print(f"  {rel}")
        for name, status in results:
            print(f"    - {name}: {status}")
            if status == "apply":
                any_apply = True
            if status == "missing":
                any_missing = True
    print()

    fully_applied = (not any_apply) and (not any_missing)

    if args.check:
        print("STATUS: already applied." if fully_applied
              else "STATUS: not (fully) applied.")
        return 0 if fully_applied else 1

    if any_missing:
        print("ABORT: one or more required anchors were not found - your files "
              "differ from the expected baseline.\nNothing was changed. Apply "
              "the change by hand using the snippets in APPLY.md.", file=sys.stderr)
        return 3

    if fully_applied:
        print("Nothing to do - the fix is already applied.")
        return 0

    if args.dry_run:
        print("DRY RUN: anchors found; the above 'apply' edits would be made. "
              "No files written.")
        return 0

    # Apply for real.
    if not args.no_backup:
        z = backup(target)
        print(f"Backup written: {z}")

    written = []
    for rel, (new_text, orig, results) in planned.items():
        if all(s != "apply" for _, s in results):
            continue
        path = files[rel]
        path.write_text(new_text, encoding="utf-8")
        written.append((rel, path, orig))

    # Verify the edited files still compile; restore on failure.
    for rel, path, orig in written:
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as e:
            print(f"ERROR: {rel} failed to compile after edit; restoring it.\n{e}",
                  file=sys.stderr)
            path.write_text(orig, encoding="utf-8")
            return 4

    print("\nDONE. Edited: " + ", ".join(rel for rel, _, _ in written))
    print("Verify with the steps in QUALITY_GATE.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
