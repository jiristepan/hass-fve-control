"""Platform for number integration."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import FveDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FVE Control numbers from a config entry."""
    coordinator: FveDataUpdateCoordinator = entry.runtime_data
    async_add_entities([FveExtraLoadPriority(coordinator)])


class FveExtraLoadPriority(CoordinatorEntity[FveDataUpdateCoordinator], NumberEntity):
    """Priority control for extra load decisions.

    1: very conservative - takes only free_power_minimum
    2: conservative - free_power_minimum + 50% battery load
    3: takes free_power_middle
    4: takes -grid + 1/2 maximum battery current out
    5: greedy - takes -grid + maximum battery current out
    """

    _attr_has_entity_name = True
    _attr_name = "extra_load_priority"
    _attr_native_max_value = 5
    _attr_native_step = 1
    _attr_native_min_value = 1
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: FveDataUpdateCoordinator) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_extra_load_priority"
        )
        self._attr_device_info = coordinator.controller.device_info

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return super().available and self.coordinator.controller.is_ready()

    @property
    def native_value(self) -> int | None:
        """Return the current priority value."""
        return self.coordinator.controller.extra_load_priority

    async def async_set_native_value(self, value: float) -> None:
        """Set the priority value."""
        self.coordinator.controller.extra_load_priority = int(value)
        self.async_write_ha_state()
