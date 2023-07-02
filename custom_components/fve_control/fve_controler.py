from datetime import datetime
import logging
import numpy as np
import pytz
import requests

from homeassistant.core import HomeAssistant
from .const import *
from .fve_appliance import FVE_Appliance
from .fve_appliance_decision import FVE_appliance_decision

_LOGGER = logging.getLogger(__name__)


class FVE_Controler:
    UPDATE_INTERVAL = 10
    MAX_HISTORY_TIME = 600
    MAX_HISTORY_LEN = int(MAX_HISTORY_TIME / UPDATE_INTERVAL)

    FVE_SUN_RISE_OFFSET = 1
    FVE_SUN_SET_OFFSET = 1
    FVE_SUN_MAX_OFFSET = 2

    extra_load_priority = 2

    _appliances = []

    attributes = [
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

    forecast_solar_attributes = [
        {
            "name": "sensor.energy_next_hour",
            "data_key": "energy_next_hour",
            "normalize": lambda x: float(x) * 1000,
        },
        # "sensor.energy_production_today",
        # "sensor.energy_production_today_remaining"
    ]

    openweather_attributes = [
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

    def __init__(self, config, hass: HomeAssistant, device_info) -> None:
        home = hass.config.as_dict()
        self._hass_instance_id = {}
        if not home is None:
            self._hass_instance_id["name"] = home.get("location_name")
            self._hass_instance_id["latitude"] = home.get("latitude")
            self._hass_instance_id["longitude"] = home.get("longitude")

        # _LOGGER.debug(f"FVE for HA instance: {self._hass_instance_id}")

        self._config = config
        self._hass = hass
        self.device_info = device_info
        self._history = {}
        self._decision_history = {}
        self._next_decision_ts = 0

        self.MAX_HISTORY_TIME = int(self._config.get("history_in_minutes") * 60)
        self.UPDATE_INTERVAL = int(self._config.get("update_interval_sec"))

        self.reset_history()

        if "appliances" in config:
            for appliance_config in config["appliances"]:
                self._appliances.append(FVE_Appliance(hass, self, appliance_config))

        self._data = {}

    def is_ready(self):
        if "fve_pv_power_sensor" in self._history:
            if len(self._history["fve_pv_power_sensor"]) > 0:
                return True

        return False

    def send_analytics(self):
        payload = {"instance-id": "TODO"}

    def decide(self, ts=None):
        now_ts = datetime.now().timestamp()
        if not self.is_ready():
            _LOGGER.debug("Decision not ready")
            return True

        if now_ts < self._next_decision_ts:
            _LOGGER.debug(
                f"Wainting after decision. Remaining [{int(self._next_decision_ts - now_ts)} sec]"
            )
            return True

        free_power = self._data["fve_free_power"]

        decisions = []

        running_appliances = list(
            filter(
                lambda applinace: applinace.is_on,
                sorted(self._appliances, key=lambda x: x.priority),
            )
        )

        running_appliances_not_max = list(
            filter(
                lambda app: app.is_on
                and (not app.is_on_max)
                and app.type == FVE_Appliance.TYPE_VARIABLE_LOAD,
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
            f"Free power: {free_power}, running power: {running_appliances_power}, running appliances: {','.join([x.name for x in running_appliances])}, available: {','.join([x.name for x in available_stoped_appliances])}"
        )

        if free_power + running_appliances_power > self._config["treshold_power"]:
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

        if free_power < 0 - self._config["treshold_power"]:
            force = free_power <= self._config["force_stop_power"]
            decisions = self.stop_appliances(
                abs(free_power), running_appliances, force_stop=force
            )

        if len(decisions) > 0:
            self._send_analytics_decisions(decisions)
            self.reset_history()
            self._next_decision_ts = max(
                map(lambda x: x.expected_maturity_timestamp, decisions)
            )
            for decision in decisions:
                _LOGGER.debug(f"Firing FVE decision: {decision.get_data()}")
                self._hass.bus.fire("fve_control", decision.get_data())

        return True

    def increase_appliances(
        self,
        free_power,
        available_appliances_list,
        running_appliances_power,
        running_appliances_list,
    ):
        """try to start appliances to use free power"""
        alocated_power = 0
        decisions = []

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
                f"Remaining free power for increase: {remaining_free_power} / ({abs(free_power)} + {lower_priority_running_appliances_power}). Testing {a.name} with lower appliances: {','.join([x.name for x in lower_priority_running_appliances_list])}"
            )
            if remaining_free_power < 0:
                break

            if (
                a.type == FVE_Appliance.TYPE_VARIABLE_LOAD
                and a.is_on
                and not a.is_on_max
                and a.step_power < remaining_free_power
            ):
                alocated_power = alocated_power + a.step_power
                _LOGGER.debug(f"{a.name} > INCREASE")
                decisions.append(
                    FVE_appliance_decision(
                        appliance_name=a.name,
                        action="increase",
                        expected_power_ballance=a.step_power,
                        expected_maturity_sec=a.startup_time_minutes * 60,
                    )
                )

            if len(decisions) > 0:
                break

            # vypnu co je navíc
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
        free_power,
        available_appliances_list,
        running_appliances_power,
        running_appliances_list,
    ):
        """try to start appliances to use free power"""
        alocated_power = 0
        decisions = []

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
                f"Remaining free power: {remaining_free_power} / ({abs(free_power)} + {lower_priority_running_appliances_power}). Testing {a.name} with lower appliances: {','.join([x.name for x in lower_priority_running_appliances_list])}"
            )
            if remaining_free_power < 0:
                break

            if (
                a.type == FVE_Appliance.TYPE_CONSTANT_LOAD
                and a.minimal_power < remaining_free_power
            ):
                alocated_power = alocated_power + a.minimal_power
                _LOGGER.debug(f"{a.name} > START")
                decisions.append(
                    FVE_appliance_decision(
                        appliance_name=a.name,
                        action="start",
                        expected_power_ballance=a.minimal_power,
                        expected_maturity_sec=a.startup_time_minutes * 60,
                    )
                )

            elif (
                a.type == FVE_Appliance.TYPE_VARIABLE_LOAD
                and (not a.is_on)
                and a.minimal_power < remaining_free_power
            ):
                alocated_power = alocated_power + a.minimal_power
                _LOGGER.debug(f"{a.name} > START")
                decisions.append(
                    FVE_appliance_decision(
                        appliance_name=a.name,
                        action="start",
                        expected_power_ballance=a.minimal_power,
                        expected_maturity_sec=a.startup_time_minutes * 60,
                    )
                )

            if len(decisions) > 0:
                break

        # vypnu co je navíc
        if alocated_power > free_power:
            stop_decs = self.stop_appliances(
                alocated_power - free_power,
                lower_priority_running_appliances_list,
                False,
            )
            decisions = decisions + stop_decs

        return decisions

    def stop_appliances(self, neccessary_power, appliances_list, force_stop=False):
        """try to find neccesary power by stopping / minimizing power"""
        saved_power = 0
        decisions = []

        for a in appliances_list:
            remaining_neccessary_power = abs(neccessary_power) - saved_power

            _LOGGER.debug(
                f"Remaining neccesary power: {remaining_neccessary_power} / {abs(neccessary_power)}. Testing {a.name}"
            )
            if remaining_neccessary_power < 0:
                break

            # stop if runing long enough
            if a.type == FVE_Appliance.TYPE_CONSTANT_LOAD and (
                a.is_running_long_enought or force_stop
            ):
                _LOGGER.debug("stoping constant")
                saved_power = saved_power + a.actual_power
                _LOGGER.debug(f"{a.name} > STOP")
                decisions.append(
                    FVE_appliance_decision(
                        appliance_name=a.name,
                        action="stop",
                        expected_power_ballance=0 - a.actual_power,
                    )
                )

            if a.type == FVE_Appliance.TYPE_VARIABLE_LOAD:
                _LOGGER.debug("testing variable load")
                # always minimize variable load
                if (a.actual_power - a.minimal_power) > remaining_neccessary_power:
                    _LOGGER.debug(f"{a.name} > MINIMAL")
                    saved_power = saved_power + (a.actual_power - a.minimal_power)
                    decisions.append(
                        FVE_appliance_decision(
                            appliance_name=a.name,
                            action="minimum",
                            expected_power_ballance=0
                            - (a.actual_power - a.minimal_power),
                        )
                    )
                # or stop in case it runs long enough
                elif a.is_running_long_enought or force_stop:
                    _LOGGER.debug(f"{a.name} > STOP")
                    saved_power = saved_power + a.actual_power
                    decisions.append(
                        FVE_appliance_decision(
                            appliance_name=a.name,
                            action="stop",
                            expected_power_ballance=0 - (a.actual_power),
                        )
                    )

        return decisions

    def update(self, ts=None):
        # read data from FVE sensors
        for attribute in self.attributes:
            data = 0.0
            if not (
                self._hass.states.get(self._config[attribute["input_sensor_key"]])
                is None
            ):
                data = self._hass.states.get(
                    self._config[attribute["input_sensor_key"]]
                ).state
                if data != "unknown":
                    self._update_history(attribute["input_sensor_key"], float(data))

        # calculate statistics on FVE variables
        self._calculate_statistics(ts)

        # read forecast solar
        if self._config["use_forecast_solar"]:
            self._read_and_normalise_sensors(self.forecast_solar_attributes)
        # read openweather
        if self._config["use_openweather"]:
            self._read_and_normalise_sensors(self.openweather_attributes)

        # calculate
        self._calculate_fve_variables()

        # _LOGGER.debug(self._data)
        for appliance in sorted(
            self._appliances, key=lambda x: x.priority, reverse=True
        ):
            appliance.update()
            # _LOGGER.debug(appstate)

        if self._config["analytics"]:
            self._send_analytics_update()

        self._round_data()

        return True

    def _read_and_normalise_sensors(self, sensor_list):
        """reads sensors and strore normalized values to _data"""
        for attr in sensor_list:
            state = self._hass.states.get(attr["name"])
            if not state is None and state.state != "unavailable":
                self._data[attr["data_key"]] = attr["normalize"](state.state)

    def _calculate_fve_variables(self):
        """calculate various data"""

        if self._data[f"{NAME_PV_POWER}_mean"] > self._data[f"{NAME_LOAD_POWER}_mean"]:
            # minimal free power. Just 0 - export to grid.
            # todo solve island systems
            self._data["fve_free_power_minimal"] = (
                0 - self._data[f"{NAME_GRID_POWER}_mean"]
            )

            # free power - to stop charging battery battery
            # it is smart to use when sun power is rising
            self._data["fve_free_power_middle"] = (
                self._data[f"{NAME_BATTERY_POWER}_mean"]
                - self._data[f"{NAME_GRID_POWER}_mean"]
            )

            # maximal free power. Combination of -grid export and maximum battery out power
            # this causes to lower battery SOC. Can be very dangerous and take something from the grid
            self._data["fve_free_power_maximal"] = (
                self._data[f"{NAME_BATTERY_POWER}_mean"]
                - self._data[f"{NAME_GRID_POWER}_mean"]
            )
            if self._data[f"{NAME_BATTERY_SOC}_mean"] >= self._config.get(
                "fve_battery_soc_min"
            ):
                self._data["fve_free_power_maximal"] = self._data[
                    "fve_free_power_maximal"
                ] + self._config.get("fve_battery_max_power_out")

        else:  # missing energy
            # grid buy + potential to charge battery
            self._data["fve_free_power_minimal"] = (
                0 - self._data[f"{NAME_GRID_POWER}_mean"]
            )
            if self._data[f"{NAME_BATTERY_SOC}_mean"] <= 99.0:
                self._data["fve_free_power_minimal"] = self._data[
                    "fve_free_power_minimal"
                ] - (
                    self._config.get("fve_battery_max_power_in")
                    - self._data[f"{NAME_BATTERY_POWER}_mean"]
                )

            # grid buy + stop discharge
            self._data["fve_free_power_middle"] = (
                0 - self._data[f"{NAME_GRID_POWER}_mean"]
            ) + self._data[f"{NAME_BATTERY_POWER}_mean"]

            # grid buy
            self._data["fve_free_power_maximal"] = (
                0 - self._data[f"{NAME_GRID_POWER}_mean"]
            )

        # calculate free final free power power according to priority
        free_power = 0
        if int(self.extra_load_priority) == 1:
            free_power = self._data["fve_free_power_minimal"]

        if int(self.extra_load_priority) == 2:
            free_power = (
                self._data["fve_free_power_minimal"]
                + self._data["fve_free_power_middle"]
            ) / 2

        if int(self.extra_load_priority) == 3:
            free_power = self._data["fve_free_power_middle"]

        if int(self.extra_load_priority) == 4:
            free_power = (
                self._data["fve_free_power_maximal"]
                + self._data["fve_free_power_middle"]
            ) / 2

        if int(self.extra_load_priority) == 5:
            free_power = self._data["fve_free_power_maximal"]

        self._data["fve_free_power"] = free_power

        # missing wats in battery
        battery_soc = self._hass.states.get(self._config["fve_battery_soc_sensor"])
        if not battery_soc is None:
            try:
                self._data["battery_gap"] = (
                    float(self._config["fve_battery_capacity"])
                    * (
                        100.0
                        - float(
                            self._hass.states.get(
                                self._config["fve_battery_soc_sensor"]
                            ).state
                        )
                    )
                    / 100.0
                )

                # hours to full battery
                battery_power_mean = self._data["battery_power_mean"]
                battery_gap = self._data["battery_gap"]

                if battery_power_mean >= 99:
                    self._data["hours_to_full_battery"] = 0.0
                elif battery_power_mean <= 0:
                    self._data["hours_to_full_battery"] = 24.0
                else:
                    self._data["hours_to_full_battery"] = (
                        battery_gap / battery_power_mean
                    )
            except ValueError:
                _LOGGER.warning("Battery calculations failed for ValueError")

        # calculate times
        sun = self._hass.states.get("sun.sun")

        if not sun is None:
            gmt = pytz.timezone("GMT")
            current_time = datetime.now(gmt)
            next_noon = datetime.fromisoformat(sun.attributes["next_noon"])
            next_setting = datetime.fromisoformat(sun.attributes["next_setting"])
            next_rising = datetime.fromisoformat(sun.attributes["next_rising"])

            hours_to_fve_max = self._calculate_hour_diff(current_time, next_noon)
            hours_to_fve_start = self._calculate_hour_diff(current_time, next_rising)
            hours_to_fve_stop = self._calculate_hour_diff(current_time, next_setting)

            # calculate FVE state
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

        running_appliances = filter(lambda x: x.is_on, self._appliances)
        running_appliances = sorted(
            running_appliances, key=lambda x: x.priority, reverse=True
        )
        running_appliances_power = sum(
            map(lambda x: x.actual_power, running_appliances)
        )
        running_appliances_names = ",".join(map(lambda x: x.name, running_appliances))

        self._data["running_appliances_power"] = running_appliances_power
        self._data["running_appliances_names"] = running_appliances_names

    def _calculate_hour_diff(self, current_time, some_time):
        current_hour = current_time.hour + current_time.minute / 60
        some_hour = some_time.hour + some_time.minute / 60
        return round(some_hour - current_hour, 2)

    def _update_history(self, attr, value):
        if not value is None:
            self._history[attr].append(value)
            if len(self._history[attr]) > self.MAX_HISTORY_LEN:
                self._history[attr].pop(0)

    def reset_history(self):
        for attr in self.attributes:
            self._history[attr["input_sensor_key"]] = []

    def update_hass_states(self):
        for attr in self._data:
            self._hass.states.set(f"sensor.{attr}", self._data[attr])

    def _calculate_statistics(self, ts=None):
        for attribute in self.attributes:
            try:
                arr = np.array(self._history[attribute["input_sensor_key"]])
                if "mean" in attribute["stats"]:
                    self._data[attribute["output_attribute"] + "_mean"] = arr.mean()
                if "stderr" in attribute["stats"]:
                    self._data[attribute["output_attribute"] + "_stderr"] = arr.std()
                if "min" in attribute["stats"]:
                    self._data[attribute["output_attribute"] + "_min"] = arr.min()
                if "max" in attribute["stats"]:
                    self._data[attribute["output_attribute"] + "_max"] = arr.max()
            except:
                _LOGGER.debug("ERROR in calculating statistics")

    def is_available(self):
        return True

    def get_state(self, attr):
        if attr in self._data:
            return self._data[attr]
        else:
            return 0.0

    def _send_analytics_update(self):
        url = f"{analytics_url}/fve_update"
        payload = {
            "hass_name": self._hass.config.location_name,
            "hass_location_lat": self._hass.config.latitude,
            "hass_location_lon": self._hass.config.longitude,
            "data": self._data,
        }
        headers = {"content-type": "application/json"}

        response = requests.post(url=url, json=payload, headers=headers)

        # _LOGGER.debug(response.status_code)
        # _LOGGER.debug(response.content)

    def _send_analytics_decisions(self, decisions):
        data = []
        for d in decisions:
            data.append(d.get_data())

        url = f"{analytics_url}/fve_decisions"
        payload = {
            "hass_name": self._hass.config.location_name,
            "hass_location_lat": self._hass.config.latitude,
            "hass_location_lon": self._hass.config.longitude,
            "data": data,
        }
        headers = {"content-type": "application/json"}

        response = requests.post(url=url, json=payload, headers=headers)

    def _round_data(self):
        """Round all floats in data object rto zero precision"""
        for key in self._data:
            val = self._data[key]
            if val.__class__.__name__ == "float":
                self._data[key] = round(val, 0)
