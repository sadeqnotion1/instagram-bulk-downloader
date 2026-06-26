# ROADMAP

## M1 - Core bulk download (current)
- [x] Login + session reuse
- [x] Saved login (config.json)
- [x] Paginated listing + download-as-you-go
- [x] Pause-and-resume on rate limits
- [x] Incremental memory (per-profile, by post timestamp)
- [x] Output layout @username + per-post folders
- [ ] Live end-to-end verification

## M2 - Quality of life
- [ ] Skip already-downloaded media within a run (dedupe by pk)
- [ ] Save post metadata (captions, timestamps) as JSON sidecars
- [ ] `--only photos|videos|reels` filter
- [ ] `--since DATE` manual override of memory

## M3 - Robustness
- [ ] Challenge/2FA interactive handler
- [ ] Proxy support
- [ ] Encrypt saved credentials at rest
- [ ] Structured run report (counts, failures) to a log file
