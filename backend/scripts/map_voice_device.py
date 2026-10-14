"""Map a Voice PE (Home Assistant device id) to a room endpoint (Kiosk), as the
owner at the terminal. Same function and receipt as PUT /api/voice-bridge/devices.

    .venv/bin/python scripts/map_voice_device.py <ha_device_id> <kiosk_id> "<your name>"
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
from routes.voice_bridge_devices import DeviceMapping, map_device  # noqa: E402

device_id, kiosk_id, name = sys.argv[1], sys.argv[2], sys.argv[3]
user = {"user_id": "owner:terminal", "name": f"{name} (owner, terminal)", "role": "owner"}
print(asyncio.run(map_device(device_id, DeviceMapping(kiosk_id=kiosk_id), user=user)))
