#!/usr/bin/env python3
"""
gschpoozi Hardware Setup Script
Interactive port assignment for Klipper configurations

Usage:
    ./setup-hardware.py                    # Full setup
    ./setup-hardware.py --board            # Board setup only
    ./setup-hardware.py --toolboard        # Toolboard setup only
    ./setup-hardware.py --list-boards      # List available boards

https://github.com/gueee/gschpoozi
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_ROOT = SCRIPT_DIR.parent
TEMPLATES_DIR = REPO_ROOT / "templates"
BOARDS_DIR = TEMPLATES_DIR / "boards"
TOOLBOARDS_DIR = TEMPLATES_DIR / "toolboards"

# State file location
STATE_FILE = REPO_ROOT / ".hardware-state.json"
WIZARD_STATE_FILE = REPO_ROOT / ".wizard-state"

# ═══════════════════════════════════════════════════════════════════════════════
# COLORS (ANSI escape codes)
# ═══════════════════════════════════════════════════════════════════════════════

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[0;33m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    CYAN = '\033[0;36m'
    WHITE = '\033[0;37m'
    
    BRED = '\033[1;31m'
    BGREEN = '\033[1;32m'
    BYELLOW = '\033[1;33m'
    BBLUE = '\033[1;34m'
    BMAGENTA = '\033[1;35m'
    BCYAN = '\033[1;36m'
    BWHITE = '\033[1;37m'
    
    NC = '\033[0m'  # No Color

# Box drawing
BOX_TL = "╔"
BOX_TR = "╗"
BOX_BL = "╚"
BOX_BR = "╝"
BOX_H = "═"
BOX_V = "║"
BOX_LT = "╠"
BOX_RT = "╣"

# ═══════════════════════════════════════════════════════════════════════════════
# DISPLAY HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')

def print_header(title: str, width: int = 60):
    """Print a boxed header."""
    padding = (width - len(title) - 2) // 2
    
    print(f"{Colors.BCYAN}")
    print(f"{BOX_TL}{BOX_H * width}{BOX_TR}")
    print(f"{BOX_V}{' ' * padding} {title} {' ' * (width - padding - len(title) - 2)}{BOX_V}")
    print(f"{BOX_LT}{BOX_H * width}{BOX_RT}")
    print(f"{Colors.NC}")

def print_footer(width: int = 60):
    """Print box footer."""
    print(f"{Colors.BCYAN}")
    print(f"{BOX_BL}{BOX_H * width}{BOX_BR}")
    print(f"{Colors.NC}")

def print_separator(width: int = 60):
    """Print a separator line."""
    print(f"{Colors.BCYAN}{BOX_LT}{BOX_H * width}{BOX_RT}{Colors.NC}")

def print_menu_item(num: str, label: str, value: str = "", status: str = ""):
    """Print a menu item."""
    status_icon = ""
    if status == "done":
        status_icon = f"{Colors.GREEN}[✓]{Colors.NC}"
    elif status == "partial":
        status_icon = f"{Colors.YELLOW}[~]{Colors.NC}"
    else:
        status_icon = f"{Colors.WHITE}[ ]{Colors.NC}"
    
    if value:
        print(f"{Colors.BCYAN}{BOX_V}{Colors.NC}  {Colors.BWHITE}{num}){Colors.NC} {status_icon} {label}: {Colors.CYAN}{value}{Colors.NC}")
    else:
        print(f"{Colors.BCYAN}{BOX_V}{Colors.NC}  {Colors.BWHITE}{num}){Colors.NC} {status_icon} {label}")

def print_info(text: str):
    """Print info line inside box."""
    print(f"{Colors.BCYAN}{BOX_V}{Colors.NC}  {text}")

def print_action(key: str, label: str):
    """Print action item."""
    print(f"{Colors.BCYAN}{BOX_V}{Colors.NC}  {Colors.BGREEN}{key}){Colors.NC} {label}")

def prompt(text: str, default: str = "") -> str:
    """Prompt for input."""
    if default:
        result = input(f"{Colors.BYELLOW}{text}{Colors.NC} [{default}]: ").strip()
        return result if result else default
    else:
        return input(f"{Colors.BYELLOW}{text}{Colors.NC}: ").strip()

def confirm(text: str, default: bool = False) -> bool:
    """Ask for confirmation."""
    suffix = "[Y/n]" if default else "[y/N]"
    result = input(f"{Colors.BYELLOW}{text}{Colors.NC} {suffix}: ").strip().lower()
    
    if not result:
        return default
    return result in ('y', 'yes')

def wait_for_key():
    """Wait for any key press."""
    input(f"\n{Colors.WHITE}Press Enter to continue...{Colors.NC}")


def configure_pin_modifiers(pin_name: str, is_adc: bool = False) -> str:
    """
    Configure pin modifiers (inversion, pull-up/pull-down) for input pins.

    Klipper pin modifiers:
    - ^ = pull-up resistor (activates internal pull-up)
    - ~ = pull-down resistor (activates internal pull-down)
    - ! = inverted logic (LOW = triggered)

    Combined example: ^!PA4 = pull-up + inverted

    Args:
        pin_name: Name of the pin/function being configured (for display)
        is_adc: True for ADC pins (thermistors) - only offer pull-up, no inversion

    Returns:
        Modifier string (e.g., "^!", "^", "!", "") to prepend to pin
    """
    print_info("")
    print_info(f"{Colors.BWHITE}Pin Options for {pin_name}:{Colors.NC}")
    print_info("")

    modifiers = ""

    if not is_adc:
        # Digital input - ask about inversion
        print_info(f"{Colors.WHITE}Is the signal inverted (active LOW)?{Colors.NC}")
        print_info(f"  Most mechanical switches: NO (active HIGH when triggered)")
        print_info(f"  Some optical/hall sensors: YES (active LOW when triggered)")
        print_info("")
        invert_choice = prompt("Inverted signal? [y/N]").strip().lower()
        if invert_choice == 'y':
            modifiers += "!"

    # Ask about pull-up/pull-down
    print_info("")
    print_info(f"{Colors.WHITE}Internal resistor configuration:{Colors.NC}")
    print_info(f"  Most switches need pull-up (^) - signal floats HIGH, goes LOW when triggered")
    print_info(f"  Some sensors have built-in pull-up - select None")
    print_info("")
    print_info(f"  1) {Colors.CYAN}^{Colors.NC} Pull-UP   - Most common for mechanical switches")
    print_info(f"  2) {Colors.CYAN}~{Colors.NC} Pull-DOWN - Rarely needed")
    print_info(f"  3) None      - Sensor has built-in resistor")
    print_info("")

    resistor_choice = prompt("Select resistor [1/2/3]", "1").strip()
    if resistor_choice == "1":
        modifiers = "^" + modifiers  # Pull-up goes before inversion
    elif resistor_choice == "2":
        modifiers = "~" + modifiers  # Pull-down goes before inversion

    if modifiers:
        print_info(f"\n{Colors.GREEN}Pin modifiers: {modifiers}{Colors.NC}")
    else:
        print_info(f"\n{Colors.GREEN}No pin modifiers{Colors.NC}")

    return modifiers


def get_pin_with_modifiers(assignment_key: str) -> str:
    """
    Get the full pin string with modifiers for a given assignment.

    Args:
        assignment_key: The key in port_assignments (e.g., 'endstop_x')

    Returns:
        Full pin string with modifiers (e.g., '^!PA4') or empty string if not assigned
    """
    port_name = state.port_assignments.get(assignment_key, "")
    if not port_name or port_name == "sensorless":
        return port_name

    modifiers = state.port_assignments.get(f"{assignment_key}_modifiers", "")
    # Note: The actual pin resolution happens in generate-config.py
    # Here we just store the modifier to be applied later
    return modifiers  # Return just modifiers, pin resolution is separate


# ═══════════════════════════════════════════════════════════════════════════════
# BOARD LOADING
# ═══════════════════════════════════════════════════════════════════════════════

def load_available_boards() -> Dict[str, Dict]:
    """Load all available board definitions."""
    boards = {}
    
    if BOARDS_DIR.exists():
        for json_file in BOARDS_DIR.glob("*.json"):
            try:
                with open(json_file) as f:
                    board = json.load(f)
                    boards[board['id']] = board
            except (json.JSONDecodeError, KeyError) as e:
                print(f"{Colors.YELLOW}Warning: Could not load {json_file}: {e}{Colors.NC}")
    
    return boards

def load_available_toolboards() -> Dict[str, Dict]:
    """Load all available toolboard definitions."""
    toolboards = {}
    
    if TOOLBOARDS_DIR.exists():
        for json_file in TOOLBOARDS_DIR.glob("*.json"):
            try:
                with open(json_file) as f:
                    board = json.load(f)
                    toolboards[board['id']] = board
            except (json.JSONDecodeError, KeyError) as e:
                print(f"{Colors.YELLOW}Warning: Could not load {json_file}: {e}{Colors.NC}")
    
    return toolboards

# ═══════════════════════════════════════════════════════════════════════════════
# MCU SERIAL DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

def detect_usb_mcus() -> List[Tuple[str, str]]:
    """
    Detect USB MCUs by scanning /dev/serial/by-id/.
    Returns list of (serial_path, description) tuples.
    """
    devices = []
    serial_dir = Path("/dev/serial/by-id")
    
    if not serial_dir.exists():
        return devices
    
    for device in serial_dir.iterdir():
        name = device.name
        # Filter for Klipper-related devices
        if any(x in name.lower() for x in ['klipper', 'stm32', 'rp2040', 'bigtreetech', 'mellow', 'katapult']):
            # Extract description from device name
            desc = "USB device"
            if 'klipper' in name.lower():
                # Extract MCU type: usb-Klipper_stm32h723xx_...
                match = re.search(r'Klipper_([^_]+)', name)
                if match:
                    desc = match.group(1)
            elif 'bigtreetech' in name.lower():
                desc = "BTT device"
            elif 'mellow' in name.lower():
                desc = "Mellow device"
            elif 'katapult' in name.lower():
                desc = "Katapult bootloader"
            
            devices.append((str(device), desc))
    
    return devices

def detect_can_mcus(interface: str = "can0") -> List[str]:
    """
    Detect CAN MCUs using canbus_query.py.
    Returns list of canbus UUIDs.
    """
    uuids = []
    
    # Check if CAN interface exists
    try:
        result = subprocess.run(
            ["ip", "link", "show", interface],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return uuids
    except FileNotFoundError:
        return uuids
    
    # Find canbus_query.py
    query_script = Path.home() / "klipper" / "scripts" / "canbus_query.py"
    python_env = Path.home() / "klippy-env" / "bin" / "python"
    
    if not query_script.exists() or not python_env.exists():
        return uuids
    
    try:
        result = subprocess.run(
            [str(python_env), str(query_script), interface],
            capture_output=True, text=True, timeout=10
        )
        # Parse UUIDs from output (12-character hex strings)
        uuids = re.findall(r'[0-9a-f]{12}', result.stdout.lower())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return uuids

def load_wizard_state() -> Dict[str, str]:
    """Load wizard state from key=value file."""
    state = {}
    if WIZARD_STATE_FILE.exists():
        with open(WIZARD_STATE_FILE) as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    state[key] = value
    return state

def detect_probe_serial() -> List[Tuple[str, str]]:
    """
    Detect USB-connected probes (Beacon, Cartographer, BTT Eddy).
    Returns list of (device_path, description) tuples.
    """
    devices = []
    serial_dir = Path("/dev/serial/by-id")
    
    if not serial_dir.exists():
        return devices
    
    # Pattern matching for known probe devices
    probe_patterns = {
        'beacon': ['beacon', 'Beacon'],
        'cartographer': ['cartographer', 'Cartographer'],
        'eddy': ['Eddy', 'eddy', 'btt_eddy'],
    }
    
    for device in serial_dir.iterdir():
        if device.is_symlink():
            name = device.name
            for probe_type, patterns in probe_patterns.items():
                for pattern in patterns:
                    if pattern in name:
                        desc = f"{probe_type.title()} Probe"
                        devices.append((str(device), desc))
                        break
    
    return devices

def select_probe_serial(probe_type: str) -> Optional[str]:
    """
    Interactive menu to select probe serial ID.
    probe_type: "beacon", "cartographer", "btt-eddy"
    Returns selected serial path or None if cancelled.
    """
    clear_screen()
    
    # Map probe types to display names
    probe_names = {
        'beacon': 'Beacon',
        'cartographer': 'Cartographer',
        'btt-eddy': 'BTT Eddy',
    }
    probe_name = probe_names.get(probe_type, probe_type.title())
    
    print_header(f"Select {probe_name} Serial")
    print_info(f"Scanning for {probe_name} devices...")
    print_info("")
    
    # Detect probe devices
    devices = detect_probe_serial()
    
    # Filter for specific probe type
    type_patterns = {
        'beacon': ['beacon', 'Beacon'],
        'cartographer': ['cartographer', 'Cartographer'],
        'btt-eddy': ['eddy', 'Eddy'],
    }
    patterns = type_patterns.get(probe_type, [probe_type])
    filtered_devices = [
        d for d in devices 
        if any(p in d[0] for p in patterns)
    ]
    
    if not filtered_devices:
        print_info(f"{Colors.YELLOW}No {probe_name} devices found.{Colors.NC}")
        print_info("")
        print_info("Make sure:")
        print_info(f"  - {probe_name} is connected via USB")
        print_info("  - Device is powered on")
        print_info("  - Device has proper firmware")
        print_info("")
        print_info(f"Run: ls /dev/serial/by-id/*{probe_type}* to check manually")
        print_separator()
        print_action("M", "Enter serial path manually")
        print_action("B", "Back")
        print_footer()
        
        choice = prompt("Select option").strip().lower()
        if choice == 'm':
            return prompt(f"Enter {probe_name} serial path").strip()
        return None
    
    # Display found devices
    for i, (path, desc) in enumerate(filtered_devices, 1):
        # Truncate long paths for display
        display_path = path
        if len(path) > 55:
            display_path = "..." + path[-52:]
        print_menu_item(str(i), desc, display_path, "")
    
    print_separator()
    print_action("M", "Enter serial path manually")
    print_action("B", "Back")
    print_footer()
    
    choice = prompt("Select device").strip()
    
    if choice.lower() == 'b':
        return None
    if choice.lower() == 'm':
        return prompt(f"Enter {probe_name} serial path").strip()
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(filtered_devices):
            return filtered_devices[idx][0]
    except ValueError:
        pass
    
    return None

def select_mcu_serial(role: str = "main", connection: str = "usb") -> Optional[str]:
    """
    Interactive menu to select MCU serial ID.
    role: "main" or "toolboard"
    connection: "usb" or "can"
    Returns selected serial path or UUID, or None if cancelled.
    """
    clear_screen()
    print_header(f"Select {role.title()} MCU Serial")
    
    if connection == "can":
        print_info("Scanning CAN bus for devices...")
        print_info("")
        
        uuids = detect_can_mcus()
        
        if not uuids:
            print_info(f"{Colors.YELLOW}No CAN devices found.{Colors.NC}")
            print_info("Make sure:")
            print_info("  - CAN interface (can0) is up")
            print_info("  - Device is powered and connected")
            print_info("  - Device has Klipper/Katapult firmware")
            print_separator()
            print_action("M", "Enter UUID manually")
            print_action("B", "Back")
            print_footer()
            
            choice = prompt("Select option").strip().lower()
            if choice == 'm':
                return prompt("Enter canbus_uuid").strip()
            return None
        
        # Display found UUIDs
        for i, uuid in enumerate(uuids, 1):
            print_menu_item(str(i), f"UUID: {uuid}", "", "")
        
        print_separator()
        print_action("M", "Enter UUID manually")
        print_action("B", "Back")
        print_footer()
        
        choice = prompt("Select device").strip()
        
        if choice.lower() == 'b':
            return None
        if choice.lower() == 'm':
            return prompt("Enter canbus_uuid").strip()
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(uuids):
                return uuids[idx]
        except ValueError:
            pass
        
        return None
    
    else:  # USB
        print_info("Scanning USB for Klipper MCUs...")
        print_info("")
        
        devices = detect_usb_mcus()
        
        if not devices:
            print_info(f"{Colors.YELLOW}No Klipper USB devices found.{Colors.NC}")
            print_info("Make sure:")
            print_info("  - MCU is connected via USB")
            print_info("  - MCU has Klipper firmware flashed")
            print_separator()
            print_action("M", "Enter path manually")
            print_action("B", "Back")
            print_footer()
            
            choice = prompt("Select option").strip().lower()
            if choice == 'm':
                return prompt("Enter serial path").strip()
            return None
        
        # Display found devices
        for i, (path, desc) in enumerate(devices, 1):
            basename = Path(path).name
            print_info(f"{Colors.BWHITE}{i}){Colors.NC} {Colors.CYAN}{desc}{Colors.NC}")
            print_info(f"    {Colors.WHITE}{basename}{Colors.NC}")
        
        print_separator()
        print_action("M", "Enter path manually")
        print_action("B", "Back")
        print_footer()
        
        choice = prompt("Select device").strip()
        
        if choice.lower() == 'b':
            return None
        if choice.lower() == 'm':
            return prompt("Enter serial path").strip()
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(devices):
                return devices[idx][0]
        except ValueError:
            pass
        
        return None

def assign_mcu_serials():
    """Interactive menu to assign MCU serial IDs."""
    toolboards = load_available_toolboards()
    has_toolboard = state.toolboard_id and state.toolboard_id != "none"
    toolboard = toolboards.get(state.toolboard_id) if has_toolboard else None
    
    # Check if probe requires serial (beacon, cartographer, btt-eddy)
    wizard_state = load_wizard_state()
    probe_type = wizard_state.get('probe_type', '')
    usb_probes = {'beacon', 'cartographer', 'btt-eddy'}
    has_usb_probe = probe_type in usb_probes
    
    # Probe display names
    probe_names = {
        'beacon': 'Beacon',
        'cartographer': 'Cartographer',
        'btt-eddy': 'BTT Eddy',
    }
    
    while True:
        clear_screen()
        print_header("MCU Serial Configuration")
        
        # Show current assignments
        mcu_status = "done" if state.mcu_serial else ""
        mcu_display = state.mcu_serial or "not configured"
        if state.mcu_serial and len(state.mcu_serial) > 50:
            mcu_display = "..." + state.mcu_serial[-47:]
        print_menu_item("1", "Main MCU (USB)", mcu_display, mcu_status)
        
        if has_toolboard:
            tb_connection = toolboard.get('connection', 'USB').upper() if toolboard else 'USB'
            
            if tb_connection == 'CAN':
                tb_status = "done" if state.toolboard_canbus_uuid else ""
                tb_display = state.toolboard_canbus_uuid or "not configured"
                print_menu_item("2", f"Toolboard ({tb_connection})", tb_display, tb_status)
            else:
                tb_status = "done" if state.toolboard_serial else ""
                tb_display = state.toolboard_serial or "not configured"
                if state.toolboard_serial and len(state.toolboard_serial) > 50:
                    tb_display = "..." + state.toolboard_serial[-47:]
                print_menu_item("2", f"Toolboard ({tb_connection})", tb_display, tb_status)
        
        # Show probe serial option if USB-connected probe selected
        if has_usb_probe:
            probe_name = probe_names.get(probe_type, probe_type.title())
            probe_status = "done" if state.probe_serial else ""
            probe_display = state.probe_serial or "not configured"
            if state.probe_serial and len(state.probe_serial) > 50:
                probe_display = "..." + state.probe_serial[-47:]
            print_menu_item("3", f"{probe_name} Probe (USB)", probe_display, probe_status)
        
        print_separator()
        print_action("D", "Done")
        print_action("B", "Back")
        print_footer()
        
        choice = prompt("Select option").strip().lower()
        
        if choice == '1':
            result = select_mcu_serial("main", "usb")
            if result:
                state.mcu_serial = result
        elif choice == '2' and has_toolboard:
            tb_connection = toolboard.get('connection', 'USB').upper() if toolboard else 'USB'
            if tb_connection == 'CAN':
                result = select_mcu_serial("toolboard", "can")
                if result:
                    state.toolboard_canbus_uuid = result
            else:
                result = select_mcu_serial("toolboard", "usb")
                if result:
                    state.toolboard_serial = result
        elif choice == '3' and has_usb_probe:
            result = select_probe_serial(probe_type)
            if result:
                state.probe_serial = result
        elif choice in ('d', 'b'):
            return

# ═══════════════════════════════════════════════════════════════════════════════
# STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

class HardwareState:
    """Manages hardware configuration state."""
    
    def __init__(self):
        self.board_id: Optional[str] = None
        self.board_name: Optional[str] = None
        self.toolboard_id: Optional[str] = None
        self.toolboard_name: Optional[str] = None
        self.port_assignments: Dict[str, str] = {}  # function -> port
        self.toolboard_assignments: Dict[str, str] = {}
        # MCU serial IDs
        self.mcu_serial: Optional[str] = None
        self.toolboard_serial: Optional[str] = None
        self.toolboard_canbus_uuid: Optional[str] = None
        # Probe serial (for Beacon, Cartographer, BTT Eddy, etc.)
        self.probe_serial: Optional[str] = None
        
    def save(self, filepath: Path = STATE_FILE):
        """Save state to JSON file."""
        data = {
            'board_id': self.board_id,
            'board_name': self.board_name,
            'toolboard_id': self.toolboard_id,
            'toolboard_name': self.toolboard_name,
            'port_assignments': self.port_assignments,
            'toolboard_assignments': self.toolboard_assignments,
            'mcu_serial': self.mcu_serial,
            'toolboard_serial': self.toolboard_serial,
            'toolboard_canbus_uuid': self.toolboard_canbus_uuid,
            'probe_serial': self.probe_serial,
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load(self, filepath: Path = STATE_FILE) -> bool:
        """Load state from JSON file."""
        if not filepath.exists():
            return False
        
        try:
            with open(filepath) as f:
                data = json.load(f)
            
            self.board_id = data.get('board_id')
            self.board_name = data.get('board_name')
            self.toolboard_id = data.get('toolboard_id')
            self.toolboard_name = data.get('toolboard_name')
            self.port_assignments = data.get('port_assignments', {})
            self.toolboard_assignments = data.get('toolboard_assignments', {})
            self.mcu_serial = data.get('mcu_serial')
            self.toolboard_serial = data.get('toolboard_serial')
            self.toolboard_canbus_uuid = data.get('toolboard_canbus_uuid')
            self.probe_serial = data.get('probe_serial')
            return True
        except (json.JSONDecodeError, KeyError):
            return False

# Global state
state = HardwareState()

# ═══════════════════════════════════════════════════════════════════════════════
# BOARD SELECTION
# ═══════════════════════════════════════════════════════════════════════════════

def select_board() -> Optional[Dict]:
    """Interactive board selection menu."""
    boards = load_available_boards()
    
    if not boards:
        print(f"{Colors.RED}No board definitions found in {BOARDS_DIR}{Colors.NC}")
        print(f"Add board JSON files to templates/boards/")
        wait_for_key()
        return None
    
    while True:
        clear_screen()
        print_header("Select Controller Board")
        
        # Group boards by manufacturer
        by_manufacturer: Dict[str, List] = {}
        for board_id, board in boards.items():
            mfr = board.get('manufacturer', 'Other')
            if mfr not in by_manufacturer:
                by_manufacturer[mfr] = []
            by_manufacturer[mfr].append((board_id, board))
        
        # Display boards
        num = 1
        board_list = []
        
        for mfr, mfr_boards in sorted(by_manufacturer.items()):
            print_info(f"{Colors.BWHITE}{mfr}:{Colors.NC}")
            for board_id, board in mfr_boards:
                motor_count = len(board.get('motor_ports', {}))
                heater_count = len(board.get('heater_ports', {}))
                fan_count = len(board.get('fan_ports', {}))
                
                info = f"{motor_count} motors, {heater_count} heaters, {fan_count} fans"
                status = "done" if state.board_id == board_id else ""
                print_menu_item(str(num), board['name'], info, status)
                board_list.append((board_id, board))
                num += 1
            print_info("")
        
        print_separator()
        print_action("B", "Back")
        print_footer()
        
        choice = prompt("Select board").strip()
        
        if choice.lower() == 'b':
            return None
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(board_list):
                board_id, board = board_list[idx]
                state.board_id = board_id
                state.board_name = board['name']
                
                # Load default assignments
                defaults = board.get('default_assignments', {})
                for func, port in defaults.items():
                    if func not in state.port_assignments:
                        state.port_assignments[func] = port
                
                return board
        except ValueError:
            pass

def select_toolboard() -> Optional[Dict]:
    """Interactive toolboard selection menu."""
    toolboards = load_available_toolboards()
    
    while True:
        clear_screen()
        print_header("Select Toolhead Board (Optional)")
        
        print_info(f"{Colors.WHITE}Toolboards handle extruder, hotend, and fans{Colors.NC}")
        print_info(f"{Colors.WHITE}on a separate MCU mounted on the toolhead.{Colors.NC}")
        print_info("")
        
        num = 1
        board_list = []
        
        # "None" option first
        status = "done" if state.toolboard_id == "none" else ""
        print_menu_item(str(num), "No toolboard (extruder on main board)", "", status)
        board_list.append(("none", None))
        num += 1
        
        print_info("")
        
        if toolboards:
            for board_id, board in toolboards.items():
                status = "done" if state.toolboard_id == board_id else ""
                conn = board.get('connection', 'USB')
                print_menu_item(str(num), board['name'], f"({conn})", status)
                board_list.append((board_id, board))
                num += 1
        else:
            print_info(f"{Colors.YELLOW}No toolboard definitions found{Colors.NC}")
        
        print_separator()
        print_action("B", "Back")
        print_footer()
        
        choice = prompt("Select toolboard").strip()
        
        if choice.lower() == 'b':
            return None
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(board_list):
                board_id, board = board_list[idx]
                state.toolboard_id = board_id
                state.toolboard_name = board['name'] if board else "None"
                
                if board:
                    # Load default assignments for toolboard
                    defaults = board.get('default_assignments', {})
                    for func, port in defaults.items():
                        if func not in state.toolboard_assignments:
                            state.toolboard_assignments[func] = port
                
                return board
        except ValueError:
            pass

# ═══════════════════════════════════════════════════════════════════════════════
# PORT ASSIGNMENT
# ═══════════════════════════════════════════════════════════════════════════════

def assign_motor_ports(board: Dict, functions: List[str]):
    """Assign motor ports for given functions."""
    motor_ports = board.get('motor_ports', {})
    
    while True:
        clear_screen()
        print_header("Assign Motor Ports")
        
        print_info(f"Board: {Colors.CYAN}{board['name']}{Colors.NC}")
        print_info("")
        
        # Show current assignments
        num = 1
        for func in functions:
            current = state.port_assignments.get(func, "not assigned")
            port_info = ""
            if current in motor_ports:
                port_info = f" ({motor_ports[current].get('label', '')})"
            
            status = "done" if current != "not assigned" else ""
            print_menu_item(str(num), func.replace('_', ' ').title(), f"{current}{port_info}", status)
            num += 1
        
        print_separator()
        print_action("A", "Set ALL to sequential defaults")
        print_action("D", "Done - Save assignments")
        print_action("B", "Back without saving")
        print_footer()
        
        choice = prompt("Select function to change, or action").strip()
        
        if choice.lower() == 'b':
            return False
        elif choice.lower() == 'd':
            return True
        elif choice.lower() == 'a':
            # Auto-assign sequentially
            port_names = list(motor_ports.keys())
            for i, func in enumerate(functions):
                if i < len(port_names):
                    state.port_assignments[func] = port_names[i]
            continue
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(functions):
                func = functions[idx]
                select_port_for_function(func, motor_ports, "motor")
        except ValueError:
            pass

def select_port_for_function(function: str, ports: Dict, port_type: str):
    """Let user select a port for a function."""
    clear_screen()
    print_header(f"Select Port for: {function.replace('_', ' ').title()}")
    
    print_info(f"Available {port_type} ports:")
    print_info("")
    
    num = 1
    port_list = list(ports.keys())
    
    # Show which ports are already used
    used_ports = {v for v in state.port_assignments.values()}
    
    for port_name in port_list:
        port = ports[port_name]
        label = port.get('label', '')
        
        # Check if port is already used
        used_by = None
        for func, assigned_port in state.port_assignments.items():
            if assigned_port == port_name and func != function:
                used_by = func
                break
        
        if used_by:
            status_text = f"{Colors.YELLOW}(used by {used_by}){Colors.NC}"
        else:
            status_text = ""
        
        current = state.port_assignments.get(function, "")
        status = "done" if current == port_name else ""
        print_menu_item(str(num), f"{port_name} - {label}", status_text, status)
        num += 1
    
    print_separator()
    print_action("B", "Back")
    print_footer()
    
    choice = prompt("Select port").strip()
    
    if choice.lower() == 'b':
        return
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(port_list):
            state.port_assignments[function] = port_list[idx]
    except ValueError:
        pass

def assign_heater_ports(board: Dict):
    """Assign heater and thermistor ports."""
    heater_ports = board.get('heater_ports', {})
    therm_ports = board.get('thermistor_ports', {})
    
    clear_screen()
    print_header("Assign Heater & Thermistor Ports")
    
    # Heater for bed
    print_info(f"{Colors.BWHITE}Heated Bed:{Colors.NC}")
    num = 1
    heater_list = list(heater_ports.keys())
    for port_name in heater_list:
        port = heater_ports[port_name]
        current = "done" if state.port_assignments.get('heater_bed') == port_name else ""
        max_amp = port.get('max_current_amps', '?')
        print_menu_item(str(num), f"{port_name} - {port['label']}", f"{max_amp}A max", current)
        num += 1
    
    choice = prompt("Select heater port for bed").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(heater_list):
            state.port_assignments['heater_bed'] = heater_list[idx]
    except ValueError:
        pass
    
    # Thermistor for bed
    print_info("")
    print_info(f"{Colors.BWHITE}Bed Thermistor:{Colors.NC}")
    num = 1
    therm_list = list(therm_ports.keys())
    for port_name in therm_list:
        port = therm_ports[port_name]
        current = "done" if state.port_assignments.get('thermistor_bed') == port_name else ""
        print_menu_item(str(num), f"{port_name} - {port['label']}", "", current)
        num += 1
    
    choice = prompt("Select thermistor port for bed").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(therm_list):
            state.port_assignments['thermistor_bed'] = therm_list[idx]
    except ValueError:
        pass
    
    # Only ask for extruder heater if no toolboard
    if state.toolboard_id in (None, "none", ""):
        print_info("")
        print_info(f"{Colors.BWHITE}Hotend Heater:{Colors.NC}")
        num = 1
        for port_name in heater_list:
            port = heater_ports[port_name]
            current = "done" if state.port_assignments.get('heater_extruder') == port_name else ""
            max_amp = port.get('max_current_amps', '?')
            print_menu_item(str(num), f"{port_name} - {port['label']}", f"{max_amp}A max", current)
            num += 1
        
        choice = prompt("Select heater port for hotend").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(heater_list):
                state.port_assignments['heater_extruder'] = heater_list[idx]
        except ValueError:
            pass
        
        print_info("")
        print_info(f"{Colors.BWHITE}Hotend Thermistor:{Colors.NC}")
        num = 1
        for port_name in therm_list:
            port = therm_ports[port_name]
            current = "done" if state.port_assignments.get('thermistor_extruder') == port_name else ""
            print_menu_item(str(num), f"{port_name} - {port['label']}", "", current)
            num += 1
        
        choice = prompt("Select thermistor port for hotend").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(therm_list):
                state.port_assignments['thermistor_extruder'] = therm_list[idx]
        except ValueError:
            pass
    
    wait_for_key()

def assign_endstop_ports(board: Dict):
    """Assign endstop ports for X, Y, and optionally Z."""
    endstop_ports = board.get('endstop_ports', board.get('gpio_ports', {}))
    
    if not endstop_ports:
        print(f"{Colors.YELLOW}No endstop/GPIO ports defined for this board{Colors.NC}")
        wait_for_key()
        return
    
    endstop_list = list(endstop_ports.keys())
    wizard_state = load_wizard_state()
    probe_type = wizard_state.get('probe_type', '')
    
    # Determine required endstops
    required_endstops = ['endstop_x', 'endstop_y']
    
    # Z endstop only needed if NOT using a probe with virtual endstop
    if probe_type in ('', 'none', 'endstop'):
        required_endstops.append('endstop_z')
    
    while True:
        clear_screen()
        print_header("Assign Endstop Ports")
        
        # Show current assignments
        print_info(f"{Colors.BWHITE}Current Endstop Assignments:{Colors.NC}")
        print_info("")
        
        num = 1
        for endstop_func in required_endstops:
            current_port = state.port_assignments.get(endstop_func, "")
            modifiers = state.port_assignments.get(f"{endstop_func}_modifiers", "")
            if current_port == "sensorless":
                display = "Sensorless (DIAG pin)"
            elif current_port:
                port_info = endstop_ports.get(current_port, {})
                label = port_info.get('label', current_port)
                # Show modifiers if configured
                if modifiers:
                    display = f"{current_port} - {label} [{modifiers}pin]"
                else:
                    display = f"{current_port} - {label}"
            else:
                display = "not assigned"

            status = "done" if current_port else ""
            axis_name = endstop_func.replace('endstop_', '').upper()
            print_menu_item(str(num), f"{axis_name} Endstop", display, status)
            num += 1
        
        print_info("")
        print_info(f"{Colors.BWHITE}Available Ports:{Colors.NC}")
        for port_name in endstop_list[:6]:  # Show first 6
            port = endstop_ports[port_name]
            label = port.get('label', port_name)
            # Check if used
            used_by = [k for k, v in state.port_assignments.items() if v == port_name]
            if used_by:
                print_info(f"  {port_name}: {label} {Colors.YELLOW}({used_by[0]}){Colors.NC}")
            else:
                print_info(f"  {port_name}: {label}")
        if len(endstop_list) > 6:
            print_info(f"  ... and {len(endstop_list) - 6} more")
        
        print_separator()
        print_action("D", "Done")
        print_action("B", "Back")
        print_footer()
        
        choice = prompt("Select endstop to configure (1-3), or action").strip().lower()
        
        if choice == 'd' or choice == 'b':
            return
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(required_endstops):
                endstop_func = required_endstops[idx]
                select_endstop_port(endstop_func, endstop_ports, endstop_list)
        except ValueError:
            pass

def select_endstop_port(endstop_func: str, endstop_ports: Dict, endstop_list: List):
    """Select a specific port for an endstop function."""
    clear_screen()
    axis_name = endstop_func.replace('endstop_', '').upper()
    print_header(f"Select Port for {axis_name} Endstop")
    
    print_info(f"Available ports:")
    print_info("")
    
    num = 1
    for port_name in endstop_list:
        port = endstop_ports[port_name]
        label = port.get('label', port_name)
        
        # Check if already used by another function
        used_by = None
        for func, assigned_port in state.port_assignments.items():
            if assigned_port == port_name and func != endstop_func:
                used_by = func
                break
        
        if used_by:
            status_text = f"{Colors.YELLOW}(used by {used_by}){Colors.NC}"
        else:
            status_text = ""
        
        current = state.port_assignments.get(endstop_func, "")
        status = "done" if current == port_name else ""
        print_menu_item(str(num), f"{port_name} - {label}", status_text, status)
        num += 1
    
    # Sensorless homing option
    print_info("")
    current = state.port_assignments.get(endstop_func, "")
    sensorless_status = "done" if current == "sensorless" else ""
    print_menu_item(str(num), "Sensorless homing (DIAG pin)", "Uses TMC driver", sensorless_status)
    sensorless_idx = num
    
    # Clear option
    print_menu_item(str(num + 1), "Clear assignment", "", "")
    
    print_separator()
    print_action("B", "Back")
    print_footer()
    
    choice = prompt("Select port").strip()
    
    if choice.lower() == 'b':
        return
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(endstop_list):
            port_name = endstop_list[idx]
            state.port_assignments[endstop_func] = port_name

            # Configure pin modifiers (inversion, pull-up/pull-down)
            axis_name = endstop_func.replace('endstop_', '').upper()
            modifiers = configure_pin_modifiers(f"{axis_name} Endstop")
            if modifiers:
                state.port_assignments[f"{endstop_func}_modifiers"] = modifiers
            elif f"{endstop_func}_modifiers" in state.port_assignments:
                del state.port_assignments[f"{endstop_func}_modifiers"]

            state.save()
        elif idx == sensorless_idx - 1:
            state.port_assignments[endstop_func] = "sensorless"
            # Clear any modifiers for sensorless
            if f"{endstop_func}_modifiers" in state.port_assignments:
                del state.port_assignments[f"{endstop_func}_modifiers"]
            state.save()
        elif idx == sensorless_idx:
            # Clear assignment
            if endstop_func in state.port_assignments:
                del state.port_assignments[endstop_func]
            if f"{endstop_func}_modifiers" in state.port_assignments:
                del state.port_assignments[f"{endstop_func}_modifiers"]
            state.save()
    except ValueError:
        pass

def assign_fan_ports(board: Dict):
    """Assign fan ports with clear menu for all fan types."""
    fan_ports = board.get('fan_ports', {})
    wizard_state = load_wizard_state()
    
    while True:
        clear_screen()
        print_header("Assign Fan Ports")
        
        fan_list = list(fan_ports.keys())
        has_toolboard = state.toolboard_id and state.toolboard_id != "none"
        
        print_info(f"Board: {Colors.CYAN}{board.get('name', 'Unknown')}{Colors.NC}")
        print_info(f"Available fan ports: {Colors.CYAN}{', '.join(fan_list)}{Colors.NC}")
        print_info("")
        
        # Show current assignments
        print_info(f"{Colors.BWHITE}Current Fan Port Assignments:{Colors.NC}")
        print_info("")
        
        # Check if fans are actually assigned to toolboard (not 'none' or empty)
        tb_pc = state.toolboard_assignments.get('fan_part_cooling', '')
        tb_hf = state.toolboard_assignments.get('fan_hotend', '')
        pc_on_toolboard = has_toolboard and tb_pc not in ('', 'none')
        hf_on_toolboard = has_toolboard and tb_hf not in ('', 'none')
        
        # Part cooling - show mainboard option if not on toolboard
        if not pc_on_toolboard:
            pc_port = state.port_assignments.get('fan_part_cooling', '')
            pc_pin = fan_ports.get(pc_port, {}).get('pin', '') if pc_port else ''
            pc_status = "done" if pc_port else ""
            pc_display = f"{pc_port} (pin: {pc_pin})" if pc_port else "not assigned"
            print_menu_item("1", "Part Cooling [fan]", pc_display, pc_status)
        else:
            print_info(f"  1) Part Cooling - {Colors.YELLOW}on toolboard ({tb_pc}){Colors.NC}")
        
        # Hotend fan - show mainboard option if not on toolboard
        if not hf_on_toolboard:
            hf_port = state.port_assignments.get('fan_hotend', '')
            hf_pin = fan_ports.get(hf_port, {}).get('pin', '') if hf_port else ''
            hf_status = "done" if hf_port else ""
            hf_display = f"{hf_port} (pin: {hf_pin})" if hf_port else "not assigned"
            print_menu_item("2", "Hotend Fan [heater_fan]", hf_display, hf_status)
        else:
            print_info(f"  2) Hotend Fan - {Colors.YELLOW}on toolboard ({tb_hf}){Colors.NC}")
        
        cf_port = state.port_assignments.get('fan_controller', '')
        cf_pin = fan_ports.get(cf_port, {}).get('pin', '') if cf_port else ''
        cf_status = "done" if cf_port else ""
        cf_display = f"{cf_port} (pin: {cf_pin})" if cf_port else "not assigned"
        print_menu_item("3", "Controller Fan [controller_fan]", cf_display, cf_status)
        
        # Optional fans
        print_info("")
        print_info(f"{Colors.BWHITE}Optional Fans:{Colors.NC}")
        
        ex_port = state.port_assignments.get('fan_exhaust', '')
        ex_pin = fan_ports.get(ex_port, {}).get('pin', '') if ex_port else ''
        ex_status = "done" if ex_port else ""
        ex_display = f"{ex_port} (pin: {ex_pin})" if ex_port else "not assigned"
        print_menu_item("4", "Exhaust Fan [fan_generic]", ex_display, ex_status)
        
        ch_port = state.port_assignments.get('fan_chamber', '')
        ch_pin = fan_ports.get(ch_port, {}).get('pin', '') if ch_port else ''
        ch_status = "done" if ch_port else ""
        ch_display = f"{ch_port} (pin: {ch_pin})" if ch_port else "not assigned"
        print_menu_item("5", "Chamber Fan [fan_generic/temperature_fan]", ch_display, ch_status)
        
        rs_port = state.port_assignments.get('fan_rscs', '')
        rs_pin = fan_ports.get(rs_port, {}).get('pin', '') if rs_port else ''
        rs_status = "done" if rs_port else ""
        rs_display = f"{rs_port} (pin: {rs_pin})" if rs_port else "not assigned"
        print_menu_item("6", "RSCS/Filter Fan [fan_generic]", rs_display, rs_status)
        
        rd_port = state.port_assignments.get('fan_radiator', '')
        rd_pin = fan_ports.get(rd_port, {}).get('pin', '') if rd_port else ''
        rd_status = "done" if rd_port else ""
        rd_display = f"{rd_port} (pin: {rd_pin})" if rd_port else "not assigned"
        print_menu_item("7", "Radiator Fan [heater_fan]", rd_display, rd_status)
        
        # Multi-pin section (only for mainboard fans - no mixing with toolboard)
        print_info("")
        print_info(f"{Colors.BWHITE}Multi-Pin (2nd port for same control):{Colors.NC}")

        # Helper to show multi-pin port
        def show_multipin_port(key, label, num):
            port = state.port_assignments.get(key, '')
            pin = fan_ports.get(port, {}).get('pin', '') if port else ''
            status = "done" if port else ""
            display = f"{port} (pin: {pin})" if port else "not assigned"
            print_menu_item(num, label, display, status)

        # Part cooling pin2 only available if part cooling is on mainboard
        if not pc_on_toolboard:
            show_multipin_port('fan_part_cooling_pin2', 'Part Cooling Pin 2', 'A')
        else:
            print_info(f"  A) Part Cooling Pin 2 - {Colors.YELLOW}N/A (fan on toolboard){Colors.NC}")

        show_multipin_port('fan_controller_pin2', 'Controller Fan Pin 2', 'B')
        show_multipin_port('fan_rscs_pin2', 'RSCS/Filter Pin 2', 'C')
        show_multipin_port('fan_radiator_pin2', 'Radiator Fan Pin 2', 'D')
        show_multipin_port('fan_chamber_pin2', 'Chamber Fan Pin 2', 'E')
        show_multipin_port('fan_exhaust_pin2', 'Exhaust Fan Pin 2', 'F')
        
        print_separator()
        print_action("X", "Clear all fan assignments")
        print_action("Q", "Done / Back")
        print_footer()
        
        choice = prompt("Select fan to configure (1-7, A-F), or action").strip().lower()
        
        if choice == 'q':
            return
        elif choice == 'x':
            # Clear all fan assignments
            fan_keys = ['fan_part_cooling', 'fan_hotend', 'fan_controller', 
                       'fan_exhaust', 'fan_chamber', 'fan_rscs', 'fan_radiator',
                       'fan_part_cooling_pin2', 'fan_controller_pin2', 'fan_rscs_pin2',
                       'fan_radiator_pin2', 'fan_chamber_pin2', 'fan_exhaust_pin2']
            for key in fan_keys:
                if key in state.port_assignments:
                    del state.port_assignments[key]
            print(f"\n{Colors.GREEN}All fan assignments cleared{Colors.NC}")
            wait_for_key()
        elif choice == '1' and not pc_on_toolboard:
            select_fan_port('fan_part_cooling', 'Part Cooling Fan', fan_ports, fan_list)
        elif choice == '2' and not hf_on_toolboard:
            select_fan_port('fan_hotend', 'Hotend Fan', fan_ports, fan_list)
        elif choice == '3':
            select_fan_port('fan_controller', 'Controller Fan', fan_ports, fan_list)
        elif choice == '4':
            select_fan_port('fan_exhaust', 'Exhaust Fan', fan_ports, fan_list)
        elif choice == '5':
            select_fan_port('fan_chamber', 'Chamber Fan', fan_ports, fan_list)
        elif choice == '6':
            select_fan_port('fan_rscs', 'RSCS/Filter Fan', fan_ports, fan_list)
        elif choice == '7':
            select_fan_port('fan_radiator', 'Radiator Fan', fan_ports, fan_list)
        elif choice == 'a' and not pc_on_toolboard:
            select_fan_port('fan_part_cooling_pin2', 'Part Cooling Pin 2', fan_ports, fan_list)
        elif choice == 'b':
            select_fan_port('fan_controller_pin2', 'Controller Fan Pin 2', fan_ports, fan_list)
        elif choice == 'c':
            select_fan_port('fan_rscs_pin2', 'RSCS/Filter Pin 2', fan_ports, fan_list)
        elif choice == 'd':
            select_fan_port('fan_radiator_pin2', 'Radiator Fan Pin 2', fan_ports, fan_list)
        elif choice == 'e':
            select_fan_port('fan_chamber_pin2', 'Chamber Fan Pin 2', fan_ports, fan_list)
        elif choice == 'f':
            select_fan_port('fan_exhaust_pin2', 'Exhaust Fan Pin 2', fan_ports, fan_list)

def select_fan_port(fan_key: str, fan_name: str, fan_ports: Dict, fan_list: List):
    """Select a specific port for a fan function."""
    clear_screen()
    print_header(f"Select Port for {fan_name}")
    
    print_info(f"Available fan ports:")
    print_info("")
    
    num = 1
    
    # "None/Skip" option first
    current = state.port_assignments.get(fan_key, '')
    none_status = "done" if current == '' else ""
    print_menu_item(str(num), "None/Skip", "Do not configure this fan", none_status)
    num += 1
    
    # Show which ports are already used
    for port_name in fan_list:
        port = fan_ports[port_name]
        label = port.get('label', port_name)
        pin = port.get('pin', '?')
        
        # Check if port is already used by another function
        used_by = None
        for func, assigned_port in state.port_assignments.items():
            if assigned_port == port_name and func != fan_key:
                used_by = func.replace('fan_', '').replace('_', ' ')
                break
        
        if used_by:
            status_text = f"{Colors.YELLOW}(used by {used_by}){Colors.NC}"
        else:
            status_text = ""
        
        status = "done" if current == port_name else ""
        print_menu_item(str(num), f"{port_name}", f"{label} - pin: {pin} {status_text}", status)
        num += 1
    
    print_separator()
    print_action("B", "Back")
    print_footer()
    
    choice = prompt("Select port").strip()
    
    if choice.lower() == 'b':
        return
    
    try:
        idx = int(choice) - 1
        if idx == 0:
            # None/Skip - remove assignment
            if fan_key in state.port_assignments:
                del state.port_assignments[fan_key]
            print(f"\n{Colors.GREEN}{fan_name} cleared{Colors.NC}")
        elif 1 <= idx < len(fan_list) + 1:
            state.port_assignments[fan_key] = fan_list[idx - 1]
            pin = fan_ports[fan_list[idx - 1]].get('pin', '?')
            print(f"\n{Colors.GREEN}{fan_name} assigned to {fan_list[idx - 1]} (pin: {pin}){Colors.NC}")
        wait_for_key()
    except ValueError:
        pass

# ═══════════════════════════════════════════════════════════════════════════════
# TOOLBOARD PORT ASSIGNMENT
# ═══════════════════════════════════════════════════════════════════════════════

def assign_toolboard_ports(toolboard: Dict):
    """Main menu for toolboard port assignment."""
    while True:
        clear_screen()
        print_header("Toolboard Port Assignment")
        
        tb_name = toolboard.get('name', 'Toolboard')
        print_info(f"Toolboard: {Colors.CYAN}{tb_name}{Colors.NC}")
        print_info(f"{Colors.WHITE}Pins will be prefixed with 'toolboard:' in config{Colors.NC}")
        print_info(f"{Colors.WHITE}Use 'none' to skip ports not used on toolboard{Colors.NC}")
        print_info("")
        
        # Show current assignments
        extruder_port = state.toolboard_assignments.get('extruder', '')
        heater_port = state.toolboard_assignments.get('heater_extruder', '')
        therm_port = state.toolboard_assignments.get('thermistor_extruder', '')
        pc_fan_port = state.toolboard_assignments.get('fan_part_cooling', '')
        he_fan_port = state.toolboard_assignments.get('fan_hotend', '')
        endstop_x_port = state.toolboard_assignments.get('endstop_x', '')
        
        # Status indicators (done = assigned, partial = some assigned)
        motor_status = "done" if extruder_port else ""
        heater_status = "done" if heater_port or therm_port else ""
        fan_status = "done" if pc_fan_port or he_fan_port else ""
        endstop_status = "done" if endstop_x_port else ""
        
        # Display with "none" shown explicitly
        def display_port(port):
            if port == 'none':
                return f"{Colors.YELLOW}none (on mainboard){Colors.NC}"
            return port or "not configured"
        
        print_menu_item("1", "Extruder Motor", display_port(extruder_port), motor_status)
        
        heater_display = f"{display_port(heater_port)} / {display_port(therm_port)}" if heater_port or therm_port else "not configured"
        print_menu_item("2", "Hotend Heater & Thermistor", heater_display, heater_status)
        
        fan_display = f"PC:{display_port(pc_fan_port)} HE:{display_port(he_fan_port)}" if pc_fan_port or he_fan_port else "not configured"
        print_menu_item("3", "Fans (Part Cooling + Hotend)", fan_display, fan_status)
        
        print_menu_item("4", "X Endstop", display_port(endstop_x_port), endstop_status)
        
        print_separator()
        print_action("A", "Auto-assign from defaults")
        print_action("C", "Clear all toolboard assignments")
        print_action("D", "Done")
        print_action("B", "Back")
        print_footer()
        
        choice = prompt("Select option").strip().lower()
        
        if choice == '1':
            assign_toolboard_motor(toolboard)
        elif choice == '2':
            assign_toolboard_heater(toolboard)
        elif choice == '3':
            assign_toolboard_fans(toolboard)
        elif choice == '4':
            assign_toolboard_endstop(toolboard)
        elif choice == 'a':
            # Auto-assign from defaults
            defaults = toolboard.get('default_assignments', {})
            for func, port in defaults.items():
                state.toolboard_assignments[func] = port
            print(f"\n{Colors.GREEN}Auto-assigned from toolboard defaults{Colors.NC}")
            wait_for_key()
        elif choice == 'c':
            # Clear all assignments
            state.toolboard_assignments.clear()
            print(f"\n{Colors.GREEN}All toolboard assignments cleared{Colors.NC}")
            wait_for_key()
        elif choice in ('d', 'b'):
            return

def assign_toolboard_motor(toolboard: Dict):
    """Assign toolboard extruder motor port."""
    motor_ports = toolboard.get('motor_ports', {})
    
    clear_screen()
    print_header("Toolboard Extruder Motor")
    
    print_info(f"Available motor ports:")
    print_info("")
    
    num = 1
    port_list = list(motor_ports.keys()) if motor_ports else []
    
    # "None" option first - extruder on mainboard
    current = state.toolboard_assignments.get('extruder', '')
    none_status = "done" if current == 'none' else ""
    print_menu_item(str(num), "None", "Extruder motor on mainboard", none_status)
    num += 1
    
    for port_name in port_list:
        port = motor_ports[port_name]
        label = port.get('label', port_name)
        step_pin = port.get('step_pin', '?')
        
        status = "done" if current == port_name else ""
        print_menu_item(str(num), f"{port_name}", f"{label} (step: {step_pin})", status)
        num += 1
    
    print_separator()
    print_action("B", "Back")
    print_footer()
    
    choice = prompt("Select motor port for extruder").strip()
    
    if choice.lower() == 'b':
        return
    
    try:
        idx = int(choice) - 1
        if idx == 0:
            state.toolboard_assignments['extruder'] = 'none'
            print(f"\n{Colors.GREEN}Extruder set to mainboard (not on toolboard){Colors.NC}")
            wait_for_key()
        elif 1 <= idx < len(port_list) + 1:
            state.toolboard_assignments['extruder'] = port_list[idx - 1]
            print(f"\n{Colors.GREEN}Extruder assigned to {port_list[idx - 1]}{Colors.NC}")
            wait_for_key()
    except ValueError:
        pass

def assign_toolboard_heater(toolboard: Dict):
    """Assign toolboard heater and thermistor ports."""
    heater_ports = toolboard.get('heater_ports', {})
    therm_ports = toolboard.get('thermistor_ports', {})
    
    clear_screen()
    print_header("Toolboard Hotend Heater & Thermistor")
    
    # Heater selection
    print_info(f"{Colors.BWHITE}Hotend Heater:{Colors.NC}")
    num = 1
    heater_list = list(heater_ports.keys()) if heater_ports else []
    
    # "None" option first
    current = state.toolboard_assignments.get('heater_extruder', '')
    none_status = "done" if current == 'none' else ""
    print_menu_item(str(num), "None", "Heater on mainboard", none_status)
    num += 1
    
    for port_name in heater_list:
        port = heater_ports[port_name]
        label = port.get('label', port_name)
        pin = port.get('pin', '?')
        status = "done" if current == port_name else ""
        print_menu_item(str(num), f"{port_name}", f"{label} (pin: {pin})", status)
        num += 1
    
    choice = prompt("Select heater port for hotend").strip()
    try:
        idx = int(choice) - 1
        if idx == 0:
            state.toolboard_assignments['heater_extruder'] = 'none'
        elif 1 <= idx < len(heater_list) + 1:
            state.toolboard_assignments['heater_extruder'] = heater_list[idx - 1]
    except ValueError:
        pass
    
    print_info("")
    
    # Thermistor selection
    print_info(f"{Colors.BWHITE}Hotend Thermistor:{Colors.NC}")
    num = 1
    therm_list = list(therm_ports.keys()) if therm_ports else []
    
    # "None" option first
    current = state.toolboard_assignments.get('thermistor_extruder', '')
    none_status = "done" if current == 'none' else ""
    print_menu_item(str(num), "None", "Thermistor on mainboard", none_status)
    num += 1
    
    for port_name in therm_list:
        port = therm_ports[port_name]
        label = port.get('label', port_name)
        pin = port.get('pin', '?')
        status = "done" if current == port_name else ""
        print_menu_item(str(num), f"{port_name}", f"{label} (pin: {pin})", status)
        num += 1
    
    choice = prompt("Select thermistor port for hotend").strip()
    try:
        idx = int(choice) - 1
        if idx == 0:
            state.toolboard_assignments['thermistor_extruder'] = 'none'
        elif 1 <= idx < len(therm_list) + 1:
            state.toolboard_assignments['thermistor_extruder'] = therm_list[idx - 1]
    except ValueError:
        pass
    
    wait_for_key()

def assign_toolboard_fans(toolboard: Dict):
    """Assign toolboard fan ports."""
    fan_ports = toolboard.get('fan_ports', {})
    
    clear_screen()
    print_header("Toolboard Fans")
    
    print_info(f"{Colors.WHITE}Select 'None' if fan is on mainboard or not used{Colors.NC}")
    print_info("")
    
    fan_list = list(fan_ports.keys()) if fan_ports else []
    
    # Part cooling fan
    print_info(f"{Colors.BWHITE}Part Cooling Fan:{Colors.NC}")
    num = 1
    
    # "None" option first
    current = state.toolboard_assignments.get('fan_part_cooling', '')
    none_status = "done" if current == 'none' else ""
    print_menu_item(str(num), "None", "Part cooling on mainboard or not used", none_status)
    num += 1
    
    for port_name in fan_list:
        port = fan_ports[port_name]
        label = port.get('label', port_name)
        pin = port.get('pin', '?')
        status = "done" if current == port_name else ""
        print_menu_item(str(num), f"{port_name}", f"{label} (pin: {pin})", status)
        num += 1
    
    choice = prompt("Select fan port for part cooling").strip()
    try:
        idx = int(choice) - 1
        if idx == 0:
            state.toolboard_assignments['fan_part_cooling'] = 'none'
        elif 1 <= idx < len(fan_list) + 1:
            state.toolboard_assignments['fan_part_cooling'] = fan_list[idx - 1]
            # Clear mainboard assignments when moving to toolboard (no mixing allowed)
            if 'fan_part_cooling' in state.port_assignments:
                del state.port_assignments['fan_part_cooling']
            if 'fan_part_cooling_pin2' in state.port_assignments:
                del state.port_assignments['fan_part_cooling_pin2']
    except ValueError:
        pass
    
    print_info("")
    
    # Hotend fan
    print_info(f"{Colors.BWHITE}Hotend Fan:{Colors.NC}")
    num = 1
    
    # "None" option first
    current = state.toolboard_assignments.get('fan_hotend', '')
    none_status = "done" if current == 'none' else ""
    print_menu_item(str(num), "None", "Hotend fan on mainboard or water cooled", none_status)
    num += 1
    
    for port_name in fan_list:
        port = fan_ports[port_name]
        label = port.get('label', port_name)
        pin = port.get('pin', '?')
        status = "done" if current == port_name else ""
        print_menu_item(str(num), f"{port_name}", f"{label} (pin: {pin})", status)
        num += 1
    
    choice = prompt("Select fan port for hotend fan").strip()
    try:
        idx = int(choice) - 1
        if idx == 0:
            state.toolboard_assignments['fan_hotend'] = 'none'
        elif 1 <= idx < len(fan_list) + 1:
            state.toolboard_assignments['fan_hotend'] = fan_list[idx - 1]
            # Clear mainboard assignment when moving to toolboard (no mixing allowed)
            if 'fan_hotend' in state.port_assignments:
                del state.port_assignments['fan_hotend']
    except ValueError:
        pass

    wait_for_key()

def assign_toolboard_endstop(toolboard: Dict):
    """Assign toolboard endstop port (typically X endstop)."""
    endstop_ports = toolboard.get('endstop_ports', {})
    
    clear_screen()
    print_header("Toolboard X Endstop")
    
    print_info(f"{Colors.WHITE}X endstop can be connected to toolboard or mainboard{Colors.NC}")
    print_info("")
    
    endstop_list = list(endstop_ports.keys()) if endstop_ports else []
    
    print_info(f"{Colors.BWHITE}X Endstop Location:{Colors.NC}")
    num = 1
    
    # "None" option first - endstop on mainboard
    current = state.toolboard_assignments.get('endstop_x', '')
    none_status = "done" if current == 'none' or current == '' else ""
    print_menu_item(str(num), "None", "X endstop on mainboard", none_status)
    num += 1
    
    for port_name in endstop_list:
        port = endstop_ports[port_name]
        label = port.get('label', port_name)
        pin = port.get('pin', '?')
        status = "done" if current == port_name else ""
        print_menu_item(str(num), f"{port_name}", f"{label} (pin: {pin})", status)
        num += 1
    
    print_separator()
    print_action("B", "Back")
    print_footer()
    
    choice = prompt("Select endstop port for X axis").strip()
    
    if choice.lower() == 'b':
        return
    
    try:
        idx = int(choice) - 1
        if idx == 0:
            state.toolboard_assignments['endstop_x'] = 'none'
            # Also clear from mainboard if needed
            print(f"\n{Colors.GREEN}X endstop set to mainboard{Colors.NC}")
            wait_for_key()
        elif 1 <= idx < len(endstop_list) + 1:
            port_name = endstop_list[idx - 1]
            state.toolboard_assignments['endstop_x'] = port_name
            # Remove X endstop from mainboard assignments since it's on toolboard
            if 'endstop_x' in state.port_assignments:
                del state.port_assignments['endstop_x']
            print(f"\n{Colors.GREEN}X endstop assigned to toolboard:{port_name}{Colors.NC}")
            wait_for_key()
    except ValueError:
        pass

# ═══════════════════════════════════════════════════════════════════════════════
# LIGHTING PIN ASSIGNMENT
# ═══════════════════════════════════════════════════════════════════════════════

def assign_lighting_port():
    """Assign lighting pin with support for different LED types."""
    wizard_state = load_wizard_state()
    has_leds = wizard_state.get('has_leds', '')
    has_caselight = wizard_state.get('has_caselight', '')
    lighting_type = wizard_state.get('lighting_type', '')
    caselight_type = wizard_state.get('caselight_type', '')

    # Determine what to configure
    configure_status_leds = has_leds == 'yes'
    configure_caselight = has_caselight == 'yes'

    if not configure_status_leds and not configure_caselight:
        print(f"{Colors.YELLOW}No lighting options selected. Enable Status LEDs or Case Lighting first.{Colors.NC}")
        wait_for_key()
        return

    boards = load_available_boards()
    board = boards.get(state.board_id)
    if not board:
        print(f"{Colors.RED}No board selected!{Colors.NC}")
        wait_for_key()
        return

    # Check for toolboard
    toolboard = None
    has_toolboard = state.toolboard_id and state.toolboard_id != 'none'
    if has_toolboard:
        toolboards = load_available_toolboards()
        toolboard = toolboards.get(state.toolboard_id)

    # If both are enabled, ask which to configure
    purpose = 'status'  # Default to status LEDs
    current_type = lighting_type or 'neopixel'
    pin_key = 'lighting_pin'
    
    if configure_status_leds and configure_caselight:
        clear_screen()
        print_header("Lighting Pin Assignment")
        print_info(f"{Colors.BWHITE}Which lighting would you like to configure?{Colors.NC}")
        print_info("")
        
        # Show current assignments
        current_status_pin = state.port_assignments.get('lighting_pin', '') or state.toolboard_assignments.get('lighting_pin', '')
        current_caselight_pin = state.port_assignments.get('caselight_pin', '')
        
        status_info = f" - Currently: {Colors.GREEN}{current_status_pin}{Colors.NC}" if current_status_pin else ""
        caselight_info = f" - Currently: {Colors.GREEN}{current_caselight_pin}{Colors.NC}" if current_caselight_pin else ""
        
        print_menu_item("1", "Status LEDs", f"({lighting_type or 'neopixel'}){status_info}", "")
        print_menu_item("2", "Case Lighting", f"({caselight_type or 'simple'}){caselight_info}", "")
        print_separator()
        print_action("B", "Back")
        print_footer()
        
        choice = prompt("Select lighting to configure").strip()
        if choice.lower() == 'b':
            return
        elif choice == '2':
            purpose = 'caselight'
            current_type = caselight_type or 'simple'
            pin_key = 'caselight_pin'
        else:
            purpose = 'status'
            current_type = lighting_type or 'neopixel'
            pin_key = 'lighting_pin'
    elif configure_caselight:
        purpose = 'caselight'
        current_type = caselight_type or 'simple'
        pin_key = 'caselight_pin'
    else:
        purpose = 'status'
        current_type = lighting_type or 'neopixel'
        pin_key = 'lighting_pin'

    clear_screen()
    purpose_name = "Status LEDs" if purpose == 'status' else "Case Lighting"
    print_header(f"{purpose_name} Pin Assignment - {current_type.upper()}")

    # Build list of available ports based on lighting type
    port_options = []
    num = 1

    # For addressable LEDs (neopixel/dotstar) - prefer dedicated ports
    if current_type in ('neopixel', 'dotstar'):
        print_info(f"{Colors.BWHITE}Addressable LED Options:{Colors.NC}")
        print_info(f"{Colors.WHITE}(Neopixel/Dotstar need a data pin, some boards have dedicated ports){Colors.NC}")
        print_info("")

        # Check for dedicated NEOPIXEL port in misc_ports
        misc_ports = board.get('misc_ports', {})
        if 'NEOPIXEL' in misc_ports:
            port = misc_ports['NEOPIXEL']
            pin = port.get('pin', '?')
            label = port.get('label', 'NeoPixel')
            current = state.port_assignments.get(pin_key, '')
            status = "done" if current == f"NEOPIXEL:{pin}" else ""
            print_menu_item(str(num), f"NEOPIXEL", f"{label} - pin: {pin}", status)
            port_options.append(('mainboard', 'NEOPIXEL', pin, 'misc', None, None))
            num += 1

        # Fan ports can also work for data signal
        print_info("")
        print_info(f"{Colors.BWHITE}Fan Ports (can be used for LED data):{Colors.NC}")
        fan_ports = board.get('fan_ports', {})
        for port_name, port in fan_ports.items():
            pin = port.get('pin', '?')
            label = port.get('label', port_name)
            status = "done" if state.port_assignments.get(pin_key, '') == f"{port_name}:{pin}" else ""
            print_menu_item(str(num), port_name, f"{label} - pin: {pin}", status)
            port_options.append(('mainboard', port_name, pin, 'fan', None, None))
            num += 1

    # For simple/PWM LED - fan ports and heater ports
    elif current_type in ('pwm', 'simple'):
        print_info(f"{Colors.BWHITE}PWM LED Options:{Colors.NC}")
        print_info(f"{Colors.WHITE}(Simple on/off or dimmable LED via PWM signal){Colors.NC}")
        print_info("")

        # Fan ports (most common for PWM LED)
        print_info(f"{Colors.BWHITE}Fan Ports:{Colors.NC}")
        fan_ports = board.get('fan_ports', {})
        for port_name, port in fan_ports.items():
            pin = port.get('pin', '?')
            label = port.get('label', port_name)
            status = "done" if state.port_assignments.get(pin_key, '') == f"{port_name}:{pin}" else ""
            print_menu_item(str(num), port_name, f"{label} - pin: {pin}", status)
            port_options.append(('mainboard', port_name, pin, 'fan', None, None))
            num += 1

        # Heater ports (for high-power LEDs)
        print_info("")
        print_info(f"{Colors.BWHITE}Heater Ports (high-power LEDs):{Colors.NC}")
        print_info(f"{Colors.YELLOW}⚠ For high-current LEDs that need more power than fan ports{Colors.NC}")
        heater_ports = board.get('heater_ports', {})
        for port_name, port in heater_ports.items():
            if port_name in ('HB',):  # Skip heated bed
                continue
            pin = port.get('pin', '?')
            label = port.get('label', port_name)
            status = "done" if state.port_assignments.get(pin_key, '') == f"{port_name}:{pin}" else ""
            print_menu_item(str(num), port_name, f"{label} - pin: {pin} (HIGH POWER)", status)
            port_options.append(('mainboard', port_name, pin, 'heater', None, None))
            num += 1

    # PCA9533 - I2C device
    elif current_type == 'pca9533':
        print_info(f"{Colors.BWHITE}PCA9533 I2C LED Driver:{Colors.NC}")
        print_info(f"{Colors.WHITE}(I2C device - uses I2C bus, address configurable){Colors.NC}")
        print_info("")
        print_info(f"  Default I2C address: 0x62")
        print_info(f"  Uses the board's I2C bus (usually i2c_software or i2c_mcu)")
        print_info("")

        # For PCA9533, we just need to store that it's configured
        current = state.port_assignments.get(pin_key, '')
        status = "done" if current == "i2c:pca9533" else ""
        print_menu_item(str(num), "I2C", "PCA9533 on I2C bus", status)
        port_options.append(('mainboard', 'I2C', 'pca9533', 'i2c', None, None))
        num += 1

    # Toolboard options (if available and applicable) - only for status LEDs, not caselight
    if has_toolboard and toolboard and current_type in ('neopixel', 'dotstar', 'pwm') and purpose == 'status':
        print_info("")
        print_info(f"{Colors.BWHITE}Toolboard Options ({state.toolboard_name}):{Colors.NC}")

        # Toolboard misc ports - check for NEOPIXEL, RGB, or HOTEND_LED
        tb_misc = toolboard.get('misc_ports', {})

        # Addressable LED ports (NEOPIXEL or RGB)
        if current_type in ('neopixel', 'dotstar'):
            for port_key in ('NEOPIXEL', 'RGB'):
                if port_key in tb_misc:
                    port = tb_misc[port_key]
                    pin = port.get('pin', '?')
                    label = port.get('label', 'NeoPixel/RGB')
                    chain_count = port.get('chain_count')
                    color_order = port.get('color_order')

                    # Build info string with chain_count and color_order if available
                    info = f"Toolboard {label} - pin: {pin}"
                    if chain_count:
                        info += f" ({chain_count} LED{'s' if chain_count > 1 else ''}"
                        if color_order:
                            info += f", {color_order}"
                        info += ")"

                    status = "done" if state.toolboard_assignments.get(pin_key, '') == f"{port_key}:{pin}" else ""
                    print_menu_item(str(num), f"TB:{port_key}", info, status)
                    # Store chain_count and color_order in port_options for later use
                    port_options.append(('toolboard', port_key, pin, 'misc', chain_count, color_order))
                    num += 1

        # Simple LED port (HOTEND_LED) - for PWM lighting
        if current_type == 'pwm' and 'HOTEND_LED' in tb_misc:
            port = tb_misc['HOTEND_LED']
            pin = port.get('pin', '?')
            label = port.get('label', 'Hotend LED')
            status = "done" if state.toolboard_assignments.get(pin_key, '') == f"HOTEND_LED:{pin}" else ""
            print_menu_item(str(num), f"TB:HOTEND_LED", f"Toolboard {label} - pin: {pin}", status)
            port_options.append(('toolboard', 'HOTEND_LED', pin, 'misc', None, None))
            num += 1

        # Toolboard fan ports
        tb_fan_ports = toolboard.get('fan_ports', {})
        for port_name, port in tb_fan_ports.items():
            pin = port.get('pin', '?')
            label = port.get('label', port_name)
            status = "done" if state.toolboard_assignments.get(pin_key, '') == f"{port_name}:{pin}" else ""
            print_menu_item(str(num), f"TB:{port_name}", f"Toolboard {label} - pin: {pin}", status)
            port_options.append(('toolboard', port_name, pin, 'fan', None, None))
            num += 1

    # Manual pin entry option
    print_info("")
    print_menu_item("M", "Manual", "Enter pin manually (e.g., PA8, PB0)", "")

    # Clear option
    print_info("")
    print_action("X", f"Clear {purpose_name.lower()} pin assignment")

    print_separator()
    print_action("B", "Back")
    print_footer()

    choice = prompt(f"Select port for {purpose_name.lower()}").strip()

    if choice.lower() == 'b':
        return
    elif choice.lower() == 'x':
        # Clear assignments for this specific purpose
        if pin_key in state.port_assignments:
            del state.port_assignments[pin_key]
        clock_key = pin_key.replace('_pin', '_clock_pin')
        if clock_key in state.port_assignments:
            del state.port_assignments[clock_key]
        if pin_key in state.toolboard_assignments:
            del state.toolboard_assignments[pin_key]
        if clock_key in state.toolboard_assignments:
            del state.toolboard_assignments[clock_key]
        print(f"\n{Colors.GREEN}{purpose_name} pin assignment cleared{Colors.NC}")
        state.save()
        wait_for_key()
        return
    elif choice.lower() == 'm':
        # Manual pin entry
        print_info("")
        pin = prompt("Enter data pin (e.g., PA8, PB0)").strip().upper()
        if pin:
            # Ask mainboard or toolboard (only for status LEDs)
            if has_toolboard and purpose == 'status':
                loc = prompt("Mainboard or Toolboard? [m/t]").strip().lower()
                if loc == 't':
                    state.toolboard_assignments[pin_key] = f"manual:{pin}"
                    if pin_key in state.port_assignments:
                        del state.port_assignments[pin_key]
                else:
                    state.port_assignments[pin_key] = f"manual:{pin}"
                    if pin_key in state.toolboard_assignments:
                        del state.toolboard_assignments[pin_key]
            else:
                # Caselight is always on mainboard
                state.port_assignments[pin_key] = f"manual:{pin}"

            # For Dotstar, also need clock pin
            if current_type == 'dotstar':
                clock = prompt("Enter clock pin for Dotstar (e.g., PA9)").strip().upper()
                if clock:
                    clock_key = pin_key.replace('_pin', '_clock_pin')
                    if has_toolboard and purpose == 'status' and loc == 't':
                        state.toolboard_assignments[clock_key] = f"manual:{clock}"
                    else:
                        state.port_assignments[clock_key] = f"manual:{clock}"

            print(f"\n{Colors.GREEN}{purpose_name} pin assigned: {pin}{Colors.NC}")
            state.save()
        wait_for_key()
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(port_options):
            location, port_name, pin, port_type, chain_count, color_order = port_options[idx]

            if location == 'toolboard':
                state.toolboard_assignments[pin_key] = f"{port_name}:{pin}"
                # Store chain_count and color_order if available from template
                if chain_count:
                    state.toolboard_assignments[f'{pin_key}_chain_count'] = str(chain_count)
                if color_order:
                    state.toolboard_assignments[f'{pin_key}_color_order'] = color_order
                # Clear mainboard assignment
                if pin_key in state.port_assignments:
                    del state.port_assignments[pin_key]
                if f'{pin_key}_chain_count' in state.port_assignments:
                    del state.port_assignments[f'{pin_key}_chain_count']
                if f'{pin_key}_color_order' in state.port_assignments:
                    del state.port_assignments[f'{pin_key}_color_order']
                print(f"\n{Colors.GREEN}{purpose_name} assigned to toolboard:{port_name} (pin: {pin}){Colors.NC}")
                if chain_count:
                    print(f"{Colors.GREEN}  Chain count: {chain_count}, Color order: {color_order or 'GRB'}{Colors.NC}")
            else:
                state.port_assignments[pin_key] = f"{port_name}:{pin}"
                # Clear toolboard assignment (only relevant for status LEDs)
                if pin_key in state.toolboard_assignments:
                    del state.toolboard_assignments[pin_key]
                if f'{pin_key}_chain_count' in state.toolboard_assignments:
                    del state.toolboard_assignments[f'{pin_key}_chain_count']
                if f'{pin_key}_color_order' in state.toolboard_assignments:
                    del state.toolboard_assignments[f'{pin_key}_color_order']
                print(f"\n{Colors.GREEN}{purpose_name} assigned to {port_name} (pin: {pin}){Colors.NC}")

            # For Dotstar on mainboard, need clock pin
            if current_type == 'dotstar' and location == 'mainboard':
                print_info("")
                print_info(f"{Colors.YELLOW}Dotstar also needs a clock pin.{Colors.NC}")
                clock = prompt("Enter clock pin (e.g., PA9) or press Enter to skip").strip().upper()
                if clock:
                    clock_key = pin_key.replace('_pin', '_clock_pin')
                    state.port_assignments[clock_key] = f"manual:{clock}"
                    print(f"{Colors.GREEN}Clock pin: {clock}{Colors.NC}")

            state.save()
            wait_for_key()
    except ValueError:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# MOTOR FUNCTION CALCULATION
# ═══════════════════════════════════════════════════════════════════════════════

def load_wizard_state() -> Dict[str, str]:
    """Load wizard state from file."""
    wizard_state = {}
    wizard_state_file = REPO_ROOT / ".wizard-state"
    
    if wizard_state_file.exists():
        try:
            with open(wizard_state_file) as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        wizard_state[key] = value
        except:
            pass
    
    return wizard_state

def get_required_motor_functions() -> List[str]:
    """
    Calculate required motor functions based on wizard state and toolboard selection.
    
    Returns list like: ['stepper_x', 'stepper_y', 'stepper_z', 'stepper_z1', 'extruder']
    For AWD: ['stepper_x', 'stepper_x1', 'stepper_y', 'stepper_y1', 'stepper_z', ...]
    
    Extruder is ONLY included if NO toolboard is selected (extruder on toolboard otherwise).
    """
    wizard_state = load_wizard_state()
    kinematics = wizard_state.get('kinematics', 'corexy')
    
    # Start with X and Y
    functions = ['stepper_x', 'stepper_y']
    
    # AWD kinematics needs X1 and Y1 as well
    if kinematics == 'corexy-awd':
        functions = ['stepper_x', 'stepper_x1', 'stepper_y', 'stepper_y1']
    
    # Add Z steppers based on count
    z_count = int(wizard_state.get('z_stepper_count', '1') or '1')
    functions.append('stepper_z')
    for i in range(1, z_count):
        functions.append(f'stepper_z{i}')
    
    # Add extruder ONLY if no toolboard selected
    # When toolboard is used, extruder motor is on the toolboard
    has_toolboard = state.toolboard_id and state.toolboard_id != "none"
    
    if not has_toolboard:
        functions.append('extruder')
    
    return functions

def get_motor_port_summary() -> str:
    """Get a summary of required motor ports."""
    functions = get_required_motor_functions()
    has_toolboard = state.toolboard_id and state.toolboard_id != "none"
    
    summary = f"{len(functions)} ports needed"
    if has_toolboard:
        summary += " (extruder on toolboard)"
    
    return summary

# ═══════════════════════════════════════════════════════════════════════════════
# SINGLE PORT SELECTION (CLI mode)
# ═══════════════════════════════════════════════════════════════════════════════

def select_single_port(port_type: str, ports: Dict, assignment_key: str, title: str) -> bool:
    """
    Interactive single port selection for CLI mode.
    port_type: 'heater', 'thermistor', 'endstop', 'fan', 'gpio'
    ports: dict of available ports
    assignment_key: key to store in state.port_assignments
    title: display title
    Returns True if saved, False if cancelled.
    """
    clear_screen()
    print_header(title)

    port_list = list(ports.keys())
    if not port_list:
        print_info(f"{Colors.YELLOW}No {port_type} ports available on this board.{Colors.NC}")
        wait_for_key()
        return False

    print_info(f"Current: {Colors.CYAN}{state.port_assignments.get(assignment_key, 'not assigned')}{Colors.NC}")
    print_info("")
    print_info(f"Available {port_type} ports:")
    print_info("")

    num = 1
    for port_name in port_list:
        port = ports[port_name]
        label = port.get('label', port_name)
        pin = port.get('pin', port.get('step_pin', '?'))

        # Check if used by another function
        used_by = None
        for func, assigned_port in state.port_assignments.items():
            if assigned_port == port_name and func != assignment_key:
                used_by = func
                break

        status_text = f" {Colors.YELLOW}(used by {used_by}){Colors.NC}" if used_by else ""
        current = state.port_assignments.get(assignment_key, "")
        status = "done" if current == port_name else ""
        print_menu_item(str(num), f"{port_name}", f"{label} - pin: {pin}{status_text}", status)
        num += 1

    print_separator()
    print_action("C", "Clear assignment")
    print_action("B", "Back without saving")
    print_footer()

    choice = prompt("Select port").strip()

    if choice.lower() == 'b':
        return False
    if choice.lower() == 'c':
        if assignment_key in state.port_assignments:
            del state.port_assignments[assignment_key]
        print(f"\n{Colors.GREEN}Assignment cleared.{Colors.NC}")
        return True

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(port_list):
            state.port_assignments[assignment_key] = port_list[idx]
            print(f"\n{Colors.GREEN}Assigned {assignment_key} to {port_list[idx]}{Colors.NC}")
            return True
    except ValueError:
        pass

    return False


def select_single_endstop(axis: str, board: Dict) -> bool:
    """Select endstop port for a single axis."""
    endstop_ports = board.get('endstop_ports', board.get('gpio_ports', {}))
    assignment_key = f'endstop_{axis.lower()}'

    clear_screen()
    print_header(f"Select {axis.upper()} Endstop Port")

    port_list = list(endstop_ports.keys())

    print_info(f"Current: {Colors.CYAN}{state.port_assignments.get(assignment_key, 'not assigned')}{Colors.NC}")
    print_info("")
    print_info("Available endstop ports:")
    print_info("")

    num = 1
    for port_name in port_list:
        port = endstop_ports[port_name]
        label = port.get('label', port_name)
        pin = port.get('pin', '?')

        used_by = None
        for func, assigned_port in state.port_assignments.items():
            if assigned_port == port_name and func != assignment_key:
                used_by = func
                break

        status_text = f" {Colors.YELLOW}(used by {used_by}){Colors.NC}" if used_by else ""
        current = state.port_assignments.get(assignment_key, "")
        status = "done" if current == port_name else ""
        print_menu_item(str(num), f"{port_name}", f"{label} - pin: {pin}{status_text}", status)
        num += 1

    # Sensorless option for X/Y
    if axis.lower() in ('x', 'y'):
        print_info("")
        current = state.port_assignments.get(assignment_key, "")
        sensorless_status = "done" if current == "sensorless" else ""
        print_menu_item(str(num), "Sensorless homing", "Uses TMC DIAG pin", sensorless_status)
        sensorless_idx = num
        num += 1
    else:
        sensorless_idx = -1

    print_separator()
    print_action("C", "Clear assignment")
    print_action("B", "Back without saving")
    print_footer()

    choice = prompt("Select port").strip()

    if choice.lower() == 'b':
        return False
    if choice.lower() == 'c':
        if assignment_key in state.port_assignments:
            del state.port_assignments[assignment_key]
        print(f"\n{Colors.GREEN}Assignment cleared.{Colors.NC}")
        return True

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(port_list):
            state.port_assignments[assignment_key] = port_list[idx]
            print(f"\n{Colors.GREEN}Assigned {assignment_key} to {port_list[idx]}{Colors.NC}")
            return True
        elif sensorless_idx > 0 and idx == sensorless_idx - 1:
            state.port_assignments[assignment_key] = "sensorless"
            print(f"\n{Colors.GREEN}Set {assignment_key} to sensorless homing{Colors.NC}")
            return True
    except ValueError:
        pass

    return False


def select_flexible_port(port_type: str, assignment_key: str, title: str,
                         supports_modifiers: bool = False, is_adc: bool = False) -> bool:
    """
    Flexible port selection - offers BOTH mainboard and toolboard ports.
    User chooses which board to assign to.

    Args:
        port_type: Type of port ('heater', 'thermistor', 'endstop', 'fan', etc.)
        assignment_key: Key for storing in port_assignments
        title: Header title for the menu
        supports_modifiers: If True, prompt for pin modifiers (inversion, pull-up/down)
        is_adc: If True and supports_modifiers, only offer pull-up (for ADC pins)
    """
    boards = load_available_boards()
    board = boards.get(state.board_id)
    has_toolboard = state.toolboard_id and state.toolboard_id != "none"

    clear_screen()
    print_header(title)

    # Get ports from mainboard
    if port_type == 'heater':
        mb_ports = board.get('heater_ports', {})
    elif port_type == 'thermistor':
        mb_ports = board.get('thermistor_ports', {})
    elif port_type == 'endstop':
        mb_ports = board.get('endstop_ports', board.get('gpio_ports', {}))
    elif port_type == 'fan':
        mb_ports = board.get('fan_ports', {})
    else:
        mb_ports = board.get('gpio_ports', {})

    # Get ports from toolboard if exists
    tb_ports = {}
    toolboard = None
    if has_toolboard:
        toolboards = load_available_toolboards()
        toolboard = toolboards.get(state.toolboard_id)
        if toolboard:
            if port_type == 'heater':
                tb_ports = toolboard.get('heater_ports', {})
            elif port_type == 'thermistor':
                tb_ports = toolboard.get('thermistor_ports', {})
            elif port_type == 'endstop':
                tb_ports = toolboard.get('endstop_ports', {})
            elif port_type == 'fan':
                tb_ports = toolboard.get('fan_ports', {})
            else:
                tb_ports = toolboard.get('gpio_ports', {})

    # Show current assignment
    current_mb = state.port_assignments.get(assignment_key, '')
    current_tb = state.toolboard_assignments.get(assignment_key, '') if has_toolboard else ''
    if current_tb and current_tb != 'none':
        print_info(f"Current: {Colors.CYAN}toolboard:{current_tb}{Colors.NC}")
    elif current_mb:
        print_info(f"Current: {Colors.CYAN}{current_mb}{Colors.NC}")
    else:
        print_info(f"Current: {Colors.CYAN}not assigned{Colors.NC}")
    print_info("")

    num = 1
    port_map = []  # (board_type, port_name)

    # Mainboard ports
    if mb_ports:
        print_info(f"{Colors.BWHITE}Mainboard ({board.get('name', 'Main')}):{Colors.NC}")
        for port_name in mb_ports:
            port = mb_ports[port_name]
            label = port.get('label', port_name)
            pin = port.get('pin', '?')
            status = "done" if current_mb == port_name else ""
            print_menu_item(str(num), f"{port_name}", f"{label} - pin: {pin}", status)
            port_map.append(('mainboard', port_name))
            num += 1
        print_info("")

    # Toolboard ports
    if tb_ports:
        print_info(f"{Colors.BWHITE}Toolboard ({toolboard.get('name', 'Toolboard')}):{Colors.NC}")
        for port_name in tb_ports:
            port = tb_ports[port_name]
            label = port.get('label', port_name)
            pin = port.get('pin', '?')
            status = "done" if current_tb == port_name else ""
            print_menu_item(str(num), f"toolboard:{port_name}", f"{label} - pin: {pin}", status)
            port_map.append(('toolboard', port_name))
            num += 1

    print_separator()
    print_action("C", "Clear assignment")
    print_action("B", "Back without saving")
    print_footer()

    choice = prompt("Select port").strip()

    if choice.lower() == 'b':
        return False
    if choice.lower() == 'c':
        if assignment_key in state.port_assignments:
            del state.port_assignments[assignment_key]
        if f"{assignment_key}_modifiers" in state.port_assignments:
            del state.port_assignments[f"{assignment_key}_modifiers"]
        if assignment_key in state.toolboard_assignments:
            del state.toolboard_assignments[assignment_key]
        if f"{assignment_key}_modifiers" in state.toolboard_assignments:
            del state.toolboard_assignments[f"{assignment_key}_modifiers"]
        print(f"\n{Colors.GREEN}Assignment cleared.{Colors.NC}")
        return True

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(port_map):
            board_type, port_name = port_map[idx]

            # Configure pin modifiers if supported
            modifiers = ""
            if supports_modifiers:
                modifiers = configure_pin_modifiers(title, is_adc=is_adc)

            if board_type == 'mainboard':
                state.port_assignments[assignment_key] = port_name
                if modifiers:
                    state.port_assignments[f"{assignment_key}_modifiers"] = modifiers
                elif f"{assignment_key}_modifiers" in state.port_assignments:
                    del state.port_assignments[f"{assignment_key}_modifiers"]
                # Clear toolboard assignment if any
                if assignment_key in state.toolboard_assignments:
                    del state.toolboard_assignments[assignment_key]
                if f"{assignment_key}_modifiers" in state.toolboard_assignments:
                    del state.toolboard_assignments[f"{assignment_key}_modifiers"]
                print(f"\n{Colors.GREEN}Assigned {assignment_key} to mainboard:{port_name}{Colors.NC}")
            else:
                state.toolboard_assignments[assignment_key] = port_name
                if modifiers:
                    state.toolboard_assignments[f"{assignment_key}_modifiers"] = modifiers
                elif f"{assignment_key}_modifiers" in state.toolboard_assignments:
                    del state.toolboard_assignments[f"{assignment_key}_modifiers"]
                # Clear mainboard assignment if any
                if assignment_key in state.port_assignments:
                    del state.port_assignments[assignment_key]
                if f"{assignment_key}_modifiers" in state.port_assignments:
                    del state.port_assignments[f"{assignment_key}_modifiers"]
                print(f"\n{Colors.GREEN}Assigned {assignment_key} to toolboard:{port_name}{Colors.NC}")

            if modifiers:
                print(f"{Colors.GREEN}Pin modifiers: {modifiers}{Colors.NC}")
            return True
    except ValueError:
        pass

    return False


def select_toolboard_single_port(port_type: str, ports: Dict, assignment_key: str, title: str) -> bool:
    """
    Interactive single port selection for toolboard (CLI mode).
    Stores in state.toolboard_assignments instead of state.port_assignments.
    """
    clear_screen()
    print_header(title)

    port_list = list(ports.keys())
    if not port_list:
        print_info(f"{Colors.YELLOW}No {port_type} ports available on this toolboard.{Colors.NC}")
        wait_for_key()
        return False

    print_info(f"Current: {Colors.CYAN}{state.toolboard_assignments.get(assignment_key, 'not assigned')}{Colors.NC}")
    print_info("")
    print_info(f"Available {port_type} ports (on toolboard):")
    print_info("")

    num = 1
    for port_name in port_list:
        port = ports[port_name]
        label = port.get('label', port_name)
        pin = port.get('pin', port.get('step_pin', '?'))

        # Check if used by another function
        used_by = None
        for func, assigned_port in state.toolboard_assignments.items():
            if assigned_port == port_name and func != assignment_key:
                used_by = func
                break

        status_text = f" {Colors.YELLOW}(used by {used_by}){Colors.NC}" if used_by else ""
        current = state.toolboard_assignments.get(assignment_key, "")
        status = "done" if current == port_name else ""
        print_menu_item(str(num), f"{port_name}", f"{label} - pin: {pin}{status_text}", status)
        num += 1

    print_separator()
    print_action("C", "Clear assignment")
    print_action("B", "Back without saving")
    print_footer()

    choice = prompt("Select port").strip()

    if choice.lower() == 'b':
        return False
    if choice.lower() == 'c':
        if assignment_key in state.toolboard_assignments:
            del state.toolboard_assignments[assignment_key]
        print(f"\n{Colors.GREEN}Assignment cleared.{Colors.NC}")
        return True

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(port_list):
            state.toolboard_assignments[assignment_key] = port_list[idx]
            print(f"\n{Colors.GREEN}Assigned {assignment_key} to toolboard:{port_list[idx]}{Colors.NC}")
            return True
    except ValueError:
        pass

    return False


def select_toolboard_endstop(axis: str, toolboard: Dict) -> bool:
    """Select endstop port on toolboard for a single axis."""
    endstop_ports = toolboard.get('endstop_ports', {})
    assignment_key = f'endstop_{axis.lower()}'

    clear_screen()
    print_header(f"Select Toolboard {axis.upper()} Endstop Port")

    port_list = list(endstop_ports.keys())
    if not port_list:
        print_info(f"{Colors.YELLOW}No endstop ports available on this toolboard.{Colors.NC}")
        wait_for_key()
        return False

    print_info(f"Current: {Colors.CYAN}{state.toolboard_assignments.get(assignment_key, 'not assigned')}{Colors.NC}")
    print_info("")
    print_info("Available endstop ports (on toolboard):")
    print_info("")

    num = 1
    for port_name in port_list:
        port = endstop_ports[port_name]
        label = port.get('label', port_name)
        pin = port.get('pin', '?')

        used_by = None
        for func, assigned_port in state.toolboard_assignments.items():
            if assigned_port == port_name and func != assignment_key:
                used_by = func
                break

        status_text = f" {Colors.YELLOW}(used by {used_by}){Colors.NC}" if used_by else ""
        current = state.toolboard_assignments.get(assignment_key, "")
        status = "done" if current == port_name else ""
        print_menu_item(str(num), f"{port_name}", f"{label} - pin: {pin}{status_text}", status)
        num += 1

    print_separator()
    print_action("C", "Clear assignment")
    print_action("B", "Back without saving")
    print_footer()

    choice = prompt("Select port").strip()

    if choice.lower() == 'b':
        return False
    if choice.lower() == 'c':
        if assignment_key in state.toolboard_assignments:
            del state.toolboard_assignments[assignment_key]
        print(f"\n{Colors.GREEN}Assignment cleared.{Colors.NC}")
        return True

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(port_list):
            state.toolboard_assignments[assignment_key] = port_list[idx]
            print(f"\n{Colors.GREEN}Assigned {assignment_key} to toolboard:{port_list[idx]}{Colors.NC}")
            return True
    except ValueError:
        pass

    return False


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN MENU
# ═══════════════════════════════════════════════════════════════════════════════

def main_menu():
    """Main hardware setup menu."""
    boards = load_available_boards()
    
    while True:
        clear_screen()
        print_header("Hardware Setup")
        
        # Calculate requirements
        required_functions = get_required_motor_functions()
        has_toolboard = state.toolboard_id and state.toolboard_id != "none"
        
        # Show current status
        board_status = "done" if state.board_id else ""
        toolboard_status = "done" if state.toolboard_id else ""
        
        # Check if all required motor functions are assigned
        assigned_motors = [k for k in state.port_assignments if k.startswith('stepper') or k == 'extruder']
        motors_status = "done" if set(required_functions) <= set(state.port_assignments.keys()) else ""
        heaters_status = "done" if 'heater_bed' in state.port_assignments else ""
        fans_status = "done" if 'fan_controller' in state.port_assignments or 'fan_part_cooling' in state.port_assignments else ""
        
        print_menu_item("1", "Main Board", state.board_name or "not selected", board_status)
        
        tb_display = state.toolboard_name or "none"
        if has_toolboard:
            tb_display += " (extruder here)"
        print_menu_item("2", "Toolhead Board", tb_display, toolboard_status)
        print_info("")
        
        if state.board_id:
            motor_info = get_motor_port_summary()
            print_menu_item("3", "Motor Ports", motor_info, motors_status)
            
            # Check endstop status
            wizard_state = load_wizard_state()
            probe_type = wizard_state.get('probe_type', '')
            endstops_needed = ['endstop_x', 'endstop_y']
            if probe_type in ('', 'none', 'endstop'):
                endstops_needed.append('endstop_z')
            endstops_status = "done" if all(e in state.port_assignments for e in endstops_needed) else ""
            endstop_info = "X, Y" + (", Z" if 'endstop_z' in endstops_needed else " (Z via probe)")
            print_menu_item("4", "Endstop Ports", endstop_info, endstops_status)
            
            heater_info = "bed"
            if not has_toolboard:
                heater_info += " + hotend"
            print_menu_item("5", "Heater & Thermistor Ports", heater_info, heaters_status)
            
            fan_info = "controller"
            if not has_toolboard:
                fan_info += " + part cooling + hotend"
            print_menu_item("6", "Fan Ports", fan_info, fans_status)
            
            # MCU Serial configuration
            mcu_status = "done" if state.mcu_serial else ""
            tb_serial_status = ""
            if has_toolboard:
                toolboards = load_available_toolboards()
                tb = toolboards.get(state.toolboard_id)
                tb_conn = tb.get('connection', 'USB').upper() if tb else 'USB'
                if tb_conn == 'CAN':
                    tb_serial_status = "done" if state.toolboard_canbus_uuid else ""
                else:
                    tb_serial_status = "done" if state.toolboard_serial else ""
            
            serial_status = "done" if mcu_status == "done" and (not has_toolboard or tb_serial_status == "done") else ""
            serial_info = "main MCU"
            if has_toolboard:
                serial_info += " + toolboard"
            print_menu_item("7", "MCU Serial IDs", serial_info, serial_status)
            
            # Toolboard port assignment (only if toolboard selected)
            if has_toolboard:
                # Check toolboard assignment status
                tb_motor = state.toolboard_assignments.get('extruder', '')
                tb_heater = state.toolboard_assignments.get('heater_extruder', '')
                tb_therm = state.toolboard_assignments.get('thermistor_extruder', '')
                tb_fan = state.toolboard_assignments.get('fan_part_cooling', '')
                tb_ports_status = "done" if tb_motor and tb_heater and tb_therm and tb_fan else ""
                tb_ports_info = "extruder, heater, fans"
                print_menu_item("8", "Toolboard Ports", tb_ports_info, tb_ports_status)
        else:
            print_info(f"  {Colors.YELLOW}Select a board first to configure ports{Colors.NC}")
        
        print_separator()
        print_action("S", "Save and Exit")
        print_action("Q", "Quit without Saving")
        print_footer()
        
        choice = prompt("Select option").strip().lower()
        
        if choice == '1':
            select_board()
        elif choice == '2':
            select_toolboard()
        elif choice == '3' and state.board_id:
            board = boards.get(state.board_id)
            if board:
                # Determine required motor functions based on wizard state
                functions = get_required_motor_functions()
                assign_motor_ports(board, functions)
        elif choice == '4' and state.board_id:
            board = boards.get(state.board_id)
            if board:
                assign_endstop_ports(board)
        elif choice == '5' and state.board_id:
            board = boards.get(state.board_id)
            if board:
                assign_heater_ports(board)
        elif choice == '6' and state.board_id:
            board = boards.get(state.board_id)
            if board:
                assign_fan_ports(board)
        elif choice == '7' and state.board_id:
            assign_mcu_serials()
        elif choice == '8' and state.board_id and has_toolboard:
            toolboards = load_available_toolboards()
            tb = toolboards.get(state.toolboard_id)
            if tb:
                assign_toolboard_ports(tb)
        elif choice == 's':
            state.save()
            print(f"\n{Colors.GREEN}Configuration saved to {STATE_FILE}{Colors.NC}")
            wait_for_key()
            return True
        elif choice == 'q':
            if confirm("Quit without saving?"):
                return False

# ═══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='gschpoozi Hardware Setup')
    parser.add_argument('--board', action='store_true', help='Board setup only')
    parser.add_argument('--toolboard', action='store_true', help='Toolboard setup only')
    parser.add_argument('--motors', action='store_true', help='Motor port assignment only')
    parser.add_argument('--heater-extruder', action='store_true', help='Assign hotend heater port')
    parser.add_argument('--thermistor-extruder', action='store_true', help='Assign hotend thermistor port')
    parser.add_argument('--heater-bed', action='store_true', help='Assign bed heater port')
    parser.add_argument('--thermistor-bed', action='store_true', help='Assign bed thermistor port')
    parser.add_argument('--thermistor-chamber', action='store_true', help='Assign chamber thermistor port')
    parser.add_argument('--endstop-x', action='store_true', help='Assign X endstop port')
    parser.add_argument('--endstop-y', action='store_true', help='Assign Y endstop port')
    parser.add_argument('--endstop-z', action='store_true', help='Assign Z endstop port')
    parser.add_argument('--probe-pin', action='store_true', help='Assign probe pin')
    parser.add_argument('--fan', type=str, metavar='KEY', help='Assign fan port (e.g., fan_part_cooling)')
    parser.add_argument('--fan-multipin', type=str, metavar='KEY', help='Assign secondary fan pin')
    parser.add_argument('--lighting', action='store_true', help='Configure lighting')
    parser.add_argument('--clear-port', type=str, metavar='KEY', help='Clear a port assignment (e.g., fan_part_cooling)')
    parser.add_argument('--list-boards', action='store_true', help='List available boards')
    parser.add_argument('--output', type=str, help='Output state file path')
    
    args = parser.parse_args()
    
    # Override state file if specified
    global STATE_FILE
    if args.output:
        STATE_FILE = Path(args.output)
    
    # Load existing state
    state.load()
    
    if args.list_boards:
        boards = load_available_boards()
        toolboards = load_available_toolboards()
        
        print(f"\n{Colors.BWHITE}Available Boards:{Colors.NC}")
        for board_id, board in boards.items():
            print(f"  - {board['name']} ({board_id})")
        
        print(f"\n{Colors.BWHITE}Available Toolboards:{Colors.NC}")
        for board_id, board in toolboards.items():
            print(f"  - {board['name']} ({board_id})")
        
        return
    
    if args.board:
        select_board()
        state.save()
    elif args.toolboard:
        select_toolboard()
        state.save()
    elif args.motors:
        # Motor port assignment - requires board to be selected
        if not state.board_id:
            print(f"{Colors.RED}Error: No board selected. Run setup-hardware.py --board first.{Colors.NC}")
            sys.exit(1)
        boards = load_available_boards()
        board = boards.get(state.board_id)
        if not board:
            print(f"{Colors.RED}Error: Board '{state.board_id}' not found.{Colors.NC}")
            sys.exit(1)
        functions = get_required_motor_functions()
        if assign_motor_ports(board, functions):
            state.save()
            print(f"\n{Colors.GREEN}Motor port assignments saved.{Colors.NC}")
    elif getattr(args, 'heater_extruder', False):
        if not state.board_id:
            print(f"{Colors.RED}Error: No board selected.{Colors.NC}")
            sys.exit(1)
        # Offer BOTH mainboard and toolboard ports - user chooses
        if select_flexible_port('heater', 'heater_extruder', 'Select Hotend Heater Port'):
            state.save()
    elif getattr(args, 'thermistor_extruder', False):
        if not state.board_id:
            print(f"{Colors.RED}Error: No board selected.{Colors.NC}")
            sys.exit(1)
        # Offer BOTH mainboard and toolboard ports - user chooses
        if select_flexible_port('thermistor', 'thermistor_extruder', 'Select Hotend Thermistor Port'):
            state.save()
    elif getattr(args, 'heater_bed', False):
        if not state.board_id:
            print(f"{Colors.RED}Error: No board selected.{Colors.NC}")
            sys.exit(1)
        # Offer BOTH mainboard and toolboard ports - user chooses
        if select_flexible_port('heater', 'heater_bed', 'Select Bed Heater Port'):
            state.save()
    elif getattr(args, 'thermistor_bed', False):
        if not state.board_id:
            print(f"{Colors.RED}Error: No board selected.{Colors.NC}")
            sys.exit(1)
        # Offer BOTH mainboard and toolboard ports - user chooses
        if select_flexible_port('thermistor', 'thermistor_bed', 'Select Bed Thermistor Port'):
            state.save()
    elif getattr(args, 'thermistor_chamber', False):
        if not state.board_id:
            print(f"{Colors.RED}Error: No board selected.{Colors.NC}")
            sys.exit(1)
        # Offer mainboard thermistor ports for chamber sensor
        if select_flexible_port('thermistor', 'thermistor_chamber', 'Select Chamber Thermistor Port'):
            state.save()
    elif getattr(args, 'endstop_x', False):
        if not state.board_id:
            print(f"{Colors.RED}Error: No board selected.{Colors.NC}")
            sys.exit(1)
        # Offer BOTH mainboard and toolboard ports - user chooses
        if select_flexible_port('endstop', 'endstop_x', 'Select X Endstop Port'):
            state.save()
    elif getattr(args, 'endstop_y', False):
        if not state.board_id:
            print(f"{Colors.RED}Error: No board selected.{Colors.NC}")
            sys.exit(1)
        # Offer BOTH mainboard and toolboard ports - user chooses
        if select_flexible_port('endstop', 'endstop_y', 'Select Y Endstop Port'):
            state.save()
    elif getattr(args, 'endstop_z', False):
        if not state.board_id:
            print(f"{Colors.RED}Error: No board selected.{Colors.NC}")
            sys.exit(1)
        # Offer BOTH mainboard and toolboard ports - user chooses
        if select_flexible_port('endstop', 'endstop_z', 'Select Z Endstop Port'):
            state.save()
    elif getattr(args, 'probe_pin', False):
        if not state.board_id:
            print(f"{Colors.RED}Error: No board selected.{Colors.NC}")
            sys.exit(1)
        # Offer BOTH mainboard and toolboard ports - user chooses
        if select_flexible_port('endstop', 'probe_pin', 'Select Probe Pin',
                                supports_modifiers=True):
            state.save()
    elif args.fan:
        if not state.board_id:
            print(f"{Colors.RED}Error: No board selected.{Colors.NC}")
            sys.exit(1)
        # Offer BOTH mainboard and toolboard ports - user chooses
        fan_key = args.fan
        if select_flexible_port('fan', fan_key, f'Select Port for {fan_key}'):
            state.save()
    elif getattr(args, 'fan_multipin', None):
        if not state.board_id:
            print(f"{Colors.RED}Error: No board selected.{Colors.NC}")
            sys.exit(1)
        boards = load_available_boards()
        board = boards.get(state.board_id)
        fan_ports = board.get('fan_ports', {})
        fan_key = args.fan_multipin + '_pin2'
        if select_single_port('fan', fan_ports, fan_key, f'Select Secondary Pin for {args.fan_multipin}'):
            state.save()
    elif args.lighting:
        assign_lighting_port()
    elif getattr(args, 'clear_port', None):
        # Clear a port assignment from both mainboard and toolboard
        key = args.clear_port
        if key in state.port_assignments:
            del state.port_assignments[key]
        # Also check toolboard assignments with common prefixes
        tb_key = key.replace('fan_', 'fan_')  # fan_part_cooling -> fan_part_cooling
        if tb_key in state.toolboard_assignments:
            del state.toolboard_assignments[tb_key]
        state.save()
    else:
        main_menu()

if __name__ == '__main__':
    main()

