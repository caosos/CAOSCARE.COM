# HA LAN relay

Home Assistant runs in a libvirt NAT VM (`192.168.122.137`). Wi-Fi room devices (Voice PE, IR Mate) and
phones must reach it, e.g. a Voice PE fetches spoken replies from HA by URL. `ha_lan_proxy.py` is a plain
TCP relay on `0.0.0.0:8123` → the VM, run as the user service `ha-lan-proxy.service`
(`systemctl --user link …/ha-lan-proxy.service && systemctl --user enable --now ha-lan-proxy`).
Exposes HA (its own login still applies) to the local network only. Owner-approved 2026-10-12.
Undo: `systemctl --user disable --now ha-lan-proxy`.
