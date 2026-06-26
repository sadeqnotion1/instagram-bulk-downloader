# APPLY - CDN download-timeout + retry fix

**What this fixes:** login/listing worked, but every media file failed with
`... timed out. (connect timeout=1)`. instagrapi's default network timeout is
**1 second**, far too short to pull files from Instagram's CDN. This patch
raises the timeout to 20s and retries each item a few times on transient errors.

**Scope (minimal):** edits **only** `app/igclient.py`. Nothing else is touched.
The `[401] graphql` lines in your log are harmless - instagrapi tries the public
web API, fails, and falls back to the private API automatically.

---

## Easiest path - run the applier

From the **root of your repo** (the folder that contains `app/`):

```bash
python apply_timeout_fix.py --target . --check   # preview (writes nothing)
python apply_timeout_fix.py --target .           # backup, then patch
```

- Copy `apply_timeout_fix.py` into your repo root first (or pass `--target` with
  the full repo path).
- Backs up the whole repo to `../<repo>-backup-<timestamp>.zip` first.
- **Idempotent**: running twice is a no-op.
- **Aborts without writing** if your `app/igclient.py` differs from the expected
  baseline on a required anchor (then use the manual steps below).
- `--dry-run` shows the plan; `--no-backup` skips the backup.

---

## Manual merge (only if the applier aborts)

All edits are in `app/igclient.py`.

**1) Add three constants** right after the `WAIT_TICK = 15` line:

```python
REQUEST_TIMEOUT = 20  # seconds for API + media/CDN downloads (instagrapi default is 1!)
DOWNLOAD_RETRIES = 3  # attempts per media item on transient download errors
DOWNLOAD_RETRY_WAIT = 5  # seconds between download retries
```

**2) In `__init__`**, after `self.cl.delay_range = list(delay_range)` add:

```python
        self.cl.request_timeout = REQUEST_TIMEOUT
```

**3) In `login()`**, in the stale-session fallback, after
`self.cl.delay_range = [2, 5]` add (note the deeper indentation):

```python
                self.cl.request_timeout = REQUEST_TIMEOUT
```

**4) (Optional but recommended) Retry each item.** In `download_all`, replace
the per-item `try: ... except Exception as item_err: ...` block with:

```python
                saved = None
                for attempt in range(1, DOWNLOAD_RETRIES + 1):
                    try:
                        saved = [str(p) for p in download_one(self.cl, media, str(post_dir)) if p]
                        break
                    except Exception as item_err:
                        pk = getattr(media, "pk", "?")
                        if attempt < DOWNLOAD_RETRIES:
                            status(f"item {pk} failed (attempt {attempt}/{DOWNLOAD_RETRIES}): {item_err}; "
                                   f"retrying in {DOWNLOAD_RETRY_WAIT}s ...")
                            time.sleep(DOWNLOAD_RETRY_WAIT)
                        else:
                            log.warning(f"failed item {pk} after {DOWNLOAD_RETRIES} tries: {item_err}")
                            failed.append(str(pk))
                if saved is not None:
                    files.extend(saved)
                    if ts > newest_ts:
                        newest_ts = ts
```

---

## Tuning

- Slow connection / very large videos still timing out? Raise `REQUEST_TIMEOUT`
  (e.g. 30 or 45).
- Want more attempts on flaky CDNs? Raise `DOWNLOAD_RETRIES`.

## Run / verify

```bash
python -m app.main danidjokic --login-user sadster710
```

Files should now save under `G:\Instagram\Users\@danidjokic\posts_..._<date>\`
instead of logging `failed item ...`. Then run `QUALITY_GATE.md`.

## Restore

Extract `../<repo>-backup-<timestamp>.zip` over your repo.
"""
