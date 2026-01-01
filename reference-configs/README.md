# Klipper Reference Configurations

This directory contains complete, single-file Klipper configurations from popular 3D printer kits for reference purposes.

## Purpose

These configs serve as reference material for the gschpoozi project, providing real-world examples of how established printer manufacturers structure their Klipper configurations.

## Available Configs

### Voron Design Printers

#### 1. **voron-2.4-octopus-raw.cfg**
- **Printer:** Voron 2.4 (250/300/350mm build sizes)
- **Controller:** BigTreeTech Octopus V1
- **Kinematics:** CoreXY
- **Notable Features:**
  - Quad gantry leveling (4x Z steppers)
  - TMC2209 UART drivers (32 microsteps)
  - Max velocity: 300mm/s, accel: 3000mm/s²
  - PID-tuned hotend and bed
  - Includes G32 macro for homing + QGL
- **Lines:** 593
- **Source:** [VoronDesign/Voron-2](https://github.com/VoronDesign/Voron-2/tree/Voron2.4/firmware/klipper_configurations)

#### 2. **voron-trident-skr13-raw.cfg**
- **Printer:** Voron Trident (250/300/350mm build sizes)
- **Controller:** BigTreeTech SKR 1.3 + SKR E3 Mini (XYE board)
- **Kinematics:** CoreXY
- **Notable Features:**
  - Dual MCU setup (main board + XYE board)
  - Z-tilt adjustment (3x Z steppers)
  - Inductive probe support
  - TMC2209 drivers
  - Includes PRINT_START/PRINT_END macros with purge line
- **Lines:** 611
- **Source:** [VoronDesign/Voron-Trident](https://github.com/VoronDesign/Voron-Trident)

#### 3. **voron-0.2-skr-mini-e3-v3-raw.cfg**
- **Printer:** Voron 0.2 (120mm build)
- **Controller:** BigTreeTech SKR Mini E3 V3
- **Kinematics:** CoreXY
- **Notable Features:**
  - Sensorless homing on X/Y (TMC2209 stallguard)
  - Compact design (max_velocity: 200mm/s)
  - 50:10 geared extruder
  - Includes filament load/unload macros
  - PID-tuned values included
- **Lines:** 417
- **Source:** [VoronDesign/Voron-0](https://github.com/VoronDesign/Voron-0/tree/Voron0.2/Firmware)

### RatRig Printers

#### 4. **ratrig-vcore3-300-base.cfg**
- **Printer:** RatRig V-Core 3 (300mm build)
- **Controller:** SKR Pro or compatible
- **Kinematics:** CoreXY
- **Notable Features:**
  - Modular config system (uses many includes)
  - Conservative defaults (max_velocity: 300mm/s, accel: 1500mm/s²)
  - Supports multiple hotend/extruder combinations
  - Includes steppers.cfg and macros.cfg
- **Lines:** 163 (base only)
- **Source:** [Rat-Rig/v-core-3-klipper-config](https://github.com/Rat-Rig/v-core-3-klipper-config) (deprecated, now uses RatOS)

#### 5. **ratrig-vcore3-compiled.cfg**
- **Printer:** RatRig V-Core 3 (compiled with common includes)
- **Controller:** SKR Pro or compatible
- **Notable Features:**
  - Compiled version with v-core-3.cfg + common modules
  - Includes probe and hotend configurations
  - Shows modular config pattern
- **Lines:** 139
- **Note:** The new official RatOS system is even more modular. This is from the legacy standalone config.

### Mainstream Printers

#### 6. **creality-ender3-v2.cfg**
- **Printer:** Creality Ender 3 V2
- **Controller:** Creality 4.2.2 board (STM32F103)
- **Kinematics:** Cartesian
- **Notable Features:**
  - Simple Cartesian setup (most common hobbyist printer)
  - Basic stepper configuration
  - Manual bed leveling
  - Stock hardware configuration
- **Lines:** 95
- **Source:** [Klipper Official Configs](https://github.com/Klipper3d/klipper/tree/master/config)

### Generic Board Configs

#### 7. **generic-btt-skr-3.cfg**
- **Board:** BigTreeTech SKR 3 (STM32H743)
- **Purpose:** Generic pin mapping reference
- **Notable Features:**
  - Complete pin mappings for all headers
  - EXP1/EXP2 display headers defined
  - Example stepper, heater, and fan configurations
  - Useful for custom builds using SKR 3
- **Lines:** 185
- **Source:** [Klipper Official Configs](https://github.com/Klipper3d/klipper/tree/master/config)

### Advanced Configurations

#### 8. **sample-idex.cfg**
- **Type:** Independent Dual Extruder (IDEX) example
- **Kinematics:** Cartesian with dual X carriages
- **Notable Features:**
  - Dual carriage setup with [dual_carriage] section
  - Copy mode and mirror mode macros
  - T0/T1 tool change macros
  - PARK macros for each extruder
  - Advanced multi-extruder configuration
- **Lines:** 132
- **Source:** [Klipper Official Configs](https://github.com/Klipper3d/klipper/tree/master/config)

## Quick Reference Table

| Config File | Printer | Kinematics | MCU | Z Leveling | Lines |
|-------------|---------|------------|-----|------------|-------|
| voron-2.4-octopus-raw.cfg | Voron 2.4 | CoreXY | Octopus V1 | Quad Gantry (4Z) | 593 |
| voron-trident-skr13-raw.cfg | Voron Trident | CoreXY | Dual MCU | Z-Tilt (3Z) | 611 |
| voron-0.2-skr-mini-e3-v3-raw.cfg | Voron 0.2 | CoreXY | SKR Mini E3 V3 | Bed Mesh | 417 |
| ratrig-vcore3-300-base.cfg | RatRig V-Core 3 | CoreXY | SKR Pro | Z-Tilt (3Z) | 163 |
| creality-ender3-v2.cfg | Ender 3 V2 | Cartesian | Creality 4.2.2 | Manual | 95 |
| generic-btt-skr-3.cfg | Generic | N/A | SKR 3 | N/A | 185 |
| sample-idex.cfg | IDEX Example | Cartesian | Generic | N/A | 132 |

## Key Observations for gschpoozi

### Common Patterns

1. **Kinematics Declaration:** All CoreXY printers use `kinematics: corexy`

2. **Stepper Configuration:**
   - `rotation_distance: 40` is standard for 2GT belts with 20T pulleys
   - `rotation_distance: 8` common for 8mm lead screw Z-axes
   - `microsteps: 16` or `32` typical for TMC drivers

3. **TMC Driver Setup:**
   - `interpolate: false` when using 32+ microsteps
   - `stealthchop_threshold: 0` disables StealthChop (quieter but less precise)
   - `sense_resistor: 0.110` standard for TMC2209

4. **Temperature Safety:**
   - Hotend `max_temp: 250-300°C` depending on all-metal vs PTFE
   - Bed `max_temp: 120-130°C` typical
   - Always `min_temp: 0` to enable thermistor failure detection

5. **Homing & Leveling:**
   - Voron 2.4 uses `[quad_gantry_level]` with 4 Z motors
   - Voron Trident uses `[z_tilt]` with 3 Z motors
   - Voron 0 uses simple 3-point `[bed_mesh]`

6. **Macro Patterns:**
   - `PRINT_START` and `PRINT_END` are standard slicer integration macros
   - `G32` often used for "home + level" routine
   - Variable storage in macros via `variable_name: value`

### Differences from gschpoozi Approach

- **Monolithic vs Modular:** These configs are mostly single-file (except RatRig/RatOS which uses includes heavily)
- **User Customization:** Voron configs have many commented sections for user to uncomment
- **gschpoozi Advantage:** Generates clean configs without user needing to edit, while still being modular

### Safety Considerations

All configs include:
- Explicit `min_temp` and `max_temp` limits
- `position_min` and `position_max` to prevent crashes
- PID tuning values (though users should re-tune)
- Retraction on homing to prevent crashes

## Usage Notes

- **DO NOT** copy these configs directly to your printer without modification
- Serial ports, thermistor types, and PID values are placeholders
- Use these as **reference only** to understand config patterns
- All configs require customization for specific hardware

## Sources & Documentation

- [Klipper Config Reference](https://www.klipper3d.org/Config_Reference.html)
- [Voron Documentation](https://docs.vorondesign.com/)
- [RatRig V-Core 3 Docs](https://docs.ratrig.com/)
- [Klipper Example Configs](https://github.com/Klipper3d/klipper/tree/master/config)
