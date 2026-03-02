from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN
from .device_mapper import map_ajax_device
import logging

_LOGGER = logging.getLogger(__name__)

# Device API states that indicate an active alarm.
_ALARM_STATES = frozenset({"ALARM", "TRIGGERED", "FIRE_ALARM", "PANIC"})


async def async_setup_entry(hass, entry, async_add_entities):
    data                = hass.data[DOMAIN][entry.entry_id]
    hub_coordinators    = data["hub_coordinators"]
    device_coordinators = data["device_coordinators"]
    devices_by_hub      = data["devices_by_hub"]
    hubs                = data.get("hubs", [])
    entities = []

    # --- Hub diagnostic companions ---
    for hub in hubs:
        hub_id = hub.get("hubId")
        coord  = hub_coordinators.get(hub_id)
        if hub_id and coord:
            entities.append(AjaxHubTamperBinarySensor(coord, hub_id))
            entities.append(AjaxHubProblemBinarySensor(coord, hub_id))

    # --- Device companion sensors + device-specific sensors ---
    for hub_id, devices in devices_by_hub.items():
        for device in devices:
            device_id = device.get("id")
            coord     = device_coordinators.get(device_id)
            if not coord:
                continue

            # Diagnostic companions (present on all devices)
            entities.append(AjaxTamperedBinarySensor(coord, device, hub_id))
            entities.append(AjaxConnectivityBinarySensor(coord, device, hub_id))
            entities.append(AjaxProblemBinarySensor(coord, device, hub_id))

            # Platform-specific sensors
            for platform, meta in map_ajax_device(device):
                if platform != "binary_sensor":
                    continue
                dc = meta.get("device_class")
                if dc == "smoke":
                    entity = FireProtectBinarySensor(coord, device, meta, hub_id)
                elif dc == "opening":
                    entity = DoorProtectBinarySensor(coord, device, meta, hub_id)
                elif dc == "motion":
                    entity = MotionProtectBinarySensor(coord, device, meta, hub_id)
                elif dc == "moisture":
                    entity = LeaksProtectBinarySensor(coord, device, meta, hub_id)
                else:
                    entity = AjaxBinarySensor(coord, device, meta, hub_id)
                entities.append(entity)

    async_add_entities(entities)


# ─────────────────────────────────────────────────────────────────────────────
# BASE CLASS
# ─────────────────────────────────────────────────────────────────────────────

class AjaxBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Generic Ajax binary sensor.

    _attr_has_entity_name=True: the visible name is composed by HA as
    "<device_name> · <entity_name>" (e.g. "Door Sensor · Opening").
    The ID is no longer included in the name — it remains only in unique_id.

    _attr_available=True: preserves the last known state during temporary API
    errors, avoiding false triggers of automations on "unavailable".
    """

    _attr_has_entity_name = True
    _attr_available       = True

    def __init__(self, coordinator, device, meta, hub_id):
        super().__init__(coordinator)
        self._meta        = meta
        self.hub_id       = hub_id
        self._device      = device
        self._device_type = device.get("deviceType", "unknown")
        device_id         = device.get("id")
        dc                = meta.get("device_class", "sensor")

        self._attr_name        = dc.replace("_", " ").title() if dc else "Sensor"
        self._attr_unique_id   = f"ajax_{device_id}_{dc}"
        self._attr_device_class = meta.get("device_class")

    def _data(self) -> dict:
        return self.coordinator.data or {}

    @property
    def is_on(self):
        return None  # overridden by subclasses

    @property
    def extra_state_attributes(self) -> dict:
        d = self._data()
        return {
            "battery":      d.get("batteryChargeLevelPercentage"),
            "online":       d.get("online"),
            "signal_level": d.get("signalLevel"),
            "tampered":     d.get("tampered"),
            "temperature":  d.get("temperature"),
            "firmware":     d.get("firmwareVersion"),
            "state_raw":    d.get("state"),
            "bypass_state": d.get("bypassState"),
            "issues_count": d.get("issuesCount"),
            "arming_state": d.get("estimatedArmingState"),
            "malfunctions": d.get("malfunctions"),
            "arming_mode":  d.get("armingMode"),
        }

    @property
    def device_info(self) -> DeviceInfo:
        d  = self._data()
        info = DeviceInfo(
            identifiers={(DOMAIN, f"ajax_{self._device.get('id')}")},
            name=self._device.get("deviceName", f"Ajax {self._device_type}"),
            manufacturer="Ajax Systems",
            model=self._device_type,
        )
        fw = d.get("firmwareVersion")
        if fw:
            info["sw_version"] = fw
        return info


# ─────────────────────────────────────────────────────────────────────────────
# DEVICE DIAGNOSTIC COMPANIONS
# ─────────────────────────────────────────────────────────────────────────────

class AjaxTamperedBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Tamper sensor for all Ajax devices (diagnostic entity)."""

    _attr_has_entity_name = True
    _attr_available       = True
    _attr_device_class    = BinarySensorDeviceClass.TAMPER
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, device, hub_id):
        super().__init__(coordinator)
        self._device         = device
        self.hub_id          = hub_id
        device_id            = device.get("id")
        self._attr_name      = "Tamper"
        self._attr_unique_id = f"ajax_{device_id}_tamper"

    @property
    def is_on(self):
        d = self.coordinator.data
        return d.get("tampered") is True if d else None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"ajax_{self._device.get('id')}")},
            name=self._device.get("deviceName", "Ajax"),
            manufacturer="Ajax Systems",
            model=self._device.get("deviceType", "Ajax"),
        )


class AjaxConnectivityBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Online/offline connectivity sensor for all Ajax devices (diagnostic entity)."""

    _attr_has_entity_name = True
    _attr_available       = True
    _attr_device_class    = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, device, hub_id):
        super().__init__(coordinator)
        self._device         = device
        self.hub_id          = hub_id
        device_id            = device.get("id")
        self._attr_name      = "Online"
        self._attr_unique_id = f"ajax_{device_id}_connectivity"

    @property
    def is_on(self):
        d = self.coordinator.data
        return d.get("online") is True if d else None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"ajax_{self._device.get('id')}")},
            name=self._device.get("deviceName", "Ajax"),
            manufacturer="Ajax Systems",
            model=self._device.get("deviceType", "Ajax"),
        )


class AjaxProblemBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Fault sensor for all Ajax devices (diagnostic entity).

    ON when issuesCount > 0.
    """

    _attr_has_entity_name = True
    _attr_available       = True
    _attr_device_class    = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, device, hub_id):
        super().__init__(coordinator)
        self._device         = device
        self.hub_id          = hub_id
        device_id            = device.get("id")
        self._attr_name      = "Problem"
        self._attr_unique_id = f"ajax_{device_id}_problem"

    @property
    def is_on(self):
        d = self.coordinator.data
        if not d:
            return None
        count = d.get("issuesCount")
        return isinstance(count, (int, float)) and count > 0

    @property
    def extra_state_attributes(self) -> dict:
        d = self.coordinator.data or {}
        return {
            "issues_count": d.get("issuesCount"),
            "malfunctions": d.get("malfunctions"),
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"ajax_{self._device.get('id')}")},
            name=self._device.get("deviceName", "Ajax"),
            manufacturer="Ajax Systems",
            model=self._device.get("deviceType", "Ajax"),
        )


# ─────────────────────────────────────────────────────────────────────────────
# DOOR PROTECT / DOOR PROTECT PLUS
# ─────────────────────────────────────────────────────────────────────────────

class DoorProtectBinarySensor(AjaxBinarySensor):

    def __init__(self, coordinator, device, meta, hub_id):
        super().__init__(coordinator, device, meta, hub_id)
        self._attr_name = "Opening"

    @property
    def icon(self) -> str:
        """Dynamic icon: door open / door closed."""
        return "mdi:door-open" if self.is_on else "mdi:door-closed"

    @property
    def is_on(self):
        d = self._data()
        reed_alarm  = d.get("reedClosed") is False
        extra_alarm = d.get("extraContactClosed") is True
        return reed_alarm or extra_alarm

    @property
    def extra_state_attributes(self) -> dict:
        attrs = super().extra_state_attributes
        d = self._data()
        attrs.update({
            "reed_closed":              d.get("reedClosed"),
            "extra_contact_closed":     d.get("extraContactClosed"),
            "reed_contact_configured":  d.get("reedContactAware"),
            "extra_contact_configured": d.get("extraContactAware"),
            "two_stage_arming_role":    d.get("twoStageArmingRole"),
        })
        # Fields present only on DoorProtectPlus — included only if not None
        for src, dst in [
            ("extraContactType",        "extra_contact_type"),
            ("shockSensorAware",        "shock_sensor_configured"),
            ("shockSensorSensitivity",  "shock_sensor_sensitivity"),
            ("accelerometerAware",      "tilt_sensor_configured"),
            ("accelerometerTiltDegrees","tilt_degrees"),
        ]:
            v = d.get(src)
            if v is not None:
                attrs[dst] = v
        return attrs


