# instagram-bulk-downloader

Download an Instagram profile's posts from the command line, built on
[`instagrapi`](https://github.com/subzeroid/instagrapi). It is a **manual tool**:
you run it, it logs in, downloads the posts, and exits.

> **No automation triggers.** There is no bot, no scheduler, no webhook, no
> background worker. Nothing runs unless you run it yourself.

Layout follows SadeQ's Project Scaffolding Standard (minimal root, thin run
wrappers) and reuses the `.agents/` AI-brain + `launcher/` theme idea from
`CreateProject` (clean-authored here, not copied).

## Features

- **Saved login.** Store your credentials once with `--save-login`; after that
  you don't sign in every run. (Resolution order: flags > env vars >
  `config.json` > prompt.) A session is also cached so reruns skip re-auth.
- **Memory / incremental downloads.** The tool remembers the newest post it
  downloaded for each profile. Run it again two weeks later and it downloads
  **only the posts from those two weeks** - everything older is skipped. Use
  `--full` to ignore memory and (re)download everything.
- **Organised output.** Files are saved as
  `G:\Instagram\Users\@<username>\posts_<username>_<date>_<time>\` - one
  folder per post, named from the post's timestamp.
- **Pause-and-resume on rate limits.** If Instagram throttles mid-run, it waits
  and retries the *same* cursor (a few times; budget resets after each good
  page) so a large profile can finish in one run. Whatever is fetched is kept.
- `--limit N` to grab only the most recent N posts.

## Output layout

With `--out G:\Instagram\Users` (the default) and target `a83ssa66`:

```text
G:\Instagram\Users\
└── @a83ssa66\
    ├── posts_a83ssa66_2026-05-01_14-24\   # one folder per post (taken_at)
    │   └── <photo/video/album files>
    └── posts_a83ssa66_2026-05-03_09-12\
        └── ...
```

## Project layout

```text
instagram-bulk-downloader/
├── app/                  # all the code
│   ├── main.py           # CLI entry (python -m app.main)
│   ├── igclient.py       # login/session + incremental, resilient download
│   ├── media.py          # per-media-type download dispatch
│   ├── store.py          # saved login + per-profile memory (JSON)
│   └── requirements.txt
├── launcher/             # dependency-free terminal theme
├── .agents/              # AI project brain (CreateProject style)
├── config.example.json   # copy to config.json to save a login
├── run.bat / run.sh
├── README.md / START_HERE.md
└── .gitignore
```

## Install

```bash
python -m pip install -r app/requirements.txt
chmod +x run.sh        # macOS/Linux, once
```

## Use

### 1. Save your login once (optional but recommended)

```bat
REM Windows
run.bat anyprofile --login-user your_login --login-pass your_pass --save-login
```

This writes `config.json` (plaintext, **gitignored**). From then on just:

```bat
run.bat natgeo
```

Prefer not to store the password? Use env vars instead:

```bash
export IG_USERNAME=your_login
export IG_PASSWORD=your_password   # or omit to be prompted
./run.sh natgeo
```

### 2. Download

```bash
./run.sh natgeo                 # new posts since last run (all on first run)
./run.sh natgeo --full          # ignore memory, (re)download everything
./run.sh natgeo --limit 50      # only the 50 most recent
./run.sh natgeo --out D:\IG     # custom output root
```

Without the run wrapper: `python -m app.main natgeo --login-user your_login`.

### Options

| Flag | Meaning |
|---|---|
| `username` | target profile to download (positional, no `@`) |
| `--login-user` | your Instagram login (or `IG_USERNAME`, or saved) |
| `--login-pass` | your password (or `IG_PASSWORD`; prompted if omitted) |
| `--save-login` | save the login to `config.json` for next time |
| `--2fa CODE` | 2FA verification code, if your account uses it |
| `--full` | ignore memory and (re)download all posts |
| `--limit N` | max posts (0 = all, default) |
| `--out DIR` | output root (default `G:\Instagram\Users`) |
| `--session PATH` | session file (default `./sessions/<login-user>.json`) |
| `--no-banner` | disable the themed banner |

Tune pacing/retries at the top of `app/igclient.py`
(`PAGE_SIZE`, `PAGE_DELAY`, `RETRY_WAIT`, `MAX_RETRIES`, `WAIT_TICK`).

## How the memory works

After each run the newest post's timestamp is saved to
`state/<target>.json`. The next run downloads only posts newer than that and
stops once it reaches a page with nothing new. Delete that file (or pass
`--full`) to start over. `state/` is gitignored.

## Notes & limits

- **Saved password is plaintext.** `config.json` is gitignored so it won't be
  committed, but anyone with access to the folder can read it. Use a throwaway
  account if that worries you, or rely on env vars / the prompt instead.
- You must log in with a real account; Instagram requires auth to list a
  profile's media.
- Rate limits are account/IP-wide. If a cooldown is longer than the total retry
  budget, the run keeps what it got - rerun later and memory continues where it
  left off.
- Respect Instagram's Terms of Service; download only content you're allowed to.
- **Verification:** the code is syntax-checked (`py_compile`) and the CLI parses
  (`--help`) without instagrapi installed, but it has **not** been run against a
  live Instagram account in this build environment.
