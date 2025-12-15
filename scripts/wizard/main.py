#!/usr/bin/env python3
"""
main.py - gschpoozi Configuration Wizard Entry Point

This is the main entry point for the Klipper configuration wizard.
Run with: python3 scripts/wizard/main.py
"""

import sys
import os
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from wizard.ui import WizardUI
from wizard.state import get_state, WizardState

# Find repo root (where templates/ lives)
SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_ROOT = SCRIPT_DIR.parent.parent  # scripts/wizard -> scripts -> repo root


class GschpooziWizard:
    """Main wizard controller."""

    VERSION = "2.0.0"

    def __init__(self):
        self.ui = WizardUI(
            title="gschpoozi",
            backtitle=f"gschpoozi v{self.VERSION} - Klipper Configuration Wizard"
        )
        self.state = get_state()

    def _format_serial_name(self, full_path: str) -> str:
        """Format a serial device path for display.

        Extracts meaningful info from paths like:
        /dev/serial/by-id/usb-Klipper_stm32h723xx_240041000451323336333538-if00
        → "Klipper stm32h723xx (...3538)"
        """
        name = Path(full_path).name

        # Remove common prefixes
        if name.startswith("usb-"):
            name = name[4:]

        # Remove -if00 suffix
        if name.endswith("-if00"):
            name = name[:-5]

        # Parse Klipper format: Klipper_mcu_serialnumber
        if name.startswith("Klipper_"):
            parts = name.split("_", 2)
            if len(parts) >= 3:
                mcu = parts[1]
                serial = parts[2]
                # Show last 4 chars of serial
                short_serial = serial[-4:] if len(serial) > 4 else serial
                return f"Klipper {mcu} (...{short_serial})"
            elif len(parts) == 2:
                return f"Klipper {parts[1]}"

        # Parse Beacon format: Beacon_Beacon_RevH_SERIAL
        if "Beacon" in name:
            parts = name.split("_")
            if len(parts) >= 3:
                rev = parts[2] if len(parts) > 2 else ""
                serial = parts[-1] if len(parts) > 3 else ""
                short_serial = serial[-4:] if len(serial) > 4 else serial
                return f"Beacon {rev} (...{short_serial})"
            return "Beacon"

        # Parse Cartographer format
        if "Cartographer" in name or "cartographer" in name:
            return "Cartographer"

        # Generic: truncate if too long
        if len(name) > 40:
            return name[:20] + "..." + name[-10:]

        return name

    def _load_board_data(self, board_id: str, board_type: str = "boards") -> dict:
        """Load full board JSON data.

        Args:
            board_id: Board ID (e.g., "btt-octopus-v1.1")
            board_type: "boards" or "toolboards"

        Returns:
            Full board dictionary or empty dict if not found
        """
        if not board_id or board_id == "other":
            return {}

        boards_dir = REPO_ROOT / "templates" / board_type
        json_file = boards_dir / f"{board_id}.json"

        if json_file.exists():
            try:
                with open(json_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        return {}

    def _get_board_ports(self, port_type: str, board_type: str = "boards",
                         default_port: str = None) -> list:
        """Get available ports from currently selected board.

        Args:
            port_type: "heater_ports", "thermistor_ports", "fan_ports",
                       "motor_ports", "endstop_ports"
            board_type: "boards" or "toolboards"
            default_port: Port ID to mark as default selection

        Returns:
            List of (port_id, label, is_default) tuples for radiolist
        """
        # Get the board ID from state
        if board_type == "boards":
            board_id = self.state.get("mcu.main.board_type", "")
        else:
            board_id = self.state.get("mcu.toolboard.board_type", "")

        board_data = self._load_board_data(board_id, board_type)
        ports = board_data.get(port_type, {})

        if not ports:
            return []

        result = []
        for port_id, port_info in ports.items():
            if isinstance(port_info, dict):
                label = port_info.get("label", port_id)
                # Include pin info if available
                pin = port_info.get("pin", port_info.get("signal_pin", ""))
                if pin:
                    label = f"{label} ({pin})"
            else:
                label = port_id

            is_default = (port_id == default_port)
            result.append((port_id, label, is_default))

        # Sort by port ID for consistent ordering
        result.sort(key=lambda x: x[0])

        # If no default was set, mark the first one as default
        if result and not any(x[2] for x in result):
            result[0] = (result[0][0], result[0][1], True)

        return result

    def _copy_stepper_settings(self, from_axis: str, to_axis: str) -> None:
        """Copy common stepper settings from one axis to another.

        Inheritance rules per schema:
        - Y from X: Copies all driver and mechanical settings (CoreXY same motors)
        - X1 from X: Only copies driver settings (templates use defaults for mechanical)
        - Y1 from Y: Only copies driver settings (templates use defaults for mechanical)

        Args:
            from_axis: Source axis (e.g., "x", "y")
            to_axis: Target axis (e.g., "y", "x1", "y1")
        """
        is_secondary = to_axis in ("x1", "y1")

        # Driver settings (always copied)
        driver_settings = [
            "driver_type",
            "driver_protocol",
            "run_current",
            "sense_resistor",
            "interpolate",
            # TMC5160-specific settings
            "driver_tbl",
            "driver_toff",
            "driver_diss2g",
            "driver_diss2vs",
        ]

        # Mechanical settings (only copied for primary axes like Y from X)
        mechanical_settings = [
            "belt_pitch",
            "pulley_teeth",
            "microsteps",
            "full_steps_per_rotation",
        ]

        # For secondary axes (X1, Y1), templates handle mechanical inheritance via defaults
        # So we only copy driver settings
        if is_secondary:
            settings_to_copy = driver_settings
        else:
            # For primary axes (Y from X), copy everything
            settings_to_copy = driver_settings + mechanical_settings

        from_key = f"stepper_{from_axis}"
        to_key = f"stepper_{to_axis}"

        for setting in settings_to_copy:
            value = self.state.get(f"{from_key}.{setting}")
            if value is not None:
                self.state.set(f"{to_key}.{setting}", value)

    def run(self) -> int:
        """Run the wizard. Returns exit code."""
        try:
            self.main_menu()
            return 0
        except KeyboardInterrupt:
            return 130
        except Exception as e:
            self.ui.msgbox(f"Error: {e}", title="Error")
            return 1

    def main_menu(self) -> None:
        """Display the main menu."""
        while True:
            status = self._get_status_text()

            choice = self.ui.menu(
                f"Welcome to gschpoozi!\n\n{status}\n\nSelect a category:",
                [
                    ("1", "Klipper Setup         (Installation & verification)"),
                    ("2", "Hardware Setup        (Configure your printer)"),
                    ("3", "Tuning & Optimization (Macros, input shaper, etc.)"),
                    ("G", "Generate Config       (Create printer.cfg)"),
                    ("Q", "Quit"),
                ],
                height=40,
                width=120,
            )

            if choice is None or choice == "Q":
                if self.ui.yesno("Are you sure you want to exit?", default_no=True):
                    break
            elif choice == "1":
                self.klipper_setup_menu()
            elif choice == "2":
                self.hardware_setup_menu()
            elif choice == "3":
                self.tuning_menu()
            elif choice == "G":
                self.generate_config()

    def _get_status_text(self) -> str:
        """Get status text showing configuration progress."""
        completion = self.state.get_completion_status()

        done = sum(1 for v in completion.values() if v)
        total = len(completion)

        if done == 0:
            return "Status: Not started"
        elif done == total:
            return "Status: Configuration complete! Ready to generate."
        else:
            items = [k for k, v in completion.items() if v]
            return f"Status: {done}/{total} sections configured ({', '.join(items)})"

    def _format_menu_item(self, base_label: str, status_info: str = None) -> str:
        """Format a menu item with checkmark and status info.

        Args:
            base_label: Base menu label (e.g., "Main Board")
            status_info: Optional status info to append (e.g., "BTT Octopus v1.1")

        Returns:
            Formatted label with checkmark if configured, status info if provided
        """
        if status_info:
            # Truncate long status info to keep menu readable
            max_status_len = 30
            if len(status_info) > max_status_len:
                status_info = status_info[:max_status_len-3] + "..."
            return f"✓ {base_label:<25} ({status_info})"
        else:
            return base_label

    # -------------------------------------------------------------------------
    # Category 1: Klipper Setup
    # -------------------------------------------------------------------------

    def klipper_setup_menu(self) -> None:
        """Klipper installation and verification menu."""
        while True:
            choice = self.ui.menu(
                "Klipper Setup - Installation & Verification\n\n"
                "These options help verify your Klipper installation.",
                [
                    ("1.1", "Check Klipper         (Verify installation)"),
                    ("1.2", "Check Moonraker       (Verify API)"),
                    ("1.3", "Web Interface         (Mainsail/Fluidd)"),
                    ("1.4", "Optional Services     (Crowsnest, KlipperScreen)"),
                    ("B", "Back to Main Menu"),
                ],
                title="1. Klipper Setup",
            )

            if choice is None or choice == "B":
                break
            elif choice == "1.1":
                self._check_klipper()
            elif choice == "1.2":
                self._check_moonraker()
            elif choice == "1.3":
                self._web_interface_menu()
            elif choice == "1.4":
                self._optional_services_menu()

    def _check_klipper(self) -> None:
        """Check Klipper installation status."""
        # TODO: Actually check Klipper status
        klipper_path = Path.home() / "klipper"
        klippy_env = Path.home() / "klippy-env"

        status_lines = []

        if klipper_path.exists():
            status_lines.append("✓ Klipper directory found")
        else:
            status_lines.append("✗ Klipper directory NOT found")

        if klippy_env.exists():
            status_lines.append("✓ Klippy virtual environment found")
        else:
            status_lines.append("✗ Klippy virtual environment NOT found")

        # Check service
        import subprocess
        result = subprocess.run(
            ["systemctl", "is-active", "klipper"],
            capture_output=True, text=True
        )
        if result.stdout.strip() == "active":
            status_lines.append("✓ Klipper service is running")
        else:
            status_lines.append("✗ Klipper service is NOT running")

        self.ui.msgbox(
            "Klipper Installation Status:\n\n" + "\n".join(status_lines),
            title="Klipper Check"
        )

    def _check_moonraker(self) -> None:
        """Check Moonraker installation status."""
        moonraker_path = Path.home() / "moonraker"

        status_lines = []

        if moonraker_path.exists():
            status_lines.append("✓ Moonraker directory found")
        else:
            status_lines.append("✗ Moonraker directory NOT found")

        # Check service
        import subprocess
        result = subprocess.run(
            ["systemctl", "is-active", "moonraker"],
            capture_output=True, text=True
        )
        if result.stdout.strip() == "active":
            status_lines.append("✓ Moonraker service is running")
        else:
            status_lines.append("✗ Moonraker service is NOT running")

        self.ui.msgbox(
            "Moonraker Installation Status:\n\n" + "\n".join(status_lines),
            title="Moonraker Check"
        )

    def _web_interface_menu(self) -> None:
        """Web interface selection."""
        self.ui.msgbox(
            "Web Interface Setup\n\n"
            "This section will help you install/verify Mainsail or Fluidd.\n\n"
            "(Coming soon - use KIAUH for now)",
            title="1.3 Web Interface"
        )

    def _optional_services_menu(self) -> None:
        """Optional services menu."""
        self.ui.msgbox(
            "Optional Services\n\n"
            "• Crowsnest - Camera streaming\n"
            "• KlipperScreen - Touch screen interface\n"
            "• Timelapse - Print timelapses\n"
            "• Sonar - Network keepalive\n\n"
            "(Coming soon - use KIAUH for now)",
            title="1.4 Optional Services"
        )

    # -------------------------------------------------------------------------
    # Category 2: Hardware Setup
    # -------------------------------------------------------------------------

    def hardware_setup_menu(self) -> None:
        """Hardware configuration menu."""
        while True:
            # Build menu items dynamically based on config
            awd_enabled = self.state.get("printer.awd_enabled", False)

            # Get status info for each section
            # MCU Configuration
            main_board_id = self.state.get("mcu.main.board_type", "")
            main_board_name = self._get_board_name(main_board_id, "boards") if main_board_id else None
            toolboard_id = self.state.get("mcu.toolboard.board_type", "")
            toolboard_name = self._get_board_name(toolboard_id, "toolboards") if toolboard_id else None
            mcu_status = None
            if main_board_name:
                mcu_status = main_board_name
                if toolboard_name:
                    mcu_status += f", {toolboard_name}"

            # Printer Settings
            kinematics = self.state.get("printer.kinematics", "")
            printer_status = None
            if kinematics:
                printer_status = kinematics.capitalize()
                if awd_enabled:
                    printer_status += " - AWD"

            # Stepper status helper
            def get_stepper_status(axis):
                driver = self.state.get(f"stepper_{axis}.driver_type", "")
                if driver:
                    return driver
                return None

            # X Axis
            x_status = get_stepper_status("x")

            # Y Axis
            y_status = get_stepper_status("y")

            # X1 Axis
            x1_status = get_stepper_status("x1") if awd_enabled else None

            # Y1 Axis
            y1_status = get_stepper_status("y1") if awd_enabled else None

            # Z Axis
            z_count = self.state.get("stepper_z.z_motor_count", None)
            z_status = None
            if z_count:
                z_status = f"{z_count} motors"

            # Extruder
            extruder_type = self.state.get("extruder.extruder_type", "")
            nozzle = self.state.get("extruder.nozzle_diameter", None)
            extruder_status = None
            if extruder_type:
                extruder_status = extruder_type.replace("_", " ").title()
                if nozzle:
                    extruder_status += f", {nozzle}mm"

            # Heated Bed
            bed_sensor = self.state.get("heater_bed.sensor_type", "")
            bed_status = bed_sensor if bed_sensor else None

            # Fans
            part_loc = self.state.get("fans.part_cooling.location", "")
            hotend_loc = self.state.get("fans.hotend.location", "")
            controller_enabled = self.state.get("fans.controller.enabled", False)
            fans_status = None
            if part_loc or hotend_loc or controller_enabled:
                parts = []
                if part_loc:
                    parts.append(f"Part:{part_loc[:2]}")
                if hotend_loc:
                    parts.append(f"Hotend:{hotend_loc[:2]}")
                if controller_enabled:
                    parts.append("Ctrl")
                fans_status = ", ".join(parts)

            menu_items = [
                ("2.1", self._format_menu_item("MCU Configuration", mcu_status) if mcu_status else "MCU Configuration     (Boards & connections)"),
                ("2.2", self._format_menu_item("Printer Settings", printer_status) if printer_status else "Printer Settings      (Kinematics & limits)"),
                ("2.3", self._format_menu_item("X Axis", x_status) if x_status else "X Axis                (Stepper & driver)"),
            ]

            # Show AWD X1 option if AWD enabled
            if awd_enabled:
                menu_items.append(("2.3.1", self._format_menu_item("X1 Axis (AWD)", x1_status) if x1_status else "X1 Axis (AWD)        (Secondary X stepper)"))

            menu_items.append(("2.4", self._format_menu_item("Y Axis", y_status) if y_status else "Y Axis                (Stepper & driver)"))

            # Show AWD Y1 option if AWD enabled
            if awd_enabled:
                menu_items.append(("2.4.1", self._format_menu_item("Y1 Axis (AWD)", y1_status) if y1_status else "Y1 Axis (AWD)        (Secondary Y stepper)"))

            menu_items.extend([
                ("2.5", self._format_menu_item("Z Axis", z_status) if z_status else "Z Axis                (Stepper(s) & driver(s))"),
                ("2.6", self._format_menu_item("Extruder", extruder_status) if extruder_status else "Extruder              (Motor & hotend)"),
                ("2.7", self._format_menu_item("Heated Bed", bed_status) if bed_status else "Heated Bed            (Heater & thermistor)"),
                ("2.8", self._format_menu_item("Fans", fans_status) if fans_status else "Fans                  (Part cooling, hotend, etc.)"),
                ("2.9", "Probe                 (BLTouch, Beacon, etc.)"),
                ("2.10", "Homing               (Safe Z home, sensorless)"),
                ("2.11", "Bed Leveling         (Mesh, Z tilt, QGL)"),
                ("2.12", "Temperature Sensors  (MCU, chamber, etc.)"),
                ("2.13", "LEDs                 (Neopixel, case light)"),
                ("2.14", "Filament Sensors     (Runout detection)"),
                ("2.15", "Display              (LCD, OLED)"),
                ("2.16", "Advanced             (Servo, buttons, etc.)"),
                ("B", "Back to Main Menu"),
            ])

            choice = self.ui.menu(
                "Hardware Setup - Configure Your Printer\n\n"
                "Work through these sections to configure your hardware.",
                menu_items,
                title="2. Hardware Setup",
                height=40,
                width=120,
            )

            if choice is None or choice == "B":
                break
            elif choice == "2.1":
                self._mcu_setup()
            elif choice == "2.2":
                self._printer_settings()
            elif choice == "2.3":
                self._stepper_axis("x")
            elif choice == "2.3.1":
                self._stepper_axis("x1")
            elif choice == "2.4":
                self._stepper_axis("y")
            elif choice == "2.4.1":
                self._stepper_axis("y1")
            elif choice == "2.5":
                self._stepper_z()
            elif choice == "2.6":
                self._extruder_setup()
            elif choice == "2.7":
                self._heater_bed_setup()
            elif choice == "2.8":
                self._fans_setup()
            elif choice == "2.9":
                self._probe_setup()
            elif choice == "2.10":
                self._homing_setup()
            elif choice == "2.11":
                self._bed_leveling_setup()
            elif choice == "2.12":
                self._temperature_sensors_setup()
            elif choice == "2.13":
                self._leds_setup()
            elif choice == "2.14":
                self._filament_sensors_setup()
            else:
                # Placeholder for remaining sections (2.15-2.16)
                self.ui.msgbox(
                    f"Section {choice} coming soon!\n\n"
                    "Optional hardware - implement as needed.",
                    title=f"Section {choice}"
                )

    def _mcu_setup(self) -> None:
        """MCU configuration wizard."""
        while True:
            # Get current configuration status
            main_board_id = self.state.get("mcu.main.board_type", "")
            main_board_name = self._get_board_name(main_board_id, "boards") if main_board_id else None

            toolboard_id = self.state.get("mcu.toolboard.board_type", "")
            toolboard_conn = self.state.get("mcu.toolboard.connection_type", "")
            toolboard_name = None
            if toolboard_id:
                toolboard_name = self._get_board_name(toolboard_id, "toolboards")
                if toolboard_conn:
                    toolboard_name = f"{toolboard_name} - {toolboard_conn}"

            host_enabled = self.state.get("mcu.host.enabled", False)

            # Format menu items with status
            menu_items = [
                ("2.1.1", self._format_menu_item("Main Board", main_board_name) if main_board_name else "Main Board            (Required)"),
                ("2.1.2", self._format_menu_item("Toolhead Board", toolboard_name) if toolboard_name else "Toolhead Board        (Optional)"),
                ("2.1.3", self._format_menu_item("Host MCU", "Enabled" if host_enabled else None) if host_enabled else "Host MCU              (For ADXL, GPIO)"),
                ("2.1.4", "Additional MCUs       (Multi-board setups)"),
                ("B", "Back"),
            ]

            choice = self.ui.menu(
                "MCU Configuration\n\n"
                "Configure your printer's control boards.",
                menu_items,
                title="2.1 MCU Configuration",
            )

            if choice is None or choice == "B":
                break
            elif choice == "2.1.1":
                self._configure_main_board()
            elif choice == "2.1.2":
                self._configure_toolboard()
            elif choice == "2.1.3":
                self._configure_host_mcu()
            else:
                self.ui.msgbox("Coming soon!", title=choice)

    def _load_boards(self, board_type: str = "boards") -> list:
        """Load board definitions from templates directory.

        Args:
            board_type: "boards" for mainboards, "toolboards" for toolboards

        Returns:
            List of (id, name) tuples
        """
        boards_dir = REPO_ROOT / "templates" / board_type
        boards = []

        if boards_dir.exists():
            for json_file in sorted(boards_dir.glob("*.json")):
                try:
                    with open(json_file) as f:
                        data = json.load(f)
                        board_id = data.get("id", json_file.stem)
                        board_name = data.get("name", json_file.stem)
                        boards.append((board_id, board_name))
                except (json.JSONDecodeError, KeyError):
                    # Skip invalid files
                    continue

        # Always add manual option at the end
        boards.append(("other", "Other / Manual"))
        return boards

    def _get_board_name(self, board_id: str, board_type: str = "boards") -> str:
        """Get board display name from board ID.

        Args:
            board_id: Board ID (e.g., "btt-octopus-v1.1")
            board_type: "boards" or "toolboards"

        Returns:
            Board name or "Other" if not found
        """
        if not board_id or board_id == "other":
            return "Other"

        board_data = self._load_board_data(board_id, board_type)
        return board_data.get("name", board_id)

    def _configure_main_board(self) -> None:
        """Configure main board."""
        # Load boards dynamically from templates/boards/
        boards = self._load_boards("boards")

        if len(boards) <= 1:
            self.ui.msgbox(
                "No board definitions found in templates/boards/\n\n"
                "Please ensure the gschpoozi repository is complete.",
                title="Error"
            )
            return

        current = self.state.get("mcu.main.board_type", "")

        board = self.ui.radiolist(
            f"Select your main control board ({len(boards)-1} boards available):",
            [(b, d, b == current) for b, d in boards],
            title="Main Board Selection",
            height=45,
            width=120,
            list_height=35,
        )

        if board is None:
            return

        # Serial detection (placeholder)
        self.ui.infobox("Scanning for connected MCUs...", title="Detecting")

        import subprocess
        import time
        time.sleep(1)  # Simulated scan

        # Try to find serial devices
        serial_path = ""
        serial_dir = Path("/dev/serial/by-id")
        if serial_dir.exists():
            devices = list(serial_dir.iterdir())
            if devices:
                # Build mapping: short_name -> full_path
                serial_map = {}
                device_items = []
                for i, d in enumerate(devices):
                    short_name = self._format_serial_name(str(d))
                    # Use index prefix to ensure uniqueness
                    tag = f"{i+1}. {short_name}"
                    serial_map[tag] = str(d)
                    device_items.append((tag, "", False))

                device_items.append(("manual", "Enter path manually", False))

                selected = self.ui.radiolist(
                    "Select the serial device for your main board:\n\n"
                    "(Full paths will be saved to config)",
                    device_items,
                    title="Main Board - Serial",
                )

                if selected == "manual":
                    serial_path = self.ui.inputbox(
                        "Enter the serial path:",
                        default="/dev/serial/by-id/usb-Klipper_"
                    )
                elif selected and selected in serial_map:
                    serial_path = serial_map[selected]
        else:
            serial_path = self.ui.inputbox(
                "No devices found. Enter serial path manually:",
                default="/dev/serial/by-id/usb-Klipper_"
            )

        if serial_path:
            # Save configuration
            self.state.set("mcu.main.board_type", board)
            self.state.set("mcu.main.serial", serial_path)
            self.state.set("mcu.main.connection_type", "USB")
            self.state.save()

            self.ui.msgbox(
                f"Main board configured!\n\n"
                f"Board: {board}\n"
                f"Serial: {serial_path}",
                title="Success"
            )

    def _configure_toolboard(self) -> None:
        """Configure toolhead board."""
        if not self.ui.yesno(
            "Do you have a toolhead board?\n\n"
            "(CAN or USB connected board on the toolhead)",
            title="Toolhead Board"
        ):
            self.state.delete("mcu.toolboard")
            self.state.save()
            return

        # Select toolboard type first
        toolboards = self._load_boards("toolboards")
        if len(toolboards) > 1:
            current = self.state.get("mcu.toolboard.board_type", "")
            board = self.ui.radiolist(
                f"Select your toolhead board ({len(toolboards)-1} boards available):",
                [(b, d, b == current) for b, d in toolboards],
                title="Toolhead Board Selection",
                height=45,
                width=120,
                list_height=35,
            )
            if board is None:
                return
            self.state.set("mcu.toolboard.board_type", board)
            self.state.set("mcu.toolboard.enabled", True)

        # Connection type - preselect based on saved value
        # Explicitly get and validate the saved connection type
        current_conn_type = self.state.get("mcu.toolboard.connection_type", "")

        # Validate: only accept "USB" or "CAN", default to USB if invalid/empty
        if current_conn_type not in ("USB", "CAN"):
            current_conn_type = "USB"  # Default to USB if not set or invalid

        # Mutually exclusive preselection: only one can be True
        default_is_usb = (current_conn_type == "USB")
        default_is_can = (current_conn_type == "CAN")

        # Safety check: ensure at least one is preselected (should always be True after validation above)
        if not default_is_usb and not default_is_can:
            # Fallback: default to USB if somehow both are False
            default_is_usb = True

        conn_type = self.ui.radiolist(
            "How is your toolhead board connected?",
            [
                ("USB", "USB (direct connection)", default_is_usb),
                ("CAN", "CAN bus", default_is_can),
            ],
            title="Connection Type",
        )

        if conn_type is None:
            return

        # Validate conn_type is one of the expected values
        if conn_type not in ("USB", "CAN"):
            self.ui.msgbox(f"Invalid connection type: {conn_type}", title="Error")
            return

        # Save connection type immediately and clear incompatible fields
        # This ensures connection_type is persisted even if user cancels serial/UUID entry
        if conn_type == "CAN":
            self.state.set("mcu.toolboard.connection_type", "CAN")
            # Clear USB-specific fields to prevent stale data
            self.state.delete("mcu.toolboard.serial")
        else:  # USB
            self.state.set("mcu.toolboard.connection_type", "USB")
            # Clear CAN-specific fields to prevent stale data
            self.state.delete("mcu.toolboard.canbus_uuid")
            self.state.delete("mcu.toolboard.canbus_bitrate")

        # Save immediately to ensure persistence
        self.state.save()

        if conn_type == "CAN":
            self.ui.msgbox(
                "CAN Bus Setup\n\n"
                "CAN bus requires additional setup:\n"
                "1. CAN adapter or USB-CAN bridge\n"
                "2. Network interface configuration\n"
                "3. Toolboard UUID detection\n\n"
                "Reference: canbus.esoterical.online",
                title="CAN Bus Info"
            )

            # Bitrate selection - load saved value
            current_bitrate = self.state.get("mcu.toolboard.canbus_bitrate", 1000000)
            bitrate = self.ui.radiolist(
                "Select CAN bus bitrate:",
                [
                    ("1000000", "1Mbit/s (recommended)", current_bitrate == 1000000),
                    ("500000", "500Kbit/s", current_bitrate == 500000),
                    ("250000", "250Kbit/s (rare)", current_bitrate == 250000),
                ],
                title="CAN Bitrate"
            )

            # UUID input - load saved value as default
            current_uuid = self.state.get("mcu.toolboard.canbus_uuid", "")
            uuid = self.ui.inputbox(
                "Enter toolboard CAN UUID:\n\n"
                "(Run: ~/klippy-env/bin/python ~/klipper/scripts/canbus_query.py can0)",
                default=current_uuid
            )

            if uuid:
                # connection_type already saved above
                self.state.set("mcu.toolboard.canbus_uuid", uuid)
                self.state.set("mcu.toolboard.canbus_bitrate", int(bitrate or 1000000))
                self.state.save()

                self.ui.msgbox(f"Toolboard configured!\n\nUUID: {uuid}", title="Success")
        else:
            # USB toolboard - scan for devices
            # Load saved serial path to preselect it
            current_serial = self.state.get("mcu.toolboard.serial", "")

            self.ui.infobox("Scanning for USB devices...", title="Detecting")
            import time
            time.sleep(1)

            serial = None
            serial_dir = Path("/dev/serial/by-id")
            if serial_dir.exists():
                devices = list(serial_dir.iterdir())
                if devices:
                    # Build mapping: short_name -> full_path
                    serial_map = {}
                    device_items = []
                    for i, d in enumerate(devices):
                        short_name = self._format_serial_name(str(d))
                        tag = f"{i+1}. {short_name}"
                        serial_map[tag] = str(d)
                        # Preselect if this matches saved serial
                        is_selected = (str(d) == current_serial)
                        device_items.append((tag, "", is_selected))

                    device_items.append(("manual", "Enter path manually", False))

                    selected = self.ui.radiolist(
                        "Select the serial device for your toolboard:\n\n"
                        "(Usually contains 'EBB', 'SHT', or toolboard MCU name)",
                        device_items,
                        title="Toolboard - Serial",
                    )

                    if selected == "manual":
                        serial = self.ui.inputbox(
                            "Enter toolboard serial path:",
                            default=current_serial or "/dev/serial/by-id/usb-Klipper_"
                        )
                    elif selected and selected in serial_map:
                        serial = serial_map[selected]
                else:
                    serial = self.ui.inputbox(
                        "No USB devices found.\nEnter toolboard serial path:",
                        default=current_serial or "/dev/serial/by-id/usb-Klipper_"
                    )
            else:
                serial = self.ui.inputbox(
                    "Enter toolboard serial path:",
                    default=current_serial or "/dev/serial/by-id/usb-Klipper_"
                )

            if serial:
                # connection_type already saved above
                self.state.set("mcu.toolboard.serial", serial)
                self.state.save()

                self.ui.msgbox(f"Toolboard configured!\n\nSerial: {serial}", title="Success")

    def _configure_host_mcu(self) -> None:
        """Configure host MCU (Raspberry Pi)."""
        # Load saved state
        current_enabled = self.state.get("mcu.host.enabled", False)
        enabled = self.ui.yesno(
            "Enable Host MCU?\n\n"
            "This allows using Raspberry Pi GPIO pins for:\n"
            "• ADXL345 accelerometer\n"
            "• Additional GPIO outputs\n"
            "• Neopixel on Pi GPIO",
            title="Host MCU",
            default_no=not current_enabled
        )

        self.state.set("mcu.host.enabled", enabled)
        self.state.save()

        if enabled:
            self.ui.msgbox(
                "Host MCU enabled!\n\n"
                "Make sure klipper_mcu service is installed.\n"
                "Serial: /tmp/klipper_host_mcu",
                title="Host MCU"
            )

    def _printer_settings(self) -> None:
        """Configure printer settings."""
        # Kinematics - load saved value
        current_kinematics = self.state.get("printer.kinematics", "corexy")
        kinematics = self.ui.radiolist(
            "Select your printer's kinematics:",
            [
                ("corexy", "CoreXY (Voron, VzBot, etc.)", current_kinematics == "corexy"),
                ("cartesian", "Cartesian (Ender, Prusa, etc.)", current_kinematics == "cartesian"),
                ("corexz", "CoreXZ", current_kinematics == "corexz"),
                ("delta", "Delta", current_kinematics == "delta"),
            ],
            title="Kinematics"
        )

        if kinematics is None:
            return

        # AWD (All Wheel Drive) - only for CoreXY - load saved value
        awd_enabled = False
        if kinematics == "corexy":
            current_awd = self.state.get("printer.awd_enabled", False)
            awd_enabled = self.ui.yesno(
                "Do you have AWD (All Wheel Drive)?\n\n"
                "AWD uses 4 motors for X/Y motion:\n"
                "• stepper_x and stepper_x1 for X axis\n"
                "• stepper_y and stepper_y1 for Y axis\n\n"
                "Common on VzBot, some Voron mods, etc.",
                title="AWD Configuration",
                default_no=not current_awd
            )

        # Bed size - load saved values
        current_bed_x = self.state.get("printer.bed_size_x", 350)
        current_bed_y = self.state.get("printer.bed_size_y", 350)
        current_bed_z = self.state.get("printer.bed_size_z", 350)

        bed_x = self.ui.inputbox("Bed X size (mm):", default=str(current_bed_x))
        if bed_x is None:
            return

        bed_y = self.ui.inputbox("Bed Y size (mm):", default=str(current_bed_y))
        if bed_y is None:
            return

        bed_z = self.ui.inputbox("Z height (mm):", default=str(current_bed_z))
        if bed_z is None:
            return

        # Velocity limits - load saved values
        current_max_velocity = self.state.get("printer.max_velocity", 300)
        current_max_accel = self.state.get("printer.max_accel", 3000)

        max_velocity = self.ui.inputbox("Max velocity (mm/s):", default=str(current_max_velocity))
        max_accel = self.ui.inputbox("Max acceleration (mm/s²):", default=str(current_max_accel))

        # Save
        self.state.set("printer.kinematics", kinematics)
        self.state.set("printer.awd_enabled", awd_enabled)
        self.state.set("printer.bed_size_x", int(bed_x))
        self.state.set("printer.bed_size_y", int(bed_y))
        self.state.set("printer.bed_size_z", int(bed_z))
        self.state.set("printer.max_velocity", int(max_velocity or 300))
        self.state.set("printer.max_accel", int(max_accel or 3000))
        self.state.save()

        awd_text = "AWD: Enabled\n" if awd_enabled else ""
        self.ui.msgbox(
            f"Printer settings saved!\n\n"
            f"Kinematics: {kinematics}\n"
            f"{awd_text}"
            f"Bed: {bed_x}x{bed_y}x{bed_z}mm\n"
            f"Max velocity: {max_velocity}mm/s\n"
            f"Max accel: {max_accel}mm/s²",
            title="Settings Saved"
        )

    def _stepper_axis(self, axis: str) -> None:
        """Configure X, Y, X1, or Y1 axis stepper with smart inheritance.

        Inheritance logic:
        - X: Full configuration (reference axis)
        - Y: Can inherit from X (most CoreXY use same motors)
        - X1 (AWD): Can inherit from X
        - Y1 (AWD): Can inherit from Y
        """
        axis_upper = axis.upper()
        state_key = f"stepper_{axis}"
        is_secondary = axis in ("x1", "y1")

        # Determine inheritance source
        # x1 inherits from x, y1 inherits from y, y can inherit from x
        if axis == "x1":
            inherit_from = "x"
        elif axis == "y1":
            inherit_from = "y"
        elif axis == "y":
            inherit_from = "x"
        else:
            inherit_from = None

        # Determine default motor port from board
        port_defaults = {"x": "MOTOR_0", "y": "MOTOR_1", "x1": "MOTOR_2", "y1": "MOTOR_3"}
        default_port = port_defaults.get(axis, "MOTOR_0")

        # Check if we should offer inheritance
        use_inherited = False
        if inherit_from:
            # Check if source axis is configured
            source_driver = self.state.get(f"stepper_{inherit_from}.driver_type")
            if source_driver:
                source_current = self.state.get(f"stepper_{inherit_from}.run_current", 1.0)
                source_belt = self.state.get(f"stepper_{inherit_from}.belt_pitch", 2)
                source_pulley = self.state.get(f"stepper_{inherit_from}.pulley_teeth", 20)

                if is_secondary:
                    prompt = (
                        f"Use same motor/driver settings as {inherit_from.upper()}?\n\n"
                        f"Current {inherit_from.upper()} settings:\n"
                        f"  Driver: {source_driver}\n"
                        f"  Current: {source_current}A\n"
                        f"  Belt: {source_belt}mm × {source_pulley}T\n\n"
                        f"If yes, you'll only need to set:\n"
                        f"  • Motor port\n"
                        f"  • Direction pin inversion"
                    )
                else:
                    prompt = (
                        f"Use same motor/driver settings as {inherit_from.upper()}?\n\n"
                        f"Current {inherit_from.upper()} settings:\n"
                        f"  Driver: {source_driver}\n"
                        f"  Current: {source_current}A\n"
                        f"  Belt: {source_belt}mm × {source_pulley}T\n\n"
                        f"If yes, you'll only need to set:\n"
                        f"  • Motor port\n"
                        f"  • Direction pin\n"
                        f"  • Endstop settings"
                    )

                use_inherited = self.ui.yesno(prompt, title=f"Stepper {axis_upper} - Inheritance")

        # Motor port selection
        motor_ports = self._get_board_ports("motor_ports", "boards")
        if motor_ports:
            current_port = self.state.get(f"{state_key}.motor_port", "")
            motor_port = self.ui.radiolist(
                f"Select motor port for {axis_upper} axis:",
                [(p, l, p == current_port or p == default_port) for p, l, d in motor_ports],
                title=f"Stepper {axis_upper} - Motor Port"
            )
        else:
            motor_port = self.ui.inputbox(
                f"Motor port for {axis_upper} axis:",
                default=default_port,
                title=f"Stepper {axis_upper} - Motor Port"
            )
        if motor_port is None:
            return

        # Direction pin inversion (always ask - this differs per motor)
        current_inverted = self.state.get(f"{state_key}.dir_pin_inverted", False)
        dir_inverted = self.ui.yesno(
            f"Invert direction pin for {axis_upper}?\n\n"
            "(If motor moves wrong direction, change this)",
            title=f"Stepper {axis_upper} - Direction",
            default_no=not current_inverted
        )

        # If inheriting, copy settings and only ask for axis-specific things
        if use_inherited:
            self._copy_stepper_settings(inherit_from, axis)

            # For primary axes (Y), still need endstop config
            if not is_secondary:
                endstop_type = self.ui.radiolist(
                    f"Endstop type for {axis_upper} axis:",
                    [
                        ("physical", "Physical switch", True),
                        ("sensorless", "Sensorless (StallGuard)", False),
                    ],
                    title=f"Stepper {axis_upper} - Endstop"
                )
                if endstop_type is None:
                    return

                # Physical endstop port and config
                endstop_port = None
                endstop_config = None
                if endstop_type == "physical":
                    endstop_ports = self._get_board_ports("endstop_ports", "boards")
                    if endstop_ports:
                        endstop_port = self.ui.radiolist(
                            f"Select endstop port for {axis_upper} axis:",
                            [(p, l, d) for p, l, d in endstop_ports],
                            title=f"Stepper {axis_upper} - Endstop Port"
                        )
                    else:
                        endstop_port = self.ui.inputbox(
                            f"Enter endstop port for {axis_upper} axis:",
                            default="",
                            title=f"Stepper {axis_upper} - Endstop Port"
                        )
                    if endstop_port is None:
                        return

                    endstop_config = self.ui.radiolist(
                        f"Endstop switch configuration for {axis_upper}:",
                        [
                            ("nc_gnd", "NC to GND (^pin) - recommended", True),
                            ("no_gnd", "NO to GND (^!pin)", False),
                            ("nc_vcc", "NC to VCC (!pin)", False),
                            ("no_vcc", "NO to VCC (pin)", False),
                        ],
                        title=f"Stepper {axis_upper} - Endstop Config"
                    )
                    if endstop_config is None:
                        return

                bed_size = self.state.get(f"printer.bed_size_{axis}", 350)
                position_max = self.ui.inputbox(
                    f"Position max for {axis_upper} (mm):",
                    default=str(bed_size),
                    title=f"Stepper {axis_upper} - Position"
                )
                if position_max is None:
                    return

                position_endstop = self.ui.inputbox(
                    f"Position endstop for {axis_upper} (0 for min, {position_max} for max):",
                    default=position_max,
                    title=f"Stepper {axis_upper} - Endstop Position"
                )
                if position_endstop is None:
                    return

                # Homing settings
                homing_speed = self.ui.inputbox(
                    f"Homing speed for {axis_upper} (mm/s):",
                    default="50",
                    title=f"Stepper {axis_upper} - Homing Speed"
                )
                if homing_speed is None:
                    return

                default_retract = "0" if endstop_type == "sensorless" else "5"
                homing_retract_dist = self.ui.inputbox(
                    f"Homing retract distance for {axis_upper} (mm):",
                    default=default_retract,
                    title=f"Stepper {axis_upper} - Homing Retract"
                )
                if homing_retract_dist is None:
                    return

                second_homing_speed = None
                if self.ui.yesno(
                    f"Use second (slower) homing speed for {axis_upper}?",
                    title=f"Stepper {axis_upper} - Second Homing Speed"
                ):
                    second_homing_speed = self.ui.inputbox(
                        f"Second homing speed for {axis_upper} (mm/s):",
                        default="10",
                        title=f"Stepper {axis_upper} - Second Homing Speed"
                    )

                self.state.set(f"{state_key}.endstop_type", endstop_type or "physical")
                if endstop_port:
                    self.state.set(f"{state_key}.endstop_port", endstop_port)
                if endstop_config:
                    self.state.set(f"{state_key}.endstop_config", endstop_config)
                self.state.set(f"{state_key}.position_max", int(position_max or bed_size))
                self.state.set(f"{state_key}.position_endstop", int(position_endstop or position_max or bed_size))
                if homing_speed:
                    self.state.set(f"{state_key}.homing_speed", int(homing_speed or 50))
                if homing_retract_dist:
                    self.state.set(f"{state_key}.homing_retract_dist", float(homing_retract_dist or (0 if endstop_type == "sensorless" else 5)))
                if second_homing_speed:
                    self.state.set(f"{state_key}.second_homing_speed", int(second_homing_speed))

            # Save axis-specific settings
            self.state.set(f"{state_key}.motor_port", motor_port)
            self.state.set(f"{state_key}.dir_pin_inverted", dir_inverted)
            self.state.save()

            # Summary
            inherited_driver = self.state.get(f"{state_key}.driver_type")
            inherited_current = self.state.get(f"{state_key}.run_current")

            if is_secondary:
                self.ui.msgbox(
                    f"Stepper {axis_upper} configured!\n\n"
                    f"Motor: {motor_port}\n"
                    f"Direction inverted: {'Yes' if dir_inverted else 'No'}\n"
                    f"(Inherited from {inherit_from.upper()}: {inherited_driver}, {inherited_current}A)",
                    title="Configuration Saved"
                )
            else:
                self.ui.msgbox(
                    f"Stepper {axis_upper} configured!\n\n"
                    f"Motor: {motor_port}\n"
                    f"Direction inverted: {'Yes' if dir_inverted else 'No'}\n"
                    f"Endstop: {endstop_type}\n"
                    f"Position: 0 to {position_max}mm\n"
                    f"(Inherited from {inherit_from.upper()}: {inherited_driver}, {inherited_current}A)",
                    title="Configuration Saved"
                )
            return

        # === FULL CONFIGURATION (no inheritance) ===

        # Belt configuration
        current_belt = self.state.get(f"{state_key}.belt_pitch", 2)
        belt_pitch = self.ui.radiolist(
            f"Belt pitch for {axis_upper} axis:",
            [
                ("2", "2mm GT2 (most common)", current_belt == 2),
                ("3", "3mm HTD3M", current_belt == 3),
            ],
            title=f"Stepper {axis_upper} - Belt"
        )

        current_pulley = self.state.get(f"{state_key}.pulley_teeth", 20)
        pulley_teeth = self.ui.radiolist(
            f"Pulley teeth for {axis_upper} axis:",
            [
                ("16", "16 tooth", current_pulley == 16),
                ("20", "20 tooth (most common)", current_pulley == 20),
                ("24", "24 tooth", current_pulley == 24),
                ("32", "32 tooth", current_pulley == 32),
                ("40", "40 tooth", current_pulley == 40),
            ],
            title=f"Stepper {axis_upper} - Pulley"
        )

        # Microsteps
        current_microsteps = self.state.get(f"{state_key}.microsteps", 32)
        microsteps = self.ui.radiolist(
            f"Microsteps for {axis_upper}:",
            [
                ("16", "16 (basic)", current_microsteps == 16),
                ("32", "32 (recommended)", current_microsteps == 32),
                ("64", "64 (high resolution)", current_microsteps == 64),
            ],
            title=f"Stepper {axis_upper} - Microsteps"
        )

        # Full steps per rotation (motor type)
        current_steps = self.state.get(f"{state_key}.full_steps_per_rotation", 200)
        full_steps = self.ui.radiolist(
            f"Motor step angle for {axis_upper}:",
            [
                ("200", "1.8° (200 steps - most common)", current_steps == 200),
                ("400", "0.9° (400 steps - high precision)", current_steps == 400),
            ],
            title=f"Stepper {axis_upper} - Motor Type"
        )

        # TMC Driver Type
        current_driver = self.state.get(f"{state_key}.driver_type", "TMC2209")
        driver_type = self.ui.radiolist(
            f"TMC driver type for {axis_upper}:",
            [
                ("TMC2209", "TMC2209 (UART)", current_driver == "TMC2209"),
                ("TMC5160", "TMC5160 (SPI)", current_driver == "TMC5160"),
                ("TMC2240", "TMC2240 (SPI/UART)", current_driver == "TMC2240"),
                ("TMC2130", "TMC2130 (SPI)", current_driver == "TMC2130"),
            ],
            title=f"Stepper {axis_upper} - Driver Type"
        )

        # Determine protocol from driver type
        spi_drivers = ["TMC5160", "TMC2130", "TMC2660"]
        driver_protocol = "spi" if driver_type in spi_drivers else "uart"

        # Run current
        current_current = self.state.get(f"{state_key}.run_current", 1.0)
        default_current = "1.7" if driver_type == "TMC5160" else str(current_current)
        run_current = self.ui.inputbox(
            f"TMC run current for {axis_upper} (A):\n\n"
            "Check your motor datasheet for max current.\n"
            "Rule of thumb: 70-85% of rated current.",
            default=default_current,
            title=f"Stepper {axis_upper} - Run Current"
        )

        # SPI-specific settings
        sense_resistor = None
        if driver_protocol == "spi":
            current_sense = self.state.get(f"{state_key}.sense_resistor", 0.075)
            sense_resistor = self.ui.radiolist(
                f"Sense resistor for {axis_upper}:\n\n"
                "(Check your driver board specifications)",
                [
                    ("0.075", "0.075Ω (standard TMC5160)", current_sense == 0.075),
                    ("0.033", "0.033Ω (high current boards)", current_sense == 0.033),
                    ("0.022", "0.022Ω (very high current)", current_sense == 0.022),
                    ("0.110", "0.110Ω (TMC2240 default)", current_sense == 0.110),
                ],
                title=f"Stepper {axis_upper} - Sense Resistor"
            )

        # Endstop configuration (only for primary steppers)
        endstop_type = None
        endstop_port = None
        endstop_config = None
        position_max = None
        position_endstop = None
        homing_speed = None
        homing_retract_dist = None
        second_homing_speed = None

        if not is_secondary:
            current_endstop = self.state.get(f"{state_key}.endstop_type", "physical")
            endstop_type = self.ui.radiolist(
                f"Endstop type for {axis_upper} axis:",
                [
                    ("physical", "Physical switch", current_endstop == "physical"),
                    ("sensorless", "Sensorless (StallGuard)", current_endstop == "sensorless"),
                ],
                title=f"Stepper {axis_upper} - Endstop"
            )
            if endstop_type is None:
                return

            # Physical endstop port and config
            if endstop_type == "physical":
                # Endstop port selection from board templates
                endstop_ports = self._get_board_ports("endstop_ports", "boards")
                if endstop_ports:
                    current_port = self.state.get(f"{state_key}.endstop_port", "")
                    endstop_port = self.ui.radiolist(
                        f"Select endstop port for {axis_upper} axis:",
                        [(p, l, p == current_port or d) for p, l, d in endstop_ports],
                        title=f"Stepper {axis_upper} - Endstop Port"
                    )
                else:
                    endstop_port = self.ui.inputbox(
                        f"Enter endstop port for {axis_upper} axis:",
                        default="",
                        title=f"Stepper {axis_upper} - Endstop Port"
                    )
                if endstop_port is None:
                    return

                # Endstop pin configuration (modifiers)
                current_config = self.state.get(f"{state_key}.endstop_config", "nc_gnd")
                endstop_config = self.ui.radiolist(
                    f"Endstop switch configuration for {axis_upper}:\n\n"
                    "(NC = Normally Closed, NO = Normally Open)",
                    [
                        ("nc_gnd", "NC to GND (^pin) - recommended", current_config == "nc_gnd"),
                        ("no_gnd", "NO to GND (^!pin)", current_config == "no_gnd"),
                        ("nc_vcc", "NC to VCC (!pin)", current_config == "nc_vcc"),
                        ("no_vcc", "NO to VCC (pin)", current_config == "no_vcc"),
                    ],
                    title=f"Stepper {axis_upper} - Endstop Config"
                )
                if endstop_config is None:
                    return

            bed_size = self.state.get(f"printer.bed_size_{axis}", 350)
            current_max = self.state.get(f"{state_key}.position_max", bed_size)
            position_max = self.ui.inputbox(
                f"Position max for {axis_upper} (mm):",
                default=str(current_max),
                title=f"Stepper {axis_upper} - Position"
            )
            if position_max is None:
                return

            current_endstop_pos = self.state.get(f"{state_key}.position_endstop", position_max)
            position_endstop = self.ui.inputbox(
                f"Position endstop for {axis_upper} (0 for min, {position_max} for max):",
                default=str(current_endstop_pos),
                title=f"Stepper {axis_upper} - Endstop Position"
            )
            if position_endstop is None:
                return

            # Homing settings
            current_homing_speed = self.state.get(f"{state_key}.homing_speed", 50)
            homing_speed = self.ui.inputbox(
                f"Homing speed for {axis_upper} (mm/s):\n\n"
                "(Default: 50-80 for X/Y)",
                default=str(current_homing_speed),
                title=f"Stepper {axis_upper} - Homing Speed"
            )
            if homing_speed is None:
                return

            current_retract = self.state.get(f"{state_key}.homing_retract_dist", 5.0)
            default_retract = "0" if endstop_type == "sensorless" else "5"
            homing_retract_dist = self.ui.inputbox(
                f"Homing retract distance for {axis_upper} (mm):\n\n"
                f"(0 for sensorless, 5 for physical - default: {default_retract})",
                default=str(current_retract),
                title=f"Stepper {axis_upper} - Homing Retract"
            )
            if homing_retract_dist is None:
                return

            # Optional second homing speed - check if already configured
            current_has_second = self.state.get(f"{state_key}.second_homing_speed") is not None
            if self.ui.yesno(
                f"Use second (slower) homing speed for {axis_upper}?",
                title=f"Stepper {axis_upper} - Second Homing Speed",
                default_no=not current_has_second
            ):
                current_second = self.state.get(f"{state_key}.second_homing_speed", 10)
                second_homing_speed = self.ui.inputbox(
                    f"Second homing speed for {axis_upper} (mm/s):\n\n"
                    "(Default: 10-20)",
                    default=str(current_second),
                    title=f"Stepper {axis_upper} - Second Homing Speed"
                )

        # Save all settings
        self.state.set(f"{state_key}.motor_port", motor_port)
        self.state.set(f"{state_key}.dir_pin_inverted", dir_inverted)
        self.state.set(f"{state_key}.belt_pitch", int(belt_pitch or 2))
        self.state.set(f"{state_key}.pulley_teeth", int(pulley_teeth or 20))
        self.state.set(f"{state_key}.microsteps", int(microsteps or 32))
        self.state.set(f"{state_key}.full_steps_per_rotation", int(full_steps or 200))
        self.state.set(f"{state_key}.driver_type", driver_type or "TMC2209")
        self.state.set(f"{state_key}.driver_protocol", driver_protocol)
        self.state.set(f"{state_key}.run_current", float(run_current or 1.0))

        if sense_resistor:
            self.state.set(f"{state_key}.sense_resistor", float(sense_resistor))

        if not is_secondary:
            self.state.set(f"{state_key}.endstop_type", endstop_type or "physical")
            if endstop_type == "physical" and endstop_port:
                self.state.set(f"{state_key}.endstop_port", endstop_port)
            if endstop_type == "physical" and endstop_config:
                self.state.set(f"{state_key}.endstop_config", endstop_config)
            bed_size = self.state.get(f"printer.bed_size_{axis}", 350)
            self.state.set(f"{state_key}.position_max", int(position_max or bed_size))
            self.state.set(f"{state_key}.position_endstop", int(position_endstop or position_max or bed_size))
            if homing_speed:
                self.state.set(f"{state_key}.homing_speed", int(homing_speed or 50))
            if homing_retract_dist:
                self.state.set(f"{state_key}.homing_retract_dist", float(homing_retract_dist or (0 if endstop_type == "sensorless" else 5)))
            if second_homing_speed:
                self.state.set(f"{state_key}.second_homing_speed", int(second_homing_speed))

        self.state.save()

        if is_secondary:
            self.ui.msgbox(
                f"Stepper {axis_upper} (AWD) configured!\n\n"
                f"Motor: {motor_port}\n"
                f"Belt: {belt_pitch}mm × {pulley_teeth}T\n"
                f"Microsteps: {microsteps}\n"
                f"Driver: {driver_type}\n"
                f"Current: {run_current}A",
                title="Configuration Saved"
            )
        else:
            self.ui.msgbox(
                f"Stepper {axis_upper} configured!\n\n"
                f"Motor: {motor_port}\n"
                f"Belt: {belt_pitch}mm × {pulley_teeth}T\n"
                f"Microsteps: {microsteps}\n"
                f"Driver: {driver_type}\n"
                f"Endstop: {endstop_type}\n"
                f"Position: 0 to {position_max}mm\n"
                f"Current: {run_current}A",
                title="Configuration Saved"
            )

    def _stepper_z(self) -> None:
        """Configure Z axis stepper(s)."""
        # Load saved values
        current_z_count = self.state.get("stepper_z.z_motor_count", 4)
        current_drive_type = self.state.get("stepper_z.drive_type", "leadscrew")
        current_pitch = self.state.get("stepper_z.leadscrew_pitch", 8)
        current_endstop = self.state.get("stepper_z.endstop_type", "probe")
        current_position_max = self.state.get("stepper_z.position_max", None)
        current_run_current = self.state.get("stepper_z.run_current", 0.8)

        # Number of Z motors
        z_count = self.ui.radiolist(
            "How many Z motors?",
            [
                ("1", "Single Z motor", current_z_count == 1),
                ("2", "Dual Z (Z tilt)", current_z_count == 2),
                ("3", "Triple Z", current_z_count == 3),
                ("4", "Quad Z (QGL)", current_z_count == 4),
            ],
            title="Z Axis - Motor Count"
        )

        # Drive type
        drive_type = self.ui.radiolist(
            "Z drive type:",
            [
                ("leadscrew", "Leadscrew (T8, TR8)", current_drive_type == "leadscrew"),
                ("belt", "Belt driven", current_drive_type == "belt"),
            ],
            title="Z Axis - Drive"
        )

        if drive_type == "leadscrew":
            pitch = self.ui.radiolist(
                "Leadscrew pitch:",
                [
                    ("8", "8mm (T8 standard)", current_pitch == 8),
                    ("4", "4mm (high speed)", current_pitch == 4),
                    ("2", "2mm (TR8x2)", current_pitch == 2),
                ],
                title="Z Axis - Leadscrew"
            )
        else:
            pitch = "2"  # Belt driven uses belt pitch

        # Endstop
        endstop_type = self.ui.radiolist(
            "Z endstop type:",
            [
                ("probe", "Probe (virtual endstop)", current_endstop == "probe"),
                ("physical_mainboard", "Physical switch (mainboard)", current_endstop == "physical_mainboard"),
                ("physical_toolboard", "Physical switch (toolboard)", current_endstop == "physical_toolboard"),
            ],
            title="Z Axis - Endstop"
        )

        # Position - use saved value or bed_z
        bed_z = self.state.get("printer.bed_size_z", 350)
        position_default = current_position_max if current_position_max is not None else bed_z
        position_max = self.ui.inputbox(
            "Z position max (mm):",
            default=str(position_default),
            title="Z Axis - Position"
        )

        # Current
        run_current = self.ui.inputbox(
            "TMC run current for Z (A):",
            default=str(current_run_current),
            title="Z Axis - Driver"
        )

        # Save
        self.state.set("stepper_z.z_motor_count", int(z_count or 4))
        self.state.set("stepper_z.drive_type", drive_type or "leadscrew")
        self.state.set("stepper_z.leadscrew_pitch", int(pitch or 8))
        self.state.set("stepper_z.endstop_type", endstop_type or "probe")
        self.state.set("stepper_z.position_max", int(position_max or bed_z))
        self.state.set("stepper_z.run_current", float(run_current or 0.8))
        self.state.save()

        self.ui.msgbox(
            f"Z Axis configured!\n\n"
            f"Motors: {z_count}\n"
            f"Drive: {drive_type} ({pitch}mm)\n"
            f"Endstop: {endstop_type}\n"
            f"Height: {position_max}mm\n"
            f"Current: {run_current}A",
            title="Configuration Saved"
        )

    def _extruder_setup(self) -> None:
        """Configure extruder motor and hotend per schema 2.6."""
        # Get current values for pre-selection (using correct state keys)
        current_type = self.state.get("extruder.extruder_type", "")
        current_location = self.state.get("extruder.location", "")
        current_dir_inv = self.state.get("extruder.dir_pin_inverted", False)
        current_microsteps = self.state.get("extruder.microsteps", 16)
        current_steps = self.state.get("extruder.full_steps_per_rotation", 200)
        current_nozzle = self.state.get("extruder.nozzle_diameter", 0.4)
        current_filament = self.state.get("extruder.filament_diameter", 1.75)
        current_drive = self.state.get("extruder.drive_type", "direct")
        current_sensor_type = self.state.get("extruder.sensor_type", "")
        current_sensor_loc = self.state.get("extruder.sensor_location", "")
        current_heater_loc = self.state.get("extruder.heater_location", "")
        current_max_temp = self.state.get("extruder.max_temp", 300)
        current_min_temp = self.state.get("extruder.min_temp", 0)
        current_max_power = self.state.get("extruder.max_power", 1.0)

        # Check if toolboard is configured
        has_toolboard = self.state.get("mcu.toolboard.enabled", False) or \
                        self.state.get("mcu.toolboard.connection_type")

        # === 2.6.1: Motor Location ===
        if has_toolboard:
            motor_location = self.ui.radiolist(
                "Where is the extruder MOTOR connected?",
                [
                    ("mainboard", "Mainboard", current_location == "mainboard"),
                    ("toolboard", "Toolboard", current_location == "toolboard" or not current_location),
                ],
                title="Extruder Motor - Location"
            )
        else:
            motor_location = "mainboard"
        if motor_location is None:
            return

        # Motor port selection
        board_type = "toolboards" if motor_location == "toolboard" else "boards"
        motor_ports = self._get_board_ports("motor_ports", board_type)
        if motor_ports:
            # Check both possible keys for current value
            current_port = self.state.get(f"extruder.motor_port_{motor_location}", "") or \
                          self.state.get("extruder.motor_port_mainboard", "") or \
                          self.state.get("extruder.motor_port_toolboard", "")
            motor_port = self.ui.radiolist(
                f"Select motor port on {motor_location}:",
                [(p, l, p == current_port or d) for p, l, d in motor_ports],
                title="Extruder Motor - Port"
            )
        else:
            motor_port = self.ui.inputbox(
                f"Enter motor port on {motor_location}:",
                default="EXTRUDER" if motor_location == "toolboard" else "MOTOR_5",
                title="Extruder Motor - Port"
            )
        if motor_port is None:
            return

        # === 2.6.2: Extruder Type ===
        extruder_types = [
            ("sherpa_mini", "Sherpa Mini"),
            ("orbiter_v2", "Orbiter v2.0/v2.5"),
            ("smart_orbiter_v3", "Smart Orbiter v3"),
            ("clockwork2", "Clockwork 2"),
            ("galileo2", "Galileo 2"),
            ("lgx_lite", "LGX Lite"),
            ("bmg", "BMG"),
            ("vz_hextrudort_8t", "VZ-Hextrudort 8T"),
            ("vz_hextrudort_10t", "VZ-Hextrudort 10T"),
            ("custom", "Custom"),
        ]

        extruder_type = self.ui.radiolist(
            "Select your extruder type:\n\n"
            "(This sets rotation_distance and gear_ratio)",
            [(k, v, k == current_type or (not current_type and k == "sherpa_mini"))
             for k, v in extruder_types],
            title="Extruder Motor - Type"
        )
        if extruder_type is None:
            return

        # === 2.6.3: Extruder Config ===
        # Motor configuration
        dir_pin_inverted = self.ui.yesno(
            "Invert extruder direction pin?",
            title="Extruder Motor - Direction",
            default_no=not current_dir_inv
        )

        microsteps = self.ui.radiolist(
            "Extruder microsteps:",
            [
                ("16", "16", current_microsteps == 16),
                ("32", "32", current_microsteps == 32),
            ],
            title="Extruder Motor - Microsteps"
        )
        if microsteps is None:
            return

        full_steps = self.ui.radiolist(
            "Motor step angle:",
            [
                ("200", "1.8° (200 steps - most common)", current_steps == 200),
                ("400", "0.9° (400 steps - high precision)", current_steps == 400),
            ],
            title="Extruder Motor - Step Angle"
        )
        if full_steps is None:
            return

        # Nozzle and filament
        nozzle_diameter = self.ui.radiolist(
            "Nozzle diameter (mm):",
            [
                ("0.4", "0.4mm (most common)", current_nozzle == 0.4),
                ("0.5", "0.5mm", current_nozzle == 0.5),
                ("0.6", "0.6mm", current_nozzle == 0.6),
                ("0.8", "0.8mm", current_nozzle == 0.8),
                ("1.0", "1.0mm", current_nozzle == 1.0),
            ],
            title="Extruder - Nozzle Diameter"
        )
        if nozzle_diameter is None:
            return

        filament_diameter = self.ui.radiolist(
            "Filament diameter (mm):",
            [
                ("1.75", "1.75mm (most common)", current_filament == 1.75),
                ("2.85", "2.85mm (3mm)", current_filament == 2.85),
            ],
            title="Extruder - Filament Diameter"
        )
        if filament_diameter is None:
            return

        # Hotend heater configuration
        if has_toolboard:
            heater_location = self.ui.radiolist(
                "Where is the hotend HEATER connected?",
                [
                    ("mainboard", "Mainboard", current_heater_loc == "mainboard"),
                    ("toolboard", "Toolboard", current_heater_loc == "toolboard" or not current_heater_loc),
                ],
                title="Hotend - Heater Location"
            )
        else:
            heater_location = "mainboard"
        if heater_location is None:
            return

        # Heater port selection
        board_type = "toolboards" if heater_location == "toolboard" else "boards"
        heater_ports = self._get_board_ports("heater_ports", board_type)
        if heater_ports:
            # Check both possible keys for current value
            current_port = self.state.get(f"extruder.heater_port_{heater_location}", "") or \
                          self.state.get("extruder.heater_port_mainboard", "") or \
                          self.state.get("extruder.heater_port_toolboard", "")
            # Filter to show hotend heaters, not bed heater
            hotend_ports = [(p, l, p == current_port or (d and "Bed" not in l))
                           for p, l, d in heater_ports if "Bed" not in l]
            if hotend_ports:
                heater_port = self.ui.radiolist(
                    f"Select heater port on {heater_location}:",
                    hotend_ports,
                    title="Hotend - Heater Port"
                )
            else:
                heater_port = self.ui.inputbox(
                    f"Enter heater port on {heater_location}:",
                    default="HE" if heater_location == "toolboard" else "HE0",
                    title="Hotend - Heater Port"
                )
        else:
            heater_port = self.ui.inputbox(
                f"Enter heater port on {heater_location}:",
                default="HE" if heater_location == "toolboard" else "HE0",
                title="Hotend - Heater Port"
            )
        if heater_port is None:
            return

        max_power = self.ui.inputbox(
            "Heater max power (0.1-1.0):\n\n"
            "(Usually 1.0, reduce for cheap SSRs)",
            default=str(current_max_power),
            title="Hotend - Max Power"
        )
        if max_power is None:
            return

        # Thermistor configuration
        if has_toolboard:
            sensor_location = self.ui.radiolist(
                "Where is the thermistor connected?",
                [
                    ("mainboard", "Mainboard", current_sensor_loc == "mainboard"),
                    ("toolboard", "Toolboard", current_sensor_loc == "toolboard" or not current_sensor_loc),
                ],
                title="Hotend - Thermistor Location"
            )
        else:
            sensor_location = "mainboard"
        if sensor_location is None:
            return

        # Thermistor port selection
        board_type = "toolboards" if sensor_location == "toolboard" else "boards"
        sensor_ports = self._get_board_ports("thermistor_ports", board_type)
        if sensor_ports:
            # Check both possible keys for current value
            current_port = self.state.get(f"extruder.sensor_port_{sensor_location}", "") or \
                          self.state.get("extruder.sensor_port_mainboard", "") or \
                          self.state.get("extruder.sensor_port_toolboard", "")
            # Filter to show hotend thermistors, not bed
            hotend_sensors = [(p, l, p == current_port or (d and "Bed" not in l))
                             for p, l, d in sensor_ports if "Bed" not in l]
            if hotend_sensors:
                sensor_port = self.ui.radiolist(
                    f"Select thermistor port on {sensor_location}:",
                    hotend_sensors,
                    title="Hotend - Thermistor Port"
                )
            else:
                sensor_port = self.ui.inputbox(
                    f"Enter thermistor port on {sensor_location}:",
                    default="TH0" if sensor_location == "toolboard" else "T0",
                    title="Hotend - Thermistor Port"
                )
        else:
            sensor_port = self.ui.inputbox(
                f"Enter thermistor port on {sensor_location}:",
                default="TH0" if sensor_location == "toolboard" else "T0",
                title="Hotend - Thermistor Port"
            )
        if sensor_port is None:
            return

        # Thermistor type
        sensor_types = [
            ("Generic 3950", "Generic 3950 (most common)"),
            ("ATC Semitec 104GT-2", "ATC Semitec 104GT-2"),
            ("ATC Semitec 104NT-4-R025H42G", "ATC Semitec 104NT-4 (Rapido, Dragon UHF)"),
            ("PT1000", "PT1000 (high temp)"),
            ("SliceEngineering 450", "SliceEngineering 450°C"),
            ("NTC 100K beta 3950", "NTC 100K beta 3950"),
        ]
        sensor_type = self.ui.radiolist(
            "Hotend thermistor/sensor type:",
            [(k, v, k == current_sensor_type or (not current_sensor_type and k == "Generic 3950"))
             for k, v in sensor_types],
            title="Hotend - Thermistor Type"
        )
        if sensor_type is None:
            return

        # Pullup resistor (only for NTC thermistors)
        pullup_resistor = None
        if sensor_type not in ["PT1000"]:
            current_pullup = self.state.get("extruder.pullup_resistor", 4700)
            pullup_resistor = self.ui.radiolist(
                "Thermistor pullup resistor value:\n\n"
                "(Check your board - most use 4.7kΩ, some toolboards use 2.2kΩ)",
                [
                    ("4700", "4.7kΩ (standard mainboards)", current_pullup == 4700),
                    ("2200", "2.2kΩ (some toolboards like Nitehawk)", current_pullup == 2200),
                    ("10000", "10kΩ (rare)", current_pullup == 10000),
                    ("custom", "Enter custom value", False),
                ],
                title="Hotend - Pullup Resistor"
            )
            if pullup_resistor == "custom":
                pullup_resistor = self.ui.inputbox(
                    "Enter pullup resistor value (Ω):",
                    default=str(current_pullup),
                    title="Hotend - Custom Pullup"
                )
            if pullup_resistor:
                pullup_resistor = int(pullup_resistor)

        # Temperature settings
        min_temp = self.ui.inputbox(
            "Minimum hotend temperature (°C):",
            default=str(current_min_temp),
            title="Hotend - Min Temp"
        )
        if min_temp is None:
            return

        max_temp = self.ui.inputbox(
            "Maximum hotend temperature (°C):",
            default=str(current_max_temp),
            title="Hotend - Max Temp"
        )
        if max_temp is None:
            return

        # Extrusion settings
        drive_type = self.ui.radiolist(
            "Extruder drive type:",
            [
                ("direct", "Direct Drive", current_drive == "direct"),
                ("bowden", "Bowden", current_drive == "bowden"),
            ],
            title="Extruder - Drive Type"
        )
        if drive_type is None:
            return

        # Set defaults based on drive type
        default_extrude_dist = 500 if drive_type == "bowden" else 150
        current_extrude_dist = self.state.get("extruder.max_extrude_only_distance", default_extrude_dist)
        max_extrude_only_distance = self.ui.inputbox(
            "Max extrude only distance (mm):\n\n"
            f"(Default: {default_extrude_dist}mm for {drive_type})",
            default=str(current_extrude_dist),
            title="Extruder - Max Extrude Distance"
        )
        if max_extrude_only_distance is None:
            return

        # Load saved values for extrusion parameters
        current_max_cross_section = self.state.get("extruder.max_extrude_cross_section", 5.0)
        current_min_extrude_temp = self.state.get("extruder.min_extrude_temp", 170)
        current_corner_velocity = self.state.get("extruder.instantaneous_corner_velocity", 1.0)

        max_extrude_cross_section = self.ui.inputbox(
            "Max extrude cross section (mm²):",
            default=str(current_max_cross_section),
            title="Extruder - Max Cross Section"
        )
        if max_extrude_cross_section is None:
            return

        min_extrude_temp = self.ui.inputbox(
            "Minimum extrude temperature (°C):",
            default=str(current_min_extrude_temp),
            title="Extruder - Min Extrude Temp"
        )
        if min_extrude_temp is None:
            return

        instantaneous_corner_velocity = self.ui.inputbox(
            "Instantaneous corner velocity (mm/s):",
            default=str(current_corner_velocity),
            title="Extruder - Corner Velocity"
        )
        if instantaneous_corner_velocity is None:
            return

        # Save all settings with correct state keys (extruder.* for everything)
        # State keys must match config-sections.yaml template expectations
        self.state.set("extruder.extruder_type", extruder_type)
        self.state.set("extruder.location", motor_location)
        # Save motor port to specific key based on location (template expects motor_port_mainboard or motor_port_toolboard)
        if motor_location == "toolboard":
            self.state.set("extruder.motor_port_toolboard", motor_port)
            self.state.delete("extruder.motor_port_mainboard")  # Clear other key
        else:
            self.state.set("extruder.motor_port_mainboard", motor_port)
            self.state.delete("extruder.motor_port_toolboard")  # Clear other key

        self.state.set("extruder.dir_pin_inverted", dir_pin_inverted)
        self.state.set("extruder.microsteps", int(microsteps or 16))
        self.state.set("extruder.full_steps_per_rotation", int(full_steps or 200))
        self.state.set("extruder.nozzle_diameter", float(nozzle_diameter or 0.4))
        self.state.set("extruder.filament_diameter", float(filament_diameter or 1.75))
        self.state.set("extruder.heater_location", heater_location)
        # Save heater port to specific key based on location (template expects heater_port_mainboard or heater_port_toolboard)
        if heater_location == "toolboard":
            self.state.set("extruder.heater_port_toolboard", heater_port)
            self.state.delete("extruder.heater_port_mainboard")  # Clear other key
        else:
            self.state.set("extruder.heater_port_mainboard", heater_port)
            self.state.delete("extruder.heater_port_toolboard")  # Clear other key

        self.state.set("extruder.max_power", float(max_power or 1.0))
        self.state.set("extruder.sensor_location", sensor_location)
        # Save sensor port to specific key based on location (template expects sensor_port_mainboard or sensor_port_toolboard)
        if sensor_location == "toolboard":
            self.state.set("extruder.sensor_port_toolboard", sensor_port)
            self.state.delete("extruder.sensor_port_mainboard")  # Clear other key
        else:
            self.state.set("extruder.sensor_port_mainboard", sensor_port)
            self.state.delete("extruder.sensor_port_toolboard")  # Clear other key

        self.state.set("extruder.sensor_type", sensor_type)
        if pullup_resistor:
            self.state.set("extruder.pullup_resistor", pullup_resistor)
        self.state.set("extruder.min_temp", int(min_temp or 0))
        self.state.set("extruder.max_temp", int(max_temp or 300))
        self.state.set("extruder.drive_type", drive_type or "direct")
        self.state.set("extruder.max_extrude_only_distance", int(max_extrude_only_distance or default_extrude_dist))
        self.state.set("extruder.max_extrude_cross_section", float(max_extrude_cross_section or 5.0))
        self.state.set("extruder.min_extrude_temp", int(min_extrude_temp or 170))
        self.state.set("extruder.instantaneous_corner_velocity", float(instantaneous_corner_velocity or 1.0))
        self.state.save()

        pullup_text = f"\n  Pullup: {pullup_resistor}Ω" if pullup_resistor else ""
        self.ui.msgbox(
            f"Extruder & Hotend configured!\n\n"
            f"EXTRUDER MOTOR:\n"
            f"  Type: {extruder_type}\n"
            f"  Location: {motor_location} ({motor_port})\n"
            f"  Microsteps: {microsteps}\n"
            f"  Step angle: {full_steps} steps\n\n"
            f"HOTEND:\n"
            f"  Heater: {heater_location} ({heater_port})\n"
            f"  Thermistor: {sensor_type}\n"
            f"  Sensor port: {sensor_location} ({sensor_port}){pullup_text}\n"
            f"  Temp range: {min_temp}°C - {max_temp}°C\n"
            f"  Drive: {drive_type}\n"
            f"  Nozzle: {nozzle_diameter}mm",
            title="Configuration Saved"
        )

    def _heater_bed_setup(self) -> None:
        """Configure heated bed per schema 2.7."""
        # Get current values
        current_heater_pin = self.state.get("heater_bed.heater_pin", "")
        current_max_power = self.state.get("heater_bed.max_power", 1.0)
        current_pwm_cycle = self.state.get("heater_bed.pwm_cycle_time", 0.0166)
        current_sensor_type = self.state.get("heater_bed.sensor_type", "Generic 3950")
        current_sensor_port = self.state.get("heater_bed.sensor_port", "")
        current_min_temp = self.state.get("heater_bed.min_temp", 0)
        current_max_temp = self.state.get("heater_bed.max_temp", 120)
        current_control = self.state.get("heater_bed.control", "pid")
        current_surface = self.state.get("heater_bed.surface_type", "")

        # === 2.7.1: Heater Configuration ===
        # Heater pin selection (bed heater is always on mainboard)
        heater_ports = self._get_board_ports("heater_ports", "boards")
        if heater_ports:
            # Filter to show bed heater
            bed_ports = [(p, l, p == current_heater_pin or "Bed" in l or p == "HB")
                        for p, l, d in heater_ports if "Bed" in l or p == "HB"]
            if bed_ports:
                heater_pin = self.ui.radiolist(
                    "Select heated bed heater pin:",
                    bed_ports,
                    title="Heated Bed - Heater Pin"
                )
            else:
                # No specific bed port found, show all heater ports
                heater_pin = self.ui.radiolist(
                    "Select heated bed heater pin:",
                    [(p, l, p == current_heater_pin or d) for p, l, d in heater_ports],
                    title="Heated Bed - Heater Pin"
                )
        else:
            heater_pin = self.ui.inputbox(
                "Enter heated bed heater pin:",
                default=current_heater_pin or "HB",
                title="Heated Bed - Heater Pin"
            )
        if heater_pin is None:
            return

        max_power = self.ui.inputbox(
            "Heater max power (0.1-1.0):\n\n"
            "(Usually 1.0, reduce for cheap SSRs that can't handle full PWM)",
            default=str(current_max_power),
            title="Heated Bed - Max Power"
        )
        if max_power is None:
            return

        pwm_cycle_time = self.ui.inputbox(
            "PWM cycle time (seconds):\n\n"
            "(Usually 0.0166 for 60Hz, rarely needs changes)",
            default=str(current_pwm_cycle),
            title="Heated Bed - PWM Cycle Time"
        )
        if pwm_cycle_time is None:
            return

        # === 2.7.2: Thermistor ===
        # Thermistor port selection (bed thermistor is always on mainboard)
        sensor_ports = self._get_board_ports("thermistor_ports", "boards")
        if sensor_ports:
            # Filter to show bed thermistor
            bed_sensors = [(p, l, p == current_sensor_port or "Bed" in l or p == "TB")
                          for p, l, d in sensor_ports if "Bed" in l or p == "TB"]
            if bed_sensors:
                sensor_port = self.ui.radiolist(
                    "Select bed thermistor port:",
                    bed_sensors,
                    title="Heated Bed - Thermistor Port"
                )
            else:
                # No specific bed port found, show all thermistor ports
                sensor_port = self.ui.radiolist(
                    "Select bed thermistor port:",
                    [(p, l, p == current_sensor_port or d) for p, l, d in sensor_ports],
                    title="Heated Bed - Thermistor Port"
                )
        else:
            sensor_port = self.ui.inputbox(
                "Enter bed thermistor port:",
                default=current_sensor_port or "TB",
                title="Heated Bed - Thermistor Port"
            )
        if sensor_port is None:
            return

        # Thermistor type
        sensor_types = [
            ("Generic 3950", "Generic 3950 (most common)"),
            ("NTC 100K beta 3950", "NTC 100K beta 3950"),
            ("ATC Semitec 104GT-2", "ATC Semitec 104GT-2"),
            ("EPCOS 100K B57560G104F", "EPCOS 100K B57560G104F"),
            ("Honeywell 100K 135-104LAG-J01", "Honeywell 100K"),
            ("PT1000", "PT1000"),
        ]
        sensor_type = self.ui.radiolist(
            "Bed thermistor type:",
            [(k, v, k == current_sensor_type) for k, v in sensor_types],
            title="Heated Bed - Thermistor Type"
        )
        if sensor_type is None:
            return

        # Pullup resistor (only for NTC thermistors)
        pullup_resistor = None
        if sensor_type != "PT1000":
            current_pullup = self.state.get("heater_bed.pullup_resistor", 4700)
            pullup_resistor = self.ui.radiolist(
                "Bed thermistor pullup resistor value:\n\n"
                "(Most mainboards use 4.7kΩ standard)",
                [
                    ("4700", "4.7kΩ (standard)", current_pullup == 4700),
                    ("2200", "2.2kΩ", current_pullup == 2200),
                    ("10000", "10kΩ", current_pullup == 10000),
                    ("custom", "Enter custom value", False),
                ],
                title="Heated Bed - Pullup Resistor"
            )
            if pullup_resistor == "custom":
                pullup_resistor = self.ui.inputbox(
                    "Enter pullup resistor value (Ω):",
                    default=str(current_pullup),
                    title="Heated Bed - Custom Pullup"
                )
            if pullup_resistor:
                pullup_resistor = int(pullup_resistor)

        # === 2.7.3: Temperature Settings ===
        min_temp = self.ui.inputbox(
            "Minimum bed temperature (°C):",
            default=str(current_min_temp),
            title="Heated Bed - Min Temp"
        )
        if min_temp is None:
            return

        max_temp = self.ui.inputbox(
            "Maximum bed temperature (°C):\n\n"
            "(Typical max for heated beds is 120°C)",
            default=str(current_max_temp),
            title="Heated Bed - Max Temp"
        )
        if max_temp is None:
            return

        control = self.ui.radiolist(
            "Temperature control method:",
            [
                ("pid", "PID (most common)", current_control == "pid"),
                ("watermark", "Watermark (simple on/off)", current_control == "watermark"),
            ],
            title="Heated Bed - Control Method"
        )
        if control is None:
            return

        # === 2.7.4: PID Values ===
        self.ui.msgbox(
            "PID values will be set to 0 initially.\n\n"
            "After first boot, run:\n"
            "PID_CALIBRATE HEATER=heater_bed TARGET=60\n\n"
            "Then SAVE_CONFIG to store the values.",
            title="Heated Bed - PID Calibration"
        )

        # === 2.7.5: Bed Surface ===
        surface_type = self.ui.radiolist(
            "Bed surface type:\n\n"
            "(Used for macro hints and slicer recommendations)",
            [
                ("pei_textured", "PEI Textured", current_surface == "pei_textured"),
                ("pei_smooth", "PEI Smooth", current_surface == "pei_smooth"),
                ("glass", "Glass", current_surface == "glass"),
                ("fr4", "FR4/G10", current_surface == "fr4"),
                ("garolite", "Garolite", current_surface == "garolite"),
                ("buildtak", "BuildTak", current_surface == "buildtak"),
                ("other", "Other", current_surface == "other" or not current_surface),
            ],
            title="Heated Bed - Surface Type"
        )
        if surface_type is None:
            return

        # Save all settings
        self.state.set("heater_bed.heater_pin", heater_pin)  # Changed from heater_port
        self.state.set("heater_bed.max_power", float(max_power or 1.0))
        self.state.set("heater_bed.pwm_cycle_time", float(pwm_cycle_time or 0.0166))
        self.state.set("heater_bed.sensor_port", sensor_port)
        self.state.set("heater_bed.sensor_type", sensor_type or "Generic 3950")
        if pullup_resistor:
            self.state.set("heater_bed.pullup_resistor", pullup_resistor)
        self.state.set("heater_bed.min_temp", int(min_temp or 0))
        self.state.set("heater_bed.max_temp", int(max_temp or 120))
        self.state.set("heater_bed.control", control or "pid")
        self.state.set("heater_bed.pid_Kp", 0.0)
        self.state.set("heater_bed.pid_Ki", 0.0)
        self.state.set("heater_bed.pid_Kd", 0.0)
        self.state.set("heater_bed.surface_type", surface_type)
        self.state.save()

        pullup_text = f"\nPullup: {pullup_resistor}Ω" if pullup_resistor else ""
        self.ui.msgbox(
            f"Heated bed configured!\n\n"
            f"Heater pin: {heater_pin}\n"
            f"Max power: {max_power}\n"
            f"Thermistor port: {sensor_port}\n"
            f"Thermistor type: {sensor_type}{pullup_text}\n"
            f"Temp range: {min_temp}°C - {max_temp}°C\n"
            f"Control: {control}\n"
            f"Surface: {surface_type}\n\n"
            "Remember to run PID_CALIBRATE HEATER=heater_bed TARGET=60",
            title="Configuration Saved"
        )

    def _fans_setup(self) -> None:
        """Configure fans."""
        has_toolboard = self.state.get("mcu.toolboard.connection_type") or \
                        self.state.get("mcu.toolboard.enabled", False)

        # === PART COOLING FAN ===
        # Load saved location
        current_part_location = self.state.get("fans.part_cooling.location", "")
        if has_toolboard:
            # Default to toolboard if no saved value, otherwise use saved value
            default_is_toolboard = (current_part_location == "toolboard") or (not current_part_location)
            part_location = self.ui.radiolist(
                "Part cooling fan connected to:",
                [
                    ("mainboard", "Mainboard", current_part_location == "mainboard"),
                    ("toolboard", "Toolboard", default_is_toolboard),
                ],
                title="Fans - Part Cooling Location"
            )
        else:
            part_location = "mainboard"

        # Part cooling fan pin selection
        board_type = "toolboards" if part_location == "toolboard" else "boards"
        fan_ports = self._get_board_ports("fan_ports", board_type)
        # Check both possible keys for current value
        current_pin = self.state.get(f"fans.part_cooling.pin_{part_location}", "") or \
                      self.state.get("fans.part_cooling.pin_mainboard", "") or \
                      self.state.get("fans.part_cooling.pin_toolboard", "")
        if fan_ports:
            # Try to find "Part Cooling" or "FAN0" as default
            part_cooling_ports = [(p, l, p == current_pin or "Part" in l or p == "FAN0")
                                  for p, l, d in fan_ports]
            part_pin = self.ui.radiolist(
                f"Select part cooling fan pin on {part_location}:",
                part_cooling_ports,
                title="Fans - Part Cooling Pin"
            )
        else:
            part_pin = self.ui.inputbox(
                f"Enter part cooling fan pin on {part_location}:",
                default=current_pin or "FAN0",
                title="Fans - Part Cooling Pin"
            )
        if part_pin is None:
            return

        # Part cooling fan parameters
        current_max_power = self.state.get("fans.part_cooling.max_power", 1.0)
        max_power = self.ui.inputbox(
            "Part cooling fan max power (0.1-1.0):",
            default=str(current_max_power),
            title="Fans - Part Cooling Max Power"
        )
        if max_power is None:
            return

        current_kick_start = self.state.get("fans.part_cooling.kick_start_time", 0.5)
        kick_start_time = self.ui.inputbox(
            "Kick start time (seconds):\n\n"
            "(Time to run at full speed to start fan)",
            default=str(current_kick_start),
            title="Fans - Part Cooling Kick Start"
        )
        if kick_start_time is None:
            return

        current_off_below = self.state.get("fans.part_cooling.off_below", 0.1)
        off_below = self.ui.inputbox(
            "Off below (PWM):\n\n"
            "(Minimum PWM for fan to spin, usually 0.1)",
            default=str(current_off_below),
            title="Fans - Part Cooling Off Below"
        )
        if off_below is None:
            return

        current_cycle = self.state.get("fans.part_cooling.cycle_time", 0.010)
        cycle_time = self.ui.inputbox(
            "Cycle time (seconds):\n\n"
            "(PWM cycle time, usually 0.010)",
            default=str(current_cycle),
            title="Fans - Part Cooling Cycle Time"
        )
        if cycle_time is None:
            return

        # === HOTEND FAN ===
        # Load saved location
        current_hotend_location = self.state.get("fans.hotend.location", "")
        if has_toolboard:
            # Default to toolboard if no saved value, otherwise use saved value
            default_is_toolboard = (current_hotend_location == "toolboard") or (not current_hotend_location)
            hotend_location = self.ui.radiolist(
                "Hotend fan connected to:",
                [
                    ("mainboard", "Mainboard", current_hotend_location == "mainboard"),
                    ("toolboard", "Toolboard", default_is_toolboard),
                ],
                title="Fans - Hotend Location"
            )
        else:
            hotend_location = "mainboard"

        # Hotend fan pin selection
        board_type = "toolboards" if hotend_location == "toolboard" else "boards"
        fan_ports = self._get_board_ports("fan_ports", board_type)
        # Check both possible keys for current value
        current_pin = self.state.get(f"fans.hotend.pin_{hotend_location}", "") or \
                      self.state.get("fans.hotend.pin_mainboard", "") or \
                      self.state.get("fans.hotend.pin_toolboard", "")
        if fan_ports:
            # Try to find "Hotend" or "FAN1" as default, exclude already used pin
            hotend_fan_ports = [(p, l, p == current_pin or "Hotend" in l or p == "FAN1")
                               for p, l, d in fan_ports if p != part_pin or hotend_location != part_location]
            if hotend_fan_ports:
                hotend_pin = self.ui.radiolist(
                    f"Select hotend fan pin on {hotend_location}:",
                    hotend_fan_ports,
                    title="Fans - Hotend Pin"
                )
            else:
                hotend_pin = self.ui.inputbox(
                    f"Enter hotend fan pin on {hotend_location}:",
                    default=current_pin or "FAN1",
                    title="Fans - Hotend Pin"
                )
        else:
            hotend_pin = self.ui.inputbox(
                f"Enter hotend fan pin on {hotend_location}:",
                default=current_pin or "FAN1",
                title="Fans - Hotend Pin"
            )
        if hotend_pin is None:
            return

        # Hotend fan parameters
        current_heater = self.state.get("fans.hotend.heater", "extruder")
        heater = self.ui.inputbox(
            "Heater to monitor:\n\n"
            "(Usually 'extruder')",
            default=current_heater,
            title="Fans - Hotend Heater"
        )
        if heater is None:
            return

        current_heater_temp = self.state.get("fans.hotend.heater_temp", 50)
        heater_temp = self.ui.inputbox(
            "Temperature to turn on fan (°C):",
            default=str(current_heater_temp),
            title="Fans - Hotend Heater Temp"
        )
        if heater_temp is None:
            return

        current_fan_speed = self.state.get("fans.hotend.fan_speed", 1.0)
        fan_speed = self.ui.inputbox(
            "Fan speed (0.1-1.0):",
            default=str(current_fan_speed),
            title="Fans - Hotend Fan Speed"
        )
        if fan_speed is None:
            return

        # === CONTROLLER FAN ===
        # Load saved state
        current_controller_enabled = self.state.get("fans.controller.enabled", False)
        has_controller_fan = self.ui.yesno(
            "Do you have an electronics cooling fan?",
            title="Fans - Controller",
            default_no=not current_controller_enabled
        )

        controller_pin = None
        if has_controller_fan:
            # Controller fan is always on mainboard
            fan_ports = self._get_board_ports("fan_ports", "boards")
            current_pin = self.state.get("fans.controller.pin", "")
            if fan_ports:
                # Exclude already used pins
                used_pins = []
                if part_location == "mainboard":
                    used_pins.append(part_pin)
                if hotend_location == "mainboard":
                    used_pins.append(hotend_pin)
                controller_ports = [(p, l, p == current_pin or p == "FAN2")
                                   for p, l, d in fan_ports if p not in used_pins]
                if controller_ports:
                    controller_pin = self.ui.radiolist(
                        "Select controller fan pin on mainboard:",
                        controller_ports,
                        title="Fans - Controller Pin"
                    )
            if not controller_pin:
                controller_pin = self.ui.inputbox(
                    "Enter controller fan pin on mainboard:",
                    default=current_pin or "FAN2",
                    title="Fans - Controller Pin"
                )
            if controller_pin is None:
                return

            # Controller fan parameters
            current_kick_start = self.state.get("fans.controller.kick_start_time", 0.5)
            controller_kick_start = self.ui.inputbox(
                "Controller fan kick start time (seconds):",
                default=str(current_kick_start),
                title="Fans - Controller Kick Start"
            )
            if controller_kick_start is None:
                return

            current_stepper = self.state.get("fans.controller.stepper", "stepper_x")
            stepper = self.ui.inputbox(
                "Stepper to monitor for activity:\n\n"
                "(Usually 'stepper_x')",
                default=current_stepper,
                title="Fans - Controller Stepper"
            )
            if stepper is None:
                return

            current_idle_timeout = self.state.get("fans.controller.idle_timeout", 60)
            idle_timeout = self.ui.inputbox(
                "Idle timeout (seconds):\n\n"
                "(Time before fan turns off after stepper stops)",
                default=str(current_idle_timeout),
                title="Fans - Controller Idle Timeout"
            )
            if idle_timeout is None:
                return

            current_idle_speed = self.state.get("fans.controller.idle_speed", 0.5)
            idle_speed = self.ui.inputbox(
                "Idle speed (0.0-1.0):\n\n"
                "(Speed when idle but not off)",
                default=str(current_idle_speed),
                title="Fans - Controller Idle Speed"
            )
            if idle_speed is None:
                return

        # === ADDITIONAL FANS ===
        additional_fans = []
        if self.ui.yesno(
            "Do you have additional fans?\n\n"
            "Examples:\n"
            "• Exhaust fan\n"
            "• RSCS (Remote Side Cooling)\n"
            "• Nevermore/chamber filter\n"
            "• Bed fans",
            title="Additional Fans"
        ):
            while True:
                fan_name = self.ui.inputbox(
                    "Fan name (e.g., exhaust_fan, nevermore):\n\n"
                    "(Leave empty to finish)",
                    default="",
                    title="Add Fan"
                )

                if not fan_name:
                    break

                # Multi-pin support
                is_multi_pin = self.ui.yesno(
                    f"Does '{fan_name}' use multiple pins?\n\n"
                    "(e.g., two fans running together as one)",
                    title=f"{fan_name} - Multi-Pin"
                )

                fan_config = {"name": fan_name}

                if is_multi_pin:
                    # For multi-pin, need to select multiple ports
                    fan_ports = self._get_board_ports("fan_ports", "boards")
                    if fan_ports:
                        pins_list = []
                        self.ui.msgbox(
                            f"Select fan ports for '{fan_name}'.\n\n"
                            "You'll select them one at a time.",
                            title=f"{fan_name} - Multi-Pin Setup"
                        )
                        while True:
                            port = self.ui.radiolist(
                                f"Select a fan port for '{fan_name}':\n"
                                f"Currently selected: {', '.join(pins_list) if pins_list else 'none'}",
                                [(p, l, False) for p, l, d in fan_ports if p not in pins_list],
                                title=f"{fan_name} - Select Port"
                            )
                            if port:
                                pins_list.append(port)
                            if not self.ui.yesno(f"Add another port to '{fan_name}'?", title="More Ports"):
                                break
                        pins = ", ".join(pins_list)
                    else:
                        pins = self.ui.inputbox(
                            f"Enter pins for '{fan_name}' (comma-separated):\n\n"
                            "Example: PA15, PB11",
                            default="",
                            title=f"{fan_name} - Pins"
                        )
                    fan_config["pin_type"] = "multi_pin"
                    fan_config["pins"] = pins
                    fan_config["multi_pin_name"] = fan_name
                else:
                    # Single pin fan - select from available ports
                    fan_ports = self._get_board_ports("fan_ports", "boards")
                    if fan_ports:
                        port = self.ui.radiolist(
                            f"Select fan port for '{fan_name}':",
                            [(p, l, False) for p, l, d in fan_ports],
                            title=f"{fan_name} - Port"
                        )
                        if port:
                            fan_config["pin_type"] = "single"
                            fan_config["port"] = port
                    else:
                        pin = self.ui.inputbox(
                            f"Pin for '{fan_name}':",
                            default="",
                            title=f"{fan_name} - Pin"
                        )
                        fan_config["pin_type"] = "single"
                        fan_config["pin"] = pin

                additional_fans.append(fan_config)

                if not self.ui.yesno("Add another fan?", title="More Fans"):
                    break

        # Multi-pin groups (for hotend cooling with multiple fans, etc.)
        multi_pins = []
        for fan in additional_fans:
            if fan.get("pin_type") == "multi_pin":
                multi_pins.append({
                    "name": fan["multi_pin_name"],
                    "pins": fan["pins"]
                })

        # Save part cooling fan
        # State keys must match config-sections.yaml template expectations
        self.state.set("fans.part_cooling.location", part_location)
        if part_location == "toolboard":
            self.state.set("fans.part_cooling.pin_toolboard", part_pin)
            self.state.delete("fans.part_cooling.pin_mainboard")  # Clear other key
        else:
            self.state.set("fans.part_cooling.pin_mainboard", part_pin)
            self.state.delete("fans.part_cooling.pin_toolboard")  # Clear other key
        self.state.set("fans.part_cooling.max_power", float(max_power or 1.0))
        self.state.set("fans.part_cooling.kick_start_time", float(kick_start_time or 0.5))
        self.state.set("fans.part_cooling.off_below", float(off_below or 0.1))
        self.state.set("fans.part_cooling.cycle_time", float(cycle_time or 0.010))

        # Save hotend fan
        # State keys must match config-sections.yaml template expectations
        self.state.set("fans.hotend.location", hotend_location)
        if hotend_location == "toolboard":
            self.state.set("fans.hotend.pin_toolboard", hotend_pin)
            self.state.delete("fans.hotend.pin_mainboard")  # Clear other key
        else:
            self.state.set("fans.hotend.pin_mainboard", hotend_pin)
            self.state.delete("fans.hotend.pin_toolboard")  # Clear other key
        self.state.set("fans.hotend.heater", heater or "extruder")
        self.state.set("fans.hotend.heater_temp", int(heater_temp or 50))
        self.state.set("fans.hotend.fan_speed", float(fan_speed or 1.0))

        # Save controller fan
        self.state.set("fans.controller.enabled", has_controller_fan)
        if has_controller_fan and controller_pin:
            self.state.set("fans.controller.pin", controller_pin)  # Changed from port
            self.state.set("fans.controller.kick_start_time", float(controller_kick_start or 0.5))
            self.state.set("fans.controller.stepper", stepper or "stepper_x")
            self.state.set("fans.controller.idle_timeout", int(idle_timeout or 60))
            self.state.set("fans.controller.idle_speed", float(idle_speed or 0.5))
        else:
            self.state.delete("fans.controller.pin")
            self.state.delete("fans.controller.kick_start_time")
            self.state.delete("fans.controller.stepper")
            self.state.delete("fans.controller.idle_timeout")
            self.state.delete("fans.controller.idle_speed")

        if additional_fans:
            self.state.set("fans.additional_fans", additional_fans)
        if multi_pins:
            self.state.set("advanced.multi_pins", multi_pins)

        self.state.save()

        summary = (
            f"Part cooling: {part_location} ({part_pin})\n"
            f"Hotend: {hotend_location} ({hotend_pin})\n"
            f"Controller fan: {'Yes (' + controller_pin + ')' if has_controller_fan and controller_pin else 'No'}"
        )
        if additional_fans:
            summary += f"\nAdditional: {', '.join(f['name'] for f in additional_fans)}"

        self.ui.msgbox(
            f"Fans configured!\n\n{summary}",
            title="Configuration Saved"
        )

    def _probe_setup(self) -> None:
        """Configure probe."""
        probe_types = [
            ("none", "No Probe"),
            ("tap", "Voron Tap"),
            ("klicky", "Klicky / Euclid"),
            ("bltouch", "BLTouch / 3DTouch"),
            ("inductive", "Inductive (PINDA)"),
            ("beacon", "Beacon (eddy current)"),
            ("cartographer", "Cartographer"),
            ("btt_eddy", "BTT Eddy"),
        ]

        probe_type = self.ui.radiolist(
            "Select your probe type:",
            [(k, v, k == "tap") for k, v in probe_types],
            title="Probe - Type"
        )

        if probe_type == "none":
            self.state.delete("probe")
            self.state.save()
            return

        # Eddy current probes have their own serial connection
        eddy_probes = ["beacon", "cartographer", "btt_eddy"]

        # Offsets (for non-Tap probes)
        if probe_type != "tap":
            x_offset = self.ui.inputbox(
                "Probe X offset from nozzle (mm):",
                default="0",
                title="Probe - X Offset"
            )
            y_offset = self.ui.inputbox(
                "Probe Y offset from nozzle (mm):",
                default="0" if probe_type not in eddy_probes else "25",
                title="Probe - Y Offset"
            )
        else:
            x_offset = "0"
            y_offset = "0"

        # Eddy probe specific settings
        serial = None
        homing_mode = None
        contact_max_temp = None
        mesh_main_direction = None
        mesh_runs = None

        if probe_type in eddy_probes:
            # Serial detection
            self.ui.infobox("Scanning for probe serial...", title="Detecting")
            import time
            time.sleep(1)

            # Try to find serial device
            serial_dir = Path("/dev/serial/by-id")
            serial_devices = []
            if serial_dir.exists():
                probe_patterns = {
                    "beacon": "Beacon",
                    "cartographer": "Cartographer",
                    "btt_eddy": "BTT"
                }
                pattern = probe_patterns.get(probe_type, "")
                serial_devices = [str(d) for d in serial_dir.iterdir()
                                  if pattern.lower() in d.name.lower()]

            if serial_devices:
                # Build mapping: short_name -> full_path
                serial_map = {}
                device_items = []
                for i, d in enumerate(serial_devices):
                    short_name = self._format_serial_name(d)
                    tag = f"{i+1}. {short_name}"
                    serial_map[tag] = d
                    device_items.append((tag, "", i == 0))

                device_items.append(("manual", "Enter manually", False))

                selected = self.ui.radiolist(
                    f"Select {probe_type} serial device:",
                    device_items,
                    title="Probe - Serial"
                )

                # Map selection back to full path
                if selected and selected in serial_map:
                    serial = serial_map[selected]
                elif selected == "manual":
                    serial = self.ui.inputbox(
                        "Enter serial path:",
                        default="/dev/serial/by-id/usb-"
                    )
                else:
                    serial = None
            else:
                serial = self.ui.inputbox(
                    f"Enter {probe_type} serial path:\n\n"
                    "(No devices auto-detected)",
                    default="/dev/serial/by-id/usb-"
                )

            # Homing mode selection
            if probe_type == "beacon":
                homing_mode = self.ui.radiolist(
                    "Beacon homing mode:",
                    [
                        ("contact", "Contact (nozzle touches bed)", True),
                        ("proximity", "Proximity (non-contact)", False),
                    ],
                    title="Beacon - Homing Mode"
                )

                if homing_mode == "contact":
                    contact_max_temp = self.ui.inputbox(
                        "Max hotend temp for contact probing (°C):\n\n"
                        "(Prevents damage from hot nozzle contact)",
                        default="180",
                        title="Beacon - Contact Temp"
                    )

            elif probe_type == "cartographer":
                homing_mode = self.ui.radiolist(
                    "Cartographer homing mode:",
                    [
                        ("touch", "Touch (contact homing)", True),
                        ("scan", "Scan (proximity homing)", False),
                    ],
                    title="Cartographer - Homing Mode"
                )

            elif probe_type == "btt_eddy":
                homing_mode = self.ui.radiolist(
                    "BTT Eddy mesh method:",
                    [
                        ("rapid_scan", "Rapid Scan (fast)", True),
                        ("scan", "Standard Scan", False),
                    ],
                    title="BTT Eddy - Mesh Method"
                )

            # Mesh settings for eddy probes
            mesh_main_direction = self.ui.radiolist(
                "Mesh scan direction:",
                [
                    ("x", "X direction", False),
                    ("y", "Y direction", True),
                ],
                title="Probe - Mesh Direction"
            )

            mesh_runs = self.ui.radiolist(
                "Mesh scan passes:",
                [
                    ("1", "1 pass (faster)", True),
                    ("2", "2 passes (more accurate)", False),
                ],
                title="Probe - Mesh Runs"
            )

        # Location for non-eddy probes
        has_toolboard = self.state.get("mcu.toolboard.connection_type")
        location = None
        if probe_type not in eddy_probes:
            if has_toolboard:
                location = self.ui.radiolist(
                    "Probe connected to:",
                    [
                        ("mainboard", "Mainboard", False),
                        ("toolboard", "Toolboard", True),
                    ],
                    title="Probe - Connection"
                )
            else:
                location = "mainboard"

        # Save
        self.state.set("probe.probe_type", probe_type)
        self.state.set("probe.x_offset", float(x_offset or 0))
        self.state.set("probe.y_offset", float(y_offset or 0))

        if serial:
            self.state.set("probe.serial", serial)
        if homing_mode:
            self.state.set("probe.homing_mode", homing_mode)
        if contact_max_temp:
            self.state.set("probe.contact_max_hotend_temperature", int(contact_max_temp))
        if mesh_main_direction:
            self.state.set("probe.mesh_main_direction", mesh_main_direction)
        if mesh_runs:
            self.state.set("probe.mesh_runs", int(mesh_runs))
        if location:
            self.state.set("probe.location", location)

        self.state.save()

        # Build summary
        summary = f"Type: {probe_type}\nOffset: X={x_offset}, Y={y_offset}"
        if serial:
            summary += f"\nSerial: {Path(serial).name if '/' in serial else serial}"
        if homing_mode:
            summary += f"\nHoming: {homing_mode}"
        if probe_type in eddy_probes:
            summary += f"\nMesh: {mesh_main_direction} direction, {mesh_runs} run(s)"

        self.ui.msgbox(
            f"Probe configured!\n\n{summary}\n\n"
            "Remember to run PROBE_CALIBRATE for Z offset",
            title="Configuration Saved"
        )

    def _homing_setup(self) -> None:
        """Configure homing."""
        probe_type = self.state.get("probe.probe_type", "none")

        # Homing method based on probe
        if probe_type in ["beacon", "cartographer"]:
            methods = [
                ("beacon_contact", "Beacon Contact", True),
                ("homing_override", "Custom Homing Override", False),
            ]
        else:
            methods = [
                ("safe_z_home", "Safe Z Home (standard)", True),
                ("homing_override", "Homing Override (sensorless)", False),
            ]

        method = self.ui.radiolist(
            "Z homing method:",
            methods,
            title="Homing - Method"
        )

        # Z hop
        z_hop = self.ui.inputbox(
            "Z hop height for homing (mm):",
            default="10",
            title="Homing - Z Hop"
        )

        # Save
        self.state.set("homing.homing_method", method or "safe_z_home")
        self.state.set("homing.z_hop", int(z_hop or 10))
        self.state.save()

        self.ui.msgbox(
            f"Homing configured!\n\n"
            f"Method: {method}\n"
            f"Z hop: {z_hop}mm",
            title="Configuration Saved"
        )

    def _bed_leveling_setup(self) -> None:
        """Configure bed leveling."""
        z_count = self.state.get("stepper_z.z_motor_count", 1)

        # Leveling type based on Z motor count
        if z_count == 4:
            leveling_options = [
                ("qgl", "Quad Gantry Level", True),
                ("none", "None", False),
            ]
        elif z_count >= 2:
            leveling_options = [
                ("z_tilt", "Z Tilt Adjust", True),
                ("none", "None", False),
            ]
        else:
            leveling_options = [
                ("none", "None (single Z)", True),
            ]

        leveling_type = self.ui.radiolist(
            "Bed leveling type:",
            leveling_options,
            title="Bed Leveling - Type"
        )

        # Bed mesh
        enable_mesh = self.ui.yesno(
            "Enable bed mesh?",
            title="Bed Leveling - Mesh",
            default_no=False
        )

        if enable_mesh:
            probe_count = self.ui.inputbox(
                "Mesh probe count (e.g., 5,5):",
                default="5,5",
                title="Bed Mesh - Probe Count"
            )
        else:
            probe_count = "5,5"

        # Save
        self.state.set("bed_leveling.leveling_type", leveling_type or "none")
        self.state.set("bed_leveling.bed_mesh.enabled", enable_mesh)
        self.state.set("bed_leveling.bed_mesh.probe_count", probe_count)
        self.state.save()

        self.ui.msgbox(
            f"Bed leveling configured!\n\n"
            f"Type: {leveling_type}\n"
            f"Mesh: {'Enabled' if enable_mesh else 'Disabled'}\n"
            f"Probe count: {probe_count}",
            title="Configuration Saved"
        )

    def _temperature_sensors_setup(self) -> None:
        """Configure temperature sensors."""
        sensors = []

        # Load saved state for MCU/host/toolboard sensors
        current_mcu_enabled = self.state.get("temperature_sensors.mcu_main.enabled", False)
        current_host_enabled = self.state.get("temperature_sensors.host.enabled", False)
        current_toolboard_enabled = self.state.get("temperature_sensors.toolboard.enabled", False)

        # MCU temperature sensor (always available)
        if self.ui.yesno(
            "Add MCU temperature sensor?\n\n"
            "Shows mainboard MCU temperature in Klipper.",
            title="Temperature Sensors",
            default_no=not current_mcu_enabled
        ):
            sensors.append({
                "name": "mcu_temp",
                "type": "temperature_mcu",
                "mcu": "mcu"
            })
            self.state.set("temperature_sensors.mcu_main.enabled", True)
        else:
            self.state.set("temperature_sensors.mcu_main.enabled", False)

        # Host (Raspberry Pi) temperature
        if self.ui.yesno(
            "Add host (Raspberry Pi) temperature sensor?",
            title="Temperature Sensors",
            default_no=not current_host_enabled
        ):
            sensors.append({
                "name": "host_temp",
                "type": "temperature_host"
            })
            self.state.set("temperature_sensors.host.enabled", True)
        else:
            self.state.set("temperature_sensors.host.enabled", False)

        # Toolboard MCU temperature (if toolboard configured)
        has_toolboard = self.state.get("mcu.toolboard.connection_type")
        if has_toolboard:
            toolboard_id = self.state.get("mcu.toolboard.board_type", "")
            toolboard_name = self._get_board_name(toolboard_id, "toolboards") if toolboard_id else "toolboard"
            if self.ui.yesno(
                f"Add toolboard MCU temperature sensor?\n\n"
                f"Shows {toolboard_name} MCU temperature in Klipper.",
                title="Temperature Sensors - Toolboard",
                default_no=not current_toolboard_enabled
            ):
                sensors.append({
                    "name": "toolboard_temp",
                    "type": "temperature_mcu",
                    "mcu": "toolboard"
                })
                self.state.set("temperature_sensors.toolboard.enabled", True)
            else:
                self.state.set("temperature_sensors.toolboard.enabled", False)
        else:
            # Clear toolboard sensor state if no toolboard configured
            self.state.delete("temperature_sensors.toolboard")

        # Chamber temperature sensor
        # Load saved state
        current_chamber_enabled = self.state.get("temperature_sensors.chamber.enabled", False)
        current_chamber_type = self.state.get("temperature_sensors.chamber.sensor_type", "")
        current_chamber_location = self.state.get("temperature_sensors.chamber.sensor_location", "")
        current_chamber_port = self.state.get("temperature_sensors.chamber.sensor_port_mainboard", "")

        if self.ui.yesno(
            "Do you have a chamber temperature sensor?",
            title="Temperature Sensors",
            default_no=not current_chamber_enabled
        ):
            # Sensor type
            sensor_type = self.ui.radiolist(
                "Chamber sensor type:",
                [
                    ("Generic 3950", "Generic 3950 (NTC)", current_chamber_type == "Generic 3950" or not current_chamber_type),
                    ("ATC Semitec 104GT-2", "ATC Semitec 104GT-2", current_chamber_type == "ATC Semitec 104GT-2"),
                    ("PT1000", "PT1000", current_chamber_type == "PT1000"),
                    ("DS18B20", "DS18B20 (1-wire)", current_chamber_type == "DS18B20"),
                ],
                title="Chamber Sensor Type"
            )
            if sensor_type is None:
                return

            # Sensor location (mainboard or rpi)
            # Default to mainboard if no saved value
            default_is_rpi = current_chamber_location == "rpi"
            sensor_location = self.ui.radiolist(
                "Chamber sensor connected to:",
                [
                    ("mainboard", "Mainboard", current_chamber_location == "mainboard" or not current_chamber_location),
                    ("rpi", "Raspberry Pi GPIO", default_is_rpi),
                ],
                title="Chamber Sensor Location"
            )
            if sensor_location is None:
                return

            sensor_pin = None
            pullup_resistor = None

            if sensor_location == "mainboard":
                # Use board template port selection
                sensor_ports = self._get_board_ports("thermistor_ports", "boards", current_chamber_port)
                if sensor_ports:
                    sensor_port = self.ui.radiolist(
                        "Select chamber sensor port on mainboard:",
                        sensor_ports,
                        title="Chamber Sensor Port"
                    )
                else:
                    sensor_port = self.ui.inputbox(
                        "Enter chamber sensor port on mainboard:",
                        default=current_chamber_port or "",
                        title="Chamber Sensor Port"
                    )

                if sensor_port is None:
                    return
                sensor_pin = sensor_port

                # Pullup resistor (only for NTC sensors, not PT1000 or DS18B20)
                if sensor_type not in ["PT1000", "DS18B20"]:
                    current_pullup = self.state.get("temperature_sensors.chamber.pullup_resistor", 4700)
                    pullup_resistor = self.ui.radiolist(
                        "Chamber thermistor pullup resistor value:\n\n"
                        "(Most mainboards use 4.7kΩ standard)",
                        [
                            ("4700", "4.7kΩ (standard)", current_pullup == 4700),
                            ("2200", "2.2kΩ", current_pullup == 2200),
                            ("10000", "10kΩ", current_pullup == 10000),
                            ("custom", "Enter custom value", False),
                        ],
                        title="Chamber Sensor - Pullup Resistor"
                    )
                    if pullup_resistor == "custom":
                        pullup_resistor = self.ui.inputbox(
                            "Enter pullup resistor value (Ω):",
                            default=str(current_pullup),
                            title="Chamber Sensor - Custom Pullup"
                        )
                    if pullup_resistor:
                        pullup_resistor = int(pullup_resistor)
            else:  # rpi
                # For RPi, only DS18B20 uses GPIO pin (gpio4 default)
                if sensor_type == "DS18B20":
                    current_rpi_pin = self.state.get("temperature_sensors.chamber.sensor_pin_rpi", "gpio4")
                    sensor_pin = self.ui.inputbox(
                        "Raspberry Pi GPIO pin (e.g., gpio4):",
                        default=current_rpi_pin,
                        title="Chamber Sensor - RPi GPIO"
                    )
                else:
                    # For NTC on RPi, still need a pin
                    current_rpi_pin = self.state.get("temperature_sensors.chamber.sensor_pin_rpi", "")
                    sensor_pin = self.ui.inputbox(
                        "Raspberry Pi GPIO pin:",
                        default=current_rpi_pin,
                        title="Chamber Sensor - RPi GPIO"
                    )
                    # Pullup resistor for NTC on RPi
                    if sensor_type not in ["PT1000"]:
                        current_pullup = self.state.get("temperature_sensors.chamber.pullup_resistor", 4700)
                        pullup_resistor = self.ui.radiolist(
                            "Chamber thermistor pullup resistor value:",
                            [
                                ("4700", "4.7kΩ (standard)", current_pullup == 4700),
                                ("2200", "2.2kΩ", current_pullup == 2200),
                                ("10000", "10kΩ", current_pullup == 10000),
                                ("custom", "Enter custom value", False),
                            ],
                            title="Chamber Sensor - Pullup Resistor"
                        )
                        if pullup_resistor == "custom":
                            pullup_resistor = self.ui.inputbox(
                                "Enter pullup resistor value (Ω):",
                                default=str(current_pullup),
                                title="Chamber Sensor - Custom Pullup"
                            )
                        if pullup_resistor:
                            pullup_resistor = int(pullup_resistor)

            if sensor_pin:
                # Save to state
                self.state.set("temperature_sensors.chamber.enabled", True)
                self.state.set("temperature_sensors.chamber.sensor_type", sensor_type)
                self.state.set("temperature_sensors.chamber.sensor_location", sensor_location)
                if sensor_location == "mainboard":
                    self.state.set("temperature_sensors.chamber.sensor_port_mainboard", sensor_pin)
                    self.state.delete("temperature_sensors.chamber.sensor_pin_rpi")
                else:
                    self.state.set("temperature_sensors.chamber.sensor_pin_rpi", sensor_pin)
                    self.state.delete("temperature_sensors.chamber.sensor_port_mainboard")
                if pullup_resistor:
                    self.state.set("temperature_sensors.chamber.pullup_resistor", pullup_resistor)
                else:
                    self.state.delete("temperature_sensors.chamber.pullup_resistor")
                self.state.save()

                sensors.append({
                    "name": "chamber",
                    "type": "temperature_sensor",
                    "sensor_type": sensor_type,
                    "sensor_location": sensor_location,
                    "sensor_pin": sensor_pin,
                    "pullup_resistor": pullup_resistor
                })
        else:
            # Disable chamber sensor
            self.state.delete("temperature_sensors.chamber")
            self.state.save()

        # Additional sensors
        while self.ui.yesno(
            "Add another temperature sensor?",
            title="More Sensors",
            default_no=True
        ):
            name = self.ui.inputbox(
                "Sensor name:",
                default="",
                title="Sensor Name"
            )
            if not name:
                break

            sensor_type = self.ui.radiolist(
                f"Sensor type for '{name}':",
                [
                    ("Generic 3950", "Generic 3950 (NTC)", True),
                    ("ATC Semitec 104GT-2", "ATC Semitec 104GT-2", False),
                    ("PT1000", "PT1000", False),
                    ("DS18B20", "DS18B20 (1-wire)", False),
                ],
                title="Sensor Type"
            )

            sensor_pin = self.ui.inputbox(
                f"Pin for '{name}':",
                default="",
                title="Sensor Pin"
            )

            if sensor_pin:
                sensors.append({
                    "name": name,
                    "type": "temperature_sensor",
                    "sensor_type": sensor_type,
                    "sensor_pin": sensor_pin
                })

        # Save
        self.state.set("temperature_sensors", sensors)
        self.state.save()

        sensor_names = [s["name"] for s in sensors]
        self.ui.msgbox(
            f"Temperature sensors configured!\n\n"
            f"Sensors: {', '.join(sensor_names) if sensor_names else 'None'}",
            title="Configuration Saved"
        )

    def _leds_setup(self) -> None:
        """Configure LED strips."""
        leds = []

        if not self.ui.yesno(
            "Do you have LED strips (Neopixel/WS2812)?",
            title="LED Configuration"
        ):
            self.state.set("leds", [])
            self.state.save()
            return

        has_toolboard = self.state.get("mcu.toolboard.connection_type")

        while True:
            led_name = self.ui.inputbox(
                "LED strip name (e.g., status_led, chamber_led):\n\n"
                "(Leave empty to finish)",
                default="status_led" if not leds else "",
                title="Add LED"
            )

            if not led_name:
                break

            # Location
            if has_toolboard:
                location = self.ui.radiolist(
                    f"'{led_name}' connected to:",
                    [
                        ("mainboard", "Mainboard", False),
                        ("toolboard", "Toolboard", True),
                    ],
                    title=f"{led_name} - Location"
                )
            else:
                location = "mainboard"

            # Pin
            pin = self.ui.inputbox(
                f"Pin for '{led_name}':",
                default="PB0" if location == "mainboard" else "PB8",
                title=f"{led_name} - Pin"
            )

            # LED count
            chain_count = self.ui.inputbox(
                f"Number of LEDs in '{led_name}' chain:",
                default="1",
                title=f"{led_name} - Count"
            )

            # Color order
            color_order = self.ui.radiolist(
                f"Color order for '{led_name}':",
                [
                    ("GRB", "GRB (most common)", True),
                    ("RGB", "RGB", False),
                    ("GRBW", "GRBW (RGBW with green first)", False),
                    ("RGBW", "RGBW", False),
                ],
                title=f"{led_name} - Color Order"
            )

            leds.append({
                "name": led_name,
                "location": location,
                "pin": pin,
                "chain_count": int(chain_count or 1),
                "color_order": color_order
            })

            if not self.ui.yesno("Add another LED strip?", title="More LEDs"):
                break

        # Save
        self.state.set("leds", leds)
        self.state.save()

        led_names = [l["name"] for l in leds]
        self.ui.msgbox(
            f"LEDs configured!\n\n"
            f"Strips: {', '.join(led_names) if led_names else 'None'}",
            title="Configuration Saved"
        )

    def _filament_sensors_setup(self) -> None:
        """Configure filament sensors."""
        sensors = []

        if not self.ui.yesno(
            "Do you have a filament runout sensor?",
            title="Filament Sensor"
        ):
            self.state.set("filament_sensors", [])
            self.state.save()
            return

        has_toolboard = self.state.get("mcu.toolboard.connection_type")

        # Sensor type
        sensor_type = self.ui.radiolist(
            "Filament sensor type:",
            [
                ("switch", "Simple switch (runout only)", True),
                ("motion", "Motion sensor (detects movement)", False),
                ("encoder", "Encoder (measures filament)", False),
            ],
            title="Sensor Type"
        )

        # Location
        if has_toolboard:
            location = self.ui.radiolist(
                "Sensor connected to:",
                [
                    ("mainboard", "Mainboard", False),
                    ("toolboard", "Toolboard", True),
                ],
                title="Sensor Location"
            )
        else:
            location = "mainboard"

        # Pin
        pin = self.ui.inputbox(
            "Sensor pin:",
            default="PG11" if location == "mainboard" else "PB6",
            title="Sensor Pin"
        )

        sensors.append({
            "name": "filament_sensor",
            "type": sensor_type,
            "location": location,
            "pin": pin,
            "pause_on_runout": True
        })

        # Save
        self.state.set("filament_sensors", sensors)
        self.state.save()

        self.ui.msgbox(
            f"Filament sensor configured!\n\n"
            f"Type: {sensor_type}\n"
            f"Location: {location}\n"
            f"Pin: {pin}",
            title="Configuration Saved"
        )

    # -------------------------------------------------------------------------
    # Category 3: Tuning
    # -------------------------------------------------------------------------

    def tuning_menu(self) -> None:
        """Tuning and optimization menu."""
        while True:
            choice = self.ui.menu(
                "Tuning & Optimization\n\n"
                "Configure advanced features and calibration.",
                [
                    ("3.1", "TMC Autotune         (Motor optimization)"),
                    ("3.2", "Input Shaper         (Resonance compensation)"),
                    ("3.6", "Macros               (START_PRINT, etc.)"),
                    ("3.9", "Exclude Object       (Cancel individual objects)"),
                    ("3.10", "Arc Support         (G2/G3 commands)"),
                    ("B", "Back to Main Menu"),
                ],
                title="3. Tuning & Optimization",
            )

            if choice is None or choice == "B":
                break
            else:
                self.ui.msgbox(
                    f"Section {choice} coming soon!",
                    title=f"Section {choice}"
                )

    # -------------------------------------------------------------------------
    # Generate Config
    # -------------------------------------------------------------------------

    def generate_config(self) -> None:
        """Generate printer configuration files."""
        completion = self.state.get_completion_status()

        if not completion.get("mcu"):
            self.ui.msgbox(
                "Cannot generate config!\n\n"
                "Please configure at least the main MCU first.",
                title="Missing Configuration"
            )
            return

        if not self.ui.yesno(
            "Generate configuration files?\n\n"
            "This will create:\n"
            "• printer.cfg\n"
            "• gschpoozi/*.cfg files\n"
            "• user-overrides.cfg (if not exists)\n\n"
            "Existing gschpoozi/ folder will be overwritten.\n"
            "user-overrides.cfg will be preserved.",
            title="Generate Config"
        ):
            return

        self.ui.infobox("Generating configuration...", title="Please wait")

        try:
            from generator import ConfigGenerator

            generator = ConfigGenerator(state=self.state)
            files = generator.generate()
            written = generator.write_files(files)

            file_list = "\n".join(f"• {p.name}" for p in written[:8])
            if len(written) > 8:
                file_list += f"\n  ... and {len(written) - 8} more"

            self.ui.msgbox(
                f"Configuration generated!\n\n"
                f"Created {len(written)} files:\n{file_list}\n\n"
                f"Location: {generator.output_dir}",
                title="Generation Complete"
            )
        except Exception as e:
            self.ui.msgbox(
                f"Error generating configuration:\n\n{e}",
                title="Generation Failed"
            )


def main():
    """Entry point."""
    wizard = GschpooziWizard()
    sys.exit(wizard.run())


if __name__ == "__main__":
    main()

