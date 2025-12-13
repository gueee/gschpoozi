# gschpoozi Wizard Menu Structure

This document defines the complete menu structure for the gschpoozi configuration wizard.
Each menu item maps directly to Klipper config sections.

**Version:** 2.0 (Refactor)  
**Status:** Draft - Open for Review

---

## Menu ID System

Menu IDs use decimal hierarchy:
- `1.x` = Klipper Setup (installation, no config output)
- `2.x` = Hardware Setup (generates printer.cfg)
- `3.x` = Tuning & Optimization

---

## Complete Menu Structure (Text)

```
0. MAIN MENU
├── 1. Klipper Setup (Installation)
├── 2. Hardware Setup (Configuration)
└── 3. Tuning & Optimization

1. KLIPPER SETUP (no config output - installation only)
├── 1.1 Klipper
├── 1.2 Moonraker
├── 1.3 Web Interface
│   ├── 1.3.1 Mainsail
│   └── 1.3.2 Fluidd
└── 1.4 Optional Services
    ├── 1.4.1 Crowsnest (camera streaming)
    ├── 1.4.2 KlipperScreen
    ├── 1.4.3 Timelapse
    └── 1.4.4 Sonar (network keepalive)

2. HARDWARE SETUP
├── 2.1 MCU Configuration
│   ├── 2.1.1 Main Board                    → [mcu]
│   │   ├── Board selection (from templates/boards/)
│   │   └── Serial ID / CAN UUID
│   ├── 2.1.2 Toolhead Board                → [mcu toolboard]
│   │   ├── Toolboard selection (from templates/toolboards/)
│   │   ├── Connection type (USB / CAN)
│   │   └── Serial ID / CAN UUID
│   ├── 2.1.3 Host MCU                      → [mcu rpi]
│   │   └── Enable host MCU (for ADXL, GPIO, etc.)
│   └── 2.1.4 Additional MCUs               → [mcu name]
│       └── MMU, expansion boards, etc.
│
├── 2.2 Printer Settings                    → [printer]
│   ├── 2.2.1 Kinematics
│   │   ├── CoreXY
│   │   ├── CoreXY AWD (All Wheel Drive)
│   │   ├── Cartesian
│   │   └── CoreXZ
│   ├── 2.2.2 max_velocity
│   ├── 2.2.3 max_accel
│   ├── 2.2.4 max_z_velocity
│   ├── 2.2.5 max_z_accel
│   └── 2.2.6 square_corner_velocity
│
├── 2.3 X Axis
│   ├── 2.3.1 Stepper X                     → [stepper_x]
│   │   ├── 2.3.1.1 Motor port (MOTOR_0, MOTOR_1, etc.)
│   │   ├── 2.3.1.2 rotation_distance
│   │   │   ├── Belt pitch (2mm GT2, 3mm HTD)
│   │   │   └── Pulley teeth (16T, 20T, etc.)
│   │   ├── 2.3.1.3 microsteps (16, 32, 64, 128, 256)
│   │   ├── 2.3.1.4 full_steps_per_rotation (200=1.8°, 400=0.9°)
│   │   ├── 2.3.1.5 Endstop
│   │   │   ├── Physical endstop (port selection)
│   │   │   ├── Sensorless homing
│   │   │   └── On toolboard (if applicable)
│   │   ├── 2.3.1.6 position_endstop
│   │   ├── 2.3.1.7 position_min
│   │   ├── 2.3.1.8 position_max
│   │   ├── 2.3.1.9 homing_speed
│   │   └── 2.3.1.10 homing_retract_dist
│   ├── 2.3.2 TMC Driver X                  → [tmc2209/5160/2130 stepper_x]
│   │   ├── 2.3.2.1 Driver type (TMC2209, TMC5160, TMC2130, TMC2660)
│   │   ├── 2.3.2.2 run_current
│   │   ├── 2.3.2.3 interpolate
│   │   ├── 2.3.2.4 sense_resistor (TMC5160 only)
│   │   ├── 2.3.2.5 UART config (uart_pin)
│   │   ├── 2.3.2.6 SPI config (cs_pin, spi_bus)
│   │   └── 2.3.2.7 Advanced tuning (TBL, TOFF, StallGuard)
│   └── 2.3.3 Stepper X1 (AWD only)         → [stepper_x1]
│       └── 2.3.4 TMC Driver X1             → [tmc driver stepper_x1]
│
├── 2.4 Y Axis
│   ├── 2.4.1 Stepper Y                     → [stepper_y]
│   │   └── (same structure as 2.3.1)
│   ├── 2.4.2 TMC Driver Y                  → [tmc driver stepper_y]
│   │   └── (same structure as 2.3.2)
│   └── 2.4.3 Stepper Y1 (AWD only)         → [stepper_y1]
│       └── 2.4.4 TMC Driver Y1             → [tmc driver stepper_y1]
│
├── 2.5 Z Axis
│   ├── 2.5.1 Z Motor Count (1, 2, 3, or 4)
│   │   └── Auto-selects leveling method (none, bed_tilt, z_tilt, QGL)
│   ├── 2.5.2 Stepper Z                     → [stepper_z]
│   │   ├── Motor port
│   │   ├── rotation_distance (leadscrew pitch)
│   │   │   ├── Common: 8mm (T8 leadscrew)
│   │   │   ├── Common: 4mm (high-speed)
│   │   │   └── Custom value
│   │   ├── microsteps
│   │   ├── full_steps_per_rotation
│   │   ├── Endstop / probe virtual endstop
│   │   ├── position_min (usually negative for probe clearance)
│   │   ├── position_max (Z height)
│   │   ├── homing_speed
│   │   └── homing_retract_dist
│   ├── 2.5.3 TMC Driver Z                  → [tmc driver stepper_z]
│   ├── 2.5.4 Stepper Z1 (if count ≥ 2)     → [stepper_z1]
│   ├── 2.5.5 TMC Driver Z1
│   ├── 2.5.6 Stepper Z2 (if count ≥ 3)     → [stepper_z2]
│   ├── 2.5.7 TMC Driver Z2
│   ├── 2.5.8 Stepper Z3 (if count = 4)     → [stepper_z3]
│   └── 2.5.9 TMC Driver Z3
│
├── 2.6 Extruder
│   ├── 2.6.1 Extruder Count (1-4 for multi-material)
│   ├── 2.6.2 Extruder 0                    → [extruder]
│   │   ├── 2.6.2.1 Motor Location
│   │   │   ├── Mainboard (port selection)
│   │   │   └── Toolboard (port selection)
│   │   ├── 2.6.2.2 Extruder Type
│   │   │   ├── Sherpa Mini → rotation_distance: 22.68, gear_ratio: 50:10
│   │   │   ├── Orbiter v2.0 → rotation_distance: 4.637, gear_ratio: 7.5:1
│   │   │   ├── Orbiter v2.5 → rotation_distance: 4.637, gear_ratio: 7.5:1
│   │   │   ├── Smart Orbiter v3 → rotation_distance: 4.69, gear_ratio: 7.5:1
│   │   │   ├── Clockwork 2 → rotation_distance: 22.68, gear_ratio: 50:10
│   │   │   ├── Galileo 2 → rotation_distance: 47.088, gear_ratio: 9:1
│   │   │   ├── LGX Lite → rotation_distance: 8, gear_ratio: 44:8
│   │   │   ├── BMG → rotation_distance: 22.68, gear_ratio: 50:17
│   │   │   ├── VZ-Hextrudort → custom config
│   │   │   └── Custom → manual entry
│   │   ├── 2.6.2.3 Stepper Settings
│   │   │   ├── microsteps
│   │   │   └── full_steps_per_rotation
│   │   ├── 2.6.2.4 Hotend Configuration
│   │   │   ├── nozzle_diameter (0.4, 0.5, 0.6, 0.8)
│   │   │   ├── filament_diameter (1.75, 2.85)
│   │   │   ├── Heater port → heater_pin
│   │   │   ├── Thermistor type → sensor_type
│   │   │   │   ├── Generic 3950
│   │   │   │   ├── ATC Semitec 104GT-2
│   │   │   │   ├── ATC Semitec 104NT-4-R025H42G
│   │   │   │   ├── PT1000 (direct)
│   │   │   │   ├── PT1000 + MAX31865
│   │   │   │   ├── PT100 + MAX31865
│   │   │   │   ├── SliceEngineering 450
│   │   │   │   └── NTC 100K beta 3950
│   │   │   ├── Thermistor port → sensor_pin
│   │   │   ├── pullup_resistor (for PT1000 direct)
│   │   │   ├── min_temp
│   │   │   └── max_temp (based on thermistor)
│   │   ├── 2.6.2.5 Extrusion Settings
│   │   │   ├── Drive type (Direct Drive / Bowden)
│   │   │   ├── max_extrude_only_distance
│   │   │   ├── max_extrude_cross_section
│   │   │   ├── max_extrude_only_velocity
│   │   │   ├── max_extrude_only_accel
│   │   │   └── min_extrude_temp
│   │   ├── 2.6.2.6 Pressure Advance
│   │   │   ├── pressure_advance (default by drive type)
│   │   │   └── pressure_advance_smooth_time
│   │   └── 2.6.2.7 PID Values
│   │       ├── pid_Kp
│   │       ├── pid_Ki
│   │       └── pid_Kd (or placeholder for PID_CALIBRATE)
│   ├── 2.6.3 TMC Driver Extruder           → [tmc driver extruder]
│   ├── 2.6.4 Extruder 1 (if multi)         → [extruder1]
│   ├── 2.6.5 Extruder 2 (if multi)         → [extruder2]
│   └── 2.6.6 Extruder 3 (if multi)         → [extruder3]
│
├── 2.7 Heated Bed                          → [heater_bed]
│   ├── 2.7.1 Heater port → heater_pin
│   ├── 2.7.2 Thermistor type → sensor_type
│   │   ├── Generic 3950
│   │   ├── NTC 100K beta 3950
│   │   ├── Keenovo silicone heater thermistor
│   │   └── Custom
│   ├── 2.7.3 Thermistor port → sensor_pin
│   ├── 2.7.4 pullup_resistor (if needed)
│   ├── 2.7.5 min_temp
│   ├── 2.7.6 max_temp
│   └── 2.7.7 PID Values (pid_Kp, pid_Ki, pid_Kd)
│
├── 2.8 Fans
│   ├── 2.8.1 Part Cooling Fan              → [fan]
│   │   ├── Pin (mainboard or toolboard)
│   │   ├── Multi-pin support               → [multi_pin]
│   │   ├── max_power
│   │   ├── cycle_time
│   │   ├── hardware_pwm
│   │   ├── kick_start_time
│   │   └── off_below
│   ├── 2.8.2 Hotend Fan                    → [heater_fan hotend_fan]
│   │   ├── Pin (mainboard or toolboard)
│   │   ├── heater (usually "extruder")
│   │   ├── heater_temp (turn-on threshold)
│   │   ├── max_power
│   │   └── kick_start_time
│   ├── 2.8.3 Controller Fan                → [controller_fan]
│   │   ├── Pin
│   │   ├── stepper (which steppers trigger it)
│   │   ├── idle_timeout
│   │   └── idle_speed
│   ├── 2.8.4 Exhaust Fan                   → [fan_generic exhaust]
│   │   └── Or [heater_fan] / [temperature_fan]
│   ├── 2.8.5 Chamber Fan                   → [temperature_fan chamber]
│   │   ├── Or [fan_generic chamber]
│   │   ├── sensor_type (if temperature controlled)
│   │   └── target_temp
│   ├── 2.8.6 RSCS Fan (Rear Side Cooling)  → [fan_generic rscs]
│   ├── 2.8.7 Nevermore / Carbon Filter     → [fan_generic nevermore]
│   └── 2.8.8 Additional Fans               → [fan_generic name]
│
├── 2.9 Probe
│   ├── 2.9.1 Probe Type
│   │   ├── None (Z endstop only)
│   │   ├── Beacon                          → [beacon]
│   │   │   ├── serial (USB)
│   │   │   ├── x_offset, y_offset
│   │   │   ├── mesh_main_direction
│   │   │   ├── mesh_runs
│   │   │   ├── Contact mode settings
│   │   │   └── Accelerometer settings
│   │   ├── Cartographer                    → [scanner] or [cartographer]
│   │   │   ├── serial or canbus_uuid
│   │   │   ├── x_offset, y_offset
│   │   │   └── Scanner/touch mode settings
│   │   ├── BTT Eddy                        → [probe_eddy_current]
│   │   │   ├── Connection (USB / I2C)
│   │   │   └── Calibration settings
│   │   ├── BLTouch / 3DTouch               → [bltouch]
│   │   │   ├── sensor_pin
│   │   │   ├── control_pin
│   │   │   ├── x_offset, y_offset, z_offset
│   │   │   ├── pin_up_touch_mode_reports_triggered
│   │   │   └── stow_on_each_sample
│   │   ├── CR-Touch                        → [bltouch]
│   │   │   └── (same as BLTouch)
│   │   ├── Klicky Probe                    → [probe] + klicky macros
│   │   │   ├── Docking position
│   │   │   └── Attach/detach macros
│   │   ├── Euclid Probe                    → [probe] + euclid macros
│   │   │   ├── Docking position
│   │   │   └── Attach/detach macros
│   │   ├── Voron TAP                       → [probe]
│   │   │   ├── sensor_pin (from toolhead)
│   │   │   ├── activate_gcode / deactivate_gcode
│   │   │   └── z_offset
│   │   └── Inductive (PINDA/SuperPINDA)    → [probe]
│   │       ├── sensor_pin
│   │       ├── x_offset, y_offset, z_offset
│   │       └── Temperature compensation (SuperPINDA)
│   ├── 2.9.2 Probe Offsets
│   │   ├── x_offset
│   │   ├── y_offset
│   │   └── z_offset
│   └── 2.9.3 Probe Settings
│       ├── speed
│       ├── lift_speed
│       ├── samples
│       ├── sample_retract_dist
│       └── samples_tolerance
│
├── 2.10 Homing Configuration
│   ├── 2.10.1 X Homing
│   │   ├── Home direction (min / max)
│   │   └── Sensorless homing enable
│   ├── 2.10.2 Y Homing
│   │   ├── Home direction (min / max)
│   │   └── Sensorless homing enable
│   ├── 2.10.3 Z Homing Method
│   │   ├── Physical Z endstop (pin selection)
│   │   ├── Probe as Z endstop (virtual_endstop)
│   │   └── Sensorless Z (rare)
│   ├── 2.10.4 Safe Z Home                  → [safe_z_home]
│   │   ├── home_xy_position (usually bed center)
│   │   ├── z_hop (before XY move)
│   │   ├── z_hop_speed
│   │   └── move_to_previous
│   ├── 2.10.5 Homing Override              → [homing_override]
│   │   └── Custom homing sequence (for sensorless, docking probes)
│   └── 2.10.6 Sensorless Homing Config
│       ├── StallGuard threshold per axis
│       ├── Homing current (reduced)
│       └── Second homing speed
│
├── 2.11 Bed Leveling
│   ├── 2.11.1 Bed Mesh                     → [bed_mesh]
│   │   ├── mesh_min (X, Y)
│   │   ├── mesh_max (X, Y)
│   │   ├── probe_count (X, Y)
│   │   ├── algorithm (lagrange / bicubic)
│   │   ├── fade_start
│   │   ├── fade_end
│   │   ├── fade_target
│   │   └── adaptive_margin (for KAMP-style)
│   ├── 2.11.2 Auto Leveling Method
│   │   ├── None (1 Z motor)
│   │   ├── Bed Tilt (2 Z, simple)          → [bed_tilt]
│   │   │   └── points
│   │   ├── Z Tilt Adjust (2-3 Z)           → [z_tilt]
│   │   │   ├── z_positions
│   │   │   ├── points
│   │   │   ├── speed
│   │   │   ├── retries
│   │   │   └── retry_tolerance
│   │   └── Quad Gantry Level (4 Z)         → [quad_gantry_level]
│   │       ├── gantry_corners
│   │       ├── points
│   │       ├── speed
│   │       ├── retries
│   │       └── retry_tolerance
│   └── 2.11.3 Manual Bed Screws
│       ├── Bed Screws                      → [bed_screws]
│       │   └── screw positions
│       └── Screws Tilt Adjust              → [screws_tilt_adjust]
│           ├── screw positions
│           └── screw_thread (CW-M3, CCW-M4, etc.)
│
├── 2.12 Temperature Sensors
│   ├── 2.12.1 MCU Temperature              → [temperature_sensor mcu_temp]
│   │   └── sensor_type: temperature_mcu
│   ├── 2.12.2 Host Temperature             → [temperature_sensor host_temp]
│   │   └── sensor_type: temperature_host
│   ├── 2.12.3 Chamber Sensor               → [temperature_sensor chamber]
│   │   ├── sensor_type (NTC 100K, etc.)
│   │   ├── sensor_pin
│   │   └── pullup_resistor
│   ├── 2.12.4 Toolboard Temperature        → [temperature_sensor toolboard]
│   │   └── sensor_type: temperature_mcu, sensor_mcu: toolboard
│   └── 2.12.5 Additional Sensors           → [temperature_sensor name]
│
├── 2.13 LEDs & Lighting
│   ├── 2.13.1 NeoPixel (WS2812, SK6812)    → [neopixel name]
│   │   ├── pin
│   │   ├── chain_count
│   │   ├── color_order (GRB, GRBW, RGB)
│   │   └── initial_color
│   ├── 2.13.2 DotStar (APA102)             → [dotstar name]
│   │   ├── data_pin, clock_pin
│   │   └── chain_count
│   ├── 2.13.3 Generic PWM LED              → [led name]
│   │   ├── red_pin, green_pin, blue_pin, white_pin
│   │   └── cycle_time
│   ├── 2.13.4 Case Light                   → [output_pin caselight]
│   │   ├── pin
│   │   ├── pwm (true/false)
│   │   └── value
│   └── 2.13.5 LED Effects (plugin)         → [led_effect]
│       └── Requires led_effects Klipper plugin
│
├── 2.14 Filament Sensors
│   ├── 2.14.1 None
│   ├── 2.14.2 Switch Sensor                → [filament_switch_sensor name]
│   │   ├── switch_pin
│   │   ├── pause_on_runout
│   │   ├── runout_gcode
│   │   └── insert_gcode
│   └── 2.14.3 Motion Sensor (BTT SFS)      → [filament_motion_sensor name]
│       ├── switch_pin
│       ├── detection_length
│       ├── extruder
│       ├── pause_on_runout
│       └── runout_gcode
│
├── 2.15 Display
│   ├── 2.15.1 None
│   ├── 2.15.2 LCD Display                  → [display]
│   │   ├── lcd_type (st7920, uc1701, ssd1306, etc.)
│   │   ├── Pin configuration
│   │   └── Menu customization
│   └── 2.15.3 KlipperScreen
│       └── (Configured via Moonraker, no printer.cfg section)
│
└── 2.16 Advanced Hardware
    ├── 2.16.1 Servo                        → [servo name]
    │   ├── pin
    │   ├── initial_angle
    │   └── maximum_servo_angle
    ├── 2.16.2 Output Pins                  → [output_pin name]
    │   ├── pin
    │   ├── pwm
    │   └── value / shutdown_value
    ├── 2.16.3 GCode Buttons                → [gcode_button name]
    │   ├── pin
    │   └── press_gcode / release_gcode
    └── 2.16.4 Chamber Heater               → [heater_generic chamber_heater]
        ├── heater_pin
        ├── sensor_type, sensor_pin
        └── control, pid values

3. TUNING & OPTIMIZATION
├── 3.1 Macros
│   ├── 3.1.1 START_PRINT Macro
│   │   ├── Building blocks selection
│   │   │   ├── Homing (conditional)
│   │   │   ├── Bed heating (wait/no-wait)
│   │   │   ├── Heat soak timer
│   │   │   ├── Chamber wait
│   │   │   ├── Bed leveling (QGL/Z_TILT)
│   │   │   ├── Z calibration (probe-specific)
│   │   │   ├── Bed mesh (adaptive/full/saved)
│   │   │   ├── Extruder heating
│   │   │   ├── Nozzle cleaning
│   │   │   ├── Purge
│   │   │   └── LED status updates
│   │   └── Block order customization
│   ├── 3.1.2 END_PRINT Macro
│   │   ├── Retract
│   │   ├── Park position
│   │   ├── Cooldown settings
│   │   └── Motor disable delay
│   └── 3.1.3 Purge Style
│       ├── Line purge
│       ├── Blob purge
│       ├── Adaptive purge (KAMP-style)
│       └── None
│
├── 3.2 Input Shaper                        → [input_shaper]
│   ├── 3.2.1 Accelerometer Setup           → [adxl345] / [lis2dw]
│   │   ├── Connection (SPI / I2C)
│   │   └── Chip location (toolhead / bed)
│   ├── 3.2.2 Resonance Tester              → [resonance_tester]
│   │   ├── accel_chip
│   │   └── probe_points
│   └── 3.2.3 Shaper Values
│       ├── shaper_type_x (mzv, ei, 2hump_ei, 3hump_ei)
│       ├── shaper_freq_x
│       ├── shaper_type_y
│       └── shaper_freq_y
│
├── 3.3 TMC Autotune                        → [autotune_tmc stepper_*]
│   ├── 3.3.1 Motor Selection
│   │   └── Which motors to autotune
│   ├── 3.3.2 Motor Database
│   │   └── Motor model selection
│   └── 3.3.3 Tuning Profile
│       ├── Silent
│       ├── Performance
│       └── Custom
│
├── 3.4 Pressure Advance
│   ├── 3.4.1 PA Value                      → updates [extruder]
│   ├── 3.4.2 Smooth Time
│   └── 3.4.3 PA Test Macro
│
├── 3.5 Firmware Retraction                 → [firmware_retraction]
│   ├── retract_length
│   ├── retract_speed
│   ├── unretract_extra_length
│   └── unretract_speed
│
├── 3.6 Extruder Calibration
│   ├── 3.6.1 rotation_distance Calculator
│   │   ├── Mark filament
│   │   ├── Extrude test amount
│   │   └── Measure and calculate
│   └── 3.6.2 Flow Rate Test
│
└── 3.7 Skew Correction                     → [skew_correction]
    └── XY, XZ, YZ skew values
```

