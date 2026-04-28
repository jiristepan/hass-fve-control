"""DataUpdateCoordinator for FVE Control."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .controller import FveController

_LOGGER = logging.getLogger(__name__)


class FveDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that wraps the FveController update cycle."""

    def __init__(
        self,
        hass: HomeAssistant,
        controller: FveController,
        update_interval: int = 10,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="fve_control",
            update_interval=timedelta(seconds=update_interval),
            always_update=False,
        )
        self.controller = controller

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from controller."""
        try:
            await self.controller.update()
        except Exception as err:
            raise UpdateFailed(f"Error updating FVE data: {err}") from err
        return dict(self.controller.data)
