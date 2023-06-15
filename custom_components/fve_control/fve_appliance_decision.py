from time import time
from datetime import datetime


class FVE_appliance_decision:
    """
    Simple class representing FVE controled appliance decision
    Mandatory:
     - action: on, off, increase, decrease, maximum, minimum
     - appliance_name
    """

    timestamp = None
    action = ""
    appliance_name = ""
    expected_power_change = None
    expected_final_load_power = None
    expected_maturity_timestamp = None
    actual_free_power = None

    ACTION_START = "start"
    ACTION_STOP = "stop"
    ACTION_INCREASE = "increase"
    ACTION_INCREASE = "decrease"
    ACTION_MAXIMUM = "maximum"
    ACTION_MINIMUM = "minimum"

    def __init__(
        self,
        appliance_name,
        action,
        expected_power_ballance=None,
        actual_free_power=None,
        expected_maturity_sec=60,
    ) -> None:
        self.timestamp = time()
        self.action = action
        self.appliance_name = appliance_name
        self.expected_power_ballance = expected_power_ballance
        self.expected_maturity_timestamp = (
            datetime.now().timestamp() + expected_maturity_sec
        )

    def get_data(self):
        out = {"appliance_name": self.appliance_name, "action": self.action}
        return out
