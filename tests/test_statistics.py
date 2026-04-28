"""Tests for statistics calculations and free power formulas."""

import statistics as pystats

import pytest


class TestCalculateStatistics:
    """Tests for _calculate_statistics method."""

    def test_mean_calculation(self, make_controller):
        c = make_controller()
        c._history["fve_pv_power_sensor"] = [100.0, 200.0, 300.0]
        c._calculate_statistics()
        assert c._data["pv_power_mean"] == pytest.approx(200.0)

    def test_stderr_uses_population_stdev(self, make_controller):
        c = make_controller()
        values = [100.0, 200.0, 300.0]
        c._history["fve_pv_power_sensor"] = values
        c._calculate_statistics()
        expected_std = pystats.pstdev(values)
        assert c._data["pv_power_stderr"] == pytest.approx(expected_std, rel=1e-5)

    def test_min_max(self, make_controller):
        c = make_controller()
        c._history["fve_pv_power_sensor"] = [100.0, 500.0, 300.0]
        c._calculate_statistics()
        assert c._data["pv_power_min"] == pytest.approx(100.0)
        assert c._data["pv_power_max"] == pytest.approx(500.0)

    def test_empty_history_no_crash(self, make_controller):
        """Empty history should not crash (bare except catches it)."""
        c = make_controller()
        c._history["fve_pv_power_sensor"] = []
        c._calculate_statistics()  # should not raise

    def test_single_value(self, make_controller):
        c = make_controller()
        c._history["fve_pv_power_sensor"] = [42.0]
        c._calculate_statistics()
        assert c._data["pv_power_mean"] == pytest.approx(42.0)
        assert c._data["pv_power_stderr"] == pytest.approx(0.0)

    def test_all_attributes_computed(self, make_controller):
        c = make_controller()
        for attr in c.attributes:
            c._history[attr["input_sensor_key"]] = [1.0, 2.0, 3.0]
        c._calculate_statistics()
        for attr in c.attributes:
            prefix = attr["output_attribute"]
            assert f"{prefix}_mean" in c._data
            assert f"{prefix}_stderr" in c._data
            assert f"{prefix}_min" in c._data
            assert f"{prefix}_max" in c._data


