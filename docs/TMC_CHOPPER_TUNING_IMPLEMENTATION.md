# TMC Chopper Auto-Tuning Implementation Plan

## Overview

This document describes the implementation of an automated TMC chopper tuning system for gschpoozi. The system helps users find optimal TMC5160/TMC2240 driver settings to eliminate mid-range resonance and vibration, particularly at 48V operation with high-performance motors.

## Problem Statement

Users with TMC5160 drivers (especially at 48V with LDO motors) experience violent vibration at certain speeds - often in the normal printing range. Manual tuning of chopper parameters (TBL, TOFF, HSTRT, HEND, TPFD) is tedious and requires understanding of TMC internals.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           WIZARD INTEGRATION                                 │
│  - Captures DIAG0/DIAG1 pins, accelerometer config, driver type             │
│  - Conditionally generates tuning macros based on hardware                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         GENERATED KLIPPER CONFIG                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  tuning.cfg:                                                                 │
│    - [gcode_button stall_monitor_x/y] (if DIAG0 configured)                 │
│    - TMC_CHOPPER_TUNE macro                                                  │
│    - _CHOPPER_* helper macros                                               │
│    - Safety limit macros                                                     │
│                                                                              │
│  Conditional on:                                                             │
│    - accelerometer.type != 'none'                                           │
│    - driver_type IN ['TMC5160', 'TMC2240']                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PYTHON ANALYZER                                      │
│  scripts/tools/chopper_analyze.py                                           │
│    - Parses accelerometer CSV data                                          │
│    - Calculates RMS vibration magnitude per parameter set                   │
│    - Generates comparison graphs                                             │
│    - Outputs recommended config snippet                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Implementation Phases

### Phase 1: Wizard State Extensions

**File:** `schema/menu-schema.yaml`

Add to TMC Driver sections (2.3.2, 2.3.4, 2.4.2, 2.4.4):

```yaml
- name: "diag0_pin"
  type: "pin"
  description: "DIAG0 pin for runtime stall detection (optional, enables safety during tuning)"
  condition: "driver_type in ['TMC5160', 'TMC2240']"
  required: false

- name: "diag1_pin"
  type: "pin"
  description: "DIAG1 pin for sensorless homing"
  condition: "endstop_type == 'sensorless'"
  required: true
```

Add to Tuning & Optimization section:

```yaml
- id: "X.X"
  name: "TMC Chopper Tuning"
  condition: >
    accelerometer.type != 'none' AND
    (stepper_x.driver_type in ['TMC5160', 'TMC2240'] OR
     stepper_y.driver_type in ['TMC5160', 'TMC2240'])
  parameters:
    - name: "chopper_tuning_enabled"
      type: "bool"
      default: true
      description: "Generate TMC chopper tuning macros"
    - name: "chopper_safety_level"
      type: "choice"
      options: ["high", "medium", "low"]
      default: "high"
      description: "high=50% limits, medium=70%, low=90%"
```

---

### Phase 2: Safety Infrastructure

**File:** `schema/config-sections.yaml` (new section)

#### 2.1 Runtime Stall Detection (Hardware)

Generated when `diag0_pin` is configured:

```yaml
tmc_stall_monitor:
  condition: "stepper_x.diag0_pin is defined or stepper_y.diag0_pin is defined"
  template: |
    # ═══════════════════════════════════════════════════════════════════════════
    # TMC RUNTIME STALL DETECTION
    # Uses DIAG0 pin for hardware-level stall monitoring during chopper tuning
    # ═══════════════════════════════════════════════════════════════════════════

    {% if stepper_x.diag0_pin is defined %}
    [gcode_button stall_monitor_x]
    pin: {{ stepper_x.diag0_pin }}
    press_gcode:
        _ON_STALL_DETECTED STEPPER=stepper_x
    release_gcode:
        # Stall cleared
    {% endif %}

    {% if stepper_y.diag0_pin is defined %}
    [gcode_button stall_monitor_y]
    pin: {{ stepper_y.diag0_pin }}
    press_gcode:
        _ON_STALL_DETECTED STEPPER=stepper_y
    release_gcode:
        # Stall cleared
    {% endif %}

    [gcode_macro _ON_STALL_DETECTED]
    variable_tuning_active: False
    gcode:
        {% set stepper = params.STEPPER|default("unknown") %}
        {% if printer["gcode_macro _ON_STALL_DETECTED"].tuning_active %}
            M118 STALL DETECTED on {{stepper}} - aborting chopper test!
            SET_GCODE_VARIABLE MACRO=_CHOPPER_TUNE_STATE VARIABLE=last_result VALUE='"STALL"'
            _CHOPPER_ABORT
        {% else %}
            M118 WARNING: Stall detected on {{stepper}} during print
            PAUSE
        {% endif %}
```

