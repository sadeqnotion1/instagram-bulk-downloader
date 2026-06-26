"""Instagram login + resilient, incremental \"download posts\" logic.

Logs in (reusing a cached session when possible) and pages through a target
profile's media list, downloading each page as it arrives into
``<out>/@<username>/posts_<username>_<date>_<time>/``.

Two behaviours worth knowing:

* **Incremental memory.** Pass ``since_ts`` (the newest post timestamp from a
  previous run). Posts at or older than it are skipped, and once a whole page
  has no new posts we stop - so a rerun two weeks later only fetches the new
  posts. ``since_ts=0`` downloads everything.
* **Pause-and-resume.** On an Instagram rate limit it PAUSES and RESUMES from
  the same cursor, so a full profile can be fetched in one run.

No bot, no scheduler - it is driven only by an explicit call from the CLI.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from app.media import download_one

log = logging.getLogger("ig")

# --- pacing / resilience knobs (tune to taste) ------------------------------
PAGE_SIZE = 50        # media per listing request (Instagram caps ~50)
PAGE_DELAY = 3.0      # seconds between successful listing pages
RETRY_WAIT = 300      # base seconds to wait after a rate limit (x retry number)
MAX_RETRIES = 3       # rate-limit retries per stall (resets after a good page)
WAIT_TICK = 15        # how often (s) to refresh the wait countdown
REQUEST_TIMEOUT = 20  # seconds for API + media/CDN downloads (instagrapi default is 1!)
DOWNLOAD_RETRIES = 3  # attempts per media item on transient download errors
DOWNLOAD_RETRY_WAIT = 5  # seconds between download retries


def _is_rate_limit(err):
    """True if `err` looks like an Instagram throttle we should wait out."""
    name = type(err).__name__.lower()
    msg = str(err).lower()
    return (
        "pleasewait" in name
        or "throttl" in name
        or "ratelimit" in name
        or "wait a few minutes" in msg
        or "try again" in msg
        or "429" in msg
        or "too many" in msg
    )


def _taken_ts(media):
    """Epoch seconds for a media's taken_at (0.0 if unavailable)."""
    ta = getattr(media, "taken_at", None)
    if ta is None:
        return 0.0
    try:
        return ta.timestamp()
    except Exception:
        return 0.0


def _post_folder(target, media):
    """Folder name like ``2026-05-01_14-24`` from taken_at."""
    ta = getattr(media, "taken_at", None)
    stamp = "unknown"
    if ta is not None:
        try:
            stamp = ta.strftime("%Y-%m-%d_%H-%M")
        except Exception:
            stamp = "unknown"
    if stamp == "unknown":
        return f"unknown_{media.pk}"
    return stamp


