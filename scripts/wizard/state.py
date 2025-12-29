"""
state.py - Wizard state management

Handles saving/loading wizard state and configuration values.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime


class WizardState:
    """Manages wizard configuration state."""

    DEFAULT_STATE_DIR = Path.home() / "printer_data" / "config"
    STATE_FILENAME = ".gschpoozi_state.json"

    def __init__(self, state_dir: Path = None):
        self.state_dir = state_dir or self.DEFAULT_STATE_DIR
        self.state_file = self.state_dir / self.STATE_FILENAME
        self._state: Dict[str, Any] = {}
        self._pin_registry: Dict[str, Dict[str, Any]] = {}  # mcu_name -> {pins: [...], prefix: "..."}
        self._assigned_pins: Dict[str, str] = {}  # pin_name -> mcu_name
        self._load()
        self._rebuild_pin_registry()

    def _load(self) -> None:
        """Load state from disk if exists."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    self._state = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._state = {}
        else:
            self._state = {}

        # Ensure basic structure
        if "wizard" not in self._state:
            self._state["wizard"] = {
                "version": "2.0",
                "created": datetime.now().isoformat(),
                "last_modified": datetime.now().isoformat(),
            }
        if "config" not in self._state:
            self._state["config"] = {}

        # Lightweight migrations / normalizations for older state files.
        # The wizard evolves over time; avoid leaving null/partial values around that
        # later cause generator output to be invalid.
        cfg = self._state.get("config", {})
        if isinstance(cfg, dict):
            # Normalize leds list items (avoid null pin/color_order)
            leds = cfg.get("leds")
            if isinstance(leds, list):
                for led in leds:
                    if not isinstance(led, dict):
                        continue
                    if led.get("pin") is None:
                        led.pop("pin", None)
                    if led.get("color_order") is None:
                        led.pop("color_order", None)

            # Normalize fan additional_fans multi-pin entries (avoid null pins)
            fans = cfg.get("fans")
            if isinstance(fans, dict):
                additional = fans.get("additional_fans")
                if isinstance(additional, list):
                    cleaned = []
                    for fan in additional:
                        if not isinstance(fan, dict):
                            continue
                        # If pins is explicitly null, drop it
                        if fan.get("pins") is None:
                            fan.pop("pins", None)
                        # If this is a multi_pin fan but pins are missing/empty, drop the entry entirely
                        # (it would crash the wizard and fail generator validation anyway).
                        if fan.get("pin_type") == "multi_pin" and not fan.get("pins"):
                            continue
                        cleaned.append(fan)
                    fans["additional_fans"] = cleaned

    def save(self) -> None:
        """Save state to disk."""
        self._state["wizard"]["last_modified"] = datetime.now().isoformat()

        # Ensure directory exists
        self.state_dir.mkdir(parents=True, exist_ok=True)

        with open(self.state_file, 'w') as f:
            json.dump(self._state, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.

        Example: state.get("mcu.main.serial")
        """
        keys = key.split(".")
        value = self._state.get("config", {})

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value using dot notation.

        Example: state.set("mcu.main.serial", "/dev/serial/...")
        """
        keys = key.split(".")
        config = self._state.setdefault("config", {})
        if not isinstance(config, dict):
            # Extremely defensive: if config was corrupted, reset it
            self._state["config"] = {}
            config = self._state["config"]

        # Navigate to parent
        for k in keys[:-1]:
            # If an intermediate key exists but isn't a dict (e.g., a list),
            # overwrite it with a dict so nested assignments don't crash.
            existing = config.get(k)
            if existing is not None and not isinstance(existing, dict):
                config[k] = {}
            config = config.setdefault(k, {})

        # Set value
        config[keys[-1]] = value

        # Rebuild pin registry if MCU configuration changed
        if keys[0] == "mcu" or (len(keys) > 0 and keys[0] in ["mcu"]):
            self._rebuild_pin_registry()

    def delete(self, key: str) -> bool:
        """Delete a configuration value. Returns True if existed."""
        keys = key.split(".")
        config = self._state.get("config", {})
        if not isinstance(config, dict):
            return False

        # Navigate to parent
        for k in keys[:-1]:
            if not isinstance(config, dict) or k not in config:
                return False
            config = config[k]

        # Delete if exists
        if isinstance(config, dict) and keys[-1] in config:
            del config[keys[-1]]
            return True
        return False

    def get_section(self, section: str) -> Dict[str, Any]:
        """Get an entire configuration section."""
        return self._state.get("config", {}).get(section, {})

    def set_section(self, section: str, data: Dict[str, Any]) -> None:
        """Set an entire configuration section."""
        self._state.setdefault("config", {})[section] = data

    def clear(self) -> None:
        """Clear all configuration (keeps wizard metadata)."""
        self._state["config"] = {}
        self._state["wizard"]["last_modified"] = datetime.now().isoformat()

    def get_all(self) -> Dict[str, Any]:
        """Get all configuration data."""
        return self._state.get("config", {})

    def is_section_complete(self, section: str) -> bool:
        """Check if a section has been configured."""
        return section in self._state.get("config", {})

    def get_completion_status(self) -> Dict[str, bool]:
        """Get completion status for all major sections."""
        config = self._state.get("config", {})

        return {
            "mcu": "mcu" in config and "main" in config.get("mcu", {}),
            "printer": "printer" in config,
            "steppers": all(k in config for k in ["stepper_x", "stepper_y", "stepper_z"]),
            "extruder": "extruder" in config,
            "heater_bed": "heater_bed" in config,
            "probe": "probe" in config,
            "fans": "fans" in config,
        }

    def export_for_generator(self) -> Dict[str, Any]:
        """Export state in format suitable for config generator."""
        config = self._state.get("config", {}) or {}
        export = {
            "version": self._state["wizard"]["version"],
            "generated": datetime.now().isoformat(),
            **config,
        }

        # Normalize temperature_sensors for templates:
        # - Wizard UI stores a dict under config.temperature_sensors (built-ins + chamber + additional)
        # - Generator schema expects a LIST called temperature_sensors
        ts = config.get("temperature_sensors")
        if isinstance(ts, dict):
            out: list = []

            if ts.get("mcu_main", {}).get("enabled"):
                out.append({"name": "mcu_temp", "type": "temperature_mcu", "mcu": "mcu"})
            if ts.get("host", {}).get("enabled"):
                out.append({"name": "host_temp", "type": "temperature_host"})
            if ts.get("toolboard", {}).get("enabled"):
                out.append({"name": "toolboard_temp", "type": "temperature_mcu", "mcu": "toolboard"})

            chamber = ts.get("chamber", {}) if isinstance(ts.get("chamber"), dict) else {}
            if chamber.get("enabled"):
                sensor_location = chamber.get("sensor_location", "mainboard")
                if sensor_location == "rpi":
                    sensor_pin = chamber.get("sensor_pin_rpi")
                else:
                    sensor_pin = chamber.get("sensor_port_mainboard")

                if sensor_pin:
                    entry = {
                        "name": "chamber",
                        "type": "temperature_sensor",
                        "sensor_type": chamber.get("sensor_type", "Generic 3950"),
                        "sensor_pin": sensor_pin,
                    }
                    # Optional field; template may ignore it, but safe to include
                    if chamber.get("pullup_resistor"):
                        entry["pullup_resistor"] = chamber.get("pullup_resistor")
                    out.append(entry)

            additional = ts.get("additional", [])
            if isinstance(additional, list):
                out.extend([s for s in additional if isinstance(s, dict)])

            export["temperature_sensors"] = out

        return export

    def _rebuild_pin_registry(self) -> None:
        """Rebuild pin registry from current state."""
        self._pin_registry = {}
        self._assigned_pins = {}
        config = self._state.get("config", {})

        # Load mainboard pins (no prefix)
        mcu_main = config.get("mcu", {}).get("main", {})
        if mcu_main.get("board_type"):
            self._add_mcu_pins("main", mcu_main.get("board_type"), "")

        # Load toolboard pins (toolboard: prefix)
        mcu_toolboard = config.get("mcu", {}).get("toolboard", {})
        if mcu_toolboard.get("enabled") and mcu_toolboard.get("board_type"):
            self._add_mcu_pins("toolboard", mcu_toolboard.get("board_type"), "toolboard:")

        # Load additional MCU pins (with prefix)
        additional_mcus = config.get("mcu", {}).get("additional", [])
        if isinstance(additional_mcus, list):
            for mcu in additional_mcus:
                if isinstance(mcu, dict):
                    mcu_name = mcu.get("name", "")
                    # Try both 'board' and 'board_type' for compatibility
                    board_type = mcu.get("board") or mcu.get("board_type")
                    if mcu_name and board_type:
                        prefix = f"{mcu_name}:"
                        self._add_mcu_pins(mcu_name, board_type, prefix)

    def _add_mcu_pins(self, mcu_name: str, board_type: str, prefix: str) -> None:
        """Add pins from a board template to the registry."""
        try:
            from pathlib import Path
            import json

            # Try to find board template
            repo_root = Path(__file__).parent.parent.parent
            board_file = None

            # Check main boards
            boards_dir = repo_root / "templates" / "boards"
            if (boards_dir / f"{board_type}.json").exists():
                board_file = boards_dir / f"{board_type}.json"
            # Check toolboards
            elif (repo_root / "templates" / "toolboards" / f"{board_type}.json").exists():
                board_file = repo_root / "templates" / "toolboards" / f"{board_type}.json"

            if board_file and board_file.exists():
                with open(board_file, 'r') as f:
                    board_data = json.load(f)

                # Extract all pins from board template
                pins = {}
                for port_type in ["motor_ports", "endstop_ports", "fan_ports", "heater_ports",
                                 "thermistor_ports", "probe_ports", "gpio_ports", "pwm_ports", "spi_ports"]:
                    ports = board_data.get(port_type, {})
                    for port_id, port_info in ports.items():
                        pin = port_info.get("pin", "")
                        if pin:
                            pin_key = f"{prefix}{pin}" if prefix else pin
                            pins[pin_key] = {
                                "pin": pin,
                                "port_id": port_id,
                                "port_type": port_type,
                                "label": port_info.get("label", port_id),
                                "mcu": mcu_name
                            }

                self._pin_registry[mcu_name] = {
                    "pins": pins,
                    "prefix": prefix,
                    "board_type": board_type
                }
        except Exception:
            # Silently fail if board template not found
            pass

    def get_available_pins(self, mcu_name: str = None, port_type: str = None) -> Dict[str, Dict[str, Any]]:
        """Get available pins, optionally filtered by MCU or port type.

        Args:
            mcu_name: Filter by specific MCU (None for all)
            port_type: Filter by port type (None for all)

        Returns:
            Dict of pin_key -> pin_info
        """
        all_pins = {}

        if mcu_name:
            mcu_data = self._pin_registry.get(mcu_name, {})
            pins = mcu_data.get("pins", {})
            if port_type:
                all_pins.update({k: v for k, v in pins.items() if v.get("port_type") == port_type})
            else:
                all_pins.update(pins)
        else:
            for mcu_data in self._pin_registry.values():
                pins = mcu_data.get("pins", {})
                if port_type:
                    all_pins.update({k: v for k, v in pins.items() if v.get("port_type") == port_type})
                else:
                    all_pins.update(pins)

        return all_pins

    def assign_pin(self, pin_key: str, purpose: str) -> bool:
        """Assign a pin for a specific purpose. Returns True if successful, False if conflict.

        Args:
            pin_key: Pin identifier (with prefix if not mainboard)
            purpose: What the pin is used for (e.g., "stepper_x.motor_port")

        Returns:
            True if assigned, False if already assigned
        """
        if pin_key in self._assigned_pins:
            return False

        self._assigned_pins[pin_key] = purpose
        return True

    def release_pin(self, pin_key: str) -> None:
        """Release a pin assignment."""
        self._assigned_pins.pop(pin_key, None)

    def check_pin_conflict(self, pin_key: str) -> Optional[str]:
        """Check if a pin is already assigned. Returns purpose if assigned, None if free."""
        return self._assigned_pins.get(pin_key)

    def get_pin_registry(self) -> Dict[str, Dict[str, Any]]:
        """Get the full pin registry (internal use only)."""
        return self._pin_registry.copy()

    def __repr__(self) -> str:
        return f"WizardState({self.state_file})"


# Global state instance (lazy loaded)
_state: Optional[WizardState] = None


def get_state() -> WizardState:
    """Get the global wizard state instance."""
    global _state
    if _state is None:
        _state = WizardState()
    return _state


def reset_state() -> WizardState:
    """Reset and return a fresh state instance."""
    global _state
    _state = WizardState()
    _state.clear()
    return _state

