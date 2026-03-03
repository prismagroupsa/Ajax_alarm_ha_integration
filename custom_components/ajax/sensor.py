from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN
from .device_mapper import map_ajax_device
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    data               = hass.data[DOMAIN][entry.entry_id]
    hub_coordinators   = data["hub_coordinators"]
    device_coordinators = data["device_coordinators"]
    devices_by_hub     = data["devices_by_hub"]
    hubs               = data.get("hubs", [])
    entities = []

    # --- Hub diagnostic companions ---
    for hub in hubs:
        hub_id = hub.get("hubId")
        coord  = hub_coordinators.get(hub_id)
        if hub_id and coord:
            entities.append(AjaxHubFirmwareSensor(coord, hub_id))
            entities.append(AjaxHubBatterySensor(coord, hub_id))
            entities.append(AjaxHubAlarmAsMalfunctionSensor(coord, hub_id))
            entities.append(AjaxHubArmPreventionConditionsSensor(coord, hub_id))

    # --- Device companion sensors + device-specific sensors ---
    for hub_id, devices in devices_by_hub.items():
        for device in devices:
            device_id = device.get("id")
            coord     = device_coordinators.get(device_id)
            if not coord:
                continue

            # Diagnostic companions (present on all devices)
            entities.append(AjaxBatterySensor(coord, device, hub_id))
            entities.append(AjaxSignalStrengthSensor(coord, device, hub_id))
            entities.append(AjaxFirmwareSensor(coord, device, hub_id))

            # Platform-specific sensors
            for platform, meta in map_ajax_device(device):
                if platform != "sensor":
                    continue
                sensor_type = meta.get("sensor_type", "")
                if meta.get("device_class") == "temperature" and sensor_type == "":
                    entity = FireProtectSensor(coord, device, meta, hub_id)
                elif sensor_type == "door_temperature":
                    entity = DoorProtectSensor(coord, device, meta, hub_id)
                elif sensor_type == "motion_temperature":
                    entity = MotionProtectSensor(coord, device, meta, hub_id)
                else:
                    entity = AjaxSensor(coord, device, meta, hub_id)
                entities.append(entity)

    async_add_entities(entities)


# ─────────────────────────────────────────────────────────────────────────────
# BASE CLASS — Generic device sensor
# ─────────────────────────────────────────────────────────────────────────────

class AjaxSensor(CoordinatorEntity, SensorEntity):
    """Generic Ajax sensor.

    _attr_has_entity_name=True: visible name is "<device_name> · <entity_name>".
    _attr_available=True: preserves the last value on transient API errors.
    device_info uses the typed DeviceInfo struct.
    """

    _attr_has_entity_name = True
    _attr_available       = True

    def __init__(self, coordinator, device, meta, hub_id):
        super().__init__(coordinator)
        self._device = device
        self.hub_id  = hub_id
        self._meta   = meta
        sensor_type  = meta.get("sensor_type", meta.get("device_class", "sensor"))
        device_id    = device.get("id")

        dc = meta.get("device_class", "sensor")
        self._attr_name                       = dc.replace("_", " ").title()
        self._attr_unique_id                  = f"ajax_{device_id}_{sensor_type}"
        self._attr_device_class               = meta.get("device_class")
        self._attr_native_unit_of_measurement = meta.get("unit")

    def _data(self) -> dict:
        return self.coordinator.data or {}

    @property
    def native_value(self):
        return None  # overridden by subclasses

    @property
    def extra_state_attributes(self):
        return {"battery_level": self._data().get("batteryChargeLevelPercentage")}

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"ajax_{self._device.get('id')}")},
            name=self._device.get("deviceName", "Ajax"),
            manufacturer="Ajax Systems",
            model=self._meta.get("device_class", "Unknown"),
        )


# ─────────────────────────────────────────────────────────────────────────────
# BATTERY — Diagnostic for all devices
# ─────────────────────────────────────────────────────────────────────────────

class AjaxBatterySensor(CoordinatorEntity, SensorEntity):
    """Battery level for all Ajax devices (diagnostic entity)."""

    _attr_has_entity_name               = True
    _attr_available                     = True
    _attr_device_class                  = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement    = "%"
    _attr_state_class                   = SensorStateClass.MEASUREMENT
    _attr_entity_category               = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, device, hub_id):
        super().__init__(coordinator)
        self._device  = device
        self.hub_id   = hub_id
        device_id     = device.get("id")
        self._attr_name      = "Battery"
        self._attr_unique_id = f"ajax_{device_id}_battery"

    @property
    def native_value(self):
        d = self.coordinator.data
        return d.get("batteryChargeLevelPercentage") if d else None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"ajax_{self._device.get('id')}")},
            name=self._device.get("deviceName", "Ajax"),
            manufacturer="Ajax Systems",
            model=self._device.get("deviceType", "Ajax"),
        )


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL STRENGTH — Diagnostic for all devices
# Maps raw API string (e.g. "STRONG", "GOOD") to one of four labels: NO_SIGNAL / WEAK / NORMAL / STRONG.
# ─────────────────────────────────────────────────────────────────────────────

