"""One config entry per room endpoint (spike, untested in HA)."""
import voluptuous as vol
from homeassistant import config_entries

DOMAIN = "caoscare_conversation"


class CaosCareConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            await self.async_set_unique_id(user_input["endpoint_id"])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=f"CAOSCare {user_input['endpoint_id']}", data=user_input)
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("bridge_url"): str,      # e.g. http://<caoscare-host>/api/voice-bridge/turn
            vol.Required("bridge_token"): str,    # CAOSCARE_VOICE_BRIDGE_TOKEN on the CAOSCare side
            vol.Required("endpoint_id"): str,     # the room's registered endpoint (Kiosk id)
        }))
