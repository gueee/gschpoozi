#!/usr/bin/env python3
"""
main.py - gschpoozi Configuration Wizard Entry Point

This is the main entry point for the Klipper configuration wizard.
Run with: python3 scripts/wizard/main.py

This version uses a skeleton-driven architecture where:
- skeleton.json is the single source of truth for menus and fields
- MenuEngine handles navigation and rendering
- FieldRenderer handles individual field types
"""

import subprocess
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from wizard.skeleton import SkeletonLoader, SkeletonValidator
from wizard.engine import MenuEngine
from wizard.fields import FieldRenderer
from wizard.state import get_state, WizardState
from wizard.ui import WizardUI

# Find repo root (where templates/ lives)
SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_ROOT = SCRIPT_DIR.parent.parent


class GschpooziWizard:
    """Main wizard controller using skeleton-driven architecture."""

    VERSION = "3.0.0"

    def __init__(self):
        """Initialize the wizard."""
        self.ui = WizardUI(
            title="gschpoozi",
            backtitle=f"gschpoozi v{self.VERSION} - Klipper Configuration Wizard"
        )
        self.state = get_state()
        self.skeleton = SkeletonLoader()

        # Create field renderer
        self.field_renderer = FieldRenderer(
            skeleton=self.skeleton,
            state=self.state,
            ui=self.ui
        )

        # Create menu engine with action handlers
        self.engine = MenuEngine(
            skeleton=self.skeleton,
            state=self.state,
            ui=self.ui,
            field_renderer=self.field_renderer,
            action_handlers={
                'generate_config': self._generate_config,
                'save_and_exit': self._save_and_exit,
                'verify_klipper': self._verify_klipper,
                'verify_moonraker': self._verify_moonraker,
                'manage_components': self._manage_components,
                'can_setup': self._can_setup,
                'katapult_setup': self._katapult_setup,
                'install_mmu_software': self._install_mmu_software,
                'verify_services': self._verify_services,
            }
        )

    def run(self) -> None:
        """Run the main wizard loop."""
        try:
            # Show welcome message on first run
            if not self.state.get('wizard_started'):
                self._show_welcome()
                self.state.set('wizard_started', True)
                self.state.save()

            # Run main menu
            self.engine.run_menu('main')

            # Save state on exit
            self.state.save()

            self.ui.msgbox(
                "Configuration saved!\n\n"
                "Run 'python3 scripts/generate-config.py' to generate Klipper configs.",
                title="Goodbye"
            )

        except KeyboardInterrupt:
            self.state.save()
            print("\n\nWizard interrupted. State saved.")
            sys.exit(0)
        except Exception as e:
            self.state.save()
            self.ui.msgbox(f"Error: {e}\n\nState saved.", title="Error")
            raise

    def _show_welcome(self) -> None:
        """Show welcome message on first run."""
        self.ui.msgbox(
            "Welcome to gschpoozi v" + self.VERSION + "!\n\n"
            "This wizard will help you configure your Klipper printer.\n\n"
            "Navigate with:\n"
            "  - Arrow keys to move\n"
            "  - Space to select\n"
            "  - Enter to confirm\n"
            "  - Tab to switch between OK/Cancel\n\n"
            "Your progress is saved automatically.",
            title="Welcome"
        )

    def _generate_config(self) -> None:
        """Generate Klipper configuration files."""
        # First validate
        state_dict = self.state.get_all()
        validator = SkeletonValidator(self.skeleton, state_dict)
        result = validator.validate_all()

        if not result['valid']:
            error_text = "Cannot generate config - please fix these issues:\n\n"
            for e in result['errors'][:5]:  # Limit to 5 errors
                error_text += f"- {e}\n"
            if len(result['errors']) > 5:
                error_text += f"\n...and {len(result['errors']) - 5} more errors"
            self.ui.msgbox(error_text, title="Validation Failed")
            return

        # Show warnings if any
        if result['warnings']:
            warning_text = "Warnings (config will still be generated):\n\n"
            for w in result['warnings']:
                warning_text += f"- {w}\n"
            self.ui.msgbox(warning_text, title="Warnings")

        # Save state first
        self.state.save()

        # Run generator
        generator_script = REPO_ROOT / "scripts" / "generate-config.py"
        output_dir = Path.home() / "printer_data" / "config" / "gschpoozi"

        if not generator_script.exists():
            self.ui.msgbox(
                f"Generator script not found: {generator_script}",
                title="Error"
            )
            return

        # Ask for confirmation
        if not self.ui.yesno(
            f"Generate config files to:\n{output_dir}\n\nProceed?",
            title="Generate Config"
        ):
            return

        # Run generator
        self.ui.infobox("Generating configuration...", title="Please Wait")

        try:
            result = subprocess.run(
                [sys.executable, str(generator_script), "--output-dir", str(output_dir)],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                self.ui.msgbox(
                    f"Configuration generated successfully!\n\n"
                    f"Files written to: {output_dir}\n\n"
                    "Add the following to your printer.cfg:\n"
                    f"[include gschpoozi/*.cfg]",
                    title="Success"
                )
            else:
                error = result.stderr or result.stdout or "Unknown error"
                self.ui.msgbox(
                    f"Generator failed:\n\n{error[:500]}",
                    title="Error"
                )

        except subprocess.TimeoutExpired:
            self.ui.msgbox("Generator timed out", title="Error")
        except Exception as e:
            self.ui.msgbox(f"Generator error: {e}", title="Error")

    def _save_and_exit(self) -> str:
        """Save state and exit."""
        self.state.save()
        return 'quit'

    def _verify_klipper(self) -> None:
        """Verify Klipper installation."""
        self.ui.infobox("Checking Klipper...", title="Please Wait")

        try:
            # Check if Klipper service is running
            result = subprocess.run(
                ["systemctl", "is-active", "klipper"],
                capture_output=True,
                text=True
            )

            if result.stdout.strip() == "active":
                self.ui.msgbox(
                    "Klipper is running!\n\n"
                    "Service: active\n"
                    "Status: OK",
                    title="Klipper Status"
                )
            else:
                self.ui.msgbox(
                    "Klipper is NOT running.\n\n"
                    "Try: sudo systemctl start klipper",
                    title="Klipper Status"
                )

        except Exception as e:
            self.ui.msgbox(f"Could not check Klipper: {e}", title="Error")

    def _verify_moonraker(self) -> None:
        """Verify Moonraker installation."""
        self.ui.infobox("Checking Moonraker...", title="Please Wait")

        try:
            result = subprocess.run(
                ["systemctl", "is-active", "moonraker"],
                capture_output=True,
                text=True
            )

            if result.stdout.strip() == "active":
                self.ui.msgbox(
                    "Moonraker is running!\n\n"
                    "Service: active\n"
                    "Status: OK",
                    title="Moonraker Status"
                )
            else:
                self.ui.msgbox(
                    "Moonraker is NOT running.\n\n"
                    "Try: sudo systemctl start moonraker",
                    title="Moonraker Status"
                )

        except Exception as e:
            self.ui.msgbox(f"Could not check Moonraker: {e}", title="Error")

    def _manage_components(self) -> None:
        """Manage Klipper ecosystem components (KIAUH-style)."""
        components = [
            ("klipper", "Klipper", "Core printer firmware"),
            ("moonraker", "Moonraker", "API server for web interfaces"),
            ("mainsail", "Mainsail", "Modern web interface"),
            ("fluidd", "Fluidd", "Alternative web interface"),
            ("klipperscreen", "KlipperScreen", "Touchscreen interface"),
            ("crowsnest", "Crowsnest", "Webcam streaming"),
        ]

        while True:
            # Build menu with status
            items = []
            for comp_id, name, desc in components:
                # Check if installed
                try:
                    result = subprocess.run(
                        ["systemctl", "is-enabled", comp_id],
                        capture_output=True, text=True
                    )
                    status = "[installed]" if result.returncode == 0 else "[not installed]"
                except Exception:
                    status = "[unknown]"
                items.append((comp_id, f"{name} {status} - {desc}"))

            items.append(("B", "Back"))

            choice = self.ui.menu(
                "Select a component to manage:",
                items,
                title="Manage Klipper Components"
            )

            if choice is None or choice == "B":
                break

            # Show component actions
            self._show_component_actions(choice)

    def _show_component_actions(self, component: str) -> None:
        """Show actions for a specific component."""
        actions = [
            ("install", "Install", "Install this component"),
            ("update", "Update", "Update to latest version"),
            ("remove", "Remove", "Uninstall this component"),
            ("B", "Back", ""),
        ]

        choice = self.ui.menu(
            f"What would you like to do with {component}?",
            [(a[0], f"{a[1]} - {a[2]}") for a in actions if a[2]],
            title=f"Manage {component}"
        )

        if choice is None or choice == "B":
            return

        if choice == "install":
            self.ui.msgbox(
                f"To install {component}, run KIAUH:\n\n"
                "cd ~ && git clone https://github.com/dw-0/kiauh.git\n"
                "./kiauh/kiauh.sh\n\n"
                "Or visit: https://github.com/dw-0/kiauh",
                title="Install Instructions"
            )
        elif choice == "update":
            self.ui.msgbox(
                f"To update {component}:\n\n"
                f"cd ~/{component}\n"
                "git pull\n"
                f"sudo systemctl restart {component}",
                title="Update Instructions"
            )
        elif choice == "remove":
            self.ui.msgbox(
                f"To remove {component}, use KIAUH:\n\n"
                "./kiauh/kiauh.sh\n"
                "Select: Remove -> {component}",
                title="Remove Instructions"
            )

    def _can_setup(self) -> None:
        """Configure CAN bus interfaces."""
        items = [
            ("check", "Check CAN Status", "View current CAN interface configuration"),
            ("install", "Install can-utils", "Install CAN utilities package"),
            ("configure", "Configure CAN Interface", "Set up socketCAN interface"),
            ("query", "Query CAN Devices", "Find CAN-connected MCUs"),
            ("B", "Back"),
        ]

        while True:
            choice = self.ui.menu(
                "CAN Bus Interface Setup:",
                items,
                title="CAN Setup"
            )

            if choice is None or choice == "B":
                break

            if choice == "check":
                self._check_can_status()
            elif choice == "install":
                self._install_can_utils()
            elif choice == "configure":
                self._configure_can_interface()
            elif choice == "query":
                self._query_can_devices()

    def _check_can_status(self) -> None:
        """Check current CAN interface status."""
        try:
            result = subprocess.run(
                ["ip", "link", "show", "can0"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                self.ui.msgbox(
                    f"CAN Interface Status:\n\n{result.stdout}",
                    title="CAN Status"
                )
            else:
                self.ui.msgbox(
                    "CAN interface 'can0' not found.\n\n"
                    "You may need to configure the CAN interface first.",
                    title="CAN Status"
                )
        except Exception as e:
            self.ui.msgbox(f"Error checking CAN: {e}", title="Error")

    def _install_can_utils(self) -> None:
        """Install can-utils package."""
        self.ui.msgbox(
            "To install can-utils, run:\n\n"
            "sudo apt-get update\n"
            "sudo apt-get install can-utils\n\n"
            "This will provide candump, cansend, and other CAN tools.",
            title="Install can-utils"
        )

    def _configure_can_interface(self) -> None:
        """Configure CAN interface."""
        bitrate = self.ui.inputbox(
            "Enter CAN bitrate (common: 500000, 1000000):",
            default="1000000",
            title="CAN Bitrate"
        )
        if bitrate is None:
            return

        self.ui.msgbox(
            f"To configure CAN interface with bitrate {bitrate}:\n\n"
            "1. Create /etc/network/interfaces.d/can0:\n"
            f"   auto can0\n"
            f"   iface can0 can static\n"
            f"       bitrate {bitrate}\n"
            f"       up ip link set can0 txqueuelen 1024\n\n"
            "2. Or for temporary setup:\n"
            f"   sudo ip link set can0 type can bitrate {bitrate}\n"
            f"   sudo ip link set can0 txqueuelen 1024\n"
            f"   sudo ip link set up can0",
            title="Configure CAN"
        )

    def _query_can_devices(self) -> None:
        """Query for CAN-connected devices."""
        self.ui.infobox("Querying CAN devices...", title="Please Wait")
        try:
            result = subprocess.run(
                [sys.executable, Path.home() / "klipper" / "scripts" / "canbus_query.py", "can0"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                self.ui.msgbox(
                    f"CAN Devices Found:\n\n{result.stdout}",
                    title="CAN Devices"
                )
            else:
                self.ui.msgbox(
                    "No CAN devices found.\n\n"
                    "Make sure:\n"
                    "1. CAN interface is up (ip link show can0)\n"
                    "2. MCU has CAN firmware\n"
                    "3. Wiring is correct (CANH, CANL, GND)\n"
                    "4. Termination resistors are present",
                    title="CAN Devices"
                )
        except FileNotFoundError:
            self.ui.msgbox(
                "Klipper canbus_query.py not found.\n\n"
                "Try:\n"
                "python3 ~/klipper/scripts/canbus_query.py can0",
                title="Error"
            )
        except Exception as e:
            self.ui.msgbox(f"Error querying CAN: {e}", title="Error")

    def _katapult_setup(self) -> None:
        """Katapult (formerly CanBoot) and firmware flashing guidance."""
        items = [
            ("dfu", "DFU Flashing", "Flash MCU via USB DFU mode"),
            ("can", "CAN Flashing", "Flash MCU via CAN bus (requires Katapult)"),
            ("install", "Install Katapult", "Clone and build Katapult bootloader"),
            ("B", "Back"),
        ]

        while True:
            choice = self.ui.menu(
                "Firmware Flashing Options:",
                items,
                title="Katapult / Firmware"
            )

            if choice is None or choice == "B":
                break

            if choice == "dfu":
                self.ui.msgbox(
                    "DFU Flashing Guide:\n\n"
                    "1. Put MCU in DFU mode (usually: hold BOOT, press RESET)\n"
                    "2. Check with: lsusb (look for STM DFU device)\n"
                    "3. Flash with:\n"
                    "   make flash FLASH_DEVICE=0483:df11\n\n"
                    "Or use dfu-util:\n"
                    "   dfu-util -a 0 -D out/klipper.bin -s 0x08000000:leave",
                    title="DFU Flashing"
                )
            elif choice == "can":
                self.ui.msgbox(
                    "CAN Flashing Guide:\n\n"
                    "Requires Katapult bootloader already installed.\n\n"
                    "1. Put MCU in bootloader mode (double-tap reset)\n"
                    "2. Query for bootloader: python3 ~/katapult/scripts/flashtool.py -q\n"
                    "3. Flash firmware:\n"
                    "   python3 ~/katapult/scripts/flashtool.py -f ~/klipper/out/klipper.bin\n\n"
                    "See: https://github.com/Arksine/katapult",
                    title="CAN Flashing"
                )
            elif choice == "install":
                self.ui.msgbox(
                    "Install Katapult:\n\n"
                    "cd ~\n"
                    "git clone https://github.com/Arksine/katapult.git\n"
                    "cd katapult\n"
                    "make menuconfig  # Configure for your MCU\n"
                    "make\n\n"
                    "Then flash via DFU first time.",
                    title="Install Katapult"
                )

    def _install_mmu_software(self) -> None:
        """Install MMU software (Happy Hare, AFC)."""
        items = [
            ("happy_hare", "Happy Hare", "Universal MMU driver (ERCF, TradRack, etc.)"),
            ("afc", "AFC-Klipper-Add-On", "Armored Turtle / Box Turtle support"),
            ("B", "Back"),
        ]

        while True:
            choice = self.ui.menu(
                "Select MMU Software to Install:",
                items,
                title="MMU Software"
            )

            if choice is None or choice == "B":
                break

            if choice == "happy_hare":
                self.ui.msgbox(
                    "Install Happy Hare:\n\n"
                    "cd ~\n"
                    "git clone https://github.com/moggieuk/Happy-Hare.git\n"
                    "cd Happy-Hare\n"
                    "./install.sh\n\n"
                    "Follow the prompts to configure for your MMU type.\n\n"
                    "Supports: ERCF, TradRack, Prusa MMU, and more.\n"
                    "Docs: https://github.com/moggieuk/Happy-Hare/wiki",
                    title="Happy Hare"
                )
            elif choice == "afc":
                self.ui.msgbox(
                    "Install AFC-Klipper-Add-On:\n\n"
                    "cd ~\n"
                    "git clone https://github.com/ArmoredTurtle/AFC-Klipper-Add-On.git\n"
                    "cd AFC-Klipper-Add-On\n"
                    "./install-afc.sh\n\n"
                    "For Box Turtle / Night Owl / Armored Turtle.\n"
                    "Docs: https://github.com/ArmoredTurtle/AFC-Klipper-Add-On",
                    title="AFC-Klipper-Add-On"
                )

    def _verify_services(self) -> None:
        """Verify all Klipper-related services."""
        services = ["klipper", "moonraker", "crowsnest", "KlipperScreen"]
        status_lines = []

        self.ui.infobox("Checking services...", title="Please Wait")

        for service in services:
            try:
                result = subprocess.run(
                    ["systemctl", "is-active", service],
                    capture_output=True, text=True
                )
                status = result.stdout.strip()
                if status == "active":
                    status_lines.append(f"✓ {service}: running")
                elif status == "inactive":
                    status_lines.append(f"✗ {service}: stopped")
                else:
                    status_lines.append(f"? {service}: {status}")
            except Exception:
                status_lines.append(f"? {service}: unknown")

        self.ui.msgbox(
            "Service Status:\n\n" + "\n".join(status_lines),
            title="Service Verification"
        )


def main():
    """Entry point."""
    wizard = GschpooziWizard()
    wizard.run()


if __name__ == "__main__":
    main()
