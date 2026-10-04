"""Start the CAOSCare backend on a validated address.

    CAOSCARE_BIND_HOST   default 127.0.0.1 (this machine only)
    CAOSCARE_BIND_PORT   default 8000

Allowed hosts: 127.0.0.1, ::1, and 192.168.122.1 - the EliteDesk's libvirt
bridge (virbr0), which the Home Assistant VM can reach and the outside
network cannot. 0.0.0.0 / :: and any other address are refused: wider
exposure needs its own decision and firewall review, not a variable change.

    cd backend && .venv/bin/python serve.py
    CAOSCARE_BIND_HOST=192.168.122.1 CAOSCARE_BIND_PORT=8092 .venv/bin/python serve.py
"""
import ipaddress
import os
import sys

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
HA_VM_BRIDGE_HOST = "192.168.122.1"
ALLOWED_HOSTS = ("127.0.0.1", "::1", HA_VM_BRIDGE_HOST)


def resolve_bind(env=None) -> tuple:
    """(host, port) from the environment, or ValueError explaining the refusal."""
    env = os.environ if env is None else env
    host = (env.get("CAOSCARE_BIND_HOST") or DEFAULT_HOST).strip()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        raise ValueError(f"CAOSCARE_BIND_HOST must be an IP address, got '{host}'")
    if host not in ALLOWED_HOSTS:
        raise ValueError(f"CAOSCARE_BIND_HOST '{host}' is not allowed (allowed: {', '.join(ALLOWED_HOSTS)})")
    raw_port = (env.get("CAOSCARE_BIND_PORT") or str(DEFAULT_PORT)).strip()
    if not raw_port.isdigit() or not 1024 <= int(raw_port) <= 65535:
        raise ValueError(f"CAOSCARE_BIND_PORT must be 1024-65535, got '{raw_port}'")
    return host, int(raw_port)


def main():
    try:
        host, port = resolve_bind()
    except ValueError as e:
        sys.exit(f"refusing to start: {e}")
    print(f"CAOSCare backend binding {host}:{port}", flush=True)
    import uvicorn
    uvicorn.run("server:app", host=host, port=port)


if __name__ == "__main__":
    main()
