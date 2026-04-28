"""Event platform for FVE Control."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .appliance_decision import (
    ACTION_DECREASE,
    ACTION_INCREASE,
    ACTION_MAXIMUM,
    ACTION_MINIMUM,
    ACTION_START,
    ACTION_STOP,
)
from .coordinator import FveDataUpdateCoordinator

EVENT_TYPES = [
    ACTION_START,
    ACTION_STOP,
    ACTION_INCREASE,
    ACTION_DECREASE,
    ACTION_MAXIMUM,
    ACTION_MINIMUM,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FVE Control event entities."""
    coordinator: FveDataUpdateCoordinator = entry.runtime_data
    controller = coordinator.controller

    global_event = FveControlEvent(coordinator)
    entities: list[EventEntity] = [global_event]

    appliance_events: dict[str, FveApplianceEvent] = {}
    for appliance in controller.appliances:
        event = FveApplianceEvent(coordinator, appliance)
        appliance_events[appliance.name] = event
        entities.append(event)

    # Wire event entities back to controller for firing
    controller.set_event_entities(global_event, appliance_events)

    async_add_entities(entities)


class FveControlEvent(EventEntity):
    """Event entity for all FVE control decisions."""

    _attr_has_entity_name = True
    _attr_name = "Decision"
    _attr_event_types = EVENT_TYPES

    def __init__(self, coordinator: FveDataUpdateCoordinator) -> None:
        """Initialize the event entity."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_decision_event"
        self._attr_device_info = coordinator.controller.device_info

    @callback
    def fire_decision(self, action: str, appliance_name: str) -> None:
        """Fire a decision event."""
        self._trigger_event(
            action,
            {"appliance_name": appliance_name},
        )
        self.async_write_ha_state()


class FveApplianceEvent(EventEntity):
    """Event entity for a specific appliance's decisions."""

    _attr_has_entity_name = True
    _attr_event_types = EVENT_TYPES

    def __init__(self, coordinator: FveDataUpdateCoordinator, appliance: Any) -> None:
        """Initialize the appliance event entity."""
        self._coordinator = coordinator
        self._appliance = appliance
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{appliance.name}_event"
        )
        self._attr_device_info = coordinator.controller.device_info
        self._attr_name = f"{appliance.name} decision"

    @callback
    def fire_decision(self, action: str) -> None:
        """Fire a decision event for this appliance."""
        self._trigger_event(action, {"appliance_name": self._appliance.name})
        self.async_write_ha_state()
