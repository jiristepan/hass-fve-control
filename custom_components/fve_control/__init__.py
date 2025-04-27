from __future__ import annotations
from datetime import timedelta

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.discovery import async_load_platform


from .const import DOMAIN
from .fve_controler import FVE_Controler

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

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
                vol.Optional("history_in_minutes", default=10): int,
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
    """Set up the FVE Load Control component."""

    if DOMAIN in config:
        conf = config[DOMAIN]
    else:
        conf = {}

    _LOGGER.debug(conf)
    hass.data.setdefault(DOMAIN, {})

    device_info = DeviceInfo(
        identifiers={(DOMAIN, "fve_controler")},
        name="FVE Control",
        manufacturer="jst",
        model="FVE Control",
        sw_version="1.0.0",
    )
    fve_controler = FVE_Controler(conf, hass, device_info)

    hass.data[DOMAIN] = fve_controler

    # Use async_load_platform instead of hass.helpers.discovery.load_platform
    await async_load_platform(hass, "sensor", DOMAIN, {}, config)
    await async_load_platform(hass, "number", DOMAIN, {}, config)

    async_track_time_interval(
        hass, fve_controler.decide, timedelta(seconds=conf.get("decision_interval_sec"))
    )
    async_track_time_interval(
        hass, fve_controler.update, timedelta(seconds=conf.get("update_interval_sec"))
    )

    return True
