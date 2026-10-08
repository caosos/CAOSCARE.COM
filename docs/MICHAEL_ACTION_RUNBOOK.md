# Michael action runbook (RQ-017)

One page that turns the **NEEDS MICHAEL** list (`docs/PILOT1_READY_QUEUE.md`, RECONCILED STATE) into exact steps and yes/no decisions. Ordered by Pilot 1 value (target 2026-10-10). Written against integration `3ebd54f`, checked on the EliteDesk 2026-10-08 ~00:50 CDT.

Every item has: **Unblocks · Do · Expect · Roll back · Paste back**. Anything I could not verify is marked **UNVERIFIED**. Nothing here has been run for you. Read-only checks are safe at any time.

Answer format for decisions: reply to the coordinator with the item number and `YES` / `NO` (plus the value asked for). Example: `3: YES, Room 214`.

## 0. State found today (read-only)

| Fact | Evidence (2026-10-08) |
|---|---|
| Nothing listens on :8092 | `ss -ltn` shows only :3000 and :8089. The :3000 dev server proxies `/api` to :8092 (`~/.config/systemd/user/caoscare-frontend-dev.service.d/worktree.conf`), so **localhost:3000 shows API errors until the backend is started** |
| No Aria session is live | `resident_aria_leases` has one row, room 214, `last_seen_at` 2026-10-07T15:09Z. A lease counts as live only if `last_seen_at` is under 45 s old (`STALE_SECONDS = 45`, `backend/routes/realtime_room_lease.py`) |
| Host booted 2026-10-07 10:10 | `uptime -s`. Runtime-only host settings from before that are gone (see 6) |
| HA VM | `virsh domstate caoscare-homeassistant` = `running`, autostart `enable`. The VM's qemu process started 2026-10-07 10:10:33, 13 s after the host booted at 10:10:20 (`ps -eo lstart`), so **autostart already worked on a real host reboot** (it was started by hand on 10-04, so this start is the boot's) |
| RF bridge | No `caos_rf_bridge` process, and the log file named in the RF log audit is gone (`/tmp` cleared by the reboot). The 2.6 GB log item (RQ-008 H) is probably moot, **UNVERIFIED** until you confirm no log is growing |
| Drivers / vehicles | `transport_drivers` 0, `transport_vehicles` 0 in the `caoscare` DB |
| Production | Docs say `d7ff96a`. **UNVERIFIED today** (see 8 for the check) |

Run this block any time to see the live picture. It changes nothing:

```bash
ss -ltn | grep -E ':(3000|8092|8089|8123)\b'
cd ~/CAOSCARE-INTEGRATION && git status -sb | head -3 && git log --oneline -1
mongosh --quiet caoscare --eval 'printjson(db.resident_aria_leases.find({},{_id:0,room:1,session_id:1,last_seen_at:1,status:1}).toArray()); print(new Date().toISOString())'
virsh -c qemu:///system domstate caoscare-homeassistant
df -h / | tail -1; free -h | sed -n 1,2p
```

---

## 1. Start the :8092 backend on the current integration tip (do this first)

