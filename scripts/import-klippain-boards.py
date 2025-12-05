#!/usr/bin/env python3
"""
Import Klippain board definitions and convert to gschpoozi JSON format.

Usage:
    ./import-klippain-boards.py /path/to/klippain/config/mcu_definitions

This script extracts pin aliases from Klippain's [board_pins] sections
and converts them to our port-based JSON format.
"""

import re
import json
import sys
from pathlib import Path

def parse_klippain_board(cfg_path: Path) -> dict:
    """Parse a Klippain board .cfg file and extract pin aliases."""
    
    content = cfg_path.read_text()
    
    # Extract board name from filename
    name = cfg_path.stem.replace('_', ' ')
    
    # Find aliases section
    aliases = {}
    in_aliases = False
    
    for line in content.split('\n'):
        line = line.strip()
        
        if line.startswith('aliases:'):
            in_aliases = True
            continue
        
        if in_aliases and line:
            # Parse alias lines like: MCU_MOTOR0_STEP=PF13 , MCU_MOTOR0_DIR=PF12
            pairs = re.findall(r'(\w+)=([^,\s]+)', line)
            for key, value in pairs:
                if not value.startswith('<'):  # Skip placeholders like <GND>
                    aliases[key] = value
    
    return {
        'name': name,
        'filename': cfg_path.name,
        'aliases': aliases
    }

