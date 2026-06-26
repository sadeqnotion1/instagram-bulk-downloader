# STATE

## Status: working scaffold, not yet run against live Instagram

### Done
- CLI entry (`app/main.py`) with argparse, env-var login, optional 2FA.
- **Saved login** (`config.json` via `app/store.py`, `--save-login`): flags >
  env > config > prompt. Session also cached/reused.
- **Memory / incremental** (`state/<target>.json`): remembers newest post
  downloaded; reruns fetch only newer posts; `--full` overrides.
- **Output layout**: `<out>/@<target>/posts_<target>_<date>_<time>/`, default
  out root `G:\Instagram\Users`.
- Resilient `download_all()`: paginated listing, download-as-you-go,
  pause-and-resume on rate limits, partial-result keeping.
- Per-media-type dispatch (`app/media.py`): photo / album / video / clip / igtv.
- Dependency-free terminal theme (`launcher/ui_theme.py`).
- Run wrappers, README, START_HERE, .gitignore per the Scaffolding Standard.

### Verified
- `py_compile` passes on all modules.
- `python -m app.main --help` works without instagrapi installed (lazy import).
- store.py memory round-trip (save_state/load_state) checked in sandbox.

### Not verified
- Live login + real download (needs real credentials + instagrapi installed).
- 2FA / challenge flows.
- Pinned-post ordering vs. the incremental stop heuristic (skip-per-item +
  stop when a whole page has no new posts; should be robust to page-1 pins).

### Known issues / risks
- `config.json` stores the password in plaintext (gitignored). Use a throwaway
  account or env vars if that's a concern.
- Instagram rate limits are account/IP-wide; long cooldowns can exceed the
  retry budget (rerun later - memory continues where it left off).
