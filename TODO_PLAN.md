# FVE Control Modernization — Implementation Plan

This document is the specification for modernizing `hass-fve-control` to current Home Assistant standards (2025.x). Each phase is self-contained with exact file changes, code patterns, and acceptance criteria.

---

## Known Bugs (fix during Phase 1)

### BUG-1: Duplicate constant in `fve_appliance_decision.py:24-25`

```python
# Current (line 24-25):
ACTION_INCREASE = "increase"
ACTION_INCREASE = "decrease"   # <-- should be ACTION_DECREASE

# Fix:
ACTION_INCREASE = "increase"
ACTION_DECREASE = "decrease"
```

### BUG-2: Class-level mutable `_appliances` list in `fve_controler.py:33`

```python
# Current (line 33):
class FVE_Controler:
    _appliances = []  # shared across ALL instances

# Fix: move to __init__
def __init__(self, ...):
    self._appliances = []
```

All class-level mutable attributes in `FVE_Appliance` (lines 19-35) have the same issue — they are overwritten in `__init__` so not currently triggering bugs, but should be removed from class level.

### BUG-3: Bare `except:` in `fve_controler.py:653`

```python
# Current:
except:
    _LOGGER.debug("ERROR in calculating statistics")

# Fix:
except (ValueError, ZeroDivisionError) as err:
    _LOGGER.debug("Error calculating statistics for %s: %s", attribute["output_attribute"], err)
```

### BUG-4: `force_stop_power` comparison logic in `fve_controler.py:193`

```python
# Current:
force = free_power <= self._config["force_stop_power"]
# When free_power is e.g. -1500 and force_stop_power is 1000 (positive default),
# -1500 <= 1000 is always True. Force stop is ALWAYS triggered.

# Fix: compare magnitudes
force = abs(free_power) >= self._config["force_stop_power"]
```

### BUG-5: `_send_analytics_decisions` missing error handling in `fve_controler.py:698`

```python
# Current (line 698): no try/except, unlike _send_analytics_update
response = requests.post(url=url, json=payload, headers=headers)

# Fix: wrap in same try/except as _send_analytics_update (line 675-678)
```

### BUG-6: `running_appliances_names` uses `ENUM` device class incorrectly in `sensor.py:229`

The `running_appliances_names` sensor uses `SensorDeviceClass.ENUM` but it's a comma-separated string of appliance names, not one of a fixed set of options. It also lacks an `options` list which ENUM requires. Remove the `device_class` for this sensor.

---

## Phase 0: Tooling & CI

**Goal**: Modern dev toolchain. Zero runtime changes.

### 0.1 Create `pyproject.toml`, delete `setup.cfg`

Create `pyproject.toml` with the following sections:

```toml
[project]
name = "hass-fve-control"
version = "0.4.0"
requires-python = ">=3.12"

[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "UP",     # pyupgrade
    "B",      # bugbear
    "SIM",    # simplify
    "S",      # bandit security
    "RUF",    # ruff-specific
]
ignore = ["E501"]

[tool.ruff.lint.isort]
known-first-party = ["custom_components"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--strict-markers --cov=custom_components"

[tool.coverage.run]
source = ["custom_components"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "raise NotImplementedError",
    "if __name__ == '__main__':",
]
show_missing = true

[tool.mypy]
python_version = "3.12"
ignore_missing_imports = true
strict = false
```

Delete `setup.cfg`.

### 0.2 Replace `.pre-commit-config.yaml`

Replace entire file. New hooks:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.6
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/codespell-project/codespell
    rev: v2.3.0
    hooks:
      - id: codespell
        args: [--skip="./.*,*.csv,*.json", --quiet-level=2]
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: check-json
      - id: check-yaml
      - id: trailing-whitespace
      - id: end-of-file-fixer
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies: [homeassistant-stubs]
```

### 0.3 Update `requirements.test.txt`

```
pytest>=8.0
pytest-cov>=5.0
pytest-homeassistant-custom-component>=0.13
pytest-asyncio>=0.23
```

### 0.4 Create `.github/workflows/ci.yml`

```yaml
name: CI
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install ruff
      - run: ruff check .
      - run: ruff format --check .

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.test.txt
      - run: pytest

  hacs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hacs/action@main
```

### 0.5 Fix HACS compliance gaps

**`manifest.json`** — add missing required fields:
```json
{
  "domain": "fve_control",
  "name": "FVE Load Control",
  "version": "0.4.0",
  "documentation": "https://github.com/jiristepan/hass-fve-control",
  "issue_tracker": "https://github.com/jiristepan/hass-fve-control/issues",
  "codeowners": ["@jiristepan"],
  "dependencies": [],
  "requirements": [],
  "config_flow": true,
  "iot_class": "calculated"
}
```

**`hacs.json`** — add minimum HA version:
```json
{
  "name": "FVE Load Control",
  "render_readme": true,
  "homeassistant": "2025.1.0"
}
```

**`brand/`** — create `brand/icon.png` (solar panel icon, at least 256x256px).

### Acceptance Criteria — Phase 0

- [ ] `ruff check .` passes with zero errors
- [ ] `ruff format --check .` passes
- [ ] `pytest` passes (existing test_init.py)
- [ ] `pre-commit run --all-files` passes
- [ ] `setup.cfg` deleted
- [ ] HACS validation action passes

### Files Created
- `pyproject.toml`
- `.github/workflows/ci.yml`
- `brand/icon.png`

### Files Modified
- `.pre-commit-config.yaml` (full rewrite)
- `requirements.test.txt` (version updates)
- `manifest.json` (add missing fields)
- `hacs.json` (add homeassistant field)

### Files Deleted
- `setup.cfg`
- `tests/bandit.yaml` (no longer needed, ruff has bandit rules)

---

## Phase 1: Code Quality

**Goal**: Fix bugs, remove heavy deps, add typing, rename to PEP 8. Preserve all external behavior (same sensors, same events, same config schema).

### 1.1 Replace `numpy` with stdlib

In `fve_controler.py`, replace `_calculate_statistics`:

```python
# Remove:
import numpy as np