---

## Mermaid Flowcharts

### Main Menu Overview

```mermaid
flowchart TD
    M0["gschpoozi Main Menu"]
    
    M1["1. Klipper Setup"]
    M2["2. Hardware Setup"]
    M3["3. Tuning"]
    
    M0 --> M1
    M0 --> M2
    M0 --> M3
    
    M1 --> M1_1["1.1 Klipper"]
    M1 --> M1_2["1.2 Moonraker"]
    M1 --> M1_3["1.3 Web Interface"]
    M1 --> M1_4["1.4 Optional Services"]
    
    M1_3 --> M1_3_1["1.3.1 Mainsail"]
    M1_3 --> M1_3_2["1.3.2 Fluidd"]
    
    M1_4 --> M1_4_1["1.4.1 Crowsnest"]
    M1_4 --> M1_4_2["1.4.2 KlipperScreen"]
    M1_4 --> M1_4_3["1.4.3 Timelapse"]
```

### Hardware Setup - MCU and Printer

```mermaid
flowchart TD
    subgraph mcu [2.1 MCU Configuration]
        M2_1["2.1 MCU Boards"]
        M2_1_1["2.1.1 Main Board"]
        M2_1_2["2.1.2 Toolhead Board"]
        M2_1_3["2.1.3 Host MCU"]
        M2_1_4["2.1.4 Additional MCUs"]
    end
    
    subgraph printer [2.2 Printer Settings]
        M2_2["2.2 Printer"]
        M2_2_1["2.2.1 Kinematics"]
        M2_2_2["2.2.2 max_velocity"]
        M2_2_3["2.2.3 max_accel"]
        M2_2_4["2.2.4 max_z_velocity"]
        M2_2_5["2.2.5 max_z_accel"]
        M2_2_6["2.2.6 square_corner_velocity"]
    end
    
    M2_1 --> M2_1_1
    M2_1 --> M2_1_2
    M2_1 --> M2_1_3
    M2_1 --> M2_1_4
    
    M2_2 --> M2_2_1
    M2_2 --> M2_2_2
    M2_2 --> M2_2_3
    M2_2 --> M2_2_4
    M2_2 --> M2_2_5
    M2_2 --> M2_2_6
```