class TestCalculateFveVariables:
    """Tests for free power calculation at each priority level."""

    def _setup_stats(self, controller, pv, grid, load, battery_power, battery_soc):
        """Helper to set up statistics data as if _calculate_statistics ran."""
        controller._data = {
            "pv_power_mean": pv,
            "grid_power_mean": grid,
            "load_power_mean": load,
            "battery_power_mean": battery_power,
            "battery_soc_mean": battery_soc,
        }

    def test_pv_greater_than_load_priority_1(self, make_controller, mock_hass):
        """Priority 1: only grid export counts as free power."""
        c = make_controller()
        # PV=3000, Grid=-500 (exporting 500W), Load=1500, Battery=1000 (charging), SoC=50%
        self._setup_stats(
            c, pv=3000, grid=-500, load=1500, battery_power=1000, battery_soc=50
        )
        mock_hass.set_state("sensor.battery_soc", "50")
        mock_hass.set_state(
            "sun.sun",
            "above_horizon",
            {
                "next_noon": "2025-06-15T12:00:00+00:00",
                "next_setting": "2025-06-15T20:00:00+00:00",
                "next_rising": "2025-06-16T05:00:00+00:00",
            },
        )
        c.extra_load_priority = 1
        c._calculate_fve_variables()

        # minimal = 0 - grid_mean = 0 - (-500) = 500
        assert c._data["fve_free_power_minimal"] == pytest.approx(500.0)
        assert c._data["fve_free_power"] == pytest.approx(500.0)

    def test_pv_greater_than_load_priority_3(self, make_controller, mock_hass):
        """Priority 3: export + battery charge rate."""
        c = make_controller()
        self._setup_stats(
            c, pv=3000, grid=-500, load=1500, battery_power=1000, battery_soc=50
        )
        mock_hass.set_state("sensor.battery_soc", "50")
        mock_hass.set_state(
            "sun.sun",
            "above_horizon",
            {
                "next_noon": "2025-06-15T12:00:00+00:00",
                "next_setting": "2025-06-15T20:00:00+00:00",
                "next_rising": "2025-06-16T05:00:00+00:00",
            },
        )
        c.extra_load_priority = 3
        c._calculate_fve_variables()

        # middle = battery_power_mean - grid_mean = 1000 - (-500) = 1500
        assert c._data["fve_free_power_middle"] == pytest.approx(1500.0)
        assert c._data["fve_free_power"] == pytest.approx(1500.0)

    def test_pv_greater_than_load_priority_5(self, make_controller, mock_hass):
        """Priority 5: export + battery charge + battery discharge capacity."""
        c = make_controller()
        self._setup_stats(
            c, pv=3000, grid=-500, load=1500, battery_power=1000, battery_soc=50
        )
        mock_hass.set_state("sensor.battery_soc", "50")
        mock_hass.set_state(
            "sun.sun",
            "above_horizon",
            {
                "next_noon": "2025-06-15T12:00:00+00:00",
                "next_setting": "2025-06-15T20:00:00+00:00",
                "next_rising": "2025-06-16T05:00:00+00:00",
            },
        )
        c.extra_load_priority = 5
        c._calculate_fve_variables()

        # maximal = battery_power - grid + battery_max_power_out (since SoC >= soc_min)
        # = 1000 - (-500) + 1900 = 3400
        assert c._data["fve_free_power_maximal"] == pytest.approx(3400.0)
        assert c._data["fve_free_power"] == pytest.approx(3400.0)

    def test_pv_greater_load_priority_5_low_soc(self, make_controller, mock_hass):
        """Priority 5 with low SoC: no battery discharge added."""
        c = make_controller()
        self._setup_stats(
            c, pv=2000, grid=-200, load=1500, battery_power=500, battery_soc=15
        )
        mock_hass.set_state("sensor.battery_soc", "15")
        mock_hass.set_state(
            "sun.sun",
            "above_horizon",
            {
                "next_noon": "2025-06-15T12:00:00+00:00",
                "next_setting": "2025-06-15T20:00:00+00:00",
                "next_rising": "2025-06-16T05:00:00+00:00",
            },
        )
        c.extra_load_priority = 5
        c._calculate_fve_variables()

        # maximal = battery_power - grid (no battery_max_power_out since SoC < soc_min 20)
        # = 500 - (-200) = 700
        assert c._data["fve_free_power_maximal"] == pytest.approx(700.0)

    def test_pv_greater_than_load_priority_2(self, make_controller, mock_hass):
        """Priority 2: average of minimal and middle."""
        c = make_controller()
        self._setup_stats(
            c, pv=3000, grid=-500, load=1500, battery_power=1000, battery_soc=50
        )
        mock_hass.set_state("sensor.battery_soc", "50")
        mock_hass.set_state(
            "sun.sun",
            "above_horizon",
            {
                "next_noon": "2025-06-15T12:00:00+00:00",
                "next_setting": "2025-06-15T20:00:00+00:00",
                "next_rising": "2025-06-16T05:00:00+00:00",
            },
        )
        c.extra_load_priority = 2
        c._calculate_fve_variables()

        # (minimal + middle) / 2 = (500 + 1500) / 2 = 1000
        assert c._data["fve_free_power"] == pytest.approx(1000.0)

    def test_pv_less_than_load_priority_1(self, make_controller, mock_hass):
        """Priority 1 with PV < Load: grid buy + potential to charge battery."""
        c = make_controller()
        # PV=500, Grid=800 (buying), Load=1500, Battery=-200 (discharging), SoC=50%
        self._setup_stats(
            c, pv=500, grid=800, load=1500, battery_power=-200, battery_soc=50
        )
        mock_hass.set_state("sensor.battery_soc", "50")
        mock_hass.set_state(
            "sun.sun",
            "above_horizon",
            {
                "next_noon": "2025-06-15T12:00:00+00:00",
                "next_setting": "2025-06-15T20:00:00+00:00",
                "next_rising": "2025-06-16T05:00:00+00:00",
            },
        )
        c.extra_load_priority = 1
        c._calculate_fve_variables()

        # minimal = 0 - grid - (max_power_in - battery_power)
        # = 0 - 800 - (1900 - (-200)) = -800 - 2100 = -2900
        assert c._data["fve_free_power_minimal"] == pytest.approx(-2900.0)
        assert c._data["fve_free_power"] == pytest.approx(-2900.0)

    def test_pv_less_than_load_priority_3(self, make_controller, mock_hass):
        """Priority 3 with PV < Load: grid buy + stop discharge."""
        c = make_controller()
        self._setup_stats(
            c, pv=500, grid=800, load=1500, battery_power=-200, battery_soc=50
        )
        mock_hass.set_state("sensor.battery_soc", "50")
        mock_hass.set_state(
            "sun.sun",
            "above_horizon",
            {
                "next_noon": "2025-06-15T12:00:00+00:00",
                "next_setting": "2025-06-15T20:00:00+00:00",
                "next_rising": "2025-06-16T05:00:00+00:00",
            },
        )
        c.extra_load_priority = 3
        c._calculate_fve_variables()

        # middle = (0 - grid) + battery_power = -800 + (-200) = -1000
        assert c._data["fve_free_power_middle"] == pytest.approx(-1000.0)
        assert c._data["fve_free_power"] == pytest.approx(-1000.0)

    def test_pv_less_than_load_priority_5(self, make_controller, mock_hass):
        """Priority 5 with PV < Load: only grid import."""
        c = make_controller()
        self._setup_stats(
            c, pv=500, grid=800, load=1500, battery_power=-200, battery_soc=50
        )
        mock_hass.set_state("sensor.battery_soc", "50")
        mock_hass.set_state(
            "sun.sun",
            "above_horizon",
            {
                "next_noon": "2025-06-15T12:00:00+00:00",
                "next_setting": "2025-06-15T20:00:00+00:00",
                "next_rising": "2025-06-16T05:00:00+00:00",
            },
        )
        c.extra_load_priority = 5
        c._calculate_fve_variables()

        # maximal = 0 - grid = -800
        assert c._data["fve_free_power_maximal"] == pytest.approx(-800.0)
        assert c._data["fve_free_power"] == pytest.approx(-800.0)


