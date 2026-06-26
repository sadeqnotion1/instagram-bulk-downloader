# NEXT - the single next task

**Task:** Run a real end-to-end download against a throwaway Instagram account.

**Done when:**
- `pip install -r app/requirements.txt` succeeds.
- `./run.sh <profile> --login-user <you>` logs in, caches the session, and
  saves media into `downloads/<profile>/`.
- A mid-run rate limit shows the wait countdown and resumes (or keeps a partial
  set) instead of crashing.

**To give the AI:** login credentials (via env vars, never pasted in chat) and
the target profile handle.
