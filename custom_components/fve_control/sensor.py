"""Platform for sensor integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import FveDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class FveControlSensorDescription(SensorEntityDescription):
    """Describes an FVE Control sensor."""

    value_fn: Callable[[dict[str, Any]], float | str | None]
    value_type: str = "float"


SENSOR_DESCRIPTIONS: tuple[FveControlSensorDescription, ...] = (
    FveControlSensorDescription(
        key="pv_power_mean",
        translation_key="pv_power_mean",
        name="FVE Control: PV power mean",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("pv_power_mean"),
    ),
    FveControlSensorDescription(
        key="pv_power_stderr",
        translation_key="pv_power_stderr",
        name="FVE Control: PV power stderr",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("pv_power_stderr"),
    ),
    FveControlSensorDescription(
        key="grid_power_mean",
        translation_key="grid_power_mean",
        name="FVE Control: grid power mean",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("grid_power_mean"),
    ),
    FveControlSensorDescription(
        key="load_power_mean",
        translation_key="load_power_mean",
        name="FVE Control: load power mean",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("load_power_mean"),
    ),
    FveControlSensorDescription(
        key="battery_power_mean",
        translation_key="battery_power_mean",
        name="FVE Control: battery power mean",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("battery_power_mean"),
    ),
    FveControlSensorDescription(
        key="battery_soc_mean",
        translation_key="battery_soc_mean",
        name="FVE Control: battery SOC mean",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("battery_soc_mean"),
    ),
    FveControlSensorDescription(
        key="free_power",
        translation_key="free_power",
        name="FVE Control: free power for decision",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("fve_free_power"),
    ),
    FveControlSensorDescription(
        key="free_power_minimal",
        translation_key="free_power_minimal",
        name="FVE Control: free power minimal",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("fve_free_power_minimal"),
    ),
    FveControlSensorDescription(
        key="free_power_maximal",
        translation_key="free_power_maximal",
        name="FVE Control: free power maximal",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("fve_free_power_maximal"),
    ),
    FveControlSensorDescription(
        key="free_power_middle",
        translation_key="free_power_middle",
        name="FVE Control: free power middle",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("fve_free_power_middle"),
    ),
    FveControlSensorDescription(
        key="battery_gap",
        translation_key="battery_gap",
        name="FVE Control: watts to full battery",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("battery_gap"),
    ),
    FveControlSensorDescription(
        key="hours_to_full_battery",
        translation_key="hours_to_full_battery",
        name="FVE Control: hours to full battery",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("hours_to_full_battery"),
    ),
    FveControlSensorDescription(
        key="hours_to_fve_start",
        translation_key="hours_to_fve_start",
        name="FVE Control: hours to start FVE at sun rising",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("hours_to_fve_start"),
    ),
    FveControlSensorDescription(
        key="hours_to_fve_stop",
        translation_key="hours_to_fve_stop",
        name="FVE Control: hours to FVE stop at sun setting",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("hours_to_fve_stop"),
    ),
    FveControlSensorDescription(
        key="hours_to_fve_max",
        translation_key="hours_to_fve_max",
        name="FVE Control: hours to FVE max at noon",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("hours_to_fve_max"),
    ),
    FveControlSensorDescription(
        key="fve_phase",
        translation_key="fve_phase",
        name="FVE Control: phase of FVE production",
        device_class=SensorDeviceClass.ENUM,
        options=["night", "start", "maximum", "finish", "lowsun"],
        value_fn=lambda data: data.get("fve_phase"),
        value_type="str",
    ),
    FveControlSensorDescription(
        key="running_appliances_names",
        translation_key="running_appliances_names",
        name="FVE Control: running appliances",
        value_fn=lambda data: data.get("running_appliances_names"),
        value_type="str",
    ),
    FveControlSensorDescription(
        key="running_appliances_power",
        translation_key="running_appliances_power",
        name="FVE Control: running appliances power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("running_appliances_power"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FVE Control sensors from a config entry."""
    coordinator: FveDataUpdateCoordinator = entry.runtime_data
    async_add_entities(
        FveControlSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class FveControlSensor(CoordinatorEntity[FveDataUpdateCoordinator], SensorEntity):
    """Sensor entity for FVE Control."""

    entity_description: FveControlSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FveDataUpdateCoordinator,
        description: FveControlSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.controller.device_info

    @property
    def native_value(self) -> float | str | None:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        value = self.entity_description.value_fn(self.coordinator.data)
        if value is not None and self.entity_description.value_type == "float":
            try:
                return round(float(value), 2)
            except (ValueError, TypeError):
                return None
        return value