# Maps raw Ajax API signalLevel strings to four human-readable labels.
# Consolidates the 8 API values into 4 meaningful tiers shown in HA.
_SIGNAL_LEVEL_MAP: dict[str, str] = {
    "STRONG":   "STRONG",
    "GOOD":     "NORMAL",
    "MEDIUM":   "NORMAL",
    "FAIR":     "NORMAL",
    "LOW":      "WEAK",
    "WEAK":     "WEAK",
    "VERY_LOW": "NO_SIGNAL",
    "NONE":     "NO_SIGNAL",
}
_SIGNAL_LEVEL_OPTIONS = ["NO_SIGNAL", "WEAK", "NORMAL", "STRONG"]


class AjaxSignalStrengthSensor(CoordinatorEntity, SensorEntity):
    """Radio signal level for all Ajax devices (diagnostic entity).

    Returns one of four string labels: NO_SIGNAL / WEAK / NORMAL / STRONG.
    Uses SensorDeviceClass.ENUM so HA treats the value as a named state.
    """

    _attr_has_entity_name = True
    _attr_available       = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class    = SensorDeviceClass.ENUM
    _attr_options         = _SIGNAL_LEVEL_OPTIONS
    _attr_icon            = "mdi:wifi"

    def __init__(self, coordinator, device, hub_id):
        super().__init__(coordinator)
        self._device  = device
        self.hub_id   = hub_id
        device_id     = device.get("id")
        self._attr_name      = "Signal Level"
        self._attr_unique_id = f"ajax_{device_id}_signal_level"

    @property
    def native_value(self) -> str | None:
        d = self.coordinator.data
        if not d:
            return None
        raw = d.get("signalLevel")
        if isinstance(raw, str):
            return _SIGNAL_LEVEL_MAP.get(raw.upper())
        return None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"ajax_{self._device.get('id')}")},
            name=self._device.get("deviceName", "Ajax"),
            manufacturer="Ajax Systems",
            model=self._device.get("deviceType", "Ajax"),
        )


# ─────────────────────────────────────────────────────────────────────────────
# FIRMWARE — Diagnostic for all devices
# ─────────────────────────────────────────────────────────────────────────────

class AjaxFirmwareSensor(CoordinatorEntity, SensorEntity):
    """Firmware version for all Ajax devices (diagnostic entity)."""

    _attr_has_entity_name = True
    _attr_available       = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon            = "mdi:chip"

    def __init__(self, coordinator, device, hub_id):
        super().__init__(coordinator)
        self._device  = device
        self.hub_id   = hub_id
        device_id     = device.get("id")
        self._attr_name      = "Firmware"
        self._attr_unique_id = f"ajax_{device_id}_firmware"

    @property
    def native_value(self):
        d = self.coordinator.data
        return d.get("firmwareVersion") if d else None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"ajax_{self._device.get('id')}")},
            name=self._device.get("deviceName", "Ajax"),
            manufacturer="Ajax Systems",
            model=self._device.get("deviceType", "Ajax"),
        )


# ─────────────────────────────────────────────────────────────────────────────
# HUB COMPANION SENSORS
# ─────────────────────────────────────────────────────────────────────────────

class AjaxHubFirmwareSensor(CoordinatorEntity, SensorEntity):
    """Firmware version of the Ajax hub (diagnostic entity)."""

    _attr_has_entity_name = True
    _attr_available       = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon            = "mdi:chip"

    def __init__(self, coordinator, hub_id: str):
        super().__init__(coordinator)
        self.hub_id          = hub_id
        self._attr_name      = "Firmware"
        self._attr_unique_id = f"ajax_hub_{hub_id}_firmware"

    @property
    def native_value(self):
        d = self.coordinator.data
        if not d:
            return None
        fw = d.get("firmware")
        # firmware is returned as dict {version, newVersionAvailable, ...} by the API.
        if isinstance(fw, dict):
            return fw.get("version")
        return fw

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"ajax_hub_{self.hub_id}")},
            name=f"Ajax Hub {self.hub_id}",
            manufacturer="Ajax Systems",
            model="Hub",
        )


