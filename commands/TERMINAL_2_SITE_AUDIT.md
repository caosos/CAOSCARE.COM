# TERMINAL 2 — CAOS Care Site, EliteDesk, DNS, and Deployment Audit

## Instruction to Claude Code

Perform this investigation now from the root of the `caosos/CAOSCARE.COM` repository on the EliteDesk.

This is an **audit-only** session. Do not edit files, install packages, change DNS, open ports, create accounts, generate credentials, deploy, commit, push, start services, stop services, or expose the machine publicly.

Never print passwords, tokens, client secrets, JWT secrets, API keys, cookies, or `.env` values. Report only whether required variables are present, missing, blank, or malformed.

First read:

1. `AGENTS.md`
2. `docs/PROJECT_STATE.md`
3. `docs/REPO_MAP.md`
4. `docs/BUILD_STATUS.md`
5. `docs/DEPLOYMENT_RUNBOOK.md`

Investigate the EliteDesk and determine:

- Whether this local checkout matches the current GitHub `main` branch.
- Current branch, commit, working-tree cleanliness, and remote.
- Whether MongoDB is installed and running.
- Whether backend and frontend dependencies exist.
- Whether ports `3000`, `8000`, `8080`, `80`, `443`, and `27017` are listening.
- Whether CAOS Care, Uvicorn, React, Node, Nginx, Caddy, MongoDB, Cloudflare Tunnel, or related systemd processes and services exist.
- Whether the local frontend and backend are reachable.
- Whether `http://127.0.0.1:8000/api/health` works.
- Whether a reverse-proxy configuration already exists.
- Whether `cloudflared` is installed.
- Whether `backend/.env` and `frontend/.env` exist and contain the required variable names, without displaying their values.
- Whether Google OAuth configuration is structurally ready for localhost and what must change for `caoscare.com`.
- Current DNS resolution for `caoscare.com` and `www.caoscare.com`.
- Current HTTP and HTTPS behavior for both hostnames.
- Whether GitHub Pages, Vercel, Netlify, Render, Railway, Linode, Cloudflare, or another deployment target is actually configured in the repository or on this host.
- Why the public website cannot currently be inspected.
- Whether the current application can safely be exposed as a temporary preview.

Use only non-destructive inspection commands such as `git status`, `git log`, `git remote`, `git diff`, `curl`, `getent`, `dig`, `host`, `nslookup`, `ss`, `lsof`, `ps`, `pgrep`, `systemctl status`, `systemctl is-active`, `find`, `ls`, `grep`, and version checks.

Return one evidence-backed Markdown report in the terminal with these sections:

1. EliteDesk runtime state
2. Local application state
3. Domain and DNS state
4. Authentication and credential state
5. Existing deployment configuration
6. What is missing
7. Exact non-destructive verification commands used
8. Three concrete paths
   - Local-only development
   - Temporary public preview
   - Production `caoscare.com` deployment
9. Safest immediate next command for Michael

Do not execute any recommended mutating command. Report it only.