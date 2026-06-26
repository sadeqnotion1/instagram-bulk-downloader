# DECISIONS (append-only ADR)

## 2026-06-26 - instagrapi over instaloader
Chose `instagrapi` (private mobile API) because it handles the full media-type
matrix (photo/album/video/clip/igtv), session reuse, and authenticated
listing that the project needs.

## 2026-06-26 - paginate + download-as-you-go (not fetch-all-then-download)
`user_medias(amount=N)` fetches the entire list up front; one rate-limited page
then discards everything. We page with `user_medias_paginated(...)` and download
each page immediately so partial results are always kept.

## 2026-06-26 - pause-and-resume on rate limits
On a throttle we sleep and retry the SAME cursor (failed tuple-assignment leaves
the cursor untouched), bounded by MAX_RETRIES, budget resetting per good page.
Lets a whole profile finish in one run without provoking harder blocks.

## 2026-06-26 - manual CLI, no triggers (explicit user requirement)
No bot / scheduler / webhook. The tool is invoked only by the user.

## 2026-06-26 - incremental memory by post timestamp
Per-profile `state/<target>.json` stores the newest downloaded post's epoch
(`last_taken_ts`). Next run skips posts at/older than it and stops when a whole
page has no new posts (robust to page-1 pinned posts). `--full` ignores memory.
Meets the "rerun in two weeks -> only the new posts" requirement.

## 2026-06-26 - output layout @username + per-post folders
Files go to `<out>/@<target>/posts_<target>_<YYYY-MM-DD_HH-MM>/`, default root
`G:\Instagram\Users` (Windows). Per-post folders are named from `taken_at`.

## 2026-06-26 - saved login in repo (config.json)
User wants to avoid signing in every time. `config.json` holds login_user /
login_pass / two_factor; resolution order flags > env > config > prompt;
`--save-login` writes it. Stored plaintext but gitignored and chmod 0600 (best
effort); documented as a throwaway-account tradeoff.

## 2026-06-26 - CreateProject content authored clean
The `.agents/` brain and `launcher/` theme follow CreateProject's *shape* but
were written fresh, because the upstream template was flagged as carrying
obfuscated injected-instruction markers. Nothing was copied verbatim.