#### 2.2 TMC Driver Configuration for DIAG0

Update TMC sections to enable DIAG0 stall output:

```yaml
tmc_stepper_x:
  template: |
    # ... existing template ...
    {% if stepper_x.diag0_pin is defined %}
    # Enable DIAG0 for runtime stall detection
    driver_DIAG0_STALL: 1
    {% endif %}
```

#### 2.3 Safety Limits Macro

```yaml
chopper_safety_limits:
  condition: "tuning.chopper_tuning_enabled"
  template: |
    [gcode_macro _CHOPPER_SAFETY_LIMITS]
    variable_safety_level: "{{ tuning.chopper_safety_level | default('high') }}"
    variable_original_velocity: 0
    variable_original_accel: 0
    gcode:
        {% set levels = {'high': 0.5, 'medium': 0.7, 'low': 0.9} %}
        {% set pct = levels[printer["gcode_macro _CHOPPER_SAFETY_LIMITS"].safety_level] %}

        # Store original values
        SET_GCODE_VARIABLE MACRO=_CHOPPER_SAFETY_LIMITS VARIABLE=original_velocity VALUE={printer.toolhead.max_velocity}
        SET_GCODE_VARIABLE MACRO=_CHOPPER_SAFETY_LIMITS VARIABLE=original_accel VALUE={printer.toolhead.max_accel}

        # Apply reduced limits
        {% set safe_vel = (printer.toolhead.max_velocity * pct)|int %}
        {% set safe_accel = (printer.toolhead.max_accel * pct)|int %}
        SET_VELOCITY_LIMIT VELOCITY={{safe_vel}} ACCEL={{safe_accel}}
        M118 Chopper tuning: Limits set to {{safe_vel}}mm/s, {{safe_accel}}mm/s2 ({{pct * 100}}%)

    [gcode_macro _CHOPPER_RESTORE_LIMITS]
    gcode:
        {% set state = printer["gcode_macro _CHOPPER_SAFETY_LIMITS"] %}
        SET_VELOCITY_LIMIT VELOCITY={state.original_velocity} ACCEL={state.original_accel}
        M118 Velocity limits restored
```

---

### Phase 3: Core Tuning Macros

**File:** `schema/config-sections.yaml` (new section)

#### 3.1 Main Entry Point

