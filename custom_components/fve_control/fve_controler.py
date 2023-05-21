import logging

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class FVE_Controler:
    MAX_HISTORY_LEN = 5
    def __init__(self, config, hass:HomeAssistant) -> None:
        self._config = config
        self._hass = hass
        self._history = {
            "fve_pv_power_sensor": []
        }


    def decide(self,ts=None):
        _LOGGER.debug(f"Making decision based on {self._config}")
        self.update(ts)
        return True

    def update(self, ts=None):
        _LOGGER.debug(f"Update based on {self._config}")
        data = self._hass.states.get(self._config["fve_pv_power_sensor"]).state
        self._update_history("fve_pv_power_sensor", int(data))
        _LOGGER.debug(self._history)
        return True

    def _update_history(self,attr, value):
        self._history[attr].append(value)
        if(len(self._history[attr]) > self.MAX_HISTORY_LEN):
            self._history[attr].pop(0)