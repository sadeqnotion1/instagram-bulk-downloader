# AGENTS.md - project brain entry point

**Project:** instagram-bulk-downloader
**What:** A manual CLI that downloads an Instagram profile's posts via
`instagrapi`. Saved login + per-profile memory (incremental). No bot, no
scheduler, no background triggers.
**Stack:** Python 3.9+, instagrapi, Pillow.

Read these in order before doing anything, then report back:
- `.agents/brain/STATE.md` - where the project is.
- `.agents/brain/NEXT.md` - the single next task.
- `.agents/brain/ROADMAP.md` - milestones.
- `.agents/brain/PLAYBOOK.md` - working rules.
- `.agents/brain/DECISIONS.md` - the "why" (skim latest).

## Repo layout (high level)
> Follows the Project Scaffolding Standard: minimal root, fewest folders,
> run files + README + .gitignore at root; all code under `app/`.

- `app/main.py` - CLI entry (`python -m app.main`).
- `app/igclient.py` - login/session + incremental, resilient `download_all()`.
- `app/media.py` - per-media-type download dispatch.
- `app/store.py` - saved login (`config.json`) + memory (`state/<target>.json`).
- `launcher/ui_theme.py` - dependency-free terminal theme.

## Behaviour notes
- Output: `<out>/@<target>/posts_<target>_<date>_<time>/`, default out root
  `G:\Instagram\Users`.
- Memory: reruns fetch only posts newer than the last run; `--full` overrides.
- Login: flags > env (`IG_USERNAME`/`IG_PASSWORD`) > `config.json` > prompt;
  `--save-login` persists it.

## Prompts
- `prompts/start.md` - kickoff prompt for a new AI session.
- `prompts/wrap-up.md` - closing prompt to update this brain.