# Add:
import statistics as stats

# Replace _calculate_statistics body:
def _calculate_statistics(self, ts=None):
    for attribute in self.attributes:
        history = self._history[attribute["input_sensor_key"]]
        if not history:
            continue
        try:
            output = attribute["output_attribute"]
            if "mean" in attribute["stats"]:
                self._data[f"{output}_mean"] = stats.mean(history)
            if "stderr" in attribute["stats"]:
                self._data[f"{output}_stderr"] = (
                    stats.pstdev(history) if len(history) > 1 else 0.0
                )
            if "min" in attribute["stats"]:
                self._data[f"{output}_min"] = min(history)
            if "max" in attribute["stats"]:
                self._data[f"{output}_max"] = max(history)
        except (ValueError, ZeroDivisionError) as err:
            _LOGGER.debug("Error calculating statistics for %s: %s", output, err)
```

Note: use `stats.pstdev()` (population stdev) not `stats.stdev()` (sample stdev) to match `numpy.std()` default behavior.

### 1.2 Replace `requests` with `aiohttp`

**Step A**: Make `update()` and `decide()` async.

Both are registered via `async_track_time_interval` which accepts async callbacks natively. Change signatures:

```python
async def update(self, ts=None):
    # ... existing sync logic stays sync (hass.states.get is sync-safe) ...
    if self._config["analytics"]:
        await self._send_analytics_update()

async def decide(self, ts=None):
    # ... existing sync logic ...
    if len(decisions) > 0:
        await self._send_analytics_decisions(decisions)
```

**Step B**: Replace requests calls.

```python
# Remove:
import requests

# Add to __init__:
from homeassistant.helpers.aiohttp_client import async_get_clientsession

# Replace _send_analytics_update:
async def _send_analytics_update(self):
    url = f"{analytics_url}/fve_update"
    payload = {
        "hass_name": self._hass.config.location_name,
        "hass_location_lat": self._hass.config.latitude,
        "hass_location_lon": self._hass.config.longitude,
        "data": self._data,
    }
    try:
        session = async_get_clientsession(self._hass)
        await session.post(url, json=payload)
    except Exception:
        _LOGGER.error("Error sending analytics update")

# Same pattern for _send_analytics_decisions
```

Remove `"requests"` from `manifest.json` `requirements` list.

### 1.3 Replace `pytz` with stdlib

```python
# Remove:
import pytz

# In _calculate_fve_variables, replace:
#   gmt = pytz.timezone("GMT")
#   current_time = datetime.now(gmt)
# With:
from datetime import datetime, timezone
current_time = datetime.now(timezone.utc)
```

### 1.4 Rename classes to PEP 8

| Current | New |
|---|---|
| `FVE_Controler` | `FveController` |
| `FVE_Appliance` | `FveAppliance` |
| `FVE_appliance_decision` | `FveApplianceDecision` |
| `General_FVE_Control_Entity` | `FveControlSensor` |
| `FVEExtraLoadPriority` | `FveExtraLoadPriority` |

Rename the files to match:
| Current | New |
|---|---|
| `fve_controler.py` | `controller.py` |
| `fve_appliance.py` | `appliance.py` |
| `fve_appliance_decision.py` | `appliance_decision.py` |

Update all imports across all files.

### 1.5 Convert `FveApplianceDecision` to dataclass

```python
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
    expected_power_balance: float = 0.0
    actual_free_power: float | None = None
    expected_maturity_sec: float = 60.0
    timestamp: float = field(default_factory=time)
    expected_maturity_timestamp: float = field(init=False)

    def __post_init__(self) -> None:
        self.expected_maturity_timestamp = (
            datetime.now().timestamp() + self.expected_maturity_sec
        )
        self.appliance_name = self.appliance.name

    def get_data(self) -> dict[str, str]:
        return {"appliance_name": self.appliance_name, "action": self.action}
```

### 1.6 Add type annotations

Add `from __future__ import annotations` to all files. Annotate key signatures:

**`controller.py`**:
```python
class FveController:
    _appliances: list[FveAppliance]
    _history: dict[str, list[float]]
    _data: dict[str, Any]
    _config: dict[str, Any]
    _hass: HomeAssistant
    extra_load_priority: int
    _next_decision_ts: float

    def __init__(self, config: dict[str, Any], hass: HomeAssistant, device_info: DeviceInfo) -> None: ...
    async def update(self, ts: datetime | None = None) -> bool: ...
    async def decide(self, ts: datetime | None = None) -> bool: ...
    def increase_appliances(self, free_power: float, ...) -> list[FveApplianceDecision]: ...
    def start_appliances(self, free_power: float, ...) -> list[FveApplianceDecision]: ...
    def stop_appliances(self, necessary_power: float, ...) -> list[FveApplianceDecision]: ...
```

**`appliance.py`**:
```python
class FveAppliance:
    name: str
    type: str
    minimal_power: int
    maximal_power: int
    step_power: int
    priority: int

    @property
    def is_available(self) -> bool: ...
    @property
    def is_on(self) -> bool: ...
    @property
    def actual_power(self) -> float: ...
    @property
    def is_running_long_enough(self) -> bool: ...  # fix typo: enought -> enough
    @property
    def is_on_max(self) -> bool: ...
```

### 1.7 Fix `not x is None` patterns

Replace all occurrences with `x is not None`:

```python
# fve_controler.py:89    not home is None        → home is not None
# fve_controler.py:539   not battery_soc is None → battery_soc is not None
# fve_controler.py:577   not sun is None         → sun is not None
# fve_appliance.py:98    not self.availability_sensor is None → self.availability_sensor is not None
# fve_appliance.py:102   (not s is None) → s is not None
# fve_appliance.py:110   not self.actual_power_sensor is None → ...
# fve_appliance.py:113   not state is None → state is not None
# fve_appliance.py:124   not self.actual_switch_sensor is None → ...
# fve_appliance.py:130   not state is None → state is not None
```

### 1.8 Fix `isinstance` check in `_round_data`

```python
# Current (line 704):
if val.__class__.__name__ == "float":

