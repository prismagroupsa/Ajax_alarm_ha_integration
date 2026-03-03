from homeassistant.components.alarm_control_panel.const import AlarmControlPanelEntityFeature
from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity, AlarmControlPanelState
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import logging
import asyncio

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    data             = hass.data[DOMAIN][config_entry.entry_id]
    hub_coordinators = data["hub_coordinators"]
    hubs             = data.get("hubs", [])
    entities = [
        AjaxAlarmPanel(hub_coordinators[hub["hubId"]], hub["hubId"])
        for hub in hubs
        if hub["hubId"] in hub_coordinators
    ]
    # update_before_add=False: the coordinator has already performed the initial fetch
    # in integration_startup.py → coordinator.async_config_entry_first_refresh()
    async_add_entities(entities)


class AjaxAlarmPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """Ajax alarm panel — uses AjaxHubCoordinator for polling."""

    # _attr_has_entity_name=True: HA builds the full name as "<device_name>"
    # for the primary entity (name=None), following HA guidelines.
    _attr_has_entity_name = True
    _attr_name            = None  # primary entity: uses the device name

    # _attr_available=True: preserves the last known state during temporary API
    # errors, avoiding false triggers of automations on "unavailable".
    _attr_available = True

    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY |
        AlarmControlPanelEntityFeature.ARM_NIGHT
    )
    _attr_code_arm_required    = False
    _attr_code_disarm_required = False

    def __init__(self, coordinator, hub_id: str):
        super().__init__(coordinator)
        self.hub_id          = hub_id
        self._attr_unique_id = f"ajax_hub_{hub_id}_alarm"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _data(self) -> dict:
        """Return the coordinator data dict, or {} if not available."""
        return self.coordinator.data or {}

    def map_ajax_state_to_ha(self, state: str | None):
        if state in {"DISARMED_NIGHT_MODE_OFF", "DISARMED_NIGHT_MODE_ON", "DISARMED"}:
            return AlarmControlPanelState.DISARMED
        if state in {"ARMED_NIGHT_MODE_OFF", "ARMED"}:
            return AlarmControlPanelState.ARMED_AWAY
        if state in {"ARMED_NIGHT_MODE_ON", "NIGHT_MODE"}:
            return AlarmControlPanelState.ARMED_NIGHT
        return None

    # ── HA properties ─────────────────────────────────────────────────────────

    @property
    def alarm_state(self):
        return self.map_ajax_state_to_ha(self._data().get("state"))

    @property
    def code_format(self):
        return None

    @property
    def device_info(self) -> DeviceInfo:
        d = self._data()
        # firmware field is a dict: {version, newVersionAvailable, ...} — extract the string.
        fw = d.get("firmware")
        fw_version = fw.get("version") if isinstance(fw, dict) else fw
        return DeviceInfo(
            identifiers={(DOMAIN, f"ajax_hub_{self.hub_id}")},
            name=d.get("name", f"Ajax Hub {self.hub_id}"),
            manufacturer="Ajax Systems",
            model=d.get("hubSubtype", "Hub"),
            sw_version=fw_version,
        )

    # ── Arm/disarm commands ───────────────────────────────────────────────────

    def _log_arm_prevention_warnings(self, command: str) -> None:
        """Log a warning if the hub has active malfunctions or arm prevention conditions.

        Bypassing malfunctions is native Ajax hub behaviour: the hub may arm anyway
        by bypassing them. This warning makes it visible in the HA log when that occurs.
        """
        d = self._data()
        malfunctions = d.get("hubMalfunctions")
        arm_prev = d.get("armPreventionConditions")
        if malfunctions:
            _LOGGER.warning(
                "Hub %s — %s sent with active malfunctions: %s "
                "(hub may arm with bypass, as per Ajax configuration)",
                self.hub_id, command, malfunctions,
            )
        if arm_prev:
            _LOGGER.warning(
                "Hub %s — %s sent with active arm_prevention_conditions: %s",
                self.hub_id, command, arm_prev,
            )

    async def async_alarm_disarm(self, code=None):
        _LOGGER.info("Disarm called for hub %s", self.hub_id)
        await self.coordinator.api.disarm_hub(self.hub_id)
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

    async def async_alarm_arm_away(self, code=None):
        _LOGGER.info("Arm away called for hub %s", self.hub_id)
        self._log_arm_prevention_warnings("ARM")
        await self.coordinator.api.arm_hub(self.hub_id)
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

    async def async_alarm_arm_night(self, code=None):
        _LOGGER.info("Arm night called for hub %s", self.hub_id)
        self._log_arm_prevention_warnings("NIGHT_MODE_ON")
        await self.coordinator.api.arm_hub_night(self.hub_id)
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

    # ── Extra attributes ──────────────────────────────────────────────────────

    @property
    def extra_state_attributes(self) -> dict:
        """Hub attributes verified via discovery API (POST /api/hub_info).

        All fields are real keys returned by the Ajax API.
        """
        d = self._data()
        return {
            # ── Identification ────────────────────────────────────────────────
            "hub_id":                               d.get("id"),
            "hub_subtype":                          d.get("hubSubtype"),
            "color":                                d.get("color"),
            "hub_address":                          d.get("hubAddress"),
            "modem_imei":                           d.get("modemImei"),
            "image_urls":                           d.get("imageUrls"),
            # ── Firmware ──────────────────────────────────────────────────────
            "firmware":                             d.get("firmware"),
            "fw_update_state":                      d.get("fwUpdateState"),
            "hardware_versions":                    d.get("hardwareVersions"),
            "debug_log_state":                      d.get("debugLogState"),
            # ── Power and battery ─────────────────────────────────────────────
            "battery":                              d.get("battery"),
            "externally_powered":                   d.get("externallyPowered"),
            "charging_mode":                        d.get("chargingMode"),
            "battery_charging_flags":               d.get("batteryChargingFlags"),
            "battery_saving_mode":                  d.get("batterySavingMode"),
            "safe_battery_charging":                d.get("safeBatteryCharging"),
            "external_power_loss_delay_timer":      d.get("externalPowerLossDelayTimer"),
            "device_power_modes":                   d.get("devicePowerModes"),
            # ── Alarm and security ────────────────────────────────────────────
            "alarm_condition":                      d.get("alarmCondition"),
            "alarm_confirmation":                   d.get("alarmConfirmation"),
            "alarm_verification":                   d.get("alarmVerification"),
            "alarm_when_ring_break":                d.get("alarmWhenRingBreak"),
            "fire_alarm":                           d.get("fireAlarm"),
            "jamming_as_alarm":                     d.get("jammingAsAlarm"),
            "interconnection_loss_as_alarm":        d.get("interconnectionLossAsAlarm"),
            "bukhoor_mode":                         d.get("bukhoorMode"),
            "panic_siren_on_any_tamper":            d.get("panicSirenOnAnyTamper"),
            "panic_siren_on_panic_button":          d.get("panicSirenOnPanicButton"),
            "restore_required_after_alarm":         d.get("restoreRequiredAfterAlarmCondition"),
            "siren_alarm_sound_restart":            d.get("sirenAlarmSoundRestart"),
            "post_alarm_indication_rules":          d.get("postAlarmIndicationRules"),
            # ── Tamper ────────────────────────────────────────────────────────
            "tampered":                             d.get("tampered"),
            "tamper_set":                           d.get("tamperSet"),
            "default_tamper_mode":                  d.get("defaultTamperMode"),
            # ── Arming ────────────────────────────────────────────────────────
            "two_stage_arming":                     d.get("twoStageArming"),
            "groups_enabled":                       d.get("groupsEnabled"),
            "arm_prevention_conditions":            d.get("armPreventionConditions"),
            "arm_prevention_mode":                  d.get("armPreventionMode"),
            "arm_preventions_system":               d.get("armPreventionsSystem"),
            "alarm_as_malfunction_arming":          d.get("alarmAsMalfunctionWhenArming"),
            "repeat_entry_delay":                   d.get("repeatEntryDelay"),
            "grade_mode":                           d.get("gradeMode"),
            "sia_cp_settings":                      d.get("siaCpSettings"),
            "current_standard":                     d.get("currentStandard"),
            "password_length":                      d.get("passwordLength"),
            # ── Faults and warnings ───────────────────────────────────────────
            "hub_malfunctions":                     d.get("hubMalfunctions"),
            "warnings":                             d.get("warnings"),
            "malfunctions_ignore_settings":         d.get("malfunctionsIgnoreSettings"),
            # ── Connectivity ──────────────────────────────────────────────────
            "active_channels":                      d.get("activeChannels"),
            "noise_level":                          d.get("noiseLevel"),
            "ethernet":                             d.get("ethernet"),
            "gsm":                                  d.get("gsm"),
            "jeweller":                             d.get("jeweller"),
            "frequency_hopping":                    d.get("frequencyHopping"),
            "external_antenna_monitoring":          d.get("externalAntennaMonitoring"),
            "connection_lost_as_malfunction":       d.get("connectionLostAsMalfunction"),
            "connection_test_in_progress":          d.get("connectionTestInProgress"),
            "connectivity_notification_settings":   d.get("connectivityNotificationSettings"),
            "arc_alarm_settings":                   d.get("arcAlarmSettings"),
            "vds_locking_status":                   d.get("vdsLockingStatus"),
            "interconnect_without_hub":             d.get("interconnectWithoutHub"),
            # ── LED and display ───────────────────────────────────────────────
            "led_brightness_level":                 d.get("ledBrightnessLevel"),
            "led_indication_mode":                  d.get("ledIndicationMode"),
            # ── Limits and configuration ──────────────────────────────────────
            "limits":                               d.get("limits"),
            "capabilities":                         d.get("capabilities"),
            "ping_period_seconds":                  d.get("pingPeriodSeconds"),
            "offline_alarm_seconds":                d.get("offlineAlarmSeconds"),
            "event_limit":                          d.get("eventLimit"),
            "event_delay_enable":                   d.get("eventDelayEnable"),
            "call_settings":                        d.get("callSettings"),
            "cms":                                  d.get("cms"),
            "photo_on_demand_details":              d.get("photoOnDemandDetails"),
            "geo_fence":                            d.get("geoFence"),
            # ── Other ─────────────────────────────────────────────────────────
            "blocked_by_provider":                  d.get("blockedByServiceProvider"),
            "time_zone":                            d.get("timeZone"),
        }
