"""Aria's voice for Home Assistant's text-to-speech step: CAOSCare speaks the
reply in the resident session voice (same voice as Aria in the room).
Streamed: playback starts as the first audio arrives, not after the whole reply."""
import logging

from homeassistant.components.tts import TextToSpeechEntity, TTSAudioRequest, TTSAudioResponse
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .bridge_client import call_speech, open_speech_stream, speech_url

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

    def _target(self):
        cfg = self.entry.data
        return async_get_clientsession(self.hass), speech_url(cfg["bridge_url"]), cfg["bridge_token"]

    async def async_get_tts_audio(self, message, language, options):
        audio, error = await call_speech(*self._target(), message)
        if audio is None:
            _LOGGER.warning("CAOSCare speech failed: %s", error)
            return None, None
        return "mp3", audio

    async def async_stream_tts_audio(self, request: TTSAudioRequest) -> TTSAudioResponse:
        message = "".join([chunk async for chunk in request.message_gen])
        gen, error = await open_speech_stream(*self._target(), message)
        if gen is None:
            _LOGGER.warning("CAOSCare speech failed: %s", error)
            raise HomeAssistantError(f"CAOSCare speech failed: {error}")
        return TTSAudioResponse("mp3", gen)
