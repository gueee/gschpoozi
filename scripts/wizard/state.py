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
        self._load()
    
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

