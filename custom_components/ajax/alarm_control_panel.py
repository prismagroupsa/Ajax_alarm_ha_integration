from homeassistant.components.alarm_control_panel.const import AlarmControlPanelEntityFeature
from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity, AlarmControlPanelState
from homeassistant.const import STATE_UNKNOWN
from datetime import timedelta
import time
import logging
import asyncio

from .api import AjaxAPI
from .const import DOMAIN


SCAN_INTERVAL = timedelta(seconds=15)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    data = hass.data[DOMAIN][config_entry.entry_id]
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    hubs = data.get("hubs", [])
    entities = [AjaxAlarmPanel(api, hub["hubId"]) for hub in hubs]
    async_add_entities(entities)


class AjaxAlarmPanel(AlarmControlPanelEntity):
    def __init__(self, api, hub_id):
        self.api = api
        self.hub_id = hub_id
        self._attr_name = "Ajax Hub"
        self._raw_state = STATE_UNKNOWN

    def map_ajax_state_to_ha(self, state):
        if state in ["DISARMED_NIGHT_MODE_OFF", "DISARMED_NIGHT_MODE_ON"]:
            return AlarmControlPanelState.DISARMED
        if state == "ARMED_NIGHT_MODE_OFF":
            return AlarmControlPanelState.ARMED_AWAY
        if state == "ARMED_NIGHT_MODE_ON":
            return AlarmControlPanelState.ARMED_NIGHT
        return None

    @property
    def supported_features(self):
        return (
            AlarmControlPanelEntityFeature.ARM_AWAY |
            AlarmControlPanelEntityFeature.ARM_NIGHT
        )

    @property
    def alarm_state(self):
        return self.map_ajax_state_to_ha(self._raw_state)

    async def async_added_to_hass(self):
        await self.async_update()

    async def async_update(self):
        start = time.perf_counter()
        hub_info = await self.api.get_hub_info(self.hub_id)
        _LOGGER.error("API response time: %.2f sec", time.perf_counter() - start)
        if not hub_info:
            _LOGGER.warning("Hub info is not available for update")
            return

        self._raw_state = hub_info["state"]
        self._attr_name = f"{hub_info['name']} ({hub_info['id']})"
        self.async_schedule_update_ha_state()

    async def async_alarm_disarm(self, code=None):
        _LOGGER.info("Disarm called")
        start = time.perf_counter()
        await self.api.disarm_hub(self.hub_id)
        _LOGGER.error("API disarm time: %.2f sec", time.perf_counter() - start)
        await asyncio.sleep(1)
        await self.async_update()
        

    async def async_alarm_arm_away(self, code=None):
        _LOGGER.info("Arm away called")
        start = time.perf_counter()
        await self.api.arm_hub(self.hub_id)
        _LOGGER.error("API arm time: %.2f sec", time.perf_counter() - start)
        await asyncio.sleep(1)
        await self.async_update()
        

    async def async_alarm_arm_night(self, code=None):
        _LOGGER.info("Arm night called")
        await self.api.arm_hub_night(self.hub_id)
        await asyncio.sleep(1)
        await self.async_update()
        

    @property
    def code_format(self):
        return None

    @property
    def code_arm_required(self):
        return False

    @property
    def code_disarm_required(self):
        return False

    @property
    def unique_id(self):
        return f"ajax_{self.hub_id}_alarm"


    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"ajax_hub_{self.hub_id}")},
            "name": "Ajax Hub",
            "manufacturer": "Ajax",
            "model": "Hub",
        }
