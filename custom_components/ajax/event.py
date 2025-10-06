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
    def __init__(self, device, meta, hub_id):
        self._device = device
        self._meta = meta 
        self.hub_id = hub_id
        self._attr_name = device.get("deviceName") + f" ({device.get('id')})"
        self._attr_unique_id = f"ajax_{device.get('id')}_{meta.get('device_class')}"
        self._attr_device_class = meta.get("device_class")

    @property
    def native_value(self):
        # Возвращаем последнее событие из устройства,
        # например, поле 'last_event' или 'event_description' — подставь своё
        return self._device.get("last_event", "No events")
    @property
    def event_types(self):
        return [self._meta.get("event_type", "ajax_event")]