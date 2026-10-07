# Persistent CAOSCare agent-team host runbook

## Prerequisites

```bash
cd ~/CAOSCARE-INTEGRATION
git fetch origin
command -v claude
command -v tmux
```

If tmux is missing on Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install tmux
```

Package installation is a host change; record it in PROJECT_STATE.

## Start / inspect

After PR #67 is accepted into the integration branch:

```bash
cd ~/CAOSCARE-INTEGRATION
git pull --ff-only
./scripts/caos-agent-team check
./scripts/caos-agent-team start-all
./scripts/caos-agent-team status
```

Attach to Agent 1:

```bash
./scripts/caos-agent-team attach 1
```

Detach without killing it: **Ctrl-b**, then **d**.

Nudge a worker after Agent 1 updates durable queue state:

```bash
./scripts/caos-agent-team nudge 3
```

## SSH-disconnect acceptance

Start the team, record `tmux list-sessions`, disconnect SSH completely, reconnect, then run `./scripts/caos-agent-team status`. All dedicated sessions must still exist.

## Reboot recovery

tmux does not survive a host reboot. Install the example user service only after review:

```bash
mkdir -p ~/.config/systemd/user
cp scripts/agent-team/caos-agent-team.service.example ~/.config/systemd/user/caos-agent-team.service
systemctl --user daemon-reload
systemctl --user enable --now caos-agent-team.service
```

For a user service to start before an interactive login, user lingering may need to be enabled:

```bash
loginctl show-user "$USER" -p Linger
sudo loginctl enable-linger "$USER"
```

Record the host change. Never enable a Linode agent-control service from this runbook.

## Recovery without systemd

```bash
cd ~/CAOSCARE-INTEGRATION
./scripts/caos-agent-team recover
```

The command is idempotent: existing dedicated sessions are kept and missing ones are started.