### Hardware Setup - Motion System

```mermaid
flowchart TD
    subgraph xaxis [2.3 X Axis]
        M2_3["2.3 X Axis"]
        M2_3_1["2.3.1 Stepper X"]
        M2_3_2["2.3.2 TMC Driver X"]
        M2_3_3["2.3.3 Stepper X1 AWD"]
        M2_3_4["2.3.4 TMC Driver X1"]
    end
    
    subgraph yaxis [2.4 Y Axis]
        M2_4["2.4 Y Axis"]
        M2_4_1["2.4.1 Stepper Y"]
        M2_4_2["2.4.2 TMC Driver Y"]
        M2_4_3["2.4.3 Stepper Y1 AWD"]
        M2_4_4["2.4.4 TMC Driver Y1"]
    end
    
    subgraph zaxis [2.5 Z Axis]
        M2_5["2.5 Z Axis"]
        M2_5_1["2.5.1 Z Motor Count"]
        M2_5_2["2.5.2 Stepper Z"]
        M2_5_3["2.5.3 TMC Driver Z"]
        M2_5_4["2.5.4 Stepper Z1"]
        M2_5_5["2.5.5 TMC Z1"]
        M2_5_6["2.5.6 Stepper Z2"]
        M2_5_7["2.5.7 TMC Z2"]
        M2_5_8["2.5.8 Stepper Z3"]
        M2_5_9["2.5.9 TMC Z3"]
    end
    
    M2_3 --> M2_3_1
    M2_3 --> M2_3_2
    M2_3 --> M2_3_3
    M2_3 --> M2_3_4
    
    M2_4 --> M2_4_1
    M2_4 --> M2_4_2
    M2_4 --> M2_4_3
    M2_4 --> M2_4_4
    
    M2_5 --> M2_5_1
    M2_5 --> M2_5_2
    M2_5 --> M2_5_3
    M2_5 --> M2_5_4
    M2_5 --> M2_5_5
    M2_5 --> M2_5_6
    M2_5 --> M2_5_7
    M2_5 --> M2_5_8
    M2_5 --> M2_5_9
```

