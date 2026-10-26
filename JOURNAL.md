# Reflex — Lab Journal

## Sprint 1 · Oct 26 – Nov 1
**Goal:** the app runs in Docker on my laptop and data survives a restart

### 2026-10-25 — Step 1 done
- Repo `sre-platform` created, public, pushed
- Structure: reflex/api, reflex/web, .gitignore

**Errors hit**
- `Permission denied to deploy key` on push — the SSH key was registered as a
  deploy key on sre-lab instead of an account key. Moved it to Settings → SSH keys.
  Deploy key = one repo. Account key = all repos.

**Next**
- Step 2: read main.py and answer the four questions
