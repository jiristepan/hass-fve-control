"""Diagnostics support for FVE Control."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import FveControlConfigEntry
from .coordinator import FveDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FveControlConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: FveDataUpdateCoordinator = entry.runtime_data
    controller = coordinator.controller

    return {
        "config": {k: v for k, v in entry.data.items() if k != "appliances"},
        "options": dict(entry.options),
        "data": coordinator.data or {},
        "appliances": [a.state for a in controller.appliances],
        "history_lengths": {k: len(v) for k, v in controller.history.items()},
        "extra_load_priority": controller.extra_load_priority,
    }
