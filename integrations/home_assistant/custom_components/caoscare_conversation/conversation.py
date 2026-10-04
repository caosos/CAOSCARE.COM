"""Assist conversation agent that delegates every turn to CAOSCare (spike, untested in HA)."""
from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession

FALLBACK = "I'm sorry, I can't reach CAOSCare right now. Please use your call button if you need help."


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
        payload = {"endpoint_id": cfg["endpoint_id"], "text": user_input.text,
                   "conversation_id": user_input.conversation_id, "language": user_input.language}
        speech, conv_id, keep_open = FALLBACK, user_input.conversation_id, False
        try:
            session = async_get_clientsession(self.hass)
            async with session.post(cfg["bridge_url"], json=payload, timeout=60,
                                    headers={"Authorization": f"Bearer {cfg['bridge_token']}"}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    speech = data.get("response_text") or FALLBACK
                    conv_id = data.get("conversation_id") or conv_id
                    keep_open = bool(data.get("continue_conversation"))
        except Exception:  # network/timeout: speak the fallback, never invent an answer
            pass
        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(speech)
        return conversation.ConversationResult(response=response, conversation_id=conv_id,
                                               continue_conversation=keep_open)