### Hardware Setup - Stepper Detail

```mermaid
flowchart TD
    subgraph stepper [Stepper Configuration Template]
        S["Stepper Section"]
        S1["Motor port selection"]
        S2["rotation_distance"]
        S2a["Belt pitch or leadscrew"]
        S2b["Pulley teeth"]
        S3["microsteps"]
        S4["full_steps_per_rotation"]
        S5["Endstop config"]
        S5a["Physical pin"]
        S5b["Sensorless"]
        S5c["On toolboard"]
        S6["position_endstop"]
        S7["position_min"]
        S8["position_max"]
        S9["homing_speed"]
        S10["homing_retract_dist"]
    end
    
    subgraph tmc [TMC Driver Template]
        T["TMC Driver Section"]
        T1["Driver type"]
        T1a["TMC2209"]
        T1b["TMC5160"]
        T1c["TMC2130"]
        T2["run_current"]
        T3["interpolate"]
        T4["sense_resistor"]
        T5["UART config"]
        T6["SPI config"]
        T7["Advanced tuning"]
    end
    
    S --> S1
    S --> S2
    S2 --> S2a
    S2 --> S2b
    S --> S3
    S --> S4
    S --> S5
    S5 --> S5a
    S5 --> S5b
    S5 --> S5c
    S --> S6
    S --> S7
    S --> S8
    S --> S9
    S --> S10
    
    T --> T1
    T1 --> T1a
    T1 --> T1b
    T1 --> T1c
    T --> T2
    T --> T3
    T --> T4
    T --> T5
    T --> T6
    T --> T7
```

