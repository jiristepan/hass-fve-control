""" Representation of extra load appliance """

from datetime import datetime
import logging

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class FVE_Appliance:
    """general represenation of extra load appliace"""

    TYPE_VARIABLE_LOAD = "wallbox"
    TYPE_CONSTANT_LOAD = "constant_load"

    # cofig
    name = None
    type = TYPE_CONSTANT_LOAD
    minimal_power = 0
    maximal_power = 0
    step_power = 0
    minimal_running_time = 0
    availability_sensor = None
    actual_power_sensor = None
    startup_time_minutes = 0
    priority = 0  # TODO: make dynamic priority

    _last_decision = None
    _last_start = None

    _assumed_state = "off"
    _assumed_load = 0.0

    def __init__(self, hass: HomeAssistant, controler, config) -> None:
        _LOGGER.debug(f"Preparing appliance: {config}")
        self._config = config
        self._controler = controler
        self.name = config.get("name")
        self.type = config.get("type")
        self.minimal_power = config.get("min_power")
        self.maximal_power = config.get("max_power")
        self.step_power = config.get("step_power")
        self.minimal_running_time = config.get("minimal_running_minutes")
        self.availability_sensor = config.get("availability_sensor")
        self.actual_power_sensor = config.get("power_sensor")
        self.actual_switch_sensor = config.get("switch_sensor")
        self.startup_time_minutes = config.get("startup_time_minutes")
        self.priority = config.get("static_priority")

        self._h_availability = False
        self._h_power = -1.0
        self._h_is_on = False

        self._hass = hass

    @property
    def state(self):
        out = {
            "name": self.name,
            "type": self.type,
            "expected_state": self._assumed_state,
            "expected_energy": self._assumed_load,
            "last_decision": self._last_decision,
            "last_start": self._last_start,
            "is_available": self.is_available,
            "is_on": self.is_on,
            "actual_running_time_minutes": self.actual_running_time_minutes,
            "actual_power": self.actual_power,
        }

        return out

    def update(self):
        """update states from hass"""
        # _LOGGER.debug(f"Updateting appliance {self.name}")
        # availability of the device
        if not self.availability_sensor is None:
            s = self._hass.states.get(self.availability_sensor)
            # _LOGGER.debug(f"availability sensor:{s}")
            out = (not s is None) and s.state == "on"
            self._h_availability = out
        else:
            _LOGGER.warning(f"ERROR - no availability sensor for {self.name}")

        # on/off state
        oldval = self._h_is_on
        self._h_is_on = False
        if not self.actual_switch_sensor is None:
            state = self._hass.states.get(self.actual_switch_sensor)
            if not state is None:
                self._h_is_on = state.state != "off" #this is because clima devices where on == cool etc.
        elif self._h_power > 1.0:
            self._h_is_on = True

        # indikace zapnuti
        if (not oldval) and self._h_is_on:
            _LOGGER.debug(f"[{self.name}] appliance start - off > on detected")
            self._last_start = datetime.now()
            self._controler.reset_history()

        # indikace vypnuti
        if oldval and (not self._h_is_on):
            _LOGGER.debug(f"[{self.name}] appliance stop - on > off detected")
            self._controler.reset_history()

        self._h_power = -1.0
        if not self.actual_power_sensor is None:
            state = self._hass.states.get(self.actual_power_sensor)
            if (
                not state is None
                and state.state != "unknown"
                and state.state != "unavailable"
            ):
                self._h_power = float(state.state)
        elif self._h_is_on:
            self._h_power = self.minimal_power

        # _LOGGER.debug(self.state)

    @property
    def is_available(self) -> bool:
        # _LOGGER.debug(f"{self.name}.is_available = {self._h_availability}")
        return self._h_availability

    @property
    def actual_running_time_minutes(self) -> int:
        now = datetime.now().timestamp()
        if self._last_start is None or not self.is_on:
            return 0

        return (now - self._last_start.timestamp()) / 60

    @property 
    def is_running_long_enought(self):
        return self.actual_running_time_minutes >= self.minimal_running_time

    @property
    def is_on(self) -> bool:
        return self._h_is_on

    @property
    def actual_power(self) -> float:
        return self._h_power

    @property
    def is_on_max(self):
        if self.type == FVE_Appliance.TYPE_CONSTANT_LOAD:
            return self.is_on

        if self.type == FVE_Appliance.TYPE_VARIABLE_LOAD:
            return self.actual_power >= self.maximal_power
