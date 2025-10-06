from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import logging
import time
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from .const import DOMAIN
from .api import AjaxAPI
from .device_mapper import map_ajax_device
from homeassistant.core import CoreState
from homeassistant.exceptions import ConfigEntryAuthFailed
from .integration_startup import do_setup
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # required_fields = ["session_token", "refresh_token", "user_id", "api_key"]
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
        # "api_key": entry.data["api_key"],
        "hubs": None,
        "devices": None,        
    }


    try:    
       
        setup_result = await do_setup(hass, entry)   
            
        return setup_result


    except Exception as e:
        _LOGGER.error(f"Ajax authorisation error: {e}")
        raise ConfigEntryAuthFailed

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    

    # Remove platforms (sensor, binary_sensor, etc.)
    platforms = entry.data.get("platforms", [])
    _LOGGER.error(f"PLATFORMS:{platforms}")
    loaded_platforms = hass.data[DOMAIN][entry.entry_id].get("loaded_platforms", [])
    _LOGGER.error(f"Loaded platforms to unload: {loaded_platforms}")

    if platforms:
        _LOGGER.error("PLATFORMS TRUE")
        unload_ok = await hass.config_entries.async_unload_platforms(entry, loaded_platforms)
        _LOGGER.error("PLATFORMS FALSE")
        unload_ok = True

    _LOGGER.error(f"UNLOAD:{unload_ok}")
    return bool(unload_ok)