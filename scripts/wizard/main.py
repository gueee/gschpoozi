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
import traceback
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from wizard.ui import WizardUI
from wizard.state import get_state, WizardState
from wizard.pins import PinManager

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

    def _get_pin_manager(self) -> PinManager:
        """Create a PinManager with current board data."""
        board_id = self.state.get("mcu.main.board_type", "")
        board_data = self._load_board_data(board_id, "boards") if board_id else {}

        toolboard_id = self.state.get("mcu.toolboard.board_type", "")
        toolboard_data = self._load_board_data(toolboard_id, "toolboards") if toolboard_id else {}

        return PinManager(self.state, self.ui, board_data, toolboard_data)

    def _wizard_log_path(self) -> Path:
        # Keep logs next to the state file so users can find it easily.
        return Path.home() / "printer_data" / "config" / ".gschpoozi_wizard.log"

    def _log_wizard(self, message: str) -> None:
        """Best-effort logging for diagnosing whiptail / control-flow issues."""
        try:
            from datetime import datetime
            ts = datetime.now().isoformat(timespec="seconds")
            path = self._wizard_log_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"{ts} {message}\n")
        except Exception:
            # Logging must never break the wizard.
            pass

    def _inputbox_debug(
        self,
        text: str,
        *,
        default: str = "",
        title: str | None = None,
        height: int = 8,
        width: int = 60,
        debug_key: str = "",
    ) -> str | None:
        """
        Inputbox that distinguishes Cancel vs. other whiptail failures and logs details.

        Returns:
            - str on OK
            - None on Cancel/Esc or whiptail failure
        """
        # Prefer going through the UI runner so we can capture the whiptail return code.
        try:
            args = [
                "--title",
                title or getattr(self.ui, "title", "gschpoozi"),
                "--inputbox",
                text,
                str(height),
                str(width),
                # Important: defaults like "-4" must not be parsed as whiptail CLI options.
                "--",
                default,
            ]
            rc, out = self.ui._run(args)  # type: ignore[attr-defined]
        except Exception as e:
            self._log_wizard(f"inputbox:{debug_key} exception={type(e).__name__}:{e}")
            return None

        if rc == 0:
            return out

        # rc is non-zero: Cancel/Esc or a whiptail failure. We can't assume user error.
        self._log_wizard(f"inputbox:{debug_key} rc={rc} out={out!r}")
        return None

    def _run_tty_command(self, cmd: list[str]) -> int:
        """
        Run an interactive command on /dev/tty.

        We use this for KIAUH-like installers that require a real TTY for prompts,
        sudo password entry, and screen control.
        """
        import subprocess
        try:
            with open("/dev/tty", "r+") as tty:
                result = subprocess.run(cmd, stdin=tty, stdout=tty, stderr=tty, text=True)
                return int(result.returncode)
        except OSError:
            # Fallback: best-effort without explicit tty binding
            result = subprocess.run(cmd)
            return int(result.returncode)

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

    def _load_mmu_template(self, filename: str) -> dict:
        """Load a JSON template from templates/mmu/ (e.g. mmu-types.json)."""
        try:
            mmu_dir = REPO_ROOT / "templates" / "mmu"
            path = mmu_dir / filename
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

    def _run_shell_interactive(self, command: str) -> int:
        """Run a shell command interactively (KIAUH-style).

        Output streams directly to terminal. For commands that need user interaction.
        Returns the exit code.
        """
        import subprocess
        # KIAUH approach: run without capturing output, let it stream to terminal
        # stderr=PIPE to capture errors, but stdout goes to terminal
        try:
            result = subprocess.run(command, shell=True, check=False)
            return result.returncode
        except Exception:
            return 1

    def _run_systemctl(self, action: str, service: str) -> bool:
        """Run systemctl command interactively (allows sudo password prompt).

        Returns True on success, False on failure.
        """
        exit_code = self._run_shell_interactive(f"sudo systemctl {action} {service}")
        return exit_code == 0

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

        # Get PinManager to check for assignments
        pin_manager = self._get_pin_manager()
        location = "mainboard" if board_type == "boards" else "toolboard"

        result = []
        for port_id, port_info in ports.items():
            if isinstance(port_info, dict):
                label = port_info.get("label", port_id)
                # Include pin info if available
                pin = port_info.get("pin", port_info.get("signal_pin", ""))
                # Check for alternative name (e.g., PWM_out)
                alt_name = port_info.get("name", port_info.get("alt_name", ""))

                # Build comprehensive label showing all identifiers
                parts = []
                if pin:
                    parts.append(pin)
                if alt_name:
                    parts.append(alt_name)

                if parts:
                    # Format: "Port ID (pin - alt_name)" or "Port ID (pin)"
                    identifiers = " - ".join(parts)
                    label = f"{port_id} ({identifiers}) - {label}"
                elif pin:
                    label = f"{port_id} ({pin}) - {label}"
                else:
                    label = f"{port_id} - {label}"
            else:
                label = port_id

            # Add assignment info if port is used
            assigned_to = pin_manager.get_used_by(location, port_id)
            if assigned_to:
                label = f"{label} ⚠️ Assigned to: {assigned_to}"

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

        # Get PinManager to check for assignments
        pin_manager = self._get_pin_manager()

        options = []
        tag_to_pin = {}
        selected_tag = None

        def _add_option(tag: str, desc: str, pin: str, port_id: str = None) -> None:
            nonlocal selected_tag
            if not pin or not isinstance(pin, str):
                return
            tag_to_pin[tag] = pin
            is_selected = False
            if default_pin and pin == default_pin and selected_tag is None:
                is_selected = True
                selected_tag = tag

            # Add assignment info if port_id is provided and it's assigned
            if port_id:
                assigned_to = pin_manager.get_used_by(location, port_id)
                if assigned_to:
                    desc = f"{desc} ⚠️ Assigned to: {assigned_to}"

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
                        _add_option(tag, f"{port_id}-{sub_id} ({sub_pin}) [{group}]", str(sub_pin), port_id)
                    continue

                if isinstance(port_info, dict):
                    # Get alternative name if available
                    alt_name = port_info.get("name", port_info.get("alt_name", ""))

                    # Common forms
                    if "pin" in port_info:
                        tag = f"{group}:{port_id}:pin"
                        pin_str = str(port_info["pin"])
                        # Build description with all identifiers
                        if alt_name:
                            desc = f"{port_id} ({pin_str} - {alt_name}) [{group}]"
                        else:
                            desc = f"{port_id} ({pin_str}) [{group}]"
                        _add_option(tag, desc, pin_str, port_id)
                    if "signal_pin" in port_info:
                        tag = f"{group}:{port_id}:signal"
                        signal_str = str(port_info["signal_pin"])
                        # Build description with all identifiers
                        if alt_name:
                            desc = f"{port_id} ({signal_str} - {alt_name}) [{group}]"
                        else:
                            desc = f"{port_id} ({signal_str}) [{group}]"
                        _add_option(tag, desc, signal_str, port_id)

                    # Include other *_pin fields (useful for "all known" discovery)
                    for k, v in port_info.items():
                        if k in {"pin", "signal_pin", "pins"}:
                            continue
                        if k.endswith("_pin") and isinstance(v, str) and v:
                            tag = f"{group}:{port_id}:{k}"
                            _add_option(tag, f"{port_id} {k} ({v}) [{group}]", v, port_id)
                else:
                    # Rare: port_info is a direct string pin
                    if isinstance(port_info, str) and port_info:
                        tag = f"{group}:{port_id}:raw"
                        _add_option(tag, f"{port_id} ({port_info}) [{group}]", port_info, port_id)

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

    def _looks_like_raw_pin(self, value: str) -> bool:
        """
        Best-effort heuristic to decide if a string is already a raw MCU pin (vs a port-id like 'FAN0').

        Keep this conservative: if we can't tell, we prefer resolving via board templates.
        """
        s = (value or "").strip()
        if not s:
            return False
        if ":" in s:
            # e.g. "toolboard:PA4" / "mcu:PA4" -> don't treat as a raw mainboard pin
            return False
        if re.match(r"^P[A-Z]\d+$", s):
            # e.g. PA1, PF13, PC0
            return True
        if re.match(r"^gpio\d+$", s, flags=re.IGNORECASE):
            # e.g. gpio26
            return True
        return False

    def _collect_mainboard_used_pins(self, *, exclude_pins: set[str] | None = None) -> dict[str, str]:
        """
        Collect a mapping of raw mainboard pins -> description for conflict detection.

        This intentionally focuses on pins the wizard assigns (steppers/fans/heaters/sensors), not a full parser.

        .. deprecated:: 2.1
            Use PinManager.load_used_from_state() and PinManager.get_all_used() instead.
            See scripts/wizard/pins.py for the new unified pin management approach.
        """
        exclude = set()
        for p in (exclude_pins or set()):
            if isinstance(p, str) and p.strip():
                exclude.add(p.strip())

        board_id = self.state.get("mcu.main.board_type", "")
        board_data = self._load_board_data(board_id, "boards")
        if not isinstance(board_data, dict) or not board_data:
            return {}

        used: dict[str, str] = {}

        def _add(pin: str, desc: str) -> None:
            pin = (pin or "").strip()
            if not pin or ":" in pin:
                return
            if pin in exclude:
                return
            used.setdefault(pin, desc)

        def _resolve_from_group(value: str, group: str) -> str:
            v = (value or "").strip()
            if not v:
                return ""
            group_data = board_data.get(group, {})
            if isinstance(group_data, dict) and v in group_data:
                info = group_data.get(v)
                if isinstance(info, dict):
                    pin = info.get("pin") or info.get("signal_pin")
                    if isinstance(pin, str) and pin:
                        return pin
                if isinstance(info, str) and info:
                    return info
            return v if self._looks_like_raw_pin(v) else ""

        def _add_motor_port(port_id: str, desc: str) -> None:
            port_id = (port_id or "").strip()
            if not port_id:
                return
            mp = board_data.get("motor_ports", {})
            info = mp.get(port_id) if isinstance(mp, dict) else None
            if not isinstance(info, dict):
                if self._looks_like_raw_pin(port_id):
                    _add(port_id, desc)
                return
            for k in ("step_pin", "dir_pin", "enable_pin", "uart_pin", "cs_pin", "diag_pin"):
                v = info.get(k)
                if isinstance(v, str) and v:
                    _add(v, f"{desc} ({k})")

        # Steppers / motors (mainboard motor ports)
        for stepper in ("stepper_x", "stepper_y", "stepper_z", "stepper_x1", "stepper_y1", "stepper_z1", "stepper_z2", "stepper_z3"):
            _add_motor_port(self.state.get(f"{stepper}.motor_port", ""), f"Stepper {stepper} motor")

        # Extruder motor (only if on mainboard)
        motor_location = self.state.get("extruder.location", "mainboard") or "mainboard"
        if motor_location == "mainboard":
            _add_motor_port(self.state.get("extruder.motor_port_mainboard", ""), "Extruder motor")

        # Endstops (mainboard)
        for stepper in ("stepper_x", "stepper_y", "stepper_z"):
            port = self.state.get(f"{stepper}.endstop_port", "")
            pin = _resolve_from_group(port, "endstop_ports") if port else ""
            if pin:
                _add(pin, f"{stepper} endstop")

        # Heaters (mainboard)
        extruder_heater = self.state.get("extruder.heater_port_mainboard", "")
        if extruder_heater:
            _add(_resolve_from_group(extruder_heater, "heater_ports"), "Extruder heater")
        bed_heater = self.state.get("heater_bed.heater_pin", "")
        if bed_heater:
            _add(_resolve_from_group(bed_heater, "heater_ports"), "Heated bed heater")

        # Thermistors (mainboard)
        extruder_sensor = self.state.get("extruder.sensor_port_mainboard", "")
        if extruder_sensor:
            _add(_resolve_from_group(extruder_sensor, "thermistor_ports"), "Extruder thermistor")
        bed_sensor = self.state.get("heater_bed.sensor_port", "")
        if bed_sensor:
            _add(_resolve_from_group(bed_sensor, "thermistor_ports"), "Bed thermistor")

        # Fans (mainboard)
        part_pin = self.state.get("fans.part_cooling.pin_mainboard", "")
        if part_pin:
            _add(_resolve_from_group(part_pin, "fan_ports"), "Part cooling fan")
        hotend_pin = self.state.get("fans.hotend.pin_mainboard", "")
        if hotend_pin:
            _add(_resolve_from_group(hotend_pin, "fan_ports"), "Hotend fan")
        controller_pin = self.state.get("fans.controller.pin", "")
        if controller_pin:
            _add(_resolve_from_group(controller_pin, "fan_ports"), "Controller fan")

        additional_fans = self.state.get("fans.additional_fans", [])
        if isinstance(additional_fans, list):
            for idx, fan in enumerate(additional_fans, start=1):
                if not isinstance(fan, dict):
                    continue
                loc = (fan.get("location") or "mainboard").strip()
                if loc != "mainboard":
                    continue
                pin = (fan.get("pin") or "").strip()
                if pin:
                    _add(_resolve_from_group(pin, "fan_ports"), f"Additional fan #{idx}")
                pins = fan.get("pins")
                if isinstance(pins, list):
                    for p in pins:
                        if isinstance(p, str) and p.strip():
                            _add(_resolve_from_group(p, "fan_ports"), f"Additional fan #{idx} (multi_pin)")

        # Raw pins already (only if they look like raw mainboard pins)
        probe_sensor_pin = self.state.get("probe.sensor_pin", "")
        if isinstance(probe_sensor_pin, str) and self._looks_like_raw_pin(probe_sensor_pin):
            _add(probe_sensor_pin, "Probe sensor_pin")

        temp_sensors = self.state.get("temperature_sensors.additional", [])
        if isinstance(temp_sensors, list):
            for s in temp_sensors:
                if not isinstance(s, dict):
                    continue
                pin = s.get("sensor_pin")
                name = (s.get("name") or "additional").strip()
                if isinstance(pin, str) and self._looks_like_raw_pin(pin):
                    _add(pin, f"Temp sensor ({name})")

        filament_sensors = self.state.get("filament_sensors", [])
        if isinstance(filament_sensors, list):
            for s in filament_sensors:
                if not isinstance(s, dict):
                    continue
                pin = s.get("pin")
                name = (s.get("name") or "filament").strip()
                if isinstance(pin, str) and self._looks_like_raw_pin(pin):
                    _add(pin, f"Filament sensor ({name})")

        leds = self.state.get("leds", [])
        if isinstance(leds, list):
            for s in leds:
                if not isinstance(s, dict):
                    continue
                pin = s.get("pin")
                name = (s.get("name") or "led").strip()
                if isinstance(pin, str) and self._looks_like_raw_pin(pin):
                    _add(pin, f"LED ({name})")

        return used

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

    def _endstop_config_to_flags(self, endstop_config: str | None) -> tuple[bool, bool]:
        """Convert legacy endstop_config string -> (pullup, invert).

        Legacy values:
        - nc_gnd: pullup True, invert False   (^pin)
        - no_gnd: pullup True, invert True    (^!pin)
        - nc_vcc: pullup False, invert True   (!pin)
        - no_vcc: pullup False, invert False  (pin)
        """
        cfg = (endstop_config or "nc_gnd").strip().lower()
        mapping: dict[str, tuple[bool, bool]] = {
            "nc_gnd": (True, False),
            "no_gnd": (True, True),
            "nc_vcc": (False, True),
            "no_vcc": (False, False),
        }
        return mapping.get(cfg, (True, False))

    def _prompt_endstop_wiring(self, *, axis_upper: str, state_key: str) -> tuple[bool, bool] | None:
        """Prompt for endstop wiring using two toggles (pullup + invert)."""
        # New state (preferred)
        if self.state.get(f"{state_key}.endstop_pullup") is not None or self.state.get(f"{state_key}.endstop_invert") is not None:
            current_pullup = bool(self.state.get(f"{state_key}.endstop_pullup", True))
            current_invert = bool(self.state.get(f"{state_key}.endstop_invert", False))
        else:
            # Back-compat: derive from legacy endstop_config if present
            current_cfg = self.state.get(f"{state_key}.endstop_config", "nc_gnd")
            current_pullup, current_invert = self._endstop_config_to_flags(current_cfg)

        pullup = self.ui.yesno(
            f"Enable pullup resistor for {axis_upper} endstop?\n\n"
            "Recommended for typical mechanical endstops.\n"
            "(This controls the '^' pin modifier)",
            title=f"Stepper {axis_upper} - Endstop Wiring",
            default_no=not current_pullup,
        )
        # Always allow cancel
        if pullup is None:
            return None

        invert = self.ui.yesno(
            f"Invert {axis_upper} endstop signal?\n\n"
            "Enable this if your endstop reads TRIGGERED when not pressed.\n"
            "(This controls the '!' pin modifier)",
            title=f"Stepper {axis_upper} - Endstop Wiring",
            default_no=not current_invert,
        )
        if invert is None:
            return None

        return (pullup, invert)

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
                    ("C", "Clear Settings        (Reset all wizard settings)"),
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
            elif choice == "C":
                self._clear_settings()

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

    def _clear_settings(self) -> None:
        """Clear all wizard settings and reset to defaults."""
        if not self.ui.yesno(
            "Clear all wizard settings?\n\n"
            "This will reset all your configuration choices.\n"
            "You will need to reconfigure everything.\n\n"
            "This action cannot be undone!",
            title="Clear Settings",
            default_no=True,
            height=14,
            width=70,
        ):
            return

        # Clear the state
        self.state.clear()
        self.state.save()

        self.ui.msgbox(
            "All settings have been cleared!\n\n"
            "You can now start fresh configuration.",
            title="Settings Cleared",
            height=10,
            width=60,
        )

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
                "Klipper Setup\n\n"
                "Manage Klipper ecosystem components and related tools.\n"
                "Warning: install/remove actions may require sudo and can modify system services.",
                [
                    ("1.1", "Manage Klipper Components  (KIAUH-style install/update/remove)"),
                    ("1.2", "CAN Interface Setup       (can0 / can-utils / systemd)"),
                    ("1.3", "Katapult / Flashing       (DFU + CAN firmware flash)"),
                    ("1.4", "Update Manager Fix        (Git fetch workaround)"),
                    ("B", "Back to Main Menu"),
                ],
                title="1. Klipper Setup",
            )

            if choice is None or choice == "B":
                break
            elif choice == "1.1":
                self._manage_klipper_components()
            elif choice == "1.2":
                self._can_interface_setup()
            elif choice == "1.3":
                self._katapult_setup()
            elif choice == "1.4":
                self._update_manager_git_fetch_workaround()

    def _update_manager_git_fetch_workaround(self) -> None:
        """
        Help users when Moonraker Update Manager / git fetch hangs on GitHub.

        Root cause varies by network stack (IPv6, HTTP/2 quirks, DNS, etc.). A pragmatic,
        low-impact mitigation is forcing HTTP/1.1 for this repo:
          git config http.version HTTP/1.1

        We store this config LOCALLY in the repo so it doesn't affect other git repos.
        """
        import subprocess

        repo = REPO_ROOT

        def get_http_version() -> str:
            try:
                r = subprocess.run(
                    ["git", "config", "--get", "http.version"],
                    cwd=str(repo),
                    capture_output=True,
                    text=True,
                )
                val = (r.stdout or "").strip()
                return val or "(default)"
            except Exception:
                return "(unknown)"

        def test_fetch() -> tuple[bool, str]:
            try:
                env = os.environ.copy()
                env["GIT_TERMINAL_PROMPT"] = "0"
                r = subprocess.run(
                    ["git", "fetch", "origin", "--prune", "--tags", "--force"],
                    cwd=str(repo),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                ok = (r.returncode == 0)
                # Keep output short for whiptail
                out = (r.stderr or r.stdout or "").strip()
                if len(out) > 1200:
                    out = out[:1200] + "\n...(truncated)..."
                return ok, out
            except subprocess.TimeoutExpired:
                return False, "Timed out after 60s (fetch likely hanging)."
            except Exception as e:
                return False, f"{type(e).__name__}: {e}"

        while True:
            current = get_http_version()
            choice = self.ui.menu(
                "Moonraker Update Manager / Git Fetch Workaround\n\n"
                "If Update Manager refreshes forever or never shows updates, the underlying\n"
                "'git fetch' may be hanging.\n\n"
                f"Current repo setting: http.version = {current}\n\n"
                "Actions (repo-local):",
                [
                    ("enable", "Enable workaround (set http.version=HTTP/1.1)"),
                    ("disable", "Disable workaround (unset http.version)"),
                    ("test", "Test git fetch (60s timeout)"),
                    ("B", "Back"),
                ],
                title="Update Manager Fix",
                height=18,
                width=90,
                menu_height=10,
            )
            if choice is None or choice == "B":
                return

            if choice == "enable":
                try:
                    subprocess.run(
                        ["git", "config", "http.version", "HTTP/1.1"],
                        cwd=str(repo),
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    self._log_wizard("update_manager_fix set http.version=HTTP/1.1")
                    self.ui.msgbox(
                        "Enabled: git config http.version HTTP/1.1\n\n"
                        "Now try Update Manager → Refresh/Update again.",
                        title="Saved",
                    )
                except Exception as e:
                    self.ui.msgbox(f"Failed to set git config:\n{type(e).__name__}: {e}", title="Error")
                continue

            if choice == "disable":
                try:
                    # Unset only for this repo; ignore if already missing.
                    subprocess.run(
                        ["git", "config", "--unset", "http.version"],
                        cwd=str(repo),
                        capture_output=True,
                        text=True,
                    )
                    self._log_wizard("update_manager_fix unset http.version")
                    self.ui.msgbox(
                        "Disabled: git config --unset http.version\n\n"
                        "Repo is back to git defaults.",
                        title="Saved",
                    )
                except Exception as e:
                    self.ui.msgbox(f"Failed to unset git config:\n{type(e).__name__}: {e}", title="Error")
                continue

            if choice == "test":
                ok, out = test_fetch()
                if ok:
                    self.ui.msgbox("git fetch: OK\n\n" + (out or "(no output)"), title="Fetch Test")
                else:
                    self.ui.msgbox("git fetch: FAILED / HUNG\n\n" + out, title="Fetch Test")

    def _get_component_status(self, component: str) -> dict:
        """Get installation status for a Klipper ecosystem component.

        Returns dict with: installed, version, service_running, service_enabled, has_service, path
        """
        import subprocess

        status = {
            "installed": False,
            "version": None,
            "has_service": False,  # True if component has a systemd service
            "service_running": False,
            "service_enabled": False,
            "path": None,
        }

        # Component paths and service names
        component_info = {
            "klipper": {"path": Path.home() / "klipper", "service": "klipper"},
            "moonraker": {"path": Path.home() / "moonraker", "service": "moonraker"},
            "mainsail": {"path": Path.home() / "mainsail", "service": None},  # nginx-served
            "fluidd": {"path": Path.home() / "fluidd", "service": None},  # nginx-served
            "crowsnest": {"path": Path.home() / "crowsnest", "service": "crowsnest"},
            "sonar": {"path": Path.home() / "sonar", "service": "sonar"},
            "timelapse": {"path": Path.home() / "moonraker-timelapse", "service": None},  # moonraker plugin
            "klipperscreen": {"path": Path.home() / "KlipperScreen", "service": "KlipperScreen"},
        }

        info = component_info.get(component.lower())
        if not info:
            return status

        path = info["path"]
        service = info["service"]
        status["has_service"] = (service is not None)

        # Check if installed (directory exists)
        if path.exists():
            status["installed"] = True
            status["path"] = str(path)

            # Try to get version from git
            try:
                r = subprocess.run(
                    ["git", "describe", "--tags", "--always"],
                    cwd=str(path),
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if r.returncode == 0:
                    status["version"] = r.stdout.strip()
            except Exception:
                pass

        # Check service status
        if service:
            try:
                r = subprocess.run(
                    ["systemctl", "is-active", service],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                status["service_running"] = (r.stdout.strip() == "active")
            except Exception:
                pass

            try:
                r = subprocess.run(
                    ["systemctl", "is-enabled", service],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                status["service_enabled"] = (r.stdout.strip() == "enabled")
            except Exception:
                pass

        return status

    def _format_component_status(self, component: str, status: dict) -> str:
        """Format component status for menu display."""
        if not status["installed"]:
            return f"{component:<14} [ Not installed ]"

        parts = ["✓"]
        if status["version"]:
            parts.append(status["version"][:20])

        # Only show service status for components that have a systemd service
        if status.get("has_service"):
            if status["service_running"]:
                parts.append("running")
            elif status["service_enabled"]:
                parts.append("stopped")
            else:
                parts.append("disabled")

        return f"{component:<14} [ {' | '.join(parts)} ]"

    def _manage_klipper_components(self) -> None:
        """
        KIAUH-style component manager.

        Shows installation status for each component, then allows
        Install/Update/Remove/Reinstall actions.
        """
        repo_root = REPO_ROOT
        tool = repo_root / "scripts" / "tools" / "klipper_component_manager.sh"
        if not tool.exists():
            self.ui.msgbox(f"Missing tool: {tool}", title="Error")
            return

        # Component definitions
        components = [
            ("klipper", "Klipper"),
            ("moonraker", "Moonraker"),
            ("mainsail", "Mainsail"),
            ("fluidd", "Fluidd"),
            ("crowsnest", "Crowsnest"),
            ("sonar", "Sonar"),
            ("timelapse", "Timelapse"),
            ("klipperscreen", "KlipperScreen"),
        ]

        while True:
            # Build menu with current status
            menu_items = []
            for comp_id, comp_name in components:
                status = self._get_component_status(comp_id)
                label = self._format_component_status(comp_name, status)
                menu_items.append((comp_id, label))

            menu_items.append(("update-all", "─────────────────────────────────"))
            menu_items.append(("update-all", "Update ALL installed components"))
            menu_items.append(("B", "Back"))

            choice = self.ui.menu(
                "Manage Klipper Components\n\n"
                "Select a component to Install/Update/Remove/Reinstall.\n"
                "Your ~/printer_data/config is preserved by remove routines.",
                menu_items,
                title="Klipper Components",
                height=26,
                width=100,
                menu_height=14,
            )

            if choice is None or choice == "B":
                return

            if choice == "update-all":
                if self.ui.yesno(
                    "Update ALL installed components?\n\n"
                    "This uses KIAUH-style routines and may restart services.\n"
                    "You may be prompted for sudo.",
                    title="Confirm Update All",
                    default_no=True,
                ):
                    self._run_tty_command(["bash", str(tool), "update-all"])
                continue

            # Selected a specific component - show actions
            comp_name = dict(components).get(choice, choice)
            status = self._get_component_status(choice)

            # Build action menu based on current status
            if choice == "klipperscreen":
                # KlipperScreen has its own manager with config options
                self._klipperscreen_setup()
                continue

            action_items = []
            if status["installed"]:
                action_items.append(("update", "Update"))
                action_items.append(("remove", "Remove (FULL uninstall)"))
                action_items.append(("reinstall", "Reinstall (remove + install)"))
            else:
                action_items.append(("install", "Install"))
            action_items.append(("B", "Back"))

            status_text = "INSTALLED" if status["installed"] else "NOT INSTALLED"
            version_text = f"Version: {status['version']}" if status["version"] else ""
            service_text = ""
            if status.get("has_service"):
                if status["service_running"]:
                    service_text = "Service: running"
                elif status["service_enabled"]:
                    service_text = "Service: enabled but stopped"
                else:
                    service_text = "Service: disabled"

            action = self.ui.menu(
                f"{comp_name}\n\n"
                f"Status: {status_text}\n"
                f"{version_text}\n"
                f"{service_text}\n\n"
                "Select action:",
                action_items,
                title=f"{comp_name} Actions",
                height=20,
                width=80,
                menu_height=6,
            )

            if action is None or action == "B":
                continue

            # Safety confirmation for destructive actions
            if action in ("remove", "reinstall"):
                if not self.ui.yesno(
                    f"WARNING: This will FULLY uninstall {comp_name}.\n\n"
                    "It will stop/disable services and delete the component directory.\n"
                    "Your ~/printer_data/config is preserved, but this can still break\n"
                    "a working setup.\n\n"
                    "Proceed?",
                    title="Danger Zone",
                    default_no=True,
                    height=16,
                    width=80,
                ):
                    continue

            self._run_tty_command(["bash", str(tool), action, choice])

    def _can_interface_setup(self) -> None:
        """
        Minimal CAN interface setup:
        - install can-utils
        - bring up can0 (or chosen iface) at a given bitrate
        - optional persistent systemd oneshot service
        """
        repo_root = REPO_ROOT
        tool = repo_root / "scripts" / "tools" / "setup_can_interface.sh"
        if not tool.exists():
            self.ui.msgbox(f"Missing tool: {tool}", title="Error")
            return

        self.ui.msgbox(
            "CAN Setup\n\n"
            "This helper configures an existing SocketCAN interface (e.g. can0).\n"
            "It can install can-utils and optionally create a systemd service to bring the interface\n"
            "up on boot.\n\n"
            "It does NOT enable your CAN hardware/driver (e.g. mcp2515 overlays, slcan).\n"
            "If can0 doesn't exist yet, fix hardware/driver first, then rerun this.",
            title="CAN Setup",
            height=18,
            width=90,
        )

        iface = self.ui.inputbox("CAN interface name:", default="can0", title="CAN Setup")
        if iface is None or iface.strip() == "":
            return

        bitrate = self.ui.inputbox(
            "CAN bitrate (e.g. 1000000):",
            default="1000000",
            title="CAN Setup",
        )
        if bitrate is None or bitrate.strip() == "":
            return

        # CAN requires the interface to be up reliably on boot; make persistence non-optional.
        self.ui.msgbox(
            "CAN interface will be made persistent on boot.\n\n"
            "This will create/enable a systemd service: can-<iface>.service",
            title="CAN Setup",
            height=12,
            width=80,
        )

        install_pkgs = self.ui.yesno(
            "Install can-utils?\n\n"
            "(Recommended; provides candump/cansend and other tools.)",
            title="CAN Setup",
            default_no=False,
        )

        args = [
            "bash",
            str(tool),
            "--iface",
            iface.strip(),
            "--bitrate",
            bitrate.strip(),
            "--persist",
            "yes",
            "--install-pkgs",
            "yes" if install_pkgs else "no",
        ]

        self._run_tty_command(args)

    def _katapult_setup(self) -> None:
        """Guided Katapult/firmware flashing helper (DFU + CAN)."""
        tool = REPO_ROOT / "scripts" / "tools" / "katapult_setup.sh"
        if not tool.exists():
            self.ui.msgbox(f"Missing tool: {tool}", title="Error")
            return

        self.ui.msgbox(
            "Katapult / Flashing (Guided)\n\n"
            "This helper can:\n"
            "- Assist flashing Katapult via USB DFU (dangerous)\n"
            "- Flash Klipper firmware over CAN using Klipper's flash_can.py\n\n"
            "WARNING:\n"
            "Firmware flashing can brick boards if you select the wrong device or parameters.\n"
            "Proceed carefully and read prompts.",
            title="Katapult / Flashing",
            height=18,
            width=90,
        )

        self._run_tty_command(["bash", str(tool)])

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
            elif choice == "2.1.4":
                self._additional_mcus_setup()
            else:
                self.ui.msgbox("Coming soon!", title=choice)

    def _additional_mcus_setup(self) -> None:
        """Configure additional MCUs (MMU/filament changers, buffers, expansion boards)."""
        mmu_types_tpl = self._load_mmu_template("mmu-types.json") or {}
        mmu_types = mmu_types_tpl.get("types", {}) if isinstance(mmu_types_tpl.get("types", {}), dict) else {}
        software_defs = mmu_types_tpl.get("software", {}) if isinstance(mmu_types_tpl.get("software", {}), dict) else {}

        boards_tpl = self._load_mmu_template("mmu-boards.json") or {}
        boards = boards_tpl.get("boards", {}) if isinstance(boards_tpl.get("boards", {}), dict) else {}

        buffers_tpl = self._load_mmu_template("buffers.json") or {}
        buffers = buffers_tpl.get("buffers", {}) if isinstance(buffers_tpl.get("buffers", {}), dict) else {}

        def _get_entries() -> list:
            entries = self.state.get("mcu.additional", [])
            if not isinstance(entries, list):
                return []
            return [e for e in entries if isinstance(e, dict)]

        def _save_entries(entries: list) -> None:
            self.state.set("mcu.additional", entries)
            self.state.save()

        def _entry_label(entry: dict) -> str:
            etype = entry.get("type", "unknown")
            hw = entry.get("hardware", "")
            board = entry.get("board", "")
            conn = entry.get("connection", "")
            sw = entry.get("software", "")
            parts = []
            if etype:
                parts.append(str(etype))
            if hw:
                parts.append(str(hw))
            if board:
                parts.append(str(board))
            if conn:
                parts.append(str(conn))
            if sw:
                parts.append(str(sw))
            return " / ".join(parts) if parts else "Unknown entry"

        def _select_software(allowed: list) -> str | None:
            allowed = [a for a in allowed if a in ("happy_hare", "afc")]
            if not allowed:
                return None
            if len(allowed) == 1:
                return allowed[0]
            # Use template names when available
            options = []
            for key in allowed:
                name = key
                if isinstance(software_defs.get(key), dict):
                    name = software_defs[key].get("name", key)
                options.append((key, name))
            chosen = self.ui.radiolist(
                "Select the software ecosystem to install/use:",
                [(k, v, i == 0) for i, (k, v) in enumerate(options)],
                title="Software",
            )
            return chosen

        def _select_board() -> str | None:
            if not boards:
                self.ui.msgbox(
                    "No MMU board definitions found.\n\n"
                    "Expected: templates/mmu/mmu-boards.json",
                    title="Error",
                )
                return None

            items = []
            for board_id, b in boards.items():
                if not isinstance(b, dict):
                    continue
                items.append((board_id, b.get("name", board_id)))
            items.sort(key=lambda x: x[1].lower())
            items.append(("other_unknown", "Other / Unknown"))

            choice = self.ui.menu(
                "Select controller board:",
                items,
                title="MMU Controller Board",
                height=20,
                width=100,
                menu_height=12,
            )
            return choice if choice and choice != "B" else None

        def _select_connection(default_conn: str | None = None) -> tuple[str | None, dict]:
            default_conn = default_conn if default_conn in ("usb", "can") else "usb"
            conn = self.ui.radiolist(
                "How is this additional MCU connected?",
                [
                    ("usb", "USB serial", default_conn == "usb"),
                    ("can", "CAN bus", default_conn == "can"),
                ],
                title="Connection Type",
            )
            if not conn:
                return None, {}

            data: dict = {"connection": conn}
            if conn == "usb":
                serial = self.ui.inputbox(
                    "Enter the MCU serial path (usually /dev/serial/by-id/...):",
                    title="USB Serial",
                    default="/dev/serial/by-id/usb-Klipper_",
                    width=100,
                )
                if not serial:
                    return None, {}
                data["serial"] = serial
            else:
                uuid = self.ui.inputbox(
                    "Enter the CAN UUID (from `ls /dev/serial/by-id` or `ip -details link show can0` tooling):",
                    title="CAN UUID",
                    default="",
                    width=100,
                )
                if not uuid:
                    return None, {}
                data["can_uuid"] = uuid

            return conn, data

        while True:
            entries = _get_entries()
            status = f"{len(entries)} configured" if entries else "none configured"

            choice = self.ui.menu(
                "Additional MCUs\n\n"
                f"Current: {status}\n\n"
                "Use this section for add-on controller MCUs and related systems like:\n"
                "- MMU/filament changers (ERCF, Tradrack, BoxTurtle, ...)\n"
                "- Smart buffers (LLL Plus) and feedback systems\n\n"
                "Note: Firmware flashing/pin mapping is still hardware-specific; this wizard focuses on recording\n"
                "the topology and offering software installers.\n",
                [
                    ("ADD_MMU", "Add MMU / Filament Changer"),
                    ("ADD_BUF", "Add Filament Buffer"),
                    ("VIEW", "View configured entries"),
                    ("REMOVE", "Remove an entry"),
                    ("B", "Back"),
                ],
                title="2.1.4 Additional MCUs",
                height=24,
                width=120,
                menu_height=10,
            )

            if choice is None or choice == "B":
                return

            if choice == "VIEW":
                if not entries:
                    self.ui.msgbox("No additional MCUs configured yet.", title="Additional MCUs")
                    continue
                lines = ["Configured entries:\n"]
                for i, e in enumerate(entries, start=1):
                    lines.append(f"{i}. {_entry_label(e)}")
                self.ui.msgbox("\n".join(lines), title="Additional MCUs", height=20, width=110)
                continue

            if choice == "REMOVE":
                if not entries:
                    self.ui.msgbox("No entries to remove.", title="Remove")
                    continue
                items = [(str(i), _entry_label(e)) for i, e in enumerate(entries)]
                pick = self.ui.menu(
                    "Select entry to remove:",
                    items + [("B", "Back")],
                    title="Remove Entry",
                    height=20,
                    width=120,
                    menu_height=12,
                )
                if pick is None or pick == "B":
                    continue
                try:
                    idx = int(pick)
                except ValueError:
                    continue
                if idx < 0 or idx >= len(entries):
                    continue
                if not self.ui.yesno(f"Remove:\n\n{_entry_label(entries[idx])}\n\nAre you sure?", title="Confirm Remove"):
                    continue
                entries.pop(idx)
                _save_entries(entries)
                self.ui.msgbox("Entry removed.", title="Removed")
                continue

            if choice == "ADD_MMU":
                if not mmu_types:
                    self.ui.msgbox(
                        "No MMU type definitions found.\n\n"
                        "Expected: templates/mmu/mmu-types.json",
                        title="Error",
                    )
                    continue

                type_items = []
                for mmu_id, info in mmu_types.items():
                    if not isinstance(info, dict):
                        continue
                    type_items.append((mmu_id, info.get("name", mmu_id)))
                type_items.sort(key=lambda x: x[1].lower())
                mmu_choice = self.ui.menu(
                    "Select your MMU/filament changer type:",
                    type_items + [("B", "Back")],
                    title="MMU Type",
                    height=22,
                    width=120,
                    menu_height=14,
                )
                if mmu_choice is None or mmu_choice == "B":
                    continue

                mmu_info = mmu_types.get(mmu_choice, {}) if isinstance(mmu_types.get(mmu_choice), dict) else {}
                versions = mmu_info.get("versions", [])
                version = None
                if isinstance(versions, list) and versions:
                    if len(versions) == 1:
                        version = versions[0]
                    else:
                        version = self.ui.radiolist(
                            "Select hardware version:",
                            [(v, v, i == 0) for i, v in enumerate(versions)],
                            title="MMU Version",
                        )
                        if version is None:
                            continue

                gates = self.ui.inputbox(
                    "How many gates/lanes does your MMU have?",
                    title="Gate Count",
                    default=str(
                        (mmu_info.get("typical_num_gates") or [4])[0]
                        if isinstance(mmu_info.get("typical_num_gates"), list)
                        else 4
                    ),
                )
                if gates is None:
                    continue
                try:
                    num_gates = int(str(gates).strip())
                except ValueError:
                    self.ui.msgbox("Gate count must be a number.", title="Error")
                    continue
                if num_gates < 1:
                    self.ui.msgbox("Gate count must be >= 1.", title="Error")
                    continue

                board_id = _select_board()
                if board_id is None:
                    continue
                board_info = boards.get(board_id, {}) if isinstance(boards.get(board_id), dict) else {}
                default_conn = board_info.get("connection") if isinstance(board_info.get("connection"), str) else "usb"
                conn, conn_data = _select_connection(default_conn=default_conn)
                if conn is None:
                    continue

                allowed_sw = mmu_info.get("recommended_software", ["happy_hare", "afc"])
                if not isinstance(allowed_sw, list):
                    allowed_sw = ["happy_hare", "afc"]
                sw = _select_software(allowed_sw)
                if sw is None:
                    self.ui.msgbox("No software option available for this MMU type.", title="Error")
                    continue

                entry = {
                    "type": "mmu",
                    "hardware": mmu_choice,
                    "version": version,
                    "num_gates": num_gates,
                    "board": board_id,
                    "software": sw,
                    **conn_data,
                }
                entries.append(entry)
                _save_entries(entries)

                install_now = self.ui.yesno(
                    "Saved configuration.\n\n"
                    "Do you want to run the software installer now?\n\n"
                    "This will open an interactive terminal step.",
                    title="Install Software Now?",
                    default_no=True,
                )
                if install_now:
                    if sw == "happy_hare":
                        if hasattr(self, "_install_happy_hare"):
                            self._install_happy_hare()
                        else:
                            self.ui.msgbox("Happy Hare installer not implemented yet.", title="Not Implemented")
                    else:
                        if hasattr(self, "_install_afc"):
                            self._install_afc()
                        else:
                            self.ui.msgbox("AFC installer not implemented yet.", title="Not Implemented")

                continue

            if choice == "ADD_BUF":
                if not buffers:
                    self.ui.msgbox(
                        "No buffer definitions found.\n\n"
                        "Expected: templates/mmu/buffers.json",
                        title="Error",
                    )
                    continue

                buf_items = []
                for buf_id, info in buffers.items():
                    if not isinstance(info, dict):
                        continue
                    buf_items.append((buf_id, info.get("name", buf_id)))
                buf_items.sort(key=lambda x: x[1].lower())
                buf_choice = self.ui.menu(
                    "Select buffer type:",
                    buf_items + [("B", "Back")],
                    title="Filament Buffer",
                    height=22,
                    width=120,
                    menu_height=14,
                )
                if buf_choice is None or buf_choice == "B":
                    continue

                buf_info = buffers.get(buf_choice, {}) if isinstance(buffers.get(buf_choice), dict) else {}
                requires_mcu = bool(buf_info.get("requires_additional_mcu", False))

                entry: dict = {"type": "buffer", "hardware": buf_choice}

                if requires_mcu:
                    board_id = _select_board()
                    if board_id is None:
                        continue
                    board_info = boards.get(board_id, {}) if isinstance(boards.get(board_id), dict) else {}
                    default_conn = board_info.get("connection") if isinstance(board_info.get("connection"), str) else "usb"
                    conn, conn_data = _select_connection(default_conn=default_conn)
                    if conn is None:
                        continue
                    entry.update({"board": board_id, **conn_data})

                # Optional: record a signal pin for smart buffers (runout/break)
                wants_signal = self.ui.yesno(
                    "Does this buffer provide a runout/break detection signal you want to wire into Klipper?",
                    title="Buffer Signal",
                    default_no=True,
                )
                if wants_signal:
                    pin = self.ui.inputbox(
                        "Enter the MCU pin for the buffer signal (optional):",
                        title="Signal Pin",
                        default="",
                        width=80,
                    )
                    if pin:
                        entry["signal_pin"] = pin

                entries.append(entry)
                _save_entries(entries)
                self.ui.msgbox("Buffer saved.", title="Saved")
                continue

    def _install_happy_hare(self) -> None:
        """Install Happy Hare MMU stack (interactive installer)."""
        from pathlib import Path

        repo = "https://github.com/moggieuk/Happy-Hare.git"
        target_dir = Path.home() / "Happy-Hare"
        installer = target_dir / "install.sh"

        if not self.ui.yesno(
            "Install/Update Happy Hare?\n\n"
            "This will:\n"
            "- Clone (or update) Happy-Hare in your home directory\n"
            "- Run the interactive installer (it will ask you questions)\n\n"
            "You may be prompted for your sudo password.\n\n"
            "Continue?",
            title="Happy Hare",
            default_no=False,
        ):
            return

        print("\n" + "=" * 60)
        print("Happy Hare (MMU) installer")
        print("=" * 60 + "\n")

        # Clone or update repo
        if target_dir.exists():
            print(f"Updating {target_dir} ...\n")
            self._run_tty_command(["bash", "-lc", f"cd {target_dir} && git pull"])
        else:
            print(f"Cloning {repo} -> {target_dir} ...\n")
            rc = self._run_tty_command(["bash", "-lc", f"cd ~ && git clone {repo} {target_dir}"])
            if rc != 0:
                self.ui.msgbox(
                    "Failed to clone Happy-Hare repository.\n\n"
                    "Check the terminal output for details.",
                    title="Happy Hare",
                )
                return

        if not installer.exists():
            self.ui.msgbox(
                f"Happy Hare installer not found at:\n{installer}\n\n"
                "Clone/update may have failed.",
                title="Happy Hare",
            )
            return

        print("\n" + "=" * 60)
        print("Running Happy Hare interactive installer (./install.sh -i)...")
        print("=" * 60 + "\n")
        rc = self._run_tty_command(["bash", "-lc", f"cd {target_dir} && chmod +x ./install.sh && ./install.sh -i"])

        if rc == 0:
            self.ui.msgbox(
                "Happy Hare installer finished.\n\n"
                "Next steps are typically:\n"
                "- Validate the generated mmu config files\n"
                "- Finish pin mapping/tuning per your hardware\n"
                "- Restart Klipper/Moonraker if needed",
                title="Happy Hare",
                height=16,
                width=90,
            )
        else:
            self.ui.msgbox(
                f"Happy Hare installer exited with code {rc}.\n\n"
                "Check the terminal output above for the error details.",
                title="Happy Hare",
            )

    def _install_afc(self) -> None:
        """Install AFC-Klipper-Add-On stack (interactive installer)."""
        from pathlib import Path

        repo = "https://github.com/ArmoredTurtle/AFC-Klipper-Add-On.git"
        target_dir = Path.home() / "AFC-Klipper-Add-On"
        installer = target_dir / "install-afc.sh"

        if not self.ui.yesno(
            "Install/Update AFC-Klipper-Add-On?\n\n"
            "This will:\n"
            "- Clone (or update) AFC-Klipper-Add-On in your home directory\n"
            "- (Optionally) install dependencies: jq + crudini\n"
            "- Run the installer script\n\n"
            "You may be prompted for your sudo password.\n\n"
            "Continue?",
            title="AFC",
            default_no=False,
        ):
            return

        print("\n" + "=" * 60)
        print("AFC-Klipper-Add-On installer")
        print("=" * 60 + "\n")

        # Clone or update repo
        if target_dir.exists():
            print(f"Updating {target_dir} ...\n")
            self._run_tty_command(["bash", "-lc", f"cd {target_dir} && git pull"])
        else:
            print(f"Cloning {repo} -> {target_dir} ...\n")
            rc = self._run_tty_command(["bash", "-lc", f"cd ~ && git clone {repo} {target_dir}"])
            if rc != 0:
                self.ui.msgbox(
                    "Failed to clone AFC-Klipper-Add-On repository.\n\n"
                    "Check the terminal output for details.",
                    title="AFC",
                )
                return

        if not installer.exists():
            self.ui.msgbox(
                f"AFC installer not found at:\n{installer}\n\n"
                "Clone/update may have failed.",
                title="AFC",
            )
            return

        install_deps = self.ui.yesno(
            "Install/update dependencies first?\n\n"
            "AFC recommends: jq and crudini\n\n"
            "Install via apt-get now?",
            title="AFC Dependencies",
            default_no=False,
        )
        if install_deps:
            print("\n" + "=" * 60)
            print("Installing dependencies: jq crudini")
            print("=" * 60 + "\n")
            self._run_tty_command(["bash", "-lc", "sudo apt-get update && sudo apt-get install -y jq crudini"])

        print("\n" + "=" * 60)
        print("Running AFC installer (./install-afc.sh)...")
        print("=" * 60 + "\n")
        rc = self._run_tty_command(["bash", "-lc", f"cd {target_dir} && chmod +x ./install-afc.sh && ./install-afc.sh"])

        if rc == 0:
            self.ui.msgbox(
                "AFC installer finished.\n\n"
                "If it asked you to add includes to printer.cfg, do that next and restart Klipper.",
                title="AFC",
                height=14,
                width=90,
            )
        else:
            self.ui.msgbox(
                f"AFC installer exited with code {rc}.\n\n"
                "Check the terminal output above for the error details.",
                title="AFC",
            )

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

        # Motor port selection using PinManager (filters used ports)
        pin_manager = self._get_pin_manager()
        current_port = self.state.get(f"{state_key}.motor_port", "")
        # Mark current port as available for reselection
        if current_port:
            pin_manager.mark_unused("mainboard", current_port)

        motor_port = pin_manager.select_motor_port(
            location="mainboard",
            purpose=f"{axis_upper} Axis",
            current_port=current_port or default_port,
            title=f"Stepper {axis_upper} - Motor Port"
        )
        if motor_port is None:
            return

        # Persist early so later cancels don't wipe already-selected values.
        self.state.set(f"{state_key}.motor_port", motor_port)
        self.state.save()

        # Direction pin inversion (always ask - this differs per motor)
        current_inverted = self.state.get(f"{state_key}.dir_pin_inverted", False)
        dir_inverted = self.ui.yesno(
            f"Invert direction pin for {axis_upper}?\n\n"
            "(If motor moves wrong direction, change this)",
            title=f"Stepper {axis_upper} - Direction",
            default_no=not current_inverted
        )

        # Persist early so later cancels don't wipe already-selected values.
        self.state.set(f"{state_key}.dir_pin_inverted", dir_inverted)
        self.state.save()

        # If inheriting, copy settings and only ask for axis-specific things
        if use_inherited:
            self._copy_stepper_settings(inherit_from, axis)
            # Persist copied settings immediately so cancelling later prompts doesn't lose them.
            self.state.save()

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
                # Persist immediately so cancelling later doesn't lose it.
                self.state.set(f"{state_key}.endstop_type", endstop_type)
                self.state.save()

                # Physical endstop port and config
                endstop_port = None
                if endstop_type == "physical":
                    # Allow selecting endstop on mainboard vs toolboard when a toolboard exists.
                    has_toolboard = bool(self.state.get("mcu.toolboard.connection_type"))
                    current_endstop_src = self.state.get(f"{state_key}.endstop_source", "")
                    if not current_endstop_src:
                        # Infer from existing stored ports so the UI reflects prior choices.
                        if self.state.get(f"{state_key}.endstop_port_toolboard"):
                            current_endstop_src = "toolboard"
                        elif self.state.get(f"{state_key}.endstop_port"):
                            current_endstop_src = "mainboard"
                        else:
                            current_endstop_src = "mainboard"

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

                    # Persist location immediately so it doesn't get lost on later cancels.
                    self.state.set(f"{state_key}.endstop_source", endstop_source)
                    self.state.save()

                    board_type = "toolboards" if endstop_source == "toolboard" else "boards"
                    if endstop_source == "toolboard":
                        current_endstop_port = self.state.get(f"{state_key}.endstop_port_toolboard", "")
                    else:
                        current_endstop_port = self.state.get(f"{state_key}.endstop_port", "")

                    endstop_ports = self._get_board_ports("endstop_ports", board_type)
                    if endstop_ports:
                        endstop_port = self.ui.radiolist(
                            f"Select endstop port for {axis_upper} axis:",
                            [
                                (
                                    p,
                                    l,
                                    (p == current_endstop_port) if current_endstop_port else bool(d),
                                )
                                for p, l, d in endstop_ports
                            ],
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

                    # Check if port is already assigned and unassign it
                    pin_manager = self._get_pin_manager()
                    assigned_to = pin_manager.get_used_by(endstop_source, endstop_port)
                    if assigned_to and endstop_port != current_endstop_port:
                        unassigned_purpose = pin_manager.unassign_port_from_state(endstop_source, endstop_port)
                        if unassigned_purpose:
                            self.ui.msgbox(
                                f"Port {endstop_port} was previously assigned to: {unassigned_purpose}\n\n"
                                f"It has been unassigned and is now available for: {axis_upper} endstop",
                                title="Port Reassigned"
                            )

                    # Persist chosen endstop port immediately and clear the other side to avoid ambiguity.
                    if endstop_source == "toolboard":
                        self.state.set(f"{state_key}.endstop_port_toolboard", endstop_port)
                        self.state.delete(f"{state_key}.endstop_port")
                    else:
                        self.state.set(f"{state_key}.endstop_port", endstop_port)
                        self.state.delete(f"{state_key}.endstop_port_toolboard")
                    self.state.save()

                    wiring = self._prompt_endstop_wiring(axis_upper=axis_upper, state_key=state_key)
                    if wiring is None:
                        return
                    endstop_pullup, endstop_invert = wiring

                    # Persist config immediately so it is reflected when re-entering the menu.
                    self.state.set(f"{state_key}.endstop_pullup", bool(endstop_pullup))
                    self.state.set(f"{state_key}.endstop_invert", bool(endstop_invert))
                    # Drop legacy encoding going forward
                    self.state.delete(f"{state_key}.endstop_config")
                    self.state.save()
                else:
                    # Sensorless: clear any stale physical endstop wiring info.
                    self.state.delete(f"{state_key}.endstop_source")
                    self.state.delete(f"{state_key}.endstop_port")
                    self.state.delete(f"{state_key}.endstop_port_toolboard")
                    self.state.delete(f"{state_key}.endstop_pullup")
                    self.state.delete(f"{state_key}.endstop_invert")
                    self.state.delete(f"{state_key}.endstop_config")
                    self.state.save()

                bed_size = self.state.get(f"printer.bed_size_{axis}", 350)
                current_position_max = self.state.get(f"{state_key}.position_max", bed_size)
                position_max = self._inputbox_debug(
                    f"Position max for {axis_upper} (mm):",
                    default=str(current_position_max),
                    title=f"Stepper {axis_upper} - Position",
                    debug_key=f"{state_key}.position_max(inherit)",
                )
                if position_max is None:
                    self.ui.msgbox(
                        f"Didn't receive a value for position_max.\n\n"
                        f"This can happen if you pressed Cancel/Esc or if whiptail failed.\n\n"
                        f"A debug log may be available at:\n{self._wizard_log_path()}",
                        title="Wizard Input Cancelled / Failed",
                    )
                    return
                # Persist immediately.
                try:
                    self.state.set(f"{state_key}.position_max", int(float(position_max)))
                    self.state.save()
                except Exception:
                    # Keep prior value if parse fails; final validation will catch issues.
                    pass

                current_position_endstop = self.state.get(f"{state_key}.position_endstop", position_max)
                position_endstop = self._inputbox_debug(
                    f"Position endstop for {axis_upper} (0 for min, {position_max} for max):",
                    default=str(current_position_endstop),
                    title=f"Stepper {axis_upper} - Endstop Position",
                    debug_key=f"{state_key}.position_endstop(inherit)",
                )
                if position_endstop is None:
                    self.ui.msgbox(
                        f"Didn't receive a value for position_endstop.\n\n"
                        f"This can happen if you pressed Cancel/Esc or if whiptail failed.\n\n"
                        f"A debug log may be available at:\n{self._wizard_log_path()}",
                        title="Wizard Input Cancelled / Failed",
                    )
                    return
                # Persist immediately.
                try:
                    self.state.set(f"{state_key}.position_endstop", int(float(position_endstop)))
                    self.state.save()
                except Exception:
                    pass

                # Position min (must be <= position_endstop)
                # Default: if endstop is negative (common for nozzle wipe zones), match it; otherwise 0.
                try:
                    parsed_endstop = float(position_endstop)
                except Exception:
                    parsed_endstop = float(current_position_endstop) if current_position_endstop is not None else 0.0

                current_position_min = self.state.get(f"{state_key}.position_min", None)
                if current_position_min is None:
                    current_position_min = int(parsed_endstop) if parsed_endstop < 0 else 0

                position_min = self.ui.inputbox(
                    f"Position min for {axis_upper} (mm):\n\n"
                    f"Must be <= position_endstop ({position_endstop}).\n"
                    "Use negative values if you have a wipe/purge zone beyond the bed.",
                    default=str(current_position_min),
                    title=f"Stepper {axis_upper} - Position Min"
                )
                if position_min is None:
                    self.ui.msgbox(
                        f"Didn't receive a value for position_min.\n\n"
                        f"This can happen if you pressed Cancel/Esc or if whiptail failed.\n\n"
                        f"A debug log may be available at:\n{self._wizard_log_path()}",
                        title="Wizard Input Cancelled / Failed",
                    )
                    return
                # Persist immediately.
                try:
                    self.state.set(f"{state_key}.position_min", int(float(position_min)))
                    self.state.save()
                except Exception:
                    pass

                # Homing settings
                current_homing_speed = self.state.get(f"{state_key}.homing_speed", 50)
                homing_speed = self.ui.inputbox(
                    f"Homing speed for {axis_upper} (mm/s):",
                    default=str(current_homing_speed),
                    title=f"Stepper {axis_upper} - Homing Speed"
                )
                if homing_speed is None:
                    return
                # Persist immediately.
                try:
                    self.state.set(f"{state_key}.homing_speed", int(float(homing_speed)))
                    self.state.save()
                except Exception:
                    pass

                current_retract = self.state.get(f"{state_key}.homing_retract_dist", 5.0 if endstop_type == "physical" else 0.0)
                default_retract = "0" if endstop_type == "sensorless" else str(int(current_retract))
                homing_retract_dist = self.ui.inputbox(
                    f"Homing retract distance for {axis_upper} (mm):",
                    default=default_retract,
                    title=f"Stepper {axis_upper} - Homing Retract"
                )
                if homing_retract_dist is None:
                    return
                # Persist immediately (0 is valid).
                try:
                    self.state.set(f"{state_key}.homing_retract_dist", float(homing_retract_dist))
                    self.state.save()
                except Exception:
                    pass

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
                    if second_homing_speed is None:
                        return
                    try:
                        self.state.set(f"{state_key}.second_homing_speed", int(float(second_homing_speed)))
                        self.state.save()
                    except Exception:
                        pass
                else:
                    # If user disables it, clear stale value.
                    if current_has_second:
                        self.state.delete(f"{state_key}.second_homing_speed")
                        self.state.save()

                # Persist final pass for consistency (but avoid clobbering toolboard vs mainboard endstop keys).
                self.state.set(f"{state_key}.endstop_type", endstop_type or "physical")
                if endstop_type == "physical":
                    resolved_source = locals().get("endstop_source") or self.state.get(f"{state_key}.endstop_source") or "mainboard"
                    if endstop_port:
                        if resolved_source == "toolboard":
                            self.state.set(f"{state_key}.endstop_port_toolboard", endstop_port)
                            self.state.delete(f"{state_key}.endstop_port")
                        else:
                            self.state.set(f"{state_key}.endstop_port", endstop_port)
                            self.state.delete(f"{state_key}.endstop_port_toolboard")
                    # Ensure legacy endstop_config stays removed
                    self.state.delete(f"{state_key}.endstop_config")
                else:
                    self.state.delete(f"{state_key}.endstop_source")
                    self.state.delete(f"{state_key}.endstop_port")
                    self.state.delete(f"{state_key}.endstop_port_toolboard")
                    self.state.delete(f"{state_key}.endstop_pullup")
                    self.state.delete(f"{state_key}.endstop_invert")
                    self.state.delete(f"{state_key}.endstop_config")

                bed_size = self.state.get(f"printer.bed_size_{axis}", 350)
                try:
                    self.state.set(f"{state_key}.position_max", int(float(position_max or bed_size)))
                except Exception:
                    self.state.set(f"{state_key}.position_max", int(bed_size))
                try:
                    self.state.set(f"{state_key}.position_endstop", int(float(position_endstop or position_max or bed_size)))
                except Exception:
                    self.state.set(f"{state_key}.position_endstop", int(float(self.state.get(f"{state_key}.position_endstop", 0) or 0)))
                try:
                    self.state.set(f"{state_key}.position_min", int(float(position_min)))
                except Exception:
                    pass
                try:
                    self.state.set(f"{state_key}.homing_speed", int(float(homing_speed or 50)))
                except Exception:
                    pass
                try:
                    # 0 is valid
                    self.state.set(f"{state_key}.homing_retract_dist", float(homing_retract_dist))
                except Exception:
                    pass
                if second_homing_speed:
                    try:
                        self.state.set(f"{state_key}.second_homing_speed", int(float(second_homing_speed)))
                    except Exception:
                        pass

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
        if belt_pitch is None:
            return
        self.state.set(f"{state_key}.belt_pitch", int(belt_pitch))
        self.state.save()

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
        if pulley_teeth is None:
            return
        self.state.set(f"{state_key}.pulley_teeth", int(pulley_teeth))
        self.state.save()

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
        if microsteps is None:
            return
        self.state.set(f"{state_key}.microsteps", int(microsteps))
        self.state.save()

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
        if full_steps is None:
            return
        self.state.set(f"{state_key}.full_steps_per_rotation", int(full_steps))
        self.state.save()

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
        if driver_type is None:
            return
        self.state.set(f"{state_key}.driver_type", driver_type)
        self.state.set(f"{state_key}.driver_protocol", "spi" if driver_type in ["TMC5160", "TMC2130", "TMC2660"] else "uart")
        self.state.save()

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
        if run_current is None:
            return
        try:
            self.state.set(f"{state_key}.run_current", float(run_current))
            self.state.save()
        except ValueError:
            # Keep previous value if user input isn't parseable; final validation will catch if needed.
            pass

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
            if sense_resistor is None:
                return
            self.state.set(f"{state_key}.sense_resistor", float(sense_resistor))
            self.state.save()

        # Endstop configuration (only for primary steppers)
        endstop_type = None
        endstop_port = None
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
            # Persist immediately.
            self.state.set(f"{state_key}.endstop_type", endstop_type)
            self.state.save()

            # Physical endstop port and config
            if endstop_type == "physical":
                # If a toolboard exists, allow selecting endstop from mainboard or toolboard.
                has_toolboard = bool(self.state.get("mcu.toolboard.connection_type"))
                current_endstop_src = self.state.get(f"{state_key}.endstop_source", "")
                if not current_endstop_src:
                    # Infer from existing stored ports so the UI reflects prior choices.
                    if self.state.get(f"{state_key}.endstop_port_toolboard"):
                        current_endstop_src = "toolboard"
                    elif self.state.get(f"{state_key}.endstop_port"):
                        current_endstop_src = "mainboard"
                    else:
                        current_endstop_src = "mainboard"
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

                # Persist location immediately so it doesn't get lost on later cancels.
                self.state.set(f"{state_key}.endstop_source", endstop_source)
                self.state.save()

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
                        [
                            (
                                p,
                                l,
                                (p == current_port) if current_port else bool(d),
                            )
                            for p, l, d in endstop_ports
                        ],
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

                # Persist chosen endstop port immediately and clear the other side to avoid ambiguity.
                if endstop_source == "toolboard":
                    self.state.set(f"{state_key}.endstop_port_toolboard", endstop_port)
                    self.state.delete(f"{state_key}.endstop_port")
                else:
                    self.state.set(f"{state_key}.endstop_port", endstop_port)
                    self.state.delete(f"{state_key}.endstop_port_toolboard")
                self.state.save()

                # Endstop pin configuration (modifiers)
                wiring = self._prompt_endstop_wiring(axis_upper=axis_upper, state_key=state_key)
                if wiring is None:
                    return
                endstop_pullup, endstop_invert = wiring

                # Persist config immediately so it is reflected when re-entering the menu.
                self.state.set(f"{state_key}.endstop_pullup", bool(endstop_pullup))
                self.state.set(f"{state_key}.endstop_invert", bool(endstop_invert))
                self.state.delete(f"{state_key}.endstop_config")
                self.state.save()
            else:
                # Sensorless: clear any stale physical endstop wiring info.
                self.state.delete(f"{state_key}.endstop_source")
                self.state.delete(f"{state_key}.endstop_port")
                self.state.delete(f"{state_key}.endstop_port_toolboard")
                self.state.delete(f"{state_key}.endstop_pullup")
                self.state.delete(f"{state_key}.endstop_invert")
                self.state.delete(f"{state_key}.endstop_config")
                self.state.save()

            bed_size = self.state.get(f"printer.bed_size_{axis}", 350)
            current_max = self.state.get(f"{state_key}.position_max", bed_size)
            position_max = self._inputbox_debug(
                f"Position max for {axis_upper} (mm):",
                default=str(current_max),
                title=f"Stepper {axis_upper} - Position",
                debug_key=f"{state_key}.position_max(full)",
            )
            if position_max is None:
                self.ui.msgbox(
                    f"Didn't receive a value for position_max.\n\n"
                    f"This can happen if you pressed Cancel/Esc or if whiptail failed.\n\n"
                    f"A debug log may be available at:\n{self._wizard_log_path()}",
                    title="Wizard Input Cancelled / Failed",
                )
                return
            # Persist immediately.
            try:
                self.state.set(f"{state_key}.position_max", int(float(position_max)))
                self.state.save()
            except Exception:
                pass

            current_endstop_pos = self.state.get(f"{state_key}.position_endstop", position_max)
            position_endstop = self._inputbox_debug(
                f"Position endstop for {axis_upper} (0 for min, {position_max} for max):",
                default=str(current_endstop_pos),
                title=f"Stepper {axis_upper} - Endstop Position",
                debug_key=f"{state_key}.position_endstop(full)",
            )
            if position_endstop is None:
                self.ui.msgbox(
                    f"Didn't receive a value for position_endstop.\n\n"
                    f"This can happen if you pressed Cancel/Esc or if whiptail failed.\n\n"
                    f"A debug log may be available at:\n{self._wizard_log_path()}",
                    title="Wizard Input Cancelled / Failed",
                )
                return
            # Persist immediately.
            try:
                self.state.set(f"{state_key}.position_endstop", int(float(position_endstop)))
                self.state.save()
            except Exception:
                pass

            # Position min (must be <= position_endstop)
            try:
                parsed_endstop = float(position_endstop)
            except Exception:
                parsed_endstop = float(current_endstop_pos) if current_endstop_pos is not None else 0.0

            current_min = self.state.get(f"{state_key}.position_min", None)
            if current_min is None:
                current_min = int(parsed_endstop) if parsed_endstop < 0 else 0

            position_min = self._inputbox_debug(
                f"Position min for {axis_upper} (mm):\n\n"
                f"Must be <= position_endstop ({position_endstop}).\n"
                "Use negative values if you have a wipe/purge zone beyond the bed.",
                default=str(current_min),
                title=f"Stepper {axis_upper} - Position Min",
                debug_key=f"{state_key}.position_min(full)",
            )
            if position_min is None:
                self.ui.msgbox(
                    f"Didn't receive a value for position_min.\n\n"
                    f"This can happen if you pressed Cancel/Esc or if whiptail failed.\n\n"
                    f"A debug log may be available at:\n{self._wizard_log_path()}",
                    title="Wizard Input Cancelled / Failed",
                )
                return
            # Persist immediately.
            try:
                self.state.set(f"{state_key}.position_min", int(float(position_min)))
                self.state.save()
            except Exception:
                pass

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
            # Persist immediately.
            try:
                self.state.set(f"{state_key}.homing_speed", int(float(homing_speed)))
                self.state.save()
            except Exception:
                pass

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
            # Persist immediately (0 is valid).
            try:
                self.state.set(f"{state_key}.homing_retract_dist", float(homing_retract_dist))
                self.state.save()
            except Exception:
                pass

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
                if second_homing_speed is None:
                    return
                try:
                    self.state.set(f"{state_key}.second_homing_speed", int(float(second_homing_speed)))
                    self.state.save()
                except Exception:
                    pass
            else:
                # If user disables it, clear stale value.
                if current_has_second:
                    self.state.delete(f"{state_key}.second_homing_speed")
                    self.state.save()

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
            # Ensure we do not keep the legacy endstop_config encoding; templates use
            # endstop_pullup/endstop_invert (with fallback for older state).
            self.state.delete(f"{state_key}.endstop_config")
            bed_size = self.state.get(f"printer.bed_size_{axis}", 350)
            self.state.set(f"{state_key}.position_max", int(position_max or bed_size))
            self.state.set(f"{state_key}.position_endstop", int(position_endstop or position_max or bed_size))
            self.state.set(f"{state_key}.position_min", int(float(position_min)))
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
        if z_count is None:
            return

        # Drive type
        drive_type = self.ui.radiolist(
            "Z drive type:",
            [
                ("leadscrew", "Leadscrew (T8, TR8)", current_drive_type == "leadscrew"),
                ("belt", "Belt driven", current_drive_type == "belt"),
            ],
            title="Z Axis - Drive"
        )
        if drive_type is None:
            return

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
            if pitch is None:
                return
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
        if endstop_type is None:
            return

        # Position - use saved value or bed_z
        bed_z = self.state.get("printer.bed_size_z", 350)
        position_default = current_position_max if current_position_max is not None else bed_z
        position_max = self.ui.inputbox(
            "Z position max (mm):",
            default=str(position_default),
            title="Z Axis - Position"
        )
        if position_max is None:
            return

        # Current
        run_current = self.ui.inputbox(
            "TMC run current for Z (A):",
            default=str(current_run_current),
            title="Z Axis - Driver"
        )
        if run_current is None:
            return

        # Save
        self.state.set("stepper_z.z_motor_count", int(z_count or 4))
        self.state.set("stepper_z.drive_type", drive_type)
        self.state.set("stepper_z.leadscrew_pitch", int(pitch or 8))
        self.state.set("stepper_z.endstop_type", endstop_type)
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
        """Configure extruder motor and hotend per schema 2.6.

        Uses PinManager for consistent pin selection with conflict detection.
        """
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

        # Motor port selection using PinManager (filters used ports)
        pin_manager = self._get_pin_manager()
        # Check both possible keys for current value
        current_port = self.state.get(f"extruder.motor_port_{motor_location}", "") or \
                      self.state.get("extruder.motor_port_mainboard", "") or \
                      self.state.get("extruder.motor_port_toolboard", "")
        # Mark current port as available for reselection
        if current_port:
            pin_manager.mark_unused(motor_location, current_port)

        motor_port = pin_manager.select_motor_port(
            location=motor_location,
            purpose="Extruder",
            current_port=current_port or ("EXTRUDER" if motor_location == "toolboard" else "MOTOR_5"),
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

        # Heater port selection using PinManager
        pin_manager = self._get_pin_manager()
        current_port = self.state.get(f"extruder.heater_port_{heater_location}", "") or \
                      self.state.get("extruder.heater_port_mainboard", "") or \
                      self.state.get("extruder.heater_port_toolboard", "")
        # Remove current port from used set so we can reconfigure
        pin_manager.mark_unused(heater_location, current_port)

        heater_port = pin_manager.select_output_pin(
            location=heater_location,
            purpose="Hotend Heater",
            output_type="mosfet",
            groups=["heater_ports", "misc_ports"],
            current_port=current_port,
            title="Hotend - Heater Port"
        )
        if heater_port is None:
            return

        pin_manager.mark_used(heater_location, heater_port, "Hotend heater")

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

        # Thermistor port selection using PinManager
        current_port = self.state.get(f"extruder.sensor_port_{sensor_location}", "") or \
                      self.state.get("extruder.sensor_port_mainboard", "") or \
                      self.state.get("extruder.sensor_port_toolboard", "")
        # Remove current port from used set so we can reconfigure
        pin_manager.mark_unused(sensor_location, current_port)

        sensor_port = pin_manager.select_output_pin(
            location=sensor_location,
            purpose="Hotend Thermistor",
            output_type="signal",
            groups=["thermistor_ports", "misc_ports"],
            current_port=current_port,
            title="Hotend - Thermistor Port"
        )
        if sensor_port is None:
            return

        pin_manager.mark_used(sensor_location, sensor_port, "Hotend thermistor")

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

        # Pullup resistor selection using PinManager
        # Default to 2200 for toolboards, 4700 for mainboards
        default_pullup = 2200 if sensor_location == "toolboard" else 4700
        extruder_cfg = self.state.get_section("extruder")
        has_pullup_key = isinstance(extruder_cfg, dict) and ("pullup_resistor" in extruder_cfg)
        current_pullup = extruder_cfg.get("pullup_resistor") if has_pullup_key else None
        effective_pullup = int(current_pullup) if isinstance(current_pullup, (int, float, str)) and current_pullup else int(default_pullup)

        pullup_resistor = pin_manager.select_pullup_resistor(
            default=effective_pullup if not (has_pullup_key and current_pullup is None) else None,
            title="Hotend - Pullup Resistor"
        )

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
        self.state.set("extruder.pullup_resistor", pullup_resistor)
        # Remove sensor_pullup if it exists (ADC inputs don't use ^ modifier)
        self.state.delete("extruder.sensor_pullup")
        self.state.set("extruder.min_temp", int(min_temp or 0))
        self.state.set("extruder.max_temp", int(max_temp or 300))
        self.state.set("extruder.drive_type", drive_type or "direct")
        self.state.set("extruder.max_extrude_only_distance", int(max_extrude_only_distance or default_extrude_dist))
        self.state.set("extruder.max_extrude_cross_section", float(max_extrude_cross_section or 5.0))
        self.state.set("extruder.min_extrude_temp", int(min_extrude_temp or 170))
        self.state.set("extruder.instantaneous_corner_velocity", float(instantaneous_corner_velocity or 1.0))
        self.state.save()

        pullup_text = f"\n  Pullup resistor: {pullup_resistor}Ω" if pullup_resistor else ""
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

    def _collect_used_mainboard_pins(self, exclude_bed: bool = False) -> set:
        # .. deprecated:: 2.1 - Use PinManager instead. See scripts/wizard/pins.py
        """Collect mainboard pins already assigned in wizard state.

        Args:
            exclude_bed: If True, don't include heater_bed pins (useful when re-configuring bed).

        Returns:
            Set of port IDs that are already in use.
        """
        used = set()

        # Steppers (mainboard motor ports)
        for axis in ["stepper_x", "stepper_y", "stepper_z", "stepper_x1", "stepper_y1"]:
            port = self.state.get(f"{axis}.motor_port")
            if port:
                used.add(port)
            endstop = self.state.get(f"{axis}.endstop_port")
            if endstop:
                used.add(endstop)

        # Z motors (if multiple)
        z_count = self.state.get("stepper_z.z_motor_count", 1) or 1
        for i in range(1, int(z_count)):
            port = self.state.get(f"stepper_z{i}.motor_port")
            if port:
                used.add(port)

        # Extruder (mainboard)
        if self.state.get("extruder.location") == "mainboard":
            port = self.state.get("extruder.motor_port_mainboard")
            if port:
                used.add(port)
        if self.state.get("extruder.heater_location") == "mainboard":
            port = self.state.get("extruder.heater_port_mainboard")
            if port:
                used.add(port)
        if self.state.get("extruder.sensor_location") == "mainboard":
            port = self.state.get("extruder.sensor_port_mainboard")
            if port:
                used.add(port)

        # Heater bed
        if not exclude_bed:
            bed_heater = self.state.get("heater_bed.heater_pin")
            if bed_heater:
                used.add(bed_heater)
            bed_sensor = self.state.get("heater_bed.sensor_port")
            if bed_sensor:
                used.add(bed_sensor)

        # Fans (mainboard)
        if self.state.get("fans.part_cooling.location") == "mainboard":
            pin = self.state.get("fans.part_cooling.pin_mainboard")
            if pin:
                used.add(pin)
        if self.state.get("fans.hotend.location") == "mainboard":
            pin = self.state.get("fans.hotend.pin_mainboard")
            if pin:
                used.add(pin)
        controller_pin = self.state.get("fans.controller.pin")
        if controller_pin:
            used.add(controller_pin)

        # Additional fans
        for fan in self.state.get("fans.additional_fans", []) or []:
            if isinstance(fan, dict) and fan.get("location") == "mainboard":
                pin = fan.get("pin")
                if pin:
                    used.add(pin)

        # Probe
        probe_pin = self.state.get("probe.probe_pin_mainboard")
        if probe_pin:
            used.add(probe_pin)

        return used

    def _build_output_pin_options(self, board_data: dict, current_value: str, used_pins: set) -> list:
        """Build radiolist options for output pins (heaters, fans, misc outputs).

        Returns list of (tag, label, is_selected) tuples.

        .. deprecated:: 2.1
            Use PinManager.select_output_pin() instead.
            See scripts/wizard/pins.py for the new unified pin selection approach.
        """
        options = []
        seen_tags = set()

        # Priority groups for output pins
        groups = ["heater_ports", "fan_ports", "misc_ports", "endstop_ports"]

        for group in groups:
            group_data = board_data.get(group, {})
            if not isinstance(group_data, dict):
                continue

            for port_id, port_info in group_data.items():
                if port_id in used_pins:
                    continue  # Skip already used

                if isinstance(port_info, dict):
                    pin = port_info.get("pin") or port_info.get("signal_pin") or ""
                    label = port_info.get("label", port_id)
                    if pin:
                        label = f"{label} ({pin})"
                else:
                    label = port_id
                    pin = str(port_info) if port_info else ""

                tag = port_id
                if tag in seen_tags:
                    continue
                seen_tags.add(tag)

                is_selected = (port_id == current_value)
                options.append((tag, f"{label} [{group}]", is_selected))

        # Sort: bed-related first, then alphabetically
        def sort_key(item):
            tag, label, _ = item
            is_bed = "bed" in tag.lower() or "hb" == tag.lower() or "tb" == tag.lower()
            return (0 if is_bed else 1, tag.lower())

        options.sort(key=sort_key)

        # Ensure something is selected
        if options and not any(x[2] for x in options):
            options[0] = (options[0][0], options[0][1], True)

        return options

    def _build_thermistor_pin_options(self, board_data: dict, current_value: str, used_pins: set) -> list:
        """Build radiolist options for thermistor/ADC pins.

        Returns list of (tag, label, is_selected) tuples.

        .. deprecated:: 2.1
            Use PinManager.select_output_pin() with groups=["thermistor_ports"] instead.
            See scripts/wizard/pins.py for the new unified pin selection approach.
        """
        options = []
        seen_tags = set()

        # Priority: thermistor ports first, then misc
        groups = ["thermistor_ports", "misc_ports"]

        for group in groups:
            group_data = board_data.get(group, {})
            if not isinstance(group_data, dict):
                continue

            for port_id, port_info in group_data.items():
                if port_id in used_pins:
                    continue  # Skip already used

                if isinstance(port_info, dict):
                    pin = port_info.get("pin") or port_info.get("signal_pin") or ""
                    label = port_info.get("label", port_id)
                    if pin:
                        label = f"{label} ({pin})"
                else:
                    label = port_id
                    pin = str(port_info) if port_info else ""

                tag = port_id
                if tag in seen_tags:
                    continue
                seen_tags.add(tag)

                is_selected = (port_id == current_value)
                options.append((tag, f"{label} [{group}]", is_selected))

        # Sort: bed-related first, then alphabetically
        def sort_key(item):
            tag, label, _ = item
            is_bed = "bed" in tag.lower() or "tb" == tag.lower()
            return (0 if is_bed else 1, tag.lower())

        options.sort(key=sort_key)

        # Ensure something is selected
        if options and not any(x[2] for x in options):
            options[0] = (options[0][0], options[0][1], True)

        return options

    def _heater_bed_setup(self) -> None:
        """Configure heated bed per schema 2.7.

        Uses PinManager for consistent pin selection with conflict detection.
        """
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

        # Get pullup resistor current value
        bed_cfg = self.state.get_section("heater_bed")
        has_pullup_key = isinstance(bed_cfg, dict) and ("pullup_resistor" in bed_cfg)
        current_pullup = bed_cfg.get("pullup_resistor") if has_pullup_key else 4700
        if current_pullup is not None:
            current_pullup = int(current_pullup) if isinstance(current_pullup, (int, float, str)) else 4700

        # Create PinManager for this session - exclude bed pins since we're reconfiguring
        pin_manager = self._get_pin_manager()
        # Remove current bed pins from used set so we can reconfigure them
        pin_manager.mark_unused("mainboard", current_heater_pin)
        pin_manager.mark_unused("mainboard", current_sensor_port)

        # Check if board is configured
        board_id = self.state.get("mcu.main.board_type", "")
        if not board_id:
            self.ui.msgbox(
                "No mainboard selected.\n\n"
                "Please select a mainboard first in MCU Setup.",
                title="Heated Bed - Error"
            )
            return

        # === 2.7.1: Heater Configuration ===
        heater_pin = pin_manager.select_output_pin(
            location="mainboard",
            purpose="Heated Bed Heater",
            output_type="mosfet",
            groups=["heater_ports", "fan_ports", "misc_ports"],
            current_port=current_heater_pin,
            title="Heated Bed - Heater Pin"
        )
        if heater_pin is None:
            return

        # Mark pin as used for conflict detection
        pin_manager.mark_used("mainboard", heater_pin, "Heated bed heater")

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
        # Select thermistor port
        sensor_port = pin_manager.select_output_pin(
            location="mainboard",
            purpose="Bed Thermistor",
            output_type="signal",
            groups=["thermistor_ports", "misc_ports"],
            current_port=current_sensor_port,
            title="Heated Bed - Thermistor Port"
        )
        if sensor_port is None:
            return

        # Sensor type selection
        sensor_type = pin_manager.select_sensor_type(
            current=current_sensor_type,
            title="Heated Bed - Thermistor Type"
        )
        if sensor_type is None:
            return

        # Pullup resistor selection using PinManager
        pullup_resistor = pin_manager.select_pullup_resistor(
            default=current_pullup,
            title="Heated Bed - Pullup Resistor"
        )

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
        self.state.set("heater_bed.heater_pin", heater_pin)
        self.state.set("heater_bed.max_power", float(max_power or 1.0))
        self.state.set("heater_bed.pwm_cycle_time", float(pwm_cycle_time or 0.0166))
        self.state.set("heater_bed.sensor_port", sensor_port)
        self.state.set("heater_bed.sensor_type", sensor_type or "Generic 3950")
        # Store pullup_resistor explicitly (None means "omit from config")
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
        """Configure fans.

        Uses PinManager for consistent pin selection with conflict detection.
        """
        has_toolboard = self.state.get("mcu.toolboard.connection_type") or \
                        self.state.get("mcu.toolboard.enabled", False)

        # Create PinManager for this session
        pin_manager = self._get_pin_manager()

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

        # Part cooling fan pin selection using PinManager
        current_pin = self.state.get(f"fans.part_cooling.pin_{part_location}", "") or \
                      self.state.get("fans.part_cooling.pin_mainboard", "") or \
                      self.state.get("fans.part_cooling.pin_toolboard", "")
        # Remove current pin from used set so we can reconfigure
        pin_manager.mark_unused(part_location, current_pin)

        part_pin = pin_manager.select_output_pin(
            location=part_location,
            purpose="Part Cooling Fan",
            output_type="pwm",
            groups=["fan_ports", "heater_ports", "misc_ports"],
            current_port=current_pin,
            title="Fans - Part Cooling Pin"
        )
        if part_pin is None:
            return

        # If empty string, user cancelled or cleared - return early
        if not part_pin:
            return

        # Mark as used for conflict detection
        pin_manager.mark_used(part_location, part_pin, "Part cooling fan")

        # Part cooling fan parameters
        current_max_power = self.state.get("fans.part_cooling.max_power", 1.0)
        max_power = self.ui.inputbox(
            "Part cooling fan max power (0.1-1.0):",
            default=str(current_max_power),
            title="Fans - Part Cooling Max Power"
        )
        if max_power is None:
            return

        current_cycle = self.state.get("fans.part_cooling.cycle_time", 0.002)
        cycle_time = self.ui.inputbox(
            "Cycle time (seconds):\n\n"
            "(PWM cycle time, usually 0.002 for part cooling fans)",
            default=str(current_cycle),
            title="Fans - Part Cooling Cycle Time"
        )
        if cycle_time is None:
            return

        # Hardware PWM (default to false for part cooling)
        current_hardware_pwm = self.state.get("fans.part_cooling.hardware_pwm", False)
        hardware_pwm = self.ui.yesno(
            "Use hardware PWM for part cooling fan?\n\n"
            "Most part cooling fans use software PWM (No).\n"
            "Hardware PWM is only needed for specific fan controllers.",
            title="Fans - Part Cooling Hardware PWM",
            default_no=not current_hardware_pwm
        )
        if hardware_pwm is None:
            return

        # Shutdown speed (default to 0 - fan should turn off on shutdown)
        current_shutdown_speed = self.state.get("fans.part_cooling.shutdown_speed", 0)
        shutdown_speed = self.ui.inputbox(
            "Shutdown speed (0.0-1.0):\n\n"
            "(Fan speed when printer shuts down, usually 0)",
            default=str(current_shutdown_speed),
            title="Fans - Part Cooling Shutdown Speed"
        )
        if shutdown_speed is None:
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

        # Hotend fan pin selection using PinManager
        current_pin = self.state.get(f"fans.hotend.pin_{hotend_location}", "") or \
                      self.state.get("fans.hotend.pin_mainboard", "") or \
                      self.state.get("fans.hotend.pin_toolboard", "")
        # Remove current pin from used set so we can reconfigure
        pin_manager.mark_unused(hotend_location, current_pin)

        hotend_pin = pin_manager.select_output_pin(
            location=hotend_location,
            purpose="Hotend Fan",
            output_type="pwm",
            groups=["fan_ports", "heater_ports", "misc_ports"],
            current_port=current_pin,
            title="Fans - Hotend Pin"
        )
        if hotend_pin is None:
            return

        # Mark as used for conflict detection (skip if cleared)
        if hotend_pin:
            pin_manager.mark_used(hotend_location, hotend_pin, "Hotend fan")

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
            # Controller fan is always on mainboard - use PinManager
            current_pin = self.state.get("fans.controller.pin", "")
            # Remove current pin from used set so we can reconfigure
            pin_manager.mark_unused("mainboard", current_pin)

            controller_pin = pin_manager.select_output_pin(
                location="mainboard",
                purpose="Controller Fan",
                output_type="pwm",
                groups=["fan_ports", "heater_ports", "misc_ports"],
                current_port=current_pin,
                title="Fans - Controller Pin"
            )
            if controller_pin is None:
                return

            # If empty string, user cancelled or cleared - skip controller fan config
            if not controller_pin:
                has_controller_fan = False
                controller_pin = None
            else:
                # Mark as used for conflict detection
                pin_manager.mark_used("mainboard", controller_pin, "Controller fan")

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

            # Location (mainboard/toolboard)
            # This affects both the pin picker UI and how pins are rendered in templates.
            current_location = (fan.get("location") if isinstance(fan, dict) else None) or "mainboard"
            location = self.ui.radiolist(
                f"Where is '{fan_name}' connected?",
                [
                    ("mainboard", "Mainboard MCU", current_location == "mainboard"),
                    ("toolboard", "Toolboard MCU", current_location == "toolboard"),
                ],
                title=f"{fan_name} - Location",
            )
            if location is None:
                return None

            # Control mode:
            # - manual: [fan_generic] (no control method required)
            # - heater: [heater_fan <name>] controlled by a heater object
            current_control = (fan.get("control_mode") if isinstance(fan, dict) else None) or "manual"
            control_mode = self.ui.radiolist(
                f"Control mode for '{fan_name}':",
                [
                    ("manual", "Manual (fan_generic)", current_control == "manual"),
                    ("heater", "Heater controlled (heater_fan)", current_control == "heater"),
                ],
                title=f"{fan_name} - Control Mode",
            )
            if control_mode is None:
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
            fan_config["control_mode"] = control_mode
            fan_config["location"] = location

            if is_multi_pin:
                # For multi-pin, need to select multiple ports
                current_pins = fan.get("pins", "") if fan else None
                board_type = "boards" if location == "mainboard" else "toolboards"
                board_id = (
                    self.state.get("mcu.main.board_type", "")
                    if location == "mainboard"
                    else self.state.get("mcu.toolboard.board_type", "")
                )
                board_data = self._load_board_data(board_id, board_type)

                # Normalize currently selected pins (supports older states that stored port IDs)
                current_set = set()
                if current_pins:
                    current_set = {p.strip() for p in str(current_pins).split(",") if p.strip()}

                # Build a unified pick list of output-capable pins:
                # - fan_ports (fan headers)
                # - heater_ports (often repurposed as fan outputs)
                # - misc_ports (GPIO / AUX pins)
                groups = [
                    ("fan_ports", "Fan"),
                    ("heater_ports", "Heater"),
                    ("misc_ports", "Misc"),
                ]
                items = []
                tag_to_pin = {}
                ordered_tags = []

                if isinstance(board_data, dict) and board_data:
                    for group_key, group_label in groups:
                        ports = board_data.get(group_key, {})
                        if not isinstance(ports, dict) or not ports:
                            continue
                        for port_id, port_info in ports.items():
                            if not isinstance(port_info, dict):
                                continue
                            pin = port_info.get("pin") or port_info.get("signal_pin")
                            if not pin:
                                continue
                            label = port_info.get("label", port_id)
                            tag = f"{group_key}:{port_id}"
                            desc = f"[{group_label}] {port_id} - {label} ({pin})"
                            tag_to_pin[tag] = str(pin).strip()
                            ordered_tags.append(tag)
                            # Preselect if current set contains either the actual pin (preferred) or the port_id (older state)
                            selected_default = (tag_to_pin[tag] in current_set) or (str(port_id).strip() in current_set) or (tag in current_set)
                            items.append((tag, desc, selected_default))

                if items:
                    selected = self.ui.checklist(
                        f"Select ALL pins for '{fan_name}'.\n\n"
                        "Use SPACE to toggle a pin, ENTER to confirm.",
                        items,
                        title=f"{fan_name} - Multi-Pin Pins",
                        height=24,
                        width=140,
                        list_height=min(18, max(8, len(items))),
                    )
                    if selected is None:
                        return None
                    # Stable output: keep original order
                    selected_set = set(selected)
                    raw_pins = [tag_to_pin[t] for t in ordered_tags if t in selected_set]
                    if location == "toolboard":
                        raw_pins = [f"toolboard:{p}" if not str(p).startswith("toolboard:") else str(p) for p in raw_pins]
                    pins = ", ".join(raw_pins)
                else:
                    # Fallback if board template doesn't provide ports
                    pins = self.ui.inputbox(
                        f"Enter pins for '{fan_name}' (comma-separated):\n\n"
                        "Example: PA15, PB11 (or toolboard:PA15, toolboard:PB11)",
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
                current_pin = fan.get("pin", "") if fan else None
                board_type = "toolboards" if location == "toolboard" else "boards"

                # Offer a picker of *valid* port IDs (what the generator expects),
                # not raw MCU pins. This avoids templates failing on board.pins[fan.pin].
                pick_items = []
                for group_key, group_label in (("fan_ports", "Fan"), ("heater_ports", "Heater"), ("misc_ports", "Misc")):
                    ports = self._get_board_ports(group_key, board_type)
                    if not ports:
                        continue
                    for port_id, label, _default in ports:
                        pick_items.append((port_id, f"[{group_label}] {label}", port_id == current_pin))

                if pick_items:
                    port = self.ui.radiolist(
                        f"Select port for '{fan_name}':\n\n"
                        "Tip: If your fan is wired to a heater output, pick an HE* port.\n"
                        "This stores the port ID (e.g. FAN2 / HE2), not the raw MCU pin.",
                        pick_items,
                        title=f"{fan_name} - Port",
                        height=24,
                        width=140,
                        list_height=min(18, max(8, len(pick_items))),
                    )
                    if port:
                        fan_config["pin_type"] = "single"
                        fan_config["pin"] = port
                else:
                    # Fallback: if the board template doesn't provide ports, accept a port ID manually.
                    pin = self.ui.inputbox(
                        f"Port for '{fan_name}':\n\n"
                        "Enter a board port ID like FAN2 or HE2 (not raw pins like PB10).",
                        default=current_pin or "",
                        title=f"{fan_name} - Port"
                    )
                    fan_config["pin_type"] = "single"
                    fan_config["pin"] = pin

            # Heater control settings (only if control_mode == 'heater')
            if control_mode == "heater":
                current_heater = (fan.get("heater") if isinstance(fan, dict) else None) or self.state.get("fans.hotend.heater", "extruder")
                heater = self._pick_heater_name(current_value=current_heater, title=f"{fan_name} - Heater")
                if heater is None or not str(heater).strip():
                    return None
                current_heater_temp = (fan.get("heater_temp") if isinstance(fan, dict) else None) or 50
                heater_temp = self.ui.inputbox(
                    f"Temperature to turn on '{fan_name}' (°C):",
                    default=str(current_heater_temp),
                    title=f"{fan_name} - Heater Temp",
                )
                if heater_temp is None:
                    return None
                current_fan_speed = (fan.get("fan_speed") if isinstance(fan, dict) else None) or 1.0
                fan_speed = self.ui.inputbox(
                    f"Fan speed for '{fan_name}' (0.1-1.0):",
                    default=str(current_fan_speed),
                    title=f"{fan_name} - Fan Speed",
                )
                if fan_speed is None:
                    return None
                fan_config["heater"] = heater
                fan_config["heater_temp"] = float(heater_temp or 50)
                fan_config["fan_speed"] = float(fan_speed or 1.0)

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
        self.state.set("fans.part_cooling.cycle_time", float(cycle_time or 0.002))
        self.state.set("fans.part_cooling.hardware_pwm", bool(hardware_pwm))
        self.state.set("fans.part_cooling.shutdown_speed", float(shutdown_speed or 0))
        # Remove invalid parameters if they exist (from old configs)
        self.state.delete("fans.part_cooling.kick_start_time")
        self.state.delete("fans.part_cooling.off_below")
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

        # Probe temperature sensor (Beacon/Cartographer/Eddy/PINDA)
        probe_type = self.state.get("probe.probe_type", "")
        eddy_probes = ["beacon", "cartographer", "btt_eddy"]
        inductive_probes = ["inductive"]  # PINDA

        current_probe_temp_enabled = self.state.get("temperature_sensors.probe.enabled", False)

        if probe_type in eddy_probes:
            # Eddy current probes (Beacon/Cartographer/BTT Eddy) have coil temperature
            probe_name_map = {"beacon": "Beacon", "cartographer": "Cartographer", "btt_eddy": "BTT Eddy"}
            probe_display_name = probe_name_map.get(probe_type, "Probe")

            if self.ui.yesno(
                f"Enable {probe_display_name} coil temperature sensor?\n\n"
                f"This monitors the eddy current coil temperature,\n"
                f"which can help with thermal drift compensation.",
                title="Probe Temperature Sensor",
                default_no=not current_probe_temp_enabled
            ):
                sensors.append({
                    "name": f"{probe_type}_coil_temp",
                    "type": "temperature_probe",
                    "probe": probe_type
                })
                self.state.set("temperature_sensors.probe.enabled", True)
                self.state.set("temperature_sensors.probe.sensor_type", "eddy_coil")
            else:
                self.state.set("temperature_sensors.probe.enabled", False)
                self.state.delete("temperature_sensors.probe.sensor_type")
            self.state.save()

        elif probe_type in inductive_probes:
            # PINDA probes can have built-in NTC temperature sensor
            if self.ui.yesno(
                "Does your PINDA probe have a temperature sensor?\n\n"
                "Some PINDA probes (v2) include a built-in NTC\n"
                "thermistor for temperature compensation.",
                title="Probe Temperature Sensor",
                default_no=not current_probe_temp_enabled
            ):
                # Ask for pin
                current_probe_pin = self.state.get("temperature_sensors.probe.sensor_pin", "")
                sensor_ports = self._get_board_ports("thermistor_ports", "boards")
                if sensor_ports:
                    probe_pin = self.ui.radiolist(
                        "Select PINDA thermistor port:",
                        [(p, l, p == current_probe_pin or d) for p, l, d in sensor_ports],
                        title="PINDA Thermistor Port"
                    )
                else:
                    probe_pin = self.ui.inputbox(
                        "Enter PINDA thermistor pin:",
                        default=current_probe_pin,
                        title="PINDA Thermistor Port"
                    )

                if probe_pin:
                    sensors.append({
                        "name": "pinda_temp",
                        "type": "temperature_sensor",
                        "sensor_type": "Generic 3950",
                        "sensor_pin": probe_pin
                    })
                    self.state.set("temperature_sensors.probe.enabled", True)
                    self.state.set("temperature_sensors.probe.sensor_type", "pinda")
                    self.state.set("temperature_sensors.probe.sensor_pin", probe_pin)
            else:
                self.state.set("temperature_sensors.probe.enabled", False)
                self.state.delete("temperature_sensors.probe.sensor_type")
                self.state.delete("temperature_sensors.probe.sensor_pin")
            self.state.save()
        else:
            # Clear probe temperature state if probe type doesn't support it
            if self.state.get("temperature_sensors.probe.enabled"):
                self.state.delete("temperature_sensors.probe")
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

        # Management loop with submenu structure
        while True:
            led_summary = f"Currently configured: {len(leds)} LED strip(s)"
            if leds:
                led_summary += f"\n{', '.join(l.get('name', 'Unknown') for l in leds)}"

            main_menu_items = [
                ("ADD", "Add LED Strip"),
                ("EDIT", f"Edit LED Strip ({len(leds)} configured)"),
                ("DELETE", f"Delete LED Strip ({len(leds)} configured)"),
                ("DONE", "Done (save and exit)"),
            ]

            choice = self.ui.menu(
                f"LED Configuration\n\n{led_summary}",
                main_menu_items,
                title="LED Management"
            )

            if choice is None or choice == "DONE":
                break
            elif choice == "ADD":
                new_led = _edit_led()
                if new_led:
                    leds.append(new_led)
            elif choice == "EDIT":
                if not leds:
                    self.ui.msgbox("No LEDs configured yet. Add one first.", title="No LEDs")
                    continue
                # Submenu for editing
                edit_items = [(str(i), led.get('name', 'Unknown')) for i, led in enumerate(leds)]
                edit_items.append(("B", "Back"))
                edit_choice = self.ui.menu(
                    "Select LED strip to edit:",
                    edit_items,
                    title="Edit LED"
                )
                if edit_choice and edit_choice != "B":
                    idx = int(edit_choice)
                    if 0 <= idx < len(leds):
                        edited = _edit_led(leds[idx])
                        if edited:
                            leds[idx] = edited
            elif choice == "DELETE":
                if not leds:
                    self.ui.msgbox("No LEDs configured yet.", title="No LEDs")
                    continue
                # Submenu for deletion
                delete_items = [(str(i), led.get('name', 'Unknown')) for i, led in enumerate(leds)]
                delete_items.append(("B", "Back"))
                delete_choice = self.ui.menu(
                    "Select LED strip to delete:",
                    delete_items,
                    title="Delete LED"
                )
                if delete_choice and delete_choice != "B":
                    idx = int(delete_choice)
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

            # Check if pin is already assigned and unassign it
            # Note: _pick_pin_from_known_ports returns raw pin strings, so we need to find the port_id
            # For now, we'll check if the pin matches any assigned port by resolving port_ids to pins
            pin_manager = self._get_pin_manager()
            board_type = "boards" if location == "mainboard" else "toolboards"
            board_id = self.state.get("mcu.main.board_type", "") if location == "mainboard" else self.state.get("mcu.toolboard.board_type", "")
            board_data = self._load_board_data(board_id, board_type)

            # Try to find which port_id this pin belongs to
            port_id_for_pin = None
            if isinstance(board_data, dict):
                for group in ["endstop_ports", "misc_ports", "probe_ports", "fan_ports", "heater_ports"]:
                    group_data = board_data.get(group, {})
                    if isinstance(group_data, dict):
                        for port_id, port_info in group_data.items():
                            if isinstance(port_info, dict):
                                port_pin = port_info.get("pin") or port_info.get("signal_pin", "")
                                if port_pin == pin:
                                    port_id_for_pin = port_id
                                    break
                            elif isinstance(port_info, str) and port_info == pin:
                                port_id_for_pin = port_id
                                break
                        if port_id_for_pin:
                            break

            # If we found a port_id, check for assignment
            if port_id_for_pin:
                assigned_to = pin_manager.get_used_by(location, port_id_for_pin)
                if assigned_to and port_id_for_pin != current_pin:
                    unassigned_purpose = pin_manager.unassign_port_from_state(location, port_id_for_pin)
                    if unassigned_purpose:
                        self.ui.msgbox(
                            f"Port {port_id_for_pin} (pin {pin}) was previously assigned to: {unassigned_purpose}\n\n"
                            f"It has been unassigned and is now available for: {name}",
                            title="Port Reassigned"
                        )

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

        # Management loop with submenu structure
        while True:
            sensor_summary = f"Currently configured: {len(sensors)} sensor(s)"
            if sensors:
                sensor_summary += f"\n{', '.join(s.get('name', 'Unknown') for s in sensors)}"

            main_menu_items = [
                ("ADD", "Add Filament Sensor"),
                ("EDIT", f"Edit Filament Sensor ({len(sensors)} configured)"),
                ("DELETE", f"Delete Filament Sensor ({len(sensors)} configured)"),
                ("DONE", "Done (save and exit)"),
            ]

            choice = self.ui.menu(
                f"Filament Sensor Configuration\n\n{sensor_summary}",
                main_menu_items,
                title="Filament Sensor Management"
            )

            if choice is None or choice == "DONE":
                break
            elif choice == "ADD":
                new_sensor = _edit_sensor()
                if new_sensor:
                    sensors.append(new_sensor)
            elif choice == "EDIT":
                if not sensors:
                    self.ui.msgbox("No filament sensors configured yet. Add one first.", title="No Sensors")
                    continue
                # Submenu for editing
                edit_items = [(str(i), sensor.get('name', 'Unknown')) for i, sensor in enumerate(sensors)]
                edit_items.append(("B", "Back"))
                edit_choice = self.ui.menu(
                    "Select filament sensor to edit:",
                    edit_items,
                    title="Edit Filament Sensor"
                )
                if edit_choice and edit_choice != "B":
                    idx = int(edit_choice)
                    if 0 <= idx < len(sensors):
                        edited = _edit_sensor(sensors[idx])
                        if edited:
                            sensors[idx] = edited
            elif choice == "DELETE":
                if not sensors:
                    self.ui.msgbox("No filament sensors configured yet.", title="No Sensors")
                    continue
                # Submenu for deletion
                delete_items = [(str(i), sensor.get('name', 'Unknown')) for i, sensor in enumerate(sensors)]
                delete_items.append(("B", "Back"))
                delete_choice = self.ui.menu(
                    "Select filament sensor to delete:",
                    delete_items,
                    title="Delete Filament Sensor"
                )
                if delete_choice and delete_choice != "B":
                    idx = int(delete_choice)
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
        """Configure display options (LCD/OLED direct display via Klipper).

        Note: KlipperScreen is managed separately in the Klipper Setup section
        (Section 1: Manage Klipper Components) since it's a software component
        rather than hardware configuration.
        """
        while True:
            choice = self.ui.menu(
                "Display Configuration\n\n"
                "Configure display hardware connected directly to the MCU.\n\n"
                "Note: KlipperScreen (touch UI) is managed in Section 1:\n"
                "      Klipper Setup > Manage Klipper Components",
                [
                    ("LCD", "LCD/OLED              (Direct display via Klipper) - Coming soon"),
                    ("B", "Back"),
                ],
                title="2.15 Display",
            )
            if choice is None or choice == "B":
                return
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
            host = self.state.get("display.klipperscreen.moonraker_host", "127.0.0.1")
            port = int(self.state.get("display.klipperscreen.moonraker_port", 7125))

            # KIAUH-style status display
            if installed:
                if running:
                    status_text = "Installed (Running)"
                else:
                    status_text = "Installed (Stopped)"
            else:
                status_text = "Not installed"

            # Build menu options based on installation status (KIAUH-style)
            menu_items = []
            if not installed:
                menu_items.append(("1", "Install KlipperScreen"))
            else:
                menu_items.append(("1", "Update KlipperScreen"))
                menu_items.append(("2", "Configure Moonraker connection"))
                menu_items.append(("3", "Add to Moonraker update_manager"))
                menu_items.append(("4", "Remove KlipperScreen"))
            menu_items.append(("B", "Back"))

            choice = self.ui.menu(
                f"KlipperScreen\n\n"
                f"Status: {status_text}\n"
                + (f"Moonraker: {host}:{port}\n" if installed else ""),
                menu_items,
                title="KlipperScreen",
                height=16,
                width=80,
                menu_height=8,
            )

            if choice is None or choice == "B":
                return

            # Handle "1" - Install (if not installed) or Update (if installed)
            if choice == "1":
                if not installed:
                    # INSTALL
                    confirm = self.ui.yesno(
                        "Install KlipperScreen?\n\n"
                        "This will clone the repository and run the installer.\n"
                        "You may need to enter your sudo password.\n\n"
                        "This may take several minutes.",
                        title="Install KlipperScreen",
                        default_no=False,
                    )
                    if not confirm:
                        continue

                    ks_repo = "https://github.com/KlipperScreen/KlipperScreen.git"
                    print("\n" + "=" * 60)
                    print("Cloning KlipperScreen repository...")
                    print("=" * 60 + "\n")

                    exit_code = self._run_shell_interactive(f"git clone {ks_repo} {ks_dir}")
                    if exit_code != 0:
                        self.ui.msgbox(
                            "Failed to clone repository.\n\n"
                            "Check terminal output for errors.",
                            title="Clone Failed",
                        )
                        continue

                    install_script = ks_dir / "scripts" / "KlipperScreen-install.sh"
                    print("\n" + "=" * 60)
                    print("Running install script...")
                    print("=" * 60 + "\n")

                    exit_code = self._run_shell_interactive(f"bash {install_script}")

                    # Check if service file was created
                    service_file = Path("/etc/systemd/system/KlipperScreen.service")
                    if not service_file.exists():
                        # Try lowercase
                        service_file = Path("/etc/systemd/system/klipperscreen.service")

                    if exit_code == 0 and service_file.exists():
                        # Ensure service is enabled and started
                        print("\n" + "=" * 60)
                        print("Enabling and starting KlipperScreen service...")
                        print("=" * 60 + "\n")

                        svc = "KlipperScreen" if "KlipperScreen" in str(service_file) else "klipperscreen"
                        self._run_shell_interactive("sudo systemctl daemon-reload")
                        self._run_systemctl("enable", svc)
                        self._run_systemctl("start", svc)

                        if update_mgr:
                            self._ensure_moonraker_update_manager_entry("KlipperScreen", update_mgr)
                        self.ui.msgbox(
                            "KlipperScreen installed successfully!\n\n"
                            "Service has been enabled and started.",
                            title="Installation Complete",
                        )
                    else:
                        # Installation failed or service not created
                        error_msg = f"Exit code: {exit_code}\n\n"
                        if not service_file.exists():
                            error_msg += "Service file was NOT created.\n"
                            error_msg += "The install script may have failed.\n\n"
                            error_msg += "Check terminal output above for errors.\n"
                            error_msg += "Common issues:\n"
                            error_msg += "- Missing dependencies\n"
                            error_msg += "- Permission denied\n"
                            error_msg += "- Python version too old"
                        self.ui.msgbox(
                            f"Installation failed!\n\n{error_msg}",
                            title="Installation Failed",
                            height=18,
                            width=80,
                        )
                else:
                    # UPDATE
                    confirm = self.ui.yesno(
                        "Update KlipperScreen?\n\n"
                        "This will stop the service, pull updates,\n"
                        "install requirements, and restart.",
                        title="Update KlipperScreen",
                        default_no=False,
                    )
                    if not confirm:
                        continue

                    print("\n" + "=" * 60)
                    print(f"Stopping {svc_name}...")
                    print("=" * 60 + "\n")
                    self._run_systemctl("stop", svc_name)

                    print("\n" + "=" * 60)
                    print("Pulling latest changes...")
                    print("=" * 60 + "\n")
                    exit_code = self._run_shell_interactive(f"cd {ks_dir} && git pull")

                    if exit_code != 0:
                        self._run_systemctl("start", svc_name)
                        self.ui.msgbox("Update failed. Service restarted.", title="Update Failed")
                        continue

                    # Check if service exists - if not, run install script
                    service_file = Path("/etc/systemd/system/KlipperScreen.service")
                    if not service_file.exists():
                        print("\n" + "=" * 60)
                        print("Service not found - running install script...")
                        print("=" * 60 + "\n")
                        install_script = ks_dir / "scripts" / "KlipperScreen-install.sh"
                        self._run_shell_interactive(f"bash {install_script}")
                        self._run_shell_interactive("sudo systemctl daemon-reload")
                    else:
                        # Just update requirements
                        ks_env = Path.home() / ".KlipperScreen-env"
                        ks_req = ks_dir / "scripts" / "KlipperScreen-requirements.txt"
                        if ks_env.exists() and ks_req.exists():
                            print("\n" + "=" * 60)
                            print("Installing requirements...")
                            print("=" * 60 + "\n")
                            self._run_shell_interactive(f"{ks_env}/bin/pip install -r {ks_req}")

                    print("\n" + "=" * 60)
                    print(f"Starting {svc_name}...")
                    print("=" * 60 + "\n")
                    self._run_systemctl("enable", svc_name)
                    self._run_systemctl("start", svc_name)

                    self.ui.msgbox("KlipperScreen updated!", title="Update Complete")
                continue

            # Handle "2" - Configure Moonraker connection (only when installed)
            elif choice == "2" and installed:
                new_host = self.ui.inputbox(
                    "Enter Moonraker host address:",
                    title="Moonraker Host",
                    default=host,
                )
                if new_host is None:
                    continue
                new_port_str = self.ui.inputbox(
                    "Enter Moonraker port:",
                    title="Moonraker Port",
                    default=str(port),
                )
                if new_port_str is None:
                    continue
                try:
                    new_port = int(new_port_str)
                except ValueError:
                    self.ui.msgbox("Invalid port number.", title="Error")
                    continue

                self.state.set("display.klipperscreen.moonraker_host", new_host)
                self.state.set("display.klipperscreen.moonraker_port", new_port)
                self.state.save()

                ok, msg = self._write_klipperscreen_conf(new_host, new_port)
                if ok:
                    # Restart service for changes to take effect
                    restart = self.ui.yesno(
                        f"Configuration saved!\n\nHost: {new_host}\nPort: {new_port}\n\n"
                        "Restart KlipperScreen now?",
                        title="Configuration Saved",
                        default_no=False,
                    )
                    if restart:
                        self._run_systemctl("restart", "KlipperScreen")
                        self.ui.msgbox("KlipperScreen restarted!", title="Done")
                else:
                    self.ui.msgbox(f"Failed to write config:\n\n{msg}", title="Error")
                continue

            # Handle "3" - Add to update_manager (only when installed)
            elif choice == "3" and installed:
                if not update_mgr:
                    self.ui.msgbox("No update_manager template found.", title="Error")
                    continue
                ok = self._ensure_moonraker_update_manager_entry("KlipperScreen", update_mgr)
                if ok:
                    self.ui.msgbox(
                        "Added to Moonraker update_manager!\n\n"
                        "KlipperScreen will appear in your update list.",
                        title="Success",
                    )
                else:
                    self.ui.msgbox("Failed to update moonraker.conf.", title="Error")
                continue

            # Handle "4" - Remove (only when installed)
            elif choice == "4" and installed:
                confirm = self.ui.yesno(
                    "Remove KlipperScreen?\n\n"
                    "This will stop the service and remove all files.\n"
                    "This cannot be undone!",
                    title="Remove KlipperScreen",
                    default_no=True,
                )
                if not confirm:
                    continue

                import shutil

                print("\n" + "=" * 60)
                print(f"Stopping {svc_name}...")
                print("=" * 60 + "\n")
                self._run_systemctl("stop", svc_name)
                self._run_systemctl("disable", svc_name)

                print("\n" + "=" * 60)
                print(f"Removing {ks_dir}...")
                print("=" * 60 + "\n")
                try:
                    if ks_dir.exists():
                        shutil.rmtree(ks_dir)
                        print("Directory removed.")
                except Exception as e:
                    self.ui.msgbox(f"Failed to remove directory:\n\n{e}", title="Error")
                    continue

                ks_env = Path.home() / ".KlipperScreen-env"
                try:
                    if ks_env.exists():
                        shutil.rmtree(ks_env)
                        print("Environment removed.")
                except Exception:
                    pass

                remove_service = self.ui.yesno(
                    "Also remove the systemd service file?",
                    title="Remove Service File",
                    default_no=True,
                )
                if remove_service:
                    self._run_shell_interactive(f"sudo rm -f /etc/systemd/system/{svc_name}.service")
                    self._run_shell_interactive("sudo systemctl daemon-reload")

                self.ui.msgbox("KlipperScreen removed!", title="Removal Complete")
                continue

    def _advanced_setup(self) -> None:
        """Configure advanced features (generator-backed)."""
        while True:
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

            # Note: Multi-pin groups removed from Advanced menu.
            # They are managed through Fans > Additional Fans when creating multi-pin fans.
            choice = self.ui.menu(
                "Advanced Configuration\n\n"
                "Optional Klipper features.\n\n"
                "Only items that are already supported by the generator are exposed here.",
                [
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
            if choice == "FM":
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
        # If the user is already defining multi-pin fans via Fans -> Additional Fans,
        # those groups are derived from that flow and should not be edited here.
        additional_fans = self.state.get("fans.additional_fans", [])
        if isinstance(additional_fans, list) and any(
            isinstance(f, dict) and f.get("pin_type") == "multi_pin"
            for f in additional_fans
        ):
            self.ui.msgbox(
                "Multi-pin fan groups are managed via:\n\n"
                "Hardware Setup -> Fans -> Additional Fans\n\n"
                "Edit them there to avoid duplicate/conflicting [multi_pin] definitions.",
                title="Multi-pin groups",
                height=14,
                width=90,
            )
            return

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

    def _configure_arc_support(self) -> None:
        """
        Configure G2/G3 arc support ([gcode_arcs]).

        This is generally safe and improves compatibility with slicers that emit arcs.
        """
        enabled = self.ui.yesno(
            "Enable Arc Support (G2/G3)?\n\n"
            "This adds the [gcode_arcs] section.\n"
            "Most users should leave this ON.\n\n"
            "Note: Some slicers require this for arc moves (G2/G3).",
            title="Arc Support",
            default_no=not bool(self.state.get("tuning.arc_support.enabled", True)),
            height=16,
            width=80,
        )
        if enabled is None:
            return

        if not enabled:
            self.state.set("tuning.arc_support.enabled", False)
            self.state.save()
            self.ui.msgbox("Arc support disabled.", title="Saved")
            return

        # Resolution is the max deviation for arc segmentation (mm).
        # Klipper defaults are commonly 0.1.
        resolution = self.ui.inputbox(
            "Arc resolution (mm):\n\n"
            "Lower = smoother arcs but more segments (more gcode processing).\n"
            "Typical: 0.1\n",
            default=str(self.state.get("tuning.arc_support.resolution", 0.1)),
            title="Arc Support - Resolution",
            height=16,
            width=80,
        )
        if resolution is None:
            return

        try:
            res_val = float(str(resolution).strip())
            if res_val <= 0:
                raise ValueError("resolution must be > 0")
        except Exception:
            self.ui.msgbox("Invalid resolution. Please enter a number > 0 (e.g. 0.1).", title="Error")
            return

        self.state.set("tuning.arc_support.enabled", True)
        self.state.set("tuning.arc_support.resolution", res_val)
        self.state.save()

        self.ui.msgbox(
            f"Arc support saved!\n\nresolution = {res_val}",
            title="Configuration Saved",
        )

    def _configure_exclude_object(self) -> None:
        """Configure Exclude Object ([exclude_object]) support."""
        enabled = self.ui.yesno(
            "Enable Exclude Object?\n\n"
            "This adds the [exclude_object] section.\n"
            "It allows cancelling individual objects mid-print (if your slicer sends object tags).\n\n"
            "Recommended: ON",
            title="Exclude Object",
            default_no=not bool(self.state.get("tuning.exclude_object.enabled", True)),
            height=16,
            width=80,
        )
        if enabled is None:
            return

        self.state.set("tuning.exclude_object.enabled", bool(enabled))
        self.state.save()

        self.ui.msgbox(
            "Exclude Object enabled." if enabled else "Exclude Object disabled.",
            title="Saved",
        )

    def _configure_tmc_autotune(self) -> None:
        """
        Configure klipper_tmc_autotune (optional third-party plugin).

        Simplified flow with voltage groups:
        - High voltage group: Core motors (X, Y, X1, Y1 for AWD)
        - Low voltage group: Z motors + extruder

        Motor selection is hierarchical (vendor -> motor) with no manual input.
        """
        import re
        from pathlib import Path as _Path

        def _tmc_autotune_install_status() -> tuple[bool, list[str], str]:
            """
            Detect whether klipper_tmc_autotune is installed and COMPLETE.

            The upstream installer links 3 files into Klipper:
              - autotune_tmc.py
              - motor_constants.py
              - motor_database.cfg

            Returns: (is_complete, missing_files, target_dir)
            """
            try:
                base = _Path.home() / "klipper" / "klippy"
                target = base / "plugins" if (base / "plugins").exists() else (base / "extras")

                required = {
                    "autotune_tmc.py": target / "autotune_tmc.py",
                    "motor_constants.py": target / "motor_constants.py",
                    "motor_database.cfg": target / "motor_database.cfg",
                }
                missing = [name for name, p in required.items() if not p.exists()]
                return (len(missing) == 0), missing, str(target)
            except Exception:
                return False, ["autotune_tmc.py", "motor_constants.py", "motor_database.cfg"], str(Path.home() / "klipper" / "klippy" / "extras")

        def _find_motor_db() -> _Path | None:
            """Find the motor database file."""
            candidates = [
                _Path.home() / "klipper_tmc_autotune" / "motor_database.cfg",
                _Path.home() / "klipper" / "klippy" / "plugins" / "motor_database.cfg",
                _Path.home() / "klipper" / "klippy" / "extras" / "motor_database.cfg",
            ]
            for p in candidates:
                if p.exists():
                    return p
            return None

        def _parse_motor_ids(cfg_text: str) -> list[str]:
            """Parse motor IDs from motor_database.cfg."""
            out: list[str] = []
            for line in cfg_text.splitlines():
                line = line.strip()
                m = re.match(r"^\[motor_constants\s+([^\]]+)\]\s*$", line)
                if m:
                    out.append(m.group(1).strip())
            return sorted(set([x for x in out if x]))

        def _parse_motor_vendors(motor_ids: list[str]) -> dict[str, list[str]]:
            """
            Extract vendor prefixes from motor IDs and group motors by vendor.

            Motor IDs typically follow the pattern: vendor-model (e.g., ldo-42sth48-2004mah)
            Returns: dict mapping vendor name to list of motor IDs
            """
            vendors: dict[str, list[str]] = {}
            for motor_id in motor_ids:
                # Extract vendor from first segment before hyphen
                parts = motor_id.split("-", 1)
                if len(parts) >= 1:
                    vendor = parts[0].lower()
                    # Normalize common vendor names for display
                    vendor_display = vendor.upper() if len(vendor) <= 4 else vendor.title()
                    if vendor_display not in vendors:
                        vendors[vendor_display] = []
                    vendors[vendor_display].append(motor_id)
            return vendors

        def _pick_motor_hierarchical(purpose: str, motor_ids: list[str], default_value: str = "") -> str | None:
            """
            Pick a motor using hierarchical vendor -> motor selection.
            No manual input allowed - only menu selection.

            Returns:
              - string (motor ID) on success
              - empty string if user chooses to skip
              - None if user cancels
            """
            if not motor_ids:
                self.ui.msgbox(
                    "Motor database not found.\n\n"
                    "Install the klipper_tmc_autotune plugin first to access the motor database.",
                    title="No Motor Database",
                    height=12,
                    width=80,
                )
                return None

            vendors = _parse_motor_vendors(motor_ids)
            if not vendors:
                self.ui.msgbox(
                    "Could not parse vendors from motor database.",
                    title="Parse Error",
                    height=10,
                    width=60,
                )
                return None

            # Determine default vendor from existing value
            default_vendor = ""
            if default_value:
                parts = default_value.split("-", 1)
                if parts:
                    dv = parts[0].lower()
                    default_vendor = dv.upper() if len(dv) <= 4 else dv.title()

            while True:
                # Step 1: Select vendor (using menu for reliable selection)
                vendor_items: list[tuple[str, str]] = []
                for vendor in sorted(vendors.keys()):
                    count = len(vendors[vendor])
                    vendor_items.append((vendor, f"{vendor} ({count} motors)"))

                # Add skip option
                vendor_items.append(("__SKIP__", "Skip (no motor for this group)"))

                selected_vendor = self.ui.menu(
                    f"Select motor vendor for {purpose}:",
                    vendor_items,
                    title=f"TMC Autotune - {purpose} - Vendor",
                    height=min(len(vendor_items) + 12, 30),
                    width=80,
                    menu_height=min(len(vendor_items), 18),
                )
                if selected_vendor is None:
                    return None
                if selected_vendor == "__SKIP__":
                    return ""

                # Step 2: Select motor from vendor (using menu for reliable selection)
                vendor_motors = vendors.get(selected_vendor, [])
                if not vendor_motors:
                    continue

                motor_items: list[tuple[str, str]] = []
                for motor in sorted(vendor_motors):
                    # Show the full motor ID
                    motor_items.append((motor, motor))

                motor_items.append(("__BACK__", "← Back to vendor selection"))

                selected_motor = self.ui.menu(
                    f"Select motor for {purpose}:\n\nVendor: {selected_vendor}",
                    motor_items,
                    title=f"TMC Autotune - {purpose} - Motor",
                    height=min(len(motor_items) + 12, 35),
                    width=100,
                    menu_height=min(len(motor_items), 25),
                )
                if selected_motor is None:
                    return None
                if selected_motor == "__BACK__":
                    continue

                return selected_motor

        # === Plugin install check ===
        plugin_installed, missing_files, target_dir = _tmc_autotune_install_status()

        if (not plugin_installed) and missing_files and ("autotune_tmc.py" not in missing_files):
            # Partial install: module exists but DB/constants are missing
            if self.ui.yesno(
                "TMC Autotune plugin appears PARTIALLY installed.\n\n"
                f"Target: {target_dir}\n"
                f"Missing: {', '.join(missing_files)}\n\n"
                "Repair by re-linking the plugin files now?",
                title="TMC Autotune - Repair",
                default_no=False,
                height=16,
                width=88,
            ):
                plugin_installed = False

        if not plugin_installed:
            if self.ui.yesno(
                "klipper_tmc_autotune plugin not detected.\n\n"
                "Would you like to install/update it now?\n\n"
                "This will:\n"
                "- clone/pull the plugin repo into ~/klipper_tmc_autotune\n"
                "- link plugin files into ~/klipper/klippy/extras/ (or plugins/)\n"
                "- optionally restart the Klipper service\n\n"
                "Note: This is system-changing and may prompt for sudo.",
                title="TMC Autotune - Install Plugin",
                default_no=False,
                height=20,
                width=88,
            ):
                if not (Path.home() / "klipper" / "klippy" / "extras").exists():
                    self.ui.msgbox(
                        "Klipper source tree not found at:\n\n"
                        "~/klipper/klippy/extras\n\n"
                        "Install Klipper first (Klipper Setup → Manage Components → install klipper),\n"
                        "then retry this install.",
                        title="Cannot Install",
                        height=14,
                        width=80,
                    )
                else:
                    restart = self.ui.yesno(
                        "Restart Klipper after installing the plugin?\n\n"
                        "Recommended: Yes (required for Klipper to load new extras).",
                        title="Restart Klipper",
                        default_no=False,
                        height=12,
                        width=70,
                    )
                    if restart is None:
                        restart = True

                    script = r"""
set -euo pipefail
REPO_URL="https://github.com/andrewmcgr/klipper_tmc_autotune.git"
PLUGIN_DIR="$HOME/klipper_tmc_autotune"
KLIPPER_BASE="$HOME/klipper/klippy"
if [ -d "$KLIPPER_BASE/plugins" ]; then
  KLIPPER_TARGET="$KLIPPER_BASE/plugins"
else
  KLIPPER_TARGET="$KLIPPER_BASE/extras"
fi

echo "== klipper_tmc_autotune install/update =="
echo "Repo: $REPO_URL"
echo "Plugin dir: $PLUGIN_DIR"
echo "Klipper target dir: $KLIPPER_TARGET"
echo ""

if [ ! -d "$KLIPPER_TARGET" ]; then
  echo "ERROR: Klipper target directory not found: $KLIPPER_TARGET"
  exit 1
fi

if [ -d "$PLUGIN_DIR/.git" ]; then
  echo "Updating existing repo..."
  git -C "$PLUGIN_DIR" fetch --prune --tags
  git -C "$PLUGIN_DIR" pull --ff-only
else
  echo "Cloning repo..."
  rm -rf "$PLUGIN_DIR"
  git clone "$REPO_URL" "$PLUGIN_DIR"
fi

SRC="$(find "$PLUGIN_DIR" -maxdepth 2 -name 'autotune_tmc.py' | head -n 1 || true)"
if [ -z "$SRC" ]; then
  echo "ERROR: Could not find autotune_tmc.py in $PLUGIN_DIR"
  exit 1
fi

echo "Linking plugin files into Klipper..."
ln -srfn "$PLUGIN_DIR/autotune_tmc.py" "$KLIPPER_TARGET/autotune_tmc.py"
ln -srfn "$PLUGIN_DIR/motor_constants.py" "$KLIPPER_TARGET/motor_constants.py"
ln -srfn "$PLUGIN_DIR/motor_database.cfg" "$KLIPPER_TARGET/motor_database.cfg"
echo "Linked."
"""
                    if restart:
                        script += r"""
echo ""
echo "Restarting klipper service..."
sudo systemctl restart klipper
echo "Restarted."
"""
                    script += r"""
echo ""
echo "Done. Press Enter to return to wizard."
read -r _
"""
                    rc = self._run_tty_command(["bash", "-lc", script])
                    plugin_installed, missing_files, target_dir = _tmc_autotune_install_status()
                    if rc == 0 and plugin_installed:
                        self.ui.msgbox(
                            "Plugin installed and detected!\n\n"
                            "You can now safely enable 'Emit active config'.",
                            title="Installed",
                            height=12,
                            width=70,
                        )
                    elif rc != 0:
                        self.ui.msgbox(
                            f"Install/update command failed (exit code {rc}).\n\n"
                            "Check the console output for details.",
                            title="Install Failed",
                            height=12,
                            width=70,
                        )
                    else:
                        self.ui.msgbox(
                            "Install/update finished, but plugin still not detected.\n\n"
                            f"Target: {target_dir}\n"
                            f"Missing: {', '.join(missing_files) if missing_files else 'unknown'}\n\n"
                            "Check the console output for details.",
                            title="Not Detected",
                            height=14,
                            width=80,
                        )

        # === Enable/Disable ===
        enabled = self.ui.yesno(
            "Enable TMC Autotune config generation?\n\n"
            "This is for the optional klipper_tmc_autotune plugin.\n"
            "If you don't have the plugin installed, generating an active config section\n"
            "would break Klipper.\n\n"
            "Recommended:\n"
            "- Enable this wizard section (to store settings)\n"
            "- Keep 'Emit active config' OFF until the plugin is installed",
            title="TMC Autotune",
            default_no=not bool(self.state.get("tuning.tmc_autotune.enabled", False)),
            height=18,
            width=88,
        )
        if enabled is None:
            return

        if not enabled:
            self.state.set("tuning.tmc_autotune.enabled", False)
            self.state.save()
            self.ui.msgbox("TMC Autotune disabled.", title="Saved")
            return

        # === Emit config? ===
        emit_current = self.state.get("tuning.tmc_autotune.emit_config", None)
        emit_default_yes = plugin_installed if emit_current is None else bool(emit_current)
        emit = self.ui.yesno(
            "Emit ACTIVE [autotune_tmc] section into the generated config?\n\n"
            "Only enable this if you have installed klipper_tmc_autotune.\n"
            "Otherwise Klipper will fail to start with an unknown section error.\n\n"
            "If unsure, choose NO (safe; emits a commented example).",
            title="TMC Autotune - Emit Config",
            default_no=not bool(emit_default_yes),
            height=16,
            width=88,
        )
        if emit is None:
            return

        # === Load motor database ===
        motor_ids: list[str] = []
        try:
            db_path = _find_motor_db()
            if db_path is not None:
                motor_ids = _parse_motor_ids(db_path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            motor_ids = []

        if not motor_ids:
            self.ui.msgbox(
                "Motor database not found or empty.\n\n"
                "Please install the klipper_tmc_autotune plugin first.\n"
                "The motor database is required for motor selection.",
                title="No Motor Database",
                height=14,
                width=80,
            )
            return

        # === Determine stepper groups based on kinematics ===
        awd_enabled = bool(self.state.get("printer.awd_enabled", False))
        z_count = int(self.state.get("stepper_z.z_motor_count", 1) or 1)
        kinematics = self.state.get("printer.kinematics", "corexy")

        # High voltage group: Core motors (X/Y, and X1/Y1 for AWD)
        high_voltage_steppers = ["stepper_x", "stepper_y"]
        if awd_enabled:
            high_voltage_steppers.extend(["stepper_x1", "stepper_y1"])

        # Low voltage group: Z motors + extruder
        low_voltage_z_steppers = ["stepper_z"]
        if z_count >= 2:
            low_voltage_z_steppers.append("stepper_z1")
        if z_count >= 3:
            low_voltage_z_steppers.append("stepper_z2")
        if z_count >= 4:
            low_voltage_z_steppers.append("stepper_z3")

        # Get existing values for defaults
        existing_high = self.state.get("tuning.tmc_autotune.high_voltage_group", {}) or {}
        existing_low = self.state.get("tuning.tmc_autotune.low_voltage_group", {}) or {}

        # Legacy fallback
        legacy_motor_x = str(self.state.get("tuning.tmc_autotune.motor_x", "") or "")
        legacy_motor_z = str(self.state.get("tuning.tmc_autotune.motor_z", "") or "")
        legacy_motor_e = str(self.state.get("tuning.tmc_autotune.motor_extruder", "") or "")

        # === Show driver info (read-only, from stepper config) ===
        x_driver = self.state.get("stepper_x.driver_type", "TMC2209")
        z_driver = self.state.get("stepper_z.driver_type", "TMC2209")
        e_driver = self.state.get("extruder.driver_type", "TMC2209")

        # === Configure High Voltage Group (Core motors) ===
        high_voltage_label = "Core Motors (X/Y" + (", X1/Y1" if awd_enabled else "") + ")"

        self.ui.msgbox(
            f"Configure HIGH VOLTAGE group:\n\n"
            f"Steppers: {', '.join(high_voltage_steppers)}\n"
            f"Driver (from stepper config): {x_driver}\n\n"
            "These motors typically share the same voltage and motor type\n"
            "in CoreXY/CoreXZ configurations.",
            title="TMC Autotune - High Voltage Group",
            height=16,
            width=80,
        )

        # High voltage selection
        current_high_voltage = existing_high.get("voltage", 48)
        high_voltage = self.ui.radiolist(
            f"Voltage for {high_voltage_label}:",
            [
                ("24", "24V", current_high_voltage == 24),
                ("48", "48V (typical for high-performance)", current_high_voltage == 48),
            ],
            title="TMC Autotune - High Voltage Group",
            height=14,
            width=70,
            list_height=4,
        )
        if high_voltage is None:
            return

        # High voltage motor selection (hierarchical)
        default_high_motor = existing_high.get("motor", legacy_motor_x) or ""
        high_motor = _pick_motor_hierarchical(
            high_voltage_label,
            motor_ids,
            default_high_motor
        )
        if high_motor is None:
            return

        # Core motors tuning goal
        current_core_goal = existing_high.get("tuning_goal", "performance")
        core_goal = self.ui.menu(
            f"Tuning goal for {high_voltage_label}:\n\n"
            "Core motors typically benefit from performance or autoswitch.",
            [
                ("auto", "Auto (plugin decides)"),
                ("silent", "Prioritize silence"),
                ("performance", "Prioritize performance (recommended)"),
                ("autoswitch", "Auto-switch modes"),
            ],
            title="TMC Autotune - Core Motors Goal",
            height=18,
            width=80,
            menu_height=6,
        )
        if core_goal is None:
            return

        # === Configure Z Motors ===
        self.ui.msgbox(
            f"Configure Z MOTORS:\n\n"
            f"Steppers: {', '.join(low_voltage_z_steppers)}\n"
            f"Driver (from stepper config): {z_driver}\n\n"
            "Z motors typically run on lower voltage and benefit from silent tuning.",
            title="TMC Autotune - Z Motors",
            height=16,
            width=80,
        )

        # Z voltage selection
        current_z_voltage = existing_low.get("voltage", 24)
        z_voltage = self.ui.radiolist(
            f"Voltage for Z motors ({', '.join(low_voltage_z_steppers)}):",
            [
                ("24", "24V (typical)", current_z_voltage == 24),
                ("48", "48V", current_z_voltage == 48),
            ],
            title="TMC Autotune - Z Motors Voltage",
            height=14,
            width=70,
            list_height=4,
        )
        if z_voltage is None:
            return

        # Z motor selection
        default_z_motor = existing_low.get("z_motor", legacy_motor_z) or ""
        z_motor = _pick_motor_hierarchical(
            f"Z Motors ({', '.join(low_voltage_z_steppers)})",
            motor_ids,
            default_z_motor
        )
        if z_motor is None:
            return

        # Z motors tuning goal
        current_z_goal = existing_low.get("z_tuning_goal", "silent")
        z_goal = self.ui.menu(
            f"Tuning goal for Z motors:\n\n"
            "Z motors move slowly - silent mode is often preferred.",
            [
                ("auto", "Auto (plugin decides)"),
                ("silent", "Prioritize silence (recommended)"),
                ("performance", "Prioritize performance"),
                ("autoswitch", "Auto-switch modes"),
            ],
            title="TMC Autotune - Z Motors Goal",
            height=18,
            width=80,
            menu_height=6,
        )
        if z_goal is None:
            return

        # === Configure Extruder ===
        self.ui.msgbox(
            f"Configure EXTRUDER:\n\n"
            f"Driver (from stepper config): {e_driver}\n\n"
            "Extruder may have different tuning needs than Z motors.",
            title="TMC Autotune - Extruder",
            height=14,
            width=80,
        )

        # Extruder voltage selection
        current_e_voltage = existing_low.get("extruder_voltage", 24)
        e_voltage = self.ui.radiolist(
            "Voltage for Extruder:",
            [
                ("24", "24V (typical)", current_e_voltage == 24),
                ("48", "48V", current_e_voltage == 48),
            ],
            title="TMC Autotune - Extruder Voltage",
            height=14,
            width=70,
            list_height=4,
        )
        if e_voltage is None:
            return

        # Extruder motor selection
        default_e_motor = existing_low.get("extruder_motor", legacy_motor_e) or ""
        extruder_motor = _pick_motor_hierarchical(
            "Extruder",
            motor_ids,
            default_e_motor
        )
        if extruder_motor is None:
            return

        # Extruder tuning goal
        current_e_goal = existing_low.get("extruder_tuning_goal", "auto")
        e_goal = self.ui.menu(
            "Tuning goal for Extruder:\n\n"
            "Extruder tuning depends on your setup and preferences.",
            [
                ("auto", "Auto (plugin decides)"),
                ("silent", "Prioritize silence"),
                ("performance", "Prioritize performance"),
                ("autoswitch", "Auto-switch modes"),
            ],
            title="TMC Autotune - Extruder Goal",
            height=18,
            width=80,
            menu_height=6,
        )
        if e_goal is None:
            return

        # === Build steppers array for generator compatibility ===
        steppers_cfg: list[dict] = []

        # Core steppers (high voltage)
        for stepper in high_voltage_steppers:
            steppers_cfg.append({
                "stepper": stepper,
                "motor": high_motor,
                "voltage": int(high_voltage),
                "tuning_goal": core_goal,
            })

        # Z steppers
        for stepper in low_voltage_z_steppers:
            steppers_cfg.append({
                "stepper": stepper,
                "motor": z_motor,
                "voltage": int(z_voltage),
                "tuning_goal": z_goal,
            })

        # Extruder
        steppers_cfg.append({
            "stepper": "extruder",
            "motor": extruder_motor,
            "voltage": int(e_voltage),
            "tuning_goal": e_goal,
        })

        # === Save state ===
        self.state.set("tuning.tmc_autotune.enabled", True)
        self.state.set("tuning.tmc_autotune.emit_config", bool(emit))

        # Save group settings for UI restoration
        self.state.set("tuning.tmc_autotune.high_voltage_group", {
            "voltage": int(high_voltage),
            "motor": high_motor,
            "tuning_goal": core_goal,
            "steppers": high_voltage_steppers,
        })
        self.state.set("tuning.tmc_autotune.low_voltage_group", {
            "voltage": int(z_voltage),
            "z_motor": z_motor,
            "z_tuning_goal": z_goal,
            "extruder_voltage": int(e_voltage),
            "extruder_motor": extruder_motor,
            "extruder_tuning_goal": e_goal,
        })

        # Save steppers array for generator compatibility
        self.state.set("tuning.tmc_autotune.steppers", steppers_cfg)
        self.state.save()

        # === Summary ===
        summary = (
            "TMC Autotune configured!\n\n"
            f"CORE MOTORS ({high_voltage}V):\n"
            f"  Motor: {high_motor or '(none)'}\n"
            f"  Goal: {core_goal}\n"
            f"  Steppers: {', '.join(high_voltage_steppers)}\n\n"
            f"Z MOTORS ({z_voltage}V):\n"
            f"  Motor: {z_motor or '(none)'}\n"
            f"  Goal: {z_goal}\n"
            f"  Steppers: {', '.join(low_voltage_z_steppers)}\n\n"
            f"EXTRUDER ({e_voltage}V):\n"
            f"  Motor: {extruder_motor or '(none)'}\n"
            f"  Goal: {e_goal}\n\n"
            f"Emit Config: {'Yes' if emit else 'No (commented)'}"
        )
        self.ui.msgbox(summary, title="TMC Autotune - Saved", height=26, width=80)

    def _configure_input_shaper(self) -> None:
        """Configure [input_shaper] (resonance compensation)."""
        enabled = self.ui.yesno(
            "Enable Input Shaper?\n\n"
            "This adds the [input_shaper] section.\n"
            "You can set frequencies to 0 and calibrate later with SHAPER_CALIBRATE.\n\n"
            "Recommended: enable once you have (or plan to do) resonance tuning.",
            title="Input Shaper",
            default_no=not bool(self.state.get("tuning.input_shaper.enabled", False)),
            height=16,
            width=88,
        )
        if enabled is None:
            return

        if not enabled:
            self.state.set("tuning.input_shaper.enabled", False)
            self.state.save()
            self.ui.msgbox("Input shaper disabled.", title="Saved")
            return

        # Shaper types
        shaper_types = [
            ("mzv", "MZV (recommended default)"),
            ("ei", "EI"),
            ("2hump_ei", "2HUMP_EI"),
            ("3hump_ei", "3HUMP_EI"),
            ("zv", "ZV"),
            ("zvd", "ZVD"),
        ]

        shaper_x = self.ui.menu(
            "Select shaper type for X:",
            shaper_types,
            title="Input Shaper - X type",
            height=18,
            width=80,
            menu_height=8,
        )
        if shaper_x is None:
            return

        freq_x = self.ui.inputbox(
            "Shaper frequency X (Hz):\n\n"
            "Set 0 to calibrate later with SHAPER_CALIBRATE.\n"
            "Typical values are ~20-80 Hz.",
            default=str(self.state.get("tuning.input_shaper.shaper_freq_x", 0)),
            title="Input Shaper - X frequency",
            height=16,
            width=88,
        )
        if freq_x is None:
            return

        damp_x = self.ui.inputbox(
            "Damping ratio X:\n\n"
            "Typical default: 0.1",
            default=str(self.state.get("tuning.input_shaper.damping_ratio_x", 0.1)),
            title="Input Shaper - X damping",
            height=14,
            width=70,
        )
        if damp_x is None:
            return

        enable_y = self.ui.yesno(
            "Configure Y axis shaper as well?",
            title="Input Shaper - Y axis",
            default_no=False,
            height=10,
            width=60,
        )
        if enable_y is None:
            return

        shaper_y = None
        freq_y = None
        damp_y = None
        if enable_y:
            shaper_y = self.ui.menu(
                "Select shaper type for Y:",
                shaper_types,
                title="Input Shaper - Y type",
                height=18,
                width=80,
                menu_height=8,
            )
            if shaper_y is None:
                return

            freq_y = self.ui.inputbox(
                "Shaper frequency Y (Hz):\n\n"
                "Set 0 to calibrate later with SHAPER_CALIBRATE.\n"
                "Typical values are ~20-80 Hz.",
                default=str(self.state.get("tuning.input_shaper.shaper_freq_y", 0)),
                title="Input Shaper - Y frequency",
                height=16,
                width=88,
            )
            if freq_y is None:
                return

            damp_y = self.ui.inputbox(
                "Damping ratio Y:\n\n"
                "Typical default: 0.1",
                default=str(self.state.get("tuning.input_shaper.damping_ratio_y", 0.1)),
                title="Input Shaper - Y damping",
                height=14,
                width=70,
            )
            if damp_y is None:
                return

        try:
            fx = float(str(freq_x).strip())
            dx = float(str(damp_x).strip())
            if fx < 0 or dx <= 0:
                raise ValueError()
            if enable_y:
                fy = float(str(freq_y).strip()) if freq_y is not None else 0.0
                dy = float(str(damp_y).strip()) if damp_y is not None else 0.1
                if fy < 0 or dy <= 0:
                    raise ValueError()
        except Exception:
            self.ui.msgbox("Invalid number entered. Please try again.", title="Error")
            return

        self.state.set("tuning.input_shaper.enabled", True)
        self.state.set("tuning.input_shaper.shaper_type_x", shaper_x)
        self.state.set("tuning.input_shaper.shaper_freq_x", fx)
        self.state.set("tuning.input_shaper.damping_ratio_x", dx)
        self.state.set("tuning.input_shaper.enable_y", bool(enable_y))
        if enable_y:
            self.state.set("tuning.input_shaper.shaper_type_y", shaper_y)
            self.state.set("tuning.input_shaper.shaper_freq_y", fy)
            self.state.set("tuning.input_shaper.damping_ratio_y", dy)
        self.state.save()

        self.ui.msgbox("Input shaper saved!", title="Saved")

    def _configure_accelerometer(self) -> None:
        """Configure accelerometer for input shaper calibration."""
        # Check for gcode_shell_command extension (required for shaper graph commands)
        def _gcode_shell_command_install_status() -> tuple[bool, str]:
            """Check if gcode_shell_command extension is installed."""
            try:
                base = Path.home() / "klipper" / "klippy"
                target = base / "plugins" if (base / "plugins").exists() else (base / "extras")
                extension_file = target / "gcode_shell_command.py"
                return extension_file.exists(), str(target)
            except Exception:
                return False, str(Path.home() / "klipper" / "klippy" / "extras")

        extension_installed, target_dir = _gcode_shell_command_install_status()

        if not extension_installed:
            if self.ui.yesno(
                "gcode_shell_command extension not detected.\n\n"
                "This extension is required for input shaper graph generation.\n\n"
                "Would you like to install it now?\n\n"
                "This will:\n"
                "- download gcode_shell_command.py to ~/klipper/klippy/extras/\n"
                "- optionally restart the Klipper service\n\n"
                "Note: This is system-changing and may prompt for sudo.",
                title="gcode_shell_command - Install Extension",
                default_no=False,
                height=18,
                width=88,
            ):
                if not (Path.home() / "klipper" / "klippy" / "extras").exists():
                    self.ui.msgbox(
                        "Klipper source tree not found at:\n\n"
                        "~/klipper/klippy/extras\n\n"
                        "Install Klipper first (Klipper Setup → Manage Components → install klipper),\n"
                        "then retry this install.",
                        title="Cannot Install",
                        height=14,
                        width=80,
                    )
                else:
                    restart = self.ui.yesno(
                        "Restart Klipper after installing the extension?\n\n"
                        "Recommended: Yes (required for Klipper to load new extras).",
                        title="Restart Klipper",
                        default_no=False,
                        height=12,
                        width=70,
                    )
                    if restart is None:
                        restart = True

                    script = r"""
set -euo pipefail
KLIPPER_BASE="$HOME/klipper/klippy"
if [ -d "$KLIPPER_BASE/plugins" ]; then
  KLIPPER_TARGET="$KLIPPER_BASE/plugins"
else
  KLIPPER_TARGET="$KLIPPER_BASE/extras"
fi

echo "== gcode_shell_command extension install =="
echo "Target dir: $KLIPPER_TARGET"
echo ""

if [ ! -d "$KLIPPER_TARGET" ]; then
  echo "ERROR: Klipper target directory not found: $KLIPPER_TARGET"
  exit 1
fi

# Download from KIAUH repository (same method KIAUH uses)
EXTENSION_URL="https://raw.githubusercontent.com/th33xitus/kiauh/master/resources/gcode_shell_command.py"

echo "Downloading gcode_shell_command.py from GitHub..."
echo "URL: $EXTENSION_URL"
echo ""

DOWNLOAD_SUCCESS=0
if command -v wget >/dev/null 2>&1; then
  echo "Using wget (this may take a few seconds)..."
  # Use timeout wrapper if available, otherwise rely on wget's own timeout
  if command -v timeout >/dev/null 2>&1; then
    if timeout 45 wget --timeout=30 --tries=2 -q -O "$KLIPPER_TARGET/gcode_shell_command.py" "$EXTENSION_URL" 2>&1; then
      DOWNLOAD_SUCCESS=1
    else
      WGET_EXIT=$?
      if [ $WGET_EXIT -eq 124 ]; then
        echo "Download timed out after 45 seconds"
      else
        echo "wget failed, exit code: $WGET_EXIT"
      fi
    fi
  else
    if wget --timeout=30 --tries=2 -q -O "$KLIPPER_TARGET/gcode_shell_command.py" "$EXTENSION_URL" 2>&1; then
      DOWNLOAD_SUCCESS=1
    else
      echo "wget failed, exit code: $?"
    fi
  fi
elif command -v curl >/dev/null 2>&1; then
  echo "Using curl (this may take a few seconds)..."
  # Use timeout wrapper if available
  if command -v timeout >/dev/null 2>&1; then
    if timeout 45 curl --max-time 30 --connect-timeout 10 -sSL -o "$KLIPPER_TARGET/gcode_shell_command.py" "$EXTENSION_URL" 2>&1; then
      DOWNLOAD_SUCCESS=1
    else
      CURL_EXIT=$?
      if [ $CURL_EXIT -eq 124 ]; then
        echo "Download timed out after 45 seconds"
      else
        echo "curl failed, exit code: $CURL_EXIT"
      fi
    fi
  else
    if curl --max-time 30 --connect-timeout 10 -sSL -o "$KLIPPER_TARGET/gcode_shell_command.py" "$EXTENSION_URL" 2>&1; then
      DOWNLOAD_SUCCESS=1
    else
      echo "curl failed, exit code: $?"
    fi
  fi
else
  echo "ERROR: Neither wget nor curl found. Please install one of them."
  exit 1
fi

if [ $DOWNLOAD_SUCCESS -eq 0 ]; then
  echo ""
  echo "ERROR: Download failed or timed out"
  echo "Please check your internet connection and try again."
  exit 1
fi

if [ ! -f "$KLIPPER_TARGET/gcode_shell_command.py" ] || [ ! -s "$KLIPPER_TARGET/gcode_shell_command.py" ]; then
  echo ""
  echo "ERROR: Downloaded file is missing or empty"
  exit 1
fi

FILE_SIZE=$(stat -c%s "$KLIPPER_TARGET/gcode_shell_command.py" 2>/dev/null || echo "0")
echo "Downloaded file size: $FILE_SIZE bytes"
if [ "$FILE_SIZE" -lt 100 ]; then
  echo "ERROR: File is too small, download may have failed"
  rm -f "$KLIPPER_TARGET/gcode_shell_command.py"
  exit 1
fi

echo ""
echo "Extension installed to: $KLIPPER_TARGET/gcode_shell_command.py"
"""
                    if restart:
                        script += r"""
echo ""
echo "Restarting klipper service..."
sudo systemctl restart klipper
echo "Restarted."
"""
                    script += r"""
echo ""
echo "Done. Press Enter to return to wizard."
read -r _
"""
                    rc = self._run_tty_command(["bash", "-lc", script])
                    extension_installed, target_dir = _gcode_shell_command_install_status()
                    if rc == 0 and extension_installed:
                        self.ui.msgbox(
                            "Extension installed and detected!\n\n"
                            "You can now use shaper graph commands in your macros.",
                            title="Installed",
                            height=12,
                            width=70,
                        )
                    elif rc != 0:
                        self.ui.msgbox(
                            f"Install command failed (exit code {rc}).\n\n"
                            "Check the console output for details.\n\n"
                            "You may need to manually download gcode_shell_command.py\n"
                            "from the Klipper community repositories.",
                            title="Install Failed",
                            height=14,
                            width=80,
                        )
                    else:
                        self.ui.msgbox(
                            "Install finished, but extension still not detected.\n\n"
                            f"Target: {target_dir}\n\n"
                            "Check the console output for details.",
                            title="Not Detected",
                            height=12,
                            width=80,
                        )

        # Show extension status and offer manual install option
        extension_status = "Installed" if extension_installed else "Not installed"

        # Detect available accelerometer sources
        sources = []

        # Check toolboard for accelerometer
        toolboard_id = self.state.get("mcu.toolboard.board_type", "")
        if toolboard_id:
            toolboard_data = self._load_board_data(toolboard_id, "toolboards")
            if toolboard_data and toolboard_data.get("accelerometer"):
                accel_info = toolboard_data["accelerometer"]
                accel_type = accel_info.get("type", "ADXL345")
                sources.append(("toolboard", f"Toolboard ({accel_type})"))

        # Check probe for accelerometer (Beacon, Cartographer)
        probe_type = self.state.get("probe.probe_type", "")
        if probe_type == "beacon":
            sources.append(("beacon", "Beacon (built-in accelerometer)"))
        elif probe_type == "cartographer":
            sources.append(("cartographer", "Cartographer (built-in accelerometer)"))

        # Always offer "none" option
        sources.append(("none", "None / Manual configuration"))

        if len(sources) == 1:  # Only "none"
            self.ui.msgbox(
                "No accelerometer detected!\n\n"
                "To use input shaper calibration, you need:\n"
                "• A toolboard with ADXL345/LIS2DW accelerometer, OR\n"
                "• A Beacon or Cartographer probe (with built-in accelerometer)\n\n"
                "Configure your hardware first, then return here.",
                title="Accelerometer Setup"
            )
            return

        current_source = self.state.get("tuning.accelerometer.source", "")

        # Build menu items
        menu_items = [(s[0], s[1], s[0] == current_source) for s in sources]

        # Add extension install option if not installed, or manual install option always
        if not extension_installed:
            menu_items.append(("__INSTALL__", f"Install gcode_shell_command extension ({extension_status})", False))
        else:
            menu_items.append(("__REINSTALL__", f"Reinstall gcode_shell_command extension ({extension_status})", False))

        # Add clear option if configured
        if current_source:
            menu_items.append(("__CLEAR__", "Clear/Reset accelerometer settings", False))

        choice = self.ui.radiolist(
            f"Select accelerometer source:\n\n"
            f"This configures [adxl345]/[lis2dw] and [resonance_tester] sections\n"
            f"for input shaper calibration.\n\n"
            f"Extension status: {extension_status}\n\n"
            f"After configuration, use CALIBRATE_SHAPER macro to calibrate.",
            menu_items,
            title="Accelerometer Setup",
            height=22,
            width=80,
        )
        if choice is None:
            return

        # Handle extension install/reinstall
        if choice == "__INSTALL__" or choice == "__REINSTALL__":
            # Re-run the installation logic
            if not (Path.home() / "klipper" / "klippy" / "extras").exists():
                self.ui.msgbox(
                    "Klipper source tree not found at:\n\n"
                    "~/klipper/klippy/extras\n\n"
                    "Install Klipper first (Klipper Setup → Manage Components → install klipper),\n"
                    "then retry this install.",
                    title="Cannot Install",
                    height=14,
                    width=80,
                )
                return

            restart = self.ui.yesno(
                "Restart Klipper after installing the extension?\n\n"
                "Recommended: Yes (required for Klipper to load new extras).",
                title="Restart Klipper",
                default_no=False,
                height=12,
                width=70,
            )
            if restart is None:
                restart = True

            script = r"""
set -euo pipefail
KLIPPER_BASE="$HOME/klipper/klippy"
if [ -d "$KLIPPER_BASE/plugins" ]; then
  KLIPPER_TARGET="$KLIPPER_BASE/plugins"
else
  KLIPPER_TARGET="$KLIPPER_BASE/extras"
fi

echo "== gcode_shell_command extension install =="
echo "Target dir: $KLIPPER_TARGET"
echo ""

if [ ! -d "$KLIPPER_TARGET" ]; then
  echo "ERROR: Klipper target directory not found: $KLIPPER_TARGET"
  exit 1
fi

# Download from KIAUH repository (same method KIAUH uses)
EXTENSION_URL="https://raw.githubusercontent.com/th33xitus/kiauh/master/resources/gcode_shell_command.py"

echo "Downloading gcode_shell_command.py from GitHub..."
echo "URL: $EXTENSION_URL"
echo ""

DOWNLOAD_SUCCESS=0
if command -v wget >/dev/null 2>&1; then
  echo "Using wget (this may take a few seconds)..."
  # Use timeout wrapper if available, otherwise rely on wget's own timeout
  if command -v timeout >/dev/null 2>&1; then
    if timeout 45 wget --timeout=30 --tries=2 -q -O "$KLIPPER_TARGET/gcode_shell_command.py" "$EXTENSION_URL" 2>&1; then
      DOWNLOAD_SUCCESS=1
    else
      WGET_EXIT=$?
      if [ $WGET_EXIT -eq 124 ]; then
        echo "Download timed out after 45 seconds"
      else
        echo "wget failed, exit code: $WGET_EXIT"
      fi
    fi
  else
    if wget --timeout=30 --tries=2 -q -O "$KLIPPER_TARGET/gcode_shell_command.py" "$EXTENSION_URL" 2>&1; then
      DOWNLOAD_SUCCESS=1
    else
      echo "wget failed, exit code: $?"
    fi
  fi
elif command -v curl >/dev/null 2>&1; then
  echo "Using curl (this may take a few seconds)..."
  # Use timeout wrapper if available
  if command -v timeout >/dev/null 2>&1; then
    if timeout 45 curl --max-time 30 --connect-timeout 10 -sSL -o "$KLIPPER_TARGET/gcode_shell_command.py" "$EXTENSION_URL" 2>&1; then
      DOWNLOAD_SUCCESS=1
    else
      CURL_EXIT=$?
      if [ $CURL_EXIT -eq 124 ]; then
        echo "Download timed out after 45 seconds"
      else
        echo "curl failed, exit code: $CURL_EXIT"
      fi
    fi
  else
    if curl --max-time 30 --connect-timeout 10 -sSL -o "$KLIPPER_TARGET/gcode_shell_command.py" "$EXTENSION_URL" 2>&1; then
      DOWNLOAD_SUCCESS=1
    else
      echo "curl failed, exit code: $?"
    fi
  fi
else
  echo "ERROR: Neither wget nor curl found. Please install one of them."
  exit 1
fi

if [ $DOWNLOAD_SUCCESS -eq 0 ]; then
  echo ""
  echo "ERROR: Download failed or timed out"
  echo "Please check your internet connection and try again."
  exit 1
fi

if [ ! -f "$KLIPPER_TARGET/gcode_shell_command.py" ] || [ ! -s "$KLIPPER_TARGET/gcode_shell_command.py" ]; then
  echo ""
  echo "ERROR: Downloaded file is missing or empty"
  exit 1
fi

FILE_SIZE=$(stat -c%s "$KLIPPER_TARGET/gcode_shell_command.py" 2>/dev/null || echo "0")
echo "Downloaded file size: $FILE_SIZE bytes"
if [ "$FILE_SIZE" -lt 100 ]; then
  echo "ERROR: File is too small, download may have failed"
  rm -f "$KLIPPER_TARGET/gcode_shell_command.py"
  exit 1
fi

echo ""
echo "Extension installed to: $KLIPPER_TARGET/gcode_shell_command.py"
"""
            if restart:
                script += r"""
echo ""
echo "Restarting klipper service..."
sudo systemctl restart klipper
echo "Restarted."
"""
            script += r"""
echo ""
echo "Done. Press Enter to return to wizard."
read -r _
"""
            rc = self._run_tty_command(["bash", "-lc", script])
            extension_installed, target_dir = _gcode_shell_command_install_status()
            if rc == 0 and extension_installed:
                self.ui.msgbox(
                    "Extension installed and detected!\n\n"
                    "You can now use shaper graph commands in your macros.",
                    title="Installed",
                    height=12,
                    width=70,
                )
            elif rc != 0:
                self.ui.msgbox(
                    f"Install command failed (exit code {rc}).\n\n"
                    "Check the console output for details.\n\n"
                    "You may need to manually download gcode_shell_command.py\n"
                    "from the Klipper community repositories.",
                    title="Install Failed",
                    height=14,
                    width=80,
                )
            else:
                self.ui.msgbox(
                    "Install finished, but extension still not detected.\n\n"
                    f"Target: {target_dir}\n\n"
                    "Check the console output for details.",
                    title="Not Detected",
                    height=12,
                    width=80,
                )
            return

        if choice == "__CLEAR__":
            if self.ui.yesno(
                "Clear accelerometer settings?\n\n"
                "This will reset the accelerometer configuration so you can\n"
                "set it up again (and trigger extension installation if needed).",
                title="Clear Accelerometer",
                default_no=False,
                height=12,
                width=70,
            ):
                self.state.delete("tuning.accelerometer")
                self.state.save()
                self.ui.msgbox("Accelerometer settings cleared.", title="Cleared")
            return

        if choice == "none":
            self.state.delete("tuning.accelerometer")
            self.state.save()
            self.ui.msgbox("Accelerometer disabled.", title="Saved")
            return

        # Configure based on source
        if choice == "toolboard":
            toolboard_data = self._load_board_data(toolboard_id, "toolboards")
            accel_info = toolboard_data.get("accelerometer", {})

            self.state.set("tuning.accelerometer.enabled", True)
            self.state.set("tuning.accelerometer.source", "toolboard")
            self.state.set("tuning.accelerometer.type", accel_info.get("type", "ADXL345"))
            self.state.set("tuning.accelerometer.mcu_prefix", "toolboard:")
            self.state.set("tuning.accelerometer.cs_pin", accel_info.get("cs_pin", ""))

            # SPI configuration
            if accel_info.get("spi_bus"):
                self.state.set("tuning.accelerometer.spi_bus", accel_info["spi_bus"])
            else:
                # Software SPI
                self.state.set("tuning.accelerometer.spi_software_sclk_pin",
                               accel_info.get("spi_software_sclk_pin", ""))
                self.state.set("tuning.accelerometer.spi_software_mosi_pin",
                               accel_info.get("spi_software_mosi_pin", ""))
                self.state.set("tuning.accelerometer.spi_software_miso_pin",
                               accel_info.get("spi_software_miso_pin", ""))

        elif choice == "beacon":
            self.state.set("tuning.accelerometer.enabled", True)
            self.state.set("tuning.accelerometer.source", "beacon")
            # Beacon has its own accel_chip, no adxl345 section needed

        elif choice == "cartographer":
            self.state.set("tuning.accelerometer.enabled", True)
            self.state.set("tuning.accelerometer.source", "cartographer")
            self.state.set("tuning.accelerometer.type", "ADXL345")
            self.state.set("tuning.accelerometer.mcu_prefix", "cartographer:")
            self.state.set("tuning.accelerometer.cs_pin", "PA3")
            self.state.set("tuning.accelerometer.spi_bus", "spi1")

        self.state.save()

        self.ui.msgbox(
            f"Accelerometer configured!\n\n"
            f"Source: {choice}\n\n"
            f"After generating config, use these macros:\n"
            f"• CALIBRATE_SHAPER - Full calibration\n"
            f"• COMPARE_BELTS - Belt tension check (CoreXY)\n"
            f"• SHAPER_CALIBRATION_WIZARD - Step-by-step guide\n\n"
            f"Graphs will be saved to config/plots/",
            title="Accelerometer - Saved",
            height=18,
            width=70
        )

    def _configure_macros(self) -> None:
        """
        Configure macro behavior (START_PRINT / END_PRINT).

        The generator already emits macros with defaults; this menu lets users store
        common overrides in wizard state so macros-config.cfg reflects them.
        """
        # Very small, high-signal set of options (safe defaults).
        while True:
            bed_mesh_mode = str(self.state.get("macros.bed_mesh_mode", "adaptive") or "adaptive")
            purge_style = str(self.state.get("macros.purge_style", "adaptive") or "adaptive")
            heat_soak = self.state.get("macros.heat_soak_time", 0) or 0
            wipe_count = self.state.get("macros.wipe_count", 3) or 3

            choice = self.ui.menu(
                "Macros (START_PRINT / END_PRINT)\n\n"
                "Configure macro defaults that will be written into macros-config.cfg.\n\n"
                f"Current:\n"
                f"  bed_mesh_mode: {bed_mesh_mode}\n"
                f"  purge_style:   {purge_style}\n"
                f"  heat_soak:     {heat_soak} min\n"
                f"  wipe_count:    {wipe_count}\n\n"
                "Select an item to edit:",
                [
                    ("mesh", "Bed mesh mode (adaptive/saved/none)"),
                    ("purge", "Purge style (adaptive/line/blob)"),
                    ("soak", "Heat soak time (minutes)"),
                    ("wipe", "Brush wipe count"),
                    ("B", "Back"),
                ],
                title="Macros",
                height=22,
                width=90,
                menu_height=10,
            )
            if choice is None or choice == "B":
                return

            if choice == "mesh":
                m = self.ui.menu(
                    "Bed mesh mode:",
                    [
                        ("adaptive", "Adaptive (recommended)"),
                        ("saved", "Saved (load default profile)"),
                        ("none", "None (skip meshing)"),
                    ],
                    title="Macros - Bed mesh mode",
                    height=16,
                    width=70,
                    menu_height=6,
                )
                if m is None:
                    continue
                self.state.set("macros.bed_mesh_mode", m)
                self.state.save()
                continue

            if choice == "purge":
                p = self.ui.menu(
                    "Purge style:",
                    [
                        ("adaptive", "Adaptive (macro chooses)"),
                        ("line", "Purge line"),
                        ("blob", "Blob/bucket purge"),
                    ],
                    title="Macros - Purge style",
                    height=16,
                    width=70,
                    menu_height=6,
                )
                if p is None:
                    continue
                self.state.set("macros.purge_style", p)
                self.state.save()
                continue

            if choice == "soak":
                v = self.ui.inputbox(
                    "Heat soak time (minutes):\n\n0 disables heat soak.",
                    default=str(self.state.get("macros.heat_soak_time", 0)),
                    title="Macros - Heat soak",
                    height=14,
                    width=70,
                )
                if v is None:
                    continue
                try:
                    mins = int(float(str(v).strip()))
                    if mins < 0:
                        raise ValueError()
                    self.state.set("macros.heat_soak_time", mins)
                    self.state.save()
                except Exception:
                    self.ui.msgbox("Invalid number. Please enter 0 or a positive integer.", title="Error")
                continue

            if choice == "wipe":
                v = self.ui.inputbox(
                    "Brush wipe count:\n\nTypical: 3",
                    default=str(self.state.get("macros.wipe_count", 3)),
                    title="Macros - Wipe count",
                    height=14,
                    width=70,
                )
                if v is None:
                    continue
                try:
                    wc = int(float(str(v).strip()))
                    if wc < 0:
                        raise ValueError()
                    self.state.set("macros.wipe_count", wc)
                    self.state.save()
                except Exception:
                    self.ui.msgbox("Invalid number. Please enter 0 or a positive integer.", title="Error")
                continue

    def tuning_menu(self) -> None:
        """Tuning and optimization menu."""
        while True:
            # Show accelerometer status
            accel_source = self.state.get("tuning.accelerometer.source", "")
            accel_status = {
                "toolboard": "Toolboard",
                "beacon": "Beacon",
                "cartographer": "Cartographer",
            }.get(accel_source, None)

            # Format accelerometer menu item
            if accel_status:
                accel_menu_label = self._format_menu_item("Accelerometer", accel_status)
            else:
                accel_menu_label = "Accelerometer         (For input shaper calibration)"

            choice = self.ui.menu(
                "Tuning & Optimization\n\n"
                "Configure advanced features and calibration.",
                [
                    ("3.1", "TMC Autotune         (Motor optimization)"),
                    ("3.2", "Input Shaper         (Resonance compensation)"),
                    ("3.3", accel_menu_label),
                    ("3.6", "Macros               (START_PRINT, etc.)"),
                    ("3.9", "Exclude Object       (Cancel individual objects)"),
                    ("3.10", "Arc Support         (G2/G3 commands)"),
                    ("B", "Back to Main Menu"),
                ],
                title="3. Tuning & Optimization",
            )

            if choice is None or choice == "B":
                break
            elif choice == "3.1":
                self._configure_tmc_autotune()
            elif choice == "3.2":
                self._configure_input_shaper()
            elif choice == "3.3":
                self._configure_accelerometer()
            elif choice == "3.6":
                self._configure_macros()
            elif choice == "3.10":
                self._configure_arc_support()
            elif choice == "3.9":
                self._configure_exclude_object()
            else:
                self.ui.msgbox(f"Section {choice} coming soon!", title=f"Section {choice}")

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
            # Format detailed error message with traceback
            error_type = type(e).__name__
            error_msg = str(e) if str(e) else "(no error message)"
            full_traceback = traceback.format_exc()
            tb_lines = full_traceback.splitlines()

            # Log full error to file for debugging
            log_path = self._wizard_log_path()
            try:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as f:
                    from datetime import datetime
                    ts = datetime.now().isoformat(timespec="seconds")
                    f.write(f"\n{'='*80}\n")
                    f.write(f"{ts} - Configuration Generation Error\n")
                    f.write(f"{'='*80}\n")
                    f.write(f"Error Type: {error_type}\n")
                    f.write(f"Error Message: {error_msg}\n")
                    f.write(f"\nFull Traceback:\n{full_traceback}\n")
            except Exception:
                # Logging must never break the wizard
                pass

            # Build a readable error message for dialog (show summary + traceback tail)
            error_details = f"Error Type: {error_type}\n"
            error_details += f"Error Message: {error_msg}\n\n"

            # Include the last 10 lines of traceback (most relevant)
            if len(tb_lines) > 10:
                error_details += "Traceback (most recent call last):\n"
                error_details += "\n".join(tb_lines[-10:])
            else:
                error_details += "Full Traceback:\n"
                error_details += "\n".join(tb_lines)

            error_details += f"\n\nFull error details logged to:\n{log_path}"

            self.ui.msgbox(
                f"Error generating configuration:\n\n{error_details}",
                title="Generation Failed"
            )


def main():
    """Entry point."""
    wizard = GschpooziWizard()
    sys.exit(wizard.run())


if __name__ == "__main__":
    main()