### Hardware Setup - Extruder

```mermaid
flowchart TD
    subgraph extruder [2.6 Extruder]
        M2_6["2.6 Extruder"]
        M2_6_1["2.6.1 Extruder Count"]
        M2_6_2["2.6.2 Extruder 0"]
        M2_6_3["2.6.3 TMC Driver E"]
    end
    
    subgraph e0_config [Extruder 0 Config]
        E0["2.6.2 Extruder 0"]
        E0_1["2.6.2.1 Motor Location"]
        E0_1a["Mainboard"]
        E0_1b["Toolboard"]
        E0_2["2.6.2.2 Extruder Type"]
        E0_2a["Sherpa Mini"]
        E0_2b["Orbiter v2/v2.5/SO3"]
        E0_2c["Clockwork 2"]
        E0_2d["Galileo 2"]
        E0_2e["LGX Lite"]
        E0_2f["BMG"]
        E0_2g["Custom"]
        E0_3["2.6.2.3 Stepper Settings"]
        E0_4["2.6.2.4 Hotend Config"]
        E0_4a["nozzle_diameter"]
        E0_4b["filament_diameter"]
        E0_4c["heater_pin"]
        E0_4d["sensor_type"]
        E0_4e["sensor_pin"]
        E0_4f["min/max_temp"]
        E0_5["2.6.2.5 Extrusion Settings"]
        E0_6["2.6.2.6 Pressure Advance"]
        E0_7["2.6.2.7 PID Values"]
    end
    
    M2_6 --> M2_6_1
    M2_6 --> M2_6_2
    M2_6 --> M2_6_3
    
    E0 --> E0_1
    E0_1 --> E0_1a
    E0_1 --> E0_1b
    E0 --> E0_2
    E0_2 --> E0_2a
    E0_2 --> E0_2b
    E0_2 --> E0_2c
    E0_2 --> E0_2d
    E0_2 --> E0_2e
    E0_2 --> E0_2f
    E0_2 --> E0_2g
    E0 --> E0_3
    E0 --> E0_4
    E0_4 --> E0_4a
    E0_4 --> E0_4b
    E0_4 --> E0_4c
    E0_4 --> E0_4d
    E0_4 --> E0_4e
    E0_4 --> E0_4f
    E0 --> E0_5
    E0 --> E0_6
    E0 --> E0_7
```

