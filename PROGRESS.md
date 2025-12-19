# gschpoozi Development Progress

> Last updated: 2025-12-19

## Project Status: Beta (Almost Fully Functional) 🎉

The wizard is now almost fully functional and ready for real-world testing!

**Found a bug?** [File an issue](https://github.com/gm-tc-collaborators/gschpoozi/issues/new/choose) using our templates.

---

## 🐛 Recent Bug Fixes

### 2025-12-19: Template Whitespace Fixes
- **Issue**: Generated config had concatenated lines (e.g., `heater_pin: PE5sensor_pin: PC1`)
- **Root Cause**: Jinja's `trim_blocks=True` eating newlines after `{% endif %}`
- **Fix**: Restructured templates to use proper whitespace control (`{%- ... -%}`)
- **Affected**: `[heater_bed]`, `[autotune_tmc]` sections

### 2025-12-19: Radiolist Pre-selection Fix
- **Issue**: `sensor_type` could be empty if no option was pre-selected
- **Root Cause**: Radiolist didn't always pre-select first item
- **Fix**: Radiolist now always ensures at least one item is selected

### 2025-12-19: Bed Heater Pin Picker
- **Issue**: Only showed dedicated bed heater ports, not SSR/MOSFET options
- **Fix**: Full pin picker with all output pins, pin conflict detection, "None" pullup option

### 2025-12-19: TMC Autotune Motor Selection UX
- **Issue**: Had to scroll through motor list for every stepper
- **Fix**: "Use same as stepper_x?" shortcut for subsequent axes

### 2025-12-06: Beacon Virtual Endstop Fix
- **Issue**: `stepper_z` was missing `homing_retract_dist: 0` in configure.sh template
- **Root Cause**: Beacon requires `homing_retract_dist: 0` for proper virtual endstop operation
- **Fix**: Added `homing_retract_dist: 0  # Required for probe-based Z homing` to stepper_z template

---

## ✅ Completed Features

### Core Framework
- [x] Interactive configuration wizard (`scripts/configure.sh`)
- [x] Hardware setup Python script (`scripts/setup-hardware.py`)
- [x] Config generator (`scripts/generate-config.py`)
- [x] Klippain board importer (`scripts/import-klippain-boards.py`)
- [x] Moonraker update manager integration

### Wizard Features
- [x] KIAUH-style text menu interface
- [x] Board selection with port count validation
- [x] Toolboard selection
- [x] Kinematics selection (CoreXY, CoreXY AWD, Cartesian, CoreXZ)
- [x] Z stepper count (1-4) with auto leveling method
- [x] Per-axis stepper driver selection
- [x] Extruder conditional on toolboard (smart port calculation)
- [x] State persistence between sessions
- [x] Extras menu (filament sensor, chamber sensor, KlipperScreen, LCD, LEDs, caselight)
- [x] MCU serial ID auto-detection (USB and CAN)
- [x] CAN bus setup wizard with interface configuration

### CAN Bus Support
- [x] CAN interface setup (`/etc/network/interfaces.d/can0`)
- [x] CAN requirements checker
- [x] CAN adapter selection (U2C, UTOC, Waveshare, USB-CAN Bridge)
- [x] Bitrate configuration (500K, 1M)
- [x] CAN diagnostics and troubleshooting
- [x] Katapult (CanBoot) installation and update manager
- [x] CAN UUID detection via `canbus_query.py`

### Leveling Methods (Auto-configured)
- [x] 1 Z motor: No leveling
- [x] 2 Z motors: Bed Tilt
- [x] 3 Z motors: Z Tilt Adjust
- [x] 4 Z motors: Quad Gantry Level (QGL)

---

## 📦 Templates

### Main Boards (27 total)
| Board | Motors | Source |
|-------|--------|--------|
| BTT Octopus v1.0/v1.1 | 8 | Klippain |
| BTT Octopus Pro v1.1 | 8 | Klippain |
| BTT Octopus Max | 10 | Klippain |
| BTT Kraken v1.0 | 8 | Klippain |
| BTT Manta M8P v1.0/v1.1/v2.0 | 8 | Klippain |
| BTT Manta M5P v1.0 | 5 | Klippain |
| BTT Manta E3EZ v1.0 | 5 | Klippain |
| BTT SKR 2 | 5 | Klippain |
| BTT SKR 3 | 5 | Klippain |
| BTT SKR v1.4 | 5 | Klippain |
| BTT SKR Pro v1.2 | 4 | Klippain |
| BTT SKR Mini E3 v2 | 4 | Klippain |
| BTT SKR Mini E3 v3 | 4 | Klippain |
| BTT SKR Pico v1.0 | 4 | Klippain |
| Fysetc Spider v1.x/v2.x/v3.x | 8 | Klippain |
| Fysetc S6 v2.x | 6 | Klippain |
| Fysetc Catalyst v1.x | 2 | Klippain |
| Fysetc Cheetah v3.x | 4 | Klippain |
| LDO Leviathan v1.2 | 6 | Klippain |
| Mellow Fly Gemini v3 | 4 | Klippain |
| Mellow Fly Super8 v1.x | 8 | Klippain |

### Toolhead Boards (17 total)
| Board | MCU | Connection | Source |
|-------|-----|------------|--------|
| BTT EBB36/42 v1.0 | STM32 | CAN | Klippain |
| BTT EBB36/42 v1.1 | STM32 | CAN | Klippain |
| BTT EBB36/42 v1.2 | STM32 | CAN | Klippain |
| BTT SB2209 v1.0 | STM32 | CAN | Klippain |
| BTT SB2209 RP2040 v1.0 | RP2040 | CAN | Klippain |
| BTT SB2240 v1.0 | STM32 | CAN | Klippain |
| Mellow SHT36/42 v1.x | STM32 | CAN | Klippain |
| Mellow SHT36 v2.x | STM32 | CAN | Klippain |
| Mellow SHT36 v3.x | STM32 | CAN | Klippain |
| Mellow SB2040 v1/v2 | RP2040 | CAN | Klippain |
| Mellow SB2040 Pro | RP2040 | CAN | Klippain |
| Fysetc SB Can TH v1.x | STM32 | CAN | Klippain |
| LDO Nitehawk-SB v1.0 | RP2040 | USB | Klippain |
| **LDO Nitehawk-36** | RP2040 | USB | Manual |
| **Orbitool SO3** | STM32F042 | USB | Manual |

### Probes (9 total)
| Probe | Type | Connection | Source |
|-------|------|------------|--------|
| Beacon | Eddy Current | USB | Manual |
| Cartographer 3D | Eddy Current | USB/CAN | Manual |
| BTT Eddy | Eddy Current | USB/I2C | Manual |
| BLTouch/3DTouch | Servo + Microswitch | 5-pin | Manual |
| CR-Touch | Servo + Optical | 5-pin | Manual |
| Klicky Probe | Dockable Microswitch | 2-pin | Manual |
| Euclid Probe | Dockable Microswitch | 2-pin | Manual |
| Voron TAP | Nozzle Contact | 3-pin | Manual |
| Inductive (PINDA) | Inductive Sensor | 3-pin | Manual |

### Extruder Profiles (9 total)
| Extruder | Gear Ratio | Rotation Distance |
|----------|------------|-------------------|
| Sherpa Mini | 50:10 | 22.67895 |
| Orbiter v2.0 | 7.5:1 | 4.637 |
| Orbiter v2.5 | 7.5:1 | 4.637 |
| Smart Orbiter v3 | 7.5:1 | 4.69 |
| Clockwork 2 | 50:10 | 22.6789511 |
| Galileo 2 | 9:1 | 47.088 |
| LGX Lite | 44:8 | 8 |
| BMG | 50:17 | 22.6789511 |
| WW-BMG | 50:17 | 22.6789511 |

### CAN Adapters (4 total)
| Adapter | Manufacturer | Connection |
|---------|--------------|------------|
| BTT U2C v2.1 | BigTreeTech | USB |
| Mellow Fly UTOC-1 | Mellow | USB |
| Mellow Fly UTOC-3 | Mellow | USB |
| Waveshare USB-CAN-A | Waveshare | USB |

### Hardware Components (5 templates)
| Template | Contents | Approach |
|----------|----------|----------|
| `fans.json` | 4 fan types, 6 functions | Type + function assignment |
| `lights.json` | 5 LED types (NeoPixel, DotStar, FCOB, etc.) | Type + location |
| `filament-sensors.json` | 2 types (switch, motion), 5 sensors | Detection capability |
| `temperature-sensors.json` | Thermistors, RTDs, Thermocouples | Sensor type + amplifier |
| `displays.json` | KlipperScreen + LCD/OLED displays | Screen type + Moonraker entry |

---

## 🔧 Supported Kinematics

| Kinematics | Axes | Status |
|------------|------|--------|
| CoreXY | X, Y | ✅ |
| CoreXY AWD | X, X1, Y, Y1 | ✅ |
| Cartesian | X, Y | ✅ |
| CoreXZ | X, Z | ✅ |

---

## 🧪 Beta Tester Coverage

### Neptunus (CoreXY AWD, 300x300 bed, 4x Z)
| Component | Template | Status |
|-----------|----------|--------|
| BTT Octopus v1.0 | `btt-octopus.json` | ✅ |
| LDO Nitehawk-36 | `ldo-nitehawk-36.json` | ✅ |
| Beacon Rev H | `beacon.json` | ✅ |
| Sherpa Mini | `extruders.json` | ✅ |
| CoreXY AWD kinematics | `corexy-awd` | ✅ |

### VzBot 330 AWD (CoreXY AWD, 330x316 bed, 1x Z)
| Component | Template | Status |
|-----------|----------|--------|
| Mellow Fly Super8 Pro | `mellow-fly-super8-v1-x.json` | ✅ |
| Orbitool SO3 | `orbitool-so3.json` | ✅ |
| Beacon Rev H (Contact) | `beacon.json` | ✅ |
| VZ Hextrudort | extruders (pending) | 🔄 |
| CoreXY AWD kinematics | `corexy-awd` | ✅ |
| TMC5160 (X/X1/Y/Y1) | SPI drivers | ✅ |
| TMC2209 (Z) | UART driver | ✅ |

---

## 📝 TODO / Roadmap

### ✅ Completed (High Priority)
- [x] Full wizard flow (MCU, kinematics, steppers, extruder, bed, fans, probe, homing, leveling)
- [x] Config generation with actual pin mappings
- [x] Klipper component management (KIAUH-style install/update/remove)
- [x] KlipperScreen integration (install, configure, remove)
- [x] Macro templates (START_PRINT, END_PRINT, building blocks)
- [x] TMC Autotune integration with motor database picker
- [x] CAN bus setup automation
- [x] More probe templates (Klicky, TAP, BLTouch, Beacon, Cartographer, BTT Eddy)

### 🔄 In Progress
- [ ] Additional MCUs section (MMU/filament changers, Happy Hare, AFC integration)
- [ ] Input shaper configuration
- [ ] More testing across different hardware combinations

### 📋 Planned
- [ ] Bed mesh configuration UI
- [ ] Config validation scripts
- [ ] Automated testing

### 💭 Future Ideas
- [ ] Web-based wizard
- [ ] Motor discovery integration

---

## 📂 File Structure

```
gschpoozi/
├── scripts/
│   ├── configure.sh           # Main wizard
│   ├── setup-hardware.py      # Port assignment
│   ├── generate-config.py     # Config generator
│   └── import-klippain-boards.py
├── templates/
│   ├── boards/                # 27 main boards
│   ├── toolboards/            # 17 toolhead boards
│   ├── probes/                # Probe templates (9)
│   ├── extruders/             # Extruder profiles (9)
│   ├── can-adapters/          # CAN adapters (4)
│   ├── hardware/              # Generic hardware (fans, lights, sensors)
│   └── macros/                # Macro building blocks
│       ├── building-blocks.json
│       ├── purge-styles.json
│       ├── start-print.cfg.template
│       └── end-print.cfg.template
├── docs/
│   ├── USAGE.md               # User manual
│   └── PROBE_CONFIGURATION.md
├── README.md
├── PROGRESS.md                # This file
└── LICENSE                    # GPL-3.0
```

---

## 🔗 Sources & Attribution

- Board templates extracted from [Klippain](https://github.com/Frix-x/klippain) (GPL-3.0)
- Orbitool SO3 from [Orbiter-Toolboards](https://github.com/RobertLorincz/Orbiter-Toolboards)
- LDO Nitehawk-36 from [MotorDynamicsLab](https://github.com/MotorDynamicsLab/Nitehawk-36)
- Beacon probe from [beacon3d.com](https://beacon3d.com/)
- Cartographer 3D from [docs.cartographer3d.com](https://docs.cartographer3d.com/)
- BTT Eddy from [bigtreetech/Eddy](https://github.com/bigtreetech/Eddy)
- CAN Bus Guide from [canbus.esoterical.online](https://canbus.esoterical.online/)
