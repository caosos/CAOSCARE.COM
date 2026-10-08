# CAOSCare Pilot 1 — Asterisk configuration

Design, decisions and acceptance tests: `docs/PILOT1_COMMUNICATIONS.md` §2.
Not yet run on real Asterisk; written for Asterisk 18 (Ubuntu 22.04 package).

| File | Purpose |
|---|---|
| `pjsip.conf` | Transports, templates, OpenAI Realtime SIP trunk; includes `pjsip_local.conf` |
| `pjsip_local.conf.example` | Room handsets, front desk phone, SIP trunk, per-room DID (copy and fill) |
| `extensions.conf` | Dialplan: 0, 911/9911/933, 700 (Aria), REFER transfers, front desk alert |
| `extensions_local.conf.example` | Front desk extension, OpenAI project id, CAOSCare API URL + token |
| `ari.conf`, `ari_local.conf.example`, `http.conf` | Local ARI for call-state events |
| `caos-911-alert.sh` | Background call file that rings the front desk on a 911 call |

Install outline (needs sudo; not done):

1. `apt install asterisk` (includes res_pjsip, res_ari, func_curl).
2. Copy these files to `/etc/asterisk/`; create the three `*_local.conf` from the examples; `chmod 640` them, owner `asterisk`.
3. Install `caos-911-alert.sh` as `/etc/asterisk/caos-911-alert.sh` (executable by `asterisk`).
4. `asterisk -rx "core reload"`; check `pjsip show endpoints`, `pjsip show registrations`, `ari show apps`.
5. Backend env: `ASTERISK_ARI_URL=http://127.0.0.1:8088`, `ASTERISK_ARI_USER=caoscare`, `ASTERISK_ARI_PASSWORD`, `CAOS_TELEPHONY_TOKEN`; restart the backend.

The `*_local.conf` files hold passwords and account data and are git-ignored.
