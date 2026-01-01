# Reference Configs Index

Quick navigation guide for the gschpoozi Klipper reference configuration library.

## 📁 Directory Contents

### 📄 Configuration Files (8 total)

**High-End Kit Printers:**
1. `voron-2.4-octopus-raw.cfg` - Voron 2.4, Quad Gantry Leveling, 593 lines
2. `voron-trident-skr13-raw.cfg` - Voron Trident, Z-Tilt, Dual MCU, 611 lines
3. `voron-0.2-skr-mini-e3-v3-raw.cfg` - Voron 0.2, Sensorless homing, 417 lines
4. `ratrig-vcore3-300-base.cfg` - RatRig V-Core 3, Modular base, 163 lines
5. `ratrig-vcore3-compiled.cfg` - RatRig with includes merged, 139 lines

**Mainstream/Generic:**
6. `creality-ender3-v2.cfg` - Ender 3 V2, Cartesian, Simple, 95 lines
7. `generic-btt-skr-3.cfg` - SKR 3 board pin reference, 185 lines
8. `sample-idex.cfg` - Dual independent X carriage example, 132 lines

### 📚 Documentation Files

- **README.md** - Comprehensive overview, features, patterns, safety notes
- **QUICK_COMPARISON.md** - Side-by-side comparison of config patterns and techniques
- **ANALYSIS.txt** - Section usage analysis across all configs
- **INDEX.md** - This file

### 🛠️ Tools

- **analyze-configs.sh** - Script to analyze config file sections and patterns

## 🔍 What to Look At For...

### **Z-Leveling Methods**
- Quad Gantry (4Z): `voron-2.4-octopus-raw.cfg`
- Z-Tilt (3Z): `voron-trident-skr13-raw.cfg`, `ratrig-vcore3-300-base.cfg`
- Bed Mesh: `voron-0.2-skr-mini-e3-v3-raw.cfg`
- Manual: `creality-ender3-v2.cfg`

### **Homing Strategies**
- Sensorless (TMC stallguard): `voron-0.2-skr-mini-e3-v3-raw.cfg`
- Standard endstops: All Voron 2.4/Trident, Ender 3 V2
- Safe Z home with probe: Voron 2.4, Voron Trident

### **Multi-MCU Setup**
- `voron-trident-skr13-raw.cfg` - Main board + XYE toolhead board

### **TMC Driver Configuration**
- All Voron configs (extensive TMC2209 usage)
- `ratrig-vcore3-300-base.cfg` (TMC2209 setup)

### **Kinematics**
- CoreXY: All Voron configs, RatRig V-Core 3
- Cartesian: `creality-ender3-v2.cfg`, `sample-idex.cfg`

### **Advanced Features**
- IDEX (dual independent extruders): `sample-idex.cfg`
- Geared extruder (50:10): `voron-0.2-skr-mini-e3-v3-raw.cfg`
- Modular includes: `ratrig-vcore3-300-base.cfg`

### **Macro Patterns**
- PRINT_START/END: Voron Trident, Voron 0.2
- G32 (home + level): Voron 2.4
- Filament management: Voron 0.2
- Tool changes (T0/T1): `sample-idex.cfg`

### **Simple Reference Config**
- `creality-ender3-v2.cfg` - Most straightforward, minimal features

### **Board Pin Mappings**
- `generic-btt-skr-3.cfg` - Complete SKR 3 pinout reference

## 📊 Statistics

- **Total configs:** 8
- **Total lines:** 2,335
- **Kinematics represented:** CoreXY (5), Cartesian (2), Generic (1)
- **Manufacturers:** VoronDesign (3), RatRig (2), Creality (1), Klipper (2)
- **Most common section:** `[stepper_x]` (in all 8 configs)

## 🎯 Recommended Reading Order

1. **Start here:** `README.md` - Get overview and safety warnings
2. **Simple example:** `creality-ender3-v2.cfg` - See basic structure
3. **CoreXY example:** `voron-0.2-skr-mini-e3-v3-raw.cfg` - Compact CoreXY
4. **Advanced CoreXY:** `voron-2.4-octopus-raw.cfg` - Full-featured
5. **Comparison guide:** `QUICK_COMPARISON.md` - Understand patterns
6. **Analysis:** `ANALYSIS.txt` - Section usage statistics

## 💡 How gschpoozi Uses These

These configs inform gschpoozi's design in several ways:

1. **Template validation** - Ensure gschpoozi generates configs matching industry standards
2. **Parameter defaults** - Real-world values for rotation_distance, currents, temps, etc.
3. **Safety limits** - Conservative max_temp, position limits from proven configs
4. **Macro patterns** - PRINT_START/END structure, variable storage methods
5. **Z-leveling logic** - When to use QGL vs z_tilt vs bed_mesh based on Z motor count
6. **TMC driver setup** - Standard configurations for interpolate, stealthchop, etc.

## 🔗 External Resources

- [Klipper Config Reference](https://www.klipper3d.org/Config_Reference.html)
- [VoronDesign/Voron-2](https://github.com/VoronDesign/Voron-2/tree/Voron2.4/firmware/klipper_configurations)
- [VoronDesign/Voron-Trident](https://github.com/VoronDesign/Voron-Trident)
- [VoronDesign/Voron-0](https://github.com/VoronDesign/Voron-0/tree/Voron0.2/Firmware)
- [Rat-Rig/v-core-3-klipper-config](https://github.com/Rat-Rig/v-core-3-klipper-config) (deprecated)
- [Rat-OS/ratos-configuration](https://github.com/Rat-OS/ratos-configuration) (current)
- [Klipper Official Example Configs](https://github.com/Klipper3d/klipper/tree/master/config)

---

**Last Updated:** 2026-01-01
**Maintained for:** gschpoozi Klipper configuration generator
**Purpose:** Reference material only - DO NOT deploy directly to printers
