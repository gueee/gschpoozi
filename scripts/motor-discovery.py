#!/usr/bin/env python3
"""
Motor Discovery Wizard for gschpoozi
Interactively identifies motor-to-port mappings and verifies directions
using Moonraker API communication with a running Klipper instance.
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, List, Any

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

MOONRAKER_URL = "http://localhost:7125"
PRINTER_DATA = Path.home() / "printer_data"
DISCOVERY_CONFIG = PRINTER_DATA / "config" / "discovery.cfg"
RESULTS_FILE = PRINTER_DATA / "config" / ".motor_mapping.json"

# ANSI Colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
WHITE = "\033[97m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Box drawing characters
BOX_TL = "╔"
BOX_TR = "╗"
BOX_BL = "╚"
BOX_BR = "╝"
BOX_H = "═"
BOX_V = "║"


# ═══════════════════════════════════════════════════════════════════════════════
# MOONRAKER API
# ═══════════════════════════════════════════════════════════════════════════════

class MoonrakerAPI:
    """Simple Moonraker API client using urllib (no external dependencies)."""
    
    def __init__(self, base_url: str = MOONRAKER_URL):
        self.base_url = base_url.rstrip('/')
    
    def _request(self, endpoint: str, method: str = "GET", data: dict = None) -> dict:
        """Make HTTP request to Moonraker."""
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        
        if data:
            req_data = json.dumps(data).encode('utf-8')
        else:
            req_data = None
        
        request = urllib.request.Request(url, data=req_data, headers=headers, method=method)
        
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.URLError as e:
            raise ConnectionError(f"Failed to connect to Moonraker: {e}")
        except json.JSONDecodeError:
            return {}
    
    def get_printer_info(self) -> dict:
        """Get printer status info."""
        return self._request("/printer/info")
    
    def is_ready(self) -> bool:
        """Check if Klipper is ready to accept commands."""
        try:
            info = self.get_printer_info()
            state = info.get("result", {}).get("state", "")
            return state == "ready"
        except:
            return False
    
    def send_gcode(self, script: str) -> dict:
        """Send G-code command(s) to Klipper."""
        return self._request("/printer/gcode/script", "POST", {"script": script})
    
    def get_gcode_store(self, count: int = 50) -> List[dict]:
        """Get recent G-code responses from console."""
        result = self._request(f"/server/gcode_store?count={count}")
        return result.get("result", {}).get("gcode_store", [])
    
    def restart_klipper(self) -> dict:
        """Restart Klipper firmware."""
        return self._request("/printer/restart", "POST")
    
    def emergency_stop(self) -> dict:
        """Emergency stop."""
        return self._request("/printer/emergency_stop", "POST")


# ═══════════════════════════════════════════════════════════════════════════════
# UI HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def clear_screen():
    """Clear terminal screen."""
    os.system('clear' if os.name == 'posix' else 'cls')


def print_header(title: str):
    """Print a styled header."""
    width = 60
    print(f"\n{CYAN}{BOX_TL}{BOX_H * (width - 2)}{BOX_TR}{RESET}")
    print(f"{CYAN}{BOX_V}{RESET}  {BOLD}{WHITE}{title.center(width - 6)}{RESET}  {CYAN}{BOX_V}{RESET}")
    print(f"{CYAN}{BOX_BL}{BOX_H * (width - 2)}{BOX_BR}{RESET}\n")


def print_warning(message: str):
    """Print a warning message."""
    print(f"\n{YELLOW}⚠️  WARNING: {message}{RESET}\n")


def print_error(message: str):
    """Print an error message."""
    print(f"\n{RED}❌ ERROR: {message}{RESET}\n")


def print_success(message: str):
    """Print a success message."""
    print(f"\n{GREEN}✓ {message}{RESET}\n")


def print_info(message: str):
    """Print an info message."""
    print(f"{CYAN}ℹ {message}{RESET}")


def prompt_yes_no(question: str, default: bool = True) -> bool:
    """Prompt for yes/no answer."""
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        answer = input(f"{question} {suffix}: ").strip().lower()
        if answer == "":
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please answer 'y' or 'n'")


def prompt_choice(question: str, options: List[str], allow_skip: bool = True) -> Optional[int]:
    """Prompt user to choose from numbered options."""
    print(f"\n{WHITE}{question}{RESET}")
    for i, opt in enumerate(options, 1):
        print(f"  {CYAN}{i}){RESET} {opt}")
    if allow_skip:
        print(f"  {YELLOW}S){RESET} Skip / None of these")
    
    while True:
        choice = input(f"\n{YELLOW}Select option{RESET}: ").strip().lower()
        if allow_skip and choice == 's':
            return None
        try:
            idx = int(choice)
            if 1 <= idx <= len(options):
                return idx - 1
        except ValueError:
            pass
        print(f"Please enter 1-{len(options)}" + (" or 's' to skip" if allow_skip else ""))


def wait_for_key(message: str = "Press Enter to continue..."):
    """Wait for user to press Enter."""
    input(f"\n{message}")


# ═══════════════════════════════════════════════════════════════════════════════
# DISCOVERY CONFIG GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def load_board_config(board_id: str) -> dict:
    """Load board configuration from JSON file."""
    # Search in templates/boards/
    script_dir = Path(__file__).parent
    boards_dir = script_dir.parent / "templates" / "boards"
    
    # Try exact match first
    board_file = boards_dir / f"{board_id}.json"
    if board_file.exists():
        with open(board_file) as f:
            return json.load(f)
    
    # Try partial match
    for f in boards_dir.glob("*.json"):
        if board_id in f.stem:
            with open(f) as fh:
                return json.load(fh)
    
    raise FileNotFoundError(f"Board config not found: {board_id}")


def generate_discovery_config(board: dict, mcu_serial: str, driver_type: str = "TMC2209") -> str:
    """Generate a temporary printer.cfg for motor discovery.
    
    Note: We intentionally do NOT include TMC driver config here.
    Basic stepper movement works without TMC drivers, and including them
    causes errors for unconnected ports or misconfigured drivers.
    The discovery only needs to move motors - no need for stealthchop etc.
    """
    motor_ports = board.get("motor_ports", {})
    
    config_lines = [
        "# MOTOR DISCOVERY CONFIG",
        "# Generated by gschpoozi - TEMPORARY FILE",
        "# This config defines all motor ports for identification",
        "# Note: TMC drivers intentionally omitted for compatibility",
        "",
        "[mcu]",
        f"serial: {mcu_serial}",
        "",
        "[printer]",
        "kinematics: none",
        "max_velocity: 300",
        "max_accel: 3000",
        "",
        "[force_move]",
        "enable_force_move: True",
        "",
    ]
    
    # Generate a stepper section for each motor port
    # No TMC config - basic stepper movement works without it
    for port_name, port_config in motor_ports.items():
        stepper_name = f"stepper_{port_name.lower()}"
        
        config_lines.extend([
            f"[manual_stepper {stepper_name}]",
            f"step_pin: {port_config['step_pin']}",
            f"dir_pin: {port_config['dir_pin']}",
            f"enable_pin: !{port_config['enable_pin']}",
            "microsteps: 16",
            "rotation_distance: 40",
            "velocity: 50",
            "accel: 1000",
            "",
        ])
    
    return "\n".join(config_lines)


# ═══════════════════════════════════════════════════════════════════════════════
# MOTOR IDENTIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

class MotorDiscovery:
    """Interactive motor discovery wizard."""
    
    def __init__(self, api: MoonrakerAPI, board: dict, kinematics: str = "corexy", 
                 z_count: int = 1, has_toolboard: bool = False):
        self.api = api
        self.board = board
        self.kinematics = kinematics
        self.z_count = z_count
        self.has_toolboard = has_toolboard
        self.motor_ports = list(board.get("motor_ports", {}).keys())
        
        # Discovered mappings: stepper_name -> {"port": "MOTOR_X", "dir_invert": bool}
        self.mappings: Dict[str, Dict[str, Any]] = {}
        
        # Build list of steppers we need to identify
        self.required_steppers = self._build_required_steppers()
    
    def _build_required_steppers(self) -> List[dict]:
        """Build list of steppers that need identification."""
        steppers = []
        
        # Z motors
        z_positions = ["Front-Left", "Front-Right", "Rear-Left", "Rear-Right", "Rear", "Front"]
        for i in range(self.z_count):
            name = "stepper_z" if i == 0 else f"stepper_z{i}"
            pos = z_positions[i] if i < len(z_positions) else f"Z{i}"
            steppers.append({
                "name": name,
                "label": f"Z Motor ({pos})",
                "direction_prompt": "Did the bed move DOWN (or gantry move UP)?",
                "type": "z"
            })
        
        # Extruder (only if no toolboard)
        if not self.has_toolboard:
            steppers.append({
                "name": "extruder",
                "label": "Extruder Motor",
                "direction_prompt": "Did the extruder gear rotate toward hotend?",
                "type": "extruder",
                "warning": "REMOVE ALL FILAMENT before testing! Testing with filament loaded will skip steps or damage filament."
            })
        
        # XY motors
        if self.kinematics == "corexy-awd":
            # AWD: 4 XY motors
            steppers.extend([
                {"name": "stepper_x", "label": "CoreXY Motor A (typically rear-left)", 
                 "direction_prompt": "Did toolhead move diagonally toward FRONT-RIGHT?", "type": "xy"},
                {"name": "stepper_y", "label": "CoreXY Motor B (typically rear-right)", 
                 "direction_prompt": "Did toolhead move diagonally toward FRONT-LEFT?", "type": "xy"},
                {"name": "stepper_x1", "label": "CoreXY Motor A1 (AWD front-left)", 
                 "direction_prompt": "Did toolhead move diagonally toward FRONT-RIGHT?", "type": "xy"},
                {"name": "stepper_y1", "label": "CoreXY Motor B1 (AWD front-right)", 
                 "direction_prompt": "Did toolhead move diagonally toward FRONT-LEFT?", "type": "xy"},
            ])
        elif self.kinematics == "corexy":
            # Standard CoreXY: 2 XY motors
            steppers.extend([
                {"name": "stepper_x", "label": "CoreXY Motor A (rear-left)", 
                 "direction_prompt": "Did toolhead move diagonally toward FRONT-RIGHT?", "type": "xy"},
                {"name": "stepper_y", "label": "CoreXY Motor B (rear-right)", 
                 "direction_prompt": "Did toolhead move diagonally toward FRONT-LEFT?", "type": "xy"},
            ])
        else:
            # Cartesian
            steppers.extend([
                {"name": "stepper_x", "label": "X Motor", 
                 "direction_prompt": "Did toolhead move to the RIGHT?", "type": "xy"},
                {"name": "stepper_y", "label": "Y Motor", 
                 "direction_prompt": "Did bed/toolhead move AWAY from you?", "type": "xy"},
            ])
        
        return steppers
    
    def buzz_motor(self, port_name: str) -> bool:
        """Buzz a motor on the given port using MANUAL_STEPPER."""
        stepper_name = f"stepper_{port_name.lower()}"
        try:
            # Enable stepper
            self.api.send_gcode(f"MANUAL_STEPPER STEPPER={stepper_name} ENABLE=1")
            time.sleep(0.2)
            
            # Move back and forth (simulating STEPPER_BUZZ)
            for _ in range(5):
                self.api.send_gcode(f"MANUAL_STEPPER STEPPER={stepper_name} MOVE=1 SPEED=50")
                time.sleep(0.15)
                self.api.send_gcode(f"MANUAL_STEPPER STEPPER={stepper_name} MOVE=-1 SPEED=50")
                time.sleep(0.15)
            
            # Disable stepper
            self.api.send_gcode(f"MANUAL_STEPPER STEPPER={stepper_name} ENABLE=0")
            return True
        except Exception as e:
            print_error(f"Failed to buzz motor: {e}")
            return False
    
    def force_move_motor(self, port_name: str, distance: float = 10, velocity: float = 20) -> bool:
        """Move a motor in one direction using MANUAL_STEPPER."""
        stepper_name = f"stepper_{port_name.lower()}"
        try:
            self.api.send_gcode(f"MANUAL_STEPPER STEPPER={stepper_name} ENABLE=1")
            time.sleep(0.2)
            self.api.send_gcode(f"MANUAL_STEPPER STEPPER={stepper_name} MOVE={distance} SPEED={velocity}")
            time.sleep(abs(distance) / velocity + 0.5)
            # Move back
            self.api.send_gcode(f"MANUAL_STEPPER STEPPER={stepper_name} MOVE={-distance} SPEED={velocity}")
            time.sleep(abs(distance) / velocity + 0.5)
            self.api.send_gcode(f"MANUAL_STEPPER STEPPER={stepper_name} ENABLE=0")
            return True
        except Exception as e:
            print_error(f"Failed to move motor: {e}")
            return False
    
    def run_identification_phase(self) -> Dict[str, str]:
        """Phase 1: Identify which physical motor is on each port."""
        print_header("Phase 1: Motor Identification")
        
        print(f"""
{WHITE}We'll buzz each motor port one at a time.{RESET}
{WHITE}Watch which physical motor moves and tell us what it is.{RESET}

