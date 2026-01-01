# Quick Config Comparison

## Section Usage Patterns

Based on analysis of all reference configs, here are the most commonly used sections:

### Universal Sections (in almost all configs)
- `[stepper_x]`, `[stepper_y]`, `[stepper_z]` - Motor definitions
- `[extruder]` - Hotend configuration
- `[heater_bed]` - Heated bed configuration
- `[fan]` - Part cooling fan
- `[mcu]` - Microcontroller connection
- `[printer]` - Kinematics and motion limits

### Common But Not Universal
- `[tmc2209 stepper_*]` - TMC driver configuration (Voron, RatRig use extensively)
- `[probe]` - Auto bed leveling probe (Voron, high-end printers)
- `[heater_fan hotend_fan]` - Hotend cooling (separate from part cooling)
- `[temperature_sensor *]` - MCU and host temperature monitoring

### Advanced Z-Leveling
- `[quad_gantry_level]` - Voron 2.4 (4 Z motors)
- `[z_tilt]` - Voron Trident, RatRig V-Core 3 (3 Z motors)
- `[bed_mesh]` - Probe-based mesh leveling
- `[bed_screws]` - Manual leveling assistance

### Macro Patterns
- `[gcode_macro PRINT_START]` - Slicer start sequence
- `[gcode_macro PRINT_END]` - Slicer end sequence
- `[gcode_macro G32]` - Voron "home + level" routine
- `[gcode_macro PAUSE]`, `[RESUME]`, `[CANCEL_PRINT]` - Print control

## Kinematics Comparison

### CoreXY (Voron 2.4, Trident, V0, RatRig V-Core 3)
```ini
[printer]
kinematics: corexy
max_velocity: 200-300
max_accel: 1500-3000
max_z_velocity: 15
max_z_accel: 20-350
```

**Characteristics:**
- X/Y steppers work together (A/B motors)
- Higher acceleration possible
- Belt-driven X/Y, lead screw Z
- `rotation_distance: 40` for XY (2GT belt, 20T pulley)
- `rotation_distance: 8` for Z (8mm lead screw)

### Cartesian (Ender 3 V2, IDEX sample)
```ini
[printer]
kinematics: cartesian
max_velocity: 100-300
max_accel: 500-3000
```

**Characteristics:**
- Independent X/Y motors
- Simpler mechanics
- Lower typical speeds/accelerations
- Bed moves in Y (bed-slinger) or CoreXZ variants

## TMC Driver Patterns

### Standard TMC2209 Configuration
```ini
[tmc2209 stepper_x]
uart_pin: PC4
interpolate: false          # False when using 32 microsteps
run_current: 0.8            # Amps (depends on motor)
sense_resistor: 0.110       # Standard for TMC2209
stealthchop_threshold: 0    # 0 = disabled (SpreadCycle mode)
```

### Sensorless Homing (Voron 0.2)
```ini
[tmc2209 stepper_x]
uart_pin: PC4
run_current: 0.5
sense_resistor: 0.110
diag_pin: ^PC1              # Virtual endstop
driver_SGTHRS: 100          # Stallguard sensitivity
```

## Temperature Configurations

### Hotend Heater
```ini
[extruder]
heater_pin: PA2
sensor_type: ATC Semitec 104GT-2    # Or Generic 3950, EPCOS 100K B57560G104F
sensor_pin: PF4
min_temp: 0                  # ALWAYS 0 (enables failure detection)
max_temp: 250-300            # 250 for PTFE, 300+ for all-metal
```

### Heated Bed
```ini
[heater_bed]
heater_pin: PA1
sensor_type: EPCOS 100K B57560G104F
sensor_pin: PF3
min_temp: 0
max_temp: 120-130            # Typical for silicone pad heaters
```

## Z-Leveling Methods Compared

### 1. Manual (Ender 3 V2)
```ini
[bed_screws]
screw1: 30, 30
screw2: 200, 30
screw3: 200, 200
screw4: 30, 200
```
User manually adjusts screws, no automation.

### 2. Bed Mesh (Voron 0.2, most printers with probe)
```ini
[bed_mesh]
speed: 120
horizontal_move_z: 5
mesh_min: 20, 20
mesh_max: 200, 200
probe_count: 5, 5
```
Probes multiple points, creates software compensation mesh.

### 3. Z-Tilt (Voron Trident, RatRig - 3 Z motors)
```ini
[z_tilt]
z_positions:
    -50, 18
    125, 298
    300, 18
points:
    30, 5
    125, 195
    220, 5
```
Physically levels gantry using 3 independent Z motors.

### 4. Quad Gantry Level (Voron 2.4 - 4 Z motors)
```ini
[quad_gantry_level]
gantry_corners:
   -60,-10
   360,370
points:
   50,25
   50,275
   300,275
   300,25
```
Levels flying gantry using 4 independent Z motors (most advanced).

## Homing Strategies

### Standard Endstops
```ini
[stepper_x]
endstop_pin: ^PG6           # ^ = pullup enabled
position_endstop: 0
position_min: 0
position_max: 350
homing_speed: 50
homing_positive_dir: false  # Home toward 0
```

### Sensorless Homing (TMC stallguard)
```ini
[stepper_x]
endstop_pin: tmc2209_stepper_x:virtual_endstop
homing_retract_dist: 0      # Must be 0 for sensorless
```

### Safe Z Home (with probe)
```ini
[safe_z_home]
home_xy_position: 175, 175  # XY position to home Z
z_hop: 10                   # Lift Z before homing XY
```

### Homing Override (Voron Trident)
```ini
[homing_override]
axes: xyz
gcode:
    {% set home_all = 'X' not in params and 'Y' not in params and 'Z' not in params %}
    # ... custom homing sequence
```

## Fan Control Patterns

### Part Cooling Fan (always PWM)
```ini
[fan]
pin: PA8
```

### Hotend Fan (typically always-on above threshold)
```ini
[heater_fan hotend_fan]
pin: PE5
heater: extruder
heater_temp: 50.0           # Turn on above 50°C
```

### Controller Fan (MCU cooling)
```ini
[controller_fan controller_fan]
pin: PD12
stepper: stepper_x,stepper_y,stepper_z,extruder
```

## Probe Types

### BLTouch (servo-based)
```ini
[bltouch]
sensor_pin: ^PB7
control_pin: PB6
x_offset: -44
y_offset: -6
z_offset: 2.0               # User must calibrate
```

### Inductive Probe (Voron standard)
```ini
[probe]
pin: ^PB7
x_offset: 0
y_offset: 25.0
z_offset: 0                 # User must calibrate
speed: 10.0
samples: 3
sample_retract_dist: 2.0
```

### Beacon/Cartographer (eddy current - advanced)
```ini
[beacon]
serial: /dev/serial/by-id/...
x_offset: 0
y_offset: 20
mesh_main_direction: x
mesh_runs: 2
```

## Key Takeaways for gschpoozi

1. **Standardization**: Most printers follow similar patterns for basic sections
2. **Differentiation**: Advanced features (QGL, sensorless homing, dual MCU) add complexity
3. **Modularity**: RatOS shows value of modular includes (matches gschpoozi approach)
4. **Safety First**: All configs enforce temp limits, position limits, homing procedures
5. **User Macros**: PRINT_START/END are universal - gschpoozi implements these well
6. **TMC Drivers**: Nearly universal in modern printers, consistent parameter patterns
7. **Z-Leveling**: Method depends on Z motor count (1=mesh, 3=z_tilt, 4=QGL)
