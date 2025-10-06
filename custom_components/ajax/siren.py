from homeassistant.components.siren import SirenEntity
from .const import DOMAIN
from .device_mapper import map_ajax_device

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
        self._attr_unique_id = f"ajax_{device.get('id')}_{meta.get('device_class')}"
        self._attr_device_class = meta.get("device_class")

        # Начальное состояние сирены (считаем, что False — выключена)
        self._is_on = False

    @property
    def is_on(self):
        # Возвращаем состояние сирены, например из device или локального поля
        return self._is_on

    # async def async_turn_on(self, **kwargs):
    #     # Вызов API для включения сирены
    #     await self._activate_siren()
    #     self._is_on = True
    #     self.async_write_ha_state()

    # async def async_turn_off(self, **kwargs):
    #     # Вызов API для выключения сирены
    #     await self._deactivate_siren()
    #     self._is_on = False
    #     self.async_write_ha_state()

    # async def _activate_siren(self):
    #     # Заглушка для вызова API, замени на реальный метод
    #     # например: await self.hass.data[DOMAIN]["api"].activate_siren(self._device["id"])
    #     pass

    # async def _deactivate_siren(self):
    #     # Заглушка для вызова API, замени на реальный метод
    #     pass