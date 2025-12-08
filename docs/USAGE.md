# gschpoozi Usage Manual

Complete guide to configuring your 3D printer with the gschpoozi wizard.

## Table of Contents

- [Installation](#installation)
- [Running the Wizard](#running-the-wizard)
- [Main Menu](#main-menu)
- [Board Configuration](#board-configuration)
- [Motion Configuration](#motion-configuration)
- [Components Configuration](#components-configuration)
- [Generated Config Files](#generated-config-files)
- [After Configuration](#after-configuration)
- [Troubleshooting](#troubleshooting)

---

## Installation

### Prerequisites

- Klipper installed and running
- SSH access to your printer
- Basic familiarity with your printer's hardware

### Install gschpoozi

```bash
cd ~
git clone https://github.com/gueee/gschpoozi.git
```

### Optional: Add to Moonraker for Updates

Add to your `moonraker.conf`:

```ini
[update_manager gschpoozi]
type: git_repo
primary_branch: main
path: ~/gschpoozi
origin: https://github.com/gueee/gschpoozi.git
install_script: scripts/update-manager/moonraker-update.sh
is_system_service: False
managed_services: klipper
info_tags:
    desc=gschpoozi Configuration Framework
```

---

## Running the Wizard

Start the configuration wizard:

```bash
~/gschpoozi/scripts/configure.sh
```

The wizard uses a menu-driven interface. Navigate using:
- **Number keys** - Select menu options
- **B** - Go back to previous menu
- **Q** - Quit the wizard

Your selections are automatically saved and will be remembered if you exit and restart.

---

## Main Menu

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                              gschpoozi Main Menu                              ║
╚═══════════════════════════════════════════════════════════════════════════════╝

  1) [✓] Boards              Main board and toolboard selection
  2) [✓] Motion              Kinematics, steppers, rotation distance
  3) [ ] Components          Extruder, thermistors, probes, fans
  4) [ ] Generate Config     Create your Klipper configuration

  Q) Quit
```

Complete sections 1-3, then use option 4 to generate your config files.

---

## Board Configuration

### Main Board Selection

Select your controller board from the list. Supported boards include:

| Manufacturer | Boards |
|-------------|--------|
| **BigTreeTech** | Octopus v1.1, Octopus Pro, Manta M8P v2, SKR 3, SKR Mini E3 v3, SKR Pico |
| **Mellow** | Fly Super8, Fly Gemini v3 |
| **Fysetc** | Spider v2.2 |

After selecting a board, you'll be prompted to assign motor ports.

### MCU Serial Detection

The wizard can automatically detect connected MCUs:

```
Detected USB MCU devices:
  1) usb-Klipper_stm32f446xx_1234567890-if00
     BTT Octopus

Select MCU: 1
```

### Toolboard Selection (Optional)

If you have a CAN or USB toolhead board:

| Manufacturer | Boards |
|-------------|--------|
| **BigTreeTech** | EBB36 v1.2, EBB42 v1.2, EBB SB2209, EBB SB2240 |
| **Mellow** | SHT36 v2, SHT42, Fly SB2040 |
| **Orbiter** | Orbitool SO3 |
| **LDO** | Nitehawk SB, Nitehawk 36 |

Toolboard connection types:
- **USB** - Direct USB connection
- **CAN** - CAN bus (requires canbus_uuid)

---

## Motion Configuration

### Kinematics Type

| Option | Description |
|--------|-------------|
| **CoreXY** | Standard CoreXY (Voron, RatRig, etc.) |
| **CoreXY AWD** | 4-motor CoreXY (all-wheel drive) |
| **Cartesian** | Bed slinger (Ender 3, Prusa, etc.) |
| **CoreXZ** | CoreXZ kinematics |

### Z Stepper Configuration

Configure your Z axis:

- **Number of Z motors** (1-4)
- **Leveling method**:
  - Single Z: Manual bed leveling
  - 2 Z motors: `[z_tilt]` bed tilt
  - 3 Z motors: `[z_tilt]` three-point
  - 4 Z motors: `[quad_gantry_level]`

### Bed Size

Enter your print area dimensions:
- **X size** (mm)
- **Y size** (mm)
- **Z height** (mm)

### Stepper Drivers

Select driver type for each axis:

| Driver | Interface | Features |
|--------|-----------|----------|
| TMC2209 | UART | StealthChop, sensorless homing |
| TMC2208 | UART | StealthChop |
| TMC5160 | SPI | High current, StealthChop |
| TMC2130 | SPI | StealthChop, sensorless homing |
| A4988 | Step/Dir | Basic driver |
| DRV8825 | Step/Dir | Basic driver |

### Rotation Distance

Configure per-axis stepper parameters:

#### Step Angle
- **1.8°** - Standard steppers (200 steps/rev)
- **0.9°** - High resolution (400 steps/rev, LDO motors)

#### Microsteps
- **16** - Recommended default
- **32/64/128/256** - Higher resolution (TMC drivers)

#### X/Y Rotation Distance (Belt-driven)

```
rotation_distance = pulley_teeth × belt_pitch
```

Common values:
| Belt | Pulley | Rotation Distance |
|------|--------|-------------------|
| GT2 (2mm) | 20T | 40mm |
| GT2 (2mm) | 16T | 32mm |
| GT3 (3mm) | 20T | 60mm |

#### Z Rotation Distance (Lead screw)

```
rotation_distance = lead = pitch × starts
```

Common lead screws:
| Type | Pitch | Starts | Lead |
|------|-------|--------|------|
| T8×8 | 2mm | 4 | 8mm |
| T8×4 | 2mm | 2 | 4mm |
| T8×2 | 2mm | 1 | 2mm |

#### Extruder Rotation Distance

Preset values for common extruders:

| Extruder | Rotation Distance |
|----------|-------------------|
| Bondtech LGX / LGX Lite | 22.6789511 |
| Bondtech BMG / Clockwork | 4.637 |
| Sherpa Mini | 33.500 |
| Orbiter 1.5 / 2.0 | 7.824 |
| E3D Titan | 5.7 |

**Note**: These are starting values. Always calibrate using the [rotation distance calibration procedure](https://www.klipper3d.org/Rotation_Distance.html).

### Motor Port Assignment

The wizard shows available motor ports on your board:

```
Available motor ports on BTT Octopus Pro:
  MOTOR_0 (X)  - PE2/PE3/PE4
  MOTOR_1 (Y)  - PE6/PA1/PE5
  MOTOR_2 (Z)  - PG0/PF15/PG1
  ...

Assign stepper_x to port: MOTOR_0
```

---

## Components Configuration

### Extruder

#### Type
- **Direct Drive** - Extruder mounted on toolhead
- **Bowden** - Extruder mounted on frame (longer tube)

Bowden configuration automatically sets:
- Higher `max_extrude_only_distance` (500mm for tube loading)
- Higher starting `pressure_advance` (0.5 vs 0.04)

#### Hotend Thermistor

| Option | Usage |
|--------|-------|
| Generic 3950 | Most common, Creality, etc. |
| ATC Semitec 104GT-2 | E3D, Slice Engineering |
| PT1000 | High-temp, direct connection |
| PT1000 (MAX31865) | High-temp, amplifier board |
| SliceEngineering 450 | 450°C capable |

#### Pullup Resistor

If your board has selectable pullups:
- **4700Ω** - Most common
- **2200Ω** - Some boards
- **1000Ω** - PT1000 direct

### Heated Bed

#### Bed Thermistor
- **Generic 3950** - Most common
- **EPCOS 100K B57560G104F** - Keenovo heaters, generic
- **Keenovo** (automatically uses Generic 3950)
- **PT1000** - High quality beds

### Probe Configuration

#### Probe Types

| Type | Description |
|------|-------------|
| **Beacon** | Eddy current probe (USB) |
| **Cartographer** | Eddy current probe (USB) |
| **BTT Eddy** | BTT eddy current probe |
| **BLTouch** | Servo-deployed touch probe |
| **Klicky** | Magnetically attached probe |
| **Inductive** | Proximity sensor |
| **Endstop** | Physical Z endstop |

#### Probe USB Detection

For USB probes (Beacon, Cartographer, Eddy), the wizard detects connected devices:

```
Detected probe devices:
  1) usb-Beacon_RevH_ABC123-if00

Select your probe: 1
```

### Endstops and Homing

#### X/Y Endstop Location
- **Min** - Endstop at X=0 / Y=0
- **Max** - Endstop at X=max / Y=max

#### Sensorless Homing
Available with TMC2209/TMC2130 drivers. Enables homing without physical switches.

#### Position Limits

Configure travel limits:
- `position_min` - Minimum position (can be negative for nozzle wipe)
- `position_endstop` - Where the endstop triggers
- `position_max` - Maximum travel (usually = bed size)

### Fan Configuration

#### Fan Types

| Fan | Klipper Section | Purpose |
|-----|-----------------|---------|
| Part Cooling | `[fan]` | Cools printed parts |
| Hotend | `[heater_fan]` | Cools hotend heatsink |
| Controller | `[controller_fan]` | Cools electronics |
| Exhaust | `[fan_generic]` | Chamber exhaust |
| Chamber | `[temperature_fan]` or `[fan_generic]` | Chamber circulation |
| RSCS/Filter | `[fan_generic]` | Recirculating filter |
| Radiator | `[heater_fan]` | Water cooling |

#### Multi-Pin Fans
For dual fans on a single output, select a second port to create a `[multi_pin]` configuration.

#### Advanced Fan Settings
- **Max Power** (0.0-1.0)
- **Cycle Time** (PWM frequency)
- **Kick Start Time** (startup burst)
- **Shutdown Speed** (speed when MCU disconnects)

### Lighting

#### LED Types

| Type | Section | Description |
|------|---------|-------------|
| NeoPixel | `[neopixel]` | WS2812B addressable LEDs |
| DotStar | `[dotstar]` | APA102 addressable LEDs |
| Simple LED | `[output_pin]` | PWM-controlled single color |

Configure:
- **Pin** - Data pin (NeoPixel/DotStar) or PWM pin
- **Chain Count** - Number of LEDs
- **Color Order** - GRB, RGB, RGBW, etc.

### Extras

#### Filament Sensor
Enables `[filament_switch_sensor]` with:
- Pause on runout
- M600 filament change macro

#### Chamber Temperature Sensor
Adds `[temperature_sensor chamber]` for monitoring enclosure temperature.

---

## Generated Config Files

After configuration, generate your files:

```
Main Menu → 4) Generate Config
```

### Output Location

```
~/printer_data/config/
├── printer.cfg           # Your main file (create if doesn't exist)
└── gschpoozi/            # Generated by wizard
    ├── hardware.cfg      # MCU, steppers, heaters, fans, probe
    └── calibration.cfg   # Motor identification macros
```

### hardware.cfg Contents

```ini
# ═══════════════════════════════════════════════════════════════════════════════
# HARDWARE CONFIGURATION
# Generated by gschpoozi - 2024-01-15 14:30
# Board: BTT Octopus Pro
# ═══════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# MCU
# ─────────────────────────────────────────────────────────────────────────────
[mcu]
serial: /dev/serial/by-id/usb-Klipper_stm32f446xx_...

# ─────────────────────────────────────────────────────────────────────────────
# PRINTER
# ─────────────────────────────────────────────────────────────────────────────
[printer]
kinematics: corexy
max_velocity: 500
max_accel: 10000
...

# ─────────────────────────────────────────────────────────────────────────────
# STEPPERS
# ─────────────────────────────────────────────────────────────────────────────
[stepper_x]
step_pin: PF13
dir_pin: PF12
enable_pin: !PF14
microsteps: 16
rotation_distance: 40
...

# ─────────────────────────────────────────────────────────────────────────────
# TMC DRIVERS
# ─────────────────────────────────────────────────────────────────────────────
[tmc2209 stepper_x]
uart_pin: PC4
run_current: 0.8
stealthchop_threshold: 999999
...

# ─────────────────────────────────────────────────────────────────────────────
# EXTRUDER
# ─────────────────────────────────────────────────────────────────────────────
[extruder]
...

# ─────────────────────────────────────────────────────────────────────────────
# HEATED BED
# ─────────────────────────────────────────────────────────────────────────────
[heater_bed]
...

# ─────────────────────────────────────────────────────────────────────────────
# FANS
# ─────────────────────────────────────────────────────────────────────────────
[fan]
...

# ─────────────────────────────────────────────────────────────────────────────
# PROBE
# ─────────────────────────────────────────────────────────────────────────────
[beacon]
...
```

### calibration.cfg Contents

Includes helper macros for initial setup:

| Macro | Purpose |
|-------|---------|
| `IDENTIFY_ALL_STEPPERS` | Buzz each motor to identify wiring |
| `IDENTIFY_STEPPER STEPPER=stepper_x` | Buzz single motor |
| `QUERY_TMC_STATUS` | Check TMC driver communication |
| `COREXY_DIRECTION_CHECK` | Verify XY movement directions |
| `Z_DIRECTION_CHECK` | Verify all Z motors move same direction |
| `STEPPER_CALIBRATION_WIZARD` | Step-by-step calibration guide |

For CoreXY AWD:
| Macro | Purpose |
|-------|---------|
| `AWD_TEST_PAIR_A` | Test motors X+Y with X1+Y1 disabled |
| `AWD_TEST_PAIR_B` | Test motors X1+Y1 with X+Y disabled |
| `AWD_FULL_TEST` | Complete AWD verification sequence |

---

## After Configuration

### 1. Update printer.cfg

Add includes to your `printer.cfg`:

```ini
[include gschpoozi/hardware.cfg]
[include gschpoozi/calibration.cfg]

# Your overrides below...
```

### 2. Initial Startup Checklist

1. **Verify MCU connection**
   ```
   ls /dev/serial/by-id/
   ```

2. **Check stepper identification**
   ```
   IDENTIFY_ALL_STEPPERS
   ```
   Watch each motor and verify it matches the expected axis.

3. **Verify TMC communication** (if using TMC drivers)
   ```
   QUERY_TMC_STATUS
   ```

4. **Check movement directions**
   ```
   COREXY_DIRECTION_CHECK  # or appropriate check for your kinematics
   ```

5. **Calibrate Z offset**
   ```
   PROBE_CALIBRATE
   ```

6. **PID tune heaters**
   ```
   PID_CALIBRATE HEATER=extruder TARGET=200
   PID_CALIBRATE HEATER=heater_bed TARGET=60
   ```

7. **Calibrate extruder rotation distance**
   Follow [Klipper's rotation distance guide](https://www.klipper3d.org/Rotation_Distance.html)

### 3. Common Overrides

Add these to `printer.cfg` after the includes:

```ini
# Calibrated values
[extruder]
rotation_distance: 22.452  # Your calibrated value
pressure_advance: 0.038    # Your calibrated value

[stepper_x]
position_endstop: 300.5    # Fine-tuned endstop position

[probe]
z_offset: 1.234            # Or let SAVE_CONFIG handle this
```

---

## Troubleshooting

### MCU Not Detected

**Symptom**: `ls /dev/serial/by-id/` shows nothing

**Solutions**:
1. Check USB cable connection
2. Verify Klipper firmware is flashed
3. Try different USB port
4. Check for permission issues: `ls -la /dev/serial/by-id/`

### TMC Driver Errors

**Symptom**: "Unable to read tmc uart" errors

**Solutions**:
1. Check UART pin assignment matches your board
2. Verify jumpers are set for UART mode (not standalone)
3. Check driver is seated properly
4. Run `QUERY_TMC_STATUS` to diagnose

### Wrong Motor Movement

**Symptom**: Motor moves wrong direction or wrong motor moves

**Solutions**:
1. Run `IDENTIFY_ALL_STEPPERS` to verify wiring
2. Swap motor cables to correct positions
3. Or invert direction in config: `dir_pin: !PF12`

### Toolboard Not Connecting

**CAN bus issues**:
1. Verify CAN cable connections
2. Check termination resistors (120Ω)
3. Run `~/klippy-env/bin/python ~/klipper/scripts/canbus_query.py can0`

**USB toolboard issues**:
1. Check USB cable (data-capable, not charge-only)
2. Verify `ls /dev/serial/by-id/` shows device

### Homing Fails

**Physical endstop**:
1. Check endstop wiring
2. Verify pin assignment
3. Test with `QUERY_ENDSTOPS`

**Sensorless homing**:
1. Verify TMC driver is configured
2. Adjust `driver_SGTHRS` value
3. Ensure proper `homing_retract_dist`

### Probe Issues

**Beacon/Cartographer/Eddy not found**:
1. Check USB connection
2. Verify serial path: `ls /dev/serial/by-id/*beacon*`
3. Check probe firmware is up to date

**BLTouch not deploying**:
1. Verify control_pin wiring
2. Check servo signal

---

## Re-running the Wizard

Your settings are saved in:
- `~/gschpoozi/.wizard-state` - Wizard selections
- `~/gschpoozi/.hardware-state.json` - Port assignments

To start fresh:
```bash
rm ~/gschpoozi/.wizard-state ~/gschpoozi/.hardware-state.json
~/gschpoozi/scripts/configure.sh
```

To update a single setting, just run the wizard and navigate to that option - previous values are shown as defaults.

---

## Getting Help

- **GitHub Issues**: [github.com/gueee/gschpoozi/issues](https://github.com/gueee/gschpoozi/issues)
- **Klipper Documentation**: [klipper3d.org](https://www.klipper3d.org)
- **Klipper Discord**: General Klipper help

---

*Generated configs are meant as a starting point. Always verify settings match your specific hardware before powering motors or heaters.*