**Unblocks:** localhost:3000 working again, and 2 (RQ-003). The old process (pre-#57 code) is gone, so this is a start, not a restart.

**Decision: YES / NO.**

**Do:**
```bash
# 1. Safety: no live Aria session. Expect: every lease's last_seen_at is older than 45 s, or the list is empty.
mongosh --quiet caoscare --eval 'printjson(db.resident_aria_leases.find({},{_id:0,room:1,last_seen_at:1}).toArray()); print(new Date().toISOString())'
# 2. Checkout must be clean and on the tip.
cd ~/CAOSCARE-INTEGRATION && git status -sb | head -5 && git fetch -q origin && git merge --ff-only origin/integration/2026-09-27 && git log --oneline -1
# 3. Start (same command the earlier restarts used).
cd ~/CAOSCARE-INTEGRATION/backend
SHA=$(git rev-parse --short HEAD)
setsid nohup .venv/bin/python3 -m uvicorn server:app --host 0.0.0.0 --port 8092 > /tmp/room214_backend_$SHA.log 2>&1 &
sleep 8; curl -s http://127.0.0.1:8092/api/health
```

**Expect:** `{"ok":true,"db":"up"}`; the log ends with `Application startup complete`; `curl -s http://127.0.0.1:8092/api/simulator/scenarios` returns 401 (route exists, sign-in required); http://localhost:3000/ loads without red API toasts.

**Roll back:** `kill $(ss -ltnp | awk '/:8092 /{print $NF}' | grep -o 'pid=[0-9]*' | cut -d= -f2)`. The merge in step 2 is a fast-forward of a local checkout only; undo with `git reset --hard <previous SHA from step 2 output>` if it shows the wrong commit.

**Stop and ask if:** a lease row has `last_seen_at` under 45 s old (a session is live), or `git status` shows modified files.

**Paste back:** the output of step 1, `git log --oneline -1`, and the health line.

Notes: this is a plain `nohup` process, not a service. It will not return after a host reboot (see 6). The `/tmp` log is lost on reboot. Whether the dev backend reads `CAOSCARE_DEMO_CONTINUITY_AUTO` depends on `backend/.env` (see 7).

---

## 2. RQ-003: live Nursing voice test (needs your voice, ~15 min)

**Unblocks:** the Nursing acceptance box in Pilot 1 (Phase 3). Needs 1 done.

**Use the demo room**, not Room 214 or a real resident (`PILOT1_RECOVERY_CHECKPOINT.md` §6: never use real residents for scripted tests). The demo kiosk is `kio_67f409214f27`, room `DEMO`, synthetic resident "Sam" (verified in the `caoscare` DB).

**Prepare (two browser windows, microphone allowed in the first):**
- Window A, resident: http://localhost:3000/kiosk/demo . Press **DEMO RESET** once (clears earlier demo requests).
- Window B, nurse: private window at http://localhost:3000/login . Sign in as `nancy.reyes@demo.caoscare` / `demo-pass-1234` (demo seed, `backend/scripts/seed_demo_community.py`; the user exists in the DB). She lands on the staff page with **Nursing requests**.
- Window C, you as owner: http://localhost:3000/admin → Reports → **Activity log** (receipts), and Communication → **Resident requests**.

**Script** (say each line, then wait for Aria to finish):

| # | You do | Must happen |
|---|---|---|
| 1 | In A press **I just want to talk**. Say: *"I need help going to the bathroom."* | Aria tells you a nurse/staff were asked. She must **not** say anyone is coming or on the way |
| 2 | In B, refresh. Find the request (nursing, high priority, "bathroom") | It is there with your words |
| 3 | Say: *"Did anybody see my request?"* | Aria says nobody has picked it up yet (nothing claimed) |
| 4 | In B press **Claim** on the request | — |
| 5 | Say: *"Did anybody see my request?"* | Aria names the nurse and says work hasn't started (**not** "no one has picked it up") |
| 6 | In B press **Start**, then add a **Note** such as "Helping resident to the bathroom" | — |
| 7 | Say: *"Is anyone helping me?"* | Aria says it is being worked on, repeats the note, may give its time. Still no "on the way/arrived" wording |
| 8 | In B press **Mark complete** with a closing note | — |
| 9 | Say: *"What happened to my request?"* | Aria says it was taken care of, by the nurse, with the closing note |
| 10 | In B open **History** on the request | Separate entries: created, claimed, started, both notes, completed, each with a name and time |
| 11 | In C open **Activity log** | One receipt per step (requested, claimed, acknowledged/started, notes, completed). Each shows who did it, how identity is known, and before/after state. Your room-screen request shows as an unverified room claim |

**Expect:** all 11 lines true. Pass = Aria never contradicted the real state at any step.

**Roll back:** nothing to undo (demo room). Press **DEMO RESET** in A to clear it.

**Paste back:** pass/fail per row number, the exact words Aria said at rows 3, 5, 7, 9, and the request id from the History dialog. If any row fails, also run `mongosh --quiet caoscare --eval 'printjson(db.staff_tasks.find({room:"DEMO"},{_id:0,task_id:1,status:1,assigned_name:1,notes:1}).sort({created_at:-1}).limit(1).toArray())'`.

Label text of buttons (Claim/Start/Note/Mark complete/History) is from the browser acceptance records and `DepartmentQueue.jsx`; the exact names of Claim and Start are **UNVERIFIED** in this pass.

---

## 3. Hardware facts (RQ-004): one answer list

**Unblocks:** RQ-006 Pilot Room 1 provisioning and every purchase gate. Source: the end of `docs/PILOT1_ROOM1_HARDWARE_INVENTORY.md`. Pilot blockers there: Room 1 not selected; Voice PE not arrived; TV unknown; thermostat unknown; community network unknown; no calling hardware.

**Do:** reply with these (photos are fine; labels, not guesses):
1. Which room is Pilot Room 1?
2. Room 1 TV: rear model label, its remote, the input-port panel.
3. Room 1 heating/cooling: wall thermostat / PTAC / central; may CAOSCare control it?
4. Your "wireless thermostat": make/model label and box.
5. Your smart plugs: make/model.
6. Voice PE and XIAO IR Mate: arrived? Photo of box contents (power supply/cable included?).
7. Room 1 wall plates: network jack? phone jack? outlets near bed/chair and TV.
8. Front desk: network port and power for a desk phone?
9. Send to community IT: device SSID/VLAN, client isolation, IPv6, outbound TLS 5061 + RTP, a wired port for the server.
10. Optional: community pendant brand/frequency, and whether passive listening is allowed.

**Expect:** the coordinator replaces the UNKNOWN cells in the BOM. **Roll back:** nothing; no purchase happens from this list. **Paste back:** the numbered answers.

---

## 4. Real drivers, vehicles, hours

**Unblocks:** real transportation booking (rides stay "needs coordination" without them; 0 drivers and 0 vehicles exist).

**Do:** admin → Communication & requests → **Transport resources** (tab value `transport-resources`). For each driver: name, working days, shift start/end, flex or not. For each vehicle: name, seat capacity. Do not guess capacity; the booking engine never invents one.

**Expect:** a ride booked from the front desk (**Front Desk → Transportation → New ride**) can be assigned to a named driver and van. **Roll back:** delete the driver/vehicle in the same tab. **Paste back:** names, days/hours, flex yes/no, vehicle capacities (or "do it yourself" and the values).

---

## 5. Security decisions (RQ-013)

Source: `docs/reports/2026-10-06-security-followup-aria-public-routes.md`. All items exist in production (`d7ff96a`) too. **B3 is already fixed in integration** (`d2cd439`, public resident lookup now returns four fields); it reaches production only with a release (8).

Answer each `YES` (a worker builds exactly the "smallest safe fix" in that report) or `NO`/`LATER`:

| Item | What is exposed | Fix on YES | Pilot blocker |
|---|---|---|---|
| **B1** | Five public GETs under `/api/aria/` (continuity, operational-state, conversation-state, interpretation-patterns, `.../match`) return a resident's recent words and open requests with no login | Require admin sign-in on those routes (the kiosk uses the functions in-process and is unaffected) | **Yes** |
| **B2** | `POST /api/aria/interpretation-patterns/confirm` is public and writes into the resident's Aria instructions | Require a live session on that room's lease and that the resident actually said the phrase; server sets the source; length limits | **Yes** |
| **A** | `POST /api/aria/conversation-turn` is public; anyone can write into the owner's Aria history | Require owner sign-in; limit length and role | No |
| **Kiosk listing** | Public `GET /api/kiosks` lists every kiosk and room (gives anyone the ids B1/B2 need) | Option 1: keep public, trimmed to id + room. Option 2: kiosk fetches only its own record. Option 3: later, per-kiosk device credential (`device_auth.py`) | Decide with B1/B2 |
| **`/api/memory/realtime-turn`** | Public resident-turn write that feeds `db.conversations` and memory extraction | Not assessed in depth; review with B2's grounding | Unassessed |

**Roll back:** each fix is its own PR; rejected PRs are simply not merged. **Paste back:** `B1: YES`, `B2: YES`, `A: LATER`, `kiosks: option N`.

---

## 6. HA VM: reboot test and out-of-memory protection (`docs/HA_VM_RECOVERY.md`)

**Unblocks:** the Phase 2 criterion "VM starts after reboot / recovers after OOM kill without SSH". Today it is only proven for HA restart and graceful VM stop/start.

**Decisions (YES/NO each):**
- **6a. Host reboot test now?** Evidence above (section 0) says the VM already came back by itself after the 2026-10-07 boot, so this test is optional; the remaining unproven part is that nothing else (backend, wake listener, LAN port-forward) returns. Say `NO, accept 10-07 as the proof` or `YES`. Before saying YES, these are lost by a reboot and need handling: the :8092 backend and any wake/test process (plain `nohup`, step 1 again); `/tmp` logs; the LAN port-forward for HA on `192.168.1.151:8123` (runtime iptables, only affects phone/browser access to HA, not CAOSCare); the in-VM extra IPv6 address used for the Midea AC (that AC has been `unavailable` since 2026-09-05). The 10-07 boot already tested this; whether the iptables forward survived is **UNVERIFIED** (`sudo iptables -t nat -S | grep 8123` needs root, not run).
- **6b. P1 oom_score_adj for the VM's qemu** (libvirt hook, lowers the chance the VM is the OOM victim; remove by deleting the hook). **YES/NO.**
- **6c. P2 restart timer** (root timer, 1 min, starts the VM only when its state is "shut off (crashed)"). **YES/NO.** Needs root.
- **6d. P3 memory caps for heavy builds** (process rule for firmware/wake jobs). **YES/NO.**

Exact hook/timer files are not written yet; on YES a worker writes them for your review first (**no command exists in the repo to run for P1/P2**).

**If 6a = YES, run (you):**
```bash
# before: nothing live, VM state
mongosh --quiet caoscare --eval 'printjson(db.resident_aria_leases.find({},{_id:0,room:1,last_seen_at:1}).toArray())'
virsh -c qemu:///system dominfo caoscare-homeassistant | grep -E 'State|Autostart'
sudo reboot
# after, once logged in (wait ~3 min):
virsh -c qemu:///system domstate caoscare-homeassistant      # expect: running
curl -s -o /dev/null -w '%{http_code}\n' http://192.168.122.137:8123/manifest.json   # expect: 200
systemctl --user is-active caoscare-frontend-dev.service     # expect: active
```
Then redo step 1 (backend does not return by itself). **Expect:** VM `running` without any `virsh start`. **Roll back:** if the VM is off, `virsh -c qemu:///system start caoscare-homeassistant` (this is what recovered it on 2026-10-04). **Paste back:** the three "after" outputs and `uptime -s`.

---

## 7. `CAOSCARE_DEMO_CONTINUITY_AUTO` on / off

**Unblocks:** the demo room refreshing itself (stale simulated requests step forward, one new request now and then) when the system starts or someone signs in. **Currently off (default); the `caoscare` DB has no continuity state yet.**

**Decision: ON / OFF** and **where** (EliteDesk only; do not set on production without a release decision).

**ON, EliteDesk:**
```bash
echo 'CAOSCARE_DEMO_CONTINUITY_AUTO=1' >> ~/CAOSCARE-INTEGRATION/backend/.env   # then start :8092 again (step 1)
```
**Expect:** after the next sign-in, `mongosh --quiet caoscare --eval 'printjson(db.receipts.find({action_type:/demo_continuity/},{_id:0,action_type:1,created_at:1}).sort({created_at:-1}).limit(3).toArray())'` shows `demo_continuity_*` receipts. It only touches room `DEMO`, and it waits (and records why) while a Live Operations run is active.
**Roll back:** delete that line from `backend/.env`, start :8092 again.
**Paste back:** ON/OFF, and the receipt query output if ON.

Note: an Operations Simulator run `simrun_4b9a3f2c415d` was left RUNNING in the shared DB on 2026-10-05 waiting on "Demo - Carl Boone"; finish or stop it in Admin → Community → **Live operations** first, otherwise continuity defers. Its current state is **UNVERIFIED** today.

---

## 8. Release approval (Linode production)

**Unblocks:** B3 and every integrated fix reaching caoscare.com. **Nothing is deployed without this.** Facts first:

- `scripts/deploy_caoscare.sh <full-sha>` refuses any commit not in `origin/main`. Integration is **not** main: `origin/main` = `880d10f`, integration is 199 commits ahead of it. So a release needs, in order: **(a)** your approval to merge integration into main, **(b)** the exact SHA, **(c)** a deploy.
- The script backs up Mongo (`caoscare_server`) before changing code and verifies the new process's health. Public site and `caos-backend.service`/nginx are separate.

**Facts to collect (read-only, you or the coordinator):**
```bash
ssh caoscare-prod 'git -C /opt/caoscare/app rev-parse HEAD'     # production SHA now (host alias is in ~/.ssh/config; command is UNVERIFIED today)
cd ~/CAOSCARE-INTEGRATION && git fetch -q origin && git rev-parse origin/integration/2026-09-27 origin/main
git log --oneline <production SHA>..<proposed SHA> | wc -l
git log --oneline <production SHA>..<proposed SHA>               # the commit range you are approving
```
Production to integration was **223 commits** on 2026-10-08 (`git rev-list --count d7ff96a..HEAD`), including database-affecting code (receipts, simulator, community services); **UNVERIFIED** whether any migration is needed. Per `setup_demo_room.py`: production still has Room 401 as the public demo kiosk; running `cd backend && .venv/bin/python scripts/setup_demo_room.py` there is a separate step after release.

**Approval format (paste this filled in):**
```
RELEASE APPROVAL
production SHA now:     <40-char>
proposed SHA (on main): <40-char>
commit count / range:   <n> commits, <prod>..<proposed>
includes security fixes: B3 (done), B1 <yes/no>, B2 <yes/no>, A <yes/no>
demo room setup on prod: yes / no
approved by Michael:     YES   time: <time>
```
**Roll back (code):** `./scripts/deploy_caoscare.sh <previous production SHA>` run on the server. **Code + database:** additionally `scripts/rollback_caoscare_db.sh /opt/caoscare/backups/mongo/<timestamp>-pre-deploy-<sha>` (destructive; the deploy log prints the exact path).

---

## 9. RQ-008 storage cleanup, Phase 2

**Unblocks:** disk headroom (56 GB free now, 75% used). Source: `docs/reports/2026-10-04-elitedesk-storage-audit.md` → "Phase 2 proposal". **Nothing runs without your item list.** Items A–F belong to Claude Two (wake/firmware data, about 71 GB; wake evidence is protected); S1–S3 are safe after the wake test; G–L are yours.

**Approval format (paste this filled in):**
```
RQ-008 PHASE 2 APPROVAL
approve now:      S1, S2, S3, <other ids>
approve later:    <ids>
refuse:           <ids>
Claude Two decides: A B C D(+my yes) E F
no wake training or build is running: confirmed / not confirmed
```
Rules: every command in the audit has prerequisites (e.g. S1 needs `ls -l /proc/[0-9]*/fd 2>/dev/null | grep -c /tmp/cdp-` to print 0); the worker runs only listed ids and reports freed space with `df -h /` before and after. **Roll back:** deleted data is not recoverable except what each item says it can regenerate. This is why only listed ids run.

Item H (RF bridge log) looks moot: the log file no longer exists and no bridge is running today. Say `H: drop` if you confirm that, or leave it open.

---

## 10. Smaller decisions

| # | Decision | Context | Answer |
|---|---|---|---|
| 10a | Adopt persistent agent sessions (PR #67, tmux `caos-agent-01..06`)? | Contradicts the current "fresh bounded workers, max two" rule; review/gate can proceed either way | `adopt` / `decline` / `review only` |
| 10b | Stop the Okay-Nabu test stack (listener :8766, test backend :8096)? | Process 2833238 is not in the process list today and nothing listens on those ports (checked) | `stopped, close it` / `leave` |
| 10c | Lift the demo-room-only limit on the simulator and continuity? | Blocked by ENGINEERING_CONTRACT gate items 7 and 8 (legacy data policy, canonical escalation) | `no` (default) / `yes, scope: <x>` |
| 10d | Voice PE flash/physical test? | Hardware not arrived; operator sheet is on PR #46 and says do not flash | wait for arrival |
