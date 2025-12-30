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

import os
import subprocess
import sys
import shutil
from pathlib import Path
from typing import Optional, Tuple

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

# Path to the klipper installation library
KLIPPER_INSTALL_LIB = REPO_ROOT / "scripts" / "lib" / "klipper-install.sh"


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
                'setup_host_mcu': self._setup_host_mcu,
                'check_module': self._check_module,
                'install_module': self._install_module,
                'install_eddy_module': self._install_eddy_module,
                'install_mmu_module': self._install_mmu_module,
                'install_ks_mmu_addon': self._install_ks_mmu_addon,
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

    # ═══════════════════════════════════════════════════════════════════════════════
    # BASH FUNCTION CALLING HELPERS
    # ═══════════════════════════════════════════════════════════════════════════════

    def _call_bash_function(self, function_name: str, show_output: bool = True) -> Tuple[bool, str]:
        """Call a function from klipper-install.sh.

        Args:
            function_name: Name of the bash function to call (e.g., 'do_install_klipper')
            show_output: Whether to show output in real-time

        Returns:
            Tuple of (success: bool, output: str)
        """
        if not KLIPPER_INSTALL_LIB.exists():
            return False, f"Installation library not found: {KLIPPER_INSTALL_LIB}"

        # Build the command to source the library and call the function
        # We need to set up colors and other variables that the bash script expects
        cmd = f'''
            # Set up colors
            export RED='\\033[0;31m'
            export GREEN='\\033[0;32m'
            export YELLOW='\\033[0;33m'
            export CYAN='\\033[0;36m'
            export WHITE='\\033[0;37m'
            export BWHITE='\\033[1;37m'
            export BCYAN='\\033[1;36m'
            export BYELLOW='\\033[1;33m'
            export NC='\\033[0m'
            export BOX_V='│'

            # Set library path for templates
            export INSTALL_LIB_DIR="{KLIPPER_INSTALL_LIB.parent}"

            # Source the library
            source "{KLIPPER_INSTALL_LIB}"

            # Call the function
            {function_name}
        '''

        try:
            if show_output:
                # Run interactively - this allows the bash scripts to show their UI
                result = subprocess.run(
                    ["bash", "-c", cmd],
                    env=dict(os.environ, TERM="xterm-256color"),
                    timeout=1800  # 30 minute timeout for long operations
                )
                return result.returncode == 0, ""
            else:
                # Capture output
                result = subprocess.run(
                    ["bash", "-c", cmd],
                    capture_output=True,
                    text=True,
                    env=dict(os.environ, TERM="xterm-256color"),
                    timeout=1800
                )
                return result.returncode == 0, result.stdout + result.stderr

        except subprocess.TimeoutExpired:
            return False, "Operation timed out"
        except Exception as e:
            return False, str(e)

    def _check_component_installed(self, component: str) -> bool:
        """Check if a component is installed.

        Args:
            component: Component ID (klipper, kalico, moonraker, mainsail, fluidd, klipperscreen, crowsnest)

        Returns:
            True if installed, False otherwise
        """
        # Map component IDs to check methods
        checks = {
            "klipper": lambda: (Path.home() / "klipper").exists() and
                              Path("/etc/systemd/system/klipper.service").exists() and
                              not (Path.home() / "kalico").exists(),  # Not Kalico
            "kalico": lambda: (Path.home() / "kalico").exists() and
                             Path("/etc/systemd/system/klipper.service").exists(),
            "moonraker": lambda: (Path.home() / "moonraker").exists() and
                                Path("/etc/systemd/system/moonraker.service").exists(),
            "mainsail": lambda: (Path.home() / "mainsail").exists() and
                               Path("/etc/nginx/sites-available/mainsail").exists(),
            "fluidd": lambda: (Path.home() / "fluidd").exists() and
                             Path("/etc/nginx/sites-available/fluidd").exists(),
            "klipperscreen": lambda: (Path.home() / "KlipperScreen").exists() and
                                    Path("/etc/systemd/system/KlipperScreen.service").exists(),
            "crowsnest": lambda: (Path.home() / "crowsnest").exists() and
                                Path("/etc/systemd/system/crowsnest.service").exists(),
        }

        check_func = checks.get(component.lower())
        if check_func:
            try:
                return check_func()
            except Exception:
                return False
        return False

    def _get_component_status(self, component: str) -> str:
        """Get the status string for a component.

        Args:
            component: Component ID

        Returns:
            Status string like "[installed]" or "[not installed]"
        """
        # Handle Klipper/Kalico mutual exclusivity
        if component == "klipper":
            # If Kalico is installed, Klipper is not available
            if (Path.home() / "kalico").exists():
                return "[not available - Kalico installed]"
        elif component == "kalico":
            # If Klipper is installed (and not Kalico), show Kalico as not installed
            if (Path.home() / "klipper").exists() and not (Path.home() / "kalico").exists():
                return "[not installed - Klipper installed]"

        if self._check_component_installed(component):
            # Also check if service is running
            service_name = component
            if component == "klipperscreen":
                service_name = "KlipperScreen"
            try:
                result = subprocess.run(
                    ["systemctl", "is-active", service_name],
                    capture_output=True, text=True
                )
                if result.stdout.strip() == "active":
                    return "[running]"
                else:
                    return "[stopped]"
            except Exception:
                return "[installed]"
        return "[not installed]"

    def _generate_config(self) -> None:
        """Generate Klipper configuration files."""
        # First validate
        state_dict = self.state.get_all()
        validator = SkeletonValidator(self.skeleton, state_dict)
        result = validator.validate_all()

        if not result['valid']:
            error_text = "Cannot generate config - please fix these issues:\n\n"

            # Show field validation errors
            if result['errors']:
                for e in result['errors'][:5]:  # Limit to 5 errors
                    error_text += f"- {e}\n"
                if len(result['errors']) > 5:
                    error_text += f"\n...and {len(result['errors']) - 5} more errors"

            # Show incomplete sections if no field errors (or in addition)
            if result['incomplete_sections']:
                if result['errors']:
                    error_text += "\n"
                error_text += "Incomplete sections:\n"
                for section in result['incomplete_sections'][:5]:
                    error_text += f"- {section}\n"
                if len(result['incomplete_sections']) > 5:
                    error_text += f"\n...and {len(result['incomplete_sections']) - 5} more sections"

            # If still empty, show generic message with debug info
            if not result['errors'] and not result['incomplete_sections']:
                error_text += "Unknown validation error.\n"
                error_text += f"Debug: valid={result['valid']}, errors={len(result['errors'])}, incomplete={len(result['incomplete_sections'])}"

            # Calculate height based on number of lines (min 10, max 20)
            line_count = error_text.count('\n') + 3
            height = min(20, max(10, line_count))
            self.ui.msgbox(error_text, title="Validation Failed", height=height)
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
                # Write full error to file for debugging
                error_log = output_dir.parent / "generator_error.log"
                try:
                    with open(error_log, 'w', encoding='utf-8') as f:
                        f.write(f"Generator failed with return code {result.returncode}\n")
                        f.write(f"STDOUT:\n{result.stdout}\n\n")
                        f.write(f"STDERR:\n{result.stderr}\n")
                except Exception:
                    pass
                
                # Show first 1000 chars (increased from 500)
                error_text = f"Generator failed:\n\n{error[:1000]}"
                if len(error) > 1000:
                    error_text += f"\n\n... (truncated, full error saved to {error_log})"
                line_count = error_text.count('\n') + 3
                height = min(25, max(10, line_count))
                self.ui.msgbox(error_text, title="Error", height=height)

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
        """Manage Klipper ecosystem components (KIAUH-style).

        This actually installs/updates/removes components by calling the
        bash functions in klipper-install.sh.
        """
        components = [
            ("klipper", "Klipper", "Core printer firmware"),
            ("kalico", "Kalico", "Klipper fork with MPC and advanced features"),
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
                status = self._get_component_status(comp_id)
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
        """Show actions for a specific component and execute them.

        This actually calls the bash functions to install/update/remove components.
        """
        # Get component display name
        component_names = {
            "klipper": "Klipper",
            "kalico": "Kalico",
            "moonraker": "Moonraker",
            "mainsail": "Mainsail",
            "fluidd": "Fluidd",
            "klipperscreen": "KlipperScreen",
            "crowsnest": "Crowsnest",
        }
        display_name = component_names.get(component, component)

        # Check if installed
        is_installed = self._check_component_installed(component)

        # Build available actions based on installation status
        actions = []
        if not is_installed:
            actions.append(("install", "Install", f"Install {display_name}"))
        else:
            actions.append(("update", "Update", f"Update {display_name} to latest version"))
            actions.append(("remove", "Remove", f"Uninstall {display_name}"))
        actions.append(("B", "Back", ""))

        choice = self.ui.menu(
            f"What would you like to do with {display_name}?",
            [(a[0], f"{a[1]} - {a[2]}") for a in actions if a[2]],
            title=f"Manage {display_name}"
        )

        if choice is None or choice == "B":
            return

        # Map component IDs to bash function names
        func_map = {
            "klipper": "klipper",
            "kalico": "kalico",
            "moonraker": "moonraker",
            "mainsail": "mainsail",
            "fluidd": "fluidd",
            "klipperscreen": "klipperscreen",
            "crowsnest": "crowsnest",
        }
        func_component = func_map.get(component, component)

        if choice == "install":
            # Special handling for Klipper/Kalico (mutually exclusive)
            if component == "kalico" and self._check_component_installed("klipper"):
                if not self.ui.yesno(
                    f"Install {display_name}?\n\n"
                    "WARNING: Klipper is already installed.\n"
                    "Kalico will replace Klipper.\n\n"
                    "This will:\n"
                    "- Stop Klipper service\n"
                    "- Install Kalico (Klipper fork)\n"
                    "- Set up systemd services\n"
                    "- Configure necessary dependencies\n\n"
                    "The installation may take several minutes.",
                    title=f"Install {display_name}"
                ):
                    return
            elif component == "klipper" and self._check_component_installed("kalico"):
                if not self.ui.yesno(
                    f"Install {display_name}?\n\n"
                    "WARNING: Kalico is already installed.\n"
                    "Klipper will replace Kalico.\n\n"
                    "This will:\n"
                    "- Stop Kalico service\n"
                    "- Install Klipper\n"
                    "- Set up systemd services\n"
                    "- Configure necessary dependencies\n\n"
                    "The installation may take several minutes.",
                    title=f"Install {display_name}"
                ):
                    return
            else:
                # Confirm installation
                if not self.ui.yesno(
                    f"Install {display_name}?\n\n"
                    "This will:\n"
                    "- Download and install the component\n"
                    "- Set up systemd services\n"
                    "- Configure necessary dependencies\n\n"
                    "The installation may take several minutes.",
                    title=f"Install {display_name}"
                ):
                    return

            self.ui.infobox(f"Installing {display_name}...\n\nThis may take several minutes.", title="Please Wait")

            # Call the bash function
            success, output = self._call_bash_function(f"do_install_{func_component}")

            if success:
                self.ui.msgbox(
                    f"{display_name} installed successfully!\n\n"
                    "The service should now be running.",
                    title="Installation Complete"
                )
            else:
                self.ui.msgbox(
                    f"Installation may have encountered issues.\n\n"
                    "Please check the terminal output for details.\n"
                    f"{output[:500] if output else ''}",
                    title="Installation Status"
                )

        elif choice == "update":
            # Confirm update
            if not self.ui.yesno(
                f"Update {display_name}?\n\n"
                "This will:\n"
                "- Stop the service temporarily\n"
                "- Pull the latest changes\n"
                "- Update dependencies\n"
                "- Restart the service",
                title=f"Update {display_name}"
            ):
                return

            self.ui.infobox(f"Updating {display_name}...", title="Please Wait")

            # Call the bash function
            success, output = self._call_bash_function(f"do_update_{func_component}")

            if success:
                self.ui.msgbox(
                    f"{display_name} updated successfully!",
                    title="Update Complete"
                )
            else:
                self.ui.msgbox(
                    f"Update may have encountered issues.\n\n"
                    "Please check the terminal output for details.\n"
                    f"{output[:500] if output else ''}",
                    title="Update Status"
                )

        elif choice == "remove":
            # Confirm removal with warning
            if not self.ui.yesno(
                f"Remove {display_name}?\n\n"
                "WARNING: This will:\n"
                "- Stop and disable the service\n"
                "- Remove installed files\n"
                "- Configuration files may be preserved\n\n"
                "This action cannot be undone!",
                title=f"Remove {display_name}"
            ):
                return

            # Double confirm for critical components
            if component in ["klipper", "moonraker"]:
                if not self.ui.yesno(
                    f"Are you REALLY sure you want to remove {display_name}?\n\n"
                    f"Removing {display_name} may break other components!",
                    title="Final Confirmation"
                ):
                    return

            self.ui.infobox(f"Removing {display_name}...", title="Please Wait")

            # Call the bash function
            success, output = self._call_bash_function(f"do_remove_{func_component}")

            if success:
                self.ui.msgbox(
                    f"{display_name} has been removed.",
                    title="Removal Complete"
                )
            else:
                self.ui.msgbox(
                    f"Removal may have encountered issues.\n\n"
                    "Please check the terminal output for details.\n"
                    f"{output[:500] if output else ''}",
                    title="Removal Status"
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
        # Check if already installed
        try:
            result = subprocess.run(
                ["which", "candump"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                self.ui.msgbox(
                    "can-utils is already installed!\n\n"
                    f"Location: {result.stdout.strip()}",
                    title="can-utils"
                )
                return
        except Exception:
            pass

        # Confirm installation
        if not self.ui.yesno(
            "Install can-utils?\n\n"
            "This will install CAN utilities including:\n"
            "- candump (monitor CAN traffic)\n"
            "- cansend (send CAN frames)\n"
            "- cansniffer (filter CAN traffic)\n\n"
            "Requires sudo access.",
            title="Install can-utils"
        ):
            return

        self.ui.infobox("Installing can-utils...", title="Please Wait")

        try:
            # Update package lists
            result = subprocess.run(
                ["sudo", "apt-get", "update"],
                capture_output=True, text=True, timeout=60
            )

            # Install can-utils
            result = subprocess.run(
                ["sudo", "apt-get", "install", "-y", "can-utils"],
                capture_output=True, text=True, timeout=120
            )

            if result.returncode == 0:
                self.ui.msgbox(
                    "can-utils installed successfully!\n\n"
                    "Available commands:\n"
                    "- candump can0 (monitor CAN traffic)\n"
                    "- cansend can0 123#DEADBEEF (send frame)\n"
                    "- ip -s link show can0 (show stats)",
                    title="Installation Complete"
                )
            else:
                self.ui.msgbox(
                    f"Installation failed:\n\n{result.stderr[:500]}",
                    title="Error"
                )

        except subprocess.TimeoutExpired:
            self.ui.msgbox("Installation timed out.", title="Error")
        except Exception as e:
            self.ui.msgbox(f"Error installing can-utils: {e}", title="Error")

    def _configure_can_interface(self) -> None:
        """Configure CAN interface."""
        # Ask for configuration method
        method = self.ui.menu(
            "How would you like to configure CAN?",
            [
                ("persistent", "Persistent Configuration - Survives reboot"),
                ("temporary", "Temporary Setup - For testing (lost on reboot)"),
                ("B", "Back"),
            ],
            title="CAN Configuration"
        )

        if method is None or method == "B":
            return

        # Get bitrate
        bitrate_choices = [
            ("1000000", "1 Mbit/s (recommended for most setups)"),
            ("500000", "500 kbit/s (legacy devices)"),
            ("250000", "250 kbit/s (older devices)"),
            ("custom", "Custom bitrate"),
        ]
        bitrate = self.ui.menu(
            "Select CAN bitrate:",
            bitrate_choices,
            title="CAN Bitrate"
        )

        if bitrate is None:
            return

        if bitrate == "custom":
            bitrate = self.ui.inputbox(
                "Enter custom CAN bitrate (in bits/second):",
                default="1000000",
                title="Custom Bitrate"
            )
            if bitrate is None:
                return

        # Validate bitrate is numeric
        try:
            int(bitrate)
        except ValueError:
            self.ui.msgbox("Invalid bitrate. Must be a number.", title="Error")
            return

        if method == "temporary":
            # Temporary setup
            if not self.ui.yesno(
                f"Set up CAN interface temporarily with bitrate {bitrate}?\n\n"
                "This will run:\n"
                f"  sudo ip link set can0 type can bitrate {bitrate}\n"
                "  sudo ip link set can0 txqueuelen 1024\n"
                "  sudo ip link set up can0\n\n"
                "Note: This will be lost on reboot.",
                title="Temporary CAN Setup"
            ):
                return

            self.ui.infobox("Configuring CAN interface...", title="Please Wait")

            try:
                # Bring down interface if it exists
                subprocess.run(
                    ["sudo", "ip", "link", "set", "down", "can0"],
                    capture_output=True, timeout=10
                )

                # Configure interface
                result = subprocess.run(
                    ["sudo", "ip", "link", "set", "can0", "type", "can", "bitrate", bitrate],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode != 0:
                    self.ui.msgbox(
                        f"Failed to set bitrate:\n\n{result.stderr}\n\n"
                        "Make sure you have a CAN adapter connected.",
                        title="Error"
                    )
                    return

                # Set queue length
                subprocess.run(
                    ["sudo", "ip", "link", "set", "can0", "txqueuelen", "1024"],
                    capture_output=True, timeout=10
                )

                # Bring up interface
                result = subprocess.run(
                    ["sudo", "ip", "link", "set", "up", "can0"],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode != 0:
                    self.ui.msgbox(
                        f"Failed to bring up interface:\n\n{result.stderr}",
                        title="Error"
                    )
                    return

                self.ui.msgbox(
                    "CAN interface configured successfully!\n\n"
                    f"Interface: can0\n"
                    f"Bitrate: {bitrate}\n"
                    f"Queue length: 1024\n\n"
                    "Use 'Query CAN Devices' to find connected MCUs.",
                    title="Success"
                )

            except subprocess.TimeoutExpired:
                self.ui.msgbox("Command timed out.", title="Error")
            except Exception as e:
                self.ui.msgbox(f"Error configuring CAN: {e}", title="Error")

        else:
            # Persistent configuration
            if not self.ui.yesno(
                f"Create persistent CAN configuration with bitrate {bitrate}?\n\n"
                "This will create /etc/network/interfaces.d/can0\n\n"
                "The interface will be automatically configured on boot.",
                title="Persistent CAN Setup"
            ):
                return

            config_content = f"""# CAN interface configuration
# Created by gschpoozi
auto can0
iface can0 can static
    bitrate {bitrate}
    up ip link set can0 txqueuelen 1024
"""

            self.ui.infobox("Creating CAN configuration...", title="Please Wait")

            try:
                # Create config file
                result = subprocess.run(
                    ["sudo", "tee", "/etc/network/interfaces.d/can0"],
                    input=config_content,
                    capture_output=True, text=True, timeout=10
                )

                if result.returncode != 0:
                    self.ui.msgbox(
                        f"Failed to create config file:\n\n{result.stderr}",
                        title="Error"
                    )
                    return

                # Bring up the interface now
                subprocess.run(
                    ["sudo", "ip", "link", "set", "down", "can0"],
                    capture_output=True, timeout=10
                )
                subprocess.run(
                    ["sudo", "ip", "link", "set", "can0", "type", "can", "bitrate", bitrate],
                    capture_output=True, timeout=10
                )
                subprocess.run(
                    ["sudo", "ip", "link", "set", "can0", "txqueuelen", "1024"],
                    capture_output=True, timeout=10
                )
                subprocess.run(
                    ["sudo", "ip", "link", "set", "up", "can0"],
                    capture_output=True, timeout=10
                )

                self.ui.msgbox(
                    "CAN interface configured successfully!\n\n"
                    f"Config file: /etc/network/interfaces.d/can0\n"
                    f"Bitrate: {bitrate}\n\n"
                    "The interface will be automatically configured on boot.\n\n"
                    "Use 'Query CAN Devices' to find connected MCUs.",
                    title="Success"
                )

            except subprocess.TimeoutExpired:
                self.ui.msgbox("Command timed out.", title="Error")
            except Exception as e:
                self.ui.msgbox(f"Error configuring CAN: {e}", title="Error")

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
        """Katapult (formerly CanBoot) and firmware flashing."""
        katapult_dir = Path.home() / "katapult"
        katapult_installed = katapult_dir.exists()

        while True:
            # Build menu based on what's installed
            items = [
                ("dfu", "DFU Flashing", "Flash MCU via USB DFU mode"),
                ("dfu_check", "Check DFU Devices", "List devices in DFU mode"),
            ]

            if katapult_installed:
                items.extend([
                    ("can", "CAN Flashing", "Flash MCU via CAN bus"),
                    ("can_query", "Query Katapult Devices", "Find devices in bootloader mode"),
                    ("update", "Update Katapult", "Pull latest changes"),
                ])
            else:
                items.append(("install", "Install Katapult", "Clone Katapult repository"))

            items.append(("B", "Back"))

            choice = self.ui.menu(
                "Firmware Flashing Options:",
                items,
                title="Katapult / Firmware"
            )

            if choice is None or choice == "B":
                break

            if choice == "dfu_check":
                self._check_dfu_devices()
            elif choice == "dfu":
                self._dfu_flashing()
            elif choice == "can":
                self._can_flashing()
            elif choice == "can_query":
                self._query_katapult_devices()
            elif choice == "install":
                self._install_katapult()
            elif choice == "update":
                self._update_katapult()

    def _check_dfu_devices(self) -> None:
        """Check for devices in DFU mode."""
        self.ui.infobox("Checking for DFU devices...", title="Please Wait")

        try:
            # Run lsusb and filter for DFU devices
            result = subprocess.run(
                ["lsusb"],
                capture_output=True, text=True, timeout=10
            )

            # Common DFU device IDs
            dfu_patterns = [
                "0483:df11",  # STM32 DFU
                "1d50:614e",  # OpenMoko DFU
                "2e8a:0003",  # RP2040 BOOTSEL
            ]

            dfu_devices = []
            for line in result.stdout.splitlines():
                for pattern in dfu_patterns:
                    if pattern in line:
                        dfu_devices.append(line)
                        break
                # Also check for "DFU" in the description
                if "DFU" in line.upper() and line not in dfu_devices:
                    dfu_devices.append(line)

            if dfu_devices:
                device_list = "\n".join(dfu_devices)
                self.ui.msgbox(
                    f"DFU Devices Found:\n\n{device_list}\n\n"
                    "These devices are ready for DFU flashing.",
                    title="DFU Devices"
                )
            else:
                self.ui.msgbox(
                    "No DFU devices found.\n\n"
                    "To enter DFU mode:\n"
                    "1. Hold BOOT button\n"
                    "2. Press RESET button\n"
                    "3. Release BOOT button\n\n"
                    "Or for RP2040:\n"
                    "1. Hold BOOTSEL button\n"
                    "2. Plug in USB cable\n"
                    "3. Release BOOTSEL button",
                    title="No DFU Devices"
                )

        except Exception as e:
            self.ui.msgbox(f"Error checking DFU devices: {e}", title="Error")

    def _dfu_flashing(self) -> None:
        """Guide through DFU flashing process."""
        klipper_dir = Path.home() / "klipper"

        if not klipper_dir.exists():
            self.ui.msgbox(
                "Klipper is not installed.\n\n"
                "Please install Klipper first to build firmware.",
                title="Error"
            )
            return

        # Check for firmware file
        firmware_file = klipper_dir / "out" / "klipper.bin"

        # Menu options
        items = [
            ("menuconfig", "Configure Firmware", "Run make menuconfig"),
            ("build", "Build Firmware", "Compile firmware (make)"),
        ]

        if firmware_file.exists():
            items.append(("flash", "Flash Firmware", "Flash via DFU"))

        items.append(("B", "Back"))

        while True:
            choice = self.ui.menu(
                "DFU Flashing Steps:",
                items,
                title="DFU Flashing"
            )

            if choice is None or choice == "B":
                break

            if choice == "menuconfig":
                self.ui.msgbox(
                    "Running make menuconfig...\n\n"
                    "Configure your MCU settings, then save and exit.",
                    title="Firmware Configuration"
                )
                try:
                    subprocess.run(
                        ["make", "menuconfig"],
                        cwd=klipper_dir,
                        env=dict(os.environ, TERM="xterm")
                    )
                except Exception as e:
                    self.ui.msgbox(f"Error running menuconfig: {e}", title="Error")

            elif choice == "build":
                self.ui.infobox("Building firmware...\n\nThis may take a few minutes.", title="Please Wait")
                try:
                    # Clean first
                    subprocess.run(["make", "clean"], cwd=klipper_dir, capture_output=True)

                    # Build
                    result = subprocess.run(
                        ["make"],
                        cwd=klipper_dir,
                        capture_output=True, text=True,
                        timeout=600
                    )

                    if result.returncode == 0:
                        self.ui.msgbox(
                            "Firmware built successfully!\n\n"
                            f"Output: {firmware_file}\n\n"
                            "You can now flash the firmware.",
                            title="Build Complete"
                        )
                        # Update menu to show flash option
                        if ("flash", "Flash Firmware", "Flash via DFU") not in items:
                            items.insert(-1, ("flash", "Flash Firmware", "Flash via DFU"))
                    else:
                        self.ui.msgbox(
                            f"Build failed:\n\n{result.stderr[:500]}",
                            title="Build Error"
                        )

                except subprocess.TimeoutExpired:
                    self.ui.msgbox("Build timed out.", title="Error")
                except Exception as e:
                    self.ui.msgbox(f"Error building firmware: {e}", title="Error")

            elif choice == "flash":
                # Ask for device ID
                device_id = self.ui.inputbox(
                    "Enter DFU device ID (e.g., 0483:df11 for STM32):\n\n"
                    "Common IDs:\n"
                    "- 0483:df11 (STM32)\n"
                    "- 2e8a:0003 (RP2040)",
                    default="0483:df11",
                    title="DFU Device"
                )

                if device_id is None:
                    continue

                if not self.ui.yesno(
                    f"Flash firmware to device {device_id}?\n\n"
                    "Make sure the device is in DFU mode!",
                    title="Confirm Flash"
                ):
                    continue

                self.ui.infobox("Flashing firmware...", title="Please Wait")

                try:
                    result = subprocess.run(
                        ["make", "flash", f"FLASH_DEVICE={device_id}"],
                        cwd=klipper_dir,
                        capture_output=True, text=True,
                        timeout=120
                    )

                    if result.returncode == 0:
                        self.ui.msgbox(
                            "Firmware flashed successfully!\n\n"
                            "The device should now restart with the new firmware.",
                            title="Flash Complete"
                        )
                    else:
                        # Try dfu-util directly
                        self.ui.msgbox(
                            f"make flash failed. Trying dfu-util...\n\n"
                            "If this fails, try manually:\n"
                            f"dfu-util -a 0 -D {firmware_file} -s 0x08000000:leave",
                            title="Retrying..."
                        )

                except subprocess.TimeoutExpired:
                    self.ui.msgbox("Flash timed out.", title="Error")
                except Exception as e:
                    self.ui.msgbox(f"Error flashing: {e}", title="Error")

    def _query_katapult_devices(self) -> None:
        """Query for devices in Katapult bootloader mode."""
        katapult_dir = Path.home() / "katapult"
        flashtool = katapult_dir / "scripts" / "flashtool.py"

        if not flashtool.exists():
            self.ui.msgbox(
                "Katapult flashtool not found.\n\n"
                "Please install Katapult first.",
                title="Error"
            )
            return

        self.ui.infobox("Querying Katapult devices...", title="Please Wait")

        try:
            result = subprocess.run(
                [sys.executable, str(flashtool), "-q"],
                capture_output=True, text=True, timeout=15
            )

            if result.stdout.strip():
                self.ui.msgbox(
                    f"Katapult Devices:\n\n{result.stdout}",
                    title="Bootloader Devices"
                )
            else:
                self.ui.msgbox(
                    "No devices in bootloader mode found.\n\n"
                    "To enter bootloader mode:\n"
                    "- Double-tap the reset button, or\n"
                    "- Send FIRMWARE_RESTART from Klipper console",
                    title="No Devices Found"
                )

        except subprocess.TimeoutExpired:
            self.ui.msgbox("Query timed out.", title="Error")
        except Exception as e:
            self.ui.msgbox(f"Error querying devices: {e}", title="Error")

    def _can_flashing(self) -> None:
        """Flash firmware via CAN using Katapult."""
        katapult_dir = Path.home() / "katapult"
        flashtool = katapult_dir / "scripts" / "flashtool.py"
        klipper_dir = Path.home() / "klipper"
        firmware_file = klipper_dir / "out" / "klipper.bin"

        if not flashtool.exists():
            self.ui.msgbox(
                "Katapult flashtool not found.\n\n"
                "Please install Katapult first.",
                title="Error"
            )
            return

        if not firmware_file.exists():
            self.ui.msgbox(
                "Firmware file not found.\n\n"
                "Please build firmware first using DFU Flashing > Build Firmware.",
                title="Error"
            )
            return

        # Query for devices first
        self.ui.infobox("Querying for devices in bootloader mode...", title="Please Wait")

        try:
            result = subprocess.run(
                [sys.executable, str(flashtool), "-q"],
                capture_output=True, text=True, timeout=15
            )

            if not result.stdout.strip():
                self.ui.msgbox(
                    "No devices in bootloader mode found.\n\n"
                    "To enter bootloader mode:\n"
                    "- Double-tap the reset button, or\n"
                    "- Send FIRMWARE_RESTART from Klipper console",
                    title="No Devices Found"
                )
                return

            # Ask for UUID
            uuid = self.ui.inputbox(
                f"Devices found:\n{result.stdout}\n\n"
                "Enter the UUID of the device to flash:",
                default="",
                title="Device UUID"
            )

            if uuid is None or not uuid.strip():
                return

            if not self.ui.yesno(
                f"Flash firmware to device {uuid}?\n\n"
                f"Firmware: {firmware_file}",
                title="Confirm Flash"
            ):
                return

            self.ui.infobox("Flashing firmware via CAN...", title="Please Wait")

            result = subprocess.run(
                [sys.executable, str(flashtool), "-u", uuid.strip(), "-f", str(firmware_file)],
                capture_output=True, text=True, timeout=120
            )

            if result.returncode == 0:
                self.ui.msgbox(
                    "Firmware flashed successfully!\n\n"
                    "The device should now restart with the new firmware.",
                    title="Flash Complete"
                )
            else:
                self.ui.msgbox(
                    f"Flash failed:\n\n{result.stderr[:500]}",
                    title="Flash Error"
                )

        except subprocess.TimeoutExpired:
            self.ui.msgbox("Operation timed out.", title="Error")
        except Exception as e:
            self.ui.msgbox(f"Error: {e}", title="Error")

    def _install_katapult(self) -> None:
        """Install Katapult bootloader."""
        katapult_dir = Path.home() / "katapult"

        if katapult_dir.exists():
            self.ui.msgbox(
                "Katapult is already installed.\n\n"
                f"Location: {katapult_dir}",
                title="Already Installed"
            )
            return

        if not self.ui.yesno(
            "Install Katapult?\n\n"
            "This will clone the Katapult repository.\n\n"
            "After installation, you'll need to:\n"
            "1. Run 'make menuconfig' to configure for your MCU\n"
            "2. Build with 'make'\n"
            "3. Flash via DFU the first time",
            title="Install Katapult"
        ):
            return

        self.ui.infobox("Cloning Katapult repository...", title="Please Wait")

        try:
            result = subprocess.run(
                ["git", "clone", "https://github.com/Arksine/katapult.git", str(katapult_dir)],
                capture_output=True, text=True, timeout=120
            )

            if result.returncode == 0:
                self.ui.msgbox(
                    "Katapult installed successfully!\n\n"
                    f"Location: {katapult_dir}\n\n"
                    "Next steps:\n"
                    "1. cd ~/katapult\n"
                    "2. make menuconfig (configure for your MCU)\n"
                    "3. make\n"
                    "4. Flash via DFU",
                    title="Installation Complete"
                )
            else:
                self.ui.msgbox(
                    f"Installation failed:\n\n{result.stderr[:500]}",
                    title="Error"
                )

        except subprocess.TimeoutExpired:
            self.ui.msgbox("Clone timed out.", title="Error")
        except Exception as e:
            self.ui.msgbox(f"Error installing Katapult: {e}", title="Error")

    def _update_katapult(self) -> None:
        """Update Katapult to latest version."""
        katapult_dir = Path.home() / "katapult"

        if not katapult_dir.exists():
            self.ui.msgbox("Katapult is not installed.", title="Error")
            return

        if not self.ui.yesno(
            "Update Katapult to latest version?",
            title="Update Katapult"
        ):
            return

        self.ui.infobox("Updating Katapult...", title="Please Wait")

        try:
            result = subprocess.run(
                ["git", "pull"],
                cwd=katapult_dir,
                capture_output=True, text=True, timeout=60
            )

            if result.returncode == 0:
                self.ui.msgbox(
                    f"Katapult updated!\n\n{result.stdout}",
                    title="Update Complete"
                )
            else:
                self.ui.msgbox(
                    f"Update failed:\n\n{result.stderr[:500]}",
                    title="Error"
                )

        except subprocess.TimeoutExpired:
            self.ui.msgbox("Update timed out.", title="Error")
        except Exception as e:
            self.ui.msgbox(f"Error updating Katapult: {e}", title="Error")

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

    def _setup_host_mcu(self) -> None:
        """Automated Host MCU setup: menuconfig, make, flash."""
        if not self.state.get('mcu.host.enabled'):
            return

        klipper_dir = Path.home() / "klipper"
        if not klipper_dir.exists():
            self.ui.msgbox(
                "Klipper directory not found at ~/klipper\n\n"
                "Please install Klipper first.",
                title="Error"
            )
            return

        # Confirm before proceeding
        if not self.ui.yesno(
            "This will configure and compile the Host MCU firmware.\n\n"
            "Steps:\n"
            "1. Run make menuconfig (select Linux process)\n"
            "2. Compile firmware (make)\n"
            "3. Flash firmware (make flash)\n\n"
            "Continue?",
            title="Host MCU Setup"
        ):
            return

        # Step 1: menuconfig
        self.ui.infobox("Running make menuconfig...\n\nSelect 'Linux process' and configure.", title="Please Wait")
        try:
            result = subprocess.run(
                ["make", "menuconfig"],
                cwd=klipper_dir,
                env=dict(os.environ, TERM="xterm"),
                timeout=300
            )
            if result.returncode != 0:
                self.ui.msgbox("menuconfig failed. Check terminal output.", title="Error")
                return
        except subprocess.TimeoutExpired:
            self.ui.msgbox("menuconfig timed out.", title="Error")
            return
        except Exception as e:
            self.ui.msgbox(f"Error running menuconfig: {e}", title="Error")
            return

        # Step 2: Compile
        self.ui.infobox("Compiling firmware...", title="Please Wait")
        try:
            result = subprocess.run(
                ["make"],
                cwd=klipper_dir,
                capture_output=True,
                text=True,
                timeout=600
            )
            if result.returncode != 0:
                self.ui.msgbox(
                    f"Compilation failed:\n\n{result.stderr[:500]}",
                    title="Error"
                )
                return
        except subprocess.TimeoutExpired:
            self.ui.msgbox("Compilation timed out.", title="Error")
            return
        except Exception as e:
            self.ui.msgbox(f"Error compiling: {e}", title="Error")
            return

        # Step 3: Flash
        if self.ui.yesno(
            "Compilation successful!\n\n"
            "Flash the firmware now?",
            title="Flash Firmware"
        ):
            self.ui.infobox("Flashing firmware...", title="Please Wait")
            try:
                result = subprocess.run(
                    ["make", "flash"],
                    cwd=klipper_dir,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    self.ui.msgbox("Host MCU firmware flashed successfully!", title="Success")
                else:
                    self.ui.msgbox(
                        f"Flash failed:\n\n{result.stderr[:500]}",
                        title="Error"
                    )
            except Exception as e:
                self.ui.msgbox(f"Error flashing: {e}", title="Error")

    def _check_module(self) -> None:
        """Check if required module is installed."""
        # Get current MCU context from state
        additional_mcus = self.state.get('mcu.additional', [])
        if not additional_mcus:
            self.ui.msgbox("No additional MCUs configured.", title="Info")
            return

        # For now, check the last configured MCU
        # In a real implementation, this would be passed as context
        last_mcu = additional_mcus[-1] if isinstance(additional_mcus, list) else {}
        mcu_type = last_mcu.get('type', '')
        mmu_type = last_mcu.get('mmu_type', '')

        module_name = None
        module_path = None

        if mcu_type == 'mmu':
            if mmu_type in ['ercf', 'tradrack']:
                module_name = "Happy Hare"
                module_path = Path.home() / "Happy-Hare"
            elif mmu_type in ['afc', 'box_turtle', 'night_owl']:
                module_name = "AFC-Klipper-Add-On"
                module_path = Path.home() / "AFC-Klipper-Add-On"

        if not module_name:
            self.ui.msgbox("No module required for this MCU type.", title="Info")
            return

        if module_path and module_path.exists():
            self.ui.msgbox(
                f"{module_name} is installed.\n\n"
                f"Location: {module_path}",
                title="Module Status"
            )
        else:
            self.ui.msgbox(
                f"{module_name} is NOT installed.\n\n"
                f"Use 'Install Module' to install it.",
                title="Module Status"
            )

    def _install_module(self) -> None:
        """Install required module (Happy Hare, AFC, etc.)."""
        # Get current MCU context from state
        additional_mcus = self.state.get('mcu.additional', [])
        if not additional_mcus:
            self.ui.msgbox("No additional MCUs configured.", title="Info")
            return

        last_mcu = additional_mcus[-1] if isinstance(additional_mcus, list) else {}
        mcu_type = last_mcu.get('type', '')
        mmu_type = last_mcu.get('mmu_type', '')

        module_name = None
        repo_url = None
        install_script = None
        install_dir = None

        if mcu_type == 'mmu':
            if mmu_type in ['ercf', 'tradrack']:
                module_name = "Happy Hare"
                repo_url = "https://github.com/moggieuk/Happy-Hare.git"
                install_dir = Path.home() / "Happy-Hare"
                install_script = install_dir / "install.sh"
            elif mmu_type in ['afc', 'box_turtle', 'night_owl']:
                module_name = "AFC-Klipper-Add-On"
                repo_url = "https://github.com/ArmoredTurtle/AFC-Klipper-Add-On.git"
                install_dir = Path.home() / "AFC-Klipper-Add-On"
                install_script = install_dir / "install-afc.sh"

        if not module_name:
            self.ui.msgbox("No module required for this MCU type.", title="Info")
            return

        # Check if already installed
        if install_dir and install_dir.exists():
            if self.ui.yesno(
                f"{module_name} appears to be already installed.\n\n"
                "Reinstall anyway?",
                title="Already Installed"
            ):
                # Remove existing
                import shutil
                try:
                    shutil.rmtree(install_dir)
                except Exception as e:
                    self.ui.msgbox(f"Error removing existing installation: {e}", title="Error")
                    return
            else:
                return

        # Confirm installation
        if not self.ui.yesno(
            f"Install {module_name}?\n\n"
            f"This will:\n"
            f"1. Clone repository from {repo_url}\n"
            f"2. Run installation script\n\n"
            "Continue?",
            title="Install Module"
        ):
            return

        # Clone repository
        self.ui.infobox(f"Cloning {module_name}...", title="Please Wait")
        try:
            result = subprocess.run(
                ["git", "clone", repo_url, str(install_dir)],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                self.ui.msgbox(
                    f"Clone failed:\n\n{result.stderr[:500]}",
                    title="Error"
                )
                return
        except Exception as e:
            self.ui.msgbox(f"Error cloning repository: {e}", title="Error")
            return

        # Run installation script
        if install_script and install_script.exists():
            self.ui.infobox(f"Running {module_name} installation script...", title="Please Wait")
            try:
                result = subprocess.run(
                    ["bash", str(install_script)],
                    cwd=install_dir,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if result.returncode == 0:
                    self.ui.msgbox(
                        f"{module_name} installed successfully!",
                        title="Success"
                    )
                else:
                    self.ui.msgbox(
                        f"Installation script failed:\n\n{result.stderr[:500]}",
                        title="Error"
                    )
            except Exception as e:
                self.ui.msgbox(f"Error running installation script: {e}", title="Error")
        else:
            self.ui.msgbox(
                f"{module_name} cloned successfully.\n\n"
                f"Please run the installation script manually:\n"
                f"cd {install_dir}\n"
                f"./install.sh",
                title="Manual Installation Required"
            )

    def _install_eddy_module(self) -> None:
        """Install eddy current probe module (Beacon, Cartographer, BTT Eddy)."""
        probe_type = self.state.get('mcu.eddy_probe.probe_type')

        if not probe_type or probe_type == 'none':
            self.ui.msgbox("Please select a probe type first.", title="Info")
            return

        module_info = {
            'beacon': {
                'name': 'Beacon',
                'repo': 'https://github.com/beacon3d/beacon_klipper.git',
                'install_dir': Path.home() / 'beacon_klipper',
                'install_script': 'install.sh'
            },
            'cartographer': {
                'name': 'Cartographer',
                'repo': 'https://github.com/Cartographer3D/cartographer-klipper.git',
                'install_dir': Path.home() / 'cartographer-klipper',
                'install_script': 'install.sh'
            },
            'btt_eddy': {
                'name': 'BTT Eddy',
                'repo': None,  # Built into Klipper
                'install_dir': None,
                'install_script': None
            }
        }

        info = module_info.get(probe_type)
        if not info:
            self.ui.msgbox(f"Unknown probe type: {probe_type}", title="Error")
            return

        if info['repo'] is None:
            self.ui.msgbox(
                f"{info['name']} support is built into Klipper.\n\n"
                "No additional module installation required.",
                title="Info"
            )
            return

        install_dir = info['install_dir']

        # Check if already installed
        if install_dir and install_dir.exists():
            if self.ui.yesno(
                f"{info['name']} appears to be already installed.\n\n"
                "Reinstall anyway?",
                title="Already Installed"
            ):
                import shutil
                try:
                    shutil.rmtree(install_dir)
                except Exception as e:
                    self.ui.msgbox(f"Error removing existing installation: {e}", title="Error")
                    return
            else:
                return

        # Confirm installation
        if not self.ui.yesno(
            f"Install {info['name']} module?\n\n"
            f"This will clone from:\n{info['repo']}\n\n"
            "Continue?",
            title="Install Module"
        ):
            return

        # Clone repository
        self.ui.infobox(f"Cloning {info['name']}...", title="Please Wait")
        try:
            result = subprocess.run(
                ["git", "clone", info['repo'], str(install_dir)],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                self.ui.msgbox(f"Clone failed:\n\n{result.stderr[:500]}", title="Error")
                return
        except Exception as e:
            self.ui.msgbox(f"Error cloning repository: {e}", title="Error")
            return

        # Run installation script
        install_script = install_dir / info['install_script']
        if install_script.exists():
            self.ui.infobox(f"Running {info['name']} installation...", title="Please Wait")
            try:
                result = subprocess.run(
                    ["bash", str(install_script)],
                    cwd=install_dir,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if result.returncode == 0:
                    self.ui.msgbox(f"{info['name']} installed successfully!", title="Success")
                else:
                    self.ui.msgbox(f"Installation failed:\n\n{result.stderr[:500]}", title="Error")
            except Exception as e:
                self.ui.msgbox(f"Error running installation: {e}", title="Error")
        else:
            self.ui.msgbox(
                f"{info['name']} cloned.\n\n"
                f"Run installation manually:\ncd {install_dir}\n./install.sh",
                title="Manual Installation Required"
            )

    def _install_mmu_module(self) -> None:
        """Install MMU software module (Happy Hare or AFC)."""
        module_type = self.state.get('mcu.mmu.module_type')

        if not module_type:
            self.ui.msgbox("Please select a software module first.", title="Info")
            return

        module_info = {
            'happy_hare': {
                'name': 'Happy Hare',
                'repo': 'https://github.com/moggieuk/Happy-Hare.git',
                'install_dir': Path.home() / 'Happy-Hare',
                'install_script': 'install.sh'
            },
            'afc': {
                'name': 'AFC-Klipper-Add-On',
                'repo': 'https://github.com/ArmoredTurtle/AFC-Klipper-Add-On.git',
                'install_dir': Path.home() / 'AFC-Klipper-Add-On',
                'install_script': 'install-afc.sh'
            }
        }

        info = module_info.get(module_type)
        if not info:
            self.ui.msgbox(f"Unknown module type: {module_type}", title="Error")
            return

        install_dir = info['install_dir']

        # Check if already installed
        if install_dir.exists():
            if self.ui.yesno(
                f"{info['name']} appears to be already installed.\n\n"
                "Reinstall anyway?",
                title="Already Installed"
            ):
                import shutil
                try:
                    shutil.rmtree(install_dir)
                except Exception as e:
                    self.ui.msgbox(f"Error removing existing installation: {e}", title="Error")
                    return
            else:
                return

        # Confirm installation
        if not self.ui.yesno(
            f"Install {info['name']}?\n\n"
            f"This will clone from:\n{info['repo']}\n\n"
            "Continue?",
            title="Install Module"
        ):
            return

        # Clone repository
        self.ui.infobox(f"Cloning {info['name']}...", title="Please Wait")
        try:
            result = subprocess.run(
                ["git", "clone", info['repo'], str(install_dir)],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                self.ui.msgbox(f"Clone failed:\n\n{result.stderr[:500]}", title="Error")
                return
        except Exception as e:
            self.ui.msgbox(f"Error cloning repository: {e}", title="Error")
            return

        # Run installation script
        install_script = install_dir / info['install_script']
        if install_script.exists():
            self.ui.infobox(f"Running {info['name']} installation...", title="Please Wait")
            try:
                result = subprocess.run(
                    ["bash", str(install_script)],
                    cwd=install_dir,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if result.returncode == 0:
                    self.ui.msgbox(f"{info['name']} installed successfully!", title="Success")
                else:
                    self.ui.msgbox(f"Installation failed:\n\n{result.stderr[:500]}", title="Error")
            except Exception as e:
                self.ui.msgbox(f"Error running installation: {e}", title="Error")
        else:
            self.ui.msgbox(
                f"{info['name']} cloned.\n\n"
                f"Run installation manually:\ncd {install_dir}\n./{info['install_script']}",
                title="Manual Installation Required"
            )

    def _install_ks_mmu_addon(self) -> None:
        """Install KlipperScreen MMU add-on."""
        module_type = self.state.get('mcu.mmu.module_type')

        addon_info = {
            'happy_hare': {
                'name': 'Happy Hare KlipperScreen',
                'repo': 'https://github.com/moggieuk/Happy-Hare.git',
                'note': 'KlipperScreen support is included with Happy Hare.\n\n'
                        'After Happy Hare installation, the KlipperScreen\n'
                        'panels should be available automatically.'
            },
            'afc': {
                'name': 'AFC KlipperScreen',
                'repo': 'https://github.com/ArmoredTurtle/AFC-Klipper-Add-On.git',
                'note': 'AFC KlipperScreen add-on is included with AFC.\n\n'
                        'After AFC installation, run the KlipperScreen\n'
                        'setup from the AFC menu if not auto-installed.'
            }
        }

        info = addon_info.get(module_type)
        if not info:
            self.ui.msgbox(
                "KlipperScreen add-on installation depends on the MMU module.\n\n"
                "Please select and install an MMU module first.",
                title="Info"
            )
            return

        self.ui.msgbox(
            f"{info['name']} Add-on\n\n{info['note']}",
            title="KlipperScreen Add-on"
        )


def main():
    """Entry point."""
    wizard = GschpooziWizard()
    wizard.run()


if __name__ == "__main__":
    main()
