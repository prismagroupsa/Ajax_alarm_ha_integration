from homeassistant.components.binary_sensor import BinarySensorEntity
from .const import DOMAIN
from .device_mapper import map_ajax_device
from .api import AjaxAPI
import logging


async def async_setup_entry(hass, entry, async_add_entities):
    devices_by_hub = hass.data[DOMAIN][entry.entry_id]["devices_by_hub"]
    entities = []
    data = hass.data[DOMAIN][entry.entry_id]
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    for hub_id, devices in devices_by_hub.items():
        for device in devices:
            for platform, meta in map_ajax_device(device):
                if platform != "binary_sensor":
                    continue
                if meta.get("device_class") == "smoke":
                    entity = FireProtectBinarySensor(device, meta, hub_id, api)
                elif meta.get("device_class") == "opening":
                    entity = DoorProtectBinarySensor(device, meta, hub_id, api)
                elif meta.get("device_class") == "motion":
                    entity = MotionProtectBinarySensor(device, meta, hub_id, api)
                else:
                    entity = AjaxBinarySensor(device, meta, hub_id, api)
                entities.append(entity)

    async_add_entities(entities)



class AjaxBinarySensor(BinarySensorEntity):
    def __init__(self, device, meta, hub_id, api):
        self.api = api
        self._meta = meta
        self.hub_id = hub_id
        self._device = device
        self._attr_name = device.get("deviceName") + f" ({device.get('id')})"
        self._attr_unique_id = f"ajax_{device.get('id')}_{meta.get('device_class')}"
        self._attr_device_class = meta.get("device_class")
        self._alarm_detected = None
        # self._battery = None
        

    @property
    def is_on(self):
        return self._alarm_detected

    async def async_update(self):
        device_info = await self.api.get_device_info(self.hub_id, self._device.get('id'))
        # self._battery = device_info.get('batteryChargeLevelPercentage')
    
    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"ajax_{self._device.get('id')}_{self._meta.get('device_class')}")},
            "name": self._attr_name,
            "manufacturer": "Ajax",
            "model": self._meta.get("device_class", "Unknown"),
        }

    # @property
    # def extra_state_attributes(self):
    #     return {
    #         "battery_level": self._battery,
    #     }
      


class FireProtectBinarySensor(AjaxBinarySensor):
    def __init__(self, device, meta, hub_id, api):
        super().__init__(device, meta, hub_id, api)
        self._smoke_alarm = None
        self._temperature_alarm = None
        self._co_alarm = None
        self._htemp_diff_alarm = None


    @property
    def is_on(self):
        return self._alarm_detected

    async def async_update(self):
        await super().async_update()
        device_info = await self.api.get_device_info(self.hub_id, self._device.get('id'))
        self._co_alarm = device_info.get('coAlarmDetected')
        self._smoke_alarm = device_info.get('smokeAlarmDetected')
        self._temperature_alarm  = device_info.get('temperatureAlarmDetected')
        self._htemp_diff_alarm  = device_info.get('highTemperatureDiffDetected')
        self._alarm_detected = any([
            self._co_alarm,
            self._smoke_alarm,
            self._temperature_alarm,
            self._htemp_diff_alarm
        ])
        


    @property
    def extra_state_attributes(self):
        # attrs = super().extra_state_attributes.copy()
        # attrs.update({
        #     "smoke_alarm": self._smoke_alarm,
        #     "temperature_alarm": self._temperature_alarm,
        #     "temperature_rise_alarm": self._htemp_diff_alarm,
        #     "high_co": self._co_alarm
        # })
        # return attrs
        return {
            "smoke_alarm": self._smoke_alarm,
            "temperature_alarm": self._temperature_alarm,
            "temperature_rise_alarm": self._htemp_diff_alarm,
            "high_co": self._co_alarm
        }



    
    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"ajax_{self._device.get('id')}")},
            "name": "Ajax FireProtectPlus",
            "manufacturer": "Ajax",
            "model": "FireProtectPlus",
        }

class DoorProtectBinarySensor(AjaxBinarySensor):
    def __init__(self, device, meta, hub_id, api):
        super().__init__(device, meta, hub_id, api)
        self._reed_closed = None
        self._extra_contact_alarm = None
        


    @property
    def is_on(self):
        return self._alarm_detected

    async def async_update(self):
        await super().async_update()
        device_info = await self.api.get_device_info(self.hub_id, self._device.get('id'))
        self._reed_closed = device_info.get('reedClosed')
        self._extra_contact_alarm = device_info.get('extraContactClosed')
        self._alarm_detected = (self._reed_closed is False or self._extra_contact_alarm is True)


    @property
    def extra_state_attributes(self):
        # attrs = super().extra_state_attributes.copy()
        # attrs.update({
        #     "reed_closed": self._reed_closed,
        #     "extra_contact_alarm": self._extra_contact_alarm,
        # })
        # return attrs
        return {
            "reed_closed": self._reed_closed,
            "extra_contact_alarm": self._extra_contact_alarm,
        }


    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"ajax_{self._device.get('id')}")},
            "name": "Ajax DoorProtect",
            "manufacturer": "Ajax",
            "model": "DoorProtect",
        }

class MotionProtectBinarySensor(AjaxBinarySensor):
    def __init__(self, device, meta, hub_id, api):
        super().__init__(device, meta, hub_id, api)
        self._sensor_state = None
        


    @property
    def is_on(self):
        return False

    async def async_update(self):
        await super().async_update()
        device_info = await self.api.get_device_info(self.hub_id, self._device.get("id"))
        self._sensor_state = device_info.get("state")
    


    @property
    def extra_state_attributes(self):
        return {
            "raw_state": self._sensor_state
    }
    


    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"ajax_{self._device.get('id')}")},
            "name": "Ajax MotionProtect",
            "manufacturer": "Ajax",
            "model": "MotionProtect",
        }