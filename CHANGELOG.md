# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `controller.py`: action-specific bus event `fve_control_<action>` (e.g. `fve_control_start`, `fve_control_stop`).
- `controller.py`: action + appliance bus event `fve_control_<action>_<appliance_name>` (e.g. `fve_control_start_miner1`) for narrow automation triggers.
- `controller.py`: richer debug logging — input sensor read status (missing / unavailable / non-numeric / accepted), computed power snapshot and free-power bands, decision thresholds, and "no decision" reason context.
- `appliance.py`: `_last_decision_timestamp` now updated on every start/stop decision and exposed in appliance state.
- `appliance.py`: recovery logic — if assumed state is `on` but switch / power feedback stays off past the startup timeout, the assumed state is released back to `off` so a start can be retried.

### Changed
- `config_flow.py`: YAML import for an existing config entry now refreshes stored sensor / entity IDs via `_abort_if_unique_id_configured(updates=import_data)` instead of hard-aborting. Edits in `configuration.yaml` propagate to the imported entry.
- `sensor.py`: `battery_soc_mean` device class corrected from `energy_storage` to `battery` (unit `%`), silencing the Home Assistant metadata warning.
- `README.md`: documented the new action-specific and per-appliance bus events alongside the legacy `fve_control` event.

### Fixed
- `sensor.py`: removed invalid `state_class=measurement` from the `battery_gap` energy sensor.
- Start retries: appliances that fail to acknowledge a start (no switch / power feedback) are no longer stuck in assumed `on` state and will be retried on the next decision cycle.

### Notes
- No schema or API-breaking changes. The legacy `fve_control` bus event and existing event payloads are preserved.
- Source detail: `custom_components/fve_control/documentation/changes.md` (session dated 2026-04-28).

## [0.4.0]

- Config flow + YAML import, HACS-compatible release. See git history for prior changes.
