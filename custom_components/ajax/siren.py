"""Ajax Siren platform — stub implementation.

turn_on and turn_off are not yet implemented: no Ajax REST API endpoint
for siren activation has been identified. This platform is registered but
entities will not be controllable until the API endpoint is available.

Note: homesiren/streetsiren devices are currently routed to binary_sensor
by device_mapper, so this platform is not loaded in practice.
"""

from homeassistant.components.siren import SirenEntity
from .const import DOMAIN
from .device_mapper import map_ajax_device
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    devices_by_hub = hass.data[DOMAIN][entry.entry_id]["devices_by_hub"]
    entities = []

    for hub_id, devices in devices_by_hub.items():
        for device in devices:
            for platform, meta in map_ajax_device(device):
                if platform != "siren":
                    continue
                entity = AjaxSiren(device, meta, hub_id)
                entities.append(entity)

    async_add_entities(entities)


class AjaxSiren(SirenEntity):
    def __init__(self, device, meta, hub_id):
        self._device = device
        self.hub_id = hub_id
        self._attr_name = device.get("deviceName") + f" ({device.get('id')})"
        self._attr_unique_id = f"ajax_{device.get('id')}_siren"
        self._attr_device_class = meta.get("device_class")
        self._is_on = False

    @property
    def is_on(self):
        return self._is_on

    async def async_turn_on(self, **kwargs):
        # TODO: implement when Ajax API endpoint for siren activation is identified
        pass

    async def async_turn_off(self, **kwargs):
        # TODO: implement when Ajax API endpoint for siren activation is identified
        pass

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"ajax_{self._device.get('id')}")},
            "name": self._attr_name,
            "manufacturer": "Ajax",
            "model": "Siren",
        }
