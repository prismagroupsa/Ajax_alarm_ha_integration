import logging
from aiohttp import ClientSession, ClientTimeout
from .const import DOMAIN
from .device_mapper import map_ajax_device
from .api import AjaxAPI
from .coordinator import AjaxHubCoordinator, AjaxDeviceCoordinator
_LOGGER = logging.getLogger(__name__)

async def do_setup(hass, entry):
    _LOGGER.debug("Ajax integration setup starting")
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
    _LOGGER.info("Received %d hubs", len(hubs))

    # Get devices per hub
    devices_by_hub = {}
    all_devices = []

    for hub in hubs:
        hub_id = hub["hubId"]
        _LOGGER.debug("Fetching devices for hub: %s", hub_id)
        devices = await api.get_hub_devices(hub_id)
        # get_hub_devices() returns None on HTTP 204 (hub with no associated devices).
        # Guard against None to prevent TypeError on extend() and coordinator loop.
        devices = devices if devices is not None else []
        devices_by_hub[hub_id] = devices
        all_devices.extend(devices)

    # Store devices in memory
    hass.data[DOMAIN][entry.entry_id]["devices_by_hub"] = devices_by_hub

    # ── Create coordinators ───────────────────────────────────────────────────
    # One coordinator per hub + one per device: all entities read from the shared
    # cache instead of making independent API calls each cycle.
    # Result: N entities per device = 1 API call per cycle (not N calls).

    hub_coordinators: dict[str, AjaxHubCoordinator] = {}
    for hub in hubs:
        hub_id = hub["hubId"]
        coord = AjaxHubCoordinator(hass, api, hub_id)
        # async_config_entry_first_refresh() raises ConfigEntryNotReady on failure
        # so HA retries setup with automatic backoff instead of starting silently
        # with all entities in unavailable state.
        await coord.async_config_entry_first_refresh()
        hub_coordinators[hub_id] = coord
    hass.data[DOMAIN][entry.entry_id]["hub_coordinators"] = hub_coordinators

    device_coordinators: dict[str, AjaxDeviceCoordinator] = {}
    for hub_id, devices in devices_by_hub.items():
        for device in devices:
            device_id = device.get("id")
            if device_id:
                coord = AjaxDeviceCoordinator(hass, api, hub_id, device_id)
                await coord.async_config_entry_first_refresh()
                device_coordinators[device_id] = coord
    hass.data[DOMAIN][entry.entry_id]["device_coordinators"] = device_coordinators
    # ─────────────────────────────────────────────────────────────────────────

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
            "platforms": list(platforms)
        }
    )
    # Forward setup to all required platforms
    await hass.config_entries.async_forward_entry_setups(entry, list(platforms))
    hass.data[DOMAIN][entry.entry_id]["loaded_platforms"] = list(platforms)

    return True
