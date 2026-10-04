"""CAOSCare conversation agent for Home Assistant Assist (not yet run in Home Assistant).

Forwards each Assist transcript to CAOSCare's voice bridge and speaks the
reply. CAOSCare owns the conversation, residents, requests and receipts;
this integration stores only the bridge URL and credential. Each Voice PE
is identified to CAOSCare by its Home Assistant device id.
"""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS = [Platform.CONVERSATION]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
