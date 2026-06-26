# START HERE

This repo downloads an **Instagram profile's posts** from the terminal.
Manual only - no bot, no scheduler, no triggers.

## 1. Install Python deps

```bash
python -m pip install -r app/requirements.txt
```

## 2. Save your login once (so you don't sign in every time)

```bat
REM Windows
run.bat anyprofile --login-user your_login --login-pass your_pass --save-login
```

```bash
# macOS / Linux
chmod +x run.sh
./run.sh anyprofile --login-user your_login --login-pass your_pass --save-login
```

This writes `config.json` (plaintext, gitignored). Prefer not to store it? Set
`IG_USERNAME` / `IG_PASSWORD` env vars instead, or let it prompt you.

## 3. Download a profile

```bash
./run.sh natgeo            # new posts since last run (all on the first run)
./run.sh natgeo --full     # ignore memory, (re)download everything
./run.sh natgeo --limit 30 # just the latest 30
```

```bat
REM Windows
run.bat natgeo
```

## What you get

Media is saved to:

```
G:\Instagram\Users\@<target>\posts_<target>_<date>_<time>\
```

(one folder per post). Change the root with `--out`.

**Memory:** the newest post downloaded per profile is remembered in
`state/<target>.json`, so reruns only fetch newer posts. If Instagram
rate-limits you mid-run, it waits and resumes; whatever it fetched is kept.

Full docs: `README.md`. Tunables: top of `app/igclient.py`.
