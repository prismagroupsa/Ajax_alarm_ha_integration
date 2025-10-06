from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol
import aiohttp
import logging
import time
from typing import Any

from .const import DOMAIN, DEFAULT_API_URL

_LOGGER = logging.getLogger(__name__)

class AjaxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.reauth_entry = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        # Get current platforms from reauth_entry.data if exists
        platforms = []
        if self.reauth_entry and "platforms" in self.reauth_entry.data:
            platforms = self.reauth_entry.data["platforms"]
        if user_input is not None:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{DEFAULT_API_URL}/api/login",
                        json={
                            "login": user_input["login"],
                            "passwordHash": user_input["password"]
                        }
                        # headers={"X-Api-Key": user_input["api_key"]},
                    ) as resp:
                        data = await resp.json()

                if resp.status != 200 or "sessionToken" not in data:
                    return self.async_show_form(
                        step_id="user",
                        data_schema=self._get_schema(),
                        errors={"base": "auth_failed"}
                    )

                new_data = {
                    # "api_key": user_input["api_key"],
                    "session_token": data["sessionToken"],
                    "user_id": data["userId"],
                    "refresh_token": data["refreshToken"],
                    "token_created_at": time.time(),
                    "platforms": platforms
                }

                # If this is a reauth flow, update existing entry
                if self.reauth_entry:
                    self.hass.config_entries.async_update_entry(
                        self.reauth_entry, data=new_data
                    )
                    # Reset reauth flag in API instance if it exists
                    domain_data = self.hass.data.get("ajax", {}).get(self.reauth_entry.entry_id, {})
                    api = domain_data.get("api")
                    if api and hasattr(api, '_reauth_in_progress'):
                        api._reauth_in_progress = False

                    # Trigger reload to re-run async_setup_entry
                    # await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
                    self.hass.config_entries.async_update_entry(self.reauth_entry, data=new_data)

                    unloaded = await self.hass.config_entries.async_unload(self.reauth_entry.entry_id)
                    if not unloaded:
                        _LOGGER.error("Failed to unload entry during reauth")
                        return self.async_abort(reason="reauth_failed")

                    setup_ok = await self.hass.config_entries.async_setup(self.reauth_entry.entry_id)
                    if not setup_ok:
                        _LOGGER.error("Failed to setup entry during reauth")
                        return self.async_abort(reason="reauth_failed")

                    return self.async_abort(reason="reauth_successful")

                    # Don't force reload, let Home Assistant handle it naturally
                    return self.async_abort(reason="reauth_successful")

                # Otherwise create new entry
                return self.async_create_entry(
                    title="Ajax Alarm",
                    data=new_data,
                )

            except Exception as e:
                _LOGGER.exception("Login error: %s", e)
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._get_schema(),
                    errors={"base": "connection_error"}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self._get_schema()
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        _LOGGER.error("reauth CALLED")
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if not self.reauth_entry:
            _LOGGER.error("Config entry not found for reauth")
            return self.async_abort(reason="entry_not_found")
        
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=self._get_reauth_schema(),
                description_placeholders={
                    "account": self.reauth_entry.data.get("user_id", "Ajax Account")
                },
            )

        # Process reauth with new credentials
        return await self.async_step_user(user_input)

    @callback
    def _get_schema(self):
        return vol.Schema({
            vol.Required("login"): str,
            vol.Required("password"): str,
            # vol.Required("api_key"): str,
        })

    @callback
    def _get_reauth_schema(self):
        """Get schema for reauth flow."""
        # Pre-fill api_key if available
        # api_key = ""
        # if self.reauth_entry:
        #     api_key = self.reauth_entry.data.get("api_key", "")
        
        return vol.Schema({
            vol.Required("login"): str,
            vol.Required("password"): str,
            # vol.Required("api_key", default=api_key): str,
        })
