"""
generator.py - Main config generator

Orchestrates loading state, rendering templates, and writing config files.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from wizard.state import WizardState, get_state
from generator.templates import TemplateRenderer


class ConfigGenerator:
    """Generates Klipper configuration files from wizard state."""

    # Output file structure
    OUTPUT_FILES = {
        "printer.cfg": "Main configuration (includes only)",
        "gschpoozi/hardware.cfg": "MCU, steppers, extruder, bed, fans",
        "gschpoozi/probe.cfg": "Probe and homing",
        "gschpoozi/homing.cfg": "Homing (safe_z_home, overrides)",
        "gschpoozi/leveling.cfg": "Bed leveling",
        "gschpoozi/macros.cfg": "G-code macros",
        "gschpoozi/macros-config.cfg": "Macro configuration variables",
        "gschpoozi/calibration.cfg": "Calibration and stepper identification macros",
        "gschpoozi/tuning.cfg": "Tuning and optional features",
    }

    def __init__(
        self,
        state: WizardState = None,
        output_dir: Path = None,
        renderer: TemplateRenderer = None,
        templates_dir: Path = None
    ):
        self.state = state or get_state()
        self.output_dir = output_dir or Path.home() / "printer_data" / "config"
        self.renderer = renderer or TemplateRenderer()
        self.templates_dir = templates_dir or self._find_templates_dir()

        # Section to file mapping
        self.file_mapping = {
            'mcu.main': 'gschpoozi/hardware.cfg',
            'mcu.toolboard': 'gschpoozi/hardware.cfg',
            'mcu.host': 'gschpoozi/hardware.cfg',
            'printer': 'gschpoozi/hardware.cfg',
            'stepper_x': 'gschpoozi/hardware.cfg',
            'tmc_stepper_x': 'gschpoozi/hardware.cfg',
            'stepper_x1': 'gschpoozi/hardware.cfg',
            'tmc_stepper_x1': 'gschpoozi/hardware.cfg',
            'stepper_y': 'gschpoozi/hardware.cfg',
            'tmc_stepper_y': 'gschpoozi/hardware.cfg',
            'stepper_y1': 'gschpoozi/hardware.cfg',
            'tmc_stepper_y1': 'gschpoozi/hardware.cfg',
            'stepper_z': 'gschpoozi/hardware.cfg',
            'tmc_stepper_z': 'gschpoozi/hardware.cfg',
            'extruder': 'gschpoozi/hardware.cfg',
            'tmc_extruder': 'gschpoozi/hardware.cfg',
            'heater_bed': 'gschpoozi/hardware.cfg',
            'fan': 'gschpoozi/hardware.cfg',
            'heater_fan': 'gschpoozi/hardware.cfg',
            'controller_fan': 'gschpoozi/hardware.cfg',
            'multi_pin': 'gschpoozi/hardware.cfg',
            'fan_generic': 'gschpoozi/hardware.cfg',
            'probe': 'gschpoozi/probe.cfg',
            'bltouch': 'gschpoozi/probe.cfg',
            'beacon': 'gschpoozi/probe.cfg',
            'cartographer': 'gschpoozi/probe.cfg',
            'btt_eddy': 'gschpoozi/probe.cfg',
            'safe_z_home': 'gschpoozi/homing.cfg',
            'bed_mesh': 'gschpoozi/leveling.cfg',
            'z_tilt': 'gschpoozi/leveling.cfg',
            'quad_gantry_level': 'gschpoozi/leveling.cfg',
            'temperature_sensor': 'gschpoozi/hardware.cfg',
            'neopixel': 'gschpoozi/hardware.cfg',
            'filament_switch_sensor': 'gschpoozi/hardware.cfg',
            'common.virtual_sdcard': 'gschpoozi/tuning.cfg',
            'common.idle_timeout': 'gschpoozi/tuning.cfg',
            'common.pause_resume': 'gschpoozi/tuning.cfg',
            'common.exclude_object': 'gschpoozi/tuning.cfg',
            'common.tmc_autotune': 'gschpoozi/tuning.cfg',
            'common.input_shaper': 'gschpoozi/tuning.cfg',
            'common.gcode_arcs': 'gschpoozi/tuning.cfg',
            'common.respond': 'gschpoozi/tuning.cfg',
            'common.save_variables': 'gschpoozi/tuning.cfg',
            'common.force_move': 'gschpoozi/tuning.cfg',
            'common.firmware_retraction': 'gschpoozi/tuning.cfg',
            'common.macro_config': 'gschpoozi/macros-config.cfg',
            'common.bed_mesh_macro': 'gschpoozi/macros.cfg',
            'common.calibration': 'gschpoozi/calibration.cfg',
        }

    def _find_templates_dir(self) -> Path:
        """Find the templates directory."""
        module_dir = Path(__file__).parent
        candidates = [
            module_dir.parent.parent / "templates",
            module_dir.parent / "templates",
            Path.home() / "gschpoozi" / "templates",
        ]
        for path in candidates:
            if path.exists():
                return path
        return candidates[0]  # Return first as default

    def get_context(self) -> Dict[str, Any]:
        """Get context for template rendering from wizard state."""
        context = self.state.export_for_generator()

        def _has_klipper_tmc_autotune() -> bool:
            """
            Detect whether the optional klipper_tmc_autotune plugin is installed.

            Typical installs place the module under Klipper extras, e.g.:
              ~/klipper/klippy/extras/autotune_tmc.py
            """
            try:
                klipper_dir = Path.home() / "klipper" / "klippy" / "extras"
                candidates = [
                    klipper_dir / "autotune_tmc.py",
                    klipper_dir / "autotune_tmc.pyc",
                    klipper_dir / "tmc_autotune.py",  # be tolerant to naming differences
                ]
                return any(p.exists() for p in candidates)
            except Exception:
                return False

        # Ensure optional top-level keys exist to avoid Jinja undefined errors
        # (Templates use these widely with defaults.)
        if not isinstance(context.get("macros"), dict):
            context["macros"] = {}
        if not isinstance(context.get("tuning"), dict):
            context["tuning"] = {}
        # Ensure nested tuning dicts exist for dot-access patterns used in templates
        for k in ("virtual_sdcard", "idle_timeout", "pause_resume", "arc_support", "respond", "save_variables", "exclude_object", "tmc_autotune", "input_shaper"):
            if not isinstance(context["tuning"].get(k), dict):
                context["tuning"][k] = {}
        # Defaults for always-safe tuning sections
        # (We changed [gcode_arcs] to be conditional; keep it enabled by default for compatibility.)
        context["tuning"]["arc_support"].setdefault("enabled", True)
        # Only emit an ACTIVE [autotune_tmc] config when the plugin is detected.
        # Do not override an explicit user choice (True/False) already stored in state.
        if bool(context["tuning"]["tmc_autotune"].get("enabled")) and "emit_config" not in context["tuning"]["tmc_autotune"]:
            context["tuning"]["tmc_autotune"]["emit_config"] = _has_klipper_tmc_autotune()
        if not isinstance(context.get("advanced"), dict):
            context["advanced"] = {}
        # Ensure nested advanced dicts exist for dot-access patterns used in templates
        for k in ("force_move", "firmware_retraction"):
            if not isinstance(context["advanced"].get(k), dict):
                context["advanced"][k] = {}
        if not isinstance(context.get("bed_leveling"), dict):
            context["bed_leveling"] = {}
        if not isinstance(context.get("homing"), dict):
            context["homing"] = {}
        if not isinstance(context.get("probe"), dict):
            context["probe"] = {}

        # Load board pin definitions from JSON files
        context['board'] = self._load_board_definition(
            self.state.get('mcu.main.board_type', 'other')
        )
        context['toolboard'] = self._load_toolboard_definition(
            self.state.get('mcu.toolboard.board_type', None)
        )
        context['extruder_presets'] = self._get_extruder_presets()

        # Apply board defaults for missing pin/port selections (best-effort).
        # This helps generate a usable config when the wizard state doesn't explicitly store
        # ports that can be derived from the selected board's default assignments.
        try:
            board_defaults = context.get("board", {}).get("defaults", {}) if isinstance(context.get("board"), dict) else {}
            if not isinstance(board_defaults, dict):
                board_defaults = {}

            # Ensure nested dicts exist
            for k in ("stepper_z", "heater_bed", "fans", "stepper_x", "stepper_y"):
                if not isinstance(context.get(k), dict):
                    context[k] = {}
            if not isinstance(context["fans"].get("part_cooling"), dict):
                context["fans"]["part_cooling"] = {}
            if not isinstance(context["fans"].get("hotend"), dict):
                context["fans"]["hotend"] = {}
            if not isinstance(context["fans"].get("controller"), dict):
                context["fans"]["controller"] = {}

            # Z motor port default
            if not context["stepper_z"].get("motor_port") and board_defaults.get("stepper_z"):
                context["stepper_z"]["motor_port"] = board_defaults.get("stepper_z")

            # Bed heater + thermistor defaults
            if not context["heater_bed"].get("heater_pin") and board_defaults.get("heater_bed"):
                context["heater_bed"]["heater_pin"] = board_defaults.get("heater_bed")
            if not context["heater_bed"].get("sensor_port") and board_defaults.get("thermistor_bed"):
                context["heater_bed"]["sensor_port"] = board_defaults.get("thermistor_bed")

            # Part cooling fan default
            part_loc = (context["fans"]["part_cooling"].get("location") or "mainboard")
            if part_loc == "mainboard" and not context["fans"]["part_cooling"].get("pin_mainboard") and board_defaults.get("fan_part_cooling"):
                context["fans"]["part_cooling"]["pin_mainboard"] = board_defaults.get("fan_part_cooling")
            if part_loc == "toolboard" and not context["fans"]["part_cooling"].get("pin_toolboard") and board_defaults.get("fan_part_cooling"):
                context["fans"]["part_cooling"]["pin_toolboard"] = board_defaults.get("fan_part_cooling")

            # Hotend fan default
            hotend_loc = (context["fans"]["hotend"].get("location") or "mainboard")
            if hotend_loc == "mainboard" and not context["fans"]["hotend"].get("pin_mainboard") and board_defaults.get("fan_hotend"):
                context["fans"]["hotend"]["pin_mainboard"] = board_defaults.get("fan_hotend")
            if hotend_loc == "toolboard" and not context["fans"]["hotend"].get("pin_toolboard") and board_defaults.get("fan_hotend"):
                context["fans"]["hotend"]["pin_toolboard"] = board_defaults.get("fan_hotend")

            # Controller fan default
            if context["fans"]["controller"].get("enabled") and not context["fans"]["controller"].get("pin") and board_defaults.get("fan_controller"):
                context["fans"]["controller"]["pin"] = board_defaults.get("fan_controller")

            # Y endstop default (common on boards)
            if (
                context["stepper_y"].get("endstop_type") == "physical"
                and not context["stepper_y"].get("endstop_port")
                and board_defaults.get("endstop_y")
            ):
                context["stepper_y"]["endstop_port"] = board_defaults.get("endstop_y")
                # Default to NC wired to GND (pullup, no invert)
                context["stepper_y"].setdefault("endstop_pullup", True)
                context["stepper_y"].setdefault("endstop_invert", False)
                context["stepper_y"].setdefault("endstop_config", "nc_gnd")

            # If a toolboard exists with X_STOP and stepper_x physical endstop config is missing,
            # default to toolboard X_STOP (common for Orbitool/Nitehawk-style setups).
            toolboard_pins = context.get("toolboard", {}).get("pins", {}) if isinstance(context.get("toolboard"), dict) else {}
            if (
                context["stepper_x"].get("endstop_type") == "physical"
                and not context["stepper_x"].get("endstop_port")
                and not context["stepper_x"].get("endstop_port_toolboard")
                and isinstance(toolboard_pins, dict)
                and "X_STOP" in toolboard_pins
            ):
                context["stepper_x"]["endstop_port_toolboard"] = "X_STOP"
                # Default to NC wired to GND (pullup, no invert)
                context["stepper_x"].setdefault("endstop_pullup", True)
                context["stepper_x"].setdefault("endstop_invert", False)
                context["stepper_x"].setdefault("endstop_config", "nc_gnd")
        except Exception:
            # Best-effort defaults only; never block generation here.
            pass

        return context

    def _load_board_definition(self, board_type: str) -> Dict[str, Any]:
        """Load main board pin definitions from JSON file."""
        if not board_type or board_type == 'other':
            return self._get_manual_board_context()

        board_file = self.templates_dir / "boards" / f"{board_type}.json"
        if board_file.exists():
            try:
                with open(board_file) as f:
                    board_data = json.load(f)
                return self._transform_board_data(board_data)
            except (json.JSONDecodeError, IOError):
                pass

        return self._get_manual_board_context()

    def _load_toolboard_definition(self, board_type: str) -> Dict[str, Any]:
        """Load toolboard pin definitions from JSON file."""
        if not board_type or not self.state.get('mcu.toolboard.connection_type'):
            return {}

        board_file = self.templates_dir / "toolboards" / f"{board_type}.json"
        if board_file.exists():
            try:
                with open(board_file) as f:
                    board_data = json.load(f)
                return self._transform_board_data(board_data)
            except (json.JSONDecodeError, IOError):
                pass

        return self._get_manual_toolboard_context()

    def _transform_board_data(self, board_data: Dict) -> Dict[str, Any]:
        """Transform board JSON data to template-friendly format."""
        pins = {}

        # Transform motor ports
        for port_name, port_data in board_data.get('motor_ports', {}).items():
            pins[port_name] = {
                'step': port_data.get('step_pin'),
                'dir': port_data.get('dir_pin'),
                'enable': port_data.get('enable_pin'),
                'uart': port_data.get('uart_pin'),
                'cs': port_data.get('cs_pin'),
                'diag': port_data.get('diag_pin'),
            }

        # Transform heater ports
        for port_name, port_data in board_data.get('heater_ports', {}).items():
            pins[port_name] = {'signal': port_data.get('pin')}

        # Transform fan ports
        for port_name, port_data in board_data.get('fan_ports', {}).items():
            pins[port_name] = {'signal': port_data.get('pin')}

        # Transform thermistor ports
        for port_name, port_data in board_data.get('thermistor_ports', {}).items():
            pins[port_name] = {'signal': port_data.get('pin')}

        # Transform endstop ports
        for port_name, port_data in board_data.get('endstop_ports', {}).items():
            pins[port_name] = {'signal': port_data.get('pin')}

        # Transform misc ports (optional)
        # Many boards expose useful general purpose pins (e.g. PS_ON, LEDs, etc).
        # Some misc ports are headers with nested pin maps (EXP1/EXP2) - skip those.
        for port_name, port_data in board_data.get('misc_ports', {}).items():
            if not isinstance(port_data, dict):
                continue
            pin = port_data.get('pin')
            if pin:
                pins[port_name] = {'signal': pin}

        # Get SPI config
        # Boards can represent SPI in two formats:
        # 1) Direct TMC pins (Mellow style): spi_config.tmc_mosi/tmc_miso/tmc_sck
        # 2) Named buses (BTT style): spi_config.<bus_name>.{mosi_pin,miso_pin,sck_pin}
        spi_config = {}
        raw_spi = board_data.get('spi_config', {})
        if isinstance(raw_spi, dict) and raw_spi:
            # Format 1: direct pins
            if 'tmc_mosi' in raw_spi or 'tmc_miso' in raw_spi or 'tmc_sck' in raw_spi:
                spi_config = {
                    'miso': raw_spi.get('tmc_miso'),
                    'mosi': raw_spi.get('tmc_mosi'),
                    'sclk': raw_spi.get('tmc_sck'),
                }
            else:
                # Format 2: first named bus dict
                for _spi_name, spi_data in raw_spi.items():
                    if isinstance(spi_data, dict):
                        spi_config = {
                            'miso': spi_data.get('miso_pin'),
                            'mosi': spi_data.get('mosi_pin'),
                            'sclk': spi_data.get('sck_pin'),
                        }
                        break  # Use first SPI config dict

        return {
            'id': board_data.get('id'),
            'name': board_data.get('name'),
            'pins': pins,
            'spi': spi_config,
            'motor_ports': list(board_data.get('motor_ports', {}).keys()),
            'heater_ports': list(board_data.get('heater_ports', {}).keys()),
            'fan_ports': list(board_data.get('fan_ports', {}).keys()),
            'thermistor_ports': list(board_data.get('thermistor_ports', {}).keys()),
            'endstop_ports': list(board_data.get('endstop_ports', {}).keys()),
            'defaults': board_data.get('default_assignments', {}),
        }

    def _get_manual_board_context(self) -> Dict[str, Any]:
        """Get fallback context for manual pin entry boards."""
        return {
            'id': 'manual',
            'name': 'Manual Configuration',
            'pins': {},
            'spi': {},
            'motor_ports': [],
            'heater_ports': [],
            'fan_ports': [],
            'thermistor_ports': [],
            'endstop_ports': [],
            'defaults': {},
        }

    def _get_manual_toolboard_context(self) -> Dict[str, Any]:
        """Get fallback context for manual toolboard pin entry."""
        return {
            'id': 'manual',
            'name': 'Manual Configuration',
            'pins': {},
            'motor_ports': [],
            'fan_ports': [],
            'heater_ports': [],
            'thermistor_ports': [],
            'endstop_ports': [],
        }

    def _get_extruder_presets(self) -> Dict[str, Any]:
        """Get extruder preset values."""
        return {
            'sherpa_mini': {
                'rotation_distance': 22.67895,
                'gear_ratio': '50:10',
                'default_pa': 0.04,
            },
            'orbiter_v2': {
                'rotation_distance': 4.637,
                'gear_ratio': '7.5:1',
                'default_pa': 0.025,
            },
            'smart_orbiter_v3': {
                'rotation_distance': 4.69,
                'gear_ratio': '7.5:1',
                'default_pa': 0.015,
            },
            'clockwork2': {
                'rotation_distance': 22.6789511,
                'gear_ratio': '50:10',
                'default_pa': 0.04,
            },
            'galileo2': {
                'rotation_distance': 47.088,
                'gear_ratio': '9:1',
                'default_pa': 0.035,
            },
            'lgx_lite': {
                'rotation_distance': 8,
                'gear_ratio': '44:8',
                'default_pa': 0.04,
            },
            'bmg': {
                'rotation_distance': 22.6789511,
                'gear_ratio': '50:17',
                'default_pa': 0.05,
            },
            'vz_hextrudort_8t': {
                'rotation_distance': 22.2,
                'gear_ratio': '50:8',
                'default_pa': 0.02,
            },
            'vz_hextrudort_10t': {
                'rotation_distance': 22.2,
                'gear_ratio': '50:10',
                'default_pa': 0.02,
            },
            'custom': {
                'rotation_distance': 22.6789511,
                'gear_ratio': '50:10',
                'default_pa': 0.04,
            },
        }

    def generate(self) -> Dict[str, str]:
        """
        Generate all configuration files.

        Returns:
            Dict mapping file paths to their contents
        """
        context = self.get_context()

        # Validation: required fields for a functional config
        # (Fail fast with actionable messages, rather than emitting partial/broken sections.)
        errors = []
        cfg = context or {}

        def _req(path: str) -> None:
            parts = path.split(".")
            cur = cfg
            for p in parts:
                if not isinstance(cur, dict) or p not in cur:
                    errors.append(f"Missing required setting: {path}")
                    return
                cur = cur[p]
            if cur is None or cur == "" or cur == []:
                errors.append(f"Missing required setting: {path}")

        # MCU serials
        _req("mcu.main.serial")

        # Core steppers
        _req("stepper_x.motor_port")
        _req("stepper_y.motor_port")
        _req("stepper_z.motor_port")

        # If physical endstops, require a port selection
        # Endstop wiring can be specified via the new endstop_pullup/endstop_invert booleans
        # OR the legacy endstop_config string (nc_gnd/no_gnd/nc_vcc/no_vcc).
        for axis in ("x", "y"):
            st = cfg.get(f"stepper_{axis}", {})
            if isinstance(st, dict) and st.get("endstop_type") == "physical":
                if not st.get("endstop_port") and not st.get("endstop_port_toolboard"):
                    errors.append(f"Missing required setting: stepper_{axis}.endstop_port (or stepper_{axis}.endstop_port_toolboard)")
                # Accept new flags OR legacy endstop_config
                has_new_flags = "endstop_pullup" in st or "endstop_invert" in st
                has_legacy = bool(st.get("endstop_config"))
                # No error if either format is present; defaults will be applied later if missing

        # Bed heater requires both heater + sensor wiring
        _req("heater_bed.heater_pin")
        _req("heater_bed.sensor_port")
        _req("heater_bed.sensor_type")

        # Fans: part cooling and hotend fan pins must be set
        part = (cfg.get("fans") or {}).get("part_cooling", {}) if isinstance(cfg.get("fans"), dict) else {}
        if isinstance(part, dict):
            loc = part.get("location") or "mainboard"
            if loc == "toolboard":
                _req("fans.part_cooling.pin_toolboard")
            else:
                _req("fans.part_cooling.pin_mainboard")

        hotend = (cfg.get("fans") or {}).get("hotend", {}) if isinstance(cfg.get("fans"), dict) else {}
        if isinstance(hotend, dict):
            loc = hotend.get("location") or "mainboard"
            if loc == "toolboard":
                _req("fans.hotend.pin_toolboard")
            else:
                _req("fans.hotend.pin_mainboard")

        # LEDs: each neopixel entry needs a pin + color order
        leds = cfg.get("leds")
        if isinstance(leds, list):
            for i, led in enumerate(leds):
                if not isinstance(led, dict):
                    continue
                if not led.get("pin"):
                    errors.append(f"Missing required setting: leds[{i}].pin")
                if not led.get("color_order"):
                    errors.append(f"Missing required setting: leds[{i}].color_order")

        # Additional fans: multi_pin must have pins
        add_fans = (cfg.get("fans") or {}).get("additional_fans") if isinstance(cfg.get("fans"), dict) else None
        if isinstance(add_fans, list):
            board_pins = cfg.get("board", {}).get("pins", {}) if isinstance(cfg.get("board"), dict) else {}
            tool_pins = cfg.get("toolboard", {}).get("pins", {}) if isinstance(cfg.get("toolboard"), dict) else {}
            for i, fan in enumerate(add_fans):
                if not isinstance(fan, dict):
                    continue
                if fan.get("pin_type") == "multi_pin" and not fan.get("pins"):
                    errors.append(f"Missing required setting: fans.additional_fans[{i}].pins")
                if fan.get("pin_type") != "multi_pin":
                    # Single-pin additional fans must reference a known port ID (e.g. FAN0/HE2),
                    # not a raw MCU pin name like PB10. Templates resolve board.pins[fan.pin].signal.
                    if not fan.get("pin"):
                        errors.append(f"Missing required setting: fans.additional_fans[{i}].pin")
                        continue
                    loc = fan.get("location") or "mainboard"
                    pin_key = fan.get("pin")
                    if loc == "toolboard":
                        if not isinstance(tool_pins, dict) or pin_key not in tool_pins:
                            errors.append(
                                f"Invalid setting: fans.additional_fans[{i}].pin='{pin_key}' (not found in toolboard port map). "
                                "Select a toolboard port (fan/heater/misc) in the wizard."
                            )
                    else:
                        if not isinstance(board_pins, dict) or pin_key not in board_pins:
                            errors.append(
                                f"Invalid setting: fans.additional_fans[{i}].pin='{pin_key}' (not found in mainboard port map). "
                                "Select a mainboard port (fan/heater/misc) in the wizard."
                            )

        if errors:
            raise ValueError("Wizard state is incomplete:\n" + "\n".join(f"- {e}" for e in errors))

        rendered = self.renderer.render_all(context)

        # Validation: fail fast on render errors (these are always broken configs)
        render_errors = []
        for section_key, content in rendered.items():
            if isinstance(content, str) and "# Render error:" in content:
                # Capture first line for readability
                first = next((ln for ln in content.splitlines() if "Render error" in ln), "").strip()
                render_errors.append(f"{section_key}: {first}")
        if render_errors:
            raise ValueError(
                "Template render errors detected (cannot generate valid config):\n"
                + "\n".join(f"- {e}" for e in render_errors[:50])
                + ("\n- ... (more)" if len(render_errors) > 50 else "")
            )

        # Group by output file
        files: Dict[str, List[str]] = {}

        for section_key, content in rendered.items():
            file_path = self.file_mapping.get(section_key, 'gschpoozi/misc.cfg')

            if file_path not in files:
                files[file_path] = []

            files[file_path].append(content)

        # Combine sections and add headers
        result = {}

        for file_path, sections in files.items():
            header = self._generate_header(file_path)
            content = header + "\n".join(sections)
            result[file_path] = content

        # Ensure expected output files exist even if empty (printer.cfg includes them).
        expected_cfgs = [
            "gschpoozi/hardware.cfg",
            "gschpoozi/probe.cfg",
            "gschpoozi/homing.cfg",
            "gschpoozi/leveling.cfg",
            "gschpoozi/macros-config.cfg",
            "gschpoozi/macros.cfg",
            "gschpoozi/calibration.cfg",
            "gschpoozi/tuning.cfg",
        ]
        for p in expected_cfgs:
            if p not in result:
                result[p] = self._generate_header(p)

        # Generate main printer.cfg with includes
        result['printer.cfg'] = self._generate_printer_cfg()

        # Generate user-overrides.cfg if it doesn't exist
        user_overrides_path = self.output_dir / "user-overrides.cfg"
        if not user_overrides_path.exists():
            result['user-overrides.cfg'] = self._generate_user_overrides()

        return result

    def _generate_header(self, file_path: str) -> str:
        """Generate file header with metadata."""
        description = self.OUTPUT_FILES.get(file_path, "Configuration")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return f"""#######################################