{CYAN}Available motor types to identify:{RESET}
""")
        
        # Show what we're looking for
        for s in self.required_steppers:
            print(f"  • {s['label']}")
        
        wait_for_key("\nReady? Press Enter to start buzzing motors...")
        
        port_to_stepper: Dict[str, str] = {}  # MOTOR_0 -> stepper_z
        identified = set()  # Already identified steppers
        
        for port_name in self.motor_ports:
            if len(identified) >= len(self.required_steppers):
                print_info("All required motors identified!")
                break
            
            clear_screen()
            print_header(f"Buzzing {port_name}")
            
            print(f"\n{YELLOW}👀 Watch your printer carefully!{RESET}")
            print(f"{WHITE}Motor on {CYAN}{port_name}{WHITE} will buzz in 3 seconds...{RESET}\n")
            
            for i in range(3, 0, -1):
                print(f"  {i}...")
                time.sleep(1)
            
            print(f"\n{GREEN}>>> BUZZING {port_name} NOW <<<{RESET}\n")
            
            if not self.buzz_motor(port_name):
                print(f"\n{YELLOW}Motor didn't respond. Options:{RESET}")
                print(f"  {CYAN}S){RESET} Skip this port, try next")
                print(f"  {CYAN}R){RESET} Retry this port")
                print(f"  {CYAN}A){RESET} Abort discovery")
                while True:
                    choice = input(f"\n{YELLOW}Choose [S/r/a]{RESET}: ").strip().lower()
                    if choice in ("", "s"):
                        break  # Skip to next port
                    elif choice == "r":
                        # Retry - continue with same port (don't break, let loop continue)
                        if self.buzz_motor(port_name):
                            break  # Success, proceed to identification
                        print_error("Still failed")
                    elif choice == "a":
                        print_info("Discovery aborted by user")
                        return {}  # Abort entire discovery
                    else:
                        print("Please enter 's', 'r', or 'a'")
                if choice in ("", "s"):
                    continue  # Skip to next port
            
            # Ask user which motor moved
            remaining = [s for s in self.required_steppers if s['name'] not in identified]
            options = [s['label'] for s in remaining]
            
            choice = prompt_choice(f"Which motor moved when {port_name} buzzed?", options)
            
            if choice is not None:
                stepper = remaining[choice]
                port_to_stepper[port_name] = stepper['name']
                identified.add(stepper['name'])
                print_success(f"{port_name} → {stepper['name']} ({stepper['label']})")
            else:
                print_info(f"Skipped {port_name}")
            
            wait_for_key()
        
        return port_to_stepper
    
    def run_direction_phase(self, port_to_stepper: Dict[str, str]) -> Dict[str, bool]:
        """Phase 2: Verify direction for each identified motor."""
        print_header("Phase 2: Direction Verification")
        
        print(f"""
{WHITE}Now we'll test the direction of each motor.{RESET}
{WHITE}Each motor will move in ONE direction - watch carefully!{RESET}
""")
        
        wait_for_key("Press Enter to start direction testing...")
        
        dir_invert: Dict[str, bool] = {}  # stepper_name -> needs_invert
        
        for port_name, stepper_name in port_to_stepper.items():
            stepper_info = next((s for s in self.required_steppers if s['name'] == stepper_name), None)
            if not stepper_info:
                continue
            
            clear_screen()
            print_header(f"Testing {stepper_info['label']}")
            
            # Special warning for extruder
            if stepper_info.get('warning'):
                print_warning(stepper_info['warning'])
                if not prompt_yes_no("Is filament removed? Continue with test?", default=False):
                    print_info("Skipping extruder direction test")
                    dir_invert[stepper_name] = False
                    continue
            
            print(f"\n{WHITE}Port: {CYAN}{port_name}{RESET}")
            print(f"{WHITE}Testing: {CYAN}{stepper_info['label']}{RESET}")
            print(f"\n{YELLOW}👀 Watch the motor carefully!{RESET}")
            print(f"{WHITE}Motor will move in 3 seconds...{RESET}\n")
            
            for i in range(3, 0, -1):
                print(f"  {i}...")
                time.sleep(1)
            
            # Determine move distance based on motor type
            if stepper_info['type'] == 'z':
                distance = 5
                velocity = 10
            elif stepper_info['type'] == 'extruder':
                distance = 20
                velocity = 5
            else:  # XY
                distance = 30
                velocity = 50
            
            print(f"\n{GREEN}>>> MOVING NOW <<<{RESET}\n")
            
            if not self.force_move_motor(port_name, distance, velocity):
                print_error("Motor movement failed")
                dir_invert[stepper_name] = False
                wait_for_key()
                continue
            
            # Ask about direction
            correct = prompt_yes_no(stepper_info['direction_prompt'])
            dir_invert[stepper_name] = not correct
            
            if correct:
                print_success(f"{stepper_name} direction is CORRECT")
            else:
                print_warning(f"{stepper_name} direction needs to be INVERTED")
            
            wait_for_key()
        
        return dir_invert
    
    def run(self) -> Dict[str, Dict[str, Any]]:
        """Run the full discovery wizard."""
        clear_screen()
        print_header("Motor Discovery Wizard")
        
        print(f"""
{WHITE}This wizard will help you:{RESET}
  1. Identify which physical motor is connected to which port
  2. Verify motor directions are correct

