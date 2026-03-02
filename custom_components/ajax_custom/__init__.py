from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import logging
import time
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from .const import DOMAIN
from .api import AjaxAPI
from .device_mapper import map_ajax_device
from homeassistant.core import CoreState
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from .integration_startup import do_setup
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    required_fields = ["session_token", "refresh_token", "user_id"]
    if not all(entry.data.get(k) for k in required_fields):
        _LOGGER.error("Missing required config entry fields. Setup aborted.")
        return False
    # Initialize domain storage if not already
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "session_token": entry.data["session_token"],
        "refresh_token": entry.data["refresh_token"],
        "token_created_at": entry.data.get("token_created_at", time.time()),
        "user_id": entry.data["user_id"],
        "hubs": None,
        "devices": None,
    }

    try:
        setup_result = await do_setup(hass, entry)
        return setup_result

    except (ConfigEntryAuthFailed, ConfigEntryNotReady):
        # Let HA handle these natively:
        # - ConfigEntryAuthFailed → HA shows "Re-authenticate" notification
        # - ConfigEntryNotReady   → HA retries setup with automatic backoff
        raise
    except Exception as e:
        _LOGGER.error("Ajax setup error: %s", e)
        raise ConfigEntryAuthFailed from e

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:

    unload_ok = True

    # Close aiohttp ClientSession to prevent TCP connection leak on unload.
    session = hass.data[DOMAIN][entry.entry_id].get("session")
    if session and not session.closed:
        await session.close()

    # Unload all platforms registered at runtime.
    loaded_platforms = hass.data[DOMAIN][entry.entry_id].get("loaded_platforms", [])
    _LOGGER.debug("Loaded platforms to unload: %s", loaded_platforms)

    if loaded_platforms:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, loaded_platforms)

    # Clean up domain data.
    hass.data[DOMAIN].pop(entry.entry_id, None)

    _LOGGER.debug("Unload result: %s", unload_ok)
    return bool(unload_ok)
