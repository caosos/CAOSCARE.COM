"""Aria's voice for Home Assistant's text-to-speech step: CAOSCare speaks the
reply in the resident session voice (same voice as Aria in the room)."""
import logging

from homeassistant.components.tts import TextToSpeechEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .bridge_client import call_speech, speech_url

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    async_add_entities([AriaVoice(hass, entry)])


class AriaVoice(TextToSpeechEntity):
    _attr_has_entity_name = True
    _attr_name = "Aria voice"
    _attr_default_language = "en"
    _attr_supported_languages = ["en"]

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_tts"

    async def async_get_tts_audio(self, message, language, options):
        cfg = self.entry.data
        audio, error = await call_speech(async_get_clientsession(self.hass), speech_url(cfg["bridge_url"]),
                                         cfg["bridge_token"], message)
        if audio is None:
            _LOGGER.warning("CAOSCare speech failed: %s", error)
            return None, None
        return "mp3", audio