def convert_to_gschpoozi_format(board_data: dict, is_toolboard: bool = False) -> dict:
    """Convert Klippain aliases to gschpoozi JSON format."""
    
    aliases = board_data['aliases']
    name = board_data['name']
    
    # Create board ID from name
    board_id = name.lower().replace(' ', '-').replace('.', '-').replace('_', '-')
    board_id = re.sub(r'-+', '-', board_id)
    
    result = {
        'id': board_id,
        'name': name,
        'manufacturer': extract_manufacturer(name),
        'source': 'Extracted from Klippain (GPL-3.0)',
        'motor_ports': {},
        'heater_ports': {},
        'fan_ports': {},
        'thermistor_ports': {},
        'endstop_ports': {},
    }
    
    if is_toolboard:
        result['mcu_name'] = 'toolhead'
    
    # Extract motor ports - handle multiple naming conventions
    motor_patterns = [
        (re.compile(r'MCU_MOTOR(\d+(?:_\d+)?)_(\w+)'), None),  # MOTOR0, MOTOR2_1 (Octopus)
        (re.compile(r'MCU_M(\d+)_(\w+)'), None),               # M1, M2, M8 (Manta)
        (re.compile(r'MCU_S(\d+)_(\w+)'), None),               # S1, S2 (Kraken)
        (re.compile(r'MCU_STEPPER(\d+)_(\w+)'), None),         # STEPPER0, STEPPER1 (Leviathan)
        (re.compile(r'MCU_HV-STEPPER(\d+)_(\w+)'), 'HV'),      # HV-STEPPER0, HV-STEPPER1 (Leviathan HV)
        (re.compile(r'MCU_DRIVE(\d+)_(\w+)'), None),           # DRIVE0, DRIVE1 (Mellow)
        (re.compile(r'MCU_(X)M_(\w+)'), 'X'),                  # XM (X axis) (SKR)
        (re.compile(r'MCU_(Y)M_(\w+)'), 'Y'),                  # YM
        (re.compile(r'MCU_(Z)M_(\w+)'), 'Z'),                  # ZM
        (re.compile(r'MCU_(E\d*)M_(\w+)'), None),              # E0M, E1M (extruders)
        (re.compile(r'MCU_(X)_MOT_(\w+)'), 'X'),               # X_MOT (Fysetc)
        (re.compile(r'MCU_(Y)_MOT_(\w+)'), 'Y'),               # Y_MOT
        (re.compile(r'MCU_(Z)_MOT_(\w+)'), 'Z'),               # Z_MOT
        (re.compile(r'MCU_(E\d*)_MOT_(\w+)'), None),           # E0_MOT, E1_MOT
        (re.compile(r'MCU_(X)_(\w+)'), 'X'),                   # X_STEP (SKR Pico)
        (re.compile(r'MCU_(Y)_(\w+)'), 'Y'),                   # Y_STEP
        (re.compile(r'MCU_(Z)_(\w+)'), 'Z'),                   # Z_STEP
        (re.compile(r'MCU_(E\d+)_(\w+)'), None),               # E0_STEP, E1_STEP
    ]
    motors = {}
    
    for key, pin in aliases.items():
        for pattern, fixed_name in motor_patterns:
            match = pattern.match(key)
            if match:
                if fixed_name == 'HV':
                    motor_id = f'HV{match.group(1)}'  # HV0, HV1
                elif fixed_name:
                    motor_id = fixed_name
                else:
                    motor_id = match.group(1).replace('_', '_')
                pin_type = match.group(2).lower()
                
                port_name = f'MOTOR_{motor_id}'
                if port_name not in motors:
                    label = f'Driver {motor_id}'
                    if motor_id == 'X':
                        label = 'X Stepper'
                    elif motor_id == 'Y':
                        label = 'Y Stepper'
                    elif motor_id == 'Z':
                        label = 'Z Stepper'
                    elif motor_id.startswith('E'):
                        label = f'Extruder {motor_id}'
                    motors[port_name] = {'label': label}
                
                if pin_type == 'step':
                    motors[port_name]['step_pin'] = pin
                elif pin_type == 'dir':
                    motors[port_name]['dir_pin'] = pin
                elif pin_type in ('enable', 'en'):
                    motors[port_name]['enable_pin'] = pin
                elif pin_type == 'uart':
                    motors[port_name]['uart_pin'] = pin
                    motors[port_name]['cs_pin'] = pin  # Often shared
                elif pin_type in ('cs', 'cs_pdn'):
                    motors[port_name]['cs_pin'] = pin
                    motors[port_name]['uart_pin'] = pin  # Often shared
                break
    
    # Handle toolboard single driver
    if is_toolboard and 'MCU_TMCDRIVER_STEP' in aliases:
        motors['EXTRUDER'] = {
            'label': 'Extruder Driver',
            'step_pin': aliases.get('MCU_TMCDRIVER_STEP'),
            'dir_pin': aliases.get('MCU_TMCDRIVER_DIR'),
            'enable_pin': aliases.get('MCU_TMCDRIVER_ENABLE'),
            'uart_pin': aliases.get('MCU_TMCDRIVER_UART'),
        }
    
    result['motor_ports'] = motors
    
    # Extract heater ports
    heaters = {}
    for key, pin in aliases.items():
        if key.startswith('MCU_HE'):
            num = key.replace('MCU_HE', '')
            heaters[f'HE{num}'] = {
                'label': f'Heater {num}',
                'pin': pin,
            }
        elif key in ('MCU_BED0', 'MCU_BED_OUT'):
            heaters['HB'] = {
                'label': 'Heated Bed',
                'pin': pin,
            }
        elif key == 'MCU_HOTEND0':
            heaters['HE'] = {
                'label': 'Hotend Heater',
                'pin': pin,
            }
    
    result['heater_ports'] = heaters
    
    # Extract fan ports
    fans = {}
    for key, pin in aliases.items():
        if key.startswith('MCU_FAN'):
            num = key.replace('MCU_FAN', '')
            fans[f'FAN{num}'] = {
                'label': f'Fan {num}',
                'pin': pin,
                'pwm': True,
            }
    
    result['fan_ports'] = fans
    
    # Extract thermistor ports
    therms = {}
    for key, pin in aliases.items():
        if key in ('MCU_TB', 'MCU_THB'):
            therms['TB'] = {
                'label': 'Bed Thermistor',
                'pin': pin,
            }
        elif key.startswith('MCU_T') and len(key) == 5 and key[4:].isdigit():
            num = key.replace('MCU_T', '')
            therms[f'T{num}'] = {
                'label': f'Thermistor {num}',
                'pin': pin,
            }
        elif key.startswith('MCU_TH') and key != 'MCU_THB':
            num = key.replace('MCU_TH', '')
            therms[f'TH{num}'] = {
                'label': f'Thermistor {num}',
                'pin': pin,
            }
    
    result['thermistor_ports'] = therms
    
    # Extract endstop ports - many naming conventions
    endstops = {}
    for key, pin in aliases.items():
        # MCU_STOP0, MCU_STOP1 (Octopus style)
        if key.startswith('MCU_STOP') and key[8:].isdigit():
            num = key.replace('MCU_STOP', '')
            endstops[f'STOP_{num}'] = {'label': f'Endstop {num}', 'pin': pin}
        
        # MCU_M1_STOP, MCU_M2_STOP (Manta style)
        elif '_STOP' in key and key.startswith('MCU_M') and key[5:6].isdigit():
            num = key.split('_')[1].replace('M', '')
            endstops[f'M{num}_STOP'] = {'label': f'Motor {num} Endstop', 'pin': pin}
        
        # MCU_DRIVE0_STOP (Kraken style)
        elif key.startswith('MCU_DRIVE') and '_STOP' in key:
            num = key.replace('MCU_DRIVE', '').replace('_STOP', '')
            endstops[f'DRIVE{num}_STOP'] = {'label': f'Drive {num} Endstop', 'pin': pin}
        
        # MCU_X_MIN, MCU_Y_MIN, MCU_Z_MIN (Spider style)
        elif key in ('MCU_X_MIN', 'MCU_Y_MIN', 'MCU_Z_MIN'):
            axis = key.split('_')[1]
            endstops[f'{axis}_MIN'] = {'label': f'{axis} Min Endstop', 'pin': pin}
        elif key in ('MCU_X_MAX', 'MCU_Y_MAX', 'MCU_Z_MAX'):
            axis = key.split('_')[1]
            endstops[f'{axis}_MAX'] = {'label': f'{axis} Max Endstop', 'pin': pin}
        
        # MCU_XSTOP, MCU_YSTOP, MCU_ZSTOP (SKR style)
        elif key in ('MCU_XSTOP', 'MCU_YSTOP', 'MCU_ZSTOP'):
            axis = key.replace('MCU_', '').replace('STOP', '')
            endstops[f'{axis}_STOP'] = {'label': f'{axis} Endstop', 'pin': pin}
        
        # MCU_E0STOP, MCU_E1STOP (Extruder endstops)
        elif key.startswith('MCU_E') and 'STOP' in key and not key.startswith('MCU_EXP'):
            num = key.replace('MCU_E', '').replace('STOP', '')
            endstops[f'E{num}_STOP'] = {'label': f'Extruder {num} Endstop', 'pin': pin}
        
        # MCU_STOP_X, MCU_STOP_Y (Leviathan style)
        elif key.startswith('MCU_STOP_'):
            axis = key.replace('MCU_STOP_', '')
            endstops[f'{axis}_STOP'] = {'label': f'{axis} Endstop', 'pin': pin}
        
        # MCU_Z_PROBE
        elif key == 'MCU_Z_PROBE':
            endstops['Z_PROBE'] = {'label': 'Z Probe', 'pin': pin}
        
        # MCU_MIN1, MCU_MIN2 (Numbered style)
        elif key.startswith('MCU_MIN') and key[7:].isdigit():
            num = key.replace('MCU_MIN', '')
            endstops[f'MIN_{num}'] = {'label': f'Endstop {num}', 'pin': pin}
        
        # MCU_PROBE, MCU_PROBE1, MCU_PROBE2
        elif key == 'MCU_PROBE':
            endstops['PROBE'] = {'label': 'Probe Input', 'pin': pin}
        elif key.startswith('MCU_PROBE') and key[9:].isdigit():
            num = key.replace('MCU_PROBE', '')
            endstops[f'PROBE_{num}'] = {'label': f'Probe {num}', 'pin': pin}
        
        # MCU_IND_PROBE (Inductive probe)
        elif key == 'MCU_IND_PROBE':
            endstops['IND_PROBE'] = {'label': 'Inductive Probe', 'pin': pin}
    
    result['endstop_ports'] = endstops
    
    # Extract filament detection ports
    filament = {}
    for key, pin in aliases.items():
        # MCU_E0DET, MCU_E1DET
        if key.startswith('MCU_E') and 'DET' in key and 'POWER' not in key:
            num = key.replace('MCU_E', '').replace('DET', '')
            filament[f'FIL_DET_{num}'] = {'label': f'Filament Detect {num}', 'pin': pin}
        # MCU_FIL_DET1, MCU_FIL_DET2
        elif key.startswith('MCU_FIL_DET'):
            num = key.replace('MCU_FIL_DET', '')
            filament[f'FIL_DET_{num}'] = {'label': f'Filament Detect {num}', 'pin': pin}
    
    if filament:
        result['filament_ports'] = filament
    
    # Extract misc ports
    misc = {}
    for key, pin in aliases.items():
        if key == 'MCU_NEOPIXEL' or key == 'MCU_RGB':
            misc['NEOPIXEL'] = {
                'label': 'NeoPixel/RGB LED',
                'pin': pin,
            }
        elif key == 'MCU_SERVOS':
            misc['SERVO'] = {
                'label': 'Servo',
                'pin': pin,
            }
        elif key == 'MCU_PS_ON':
            misc['PS_ON'] = {
                'label': 'Power Supply Control',
                'pin': pin,
            }
    
    if misc:
        result['misc_ports'] = misc
    
    return result

