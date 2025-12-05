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
from typing import Dict, Optional, Any

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
    
    # Endstop - check for sensorless or physical
    x_endstop = assignments.get('endstop_x', '')
    if x_endstop == 'sensorless':
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
                lines.append("endstop_pin: beacon:z_virtual_endstop")
                lines.append("homing_retract_dist: 0  # Beacon requires this")
                lines.append("position_endstop: 0")
            elif probe_type == 'cartographer':
                lines.append("endstop_pin: cartographer:z_virtual_endstop")
                lines.append("homing_retract_dist: 0  # Cartographer requires this")
                lines.append("position_endstop: 0")
            elif probe_type == 'btt-eddy':
                lines.append("endstop_pin: btt_eddy:z_virtual_endstop")
                lines.append("homing_retract_dist: 0  # Eddy probe requires this")
                lines.append("position_endstop: 0")
            elif probe_type in ('bltouch', 'klicky', 'inductive'):
                lines.append("endstop_pin: probe:z_virtual_endstop")
                lines.append("position_endstop: 0")
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
    
    if toolboard:
        # Extruder on toolboard
        tb_assignments = hardware_state.get('toolboard_assignments', {})
        e_port = tb_assignments.get('extruder', 'EXTRUDER')
        e_pins = get_motor_pins(toolboard, e_port)
        
        lines.append("[extruder]")
        lines.append(f"step_pin: toolboard:{e_pins['step_pin']}      # {e_port}")
        lines.append(f"dir_pin: toolboard:{e_pins['dir_pin']}       # {e_port}")
        lines.append(f"enable_pin: !toolboard:{e_pins['enable_pin']}  # {e_port}")
        
        he_port = tb_assignments.get('heater_extruder', 'HE')
        he_pin = get_heater_pin(toolboard, he_port)
        th_port = tb_assignments.get('thermistor_extruder', 'TH0')
        th_pin = get_thermistor_pin(toolboard, th_port)
        
        lines.append("microsteps: 16")
        lines.append("rotation_distance: 22.6789511  # Calibrate this!")
        lines.append("nozzle_diameter: 0.400")
        lines.append("filament_diameter: 1.750")
        lines.append(f"heater_pin: toolboard:{he_pin}  # {he_port}")
        lines.append(f"sensor_type: {hotend_therm}")
        lines.append(f"sensor_pin: toolboard:{th_pin}  # {th_port}")
    else:
        # Extruder on main board
        e_port = assignments.get('extruder', 'MOTOR_5')
        e_pins = get_motor_pins(board, e_port)
        
        lines.append("[extruder]")
        lines.append(f"step_pin: {e_pins['step_pin']}      # {e_port}")
        lines.append(f"dir_pin: {e_pins['dir_pin']}       # {e_port}")
        lines.append(f"enable_pin: !{e_pins['enable_pin']}  # {e_port}")
        
        he_port = assignments.get('heater_extruder', 'HE0')
        he_pin = get_heater_pin(board, he_port)
        th_port = assignments.get('thermistor_extruder', 'T0')
        th_pin = get_thermistor_pin(board, th_port)
        
        lines.append("microsteps: 16")
        lines.append("rotation_distance: 22.6789511  # Calibrate this!")
        lines.append("nozzle_diameter: 0.400")
        lines.append("filament_diameter: 1.750")
        lines.append(f"heater_pin: {he_pin}  # {he_port}")
        lines.append(f"sensor_type: {hotend_therm}")
        lines.append(f"sensor_pin: {th_pin}  # {th_port}")
    
    lines.append("min_temp: 0")
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
    
    if toolboard:
        # Fans on toolboard
        tb_assignments = hardware_state.get('toolboard_assignments', {})
        pc_port = tb_assignments.get('fan_part_cooling', 'FAN0')
        pc_pin = get_fan_pin(toolboard, pc_port)
        hf_port = tb_assignments.get('fan_hotend', 'FAN1')
        hf_pin = get_fan_pin(toolboard, hf_port)
        
        lines.append("[fan]")
        lines.append(f"pin: toolboard:{pc_pin}  # {pc_port} - Part cooling")
        lines.append("")
        lines.append("[heater_fan hotend_fan]")
        lines.append(f"pin: toolboard:{hf_pin}  # {hf_port}")
        lines.append("heater: extruder")
        lines.append("heater_temp: 50.0")
    else:
        pc_port = assignments.get('fan_part_cooling', 'FAN0')
        pc_pin = get_fan_pin(board, pc_port)
        hf_port = assignments.get('fan_hotend', 'FAN1')
        hf_pin = get_fan_pin(board, hf_port)
        
        lines.append("[fan]")
        lines.append(f"pin: {pc_pin}  # {pc_port} - Part cooling")
        lines.append("")
        lines.append("[heater_fan hotend_fan]")
        lines.append(f"pin: {hf_pin}  # {hf_port}")
        lines.append("heater: extruder")
        lines.append("heater_temp: 50.0")
    
    lines.append("")
    
    # Controller fan on main board
    cf_port = assignments.get('fan_controller')
    if cf_port:
        cf_pin = get_fan_pin(board, cf_port)
        lines.append("[controller_fan electronics_fan]")
        lines.append(f"pin: {cf_pin}  # {cf_port}")
        lines.append("heater: heater_bed, extruder")
        lines.append("idle_timeout: 60")
        lines.append("")
    
    # Probe configuration
    probe_type = wizard_state.get('probe_type', '')
    if probe_type and probe_type != 'none' and probe_type != 'endstop':
        lines.append("# " + "─" * 77)
        lines.append("# PROBE")
        lines.append("# " + "─" * 77)
        
        if probe_type == 'beacon':
            lines.append("[beacon]")
            lines.append("serial: /dev/serial/by-id/REPLACE_WITH_BEACON_ID")
            lines.append("# Run: ls /dev/serial/by-id/*beacon* to find your device")
            lines.append("x_offset: 0")
            lines.append("y_offset: 20  # Adjust for your toolhead")
            lines.append("mesh_main_direction: x")
            lines.append("mesh_runs: 2")
        elif probe_type == 'cartographer':
            lines.append("[cartographer]")
            lines.append("serial: /dev/serial/by-id/REPLACE_WITH_CARTOGRAPHER_ID")
            lines.append("# Run: ls /dev/serial/by-id/*cartographer* to find your device")
            lines.append("x_offset: 0")
            lines.append("y_offset: 20  # Adjust for your toolhead")
            lines.append("mesh_main_direction: x")
            lines.append("mesh_runs: 2")
        elif probe_type == 'btt-eddy':
            lines.append("[mcu eddy]")
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

