# gschpoozi Usage Manual

Complete guide to configuring your 3D printer with the gschpoozi wizard.

## Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
- [Navigating the Wizard](#navigating-the-wizard)
- [Main Menu](#main-menu)
- [Board Configuration](#board-configuration)
- [Motion Configuration](#motion-configuration)
- [Components Configuration](#components-configuration)
- [Generated Config Files](#generated-config-files)
- [After Configuration](#after-configuration)
- [Safety Checklist](#safety-checklist)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

gschpoozi is a complete Klipper installation and configuration system. You only need two things:

```bash
# 1. Clone the repository
cd ~ && git clone https://github.com/gm-tc-collaborators/gschpoozi.git

# 2. Run the configuration wizard
~/gschpoozi/scripts/configure.sh
```

That's it! The script handles everything including Klipper installation if needed.

---

## Safety Warning (Read This First)

This project generates **hardware-critical** Klipper configuration (motors, endstops, heaters). A wrong pin or direction can cause crashes, damage, or fire.

- Always review generated files before restarting Klipper
- Keep your hand near emergency stop / power switch on the first home
- Prefer `STEPPER_BUZZ` / identification macros before any homing or movement

**Found a bug?** [File an issue on GitHub](https://github.com/gm-tc-collaborators/gschpoozi/issues/new/choose) with details about your hardware and the error.

**Notes:**
- Stepper discovery is informational only — you need to know your wiring/ports
- Macro defaults may need tuning for your specific printer setup

---

## Installation

### What You Need

- **A Raspberry Pi** (or similar SBC) connected to your printer
- **SSH access** to your Pi
- **Basic knowledge** of your printer's hardware (board type, motors, probe, etc.)

**You do NOT need Klipper pre-installed** - the script will guide you through the installtion if needed.

### Install Steps

1. **SSH into your Raspberry Pi:**
   ```bash
   ssh pi@your-printer-ip
   ```

2. **Clone gschpoozi:**
   ```bash
   cd ~
   git clone https://github.com/gm-tc-collaborators/gschpoozi.git
   ```

3. **Run the wizard:**
   ```bash
   ~/gschpoozi/scripts/configure.sh
   ```

The wizard will handle:
- Installation of Klipper, Moonraker, and Mainsail/Fluidd (if not already installed)
- Adding gschpoozi to Moonraker Update Manager (for automatic updates)
- Guide you through hardware configuration
- Generate ready-to-use config files

---

## Navigating the Wizard

The wizard uses a menu-driven terminal interface. Here's how to use it:

### Navigation Keys

| Key | Action |
|-----|--------|
| **1-9** | Select numbered menu options |
| **B** | Go back to previous menu |
| **Q** | Quit the wizard (progress is saved) |
| **Enter** | Confirm selection or accept default |

### Visual Indicators

```
  1) [✓] Boards              Already configured
  2) [ ] Motion              Not yet configured
  3) [→] Components          Currently selected
```

- **[✓]** - Section is complete
- **[ ]** - Section needs configuration
- **[→]** - Currently active/selected

### Saved State

Your selections are automatically saved as you go. If you quit and restart the wizard, all your previous choices are remembered. You can:
- Exit anytime and resume later
- Go back and change individual settings
- Re-generate configs after making changes

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

## Klipper Setup

The **Klipper Setup** section provides KIAUH-style component management and related tools.

### Menu Options

| Option | Description |
|--------|-------------|
| **1.1 Manage Klipper Components** | KIAUH-style status view with Install/Update/Remove/Reinstall |
| **1.2 CAN Interface Setup** | Configure can0, install can-utils, create persistent service |
| **1.3 Katapult / Flashing** | USB DFU and CAN firmware flashing helper |
| **1.4 Update Manager Fix** | Git fetch workaround for network issues |

### Manage Klipper Components

Shows installation status for all Klipper ecosystem components:
- **Klipper** - Core firmware
- **Moonraker** - API server
- **Mainsail** / **Fluidd** - Web interfaces
- **Crowsnest** - Camera streaming
- **Sonar** - Network keepalive
- **Timelapse** - Print timelapse plugin
- **KlipperScreen** - Touchscreen UI

Each component shows: installed status, version (from git), and service state (running/stopped/disabled).

Selecting a component offers context-appropriate actions:
- **Not installed**: Install
- **Installed**: Update, Remove (full uninstall), Reinstall

**Safety notes:**
- Install/remove actions may prompt for `sudo` and will modify system services.
- Full uninstall deletes component directories/venvs (while trying to preserve `~/printer_data/config`). Use with care.
- CAN helper does **not** enable hardware drivers (e.g., SPI overlays for mcp2515, slcan setups). It only configures an existing SocketCAN interface.
- For CAN users, interface persistence is required; the wizard will install a `can-<iface>.service` to bring CAN up on boot.
- Katapult/firmware flashing can brick boards if used incorrectly—double-check device selection and parameters.

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
    ├── calibration.cfg   # Motor identification macros
    ├── macros.cfg        # START_PRINT, END_PRINT, and building blocks
    └── macros-config.cfg # User-editable macro configuration variables
```

### Important Notes (Macros + Stepper Discovery)

- The generated macro suite is powerful but **not fully tested across printers**. Treat it as a starting point and validate behavior with safe, incremental tests.
- Stepper discovery is not currently a fully automated workflow. Use identification macros (`STEPPER_BUZZ`, `IDENTIFY_ALL_STEPPERS`, etc.) and verify each axis manually before homing.

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

### macros.cfg Contents

The main print macros with hardware-aware building blocks:

| Macro | Purpose |
|-------|---------|
| `START_PRINT` | Complete print start sequence |
| `END_PRINT` | Print end with parking and cooldown |
| `PAUSE` / `RESUME` | Pause and resume printing |
| `CANCEL_PRINT` | Cancel with safe shutdown |
| `M600` | Filament change |
| `LOAD_FILAMENT` / `UNLOAD_FILAMENT` | Filament management |

Building block macros (called by START_PRINT):

| Macro | Purpose |
|-------|---------|
| `_HOME_IF_NEEDED` | Conditional homing |
| `_HEAT_SOAK` | Bed temperature stabilization |
| `_CHAMBER_WAIT` | Chamber temperature wait |
| `_LEVEL_BED` | Auto-selects QGL or Z_TILT |
| `_BED_MESH` | Adaptive, full, or saved mesh |
| `_CLEAN_NOZZLE` | Brush/wipe nozzle |
| `_PURGE` | Line, blob, or adaptive purge |
| `_PARK` | Park toolhead at end |
| `_STATUS_LED` | LED color updates |

### macros-config.cfg Contents

User-editable configuration variables. Edit this file to customize macro behavior without modifying the macros themselves:

```ini
[gcode_macro _MACRO_CONFIG]
# Printer dimensions (from wizard)
variable_bed_size_x: 300
variable_bed_size_y: 300
variable_bed_center_x: 150
variable_bed_center_y: 150

# Heat soak
variable_heat_soak_time: 0           # Minutes (0=disabled)

# Bed mesh
variable_bed_mesh_mode: "adaptive"   # adaptive/full/saved/none

# Nozzle cleaning
variable_brush_enabled: False
variable_brush_x: 50
variable_brush_y: 305

# Purge
variable_purge_style: "line"         # line/blob/adaptive/none
variable_purge_amount: 30

# LED status
variable_led_enabled: False
variable_led_name: "status_led"

# Park position
variable_park_position: "front"      # front/back/center

# Cooldown
variable_turn_off_bed: True
variable_turn_off_extruder: True
variable_motor_off_delay: 300        # Seconds
```

---

## Slicer Integration

### Start G-code

Configure your slicer to call `START_PRINT` with temperature parameters:

#### PrusaSlicer / SuperSlicer / OrcaSlicer

**Basic:**
```gcode
START_PRINT BED=[first_layer_bed_temperature] EXTRUDER=[first_layer_temperature]
```

**With chamber and material:**
```gcode
START_PRINT BED=[first_layer_bed_temperature] EXTRUDER=[first_layer_temperature] CHAMBER=[chamber_temperature] MATERIAL=[filament_type]
```

**Full adaptive (for adaptive mesh/purge):**
```gcode
START_PRINT BED=[first_layer_bed_temperature] EXTRUDER=[first_layer_temperature] CHAMBER=[chamber_temperature] MATERIAL=[filament_type] PRINT_MIN={first_layer_print_min[0]},{first_layer_print_min[1]} PRINT_MAX={first_layer_print_max[0]},{first_layer_print_max[1]}
```

#### Cura

```gcode
START_PRINT BED={material_bed_temperature_layer_0} EXTRUDER={material_print_temperature_layer_0} MATERIAL={material_type}
```

#### Simplify3D

```gcode
START_PRINT BED=[bed0_temperature] EXTRUDER=[extruder0_temperature]
```

### End G-code

All slicers (simple):

```gcode
END_PRINT
```

### START_PRINT Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `BED` | int | 60 | Bed temperature |
| `EXTRUDER` | int | 200 | Extruder temperature |
| `CHAMBER` | int | 0 | Chamber temperature (0=skip) |
| `MATERIAL` | string | PLA | Filament type for tuning |
| `MESH` | string | config | Mesh mode override: adaptive/full/saved/none |
| `PURGE` | string | config | Purge style override: line/blob/adaptive/none |

---

## After Configuration

### 1. Update printer.cfg

Add includes to your `printer.cfg`:

```ini
[include gschpoozi/hardware.cfg]
[include gschpoozi/macros-config.cfg]
[include gschpoozi/macros.cfg]
[include gschpoozi/calibration.cfg]

# Your overrides below...
```

**Note:** `macros-config.cfg` must be included BEFORE `macros.cfg` since the macros reference the config variables.

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

## Safety Checklist

**Before powering motors or heaters, complete this checklist:**

### Pre-Flight Checks

1. **Review Generated Config Files**
   - Open `~/printer_data/config/gschpoozi/hardware.cfg`
   - Verify all pin assignments match your actual wiring
   - Check thermistor types match your hardware
   - Verify probe type and settings

2. **Verify MCU Connection**
   ```bash
   ls /dev/serial/by-id/
   ```
   Ensure your board appears and the serial path matches the config.

3. **Check Klipper Starts Without Errors**
   - Restart Klipper: `sudo systemctl restart klipper`
   - Check logs: `journalctl -u klipper -f`
   - Look for any `mcu` or `config` errors

### Motor Safety Tests

**Do these BEFORE homing:**

4. **Identify Each Motor**
   ```gcode
   STEPPER_BUZZ STEPPER=stepper_x
   STEPPER_BUZZ STEPPER=stepper_y
   STEPPER_BUZZ STEPPER=stepper_z
   STEPPER_BUZZ STEPPER=extruder
   ```
   Each motor should buzz briefly. Verify the correct motor moves for each command.

5. **Check Movement Directions**
   - Move each axis manually (motors off)
   - Note which way is positive
   - Use `SET_KINEMATIC_POSITION X=150 Y=150 Z=50` to set a fake position
   - Send `G1 X160 F1000` - X should move in positive direction
   - If wrong, add `!` to invert: `dir_pin: !PF12`

### Homing Safety

6. **First Home Attempt**
   - **Keep hand on power switch** or emergency stop
   - Home X first: `G28 X`
   - Home Y: `G28 Y`
   - Home Z: `G28 Z` (ensure probe is working first)
   - Watch for crashes - stop immediately if wrong direction

### Heater Safety

7. **Verify Thermistors Read Correctly**
   - Room temperature should show ~20-25°C
   - If reading -14°C or 0°C: wiring issue
   - If reading very high: wrong thermistor type

8. **PID Tune Before Printing**
   ```gcode
   PID_CALIBRATE HEATER=extruder TARGET=200
   PID_CALIBRATE HEATER=heater_bed TARGET=60
   SAVE_CONFIG
   ```

### Probe Calibration

9. **Calibrate Probe Z Offset**
   ```gcode
   G28
   PROBE_CALIBRATE
   ```
   Follow the paper test procedure.

10. **Test Bed Mesh**
    ```gcode
    BED_MESH_CALIBRATE
    ```
    Ensure probe reaches all points without crashing.

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

### Update Manager Issues

**Symptom**: Update Manager refresh hangs or never shows gschpoozi updates

**Manual update workaround**:
```bash
cd ~/gschpoozi && git pull
```

Or to force-reset to latest (discards any local changes):
```bash
cd ~/gschpoozi && git fetch origin && git reset --hard origin/main
```

**If `git fetch` hangs** (common on some networks):

The wizard includes a fix: **Klipper Setup → Update Manager Fix → Enable workaround**

Or manually:
```bash
cd ~/gschpoozi && git config http.version HTTP/1.1
```

This forces HTTP/1.1 which resolves fetch hangs on some network configurations.

### Hotend Temperature Reading Wrong (~350°C)

**Symptom**: `ADC out of range` error, temperature reads ~350°C

**Cause**: Wrong `pullup_resistor` value for your board

**Fix**: Re-run wizard → **Extruder** → select correct pullup:
- **2.2kΩ** for most toolboards (EBB, SHT36, Nitehawk, etc.)
- **4.7kΩ** for most mainboards

---

## Re-running the Wizard

Your settings are saved in:
- `~/printer_data/config/.gschpoozi_state.json` - All wizard selections

To start fresh:
```bash
rm ~/printer_data/config/.gschpoozi_state.json
~/gschpoozi/scripts/configure.sh
```

To update a single setting, just run the wizard and navigate to that option - previous values are shown as defaults.

---

## Getting Help

- **GitHub Issues**: [github.com/gm-tc-collaborators/gschpoozi/issues](https://github.com/gm-tc-collaborators/gschpoozi/issues)
- **Klipper Documentation**: [klipper3d.org](https://www.klipper3d.org)
- **Klipper Discord**: General Klipper help

---

*Generated configs are meant as a starting point. Always verify settings match your specific hardware before powering motors or heaters.*