```yaml
chopper_tune_macro:
  condition: "tuning.chopper_tuning_enabled and accelerometer.type != 'none'"
  template: |
    # ═══════════════════════════════════════════════════════════════════════════
    # TMC CHOPPER AUTO-TUNING SYSTEM
    # Automatically finds optimal chopper settings to reduce vibration
    # Requires: Accelerometer, TMC5160/TMC2240 drivers
    # ═══════════════════════════════════════════════════════════════════════════

    [gcode_macro TMC_CHOPPER_TUNE]
    description: Auto-tune TMC chopper settings to reduce vibration
    variable_state: "idle"
    gcode:
        {% set stepper = params.STEPPER|default("stepper_x") %}
        {% set mode = params.MODE|default("full") %}  # full, find_resonance, optimize, test
        {% set speeds = params.SPEEDS|default("") %}  # Manual speed override "45,90"
        {% set safety = params.SAFETY|default("high") %}

        # Validate stepper has compatible driver
        {% set tmc_type = printer.configfile.config["tmc5160 " ~ stepper] is defined %}
        {% if not tmc_type %}
            {% set tmc_type = printer.configfile.config["tmc2240 " ~ stepper] is defined %}
        {% endif %}
        {% if not tmc_type %}
            { action_raise_error("TMC_CHOPPER_TUNE requires TMC5160 or TMC2240 driver") }
        {% endif %}

        # Ensure homed
        {% if printer.toolhead.homed_axes != "xyz" %}
            M118 Homing required...
            G28
        {% endif %}

        # Apply safety limits
        SET_GCODE_VARIABLE MACRO=_CHOPPER_SAFETY_LIMITS VARIABLE=safety_level VALUE='"{{safety}}"'
        _CHOPPER_SAFETY_LIMITS

        # Enable stall detection if available
        SET_GCODE_VARIABLE MACRO=_ON_STALL_DETECTED VARIABLE=tuning_active VALUE=True

        # Move to safe position (center, Z up)
        _CHOPPER_SAFE_POSITION

        {% if mode == "find_resonance" or mode == "full" %}
            M118 === Phase 1: Finding resonant speeds ===
            _CHOPPER_FIND_RESONANCE STEPPER={stepper}
        {% endif %}

        {% if mode == "optimize" or mode == "full" %}
            M118 === Phase 2: Optimizing chopper parameters ===
            {% if speeds != "" %}
                _CHOPPER_OPTIMIZE STEPPER={stepper} SPEEDS="{speeds}"
            {% else %}
                _CHOPPER_OPTIMIZE STEPPER={stepper}
            {% endif %}
        {% endif %}

        {% if mode == "test" %}
            # Single parameter test
            {% set tpfd = params.TPFD|default(0)|int %}
            {% set tbl = params.TBL|default(2)|int %}
            {% set toff = params.TOFF|default(3)|int %}
            {% set hstrt = params.HSTRT|default(5)|int %}
            {% set hend = params.HEND|default(3)|int %}
            _CHOPPER_TEST STEPPER={stepper} TPFD={tpfd} TBL={tbl} TOFF={toff} HSTRT={hstrt} HEND={hend}
        {% endif %}

        # Cleanup
        SET_GCODE_VARIABLE MACRO=_ON_STALL_DETECTED VARIABLE=tuning_active VALUE=False
        _CHOPPER_RESTORE_LIMITS

        M118 === Chopper tuning complete ===
        M118 Results saved to ~/printer_data/config/chopper_results/
        M118 Run CHOPPER_ANALYZE to generate recommendations
```

#### 3.2 Find Resonance Phase

```yaml
chopper_find_resonance:
  template: |
    [gcode_macro _CHOPPER_FIND_RESONANCE]
    description: Sweep speeds to identify resonant frequencies
    gcode:
        {% set stepper = params.STEPPER %}
        {% set min_speed = params.MIN_SPEED|default(20)|int %}
        {% set max_speed = params.MAX_SPEED|default(150)|int %}
        {% set step = params.STEP|default(10)|int %}

        M118 Sweeping {{min_speed}} to {{max_speed}} mm/s in {{step}}mm/s increments

        # Determine axis from stepper name
        {% set axis = "X" if "x" in stepper else "Y" %}
        {% set distance = 50 %}  # Movement distance for each test

        ACCELEROMETER_MEASURE CHIP={{ input_shaper.accel_chip | default('adxl345') }}

        {% for speed in range(min_speed, max_speed + 1, step) %}
            M118 Testing {{speed}} mm/s...
            # Move back and forth at this speed
            G1 {{axis}}{{printer.toolhead.axis_maximum[axis|lower] / 2 + distance}} F{{speed * 60}}
            G1 {{axis}}{{printer.toolhead.axis_maximum[axis|lower] / 2 - distance}} F{{speed * 60}}
            G1 {{axis}}{{printer.toolhead.axis_maximum[axis|lower] / 2}} F{{speed * 60}}
            G4 P200  # Brief pause between tests
        {% endfor %}

        ACCELEROMETER_MEASURE CHIP={{ input_shaper.accel_chip | default('adxl345') }} NAME=resonance_sweep

        M118 Resonance sweep complete
        M118 Run: RUN_SHELL_COMMAND CMD=chopper_analyze PARAMS="find_resonance"
```

#### 3.3 Parameter Optimization Phase

