"""Constants for FVE Control integration."""

from homeassistant.const import Platform

DOMAIN = "fve_control"

# Sensor name prefixes
NAME_PV_POWER = "pv_power"
NAME_LOAD_POWER = "load_power"
NAME_GRID_POWER = "grid_power"
NAME_BATTERY_POWER = "battery_power"
NAME_BATTERY_SOC = "battery_soc"

# Config keys
CONF_PV_POWER_SENSOR = "fve_pv_power_sensor"
CONF_GRID_POWER_SENSOR = "fve_grid_power_sensor"
CONF_LOAD_POWER_SENSOR = "fve_load_power_sensor"
CONF_BATTERY_POWER_SENSOR = "fve_battery_power_sensor"
CONF_BATTERY_SOC_SENSOR = "fve_battery_soc_sensor"
CONF_BATTERY_CAPACITY = "fve_battery_capacity"
CONF_BATTERY_SOC_MIN = "fve_battery_soc_min"
CONF_BATTERY_MAX_POWER_IN = "fve_battery_max_power_in"
CONF_BATTERY_MAX_POWER_OUT = "fve_battery_max_power_out"
CONF_USE_FORECAST_SOLAR = "use_forecast_solar"
CONF_USE_OPENWEATHER = "use_openweather"
CONF_UPDATE_INTERVAL = "update_interval_sec"
CONF_DECISION_INTERVAL = "decision_interval_sec"
CONF_MAX_HISTORY_MINUTES = "max_history_in_minutes"
CONF_THRESHOLD_POWER = "treshold_power"
CONF_FORCE_STOP_POWER = "force_stop_power"
CONF_ANALYTICS = "analytics"
CONF_APPLIANCES = "appliances"

# Analytics
analytics_url = "https://europe-west1-fve-control.cloudfunctions.net"

# Platforms
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.NUMBER, Platform.EVENT]