### Hardware Setup - Thermal

```mermaid
flowchart TD
    subgraph bed [2.7 Heated Bed]
        M2_7["2.7 Heated Bed"]
        M2_7_1["2.7.1 heater_pin"]
        M2_7_2["2.7.2 sensor_type"]
        M2_7_3["2.7.3 sensor_pin"]
        M2_7_4["2.7.4 pullup_resistor"]
        M2_7_5["2.7.5 min_temp"]
        M2_7_6["2.7.6 max_temp"]
        M2_7_7["2.7.7 PID Values"]
    end
    
    subgraph fans [2.8 Fans]
        M2_8["2.8 Fans"]
        M2_8_1["2.8.1 Part Cooling"]
        M2_8_2["2.8.2 Hotend Fan"]
        M2_8_3["2.8.3 Controller Fan"]
        M2_8_4["2.8.4 Exhaust Fan"]
        M2_8_5["2.8.5 Chamber Fan"]
        M2_8_6["2.8.6 RSCS Fan"]
        M2_8_7["2.8.7 Nevermore"]
        M2_8_8["2.8.8 Additional Fans"]
    end
    
    M2_7 --> M2_7_1
    M2_7 --> M2_7_2
    M2_7 --> M2_7_3
    M2_7 --> M2_7_4
    M2_7 --> M2_7_5
    M2_7 --> M2_7_6
    M2_7 --> M2_7_7
    
    M2_8 --> M2_8_1
    M2_8 --> M2_8_2
    M2_8 --> M2_8_3
    M2_8 --> M2_8_4
    M2_8 --> M2_8_5
    M2_8 --> M2_8_6
    M2_8 --> M2_8_7
    M2_8 --> M2_8_8
```