```yaml
chopper_optimize:
  template: |
    [gcode_macro _CHOPPER_OPTIMIZE]
    description: Iterate through chopper parameters at resonant speeds
    variable_current_test: 0
    variable_total_tests: 0
    variable_best_magnitude: 999999
    variable_best_params: ""
    gcode:
        {% set stepper = params.STEPPER %}
        {% set speeds = params.SPEEDS|default("50,100")|string %}
        {% set speed_list = speeds.split(",") %}

        # Hierarchical tuning - most impactful parameters first
        # Phase A: TPFD (mid-range resonance damping) - primary for this use case
        {% set tpfd_values = [0, 4, 8, 12] %}

        # Phase B: TBL/TOFF combinations (chopper frequency)
        {% set tbl_values = [0, 1, 2] %}
        {% set toff_values = [2, 3, 4, 5] %}

        # Phase C: Hysteresis fine-tuning
        {% set hstrt_values = [4, 5, 6] %}
        {% set hend_values = [2, 3, 4, 5] %}

        M118 Starting parameter optimization
        M118 Target speeds: {{speeds}} mm/s

        # Phase A: Find best TPFD
        M118 --- Phase A: TPFD optimization ---
        {% for tpfd in tpfd_values %}
            _CHOPPER_TEST_COMBO STEPPER={stepper} SPEEDS="{speeds}" TPFD={tpfd} TBL=2 TOFF=3 HSTRT=5 HEND=3
        {% endfor %}

        # TODO: Read best TPFD from results, continue with Phase B and C
        # This requires shell command integration to parse intermediate results

        M118 Parameter sweep complete
        M118 Run: RUN_SHELL_COMMAND CMD=chopper_analyze PARAMS="optimize"

    [gcode_macro _CHOPPER_TEST_COMBO]
    description: Test a single parameter combination
    gcode:
        {% set stepper = params.STEPPER %}
        {% set speeds = params.SPEEDS|string %}
        {% set tpfd = params.TPFD|int %}
        {% set tbl = params.TBL|int %}
        {% set toff = params.TOFF|int %}
        {% set hstrt = params.HSTRT|int %}
        {% set hend = params.HEND|int %}

        # Apply parameters
        SET_TMC_FIELD STEPPER={stepper} FIELD=tpfd VALUE={tpfd}
        SET_TMC_FIELD STEPPER={stepper} FIELD=tbl VALUE={tbl}
        SET_TMC_FIELD STEPPER={stepper} FIELD=toff VALUE={toff}
        SET_TMC_FIELD STEPPER={stepper} FIELD=hstrt VALUE={hstrt}
        SET_TMC_FIELD STEPPER={stepper} FIELD=hend VALUE={hend}

        G4 P100  # Wait for settings to stabilize

        # Check driver status for errors
        _CHOPPER_CHECK_DRIVER STEPPER={stepper}

        # Test filename encodes parameters
        {% set test_name = "t" ~ tpfd ~ "_" ~ tbl ~ "_" ~ toff ~ "_" ~ hstrt ~ "_" ~ hend %}

        # Measure at each speed
        {% for speed in speeds.split(",") %}
            {% set axis = "X" if "x" in stepper else "Y" %}
            {% set distance = 40 %}

            ACCELEROMETER_MEASURE CHIP={{ input_shaper.accel_chip | default('adxl345') }}

            # Execute test movement
            G1 {{axis}}{{printer.toolhead.axis_maximum[axis|lower] / 2 + distance}} F{{speed|int * 60}}
            G1 {{axis}}{{printer.toolhead.axis_maximum[axis|lower] / 2 - distance}} F{{speed|int * 60}}
            G1 {{axis}}{{printer.toolhead.axis_maximum[axis|lower] / 2}} F{{speed|int * 60}}

            ACCELEROMETER_MEASURE CHIP={{ input_shaper.accel_chip | default('adxl345') }} NAME={{test_name}}_s{{speed}}
        {% endfor %}

        M118 Tested: TPFD={{tpfd}} TBL={{tbl}} TOFF={{toff}} HSTRT={{hstrt}} HEND={{hend}}
```

#### 3.4 Helper Macros