# Fix:
if isinstance(val, float):
```

### Acceptance Criteria — Phase 1

- [ ] All 6 bugs fixed (BUG-1 through BUG-6)
- [ ] `numpy` removed from imports and not installed
- [ ] `requests` removed from imports, `manifest.json` requirements empty
- [ ] `pytz` removed from imports
- [ ] All classes follow PEP 8 naming
- [ ] All files renamed (`controller.py`, `appliance.py`, `appliance_decision.py`)
- [ ] `FveApplianceDecision` is a `@dataclass`
- [ ] `update()` and `decide()` are `async`
- [ ] Type annotations on all public methods
- [ ] `ruff check .` passes
- [ ] Existing test passes
- [ ] Integration loads in HA and produces same sensors/events as before

### Files Modified
- `custom_components/fve_control/fve_controler.py` → renamed to `controller.py` (major rewrite)
- `custom_components/fve_control/fve_appliance.py` → renamed to `appliance.py` (typing, cleanup)
- `custom_components/fve_control/fve_appliance_decision.py` → renamed to `appliance_decision.py` (dataclass)
- `custom_components/fve_control/__init__.py` (import updates)
- `custom_components/fve_control/sensor.py` (import updates, class rename)
- `custom_components/fve_control/number.py` (import updates)
- `custom_components/fve_control/const.py` (no changes expected)
- `custom_components/fve_control/manifest.json` (remove `requests`)

---

## Phase 2: Config Flow & Config Entries

**Goal**: Replace YAML-only configuration with UI-based config flow. Maintain YAML import path for backward compatibility.

### 2.1 Create `const.py` additions

Add config key constants to `const.py`:

```python
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
CONF_THRESHOLD_POWER = "threshold_power"
CONF_FORCE_STOP_POWER = "force_stop_power"
CONF_ANALYTICS = "analytics"
CONF_APPLIANCES = "appliances"

# Analytics
ANALYTICS_URL = "https://europe-west1-fve-control.cloudfunctions.net"

# Platforms
PLATFORMS = [Platform.SENSOR, Platform.NUMBER, Platform.EVENT]
```

### 2.2 Create `config_flow.py`

Two-step config flow + options flow:

```python
"""Config flow for FVE Control."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    BooleanSelector,
)
from homeassistant.components.sensor import SensorDeviceClass

from .const import DOMAIN, CONF_*  # all config constants


class FveControlConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for FVE Control."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: Core FVE sensors and battery config."""
        if user_input is not None:
            # Only allow single instance
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="FVE Control",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
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
                        min=100, max=100000, step=100,
                        unit_of_measurement="Wh",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(CONF_BATTERY_SOC_MIN, default=20): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=100, step=1,
                        unit_of_measurement="%",
                    )
                ),
                vol.Required(CONF_BATTERY_MAX_POWER_IN, default=1900): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=50000, step=100,
                        unit_of_measurement="W",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(CONF_BATTERY_MAX_POWER_OUT, default=1900): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=50000, step=100,
                        unit_of_measurement="W",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }),
        )

    async def async_step_import(
        self, import_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle YAML import."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title="FVE Control (imported)",
            data=import_data,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the options flow."""
        return FveControlOptionsFlow()


class FveControlOptionsFlow(OptionsFlowWithReload):
    """Options flow for runtime settings."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=current.get(CONF_UPDATE_INTERVAL, 10),
                ): NumberSelector(NumberSelectorConfig(min=5, max=120, step=5, unit_of_measurement="s")),
                vol.Optional(
                    CONF_DECISION_INTERVAL,
                    default=current.get(CONF_DECISION_INTERVAL, 60),
                ): NumberSelector(NumberSelectorConfig(min=10, max=600, step=10, unit_of_measurement="s")),
                vol.Optional(
                    CONF_MAX_HISTORY_MINUTES,
                    default=current.get(CONF_MAX_HISTORY_MINUTES, 10),
                ): NumberSelector(NumberSelectorConfig(min=1, max=60, step=1, unit_of_measurement="min")),
                vol.Optional(
                    CONF_THRESHOLD_POWER,
                    default=current.get(CONF_THRESHOLD_POWER, 100),
                ): NumberSelector(NumberSelectorConfig(min=10, max=1000, step=10, unit_of_measurement="W")),
                vol.Optional(
                    CONF_FORCE_STOP_POWER,
                    default=current.get(CONF_FORCE_STOP_POWER, 1000),
                ): NumberSelector(NumberSelectorConfig(min=100, max=10000, step=100, unit_of_measurement="W")),
                vol.Optional(
                    CONF_ANALYTICS,
                    default=current.get(CONF_ANALYTICS, True),
                ): BooleanSelector(),
            }),
        )
