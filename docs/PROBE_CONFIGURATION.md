# Probe Configuration Reference

This document provides official documentation links and configuration references for all supported probes in gschpoozi.

## Eddy Current Probes

Eddy current probes use electromagnetic induction to detect the print bed without physical contact. They support two operation modes:

- **Proximity/Scan Mode**: Contactless sensing for rapid bed mesh scanning
- **Touch/Contact Mode**: Physical contact for precise Z homing

### BTT Eddy

BigTreeTech's Eddy probe using the LDC1612 sensor.

**Official Documentation:**
- https://www.klipper3d.org/Eddy_Probe.html
- https://github.com/bigtreetech/Eddy

**Key Configuration:**
```ini
[mcu eddy]
serial: /dev/serial/by-id/usb-Klipper_rp2040_XXXXXXXX-if00

[probe_eddy_current btt_eddy]
sensor_type: ldc1612
i2c_mcu: eddy
i2c_bus: i2c0f
x_offset: 0
y_offset: 0
z_offset: 1.0
speed: 40
lift_speed: 5
```

**Calibration Commands:**
```
PROBE_EDDY_CURRENT_CALIBRATE CHIP=btt_eddy
TEMPERATURE_PROBE_CALIBRATE PROBE=btt_eddy TARGET=70
```

**Important Notes:**
- Probe should be 2-3mm above bed when nozzle touches (2.5mm optimal)
- Use `BED_MESH_CALIBRATE METHOD=rapid_scan ADAPTIVE=1` for fastest mesh
- `stepper_z` must use `endstop_pin: btt_eddy:z_virtual_endstop`

---

### Beacon

Beacon is a high-precision eddy current probe with contact mode support on Rev H and later.

**Official Documentation:**
- https://docs.beacon3d.com/
- https://github.com/beacon3d/beacon_klipper

**Key Configuration:**
```ini
[beacon]
serial: /dev/serial/by-id/usb-Beacon_...
x_offset: 0
y_offset: 20
mesh_main_direction: x
mesh_runs: 2

# Contact mode (Rev H+ only)
home_method: contact
home_xy_position: 150, 150
home_z_hop: 5
home_z_hop_speed: 30
contact_max_hotend_temperature: 180
```

**Calibration Commands:**
```
BEACON_CALIBRATE              # Proximity calibration
BEACON_CALIBRATE_CONTACT      # Contact mode calibration (Rev H+)
```

**Important Notes:**
- `stepper_z` must use `endstop_pin: probe:z_virtual_endstop`
- Contact mode requires Beacon Rev H or later hardware
- `contact_max_hotend_temperature` prevents contact while nozzle is too hot

---

### Cartographer

Cartographer is an eddy current probe with touch mode support.

**Official Documentation:**
- https://docs.cartographer3d.com/

**Key Configuration:**
```ini
[cartographer]
serial: /dev/serial/by-id/usb-cartographer_...
# Or for CAN: canbus_uuid: YOUR_UUID
x_offset: 0
y_offset: 20
mesh_main_direction: x
mesh_runs: 2
```

**Calibration Commands:**
```
CARTOGRAPHER_CALIBRATE        # Initial calibration
```

**Important Notes:**
- `stepper_z` must use `endstop_pin: cartographer:z_virtual_endstop`
- For touch mode setup, refer to official documentation

---

## Pin-Based Probes

These probes use physical mechanisms to detect the bed surface.

### BLTouch / CR-Touch

Servo-actuated pin probe.

**Key Configuration:**
```ini
[bltouch]
sensor_pin: ^PA7           # Probe signal pin (with pullup)
control_pin: PA8           # Servo control pin
x_offset: 0
y_offset: 20
z_offset: 0                # Run PROBE_CALIBRATE
```

**Calibration Commands:**
```
PROBE_CALIBRATE
```

---

### Klicky / Euclid

Magnetic dock probes that attach/detach from the toolhead.

**Key Configuration:**
```ini
[probe]
pin: ^PA7                  # Probe signal pin (with pullup)
x_offset: 0
y_offset: 20
z_offset: 0
speed: 5
samples: 3
sample_retract_dist: 2
samples_result: median
```

**Important Notes:**
- Requires additional dock/attach macros
- See Klicky-Probe or Euclid documentation for dock configuration

---

### Inductive Probes

Inductive proximity sensors (PINDA, SuperPINDA, generic LJ12A3).

**Key Configuration:**
```ini
[probe]
pin: ^PA7                  # May need ! for NPN sensors
x_offset: 0
y_offset: 20
z_offset: 0
speed: 5
samples: 3
```

**Important Notes:**
- NPN sensors (most common) may need inverted pin: `pin: !^PA7`
- PNP sensors typically use: `pin: ^PA7`
- Sensing distance varies - mount 1-3mm above bed

---

## Common Requirements

### safe_z_home

**Required for ALL probes** (except physical Z endstop):

```ini
[safe_z_home]
home_xy_position: 150, 150    # Center of your bed
z_hop: 10                      # Lift before moving to home position
z_hop_speed: 25
speed: 150
```

This ensures the toolhead moves to a safe XY position (center of bed) before attempting Z homing, preventing crashes with bed clips or edges.

### bed_mesh

**Recommended for ALL probes**:

```ini
[bed_mesh]
speed: 150
horizontal_move_z: 5
mesh_min: 30, 30
mesh_max: 270, 270
probe_count: 5, 5
algorithm: bicubic
```

For eddy probes, use rapid scan:
```
BED_MESH_CALIBRATE METHOD=rapid_scan ADAPTIVE=1
```

---

## Troubleshooting

### "Probe triggered prior to movement"
- Ensure the probe is not already triggered before homing
- Check probe wiring and signal polarity
- For eddy probes, verify the probe is at correct height

### "Move out of range" during homing
- Check `position_min` in `[stepper_z]` (should be -5 or lower)
- Verify probe offsets don't exceed bed boundaries

### Inconsistent Z offset
- For eddy probes: run temperature calibration
- Ensure bed is at operating temperature when calibrating
- Check probe mount for looseness

