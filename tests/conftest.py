"""Test fixtures for FVE Control."""

from unittest.mock import MagicMock

import pytest

from custom_components.fve_control.appliance import FveAppliance
from custom_components.fve_control.controller import FveController


class MockState:
    """Mock HA state object."""

    def __init__(self, state, attributes=None):
        self.state = str(state)
        self.attributes = attributes or {}


class MockHass:
    """Minimal mock of HomeAssistant for unit tests."""

    def __init__(self):
        self._states = {}
        self.states = self
        self.config = MagicMock()
        self.config.as_dict.return_value = {
            "location_name": "Test Home",
            "latitude": 50.0,
            "longitude": 14.0,
        }
        self.config.location_name = "Test Home"
        self.config.latitude = 50.0
        self.config.longitude = 14.0
        self.bus = MagicMock()

    def get(self, entity_id):
        return self._states.get(entity_id)

    def set_state(self, entity_id, state, attributes=None):
        self._states[entity_id] = MockState(state, attributes)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    return MockHass()


@pytest.fixture
def base_config():
    """Minimal valid configuration."""
    return {
        "fve_pv_power_sensor": "sensor.pv_power",
        "fve_grid_power_sensor": "sensor.grid_power",
        "fve_load_power_sensor": "sensor.load_power",
        "fve_battery_power_sensor": "sensor.battery_power",
        "fve_battery_soc_sensor": "sensor.battery_soc",
        "fve_battery_capacity": 10000,
        "fve_battery_soc_min": 20,
        "fve_battery_max_power_in": 1900,
        "fve_battery_max_power_out": 1900,
        "update_interval_sec": 10,
        "decision_interval_sec": 60,
        "max_history_in_minutes": 10,
        "treshold_power": 100,
        "force_stop_power": 1000,
        "analytics": False,
        "use_forecast_solar": False,
        "use_openweather": False,
    }


@pytest.fixture
def device_info():
    """Mock device info."""
    return {"identifiers": {("fve_control", "test")}, "name": "FVE Control"}


@pytest.fixture
def make_controller(mock_hass, base_config, device_info):
    """Factory for creating a controller with given appliance configs."""

    def _make(appliance_configs=None, **config_overrides):
        config = {**base_config, **config_overrides}
        if appliance_configs:
            config["appliances"] = appliance_configs
        return FveController(config, mock_hass, device_info)

    return _make


@pytest.fixture
def make_appliance(mock_hass):
    """Factory for creating test appliances with mocked HA states."""

    def _make(
        name="test_appliance",
        type_=FveAppliance.TYPE_CONSTANT_LOAD,
        min_power=1000,
        max_power=None,
        step_power=0,
        priority=50,
        is_available=True,
        is_on=False,
        power=None,
        minimal_running_minutes=5,
        startup_time_minutes=1,
    ):
        mock_hass.set_state(
            f"binary_sensor.{name}_available", "on" if is_available else "off"
        )
        mock_hass.set_state(f"switch.{name}", "on" if is_on else "off")

        if power is not None:
            mock_hass.set_state(f"sensor.{name}_power", str(power))

        config = {
            "name": name,
            "type": type_,
            "min_power": min_power,
            "max_power": max_power if max_power is not None else min_power,
            "step_power": step_power,
            "availability_sensor": f"binary_sensor.{name}_available",
            "switch_sensor": f"switch.{name}",
            "power_sensor": f"sensor.{name}_power" if power is not None else None,
            "static_priority": priority,
            "minimal_running_minutes": minimal_running_minutes,
            "startup_time_minutes": startup_time_minutes,
        }
        controller_mock = MagicMock()
        controller_mock.reset_history = MagicMock()
        appliance = FveAppliance(mock_hass, controller_mock, config)
        appliance.update()
        return appliance

    return _make
