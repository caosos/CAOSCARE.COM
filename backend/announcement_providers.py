"""Room announcement providers - the one place that decides HOW an approved
announcement reaches a room's speaker. routes/room_announcements.py speaks
only this interface, so stock Voice PE firmware, an approved custom
firmware, a future realtime path or an external room speaker can be added
here without changing the canonical announcement object.

Today's provider: Home Assistant's official Assist satellite `announce`
service (assist_satellite.announce over HA's REST API). HA calls the
service with blocking=True and the satellite's async_internal_announce
blocks until the announcement finishes, setting the satellite state to
"responding" and back to "idle"; the REST response lists the states that
changed under the call's context (home-assistant/core 275e8b6:
components/api/__init__.py 425-475, components/assist_satellite/entity.py
198-240). That is the strongest evidence available: it is HA-reported, not
an acoustic confirmation that a person heard it.
"""
from dataclasses import dataclass, field
from typing import Optional, Protocol

import httpx

import device_adapters  # one source for HA_BASE_URL / HA_TOKEN


@dataclass
class ProviderResult:
    accepted: bool                      # provider took the request
    evidence_level: str                 # see models_announcements.EvidenceLevel
    started: bool = False
    finished: bool = False
    failure: Optional[str] = None       # device_unavailable / satellite_busy / provider_error / provider_timeout / not_configured
    timed_out: bool = False
    request: dict = field(default_factory=dict)
    response: dict = field(default_factory=dict)


class AnnouncementProvider(Protocol):
    name: str
    simulated: bool

    async def announce(self, target_device_id: str, message: str, *, preannounce: bool,
                       timeout_s: float) -> ProviderResult: ...


def _target(device_id: str) -> dict:
    """A satellite entity id targets one entity; anything else is an HA device id."""
    if device_id.startswith("assist_satellite."):
        return {"entity_id": device_id}
    return {"device_id": device_id}


def evidence_from_states(device_id: str, states: list) -> tuple:
    """(started, finished) from the states HA says changed under this call."""
    seen = [s.get("state") for s in states if isinstance(s, dict)
            and str(s.get("entity_id", "")).startswith("assist_satellite.")
            and (not device_id.startswith("assist_satellite.") or s.get("entity_id") == device_id)]
    started = "responding" in seen
    finished = started and seen[-1] == "idle"
    return started, finished


class HomeAssistantAssistSatellite:
    name = "ha_assist_satellite"
    simulated = False

    async def announce(self, target_device_id: str, message: str, *, preannounce: bool,
                       timeout_s: float) -> ProviderResult:
        body = {**_target(target_device_id), "message": message, "preannounce": preannounce}
        req = {"service": "assist_satellite.announce", "data": body}
        if not device_adapters.HA_BASE_URL or not device_adapters.HA_TOKEN:
            return ProviderResult(False, "none", failure="not_configured", request=req)
        headers = {"Authorization": f"Bearer {device_adapters.HA_TOKEN}"}
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                if target_device_id.startswith("assist_satellite."):
                    st = await client.get(f"{device_adapters.HA_BASE_URL}/api/states/{target_device_id}",
                                          headers=headers)
                    if st.status_code == 404 or (st.status_code == 200
                                                 and st.json().get("state") == "unavailable"):
                        return ProviderResult(False, "none", failure="device_unavailable", request=req,
                                              response={"status_code": st.status_code})
                resp = await client.post(
                    f"{device_adapters.HA_BASE_URL}/api/services/assist_satellite/announce",
                    headers=headers, json=body)
        except httpx.TimeoutException:
            return ProviderResult(False, "none", failure="provider_timeout", timed_out=True, request=req)
        except httpx.HTTPError as e:
            return ProviderResult(False, "none", failure="provider_error", request=req,
                                  response={"error": type(e).__name__})
        info = {"status_code": resp.status_code}
        if resp.status_code != 200:
            text = resp.text[:200]
            info["body"] = text
            failure = "satellite_busy" if "busy" in text.lower() else "provider_error"
            return ProviderResult(False, "none", failure=failure, request=req, response=info)
        try:
            states = resp.json()
        except ValueError:
            states = []
        states = states if isinstance(states, list) else states.get("changed_states", [])
        info["changed_states"] = [{"entity_id": s.get("entity_id"), "state": s.get("state")}
                                  for s in states if isinstance(s, dict)]
        started, finished = evidence_from_states(target_device_id, states)
        level = ("provider_reported_finished" if finished else
                 "provider_reported_started" if started else "provider_accepted")
        return ProviderResult(True, level, started=started, finished=finished, request=req, response=info)


_PROVIDERS = {"ha_assist_satellite": HomeAssistantAssistSatellite()}


def get_provider(name: str = "ha_assist_satellite") -> AnnouncementProvider:
    return _PROVIDERS[name]
