from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import hashlib
import voluptuous as vol
import aiohttp
import logging
import time
from typing import Any

from .const import (
    DOMAIN,
    DEFAULT_API_URL,
    CONF_POLL_INTERVAL_DISARMED,
    CONF_POLL_INTERVAL_ARMED,
    DEFAULT_POLL_INTERVAL_DISARMED,
    DEFAULT_POLL_INTERVAL_ARMED,
)

_LOGGER = logging.getLogger(__name__)

class AjaxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return AjaxOptionsFlow(config_entry)

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
                # ClientTimeout(total=10) prevents indefinite block if the server
                # is unreachable, which would freeze the config flow UI.
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as session:
                    async with session.post(
                        f"{DEFAULT_API_URL}/api/login",
                        # Password is hashed with SHA256 before transmission.
                        # The Ajax API expects SHA256(password) in the passwordHash field.
                        json={
                            "login": user_input["login"],
                            "passwordHash": hashlib.sha256(
                                user_input["password"].encode()
                            ).hexdigest()
                        }
                    ) as resp:
                        data = await resp.json()

                if resp.status != 200 or "sessionToken" not in data:
                    return self.async_show_form(
                        step_id="user",
                        data_schema=self._get_schema(),
                        errors={"base": "auth_failed"}
                    )

                new_data = {
                    # Store the login email for display in the reauth dialog
                    # instead of the internal user_id UUID.
                    "login": user_input["login"],
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
                    domain_data = self.hass.data.get(DOMAIN, {}).get(self.reauth_entry.entry_id, {})
                    api = domain_data.get("api")
                    if api and hasattr(api, '_reauth_in_progress'):
                        api._reauth_in_progress = False

                    unloaded = await self.hass.config_entries.async_unload(self.reauth_entry.entry_id)
                    if not unloaded:
                        _LOGGER.error("Failed to unload entry during reauth")
                        return self.async_abort(reason="reauth_failed")

                    setup_ok = await self.hass.config_entries.async_setup(self.reauth_entry.entry_id)
                    if not setup_ok:
                        _LOGGER.error("Failed to setup entry during reauth")
                        return self.async_abort(reason="reauth_failed")

                    return self.async_abort(reason="reauth_successful")

                # Otherwise create new entry
                # unique_id prevents duplicate entries for the same Ajax account.
                await self.async_set_unique_id(new_data["user_id"])
                self._abort_if_unique_id_configured()
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
        _LOGGER.debug("Reauth flow initiated")
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
            # Display the stored login email; fall back to user_id for existing
            # installations that predate the login field.
            account_display = (
                self.reauth_entry.data.get("login") or
                self.reauth_entry.data.get("user_id", "Ajax Account")
            )
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=self._get_reauth_schema(),
                description_placeholders={
                    "account": account_display
                },
            )

        # Process reauth with new credentials
        return await self.async_step_user(user_input)

    @callback
    def _get_schema(self):
        return vol.Schema({
            vol.Required("login"): str,
            vol.Required("password"): str,
        })

    @callback
    def _get_reauth_schema(self):
        """Get schema for reauth flow."""
        return vol.Schema({
            vol.Required("login"): str,
            vol.Required("password"): str,
        })


class AjaxOptionsFlow(config_entries.OptionsFlow):
    """Options flow for post-setup configuration.

    Allows adjusting polling intervals without removing and re-adding
    the integration.
    """

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Main step of the options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options
        schema = vol.Schema({
            vol.Optional(
                CONF_POLL_INTERVAL_DISARMED,
                default=current.get(CONF_POLL_INTERVAL_DISARMED, DEFAULT_POLL_INTERVAL_DISARMED),
            ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
            vol.Optional(
                CONF_POLL_INTERVAL_ARMED,
                default=current.get(CONF_POLL_INTERVAL_ARMED, DEFAULT_POLL_INTERVAL_ARMED),
            ): vol.All(vol.Coerce(int), vol.Range(min=30, max=600)),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
