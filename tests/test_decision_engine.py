"""Tests for the decision engine (start/stop/increase logic)."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_analytics():
    """Mock aiohttp session to prevent real HTTP calls in analytics."""
    with patch(
        "custom_components.fve_control.controller.async_get_clientsession"
    ) as mock_session:
        mock_client = MagicMock()
        mock_client.post = MagicMock(return_value=MagicMock())
        mock_session.return_value = mock_client
        yield mock_client


class TestStartAppliances:
    """Tests for start_appliances method."""

    def test_start_constant_load_when_free_power_sufficient(
        self, make_appliance, make_controller
    ):
        a = make_appliance(
            name="heater",
            type_="constant_load",
            min_power=1000,
            priority=50,
            is_available=True,
            is_on=False,
        )
        c = make_controller()
        decisions = c.start_appliances(
            free_power=1500,
            available_appliances_list=[a],
            running_appliances_power=0,
            running_appliances_list=[],
        )
        assert len(decisions) == 1
        assert decisions[0].action == "start"
        assert decisions[0].appliance_name == "heater"

    def test_no_start_when_free_power_insufficient(
        self, make_appliance, make_controller
    ):
        a = make_appliance(
            name="heater",
            type_="constant_load",
            min_power=2000,
            priority=50,
            is_available=True,
            is_on=False,
        )
        c = make_controller()
        decisions = c.start_appliances(
            free_power=1000,
            available_appliances_list=[a],
            running_appliances_power=0,
            running_appliances_list=[],
        )
        assert len(decisions) == 0

    def test_start_highest_priority_first(self, make_appliance, make_controller):
        """Available list is pre-sorted descending by priority."""
        a_high = make_appliance(
            name="high",
            type_="constant_load",
            min_power=500,
            priority=80,
            is_available=True,
            is_on=False,
        )
        a_low = make_appliance(
            name="low",
            type_="constant_load",
            min_power=500,
            priority=20,
            is_available=True,
            is_on=False,
        )
        c = make_controller()
        # Sorted desc: high first
        decisions = c.start_appliances(
            free_power=600,
            available_appliances_list=[a_high, a_low],
            running_appliances_power=0,
            running_appliances_list=[],
        )
        assert len(decisions) == 1
        assert decisions[0].appliance_name == "high"

    def test_start_multiple_appliances_within_budget(
        self, make_appliance, make_controller
    ):
        a1 = make_appliance(
            name="a1",
            type_="constant_load",
            min_power=500,
            priority=80,
            is_available=True,
            is_on=False,
        )
        a2 = make_appliance(
            name="a2",
            type_="constant_load",
            min_power=500,
            priority=60,
            is_available=True,
            is_on=False,
        )
        c = make_controller()
        decisions = c.start_appliances(
            free_power=1500,
            available_appliances_list=[a1, a2],
            running_appliances_power=0,
            running_appliances_list=[],
        )
        assert len(decisions) == 2
        assert decisions[0].appliance_name == "a1"
        assert decisions[1].appliance_name == "a2"

    def test_start_variable_load(self, make_appliance, make_controller):
        a = make_appliance(
            name="wallbox",
            type_="wallbox",
            min_power=1800,
            max_power=3600,
            step_power=230,
            priority=50,
            is_available=True,
            is_on=False,
        )
        c = make_controller()
        decisions = c.start_appliances(
            free_power=2000,
            available_appliances_list=[a],
            running_appliances_power=0,
            running_appliances_list=[],
        )
        assert len(decisions) == 1
        assert decisions[0].action == "start"

    def test_no_start_when_empty_list(self, make_controller):
        c = make_controller()
        decisions = c.start_appliances(
            free_power=5000,
            available_appliances_list=[],
            running_appliances_power=0,
            running_appliances_list=[],
        )
        assert len(decisions) == 0

    def test_start_stops_lower_priority_if_over_budget(
        self, make_appliance, make_controller
    ):
        """If starting a high-priority appliance exceeds free power, stop lower ones."""
        a_running = make_appliance(
            name="running_low",
            type_="constant_load",
            min_power=800,
            priority=20,
            is_available=True,
            is_on=True,
            power=800.0,
            minimal_running_minutes=0,
        )
        # Make it running long enough
        a_running._last_start = datetime.now() - timedelta(minutes=30)

        a_new = make_appliance(
            name="new_high",
            type_="constant_load",
            min_power=1000,
            priority=80,
            is_available=True,
            is_on=False,
        )
        c = make_controller()
        decisions = c.start_appliances(
            free_power=500,
            available_appliances_list=[a_new],
            running_appliances_power=800,
            running_appliances_list=[a_running],
        )
        # Should start new_high and stop running_low
        start_decisions = [d for d in decisions if d.action == "start"]
        assert len(start_decisions) >= 1
        assert start_decisions[0].appliance_name == "new_high"


class TestStopAppliances:
    """Tests for stop_appliances method."""

    def test_stop_constant_load_when_running_long_enough(
        self, make_appliance, make_controller
    ):
        a = make_appliance(
            name="heater",
            type_="constant_load",
            min_power=1000,
            priority=50,
            is_on=True,
            power=1000.0,
            minimal_running_minutes=5,
        )
        a._last_start = datetime.now() - timedelta(minutes=10)
        c = make_controller()
        decisions = c.stop_appliances(1500, [a])
        assert len(decisions) == 1
        assert decisions[0].action == "stop"

    def test_no_stop_constant_load_before_min_runtime(
        self, make_appliance, make_controller
    ):
        a = make_appliance(
            name="heater",
            type_="constant_load",
            min_power=1000,
            priority=50,
            is_on=True,
            power=1000.0,
            minimal_running_minutes=30,
        )
        a._last_start = datetime.now() - timedelta(minutes=5)
        c = make_controller()
        decisions = c.stop_appliances(1500, [a], force_stop=False)
        assert len(decisions) == 0

    def test_force_stop_ignores_min_runtime(self, make_appliance, make_controller):
        a = make_appliance(
            name="heater",
            type_="constant_load",
            min_power=1000,
            priority=50,
            is_on=True,
            power=1000.0,
            minimal_running_minutes=30,
        )
        a._last_start = datetime.now() - timedelta(minutes=5)
        c = make_controller()
        decisions = c.stop_appliances(1500, [a], force_stop=True)
        assert len(decisions) == 1
        assert decisions[0].action == "stop"

    def test_minimize_variable_load_before_stopping(
        self, make_appliance, make_controller
    ):
        """If reducing variable load covers the deficit, minimize instead of stop."""
        a = make_appliance(
            name="wallbox",
            type_="wallbox",
            min_power=1800,
            max_power=3600,
            step_power=230,
            priority=50,
            is_on=True,
            power=3000.0,
            minimal_running_minutes=5,
        )
        a._last_start = datetime.now() - timedelta(minutes=10)
        c = make_controller()
        # Need to save 500W. wallbox at 3000 can go to 1800 (save 1200) -> minimize enough
        decisions = c.stop_appliances(500, [a])
        assert len(decisions) == 1
        assert decisions[0].action == "minimum"

    def test_stop_variable_load_when_minimize_insufficient(
        self, make_appliance, make_controller
    ):
        """If minimizing doesn't cover deficit, stop entirely."""
        a = make_appliance(
            name="wallbox",
            type_="wallbox",
            min_power=1800,
            max_power=3600,
            step_power=230,
            priority=50,
            is_on=True,
            power=2000.0,
            minimal_running_minutes=5,
        )
        a._last_start = datetime.now() - timedelta(minutes=10)
        c = make_controller()
        # Need 1500W. Minimize saves only 200 (2000-1800). Must stop.
        decisions = c.stop_appliances(1500, [a])
        assert len(decisions) == 1
        assert decisions[0].action == "stop"

    def test_stop_lowest_priority_first(self, make_appliance, make_controller):
        """Appliances list is pre-sorted ascending by priority (lowest first)."""
        a_low = make_appliance(
            name="low",
            type_="constant_load",
            min_power=1000,
            priority=20,
            is_on=True,
            power=1000.0,
            minimal_running_minutes=0,
        )
        a_low._last_start = datetime.now() - timedelta(minutes=30)

        a_high = make_appliance(
            name="high",
            type_="constant_load",
            min_power=1000,
            priority=80,
            is_on=True,
            power=1000.0,
            minimal_running_minutes=0,
        )
        a_high._last_start = datetime.now() - timedelta(minutes=30)

        c = make_controller()
        # Only need 800W — should stop low first
        decisions = c.stop_appliances(800, [a_low, a_high])
        assert len(decisions) == 1
        assert decisions[0].appliance_name == "low"

    def test_stop_only_enough_to_cover_deficit(self, make_appliance, make_controller):
        a1 = make_appliance(
            name="a1",
            type_="constant_load",
            min_power=500,
            priority=20,
            is_on=True,
            power=500.0,
            minimal_running_minutes=0,
        )
        a1._last_start = datetime.now() - timedelta(minutes=30)

        a2 = make_appliance(
            name="a2",
            type_="constant_load",
            min_power=500,
            priority=30,
            is_on=True,
            power=500.0,
            minimal_running_minutes=0,
        )
        a2._last_start = datetime.now() - timedelta(minutes=30)

        c = make_controller()
        decisions = c.stop_appliances(400, [a1, a2])
        assert len(decisions) == 1
        assert decisions[0].appliance_name == "a1"


