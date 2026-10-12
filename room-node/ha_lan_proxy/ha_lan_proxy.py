"""Expose the Home Assistant VM (libvirt NAT, 192.168.122.x) on the EliteDesk's LAN address so
Wi-Fi room devices - the Voice PE first - and phones on the home network can reach it (the Voice
PE fetches spoken replies from HA by URL). Plain TCP relay, no TLS termination, no inspection.
Runs as a user service (ha-lan-proxy.service); stopping the service removes the exposure.
Owner decision, Michael 2026-10-12. Env: HA_PROXY_LISTEN (default 0.0.0.0:8123),
HA_PROXY_TARGET (default 192.168.122.137:8123)."""
import asyncio
import os


def _addr(v):
    host, port = v.rsplit(":", 1)
    return host, int(port)


LISTEN = _addr(os.environ.get("HA_PROXY_LISTEN", "0.0.0.0:8123"))
TARGET = _addr(os.environ.get("HA_PROXY_TARGET", "192.168.122.137:8123"))


async def _pipe(reader, writer):
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def _handle(client_r, client_w):
    try:
        up_r, up_w = await asyncio.wait_for(asyncio.open_connection(*TARGET), 5)
    except Exception:
        client_w.close()
        return
    await asyncio.gather(_pipe(client_r, up_w), _pipe(up_r, client_w))


async def main():
    server = await asyncio.start_server(_handle, *LISTEN)
    print(f"ha_lan_proxy {LISTEN[0]}:{LISTEN[1]} -> {TARGET[0]}:{TARGET[1]}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
