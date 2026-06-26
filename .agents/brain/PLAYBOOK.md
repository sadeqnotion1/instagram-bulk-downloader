# PLAYBOOK - working rules

## Principles
1. **Manual only.** Never add bots, schedulers, webhooks, or background
   triggers. The tool runs only when the user runs it.
2. **Minimal, anchored edits.** Prefer small additions over rewrites. Don't
   invent Instagram API behavior - ground it in instagrapi's source.
3. **Keep secrets out of git.** Credentials via env vars / prompt only;
   `sessions/` and `downloads/` stay gitignored.
4. **Be gentle with Instagram.** Keep the pacing delays and pause-and-resume;
   don't crank `PAGE_SIZE` or remove the per-page sleep.

## Scaffolding
- Follow the Project Scaffolding Standard: minimal root, all code in `app/`.
- Thin run wrappers only; real logic lives under `app/`.

## Session loop
- Start: read the brain (see AGENTS.md), report state + next task.
- Work: implement the single NEXT task; keep `py_compile` green.
- Wrap up: update STATE.md / NEXT.md / SESSION_LOG.md (use prompts/wrap-up.md).