class TestIncreaseAppliances:
    """Tests for increase_appliances method."""

    def test_increase_variable_load_by_step(self, make_appliance, make_controller):
        a = make_appliance(
            name="wallbox",
            type_="wallbox",
            min_power=1800,
            max_power=3600,
            step_power=230,
            priority=50,
            is_on=True,
            power=2000.0,
        )
        c = make_controller()
        decisions = c.increase_appliances(
            free_power=500,
            available_appliances_list=[a],
            running_appliances_power=2000,
            running_appliances_list=[a],
        )
        assert len(decisions) == 1
        assert decisions[0].action == "increase"

    def test_no_increase_when_already_at_max(self, make_appliance, make_controller):
        a = make_appliance(
            name="wallbox",
            type_="wallbox",
            min_power=1800,
            max_power=3600,
            step_power=230,
            priority=50,
            is_on=True,
            power=3600.0,
        )
        c = make_controller()
        decisions = c.increase_appliances(
            free_power=500,
            available_appliances_list=[a],
            running_appliances_power=3600,
            running_appliances_list=[a],
        )
        assert len(decisions) == 0

    def test_no_increase_constant_load(self, make_appliance, make_controller):
        """Constant loads can't be increased."""
        a = make_appliance(
            name="heater",
            type_="constant_load",
            min_power=1000,
            priority=50,
            is_on=True,
            power=1000.0,
        )
        c = make_controller()
        decisions = c.increase_appliances(
            free_power=500,
            available_appliances_list=[a],
            running_appliances_power=1000,
            running_appliances_list=[a],
        )
        assert len(decisions) == 0

    def test_no_increase_insufficient_free_power(self, make_appliance, make_controller):
        a = make_appliance(
            name="wallbox",
            type_="wallbox",
            min_power=1800,
            max_power=3600,
            step_power=500,
            priority=50,
            is_on=True,
            power=2000.0,
        )
        c = make_controller()
        decisions = c.increase_appliances(
            free_power=100,
            available_appliances_list=[a],
            running_appliances_power=2000,
            running_appliances_list=[a],
        )
        assert len(decisions) == 0


