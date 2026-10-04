"""Assist conversation agent that delegates every turn to CAOSCare.

Not yet run inside Home Assistant. Written against the ConversationEntity
API (async_process / ConversationResult with continue_conversation, HA
2025.4+); verify against the installed HA version before use.
"""
from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .bridge_client import build_payload, call_bridge


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    async_add_entities([CaosCareAgent(hass, entry)])


class CaosCareAgent(conversation.ConversationEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_languages = "*"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = entry.entry_id

    async def async_process(self, user_input: conversation.ConversationInput) -> conversation.ConversationResult:
        cfg = self.entry.data
        payload = build_payload(user_input.text, user_input.conversation_id, user_input.language,
                                device_id=getattr(user_input, "device_id", None),
                                satellite_id=getattr(user_input, "satellite_id", None))
        out = await call_bridge(async_get_clientsession(self.hass), cfg["bridge_url"],
                                cfg["bridge_token"], payload)
        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(out["speech"])
        # continue_conversation=False returns the Voice PE to wake-word mode.
        return conversation.ConversationResult(response=response,
                                               conversation_id=out["conversation_id"],
                                               continue_conversation=out["continue_conversation"])
