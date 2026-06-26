# APPLY - 2FA login fix for instagram-bulk-downloader

**What this fixes:** logins on accounts with two-factor auth failed with
`Two-factor authentication required (you did not provide verification_code...)`.
After this patch the tool asks for the 6-digit code when Instagram requests it
(and can auto-generate it from a saved TOTP seed).

**Scope (additive, minimal):** edits only two files -
`app/igclient.py` and `app/main.py`. Nothing else is touched. Your local
changes elsewhere are safe.

---

## Easiest path - run the applier

From the **root of your repo** (the folder that contains `app/`):

```bash
# 1) see what it will do (writes nothing)
python apply_2fa_fix.py --target . --check

# 2) apply it (makes a timestamped backup zip first, then edits the 2 files)
python apply_2fa_fix.py --target .
```

- Copy `apply_2fa_fix.py` into your repo root first, or pass `--target` with the
  full path to your repo.
- It **backs up the whole repo to** `../<repo>-backup-<timestamp>.zip` before
  changing anything.
- It is **idempotent**: running it twice is a no-op ("already applied").
- It **refuses to half-apply**: if your `app/igclient.py` / `app/main.py` differ
  from the expected baseline and an anchor is missing, it ABORTS without writing
  and tells you to use the manual steps below.
- `--dry-run` shows the plan without writing; `--no-backup` skips the backup.

If the applier aborts with "anchors not found", do the manual merge below.

---

## Manual merge (only if the applier aborts)

### A) `app/igclient.py` - replace the whole `login()` method

**Find** the current method that starts with:

```python
    def login(self, username, password, verification_code=""):
        """Log in, reusing a saved session when it is still valid."""
```

…down to its final `return True`. **Replace that entire method** with the two
helpers + new method below (same indentation - 4 spaces, inside the class):

```python
    def _save_session(self):
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        self.cl.dump_settings(self.session_path)

    def _totp_code(self, totp_seed):
        if not totp_seed:
            return ""
        try:
            return self.cl.totp_generate_code(totp_seed)
        except Exception as e:
            log.warning(f"could not generate TOTP code from seed: {e}")
            return ""

    def login(self, username, password, verification_code="", totp_seed="",
              on_need_2fa=None):
        def _needs_2fa(err):
            name = type(err).__name__.lower()
            msg = str(err).lower()
            return ("twofactor" in name or "two_factor" in name
                    or "two-factor" in msg or "two factor" in msg
                    or "verification_code" in msg or "2fa" in msg)

        first_code = self._totp_code(totp_seed) or verification_code

        if self.session_path.exists():
            try:
                self.cl.load_settings(self.session_path)
                self.cl.login(username, password, verification_code=first_code)
                self.cl.get_timeline_feed()
                log.info("reused saved session.")
                self._save_session()
                return True
            except Exception as e:
                log.warning(f"saved session invalid ({e}); logging in fresh.")
                from instagrapi import Client
                self.cl = Client()
                self.cl.delay_range = [2, 5]

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
```

### B) `app/main.py` - 3 small edits

**B1.** Right after the `--2fa` argument, add the TOTP-seed flag:

```python
    p.add_argument("--totp-seed", dest="totp_seed", default="",
                   help="2FA TOTP secret/seed to auto-generate codes every login")
```

**B2.** Where the login values are resolved, add a `totp_seed` line right after
the `two_factor = ...` line:

```python
    totp_seed = args.totp_seed or cfg.get("totp_seed", "")
```

(Optional: if you save credentials with `--save-login`, add
`"totp_seed": totp_seed,` to the dict passed to `store.save_config({...})`.)

**B3.** Replace the login call. **Find:**

```python
    arch = InstagramArchiver(session)
    try:
        arch.login(login_user, login_pass, verification_code=two_factor)
```

**Replace with:**

```python
    def ask_2fa():
        try:
            return input("Enter the 6-digit 2FA code from your authenticator app/SMS: ").strip()
        except EOFError:
            return ""

    arch = InstagramArchiver(session)
    try:
        arch.login(login_user, login_pass, verification_code=two_factor,
                   totp_seed=totp_seed, on_need_2fa=ask_2fa)
```

> If your variable is named differently (e.g. you pass `args.two_factor`
> directly), keep your name - just add the `totp_seed=...` and
> `on_need_2fa=ask_2fa` keyword arguments and the `ask_2fa` function above the
> call.

---

## Run / verify

```bash
python -m app.main danidjokic --login-user sadster710
```

After the password it will prompt:
`Enter the 6-digit 2FA code from your authenticator app/SMS:` - type the
current code and it continues.

**No-prompt option:** pass your authenticator's setup key once and save it:

```bash
python -m app.main danidjokic --login-user sadster710 --login-pass PW --totp-seed YOURSEED --save-login
```

Then future runs generate the code automatically.

Then run the checklist in `QUALITY_GATE.md`.

## Restore (if anything looks wrong)

Delete the two edited files' changes by extracting the backup zip the applier
wrote (`../<repo>-backup-<timestamp>.zip`) over your repo.
