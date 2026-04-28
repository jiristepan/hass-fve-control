"""Core FVE controller logic."""

from __future__ import annotations

import logging
import statistics as stats
from datetime import UTC, datetime
from typing import Any, ClassVar

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .appliance import FveAppliance
from .appliance_decision import FveApplianceDecision
from .const import (
    NAME_BATTERY_POWER,
    NAME_BATTERY_SOC,
    NAME_GRID_POWER,
    NAME_LOAD_POWER,
    NAME_PV_POWER,
    analytics_url,
)

_LOGGER = logging.getLogger(__name__)


class FveController:
    """FVE load control decision engine."""

    UPDATE_INTERVAL = 10
    MAX_HISTORY_TIME = 600
    MAX_HISTORY_LEN = int(MAX_HISTORY_TIME / UPDATE_INTERVAL)

    FVE_SUN_RISE_OFFSET = 1
    FVE_SUN_SET_OFFSET = 1
    FVE_SUN_MAX_OFFSET = 2

    attributes: ClassVar[list[dict[str, Any]]] = [
        {
            "input_sensor_key": "fve_pv_power_sensor",
            "output_attribute": NAME_PV_POWER,
            "stats": ["mean", "min", "max", "stderr"],
        },
        {
            "input_sensor_key": "fve_grid_power_sensor",
            "output_attribute": NAME_GRID_POWER,
            "stats": ["mean", "min", "max", "stderr"],
        },
        {
            "input_sensor_key": "fve_load_power_sensor",
            "output_attribute": NAME_LOAD_POWER,
            "stats": ["mean", "min", "max", "stderr"],
        },
        {
            "input_sensor_key": "fve_battery_power_sensor",
            "output_attribute": NAME_BATTERY_POWER,
            "stats": ["mean", "min", "max", "stderr"],
        },
        {
            "input_sensor_key": "fve_battery_soc_sensor",
            "output_attribute": NAME_BATTERY_SOC,
            "stats": ["mean", "min", "max", "stderr"],
        },
    ]

    forecast_solar_attributes: ClassVar[list[dict[str, Any]]] = [
        {
            "name": "sensor.energy_next_hour",
            "data_key": "energy_next_hour",
            "normalize": lambda x: float(x) * 1000,
        },
    ]

    openweather_attributes: ClassVar[list[dict[str, Any]]] = [
        {
            "name": "sensor.openweathermap_cloud_coverage",
            "data_key": "cloud_coverage",
            "normalize": lambda x: int(x),
        },
        {
            "name": "sensor.openweathermap_forecast_condition",
            "data_key": "forecast_condition",
            "normalize": lambda x: x,
        },
    ]

    def __init__(
        self, config: dict[str, Any], hass: HomeAssistant, device_info: Any
    ) -> None:
        home = hass.config.as_dict()
        self._hass_instance_id: dict[str, Any] = {}
        if home is not None:
            self._hass_instance_id["name"] = home.get("location_name")
            self._hass_instance_id["latitude"] = home.get("latitude")
            self._hass_instance_id["longitude"] = home.get("longitude")

        self._config = config
        self._hass = hass
        self.device_info = device_info
        self._history: dict[str, list[float]] = {}
        self._decision_history: dict[str, Any] = {}
        self._next_decision_ts: float = 0
        self._appliances: list[FveAppliance] = []
        self._data: dict[str, Any] = {}

        self.extra_load_priority: int = 2
        self._event_entity: Any = None
        self._appliance_events: dict[str, Any] = {}

        self.MAX_HISTORY_TIME = int(self._config.get("max_history_in_minutes", 10) * 60)
        self.UPDATE_INTERVAL = int(self._config.get("update_interval_sec", 10))
        self.MAX_HISTORY_LEN = int(self.MAX_HISTORY_TIME / self.UPDATE_INTERVAL)

        self.reset_history()

        if "appliances" in config:
            for appliance_config in config["appliances"]:
                self._appliances.append(FveAppliance(hass, self, appliance_config))

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    @property
    def history(self) -> dict[str, list[float]]:
        return self._history

    @property
    def appliances(self) -> list[FveAppliance]:
        return self._appliances

    def set_event_entities(
        self, global_event: Any, appliance_events: dict[str, Any]
    ) -> None:
        """Set event entity references for firing decisions."""
        self._event_entity = global_event
        self._appliance_events = appliance_events

    def is_ready(self) -> bool:
        return (
            "fve_pv_power_sensor" in self._history
            and len(self._history["fve_pv_power_sensor"]) > 0
        )

    async def decide(self, ts: Any = None) -> bool:
        """Run decision cycle."""
        now_ts = datetime.now().timestamp()
        if not self.is_ready():
            _LOGGER.debug("Decision not ready")
            return True

        if now_ts < self._next_decision_ts:
            _LOGGER.debug(
                "Waiting after decision. Remaining [%d sec]",
                int(self._next_decision_ts - now_ts),
            )
            return True

        free_power = self._data["fve_free_power"]
        threshold_power = self._config["treshold_power"]
        force_stop_power = self._config["force_stop_power"]

        # debug appliances
        for appliance in self._appliances:
            appliance.print_state()

        decisions: list[FveApplianceDecision] = []

        running_appliances = list(
            filter(
                lambda appliance: appliance.is_on,
                sorted(self._appliances, key=lambda x: x.priority),
            )
        )

        running_appliances_not_max = list(
            filter(
                lambda app: (
                    app.is_on
                    and (not app.is_on_max)
                    and app.type == FveAppliance.TYPE_VARIABLE_LOAD
                ),
                sorted(self._appliances, key=lambda x: x.priority, reverse=True),
            )
        )

        running_appliances_power = sum(
            map(lambda item: item.actual_power, running_appliances)
        )
        available_stoped_appliances = list(
            filter(
                lambda a: a.is_available and (not a.is_on),
                sorted(self._appliances, key=lambda x: x.priority, reverse=True),
            )
        )
        _LOGGER.debug(
            "Free power: %s, running power: %s, running appliances: %s, available: %s",
            free_power,
            running_appliances_power,
            ",".join([x.name for x in running_appliances]),
            ",".join([x.name for x in available_stoped_appliances]),
        )
        _LOGGER.debug(
            "Decision thresholds: start/increase>%sW, force_stop>%sW",
            threshold_power,
            force_stop_power,
        )

        if free_power + running_appliances_power > threshold_power:
            decisions = self.increase_appliances(
                free_power,
                running_appliances_not_max,
                running_appliances_power,
                running_appliances,
            )

            if len(decisions) == 0:
                decisions = self.start_appliances(
                    free_power,
                    available_stoped_appliances,
                    running_appliances_power,
                    running_appliances,
                )

        if free_power < 0 - threshold_power:
            # BUG-4 fix: compare magnitudes instead of signed values
            force = abs(free_power) >= force_stop_power
            decisions = self.stop_appliances(
                abs(free_power), running_appliances, force_stop=force
            )

        if len(decisions) > 0:
            await self._send_analytics_decisions(decisions)
            self.reset_history()
            self._next_decision_ts = max(
                map(lambda x: x.expected_maturity_timestamp, decisions)
            )

            for decision in decisions:
                _LOGGER.debug("Firing FVE decision: %s", decision.get_data())

                # set assumed state and last decision
                if decision.action == "stop":
                    decision.appliance.stop_appliance(decision)
                else:
                    decision.appliance.start_appliance(decision)

                # Fire event entities (modern pattern)
                if self._event_entity is not None:
                    self._event_entity.fire_decision(
                        decision.action, decision.appliance_name
                    )
                appliance_event = self._appliance_events.get(decision.appliance_name)
                if appliance_event is not None:
                    appliance_event.fire_decision(decision.action)

                # Also fire on bus for backward compatibility and automation flexibility.
                event_data = decision.get_data()
                appliance_slug = decision.appliance_name.lower().replace(" ", "_")
                self._hass.bus.fire("fve_control", event_data)
                self._hass.bus.fire(f"fve_control_{decision.action}", event_data)
                self._hass.bus.fire(
                    f"fve_control_{decision.action}_{appliance_slug}", event_data
                )

        if len(decisions) == 0:
            _LOGGER.debug(
                "No decisions taken. free_power=%sW, running_power=%sW, available_count=%s",
                free_power,
                running_appliances_power,
                len(available_stoped_appliances),
            )

        return True

    def increase_appliances(
        self,
        free_power: float,
        available_appliances_list: list[FveAppliance],
        running_appliances_power: float,
        running_appliances_list: list[FveAppliance],
    ) -> list[FveApplianceDecision]:
        """Try to increase variable load appliances to use free power."""
        alocated_power = 0.0
        decisions: list[FveApplianceDecision] = []

        for a in available_appliances_list:
            lower_priority_running_appliances_list = list(
                filter(lambda ap: ap.priority < a.priority, running_appliances_list)
            )
            lower_priority_running_appliances_power = sum(
                [ap.actual_power for ap in lower_priority_running_appliances_list]
            )

            remaining_free_power = (
                abs(free_power)
                - alocated_power
                + lower_priority_running_appliances_power
            )
            _LOGGER.debug(
                "Remaining free power for increase: %s / (%s + %s). Testing %s",
                remaining_free_power,
                abs(free_power),
                lower_priority_running_appliances_power,
                a.name,
            )
            if remaining_free_power < 0:
                break

            if (
                a.type == FveAppliance.TYPE_VARIABLE_LOAD
                and a.is_on
                and not a.is_on_max
                and a.step_power < remaining_free_power
            ):
                alocated_power = alocated_power + a.step_power
                _LOGGER.debug("%s > INCREASE", a.name)
                decisions.append(
                    FveApplianceDecision(
                        appliance=a,
                        action="increase",
                        expected_power_ballance=a.step_power,
                        expected_maturity_sec=a.startup_time_minutes * 60,
                    )
                )

            # stop lower priority if over budget
            if alocated_power > free_power:
                stop_decs = self.stop_appliances(
                    alocated_power - free_power,
                    lower_priority_running_appliances_list,
                    False,
                )
                decisions = decisions + stop_decs

        return decisions

    def start_appliances(
        self,
        free_power: float,
        available_appliances_list: list[FveAppliance],
        running_appliances_power: float,
        running_appliances_list: list[FveAppliance],
    ) -> list[FveApplianceDecision]:
        """Try to start appliances to use free power."""
        alocated_power = 0.0
        decisions: list[FveApplianceDecision] = []
        lower_priority_running_appliances_list: list[FveAppliance] = []

        for a in available_appliances_list:
            lower_priority_running_appliances_list = list(
                filter(lambda ap: ap.priority < a.priority, running_appliances_list)
            )

            lower_priority_running_appliances_power = sum(
                [ap.actual_power for ap in lower_priority_running_appliances_list]
            )

            remaining_free_power = (
                abs(free_power)
                - alocated_power
                + lower_priority_running_appliances_power
            )
            _LOGGER.debug(
                "Remaining free power: %s / (%s + %s). Testing %s",
                remaining_free_power,
                abs(free_power),
                lower_priority_running_appliances_power,
                a.name,
            )
            if remaining_free_power < 0:
                break

            if (
                a.type == FveAppliance.TYPE_CONSTANT_LOAD
                and a.minimal_power < remaining_free_power
            ):
                alocated_power = alocated_power + a.minimal_power
                _LOGGER.debug("%s > START", a.name)
                decisions.append(
                    FveApplianceDecision(
                        appliance=a,
                        action="start",
                        expected_power_ballance=a.minimal_power,
                        expected_maturity_sec=a.startup_time_minutes * 60,
                    )
                )

            elif (
                a.type == FveAppliance.TYPE_VARIABLE_LOAD
                and (not a.is_on)
                and a.minimal_power < remaining_free_power
            ):
                alocated_power = alocated_power + a.minimal_power
                _LOGGER.debug("%s > START", a.name)
                decisions.append(
                    FveApplianceDecision(
                        appliance=a,
                        action="start",
                        expected_power_ballance=a.minimal_power,
                        expected_maturity_sec=a.startup_time_minutes * 60,
                    )
                )

        # stop lower priority if over budget
        if alocated_power > free_power:
            stop_decs = self.stop_appliances(
                alocated_power - free_power,
                lower_priority_running_appliances_list,
                False,
            )
            decisions = decisions + stop_decs

        return decisions

    def stop_appliances(
        self,
        neccessary_power: float,
        appliances_list: list[FveAppliance],
        force_stop: bool = False,
    ) -> list[FveApplianceDecision]:
        """Try to find necessary power by stopping/minimizing appliances."""
        saved_power = 0.0
        decisions: list[FveApplianceDecision] = []

        for a in appliances_list:
            remaining_neccessary_power = abs(neccessary_power) - saved_power

            _LOGGER.debug(
                "Remaining necessary power: %s / %s. Testing %s",
                remaining_neccessary_power,
                abs(neccessary_power),
                a.name,
            )
            if remaining_neccessary_power < 0:
                break

            # stop if running long enough
            if a.type == FveAppliance.TYPE_CONSTANT_LOAD and (
                a.is_running_long_enought or force_stop
            ):
                _LOGGER.debug("Stopping constant")
                saved_power = saved_power + a.actual_power
                _LOGGER.debug("%s > STOP", a.name)
                decisions.append(
                    FveApplianceDecision(
                        appliance=a,
                        action="stop",
                        expected_power_ballance=0 - a.actual_power,
                    )
                )

            if a.type == FveAppliance.TYPE_VARIABLE_LOAD:
                _LOGGER.debug("Testing variable load")
                # always minimize variable load
                if (a.actual_power - a.minimal_power) > remaining_neccessary_power:
                    _LOGGER.debug("%s > MINIMAL", a.name)
                    saved_power = saved_power + (a.actual_power - a.minimal_power)
                    decisions.append(
                        FveApplianceDecision(
                            appliance=a,
                            action="minimum",
                            expected_power_ballance=0
                            - (a.actual_power - a.minimal_power),
                        )
                    )
                # or stop in case it runs long enough
                elif a.is_running_long_enought or force_stop:
                    _LOGGER.debug("%s > STOP", a.name)
                    saved_power = saved_power + a.actual_power
                    decisions.append(
                        FveApplianceDecision(
                            appliance=a,
                            action="stop",
                            expected_power_ballance=0 - a.actual_power,
                        )
                    )

        return decisions

    async def update(self, ts: Any = None) -> bool:
        """Run update cycle — read sensors, calculate statistics."""
        # read data from FVE sensors
        for attribute in self.attributes:
            sensor_entity_id = self._config[attribute["input_sensor_key"]]
            state = self._hass.states.get(sensor_entity_id)
            if state is None:
                _LOGGER.debug(
                    "Input sensor missing: %s (%s)",
                    attribute["input_sensor_key"],
                    sensor_entity_id,
                )
                continue
            if state.state in ("unknown", "unavailable"):
                _LOGGER.debug(
                    "Input sensor unavailable: %s (%s) -> %s",
                    attribute["input_sensor_key"],
                    sensor_entity_id,
                    state.state,
                )
                continue
            try:
                numeric_state = float(state.state)
            except (TypeError, ValueError):
                _LOGGER.debug(
                    "Input sensor non-numeric: %s (%s) -> %s",
                    attribute["input_sensor_key"],
                    sensor_entity_id,
                    state.state,
                )
                continue

            _LOGGER.debug(
                "Input sensor value: %s (%s) -> %s",
                attribute["input_sensor_key"],
                sensor_entity_id,
                numeric_state,
            )
            self._update_history(attribute["input_sensor_key"], numeric_state)

        # calculate statistics on FVE variables
        self._calculate_statistics(ts)

        # read forecast solar
        if self._config.get("use_forecast_solar"):
            self._read_and_normalise_sensors(self.forecast_solar_attributes)
        # read openweather
        if self._config.get("use_openweather"):
            self._read_and_normalise_sensors(self.openweather_attributes)

        # calculate
        self._calculate_fve_variables()

        _LOGGER.debug(
            "Energy snapshot: pv=%sW load=%sW grid=%sW batt=%sW soc=%s%% | free[min/mid/max/final]=%s/%s/%s/%sW",
            self._data.get("pv_power_mean"),
            self._data.get("load_power_mean"),
            self._data.get("grid_power_mean"),
            self._data.get("battery_power_mean"),
            self._data.get("battery_soc_mean"),
            self._data.get("fve_free_power_minimal"),
            self._data.get("fve_free_power_middle"),
            self._data.get("fve_free_power_maximal"),
            self._data.get("fve_free_power"),
        )

        for appliance in sorted(
            self._appliances, key=lambda x: x.priority, reverse=True
        ):
            appliance.update()

        if self._config.get("analytics"):
            await self._send_analytics_update()

        self._round_data()

        return True

    def _read_and_normalise_sensors(self, sensor_list: list[dict[str, Any]]) -> None:
        """Read sensors and store normalized values to _data."""
        for attr in sensor_list:
            state = self._hass.states.get(attr["name"])
            if state is not None and state.state != "unavailable":
                self._data[attr["data_key"]] = attr["normalize"](state.state)

    def _calculate_fve_variables(self) -> None:
        """Calculate various derived data."""
        pv_mean = self._data.get(f"{NAME_PV_POWER}_mean", 0)
        load_mean = self._data.get(f"{NAME_LOAD_POWER}_mean", 0)
        grid_mean = self._data.get(f"{NAME_GRID_POWER}_mean", 0)
        battery_mean = self._data.get(f"{NAME_BATTERY_POWER}_mean", 0)
        battery_soc_mean = self._data.get(f"{NAME_BATTERY_SOC}_mean", 0)

        if pv_mean > load_mean:
            # PV producing more than load
            self._data["fve_free_power_minimal"] = 0 - grid_mean

            self._data["fve_free_power_middle"] = battery_mean - grid_mean

            self._data["fve_free_power_maximal"] = battery_mean - grid_mean
            if battery_soc_mean >= self._config.get("fve_battery_soc_min", 20):
                self._data["fve_free_power_maximal"] = self._data[
                    "fve_free_power_maximal"
                ] + self._config.get("fve_battery_max_power_out", 1900)

        else:  # missing energy
            self._data["fve_free_power_minimal"] = 0 - grid_mean
            if battery_soc_mean <= 99.0:
                self._data["fve_free_power_minimal"] = self._data[
                    "fve_free_power_minimal"
                ] - (self._config.get("fve_battery_max_power_in", 1900) - battery_mean)

            self._data["fve_free_power_middle"] = (0 - grid_mean) + battery_mean

            self._data["fve_free_power_maximal"] = 0 - grid_mean

        # calculate final free power according to priority
        free_power = 0.0
        priority = int(self.extra_load_priority)
        if priority == 1:
            free_power = self._data["fve_free_power_minimal"]
        elif priority == 2:
            free_power = (
                self._data["fve_free_power_minimal"]
                + self._data["fve_free_power_middle"]
            ) / 2
        elif priority == 3:
            free_power = self._data["fve_free_power_middle"]
        elif priority == 4:
            free_power = (
                self._data["fve_free_power_maximal"]
                + self._data["fve_free_power_middle"]
            ) / 2
        elif priority == 5:
            free_power = self._data["fve_free_power_maximal"]

        self._data["fve_free_power"] = free_power

        # missing watts in battery
        battery_soc_state = self._hass.states.get(
            self._config["fve_battery_soc_sensor"]
        )
        if battery_soc_state is not None:
            try:
                battery_soc_value = float(battery_soc_state.state)
                self._data["battery_gap"] = (
                    float(self._config["fve_battery_capacity"])
                    * (100.0 - battery_soc_value)
                    / 100.0
                )

                battery_power_mean = self._data.get("battery_power_mean", 0)
                battery_gap = self._data["battery_gap"]

                if battery_soc_value >= 99:
                    self._data["hours_to_full_battery"] = 0.0
                elif battery_power_mean <= 0:
                    self._data["hours_to_full_battery"] = 24.0
                else:
                    self._data["hours_to_full_battery"] = min(
                        battery_gap / battery_power_mean, 24.0
                    )

            except ValueError:
                _LOGGER.warning("Battery calculations failed for ValueError")

        # calculate times
        sun = self._hass.states.get("sun.sun")

        if sun is not None:
            current_time = datetime.now(UTC)
            next_noon = datetime.fromisoformat(sun.attributes["next_noon"])
            next_setting = datetime.fromisoformat(sun.attributes["next_setting"])
            next_rising = datetime.fromisoformat(sun.attributes["next_rising"])

            hours_to_fve_max = self._calculate_hour_diff(current_time, next_noon)
            hours_to_fve_start = self._calculate_hour_diff(current_time, next_rising)
            hours_to_fve_stop = self._calculate_hour_diff(current_time, next_setting)

            # calculate FVE phase
            fve_phase = "unknown"
            if (hours_to_fve_stop <= self.FVE_SUN_SET_OFFSET) or (
                hours_to_fve_start >= 0 - self.FVE_SUN_RISE_OFFSET
            ):
                fve_phase = "night"
            elif (hours_to_fve_stop <= 2 * self.FVE_SUN_SET_OFFSET) or (
                hours_to_fve_start >= 0 - 2 * self.FVE_SUN_RISE_OFFSET
            ):
                fve_phase = "lowsun"
            elif abs(hours_to_fve_max) <= self.FVE_SUN_MAX_OFFSET:
                fve_phase = "maximum"
            elif hours_to_fve_max > self.FVE_SUN_MAX_OFFSET:
                fve_phase = "start"
            elif hours_to_fve_max < 0 - self.FVE_SUN_MAX_OFFSET:
                fve_phase = "finish"

            self._data["fve_phase"] = fve_phase
            self._data["hours_to_fve_max"] = hours_to_fve_max
            self._data["hours_to_fve_start"] = hours_to_fve_start
            self._data["hours_to_fve_stop"] = hours_to_fve_stop

        running_appliances = sorted(
            filter(lambda x: x.is_on, self._appliances),
            key=lambda x: x.priority,
            reverse=True,
        )
        running_appliances_power = sum(
            map(lambda x: x.actual_power, running_appliances)
        )
        running_appliances_names = ",".join(map(lambda x: x.name, running_appliances))

        self._data["running_appliances_power"] = running_appliances_power
        self._data["running_appliances_names"] = running_appliances_names

    def _calculate_hour_diff(
        self, current_time: datetime, some_time: datetime
    ) -> float:
        current_hour = current_time.hour + current_time.minute / 60
        some_hour = some_time.hour + some_time.minute / 60
        return round(some_hour - current_hour, 2)

    def _update_history(self, attr: str, value: float) -> None:
        if value is not None:
            self._history[attr].append(value)
            if len(self._history[attr]) > self.MAX_HISTORY_LEN:
                self._history[attr].pop(0)

    def reset_history(self) -> None:
        for attr in self.attributes:
            self._history[attr["input_sensor_key"]] = []

    def _calculate_statistics(self, ts: Any = None) -> None:
        for attribute in self.attributes:
            history = self._history[attribute["input_sensor_key"]]
            if not history:
                continue
            try:
                output = attribute["output_attribute"]
                if "mean" in attribute["stats"]:
                    self._data[f"{output}_mean"] = stats.mean(history)
                if "stderr" in attribute["stats"]:
                    self._data[f"{output}_stderr"] = (
                        stats.pstdev(history) if len(history) > 1 else 0.0
                    )
                if "min" in attribute["stats"]:
                    self._data[f"{output}_min"] = min(history)
                if "max" in attribute["stats"]:
                    self._data[f"{output}_max"] = max(history)
            except (ValueError, ZeroDivisionError) as err:
                _LOGGER.debug("Error calculating statistics for %s: %s", output, err)

    def is_available(self) -> bool:
        return True

    def get_state(self, attr: str) -> Any:
        return self._data.get(attr, 0.0)

    async def _send_analytics_update(self) -> None:
        url = f"{analytics_url}/fve_update"
        payload = {
            "hass_name": self._hass.config.location_name,
            "hass_location_lat": self._hass.config.latitude,
            "hass_location_lon": self._hass.config.longitude,
            "data": self._data,
        }
        try:
            session = async_get_clientsession(self._hass)
            await session.post(url, json=payload)
        except Exception:
            _LOGGER.error("Error sending analytics update")

    async def _send_analytics_decisions(
        self, decisions: list[FveApplianceDecision]
    ) -> None:
        data = [d.get_data() for d in decisions]
        url = f"{analytics_url}/fve_decisions"
        payload = {
            "hass_name": self._hass.config.location_name,
            "hass_location_lat": self._hass.config.latitude,
            "hass_location_lon": self._hass.config.longitude,
            "data": data,
        }
        try:
            session = async_get_clientsession(self._hass)
            await session.post(url, json=payload)
        except Exception:
            _LOGGER.error("Error sending analytics decisions")

    def _round_data(self) -> None:
        """Round all floats in data to zero precision."""
        for key in self._data:
            val = self._data[key]
            if isinstance(val, float):
                self._data[key] = round(val, 0)


# Backward-compatible alias
FVE_Controler = FveController
