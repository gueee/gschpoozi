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
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

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
        
    def save(self, filepath: Path = STATE_FILE):
        """Save state to JSON file."""
        data = {
            'board_id': self.board_id,
            'board_name': self.board_name,
            'toolboard_id': self.toolboard_id,
            'toolboard_name': self.toolboard_name,
            'port_assignments': self.port_assignments,
            'toolboard_assignments': self.toolboard_assignments,
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

def assign_fan_ports(board: Dict):
    """Assign fan ports."""
    fan_ports = board.get('fan_ports', {})
    
    clear_screen()
    print_header("Assign Fan Ports")
    
    fan_list = list(fan_ports.keys())
    
    # Part cooling fan (only if no toolboard)
    if state.toolboard_id in (None, "none", ""):
        print_info(f"{Colors.BWHITE}Part Cooling Fan:{Colors.NC}")
        num = 1
        for port_name in fan_list:
            port = fan_ports[port_name]
            current = "done" if state.port_assignments.get('fan_part_cooling') == port_name else ""
            print_menu_item(str(num), f"{port_name} - {port['label']}", "", current)
            num += 1
        
        choice = prompt("Select fan port for part cooling").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(fan_list):
                state.port_assignments['fan_part_cooling'] = fan_list[idx]
        except ValueError:
            pass
        
        # Hotend fan
        print_info("")
        print_info(f"{Colors.BWHITE}Hotend Fan:{Colors.NC}")
        num = 1
        for port_name in fan_list:
            port = fan_ports[port_name]
            current = "done" if state.port_assignments.get('fan_hotend') == port_name else ""
            print_menu_item(str(num), f"{port_name} - {port['label']}", "", current)
            num += 1
        
        choice = prompt("Select fan port for hotend fan").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(fan_list):
                state.port_assignments['fan_hotend'] = fan_list[idx]
        except ValueError:
            pass
    
    # Controller fan (always on main board)
    print_info("")
    print_info(f"{Colors.BWHITE}Controller/Electronics Fan:{Colors.NC}")
    num = 1
    for port_name in fan_list:
        port = fan_ports[port_name]
        current = "done" if state.port_assignments.get('fan_controller') == port_name else ""
        print_menu_item(str(num), f"{port_name} - {port['label']}", "", current)
        num += 1
    print_menu_item(str(num), "Skip (no controller fan)", "", "")
    
    choice = prompt("Select fan port for controller fan").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(fan_list):
            state.port_assignments['fan_controller'] = fan_list[idx]
    except ValueError:
        pass
    
    wait_for_key()

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
            
            heater_info = "bed"
            if not has_toolboard:
                heater_info += " + hotend"
            print_menu_item("4", "Heater & Thermistor Ports", heater_info, heaters_status)
            
            fan_info = "controller"
            if not has_toolboard:
                fan_info += " + part cooling + hotend"
            print_menu_item("5", "Fan Ports", fan_info, fans_status)
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
                assign_heater_ports(board)
        elif choice == '5' and state.board_id:
            board = boards.get(state.board_id)
            if board:
                assign_fan_ports(board)
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
    else:
        main_menu()

if __name__ == '__main__':
    main()

