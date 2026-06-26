# QUALITY GATE - CDN download-timeout + retry fix

Keep the change only if ALL of these pass. Otherwise restore the backup zip the
applier wrote (`../<repo>-backup-<timestamp>.zip`) and nothing is lost.

## Checks

- [ ] **Compiles.** From the repo root:
  ```bash
  python -m py_compile app/igclient.py
  ```
  No output = success.

- [ ] **CLI still parses** (works without instagrapi installed):
  ```bash
  python -m app.main --help
  ```

- [ ] **Downloads now succeed** on a real run: items save under
  `G:\Instagram\Users\@<target>\posts_..._<date>\` instead of logging
  `failed item ... connect timeout=1`.

- [ ] **Status shortcut:**
  ```bash
  python apply_timeout_fix.py --target . --check   # rc 0 = applied
  ```

- [ ] **Edits are minimal** - only `app/igclient.py` changed.

- [ ] **Backup exists** - `../<repo>-backup-<timestamp>.zip` was created.

## What was NOT changed

- No new dependencies.
- No automation/triggers - the tool stays fully manual.
- 2FA, memory/incremental, per-post folders, the `@username` path, and
  pause-and-resume are untouched.

## Still seeing timeouts?

The `[401] graphql` lines are normal (public-API fallback). If large videos on
a slow link still time out, raise `REQUEST_TIMEOUT` (e.g. 30-45) and/or
`DOWNLOAD_RETRIES` near the top of `app/igclient.py`.