# ─────────────────────────────────────────────────────────────────────────────
# MOTION PROTECT / MOTION PROTECT PLUS / MOTION PROTECT CURTAIN
# ─────────────────────────────────────────────────────────────────────────────

class MotionProtectBinarySensor(AjaxBinarySensor):

    def __init__(self, coordinator, device, meta, hub_id):
        super().__init__(coordinator, device, meta, hub_id)
        self._attr_name = "Motion"

    @property
    def is_on(self):
        d = self._data()
        return d.get("state", "") in _ALARM_STATES

    @property
    def extra_state_attributes(self) -> dict:
        attrs = super().extra_state_attributes
        d = self._data()
        for src, dst in [
            ("sensitivity",  "sensitivity"),
            ("petImmunity",  "pet_immunity"),
            ("masked",       "masked"),
            ("antimasking",  "antimasking"),
        ]:
            v = d.get(src)
            if v is not None:
                attrs[dst] = v
        return attrs


# ─────────────────────────────────────────────────────────────────────────────
# LEAKS PROTECT
# ─────────────────────────────────────────────────────────────────────────────

class LeaksProtectBinarySensor(AjaxBinarySensor):

    def __init__(self, coordinator, device, meta, hub_id):
        super().__init__(coordinator, device, meta, hub_id)
        self._attr_name = "Leak"

    @property
    def is_on(self):
        d = self._data()
        return d.get("leakDetected") is True

    @property
    def extra_state_attributes(self) -> dict:
        attrs = super().extra_state_attributes
        attrs["leak_detected"] = self._data().get("leakDetected")
        return attrs


# ─────────────────────────────────────────────────────────────────────────────
# FIRE PROTECT / FIRE PROTECT PLUS
# ─────────────────────────────────────────────────────────────────────────────

class FireProtectBinarySensor(AjaxBinarySensor):

    def __init__(self, coordinator, device, meta, hub_id):
        super().__init__(coordinator, device, meta, hub_id)
        self._attr_name = "Smoke"

    @property
    def is_on(self):
        d = self._data()
        return any([
            d.get("coAlarmDetected"),
            d.get("smokeAlarmDetected"),
            d.get("temperatureAlarmDetected"),
            d.get("highTemperatureDiffDetected"),
        ])

    @property
    def extra_state_attributes(self) -> dict:
        attrs = super().extra_state_attributes
        d = self._data()
        attrs.update({
            "smoke_alarm":            d.get("smokeAlarmDetected"),
            "temperature_alarm":      d.get("temperatureAlarmDetected"),
            "temperature_rise_alarm": d.get("highTemperatureDiffDetected"),
            "co_alarm":               d.get("coAlarmDetected"),
        })
        return attrs


# ─────────────────────────────────────────────────────────────────────────────
# HUB DIAGNOSTIC COMPANIONS
# ─────────────────────────────────────────────────────────────────────────────

class AjaxHubTamperBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Tamper sensor for the Ajax hub (diagnostic entity)."""

    _attr_has_entity_name = True
    _attr_available       = True
    _attr_device_class    = BinarySensorDeviceClass.TAMPER
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, hub_id: str):
        super().__init__(coordinator)
        self.hub_id          = hub_id
        self._attr_name      = "Tamper"
        self._attr_unique_id = f"ajax_hub_{hub_id}_tamper"

    @property
    def is_on(self):
        d = self.coordinator.data
        return d.get("tampered") is True if d else None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"ajax_hub_{self.hub_id}")},
            name=f"Ajax Hub {self.hub_id}",
            manufacturer="Ajax Systems",
            model="Hub",
        )


class AjaxHubProblemBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Fault sensor for the Ajax hub (diagnostic entity).

    ON when hubMalfunctions is a non-empty list.
    """

    _attr_has_entity_name = True
    _attr_available       = True
    _attr_device_class    = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, hub_id: str):
        super().__init__(coordinator)
        self.hub_id          = hub_id
        self._attr_name      = "Problem"
        self._attr_unique_id = f"ajax_hub_{hub_id}_problem"

    @property
    def is_on(self):
        d = self.coordinator.data
        if not d:
            return None
        m = d.get("hubMalfunctions")
        return isinstance(m, list) and len(m) > 0

    @property
    def extra_state_attributes(self) -> dict:
        d = self.coordinator.data or {}
        return {"hub_malfunctions": d.get("hubMalfunctions")}

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"ajax_hub_{self.hub_id}")},
            name=f"Ajax Hub {self.hub_id}",
            manufacturer="Ajax Systems",
            model="Hub",
        )