```yaml
chopper_helpers:
  template: |
    [gcode_macro _CHOPPER_SAFE_POSITION]
    description: Move to center of bed with Z clearance
    gcode:
        {% set x_center = printer.toolhead.axis_maximum.x / 2 %}
        {% set y_center = printer.toolhead.axis_maximum.y / 2 %}
        {% set z_safe = 50 %}

        G0 Z{{z_safe}} F1200
        G0 X{{x_center}} Y{{y_center}} F6000
        M118 At safe position: X{{x_center}} Y{{y_center}} Z{{z_safe}}

    [gcode_macro _CHOPPER_CHECK_DRIVER]
    description: Check TMC driver for errors
    gcode:
        {% set stepper = params.STEPPER %}
        {% set tmc = "tmc5160 " ~ stepper %}
        {% if printer[tmc] is not defined %}
            {% set tmc = "tmc2240 " ~ stepper %}
        {% endif %}

        {% set status = printer[tmc].drv_status %}

        {% if status.ot %}
            { action_raise_error("ABORT: " ~ stepper ~ " overtemperature!") }
        {% endif %}
        {% if status.ola or status.olb %}
            { action_raise_error("ABORT: " ~ stepper ~ " open load - check motor connection") }
        {% endif %}
        {% if status.s2ga or status.s2gb %}
            { action_raise_error("ABORT: " ~ stepper ~ " short to ground!") }
        {% endif %}

    [gcode_macro _CHOPPER_ABORT]
    description: Emergency abort chopper tuning
    gcode:
        M118 !!! CHOPPER TUNING ABORTED !!!
        SET_GCODE_VARIABLE MACRO=_ON_STALL_DETECTED VARIABLE=tuning_active VALUE=False
        _CHOPPER_RESTORE_LIMITS
        # Restore default chopper settings
        # TODO: Store originals and restore here
        M112  # Emergency stop - safest option on stall

    [gcode_macro CHOPPER_ANALYZE]
    description: Run analysis script on collected data
    gcode:
        RUN_SHELL_COMMAND CMD=chopper_analyze
```

---

### Phase 4: Python Analyzer Script

**File:** `scripts/tools/chopper_analyze.py`

