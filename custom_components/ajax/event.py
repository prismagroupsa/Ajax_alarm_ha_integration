from homeassistant.components.event import EventEntity
from .const import DOMAIN
from .device_mapper import map_ajax_device

async def async_setup_entry(hass, entry, async_add_entities):
    devices_by_hub = hass.data[DOMAIN][entry.entry_id]["devices_by_hub"]
    entities = []

    for hub_id, devices in devices_by_hub.items():
        for device in devices:
            for platform, meta in map_ajax_device(device):
                if platform != "event":
                    continue
                entity = AjaxEvent(device, meta, hub_id)
                entities.append(entity)

    async_add_entities(entities)


class AjaxEvent(EventEntity):
    # HA 2024.1+ requires _attr_event_types as a class-level or __init__-level
    # attribute set before async_added_to_hass. Set as instance attribute in __init__.

    def __init__(self, device, meta, hub_id):
        self._device = device
        self._meta = meta
        self.hub_id = hub_id
        self._attr_name = device.get("deviceName") + f" ({device.get('id')})"
        self._attr_unique_id = f"ajax_{device.get('id')}_{meta.get('event_type', 'event')}"
        self._attr_event_types = [meta.get("event_type", "ajax_event")]

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"ajax_{self._device.get('id')}")},
            "name": self._attr_name,
            "manufacturer": "Ajax",
            "model": self._meta.get("event_type", "Event"),
        }
