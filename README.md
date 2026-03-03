# 🛡️ Ajax Alarm System Integration for Home Assistant

Integrate your **Ajax Security System** seamlessly with **Home Assistant** — control, automate, and monitor your alarm system directly from your smart home dashboard.

---

## ⚠️ Secure Your Home Assistant Installation First!

Before installing this integration, **please make sure your Home Assistant instance is properly secured**.
Following best practices will protect both your home network and your Ajax account.

### 🧱 Security Best Practices

- 🔑 Use a **strong and unique username and password**.
- 🔒 Enable **Two-Factor Authentication (2FA)** for your Home Assistant account.
- 🚫 **Do not expose** Home Assistant directly to the internet using the default port.
  Instead, consider one (or combine several) of the following:
  - 🌀 **Reverse Proxy** (e.g., Nginx, Traefik)
  - ☁️ **Web Application Firewall (WAF)** such as [Cloudflare](https://www.cloudflare.com/)
  - 🔐 **Private VPN** access only

### 👤 Dedicated Account for Ajax
- Avoid using your **admin** account for this integration.
- Create a **dedicated Ajax account** with **minimal permissions** (usually only ability to arm night mode is enough).
- Configure **network access restrictions** — only allow connections from trusted networks.

---

## 🧩 Requirements

- Home Assistant **2024.6+**
- HACS installed
- Ajax account with limited permissions
- Internet access for Ajax API connectivity

---

## ✅ Supported Devices

| Device | Binary Sensor | Temperature Sensor | Notes |
|---|---|---|---|
| Hub 2 / Hub 2 Plus (4G) | Alarm panel | — | Full attribute set from API |
| Door Protect | Opening | Temperature | Reed + extra contact |
| Door Protect Plus | Opening | Temperature | + shock sensor, tilt sensor |
| Motion Protect | Motion | Temperature | Sensitivity, pet immunity |
| Motion Protect Plus | Motion | Temperature | + antimasking |
| Motion Protect Curtain | Motion | Temperature | + masked state |
| LeaksProtect | Moisture | — | leakDetected field |
| Fire Protect Plus | Smoke | Temperature | CO, smoke, temp, high-temp-diff alarms |
| HomeSiren / StreetSiren | Alarm active | — | Volume, duration, blink config |
| REX 2 | Extender Sensor | Battery | Signal + extra contact |


This integration is actively maintained, and new device support will be introduced in future updates.

---

## ⚙️ Installation Guide

> 💡 **Recommended method:** via [HACS (Home Assistant Community Store)](https://hacs.xyz/)

### 🧩 Step-by-Step

1. **Add this repository** as a custom repository in HACS.
   - Go to: `HACS → Integrations → Custom Repositories`
   - Add the repository URL (this repo).
2. **Search for** `Ajax Integration Custom Plugin` in HACS.
3. **Install** the integration from HACS.
4. **Restart Home Assistant** to apply changes.
5. Go to `Settings → Devices & Services → Add Integration`.
6. Search for **Ajax** and **authenticate** with your **dedicated Ajax account**.
7. Complete device customization in the UI.
8. 🎉 **Enjoy!**
   Use your Ajax Alarm System directly in Home Assistant and create powerful automations and scripts.

---

## 🧰 Features

- 🔔 Arm, disarm, and set night mode on your Ajax hub.
- 💡 Integrate alarm states into Home Assistant automations.
- 📱 Customize notifications, triggers, and automations using Lovelace dashboards.
- ⚙️ Simple configuration and automatic entity discovery.
- 🔋 Per-device battery, signal strength, firmware, tamper, connectivity and problem entities — all in the Diagnostics section.
- 🔋 **Hub battery sensor** — monitors the hub's internal backup battery level and charge state.
- 📡 Shared polling coordinator — adaptive polling (30s disarmed / 60s armed).
- 🔒 Password transmitted as SHA256 hash — never in plaintext.
- ⚙️ Post-setup options flow — adjust polling intervals without reconfiguring.
- 🩺 Diagnostics support — export anonymized debug data via HA diagnostics UI.
- 🔁 **Auto-retry on rate limit** — arm/disarm/night mode commands automatically retry up to 50 times if the Ajax server is temporarily busy, without requiring user action.

---

## ⚠️ Known Limitations

| Feature | Status | Notes |
|---|---|---|
| **Switch `turn_on` / `turn_off`** | 🔴 Not implemented | Relay / WallSwitch control not yet available |
| **Siren control (`turn_on` / `turn_off`)** | 🔴 Not implemented | Alarm state is monitored; manual trigger not supported |
| **Night mode bypass malfunctions** | ℹ️ Hub-side behavior | The hub may arm bypassing active malfunctions — this is normal Ajax behaviour |
| **Real-time push events** | 🟡 Polling only | State is refreshed every 30s (disarmed) or 60s (armed) |
| **Groups / partitions** | 🔴 Not implemented | All zones are treated as a single partition |
| **Arm / Disarm timeout** | ℹ️ Max 60s | If the server is unreachable for >60s, the command fails with an explicit error — check hub status in the Ajax app |

---

## 📦 Entities Created per Device

For **every** Ajax device discovered, the following entities are created automatically:

### Diagnostic entities (always present)

| Entity | Type | Field | Description |
|---|---|---|---|
| `{name} Battery` | Sensor (%) | `batteryChargeLevelPercentage` | Battery level |
| `{name} Signal Level` | Sensor (enum) | `signalLevel` | Radio signal: NO_SIGNAL / WEAK / NORMAL / STRONG |
| `{name} Firmware` | Sensor (string) | `firmwareVersion` | Firmware version |
| `{name} Tamper` | Binary sensor | `tampered` | Tamper detection |
| `{name} Online` | Binary sensor | `online` | Device connectivity |
| `{name} Problem` | Binary sensor | `issuesCount` | Active issues flag |

### Platform-specific entities

| Device | Extra entities |
|---|---|
| Door Protect / Plus | Opening binary sensor, Temperature sensor |
| Motion Protect / Plus / Curtain | Motion binary sensor, Temperature sensor |
| LeaksProtect | Moisture binary sensor |
| Fire Protect Plus | Smoke binary sensor, Temperature sensor |
| HomeSiren / StreetSiren | Alarm binary sensor |
| REX / REX 2 Extender | Connectivity binary sensor |

### Attributes on binary sensor entities

All device binary sensors expose the following attributes:

| Attribute | Source field |
|---|---|
| `battery` | `batteryChargeLevelPercentage` |
| `online` | `online` |
| `signal_level` | `signalLevel` (mapped: NO_SIGNAL / WEAK / NORMAL / STRONG) |
| `tampered` | `tampered` |
| `temperature` | `temperature` |
| `firmware` | `firmwareVersion` |
| `state_raw` | `state` |
| `bypass_state` | `bypassState` |
| `issues_count` | `issuesCount` |
| `malfunctions` | `malfunctions` |
| `arming_mode` | `armingMode` |
| `arming_state` | `estimatedArmingState` |
| `night_mode_arm` | `nightModeArm` |
| `arm_delay_seconds` | `armDelaySeconds` |
| `alarm_delay_seconds` | `alarmDelaySeconds` |
| `arm_delay_night_seconds` | `armDelaySecondsInNightMode` |
| `alarm_delay_night_seconds` | `alarmDelaySecondsInNightMode` |
| `apply_delays_night_mode` | `applyDelaysToNightMode` |
| `always_active` | `alwaysActive` |
| `confirms_alarm` | `confirmsAlarm` |
| `verifies_alarm` | `verifiesAlarm` |
| `group_id` | `groupId` |
| `room_id` | `roomId` |
| `color` | `color` |
| `capabilities` | `capabilities` |
| `siren_triggers` | `sirenTriggers` |
| `self_monitoring_config` | `selfMonitoringConfig` |
| `indicator_light_mode` | `indicatorLightMode` |

**Door Protect / Plus** additionally exposes: `reed_closed`, `extra_contact_closed`, `reed_contact_configured`, `extra_contact_configured`, `two_stage_arming_role`, and (Plus only) `extra_contact_type`, `shock_sensor_configured`, `shock_sensor_sensitivity`, `tilt_sensor_configured`, `tilt_degrees`.

**Motion Protect / Plus / Curtain** additionally exposes: `sensitivity`, `pet_immunity`, `masked`, `antimasking`.

**HomeSiren / StreetSiren** additionally exposes: `alarm_duration`, `siren_volume_level`, `beep_volume_level`, `beep_on_arm_disarm`, `blink_while_armed`, `post_alarm_indication_mode`, `alarm_restriction_mode`, `chimes_enabled`, `act_on_arming`.

---

## 🏠 Hub Entities

The Ajax Hub creates the following entities, all linked to the same device card:

| Entity | Type | Description |
|---|---|---|
| `Ajax Hub {id}` | Alarm Control Panel | Arm / Disarm / Night mode |
| `Ajax Hub {id} Firmware` | Sensor | Hub firmware version string |
| `Ajax Hub {id} Battery` | Sensor (%) | Hub internal battery level and charge state |
| `Ajax Hub {id} Alarm As Malfunction Arming` | Sensor | `alarmAsMalfunctionWhenArming` flag |
| `Ajax Hub {id} Arm Prevention Conditions` | Sensor | Count of active arm prevention conditions |
| `Ajax Hub {id} Tamper` | Binary sensor | Hub tamper state |
| `Ajax Hub {id} Problem` | Binary sensor | Hub malfunction flag |

### Hub Attributes (Alarm Control Panel)

The alarm panel entity exposes **75 attributes** from the Ajax API, covering:

- **Identification:** `hub_id`, `hub_subtype`, `color`, `hub_address`, `modem_imei`
- **Firmware:** `firmware`, `fw_update_state`, `hardware_versions`, `debug_log_state`
- **Power:** `battery`, `externally_powered`, `charging_mode`, `battery_charging_flags`, `battery_saving_mode`, `safe_battery_charging`, `device_power_modes`
- **Alarm & Security:** `alarm_condition`, `alarm_confirmation`, `alarm_verification`, `fire_alarm`, `jamming_as_alarm`, `panic_siren_on_any_tamper`, `panic_siren_on_panic_button`, and more
- **Tamper:** `tampered`, `tamper_set`, `default_tamper_mode`
- **Arming:** `two_stage_arming`, `arm_prevention_conditions`, `arm_prevention_mode`, `grade_mode`, `sia_cp_settings`, `current_standard`, `password_length`, and more
- **Connectivity:** `active_channels`, `ethernet`, `gsm`, `jeweller`, `frequency_hopping`, `arc_alarm_settings`, `vds_locking_status`, and more
- **Configuration:** `limits`, `capabilities`, `ping_period_seconds`, `offline_alarm_seconds`, `led_brightness_level`, `led_indication_mode`, and more

---

## 🧠 Tips

- Combine this integration with **Home Assistant Automations** for:
  - Auto-arming when everyone leaves home.
  - Disarming when you arrive via geolocation.
  - Sending Telegram or mobile alerts on alarm triggers.
  - Alerting when battery drops below a threshold on any sensor.
  - Sending a notification if any device goes offline.

---

## 📋 Changelog

### v0.5.2 — REX 2 Extender Support

#### 🟢 New Device Support
- **REX / REX 2 Extender** — range extenders now appear as proper devices in HA with a **Connectivity** binary sensor (online / offline state) plus the standard diagnostic entities: Battery, Signal Level, Firmware, Tamper, Online, Problem.

#### 🐛 Bug Fixes
- **Signal Level sensor** — fixed stale comment in code (cosmetic, no functional change).

---

### v0.5.1 — Bug Fixes

#### 🐛 Bug Fixes
- **Signal Level sensor** — now returns a human-readable label (`NO_SIGNAL` / `WEAK` / `NORMAL` / `STRONG`) instead of a raw numeric value (0–4). The sensor uses the HA `ENUM` device class for proper state display and translation.
- **Arm / Disarm / Night mode timeout** — retry window extended to 60 attempts × 1s (60s total). On timeout, a clear error is logged: *"command timed out — the Ajax server did not confirm the operation after 60 attempts. Please verify the hub status in the Ajax app and try again."*
- **Setup retry timing** — integration setup retries are now aligned to 1s intervals (60 attempts max), consistent with arm command behaviour.

---

### v0.5.0 — Reliability & Device Attributes

#### 🟢 New Entities
- **Hub Battery sensor** — exposes the hub's internal backup battery percentage, charge state (`CHARGED`, `CHARGING`, `DISCHARGING`), external power status and charging mode. Appears as a diagnostic sensor on the hub device card.
- **HomeSiren / StreetSiren support** — sirens now have a dedicated `Alarm` binary sensor (active during triggered states) with siren-specific attributes: `alarm_duration`, `siren_volume_level`, `beep_volume_level`, `post_alarm_indication_mode`, `chimes_enabled`, and more.

#### 🟠 Improved Reliability
- **Arm / Disarm / Night mode auto-retry** — commands now automatically retry up to 50 times (500ms between attempts) when the server is temporarily rate-limited or unavailable. No user action required — HA will confirm the state change once the server accepts the command.
- **Setup retry on rate limit** — if the Ajax server rate-limits requests during integration startup (common with many devices), the setup now waits and retries automatically instead of failing and requiring a manual restart.
- **Rate limit detection** — the integration now correctly detects both HTTP 429 responses and the Ajax server's `"exceeded the limit"` message body, which is returned as HTTP 200 in some cases.

#### 🐛 Bug Fixes
- **Hub firmware version** — the `Firmware` sensor and hub device card now correctly show the firmware version string (e.g. `2.36.123`) instead of the raw API object.
- **Hub model** — the hub device card now shows the actual model identifier from the API (e.g. `HUB_2`) instead of the generic label `Hub`.

#### 🟡 More Device Attributes
All device binary sensors expose 17 additional attributes from the Ajax API, including arming delays (`arm_delay_seconds`, `alarm_delay_seconds`, night mode variants), alarm confirmation flags (`confirms_alarm`, `verifies_alarm`), and device metadata (`group_id`, `room_id`, `color`, `capabilities`, `siren_triggers`, `indicator_light_mode`).

---

### v0.4.2 — Code Quality & Documentation

- Translated all internal comments and log messages to English throughout the codebase
- Removed development artefacts (commented-out debug code, internal annotation tags)
- No functional changes — full backwards compatibility maintained

---

### v0.4.1 — Improved Arm/Disarm Reliability

#### 🔴 Bug Fixes
- Fixed error handling during arm, disarm, and night mode operations — transient server errors no longer cause unhandled exceptions in HA logs

#### 🟡 Improvements
- Malfunction warning: a log warning is now emitted when an arm command is issued while the hub reports active malfunctions or arm prevention conditions (the hub may arm with bypass anyway — this is normal Ajax behaviour)

---

### v0.4.0 — Security & Stability Update

#### 🔴 Security Fixes
- Password is now transmitted as a **SHA256 hash** — it was previously sent in plaintext
- Added request timeout on token refresh — prevents coordinator freeze on unresponsive server

#### 🟠 Robustness
- Entities maintain last known state during transient API errors — no false "unavailable" transitions
- Improved authentication stability — tolerates transient errors before triggering re-authentication
- **Adaptive polling**: 30s when disarmed, 60s when armed — reduces API load by ~50% when armed
- Client-side rate limiting prevents HTTP 429 on accounts with many devices
- Automatic retry with exponential backoff on transient network errors

#### 🟠 Code Quality
- Entity naming now follows HA guidelines (`"Device · Sensor"` format) — ⚠️ **Breaking change**: friendly names will change for existing entities
- `DeviceInfo` updated to typed struct with corrected manufacturer name (`"Ajax Systems"`)

#### 🟡 Features
- Added UI translations (English, Italian)
- Post-setup options flow: adjust polling intervals without reconfiguring the integration
- HA Diagnostics support: export anonymized debug data via the HA diagnostics UI

---

### v0.3.1 — Authentication & Stability Fixes

- Fixed false re-authentication prompts caused by concurrent token refresh across multiple coordinators
- Fixed startup failure when hub has no devices configured
- Fixed rate-limit responses incorrectly treated as authentication failures
- Fixed startup error handling — HA now shows "Not ready / retrying" instead of a misleading re-auth dialog
- Fixed config flow: added timeout, resolved duplicate entry creation, improved reauth dialog clarity
- Fixed device class warning for transmitter/multitransmitter devices on startup

---

### v0.3.0 — Coordinator Architecture

- Introduced shared `DataUpdateCoordinator` — one API call per device/hub per cycle, shared across all entities
- All entities use `CoordinatorEntity` — automatic `unavailable` state on API failure
- Arm/disarm commands now trigger an immediate coordinator refresh

---

### v0.2.0

- Added signal strength and firmware sensors for all devices
- Added hub companion sensors: Firmware, Alarm As Malfunction Arming, Arm Prevention Conditions
- Added hub companion binary sensors: Tamper, Problem
- Full hub `extra_state_attributes` from real API discovery

---

### v0.1.x

- Initial release: alarm panel, device binary sensors (opening, motion, smoke, moisture)
- Companion diagnostics: battery, tamper, connectivity, problem per device
- Device-specific attributes from real API discovery (DoorProtect, MotionProtect, LeaksProtect, FireProtect)

---

## 💬 Support & Feedback

If you encounter issues or have feature requests:
- Open a GitHub issue

---

## 🏷️ License

This project is licensed under the **MIT License** — see the [LICENSE](./LICENSE) file for details.

---

### ❤️ Credits

Developed with care for the Home Assistant community.
Secure. Private. Flexible.

> _"Automation should make your home smarter — not less secure."_

<img width="1536" height="1024" alt="image" src="https://github.com/user-attachments/assets/66f4c5bc-3d72-4c22-b7aa-fe275904ec9d" />