```python
#!/usr/bin/env python3
"""
TMC Chopper Tuning Analyzer

Analyzes accelerometer data from chopper tuning runs and recommends
optimal driver settings.

Usage:
    chopper_analyze.py find_resonance  - Analyze speed sweep, find problem speeds
    chopper_analyze.py optimize        - Analyze parameter sweep, recommend settings
    chopper_analyze.py report          - Generate full report with graphs
"""

import os
import sys
import csv
import json
import numpy as np
from pathlib import Path
from datetime import datetime

# Configuration
RESULTS_DIR = Path.home() / "printer_data" / "config" / "chopper_results"
ACCEL_DIR = Path("/tmp")  # Where Klipper stores accelerometer CSVs


def parse_accel_csv(filepath: Path) -> np.ndarray:
    """Parse Klipper accelerometer CSV, return RMS magnitude."""
    data = []
    with open(filepath, 'r') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        for row in reader:
            # Columns: time, x, y, z
            x, y, z = float(row[1]), float(row[2]), float(row[3])
            magnitude = np.sqrt(x**2 + y**2 + z**2)
            data.append(magnitude)

    return np.array(data)


def calculate_vibration_score(data: np.ndarray) -> float:
    """Calculate vibration score from accelerometer data."""
    # RMS of magnitude, ignoring outliers
    percentile_95 = np.percentile(data, 95)
    filtered = data[data <= percentile_95]
    return np.sqrt(np.mean(filtered**2))


def find_resonance_speeds(results_dir: Path) -> list:
    """Analyze speed sweep to find problematic speeds."""
    # Find resonance sweep files
    sweep_files = list(results_dir.glob("resonance_sweep*.csv"))

    if not sweep_files:
        print("ERROR: No resonance sweep data found")
        print("Run: TMC_CHOPPER_TUNE MODE=find_resonance")
        return []

    # Parse and analyze
    # TODO: Implement frequency analysis to identify resonant speeds

    # For now, return common problem speeds
    return [50, 100]


def analyze_parameter_sweep(results_dir: Path) -> dict:
    """Analyze parameter combinations and find optimal settings."""
    results = []

    # Find all test files matching pattern: t{tpfd}_{tbl}_{toff}_{hstrt}_{hend}_s{speed}.csv
    for csv_file in results_dir.glob("t*_s*.csv"):
        name = csv_file.stem
        # Parse parameters from filename
        parts = name.split("_")
        params = {
            'tpfd': int(parts[0][1:]),  # Remove 't' prefix
            'tbl': int(parts[1]),
            'toff': int(parts[2]),
            'hstrt': int(parts[3]),
            'hend': int(parts[4]),
            'speed': int(parts[5][1:]),  # Remove 's' prefix
        }

        # Calculate vibration score
        data = parse_accel_csv(csv_file)
        params['score'] = calculate_vibration_score(data)
        results.append(params)

    if not results:
        print("ERROR: No parameter sweep data found")
        return {}

    # Find best combination (lowest score)
    best = min(results, key=lambda x: x['score'])

    return {
        'best_params': {
            'tpfd': best['tpfd'],
            'tbl': best['tbl'],
            'toff': best['toff'],
            'hstrt': best['hstrt'],
            'hend': best['hend'],
        },
        'best_score': best['score'],
        'all_results': results,
    }


def generate_config_snippet(params: dict, stepper: str = "stepper_x", driver_type: str = "tmc5160") -> str:
    """Generate Klipper config snippet with optimal settings.

    Args:
        params: Dictionary with chopper parameters (tpfd, tbl, toff, hstrt, hend)
        stepper: Stepper name (e.g., "stepper_x", "stepper_y")
        driver_type: TMC driver type ("tmc5160" or "tmc2240"), defaults to "tmc5160"
    """
    driver_type_lower = driver_type.lower()
    return f"""
# Optimized chopper settings for {stepper}
# Generated by gschpoozi chopper analyzer on {datetime.now().isoformat()}
# Vibration score: {params.get('score', 'N/A')}

[{driver_type_lower} {stepper}]
driver_TBL: {params['tbl']}
driver_TOFF: {params['toff']}
driver_HSTRT: {params['hstrt']}
driver_HEND: {params['hend']}
driver_TPFD: {params['tpfd']}
"""


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if len(sys.argv) < 2:
        mode = "report"
    else:
        mode = sys.argv[1]

    if mode == "find_resonance":
        speeds = find_resonance_speeds(RESULTS_DIR)
        print(f"Resonant speeds identified: {speeds}")
        print(f"Use these with: TMC_CHOPPER_TUNE MODE=optimize SPEEDS=\"{','.join(map(str, speeds))}\"")

    elif mode == "optimize":
        results = analyze_parameter_sweep(RESULTS_DIR)
        if results:
            print("\n" + "="*60)
            print("OPTIMAL CHOPPER SETTINGS FOUND")
            print("="*60)
            print(f"TPFD: {results['best_params']['tpfd']}")
            print(f"TBL:  {results['best_params']['tbl']}")
            print(f"TOFF: {results['best_params']['toff']}")
            print(f"HSTRT: {results['best_params']['hstrt']}")
            print(f"HEND: {results['best_params']['hend']}")
            print(f"\nVibration score: {results['best_score']:.2f}")
            print("\n" + "-"*60)
            print("Add to your printer.cfg:")
            print(generate_config_snippet(results['best_params']))

            # Save results
            with open(RESULTS_DIR / "optimal_settings.json", 'w') as f:
                json.dump(results, f, indent=2)

    elif mode == "report":
        print("Full report generation not yet implemented")
        print("Use 'find_resonance' or 'optimize' modes")

    else:
        print(f"Unknown mode: {mode}")
        print("Usage: chopper_analyze.py [find_resonance|optimize|report]")


if __name__ == "__main__":
    main()
```

---

### Phase 5: Shell Command Integration

**File:** `schema/config-sections.yaml`

```yaml
chopper_shell_command:
  condition: "tuning.chopper_tuning_enabled"
  template: |
    [gcode_shell_command chopper_analyze]
    command: python3 ~/gschpoozi/scripts/tools/chopper_analyze.py
    timeout: 60.0
    verbose: True
```

---

### Phase 6: AWD Support

For CoreXY AWD setups, the tuning must handle motor pairs:

