#!/usr/bin/env python3
"""
gschpoozi Configuration Generator
Generates Klipper config files from wizard state and hardware assignments

Usage:
    ./generate-config.py --output-dir ~/printer_data/config/gschpoozi

https://github.com/gm-tc-collaborators/gschpoozi
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any, List

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_ROOT = SCRIPT_DIR.parent
TEMPLATES_DIR = REPO_ROOT / "templates"
BOARDS_DIR = TEMPLATES_DIR / "boards"
TOOLBOARDS_DIR = TEMPLATES_DIR / "toolboards"
PROFILES_DIR = TEMPLATES_DIR / "profiles"

HARDWARE_STATE_FILE = REPO_ROOT / ".hardware-state.json"
WIZARD_STATE_FILE = REPO_ROOT / ".wizard-state"

# ═══════════════════════════════════════════════════════════════════════════════
# STATE LOADING
# ═══════════════════════════════════════════════════════════════════════════════

def load_hardware_state() -> Dict:
    """Load hardware state from JSON."""
    if HARDWARE_STATE_FILE.exists():
        with open(HARDWARE_STATE_FILE) as f:
            return json.load(f)
    return {}

def load_profile(profile_id: str) -> Optional[Dict]:
    """Load a printer profile by ID."""
    if not profile_id:
        return None
    profile_file = PROFILES_DIR / f"{profile_id}.json"
    if profile_file.exists():
        with open(profile_file) as f:
            return json.load(f)
    return None

def load_wizard_state() -> Dict:
    """Load wizard state from key=value file."""
    state = {}
    if WIZARD_STATE_FILE.exists():
        with open(WIZARD_STATE_FILE) as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    state[key] = value
    return state

def load_board_template(board_id: str) -> Optional[Dict]:
    """Load board template JSON."""
    board_file = BOARDS_DIR / f"{board_id}.json"
    if board_file.exists():
        with open(board_file) as f:
            return json.load(f)
    return None

def load_toolboard_template(toolboard_id: str) -> Optional[Dict]:
    """Load toolboard template JSON."""
    if not toolboard_id or toolboard_id == "none":
        return None
    toolboard_file = TOOLBOARDS_DIR / f"{toolboard_id}.json"
    if toolboard_file.exists():
        with open(toolboard_file) as f:
            return json.load(f)
    return None

def load_motor_mapping() -> Dict:
    """Load motor mapping from discovery wizard results.

    Returns dict like: {"stepper_x": {"port": "MOTOR_0", "dir_invert": True}, ...}
    """
    # Check in printer_data/config first (standard location)
    motor_mapping_file = Path.home() / "printer_data" / "config" / ".motor_mapping.json"
    if motor_mapping_file.exists():
        with open(motor_mapping_file) as f:
            data = json.load(f)
            return data.get("motor_mapping", {})
    return {}

# ═══════════════════════════════════════════════════════════════════════════════
# PIN RESOLUTION
# ═══════════════════════════════════════════════════════════════════════════════

def get_motor_pins(board: Dict, port_name: str) -> Dict[str, str]:
    """Get motor pins for a given port."""
    motor_ports = board.get('motor_ports', {})
    port = motor_ports.get(port_name, {})
    return {
        'step_pin': port.get('step_pin', 'REPLACE_PIN'),
        'dir_pin': port.get('dir_pin', 'REPLACE_PIN'),
        'enable_pin': port.get('enable_pin', 'REPLACE_PIN'),
        'uart_pin': port.get('uart_pin'),
        'cs_pin': port.get('cs_pin'),
        'diag_pin': port.get('diag_pin'),
        'spi_bus': port.get('spi_bus'),
    }

def get_spi_pins(board: Dict, spi_bus_name: str = None) -> Dict[str, str]:
    """Get SPI pins from board config.

    Handles two formats:
    1. Direct TMC pins: spi_config.tmc_mosi, tmc_miso, tmc_sck
    2. Named bus: spi_config.spi4.mosi_pin, miso_pin, sck_pin
    """
    spi_config = board.get('spi_config', {})

    # Try direct TMC pins first (Mellow style)
    if 'tmc_mosi' in spi_config:
        return {
            'mosi': spi_config.get('tmc_mosi'),
            'miso': spi_config.get('tmc_miso'),
            'sck': spi_config.get('tmc_sck'),
            'bus': spi_config.get('tmc_spi_bus'),
        }

    # Try named bus (BTT style)
    if spi_bus_name and spi_bus_name in spi_config:
        bus_config = spi_config[spi_bus_name]
        return {
            'mosi': bus_config.get('mosi_pin'),
            'miso': bus_config.get('miso_pin'),
            'sck': bus_config.get('sck_pin'),
            'bus': spi_bus_name,
        }

    # Check all named buses
    for bus_name, bus_config in spi_config.items():
        if isinstance(bus_config, dict) and 'mosi_pin' in bus_config:
            return {
                'mosi': bus_config.get('mosi_pin'),
                'miso': bus_config.get('miso_pin'),
                'sck': bus_config.get('sck_pin'),
                'bus': bus_name,
            }

    return {'mosi': None, 'miso': None, 'sck': None, 'bus': None}

def get_heater_pin(board: Dict, port_name: str) -> str:
    """Get heater pin for a given port."""
    heater_ports = board.get('heater_ports', {})
    port = heater_ports.get(port_name, {})
    return port.get('pin', 'REPLACE_PIN')

def get_thermistor_pin(board: Dict, port_name: str) -> str:
    """Get thermistor pin for a given port."""
    therm_ports = board.get('thermistor_ports', {})
    port = therm_ports.get(port_name, {})
    return port.get('pin', 'REPLACE_PIN')

def get_fan_pin(board: Dict, port_name: str) -> str:
    """Get fan pin for a given port."""
    fan_ports = board.get('fan_ports', {})
    port = fan_ports.get(port_name, {})
    return port.get('pin', 'REPLACE_PIN')

def get_endstop_pin(board: Dict, port_name: str) -> str:
    """Get endstop pin for a given port.

    Handles different naming conventions between boards:
    - BTT style: STOP_0, STOP_1, STOP_2...
    - Mellow style: IO0, IO1, IO2...
    """
    endstop_ports = board.get('endstop_ports', {})

    # Direct lookup first
    if port_name in endstop_ports:
        return endstop_ports[port_name].get('pin', 'REPLACE_PIN')

    # Try mapping STOP_x -> IOx (BTT to Mellow)
    if port_name.startswith('STOP_'):
        io_name = f"IO{port_name[5:]}"
        if io_name in endstop_ports:
            return endstop_ports[io_name].get('pin', 'REPLACE_PIN')

    # Try mapping IOx -> STOP_x (Mellow to BTT)
    if port_name.startswith('IO') and port_name[2:].isdigit():
        stop_name = f"STOP_{port_name[2:]}"
        if stop_name in endstop_ports:
            return endstop_ports[stop_name].get('pin', 'REPLACE_PIN')

    # If port_name looks like a pin (e.g., PG12), use it directly
    if len(port_name) >= 2 and port_name[0] == 'P' and port_name[1].isalpha():
        return port_name

    return 'REPLACE_PIN'

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def apply_dir_invert(dir_pin: str, stepper_name: str, motor_mapping: Dict, hardware_state: Dict = None) -> str:
    """Apply direction inversion to dir_pin if configured in motor mapping or hardware state.

    If dir_invert is True for this stepper, prepend '!' to invert the pin.
    If the pin already has '!', remove it (double inversion = no inversion).

    Checks two sources for direction inversion:
    1. motor_mapping: from motor discovery wizard (.motor_mapping.json)
    2. hardware_state: from manual port assignment (.hardware-state.json, {stepper}_dir_invert)
    """
    needs_invert = motor_mapping.get(stepper_name, {}).get('dir_invert', False)

    # Also check hardware_state for manual assignment direction inversion
    if hardware_state and not needs_invert:
        assignments = hardware_state.get('port_assignments', {})
        needs_invert = assignments.get(f"{stepper_name}_dir_invert", False)

    if needs_invert:
        if dir_pin.startswith('!'):
            # Already inverted, remove the inversion (double invert = normal)
            return dir_pin[1:]
        else:
            return f"!{dir_pin}"
    return dir_pin


def generate_hardware_cfg(
    wizard_state: Dict,
    hardware_state: Dict,
    board: Dict,
    toolboard: Optional[Dict] = None
) -> str:
    """Generate hardware.cfg content."""

    assignments = hardware_state.get('port_assignments', {})
    board_name = hardware_state.get('board_name', 'Unknown')

    # Load motor mapping for direction inversion settings
    motor_mapping = load_motor_mapping()

    # Get values from wizard state
    kinematics = wizard_state.get('kinematics', 'corexy')
    bed_x = wizard_state.get('bed_size_x', '300')
    bed_y = wizard_state.get('bed_size_y', '300')
    bed_z = wizard_state.get('bed_size_z', '350')
    z_count = int(wizard_state.get('z_stepper_count', '1'))
    hotend_therm = wizard_state.get('hotend_thermistor', 'Generic 3950')
    hotend_pullup = wizard_state.get('hotend_pullup_resistor', '')
    bed_therm = wizard_state.get('bed_thermistor', 'Generic 3950')
    bed_pullup = wizard_state.get('bed_pullup_resistor', '')

    # Get per-axis stepper settings (step angle, microsteps, rotation distance)
    # Use 'or' to handle empty strings in wizard state
    # X axis
    x_step_angle = wizard_state.get('stepper_x_step_angle') or '1.8'
    x_microsteps = wizard_state.get('stepper_x_microsteps') or '16'
    x_rotation_distance = wizard_state.get('stepper_x_rotation_distance') or '40'
    x_full_steps = '200' if x_step_angle == '1.8' else '400'
    # Y axis
    y_step_angle = wizard_state.get('stepper_y_step_angle') or '1.8'
    y_microsteps = wizard_state.get('stepper_y_microsteps') or '16'
    y_rotation_distance = wizard_state.get('stepper_y_rotation_distance') or '40'
    y_full_steps = '200' if y_step_angle == '1.8' else '400'
    # Z axis
    z_step_angle = wizard_state.get('stepper_z_step_angle') or '1.8'
    z_microsteps = wizard_state.get('stepper_z_microsteps') or '16'
    z_rotation_distance = wizard_state.get('stepper_z_rotation_distance') or '8'
    z_full_steps = '200' if z_step_angle == '1.8' else '400'
    # Extruder
    e_step_angle = wizard_state.get('stepper_e_step_angle') or '1.8'
    e_microsteps = wizard_state.get('stepper_e_microsteps') or '16'
    e_rotation_distance = wizard_state.get('stepper_e_rotation_distance') or '22.6789511'
    e_full_steps = '200' if e_step_angle == '1.8' else '400'

    # Get driver type
    driver_x = wizard_state.get('driver_X', wizard_state.get('stepper_driver', 'TMC2209'))

    lines = []
    lines.append("# " + "═" * 77)
    lines.append("# HARDWARE CONFIGURATION")
    lines.append(f"# Generated by gschpoozi - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"# Board: {board_name}")
    lines.append("# " + "═" * 77)
    lines.append("")

    # MCU Section
    lines.append("# " + "─" * 77)
    lines.append("# MCU")
    lines.append("# " + "─" * 77)
    lines.append("[mcu]")

    # MCU serial - check wizard_state first, then hardware_state
    mcu_serial = wizard_state.get('mcu_serial') or hardware_state.get('mcu_serial')
    if mcu_serial:
        lines.append(f"serial: {mcu_serial}")
    else:
        # Use placeholder path - Klipper will error clearly if not set
        lines.append("serial: /dev/serial/by-id/SET_YOUR_MCU_ID_HERE")
        lines.append("# ^^^ Run: ls /dev/serial/by-id/* to find your MCU")
    lines.append("")

    # Toolboard MCU if present
    if toolboard:
        tb_name = hardware_state.get('toolboard_name', 'Toolboard')
        tb_connection = toolboard.get('connection', 'USB').upper()
        lines.append(f"[mcu toolboard]")

        if tb_connection == 'CAN':
            canbus_uuid = wizard_state.get('toolboard_canbus_uuid') or hardware_state.get('toolboard_canbus_uuid')
            if canbus_uuid:
                lines.append(f"canbus_uuid: {canbus_uuid}")
            else:
                lines.append("canbus_uuid: SET_YOUR_CANBUS_UUID_HERE")
                lines.append("# ^^^ Run: ~/klippy-env/bin/python ~/klipper/scripts/canbus_query.py can0")
        else:
            tb_serial = wizard_state.get('toolboard_serial') or hardware_state.get('toolboard_serial')
            if tb_serial:
                lines.append(f"serial: {tb_serial}")
            else:
                lines.append("serial: /dev/serial/by-id/SET_YOUR_TOOLBOARD_ID_HERE")
                lines.append("# ^^^ Run: ls /dev/serial/by-id/* to find your toolboard")

        lines.append(f"# {tb_name} ({tb_connection})")
        lines.append("")

    # Printer section
    lines.append("# " + "─" * 77)
    lines.append("# PRINTER")
    lines.append("# " + "─" * 77)
    lines.append("[printer]")
    # Handle AWD kinematics
    kin = kinematics.replace('-awd', '')  # Klipper uses 'corexy' not 'corexy-awd'
    lines.append(f"kinematics: {kin}")
    lines.append("max_velocity: 500")
    lines.append("max_accel: 10000")
    lines.append("max_z_velocity: 30")
    lines.append("max_z_accel: 350")
    lines.append("")

    # Stepper X
    lines.append("# " + "─" * 77)
    lines.append("# STEPPERS")
    lines.append("# " + "─" * 77)

    x_port = assignments.get('stepper_x', 'MOTOR_0')
    x_pins = get_motor_pins(board, x_port)
    x_dir_pin = apply_dir_invert(x_pins['dir_pin'], 'stepper_x', motor_mapping, hardware_state)
    lines.append(f"[stepper_x]")
    lines.append(f"step_pin: {x_pins['step_pin']}      # {x_port}")
    lines.append(f"dir_pin: {x_dir_pin}       # {x_port}")
    lines.append(f"enable_pin: !{x_pins['enable_pin']}  # {x_port}")
    lines.append(f"microsteps: {x_microsteps}")
    lines.append(f"rotation_distance: {x_rotation_distance}")
    if x_full_steps != '200':
        lines.append(f"full_steps_per_rotation: {x_full_steps}  # 0.9° stepper")

    # Endstop - check for toolboard, sensorless, or physical on mainboard
    tb_assignments = hardware_state.get('toolboard_assignments', {}) if toolboard else {}
    x_endstop_tb = tb_assignments.get('endstop_x', '')
    x_endstop = assignments.get('endstop_x', '')

    if x_endstop_tb and x_endstop_tb not in ('', 'none'):
        # X endstop on toolboard
        endstop_pin = get_endstop_pin(toolboard, x_endstop_tb)
        lines.append(f"endstop_pin: ^toolboard:{endstop_pin}  # {x_endstop_tb} on toolboard")
    elif x_endstop == 'sensorless':
        lines.append(f"endstop_pin: tmc2209_stepper_x:virtual_endstop  # Sensorless homing")
    elif x_endstop:
        endstop_pin = get_endstop_pin(board, x_endstop)
        lines.append(f"endstop_pin: ^{endstop_pin}  # {x_endstop}")
    # If no endstop assigned, Klipper will error - user must configure in Hardware Setup

    # Homing position - use configured values or defaults based on home direction
    x_home = wizard_state.get('home_x', 'max')  # 'min' or 'max'
    x_pos_min = wizard_state.get('position_min_x', '0')
    x_pos_endstop = wizard_state.get('position_endstop_x', '')
    if x_home == 'min':
        lines.append(f"position_min: {x_pos_min}")
        lines.append(f"position_max: {bed_x}")
        lines.append(f"position_endstop: {x_pos_endstop if x_pos_endstop else x_pos_min}")
    else:
        lines.append(f"position_min: {x_pos_min}")
        lines.append(f"position_max: {bed_x}")
        lines.append(f"position_endstop: {x_pos_endstop if x_pos_endstop else bed_x}")
    lines.append("homing_speed: 80")
    lines.append("homing_retract_dist: 5")
    lines.append("")

    # Stepper Y
    y_port = assignments.get('stepper_y', 'MOTOR_1')
    y_pins = get_motor_pins(board, y_port)
    y_dir_pin = apply_dir_invert(y_pins['dir_pin'], 'stepper_y', motor_mapping, hardware_state)
    lines.append(f"[stepper_y]")
    lines.append(f"step_pin: {y_pins['step_pin']}      # {y_port}")
    lines.append(f"dir_pin: {y_dir_pin}       # {y_port}")
    lines.append(f"enable_pin: !{y_pins['enable_pin']}  # {y_port}")
    lines.append(f"microsteps: {y_microsteps}")
    lines.append(f"rotation_distance: {y_rotation_distance}")
    if y_full_steps != '200':
        lines.append(f"full_steps_per_rotation: {y_full_steps}  # 0.9° stepper")

    y_endstop = assignments.get('endstop_y', '')
    if y_endstop == 'sensorless':
        lines.append(f"endstop_pin: tmc2209_stepper_y:virtual_endstop  # Sensorless homing")
    elif y_endstop:
        endstop_pin = get_endstop_pin(board, y_endstop)
        lines.append(f"endstop_pin: ^{endstop_pin}  # {y_endstop}")
    # If no endstop assigned, Klipper will error - user must configure in Hardware Setup

    # Homing position - use configured values or defaults based on home direction
    y_home = wizard_state.get('home_y', 'max')  # 'min' or 'max'
    y_pos_min = wizard_state.get('position_min_y', '0')
    y_pos_endstop = wizard_state.get('position_endstop_y', '')
    if y_home == 'min':
        lines.append(f"position_min: {y_pos_min}")
        lines.append(f"position_max: {bed_y}")
        lines.append(f"position_endstop: {y_pos_endstop if y_pos_endstop else y_pos_min}")
    else:
        lines.append(f"position_min: {y_pos_min}")
        lines.append(f"position_max: {bed_y}")
        lines.append(f"position_endstop: {y_pos_endstop if y_pos_endstop else bed_y}")
    lines.append("homing_speed: 80")
    lines.append("homing_retract_dist: 5")
    lines.append("")

    # AWD: Add X1 and Y1 steppers
    if kinematics == 'corexy-awd':
        x1_port = assignments.get('stepper_x1', 'MOTOR_2')
        x1_pins = get_motor_pins(board, x1_port)
        x1_dir_pin = apply_dir_invert(x1_pins['dir_pin'], 'stepper_x1', motor_mapping, hardware_state)
        lines.append(f"[stepper_x1]")
        lines.append(f"step_pin: {x1_pins['step_pin']}      # {x1_port}")
        lines.append(f"dir_pin: {x1_dir_pin}       # {x1_port}")
        lines.append(f"enable_pin: !{x1_pins['enable_pin']}  # {x1_port}")
        lines.append(f"microsteps: {x_microsteps}")
        lines.append(f"rotation_distance: {x_rotation_distance}")
        if x_full_steps != '200':
            lines.append(f"full_steps_per_rotation: {x_full_steps}  # 0.9° stepper")
        lines.append("")

        y1_port = assignments.get('stepper_y1', 'MOTOR_3')
        y1_pins = get_motor_pins(board, y1_port)
        y1_dir_pin = apply_dir_invert(y1_pins['dir_pin'], 'stepper_y1', motor_mapping, hardware_state)
        lines.append(f"[stepper_y1]")
        lines.append(f"step_pin: {y1_pins['step_pin']}      # {y1_port}")
        lines.append(f"dir_pin: {y1_dir_pin}       # {y1_port}")
        lines.append(f"enable_pin: !{y1_pins['enable_pin']}  # {y1_port}")
        lines.append(f"microsteps: {y_microsteps}")
        lines.append(f"rotation_distance: {y_rotation_distance}")
        if y_full_steps != '200':
            lines.append(f"full_steps_per_rotation: {y_full_steps}  # 0.9° stepper")
        lines.append("")

    # Stepper Z (and Z1, Z2, Z3 if multi-Z)
    for z_idx in range(z_count):
        suffix = "" if z_idx == 0 else str(z_idx)
        z_key = f"stepper_z{suffix}" if suffix else "stepper_z"
        z_port = assignments.get(z_key, f'MOTOR_{2 + z_idx}')
        z_pins = get_motor_pins(board, z_port)
        z_dir_pin = apply_dir_invert(z_pins['dir_pin'], z_key, motor_mapping, hardware_state)

        section_name = f"stepper_z{suffix}"
        lines.append(f"[{section_name}]")
        lines.append(f"step_pin: {z_pins['step_pin']}      # {z_port}")
        lines.append(f"dir_pin: {z_dir_pin}       # {z_port}")
        lines.append(f"enable_pin: !{z_pins['enable_pin']}  # {z_port}")
        lines.append(f"microsteps: {z_microsteps}")
        lines.append(f"rotation_distance: {z_rotation_distance}")
        if z_full_steps != '200':
            lines.append(f"full_steps_per_rotation: {z_full_steps}  # 0.9° stepper")

        if z_idx == 0:
            # Use correct virtual endstop based on probe type
            # All probes register as 'probe' chip, NOT their MCU name
            probe_type = wizard_state.get('probe_type', '')
            if probe_type == 'beacon':
                # Beacon registers as 'probe' chip (NOT 'beacon' - that's the MCU)
                lines.append("endstop_pin: probe:z_virtual_endstop")
                lines.append("homing_retract_dist: 0  # Beacon requires this")
            elif probe_type == 'cartographer':
                # Cartographer registers as 'probe' chip
                lines.append("endstop_pin: probe:z_virtual_endstop")
                lines.append("homing_retract_dist: 0  # Cartographer requires this")
            elif probe_type == 'btt-eddy':
                # BTT Eddy registers as 'probe' chip
                lines.append("endstop_pin: probe:z_virtual_endstop")
                lines.append("homing_retract_dist: 0  # Eddy probe requires this")
            elif probe_type in ('bltouch', 'klicky', 'inductive'):
                lines.append("endstop_pin: probe:z_virtual_endstop")
                lines.append("homing_retract_dist: 5")
            elif probe_type == 'endstop':
                # Physical Z endstop - check for assignment
                z_endstop = assignments.get('endstop_z', '')
                if z_endstop:
                    z_endstop_pin = get_endstop_pin(board, z_endstop)
                    lines.append(f"endstop_pin: ^{z_endstop_pin}  # {z_endstop}")
                # If no assignment, Klipper will error - user must configure
                lines.append("position_endstop: 0  # Adjust after homing")
                lines.append("homing_retract_dist: 5")
            lines.append("position_min: -5")
            lines.append(f"position_max: {bed_z}")
            lines.append("homing_speed: 15")

        lines.append("")

    # TMC Driver Sections
    lines.append("# " + "─" * 77)
    lines.append("# TMC DRIVERS")
    lines.append("# " + "─" * 77)

    # Get SPI pins from board config (for SPI-based TMC drivers)
    spi_pins = get_spi_pins(board)

    # Helper to generate TMC section
    def generate_tmc_section(stepper_name: str, driver_type: str, motor_pins: Dict,
                              run_current: str = "0.8", mcu_prefix: str = "") -> List[str]:
        """Generate TMC driver config section."""
        tmc_lines = []
        driver_lower = driver_type.lower()
        prefix = f"{mcu_prefix}:" if mcu_prefix else ""

        tmc_lines.append(f"[{driver_lower} {stepper_name}]")
        is_spi_driver = 'spi' in driver_lower or driver_type in ('TMC5160', 'TMC2130')

        if is_spi_driver:
            # Use cs_pin if available, fall back to uart_pin
            cs_pin = motor_pins.get('cs_pin') or motor_pins.get('uart_pin')
            tmc_lines.append(f"cs_pin: {prefix}{cs_pin}")

            # Check if motor port specifies spi_bus (BTT style)
            motor_spi_bus = motor_pins.get('spi_bus')
            if motor_spi_bus:
                # Use hardware SPI bus
                tmc_lines.append(f"spi_bus: {motor_spi_bus}")
            elif spi_pins.get('mosi') and spi_pins.get('miso') and spi_pins.get('sck'):
                # Use software SPI with actual pins from board config
                tmc_lines.append(f"spi_software_miso_pin: {spi_pins['miso']}")
                tmc_lines.append(f"spi_software_mosi_pin: {spi_pins['mosi']}")
                tmc_lines.append(f"spi_software_sclk_pin: {spi_pins['sck']}")
            else:
                # No SPI config found - add comment for manual config
                tmc_lines.append("# SPI pins not found in board config - configure manually:")
                tmc_lines.append("# spi_software_miso_pin: REPLACE_MISO")
                tmc_lines.append("# spi_software_mosi_pin: REPLACE_MOSI")
                tmc_lines.append("# spi_software_sclk_pin: REPLACE_SCLK")
        else:
            tmc_lines.append(f"uart_pin: {prefix}{motor_pins.get('uart_pin')}")

        tmc_lines.append(f"run_current: {run_current}")
        # Add stealthchop for quiet operation on XY, off for Z/extruder typically
        if 'x' in stepper_name.lower() or 'y' in stepper_name.lower():
            tmc_lines.append("stealthchop_threshold: 999999")
        else:
            tmc_lines.append("stealthchop_threshold: 0")
        tmc_lines.append("")
        return tmc_lines

    # Default driver type (fallback)
    default_driver = wizard_state.get('stepper_driver', 'TMC2209')

    # Stepper X TMC
    driver_x_type = wizard_state.get('driver_X', default_driver)
    if driver_x_type and (x_pins.get('uart_pin') or x_pins.get('cs_pin')):
        lines.extend(generate_tmc_section('stepper_x', driver_x_type, x_pins))

    # Stepper Y TMC
    driver_y_type = wizard_state.get('driver_Y', default_driver)
    y_port = assignments.get('stepper_y', 'MOTOR_1')
    y_pins_tmc = get_motor_pins(board, y_port)
    if driver_y_type and (y_pins_tmc.get('uart_pin') or y_pins_tmc.get('cs_pin')):
        lines.extend(generate_tmc_section('stepper_y', driver_y_type, y_pins_tmc))

    # AWD: X1 and Y1 TMC
    if kinematics == 'corexy-awd':
        driver_x1_type = wizard_state.get('driver_X1', default_driver)
        x1_port = assignments.get('stepper_x1', 'MOTOR_2')
        x1_pins_tmc = get_motor_pins(board, x1_port)
        if driver_x1_type and (x1_pins_tmc.get('uart_pin') or x1_pins_tmc.get('cs_pin')):
            lines.extend(generate_tmc_section('stepper_x1', driver_x1_type, x1_pins_tmc))

        driver_y1_type = wizard_state.get('driver_Y1', default_driver)
        y1_port = assignments.get('stepper_y1', 'MOTOR_3')
        y1_pins_tmc = get_motor_pins(board, y1_port)
        if driver_y1_type and (y1_pins_tmc.get('uart_pin') or y1_pins_tmc.get('cs_pin')):
            lines.extend(generate_tmc_section('stepper_y1', driver_y1_type, y1_pins_tmc))

    # Stepper Z TMC (and Z1, Z2, Z3)
    for z_idx in range(z_count):
        suffix = "" if z_idx == 0 else str(z_idx)
        stepper_name = f"stepper_z{suffix}"
        driver_key = f"driver_Z{suffix}" if suffix else "driver_Z"
        driver_z_type = wizard_state.get(driver_key, default_driver)
        z_port_name = f"stepper_z{suffix}" if suffix else "stepper_z"
        z_port_tmc = assignments.get(z_port_name, f'MOTOR_{4 + z_idx}')
        z_pins_tmc = get_motor_pins(board, z_port_tmc)
        if driver_z_type and (z_pins_tmc.get('uart_pin') or z_pins_tmc.get('cs_pin')):
            lines.extend(generate_tmc_section(stepper_name, driver_z_type, z_pins_tmc, "0.8"))

    # Extruder TMC (on mainboard or toolboard)
    driver_e_type = wizard_state.get('driver_E', default_driver)
    tb_extruder = hardware_state.get('toolboard_assignments', {}).get('extruder', '') if toolboard else ''
    extruder_on_tb = toolboard and tb_extruder not in ('', 'none')
    if extruder_on_tb:
        e_port_tmc = hardware_state.get('toolboard_assignments', {}).get('extruder', 'EXTRUDER')
        e_pins_tmc = get_motor_pins(toolboard, e_port_tmc)
        if driver_e_type and (e_pins_tmc.get('uart_pin') or e_pins_tmc.get('cs_pin')):
            lines.extend(generate_tmc_section('extruder', driver_e_type, e_pins_tmc, "0.5", "toolboard"))
    else:
        e_port_tmc = assignments.get('extruder', 'MOTOR_5')
        e_pins_tmc = get_motor_pins(board, e_port_tmc)
        if driver_e_type and (e_pins_tmc.get('uart_pin') or e_pins_tmc.get('cs_pin')):
            lines.extend(generate_tmc_section('extruder', driver_e_type, e_pins_tmc, "0.5"))

    # Extruder (on main board or toolboard)
    lines.append("# " + "─" * 77)
    lines.append("# EXTRUDER")
    lines.append("# " + "─" * 77)

    # Check if extruder is on toolboard (not 'none')
    tb_assignments = hardware_state.get('toolboard_assignments', {}) if toolboard else {}
    extruder_on_toolboard = toolboard and tb_assignments.get('extruder', '') not in ('', 'none')
    heater_on_toolboard = toolboard and tb_assignments.get('heater_extruder', '') not in ('', 'none')
    therm_on_toolboard = toolboard and tb_assignments.get('thermistor_extruder', '') not in ('', 'none')

    lines.append("[extruder]")

    if extruder_on_toolboard:
        # Extruder motor on toolboard
        e_port = tb_assignments.get('extruder', 'EXTRUDER')
        e_pins = get_motor_pins(toolboard, e_port)
        e_dir_pin = apply_dir_invert(e_pins['dir_pin'], 'extruder', motor_mapping, hardware_state)
        lines.append(f"step_pin: toolboard:{e_pins['step_pin']}      # {e_port}")
        lines.append(f"dir_pin: toolboard:{e_dir_pin}       # {e_port}")
        lines.append(f"enable_pin: !toolboard:{e_pins['enable_pin']}  # {e_port}")
    else:
        # Extruder motor on main board
        e_port = assignments.get('extruder', 'MOTOR_5')
        e_pins = get_motor_pins(board, e_port)
        e_dir_pin = apply_dir_invert(e_pins['dir_pin'], 'extruder', motor_mapping, hardware_state)
        lines.append(f"step_pin: {e_pins['step_pin']}      # {e_port}")
        lines.append(f"dir_pin: {e_dir_pin}       # {e_port}")
        lines.append(f"enable_pin: !{e_pins['enable_pin']}  # {e_port}")

    lines.append(f"microsteps: {e_microsteps}")
    lines.append(f"rotation_distance: {e_rotation_distance}  # Calibrate with Klipper esteps test")
    if e_full_steps != '200':
        lines.append(f"full_steps_per_rotation: {e_full_steps}  # 0.9° stepper")
    lines.append("nozzle_diameter: 0.400")
    lines.append("filament_diameter: 1.750")

    if heater_on_toolboard:
        he_port = tb_assignments.get('heater_extruder', 'HE')
        he_pin = get_heater_pin(toolboard, he_port)
        lines.append(f"heater_pin: toolboard:{he_pin}  # {he_port}")
    else:
        he_port = assignments.get('heater_extruder', 'HE0')
        he_pin = get_heater_pin(board, he_port)
        lines.append(f"heater_pin: {he_pin}  # {he_port}")

    # Handle special sensor types (MAX31865 for PT100/PT1000)
    # MAX31865 requires SPI - user must configure CS pin manually
    if hotend_therm == 'PT1000_MAX31865':
        lines.append("sensor_type: MAX31865")
        lines.append("sensor_pin: SET_YOUR_MAX31865_CS_PIN  # MAX31865 chip select")
        lines.append("spi_bus: spi1  # Adjust for your board")
        lines.append("rtd_nominal_r: 1000")
        lines.append("rtd_reference_r: 4300")
        lines.append("rtd_num_of_wires: 2")
    elif hotend_therm == 'PT100_MAX31865':
        lines.append("sensor_type: MAX31865")
        lines.append("sensor_pin: SET_YOUR_MAX31865_CS_PIN  # MAX31865 chip select")
        lines.append("spi_bus: spi1  # Adjust for your board")
        lines.append("rtd_nominal_r: 100")
        lines.append("rtd_reference_r: 430")
        lines.append("rtd_num_of_wires: 2")
    else:
        lines.append(f"sensor_type: {hotend_therm}")

        if therm_on_toolboard:
            th_port = tb_assignments.get('thermistor_extruder', 'TH0')
            th_pin = get_thermistor_pin(toolboard, th_port)
            lines.append(f"sensor_pin: toolboard:{th_pin}  # {th_port}")
        else:
            th_port = assignments.get('thermistor_extruder', 'T0')
            th_pin = get_thermistor_pin(board, th_port)
            lines.append(f"sensor_pin: {th_pin}  # {th_port}")

        # Add pullup_resistor if specified (important for PT1000 direct)
        if hotend_pullup:
            lines.append(f"pullup_resistor: {hotend_pullup}  # Board-specific pullup value")

    lines.append("min_temp: 0")

    # Set max_temp based on sensor type
    if hotend_therm == 'SliceEngineering450':
        lines.append("max_temp: 450  # High-temp thermistor")
    elif 'PT1000' in hotend_therm or 'PT100' in hotend_therm:
        lines.append("max_temp: 350  # RTD sensor")
    else:
        lines.append("max_temp: 300")
    # Adjust settings based on extruder type (direct-drive vs bowden)
    extruder_type = wizard_state.get('extruder_type', 'direct-drive')
    if extruder_type == 'bowden':
        lines.append("max_extrude_only_distance: 500  # Bowden: longer for tube loading")
        lines.append("max_extrude_cross_section: 5")
    else:
        lines.append("max_extrude_only_distance: 150")

    lines.append("control: pid")
    lines.append("pid_kp: 26.213  # Run PID_CALIBRATE HEATER=extruder TARGET=200")
    lines.append("pid_ki: 1.304")
    lines.append("pid_kd: 131.721")

    # Pressure advance: direct-drive ~0.04, bowden ~0.5-1.0 (requires tuning)
    if extruder_type == 'bowden':
        lines.append("pressure_advance: 0.5  # Bowden starting value - tune this!")
    else:
        lines.append("pressure_advance: 0.04  # Direct drive starting value")
    lines.append("pressure_advance_smooth_time: 0.040")
    lines.append("")

    # Heated Bed
    lines.append("# " + "─" * 77)
    lines.append("# HEATED BED")
    lines.append("# " + "─" * 77)

    hb_port = assignments.get('heater_bed', 'HB')
    hb_pin = get_heater_pin(board, hb_port)
    tb_port = assignments.get('thermistor_bed', 'TB')
    tb_pin = get_thermistor_pin(board, tb_port)

    lines.append("[heater_bed]")
    lines.append(f"heater_pin: {hb_pin}  # {hb_port}")
    lines.append(f"sensor_type: {bed_therm}")
    lines.append(f"sensor_pin: {tb_pin}  # {tb_port}")
    # Add pullup_resistor if specified
    if bed_pullup:
        lines.append(f"pullup_resistor: {bed_pullup}  # Board-specific pullup value")
    lines.append("control: pid")
    lines.append("pid_kp: 54.027  # Run PID_CALIBRATE HEATER=heater_bed TARGET=60")
    lines.append("pid_ki: 0.770")
    lines.append("pid_kd: 948.182")
    lines.append("min_temp: 0")
    lines.append("max_temp: 120")
    lines.append("")

    # Fans
    lines.append("# " + "─" * 77)
    lines.append("# FANS")
    lines.append("# " + "─" * 77)

    # Get fan settings from wizard state
    fan_pc = wizard_state.get('fan_part_cooling', '')
    fan_pc_multipin = wizard_state.get('fan_part_cooling_multipin', '')
    fan_hotend = wizard_state.get('fan_hotend', '')
    fan_hotend_multipin = wizard_state.get('fan_hotend_multipin', '')
    fan_hotend_type = wizard_state.get('fan_hotend_type', 'heater')  # manual, heater, temperature (default heater)
    fan_controller = wizard_state.get('fan_controller', '')
    fan_controller_multipin = wizard_state.get('fan_controller_multipin', '')
    fan_controller_type = wizard_state.get('fan_controller_type', 'controller')  # controller, manual, heater
    fan_exhaust = wizard_state.get('fan_exhaust', '')
    fan_exhaust_multipin = wizard_state.get('fan_exhaust_multipin', '')
    fan_exhaust_type = wizard_state.get('fan_exhaust_type', 'manual')  # manual, heater, temperature
    fan_chamber = wizard_state.get('fan_chamber', '')
    fan_chamber_type = wizard_state.get('fan_chamber_type', 'manual')  # manual, heater, temperature
    fan_chamber_multipin = wizard_state.get('fan_chamber_multipin', '')
    fan_rscs = wizard_state.get('fan_rscs', '')
    fan_rscs_multipin = wizard_state.get('fan_rscs_multipin', '')
    fan_rscs_type = wizard_state.get('fan_rscs_type', 'manual')  # manual, heater, temperature
    fan_radiator = wizard_state.get('fan_radiator', '')
    fan_radiator_multipin = wizard_state.get('fan_radiator_multipin', '')
    fan_radiator_type = wizard_state.get('fan_radiator_type', 'heater')  # manual, heater, temperature (default heater for water cooling)

    # Advanced settings for all fans (prefix: pc=part cooling, hf=hotend, cf=controller, ex=exhaust, ch=chamber, rs=rscs, rd=radiator)
    def get_fan_settings(prefix: str) -> dict:
        """Get advanced settings for a fan type."""
        return {
            'max_power': wizard_state.get(f'fan_{prefix}_max_power', ''),
            'cycle_time': wizard_state.get(f'fan_{prefix}_cycle_time', ''),
            'hardware_pwm': wizard_state.get(f'fan_{prefix}_hardware_pwm', ''),
            'shutdown_speed': wizard_state.get(f'fan_{prefix}_shutdown_speed', ''),
            'kick_start': wizard_state.get(f'fan_{prefix}_kick_start', ''),
        }

    def add_fan_settings(lines: List[str], settings: dict, defaults: dict = None):
        """Add fan advanced settings to config lines, using defaults where not specified."""
        if defaults is None:
            defaults = {}
        # max_power
        if settings['max_power']:
            lines.append(f"max_power: {settings['max_power']}")
        elif defaults.get('max_power'):
            lines.append(f"max_power: {defaults['max_power']}")
        # cycle_time
        if settings['cycle_time']:
            lines.append(f"cycle_time: {settings['cycle_time']}")
        elif defaults.get('cycle_time'):
            lines.append(f"cycle_time: {defaults['cycle_time']}")
        # hardware_pwm
        if settings['hardware_pwm']:
            lines.append(f"hardware_pwm: {settings['hardware_pwm']}")
        elif defaults.get('hardware_pwm'):
            lines.append(f"hardware_pwm: {defaults['hardware_pwm']}")
        # shutdown_speed
        if settings['shutdown_speed']:
            lines.append(f"shutdown_speed: {settings['shutdown_speed']}")
        elif defaults.get('shutdown_speed'):
            lines.append(f"shutdown_speed: {defaults['shutdown_speed']}")
        # kick_start_time
        if settings['kick_start']:
            lines.append(f"kick_start_time: {settings['kick_start']}")
        elif defaults.get('kick_start'):
            lines.append(f"kick_start_time: {defaults['kick_start']}")

    pc_settings = get_fan_settings('pc')
    hf_settings = get_fan_settings('hf')
    cf_settings = get_fan_settings('cf')
    ex_settings = get_fan_settings('ex')
    ch_settings = get_fan_settings('ch')
    rs_settings = get_fan_settings('rs')
    rd_settings = get_fan_settings('rd')

    # Helper function to generate multi_pin section
    def generate_multipin(name: str, pin1: str, pin2: str, port1: str, port2: str) -> List[str]:
        mp_lines = []
        mp_lines.append(f"[multi_pin {name}_pins]")
        mp_lines.append(f"pins: {pin1}, {pin2}  # {port1} + {port2}")
        mp_lines.append("")
        return mp_lines

    # Check if fans are on toolboard (not 'none')
    pc_on_toolboard = toolboard and tb_assignments.get('fan_part_cooling', '') not in ('', 'none')
    hf_on_toolboard = toolboard and tb_assignments.get('fan_hotend', '') not in ('', 'none')

    # Multi-pin part cooling - if second port is assigned
    pc2_port = assignments.get('fan_part_cooling_pin2', '')
    if pc2_port:
        pc2_pin = get_fan_pin(board, pc2_port)

        if pc_on_toolboard:
            pc_port = tb_assignments.get('fan_part_cooling', 'FAN0')
            pc_pin = get_fan_pin(toolboard, pc_port)
            lines.extend(generate_multipin('part_cooling', f'toolboard:{pc_pin}', pc2_pin, pc_port, pc2_port))
        else:
            pc_port = assignments.get('fan_part_cooling', 'FAN0')
            pc_pin = get_fan_pin(board, pc_port)
            lines.extend(generate_multipin('part_cooling', pc_pin, pc2_pin, pc_port, pc2_port))

        # Part cooling fan using multi_pin
        lines.append("[fan]")
        lines.append("pin: multi_pin:part_cooling_pins")
    else:
        # Part cooling fan - single pin
        if pc_on_toolboard:
            pc_port = tb_assignments.get('fan_part_cooling', 'FAN0')
            pc_pin = get_fan_pin(toolboard, pc_port)
            lines.append("[fan]")
            lines.append(f"pin: toolboard:{pc_pin}  # {pc_port} - Part cooling")
        else:
            pc_port = assignments.get('fan_part_cooling', 'FAN0')
            pc_pin = get_fan_pin(board, pc_port)
            lines.append("[fan]")
            lines.append(f"pin: {pc_pin}  # {pc_port} - Part cooling")

    # Add advanced settings (no defaults for part cooling - all optional)
    add_fan_settings(lines, pc_settings)
    lines.append("")

    # Hotend fan (control type: heater/manual/temperature)
    if fan_hotend != 'none':
        hf_port = None
        hf_pin = None
        if hf_on_toolboard:
            hf_port = tb_assignments.get('fan_hotend', 'FAN1')
            hf_pin = f"toolboard:{get_fan_pin(toolboard, hf_port)}"
        elif assignments.get('fan_hotend'):
            hf_port = assignments.get('fan_hotend', 'FAN1')
            hf_pin = get_fan_pin(board, hf_port)

        if hf_port and hf_pin:
            if fan_hotend_type == 'heater':
                hf_heater = wizard_state.get('fan_hotend_heater', 'extruder')
                hf_heater_temp = wizard_state.get('fan_hotend_heater_temp', '50')
                lines.append("[heater_fan hotend_fan]")
                lines.append(f"pin: {hf_pin}  # {hf_port}")
                add_fan_settings(lines, hf_settings, {'max_power': '1.0', 'kick_start': '0.5'})
                lines.append(f"heater: {hf_heater}")
                lines.append(f"heater_temp: {hf_heater_temp}.0")
            elif fan_hotend_type == 'temperature':
                hf_sensor = wizard_state.get('fan_hotend_sensor_type', '')
                hf_target = wizard_state.get('fan_hotend_target_temp', '40')
                lines.append("[temperature_fan hotend_fan]")
                lines.append(f"pin: {hf_pin}  # {hf_port}")
                add_fan_settings(lines, hf_settings, {'max_power': '1.0', 'kick_start': '0.5', 'shutdown_speed': '0'})
                if hf_sensor and hf_sensor != 'chamber':
                    lines.append(f"sensor_type: {hf_sensor}")
                    lines.append("sensor_pin: REPLACE_PIN  # Connect temperature sensor")
                else:
                    lines.append("sensor_type: temperature_combined")
                    lines.append("sensor_list: temperature_sensor chamber")
                    lines.append("combination_method: max")
                lines.append("min_temp: 0")
                lines.append("max_temp: 100")
                lines.append(f"target_temp: {hf_target}")
                lines.append("control: watermark")
            else:  # manual
                lines.append("[fan_generic hotend_fan]")
                lines.append(f"pin: {hf_pin}  # {hf_port}")
                add_fan_settings(lines, hf_settings, {'max_power': '1.0', 'kick_start': '0.5'})
                lines.append("# Manual control: SET_FAN_SPEED FAN=hotend_fan SPEED=x")
            lines.append("")

    # Controller fan on main board (control type: controller/manual/heater)
    cf_port = assignments.get('fan_controller')
    cf2_port = assignments.get('fan_controller_pin2', '')
    if cf_port:
        cf_pin = get_fan_pin(board, cf_port)

        # Multi-pin if second port is assigned
        if cf2_port:
            cf2_pin = get_fan_pin(board, cf2_port)
            lines.extend(generate_multipin('controller', cf_pin, cf2_pin, cf_port, cf2_port))
            cf_pin_str = "multi_pin:controller_pins"
        else:
            cf_pin_str = f"{cf_pin}  # {cf_port}"

        if fan_controller_type == 'controller':
            lines.append("[controller_fan electronics_fan]")
            lines.append(f"pin: {cf_pin_str}")
            add_fan_settings(lines, cf_settings, {'max_power': '1.0', 'kick_start': '0.5'})
            lines.append("heater: heater_bed, extruder")
            lines.append("idle_timeout: 60")
            lines.append("idle_speed: 0.5")
        elif fan_controller_type == 'heater':
            cf_heater = wizard_state.get('fan_controller_heater', 'extruder')
            cf_heater_temp = wizard_state.get('fan_controller_heater_temp', '50')
            lines.append("[heater_fan electronics_fan]")
            lines.append(f"pin: {cf_pin_str}")
            add_fan_settings(lines, cf_settings, {'max_power': '1.0', 'kick_start': '0.5'})
            lines.append(f"heater: {cf_heater}")
            lines.append(f"heater_temp: {cf_heater_temp}.0")
        else:  # manual
            lines.append("[fan_generic electronics_fan]")
            lines.append(f"pin: {cf_pin_str}")
            add_fan_settings(lines, cf_settings, {'max_power': '1.0', 'kick_start': '0.5'})
            lines.append("# Manual control: SET_FAN_SPEED FAN=electronics_fan SPEED=x")
        lines.append("")

    # Exhaust fan - generated if port is assigned (control type: manual/heater/temperature)
    ex_port = assignments.get('fan_exhaust')
    ex2_port = assignments.get('fan_exhaust_pin2', '')
    if ex_port:
        ex_pin = get_fan_pin(board, ex_port)

        # Multi-pin if second port is assigned
        if ex2_port:
            ex2_pin = get_fan_pin(board, ex2_port)
            lines.extend(generate_multipin('exhaust', ex_pin, ex2_pin, ex_port, ex2_port))
            pin_value = "multi_pin:exhaust_pins"
        else:
            pin_value = f"{ex_pin}  # {ex_port}"

        if fan_exhaust_type == 'heater':
            # Heater-triggered exhaust fan
            ex_heater = wizard_state.get('fan_exhaust_heater', 'extruder')
            ex_heater_temp = wizard_state.get('fan_exhaust_heater_temp', '50')
            lines.append("[heater_fan exhaust_fan]")
            lines.append(f"pin: {pin_value}")
            add_fan_settings(lines, ex_settings, {'max_power': '1.0', 'kick_start': '0.5'})
            lines.append(f"heater: {ex_heater}")
            lines.append(f"heater_temp: {ex_heater_temp}.0")
            lines.append("# Exhaust fan - runs when heater is active")
        elif fan_exhaust_type == 'temperature':
            # Temperature-controlled exhaust fan
            ex_sensor_type = wizard_state.get('fan_exhaust_sensor_type', '')
            ex_target_temp = wizard_state.get('fan_exhaust_target_temp', '45')

            lines.append("[temperature_fan exhaust]")
            lines.append(f"pin: {pin_value}")
            add_fan_settings(lines, ex_settings, {'max_power': '1.0', 'shutdown_speed': '0', 'kick_start': '0.5'})

            # Check if using existing chamber sensor or dedicated sensor
            if ex_sensor_type == 'chamber':
                lines.append("sensor_type: temperature_combined")
                lines.append("sensor_list: temperature_sensor chamber")
                lines.append("combination_method: max")
            else:
                # Need dedicated sensor pin from hardware state
                ex_sensor_pin = assignments.get('fan_exhaust_sensor', '')
                if ex_sensor_pin:
                    sensor_type = ex_sensor_type or 'Generic 3950'
                    lines.append(f"sensor_type: {sensor_type}")
                    lines.append(f"sensor_pin: {ex_sensor_pin}")
                else:
                    # Fall back to chamber sensor if available
                    chamber_configured = wizard_state.get('has_chamber_sensor', '')
                    if chamber_configured == 'yes':
                        lines.append("sensor_type: temperature_combined")
                        lines.append("sensor_list: temperature_sensor chamber")
                        lines.append("combination_method: max")
                    else:
                        sensor_type = ex_sensor_type or 'Generic 3950'
                        lines.append(f"sensor_type: {sensor_type}")
                        lines.append("sensor_pin: SET_SENSOR_PIN  # Assign in Hardware Setup")

            lines.append("min_temp: 0")
            lines.append("max_temp: 80")
            lines.append(f"target_temp: {ex_target_temp}")
            lines.append("control: watermark")
            lines.append("# Temperature-controlled exhaust - maintains target chamber temp")
        else:
            # Manual control (default)
            lines.append("[fan_generic exhaust_fan]")
            lines.append(f"pin: {pin_value}")
            add_fan_settings(lines, ex_settings, {'max_power': '1.0', 'shutdown_speed': '0', 'kick_start': '0.5'})
            lines.append("off_below: 0.10")
            lines.append("# Control with: SET_FAN_SPEED FAN=exhaust_fan SPEED=0.5")
        lines.append("")

    # Chamber fan - generated if port is assigned (control type: manual/heater/temperature)
    ch_port = assignments.get('fan_chamber')
    ch2_port = assignments.get('fan_chamber_pin2', '')
    if ch_port:
        ch_pin = get_fan_pin(board, ch_port)

        # Multi-pin if second port is assigned
        if ch2_port:
            ch2_pin = get_fan_pin(board, ch2_port)
            lines.extend(generate_multipin('chamber', ch_pin, ch2_pin, ch_port, ch2_port))
            pin_value = "multi_pin:chamber_pins"
        else:
            pin_value = f"{ch_pin}  # {ch_port}"

        if fan_chamber_type == 'heater':
            # Heater-triggered chamber fan
            ch_heater = wizard_state.get('fan_chamber_heater', 'extruder')
            ch_heater_temp = wizard_state.get('fan_chamber_heater_temp', '50')
            lines.append("[heater_fan chamber_fan]")
            lines.append(f"pin: {pin_value}")
            add_fan_settings(lines, ch_settings, {'max_power': '1.0', 'kick_start': '0.5'})
            lines.append(f"heater: {ch_heater}")
            lines.append(f"heater_temp: {ch_heater_temp}.0")
            lines.append("# Chamber fan - runs when heater is active")
        elif fan_chamber_type == 'temperature':
            # Temperature-controlled chamber fan
            ch_sensor_type = wizard_state.get('fan_chamber_sensor_type', '')
            ch_target_temp = wizard_state.get('fan_chamber_target_temp', '45')

            lines.append("[temperature_fan chamber]")
            lines.append(f"pin: {pin_value}")
            add_fan_settings(lines, ch_settings, {'max_power': '1.0', 'shutdown_speed': '0', 'kick_start': '0.5'})

            # Check if using existing chamber sensor or dedicated sensor
            if ch_sensor_type == 'chamber':
                lines.append("sensor_type: temperature_combined")
                lines.append("sensor_list: temperature_sensor chamber")
                lines.append("combination_method: max")
            else:
                # Use chamber sensor pin from hardware assignments if available
                ch_sensor_pin = assignments.get('fan_chamber_sensor', wizard_state.get('fan_chamber_sensor_pin', ''))
                if ch_sensor_pin:
                    sensor_type = ch_sensor_type or 'Generic 3950'
                    lines.append(f"sensor_type: {sensor_type}")
                    lines.append(f"sensor_pin: {ch_sensor_pin}")
                else:
                    # Check if chamber sensor is configured elsewhere
                    chamber_configured = wizard_state.get('has_chamber_sensor', '')
                    if chamber_configured == 'yes':
                        lines.append("sensor_type: temperature_combined")
                        lines.append("sensor_list: temperature_sensor chamber")
                        lines.append("combination_method: max")
                    else:
                        sensor_type = ch_sensor_type or 'Generic 3950'
                        lines.append(f"sensor_type: {sensor_type}")
                        lines.append("sensor_pin: SET_SENSOR_PIN  # Assign in Hardware Setup")

            lines.append("min_temp: 0")
            lines.append("max_temp: 80")
            lines.append(f"target_temp: {ch_target_temp}")
            lines.append("control: watermark")
            lines.append("gcode_id: C")
        else:
            # Manual chamber fan (default)
            lines.append("[fan_generic chamber_fan]")
            lines.append(f"pin: {pin_value}")
            add_fan_settings(lines, ch_settings, {'max_power': '1.0', 'shutdown_speed': '0', 'kick_start': '0.5'})
            lines.append("off_below: 0.10")
            lines.append("# Control with: SET_FAN_SPEED FAN=chamber_fan SPEED=0.5")
        lines.append("")

    # RSCS/Filter fan (control type: manual/heater/temperature)
    rs_port = assignments.get('fan_rscs')
    rs2_port = assignments.get('fan_rscs_pin2', '')
    if rs_port:
        rs_pin = get_fan_pin(board, rs_port)

        # Multi-pin if second port is assigned
        if rs2_port:
            rs2_pin = get_fan_pin(board, rs2_port)
            lines.extend(generate_multipin('rscs', rs_pin, rs2_pin, rs_port, rs2_port))
            rs_pin_str = "multi_pin:rscs_pins"
        else:
            rs_pin_str = f"{rs_pin}  # {rs_port}"

        if fan_rscs_type == 'heater':
            rs_heater = wizard_state.get('fan_rscs_heater', 'extruder')
            rs_heater_temp = wizard_state.get('fan_rscs_heater_temp', '50')
            lines.append("[heater_fan rscs_fan]")
            lines.append(f"pin: {rs_pin_str}")
            add_fan_settings(lines, rs_settings, {'max_power': '1.0', 'kick_start': '0.5'})
            lines.append(f"heater: {rs_heater}")
            lines.append(f"heater_temp: {rs_heater_temp}.0")
            lines.append("# Recirculating active carbon/HEPA filter")
        elif fan_rscs_type == 'temperature':
            rs_sensor = wizard_state.get('fan_rscs_sensor_type', '')
            rs_target = wizard_state.get('fan_rscs_target_temp', '45')
            lines.append("[temperature_fan rscs_fan]")
            lines.append(f"pin: {rs_pin_str}")
            add_fan_settings(lines, rs_settings, {'max_power': '1.0', 'shutdown_speed': '0', 'kick_start': '0.5'})
            if rs_sensor and rs_sensor != 'chamber':
                lines.append(f"sensor_type: {rs_sensor}")
                lines.append("sensor_pin: REPLACE_PIN  # Connect temperature sensor")
            else:
                lines.append("sensor_type: temperature_combined")
                lines.append("sensor_list: temperature_sensor chamber")
                lines.append("combination_method: max")
            lines.append("min_temp: 0")
            lines.append("max_temp: 80")
            lines.append(f"target_temp: {rs_target}")
            lines.append("control: watermark")
            lines.append("gcode_id: R")
            lines.append("# Recirculating active carbon/HEPA filter - temp controlled")
        else:  # manual
            lines.append("[fan_generic rscs_fan]")
            lines.append(f"pin: {rs_pin_str}")
            add_fan_settings(lines, rs_settings, {'max_power': '1.0', 'shutdown_speed': '0', 'kick_start': '0.5'})
            lines.append("off_below: 0.10")
            lines.append("# Recirculating active carbon/HEPA filter")
            lines.append("# Control with: SET_FAN_SPEED FAN=rscs_fan SPEED=0.5")
        lines.append("")

    # Radiator fan - generated if port is assigned (control type: manual/heater/temperature, default heater for water cooling)
    rd_port = assignments.get('fan_radiator')
    rd2_port = assignments.get('fan_radiator_pin2', '')
    if rd_port:
        rd_pin = get_fan_pin(board, rd_port)

        # Multi-pin if second port is assigned
        if rd2_port:
            rd2_pin = get_fan_pin(board, rd2_port)
            lines.extend(generate_multipin('radiator', rd_pin, rd2_pin, rd_port, rd2_port))
            pin_value = "multi_pin:radiator_pins"
        else:
            pin_value = f"{rd_pin}  # {rd_port}"

        if fan_radiator_type == 'manual':
            # Manual control
            lines.append("[fan_generic radiator_fan]")
            lines.append(f"pin: {pin_value}")
            add_fan_settings(lines, rd_settings, {'max_power': '1.0', 'shutdown_speed': '0', 'kick_start': '0.5'})
            lines.append("off_below: 0.10")
            lines.append("# Water cooling radiator fan - manual control")
            lines.append("# Control with: SET_FAN_SPEED FAN=radiator_fan SPEED=0.5")
        elif fan_radiator_type == 'temperature':
            # Temperature-controlled radiator fan
            rd_sensor_type = wizard_state.get('fan_radiator_sensor_type', '')
            rd_target_temp = wizard_state.get('fan_radiator_target_temp', '45')

            lines.append("[temperature_fan radiator]")
            lines.append(f"pin: {pin_value}")
            add_fan_settings(lines, rd_settings, {'max_power': '1.0', 'shutdown_speed': '0', 'kick_start': '0.5'})

            # Check if using existing chamber sensor or dedicated sensor
            if rd_sensor_type == 'chamber':
                lines.append("sensor_type: temperature_combined")
                lines.append("sensor_list: temperature_sensor chamber")
                lines.append("combination_method: max")
            else:
                # Need dedicated sensor pin from hardware state
                rd_sensor_pin = assignments.get('fan_radiator_sensor', '')
                if rd_sensor_pin:
                    sensor_type = rd_sensor_type or 'Generic 3950'
                    lines.append(f"sensor_type: {sensor_type}")
                    lines.append(f"sensor_pin: {rd_sensor_pin}")
                else:
                    sensor_type = rd_sensor_type or 'Generic 3950'
                    lines.append(f"sensor_type: {sensor_type}")
                    lines.append("sensor_pin: SET_SENSOR_PIN  # Assign in Hardware Setup")

            lines.append("min_temp: 0")
            lines.append("max_temp: 80")
            lines.append(f"target_temp: {rd_target_temp}")
            lines.append("control: watermark")
            lines.append("# Temperature-controlled radiator fan")
        else:
            # Heater-triggered (default for water cooling)
            rd_heater = wizard_state.get('fan_radiator_heater', 'extruder')
            rd_heater_temp = wizard_state.get('fan_radiator_heater_temp', '50')
            lines.append("[heater_fan radiator_fan]")
            lines.append(f"pin: {pin_value}")
            add_fan_settings(lines, rd_settings, {'max_power': '1.0', 'kick_start': '0.5'})
            lines.append(f"heater: {rd_heater}")
            lines.append(f"heater_temp: {rd_heater_temp}.0")
            lines.append("# Water cooling radiator fan - runs when hotend is hot")
        lines.append("")

    # Probe configuration
    probe_type = wizard_state.get('probe_type', '')
    probe_mode = wizard_state.get('probe_mode', 'proximity')  # Default to proximity
    # Get probe serial/CAN - check wizard state first, then hardware state as fallback
    probe_serial = wizard_state.get('probe_serial') or hardware_state.get('probe_serial')
    probe_canbus_uuid = wizard_state.get('probe_canbus_uuid') or hardware_state.get('probe_canbus_uuid')

    # Get bed dimensions for homing position calculations
    bed_x = int(wizard_state.get('bed_size_x', '300') or '300')
    bed_y = int(wizard_state.get('bed_size_y', '300') or '300')

    # Z homing position - user configurable, defaults to bed center
    z_home_x = int(wizard_state.get('z_home_x', '') or str(bed_x // 2))
    z_home_y = int(wizard_state.get('z_home_y', '') or str(bed_y // 2))

    # Mesh margin - user configurable, defaults to 30mm
    mesh_margin = int(wizard_state.get('mesh_margin', '30') or '30')

    if probe_type and probe_type != 'none' and probe_type != 'endstop':
        lines.append("# " + "─" * 77)
        lines.append("# PROBE")
        lines.append("# " + "─" * 77)

        if probe_type == 'beacon':
            lines.append("[beacon]")
            if probe_serial:
                lines.append(f"serial: {probe_serial}")
            elif probe_canbus_uuid:
                lines.append(f"canbus_uuid: {probe_canbus_uuid}")
            else:
                lines.append("serial: /dev/serial/by-id/SET_YOUR_BEACON_ID_HERE")
                lines.append("# ^^^ Run: ls /dev/serial/by-id/*beacon* to find your device")
            lines.append("x_offset: 0")
            lines.append("y_offset: 20  # Adjust for your toolhead")
            lines.append("mesh_main_direction: x")
            lines.append("mesh_runs: 2")

            # Contact/Touch mode configuration for Beacon
            if probe_mode == 'touch':
                lines.append("")
                lines.append("# Contact mode settings (Beacon Rev H+ required)")
                lines.append("home_method: contact")
                lines.append(f"home_xy_position: {z_home_x}, {z_home_y}")
                lines.append("home_z_hop: 5")
                lines.append("home_z_hop_speed: 30")
                lines.append("contact_max_hotend_temperature: 180")
                lines.append("")
                lines.append("# For additional contact mode options, see:")
                lines.append("# https://docs.beacon3d.com/")
            else:
                lines.append("")
                lines.append("# Proximity mode (default)")
                lines.append("# Uses eddy current sensing for Z reference")

        elif probe_type == 'cartographer':
            lines.append("[cartographer]")
            if probe_serial:
                lines.append(f"serial: {probe_serial}")
            elif probe_canbus_uuid:
                lines.append(f"canbus_uuid: {probe_canbus_uuid}")
            else:
                lines.append("serial: /dev/serial/by-id/SET_YOUR_CARTOGRAPHER_ID_HERE")
                lines.append("# ^^^ Run: ls /dev/serial/by-id/*cartographer* to find your device")
            lines.append("x_offset: 0")
            lines.append("y_offset: 20  # Adjust for your toolhead")

            lines.append("mesh_main_direction: x")
            lines.append("mesh_runs: 2")

            # Mode-specific comments
            if probe_mode == 'touch':
                lines.append("")
                lines.append("# Touch mode enabled")
                lines.append("# Cartographer touch mode provides higher precision Z homing")
                lines.append("# For touch mode setup and calibration, see:")
                lines.append("# https://docs.cartographer3d.com/")
            else:
                lines.append("")
                lines.append("# Scan/Proximity mode (default)")
                lines.append("# Uses eddy current sensing for contactless Z reference")

        elif probe_type == 'btt-eddy':
            lines.append("[mcu eddy]")
            if probe_serial:
                lines.append(f"serial: {probe_serial}")
            elif probe_canbus_uuid:
                lines.append(f"canbus_uuid: {probe_canbus_uuid}")
            else:
                lines.append("serial: /dev/serial/by-id/SET_YOUR_BTT_EDDY_ID_HERE")
                lines.append("# ^^^ Run: ls /dev/serial/by-id/*Eddy* to find your device")
            lines.append("")
            lines.append("[temperature_sensor btt_eddy_mcu]")
            lines.append("sensor_type: temperature_mcu")
            lines.append("sensor_mcu: eddy")
            lines.append("")
            lines.append("[probe_eddy_current btt_eddy]")
            lines.append("sensor_type: ldc1612")
            lines.append("i2c_mcu: eddy")
            lines.append("i2c_bus: i2c0f")
            lines.append("x_offset: 0")
            lines.append("y_offset: 20  # Adjust for your toolhead")

            # Touch mode configuration for BTT Eddy
            if probe_mode == 'touch':
                lines.append("")
                lines.append("# Touch/Tap mode settings")
                lines.append("# BTT Eddy uses tap detection for Z homing")
                lines.append("z_offset: 0.0  # Adjust after PROBE_CALIBRATE")
                lines.append("speed: 2  # Touch speed (mm/s)")
                lines.append("lift_speed: 5")
                lines.append("samples: 3")
                lines.append("sample_retract_dist: 2")
                lines.append("samples_result: median")
                lines.append("")
                lines.append("# Touch mode calibration:")
                lines.append("# Run PROBE_EDDY_CURRENT_CALIBRATE CHIP=btt_eddy")
            else:
                lines.append("")
                lines.append("# Proximity/Scan mode (default)")
                lines.append("# Uses eddy current induction for contactless sensing")
                lines.append("z_offset: 1.0  # Standard proximity offset")
                lines.append("speed: 40")
                lines.append("lift_speed: 5")
                lines.append("data_rate: 500")
                lines.append("")
                lines.append("[temperature_probe btt_eddy]")
                lines.append("sensor_type: Generic 3950")
                lines.append("sensor_pin: eddy:gpio26")
                lines.append("horizontal_move_z: 2")
                lines.append("")
                lines.append("# Calibration commands:")
                lines.append("# PROBE_EDDY_CURRENT_CALIBRATE CHIP=btt_eddy")
                lines.append("# TEMPERATURE_PROBE_CALIBRATE PROBE=btt_eddy TARGET=70")

        elif probe_type == 'bltouch':
            # BLTouch requires probe pin assignment
            probe_pin = assignments.get('probe_pin', '')
            if probe_pin:
                probe_pin_resolved = get_endstop_pin(board, probe_pin)
                lines.append("[bltouch]")
                lines.append(f"sensor_pin: ^{probe_pin_resolved}  # {probe_pin}")
                lines.append(f"control_pin: {probe_pin_resolved}  # BLTouch servo - may need different pin")
                lines.append("x_offset: 0")
                lines.append("y_offset: 20  # Adjust for your toolhead")
                lines.append("z_offset: 0  # Run PROBE_CALIBRATE")
            # If no probe_pin assigned, skip section - user must configure in Hardware Setup
        elif probe_type == 'klicky' or probe_type == 'inductive':
            # Klicky/Inductive require probe pin assignment
            probe_pin = assignments.get('probe_pin', '')
            if probe_pin:
                probe_pin_resolved = get_endstop_pin(board, probe_pin)
                lines.append("[probe]")
                lines.append(f"pin: ^{probe_pin_resolved}  # {probe_pin}")
                lines.append("x_offset: 0")
                lines.append("y_offset: 20  # Adjust for your toolhead")
                lines.append("z_offset: 0  # Run PROBE_CALIBRATE")
                lines.append("speed: 5")
                lines.append("samples: 3")
                lines.append("sample_retract_dist: 2")
                lines.append("samples_result: median")
            # If no probe_pin assigned, skip section - user must configure in Hardware Setup

        lines.append("")

        # ─────────────────────────────────────────────────────────────────────
        # SAFE Z HOME - Required unless probe handles homing itself
        # ─────────────────────────────────────────────────────────────────────
        # Beacon touch mode handles Z homing via home_method: contact
        # and has its own home_xy_position, so safe_z_home would conflict
        skip_safe_z_home = (probe_type == 'beacon' and probe_mode == 'touch')

        if not skip_safe_z_home:
            lines.append("# " + "─" * 77)
            lines.append("# SAFE Z HOME")
            lines.append("# " + "─" * 77)
            lines.append("[safe_z_home]")
            lines.append(f"home_xy_position: {z_home_x}, {z_home_y}")
            lines.append("z_hop: 10  # Lift Z before homing")
            lines.append("z_hop_speed: 25")
            lines.append("speed: 150")
            lines.append("")

        # ─────────────────────────────────────────────────────────────────────
        # BED MESH - Required for ALL probe types
        # ─────────────────────────────────────────────────────────────────────
        lines.append("# " + "─" * 77)
        lines.append("# BED MESH")
        lines.append("# " + "─" * 77)
        lines.append("[bed_mesh]")
        lines.append("speed: 150")
        lines.append("horizontal_move_z: 5")

        # Eddy current probes can use rapid scanning
        if probe_type in ('beacon', 'cartographer', 'btt-eddy'):
            lines.append("# Eddy probe: use rapid scan for faster mesh")
            lines.append("# BED_MESH_CALIBRATE METHOD=rapid_scan")
            if probe_type == 'btt-eddy':
                lines.append("scan_overshoot: 8")
            lines.append(f"mesh_min: {mesh_margin}, {mesh_margin}")
            lines.append(f"mesh_max: {bed_x - mesh_margin}, {bed_y - mesh_margin}")
            lines.append("probe_count: 9, 9")
            lines.append("algorithm: bicubic")
        else:
            # Pin-based probes (BLTouch, Klicky, Inductive)
            lines.append(f"mesh_min: {mesh_margin}, {mesh_margin}")
            lines.append(f"mesh_max: {bed_x - mesh_margin}, {bed_y - mesh_margin}")
            lines.append("probe_count: 5, 5")
            lines.append("algorithm: bicubic")
            lines.append("# Use ADAPTIVE=1 for adaptive meshing: BED_MESH_CALIBRATE ADAPTIVE=1")
        lines.append("")

    # Leveling configuration based on Z motor count
    leveling_method = wizard_state.get('leveling_method', '')
    profile_id = wizard_state.get('profile_id')
    profile = load_profile(profile_id) if profile_id else None

    if leveling_method == 'quad_gantry_level' or z_count == 4:
        lines.append("# " + "─" * 77)
        lines.append("# QUAD GANTRY LEVEL")
        lines.append("# " + "─" * 77)
        lines.append("[quad_gantry_level]")

        # Use profile values if available, otherwise use defaults based on bed size
        if profile and 'quad_gantry_level' in profile:
            qgl = profile['quad_gantry_level']
            gc = qgl.get('gantry_corners', [[-60, -10], [int(bed_x)+60, int(bed_y)+70]])
            pts = qgl.get('points', [[50, 25], [50, int(bed_y)-75], [int(bed_x)-50, int(bed_y)-75], [int(bed_x)-50, 25]])
            lines.append(f"gantry_corners:")
            lines.append(f"    {gc[0][0]}, {gc[0][1]}")
            lines.append(f"    {gc[1][0]}, {gc[1][1]}")
            lines.append(f"points:")
            for pt in pts:
                lines.append(f"    {pt[0]}, {pt[1]}")
            lines.append(f"speed: {qgl.get('speed', 200)}")
            lines.append(f"horizontal_move_z: {qgl.get('horizontal_move_z', 10)}")
            lines.append(f"retries: {qgl.get('retries', 5)}")
            lines.append(f"retry_tolerance: {qgl.get('retry_tolerance', 0.0075)}")
            lines.append(f"max_adjust: {qgl.get('max_adjust', 10)}")
        else:
            # Default QGL config based on bed size
            bx, by = int(bed_x), int(bed_y)
            lines.append("gantry_corners:")
            lines.append(f"    -60, -10")
            lines.append(f"    {bx + 60}, {by + 70}")
            lines.append("points:")
            lines.append(f"    50, 25")
            lines.append(f"    50, {by - 75}")
            lines.append(f"    {bx - 50}, {by - 75}")
            lines.append(f"    {bx - 50}, 25")
            lines.append("speed: 200")
            lines.append("horizontal_move_z: 10")
            lines.append("retries: 5")
            lines.append("retry_tolerance: 0.0075")
            lines.append("max_adjust: 10")
        lines.append("")

    elif leveling_method == 'z_tilt' or z_count == 3:
        lines.append("# " + "─" * 77)
        lines.append("# Z TILT ADJUST")
        lines.append("# " + "─" * 77)
        lines.append("[z_tilt]")
        bx, by = int(bed_x), int(bed_y)
        # Default 3-point Z tilt
        lines.append("z_positions:")
        lines.append(f"    {bx // 2}, {by + 50}   # Front center")
        lines.append(f"    0, -50               # Back left")
        lines.append(f"    {bx}, -50            # Back right")
        lines.append("points:")
        lines.append(f"    {bx // 2}, {by - 30}")
        lines.append(f"    30, 30")
        lines.append(f"    {bx - 30}, 30")
        lines.append("speed: 200")
        lines.append("horizontal_move_z: 10")
        lines.append("retries: 5")
        lines.append("retry_tolerance: 0.0075")
        lines.append("")

    elif leveling_method == 'bed_tilt' or z_count == 2:
        lines.append("# " + "─" * 77)
        lines.append("# BED TILT (2 Z motors)")
        lines.append("# " + "─" * 77)
        lines.append("[z_tilt]")
        bx, by = int(bed_x), int(bed_y)
        lines.append("z_positions:")
        lines.append(f"    0, {by // 2}")
        lines.append(f"    {bx}, {by // 2}")
        lines.append("points:")
        lines.append(f"    30, {by // 2}")
        lines.append(f"    {bx - 30}, {by // 2}")
        lines.append("speed: 200")
        lines.append("horizontal_move_z: 10")
        lines.append("retries: 5")
        lines.append("retry_tolerance: 0.0075")
        lines.append("")

    # Lighting configuration
    lighting_type = wizard_state.get('lighting_type', '')
    caselight_type = wizard_state.get('caselight_type', '')
    lighting_count = wizard_state.get('lighting_count') or '1'
    lighting_color_order = wizard_state.get('lighting_color_order') or 'GRB'
    has_leds = wizard_state.get('has_leds', '')
    has_caselight = wizard_state.get('has_caselight', '')

    # Get lighting pins from hardware state (user-selected pins)
    lighting_pin = assignments.get('lighting_pin', '')
    tb_lighting_pin = tb_assignments.get('lighting_pin', '')
    caselight_pin = assignments.get('caselight_pin', '')

    # Check for toolboard RGB LEDs (fallback if no user selection)
    toolboard_rgb = None
    if toolboard:
        misc_ports = toolboard.get('misc_ports', {})
        if 'RGB' in misc_ports:
            toolboard_rgb = misc_ports['RGB']

    # Check for mainboard RGB port (fallback if no user selection)
    mainboard_rgb = None
    if board:
        board_misc = board.get('misc_ports', {})
        if 'RGB' in board_misc:
            mainboard_rgb = board_misc['RGB']

    if (lighting_type and lighting_type != 'none') or has_leds == 'yes' or has_caselight == 'yes':
        lines.append("# " + "─" * 77)
        lines.append("# LIGHTING")
        lines.append("# " + "─" * 77)

        # Status LEDs (toolhead neopixels)
        if has_leds == 'yes' or lighting_type == 'neopixel':
            # Priority: 1) User-selected toolboard pin, 2) User-selected mainboard pin,
            #           3) Toolboard RGB from template, 4) REPLACE_PIN
            if tb_lighting_pin:
                # User selected a toolboard pin
                # Extract just the pin from format like "RGB:gpio7" or "manual:PD15"
                pin_parts = tb_lighting_pin.split(':')
                pin = pin_parts[1] if len(pin_parts) > 1 else tb_lighting_pin
                lines.append("[neopixel status_led]")
                lines.append(f"pin: toolboard:{pin}")
                # Use toolboard RGB settings if available for chain_count/color_order
                if toolboard_rgb:
                    rgb_count = toolboard_rgb.get('chain_count', 3)
                    rgb_order = toolboard_rgb.get('color_order', 'GRB')
                    lines.append(f"chain_count: {rgb_count}")
                    lines.append(f"color_order: {rgb_order}")
                else:
                    lines.append(f"chain_count: {lighting_count}")
                    lines.append(f"color_order: {lighting_color_order}")
            elif lighting_pin:
                # User selected a mainboard pin
                # Extract just the pin from format like "FAN0:PA8" or "manual:PD15"
                pin_parts = lighting_pin.split(':')
                pin = pin_parts[1] if len(pin_parts) > 1 else lighting_pin
                lines.append("[neopixel status_led]")
                lines.append(f"pin: {pin}")
                lines.append(f"chain_count: {lighting_count}")
                lines.append(f"color_order: {lighting_color_order}")
            elif toolboard_rgb and toolboard_rgb.get('pin'):
                # Fall back to toolboard RGB from template (if pin exists)
                rgb_pin = toolboard_rgb['pin']
                rgb_count = toolboard_rgb.get('chain_count', 3)
                rgb_order = toolboard_rgb.get('color_order', 'GRB')
                lines.append("[neopixel status_led]")
                lines.append(f"pin: toolboard:{rgb_pin}")
                lines.append(f"chain_count: {rgb_count}")
                lines.append(f"color_order: {rgb_order}")
                lines.append("initial_RED: 0.2")
                lines.append("initial_GREEN: 0.2")
                lines.append("initial_BLUE: 0.2")
                lines.append("")
            # If no valid pin source, skip LED section - user must configure in Hardware Setup

        # Case lighting (mainboard RGB or simple LED)
        if has_caselight == 'yes':
            # Priority: 1) User-selected caselight pin, 2) Mainboard RGB from template
            if caselight_pin:
                # User selected a caselight pin
                pin_parts = caselight_pin.split(':')
                pin = pin_parts[1] if len(pin_parts) > 1 else caselight_pin
                if caselight_type == 'neopixel':
                    lines.append("[neopixel caselight]")
                    lines.append(f"pin: {pin}")
                    lines.append("chain_count: 10  # Adjust for your LED strip")
                    lines.append("color_order: GRB")
                    lines.append("initial_RED: 1.0")
                    lines.append("initial_GREEN: 1.0")
                    lines.append("initial_BLUE: 1.0")
                else:
                    # Simple PWM LED
                    lines.append("[output_pin caselight]")
                    lines.append(f"pin: {pin}  # Case light pin")
                    lines.append("pwm: True")
                    lines.append("value: 0.5")
                    lines.append("cycle_time: 0.01")
                lines.append("")
            elif mainboard_rgb and mainboard_rgb.get('pin') and caselight_type == 'neopixel':
                rgb_pin = mainboard_rgb['pin']
                rgb_count = mainboard_rgb.get('chain_count', 10)
                rgb_order = mainboard_rgb.get('color_order', 'GRB')
                lines.append("[neopixel caselight]")
                lines.append(f"pin: {rgb_pin}")
                lines.append(f"chain_count: {rgb_count}  # Adjust for your LED strip")
                lines.append(f"color_order: {rgb_order}")
                lines.append("initial_RED: 1.0")
                lines.append("initial_GREEN: 1.0")
                lines.append("initial_BLUE: 1.0")
                lines.append("")
            # If no valid pin, skip caselight section - user must configure in Hardware Setup

        # Dotstar (SPI LEDs) - requires manual pin configuration
        # Skip if lighting_type == 'dotstar' since pins aren't assignable in wizard yet
        # User would need to add [dotstar] section manually with their data_pin and clock_pin

    # Filament sensor configuration
    has_filament_sensor = wizard_state.get('has_filament_sensor', '')
    filament_sensor_type = wizard_state.get('filament_sensor_type', 'switch')
    # Try hardware assignments first, then wizard state
    filament_port = assignments.get('filament_sensor', '')
    if filament_port:
        filament_sensor_pin = get_endstop_pin(board, filament_port)
    else:
        filament_sensor_pin = wizard_state.get('filament_sensor_pin', '')

    # Pin modifiers (Klipper): ^ (pull-up), ~ (pull-down), ! (invert)
    # Prefer hardware assignment modifiers if available; otherwise default to pull-up to match previous behavior.
    filament_sensor_mods = (
        assignments.get('filament_sensor_modifiers')
        or wizard_state.get('filament_sensor_modifiers')
        or '^'
    )

    # Only include filament sensor section if pin is configured
    if has_filament_sensor == 'yes' and filament_sensor_pin:
        lines.append("# " + "─" * 77)
        lines.append("# FILAMENT SENSOR")
        lines.append("# " + "─" * 77)

        if filament_sensor_type == 'motion':
            lines.append("[filament_motion_sensor filament_sensor]")
            lines.append(f"switch_pin: {filament_sensor_mods}{filament_sensor_pin}  # {filament_port or 'direct pin'}")
            lines.append("detection_length: 7.0  # Adjust based on your sensor")
            lines.append("extruder: extruder")
        else:
            lines.append("[filament_switch_sensor filament_sensor]")
            lines.append(f"switch_pin: {filament_sensor_mods}{filament_sensor_pin}  # {filament_port or 'direct pin'}")

        lines.append("pause_on_runout: True")
        lines.append("runout_gcode:")
        lines.append("    M600  # Pause for filament change")
        lines.append("insert_gcode:")
        lines.append("    M117 Filament inserted")
        lines.append("")
    # If has_filament_sensor but no pin, skip section - user must assign in Hardware Setup

    # Chamber temperature sensor
    has_chamber_sensor = wizard_state.get('has_chamber_sensor', '')
    chamber_sensor_type = wizard_state.get('chamber_sensor_type') or 'Generic 3950'
    # Try hardware assignments first, then wizard state
    chamber_port = assignments.get('thermistor_chamber', '')
    if chamber_port:
        chamber_sensor_pin = get_thermistor_pin(board, chamber_port)
    else:
        chamber_sensor_pin = wizard_state.get('chamber_sensor_pin', '')

    # Only include chamber sensor section if pin is configured
    if has_chamber_sensor == 'yes' and chamber_sensor_pin:
        lines.append("# " + "─" * 77)
        lines.append("# CHAMBER SENSOR")
        lines.append("# " + "─" * 77)
        lines.append("[temperature_sensor chamber]")
        lines.append(f"sensor_type: {chamber_sensor_type}")
        lines.append(f"sensor_pin: {chamber_sensor_pin}  # {chamber_port or 'direct pin'}")
        lines.append("min_temp: 0")
        lines.append("max_temp: 80")
        lines.append("gcode_id: C")
        lines.append("")
    # If has_chamber_sensor but no pin, skip section - user must assign in Hardware Setup

    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════════════════════════
# CALIBRATION CONFIG GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_calibration_cfg(wizard_state: Dict, hardware_state: Dict) -> str:
    """Generate calibration.cfg with stepper identification and direction test macros."""

    kinematics = wizard_state.get('kinematics', 'corexy')
    is_awd = kinematics == 'corexy-awd'
    z_count = int(wizard_state.get('z_stepper_count', '1'))
    driver_type = wizard_state.get('driver_X', wizard_state.get('stepper_driver', 'TMC2209'))
    is_tmc = driver_type.upper().startswith('TMC')

    lines = []
    lines.append("# " + "═" * 77)
    lines.append("# STEPPER IDENTIFICATION & CALIBRATION MACROS")
    lines.append(f"# Generated by gschpoozi - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("# " + "═" * 77)
    lines.append("#")
    lines.append("# These macros help you:")
    lines.append("# 1. Identify which physical motor is connected to which driver")
    lines.append("# 2. Verify motor directions are correct")
    if is_awd:
        lines.append("# 3. For CoreXY AWD: Test motor pairs safely without risk of fighting")
    lines.append("#")
    lines.append("# Reference: https://www.klipper3d.org/Config_checks.html")
    lines.append("#            https://mpx.wiki/Troubleshooting/corexy-direction")
    lines.append("# " + "═" * 77)
    lines.append("")

    # Force move section (required for STEPPER_BUZZ and FORCE_MOVE)
    lines.append("[force_move]")
    lines.append("enable_force_move: True")
    lines.append("# Required for STEPPER_BUZZ and FORCE_MOVE commands")
    lines.append("")

    # TMC status query macros (only if using TMC drivers)
    if is_tmc:
        lines.append("# " + "─" * 77)
        lines.append("# TMC DRIVER STATUS")
        lines.append("# " + "─" * 77)
        lines.append("")
        lines.append("[gcode_macro QUERY_TMC_STATUS]")
        lines.append("description: Query TMC driver status for all configured steppers")
        lines.append("gcode:")
        lines.append("    M118 === TMC Driver Status ===")

        # Query each configured stepper
        steppers = ['stepper_x', 'stepper_y']
        if is_awd:
            steppers.extend(['stepper_x1', 'stepper_y1'])
        steppers.append('stepper_z')
        for i in range(1, z_count):
            steppers.append(f'stepper_z{i}')
        steppers.append('extruder')

        for stepper in steppers:
            lines.append(f"    M118 Querying {stepper}...")
            lines.append(f"    DUMP_TMC STEPPER={stepper}")

        lines.append("    M118 === End TMC Status ===")
        lines.append("")

        lines.append("[gcode_macro CHECK_MOTOR_CONNECTED]")
        lines.append("description: Check if a motor appears connected via TMC driver status")
        lines.append("gcode:")
        lines.append('    {% set stepper = params.STEPPER|default("stepper_x") %}')
        lines.append("    M118 Checking {stepper}...")
        lines.append("    DUMP_TMC STEPPER={stepper}")
        lines.append("    M118 Look for 'ola' or 'olb' flags - if set, motor may be disconnected")
        lines.append("")

    # Individual stepper identification
    lines.append("# " + "─" * 77)
    lines.append("# INDIVIDUAL STEPPER IDENTIFICATION")
    lines.append("# " + "─" * 77)
    lines.append("")

    lines.append("[gcode_macro IDENTIFY_STEPPER]")
    lines.append("description: Buzz a single stepper to identify which physical motor it is")
    lines.append("gcode:")
    lines.append('    {% set stepper = params.STEPPER|default("stepper_x") %}')
    lines.append("    M118 === Identifying {stepper} ===")
    lines.append("    M118 Watch which motor moves (10 short buzzes)")
    lines.append("    STEPPER_BUZZ STEPPER={stepper}")
    lines.append("    M118 === Done identifying {stepper} ===")
    lines.append("")

    lines.append("[gcode_macro IDENTIFY_ALL_STEPPERS]")
    lines.append("description: Buzz each stepper one by one with pauses for identification")
    lines.append("gcode:")
    lines.append("    M118 === STEPPER IDENTIFICATION SEQUENCE ===")
    lines.append("    M118 Each stepper will buzz 10 times. Watch and note which motor moves.")
    lines.append("    M118 Starting in 3 seconds...")
    lines.append("    G4 P3000")
    lines.append("")

    # Generate buzz sequence for configured steppers
    lines.append("    M118 >>> STEPPER_X - Watch now...")
    lines.append("    STEPPER_BUZZ STEPPER=stepper_x")
    lines.append("    G4 P2000")
    lines.append("")

    lines.append("    M118 >>> STEPPER_Y - Watch now...")
    lines.append("    STEPPER_BUZZ STEPPER=stepper_y")
    lines.append("    G4 P2000")
    lines.append("")

    if is_awd:
        lines.append("    M118 >>> STEPPER_X1 - Watch now...")
        lines.append("    STEPPER_BUZZ STEPPER=stepper_x1")
        lines.append("    G4 P2000")
        lines.append("")

        lines.append("    M118 >>> STEPPER_Y1 - Watch now...")
        lines.append("    STEPPER_BUZZ STEPPER=stepper_y1")
        lines.append("    G4 P2000")
        lines.append("")

    lines.append("    M118 >>> STEPPER_Z - Watch now...")
    lines.append("    STEPPER_BUZZ STEPPER=stepper_z")
    lines.append("    G4 P2000")
    lines.append("")

    for i in range(1, z_count):
        lines.append(f"    M118 >>> STEPPER_Z{i} - Watch now...")
        lines.append(f"    STEPPER_BUZZ STEPPER=stepper_z{i}")
        lines.append("    G4 P2000")
        lines.append("")

    lines.append("    M118 >>> EXTRUDER - Watch now...")
    lines.append("    STEPPER_BUZZ STEPPER=extruder")
    lines.append("")
    lines.append("    M118 === IDENTIFICATION COMPLETE ===")
    lines.append("")

    # AWD-specific macros
    if is_awd:
        lines.append("# " + "─" * 77)
        lines.append("# COREXY AWD SAFE PAIR TESTING")
        lines.append("# Test one motor pair at a time to prevent motors from fighting")
        lines.append("# " + "─" * 77)
        lines.append("")

        lines.append("[gcode_macro AWD_TEST_PAIR_A]")
        lines.append("description: Test first motor pair (X+Y) with second pair (X1+Y1) disabled")
        lines.append("gcode:")
        lines.append("    {% set distance = params.DISTANCE|default(20)|float %}")
        lines.append("    {% set speed = params.SPEED|default(50)|float %}")
        lines.append("")
        lines.append("    M118 ════════════════════════════════════════════════════════════")
        lines.append("    M118 AWD PAIR A TEST (stepper_x + stepper_y)")
        lines.append("    M118 ════════════════════════════════════════════════════════════")
        lines.append("    M118 This test moves ONLY stepper_x and stepper_y.")
        lines.append("    M118 stepper_x1 and stepper_y1 are DISABLED.")
        lines.append("    M118 The toolhead should move in a square pattern.")
        lines.append("")
        lines.append("    # Disable second pair")
        lines.append("    SET_STEPPER_ENABLE STEPPER=stepper_x1 ENABLE=0")
        lines.append("    SET_STEPPER_ENABLE STEPPER=stepper_y1 ENABLE=0")
        lines.append("")
        lines.append("    # Enable first pair")
        lines.append("    SET_STEPPER_ENABLE STEPPER=stepper_x ENABLE=1")
        lines.append("    SET_STEPPER_ENABLE STEPPER=stepper_y ENABLE=1")
        lines.append("")
        lines.append("    M118 Moving +X...")
        lines.append("    FORCE_MOVE STEPPER=stepper_x DISTANCE={distance} VELOCITY={speed}")
        lines.append("    FORCE_MOVE STEPPER=stepper_y DISTANCE={distance} VELOCITY={speed}")
        lines.append("    G4 P500")
        lines.append("")
        lines.append("    M118 Moving +Y...")
        lines.append("    FORCE_MOVE STEPPER=stepper_x DISTANCE={distance} VELOCITY={speed}")
        lines.append("    FORCE_MOVE STEPPER=stepper_y DISTANCE={-distance} VELOCITY={speed}")
        lines.append("    G4 P500")
        lines.append("")
        lines.append("    M118 Moving -X...")
        lines.append("    FORCE_MOVE STEPPER=stepper_x DISTANCE={-distance} VELOCITY={speed}")
        lines.append("    FORCE_MOVE STEPPER=stepper_y DISTANCE={-distance} VELOCITY={speed}")
        lines.append("    G4 P500")
        lines.append("")
        lines.append("    M118 Moving -Y (back to start)...")
        lines.append("    FORCE_MOVE STEPPER=stepper_x DISTANCE={-distance} VELOCITY={speed}")
        lines.append("    FORCE_MOVE STEPPER=stepper_y DISTANCE={distance} VELOCITY={speed}")
        lines.append("")
        lines.append("    M118 PAIR A TEST COMPLETE")
        lines.append("    M118 Did the toolhead move in a correct square pattern?")
        lines.append("")

        lines.append("[gcode_macro AWD_TEST_PAIR_B]")
        lines.append("description: Test second motor pair (X1+Y1) with first pair (X+Y) disabled")
        lines.append("gcode:")
        lines.append("    {% set distance = params.DISTANCE|default(20)|float %}")
        lines.append("    {% set speed = params.SPEED|default(50)|float %}")
        lines.append("")
        lines.append("    M118 ════════════════════════════════════════════════════════════")
        lines.append("    M118 AWD PAIR B TEST (stepper_x1 + stepper_y1)")
        lines.append("    M118 ════════════════════════════════════════════════════════════")
        lines.append("    M118 This test moves ONLY stepper_x1 and stepper_y1.")
        lines.append("    M118 stepper_x and stepper_y are DISABLED.")
        lines.append("    M118 Should move in the SAME pattern as Pair A.")
        lines.append("")
        lines.append("    # Disable first pair")
        lines.append("    SET_STEPPER_ENABLE STEPPER=stepper_x ENABLE=0")
        lines.append("    SET_STEPPER_ENABLE STEPPER=stepper_y ENABLE=0")
        lines.append("")
        lines.append("    # Enable second pair")
        lines.append("    SET_STEPPER_ENABLE STEPPER=stepper_x1 ENABLE=1")
        lines.append("    SET_STEPPER_ENABLE STEPPER=stepper_y1 ENABLE=1")
        lines.append("")
        lines.append("    M118 Moving +X...")
        lines.append("    FORCE_MOVE STEPPER=stepper_x1 DISTANCE={distance} VELOCITY={speed}")
        lines.append("    FORCE_MOVE STEPPER=stepper_y1 DISTANCE={distance} VELOCITY={speed}")
        lines.append("    G4 P500")
        lines.append("")
        lines.append("    M118 Moving +Y...")
        lines.append("    FORCE_MOVE STEPPER=stepper_x1 DISTANCE={distance} VELOCITY={speed}")
        lines.append("    FORCE_MOVE STEPPER=stepper_y1 DISTANCE={-distance} VELOCITY={speed}")
        lines.append("    G4 P500")
        lines.append("")
        lines.append("    M118 Moving -X...")
        lines.append("    FORCE_MOVE STEPPER=stepper_x1 DISTANCE={-distance} VELOCITY={speed}")
        lines.append("    FORCE_MOVE STEPPER=stepper_y1 DISTANCE={-distance} VELOCITY={speed}")
        lines.append("    G4 P500")
        lines.append("")
        lines.append("    M118 Moving -Y (back to start)...")
        lines.append("    FORCE_MOVE STEPPER=stepper_x1 DISTANCE={-distance} VELOCITY={speed}")
        lines.append("    FORCE_MOVE STEPPER=stepper_y1 DISTANCE={distance} VELOCITY={speed}")
        lines.append("")
        lines.append("    M118 PAIR B TEST COMPLETE")
        lines.append("    M118 Did it move the SAME as Pair A?")
        lines.append("")

        lines.append("[gcode_macro AWD_ENABLE_ALL]")
        lines.append("description: Re-enable all AWD motors after testing")
        lines.append("gcode:")
        lines.append("    M118 Re-enabling all motors...")
        lines.append("    SET_STEPPER_ENABLE STEPPER=stepper_x ENABLE=1")
        lines.append("    SET_STEPPER_ENABLE STEPPER=stepper_y ENABLE=1")
        lines.append("    SET_STEPPER_ENABLE STEPPER=stepper_x1 ENABLE=1")
        lines.append("    SET_STEPPER_ENABLE STEPPER=stepper_y1 ENABLE=1")
        lines.append("    M118 All motors enabled.")
        lines.append("")

        lines.append("[gcode_macro AWD_FULL_TEST]")
        lines.append("description: Run complete AWD motor pair verification sequence")
        lines.append("gcode:")
        lines.append("    {% set distance = params.DISTANCE|default(20)|float %}")
        lines.append("")
        lines.append("    M118 ════════════════════════════════════════════════════════════════════")
        lines.append("    M118 COREXY AWD FULL CALIBRATION SEQUENCE")
        lines.append("    M118 ════════════════════════════════════════════════════════════════════")
        lines.append("    M118 Testing each motor pair separately for safety.")
        lines.append("    M118 If anything looks wrong, use EMERGENCY STOP (M112)!")
        lines.append("    M118 Starting Pair A test in 5 seconds...")
        lines.append("    G4 P5000")
        lines.append("")
        lines.append("    AWD_TEST_PAIR_A DISTANCE={distance}")
        lines.append("")
        lines.append("    M118 Pausing 5 seconds before Pair B test...")
        lines.append("    G4 P5000")
        lines.append("")
        lines.append("    AWD_TEST_PAIR_B DISTANCE={distance}")
        lines.append("")
        lines.append("    AWD_ENABLE_ALL")
        lines.append("")
        lines.append("    M118 ════════════════════════════════════════════════════════════════════")
        lines.append("    M118 AWD CALIBRATION COMPLETE")
        lines.append("    M118 ════════════════════════════════════════════════════════════════════")
        lines.append("    M118 If both pairs moved identically: AWD is correctly configured!")
        lines.append("    M118 If not, see: https://mpx.wiki/Troubleshooting/corexy-direction")
        lines.append("")
    else:
        # Standard CoreXY direction check (non-AWD)
        lines.append("# " + "─" * 77)
        lines.append("# COREXY DIRECTION CHECK")
        lines.append("# " + "─" * 77)
        lines.append("")

        lines.append("[gcode_macro COREXY_DIRECTION_CHECK]")
        lines.append("description: Test CoreXY motor directions (X and Y steppers)")
        lines.append("gcode:")
        lines.append("    {% set distance = params.DISTANCE|default(20)|float %}")
        lines.append("    {% set speed = params.SPEED|default(50)|float %}")
        lines.append("")
        lines.append("    M118 ════════════════════════════════════════════════════════════")
        lines.append("    M118 COREXY DIRECTION CHECK")
        lines.append("    M118 ════════════════════════════════════════════════════════════")
        lines.append("    M118 Watch carefully and verify:")
        lines.append("    M118 - +X command moves toolhead RIGHT")
        lines.append("    M118 - +Y command moves toolhead BACK (away from you)")
        lines.append("    M118 Starting in 3 seconds...")
        lines.append("    G4 P3000")
        lines.append("")
        lines.append("    M118 Moving +X (should go RIGHT)...")
        lines.append("    FORCE_MOVE STEPPER=stepper_x DISTANCE={distance} VELOCITY={speed}")
        lines.append("    FORCE_MOVE STEPPER=stepper_y DISTANCE={distance} VELOCITY={speed}")
        lines.append("    G4 P1000")
        lines.append("")
        lines.append("    M118 Moving +Y (should go BACK)...")
        lines.append("    FORCE_MOVE STEPPER=stepper_x DISTANCE={distance} VELOCITY={speed}")
        lines.append("    FORCE_MOVE STEPPER=stepper_y DISTANCE={-distance} VELOCITY={speed}")
        lines.append("    G4 P1000")
        lines.append("")
        lines.append("    M118 Moving -X (should go LEFT)...")
        lines.append("    FORCE_MOVE STEPPER=stepper_x DISTANCE={-distance} VELOCITY={speed}")
        lines.append("    FORCE_MOVE STEPPER=stepper_y DISTANCE={-distance} VELOCITY={speed}")
        lines.append("    G4 P1000")
        lines.append("")
        lines.append("    M118 Moving -Y (back to start)...")
        lines.append("    FORCE_MOVE STEPPER=stepper_x DISTANCE={-distance} VELOCITY={speed}")
        lines.append("    FORCE_MOVE STEPPER=stepper_y DISTANCE={distance} VELOCITY={speed}")
        lines.append("")
        lines.append("    M118 DIRECTION CHECK COMPLETE")
        lines.append("    M118 See: https://mpx.wiki/Troubleshooting/corexy-direction")
        lines.append("")

    # Z axis verification (always included)
    if z_count > 1:
        lines.append("# " + "─" * 77)
        lines.append("# Z AXIS VERIFICATION")
        lines.append("# " + "─" * 77)
        lines.append("")

        lines.append("[gcode_macro Z_DIRECTION_CHECK]")
        lines.append("description: Verify all Z motors move in the same direction")
        lines.append("gcode:")
        lines.append("    M118 ════════════════════════════════════════════════════════════")
        lines.append("    M118 Z AXIS DIRECTION CHECK")
        lines.append("    M118 ════════════════════════════════════════════════════════════")
        lines.append("    M118 All Z motors will buzz. Verify they ALL move in the SAME direction.")
        lines.append("    M118 Starting in 3 seconds...")
        lines.append("    G4 P3000")
        lines.append("")
        lines.append("    M118 Buzzing stepper_z...")
        lines.append("    STEPPER_BUZZ STEPPER=stepper_z")
        lines.append("    G4 P1000")
        lines.append("")

        for i in range(1, z_count):
            lines.append(f"    M118 Buzzing stepper_z{i}...")
            lines.append(f"    STEPPER_BUZZ STEPPER=stepper_z{i}")
            lines.append("    G4 P1000")
            lines.append("")

        lines.append("    M118 Z DIRECTION CHECK COMPLETE")
        lines.append("    M118 All Z motors should have moved in the same direction.")
        lines.append("")

    # Calibration wizard summary
    lines.append("# " + "─" * 77)
    lines.append("# CALIBRATION WIZARD")
    lines.append("# " + "─" * 77)
    lines.append("")
    lines.append("[gcode_macro STEPPER_CALIBRATION_WIZARD]")
    lines.append("description: Display stepper calibration instructions")
    lines.append("gcode:")
    lines.append("    M118 ════════════════════════════════════════════════════════════════════")
    lines.append("    M118 STEPPER CALIBRATION WIZARD")
    lines.append("    M118 ════════════════════════════════════════════════════════════════════")
    lines.append("    M118")
    lines.append("    M118 STEP 1: MOTOR IDENTIFICATION")
    lines.append("    M118 Run: IDENTIFY_ALL_STEPPERS")
    lines.append("    M118 Watch each motor and note which one corresponds to each name.")
    lines.append("    M118")
    if is_tmc:
        lines.append("    M118 STEP 2: TMC STATUS CHECK")
        lines.append("    M118 Run: QUERY_TMC_STATUS")
        lines.append("    M118 Verify all drivers communicate properly.")
        lines.append("    M118")
    lines.append("    M118 STEP 3: DIRECTION VERIFICATION")
    if is_awd:
        lines.append("    M118 Run: AWD_FULL_TEST")
        lines.append("    M118 Tests each motor pair separately for safety.")
    else:
        lines.append("    M118 Run: COREXY_DIRECTION_CHECK")
        lines.append("    M118 Verify toolhead moves in correct directions.")
    lines.append("    M118")
    if z_count > 1:
        lines.append("    M118 STEP 4: Z AXIS CHECK")
        lines.append("    M118 Run: Z_DIRECTION_CHECK")
        lines.append("    M118 Verify all Z motors move in the same direction.")
        lines.append("    M118")
    lines.append("    M118 ════════════════════════════════════════════════════════════════════")
    lines.append("    M118 References:")
    lines.append("    M118   https://www.klipper3d.org/Config_checks.html")
    lines.append("    M118   https://mpx.wiki/Troubleshooting/corexy-direction")
    lines.append("    M118 ════════════════════════════════════════════════════════════════════")
    lines.append("")

    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════════════════════════
# MACROS CONFIG GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_macros_config_cfg(wizard_state: Dict) -> str:
    """Generate macros-config.cfg with user-editable variables."""

    # Get values from wizard state with defaults
    bed_x = int(wizard_state.get('bed_size_x', '300'))
    bed_y = int(wizard_state.get('bed_size_y', '300'))
    bed_z = int(wizard_state.get('bed_size_z', '350'))
    z_count = int(wizard_state.get('z_stepper_count', '1'))
    probe_type = wizard_state.get('probe_type', 'none')

    # Determine leveling method
    leveling_method = "none"
    if z_count >= 4:
        leveling_method = "quad_gantry_level"
    elif z_count >= 2:
        leveling_method = "z_tilt"

    # Get macro settings from wizard state
    heat_soak_time = int(wizard_state.get('macro_heat_soak_time', '0'))
    if wizard_state.get('macro_heat_soak') != 'yes':
        heat_soak_time = 0

    chamber_temp = int(wizard_state.get('macro_chamber_temp_default', '0'))
    if wizard_state.get('macro_chamber_wait') != 'yes':
        chamber_temp = 0

    bed_mesh_mode = wizard_state.get('macro_bed_mesh_mode', 'adaptive')
    purge_style = wizard_state.get('macro_purge_style', 'line')
    purge_amount = float(wizard_state.get('macro_purge_amount', '30'))

    # Nozzle cleaning
    brush_enabled = wizard_state.get('macro_brush_enabled', 'no') == 'yes'
    brush_x = float(wizard_state.get('macro_brush_x', '50'))
    brush_y = float(wizard_state.get('macro_brush_y', str(bed_y + 5)))
    brush_z = float(wizard_state.get('macro_brush_z', '1'))
    brush_width = float(wizard_state.get('macro_brush_width', '30'))
    wipe_count = int(wizard_state.get('macro_wipe_count', '3'))

    # Bucket for blob purge
    bucket_x = float(wizard_state.get('macro_bucket_x', str(bed_x // 2)))
    bucket_y = float(wizard_state.get('macro_bucket_y', str(bed_y + 5)))
    bucket_z = float(wizard_state.get('macro_bucket_z', '5'))

    # LED status
    led_enabled = wizard_state.get('macro_led_enabled', 'no') == 'yes'
    led_name = wizard_state.get('macro_led_name', 'status_led')

    # Park position
    park_position = wizard_state.get('macro_park_position', 'front')
    park_z_hop = float(wizard_state.get('macro_park_z_hop', '10'))
    park_z_max = float(wizard_state.get('macro_park_z_max', '50'))

    # Cooldown
    cooldown_bed = wizard_state.get('macro_cooldown_bed', 'yes') == 'yes'
    cooldown_extruder = wizard_state.get('macro_cooldown_extruder', 'yes') == 'yes'
    cooldown_fans = wizard_state.get('macro_cooldown_fans', 'no') == 'yes'
    fan_off_delay = int(wizard_state.get('macro_fan_off_delay', '0'))
    motor_off_delay = int(wizard_state.get('macro_motor_off_delay', '300'))

    # Retract
    end_retract_length = float(wizard_state.get('macro_end_retract_length', '10'))
    end_retract_speed = float(wizard_state.get('macro_end_retract_speed', '30'))

    lines = []
    lines.append("# " + "═" * 77)
    lines.append("# MACRO CONFIGURATION")
    lines.append(f"# Generated by gschpoozi - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("# " + "═" * 77)
    lines.append("#")
    lines.append("# Edit these variables to customize macro behavior without")
    lines.append("# modifying the macros themselves.")
    lines.append("#")
    lines.append("# Re-running generate-config.py will overwrite this file!")
    lines.append("# To preserve customizations, copy your settings elsewhere first.")
    lines.append("# " + "═" * 77)
    lines.append("")
    lines.append("[gcode_macro _MACRO_CONFIG]")
    lines.append("description: Configuration variables for START_PRINT and END_PRINT macros")
    lines.append("")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append("# Printer Dimensions (from wizard)")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append(f"variable_bed_size_x: {bed_x}")
    lines.append(f"variable_bed_size_y: {bed_y}")
    lines.append(f"variable_bed_size_z: {bed_z}")
    lines.append(f"variable_bed_center_x: {bed_x // 2}")
    lines.append(f"variable_bed_center_y: {bed_y // 2}")
    lines.append("")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append("# Probe and Leveling")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append(f'variable_probe_type: "{probe_type}"')
    lines.append(f'variable_leveling_method: "{leveling_method}"')
    lines.append(f"variable_leveling_enabled: {'True' if leveling_method != 'none' else 'False'}")
    lines.append(f"variable_z_calibration_enabled: {'True' if probe_type in ['beacon', 'cartographer', 'btt-eddy', 'voron-tap'] else 'False'}")
    lines.append(f"variable_always_home_z: False  # Re-home Z even if already homed")
    lines.append("")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append("# Heat Soak")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append(f"variable_heat_soak_time: {heat_soak_time}  # Minutes to soak after bed reaches temp (0=disabled)")
    lines.append("")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append("# Chamber Heating")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append(f"variable_chamber_temp_default: {chamber_temp}  # Default chamber temp (0=skip)")
    lines.append("")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append("# Bed Mesh")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append(f'variable_bed_mesh_mode: "{bed_mesh_mode}"  # adaptive/full/saved/none')
    lines.append("")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append("# Nozzle Cleaning (Brush)")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append(f"variable_brush_enabled: {'True' if brush_enabled else 'False'}")
    lines.append(f"variable_brush_x: {brush_x}")
    lines.append(f"variable_brush_y: {brush_y}")
    lines.append(f"variable_brush_z: {brush_z}")
    lines.append(f"variable_brush_width: {brush_width}")
    lines.append(f"variable_wipe_count: {wipe_count}")
    lines.append("")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append("# Purge Settings")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append(f'variable_purge_style: "{purge_style}"  # line/blob/adaptive/voron/none')
    lines.append(f"variable_purge_amount: {purge_amount}  # mm of filament to purge")
    lines.append(f"variable_purge_x: 5  # Line purge X start position")
    lines.append(f"variable_purge_y: 5  # Line purge Y start position")
    lines.append("")
    lines.append("# Bucket (for blob/voron purge)")
    lines.append(f"variable_bucket_x: {bucket_x}")
    lines.append(f"variable_bucket_y: {bucket_y}")
    lines.append(f"variable_bucket_z: {bucket_z}")
    lines.append("")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append("# LED Status")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append(f"variable_led_enabled: {'True' if led_enabled else 'False'}")
    lines.append(f'variable_led_name: "{led_name}"  # Name of your [neopixel] section')
    lines.append("")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append("# Park Position (END_PRINT)")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append(f'variable_park_position: "{park_position}"  # front/back/center/front_left/etc')
    lines.append(f"variable_park_z_hop: {park_z_hop}  # Z hop before parking")
    lines.append(f"variable_park_z_max: {park_z_max}  # Max Z height for parking")
    lines.append("")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append("# Cooldown (END_PRINT)")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append(f"variable_turn_off_bed: {'True' if cooldown_bed else 'False'}")
    lines.append(f"variable_turn_off_extruder: {'True' if cooldown_extruder else 'False'}")
    lines.append(f"variable_turn_off_fans: {'True' if cooldown_fans else 'False'}")
    lines.append(f"variable_fan_off_delay: {fan_off_delay}  # Seconds before turning off fans")
    lines.append(f"variable_motor_off_delay: {motor_off_delay}  # Seconds before disabling motors")
    lines.append("")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append("# Retract (END_PRINT)")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append(f"variable_end_retract_length: {end_retract_length}  # mm to retract at end")
    lines.append(f"variable_end_retract_speed: {end_retract_speed}  # mm/s retract speed")
    lines.append("")
    lines.append("# Dummy gcode (required by Klipper)")
    lines.append("gcode:")
    lines.append("    # This macro only holds variables, no gcode")
    lines.append("")

    return "\n".join(lines)


def generate_macros_cfg(wizard_state: Dict) -> str:
    """Generate macros.cfg with START_PRINT, END_PRINT, and building block macros."""

    # Get configuration from wizard state
    bed_x = int(wizard_state.get('bed_size_x', '300'))
    bed_y = int(wizard_state.get('bed_size_y', '300'))
    probe_type = wizard_state.get('probe_type', 'none')
    z_count = int(wizard_state.get('z_stepper_count', '1'))

    lines = []
    lines.append("# " + "═" * 77)
    lines.append("# MACROS")
    lines.append(f"# Generated by gschpoozi - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("# " + "═" * 77)
    lines.append("#")
    lines.append("# These macros use variables from macros-config.cfg")
    lines.append("# Edit macros-config.cfg to customize behavior.")
    lines.append("#")
    lines.append("# Slicer start G-code:")
    lines.append("#   START_PRINT BED=60 EXTRUDER=200")
    lines.append("#   START_PRINT BED=110 EXTRUDER=250 CHAMBER=50 MATERIAL=ABS")
    lines.append("#")
    lines.append("# Slicer end G-code:")
    lines.append("#   END_PRINT")
    lines.append("# " + "═" * 77)
    lines.append("")

    # Required sections for Mainsail/Fluidd
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append("# MAINSAIL / FLUIDD REQUIRED SECTIONS")
    lines.append("# ─────────────────────────────────────────────────────────────────────────────")
    lines.append("[virtual_sdcard]")
    lines.append("path: ~/printer_data/gcodes")
    lines.append("on_error_gcode: CANCEL_PRINT")
    lines.append("")
    lines.append("[display_status]")
    lines.append("# Required for M117 messages and print status")
    lines.append("")
    lines.append("[pause_resume]")
    lines.append("# Required for PAUSE/RESUME functionality")
    lines.append("")
    lines.append("[exclude_object]")
    lines.append("# Required for object cancellation in Mainsail/Fluidd")
    lines.append("")
    lines.append("[respond]")
    lines.append("# Required for M118 messages")
    lines.append("")

    # START_PRINT macro
    lines.append("# ═══════════════════════════════════════════════════════════════════════════════")
    lines.append("# START_PRINT")
    lines.append("# ═══════════════════════════════════════════════════════════════════════════════")
    lines.append("")
    lines.append("[gcode_macro START_PRINT]")
    lines.append("description: Complete print start sequence with heating, leveling, meshing, and purging")
    lines.append("gcode:")
    lines.append("    # ───────────────────────────────────────────────────────────────────────────")
    lines.append("    # Parse parameters (with defaults from config)")
    lines.append("    # ───────────────────────────────────────────────────────────────────────────")
    lines.append('    {% set cfg = printer["gcode_macro _MACRO_CONFIG"] %}')
    lines.append("    ")
    lines.append("    {% set BED_TEMP = params.BED|default(60)|int %}")
    lines.append("    {% set EXTRUDER_TEMP = params.EXTRUDER|default(200)|int %}")
    lines.append("    {% set CHAMBER_TEMP = params.CHAMBER|default(cfg.chamber_temp_default)|int %}")
    lines.append('    {% set MATERIAL = params.MATERIAL|default("PLA")|upper %}')
    lines.append("    {% set MESH_MODE = params.MESH|default(cfg.bed_mesh_mode)|lower %}")
    lines.append("    {% set PURGE_STYLE = params.PURGE|default(cfg.purge_style)|lower %}")
    lines.append("    ")
    lines.append("    # Preheat extruder to safe probing temp (prevents ooze during mesh)")
    lines.append("    {% set EXTRUDER_PREHEAT = 150 %}")
    lines.append("    ")
    lines.append("    # ───────────────────────────────────────────────────────────────────────────")
    lines.append("    # Phase 1: Start heating and home")
    lines.append("    # ───────────────────────────────────────────────────────────────────────────")
    lines.append("    M117 Heating bed...")
    lines.append("    {% if cfg.led_enabled %}")
    lines.append("    _STATUS_LED STATUS=heating")
    lines.append("    {% endif %}")
    lines.append("    ")
    lines.append("    # Start bed heating (don't wait yet)")
    lines.append("    M140 S{BED_TEMP}")
    lines.append("    ")
    lines.append("    # Preheat extruder to prevent cold ooze (don't wait)")
    lines.append("    M104 S{EXTRUDER_PREHEAT}")
    lines.append("    ")
    lines.append("    # Home if needed")
    lines.append("    _HOME_IF_NEEDED")
    lines.append("    ")
    lines.append("    # ───────────────────────────────────────────────────────────────────────────")
    lines.append("    # Phase 2: Wait for bed and optional heat soak")
    lines.append("    # ───────────────────────────────────────────────────────────────────────────")
    lines.append("    M117 Waiting for bed...")
    lines.append("    M190 S{BED_TEMP}")
    lines.append("    ")
    lines.append("    {% if cfg.heat_soak_time > 0 %}")
    lines.append("    _HEAT_SOAK MINUTES={cfg.heat_soak_time}")
    lines.append("    {% endif %}")
    lines.append("    ")
    lines.append("    # ───────────────────────────────────────────────────────────────────────────")
    lines.append("    # Phase 3: Chamber heating (if configured)")
    lines.append("    # ───────────────────────────────────────────────────────────────────────────")
    lines.append("    {% if CHAMBER_TEMP > 0 %}")
    lines.append("    _CHAMBER_WAIT TEMP={CHAMBER_TEMP}")
    lines.append("    {% endif %}")
    lines.append("    ")
    lines.append("    # ───────────────────────────────────────────────────────────────────────────")
    lines.append("    # Phase 4: Bed leveling")
    lines.append("    # ───────────────────────────────────────────────────────────────────────────")
    lines.append("    {% if cfg.led_enabled %}")
    lines.append("    _STATUS_LED STATUS=leveling")
    lines.append("    {% endif %}")
    lines.append("    ")
    lines.append("    {% if cfg.leveling_enabled %}")
    lines.append("    M117 Leveling bed...")
    lines.append("    _LEVEL_BED")
    lines.append("    {% endif %}")
    lines.append("    ")
    lines.append("    # ───────────────────────────────────────────────────────────────────────────")
    lines.append("    # Phase 5: Bed mesh")
    lines.append("    # ───────────────────────────────────────────────────────────────────────────")
    lines.append("    {% if cfg.led_enabled %}")
    lines.append("    _STATUS_LED STATUS=meshing")
    lines.append("    {% endif %}")
    lines.append("    ")
    lines.append('    {% if MESH_MODE != "none" %}')
    lines.append("    M117 Bed mesh...")
    lines.append("    _BED_MESH MODE={MESH_MODE}")
    lines.append("    {% endif %}")
    lines.append("    ")
    lines.append("    # ───────────────────────────────────────────────────────────────────────────")
    lines.append("    # Phase 6: Heat extruder to print temperature")
    lines.append("    # ───────────────────────────────────────────────────────────────────────────")
    lines.append("    {% if cfg.led_enabled %}")
    lines.append("    _STATUS_LED STATUS=heating")
    lines.append("    {% endif %}")
    lines.append("    ")
    lines.append("    M117 Heating extruder...")
    lines.append("    M109 S{EXTRUDER_TEMP}")
    lines.append("    ")
    lines.append("    # ───────────────────────────────────────────────────────────────────────────")
    lines.append("    # Phase 7: Nozzle cleaning (if enabled)")
    lines.append("    # ───────────────────────────────────────────────────────────────────────────")
    lines.append("    {% if cfg.brush_enabled %}")
    lines.append("    M117 Cleaning nozzle...")
    lines.append("    _CLEAN_NOZZLE")
    lines.append("    {% endif %}")
    lines.append("    ")
    lines.append("    # ───────────────────────────────────────────────────────────────────────────")
    lines.append("    # Phase 8: Purge")
    lines.append("    # ───────────────────────────────────────────────────────────────────────────")
    lines.append('    {% if PURGE_STYLE != "none" %}')
    lines.append("    M117 Purging...")
    lines.append("    _PURGE STYLE={PURGE_STYLE}")
    lines.append("    {% endif %}")
    lines.append("    ")
    lines.append("    # ───────────────────────────────────────────────────────────────────────────")
    lines.append("    # Phase 9: Ready to print")
    lines.append("    # ───────────────────────────────────────────────────────────────────────────")
    lines.append("    {% if cfg.led_enabled %}")
    lines.append("    _STATUS_LED STATUS=printing")
    lines.append("    {% endif %}")
    lines.append("    ")
    lines.append("    M117 Printing...")
    lines.append("    G92 E0  ; Reset extruder")
    lines.append("    G90     ; Absolute positioning")
    lines.append("")

    # END_PRINT macro
    lines.append("# ═══════════════════════════════════════════════════════════════════════════════")
    lines.append("# END_PRINT")
    lines.append("# ═══════════════════════════════════════════════════════════════════════════════")
    lines.append("")
    lines.append("[gcode_macro END_PRINT]")
    lines.append("description: Complete print end sequence with retraction, parking, and cooldown")
    lines.append("gcode:")
    lines.append('    {% set cfg = printer["gcode_macro _MACRO_CONFIG"] %}')
    lines.append("    {% set PARK_POS = params.PARK|default(cfg.park_position)|lower %}")
    lines.append("    ")
    lines.append("    # Turn off heaters first (they take longest to cool)")
    lines.append("    {% if cfg.turn_off_extruder %}")
    lines.append("    M104 S0")
    lines.append("    {% endif %}")
    lines.append("    ")
    lines.append("    {% if cfg.turn_off_bed %}")
    lines.append("    M140 S0")
    lines.append("    {% endif %}")
    lines.append("    ")
    lines.append("    # Retract filament")
    lines.append("    _END_RETRACT")
    lines.append("    ")
    lines.append("    # Park toolhead")
    lines.append("    _PARK POSITION={PARK_POS}")
    lines.append("    ")
    lines.append("    # Fan management")
    lines.append("    {% if cfg.turn_off_fans %}")
    lines.append("        {% if cfg.fan_off_delay > 0 %}")
    lines.append("        UPDATE_DELAYED_GCODE ID=_DELAYED_FAN_OFF DURATION={cfg.fan_off_delay}")
    lines.append("        {% else %}")
    lines.append("        M106 S0")
    lines.append("        {% endif %}")
    lines.append("    {% endif %}")
    lines.append("    ")
    lines.append("    # Status LED")
    lines.append("    {% if cfg.led_enabled %}")
    lines.append("    _STATUS_LED STATUS=complete")
    lines.append("    {% endif %}")
    lines.append("    ")
    lines.append("    # Disable motors (delayed if configured)")
    lines.append("    {% if cfg.motor_off_delay > 0 %}")
    lines.append("    UPDATE_DELAYED_GCODE ID=_DELAYED_MOTOR_OFF DURATION={cfg.motor_off_delay}")
    lines.append("    {% else %}")
    lines.append("    M84")
    lines.append("    {% endif %}")
    lines.append("    ")
    lines.append("    M117 Print complete!")
    lines.append("")

    # Building block macros
    lines.append("# ═══════════════════════════════════════════════════════════════════════════════")
    lines.append("# BUILDING BLOCK MACROS")
    lines.append("# ═══════════════════════════════════════════════════════════════════════════════")
    lines.append("")

    # _HOME_IF_NEEDED
    lines.append("[gcode_macro _HOME_IF_NEEDED]")
    lines.append("description: Home axes only if not already homed")
    lines.append("gcode:")
    lines.append('    {% set cfg = printer["gcode_macro _MACRO_CONFIG"] %}')
    lines.append("    ")
    lines.append("    {% if cfg.led_enabled %}")
    lines.append("    _STATUS_LED STATUS=homing")
    lines.append("    {% endif %}")
    lines.append("    ")
    lines.append("    M117 Homing...")
    lines.append("    ")
    lines.append('    {% if "xyz" not in printer.toolhead.homed_axes %}')
    lines.append("        G28")
    lines.append("    {% else %}")
    lines.append("        {% if cfg.always_home_z %}")
    lines.append("        G28 Z")
    lines.append("        {% endif %}")
    lines.append("    {% endif %}")
    lines.append("")

    # _HEAT_SOAK
    lines.append("[gcode_macro _HEAT_SOAK]")
    lines.append("description: Wait for bed temperature to stabilize")
    lines.append("gcode:")
    lines.append("    {% set MINUTES = params.MINUTES|default(0)|int %}")
    lines.append('    {% set cfg = printer["gcode_macro _MACRO_CONFIG"] %}')
    lines.append("    ")
    lines.append("    {% if MINUTES > 0 %}")
    lines.append("        M117 Heat soak {MINUTES}min...")
    lines.append("        G0 X{cfg.bed_center_x} Y{cfg.bed_center_y} Z30 F6000")
    lines.append("        ")
    lines.append("        {% for i in range(MINUTES) %}")
    lines.append("            M117 Heat soak {MINUTES - i}min remaining...")
    lines.append("            G4 P60000")
    lines.append("        {% endfor %}")
    lines.append("    {% endif %}")
    lines.append("")

    # _CHAMBER_WAIT
    lines.append("[gcode_macro _CHAMBER_WAIT]")
    lines.append("description: Wait for chamber to reach target temperature")
    lines.append("gcode:")
    lines.append("    {% set TEMP = params.TEMP|default(0)|int %}")
    lines.append("    ")
    lines.append("    {% if TEMP > 0 %}")
    lines.append("        M117 Chamber heating to {TEMP}C...")
    lines.append("        ")
    lines.append('        {% if printer["temperature_sensor chamber"] is defined %}')
    lines.append('            TEMPERATURE_WAIT SENSOR="temperature_sensor chamber" MINIMUM={TEMP}')
    lines.append('        {% elif printer["temperature_fan chamber"] is defined %}')
    lines.append("            SET_TEMPERATURE_FAN_TARGET TEMPERATURE_FAN=chamber TARGET={TEMP}")
    lines.append('            TEMPERATURE_WAIT SENSOR="temperature_fan chamber" MINIMUM={TEMP}')
    lines.append("        {% else %}")
    lines.append("            M117 No chamber sensor found")
    lines.append("        {% endif %}")
    lines.append("    {% endif %}")
    lines.append("")

    # _LEVEL_BED
    lines.append("[gcode_macro _LEVEL_BED]")
    lines.append("description: Level bed using QGL or Z_TILT based on configuration")
    lines.append("gcode:")
    lines.append('    {% set cfg = printer["gcode_macro _MACRO_CONFIG"] %}')
    lines.append("    ")
    lines.append('    {% if cfg.leveling_method == "quad_gantry_level" %}')
    lines.append("        {% if printer.quad_gantry_level.applied|lower == 'false' %}")
    lines.append("            QUAD_GANTRY_LEVEL")
    lines.append("        {% endif %}")
    lines.append('    {% elif cfg.leveling_method == "z_tilt" %}')
    lines.append("        {% if printer.z_tilt.applied|lower == 'false' %}")
    lines.append("            Z_TILT_ADJUST")
    lines.append("        {% endif %}")
    lines.append("    {% endif %}")
    lines.append("    ")
    lines.append("    G28 Z")
    lines.append("")

    # _BED_MESH
    lines.append("[gcode_macro _BED_MESH]")
    lines.append("description: Generate or load bed mesh")
    lines.append("gcode:")
    lines.append('    {% set MODE = params.MODE|default("adaptive")|lower %}')
    lines.append('    {% set cfg = printer["gcode_macro _MACRO_CONFIG"] %}')
    lines.append("    ")
    lines.append('    {% if MODE == "none" %}')
    lines.append("        M117 Skipping mesh")
    lines.append('    {% elif MODE == "saved" %}')
    lines.append("        BED_MESH_PROFILE LOAD=default")
    lines.append('    {% elif MODE == "adaptive" %}')

    # Probe-specific mesh commands
    if probe_type in ('beacon', 'cartographer', 'btt-eddy'):
        lines.append("        BED_MESH_CALIBRATE METHOD=rapid_scan")
    else:
        lines.append("        BED_MESH_CALIBRATE ADAPTIVE=1")

    lines.append("    {% else %}")

    if probe_type in ('beacon', 'cartographer', 'btt-eddy'):
        lines.append("        BED_MESH_CALIBRATE METHOD=rapid_scan")
    else:
        lines.append("        BED_MESH_CALIBRATE")

    lines.append("    {% endif %}")
    lines.append("")

    # _CLEAN_NOZZLE
    lines.append("[gcode_macro _CLEAN_NOZZLE]")
    lines.append("description: Clean nozzle at brush station")
    lines.append("gcode:")
    lines.append('    {% set cfg = printer["gcode_macro _MACRO_CONFIG"] %}')
    lines.append("    {% set WIPES = params.WIPES|default(cfg.wipe_count)|int %}")
    lines.append("    ")
    lines.append("    {% if cfg.brush_enabled %}")
    lines.append("        G0 Z{cfg.brush_z + 5} F3000")
    lines.append("        G0 X{cfg.brush_x} Y{cfg.brush_y} F6000")
    lines.append("        G0 Z{cfg.brush_z} F1000")
    lines.append("        ")
    lines.append("        {% for i in range(WIPES) %}")
    lines.append("            G0 X{cfg.brush_x + cfg.brush_width} F3000")
    lines.append("            G0 X{cfg.brush_x} F3000")
    lines.append("        {% endfor %}")
    lines.append("        ")
    lines.append("        G0 Z{cfg.brush_z + 5} F3000")
    lines.append("    {% endif %}")
    lines.append("")

    # _PURGE
    lines.append("[gcode_macro _PURGE]")
    lines.append("description: Purge filament before printing")
    lines.append("gcode:")
    lines.append('    {% set STYLE = params.STYLE|default("line")|lower %}')
    lines.append('    {% set cfg = printer["gcode_macro _MACRO_CONFIG"] %}')
    lines.append("    {% set AMOUNT = params.AMOUNT|default(cfg.purge_amount)|float %}")
    lines.append("    ")
    lines.append('    {% if STYLE == "none" %}')
    lines.append("        # Skip purge")
    lines.append('    {% elif STYLE == "blob" %}')
    lines.append("        _PURGE_BLOB AMOUNT={AMOUNT}")
    lines.append('    {% elif STYLE == "adaptive" %}')
    lines.append("        _PURGE_ADAPTIVE AMOUNT={AMOUNT}")
    lines.append("    {% else %}")
    lines.append("        _PURGE_LINE AMOUNT={AMOUNT}")
    lines.append("    {% endif %}")
    lines.append("")

    # _PURGE_LINE
    lines.append("[gcode_macro _PURGE_LINE]")
    lines.append("description: Simple line purge along bed edge")
    lines.append("gcode:")
    lines.append('    {% set cfg = printer["gcode_macro _MACRO_CONFIG"] %}')
    lines.append("    {% set AMOUNT = params.AMOUNT|default(cfg.purge_amount)|float %}")
    lines.append(f"    {{% set LINE_LENGTH = [AMOUNT * 3, {bed_y - 20}]|min %}}")
    lines.append("    {% set START_X = cfg.purge_x %}")
    lines.append("    {% set START_Y = cfg.purge_y %}")
    lines.append("    ")
    lines.append("    G92 E0")
    lines.append("    G0 Z5 F3000")
    lines.append("    G0 X{START_X} Y{START_Y} F6000")
    lines.append("    G0 Z0.3 F1000")
    lines.append("    G1 Y{START_Y + LINE_LENGTH} E{AMOUNT} F1500")
    lines.append("    G1 E-0.5 F3000")
    lines.append("    G0 Z2 F3000")
    lines.append("    G0 X{START_X + 5} F6000")
    lines.append("    G92 E0")
    lines.append("")

    # _PURGE_BLOB
    lines.append("[gcode_macro _PURGE_BLOB]")
    lines.append("description: Purge blob into bucket")
    lines.append("gcode:")
    lines.append('    {% set cfg = printer["gcode_macro _MACRO_CONFIG"] %}')
    lines.append("    {% set AMOUNT = params.AMOUNT|default(cfg.purge_amount)|float %}")
    lines.append("    ")
    lines.append("    G0 Z10 F3000")
    lines.append("    G0 X{cfg.bucket_x} Y{cfg.bucket_y} F6000")
    lines.append("    G0 Z{cfg.bucket_z} F1000")
    lines.append("    G92 E0")
    lines.append("    G1 E{AMOUNT} F150")
    lines.append("    G1 E-2 F3000")
    lines.append("    G4 P1000")
    lines.append("    G0 Z{cfg.bucket_z + 10} F3000")
    lines.append("    G92 E0")
    lines.append("")

    # _PURGE_ADAPTIVE
    lines.append("[gcode_macro _PURGE_ADAPTIVE]")
    lines.append("description: Adaptive purge near print area")
    lines.append("gcode:")
    lines.append('    {% set cfg = printer["gcode_macro _MACRO_CONFIG"] %}')
    lines.append("    {% set AMOUNT = params.AMOUNT|default(cfg.purge_amount)|float %}")
    lines.append("    ")
    lines.append("    # Fall back to line purge (adaptive requires slicer print bounds)")
    lines.append("    _PURGE_LINE AMOUNT={AMOUNT}")
    lines.append("")

    # _END_RETRACT
    lines.append("[gcode_macro _END_RETRACT]")
    lines.append("description: Retract filament at end of print")
    lines.append("gcode:")
    lines.append('    {% set cfg = printer["gcode_macro _MACRO_CONFIG"] %}')
    lines.append("    ")
    lines.append("    M83")
    lines.append("    G1 E-{cfg.end_retract_length} F{cfg.end_retract_speed * 60}")
    lines.append("    M82")
    lines.append("    G92 E0")
    lines.append("")

    # _PARK
    lines.append("[gcode_macro _PARK]")
    lines.append("description: Park toolhead at specified position")
    lines.append("gcode:")
    lines.append('    {% set cfg = printer["gcode_macro _MACRO_CONFIG"] %}')
    lines.append("    {% set POSITION = params.POSITION|default(cfg.park_position)|lower %}")
    lines.append("    ")
    lines.append("    {% set current_z = printer.toolhead.position.z %}")
    lines.append("    {% set z_max = printer.toolhead.axis_maximum.z %}")
    lines.append("    {% set park_z = [current_z + cfg.park_z_hop, cfg.park_z_max, z_max - 5]|min %}")
    lines.append("    ")
    lines.append("    {% set bed_x = cfg.bed_size_x %}")
    lines.append("    {% set bed_y = cfg.bed_size_y %}")
    lines.append("    ")
    lines.append('    {% if POSITION == "front" %}')
    lines.append("        {% set park_x = bed_x / 2 %}")
    lines.append("        {% set park_y = 10 %}")
    lines.append('    {% elif POSITION == "back" %}')
    lines.append("        {% set park_x = bed_x / 2 %}")
    lines.append("        {% set park_y = bed_y - 10 %}")
    lines.append('    {% elif POSITION == "center" %}')
    lines.append("        {% set park_x = bed_x / 2 %}")
    lines.append("        {% set park_y = bed_y / 2 %}")
    lines.append('    {% elif POSITION == "front_left" %}')
    lines.append("        {% set park_x = 10 %}")
    lines.append("        {% set park_y = 10 %}")
    lines.append('    {% elif POSITION == "front_right" %}')
    lines.append("        {% set park_x = bed_x - 10 %}")
    lines.append("        {% set park_y = 10 %}")
    lines.append('    {% elif POSITION == "back_left" %}')
    lines.append("        {% set park_x = 10 %}")
    lines.append("        {% set park_y = bed_y - 10 %}")
    lines.append('    {% elif POSITION == "back_right" %}')
    lines.append("        {% set park_x = bed_x - 10 %}")
    lines.append("        {% set park_y = bed_y - 10 %}")
    lines.append("    {% else %}")
    lines.append("        {% set park_x = bed_x / 2 %}")
    lines.append("        {% set park_y = 10 %}")
    lines.append("    {% endif %}")
    lines.append("    ")
    lines.append("    G90")
    lines.append("    G0 Z{park_z} F3000")
    lines.append("    G0 X{park_x} Y{park_y} F6000")
    lines.append("")

    # _STATUS_LED
    lines.append("[gcode_macro _STATUS_LED]")
    lines.append("description: Update LED status color")
    lines.append("gcode:")
    lines.append('    {% set STATUS = params.STATUS|default("ready")|lower %}')
    lines.append('    {% set cfg = printer["gcode_macro _MACRO_CONFIG"] %}')
    lines.append("    ")
    lines.append("    {% if cfg.led_enabled %}")
    lines.append("        {% set colors = {")
    lines.append('            "heating":  {"r": 1.0, "g": 0.2, "b": 0.0},')
    lines.append('            "homing":   {"r": 0.0, "g": 0.5, "b": 1.0},')
    lines.append('            "leveling": {"r": 0.5, "g": 0.0, "b": 1.0},')
    lines.append('            "meshing":  {"r": 0.0, "g": 1.0, "b": 0.5},')
    lines.append('            "printing": {"r": 1.0, "g": 1.0, "b": 1.0},')
    lines.append('            "complete": {"r": 0.0, "g": 1.0, "b": 0.0},')
    lines.append('            "error":    {"r": 1.0, "g": 0.0, "b": 0.0},')
    lines.append('            "ready":    {"r": 0.2, "g": 0.2, "b": 0.2}')
    lines.append("        } %}")
    lines.append("        ")
    lines.append('        {% set c = colors[STATUS] if STATUS in colors else colors["ready"] %}')
    lines.append("        SET_LED LED={cfg.led_name} RED={c.r} GREEN={c.g} BLUE={c.b}")
    lines.append("    {% endif %}")
    lines.append("")

    # Delayed gcode macros
    lines.append("[delayed_gcode _DELAYED_FAN_OFF]")
    lines.append("gcode:")
    lines.append("    M106 S0")
    lines.append("")
    lines.append("[delayed_gcode _DELAYED_MOTOR_OFF]")
    lines.append("gcode:")
    lines.append("    M84")
    lines.append("")

    # CANCEL_PRINT
    lines.append("# ═══════════════════════════════════════════════════════════════════════════════")
    lines.append("# UTILITY MACROS")
    lines.append("# ═══════════════════════════════════════════════════════════════════════════════")
    lines.append("")
    lines.append("[gcode_macro CANCEL_PRINT]")
    lines.append("description: Cancel the running print")
    lines.append("rename_existing: CANCEL_PRINT_BASE")
    lines.append("gcode:")
    lines.append('    {% set cfg = printer["gcode_macro _MACRO_CONFIG"] %}')
    lines.append("    ")
    lines.append("    M104 S0")
    lines.append("    M140 S0")
    lines.append("    _END_RETRACT")
    lines.append("    _PARK POSITION={cfg.park_position}")
    lines.append("    M106 S0")
    lines.append("    ")
    lines.append("    {% if cfg.led_enabled %}")
    lines.append("    _STATUS_LED STATUS=error")
    lines.append("    {% endif %}")
    lines.append("    ")
    lines.append("    CANCEL_PRINT_BASE")
    lines.append("    M117 Print cancelled")
    lines.append("")

    # PAUSE
    lines.append("[gcode_macro PAUSE]")
    lines.append("description: Pause the running print")
    lines.append("rename_existing: PAUSE_BASE")
    lines.append("variable_extrude: 1.0")
    lines.append("gcode:")
    lines.append('    {% set cfg = printer["gcode_macro _MACRO_CONFIG"] %}')
    lines.append('    {% set E = printer["gcode_macro PAUSE"].extrude|float %}')
    lines.append("    ")
    lines.append("    SAVE_GCODE_STATE NAME=PAUSE_state")
    lines.append("    M83")
    lines.append("    G1 E-{E} F2100")
    lines.append("    _PARK POSITION={cfg.park_position}")
    lines.append("    PAUSE_BASE")
    lines.append("    M117 Print paused")
    lines.append("")

    # RESUME
    lines.append("[gcode_macro RESUME]")
    lines.append("description: Resume the paused print")
    lines.append("rename_existing: RESUME_BASE")
    lines.append("gcode:")
    lines.append('    {% set E = printer["gcode_macro PAUSE"].extrude|float %}')
    lines.append("    ")
    lines.append("    M83")
    lines.append("    G1 E{E} F2100")
    lines.append("    RESTORE_GCODE_STATE NAME=PAUSE_state MOVE=1 MOVE_SPEED=100")
    lines.append("    RESUME_BASE")
    lines.append("    M117 Printing...")
    lines.append("")

    # M600 Filament Change
    lines.append("[gcode_macro M600]")
    lines.append("description: Filament change")
    lines.append("gcode:")
    lines.append('    {% set cfg = printer["gcode_macro _MACRO_CONFIG"] %}')
    lines.append("    ")
    lines.append("    M117 Filament change...")
    lines.append("    PAUSE")
    lines.append("    ")
    lines.append("    {% if cfg.led_enabled %}")
    lines.append("    _STATUS_LED STATUS=error")
    lines.append("    {% endif %}")
    lines.append("    ")
    lines.append("    M83")
    lines.append("    G1 E-50 F1800")
    lines.append("    M117 Load new filament and RESUME")
    lines.append("")

    # LOAD/UNLOAD filament
    lines.append("[gcode_macro LOAD_FILAMENT]")
    lines.append("description: Load filament into the extruder")
    lines.append("gcode:")
    lines.append("    {% set TEMP = params.TEMP|default(220)|float %}")
    lines.append("    {% set LENGTH = params.LENGTH|default(100)|float %}")
    lines.append("    ")
    lines.append("    M109 S{TEMP}")
    lines.append("    M83")
    lines.append("    G1 E{LENGTH} F300")
    lines.append("    M82")
    lines.append("    M104 S0")
    lines.append("")

    lines.append("[gcode_macro UNLOAD_FILAMENT]")
    lines.append("description: Unload filament from the extruder")
    lines.append("gcode:")
    lines.append("    {% set TEMP = params.TEMP|default(220)|float %}")
    lines.append("    {% set LENGTH = params.LENGTH|default(100)|float %}")
    lines.append("    ")
    lines.append("    M109 S{TEMP}")
    lines.append("    M83")
    lines.append("    G1 E10 F300")
    lines.append("    G1 E-{LENGTH} F1800")
    lines.append("    M82")
    lines.append("    M104 S0")
    lines.append("")

    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Generate Klipper config files')
    parser.add_argument('--output-dir', type=str, required=True, help='Output directory')
    parser.add_argument('--hardware-only', action='store_true', help='Generate only hardware.cfg')
    parser.add_argument('--calibration-only', action='store_true', help='Generate only calibration.cfg')
    parser.add_argument('--macros-only', action='store_true', help='Generate only macros.cfg and macros-config.cfg')

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load state
    wizard_state = load_wizard_state()
    hardware_state = load_hardware_state()

    board_id = hardware_state.get('board_id')
    if not board_id:
        print("Error: No board selected. Run setup-hardware.py first.", file=sys.stderr)
        sys.exit(1)

    board = load_board_template(board_id)
    if not board:
        print(f"Error: Board template not found: {board_id}", file=sys.stderr)
        sys.exit(1)

    toolboard_id = hardware_state.get('toolboard_id')
    toolboard = load_toolboard_template(toolboard_id)

    # Generate hardware.cfg (unless calibration-only or macros-only)
    if not args.calibration_only and not args.macros_only:
        hardware_cfg = generate_hardware_cfg(wizard_state, hardware_state, board, toolboard)

        output_file = output_dir / "hardware.cfg"
        with open(output_file, 'w') as f:
            f.write(hardware_cfg)

        print(f"Generated: {output_file}")

    # Generate calibration.cfg (unless hardware-only or macros-only)
    if not args.hardware_only and not args.macros_only:
        calibration_cfg = generate_calibration_cfg(wizard_state, hardware_state)

        output_file = output_dir / "calibration.cfg"
        with open(output_file, 'w') as f:
            f.write(calibration_cfg)

        print(f"Generated: {output_file}")

    # Generate macros.cfg and macros-config.cfg (unless hardware-only or calibration-only)
    if not args.hardware_only and not args.calibration_only:
        # Generate macros-config.cfg (user-editable variables)
        macros_config_cfg = generate_macros_config_cfg(wizard_state)
        output_file = output_dir / "macros-config.cfg"
        with open(output_file, 'w') as f:
            f.write(macros_config_cfg)
        print(f"Generated: {output_file}")

        # Generate macros.cfg (the actual macros)
        macros_cfg = generate_macros_cfg(wizard_state)
        output_file = output_dir / "macros.cfg"
        with open(output_file, 'w') as f:
            f.write(macros_cfg)
        print(f"Generated: {output_file}")

if __name__ == '__main__':
    main()

