"""Platform for sensor integration."""

from __future__ import annotations

import logging
from typing import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import *
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA_BASE
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from typing import Any, Callable, Dict, Optional
from homeassistant.const import UnitOfPower, UnitOfEnergy


from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities: Callable,
    discovery_info=None,
) -> None:
    """Set up the FVE CONTROL sensors platform."""

    fve_controler = hass.data[DOMAIN]

    entities = [
        General_FVE_Control_Entity(
            fve_controler,
            {
                "fve_data_attribute": "pv_power_mean",
                "name": "FVE Control: PV power mean",
                "unique_id": "pv_power_mean",
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "native_unit_of_measurement": UnitOfPower.WATT,
                "type": "float",
            },
        ),
        General_FVE_Control_Entity(
            fve_controler,
            {
                "fve_data_attribute": "pv_power_stderr",
                "name": "FVE Control: PV power stderr",
                "unique_id": "pv_power_stderr",
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "native_unit_of_measurement": UnitOfPower.WATT,
                "type": "float",
            },
        ),
        General_FVE_Control_Entity(
            fve_controler,
            {
                "fve_data_attribute": "grid_power_mean",
                "name": "FVE Control: grid power mean",
                "unique_id": "grid_power_mean",
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "native_unit_of_measurement": UnitOfPower.WATT,
                "type": "float",
            },
        ),
        General_FVE_Control_Entity(
            fve_controler,
            {
                "fve_data_attribute": "load_power_mean",
                "name": "FVE Control: load power mean",
                "unique_id": "load_power_mean",
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "native_unit_of_measurement": UnitOfPower.WATT,
                "type": "float",
            },
        ),
        General_FVE_Control_Entity(
            fve_controler,
            {
                "fve_data_attribute": "battery_power_mean",
                "name": "FVE Control: battery power mean",
                "unique_id": "battery_power_mean",
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "native_unit_of_measurement": UnitOfPower.WATT,
                "type": "float",
            },
        ),
        General_FVE_Control_Entity(
            fve_controler,
            {
                "fve_data_attribute": "battery_soc_mean",
                "name": "FVE Control: battery SOC mean",
                "unique_id": "battery_soc_mean",
                "device_class": SensorDeviceClass.ENERGY_STORAGE,
                "state_class": SensorStateClass.MEASUREMENT,
                "native_unit_of_measurement": PERCENTAGE,
                "type": "float",
            },
        ),
        General_FVE_Control_Entity(
            fve_controler,
            {
                "fve_data_attribute": "fve_free_power",
                "name": "FVE Control: free power for decision",
                "unique_id": "free_power",
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "native_unit_of_measurement": UnitOfPower.WATT,
                "type": "float",
            },
        ),
        General_FVE_Control_Entity(
            fve_controler,
            {
                "fve_data_attribute": "fve_free_power_minimal",
                "name": "FVE Control: free power minimal",
                "unique_id": "free_power_minimal",
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "native_unit_of_measurement": UnitOfPower.WATT,
                "type": "float",
            },
        ),
        General_FVE_Control_Entity(
            fve_controler,
            {
                "fve_data_attribute": "fve_free_power_maximal",
                "name": "FVE Control: free power maximal",
                "unique_id": "free_power_maximal",
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "native_unit_of_measurement": UnitOfPower.WATT,
                "type": "float",
            },
        ),
        General_FVE_Control_Entity(
            fve_controler,
            {
                "fve_data_attribute": "fve_free_power_middle",
                "name": "FVE Control: free power middle",
                "unique_id": "free_power_middle",
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "native_unit_of_measurement": UnitOfPower.WATT,
                "type": "float",
            },
        ),
        General_FVE_Control_Entity(
            fve_controler,
            {
                "fve_data_attribute": "battery_gap",
                "name": "FVE Control: watts to full battery",
                "unique_id": "battery_gap",
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.MEASUREMENT,
                "native_unit_of_measurement": UnitOfEnergy.WATT_HOUR,
                "type": "float",
            },
        ),
        General_FVE_Control_Entity(
            fve_controler,
            {
                "fve_data_attribute": "hours_to_full_battery",
                "name": "FVE Control: hours to full battery",
                "unique_id": "hours_to_full_battery",
                "state_class": SensorStateClass.MEASUREMENT,
                "type": "float",
            },
        ),
        General_FVE_Control_Entity(
            fve_controler,
            {
                "fve_data_attribute": "hours_to_fve_start",
                "name": "FVE Control: hours to start FVE at sun rising",
                "unique_id": "hours_to_fve_start",
                "state_class": SensorStateClass.MEASUREMENT,
                "type": "float",
            },
        ),
        General_FVE_Control_Entity(
            fve_controler,
            {
                "fve_data_attribute": "hours_to_fve_stop",
                "name": "FVE Control: hours to FVE stop at sun setting",
                "unique_id": "hours_to_fve_stop",
                "state_class": SensorStateClass.MEASUREMENT,
                "type": "float",
            },
        ),
        General_FVE_Control_Entity(
            fve_controler,
            {
                "fve_data_attribute": "hours_to_fve_max",
                "name": "FVE Control: hours to FVE max at noon",
                "unique_id": "hours_to_fve_max",
                "state_class": SensorStateClass.MEASUREMENT,
                "type": "float",
            },
        ),
        General_FVE_Control_Entity(
            fve_controler,
            {
                "fve_data_attribute": "fve_phase",
                "name": "FVE Control: phase of FVE production",
                "unique_id": "fve_phase",
                "options": ["night", "start", "maximum", "finish", "lowsun"],
                "device_class": SensorDeviceClass.ENUM,
                "type": "str",
            },
        ),
        General_FVE_Control_Entity(
            fve_controler,
            {
                "fve_data_attribute": "running_appliances_names",
                "name": "FVE Control: running appliances",
                "unique_id": "running_appliances_names",
                "device_class": SensorDeviceClass.ENUM,
                "type": "str",
            },
        ),
        General_FVE_Control_Entity(
            fve_controler,
            {
                "fve_data_attribute": "running_appliances_power",
                "name": "FVE Control: running applikaces power",
                "unique_id": "running_appliances_power",
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "native_unit_of_measurement": UnitOfPower.WATT,
                "type": "float",
            },
        ),
    ]

    async_add_entities(entities, update_before_add=False)
    # _LOGGER.debug(entities)


