# SESSION LOG

## 2026-06-26 - initial scaffold
- Created the repo from scratch: `app/` (main/igclient/media), `launcher/`
  theme, run wrappers, README, START_HERE, .gitignore, `.agents/` brain.
- Ported the resilient pagination + pause-and-resume logic into a standalone,
  trigger-free CLI.
- Verified `py_compile` and `--help`. Live run still pending (M1).

## 2026-06-26 - memory + saved login + output layout
- Added `app/store.py`: saved login (`config.json`) and per-profile memory
  (`state/<target>.json`).
- `download_all()` now incremental (skip posts <= since_ts, stop when a page
  has no new posts) and writes to `<out>/@<target>/posts_<target>_<date>_<time>/`.
- `main.py`: `--save-login`, `--full`, default `--out G:\Instagram\Users`,
  login resolution flags > env > config > prompt; saves memory after each run.
- Updated README / START_HERE / .gitignore (config.json + state/ ignored).
- Re-verified py_compile + --help; live run still pending.
