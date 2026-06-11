# Workspace rules

## Authoritative repository

- **Repo root (the only place to edit):** `~/earnings-intelligence-os/backend`
- **Backend (Python / FastAPI):** repo root (`src/`, `app/`, `run_*.py`, `test_*.py`)
- **Frontend (Next.js):** `frontend/`

All other copies of this project (handoff folders, snapshots, secondary
clones such as `~/Desktop/Projects/earnings-intelligence-os/`) are
**read-only references**. Never edit, commit, or "sync" them unless
explicitly approved.

## Before editing any file (AI assistants and humans)

Run and check the output:

    pwd
    git rev-parse --show-toplevel   # must print .../earnings-intelligence-os/backend
    git status --short

If `git rev-parse` fails or prints a different path, **stop** — you are in
the wrong folder.

## Verification rules

- Do not assume a folder is a Git repository — verify `.git` exists.
- Do not state that files were copied, committed, pushed, or deployed
  without verified command output (or a fetch of the live URL).

## Secrets

- Never read into output, print, commit, or overwrite `.env`, `.env.*`,
  or deployment secrets. `.venv/`, `node_modules/`, `.next/`, and build
  artifacts are never copied between folders.
