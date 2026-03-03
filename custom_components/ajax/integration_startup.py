import asyncio
import logging
from aiohttp import ClientSession, ClientTimeout
from homeassistant.exceptions import ConfigEntryNotReady
from .const import DOMAIN
from .device_mapper import map_ajax_device
from .api import AjaxAPI, AjaxAPIError
from .coordinator import AjaxHubCoordinator, AjaxDeviceCoordinator

_LOGGER = logging.getLogger(__name__)

# Retry parameters for transient API errors (rate limit, network) during setup.
# Max 50 retries × 500 ms = up to 25s of waiting before giving up.
_MAX_SETUP_RETRIES = 50
_SETUP_RETRY_WAIT  = 0.5  # seconds


async def _retry_api_call(fn, *args, label: str = "call", **kwargs):
    """Call ``fn(*args, **kwargs)`` retrying up to _MAX_SETUP_RETRIES on AjaxAPIError.

    Used during integration setup to handle transient rate-limit responses
    (HTTP 429 / "exceeded the limit") without failing the entire setup.
    ConfigEntryAuthFailed and other non-AjaxAPIError exceptions propagate immediately.
    """
    for attempt in range(_MAX_SETUP_RETRIES + 1):
        try:
            return await fn(*args, **kwargs)
        except AjaxAPIError as exc:
            if attempt < _MAX_SETUP_RETRIES:
                _LOGGER.warning(
                    "%s: transient error (attempt %d/%d): %s — retrying in %.1fs",
                    label, attempt + 1, _MAX_SETUP_RETRIES, exc, _SETUP_RETRY_WAIT,
                )
                await asyncio.sleep(_SETUP_RETRY_WAIT)
            else:
                _LOGGER.error(
                    "%s: max retries (%d) exceeded: %s",
                    label, _MAX_SETUP_RETRIES, exc,
                )
                raise


async def _first_refresh_with_retry(coord, label: str) -> None:
    """Call async_config_entry_first_refresh() with retry on ConfigEntryNotReady.

    ConfigEntryNotReady is raised when the coordinator's first data fetch fails
    with UpdateFailed (e.g. rate limit during setup).  We retry up to
    _MAX_SETUP_RETRIES times with _SETUP_RETRY_WAIT between attempts.
    ConfigEntryAuthFailed is never caught here — it propagates to HA immediately.
    """
    for attempt in range(_MAX_SETUP_RETRIES + 1):
        try:
            await coord.async_config_entry_first_refresh()
            return
        except ConfigEntryNotReady as exc:
            if attempt < _MAX_SETUP_RETRIES:
                _LOGGER.warning(
                    "%s: first refresh failed (attempt %d/%d): %s — retrying in %.1fs",
                    label, attempt + 1, _MAX_SETUP_RETRIES, exc, _SETUP_RETRY_WAIT,
                )
                await asyncio.sleep(_SETUP_RETRY_WAIT)
            else:
                _LOGGER.error(
                    "%s: first refresh failed after %d retries — giving up",
                    label, _MAX_SETUP_RETRIES,
                )
                raise


async def do_setup(hass, entry):
    _LOGGER.debug("Ajax integration setup starting")
    session = ClientSession(timeout=ClientTimeout(total=10))
    api = AjaxAPI(entry.data, hass, entry, session)
    hass.data[DOMAIN][entry.entry_id]["api"] = api
    hass.data[DOMAIN][entry.entry_id]["session"] = session

    # Only refresh token if session token is expired or close to expiring
    if api.is_token_expired():
        await api.update_refresh_token()

    # Get list of hubs — retry on transient rate-limit / network errors.
    hubs = await _retry_api_call(api.get_hubs, label="get_hubs")
    if not hubs or not isinstance(hubs, list):
        _LOGGER.error("No hubs returned from API or invalid format. Got: %s", type(hubs))
        return False
    hass.data[DOMAIN][entry.entry_id]["hubs"] = hubs
    _LOGGER.info("Received %d hubs", len(hubs))

    # Get devices per hub — retry on transient rate-limit / network errors.
    devices_by_hub = {}
    all_devices = []

    for hub in hubs:
        hub_id = hub["hubId"]
        _LOGGER.debug("Fetching devices for hub: %s", hub_id)
        devices = await _retry_api_call(
            api.get_hub_devices, hub_id, label=f"get_hub_devices({hub_id})"
        )
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
        # _first_refresh_with_retry wraps async_config_entry_first_refresh():
        #   - retries up to 50× on ConfigEntryNotReady (rate limit / network)
        #   - ConfigEntryAuthFailed propagates immediately (auth problem)
        await _first_refresh_with_retry(coord, label=f"hub_coordinator({hub_id})")
        hub_coordinators[hub_id] = coord
    hass.data[DOMAIN][entry.entry_id]["hub_coordinators"] = hub_coordinators

    device_coordinators: dict[str, AjaxDeviceCoordinator] = {}
    for hub_id, devices in devices_by_hub.items():
        for device in devices:
            device_id = device.get("id")
            if device_id:
                coord = AjaxDeviceCoordinator(hass, api, hub_id, device_id)
                await _first_refresh_with_retry(
                    coord, label=f"device_coordinator({device_id})"
                )
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
