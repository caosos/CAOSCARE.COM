"""Create the demo-only room for the public demo kiosk and make its kiosk
the public demo (routes/demo_kiosk.py::ensure_demo_room). Idempotent.

Other rooms are untouched except that any other kiosk loses the
`public_demo` flag. Run DEMO RESET afterwards (POST /api/demo/reset, or the
kiosk's Demo reset button) to create the simulated devices.

    cd backend && .venv/bin/python scripts/setup_demo_room.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from routes.demo_kiosk import ensure_demo_room  # noqa: E402


if __name__ == "__main__":
    print(asyncio.run(ensure_demo_room()))