```

### 2.3 Create `strings.json`

```json
{
  "config": {
    "step": {
      "user": {
        "title": "FVE Control Setup",
        "description": "Configure your solar (FVE) system sensors and battery parameters.",
        "data": {
          "fve_pv_power_sensor": "PV power sensor",
          "fve_grid_power_sensor": "Grid power sensor (positive = buying, negative = exporting)",
          "fve_load_power_sensor": "House load power sensor",
          "fve_battery_power_sensor": "Battery power sensor (positive = charging, negative = discharging)",
          "fve_battery_soc_sensor": "Battery state of charge sensor",
          "fve_battery_capacity": "Battery capacity",
          "fve_battery_soc_min": "Minimum battery SoC (don't discharge below this)",
          "fve_battery_max_power_in": "Maximum battery charge power",
          "fve_battery_max_power_out": "Maximum battery discharge power"
        }
      }
    },
    "abort": {
      "already_configured": "FVE Control is already configured"
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "FVE Control Options",
        "data": {
          "update_interval_sec": "Sensor update interval",
          "decision_interval_sec": "Decision interval",
          "max_history_in_minutes": "Statistics rolling window",
          "threshold_power": "Minimum power threshold for decisions",
          "force_stop_power": "Force stop power threshold",
          "analytics": "Send anonymous analytics"
        }
      }
    }
  },
  "entity": {
    "sensor": {
      "pv_power_mean": { "name": "PV power mean" },
      "pv_power_stderr": { "name": "PV power stderr" },
      "grid_power_mean": { "name": "Grid power mean" },
      "load_power_mean": { "name": "Load power mean" },
      "battery_power_mean": { "name": "Battery power mean" },
      "battery_soc_mean": { "name": "Battery SoC mean" },
      "free_power": { "name": "Free power for decision" },
      "free_power_minimal": { "name": "Free power minimal" },
      "free_power_maximal": { "name": "Free power maximal" },
      "free_power_middle": { "name": "Free power middle" },
      "battery_gap": { "name": "Energy to full battery" },
      "hours_to_full_battery": { "name": "Hours to full battery" },
      "hours_to_fve_start": { "name": "Hours to sunrise" },
      "hours_to_fve_stop": { "name": "Hours to sunset" },
      "hours_to_fve_max": { "name": "Hours to solar noon" },
      "fve_phase": { "name": "Solar production phase" },
      "running_appliances_names": { "name": "Running appliances" },
      "running_appliances_power": { "name": "Running appliances power" }
    },
    "number": {
      "extra_load_priority": { "name": "Extra load priority" }
    },
    "event": {
      "appliance_decision": { "name": "Appliance decision" }
    }
  }
}
```

Create `translations/en.json` as a copy of `strings.json`.

### 2.4 Rewrite `__init__.py`

Full rewrite. The new structure:

```python
"""FVE Load Control integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, PLATFORMS, CONF_UPDATE_INTERVAL, CONF_DECISION_INTERVAL, CONF_APPLIANCES
from .controller import FveController

_LOGGER = logging.getLogger(__name__)

type FveControlConfigEntry = ConfigEntry[FveController]

# Keep YAML schema for import path only
LOAD_SCHEMA = vol.Schema({...})  # same as current
CONFIG_SCHEMA = vol.Schema({...})  # same as current


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Handle YAML configuration (import to config entry)."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "import"}, data=config[DOMAIN]
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: FveControlConfigEntry) -> bool:
    """Set up FVE Control from a config entry."""
    # Merge entry.data (core config) + entry.options (runtime settings)
    config = {**entry.data, **entry.options}

    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="FVE Control",
        manufacturer="jiristepan",
        model="FVE Load Control",
        sw_version=entry.version,
        entry_type=DeviceEntryType.SERVICE,
    )

    controller = FveController(config, hass, device_info)
    entry.runtime_data = controller

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    update_interval = config.get(CONF_UPDATE_INTERVAL, 10)
    decision_interval = config.get(CONF_DECISION_INTERVAL, 60)

    entry.async_on_unload(
        async_track_time_interval(
            hass, controller.update, timedelta(seconds=update_interval)
        )
    )
    entry.async_on_unload(
        async_track_time_interval(
            hass, controller.decide, timedelta(seconds=decision_interval)
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FveControlConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
```

Key changes from current:
- `async_setup()` only triggers YAML import flow, does NOT create controller
- `async_setup_entry()` creates controller, stores in `entry.runtime_data`
- `async_unload_entry()` enables proper cleanup
- `entry.async_on_unload()` ensures intervals are cancelled on unload
- `async_forward_entry_setups` replaces deprecated `async_load_platform`

### 2.5 Rewrite `sensor.py` platform setup

Change from `async_setup_platform` to `async_setup_entry`:

```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: FveControlConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FVE Control sensors from a config entry."""
    controller = entry.runtime_data
    async_add_entities(
        FveControlSensor(controller, description)
        for description in SENSOR_DESCRIPTIONS
    )
```

The entity class accesses `entry.runtime_data` (the controller) through its stored reference.

### 2.6 Rewrite `number.py` platform setup

Same pattern as sensor.py:

```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: FveControlConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FVE Control numbers from a config entry."""
    controller = entry.runtime_data
    async_add_entities([FveExtraLoadPriority(controller)])
```

### 2.7 Appliance configuration strategy

Appliances remain in YAML for this phase. The config flow stores core sensor/battery config. Appliance configs are passed through the YAML import path in `entry.data["appliances"]`.

For UI-only users (no YAML), appliances can be added later via a Phase 3 enhancement (sub-entries or a service call).

### Acceptance Criteria — Phase 2

- [ ] Config flow works: user can set up integration from UI with sensor pickers
- [ ] Options flow works: user can change intervals/thresholds from UI
- [ ] YAML import works: existing `configuration.yaml` auto-imports on first load
- [ ] Integration loads via config entry
- [ ] Integration unloads cleanly (no leftover intervals)
- [ ] `entry.runtime_data` is typed `FveController`
- [ ] Unique ID prevents duplicate config entries
- [ ] `strings.json` and `translations/en.json` exist and are valid
- [ ] HACS validation passes with `config_flow: true`
- [ ] All existing sensors and number entity still appear

### Files Created
- `custom_components/fve_control/config_flow.py`
- `custom_components/fve_control/strings.json`
- `custom_components/fve_control/translations/en.json`

### Files Modified
- `custom_components/fve_control/__init__.py` (full rewrite)
- `custom_components/fve_control/sensor.py` (platform setup signature)
- `custom_components/fve_control/number.py` (platform setup signature)
- `custom_components/fve_control/const.py` (add config key constants)
- `custom_components/fve_control/manifest.json` (set `config_flow: true`)

---

## Phase 3: Architecture — Coordinator, EventEntity, Services

**Goal**: Adopt `DataUpdateCoordinator` pattern, replace raw bus events with `EventEntity`, add HA services, add diagnostics.

### 3.1 Create `coordinator.py`

```python
"""DataUpdateCoordinator for FVE Control."""
from __future__ import annotations

from datetime import timedelta
from typing import Any
import logging

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
        super().__init__(
            hass,
            _LOGGER,
            name="fve_control",
            update_interval=timedelta(seconds=update_interval),
            always_update=False,
        )
        self.controller = controller

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from controller (runs every update_interval)."""
        try:
            await self.controller.update()
        except Exception as err:
            raise UpdateFailed(f"Error updating FVE data: {err}") from err
        return dict(self.controller.data)