class InstagramArchiver:
    """Thin wrapper around instagrapi for one-profile bulk downloads."""

    def __init__(self, session_path, delay_range=(2, 5)):
        # Import lazily so `--help` works without instagrapi installed.
        from instagrapi import Client

        self.session_path = Path(session_path)
        self.cl = Client()
        self.cl.delay_range = list(delay_range)
        self.cl.request_timeout = REQUEST_TIMEOUT

    # -- auth ----------------------------------------------------------------
    def _save_session(self):
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        self.cl.dump_settings(self.session_path)

    def _totp_code(self, totp_seed):
        """Generate a fresh 6-digit code from a TOTP seed (or '')."""
        if not totp_seed:
            return ""
        try:
            return self.cl.totp_generate_code(totp_seed)
        except Exception as e:
            log.warning(f"could not generate TOTP code from seed: {e}")
            return ""

    def login(self, username, password="", verification_code="", totp_seed="",
              on_need_2fa=None, on_need_password=None):
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

        # 1) Try an existing session first - usually no password/2FA needed.
        if self.session_path.exists():
            session_loaded = False
            try:
                self.cl.load_settings(self.session_path)
                self.cl.request_timeout = REQUEST_TIMEOUT
                session_loaded = True
                self.cl.get_timeline_feed()  # validate the session
                log.info("reused saved session.")
                self._save_session()
                return True
            except Exception as e:
                log.warning(f"saved session invalid ({e}); logging in fresh.")
                if not session_loaded:
                    from instagrapi import Client  # lazy: only needed to reset
                    self.cl = Client()
                    self.cl.delay_range = [2, 5]
                    self.cl.request_timeout = REQUEST_TIMEOUT
                else:
                    # Keep the loaded device profile but clear session data
                    try:
                        self.cl.set_cookies({})
                    except Exception:
                        pass
                    self.cl.authorization_data = {}

        # 2) Fresh login: prompt for password if not provided
        active_password = password
        if not active_password and on_need_password is not None:
            active_password = on_need_password()
        if not active_password:
            raise ValueError("Password is required for fresh login.")

        # A code to try on the first attempt (seed wins, else any passed code).
        first_code = self._totp_code(totp_seed) or verification_code

        # 3) Fresh login, retrying once with a 2FA code if required.
        try:
            self.cl.login(username, active_password, verification_code=first_code)
        except Exception as e:
            if not _needs_2fa(e):
                raise
            code = self._totp_code(totp_seed)
            if not code and on_need_2fa is not None:
                code = (on_need_2fa() or "").strip()
            if not code:
                raise
            log.info("submitting 2FA verification code ...")
            self.cl.login(username, active_password, verification_code=code)

        log.info("logged in with password.")
        self._save_session()
        return True

    def _migrate_archive(self, target, user_dir):
        """Rename old-format folders and files to the new format."""
        prefix = f"posts_{target}_"
        for p in list(user_dir.iterdir()):
            if p.is_dir() and p.name.startswith(prefix):
                stamp = p.name[len(prefix):]
                new_dir = user_dir / stamp
                
                # Check for collision
                if new_dir.exists():
                    # Move all files from old dir to new dir
                    for f in p.iterdir():
                        if f.is_file():
                            dest_file = new_dir / f.name
                            if not dest_file.exists():
                                try:
                                    f.rename(dest_file)
                                except Exception:
                                    pass
                    # Remove empty old dir
                    try:
                        p.rmdir()
                    except Exception:
                        pass
                else:
                    # Rename the entire directory
                    try:
                        p.rename(new_dir)
                    except Exception:
                        pass
                
        # Now rename any files inside the new directories that still have the old username_ prefix or start with an extra "_"
        for p in user_dir.iterdir():
            if p.is_dir() and not p.name.startswith("posts_"):
                for f in p.iterdir():
                    if f.is_file():
                        if f.name.startswith(f"{target}_"):
                            new_name = f.name[len(target) + 1:]
                        elif f.name.startswith("_"):
                            new_name = f.name[1:]
                        else:
                            continue
                        
                        dest = f.parent / new_name
                        if dest.exists():
                            try:
                                f.unlink()
                            except Exception:
                                pass
                        else:
                            try:
                                f.rename(dest)
                            except Exception:
                                pass

    # -- bulk / incremental download ----------------------------------------
    def download_all(self, target, out_dir, limit=0, on_status=None, since_ts=0.0):
        """Download posts of `target` into out_dir/@<target>/posts_<...>/.

        If `since_ts` > 0, only posts strictly newer than it are downloaded
        (incremental mode). Returns a summary dict including `newest_ts`, the
        timestamp of the newest post seen this run (save it for next time).
        Keeps everything fetched even if a later page is rate limited.
        """
        def status(msg):
            if on_status:
                on_status(msg)
                log.debug(msg)
            else:
                log.info(msg)

        mode = "new posts only" if since_ts else "all posts"
        status(f"resolving @{target} ({mode}) ...")
        try:
            user_id = str(self.cl.user_info_by_username_v1(target).pk)
        except Exception as e:
            log.warning(f"private user lookup failed ({e}); falling back to standard lookup.")
            user_id = self.cl.user_id_from_username(target)

        user_dir = Path(out_dir) / f"@{target}"
        user_dir.mkdir(parents=True, exist_ok=True)
        self._migrate_archive(target, user_dir)

        files = []
        failed = []
        end_cursor = ""
        fetched = 0
        skipped = 0
        page_no = 0
        retries = 0
        newest_ts = float(since_ts or 0.0)
        stopped_early = False
        reached_old = False

        while True:
            page_no += 1
            status(f"listing @{target} (page {page_no}, {fetched} new so far) ...")
            try:
                page, end_cursor = self.cl.user_medias_paginated(
                    user_id, amount=PAGE_SIZE, end_cursor=end_cursor
                )
                retries = 0  # a good page resets the per-stall retry budget
            except Exception as e:
                if _is_rate_limit(e) and retries < MAX_RETRIES:
                    retries += 1
                    wait_s = int(RETRY_WAIT * retries)
                    status(
                        f"rate limited at page {page_no} ({fetched} so far); "
                        f"waiting {wait_s}s then resuming "
                        f"(retry {retries}/{MAX_RETRIES}) ..."
                    )
                    waited = 0
                    while waited < wait_s:
                        remaining = wait_s - waited
                        status(
                            f"rate limited - resuming @{target} in {remaining}s "
                            f"(got {fetched}) ..."
                        )
                        step = WAIT_TICK if remaining > WAIT_TICK else remaining
                        time.sleep(step)
                        waited += step
                    page_no -= 1   # the retry is not a new page
                    continue        # retry the same cursor
                stopped_early = True
                status(f"listing stopped after {fetched} item(s): {e}")
                break

            if not page:
                break

            new_in_page = 0
            for media in page:
                if limit and fetched >= limit:
                    break
                ts = _taken_ts(media)
                # Incremental: skip posts we already had last time.
                if since_ts and ts and ts <= since_ts:
                    skipped += 1
                    continue

                # Check if directory already exists and has files (already downloaded)
                post_dir = user_dir / _post_folder(target, media)
                if post_dir.exists() and any(post_dir.iterdir()):
                    skipped += 1
                    status(f"skipping already-downloaded post: {post_dir.name}")
                    if ts > newest_ts:
                        newest_ts = ts
                    continue

                fetched += 1
                new_in_page += 1
                post_dir.mkdir(parents=True, exist_ok=True)
                status(f"downloading {fetched} from @{target} -> {post_dir.name} ...")
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

            if limit and fetched >= limit:
                status(f"reached limit of {limit}.")
                break
            # Incremental: a full page with no new posts means we're caught up.
            if since_ts and new_in_page == 0:
                reached_old = True
                status("no new posts on this page; already up to date.")
                break
            if not end_cursor:
                break
            time.sleep(PAGE_DELAY)  # pace pagination to avoid rate limits

        if stopped_early:
            status(
                f"partial result: {len(files)} file(s) saved before listing stopped."
            )

        return {
            "target": target,
            "out_dir": str(user_dir),
            "listed": fetched,
            "skipped": skipped,
            "downloaded": len(files),
            "files": files,
            "failed": failed,
            "newest_ts": newest_ts,
            "since_ts": float(since_ts or 0.0),
            "reached_old": reached_old,
            "complete": not stopped_early,
        }
