"""Diagnostics support for the Ajax Custom Integration.

Exposes configuration and runtime data through the HA Diagnostics interface
for bug reporting. Sensitive fields are automatically redacted.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

# Sensitive keys — never exposed in diagnostics output.
_TO_REDACT = {
    "session_token",
    "refresh_token",
    "password",
    "passwordHash",
    "login",
    "user_id",
    "token_created_at",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics data for a config entry.

    Sensitive data (tokens, credentials) is redacted before exposure.
    """
    domain_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})

    # Collect non-sensitive runtime information.
    runtime_info: dict[str, Any] = {}

    hubs = domain_data.get("hubs")
    if hubs:
        runtime_info["hubs_count"] = len(hubs)
        runtime_info["hub_ids"] = [h.get("hubId") for h in hubs]

    devices_by_hub = domain_data.get("devices_by_hub", {})
    if devices_by_hub:
        runtime_info["devices_count"] = sum(
            len(devices) for devices in devices_by_hub.values()
        )

    loaded_platforms = domain_data.get("loaded_platforms")
    if loaded_platforms:
        runtime_info["loaded_platforms"] = sorted(loaded_platforms)

    hub_coordinators = domain_data.get("hub_coordinators", {})
    coordinator_states: dict[str, Any] = {}
    for hub_id, coord in hub_coordinators.items():
        coordinator_states[hub_id] = {
            "last_update_success": coord.last_update_success,
            "update_interval_seconds": (
                coord.update_interval.seconds if coord.update_interval else None
            ),
            "consecutive_auth_errors": getattr(coord, "_consecutive_auth_errors", 0),
        }
    if coordinator_states:
        runtime_info["hub_coordinators"] = coordinator_states

    return {
        "entry_data": async_redact_data(dict(entry.data), _TO_REDACT),
        "entry_options": dict(entry.options),
        "runtime": runtime_info,
    }