```

**Impact on `__init__.py`**: Replace the manual `async_track_time_interval` for `update` with the coordinator. Keep the decision interval as a separate `async_track_time_interval` because `decide()` has side effects (firing events).

```python
async def async_setup_entry(hass, entry):
    controller = FveController(config, hass, device_info)
    coordinator = FveDataUpdateCoordinator(hass, controller, update_interval)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator  # type changes to FveDataUpdateCoordinator

    # decision cycle stays as interval (has side effects)
    entry.async_on_unload(
        async_track_time_interval(hass, controller.decide, timedelta(seconds=decision_interval))
    )
```

Update the typed config entry:
```python
type FveControlConfigEntry = ConfigEntry[FveDataUpdateCoordinator]
```

### 3.2 Convert sensors to `CoordinatorEntity`

Define `SensorEntityDescription` dataclasses:

```python
from dataclasses import dataclass
from collections.abc import Callable
from typing import Any
from homeassistant.components.sensor import SensorEntityDescription, SensorDeviceClass, SensorStateClass

@dataclass(frozen=True, kw_only=True)
class FveControlSensorDescription(SensorEntityDescription):
    """Describes an FVE Control sensor."""
    value_fn: Callable[[dict[str, Any]], float | str | None]


SENSOR_DESCRIPTIONS: tuple[FveControlSensorDescription, ...] = (
    FveControlSensorDescription(
        key="pv_power_mean",
        translation_key="pv_power_mean",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("pv_power_mean"),
    ),
    FveControlSensorDescription(
        key="pv_power_stderr",
        translation_key="pv_power_stderr",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("pv_power_stderr"),
    ),
    FveControlSensorDescription(
        key="grid_power_mean",
        translation_key="grid_power_mean",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("grid_power_mean"),
    ),
    FveControlSensorDescription(
        key="load_power_mean",
        translation_key="load_power_mean",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("load_power_mean"),
    ),
    FveControlSensorDescription(
        key="battery_power_mean",
        translation_key="battery_power_mean",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("battery_power_mean"),
    ),
    FveControlSensorDescription(
        key="battery_soc_mean",
        translation_key="battery_soc_mean",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("battery_soc_mean"),
    ),
    FveControlSensorDescription(
        key="free_power",
        translation_key="free_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("fve_free_power"),
    ),
    FveControlSensorDescription(
        key="free_power_minimal",
        translation_key="free_power_minimal",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("fve_free_power_minimal"),
    ),
    FveControlSensorDescription(
        key="free_power_maximal",
        translation_key="free_power_maximal",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("fve_free_power_maximal"),
    ),
    FveControlSensorDescription(
        key="free_power_middle",
        translation_key="free_power_middle",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("fve_free_power_middle"),
    ),
    FveControlSensorDescription(
        key="battery_gap",
        translation_key="battery_gap",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("battery_gap"),
    ),
    FveControlSensorDescription(
        key="hours_to_full_battery",
        translation_key="hours_to_full_battery",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("hours_to_full_battery"),
    ),
    FveControlSensorDescription(
        key="hours_to_fve_start",
        translation_key="hours_to_fve_start",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("hours_to_fve_start"),
    ),
    FveControlSensorDescription(
        key="hours_to_fve_stop",
        translation_key="hours_to_fve_stop",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("hours_to_fve_stop"),
    ),
    FveControlSensorDescription(
        key="hours_to_fve_max",
        translation_key="hours_to_fve_max",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("hours_to_fve_max"),
    ),
    FveControlSensorDescription(
        key="fve_phase",
        translation_key="fve_phase",
        device_class=SensorDeviceClass.ENUM,
        options=["night", "start", "maximum", "finish", "lowsun"],
        value_fn=lambda data: data.get("fve_phase"),
    ),
    FveControlSensorDescription(
        key="running_appliances_names",
        translation_key="running_appliances_names",
        value_fn=lambda data: data.get("running_appliances_names"),
    ),
    FveControlSensorDescription(
        key="running_appliances_power",
        translation_key="running_appliances_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("running_appliances_power"),
    ),
)
```

Entity class:

```python
class FveControlSensor(CoordinatorEntity[FveDataUpdateCoordinator], SensorEntity):
    """Sensor entity for FVE Control."""

    entity_description: FveControlSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FveDataUpdateCoordinator,
        description: FveControlSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.controller.device_info

    @property
    def native_value(self) -> float | str | None:
        if self.coordinator.data is None:
            return None
        value = self.entity_description.value_fn(self.coordinator.data)
        return value
```

This eliminates the `async_update` polling on each sensor. The coordinator pushes updates to all entities at once.

### 3.3 Create `event.py` — `EventEntity` platform

Replace raw `hass.bus.fire("fve_control", ...)` with proper `EventEntity`:

```python
"""Event platform for FVE Control."""
from __future__ import annotations

from homeassistant.components.event import EventEntity, EventDeviceClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .appliance_decision import (
    ACTION_START, ACTION_STOP, ACTION_INCREASE,
    ACTION_DECREASE, ACTION_MAXIMUM, ACTION_MINIMUM,
)

EVENT_TYPES = [
    ACTION_START,
    ACTION_STOP,
    ACTION_INCREASE,
    ACTION_DECREASE,
    ACTION_MAXIMUM,
    ACTION_MINIMUM,
]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up FVE Control event entities."""
    coordinator = entry.runtime_data
    controller = coordinator.controller

    # One event entity per appliance
    entities = [
        FveApplianceEvent(coordinator, appliance)
        for appliance in controller.appliances
    ]
    # Also a global event entity for all decisions
    entities.append(FveControlEvent(coordinator))

    async_add_entities(entities)


class FveControlEvent(EventEntity):
    """Event entity for all FVE control decisions."""

    _attr_has_entity_name = True
    _attr_translation_key = "appliance_decision"
    _attr_event_types = EVENT_TYPES

    def __init__(self, coordinator):
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_decision_event"
        self._attr_device_info = coordinator.controller.device_info

    @callback
    def fire_decision(self, action: str, appliance_name: str) -> None:
        """Fire a decision event."""
        self._trigger_event(
            action,
            {"appliance_name": appliance_name},
        )
        self.async_write_ha_state()


class FveApplianceEvent(EventEntity):
    """Event entity for a specific appliance's decisions."""

    _attr_has_entity_name = True
    _attr_event_types = EVENT_TYPES

    def __init__(self, coordinator, appliance):
        self._coordinator = coordinator
        self._appliance = appliance
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{appliance.name}_event"
        )
        self._attr_device_info = coordinator.controller.device_info
        self._attr_name = f"{appliance.name} decision"

    @callback
    def fire_decision(self, action: str) -> None:
        """Fire a decision event for this appliance."""
        self._trigger_event(action, {"appliance_name": self._appliance.name})
        self.async_write_ha_state()
