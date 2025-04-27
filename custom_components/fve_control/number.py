"""Platform for number integration."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity
from homeassistant.const import  EntityCategory

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from typing import Callable


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

    entities = [FVEExtraLoadPriority(fve_controler)]
    async_add_entities(entities, True)


class FVEExtraLoadPriority(NumberEntity):
    """
    Representation the priority of extra load
    1: very conservative. Takes only free_power_minimum
    2: conservative takes takes only free_power_minimum + 50% battery load
    3: takes free_power_middle = free_power_minimum + 50% battery load
    4: takes -grid + 1/2 maximim battery current out
    5: greedy takes -grid + maximim battery current out

    """

    _attr_has_entity_name = True
    _attr_name = "extra_load_priority"
    _attr_unique_id = "extra_load_priority"
    _attr_native_max_value = 5
    _attr_native_step = 1
    _attr_native_min_value = 1
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, device) -> None:
        super().__init__()
        self.device = device

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self.device.device_info

    @property
    def available(self) -> bool | None:
        return self.device.is_ready()

    @property
    def native_value(self) -> int | None:
        """Return the state of the number entity."""
        return self.device.extra_load_priority

    async def async_set_native_value(self, value: float) -> None:
        """Set the value of the entity."""
        self.device.extra_load_priority = int(value)