### Hardware Setup - Probe

```mermaid
flowchart TD
    subgraph probe [2.9 Probe]
        M2_9["2.9 Probe"]
        M2_9_1["2.9.1 Probe Type"]
        M2_9_1a["None - Z Endstop"]
        M2_9_1b["Beacon"]
        M2_9_1c["Cartographer"]
        M2_9_1d["BTT Eddy"]
        M2_9_1e["BLTouch"]
        M2_9_1f["CR-Touch"]
        M2_9_1g["Klicky"]
        M2_9_1h["Euclid"]
        M2_9_1i["Voron TAP"]
        M2_9_1j["Inductive PINDA"]
        M2_9_2["2.9.2 Probe Offsets"]
        M2_9_3["2.9.3 Probe Settings"]
    end
    
    M2_9 --> M2_9_1
    M2_9_1 --> M2_9_1a
    M2_9_1 --> M2_9_1b
    M2_9_1 --> M2_9_1c
    M2_9_1 --> M2_9_1d
    M2_9_1 --> M2_9_1e
    M2_9_1 --> M2_9_1f
    M2_9_1 --> M2_9_1g
    M2_9_1 --> M2_9_1h
    M2_9_1 --> M2_9_1i
    M2_9_1 --> M2_9_1j
    M2_9 --> M2_9_2
    M2_9 --> M2_9_3
```

### Hardware Setup - Homing and Leveling

```mermaid
flowchart TD
    subgraph homing [2.10 Homing Configuration]
        M2_10["2.10 Homing"]
        M2_10_1["2.10.1 X Homing"]
        M2_10_2["2.10.2 Y Homing"]
        M2_10_3["2.10.3 Z Homing Method"]
        M2_10_3a["Physical endstop"]
        M2_10_3b["Probe virtual endstop"]
        M2_10_3c["Sensorless"]
        M2_10_4["2.10.4 Safe Z Home"]
        M2_10_5["2.10.5 Homing Override"]
        M2_10_6["2.10.6 Sensorless Config"]
    end
    
    subgraph leveling [2.11 Bed Leveling]
        M2_11["2.11 Bed Leveling"]
        M2_11_1["2.11.1 Bed Mesh"]
        M2_11_2["2.11.2 Auto Leveling"]
        M2_11_2a["None - 1 Z"]
        M2_11_2b["Bed Tilt - 2 Z"]
        M2_11_2c["Z Tilt - 2-3 Z"]
        M2_11_2d["QGL - 4 Z"]
        M2_11_3["2.11.3 Manual Screws"]
    end
    
    M2_10 --> M2_10_1
    M2_10 --> M2_10_2
    M2_10 --> M2_10_3
    M2_10_3 --> M2_10_3a
    M2_10_3 --> M2_10_3b
    M2_10_3 --> M2_10_3c
    M2_10 --> M2_10_4
    M2_10 --> M2_10_5
    M2_10 --> M2_10_6
    
    M2_11 --> M2_11_1
    M2_11 --> M2_11_2
    M2_11_2 --> M2_11_2a
    M2_11_2 --> M2_11_2b
    M2_11_2 --> M2_11_2c
    M2_11_2 --> M2_11_2d
    M2_11 --> M2_11_3
```

### Hardware Setup - Extras