{YELLOW}SAFETY NOTES:{RESET}
  • Keep hands clear of moving parts
  • Have emergency stop ready (power switch)
  • For extruder: REMOVE FILAMENT before testing
  • Movements are small and slow for safety

{CYAN}Your Configuration:{RESET}
  Kinematics: {self.kinematics}
  Z Motors: {self.z_count}
  Motor Ports: {len(self.motor_ports)}
  Toolboard: {'Yes' if self.has_toolboard else 'No'}
""")
        
        if not prompt_yes_no("Ready to begin motor discovery?"):
            print_info("Discovery cancelled")
            return {}
        
        # Phase 1: Identification
        port_to_stepper = self.run_identification_phase()
        
        if not port_to_stepper:
            print_error("No motors were identified!")
            return {}
        
        # Phase 2: Direction verification
        dir_invert = self.run_direction_phase(port_to_stepper)
        
        # Build final mappings
        for port_name, stepper_name in port_to_stepper.items():
            self.mappings[stepper_name] = {
                "port": port_name,
                "dir_invert": dir_invert.get(stepper_name, False)
            }
        
        # Show summary
        clear_screen()
        print_header("Discovery Complete!")
        
        print(f"{WHITE}Motor Mappings:{RESET}\n")
        for stepper_name, mapping in self.mappings.items():
            invert_str = f" {YELLOW}(INVERT){RESET}" if mapping['dir_invert'] else ""
            print(f"  {CYAN}{stepper_name}{RESET} → {mapping['port']}{invert_str}")
        
        return self.mappings


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Motor Discovery Wizard")
    parser.add_argument("--board", required=True, help="Board ID (e.g., btt-manta-m8p-v2)")
    parser.add_argument("--mcu-serial", required=True, help="MCU serial path")
    parser.add_argument("--driver", default="TMC2209", help="Driver type (default: TMC2209)")
    parser.add_argument("--kinematics", default="corexy", help="Kinematics type")
    parser.add_argument("--z-count", type=int, default=1, help="Number of Z motors")
    parser.add_argument("--has-toolboard", action="store_true", help="Has toolboard (extruder not on main board)")
    parser.add_argument("--moonraker-url", default=MOONRAKER_URL, help="Moonraker URL")
    parser.add_argument("--output", default=str(RESULTS_FILE), help="Output file for results")
    args = parser.parse_args()
    
    # Initialize API
    api = MoonrakerAPI(args.moonraker_url)
    
    # Load board config
    try:
        board = load_board_config(args.board)
    except FileNotFoundError as e:
        print_error(str(e))
        sys.exit(1)
    
    print_info(f"Loaded board config: {board.get('name', args.board)}")
    
    # Check Klipper/Moonraker status
    print_info("Checking Klipper/Moonraker connection...")
    
    try:
        info = api.get_printer_info()
        state = info.get("result", {}).get("state", "unknown")
        print_info(f"Klipper state: {state}")
    except ConnectionError as e:
        print_error(f"Cannot connect to Moonraker at {args.moonraker_url}")
        print_info("Make sure Klipper and Moonraker are running")
        sys.exit(1)
    
    # Generate and write discovery config
    print_info("Generating discovery configuration...")
    config_content = generate_discovery_config(board, args.mcu_serial, args.driver)
    
    # Backup existing config if present
    printer_cfg = PRINTER_DATA / "config" / "printer.cfg"
    backup_cfg = PRINTER_DATA / "config" / "printer.cfg.discovery_backup"
    
    if printer_cfg.exists():
        print_info("Backing up existing printer.cfg...")
        import shutil
        shutil.copy(printer_cfg, backup_cfg)
    
    # Write discovery config
    with open(printer_cfg, 'w') as f:
        f.write(config_content)
    print_success("Discovery config written")
    
    # Restart Klipper to load new config
    print_info("Restarting Klipper with discovery config...")
    try:
        api.restart_klipper()
        time.sleep(3)
        
        # Wait for Klipper to be ready
        for _ in range(30):
            if api.is_ready():
                break
            time.sleep(1)
        else:
            print_error("Klipper did not become ready after restart")
            # Restore backup
            if backup_cfg.exists():
                import shutil
                shutil.copy(backup_cfg, printer_cfg)
            sys.exit(1)
    except Exception as e:
        print_error(f"Failed to restart Klipper: {e}")
        sys.exit(1)
    
    print_success("Klipper ready with discovery config")
    
    # Run discovery wizard
    try:
        discovery = MotorDiscovery(
            api=api,
            board=board,
            kinematics=args.kinematics,
            z_count=args.z_count,
            has_toolboard=args.has_toolboard
        )
        mappings = discovery.run()
        
        if mappings:
            # Save results
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump({"motor_mapping": mappings}, f, indent=2)
            print_success(f"Results saved to {output_path}")
        
    finally:
        # Restore original config
        if backup_cfg.exists():
            print_info("Restoring original printer.cfg...")
            import shutil
            shutil.copy(backup_cfg, printer_cfg)
            backup_cfg.unlink()
            
            # Restart Klipper with original config
            print_info("Restarting Klipper with original config...")
            try:
                api.restart_klipper()
            except:
                pass
    
    print_success("Motor discovery complete!")
    
    if mappings:
        print(f"\n{WHITE}To apply these mappings, run the configuration wizard.{RESET}")


if __name__ == "__main__":
    main()

