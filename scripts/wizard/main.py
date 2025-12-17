#!/usr/bin/env python3
"""
main.py - gschpoozi Configuration Wizard Entry Point

This is the main entry point for the Klipper configuration wizard.
Run with: python3 scripts/wizard/main.py
"""

import sys
import os
import json
import re
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

    def _load_hardware_template(self, filename: str) -> dict:
        """Load a JSON template from templates/hardware/ (e.g. displays.json)."""
        try:
            hw_dir = REPO_ROOT / "templates" / "hardware"
            path = hw_dir / filename
            if not path.exists():
                return {}
            with open(path) as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _has_passwordless_sudo(self) -> bool:
        """Return True if sudo can run non-interactively (no password prompt)."""
        try:
            import subprocess
            result = subprocess.run(["sudo", "-n", "true"], capture_output=True, text=True)
            return result.returncode == 0
        except Exception:
            return False

    def _run_shell(self, command: str) -> tuple[bool, str]:
        """Run a shell command and return (ok, combined_output)."""
        try:
            import subprocess
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
            )
            out = ""
            if result.stdout:
                out += result.stdout
            if result.stderr:
                out += ("\n" if out else "") + result.stderr
            return result.returncode == 0, out.strip()
        except Exception as e:
            return False, str(e)

    def _backup_file(self, path: Path) -> None:
        """Create a timestamped backup of a file if it exists."""
        try:
            if not path.exists():
                return
            from datetime import datetime
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = path.with_suffix(path.suffix + f".bak.{ts}")
            backup.write_text(path.read_text(), encoding="utf-8")
        except Exception:
            # Best-effort; do not block wizard
            return

    def _ensure_moonraker_update_manager_entry(self, name: str, entry: dict) -> bool:
        """
        Ensure a [update_manager <name>] entry exists in moonraker.conf.
        Returns True if present/added, False if cannot write.
        """
        conf = Path.home() / "printer_data" / "config" / "moonraker.conf"
        try:
            conf.parent.mkdir(parents=True, exist_ok=True)
            if conf.exists():
                content = conf.read_text(encoding="utf-8", errors="ignore")
            else:
                content = ""

            header = f"[update_manager {name}]"
            if header in content:
                return True

            # Backup then append
            if conf.exists():
                self._backup_file(conf)

            lines = ["", header]
            # Preserve ordering similar to Moonraker docs
            for key in ("type", "path", "origin", "primary_branch", "virtualenv", "requirements", "system_dependencies", "managed_services"):
                if key in entry and entry[key] is not None and entry[key] != "":
                    lines.append(f"{key}: {entry[key]}")
            conf.write_text(content + "\n".join(lines) + "\n", encoding="utf-8")
            return True
        except Exception:
            return False

    def _write_klipperscreen_conf(self, host: str, port: int) -> tuple[bool, str]:
        """Write/update ~/KlipperScreen/KlipperScreen.conf with [printer default]."""
        conf_path = Path.home() / "KlipperScreen" / "KlipperScreen.conf"
        try:
            conf_path.parent.mkdir(parents=True, exist_ok=True)
            if conf_path.exists():
                self._backup_file(conf_path)
                original = conf_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            else:
                original = []

            section_header = "[printer default]"
            in_section = False
            seen_section = False
            wrote_host = False
            wrote_port = False
            out_lines: list[str] = []

            def _maybe_append_missing():
                nonlocal wrote_host, wrote_port
                if not wrote_host:
                    out_lines.append(f"moonraker_host: {host}")
                    wrote_host = True
                if not wrote_port:
                    out_lines.append(f"moonraker_port: {int(port)}")
                    wrote_port = True

            for line in original:
                stripped = line.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    # Leaving previous section
                    if in_section:
                        _maybe_append_missing()
                        in_section = False
                    # Entering new section
                    if stripped.lower() == section_header.lower():
                        in_section = True
                        seen_section = True
                        out_lines.append(section_header)
                        continue

                if in_section:
                    key = stripped.split(":", 1)[0].strip().lower() if ":" in stripped else ""
                    if key == "moonraker_host":
                        out_lines.append(f"moonraker_host: {host}")
                        wrote_host = True
                        continue
                    if key == "moonraker_port":
                        out_lines.append(f"moonraker_port: {int(port)}")
                        wrote_port = True
                        continue

                out_lines.append(line)

            if in_section:
                _maybe_append_missing()
                in_section = False

            if not seen_section:
                if out_lines and out_lines[-1].strip() != "":
                    out_lines.append("")
                out_lines.append(section_header)
                out_lines.append(f"moonraker_host: {host}")
                out_lines.append(f"moonraker_port: {int(port)}")

            conf_path.write_text("\n".join(out_lines).rstrip() + "\n", encoding="utf-8")
            return True, str(conf_path)
        except Exception as e:
            return False, str(e)

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

    def _pick_pin_from_known_ports(
        self,
        *,
        location: str,
        default_pin: str = "",
        title: str = "Select Pin",
        prompt: str = "Select a pin:",
        preferred_groups: list = None,
    ):
        """
        Pick a pin from known board/toolboard template ports (with manual fallback).

        - location: "mainboard" or "toolboard"
        - preferred_groups: ordered list of JSON groups to show first (e.g. ["endstop_ports","misc_ports"])

        Returns:
            Selected raw pin string (e.g. "PA8", "gpio22") or None if cancelled.
        """
        if location not in {"mainboard", "toolboard"}:
            return self.ui.inputbox(prompt, default=default_pin or "", title=title)

        board_type = "boards" if location == "mainboard" else "toolboards"
        board_id = (
            self.state.get("mcu.main.board_type", "")
            if location == "mainboard"
            else self.state.get("mcu.toolboard.board_type", "")
        )
        board_data = self._load_board_data(board_id, board_type)
        if not isinstance(board_data, dict) or not board_data:
            return self.ui.inputbox(prompt, default=default_pin or "", title=title)

        # For "ports_plus_all_known", we intentionally include many groups.
        # NOTE: some of these pins may normally be used for other functions (fan/heater/etc).
        all_groups = [
            "misc_ports",
            "endstop_ports",
            "probe_ports",
            "fan_ports",
            "heater_ports",
            "thermistor_ports",
            "motor_ports",
        ]
        groups = []
        if preferred_groups:
            for g in preferred_groups:
                if g in all_groups and g not in groups:
                    groups.append(g)
        for g in all_groups:
            if g not in groups:
                groups.append(g)

        options = []
        tag_to_pin = {}
        selected_tag = None

        def _add_option(tag: str, desc: str, pin: str) -> None:
            nonlocal selected_tag
            if not pin or not isinstance(pin, str):
                return
            tag_to_pin[tag] = pin
            is_selected = False
            if default_pin and pin == default_pin and selected_tag is None:
                is_selected = True
                selected_tag = tag
            options.append((tag, desc, is_selected))

        for group in groups:
            group_data = board_data.get(group, {})
            if not isinstance(group_data, dict):
                continue

            for port_id, port_info in group_data.items():
                # Flatten header-style pin maps: {"pins": {"1":"PE8", ...}}
                if isinstance(port_info, dict) and isinstance(port_info.get("pins"), dict):
                    for sub_id, sub_pin in port_info["pins"].items():
                        tag = f"{group}:{port_id}:{sub_id}"
                        _add_option(tag, f"{port_id}-{sub_id} ({sub_pin}) [{group}]", str(sub_pin))
                    continue

                if isinstance(port_info, dict):
                    # Common forms
                    if "pin" in port_info:
                        tag = f"{group}:{port_id}:pin"
                        _add_option(tag, f"{port_id} ({port_info['pin']}) [{group}]", str(port_info["pin"]))
                    if "signal_pin" in port_info:
                        tag = f"{group}:{port_id}:signal"
                        _add_option(tag, f"{port_id} ({port_info['signal_pin']}) [{group}]", str(port_info["signal_pin"]))

                    # Include other *_pin fields (useful for “all known” discovery)
                    for k, v in port_info.items():
                        if k in {"pin", "signal_pin", "pins"}:
                            continue
                        if k.endswith("_pin") and isinstance(v, str) and v:
                            tag = f"{group}:{port_id}:{k}"
                            _add_option(tag, f"{port_id} {k} ({v}) [{group}]", v)
                else:
                    # Rare: port_info is a direct string pin
                    if isinstance(port_info, str) and port_info:
                        tag = f"{group}:{port_id}:raw"
                        _add_option(tag, f"{port_id} ({port_info}) [{group}]", port_info)

        # Add manual fallback
        options.append(("manual", "Manual entry", selected_tag is None))

        choice = self.ui.radiolist(
            prompt,
            options,
            title=title
        )
        if choice is None:
            return None
        if choice == "manual":
            return self.ui.inputbox(prompt, default=default_pin or "", title=title)
        return tag_to_pin.get(choice, default_pin or "")

    # -------------------------------------------------------------------------
    # Heater discovery / picker helpers
    # -------------------------------------------------------------------------

    def _collect_cfg_files_for_scan(self) -> list:
        """Collect Klipper cfg files to scan (best-effort).

        - Starts from ~/printer_data/config/printer.cfg (if it exists)
        - Follows [include ...] directives recursively (best-effort, no crash on missing files)
        - Also scans ~/printer_data/config/gschpoozi/*.cfg
        """
        base = Path.home() / "printer_data" / "config"
        start = base / "printer.cfg"

        # Allow trailing comments after the closing bracket:
        #   [include foo.cfg]  # comment
        #   [include foo/*.cfg] ; comment
        include_re = re.compile(r"^\s*\[include\s+([^\]]+)\]\s*(?:[;#].*)?$")

        visited = set()
        out = []
        queue = []

        # Always include gschpoozi cfgs if present (they're predictable for our project)
        try:
            gdir = base / "gschpoozi"
            if gdir.exists():
                for p in sorted(gdir.glob("*.cfg")):
                    rp = p.resolve()
                    if rp not in visited:
                        visited.add(rp)
                        out.append(p)
        except Exception:
            pass

        if start.exists():
            queue.append(start)

        # BFS include traversal with a hard cap
        while queue and len(out) < 250:
            p = queue.pop(0)
            try:
                rp = p.resolve()
                if rp in visited:
                    continue
                visited.add(rp)
                out.append(p)
                txt = p.read_text(encoding="utf-8", errors="ignore").splitlines()
            except Exception:
                continue

            for line in txt:
                s = line.strip()
                if not s or s.startswith("#") or s.startswith(";"):
                    continue
                m = include_re.match(s)
                if not m:
                    continue
                inc = m.group(1).strip()
                if not inc:
                    continue

                # Includes can be relative, absolute, or globs. Resolve relative to the file directory.
                base_dir = p.parent
                inc_path = Path(inc)
                candidates = []
                if str(inc_path).startswith("~/"):
                    candidates = [Path.home() / str(inc_path)[2:]]
                elif inc_path.is_absolute():
                    candidates = [inc_path]
                else:
                    # Relative; allow globbing
                    globbed = list(base_dir.glob(inc))
                    candidates = globbed if globbed else [base_dir / inc]

                for c in candidates:
                    try:
                        if c.exists() and c.is_file():
                            queue.append(c)
                    except Exception:
                        continue

        return out

    def _discover_heater_names_from_cfg(self, cfg_files: list) -> set:
        """Discover heater object names from Klipper config files."""
        # Allow trailing comments after section headers too:
        #   [heater_generic chamber]  # comment
        section_re = re.compile(r"^\s*\[([^\]]+)\]\s*(?:[;#].*)?$")

        heaters = set()
        for p in cfg_files or []:
            try:
                lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
            except Exception:
                continue
            for line in lines:
                s = line.strip()
                if not s or s.startswith("#") or s.startswith(";"):
                    continue
                m = section_re.match(s)
                if not m:
                    continue
                section = m.group(1).strip()
                if not section:
                    continue
                # Skip includes (not real sections)
                if section.lower().startswith("include "):
                    continue

                # Heater objects that can be referenced by [heater_fan] heater:
                # - extruder, extruder1, extruder2, ...
                # - heater_bed
                # - heater_generic <name>
                if section == "extruder" or re.match(r"^extruder\d+$", section):
                    heaters.add(section)
                elif section == "heater_bed":
                    heaters.add(section)
                elif section.startswith("heater_generic "):
                    heaters.add(section)

        return heaters

    def _get_known_heater_choices(self, current_value: str = "") -> list:
        """Return list of (value,label) heater choices."""
        generated = {"extruder", "heater_bed"}
        detected = set()
        try:
            cfgs = self._collect_cfg_files_for_scan()
            detected = self._discover_heater_names_from_cfg(cfgs)
        except Exception:
            detected = set()

        all_values = set(generated) | set(detected)
        if current_value and isinstance(current_value, str) and current_value.strip():
            all_values.add(current_value.strip())

        def _sort_key(v: str):
            if v == "extruder":
                return (0, v)
            if v == "heater_bed":
                return (1, v)
            # Put heater_generic after basic heaters, then extruderN, then others
            if v.startswith("extruder") and v != "extruder":
                return (2, v)
            if v.startswith("heater_generic "):
                return (3, v)
            return (4, v)

        ordered = sorted(all_values, key=_sort_key)
        out = []
        for v in ordered:
            label = v
            if v in generated:
                label = f"{v} (generated)"
            elif v in detected:
                label = f"{v} (detected)"
            else:
                label = f"{v} (custom)"
            out.append((v, label))
        return out

    def _pick_heater_name(self, *, current_value: str, title: str) -> str | None:
        """Pick a heater name from known heaters; manual entry fallback."""
        choices = self._get_known_heater_choices(current_value=current_value or "")
        tag_to_value = {}
        items = []
        selected_tag = None

        for idx, (val, label) in enumerate(choices):
            tag = f"h{idx}"
            tag_to_value[tag] = val
            sel = (val == (current_value or "")) and selected_tag is None
            if sel:
                selected_tag = tag
            items.append((tag, label, sel))

        # Manual entry option
        items.append(("manual", "Manual entry", selected_tag is None))

        picked = self.ui.radiolist(
            "Select heater to monitor:",
            items,
            title=title,
            height=22,
            width=120,
            list_height=min(16, max(6, len(items))),
        )
        if picked is None:
            return None
        if picked == "manual":
            return self.ui.inputbox(
                "Heater to monitor:\n\nExample: extruder, heater_bed, heater_generic chamber",
                default=current_value or "extruder",
                title=title,
                height=10,
                width=90,
            )
        return tag_to_value.get(picked, current_value or "extruder")

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

            # Probe
            probe_type = self.state.get("probe.probe_type", "")
            probe_status = None
            if probe_type and probe_type != "none":
                # Format probe type nicely: capitalize and replace underscores
                probe_status = probe_type.replace("_", " ").title()

            # Homing
            homing_method = self.state.get("homing.homing_method", "")
            homing_status = None
            if homing_method:
                # Format homing method nicely: capitalize and replace underscores
                homing_status = homing_method.replace("_", " ").title()

            # Bed Leveling
            leveling_type = self.state.get("bed_leveling.leveling_type", "")
            mesh_enabled = self.state.get("bed_leveling.bed_mesh.enabled", False)
            leveling_status = None
            parts = []
            if leveling_type and leveling_type != "none":
                # Format leveling type nicely
                formatted_type = (
                    leveling_type.replace("_", " ").upper()
                    if leveling_type == "qgl"
                    else leveling_type.replace("_", " ").title()
                )
                parts.append(formatted_type)
            if mesh_enabled:
                parts.append("Mesh")
            if parts:
                leveling_status = " + ".join(parts)

            # Temperature Sensors
            temp_sensor_count = 0
            if self.state.get("temperature_sensors.mcu_main.enabled", False):
                temp_sensor_count += 1
            if self.state.get("temperature_sensors.host.enabled", False):
                temp_sensor_count += 1
            if self.state.get("temperature_sensors.toolboard.enabled", False):
                temp_sensor_count += 1
            if self.state.get("temperature_sensors.chamber.enabled", False):
                temp_sensor_count += 1
            # Count additional user-defined sensors
            additional_sensors = self.state.get("temperature_sensors.additional", [])
            if isinstance(additional_sensors, list):
                temp_sensor_count += len([s for s in additional_sensors if isinstance(s, dict)])
            temp_sensors_status = None
            if temp_sensor_count > 0:
                temp_sensors_status = f"{temp_sensor_count} sensor{'s' if temp_sensor_count != 1 else ''}"

            # LEDs
            leds = self.state.get("leds", [])
            if not isinstance(leds, list):
                leds = []
            leds_count = len(leds)
            leds_status = None
            if leds_count > 0:
                leds_status = f"{leds_count} LED{'s' if leds_count != 1 else ''}"

            # Filament Sensors
            filament_sensors = self.state.get("filament_sensors", [])
            if not isinstance(filament_sensors, list):
                filament_sensors = []
            filament_count = len(filament_sensors)
            filament_sensors_status = None
            if filament_count > 0:
                filament_sensors_status = f"{filament_count} sensor{'s' if filament_count != 1 else ''}"

            # Display (KlipperScreen first)
            display_status = None
            ks_enabled = self.state.get("display.klipperscreen.enabled", False)
            try:
                ks_installed = (Path.home() / "KlipperScreen").exists()
            except Exception:
                ks_installed = False
            ks_running = False
            if ks_installed:
                try:
                    import subprocess
                    # Try common service names
                    for svc in ("KlipperScreen", "klipperscreen"):
                        result = subprocess.run(
                            ["systemctl", "is-active", svc],
                            capture_output=True,
                            text=True,
                        )
                        if result.stdout.strip() == "active":
                            ks_running = True
                            break
                except Exception:
                    ks_running = False

            if ks_running:
                display_status = "KlipperScreen (running)"
            elif ks_installed:
                display_status = "KlipperScreen (installed)"
            elif ks_enabled:
                display_status = "KlipperScreen (enabled)"

            # Advanced
            advanced_status = None
            adv_parts = []
            multi_pins = self.state.get("advanced.multi_pins", [])
            if isinstance(multi_pins, list) and len(multi_pins) > 0:
                adv_parts.append("Multi-pin")
            if self.state.get("advanced.force_move.enable_force_move", False):
                adv_parts.append("ForceMove")
            if self.state.get("advanced.firmware_retraction.enabled", False):
                adv_parts.append("FWRetract")
            if adv_parts:
                advanced_status = ", ".join(adv_parts)

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
                ("2.9", self._format_menu_item("Probe", probe_status) if probe_status else "Probe                 (BLTouch, Beacon, etc.)"),
                ("2.10", self._format_menu_item("Homing", homing_status) if homing_status else "Homing               (Safe Z home, sensorless)"),
                ("2.11", self._format_menu_item("Bed Leveling", leveling_status) if leveling_status else "Bed Leveling         (Mesh, Z tilt, QGL)"),
                ("2.12", self._format_menu_item("Temperature Sensors", temp_sensors_status) if temp_sensors_status else "Temperature Sensors  (MCU, chamber, etc.)"),
                ("2.13", self._format_menu_item("LEDs", leds_status) if leds_status else "LEDs                 (Neopixel, case light)"),
                ("2.14", self._format_menu_item("Filament Sensors", filament_sensors_status) if filament_sensors_status else "Filament Sensors     (Runout detection)"),
                ("2.15", self._format_menu_item("Display", display_status) if display_status else "Display              (LCD, OLED, KlipperScreen)"),
                ("2.16", self._format_menu_item("Advanced", advanced_status) if advanced_status else "Advanced             (Servo, buttons, etc.)"),
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
            elif choice == "2.15":
                self._display_setup()
            elif choice == "2.16":
                self._advanced_setup()
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

        # Load saved serial path
        current_serial = self.state.get("mcu.main.serial", "")

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
                        default=current_serial or "/dev/serial/by-id/usb-Klipper_"
                    )
                elif selected and selected in serial_map:
                    serial_path = serial_map[selected]
        else:
            serial_path = self.ui.inputbox(
                "No devices found. Enter serial path manually:",
                default=current_serial or "/dev/serial/by-id/usb-Klipper_"
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
        current_max_z_velocity = self.state.get("printer.max_z_velocity", 15)
        current_max_z_accel = self.state.get("printer.max_z_accel", 350)
        current_scv = self.state.get("printer.square_corner_velocity", "")

        max_velocity = self.ui.inputbox("Max velocity (mm/s):", default=str(current_max_velocity))
        if max_velocity is None:
            return
        max_accel = self.ui.inputbox("Max acceleration (mm/s²):", default=str(current_max_accel))
        if max_accel is None:
            return
        max_z_velocity = self.ui.inputbox("Max Z velocity (mm/s):", default=str(current_max_z_velocity))
        if max_z_velocity is None:
            return
        max_z_accel = self.ui.inputbox("Max Z acceleration (mm/s²):", default=str(current_max_z_accel))
        if max_z_accel is None:
            return
        square_corner_velocity = self.ui.inputbox(
            "Square corner velocity (mm/s):\n\n(Leave empty to omit from config)",
            default=str(current_scv) if current_scv not in (None, "") else "",
        )

        # Save
        self.state.set("printer.kinematics", kinematics)
        self.state.set("printer.awd_enabled", awd_enabled)
        self.state.set("printer.bed_size_x", int(bed_x))
        self.state.set("printer.bed_size_y", int(bed_y))
        self.state.set("printer.bed_size_z", int(bed_z))
        self.state.set("printer.max_velocity", int(max_velocity or 300))
        self.state.set("printer.max_accel", int(max_accel or 3000))
        self.state.set("printer.max_z_velocity", int(max_z_velocity or 15))
        self.state.set("printer.max_z_accel", int(max_z_accel or 350))
        if square_corner_velocity not in (None, ""):
            # Allow explicit 0
            try:
                self.state.set("printer.square_corner_velocity", float(square_corner_velocity))
            except ValueError:
                self.state.set("printer.square_corner_velocity", square_corner_velocity)
        else:
            self.state.delete("printer.square_corner_velocity")
        self.state.save()

        awd_text = "AWD: Enabled\n" if awd_enabled else ""
        self.ui.msgbox(
            f"Printer settings saved!\n\n"
            f"Kinematics: {kinematics}\n"
            f"{awd_text}"
            f"Bed: {bed_x}x{bed_y}x{bed_z}mm\n"
            f"Max velocity: {max_velocity}mm/s\n"
            f"Max accel: {max_accel}mm/s²\n"
            f"Max Z velocity: {max_z_velocity}mm/s\n"
            f"Max Z accel: {max_z_accel}mm/s²\n"
            f"Square corner velocity: {square_corner_velocity if square_corner_velocity not in (None, '') else '(omitted)'}",
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
                # Load saved endstop type
                current_endstop_type = self.state.get(f"{state_key}.endstop_type", "physical")
                endstop_type = self.ui.radiolist(
                    f"Endstop type for {axis_upper} axis:",
                    [
                        ("physical", "Physical switch", current_endstop_type == "physical"),
                        ("sensorless", "Sensorless (StallGuard)", current_endstop_type == "sensorless"),
                    ],
                    title=f"Stepper {axis_upper} - Endstop"
                )
                if endstop_type is None:
                    return

                # Physical endstop port and config
                endstop_port = None
                endstop_config = None
                if endstop_type == "physical":
                    current_endstop_port = self.state.get(f"{state_key}.endstop_port", "")
                    endstop_ports = self._get_board_ports("endstop_ports", "boards")
                    if endstop_ports:
                        endstop_port = self.ui.radiolist(
                            f"Select endstop port for {axis_upper} axis:",
                            [(p, l, p == current_endstop_port or d) for p, l, d in endstop_ports],
                            title=f"Stepper {axis_upper} - Endstop Port"
                        )
                    else:
                        endstop_port = self.ui.inputbox(
                            f"Enter endstop port for {axis_upper} axis:",
                            default=current_endstop_port or "",
                            title=f"Stepper {axis_upper} - Endstop Port"
                        )
                    if endstop_port is None:
                        return

                    current_endstop_config = self.state.get(f"{state_key}.endstop_config", "nc_gnd")
                    endstop_config = self.ui.radiolist(
                        f"Endstop switch configuration for {axis_upper}:",
                        [
                            ("nc_gnd", "NC to GND (^pin) - recommended", current_endstop_config == "nc_gnd"),
                            ("no_gnd", "NO to GND (^!pin)", current_endstop_config == "no_gnd"),
                            ("nc_vcc", "NC to VCC (!pin)", current_endstop_config == "nc_vcc"),
                            ("no_vcc", "NO to VCC (pin)", current_endstop_config == "no_vcc"),
                        ],
                        title=f"Stepper {axis_upper} - Endstop Config"
                    )
                    if endstop_config is None:
                        return

                bed_size = self.state.get(f"printer.bed_size_{axis}", 350)
                current_position_max = self.state.get(f"{state_key}.position_max", bed_size)
                position_max = self.ui.inputbox(
                    f"Position max for {axis_upper} (mm):",
                    default=str(current_position_max),
                    title=f"Stepper {axis_upper} - Position"
                )
                if position_max is None:
                    return

                current_position_endstop = self.state.get(f"{state_key}.position_endstop", position_max)
                position_endstop = self.ui.inputbox(
                    f"Position endstop for {axis_upper} (0 for min, {position_max} for max):",
                    default=str(current_position_endstop),
                    title=f"Stepper {axis_upper} - Endstop Position"
                )
                if position_endstop is None:
                    return

                # Homing settings
                current_homing_speed = self.state.get(f"{state_key}.homing_speed", 50)
                homing_speed = self.ui.inputbox(
                    f"Homing speed for {axis_upper} (mm/s):",
                    default=str(current_homing_speed),
                    title=f"Stepper {axis_upper} - Homing Speed"
                )
                if homing_speed is None:
                    return

                current_retract = self.state.get(f"{state_key}.homing_retract_dist", 5.0 if endstop_type == "physical" else 0.0)
                default_retract = "0" if endstop_type == "sensorless" else str(int(current_retract))
                homing_retract_dist = self.ui.inputbox(
                    f"Homing retract distance for {axis_upper} (mm):",
                    default=default_retract,
                    title=f"Stepper {axis_upper} - Homing Retract"
                )
                if homing_retract_dist is None:
                    return

                second_homing_speed = None
                current_has_second = self.state.get(f"{state_key}.second_homing_speed") is not None
                if self.ui.yesno(
                    f"Use second (slower) homing speed for {axis_upper}?",
                    title=f"Stepper {axis_upper} - Second Homing Speed",
                    default_no=not current_has_second
                ):
                    current_second = self.state.get(f"{state_key}.second_homing_speed", 10)
                    second_homing_speed = self.ui.inputbox(
                        f"Second homing speed for {axis_upper} (mm/s):",
                        default=str(current_second),
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
        # Default to 16 for X/Y motion steppers unless explicitly set (common on many builds)
        default_microsteps = 16 if axis in ("x", "y", "x1", "y1") else 32
        current_microsteps = self.state.get(f"{state_key}.microsteps", default_microsteps)
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
                # If a toolboard exists, allow selecting endstop from mainboard or toolboard.
                has_toolboard = bool(self.state.get("mcu.toolboard.connection_type"))
                current_endstop_src = self.state.get(f"{state_key}.endstop_source", "")
                if has_toolboard:
                    endstop_source = self.ui.radiolist(
                        f"Where is the {axis_upper} endstop connected?",
                        [
                            ("mainboard", "Mainboard", current_endstop_src == "mainboard"),
                            ("toolboard", "Toolboard", current_endstop_src == "toolboard"),
                        ],
                        title=f"Stepper {axis_upper} - Endstop Location",
                    )
                    if endstop_source is None:
                        return
                else:
                    endstop_source = "mainboard"

                # Endstop port selection from board templates
                board_type = "toolboards" if endstop_source == "toolboard" else "boards"
                endstop_ports = self._get_board_ports("endstop_ports", board_type)
                if endstop_ports:
                    if endstop_source == "toolboard":
                        current_port = self.state.get(f"{state_key}.endstop_port_toolboard", "")
                    else:
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
                # Persist which side we used so the generator schema can render the right pin map.
                if "endstop_source" in locals():
                    self.state.set(f"{state_key}.endstop_source", endstop_source)
                if "endstop_source" in locals() and endstop_source == "toolboard":
                    self.state.set(f"{state_key}.endstop_port_toolboard", endstop_port)
                    # Clear mainboard key to avoid ambiguity
                    self.state.delete(f"{state_key}.endstop_port")
                else:
                    self.state.set(f"{state_key}.endstop_port", endstop_port)
                    self.state.delete(f"{state_key}.endstop_port_toolboard")
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
                default=current_port or ("EXTRUDER" if motor_location == "toolboard" else "MOTOR_5"),
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
                    default=current_port or ("HE" if heater_location == "toolboard" else "HE0"),
                    title="Hotend - Heater Port"
                )
        else:
            heater_port = self.ui.inputbox(
                f"Enter heater port on {heater_location}:",
                default=current_port or ("HE" if heater_location == "toolboard" else "HE0"),
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
                    default=current_port or ("TH0" if sensor_location == "toolboard" else "T0"),
                    title="Hotend - Thermistor Port"
                )
        else:
            sensor_port = self.ui.inputbox(
                f"Enter thermistor port on {sensor_location}:",
                default=current_port or ("TH0" if sensor_location == "toolboard" else "T0"),
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
        heater = self._pick_heater_name(current_value=current_heater, title="Fans - Hotend Heater")
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
        # Load existing additional fans from state
        additional_fans = self.state.get("fans.additional_fans", [])
        if not isinstance(additional_fans, list):
            additional_fans = []

        def _edit_fan(fan=None):
            """Edit or add an additional fan. If fan is None, add new."""
            if fan:
                fan_name = self.ui.inputbox(
                    "Fan name:",
                    default=fan.get("name", ""),
                    title="Edit Fan"
                )
            else:
                fan_name = self.ui.inputbox(
                    "Fan name (e.g., exhaust_fan, nevermore):",
                    default="",
                    title="Add Fan"
                )

            if not fan_name:
                return None

            # Multi-pin support
            current_is_multi = fan.get("pin_type") == "multi_pin" if fan else None
            is_multi_pin = self.ui.yesno(
                f"Does '{fan_name}' use multiple pins?\n\n"
                "(e.g., two fans running together as one)",
                title=f"{fan_name} - Multi-Pin",
                default_no=not current_is_multi if current_is_multi is not None else True
            )

            fan_config = {"name": fan_name}

            if is_multi_pin:
                # For multi-pin, need to select multiple ports
                current_pins = fan.get("pins", "") if fan else None
                fan_ports = self._get_board_ports("fan_ports", "boards")
                if fan_ports:
                    pins_list = []
                    if current_pins:
                        # Parse existing pins
                        pins_list = [p.strip() for p in current_pins.split(",")]

                    self.ui.msgbox(
                        f"Select fan ports for '{fan_name}'.\n\n"
                        "You'll select them one at a time.",
                        title=f"{fan_name} - Multi-Pin Setup"
                    )
                    while True:
                        port = self.ui.radiolist(
                            f"Select a fan port for '{fan_name}':\n"
                            f"Currently selected: {', '.join(pins_list) if pins_list else 'none'}",
                            [(p, l, p in pins_list) for p, l, d in fan_ports],
                            title=f"{fan_name} - Select Port"
                        )
                        if port:
                            if port in pins_list:
                                pins_list.remove(port)
                            else:
                                pins_list.append(port)
                        if not self.ui.yesno(f"Add/remove another port to '{fan_name}'?", title="More Ports"):
                            break
                    pins = ", ".join(pins_list)
                else:
                    pins = self.ui.inputbox(
                        f"Enter pins for '{fan_name}' (comma-separated):\n\n"
                        "Example: PA15, PB11",
                        default=current_pins or "",
                        title=f"{fan_name} - Pins"
                    )
                if not pins or not str(pins).strip():
                    self.ui.msgbox("Multi-pin fan requires at least one pin.", title="Invalid Fan Pins")
                    return None
                fan_config["pin_type"] = "multi_pin"
                fan_config["pins"] = pins
                fan_config["multi_pin_name"] = fan_name
            else:
                # Single pin fan - select from available ports
                current_port = fan.get("port", "") if fan else None
                current_pin = fan.get("pin", "") if fan else None
                fan_ports = self._get_board_ports("fan_ports", "boards")
                if fan_ports:
                    port = self.ui.radiolist(
                        f"Select fan port for '{fan_name}':",
                        [(p, l, p == current_port or d) for p, l, d in fan_ports],
                        title=f"{fan_name} - Port"
                    )
                    if port:
                        fan_config["pin_type"] = "single"
                        fan_config["port"] = port
                else:
                    pin = self.ui.inputbox(
                        f"Pin for '{fan_name}':",
                        default=current_pin or "",
                        title=f"{fan_name} - Pin"
                    )
                    fan_config["pin_type"] = "single"
                    fan_config["pin"] = pin

            return fan_config

        # Management loop
        while True:
            menu_items = [("ADD", "Add new fan")]
            for i, fan in enumerate(additional_fans):
                menu_items.append((f"EDIT_{i}", f"Edit: {fan.get('name', 'Unknown')}"))
            for i, fan in enumerate(additional_fans):
                menu_items.append((f"DELETE_{i}", f"Delete: {fan.get('name', 'Unknown')}"))
            menu_items.append(("DONE", "Done (save and exit)"))

            choice = self.ui.menu(
                f"Additional Fans Configuration\n\n"
                f"Currently configured: {len(additional_fans)} fan(s)\n"
                f"{', '.join(f.get('name', 'Unknown') for f in additional_fans) if additional_fans else 'None'}",
                menu_items,
                title="Additional Fans Management"
            )

            if choice is None or choice == "DONE":
                break
            elif choice == "ADD":
                new_fan = _edit_fan()
                if new_fan:
                    additional_fans.append(new_fan)
            elif choice.startswith("EDIT_"):
                idx = int(choice.split("_")[1])
                if 0 <= idx < len(additional_fans):
                    edited = _edit_fan(additional_fans[idx])
                    if edited:
                        additional_fans[idx] = edited
            elif choice.startswith("DELETE_"):
                idx = int(choice.split("_")[1])
                if 0 <= idx < len(additional_fans):
                    if self.ui.yesno(f"Delete fan '{additional_fans[idx].get('name', 'Unknown')}'?", title="Confirm Delete"):
                        additional_fans.pop(idx)

        # Multi-pin groups (for hotend cooling with multiple fans, etc.)
        # Be defensive: older/broken state may contain multi_pin entries without "pins".
        multi_pins = []
        cleaned_additional_fans = []
        for fan in additional_fans:
            if not isinstance(fan, dict):
                continue
            if not fan.get("name"):
                continue
            if fan.get("pin_type") == "multi_pin":
                pins = fan.get("pins")
                mp_name = fan.get("multi_pin_name") or fan.get("name")
                if not pins:
                    # Skip invalid entry (prevents KeyError 'pins')
                    continue
                cleaned_additional_fans.append(fan)
                multi_pins.append({"name": mp_name, "pins": pins})
            else:
                cleaned_additional_fans.append(fan)

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
        # Save progress even if user later cancels out
        self.state.save()

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
        # Save progress even if user later cancels out
        self.state.save()

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
        # Save progress even if user later cancels out
        self.state.save()

        if cleaned_additional_fans:
            self.state.set("fans.additional_fans", cleaned_additional_fans)
        else:
            self.state.delete("fans.additional_fans")
        if multi_pins:
            self.state.set("advanced.multi_pins", multi_pins)
        else:
            self.state.delete("advanced.multi_pins")

        self.state.save()

        summary = (
            f"Part cooling: {part_location} ({part_pin})\n"
            f"Hotend: {hotend_location} ({hotend_pin})\n"
            f"Controller fan: {'Yes (' + controller_pin + ')' if has_controller_fan and controller_pin else 'No'}"
        )
        if cleaned_additional_fans:
            summary += f"\nAdditional: {', '.join(f.get('name', 'Unknown') for f in cleaned_additional_fans)}"

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

        # Load saved probe type
        current_probe_type = self.state.get("probe.probe_type", "tap")
        probe_type = self.ui.radiolist(
            "Select your probe type:",
            [(k, v, k == current_probe_type) for k, v in probe_types],
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
            current_x_offset = self.state.get("probe.x_offset", 0.0)
            current_y_offset = self.state.get("probe.y_offset", 0.0)
            default_y = str(int(current_y_offset)) if current_y_offset else ("25" if probe_type in eddy_probes else "0")
            x_offset = self.ui.inputbox(
                "Probe X offset from nozzle (mm):",
                default=str(int(current_x_offset)),
                title="Probe - X Offset"
            )
            y_offset = self.ui.inputbox(
                "Probe Y offset from nozzle (mm):",
                default=default_y,
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

            # Load saved serial
            current_serial = self.state.get("probe.serial", "")

            if serial_devices:
                # Build mapping: short_name -> full_path
                serial_map = {}
                device_items = []
                selected_index = 0
                for i, d in enumerate(serial_devices):
                    short_name = self._format_serial_name(d)
                    tag = f"{i+1}. {short_name}"
                    serial_map[tag] = d
                    # Check if this matches saved serial
                    is_current = str(d) == current_serial
                    if is_current:
                        selected_index = i
                    device_items.append((tag, "", is_current))

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
                        default=current_serial or "/dev/serial/by-id/usb-"
                    )
                else:
                    serial = None
            else:
                serial = self.ui.inputbox(
                    f"Enter {probe_type} serial path:\n\n"
                    "(No devices auto-detected)",
                    default=current_serial or "/dev/serial/by-id/usb-"
                )

            # Homing mode selection
            current_homing_mode = self.state.get("probe.homing_mode", "")
            if probe_type == "beacon":
                homing_mode = self.ui.radiolist(
                    "Beacon homing mode:",
                    [
                        ("contact", "Contact (nozzle touches bed)", current_homing_mode == "contact" or (not current_homing_mode and True)),
                        ("proximity", "Proximity (non-contact)", current_homing_mode == "proximity"),
                    ],
                    title="Beacon - Homing Mode"
                )

                if homing_mode == "contact":
                    current_contact_temp = self.state.get("probe.contact_max_hotend_temperature", 180)
                    contact_max_temp = self.ui.inputbox(
                        "Max hotend temp for contact probing (°C):\n\n"
                        "(Prevents damage from hot nozzle contact)",
                        default=str(current_contact_temp),
                        title="Beacon - Contact Temp"
                    )

            elif probe_type == "cartographer":
                homing_mode = self.ui.radiolist(
                    "Cartographer homing mode:",
                    [
                        ("touch", "Touch (contact homing)", current_homing_mode == "touch" or (not current_homing_mode and True)),
                        ("scan", "Scan (proximity homing)", current_homing_mode == "scan"),
                    ],
                    title="Cartographer - Homing Mode"
                )

            elif probe_type == "btt_eddy":
                homing_mode = self.ui.radiolist(
                    "BTT Eddy mesh method:",
                    [
                        ("rapid_scan", "Rapid Scan (fast)", current_homing_mode == "rapid_scan" or (not current_homing_mode and True)),
                        ("scan", "Standard Scan", current_homing_mode == "scan"),
                    ],
                    title="BTT Eddy - Mesh Method"
                )

            # Mesh settings for eddy probes
            current_mesh_direction = self.state.get("probe.mesh_main_direction", "y")
            mesh_main_direction = self.ui.radiolist(
                "Mesh scan direction:",
                [
                    ("x", "X direction", current_mesh_direction == "x"),
                    ("y", "Y direction", current_mesh_direction == "y" or (not current_mesh_direction and True)),
                ],
                title="Probe - Mesh Direction"
            )

            current_mesh_runs = self.state.get("probe.mesh_runs", 1)
            mesh_runs = self.ui.radiolist(
                "Mesh scan passes:",
                [
                    ("1", "1 pass (faster)", current_mesh_runs == 1 or (not current_mesh_runs and True)),
                    ("2", "2 passes (more accurate)", current_mesh_runs == 2),
                ],
                title="Probe - Mesh Runs"
            )

        # Location for non-eddy probes
        has_toolboard = self.state.get("mcu.toolboard.connection_type")
        location = None
        if probe_type not in eddy_probes:
            current_location = self.state.get("probe.location", "toolboard" if has_toolboard else "mainboard")
            if has_toolboard:
                location = self.ui.radiolist(
                    "Probe connected to:",
                    [
                        ("mainboard", "Mainboard", current_location == "mainboard"),
                        ("toolboard", "Toolboard", current_location == "toolboard" or (not current_location and True)),
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
        current_method = self.state.get("homing.homing_method", "")

        # Homing method based on probe
        if probe_type in ["beacon", "cartographer"]:
            methods = [
                ("beacon_contact", "Beacon Contact", current_method == "beacon_contact" or (not current_method and True)),
                ("homing_override", "Custom Homing Override", current_method == "homing_override"),
            ]
        else:
            methods = [
                ("safe_z_home", "Safe Z Home (standard)", current_method == "safe_z_home" or (not current_method and True)),
                ("homing_override", "Homing Override (sensorless)", current_method == "homing_override"),
            ]

        method = self.ui.radiolist(
            "Z homing method:",
            methods,
            title="Homing - Method"
        )

        # Z hop
        current_z_hop = self.state.get("homing.z_hop", 10)
        z_hop = self.ui.inputbox(
            "Z hop height for homing (mm):",
            default=str(current_z_hop),
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
        probe_type = self.state.get("probe.probe_type", "none")
        eddy_probes = {"beacon", "cartographer", "btt_eddy"}
        is_eddy_probe = probe_type in eddy_probes

        def _format_leveling_type(value: str) -> str:
            if not value or value == "none":
                return "None"
            return value.replace("_", " ").upper() if value == "qgl" else value.replace("_", " ").title()

        def _configure_mesh() -> None:
            current_mesh_enabled = self.state.get("bed_leveling.bed_mesh.enabled", False)
            enable_mesh = self.ui.yesno(
                "Enable bed mesh?",
                title="Bed Leveling - Bed Mesh",
                default_no=not current_mesh_enabled
            )

            # Mesh boundaries and/or probe count
            current_probe_count = self.state.get("bed_leveling.bed_mesh.probe_count", "5,5")
            current_mesh_min = self.state.get("bed_leveling.bed_mesh.mesh_min", None)
            current_mesh_max = self.state.get("bed_leveling.bed_mesh.mesh_max", None)

            probe_count = current_probe_count
            mesh_min = current_mesh_min
            mesh_max = current_mesh_max

            if enable_mesh:
                # Defaults for mesh boundaries (same logic as schema/config-sections.yaml "auto")
                bed_x = float(self.state.get("printer.bed_size_x", 300))
                bed_y = float(self.state.get("printer.bed_size_y", 300))
                x_off = float(self.state.get("probe.x_offset", 0.0))
                y_off = float(self.state.get("probe.y_offset", 0.0))
                default_mesh_min = f"{int(abs(x_off) + 10)}, {int(abs(y_off) + 10)}"
                default_mesh_max = f"{int(bed_x - abs(x_off) - 10)}, {int(bed_y - abs(y_off) - 10)}"

                if is_eddy_probe:
                    # Eddy probes use rapid scanning; boundaries matter most.
                    mesh_min = self.ui.inputbox(
                        "Mesh minimum (x, y):\n\n"
                        "Defines the start of the scan area.\n"
                        "Example: 15, 28\n"
                        "You can also enter 'auto' to let gschpoozi calculate safe bounds.",
                        default=(mesh_min if mesh_min not in [None, ""] else default_mesh_min),
                        title="Bed Mesh - Mesh Min"
                    )
                    if mesh_min is None:
                        return

                    mesh_max = self.ui.inputbox(
                        "Mesh maximum (x, y):\n\n"
                        "Defines the end of the scan area.\n"
                        "Example: 315, 280\n"
                        "You can also enter 'auto' to let gschpoozi calculate safe bounds.",
                        default=(mesh_max if mesh_max not in [None, ""] else default_mesh_max),
                        title="Bed Mesh - Mesh Max"
                    )
                    if mesh_max is None:
                        return

                    # Keep probe_count as-is for compatibility, but don't force the user to set it here.
                    probe_count = current_probe_count
                else:
                    # Standard probes: probe_count is the primary setting; default boundaries to auto if not set.
                    probe_count = self.ui.inputbox(
                        "Mesh probe count (e.g., 5,5):",
                        default=current_probe_count,
                        title="Bed Mesh - Probe Count"
                    )
                    if probe_count is None:
                        return
                    if not mesh_min:
                        mesh_min = "auto"
                    if not mesh_max:
                        mesh_max = "auto"

            self.state.set("bed_leveling.bed_mesh.enabled", enable_mesh)
            self.state.set("bed_leveling.bed_mesh.probe_count", probe_count)
            if enable_mesh:
                # Always store boundaries (template supports "auto")
                self.state.set("bed_leveling.bed_mesh.mesh_min", mesh_min or "auto")
                self.state.set("bed_leveling.bed_mesh.mesh_max", mesh_max or "auto")
            self.state.save()

            mesh_details = ""
            if enable_mesh:
                if is_eddy_probe:
                    mesh_details = f"Mesh min/max: {mesh_min} → {mesh_max}\n"
                else:
                    mesh_details = f"Probe count: {probe_count}\n"

            self.ui.msgbox(
                f"Bed mesh saved!\n\n"
                f"Mesh: {'Enabled' if enable_mesh else 'Disabled'}\n"
                f"{mesh_details}",
                title="Configuration Saved"
            )

        def _configure_leveling_method() -> None:
            current_leveling_type = self.state.get("bed_leveling.leveling_type", "none") or "none"

            # Leveling type based on Z motor count
            if z_count == 4:
                leveling_options = [
                    ("qgl", "Quad Gantry Level", current_leveling_type == "qgl"),
                    ("none", "None", current_leveling_type == "none"),
                ]
            elif z_count >= 2:
                leveling_options = [
                    ("z_tilt", "Z Tilt Adjust", current_leveling_type == "z_tilt"),
                    ("none", "None", current_leveling_type == "none"),
                ]
            else:
                self.ui.msgbox(
                    "You have a single Z stepper.\n\n"
                    "Z Tilt / QGL are not applicable.\n"
                    "You can still configure Bed Mesh from this menu.",
                    title="Leveling Method"
                )
                return

            leveling_type = self.ui.radiolist(
                "Leveling method (optional):",
                leveling_options,
                title="Bed Leveling - Method"
            )
            if leveling_type is None:
                return

            self.state.set("bed_leveling.leveling_type", leveling_type or "none")
            self.state.save()

            self.ui.msgbox(
                f"Leveling method saved!\n\n"
                f"Method: {_format_leveling_type(leveling_type)}",
                title="Configuration Saved"
            )

        # Top-level menu: always offer bed mesh; offer method only when applicable.
        while True:
            current_method = self.state.get("bed_leveling.leveling_type", "none") or "none"
            current_mesh_enabled = self.state.get("bed_leveling.bed_mesh.enabled", False)
            mesh_status = "Enabled" if current_mesh_enabled else "Disabled"
            method_status = _format_leveling_type(current_method)

            menu_items = [
                ("MESH", f"Bed Mesh ({mesh_status})"),
            ]
            if z_count >= 2:
                label = "Leveling Method (QGL)" if z_count == 4 else "Leveling Method (Z Tilt)"
                menu_items.append(("METHOD", f"{label} ({method_status})"))
            else:
                menu_items.append(("METHOD", f"Leveling Method ({method_status})"))

            menu_items.append(("DONE", "Done"))

            choice = self.ui.menu(
                "Bed Leveling\n\n"
                "Configure bed mesh and (optional) gantry leveling.\n"
                "Mesh is independent and works on single-Z setups too.",
                menu_items,
                title="Bed Leveling"
            )

            if choice is None or choice == "DONE":
                break
            if choice == "MESH":
                _configure_mesh()
            elif choice == "METHOD":
                _configure_leveling_method()

    def _temperature_sensors_setup(self) -> None:
        """Configure temperature sensors."""
        sensors = []

        # --- Migration: older wizard versions stored temperature_sensors as a LIST ---
        # That breaks nested keys like temperature_sensors.mcu_main.enabled and causes:
        # "'list' object has no attribute 'setdefault'".
        legacy_ts = self.state.get("temperature_sensors", None)
        if isinstance(legacy_ts, list):
            built_in_names = {"mcu_temp", "host_temp", "toolboard_temp", "chamber"}
            legacy_by_name = {
                s.get("name"): s for s in legacy_ts
                if isinstance(s, dict) and s.get("name")
            }

            # Infer enable flags from legacy list entries
            self.state.delete("temperature_sensors")
            self.state.set("temperature_sensors.mcu_main.enabled", "mcu_temp" in legacy_by_name)
            self.state.set("temperature_sensors.host.enabled", "host_temp" in legacy_by_name)
            self.state.set("temperature_sensors.toolboard.enabled", "toolboard_temp" in legacy_by_name)

            chamber = legacy_by_name.get("chamber")
            if isinstance(chamber, dict):
                self.state.set("temperature_sensors.chamber.enabled", True)
                if chamber.get("sensor_type"):
                    self.state.set("temperature_sensors.chamber.sensor_type", chamber.get("sensor_type"))
                if chamber.get("sensor_location"):
                    self.state.set("temperature_sensors.chamber.sensor_location", chamber.get("sensor_location"))
                # Legacy stored a single sensor_pin; map it back to the appropriate field
                if chamber.get("sensor_pin"):
                    if chamber.get("sensor_location") == "rpi":
                        self.state.set("temperature_sensors.chamber.sensor_pin_rpi", chamber.get("sensor_pin"))
                    else:
                        self.state.set("temperature_sensors.chamber.sensor_port_mainboard", chamber.get("sensor_pin"))
                if chamber.get("pullup_resistor"):
                    self.state.set("temperature_sensors.chamber.pullup_resistor", chamber.get("pullup_resistor"))
            else:
                self.state.delete("temperature_sensors.chamber")

            # Preserve any non built-in sensors as "additional"
            additional = [
                s for s in legacy_ts
                if isinstance(s, dict) and s.get("name") not in built_in_names
            ]
            self.state.set("temperature_sensors.additional", additional)
            self.state.save()

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

        # Additional sensors - load existing and filter out built-in ones
        existing_sensors = self.state.get("temperature_sensors.additional", [])
        if not isinstance(existing_sensors, list):
            existing_sensors = []

        additional_sensors = [s for s in existing_sensors if isinstance(s, dict)]

        def _edit_additional_sensor(sensor=None):
            """Edit or add an additional temperature sensor. If sensor is None, add new."""
            if sensor:
                name = self.ui.inputbox(
                    "Sensor name:",
                    default=sensor.get("name", ""),
                    title="Edit Sensor"
                )
            else:
                name = self.ui.inputbox(
                    "Sensor name:",
                    default="",
                    title="Add Sensor"
                )

            if not name:
                return None

            current_type = sensor.get("sensor_type", "Generic 3950") if sensor else None
            sensor_type = self.ui.radiolist(
                f"Sensor type for '{name}':",
                [
                    ("Generic 3950", "Generic 3950 (NTC)", current_type == "Generic 3950" if current_type else True),
                    ("ATC Semitec 104GT-2", "ATC Semitec 104GT-2", current_type == "ATC Semitec 104GT-2"),
                    ("PT1000", "PT1000", current_type == "PT1000"),
                    ("DS18B20", "DS18B20 (1-wire)", current_type == "DS18B20"),
                ],
                title="Sensor Type"
            )

            current_pin = sensor.get("sensor_pin", "") if sensor else None
            sensor_pin = self.ui.inputbox(
                f"Pin for '{name}':",
                default=current_pin or "",
                title="Sensor Pin"
            )

            if sensor_pin:
                return {
                    "name": name,
                    "type": "temperature_sensor",
                    "sensor_type": sensor_type,
                    "sensor_pin": sensor_pin
                }
            return None

        # Management loop for additional sensors
        while True:
            menu_items = [("ADD", "Add new temperature sensor")]
            for i, sensor in enumerate(additional_sensors):
                menu_items.append((f"EDIT_{i}", f"Edit: {sensor.get('name', 'Unknown')}"))
            for i, sensor in enumerate(additional_sensors):
                menu_items.append((f"DELETE_{i}", f"Delete: {sensor.get('name', 'Unknown')}"))
            menu_items.append(("DONE", "Done (save and exit)"))

            choice = self.ui.menu(
                f"Additional Temperature Sensors\n\n"
                f"Currently configured: {len(additional_sensors)} sensor(s)\n"
                f"{', '.join(s.get('name', 'Unknown') for s in additional_sensors) if additional_sensors else 'None'}",
                menu_items,
                title="Additional Sensors Management"
            )

            if choice is None or choice == "DONE":
                break
            elif choice == "ADD":
                new_sensor = _edit_additional_sensor()
                if new_sensor:
                    additional_sensors.append(new_sensor)
            elif choice.startswith("EDIT_"):
                idx = int(choice.split("_")[1])
                if 0 <= idx < len(additional_sensors):
                    edited = _edit_additional_sensor(additional_sensors[idx])
                    if edited:
                        additional_sensors[idx] = edited
            elif choice.startswith("DELETE_"):
                idx = int(choice.split("_")[1])
                if 0 <= idx < len(additional_sensors):
                    if self.ui.yesno(f"Delete sensor '{additional_sensors[idx].get('name', 'Unknown')}'?", title="Confirm Delete"):
                        additional_sensors.pop(idx)

        # Rebuild full sensors list: built-in ones + additional ones
        sensors.extend(additional_sensors)

        # Save additional sensors without overwriting the temperature_sensors dict structure
        self.state.set("temperature_sensors.additional", additional_sensors)
        self.state.save()

        sensor_names = [s["name"] for s in sensors]
        self.ui.msgbox(
            f"Temperature sensors configured!\n\n"
            f"Sensors: {', '.join(sensor_names) if sensor_names else 'None'}",
            title="Configuration Saved"
        )

    def _leds_setup(self) -> None:
        """Configure LED strips."""
        # Load existing LEDs from state
        leds = self.state.get("leds", [])
        if not isinstance(leds, list):
            leds = []

        if not self.ui.yesno(
            "Do you have LED strips (Neopixel/WS2812)?",
            title="LED Configuration"
        ):
            self.state.set("leds", [])
            self.state.save()
            return

        has_toolboard = self.state.get("mcu.toolboard.connection_type")

        def _edit_led(led=None):
            """Edit or add an LED. If led is None, add new."""
            if led:
                led_name = self.ui.inputbox(
                    "LED strip name:",
                    default=led.get("name", ""),
                    title="Edit LED"
                )
            else:
                led_name = self.ui.inputbox(
                    "LED strip name (e.g., status_led, chamber_led):",
                    default="status_led" if not leds else "",
                    title="Add LED"
                )

            if not led_name:
                return None

            # Location
            current_location = led.get("location", "toolboard" if has_toolboard else "mainboard") if led else None
            if has_toolboard:
                location = self.ui.radiolist(
                    f"'{led_name}' connected to:",
                    [
                        ("mainboard", "Mainboard", current_location == "mainboard" if current_location else False),
                        ("toolboard", "Toolboard", current_location == "toolboard" if current_location else True),
                    ],
                    title=f"{led_name} - Location"
                )
            else:
                location = "mainboard"

            # Pin
            current_pin = led.get("pin", "") if led else None
            default_pin = current_pin if current_pin else ("PB0" if location == "mainboard" else "PB8")
            pin = self._pick_pin_from_known_ports(
                location=location,
                default_pin=default_pin,
                title=f"{led_name} - Pin",
                prompt=f"Pin for '{led_name}':",
                preferred_groups=["misc_ports", "endstop_ports", "probe_ports"],
            )
            if pin is None:
                return None
            if not isinstance(pin, str) or not pin.strip():
                self.ui.msgbox("LED pin cannot be empty.", title="Invalid LED Pin")
                return None

            # LED count
            current_count = led.get("chain_count", 1) if led else None
            chain_count = self.ui.inputbox(
                f"Number of LEDs in '{led_name}' chain:",
                default=str(current_count) if current_count else "1",
                title=f"{led_name} - Count"
            )

            # Color order
            current_color_order = led.get("color_order", "GRB") if led else None
            color_order = self.ui.radiolist(
                f"Color order for '{led_name}':",
                [
                    ("GRB", "GRB (most common)", current_color_order == "GRB" if current_color_order else True),
                    ("RGB", "RGB", current_color_order == "RGB"),
                    ("GRBW", "GRBW (RGBW with green first)", current_color_order == "GRBW"),
                    ("RGBW", "RGBW", current_color_order == "RGBW"),
                ],
                title=f"{led_name} - Color Order"
            )
            if not color_order:
                self.ui.msgbox("Color order must be selected.", title="Invalid LED Config")
                return None

            return {
                "name": led_name,
                "location": location,
                "pin": pin,
                "chain_count": int(chain_count or 1),
                "color_order": color_order
            }

        # Management loop
        while True:
            menu_items = [("ADD", "Add new LED strip")]
            for i, led in enumerate(leds):
                menu_items.append((f"EDIT_{i}", f"Edit: {led.get('name', 'Unknown')}"))
            for i, led in enumerate(leds):
                menu_items.append((f"DELETE_{i}", f"Delete: {led.get('name', 'Unknown')}"))
            menu_items.append(("DONE", "Done (save and exit)"))

            choice = self.ui.menu(
                f"LED Configuration\n\n"
                f"Currently configured: {len(leds)} LED strip(s)\n"
                f"{', '.join(l.get('name', 'Unknown') for l in leds) if leds else 'None'}",
                menu_items,
                title="LED Management"
            )

            if choice is None or choice == "DONE":
                break
            elif choice == "ADD":
                new_led = _edit_led()
                if new_led:
                    leds.append(new_led)
            elif choice.startswith("EDIT_"):
                idx = int(choice.split("_")[1])
                if 0 <= idx < len(leds):
                    edited = _edit_led(leds[idx])
                    if edited:
                        leds[idx] = edited
            elif choice.startswith("DELETE_"):
                idx = int(choice.split("_")[1])
                if 0 <= idx < len(leds):
                    if self.ui.yesno(f"Delete LED '{leds[idx].get('name', 'Unknown')}'?", title="Confirm Delete"):
                        leds.pop(idx)

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
        # Load existing sensors from state
        sensors = self.state.get("filament_sensors", [])
        if not isinstance(sensors, list):
            sensors = []

        if not self.ui.yesno(
            "Do you have a filament runout sensor?",
            title="Filament Sensor"
        ):
            self.state.set("filament_sensors", [])
            self.state.save()
            return

        has_toolboard = self.state.get("mcu.toolboard.connection_type")

        def _edit_sensor(sensor=None):
            """Edit or add a filament sensor. If sensor is None, add new."""
            if sensor:
                name = self.ui.inputbox(
                    "Sensor name:",
                    default=sensor.get("name", "filament_sensor"),
                    title="Edit Sensor"
                )
            else:
                name = self.ui.inputbox(
                    "Sensor name:",
                    default="filament_sensor",
                    title="Add Sensor"
                )

            if not name:
                return None

            # Sensor type
            current_type = sensor.get("type", "switch") if sensor else None
            sensor_type = self.ui.radiolist(
                "Filament sensor type:",
                [
                    ("switch", "Simple switch (runout only)", current_type == "switch" if current_type else True),
                    ("motion", "Motion sensor (detects movement)", current_type == "motion"),
                    ("encoder", "Encoder (measures filament)", current_type == "encoder"),
                ],
                title="Sensor Type"
            )

            # Location
            current_location = sensor.get("location", "toolboard" if has_toolboard else "mainboard") if sensor else None
            if has_toolboard:
                location = self.ui.radiolist(
                    "Sensor connected to:",
                    [
                        ("mainboard", "Mainboard", current_location == "mainboard" if current_location else False),
                        ("toolboard", "Toolboard", current_location == "toolboard" if current_location else True),
                    ],
                    title="Sensor Location"
                )
            else:
                location = "mainboard"

            # Pin
            current_pin = sensor.get("pin", "") if sensor else None
            default_pin = current_pin if current_pin else ("PG11" if location == "mainboard" else "PB6")
            pin = self._pick_pin_from_known_ports(
                location=location,
                default_pin=default_pin,
                title="Sensor Pin",
                prompt="Sensor pin:",
                preferred_groups=["endstop_ports", "misc_ports", "probe_ports"],
            )
            if pin is None:
                return None

            # Pin modifiers (Klipper): ^ (pull-up), ~ (pull-down), ! (invert)
            # Default pull-up ON to preserve existing behavior (previously hard-coded '^').
            current_pullup = sensor.get("pin_pullup", True) if sensor else True
            current_pulldown = sensor.get("pin_pulldown", False) if sensor else False
            current_invert = sensor.get("pin_invert", False) if sensor else False

            pin_pullup = self.ui.yesno(
                "Enable internal pull-up resistor for this sensor pin?\n\n"
                "Most mechanical runout switches use pull-up (^).",
                title="Sensor Pin - Pull-up",
                default_no=not current_pullup,
            )

            # Only ask for pull-down if pull-up is NOT enabled
            pin_pulldown = False
            if not pin_pullup:
                pin_pulldown = self.ui.yesno(
                    "Enable internal pull-down resistor for this sensor pin?\n\n"
                    "This is rarely needed (~).",
                    title="Sensor Pin - Pull-down",
                    default_no=not current_pulldown,
                )

            pin_invert = self.ui.yesno(
                "Invert the sensor signal (active LOW)?\n\n"
                "If the sensor triggers in reverse, enable inversion (!).",
                title="Sensor Pin - Invert",
                default_no=not current_invert,
            )

            return {
                "name": name,
                "type": sensor_type,
                "location": location,
                "pin": pin,
                "pin_pullup": bool(pin_pullup),
                "pin_pulldown": bool(pin_pulldown),
                "pin_invert": bool(pin_invert),
                "pause_on_runout": sensor.get("pause_on_runout", True) if sensor else True
            }

        # Management loop
        while True:
            menu_items = [("ADD", "Add new filament sensor")]
            for i, sensor in enumerate(sensors):
                menu_items.append((f"EDIT_{i}", f"Edit: {sensor.get('name', 'Unknown')}"))
            for i, sensor in enumerate(sensors):
                menu_items.append((f"DELETE_{i}", f"Delete: {sensor.get('name', 'Unknown')}"))
            menu_items.append(("DONE", "Done (save and exit)"))

            choice = self.ui.menu(
                f"Filament Sensor Configuration\n\n"
                f"Currently configured: {len(sensors)} sensor(s)\n"
                f"{', '.join(s.get('name', 'Unknown') for s in sensors) if sensors else 'None'}",
                menu_items,
                title="Filament Sensor Management"
            )

            if choice is None or choice == "DONE":
                break
            elif choice == "ADD":
                new_sensor = _edit_sensor()
                if new_sensor:
                    sensors.append(new_sensor)
            elif choice.startswith("EDIT_"):
                idx = int(choice.split("_")[1])
                if 0 <= idx < len(sensors):
                    edited = _edit_sensor(sensors[idx])
                    if edited:
                        sensors[idx] = edited
            elif choice.startswith("DELETE_"):
                idx = int(choice.split("_")[1])
                if 0 <= idx < len(sensors):
                    if self.ui.yesno(f"Delete sensor '{sensors[idx].get('name', 'Unknown')}'?", title="Confirm Delete"):
                        sensors.pop(idx)

        # Save
        self.state.set("filament_sensors", sensors)
        self.state.save()

        sensor_names = [s["name"] for s in sensors]
        self.ui.msgbox(
            f"Filament sensor configured!\n\n"
            f"Sensors: {', '.join(sensor_names) if sensor_names else 'None'}",
            title="Configuration Saved"
        )

    def _display_setup(self) -> None:
        """Configure display options (KlipperScreen first)."""
        while True:
            choice = self.ui.menu(
                "Display Configuration\n\n"
                "Configure display hardware and UI.\n\n"
                "KlipperScreen runs on the host (Pi/CB1) and connects to Moonraker.",
                [
                    ("KS", "KlipperScreen         (Touch UI on host)"),
                    ("LCD", "LCD/OLED              (Direct display via Klipper) - Coming soon"),
                    ("B", "Back"),
                ],
                title="2.15 Display",
            )
            if choice is None or choice == "B":
                return
            if choice == "KS":
                self._klipperscreen_setup()
            else:
                self.ui.msgbox("Coming soon!", title="Display")

    def _klipperscreen_setup(self) -> None:
        """KlipperScreen management (install/update/remove + config)."""
        displays = self._load_hardware_template("displays.json")
        ks_meta = displays.get("klipperscreen", {}) if isinstance(displays, dict) else {}
        install_cmd = (ks_meta.get("installation", {}) or {}).get("command", "")
        update_mgr = (ks_meta.get("moonraker_update_manager", {}) or {}).get("update_manager KlipperScreen", {})

        ks_dir = Path.home() / "KlipperScreen"
        conf_path = ks_dir / "KlipperScreen.conf"

        # Detect service state
        def _service_state() -> tuple[bool, bool, str]:
            installed = ks_dir.exists()
            running = False
            svc_name = "KlipperScreen"
            if installed:
                try:
                    import subprocess
                    for svc in ("KlipperScreen", "klipperscreen"):
                        result = subprocess.run(
                            ["systemctl", "is-active", svc],
                            capture_output=True,
                            text=True,
                        )
                        if result.stdout.strip() == "active":
                            running = True
                            svc_name = svc
                            break
                except Exception:
                    running = False
            return installed, running, svc_name

        while True:
            installed, running, svc_name = _service_state()
            enabled = self.state.get("display.klipperscreen.enabled", False)
            host = self.state.get("display.klipperscreen.moonraker_host", "127.0.0.1")
            port = int(self.state.get("display.klipperscreen.moonraker_port", 7125))

            status = []
            status.append(f"Installed: {'Yes' if installed else 'No'}")
            status.append(f"Service: {'Running' if running else ('Stopped' if installed else 'N/A')}")
            status.append(f"Config: {str(conf_path) if installed else str(conf_path)}")
            status.append(f"Moonraker: {host}:{port}")
            status.append(f"Wizard enabled: {'Yes' if enabled else 'No'}")

            choice = self.ui.menu(
                "KlipperScreen\n\n"
                + "\n".join(status)
                + "\n\nSelect an action:",
                [
                    ("ENABLE", "Enable/Disable (wizard state)"),
                    ("CONF", "Configure Moonraker connection (KlipperScreen.conf)"),
                    ("UM", "Ensure Moonraker update_manager entry"),
                    ("INSTALL", "Install KlipperScreen"),
                    ("UPDATE", "Update KlipperScreen (git pull + restart)"),
                    ("REMOVE", "Remove KlipperScreen"),
                    ("B", "Back"),
                ],
                title="KlipperScreen",
                height=22,
                width=120,
                menu_height=10,
            )

            if choice is None or choice == "B":
                return

            if choice == "ENABLE":
                new_enabled = self.ui.yesno(
                    "Enable KlipperScreen in wizard?\n\n"
                    "This does not install it, but marks it as desired and enables status display.",
                    title="KlipperScreen - Enable",
                    default_no=enabled,
                )
                self.state.set("display.klipperscreen.enabled", bool(new_enabled))
                self.state.save()
                continue

    def _advanced_setup(self) -> None:
        """Configure advanced features (generator-backed)."""
        while True:
            multi_pins = self.state.get("advanced.multi_pins", [])
            multi_pin_status = f"{len(multi_pins)} group(s)" if isinstance(multi_pins, list) and multi_pins else None
            fm_enabled = self.state.get("advanced.force_move.enable_force_move", False)
            fr_enabled = self.state.get("advanced.firmware_retraction.enabled", False)
            inc_mainsail = self.state.get("includes.mainsail.enabled")
            inc_timelapse = self.state.get("includes.timelapse.enabled")
            inc_status = None
            if inc_mainsail or inc_timelapse:
                parts = []
                if inc_mainsail:
                    parts.append("mainsail")
                if inc_timelapse:
                    parts.append("timelapse")
                inc_status = ", ".join(parts)

            choice = self.ui.menu(
                "Advanced Configuration\n\n"
                "Optional Klipper features.\n\n"
                "Only items that are already supported by the generator are exposed here.",
                [
                    ("MP", self._format_menu_item("Multi-pin groups", multi_pin_status) if multi_pin_status else "Multi-pin groups      ([multi_pin])"),
                    ("FM", self._format_menu_item("Force move", "Enabled" if fm_enabled else None) if fm_enabled else "Force move            ([force_move])"),
                    ("FR", self._format_menu_item("Firmware retraction", "Enabled" if fr_enabled else None) if fr_enabled else "Firmware retraction   ([firmware_retraction])"),
                    ("INC", self._format_menu_item("printer.cfg includes", inc_status) if inc_status else "printer.cfg includes  (mainsail/timelapse)"),
                    ("B", "Back"),
                ],
                title="2.16 Advanced",
                height=20,
                width=120,
                menu_height=10,
            )
            if choice is None or choice == "B":
                return
            if choice == "MP":
                self._advanced_multi_pin_setup()
            elif choice == "FM":
                self._advanced_force_move_setup()
            elif choice == "FR":
                self._advanced_firmware_retraction_setup()
            elif choice == "INC":
                self._advanced_printer_cfg_includes_setup()

    def _advanced_printer_cfg_includes_setup(self) -> None:
        """Manage wizard-controlled non-gschpoozi includes in printer.cfg."""
        # Best-effort detection from existing printer.cfg (on the printer).
        detected_mainsail = False
        detected_timelapse = False
        try:
            cfg_path = Path.home() / "printer_data" / "config" / "printer.cfg"
            if cfg_path.exists():
                txt = cfg_path.read_text(encoding="utf-8", errors="ignore")
                detected_mainsail = "[include mainsail.cfg]" in txt
                detected_timelapse = "[include timelapse.cfg]" in txt
        except Exception:
            pass

        current_mainsail = self.state.get("includes.mainsail.enabled", detected_mainsail)
        current_timelapse = self.state.get("includes.timelapse.enabled", detected_timelapse)

        mainsail = self.ui.yesno(
            "Include mainsail.cfg in printer.cfg?",
            title="printer.cfg includes - Mainsail",
            default_no=not bool(current_mainsail),
        )
        timelapse = self.ui.yesno(
            "Include timelapse.cfg in printer.cfg?",
            title="printer.cfg includes - Timelapse",
            default_no=not bool(current_timelapse),
        )

        self.state.set("includes.mainsail.enabled", bool(mainsail))
        self.state.set("includes.timelapse.enabled", bool(timelapse))
        self.state.save()

        self.ui.msgbox(
            "printer.cfg includes saved!\n\n"
            f"mainsail.cfg: {'Enabled' if mainsail else 'Disabled'}\n"
            f"timelapse.cfg: {'Enabled' if timelapse else 'Disabled'}",
            title="Configuration Saved",
        )

    def _advanced_multi_pin_setup(self) -> None:
        """Manage multi-pin groups (advanced.multi_pins)."""
        groups = self.state.get("advanced.multi_pins", [])
        if not isinstance(groups, list):
            groups = []

        def _edit_group(group=None):
            current_name = group.get("name", "") if isinstance(group, dict) else ""
            current_pins = group.get("pins", "") if isinstance(group, dict) else ""

            name = self.ui.inputbox(
                "Multi-pin group name:\n\nExample: part_fans, exhaust_pair",
                default=current_name or "",
                title="Multi-pin - Name",
            )
            if name is None or not name.strip():
                return None

            pins = self.ui.inputbox(
                "Pins (comma-separated):\n\nExample: PA1, PA2\n\n"
                "Use Klipper pin syntax (you can include toolboard: prefix if needed).",
                default=current_pins or "",
                title="Multi-pin - Pins",
                height=12,
                width=90,
            )
            if pins is None or not pins.strip():
                return None

            return {"name": name.strip(), "pins": pins.strip()}

        while True:
            menu_items = [("ADD", "Add new multi-pin group")]
            for i, g in enumerate(groups):
                if isinstance(g, dict):
                    menu_items.append((f"EDIT_{i}", f"Edit: {g.get('name', 'Unnamed')}"))
            for i, g in enumerate(groups):
                if isinstance(g, dict):
                    menu_items.append((f"DELETE_{i}", f"Delete: {g.get('name', 'Unnamed')}"))
            menu_items.append(("DONE", "Done"))

            choice = self.ui.menu(
                "Multi-pin groups\n\n"
                "These create [multi_pin <name>] sections for sharing pins.\n"
                "Useful for fans that need multiple outputs.\n\n"
                f"Currently configured: {len([g for g in groups if isinstance(g, dict)])}",
                menu_items,
                title="Multi-pin groups",
                height=22,
                width=120,
                menu_height=12,
            )
            if choice is None or choice == "DONE":
                break
            if choice == "ADD":
                new_g = _edit_group()
                if new_g:
                    groups.append(new_g)
            elif choice.startswith("EDIT_"):
                idx = int(choice.split("_", 1)[1])
                if 0 <= idx < len(groups) and isinstance(groups[idx], dict):
                    edited = _edit_group(groups[idx])
                    if edited:
                        groups[idx] = edited
            elif choice.startswith("DELETE_"):
                idx = int(choice.split("_", 1)[1])
                if 0 <= idx < len(groups) and isinstance(groups[idx], dict):
                    if self.ui.yesno(f"Delete multi-pin group '{groups[idx].get('name', 'Unnamed')}'?", title="Confirm Delete", default_no=True):
                        groups.pop(idx)

        # Save
        # If empty, clear key to avoid stale config
        cleaned = [g for g in groups if isinstance(g, dict) and g.get("name") and g.get("pins")]
        if cleaned:
            self.state.set("advanced.multi_pins", cleaned)
        else:
            self.state.delete("advanced.multi_pins")
        self.state.save()

        self.ui.msgbox(
            f"Multi-pin groups saved!\n\nCount: {len(cleaned)}",
            title="Configuration Saved",
        )

    def _advanced_force_move_setup(self) -> None:
        """Configure [force_move]."""
        current = self.state.get("advanced.force_move.enable_force_move", False)
        enabled = self.ui.yesno(
            "Enable [force_move]?\n\n"
            "This allows moving steppers without homing.\n"
            "Use with care.",
            title="Force move",
            default_no=not current,
            height=12,
            width=80,
        )
        self.state.set("advanced.force_move.enable_force_move", bool(enabled))
        self.state.save()
        self.ui.msgbox(
            f"Force move: {'Enabled' if enabled else 'Disabled'}",
            title="Configuration Saved",
        )

    def _advanced_firmware_retraction_setup(self) -> None:
        """Configure [firmware_retraction]."""
        current_enabled = self.state.get("advanced.firmware_retraction.enabled", False)
        enabled = self.ui.yesno(
            "Enable firmware retraction?\n\n"
            "This adds [firmware_retraction] so slicers can use G10/G11.\n"
            "You can still use normal retractions if disabled.",
            title="Firmware retraction",
            default_no=not current_enabled,
            height=13,
            width=90,
        )
        self.state.set("advanced.firmware_retraction.enabled", bool(enabled))
        if not enabled:
            self.state.save()
            self.ui.msgbox("Firmware retraction disabled.", title="Saved")
            return

        retract_length = self.ui.inputbox(
            "Retract length (mm):",
            default=str(self.state.get("advanced.firmware_retraction.retract_length", 0.5)),
            title="Firmware retraction - Retract length",
        )
        if retract_length is None:
            return
        retract_speed = self.ui.inputbox(
            "Retract speed (mm/s):",
            default=str(self.state.get("advanced.firmware_retraction.retract_speed", 35)),
            title="Firmware retraction - Retract speed",
        )
        if retract_speed is None:
            return
        unretract_extra_length = self.ui.inputbox(
            "Unretract extra length (mm):",
            default=str(self.state.get("advanced.firmware_retraction.unretract_extra_length", 0.0)),
            title="Firmware retraction - Unretract extra",
        )
        if unretract_extra_length is None:
            return
        unretract_speed = self.ui.inputbox(
            "Unretract speed (mm/s):",
            default=str(self.state.get("advanced.firmware_retraction.unretract_speed", 35)),
            title="Firmware retraction - Unretract speed",
        )
        if unretract_speed is None:
            return

        try:
            self.state.set("advanced.firmware_retraction.retract_length", float(retract_length))
            self.state.set("advanced.firmware_retraction.retract_speed", float(retract_speed))
            self.state.set("advanced.firmware_retraction.unretract_extra_length", float(unretract_extra_length))
            self.state.set("advanced.firmware_retraction.unretract_speed", float(unretract_speed))
            self.state.save()
        except ValueError:
            self.ui.msgbox("Invalid number entered. Please try again.", title="Error")
            return

        self.ui.msgbox(
            "Firmware retraction saved!",
            title="Configuration Saved",
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

