""" Representation of extra load appliance """

from datetime import datetime
import logging

from homeassistant.core import HomeAssistant
from .fve_appliance_decision import FVE_appliance_decision

_LOGGER = logging.getLogger(__name__)

class FVE_Appliance:
    """ general represenation of extra load appliace """
    TYPE_VARIABLE_LOAD = "variable_load"
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
    priority = 0    # TODO: make dynamic priority

    _last_decision = None
    _last_start = None

    _assumed_state = "off"
    _assumed_load = 0.0

    def __init__(self, hass:HomeAssistant, config) -> None:
        _LOGGER.debug(f"Preparing appliance: {config}")
        self._config = config
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
            "name" : self.name,
            "type" : self.type,
            "expected_state" : self._assumed_state,
            "expected_energy" : self._assumed_load,
            "last_decision" : self._last_decision,
            "last_start" : self._last_start,
            "is_available" : self.is_available,
            "is_on" : self.is_on,
            "actual_running_time_minutes": self.actual_running_time_minutes,
            "actual_power": self.actual_power
        }

        return out

    def update(self):
        """ update states from hass """

        # _LOGGER.debug(f"Updateting appliance {self.name}")
        #availability of the device
        if (not self.availability_sensor is None):
            s = self._hass.states.get(self.availability_sensor)
            _LOGGER.debug(f"availability sensor:{s}")
            out = ((not s is None) and s.state == "on")
            self._h_availability = out
        else:
            _LOGGER.warning(f"ERROR - no availability sensor for {self.name}")



        #on/off state
        oldval = self._h_is_on
        self._h_is_on = False
        if not self.actual_switch_sensor is None:
            state = self._hass.states.get(self.actual_switch_sensor)
            if not state is None:
                self._h_is_on = (state.state == "on")
        elif self._h_power > 1.0:
            self._h_is_on = True

        # indikace zapnuti
        if (not oldval) and self._h_is_on:
            _LOGGER.debug(f"Virtual appliace start: {self.name}")
            self._last_start = datetime.now()

        self._h_power = -1.0
        if not self.actual_power_sensor is None:
            state = self._hass.states.get(self.actual_power_sensor)
            if not state is None and state.state != "unknown" and state.state != "unavailable":
                self._h_power = float(state.state)
        elif self._h_is_on:
            self._h_power = self.minimal_power



    @property
    def is_available(self) -> bool:
        return self._h_availability

    @property
    def actual_running_time_minutes(self) -> int:
        now = datetime.now().timestamp()
        if self._last_start is None or not self.is_on:
            return 0

        return (now - self._last_start.timestamp()) / 60

    @property
    def is_on(self) -> bool:
        return self._h_is_on


    @property
    def actual_power(self) -> float:
        return self._h_power

    def negotiate_free_power(self, free_power:int, running_appliances):
        """answer if this appliance can use some of free available power"""
        self.update()
        now = datetime.now().timestamp()
        actions = []

        _LOGGER.debug(f"RUNNING APP {running_appliances}")
        running_appliances_power = sum(
            map(
                lambda item: item.actual_power,
                list(filter(
                    lambda item: item.name != self.name and item.priority < self.priority,
                    running_appliances
                ))
            )
        )

        _LOGGER.debug(f'FREEPOWER {free_power}, state:{self.state}, other_appliances_power:{running_appliances_power}')

        # it is neccesary to switch off something other
        if self.is_available and not self.is_on and self.minimal_power > free_power and self.minimal_power < (free_power + running_appliances_power):
            decisions = []
            needed_power = self.minimal_power - free_power
            found_power = 0
            decisions = []
            _LOGGER.debug(f"Stoping other appliances. Looking for {needed_power}")
            for appliance in running_appliances:
                decisions = decisions + appliance.negotiate_missing_power(needed_power)
                found_power = sum(map(lambda x: abs(x.expected_power_ballance),decisions))
                if found_power > needed_power:
                    actions = decisions
                    break

        # if is on and is enough power, start it
        if self.is_available and not self.is_on and self.minimal_power < free_power:
            _LOGGER.debug("\tAction: START")
            actions.append(
                FVE_appliance_decision(
                    self.name,
                    FVE_appliance_decision.ACTION_START,
                    expected_power_ballance = self.minimal_power,
                    actual_free_power = free_power,
                    expected_maturity_timestamp = now + self.startup_time_minutes * 60
                )
            )
            self._last_start = now
            self._assumed_state = "on"
            self._assumed_energy = self.minimal_power

            if self.type == self.TYPE_VARIABLE_LOAD:
                _LOGGER.debug("\tAction: SET MINIMAL")
                actions.append(
                    FVE_appliance_decision(
                        self.name,
                        FVE_appliance_decision.ACTION_MINIMUM,
                        expected_power_ballance = self.minimal_power,
                        actual_free_power = free_power,
                        expected_maturity_timestamp = now + self.startup_time_minutes * 60
                    )
                )

        # in case of variable load, try increase it N-times
        if self.is_on and not self.step_power is None and free_power > self.step_power:
            num_steps = int(free_power / self.step_power)
            _LOGGER.debug(f"\tAction: INCREASE x {num_steps}")
            for i in range(num_steps):
                actions.append(
                    FVE_appliance_decision(
                        self.name,
                        FVE_appliance_decision.ACTION_INCREASE,
                        expected_power_ballance = self.step_power,
                        actual_free_power = free_power + (i+1) * self.step_power,
                        expected_maturity_timestamp = now + self.startup_time_minutes * 60
                    )
                )
                self._assumed_load = self._assumed_load + self.step_power

        if len(actions) > 0:
            self._last_decision = now

        return actions

    def negotiate_missing_power(self, free_power:int, force=False):
        """
            answer if this appliacne can lower its power in case power is missing
            free_power is negative in this case.
        """
        self.update()
        now = datetime.now().timestamp()
        actions = []
        missing_power = abs(free_power)

        _LOGGER.debug(f'Nego MISSING {free_power} :: {self.state} ')

        # in case of variable load minimize it
        if self.type == self.TYPE_VARIABLE_LOAD:
            if (self.actual_power - self.minimal_power) > missing_power:
                _LOGGER.debug("\tACTION: MINIMAL")
                actions.append(
                    FVE_appliance_decision(
                        self.name,
                        FVE_appliance_decision.ACTION_MINIMUM,
                        expected_power_ballance = 0-(self.actual_power - self.minimal_power),
                        actual_free_power = free_power + (self.actual_power - self.minimal_power),
                        expected_maturity_timestamp = now + 10
                    )
                )
                self._last_decision = now
                self._assumed_state="off"
                self._assumed_load=0.0
                return actions

        # switch off if neccesary
        # - in case it is running longer than minimal time
        # - in case it forced stop
        if (self.is_on and force) or (self.is_on and self.actual_running_time_minutes >= self.minimal_running_time):
            _LOGGER.debug("\tACTION: STOP")
            actions.append(
                FVE_appliance_decision(
                    self.name,
                    FVE_appliance_decision.ACTION_STOP,
                    expected_power_ballance = 0-self.minimal_power,
                    actual_free_power = free_power + self.minimal_power,
                    expected_maturity_timestamp = now + 10
                )
            )
            self._last_decision = now
            self._assumed_state="off"
            self._assumed_load=0.0

        return actions
