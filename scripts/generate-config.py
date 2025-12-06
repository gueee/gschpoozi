#!/usr/bin/env python3
"""
gschpoozi Configuration Generator
Generates Klipper config files from wizard state and hardware assignments

Usage:
    ./generate-config.py --output-dir ~/printer_data/config/gschpoozi

https://github.com/gueee/gschpoozi
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
    }

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
    """Get endstop pin for a given port."""
    endstop_ports = board.get('endstop_ports', {})
    port = endstop_ports.get(port_name, {})
    return port.get('pin', 'REPLACE_PIN')

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_hardware_cfg(
    wizard_state: Dict,
    hardware_state: Dict,
    board: Dict,
    toolboard: Optional[Dict] = None
) -> str:
    """Generate hardware.cfg content."""
    
    assignments = hardware_state.get('port_assignments', {})
    board_name = hardware_state.get('board_name', 'Unknown')
    
    # Get values from wizard state
    kinematics = wizard_state.get('kinematics', 'corexy')
    bed_x = wizard_state.get('bed_size_x', '300')
    bed_y = wizard_state.get('bed_size_y', '300')
    bed_z = wizard_state.get('bed_size_z', '350')
    z_count = int(wizard_state.get('z_stepper_count', '1'))
    hotend_therm = wizard_state.get('hotend_thermistor', 'Generic 3950')
    hotend_pullup = wizard_state.get('hotend_pullup_resistor', '')
    bed_therm = wizard_state.get('bed_thermistor', 'Generic 3950')
    
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
    
    # Use stored serial if available, otherwise placeholder
    mcu_serial = hardware_state.get('mcu_serial')
    if mcu_serial:
        lines.append(f"serial: {mcu_serial}")
    else:
        lines.append("serial: /dev/serial/by-id/REPLACE_WITH_YOUR_MCU_ID")
        lines.append("# Run: ls /dev/serial/by-id/* to find your MCU")
    lines.append("")
    
    # Toolboard MCU if present
    if toolboard:
        tb_name = hardware_state.get('toolboard_name', 'Toolboard')
        tb_connection = toolboard.get('connection', 'USB').upper()
        lines.append(f"[mcu toolboard]")
        
        if tb_connection == 'CAN':
            # Use stored canbus_uuid if available
            canbus_uuid = hardware_state.get('toolboard_canbus_uuid')
            if canbus_uuid:
                lines.append(f"canbus_uuid: {canbus_uuid}")
            else:
                lines.append("canbus_uuid: REPLACE_WITH_CANBUS_UUID")
                lines.append("# Run: ~/klippy-env/bin/python ~/klipper/scripts/canbus_query.py can0")
                lines.append("# to find your toolboard's canbus_uuid")
        else:
            # Use stored serial if available
            tb_serial = hardware_state.get('toolboard_serial')
            if tb_serial:
                lines.append(f"serial: {tb_serial}")
            else:
                lines.append("serial: /dev/serial/by-id/REPLACE_WITH_TOOLBOARD_ID")
                lines.append("# Run: ls /dev/serial/by-id/* to find your toolboard")
        
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
    lines.append(f"[stepper_x]")
    lines.append(f"step_pin: {x_pins['step_pin']}      # {x_port}")
    lines.append(f"dir_pin: {x_pins['dir_pin']}       # {x_port}")
    lines.append(f"enable_pin: !{x_pins['enable_pin']}  # {x_port}")
    lines.append("microsteps: 16")
    lines.append("rotation_distance: 40")
    
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
    else:
        lines.append(f"endstop_pin: ^REPLACE_PIN  # Configure X endstop port")
    
    # Homing position - check wizard state for endstop location
    x_home = wizard_state.get('home_x', 'max')  # 'min' or 'max'
    if x_home == 'min':
        lines.append("position_min: 0")
        lines.append(f"position_max: {bed_x}")
        lines.append("position_endstop: 0")
    else:
        lines.append("position_min: 0")
        lines.append(f"position_max: {bed_x}")
        lines.append(f"position_endstop: {bed_x}")
    lines.append("homing_speed: 80")
    lines.append("homing_retract_dist: 5")
    lines.append("")
    
    # Stepper Y
    y_port = assignments.get('stepper_y', 'MOTOR_1')
    y_pins = get_motor_pins(board, y_port)
    lines.append(f"[stepper_y]")
    lines.append(f"step_pin: {y_pins['step_pin']}      # {y_port}")
    lines.append(f"dir_pin: {y_pins['dir_pin']}       # {y_port}")
    lines.append(f"enable_pin: !{y_pins['enable_pin']}  # {y_port}")
    lines.append("microsteps: 16")
    lines.append("rotation_distance: 40")
    
    y_endstop = assignments.get('endstop_y', '')
    if y_endstop == 'sensorless':
        lines.append(f"endstop_pin: tmc2209_stepper_y:virtual_endstop  # Sensorless homing")
    elif y_endstop:
        endstop_pin = get_endstop_pin(board, y_endstop)
        lines.append(f"endstop_pin: ^{endstop_pin}  # {y_endstop}")
    else:
        lines.append(f"endstop_pin: ^REPLACE_PIN  # Configure Y endstop port")
    
    # Homing position - check wizard state for endstop location
    y_home = wizard_state.get('home_y', 'max')  # 'min' or 'max'
    if y_home == 'min':
        lines.append("position_min: 0")
        lines.append(f"position_max: {bed_y}")
        lines.append("position_endstop: 0")
    else:
        lines.append("position_min: 0")
        lines.append(f"position_max: {bed_y}")
        lines.append(f"position_endstop: {bed_y}")
    lines.append("homing_speed: 80")
    lines.append("homing_retract_dist: 5")
    lines.append("")
    
    # AWD: Add X1 and Y1 steppers
    if kinematics == 'corexy-awd':
        x1_port = assignments.get('stepper_x1', 'MOTOR_2')
        x1_pins = get_motor_pins(board, x1_port)
        lines.append(f"[stepper_x1]")
        lines.append(f"step_pin: {x1_pins['step_pin']}      # {x1_port}")
        lines.append(f"dir_pin: {x1_pins['dir_pin']}       # {x1_port}")
        lines.append(f"enable_pin: !{x1_pins['enable_pin']}  # {x1_port}")
        lines.append("microsteps: 16")
        lines.append("rotation_distance: 40")
        lines.append("")
        
        y1_port = assignments.get('stepper_y1', 'MOTOR_3')
        y1_pins = get_motor_pins(board, y1_port)
        lines.append(f"[stepper_y1]")
        lines.append(f"step_pin: {y1_pins['step_pin']}      # {y1_port}")
        lines.append(f"dir_pin: {y1_pins['dir_pin']}       # {y1_port}")
        lines.append(f"enable_pin: !{y1_pins['enable_pin']}  # {y1_port}")
        lines.append("microsteps: 16")
        lines.append("rotation_distance: 40")
        lines.append("")
    
    # Stepper Z (and Z1, Z2, Z3 if multi-Z)
    for z_idx in range(z_count):
        suffix = "" if z_idx == 0 else str(z_idx)
        z_key = f"stepper_z{suffix}" if suffix else "stepper_z"
        z_port = assignments.get(z_key, f'MOTOR_{2 + z_idx}')
        z_pins = get_motor_pins(board, z_port)
        
        section_name = f"stepper_z{suffix}"
        lines.append(f"[{section_name}]")
        lines.append(f"step_pin: {z_pins['step_pin']}      # {z_port}")
        lines.append(f"dir_pin: {z_pins['dir_pin']}       # {z_port}")
        lines.append(f"enable_pin: !{z_pins['enable_pin']}  # {z_port}")
        lines.append("microsteps: 16")
        lines.append("rotation_distance: 8")
        
        if z_idx == 0:
            # Use correct virtual endstop based on probe type
            probe_type = wizard_state.get('probe_type', '')
            if probe_type == 'beacon':
                # Beacon registers as 'probe' chip, not 'beacon'
                lines.append("endstop_pin: probe:z_virtual_endstop")
                lines.append("homing_retract_dist: 0  # Beacon requires this")
            elif probe_type == 'cartographer':
                # Cartographer registers as 'cartographer' chip
                lines.append("endstop_pin: cartographer:z_virtual_endstop")
                lines.append("homing_retract_dist: 0  # Cartographer requires this")
            elif probe_type == 'btt-eddy':
                # BTT Eddy registers as 'btt_eddy' chip
                lines.append("endstop_pin: btt_eddy:z_virtual_endstop")
                lines.append("homing_retract_dist: 0  # Eddy probe requires this")
            elif probe_type in ('bltouch', 'klicky', 'inductive'):
                lines.append("endstop_pin: probe:z_virtual_endstop")
                lines.append("homing_retract_dist: 5")
            else:
                lines.append("endstop_pin: REPLACE_PIN  # Physical Z endstop")
                lines.append("position_endstop: 0  # Adjust after homing")
                lines.append("homing_retract_dist: 5")
            lines.append("position_min: -5")
            lines.append(f"position_max: {bed_z}")
            lines.append("homing_speed: 15")
        
        lines.append("")
    
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
        lines.append(f"step_pin: toolboard:{e_pins['step_pin']}      # {e_port}")
        lines.append(f"dir_pin: toolboard:{e_pins['dir_pin']}       # {e_port}")
        lines.append(f"enable_pin: !toolboard:{e_pins['enable_pin']}  # {e_port}")
    else:
        # Extruder motor on main board
        e_port = assignments.get('extruder', 'MOTOR_5')
        e_pins = get_motor_pins(board, e_port)
        lines.append(f"step_pin: {e_pins['step_pin']}      # {e_port}")
        lines.append(f"dir_pin: {e_pins['dir_pin']}       # {e_port}")
        lines.append(f"enable_pin: !{e_pins['enable_pin']}  # {e_port}")
    
    lines.append("microsteps: 16")
    lines.append("rotation_distance: 22.6789511  # Calibrate this!")
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
    if hotend_therm == 'PT1000_MAX31865':
        lines.append("sensor_type: MAX31865")
        lines.append("sensor_pin: REPLACE_SPI_CS_PIN  # MAX31865 chip select")
        lines.append("spi_bus: spi1  # Adjust for your board")
        lines.append("rtd_nominal_r: 1000")
        lines.append("rtd_reference_r: 4300")
        lines.append("rtd_num_of_wires: 2")
    elif hotend_therm == 'PT100_MAX31865':
        lines.append("sensor_type: MAX31865")
        lines.append("sensor_pin: REPLACE_SPI_CS_PIN  # MAX31865 chip select")
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
    lines.append("max_extrude_only_distance: 150")
    lines.append("control: pid")
    lines.append("pid_kp: 26.213  # Run PID_CALIBRATE HEATER=extruder TARGET=200")
    lines.append("pid_ki: 1.304")
    lines.append("pid_kd: 131.721")
    lines.append("pressure_advance: 0.04")
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
    fan_controller = wizard_state.get('fan_controller', '')
    fan_controller_multipin = wizard_state.get('fan_controller_multipin', '')
    fan_exhaust = wizard_state.get('fan_exhaust', '')
    fan_exhaust_multipin = wizard_state.get('fan_exhaust_multipin', '')
    fan_chamber = wizard_state.get('fan_chamber', '')
    fan_chamber_type = wizard_state.get('fan_chamber_type', '')
    fan_chamber_multipin = wizard_state.get('fan_chamber_multipin', '')
    fan_rscs = wizard_state.get('fan_rscs', '')
    fan_rscs_multipin = wizard_state.get('fan_rscs_multipin', '')
    fan_radiator = wizard_state.get('fan_radiator', '')
    fan_radiator_multipin = wizard_state.get('fan_radiator_multipin', '')
    
    # Advanced settings
    pc_max_power = wizard_state.get('fan_pc_max_power', '')
    pc_cycle_time = wizard_state.get('fan_pc_cycle_time', '')
    pc_hardware_pwm = wizard_state.get('fan_pc_hardware_pwm', '')
    pc_shutdown_speed = wizard_state.get('fan_pc_shutdown_speed', '')
    pc_kick_start = wizard_state.get('fan_pc_kick_start', '')
    
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
    
    # Add advanced settings if specified
    if pc_max_power:
        lines.append(f"max_power: {pc_max_power}")
    if pc_cycle_time:
        lines.append(f"cycle_time: {pc_cycle_time}")
    if pc_hardware_pwm:
        lines.append(f"hardware_pwm: {pc_hardware_pwm}")
    if pc_shutdown_speed:
        lines.append(f"shutdown_speed: {pc_shutdown_speed}")
    if pc_kick_start:
        lines.append(f"kick_start_time: {pc_kick_start}")
    lines.append("")
    
    # Hotend fan (only if not water cooled / actually used)
    if fan_hotend != 'none':
        if hf_on_toolboard:
            hf_port = tb_assignments.get('fan_hotend', 'FAN1')
            hf_pin = get_fan_pin(toolboard, hf_port)
            lines.append("[heater_fan hotend_fan]")
            lines.append(f"pin: toolboard:{hf_pin}  # {hf_port}")
            lines.append("max_power: 1.0")
            lines.append("kick_start_time: 0.5")
            lines.append("heater: extruder")
            lines.append("heater_temp: 50.0")
            lines.append("")
        elif assignments.get('fan_hotend'):
            hf_port = assignments.get('fan_hotend', 'FAN1')
            hf_pin = get_fan_pin(board, hf_port)
            lines.append("[heater_fan hotend_fan]")
            lines.append(f"pin: {hf_pin}  # {hf_port}")
            lines.append("max_power: 1.0")
            lines.append("kick_start_time: 0.5")
            lines.append("heater: extruder")
            lines.append("heater_temp: 50.0")
            lines.append("")
    
    # Controller fan on main board - generated if port is assigned
    cf_port = assignments.get('fan_controller')
    cf2_port = assignments.get('fan_controller_pin2', '')
    if cf_port:
        cf_pin = get_fan_pin(board, cf_port)
        
        # Multi-pin if second port is assigned
        if cf2_port:
            cf2_pin = get_fan_pin(board, cf2_port)
            lines.extend(generate_multipin('controller', cf_pin, cf2_pin, cf_port, cf2_port))
            lines.append("[controller_fan electronics_fan]")
            lines.append("pin: multi_pin:controller_pins")
        else:
            lines.append("[controller_fan electronics_fan]")
            lines.append(f"pin: {cf_pin}  # {cf_port}")
        
        lines.append("max_power: 1.0")
        lines.append("kick_start_time: 0.5")
        lines.append("heater: heater_bed, extruder")
        lines.append("idle_timeout: 60")
        lines.append("idle_speed: 0.5")
        lines.append("")
    
    # Exhaust fan (fan_generic) - generated if port is assigned
    ex_port = assignments.get('fan_exhaust')
    ex2_port = assignments.get('fan_exhaust_pin2', '')
    if ex_port:
        ex_pin = get_fan_pin(board, ex_port)
        
        # Multi-pin if second port is assigned
        if ex2_port:
            ex2_pin = get_fan_pin(board, ex2_port)
            lines.extend(generate_multipin('exhaust', ex_pin, ex2_pin, ex_port, ex2_port))
            lines.append("[fan_generic exhaust_fan]")
            lines.append("pin: multi_pin:exhaust_pins")
        else:
            lines.append("[fan_generic exhaust_fan]")
            lines.append(f"pin: {ex_pin}  # {ex_port}")
        
        lines.append("max_power: 1.0")
        lines.append("shutdown_speed: 0")
        lines.append("kick_start_time: 0.5")
        lines.append("off_below: 0.10")
        lines.append("# Control with: SET_FAN_SPEED FAN=exhaust_fan SPEED=0.5")
        lines.append("")
    
    # Chamber fan (fan_generic or temperature_fan) - generated if port is assigned
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
        
        if fan_chamber_type == 'temperature':
            # Temperature-controlled chamber fan
            ch_sensor_type = wizard_state.get('fan_chamber_sensor_type', 'Generic 3950')
            ch_sensor_pin = wizard_state.get('fan_chamber_sensor_pin', 'REPLACE_PIN')
            ch_target_temp = wizard_state.get('fan_chamber_target_temp', '45')
            
            lines.append("[temperature_fan chamber]")
            lines.append(f"pin: {pin_value}")
            lines.append("max_power: 1.0")
            lines.append("shutdown_speed: 0")
            lines.append("kick_start_time: 0.5")
            lines.append(f"sensor_type: {ch_sensor_type}")
            lines.append(f"sensor_pin: {ch_sensor_pin}  # Configure chamber thermistor pin")
            lines.append("min_temp: 0")
            lines.append("max_temp: 80")
            lines.append(f"target_temp: {ch_target_temp}")
            lines.append("control: watermark")
            lines.append("gcode_id: C")
        else:
            # Manual chamber fan (default)
            lines.append("[fan_generic chamber_fan]")
            lines.append(f"pin: {pin_value}")
            lines.append("max_power: 1.0")
            lines.append("shutdown_speed: 0")
            lines.append("kick_start_time: 0.5")
            lines.append("off_below: 0.10")
            lines.append("# Control with: SET_FAN_SPEED FAN=chamber_fan SPEED=0.5")
        lines.append("")
    
    # RSCS/Filter fan (fan_generic) - generated if port is assigned
    rs_port = assignments.get('fan_rscs')
    rs2_port = assignments.get('fan_rscs_pin2', '')
    if rs_port:
        rs_pin = get_fan_pin(board, rs_port)
        
        # Multi-pin if second port is assigned
        if rs2_port:
            rs2_pin = get_fan_pin(board, rs2_port)
            lines.extend(generate_multipin('rscs', rs_pin, rs2_pin, rs_port, rs2_port))
            lines.append("[fan_generic rscs_fan]")
            lines.append("pin: multi_pin:rscs_pins")
        else:
            lines.append("[fan_generic rscs_fan]")
            lines.append(f"pin: {rs_pin}  # {rs_port}")
        
        lines.append("max_power: 1.0")
        lines.append("shutdown_speed: 0")
        lines.append("kick_start_time: 0.5")
        lines.append("off_below: 0.10")
        lines.append("# Recirculating active carbon/HEPA filter")
        lines.append("# Control with: SET_FAN_SPEED FAN=rscs_fan SPEED=0.5")
        lines.append("")
    
    # Radiator fan (heater_fan - for water cooling) - generated if port is assigned
    rd_port = assignments.get('fan_radiator')
    rd2_port = assignments.get('fan_radiator_pin2', '')
    if rd_port:
        rd_pin = get_fan_pin(board, rd_port)
        
        # Multi-pin if second port is assigned
        if rd2_port:
            rd2_pin = get_fan_pin(board, rd2_port)
            lines.extend(generate_multipin('radiator', rd_pin, rd2_pin, rd_port, rd2_port))
            lines.append("[heater_fan radiator_fan]")
            lines.append("pin: multi_pin:radiator_pins")
        else:
            lines.append("[heater_fan radiator_fan]")
            lines.append(f"pin: {rd_pin}  # {rd_port}")
        
        lines.append("max_power: 1.0")
        lines.append("kick_start_time: 0.5")
        lines.append("heater: extruder")
        lines.append("heater_temp: 50.0")
        lines.append("# Water cooling radiator fan - runs when hotend is hot")
        lines.append("")
    
    # Probe configuration
    probe_type = wizard_state.get('probe_type', '')
    # Get probe serial from hardware state
    probe_serial = hardware_state.get('probe_serial')
    
    if probe_type and probe_type != 'none' and probe_type != 'endstop':
        lines.append("# " + "─" * 77)
        lines.append("# PROBE")
        lines.append("# " + "─" * 77)
        
        if probe_type == 'beacon':
            lines.append("[beacon]")
            if probe_serial:
                lines.append(f"serial: {probe_serial}")
            else:
                lines.append("serial: /dev/serial/by-id/REPLACE_WITH_BEACON_ID")
                lines.append("# Run: ls /dev/serial/by-id/*beacon* to find your device")
            lines.append("x_offset: 0")
            lines.append("y_offset: 20  # Adjust for your toolhead")
            lines.append("mesh_main_direction: x")
            lines.append("mesh_runs: 2")
        elif probe_type == 'cartographer':
            lines.append("[cartographer]")
            if probe_serial:
                lines.append(f"serial: {probe_serial}")
            else:
                lines.append("serial: /dev/serial/by-id/REPLACE_WITH_CARTOGRAPHER_ID")
                lines.append("# Run: ls /dev/serial/by-id/*cartographer* to find your device")
            lines.append("x_offset: 0")
            lines.append("y_offset: 20  # Adjust for your toolhead")
            lines.append("mesh_main_direction: x")
            lines.append("mesh_runs: 2")
        elif probe_type == 'btt-eddy':
            lines.append("[mcu eddy]")
            if probe_serial:
                lines.append(f"serial: {probe_serial}")
            else:
                lines.append("serial: /dev/serial/by-id/REPLACE_WITH_EDDY_ID")
                lines.append("# Run: ls /dev/serial/by-id/*Eddy* to find your device")
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
        elif probe_type == 'bltouch':
            lines.append("[bltouch]")
            lines.append("sensor_pin: ^REPLACE_PIN  # Probe signal pin")
            lines.append("control_pin: REPLACE_PIN  # Servo control pin")
            lines.append("x_offset: 0")
            lines.append("y_offset: 20  # Adjust for your toolhead")
            lines.append("z_offset: 0  # Run PROBE_CALIBRATE")
        elif probe_type == 'klicky' or probe_type == 'inductive':
            lines.append("[probe]")
            lines.append("pin: ^REPLACE_PIN  # Probe signal pin")
            lines.append("x_offset: 0")
            lines.append("y_offset: 20  # Adjust for your toolhead")
            lines.append("z_offset: 0  # Run PROBE_CALIBRATE")
            lines.append("speed: 5")
            lines.append("samples: 3")
            lines.append("sample_retract_dist: 2")
            lines.append("samples_result: median")
        
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
    
    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate Klipper config files')
    parser.add_argument('--output-dir', type=str, required=True, help='Output directory')
    parser.add_argument('--hardware-only', action='store_true', help='Generate only hardware.cfg')
    
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
    
    # Generate hardware.cfg
    hardware_cfg = generate_hardware_cfg(wizard_state, hardware_state, board, toolboard)
    
    output_file = output_dir / "hardware.cfg"
    with open(output_file, 'w') as f:
        f.write(hardware_cfg)
    
    print(f"Generated: {output_file}")

if __name__ == '__main__':
    main()

