"""FVE Load Control integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_DECISION_INTERVAL,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .controller import FveController
from .coordinator import FveDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

type FveControlConfigEntry = ConfigEntry[FveDataUpdateCoordinator]

# YAML schema — kept for backward-compatible import path
LOAD_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Required("type"): cv.string,
        vol.Required("min_power"): int,
        vol.Optional("max_power"): int,
        vol.Optional("step_power"): int,
        vol.Optional("power_sensor"): cv.entity_id,
        vol.Required("switch_sensor"): cv.entity_id,
        vol.Optional("static_priority"): int,
        vol.Required("availability_sensor"): cv.entity_id,
        vol.Optional("priority_sensor"): cv.entity_id,
        vol.Optional("minimal_running_minutes", default=5): int,
        vol.Optional("startup_time_minutes", default=1): int,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required("fve_load_power_sensor"): cv.entity_id,
                vol.Required("fve_grid_power_sensor"): cv.entity_id,
                vol.Required("fve_pv_power_sensor"): cv.entity_id,
                vol.Required("fve_battery_power_sensor"): cv.entity_id,
                vol.Required("fve_battery_soc_sensor"): cv.entity_id,
                vol.Required("fve_battery_capacity"): int,
                vol.Optional("fve_battery_soc_min"): int,
                vol.Optional("fve_battery_max_power_in"): int,
                vol.Optional("fve_battery_max_power_out"): int,
                vol.Optional("use_forecast_solar", default=False): bool,
                vol.Optional("use_openweather", default=False): bool,
                vol.Optional("update_interval_sec", default=10): int,
                vol.Optional("decision_interval_sec", default=60): int,
                vol.Optional("max_history_in_minutes", default=10): int,
                vol.Optional("appliances"): vol.All(cv.ensure_list, [LOAD_SCHEMA]),
                vol.Optional("analytics", default=True): bool,
                vol.Optional("treshold_power", default=100): int,
                vol.Optional("force_stop_power", default=1000): int,
            }
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Handle YAML configuration — import to config entry."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "import"}, data=config[DOMAIN]
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: FveControlConfigEntry) -> bool:
    """Set up FVE Control from a config entry."""
    # Merge entry.data (core config) + entry.options (runtime overrides)
    config: dict[str, Any] = {**entry.data, **entry.options}

    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="FVE Control",
        manufacturer="jiristepan",
        model="FVE Load Control",
        sw_version="0.5.0",
    )

    controller = FveController(config, hass, device_info)
    update_interval = config.get(CONF_UPDATE_INTERVAL, 10)
    decision_interval = config.get(CONF_DECISION_INTERVAL, 60)

    coordinator = FveDataUpdateCoordinator(hass, controller, update_interval)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Decision cycle as separate interval (has side effects: fires events)
    entry.async_on_unload(
        async_track_time_interval(
            hass, controller.decide, timedelta(seconds=decision_interval)
        )
    )

    # Register services
    async def handle_set_priority(call: ServiceCall) -> None:
        controller.extra_load_priority = int(call.data["priority"])

    async def handle_force_decide(call: ServiceCall) -> None:
        await controller.decide()

    async def handle_reset_history(call: ServiceCall) -> None:
        controller.reset_history()

    hass.services.async_register(DOMAIN, "set_priority", handle_set_priority)
    hass.services.async_register(DOMAIN, "force_decide", handle_force_decide)
    hass.services.async_register(DOMAIN, "reset_history", handle_reset_history)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FveControlConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.services.async_remove(DOMAIN, "set_priority")
        hass.services.async_remove(DOMAIN, "force_decide")
        hass.services.async_remove(DOMAIN, "reset_history")
    return unload_ok
