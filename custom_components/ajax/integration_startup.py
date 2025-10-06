import logging
from aiohttp import ClientSession, ClientTimeout
from .const import DOMAIN
from .device_mapper import map_ajax_device
from .api import AjaxAPI
_LOGGER = logging.getLogger(__name__)

async def do_setup(hass, entry):
    _LOGGER.error(f"INIT HASS: {hass!r} ({bool(hass)}) ENTRY: {entry!r} ({bool(entry)})")
    session = ClientSession(timeout=ClientTimeout(total=10))
    api = AjaxAPI(entry.data, hass, entry, session)
    hass.data[DOMAIN][entry.entry_id]["api"] = api
    hass.data[DOMAIN][entry.entry_id]["session"] = session


    # Only refresh token if session token is expired or close to expiring
    if api.is_token_expired():
        await api.update_refresh_token()
       
   
    # Get list of hubs
    hubs = await api.get_hubs()
    if not hubs or not isinstance(hubs, list):
        _LOGGER.error("No hubs returned from API or invalid format. Got: %s", type(hubs))
        return False
    hass.data[DOMAIN][entry.entry_id]["hubs"] = hubs
    _LOGGER.error("Received %d hubs", len(hubs))

    # Get devices per hub
    devices_by_hub = {}
    all_devices = []

    for hub in hubs:
        hub_id = hub["hubId"]
        _LOGGER.warning("Fetching devices for hub: %s", hub_id)
        devices = await api.get_hub_devices(hub_id)
        devices_by_hub[hub_id] = devices
        all_devices.extend(devices)

    # Store devices in memory
    hass.data[DOMAIN][entry.entry_id]["devices_by_hub"] = devices_by_hub



    # Determine required platforms based on device types
    platforms = set()
    for device in all_devices:
        mappings = map_ajax_device(device)
        for platform, _ in mappings:
            platforms.add(platform)

    # Ensure alarm panel is always registered
    platforms.add("alarm_control_panel")
    

    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            "platforms": list(platforms)  # save platforms to memory
        }
    )
    # Forward setup to all required platforms
    await hass.config_entries.async_forward_entry_setups(entry, list(platforms))
    hass.data[DOMAIN][entry.entry_id]["loaded_platforms"] = list(platforms)
    
    return True

        