def extract_manufacturer(name: str) -> str:
    """Extract manufacturer from board name."""
    name_lower = name.lower()
    
    if 'btt' in name_lower or 'bigtreetech' in name_lower:
        return 'BigTreeTech'
    elif 'fysetc' in name_lower:
        return 'Fysetc'
    elif 'mellow' in name_lower:
        return 'Mellow'
    elif 'ldo' in name_lower:
        return 'LDO'
    elif 'creality' in name_lower:
        return 'Creality'
    elif 'mks' in name_lower:
        return 'MKS'
    else:
        return 'Other'

def main():
    if len(sys.argv) < 2:
        print("Usage: ./import-klippain-boards.py /path/to/klippain/config/mcu_definitions")
        print("       ./import-klippain-boards.py /tmp/klippain-temp/config/mcu_definitions")
        sys.exit(1)
    
    klippain_path = Path(sys.argv[1])
    
    if not klippain_path.exists():
        print(f"Error: Path not found: {klippain_path}")
        sys.exit(1)
    
    # Output directories
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    boards_out = repo_root / 'templates' / 'boards'
    toolboards_out = repo_root / 'templates' / 'toolboards'
    
    boards_out.mkdir(parents=True, exist_ok=True)
    toolboards_out.mkdir(parents=True, exist_ok=True)
    
    # Process main boards
    main_boards = klippain_path / 'main'
    if main_boards.exists():
        print("\n=== Main Boards ===")
        for cfg_file in sorted(main_boards.glob('*.cfg')):
            board_data = parse_klippain_board(cfg_file)
            result = convert_to_gschpoozi_format(board_data, is_toolboard=False)
            
            # Save JSON
            out_file = boards_out / f"{result['id']}.json"
            with open(out_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            motor_count = len(result['motor_ports'])
            print(f"  ✓ {result['name']} ({motor_count} motors) -> {out_file.name}")
    
    # Process toolhead boards
    toolhead_boards = klippain_path / 'toolhead'
    if toolhead_boards.exists():
        print("\n=== Toolhead Boards ===")
        for cfg_file in sorted(toolhead_boards.glob('*.cfg')):
            board_data = parse_klippain_board(cfg_file)
            result = convert_to_gschpoozi_format(board_data, is_toolboard=True)
            
            # Save JSON
            out_file = toolboards_out / f"{result['id']}.json"
            with open(out_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            print(f"  ✓ {result['name']} -> {out_file.name}")
    
    print("\nDone! Board templates saved to templates/boards/ and templates/toolboards/")

if __name__ == '__main__':
    main()

