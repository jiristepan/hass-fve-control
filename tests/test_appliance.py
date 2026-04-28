"""Tests for FveAppliance."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

from custom_components.fve_control.appliance import FveAppliance


class TestApplianceAvailability:
    """Tests for is_available property."""

    def test_available_when_sensor_on(self, make_appliance):
        a = make_appliance(is_available=True, is_on=False)
        assert a.is_available is True

    def test_not_available_when_sensor_off(self, make_appliance):
        a = make_appliance(is_available=False, is_on=False)
        assert a.is_available is False

    def test_not_available_during_cooldown_after_start(self, make_appliance):
        a = make_appliance(is_available=True, is_on=False, startup_time_minutes=2)
        # Simulate a recent start decision
        a._assumed_state = "on"
        a._last_decision_dt = datetime.now()
        # Should not be available during cooldown (startup_time * 5)
        assert a.is_available is False

    def test_available_after_cooldown(self, make_appliance):
        a = make_appliance(is_available=True, is_on=False, startup_time_minutes=1)
        a._assumed_state = "on"
        # Set decision far in the past
        a._last_decision_dt = datetime.now() - timedelta(minutes=30)
        assert a.is_available is True

    def test_available_when_no_prior_decision(self, make_appliance):
        a = make_appliance(is_available=True)
        assert a._last_decision_dt is None
        assert a.is_available is True


class TestApplianceOnState:
    """Tests for is_on property."""

    def test_is_on_from_switch_sensor(self, make_appliance):
        a = make_appliance(is_on=True)
        assert a.is_on is True

    def test_is_off_from_switch_sensor(self, make_appliance):
        a = make_appliance(is_on=False)
        assert a.is_on is False

    def test_is_on_from_power_when_no_switch(self, mock_hass):
        """When no switch sensor, use power > 1.0 as on indicator."""
        mock_hass.set_state("binary_sensor.test_available", "on")
        mock_hass.set_state("sensor.test_power", "500")

        config = {
            "name": "test",
            "type": "constant_load",
            "min_power": 1000,
            "max_power": 1000,
            "step_power": 0,
            "availability_sensor": "binary_sensor.test_available",
            "switch_sensor": None,
            "power_sensor": "sensor.test_power",
            "static_priority": 50,
            "minimal_running_minutes": 5,
            "startup_time_minutes": 1,
        }
        a = FveAppliance(mock_hass, MagicMock(), config)
        a.update()
        assert a.is_on is True


class TestAppliancePower:
    """Tests for actual_power property."""

    def test_actual_power_from_sensor(self, make_appliance):
        a = make_appliance(is_on=True, power=1500.0)
        assert a.actual_power == 1500.0

    def test_actual_power_assumed_when_no_sensor(self, make_appliance):
        a = make_appliance(is_on=True, min_power=1000, power=None)
        # Power is computed before on/off state in update().
        # After first update, _h_is_on is True. Second update uses it.
        a.update()  # second update: now _h_is_on=True, so _h_power=min_power
        assert a.actual_power == 1000.0

    def test_actual_power_negative_when_off_no_sensor(self, make_appliance):
        a = make_appliance(is_on=False, power=None)
        assert a.actual_power == -1.0


class TestApplianceRunningTime:
    """Tests for running time tracking."""

    def test_running_time_zero_when_off(self, make_appliance):
        a = make_appliance(is_on=False)
        assert a.actual_running_time_minutes == 0

    def test_running_time_zero_when_never_started(self, make_appliance):
        a = make_appliance(is_on=True)
        # _last_start is None initially (unless transition detected)
        a._last_start = None
        assert a.actual_running_time_minutes == 0

    def test_running_time_positive_when_running(self, make_appliance):
        a = make_appliance(is_on=True)
        a._last_start = datetime.now() - timedelta(minutes=10)
        assert a.actual_running_time_minutes >= 9.9

    def test_is_running_long_enough(self, make_appliance):
        a = make_appliance(is_on=True, minimal_running_minutes=5)
        a._last_start = datetime.now() - timedelta(minutes=10)
        assert a.is_running_long_enought is True

    def test_not_running_long_enough(self, make_appliance):
        a = make_appliance(is_on=True, minimal_running_minutes=30)
        a._last_start = datetime.now() - timedelta(minutes=5)
        assert a.is_running_long_enought is False


class TestApplianceMaxPower:
    """Tests for is_on_max property."""

    def test_constant_load_is_on_max_when_on(self, make_appliance):
        a = make_appliance(
            type_=FveAppliance.TYPE_CONSTANT_LOAD, is_on=True, power=1000.0
        )
        assert a.is_on_max is True

    def test_constant_load_is_not_on_max_when_off(self, make_appliance):
        a = make_appliance(type_=FveAppliance.TYPE_CONSTANT_LOAD, is_on=False)
        assert a.is_on_max is False

    def test_variable_load_is_on_max(self, make_appliance):
        a = make_appliance(
            type_=FveAppliance.TYPE_VARIABLE_LOAD,
            is_on=True,
            min_power=1000,
            max_power=3000,
            power=3000.0,
        )
        assert a.is_on_max is True

    def test_variable_load_not_on_max(self, make_appliance):
        a = make_appliance(
            type_=FveAppliance.TYPE_VARIABLE_LOAD,
            is_on=True,
            min_power=1000,
            max_power=3000,
            power=2000.0,
        )
        assert a.is_on_max is False


class TestApplianceTransitions:
    """Tests for on/off transition detection."""

    def test_start_transition_resets_history(self, mock_hass):
        controller_mock = MagicMock()
        mock_hass.set_state("binary_sensor.t_available", "on")
        mock_hass.set_state("switch.t", "off")

        config = {
            "name": "t",
            "type": "constant_load",
            "min_power": 1000,
            "max_power": 1000,
            "step_power": 0,
            "availability_sensor": "binary_sensor.t_available",
            "switch_sensor": "switch.t",
            "power_sensor": None,
            "static_priority": 50,
            "minimal_running_minutes": 5,
            "startup_time_minutes": 1,
        }
        a = FveAppliance(mock_hass, controller_mock, config)
        a.update()  # initial state: off
        assert a.is_on is False

        # Simulate turning on
        mock_hass.set_state("switch.t", "on")
        a.update()
        assert a.is_on is True
        controller_mock.reset_history.assert_called()

    def test_stop_transition_resets_history(self, mock_hass):
        controller_mock = MagicMock()
        mock_hass.set_state("binary_sensor.t_available", "on")
        mock_hass.set_state("switch.t", "on")

        config = {
            "name": "t",
            "type": "constant_load",
            "min_power": 1000,
            "max_power": 1000,
            "step_power": 0,
            "availability_sensor": "binary_sensor.t_available",
            "switch_sensor": "switch.t",
            "power_sensor": None,
            "static_priority": 50,
            "minimal_running_minutes": 5,
            "startup_time_minutes": 1,
        }
        a = FveAppliance(mock_hass, controller_mock, config)
        a.update()  # initial state: on

        # Simulate turning off
        mock_hass.set_state("switch.t", "off")
        a.update()
        assert a.is_on is False
        controller_mock.reset_history.assert_called()
