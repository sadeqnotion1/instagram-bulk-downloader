# QUALITY GATE - 2FA login fix

Keep the change only if ALL of these pass. Otherwise restore the backup zip the
applier wrote (`../<repo>-backup-<timestamp>.zip`) and nothing is lost.

## Checks

- [ ] **Compiles.** From the repo root:
  ```bash
  python -m py_compile app/igclient.py app/main.py
  ```
  No output = success.

- [ ] **CLI still parses** (works even without instagrapi installed):
  ```bash
  python -m app.main --help
  ```
  The help text now lists `--totp-seed`.

- [ ] **Existing features unchanged.** Memory (incremental), saved login,
  per-post folders, pause-and-resume, and the `@username` output path all still
  behave as before - this patch only touched `login()` and the login wiring.

- [ ] **2FA path works** on a real run: after the password you are prompted for
  the 6-digit code (or, with `--totp-seed`, it logs in without a prompt) and the
  download proceeds.

- [ ] **Edits are minimal** - only `app/igclient.py` and `app/main.py` changed.

- [ ] **Backup exists** - `../<repo>-backup-<timestamp>.zip` was created.

## Status check shortcut

```bash
python apply_2fa_fix.py --target . --check   # rc 0 = applied, rc 1 = not
```

## What was NOT changed

- No new dependencies (TOTP code generation uses instagrapi's built-in
  `totp_generate_code`).
- No automation/triggers were added - the tool is still fully manual.
- No other files, features, or settings were modified.