class General_FVE_Control_Entity(SensorEntity):
    """Representation mean value of PV power"""

    _attr_has_entity_name = True

    def __init__(self, device, config) -> None:
        super().__init__()
        self.device = device
        self._state = None
        self._available = True
        self._config = config
        # _LOGGER.debug(f"sensor init: {config}" )

    @property
    def name(self) -> str:
        return self._config["name"]

    @property
    def unique_id(self) -> str:
        return self._config["unique_id"]

    @property
    def device_class(self):
        return self._config.get("device_class")

    @property
    def state_class(self):
        return self._config.get("state_class")

    @property
    def options(self):
        return self._config.get("options")

    @property
    def native_unit_of_measurement(self):
        return self._config.get("native_unit_of_measurement")

    @property
    def available(self) -> bool | None:
        return self.device.is_available()

    @property
    def state(self) -> Optional[str]:
        return self._state

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        # _LOGGER.debug(f"sensor device info {self.device.device_info}")
        return self.device.device_info

    async def async_update(self) -> None:
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        # _LOGGER.debug(f"Async Sensor -> {self.device.get_state(self._attr_unique_id)}")
        val = self.device.get_state(self._config["fve_data_attribute"])

        if "type" in self._config:
            if self._config["type"] == "float":
                val = round(float(val), 2)

            if self._config["type"] == "int":
                val = int(val)

        self._state = val