```

**Modify `controller.py`**: Instead of `self._hass.bus.fire(...)`, the controller calls `fire_decision()` on the event entities. The controller needs a reference to the event entities, set after platform setup:

```python
# In controller.py:
class FveController:
    _event_entity: FveControlEvent | None = None
    _appliance_events: dict[str, FveApplianceEvent] = {}

    def set_event_entities(self, global_event, appliance_events):
        self._event_entity = global_event
        self._appliance_events = appliance_events

    # In decide(), replace:
    #   self._hass.bus.fire("fve_control", decision.get_data())
    # With:
    if self._event_entity:
        self._event_entity.fire_decision(decision.action, decision.appliance_name)
    appliance_event = self._appliance_events.get(decision.appliance_name)
    if appliance_event:
        appliance_event.fire_decision(decision.action)

    # ALSO keep bus.fire for backward compatibility during transition:
    self._hass.bus.fire("fve_control", decision.get_data())
```

**Why both per-appliance and global**: The global event entity lets users write a single automation for all decisions (like today). Per-appliance entities enable per-device automations in the UI.

### 3.4 Register HA services

Create `services.yaml`:

```yaml
set_priority:
  name: Set extra load priority
  description: Set the aggressiveness level for extra load decisions (1=conservative, 5=aggressive).
  fields:
    priority:
      name: Priority
      description: Priority level 1-5
      required: true
      selector:
        number:
          min: 1
          max: 5
          step: 1

force_decide:
  name: Force decision
  description: Trigger an immediate decision cycle regardless of the normal interval.

reset_history:
  name: Reset history
  description: Clear the rolling statistics history and start fresh.
```

Register in `__init__.py` `async_setup_entry`:

```python
from homeassistant.core import ServiceCall

async def async_setup_entry(hass, entry):
    # ... existing setup ...

    async def handle_set_priority(call: ServiceCall) -> None:
        controller.extra_load_priority = int(call.data["priority"])

    async def handle_force_decide(call: ServiceCall) -> None:
        await controller.decide()

    async def handle_reset_history(call: ServiceCall) -> None:
        controller.reset_history()

    hass.services.async_register(DOMAIN, "set_priority", handle_set_priority)
    hass.services.async_register(DOMAIN, "force_decide", handle_force_decide)
    hass.services.async_register(DOMAIN, "reset_history", handle_reset_history)