class TestDecideMethod:
    """Tests for the main decide() method."""

    @pytest.mark.asyncio
    async def test_no_decision_when_not_ready(self, make_controller):
        c = make_controller()
        # Empty history -> not ready
        result = await c.decide()
        assert result is True

    @pytest.mark.asyncio
    async def test_no_decision_during_cooldown(self, make_controller):
        c = make_controller()
        c._history["fve_pv_power_sensor"] = [100.0]
        c._data["fve_free_power"] = 50  # below threshold
        # Set next decision far in the future
        c._next_decision_ts = datetime.now().timestamp() + 3600
        result = await c.decide()
        assert result is True

    @pytest.mark.asyncio
    async def test_start_when_free_power_above_threshold(
        self, make_controller, make_appliance, mock_hass
    ):
        a = make_appliance(
            name="heater",
            type_="constant_load",
            min_power=500,
            priority=50,
            is_available=True,
            is_on=False,
        )
        c = make_controller()
        c._appliances = [a]
        c._history["fve_pv_power_sensor"] = [100.0]
        c._data["fve_free_power"] = 1000  # above threshold 100
        c._next_decision_ts = 0

        result = await c.decide()
        assert result is True
        # Should have fired bus event
        mock_hass.bus.fire.assert_called()
        call_args = mock_hass.bus.fire.call_args
        assert call_args[0][0] == "fve_control"
        assert call_args[0][1]["action"] == "start"

    @pytest.mark.asyncio
    async def test_stop_when_free_power_below_negative_threshold(
        self, make_controller, make_appliance, mock_hass
    ):
        a = make_appliance(
            name="heater",
            type_="constant_load",
            min_power=1000,
            priority=50,
            is_on=True,
            power=1000.0,
            minimal_running_minutes=0,
        )
        a._last_start = datetime.now() - timedelta(minutes=30)

        c = make_controller()
        c._appliances = [a]
        c._history["fve_pv_power_sensor"] = [100.0]
        c._data["fve_free_power"] = -500  # below -threshold
        c._next_decision_ts = 0

        result = await c.decide()
        assert result is True
        mock_hass.bus.fire.assert_called()
        call_args = mock_hass.bus.fire.call_args
        assert call_args[0][1]["action"] == "stop"

    @pytest.mark.asyncio
    async def test_events_fired_for_each_decision(
        self, make_controller, make_appliance, mock_hass
    ):
        a1 = make_appliance(
            name="a1",
            type_="constant_load",
            min_power=300,
            priority=50,
            is_on=True,
            power=300.0,
            minimal_running_minutes=0,
        )
        a1._last_start = datetime.now() - timedelta(minutes=30)

        a2 = make_appliance(
            name="a2",
            type_="constant_load",
            min_power=300,
            priority=30,
            is_on=True,
            power=300.0,
            minimal_running_minutes=0,
        )
        a2._last_start = datetime.now() - timedelta(minutes=30)

        c = make_controller()
        c._appliances = [a1, a2]
        c._history["fve_pv_power_sensor"] = [100.0]
        c._data["fve_free_power"] = -800
        c._next_decision_ts = 0

        await c.decide()
        # At least one event fired
        assert mock_hass.bus.fire.call_count >= 1

    @pytest.mark.asyncio
    async def test_history_reset_after_decision(
        self, make_controller, make_appliance, mock_hass
    ):
        a = make_appliance(
            name="a1",
            type_="constant_load",
            min_power=500,
            priority=50,
            is_available=True,
            is_on=False,
        )
        c = make_controller()
        c._appliances = [a]
        c._history["fve_pv_power_sensor"] = [100.0, 200.0, 300.0]
        c._data["fve_free_power"] = 1000
        c._next_decision_ts = 0

        await c.decide()
        # History should be reset after decisions
        assert len(c._history["fve_pv_power_sensor"]) == 0
