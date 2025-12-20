#!/usr/bin/env python3
"""
test_pin_parity.py - Verify generator output parity before/after refactoring

Usage:
    # Create baseline (run BEFORE refactoring):
    python test_pin_parity.py --create-baseline

    # Verify parity (run AFTER refactoring):
    python test_pin_parity.py --verify

    # Run with custom state file:
    python test_pin_parity.py --create-baseline --state path/to/state.json

    # Run with verbose diff output:
    python test_pin_parity.py --verify --verbose
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from difflib import unified_diff
from pathlib import Path

# Add script directories to path
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR / "scripts"))

from wizard.state import WizardState
from generator.generator import ConfigGenerator


# Sample state for testing (covers common config scenarios)
SAMPLE_STATE = {
    # MCU Configuration
    "mcu.main.board_type": "btt-octopus-v1.1",
    "mcu.main.serial": "/dev/serial/by-id/usb-Klipper_stm32f446xx_12345",
    "mcu.toolboard.board_type": "btt-ebb36-v1.2",
    "mcu.toolboard.connection_type": "can",
    "mcu.toolboard.canbus_uuid": "abcd1234",

    # Printer basics
    "printer.kinematics": "corexy",
    "printer.max_velocity": 300,
    "printer.max_accel": 3000,
    "printer.max_z_velocity": 15,
    "printer.max_z_accel": 45,
    "printer.square_corner_velocity": 5.0,
    "printer.bed_size_x": 350,
    "printer.bed_size_y": 350,
    "printer.bed_size_z": 300,

    # Stepper X
    "stepper_x.motor_port": "MOTOR_0",
    "stepper_x.rotation_distance": 40,
    "stepper_x.microsteps": 32,
    "stepper_x.belt_pitch": 2,
    "stepper_x.pulley_teeth": 20,
    "stepper_x.endstop_type": "physical",
    "stepper_x.endstop_port_toolboard": "STOP",
    "stepper_x.endstop_pullup": True,
    "stepper_x.endstop_invert": False,
    "stepper_x.homing_dir": "negative",
    "stepper_x.position_min": 0,
    "stepper_x.position_max": 350,
    "stepper_x.position_endstop": 0,
    "stepper_x.homing_speed": 50,
    "stepper_x.homing_retract_dist": 5,
    "stepper_x.driver_type": "tmc2209",
    "stepper_x.run_current": 0.8,
    "stepper_x.hold_current": 0.5,
    "stepper_x.stealthchop_threshold": 999999,
    "stepper_x.dir_pin_inverted": False,

    # Stepper Y
    "stepper_y.motor_port": "MOTOR_1",
    "stepper_y.rotation_distance": 40,
    "stepper_y.microsteps": 32,
    "stepper_y.belt_pitch": 2,
    "stepper_y.pulley_teeth": 20,
    "stepper_y.endstop_type": "physical",
    "stepper_y.endstop_port": "STOP_1",
    "stepper_y.endstop_pullup": True,
    "stepper_y.endstop_invert": False,
    "stepper_y.homing_dir": "positive",
    "stepper_y.position_min": 0,
    "stepper_y.position_max": 350,
    "stepper_y.position_endstop": 350,
    "stepper_y.homing_speed": 50,
    "stepper_y.homing_retract_dist": 5,
    "stepper_y.driver_type": "tmc2209",
    "stepper_y.run_current": 0.8,
    "stepper_y.hold_current": 0.5,
    "stepper_y.stealthchop_threshold": 999999,
    "stepper_y.dir_pin_inverted": False,

    # Stepper Z
    "stepper_z.motor_port": "MOTOR_2_1",
    "stepper_z.drive_type": "leadscrew",
    "stepper_z.leadscrew_pitch": 8,
    "stepper_z.microsteps": 32,
    "stepper_z.endstop_type": "probe",
    "stepper_z.homing_dir": "negative",
    "stepper_z.position_min": -5,
    "stepper_z.position_max": 300,
    "stepper_z.position_endstop": 0,
    "stepper_z.homing_speed": 10,
    "stepper_z.homing_retract_dist": 0,
    "stepper_z.driver_type": "tmc2209",
    "stepper_z.run_current": 0.8,
    "stepper_z.hold_current": 0.5,
    "stepper_z.stealthchop_threshold": 999999,
    "stepper_z.dir_pin_inverted": False,

    # Extruder
    "extruder.location": "toolboard",
    "extruder.motor_port_toolboard": "EXTRUDER",
    "extruder.extruder_type": "orbiter_v2",
    "extruder.microsteps": 16,
    "extruder.nozzle_diameter": 0.4,
    "extruder.filament_diameter": 1.75,
    "extruder.max_extrude_only_distance": 200,
    "extruder.driver_type": "tmc2209",
    "extruder.run_current": 0.6,
    "extruder.hold_current": 0.3,
    "extruder.stealthchop_threshold": 999999,
    "extruder.dir_pin_inverted": False,

    # Extruder heater (toolboard)
    "extruder.heater_location": "toolboard",
    "extruder.heater_port_toolboard": "HE",
    "extruder.max_power": 1.0,

    # Extruder sensor (toolboard)
    "extruder.sensor_location": "toolboard",
    "extruder.sensor_port_toolboard": "TH0",
    "extruder.sensor_type": "ATC Semitec 104NT-4-R025H42G",
    "extruder.pullup_resistor": 2200,
    "extruder.sensor_pullup": True,
    "extruder.min_temp": 0,
    "extruder.max_temp": 300,
    "extruder.control": "pid",

    # Heater bed
    "heater_bed.heater_pin": "HB",
    "heater_bed.sensor_port": "TB",
    "heater_bed.sensor_type": "Generic 3950",
    "heater_bed.pullup_resistor": 4700,
    "heater_bed.min_temp": 0,
    "heater_bed.max_temp": 120,
    "heater_bed.max_power": 0.6,
    "heater_bed.control": "pid",

    # Fans
    "fans.part_cooling.location": "toolboard",
    "fans.part_cooling.pin_toolboard": "FAN0",
    "fans.part_cooling.control_type": "pwm",
    "fans.hotend.location": "toolboard",
    "fans.hotend.pin_toolboard": "FAN1",
    "fans.hotend.control_type": "pwm",
    "fans.controller.enabled": True,
    "fans.controller.pin": "FAN2",
    "fans.controller.control_type": "pwm",

    # Probe
    "probe.type": "beacon",
    "probe.x_offset": 0,
    "probe.y_offset": 0,
    "probe.serial": "/dev/serial/by-id/usb-Beacon_Beacon_RevD-if00",

    # Homing
    "homing.z_home_x": 175,
    "homing.z_home_y": 175,

    # Bed mesh
    "bed_mesh.mesh_min_x": 30,
    "bed_mesh.mesh_min_y": 30,
    "bed_mesh.mesh_max_x": 320,
    "bed_mesh.mesh_max_y": 320,
    "bed_mesh.probe_count": 10,
    "bed_mesh.speed": 200,

    # Common/tuning
    "tuning.input_shaper.enabled": True,
    "tuning.firmware_retraction.enabled": True,
    "tuning.firmware_retraction.length": 0.5,
    "tuning.firmware_retraction.speed": 35,
}

# Baseline directory
BASELINE_DIR = SCRIPT_DIR / "test_baselines"


def flat_to_nested(flat_dict: dict) -> dict:
    """Convert flat dot-notation keys to nested dict structure."""
    result = {}
    for key, value in flat_dict.items():
        parts = key.split(".")
        current = result
        for i, part in enumerate(parts[:-1]):
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    return result


def create_state_from_dict(state_dict: dict, state_dir: Path = None) -> WizardState:
    """Create a WizardState object from a dict.
    
    The state_dict can use either flat dot-notation keys (e.g., "mcu.main.board_type")
    or nested dicts. Flat keys will be converted to nested structure.
    """
    # Create a temporary state directory with proper structure
    if state_dir is None:
        state_dir = Path(tempfile.mkdtemp())

    # Check if state_dict uses flat keys (has dots in keys)
    has_flat_keys = any("." in k for k in state_dict.keys())
    if has_flat_keys:
        nested_state = flat_to_nested(state_dict)
    else:
        nested_state = state_dict

    # WizardState expects {"wizard": {...}, "config": {...}} structure
    full_state = {
        "wizard": {
            "version": "2.0",
            "created": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat(),
        },
        "config": nested_state
    }

    state_file = state_dir / ".gschpoozi_state.json"
    state_file.write_text(json.dumps(full_state, indent=2))

    # Create WizardState with the directory
    state = WizardState(state_dir)
    return state


def generate_configs(state: WizardState, templates_dir: Path = None) -> dict:
    """Generate configs and return as dict (file_path -> content)."""
    if templates_dir is None:
        templates_dir = SCRIPT_DIR / "templates"

    # Use a temp directory for output (we don't actually write)
    with tempfile.TemporaryDirectory() as tmpdir:
        generator = ConfigGenerator(
            state=state,
            output_dir=Path(tmpdir),
            templates_dir=templates_dir,
        )
        return generator.generate()


def normalize_content(content: str) -> str:
    """Normalize content for comparison (strip timestamps, etc.)."""
    lines = []
    for line in content.splitlines():
        # Skip timestamp lines in headers
        if line.startswith("# 20") and ":" in line:  # e.g., "# 2025-01-15 10:30:45"
            continue
        lines.append(line)
    return "\n".join(lines)


def content_hash(content: str) -> str:
    """Generate hash of normalized content."""
    return hashlib.sha256(normalize_content(content).encode()).hexdigest()[:16]


def create_baseline(state_dict: dict = None, verbose: bool = False) -> None:
    """Create baseline output for comparison."""
    if state_dict is None:
        state_dict = SAMPLE_STATE

    print("Creating baseline...")

    # Ensure baseline dir exists
    BASELINE_DIR.mkdir(exist_ok=True)

    # Create state and generate
    state_dir = Path(tempfile.mkdtemp())

    try:
        state = create_state_from_dict(state_dict, state_dir)
        configs = generate_configs(state)

        # Save each generated file
        for file_path, content in configs.items():
            safe_name = file_path.replace("/", "_").replace("\\", "_")
            baseline_file = BASELINE_DIR / f"{safe_name}.baseline"
            baseline_file.write_text(content)
            h = content_hash(content)
            if verbose:
                print(f"  {file_path}: {h}")

        # Save state used for baseline
        state_baseline = BASELINE_DIR / "state.json"
        state_baseline.write_text(json.dumps(state_dict, indent=2))

        print(f"Baseline created in {BASELINE_DIR}")
        print(f"  {len(configs)} files generated")

    finally:
        shutil.rmtree(state_dir, ignore_errors=True)


def verify_parity(verbose: bool = False) -> bool:
    """Verify current output matches baseline."""
    if not BASELINE_DIR.exists():
        print("ERROR: No baseline found. Run with --create-baseline first.")
        return False

    # Load baseline state
    state_file = BASELINE_DIR / "state.json"
    if not state_file.exists():
        print("ERROR: Baseline state.json not found.")
        return False

    state_dict = json.loads(state_file.read_text())

    print("Verifying parity against baseline...")

    # Create state and generate
    state_dir = Path(tempfile.mkdtemp())

    try:
        state = create_state_from_dict(state_dict, state_dir)
        configs = generate_configs(state)

        all_passed = True
        checked = 0
        different = []

        for file_path, content in configs.items():
            safe_name = file_path.replace("/", "_").replace("\\", "_")
            baseline_file = BASELINE_DIR / f"{safe_name}.baseline"

            if not baseline_file.exists():
                print(f"  SKIP: {file_path} (no baseline)")
                continue

            baseline_content = baseline_file.read_text()
            checked += 1

            # Compare normalized content
            norm_baseline = normalize_content(baseline_content)
            norm_current = normalize_content(content)

            if norm_baseline == norm_current:
                if verbose:
                    print(f"  PASS: {file_path}")
            else:
                all_passed = False
                different.append(file_path)
                print(f"  DIFF: {file_path}")

                if verbose:
                    # Show unified diff
                    diff = unified_diff(
                        norm_baseline.splitlines(keepends=True),
                        norm_current.splitlines(keepends=True),
                        fromfile=f"baseline/{file_path}",
                        tofile=f"current/{file_path}",
                    )
                    for line in diff:
                        print(f"    {line}", end="")

        print()
        if all_passed:
            print(f"SUCCESS: All {checked} files match baseline!")
            return True
        else:
            print(f"FAILURE: {len(different)} of {checked} files differ:")
            for f in different:
                print(f"  - {f}")
            return False

    finally:
        shutil.rmtree(state_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(
        description="Verify generator output parity before/after refactoring"
    )
    parser.add_argument(
        "--create-baseline",
        action="store_true",
        help="Create baseline output (run BEFORE refactoring)"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify current output matches baseline"
    )
    parser.add_argument(
        "--state",
        type=Path,
        help="Custom state file to use (JSON)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output"
    )

    args = parser.parse_args()

    # Load custom state if provided
    state_dict = None
    if args.state:
        if not args.state.exists():
            print(f"ERROR: State file not found: {args.state}")
            sys.exit(1)
        state_dict = json.loads(args.state.read_text())

    if args.create_baseline:
        create_baseline(state_dict, args.verbose)
    elif args.verify:
        success = verify_parity(args.verbose)
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
        print("\nExample usage:")
        print("  # Before refactoring:")
        print("  python test_pin_parity.py --create-baseline")
        print()
        print("  # After refactoring:")
        print("  python test_pin_parity.py --verify")


if __name__ == "__main__":
    main()