```

Unregister in `async_unload_entry`:
```python
async def async_unload_entry(hass, entry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.services.async_remove(DOMAIN, "set_priority")
        hass.services.async_remove(DOMAIN, "force_decide")
        hass.services.async_remove(DOMAIN, "reset_history")
    return unload_ok
```

### 3.5 Create `diagnostics.py`

```python
"""Diagnostics support for FVE Control."""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import FveControlConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FveControlConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    controller = coordinator.controller

    return {
        "config": {
            k: v for k, v in entry.data.items()
            if k != "appliances"  # don't dump full appliance config
        },
        "options": dict(entry.options),
        "data": coordinator.data or {},
        "appliances": [a.state for a in controller.appliances],
        "history_lengths": {
            k: len(v) for k, v in controller.history.items()
        },
        "extra_load_priority": controller.extra_load_priority,
    }
```

### 3.6 Convert `NumberEntity` to `CoordinatorEntity`

```python
class FveExtraLoadPriority(CoordinatorEntity[FveDataUpdateCoordinator], NumberEntity):
    """Priority control number entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "extra_load_priority"
    _attr_native_max_value = 5
    _attr_native_step = 1
    _attr_native_min_value = 1
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: FveDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_extra_load_priority"
        self._attr_device_info = coordinator.controller.device_info

    @property
    def native_value(self) -> int | None:
        return self.coordinator.controller.extra_load_priority

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.controller.extra_load_priority = int(value)
        self.async_write_ha_state()
```

### 3.7 Expose controller internals as properties

Add clean property access to `FveController` for coordinator/diagnostics:

```python
class FveController:
    @property
    def data(self) -> dict[str, Any]:
        return self._data

    @property
    def history(self) -> dict[str, list[float]]:
        return self._history

    @property
    def appliances(self) -> list[FveAppliance]:
        return self._appliances
```

### Acceptance Criteria — Phase 3

- [ ] `DataUpdateCoordinator` manages the update cycle
- [ ] Sensors are `CoordinatorEntity` subclasses — no individual `async_update` calls
- [ ] `SensorEntityDescription` dataclasses used for all sensors
- [ ] `EventEntity` fires on each decision (per-appliance + global)
- [ ] Legacy `bus.fire("fve_control", ...)` still works (backward compat)
- [ ] Services registered: `set_priority`, `force_decide`, `reset_history`
- [ ] `services.yaml` valid and services appear in HA Developer Tools
- [ ] Diagnostics downloadable from HA UI
- [ ] `NumberEntity` is `CoordinatorEntity`
- [ ] All entities have `has_entity_name = True` and `translation_key`
- [ ] `unique_id` uses `entry.entry_id` prefix (stable across reinstalls)

### Files Created
- `custom_components/fve_control/coordinator.py`
- `custom_components/fve_control/event.py`
- `custom_components/fve_control/diagnostics.py`
- `custom_components/fve_control/services.yaml`

### Files Modified
- `custom_components/fve_control/__init__.py` (coordinator setup, service registration)
- `custom_components/fve_control/sensor.py` (full rewrite: CoordinatorEntity + EntityDescription)
- `custom_components/fve_control/number.py` (CoordinatorEntity)
- `custom_components/fve_control/controller.py` (expose properties, event entity refs, keep bus.fire)
- `custom_components/fve_control/const.py` (add PLATFORMS with Platform.EVENT)

---

## Phase 4: Test Coverage

**Goal**: Comprehensive test suite covering all modules. Decision engine tests should be written before Phase 1 changes and maintained throughout.

### 4.1 Create `tests/conftest.py`

Shared fixtures:

```python
"""Test fixtures for FVE Control."""
import pytest
from unittest.mock import MagicMock, patch
from homeassistant.core import HomeAssistant

from custom_components.fve_control.controller import FveController
from custom_components.fve_control.appliance import FveAppliance


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance with sensor states."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config.location_name = "Test Home"
    hass.config.latitude = 50.0
    hass.config.longitude = 14.0

    states = {}

    def get_state(entity_id):
        if entity_id in states:
            mock_state = MagicMock()
            mock_state.state = states[entity_id]
            mock_state.attributes = {}
            return mock_state
        return None

    hass.states.get = get_state
    hass.states._states = states  # for test setup
    return hass, states


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
        "threshold_power": 100,
        "force_stop_power": 1000,
        "analytics": False,
        "use_forecast_solar": False,
        "use_openweather": False,
    }


@pytest.fixture
def make_appliance(mock_hass):
    """Factory for test appliances."""
    hass, states = mock_hass

    def _make(
        name="test_appliance",
        type_="constant_load",
        min_power=1000,
        max_power=None,
        step_power=None,
        priority=50,
        availability=True,
        is_on=False,
        power=0.0,
        minimal_running_minutes=5,
        startup_time_minutes=1,
    ):
        states[f"binary_sensor.{name}_available"] = "on" if availability else "off"
        states[f"switch.{name}"] = "on" if is_on else "off"
        if power > 0:
            states[f"sensor.{name}_power"] = str(power)

        config = {
            "name": name,
            "type": type_,
            "min_power": min_power,
            "max_power": max_power or min_power,
            "step_power": step_power or 0,
            "availability_sensor": f"binary_sensor.{name}_available",
            "switch_sensor": f"switch.{name}",
            "power_sensor": f"sensor.{name}_power" if power > 0 else None,
            "static_priority": priority,
            "minimal_running_minutes": minimal_running_minutes,
            "startup_time_minutes": startup_time_minutes,
        }
        controller_mock = MagicMock()
        controller_mock.reset_history = MagicMock()
        return FveAppliance(hass, controller_mock, config)

    return _make
```

### 4.2 Create `tests/test_decision_engine.py`

**HIGHEST PRIORITY**. These tests protect the core logic through all refactoring.

```python
"""Tests for the decision engine (start/stop/increase logic)."""


class TestStartAppliances:
    """Tests for start_appliances method."""

    def test_start_constant_load_when_free_power_sufficient(self): ...
    def test_no_start_when_free_power_insufficient(self): ...
    def test_start_highest_priority_first(self): ...
    def test_start_variable_load(self): ...
    def test_no_start_when_unavailable(self): ...
    def test_start_multiple_appliances_within_budget(self): ...
    def test_stop_lower_priority_when_starting_higher(self): ...


class TestStopAppliances:
    """Tests for stop_appliances method."""

    def test_stop_constant_load_when_running_long_enough(self): ...
    def test_no_stop_constant_load_before_min_runtime(self): ...
    def test_force_stop_ignores_min_runtime(self): ...
    def test_minimize_variable_load_before_stopping(self): ...
    def test_stop_variable_load_when_minimize_insufficient(self): ...
    def test_stop_lowest_priority_first(self): ...
    def test_stop_only_enough_to_cover_deficit(self): ...


class TestIncreaseAppliances:
    """Tests for increase_appliances method."""

    def test_increase_variable_load_by_step(self): ...
    def test_no_increase_when_already_at_max(self): ...
    def test_no_increase_constant_load(self): ...
    def test_increase_highest_priority_first(self): ...


class TestDecide:
    """Tests for the main decide() method."""

    def test_no_decision_when_not_ready(self): ...
    def test_no_decision_during_cooldown(self): ...
    def test_start_when_free_power_above_threshold(self): ...
    def test_stop_when_free_power_below_negative_threshold(self): ...
    def test_force_stop_when_exceeding_force_stop_power(self): ...
    def test_events_fired_for_each_decision(self): ...
    def test_history_reset_after_decision(self): ...
    def test_next_decision_ts_set_to_max_maturity(self): ...
```

### 4.3 Create `tests/test_appliance.py`

```python
"""Tests for FveAppliance."""


class TestAppliance:
    def test_is_available_when_sensor_on(self): ...
    def test_not_available_when_sensor_off(self): ...
    def test_not_available_during_cooldown_after_start(self): ...
    def test_is_on_from_switch_sensor(self): ...
    def test_is_on_from_power_when_no_switch(self): ...
    def test_actual_power_from_sensor(self): ...
    def test_actual_power_assumed_when_no_sensor(self): ...
    def test_actual_running_time_minutes(self): ...
    def test_is_running_long_enough(self): ...
    def test_is_on_max_constant_load(self): ...
    def test_is_on_max_variable_load(self): ...
    def test_start_stop_transitions_trigger_history_reset(self): ...
```

### 4.4 Create `tests/test_statistics.py`

```python
"""Tests for statistics calculations and free power formulas."""


class TestCalculateStatistics:
    def test_mean_calculation(self): ...
    def test_stderr_uses_population_stdev(self): ...
    def test_min_max(self): ...
    def test_empty_history_skipped(self): ...
    def test_single_value_stderr_is_zero(self): ...


class TestCalculateFveVariables:
    """Test free power calculation at each priority level."""

    def test_pv_greater_than_load_priority_1(self): ...
    def test_pv_greater_than_load_priority_2(self): ...
    def test_pv_greater_than_load_priority_3(self): ...
    def test_pv_greater_than_load_priority_4(self): ...
    def test_pv_greater_than_load_priority_5(self): ...
    def test_pv_less_than_load_priority_1(self): ...
    def test_pv_less_than_load_priority_3(self): ...
    def test_pv_less_than_load_priority_5(self): ...
    def test_battery_gap_calculation(self): ...
    def test_hours_to_full_battery_charging(self): ...
    def test_hours_to_full_battery_discharging(self): ...
    def test_hours_to_full_battery_full(self): ...
    def test_fve_phase_night(self): ...
    def test_fve_phase_start(self): ...
    def test_fve_phase_maximum(self): ...
    def test_fve_phase_finish(self): ...
    def test_fve_phase_lowsun(self): ...
```

### 4.5 Create `tests/test_config_flow.py` (after Phase 2)

```python
"""Tests for config flow."""


class TestConfigFlow:
    async def test_user_flow_creates_entry(self, hass): ...
    async def test_already_configured_aborts(self, hass): ...
    async def test_import_from_yaml(self, hass): ...


class TestOptionsFlow:
    async def test_options_update(self, hass): ...
    async def test_options_defaults(self, hass): ...
```

### 4.6 Create `tests/test_sensor.py` and `tests/test_number.py` (after Phase 3)

```python
"""Tests for sensor platform."""

class TestSensorSetup:
    async def test_all_sensors_created(self, hass): ...
    async def test_sensor_device_classes(self, hass): ...
    async def test_sensor_values_from_coordinator(self, hass): ...
    async def test_sensor_unavailable_when_coordinator_fails(self, hass): ...
```

### 4.7 Create `tests/test_integration.py` (end-to-end)

```python
"""End-to-end integration test."""

class TestIntegration:
    async def test_full_cycle(self, hass):
        """Setup → set sensor states → update → decide → verify events."""
        ...
```

### Acceptance Criteria — Phase 4

- [ ] `pytest --cov` reports ≥80% coverage on `custom_components/fve_control/`
- [ ] Decision engine tests (4.2) pass before AND after Phase 1 changes
- [ ] Config flow tests pass
- [ ] All sensor descriptions produce expected entities
- [ ] Integration test verifies full update→decide→event cycle

### Files Created
- `tests/conftest.py`
- `tests/test_decision_engine.py`
- `tests/test_appliance.py`
- `tests/test_statistics.py`
- `tests/test_config_flow.py`
- `tests/test_sensor.py`
- `tests/test_number.py`
- `tests/test_integration.py`

### Files Modified
- `tests/test_init.py` (update for config entry setup)

---

## Phase 5: Documentation & HACS Polish

### 5.1 English README

Rewrite `README.md` as bilingual (English primary, Czech section preserved). Structure:

1. What it does (1 paragraph + screenshot)
2. Installation (HACS + manual)
3. Configuration (config flow screenshots + YAML appliance reference)
4. Priority levels explained (table)
5. Automation examples (responding to EventEntity)
6. Sensors reference (table)
7. Services reference
8. Debug logging
9. Czech section (existing content, condensed)

### 5.2 Update `info.md`

Short English HACS description (1-2 paragraphs).

### 5.3 Update `CLAUDE.md`

Reflect the new architecture: coordinator pattern, config flow, EventEntity, services, test commands.

### Acceptance Criteria — Phase 5

- [ ] README has English installation + configuration instructions
- [ ] HACS listing shows correct info
- [ ] CLAUDE.md reflects current architecture

---

## Execution Order

```
Phase 0   Tooling & CI                    (0.5 days)
   │
   ├── Phase 4.1-4.3   Core tests        (2 days, parallel with Phase 0)
   │
Phase 1   Code quality + bug fixes        (1.5 days)
   │
Phase 2   Config flow                     (3 days)
   │
Phase 3   Coordinator + EventEntity       (3 days)
   │
   ├── Phase 4.4-4.7   Remaining tests   (2 days, parallel with Phase 3)
   │
Phase 5   Documentation                   (1 day)
```

**Total**: ~13 days of implementation work.

**Critical rule**: Phase 4.1-4.3 (decision engine tests) MUST be written against the current code BEFORE Phase 1 changes. These tests are the safety net for all subsequent refactoring.

---

## Summary: File Inventory After All Phases

```
custom_components/fve_control/
├── __init__.py              # Config entry lifecycle, services, YAML import
├── config_flow.py           # NEW: ConfigFlow + OptionsFlowWithReload
├── const.py                 # Domain + all config key constants
├── controller.py            # RENAMED from fve_controler.py: core logic
├── appliance.py             # RENAMED from fve_appliance.py: device model
├── appliance_decision.py    # RENAMED from fve_appliance_decision.py: @dataclass
├── coordinator.py           # NEW: DataUpdateCoordinator
├── sensor.py                # CoordinatorEntity + SensorEntityDescription
├── number.py                # CoordinatorEntity NumberEntity
├── event.py                 # NEW: EventEntity platform
├── diagnostics.py           # NEW: diagnostics download
├── services.yaml            # NEW: service definitions
├── manifest.json            # Updated: config_flow true, no requirements
├── strings.json             # NEW: UI translations source
└── translations/
    └── en.json              # NEW: English translations

tests/
├── __init__.py
├── conftest.py              # NEW: shared fixtures
├── test_init.py             # Updated for config entry
├── test_decision_engine.py  # NEW: core logic tests
├── test_appliance.py        # NEW: appliance model tests
├── test_statistics.py       # NEW: calculation tests
├── test_config_flow.py      # NEW: config flow tests
├── test_sensor.py           # NEW: sensor platform tests
├── test_number.py           # NEW: number platform tests
└── test_integration.py      # NEW: end-to-end test

brand/
└── icon.png                 # NEW: integration icon

.github/workflows/
└── ci.yml                   # NEW: CI pipeline

pyproject.toml               # NEW: replaces setup.cfg
```

**Deleted files**: `setup.cfg`, `tests/bandit.yaml`, `fve_controler.py`, `fve_appliance.py`, `fve_appliance_decision.py`