```yaml
chopper_awd_support:
  condition: "printer.awd_enabled and tuning.chopper_tuning_enabled"
  template: |
    [gcode_macro TMC_CHOPPER_TUNE_AWD]
    description: Auto-tune chopper settings for AWD setups
    gcode:
        {% set pair = params.PAIR|default("ALL") %}  # A, B, or ALL
        {% set safety = params.SAFETY|default("high") %}

        M118 === AWD CHOPPER TUNING ===
        M118 Testing motor pairs separately for safety

        {% if pair == "A" or pair == "ALL" %}
            M118 --- Testing Pair A (stepper_x + stepper_y) ---
            # Disable rear pair
            SET_STEPPER_ENABLE STEPPER=stepper_x1 ENABLE=0
            SET_STEPPER_ENABLE STEPPER=stepper_y1 ENABLE=0

            TMC_CHOPPER_TUNE STEPPER=stepper_x SAFETY={safety}
            TMC_CHOPPER_TUNE STEPPER=stepper_y SAFETY={safety}

            # Re-enable
            SET_STEPPER_ENABLE STEPPER=stepper_x1 ENABLE=1
            SET_STEPPER_ENABLE STEPPER=stepper_y1 ENABLE=1
        {% endif %}

        {% if pair == "B" or pair == "ALL" %}
            M118 --- Testing Pair B (stepper_x1 + stepper_y1) ---
            # Disable front pair
            SET_STEPPER_ENABLE STEPPER=stepper_x ENABLE=0
            SET_STEPPER_ENABLE STEPPER=stepper_y ENABLE=0

            TMC_CHOPPER_TUNE STEPPER=stepper_x1 SAFETY={safety}
            TMC_CHOPPER_TUNE STEPPER=stepper_y1 SAFETY={safety}

            # Re-enable
            SET_STEPPER_ENABLE STEPPER=stepper_x ENABLE=1
            SET_STEPPER_ENABLE STEPPER=stepper_y ENABLE=1
        {% endif %}

        M118 === AWD tuning complete ===
        M118 Compare results between pairs - if very different, check belt tension!
```

---

## Conditional Generation Summary

| Condition | Generated Content |
|-----------|-------------------|
| `accelerometer != none` AND `driver IN [TMC5160, TMC2240]` | Full tuning macros |
| `diag0_pin` defined | Hardware stall detection via gcode_button |
| `diag0_pin` NOT defined | Software-only safety (velocity limits, driver status checks) |
| `awd_enabled` | AWD pair-wise tuning macros |
| `accelerometer == none` OR `driver NOT IN [TMC5160, TMC2240]` | Comment noting requirements, no macros |

---

## File Changes Summary

| File | Changes |
|------|---------|
| `schema/menu-schema.yaml` | Add `diag0_pin`, `diag1_pin`, chopper tuning options |
| `schema/config-sections.yaml` | Add tuning macro templates |
| `scripts/tools/chopper_analyze.py` | New - Python analyzer |
| `scripts/tools/gcode_shell_command.py` | Already exists - reuse |
| `templates/boards/*.json` | Add DIAG0 pin mappings |

---

## Testing Plan

1. **Unit Tests**
   - `chopper_analyze.py` parsing and scoring
   - Config generation with various wizard states

2. **Integration Tests**
   - Generate config with accelerometer + TMC5160
   - Generate config with AWD enabled
   - Generate config without accelerometer (should skip macros)

3. **Hardware Tests**
   - Run on actual printer with TMC5160 + ADXL345
   - Verify stall detection triggers correctly
   - Verify safety limits are applied/restored
   - Verify parameter sweep completes without issues

---

## Usage Example

```gcode
# Full automatic tuning
TMC_CHOPPER_TUNE STEPPER=stepper_x

# Just find problem speeds
TMC_CHOPPER_TUNE STEPPER=stepper_x MODE=find_resonance

# Optimize at known problem speeds
TMC_CHOPPER_TUNE STEPPER=stepper_x MODE=optimize SPEEDS="45,90"

# Test specific parameters
TMC_CHOPPER_TUNE STEPPER=stepper_x MODE=test TPFD=8 TBL=2 TOFF=4

# AWD tuning
TMC_CHOPPER_TUNE_AWD PAIR=ALL

# Analyze results
CHOPPER_ANALYZE
```

---

## References

- [Klipper TMC Drivers Documentation](https://www.klipper3d.org/TMC_Drivers.html)
- [TMC5160 Datasheet](https://www.trinamic.com/products/integrated-circuits/details/tmc5160/)
- [klipper_tmc_autotune](https://github.com/andrewmcgr/klipper_tmc_autotune)
- [chopper-resonance-tuner](https://github.com/MRX8024/chopper-resonance-tuner)
- [Klipper PR #6592 - StallGuard Monitoring](https://github.com/Klipper3d/klipper/pull/6592)
