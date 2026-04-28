"""Data class representing an FVE controlled appliance decision."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from time import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .appliance import FveAppliance

ACTION_START = "start"
ACTION_STOP = "stop"
ACTION_INCREASE = "increase"
ACTION_DECREASE = "decrease"
ACTION_MAXIMUM = "maximum"
ACTION_MINIMUM = "minimum"


@dataclass
class FveApplianceDecision:
    """A single control decision for an appliance."""

    appliance: FveAppliance
    action: str
    expected_power_ballance: float = 0.0
    actual_free_power: float | None = None
    expected_maturity_sec: float = 60.0
    timestamp: float = field(default_factory=time)
    expected_maturity_timestamp: float = field(init=False)
    appliance_name: str = field(init=False)

    def __post_init__(self) -> None:
        self.expected_maturity_timestamp = (
            datetime.now().timestamp() + self.expected_maturity_sec
        )
        self.appliance_name = self.appliance.name

    def get_data(self) -> dict[str, str]:
        return {"appliance_name": self.appliance_name, "action": self.action}


# Backward-compatible aliases
FVE_appliance_decision = FveApplianceDecision