```mermaid
flowchart TD
    subgraph sensors [2.12 Temperature Sensors]
        M2_12["2.12 Temp Sensors"]
        M2_12_1["2.12.1 MCU Temp"]
        M2_12_2["2.12.2 Host Temp"]
        M2_12_3["2.12.3 Chamber Sensor"]
        M2_12_4["2.12.4 Toolboard Temp"]
        M2_12_5["2.12.5 Additional"]
    end
    
    subgraph leds [2.13 LEDs]
        M2_13["2.13 LEDs"]
        M2_13_1["2.13.1 NeoPixel"]
        M2_13_2["2.13.2 DotStar"]
        M2_13_3["2.13.3 PWM LED"]
        M2_13_4["2.13.4 Case Light"]
        M2_13_5["2.13.5 LED Effects"]
    end
    
    subgraph filament [2.14 Filament Sensors]
        M2_14["2.14 Filament Sensors"]
        M2_14_1["2.14.1 None"]
        M2_14_2["2.14.2 Switch Sensor"]
        M2_14_3["2.14.3 Motion Sensor"]
    end
    
    subgraph display [2.15 Display]
        M2_15["2.15 Display"]
        M2_15_1["2.15.1 None"]
        M2_15_2["2.15.2 LCD"]
        M2_15_3["2.15.3 KlipperScreen"]
    end
    
    subgraph advanced [2.16 Advanced]
        M2_16["2.16 Advanced"]
        M2_16_1["2.16.1 Servo"]
        M2_16_2["2.16.2 Output Pins"]
        M2_16_3["2.16.3 GCode Buttons"]
        M2_16_4["2.16.4 Chamber Heater"]
    end
    
    M2_12 --> M2_12_1
    M2_12 --> M2_12_2
    M2_12 --> M2_12_3
    M2_12 --> M2_12_4
    M2_12 --> M2_12_5
    
    M2_13 --> M2_13_1
    M2_13 --> M2_13_2
    M2_13 --> M2_13_3
    M2_13 --> M2_13_4
    M2_13 --> M2_13_5
    
    M2_14 --> M2_14_1
    M2_14 --> M2_14_2
    M2_14 --> M2_14_3
    
    M2_15 --> M2_15_1
    M2_15 --> M2_15_2
    M2_15 --> M2_15_3
    
    M2_16 --> M2_16_1
    M2_16 --> M2_16_2
    M2_16 --> M2_16_3
    M2_16 --> M2_16_4
```

### Tuning Section

```mermaid
flowchart TD
    subgraph macros [3.1 Macros]
        M3_1["3.1 Macros"]
        M3_1_1["3.1.1 START_PRINT"]
        M3_1_2["3.1.2 END_PRINT"]
        M3_1_3["3.1.3 Purge Style"]
    end
    
    subgraph shaper [3.2 Input Shaper]
        M3_2["3.2 Input Shaper"]
        M3_2_1["3.2.1 Accelerometer"]
        M3_2_2["3.2.2 Resonance Tester"]
        M3_2_3["3.2.3 Shaper Values"]
    end
    
    subgraph autotune [3.3 TMC Autotune]
        M3_3["3.3 TMC Autotune"]
        M3_3_1["3.3.1 Motor Selection"]
        M3_3_2["3.3.2 Motor Database"]
        M3_3_3["3.3.3 Tuning Profile"]
    end
    
    subgraph calibration [3.4-3.7 Calibration]
        M3_4["3.4 Pressure Advance"]
        M3_5["3.5 Firmware Retraction"]
        M3_6["3.6 Extruder Calibration"]
        M3_7["3.7 Skew Correction"]
    end
    
    M3_1 --> M3_1_1
    M3_1 --> M3_1_2
    M3_1 --> M3_1_3
    
    M3_2 --> M3_2_1
    M3_2 --> M3_2_2
    M3_2 --> M3_2_3
    
    M3_3 --> M3_3_1
    M3_3 --> M3_3_2
    M3_3 --> M3_3_3
```

---

## Config Section Mapping

| Menu ID | Klipper Section | Required |
|---------|-----------------|----------|
| 2.1.1 | `[mcu]` | Yes |
| 2.1.2 | `[mcu toolboard]` | No |
| 2.1.3 | `[mcu rpi]` | No |
| 2.2 | `[printer]` | Yes |
| 2.3.1 | `[stepper_x]` | Yes |
| 2.3.2 | `[tmc2209/5160 stepper_x]` | Yes |
| 2.3.3 | `[stepper_x1]` | AWD only |
| 2.4.1 | `[stepper_y]` | Yes |
| 2.4.2 | `[tmc2209/5160 stepper_y]` | Yes |
| 2.4.3 | `[stepper_y1]` | AWD only |
| 2.5.2 | `[stepper_z]` | Yes |
| 2.5.4-9 | `[stepper_z1/z2/z3]` | Multi-Z |
| 2.6.2 | `[extruder]` | Yes |
| 2.6.3 | `[tmc2209 extruder]` | Yes |
| 2.7 | `[heater_bed]` | Yes |
| 2.8.1 | `[fan]` | Yes |
| 2.8.2 | `[heater_fan hotend_fan]` | Recommended |
| 2.8.3 | `[controller_fan]` | No |
| 2.9 | `[probe]`/`[beacon]`/`[bltouch]` | Recommended |
| 2.10.4 | `[safe_z_home]` | If using probe |
| 2.11.1 | `[bed_mesh]` | If using probe |
| 2.11.2 | `[quad_gantry_level]`/`[z_tilt]` | Multi-Z |
| 3.2 | `[input_shaper]` | No |
| 3.3 | `[autotune_tmc]` | No |

---

## Feedback Welcome

This structure is open for review. Please provide feedback on:
- Missing config sections
- Incorrect menu hierarchy
- Parameter groupings that don't make sense
- Workflow improvements

Submit feedback via GitHub issues or discussions.

