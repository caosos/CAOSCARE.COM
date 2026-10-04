"""Test server for voice-bridge load runs: the real CAOSCare app with the
language model replaced by loadtest.mock_provider. Started by loadtest/run.py
as `uvicorn loadtest.mock_app:app` with all external provider keys blank, so
no paid or external call is possible."""
import os

import routes.voice_bridge as vb
from loadtest import mock_provider
from routes.voice_bridge_admission import ADMISSION
from server import app

assert not os.environ.get("OPENAI_API_KEY"), "load server must run without a real OpenAI key"
assert os.environ.get("DB_NAME", "").startswith("caos_vb_load_"), "load server must use a throwaway database"

vb._post_openai = mock_provider.simulated_post


@app.middleware("http")
async def _dump_counters(request, call_next):
    response = await call_next(request)
    if request.url.path.endswith("/voice-bridge/turn"):
        mock_provider.dump_stats({"pid": os.getpid(), "admission": ADMISSION.snapshot()})
    return response
