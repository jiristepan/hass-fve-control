# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Home Assistant custom integration (`fve_control`) that maximizes solar (FVE/photovoltaic) self-consumption by automatically controlling extra appliances (EV chargers, heaters, miners) based on available free power. Fires `EventEntity` events and legacy `fve_control` bus events with start/stop/increase/decrease actions for HA automations.

Version 0.4.0, config flow + YAML import, HACS-compatible, Apache 2.0.

## Commands

```bash
# Install test dependencies
pip install -r requirements.test.txt

# Run all tests with coverage
python3 -m pytest --strict-markers --cov=custom_components

# Run a single test file
python3 -m pytest tests/test_decision_engine.py -v

# Run a single test
python3 -m pytest tests/test_appliance.py::TestApplianceAvailability::test_available_when_sensor_on

# Lint
ruff check custom_components/ tests/

# Format
ruff format custom_components/ tests/

# Pre-commit hooks (ruff, codespell, mypy)
pre-commit run --all-files
```

## Code Style

- **ruff** for linting and formatting (replaces black, flake8, isort, pyupgrade, bandit)
- Line length 88, Python 3.12+ target
- Config in `pyproject.toml`

## Architecture

### Data Flow

```
HA Sensors → DataUpdateCoordinator (10s) → FveController._data → CoordinatorEntity sensors
                                            ↓
                    async_track_time_interval (60s) → FveController.decide()
                                                        ↓
                                            EventEntity + bus.fire("fve_control")
                                                        ↓
                                            User automations respond
```

### Config Entry Lifecycle

- `async_setup()` — handles YAML import to config entry via `config_entries.flow.async_init`
- `async_setup_entry()` — creates `FveController`, wraps in `FveDataUpdateCoordinator`, forwards platform setups, registers services
- `async_unload_entry()` — unloads platforms, removes services

### Key Modules

- **`__init__.py`** — Config entry lifecycle, YAML schema (backward compat), service registration (`set_priority`, `force_decide`, `reset_history`)
- **`config_flow.py`** — `FveControlConfigFlow` (sensor pickers + battery params) + `FveControlOptionsFlow` (intervals, thresholds, analytics)
- **`coordinator.py`** — `FveDataUpdateCoordinator` wraps controller's `update()` cycle
- **`controller.py`** — Core engine. `_calculate_statistics()` (stdlib `statistics`), `_calculate_fve_variables()`, `decide()` → `start_appliances()`/`stop_appliances()`/`increase_appliances()`. Fires events via `EventEntity` + bus
- **`appliance.py`** — `FveAppliance` — tracks on/off state, power, running time, availability. Types: `constant_load`, `wallbox` (variable)
- **`appliance_decision.py`** — `@dataclass FveApplianceDecision` — action, appliance, timestamps, power balance
- **`sensor.py`** — 18 `CoordinatorEntity` sensors via `FveControlSensorDescription` dataclasses
- **`number.py`** — `FveExtraLoadPriority` `CoordinatorEntity` (1-5)
- **`event.py`** — `FveControlEvent` (global) + `FveApplianceEvent` (per-appliance) `EventEntity` instances
- **`diagnostics.py`** — Config entry diagnostics download
- **`services.yaml`** — `set_priority`, `force_decide`, `reset_history`

### Decision Logic (Priority 1-5)

The `extra_load_priority` (1=conservative, 5=aggressive) controls how "free power" is calculated:
- **Priority 1**: Only grid export counts as free (battery charges first)
- **Priority 3**: Export + battery charge rate (may pause battery charging)
- **Priority 5**: Export + battery discharge capacity (will drain battery for loads)
- Priorities 2/4 are averages of adjacent levels

When free_power > threshold: increase variable loads, then start new appliances (highest static_priority first). When free_power < -threshold: stop/reduce appliances (lowest priority first), respecting `minimal_running_minutes` unless `force_stop_power` exceeded.

### Event-Driven Control

The integration does NOT directly control devices. Two mechanisms:
1. **EventEntity** (modern) — per-appliance and global event entities, automatable via HA UI
2. **Bus events** (legacy) — `fve_control` event with `{appliance_name, action}` for backward compatibility

## Key Sensor Conventions

- Grid power: positive = buying from grid, negative = exporting
- Battery power: positive = charging, negative = discharging
- PV power: always positive
- Load power: always positive (household consumption)

## Dependencies

Runtime: `homeassistant`, `voluptuous`, `sun.sun` entity (no external packages)
Test: `pytest`, `pytest-cov`, `pytest-asyncio`, `pytest-homeassistant-custom-component`
