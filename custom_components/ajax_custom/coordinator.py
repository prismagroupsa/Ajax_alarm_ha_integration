from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed
from datetime import timedelta
import logging
from .api import AjaxAPIError

_LOGGER = logging.getLogger(__name__)

# Adaptive polling intervals based on arming state.
# Armed: 60s reduces API load by ~2x compared to the previous 15s default.
# Disarmed: 30s ensures responsiveness without rate-limit risk.
HUB_SCAN_INTERVAL_DISARMED  = timedelta(seconds=30)
HUB_SCAN_INTERVAL_ARMED     = timedelta(seconds=60)
DEVICE_SCAN_INTERVAL        = timedelta(seconds=30)

# Maximum consecutive auth errors before propagating ConfigEntryAuthFailed.
# Tolerates transient 401 errors (e.g. momentarily overloaded server).
_MAX_CONSECUTIVE_AUTH_ERRORS = 3

# Hub API states that indicate the system is armed (used for adaptive polling).
_ARMED_STATES = frozenset({"ARMED", "ARMED_NIGHT_MODE_OFF", "ARMED_NIGHT_MODE_ON", "NIGHT_MODE"})


class AjaxHubCoordinator(DataUpdateCoordinator):
    """Coordinator for a single Ajax hub.

    A single get_hub_info() call per cycle — the result is shared by all
    entities associated with the hub:
      - AjaxAlarmPanel
      - AjaxHubFirmwareSensor
      - AjaxHubAlarmAsMalfunctionSensor
      - AjaxHubArmPreventionConditionsSensor
      - AjaxHubTamperBinarySensor
      - AjaxHubProblemBinarySensor

    Adaptive polling interval: 30s when disarmed / 60s when armed.
    """

    def __init__(self, hass, api, hub_id: str):
        super().__init__(
            hass,
            _LOGGER,
            name=f"Ajax Hub {hub_id}",
            update_interval=HUB_SCAN_INTERVAL_DISARMED,
        )
        self.api    = api
        self.hub_id = hub_id
        # Counter for consecutive auth errors — avoids reauth on transient failures.
        self._consecutive_auth_errors: int = 0

    async def _async_update_data(self) -> dict:
        try:
            data = await self.api.get_hub_info(self.hub_id)
            self._consecutive_auth_errors = 0  # reset on successful fetch
        except ConfigEntryAuthFailed:
            # Tolerate up to _MAX_CONSECUTIVE_AUTH_ERRORS consecutive 401s.
            # A single 401 can be transient: convert to UpdateFailed until the
            # threshold is exceeded, then re-raise to trigger the reauth flow.
            self._consecutive_auth_errors += 1
            if self._consecutive_auth_errors >= _MAX_CONSECUTIVE_AUTH_ERRORS:
                _LOGGER.error(
                    "Hub %s: %d consecutive auth errors — triggering reauth flow",
                    self.hub_id, self._consecutive_auth_errors,
                )
                raise
            _LOGGER.warning(
                "Hub %s: temporary auth error (%d/%d) — retrying next cycle",
                self.hub_id, self._consecutive_auth_errors, _MAX_CONSECUTIVE_AUTH_ERRORS,
            )
            raise UpdateFailed(f"Hub {self.hub_id}: temporary auth error") from None
        except AjaxAPIError as e:
            # AjaxAPIError = temporary error (rate limit, network timeout).
            # UpdateFailed: coordinator retries next cycle without triggering reauth.
            raise UpdateFailed(f"Hub {self.hub_id}: {e}") from e

        if not data:
            raise UpdateFailed(f"Hub {self.hub_id}: no data received from API")

        # Update polling interval based on arming state.
        hub_state = data.get("state", "")
        new_interval = (
            HUB_SCAN_INTERVAL_ARMED
            if hub_state in _ARMED_STATES
            else HUB_SCAN_INTERVAL_DISARMED
        )
        if self.update_interval != new_interval:
            _LOGGER.debug(
                "Hub %s: polling interval → %ds (state: %s)",
                self.hub_id, new_interval.seconds, hub_state,
            )
            self.update_interval = new_interval

        return data


class AjaxDeviceCoordinator(DataUpdateCoordinator):
    """Coordinator for a single Ajax device.

    A single get_device_info() call per cycle — the result is shared by all
    entities of the device:
      - AjaxBatterySensor
      - AjaxSignalStrengthSensor
      - AjaxFirmwareSensor
      - AjaxTamperedBinarySensor
      - AjaxConnectivityBinarySensor
      - AjaxProblemBinarySensor
      - DoorProtectBinarySensor / MotionProtectBinarySensor / etc.
    """

    def __init__(self, hass, api, hub_id: str, device_id: str):
        super().__init__(
            hass,
            _LOGGER,
            name=f"Ajax Device {device_id}",
            update_interval=DEVICE_SCAN_INTERVAL,
        )
        self.api       = api
        self.hub_id    = hub_id
        self.device_id = device_id
        # Counter for consecutive auth errors.
        self._consecutive_auth_errors: int = 0

    async def _async_update_data(self) -> dict:
        try:
            data = await self.api.get_device_info(self.hub_id, self.device_id)
            self._consecutive_auth_errors = 0
        except ConfigEntryAuthFailed:
            # Same logic as hub coordinator.
            self._consecutive_auth_errors += 1
            if self._consecutive_auth_errors >= _MAX_CONSECUTIVE_AUTH_ERRORS:
                _LOGGER.error(
                    "Device %s: %d consecutive auth errors — triggering reauth flow",
                    self.device_id, self._consecutive_auth_errors,
                )
                raise
            _LOGGER.warning(
                "Device %s: temporary auth error (%d/%d) — retrying next cycle",
                self.device_id, self._consecutive_auth_errors, _MAX_CONSECUTIVE_AUTH_ERRORS,
            )
            raise UpdateFailed(f"Device {self.device_id}: temporary auth error") from None
        except AjaxAPIError as e:
            raise UpdateFailed(f"Device {self.device_id}: {e}") from e

        if not data:
            raise UpdateFailed(f"Device {self.device_id}: no data received from API")
        return data