class AjaxHubBatterySensor(CoordinatorEntity, SensorEntity):
    """Battery level and state for the Ajax hub (diagnostic entity).

    The hub exposes battery as a dict: {chargeLevelPercentage, state}.
    native_value = chargeLevelPercentage (integer %).
    extra_state_attributes = {battery_state, externally_powered}.
    """

    _attr_has_entity_name               = True
    _attr_available                     = True
    _attr_device_class                  = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement    = "%"
    _attr_state_class                   = SensorStateClass.MEASUREMENT
    _attr_entity_category               = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, hub_id: str):
        super().__init__(coordinator)
        self.hub_id          = hub_id
        self._attr_name      = "Battery"
        self._attr_unique_id = f"ajax_hub_{hub_id}_battery"

    @property
    def native_value(self):
        d = self.coordinator.data
        if not d:
            return None
        battery = d.get("battery")
        if isinstance(battery, dict):
            return battery.get("chargeLevelPercentage")
        return None

    @property
    def extra_state_attributes(self) -> dict:
        d = self.coordinator.data or {}
        battery = d.get("battery") or {}
        return {
            "battery_state":      battery.get("state") if isinstance(battery, dict) else None,
            "externally_powered": d.get("externallyPowered"),
            "charging_mode":      d.get("chargingMode"),
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"ajax_hub_{self.hub_id}")},
            name=f"Ajax Hub {self.hub_id}",
            manufacturer="Ajax Systems",
            model="Hub",
        )


class AjaxHubAlarmAsMalfunctionSensor(CoordinatorEntity, SensorEntity):
    """alarmAsMalfunctionWhenArming flag for the Ajax hub (diagnostic entity)."""

    _attr_has_entity_name = True
    _attr_available       = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon            = "mdi:shield-alert-outline"

    def __init__(self, coordinator, hub_id: str):
        super().__init__(coordinator)
        self.hub_id          = hub_id
        self._attr_name      = "Alarm As Malfunction Arming"
        self._attr_unique_id = f"ajax_hub_{hub_id}_alarm_as_malfunction_arming"

    @property
    def native_value(self):
        d = self.coordinator.data
        return d.get("alarmAsMalfunctionWhenArming") if d else None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"ajax_hub_{self.hub_id}")},
            name=f"Ajax Hub {self.hub_id}",
            manufacturer="Ajax Systems",
            model="Hub",
        )


class AjaxHubArmPreventionConditionsSensor(CoordinatorEntity, SensorEntity):
    """armPreventionConditions for the Ajax hub (diagnostic entity)."""

    _attr_has_entity_name = True
    _attr_available       = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon            = "mdi:shield-lock-outline"

    def __init__(self, coordinator, hub_id: str):
        super().__init__(coordinator)
        self.hub_id          = hub_id
        self._attr_name      = "Arm Prevention Conditions"
        self._attr_unique_id = f"ajax_hub_{hub_id}_arm_prevention_conditions"

    @property
    def native_value(self):
        d = self.coordinator.data
        if not d:
            return None
        v = d.get("armPreventionConditions")
        if isinstance(v, list):
            return len(v)
        return v

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data
        return {"conditions": d.get("armPreventionConditions") if d else None}

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"ajax_hub_{self.hub_id}")},
            name=f"Ajax Hub {self.hub_id}",
            manufacturer="Ajax Systems",
            model="Hub",
        )


# ─────────────────────────────────────────────────────────────────────────────
# DEVICE-SPECIFIC SENSORS (temperature)
# ─────────────────────────────────────────────────────────────────────────────

class FireProtectSensor(AjaxSensor):
    def __init__(self, coordinator, device, meta, hub_id):
        super().__init__(coordinator, device, meta, hub_id)
        self._attr_name = "Temperature"

    @property
    def native_value(self):
        d = self.coordinator.data
        return d.get("temperature") if d else None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"ajax_{self._device.get('id')}")},
            name=self._device.get("deviceName", "Ajax FireProtectPlus"),
            manufacturer="Ajax Systems",
            model="FireProtectPlus",
        )


class DoorProtectSensor(AjaxSensor):
    def __init__(self, coordinator, device, meta, hub_id):
        super().__init__(coordinator, device, meta, hub_id)
        self._attr_name = "Temperature"

    @property
    def native_value(self):
        d = self.coordinator.data
        return d.get("temperature") if d else None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"ajax_{self._device.get('id')}")},
            name=self._device.get("deviceName", "Ajax DoorProtect"),
            manufacturer="Ajax Systems",
            model="DoorProtect",
        )


class MotionProtectSensor(AjaxSensor):
    def __init__(self, coordinator, device, meta, hub_id):
        super().__init__(coordinator, device, meta, hub_id)
        self._attr_name = "Temperature"

    @property
    def native_value(self):
        d = self.coordinator.data
        return d.get("temperature") if d else None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"ajax_{self._device.get('id')}")},
            name=self._device.get("deviceName", "Ajax MotionProtect"),
            manufacturer="Ajax Systems",
            model="MotionProtect",
        )
