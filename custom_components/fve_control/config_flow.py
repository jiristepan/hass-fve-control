"""Config flow for FVE Control."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    CONF_ANALYTICS,
    CONF_BATTERY_CAPACITY,
    CONF_BATTERY_MAX_POWER_IN,
    CONF_BATTERY_MAX_POWER_OUT,
    CONF_BATTERY_POWER_SENSOR,
    CONF_BATTERY_SOC_MIN,
    CONF_BATTERY_SOC_SENSOR,
    CONF_DECISION_INTERVAL,
    CONF_FORCE_STOP_POWER,
    CONF_GRID_POWER_SENSOR,
    CONF_LOAD_POWER_SENSOR,
    CONF_MAX_HISTORY_MINUTES,
    CONF_PV_POWER_SENSOR,
    CONF_THRESHOLD_POWER,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)


class FveControlConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for FVE Control."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial configuration step."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="FVE Control",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PV_POWER_SENSOR): EntitySelector(
                        EntitySelectorConfig(
                            domain="sensor",
                            device_class=SensorDeviceClass.POWER,
                        )
                    ),
                    vol.Required(CONF_GRID_POWER_SENSOR): EntitySelector(
                        EntitySelectorConfig(
                            domain="sensor",
                            device_class=SensorDeviceClass.POWER,
                        )
                    ),
                    vol.Required(CONF_LOAD_POWER_SENSOR): EntitySelector(
                        EntitySelectorConfig(
                            domain="sensor",
                            device_class=SensorDeviceClass.POWER,
                        )
                    ),
                    vol.Required(CONF_BATTERY_POWER_SENSOR): EntitySelector(
                        EntitySelectorConfig(
                            domain="sensor",
                            device_class=SensorDeviceClass.POWER,
                        )
                    ),
                    vol.Required(CONF_BATTERY_SOC_SENSOR): EntitySelector(
                        EntitySelectorConfig(
                            domain="sensor",
                            device_class=SensorDeviceClass.BATTERY,
                        )
                    ),
                    vol.Required(CONF_BATTERY_CAPACITY): NumberSelector(
                        NumberSelectorConfig(
                            min=100,
                            max=100000,
                            step=100,
                            unit_of_measurement="Wh",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(CONF_BATTERY_SOC_MIN, default=20): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=100,
                            step=1,
                            unit_of_measurement="%",
                        )
                    ),
                    vol.Required(
                        CONF_BATTERY_MAX_POWER_IN, default=1900
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=50000,
                            step=100,
                            unit_of_measurement="W",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_BATTERY_MAX_POWER_OUT, default=1900
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=50000,
                            step=100,
                            unit_of_measurement="W",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle YAML import."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured(updates=import_data)
        return self.async_create_entry(
            title="FVE Control (imported)",
            data=import_data,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow."""
        return FveControlOptionsFlow(config_entry)


class FveControlOptionsFlow(OptionsFlow):
    """Options flow for runtime settings."""

    def __init__(self, config_entry) -> None:
        """Initialize options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_UPDATE_INTERVAL,
                        default=current.get(CONF_UPDATE_INTERVAL, 10),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=5,
                            max=120,
                            step=5,
                            unit_of_measurement="s",
                        )
                    ),
                    vol.Optional(
                        CONF_DECISION_INTERVAL,
                        default=current.get(CONF_DECISION_INTERVAL, 60),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=10,
                            max=600,
                            step=10,
                            unit_of_measurement="s",
                        )
                    ),
                    vol.Optional(
                        CONF_MAX_HISTORY_MINUTES,
                        default=current.get(CONF_MAX_HISTORY_MINUTES, 10),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1,
                            max=60,
                            step=1,
                            unit_of_measurement="min",
                        )
                    ),
                    vol.Optional(
                        CONF_THRESHOLD_POWER,
                        default=current.get(CONF_THRESHOLD_POWER, 100),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=10,
                            max=1000,
                            step=10,
                            unit_of_measurement="W",
                        )
                    ),
                    vol.Optional(
                        CONF_FORCE_STOP_POWER,
                        default=current.get(CONF_FORCE_STOP_POWER, 1000),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=100,
                            max=10000,
                            step=100,
                            unit_of_measurement="W",
                        )
                    ),
                    vol.Optional(
                        CONF_ANALYTICS,
                        default=current.get(CONF_ANALYTICS, True),
                    ): BooleanSelector(),
                }
            ),
        )
