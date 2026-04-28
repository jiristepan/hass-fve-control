"""Representation of extra load appliance."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from .appliance_decision import FveApplianceDecision

_LOGGER = logging.getLogger(__name__)


class FveAppliance:
    """Representation of a controllable extra load appliance."""

    TYPE_VARIABLE_LOAD = "wallbox"
    TYPE_CONSTANT_LOAD = "constant_load"

    def __init__(
        self, hass: HomeAssistant, controller: Any, config: dict[str, Any]
    ) -> None:
        _LOGGER.debug("Preparing appliance: %s", config)
        self._config = config
        self._controller = controller
        self.name: str = config.get("name", "")
        self.type: str = config.get("type", self.TYPE_CONSTANT_LOAD)
        self.minimal_power: int = config.get("min_power", 0)
        self.maximal_power: int = config.get("max_power", 0)
        self.step_power: int = config.get("step_power", 0)
        self.minimal_running_time: int = config.get("minimal_running_minutes", 5)
        self.availability_sensor: str | None = config.get("availability_sensor")
        self.actual_power_sensor: str | None = config.get("power_sensor")
        self.actual_switch_sensor: str | None = config.get("switch_sensor")
        self.startup_time_minutes: int = config.get("startup_time_minutes", 1)
        self.priority: int = config.get("static_priority", 0)

        self._h_availability: bool = False
        self._h_power: float = -1.0
        self._h_is_on: bool = False
        self._last_decision: FveApplianceDecision | None = None
        self._last_decision_dt: datetime | None = None
        self._last_decision_timestamp: float | None = None
        self._last_start: datetime | None = None
        self._assumed_state: str = "off"
        self._assumed_load: float = 0.0

        self._hass = hass

    def start_appliance(self, decision: FveApplianceDecision) -> None:
        self._last_decision = decision
        self._assumed_state = "on"
        self._last_decision_dt = datetime.now()
        self._last_decision_timestamp = self._last_decision_dt.timestamp()

    def stop_appliance(self, decision: FveApplianceDecision) -> None:
        self._last_decision = decision
        self._assumed_state = "off"
        self._last_decision_dt = datetime.now()
        self._last_decision_timestamp = self._last_decision_dt.timestamp()

    def print_state(self) -> None:
        _LOGGER.debug("[%s] appliance state: %s", self.name, self.state)

    @property
    def state(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "expected_state": self._assumed_state,
            "expected_energy": self._assumed_load,
            "last_decision_timestamp": self._last_decision_timestamp,
            "last_start": self._last_start,
            "is_available": self.is_available,
            "is_on": self.is_on,
            "actual_running_time_minutes": self.actual_running_time_minutes,
            "actual_power": self.actual_power,
        }

    def update(self) -> None:
        """Update states from hass."""
        # availability of the device
        if self.availability_sensor is not None:
            s = self._hass.states.get(self.availability_sensor)
            out = (s is not None) and (
                s.state == "on" or s.state == "true" or s.state is True
            )
            self._h_availability = out
        else:
            _LOGGER.warning("No availability sensor for %s", self.name)

        self._h_power = -1.0
        if self.actual_power_sensor is not None:
            state = self._hass.states.get(self.actual_power_sensor)
            if (
                state is not None
                and state.state != "unknown"
                and state.state != "unavailable"
            ):
                self._h_power = float(state.state)
        elif self._h_is_on:
            self._h_power = self.minimal_power

        # on/off state
        oldval = self._h_is_on
        self._h_is_on = False
        if self.actual_switch_sensor is not None:
            state = self._hass.states.get(self.actual_switch_sensor)
            if state is not None:
                self._h_is_on = (
                    (state.state != "off")
                    and (state.state != "unavailable")
                    and (state.state != "unknown")
                )
        elif self._h_power > 1.0:
            self._h_is_on = True

        # detect start transition
        if (not oldval) and self._h_is_on:
            _LOGGER.debug("[%s] appliance start - off > on detected", self.name)
            self._last_start = datetime.now()
            self._controller.reset_history()

        # detect stop transition
        if oldval and (not self._h_is_on):
            _LOGGER.debug("[%s] appliance stop - on > off detected", self.name)
            self._controller.reset_history()

        # If a requested start was not acknowledged by switch/power feedback,
        # release assumed state after startup timeout so start can be retried.
        if (
            self._assumed_state == "on"
            and not self._h_is_on
            and self._last_decision_dt is not None
        ):
            seconds_since_decision = (
                datetime.now().timestamp() - self._last_decision_dt.timestamp()
            )
            if seconds_since_decision >= self.startup_time_minutes * 60:
                _LOGGER.debug(
                    "[%s] start was not acknowledged, releasing assumed on state",
                    self.name,
                )
                self._assumed_state = "off"

    @property
    def is_available(self) -> bool:
        """Check if appliance is ready for start."""
        if self._last_decision_dt is None:
            sec_from_last_decision = 60 * 1000
        else:
            sec_from_last_decision = (
                datetime.now().timestamp() - self._last_decision_dt.timestamp()
            )

        return self._h_availability and (
            sec_from_last_decision >= self.startup_time_minutes * 60 * 5
            or self._assumed_state == "off"
        )

    @property
    def actual_running_time_minutes(self) -> float:
        now = datetime.now().timestamp()
        if self._last_start is None or not self.is_on:
            return 0

        return (now - self._last_start.timestamp()) / 60

    @property
    def is_running_long_enought(self) -> bool:
        return self.actual_running_time_minutes >= self.minimal_running_time

    @property
    def is_on(self) -> bool:
        return self._h_is_on

    @property
    def actual_power(self) -> float:
        return self._h_power

    @property
    def is_on_max(self) -> bool:
        if self.type == FveAppliance.TYPE_CONSTANT_LOAD:
            return self.is_on

        if self.type == FveAppliance.TYPE_VARIABLE_LOAD:
            return self.actual_power >= self.maximal_power

        return False


# Backward-compatible alias
FVE_Appliance = FveAppliance
