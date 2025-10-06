from homeassistant.components.switch import SwitchEntity
from .const import DOMAIN
from .device_mapper import map_ajax_device


async def async_setup_entry(hass, entry, async_add_entities):
    devices_by_hub = hass.data[DOMAIN][entry.entry_id]["devices_by_hub"]
    entities = []

    for hub_id, devices in devices_by_hub.items():
        for device in devices:
            for platform, meta in map_ajax_device(device):
                if platform != "switch":
                    continue
                entity = AjaxSwitch(device, meta, hub_id)
                entities.append(entity)

    async_add_entities(entities)



class AjaxSwitch(SwitchEntity):
    def __init__(self, device, hub_id):
        self._device = device
        self.hub_id = hub_id
        self._attr_name = device.get("deviceName") + f" ({device.get('id')})"
        self._attr_unique_id = f"ajax_{device.get('id')}"

    @property
    def is_on(self):
        return self._device.get("state") == "on"

    async def async_turn_on(self, **kwargs):
        # TODO: вызвать API для включения
        pass

    async def async_turn_off(self, **kwargs):
        # TODO: вызвать API для выключения
        pass