class TestBatteryCalculations:
    """Tests for battery gap and hours-to-full calculations."""

    def _setup_for_battery(self, controller, mock_hass, soc, battery_power_mean):
        controller._data = {
            "pv_power_mean": 3000,
            "grid_power_mean": -500,
            "load_power_mean": 1500,
            "battery_power_mean": battery_power_mean,
            "battery_soc_mean": soc,
        }
        mock_hass.set_state("sensor.battery_soc", str(soc))
        mock_hass.set_state(
            "sun.sun",
            "above_horizon",
            {
                "next_noon": "2025-06-15T12:00:00+00:00",
                "next_setting": "2025-06-15T20:00:00+00:00",
                "next_rising": "2025-06-16T05:00:00+00:00",
            },
        )

    def test_battery_gap_at_50_percent(self, make_controller, mock_hass):
        c = make_controller()
        self._setup_for_battery(c, mock_hass, soc=50, battery_power_mean=1000)
        c._calculate_fve_variables()
        # gap = capacity * (100 - soc) / 100 = 10000 * 50 / 100 = 5000
        assert c._data["battery_gap"] == pytest.approx(5000.0)

    def test_hours_to_full_charging(self, make_controller, mock_hass):
        c = make_controller()
        self._setup_for_battery(c, mock_hass, soc=50, battery_power_mean=1000)
        c._calculate_fve_variables()
        # hours = gap / power = 5000 / 1000 = 5.0
        assert c._data["hours_to_full_battery"] == pytest.approx(5.0)

    def test_hours_to_full_discharging(self, make_controller, mock_hass):
        c = make_controller()
        self._setup_for_battery(c, mock_hass, soc=50, battery_power_mean=-500)
        c._calculate_fve_variables()
        # discharging -> 24 hours (can't estimate)
        assert c._data["hours_to_full_battery"] == pytest.approx(24.0)

    def test_hours_to_full_when_full(self, make_controller, mock_hass):
        c = make_controller()
        self._setup_for_battery(c, mock_hass, soc=99, battery_power_mean=100)
        c._calculate_fve_variables()
        assert c._data["hours_to_full_battery"] == pytest.approx(0.0)
