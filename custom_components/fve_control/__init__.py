
from __future__ import annotations
from datetime import timedelta

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN
from .fve_controler import FVE_Controler

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(
                    "fve_grid_power_sensor"
                ): cv.entity_id,
                        vol.Optional(
                    "fve_pv_power_sensor"
                ): cv.entity_id,
                        vol.Optional(
                    "fve_battery_power_sensor"
                ): cv.entity_id,
                        vol.Optional(
                    "fve_battery_soc_sensor"
                ): cv.entity_id
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

    hass.data.setdefault(DOMAIN, {})

    fve_controler = FVE_Controler(conf,hass)
    hass.data[DOMAIN] = fve_controler

    async_track_time_interval(hass, fve_controler.decide, timedelta(seconds=10))

    return True