# {description}
# Generated by gschpoozi v2.0
# {timestamp}
#
# DO NOT EDIT - Changes will be overwritten
# Use user-overrides.cfg for customizations
#######################################

"""

    def _generate_printer_cfg(self) -> str:
        """Generate main printer.cfg with includes."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Wizard-managed non-gschpoozi includes
        pre_includes = []
        if self.state.get("includes.mainsail.enabled", False):
            pre_includes.append("mainsail.cfg")
        if self.state.get("includes.timelapse.enabled", False):
            pre_includes.append("timelapse.cfg")

        includes = [
            "gschpoozi/hardware.cfg",
            "gschpoozi/probe.cfg",
            "gschpoozi/homing.cfg",
            "gschpoozi/leveling.cfg",
            "gschpoozi/macros-config.cfg",
            "gschpoozi/macros.cfg",
            "gschpoozi/calibration.cfg",
            "gschpoozi/tuning.cfg",
            "user-overrides.cfg",
        ]

        lines = [
            "#######################################",
            "# Klipper Configuration",
            f"# Generated by gschpoozi v2.0",
            f"# {timestamp}",
            "#",
            "# Edit user-overrides.cfg for customizations",
            "#######################################",
            "",
        ]

        for inc in pre_includes:
            lines.append(f"[include {inc}]")
        for include in includes:
            lines.append(f"[include {include}]")

        lines.append("")

        generated_block = "\n".join(lines).rstrip() + "\n"

        # Preserve existing content:
        # - Keep any user includes/settings in the pre-SAVE_CONFIG area (e.g. mainsail.cfg)
        # - Replace any existing gschpoozi includes with the new include block
        # - Preserve the SAVE_CONFIG block verbatim if present
        try:
            # Primary: preserve from an existing printer.cfg in the OUTPUT directory (live generation).
            existing_path = self.output_dir / "printer.cfg"
            # Preview generation writes to a separate output dir; in that case preserve from the
            # wizard state dir (typically ~/printer_data/config/printer.cfg) instead.
            if not existing_path.exists():
                state_dir = getattr(self.state, "state_dir", None)
                if state_dir:
                    alt = Path(state_dir) / "printer.cfg"
                    if alt.exists():
                        existing_path = alt
                    else:
                        return generated_block
                else:
                    return generated_block

            existing = existing_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            # Be tolerant: some installs vary whitespace/dashes; match any SAVE_CONFIG marker line.
            # Typical Klipper marker:
            #   #*# <---------------------- SAVE_CONFIG ---------------------->
            save_idx = None
            for i, ln in enumerate(existing):
                s = ln.strip()
                if "SAVE_CONFIG" in s and s.startswith("#*#"):
                    save_idx = i
                    break

            pre = existing if save_idx is None else existing[:save_idx]
            save_block = [] if save_idx is None else existing[save_idx:]

            # Remove old generator include lines from pre-block; keep everything else.
            kept_pre: list[str] = []
            for ln in pre:
                s = ln.strip()
                if s.startswith("[include gschpoozi/") and s.endswith("]"):
                    continue
                if s == "[include user-overrides.cfg]":
                    continue
                if s == "[include mainsail.cfg]":
                    continue
                if s == "[include timelapse.cfg]":
                    continue
                kept_pre.append(ln)

            # If pre already had a gschpoozi include position, we want our new block after existing
            # non-gschpoozi include lines. We'll simply append the generated include block after
            # the kept preamble and add a blank line separator if needed.
            merged: list[str] = []
            merged.extend(kept_pre)
            if merged and merged[-1].strip() != "":
                merged.append("")
            merged.extend(generated_block.splitlines())

            # Ensure exactly one blank line before SAVE_CONFIG block
            if save_block:
                while merged and merged[-1].strip() == "":
                    merged.pop()
                merged.append("")
                merged.append("")
                merged.extend(save_block)

            return "\n".join(merged).rstrip() + "\n"
        except Exception:
            return generated_block

    def _generate_user_overrides(self) -> str:
        """Generate initial user-overrides.cfg."""
        return """#######################################
# User Overrides
#
# This file is preserved during config regeneration.
# Add your customizations here.
#######################################

# Example: Override stepper current
# [tmc2209 stepper_x]
# run_current: 1.2

# Example: Add custom macro
# [gcode_macro MY_MACRO]
# gcode:
#     G28

"""

    def write_files(self, files: Dict[str, str] = None) -> List[Path]:
        """
        Write generated files to disk.

        Args:
            files: Optional pre-generated files dict

        Returns:
            List of written file paths
        """
        if files is None:
            files = self.generate()

        written = []

        # Ensure gschpoozi directory exists
        gschpoozi_dir = self.output_dir / "gschpoozi"
        gschpoozi_dir.mkdir(parents=True, exist_ok=True)

        for file_path, content in files.items():
            full_path = self.output_dir / file_path

            # Create parent directories if needed
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Don't overwrite user-overrides.cfg if it exists
            if file_path == 'user-overrides.cfg' and full_path.exists():
                continue

            with open(full_path, 'w') as f:
                f.write(content)

            written.append(full_path)

        return written

    def preview(self) -> str:
        """Generate a preview of all config files."""
        files = self.generate()

        lines = ["=" * 60]
        lines.append("CONFIGURATION PREVIEW")
        lines.append("=" * 60)

        for file_path in sorted(files.keys()):
            lines.append("")
            lines.append(f"--- {file_path} ---")
            lines.append(files[file_path])

        return "\n".join(lines)


def main():
    """CLI entry point for testing."""
    generator = ConfigGenerator()

    if len(sys.argv) > 1 and sys.argv[1] == '--preview':
        print(generator.preview())
    else:
        files = generator.write_files()
        print(f"Generated {len(files)} files:")
        for path in files:
            print(f"  - {path}")


if __name__ == "__main__":
    main()

