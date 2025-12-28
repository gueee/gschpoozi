"""
fields.py - Field rendering for skeleton-driven wizard

The FieldRenderer handles displaying and collecting values for
different field types defined in skeleton.json.
"""

import glob
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .skeleton import SkeletonLoader
from .state import WizardState
from .ui import WizardUI


# Find repo root for loading templates
SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_ROOT = SCRIPT_DIR.parent.parent


class FieldRenderer:
    """Renders individual field types to UI widgets.

    Each field type maps to a specific UI widget:
    - text -> inputbox
    - int -> inputbox with validation
    - float -> inputbox with validation
    - bool -> yesno dialog
    - choice -> radiolist
    - exclusive_choice -> radiolist with group options
    - multi_select -> checklist
    - serial_select -> serial device picker
    - port_select -> board port picker
    - board_select -> board selector from templates
    """

    def __init__(
        self,
        skeleton: SkeletonLoader,
        state: WizardState,
        ui: WizardUI,
        pin_manager: Any = None
    ):
        """Initialize the field renderer.

        Args:
            skeleton: Loaded skeleton
            state: Wizard state manager
            ui: UI wrapper for dialogs
            pin_manager: Optional PinManager for port conflict detection
        """
        self.skeleton = skeleton
        self.state = state
        self.ui = ui
        self.pin_manager = pin_manager

    def _get_state_value(self, key: str) -> Any:
        """Get a value from state by dot-notation key."""
        if not key:
            return None
        return self.state.get(key)

    def _set_state_value(self, key: str, value: Any) -> None:
        """Set a value in state by dot-notation key."""
        if key:
            self.state.set(key, value)

    def render_field(self, field: Dict[str, Any]) -> Optional[Any]:
        """Render a field and return the user's input.

        Args:
            field: Field definition from skeleton

        Returns:
            The value entered by user, or None if cancelled
        """
        field_type = field.get('type', 'text')

        # Map field types to render methods
        renderers = {
            'text': self._render_text,
            'int': self._render_int,
            'float': self._render_float,
            'bool': self._render_bool,
            'choice': self._render_choice,
            'exclusive_choice': self._render_exclusive_choice,
            'multi_select': self._render_multi_select,
            'serial_select': self._render_serial_select,
            'port_select': self._render_port_select,
            'board_select': self._render_board_select,
        }

        renderer = renderers.get(field_type, self._render_text)
        return renderer(field)

    def _render_text(self, field: Dict[str, Any]) -> Optional[str]:
        """Render a text input field."""
        label = field.get('label', 'Enter value')
        state_key = field.get('state_key', '')
        default = field.get('default', '')
        current = self._get_state_value(state_key)

        if current is not None:
            default = str(current)

        help_text = field.get('help', '')
        prompt = label
        if help_text:
            prompt = f"{label}\n\n{help_text}"

        result = self.ui.inputbox(prompt, default=str(default), title=label)

        if result is not None:
            self._set_state_value(state_key, result)
            return result

        return None

    def _render_int(self, field: Dict[str, Any]) -> Optional[int]:
        """Render an integer input field with validation."""
        label = field.get('label', 'Enter number')
        state_key = field.get('state_key', '')
        default = field.get('default', 0)
        current = self._get_state_value(state_key)
        range_def = field.get('range', [])

        if current is not None:
            default = current

        help_text = field.get('help', '')
        if range_def:
            range_hint = f"Valid range: {range_def[0]} - {range_def[1]}"
            help_text = f"{range_hint}\n{help_text}" if help_text else range_hint

        prompt = label
        if help_text:
            prompt = f"{label}\n\n{help_text}"

        while True:
            result = self.ui.inputbox(prompt, default=str(default), title=label)

            if result is None:
                return None

            try:
                value = int(result)

                # Validate range
                if range_def and len(range_def) == 2:
                    if value < range_def[0] or value > range_def[1]:
                        self.ui.msgbox(
                            f"Value must be between {range_def[0]} and {range_def[1]}",
                            title="Invalid Value"
                        )
                        continue

                self._set_state_value(state_key, value)
                return value

            except ValueError:
                self.ui.msgbox("Please enter a valid integer", title="Invalid Input")
                continue

    def _render_float(self, field: Dict[str, Any]) -> Optional[float]:
        """Render a float input field with validation."""
        label = field.get('label', 'Enter number')
        state_key = field.get('state_key', '')
        default = field.get('default', 0.0)
        current = self._get_state_value(state_key)
        range_def = field.get('range', [])

        if current is not None:
            default = current

        help_text = field.get('help', '')
        if range_def:
            range_hint = f"Valid range: {range_def[0]} - {range_def[1]}"
            help_text = f"{range_hint}\n{help_text}" if help_text else range_hint

        prompt = label
        if help_text:
            prompt = f"{label}\n\n{help_text}"

        while True:
            result = self.ui.inputbox(prompt, default=str(default), title=label)

            if result is None:
                return None

            try:
                value = float(result)

                # Validate range
                if range_def and len(range_def) == 2:
                    if value < range_def[0] or value > range_def[1]:
                        self.ui.msgbox(
                            f"Value must be between {range_def[0]} and {range_def[1]}",
                            title="Invalid Value"
                        )
                        continue

                self._set_state_value(state_key, value)
                return value

            except ValueError:
                self.ui.msgbox("Please enter a valid number", title="Invalid Input")
                continue

    def _render_bool(self, field: Dict[str, Any]) -> Optional[bool]:
        """Render a yes/no field."""
        label = field.get('label', 'Enable?')
        state_key = field.get('state_key', '')
        default = field.get('default', False)
        current = self._get_state_value(state_key)

        if current is not None:
            default = bool(current)

        result = self.ui.yesno(label, default_no=not default, title=label)

        self._set_state_value(state_key, result)
        return result

    def _render_choice(self, field: Dict[str, Any]) -> Optional[str]:
        """Render a single-choice selection from inline options."""
        label = field.get('label', 'Select option')
        state_key = field.get('state_key', '')
        options = field.get('options', [])
        default = field.get('default')
        current = self._get_state_value(state_key)

        if current is not None:
            default = current

        # Build radiolist items
        state_dict = self.state.get_all()
        items: List[Tuple[str, str, bool]] = []

        for opt in options:
            # Check option-level condition
            condition = opt.get('condition')
            if condition and not self.skeleton.evaluate_condition(condition, state_dict):
                continue

            value = opt.get('value')
            opt_label = opt.get('label', str(value))
            is_selected = (value == default)
            items.append((str(value), opt_label, is_selected))

        if not items:
            self.ui.msgbox("No options available", title=label)
            return None

        result = self.ui.radiolist(label, items, title=label)

        if result is not None:
            # Convert back to original type if needed
            for opt in options:
                if str(opt.get('value')) == result:
                    self._set_state_value(state_key, opt.get('value'))
                    return opt.get('value')

        return None

    def _render_exclusive_choice(self, field: Dict[str, Any]) -> Optional[str]:
        """Render a single-choice selection from an exclusive group."""
        label = field.get('label', 'Select option')
        state_key = field.get('state_key', '')
        group_id = field.get('group', '')
        current = self._get_state_value(state_key)

        if not group_id:
            # Fall back to inline options
            return self._render_choice(field)

        # Get options from exclusive group
        state_dict = self.state.get_all()
        options = self.skeleton.get_available_options(group_id, state_dict)

        if not options:
            self.ui.msgbox(f"No options available for {label}", title=label)
            return None

        # Build radiolist items
        items: List[Tuple[str, str, bool]] = []
        for opt in options:
            value = opt.get('value')
            opt_label = opt.get('label', str(value))
            is_selected = (value == current)
            items.append((str(value), opt_label, is_selected))

        result = self.ui.radiolist(label, items, title=label)

        if result is not None:
            # Find the actual value (might not be string)
            for opt in options:
                if str(opt.get('value')) == result:
                    self._set_state_value(state_key, opt.get('value'))
                    return opt.get('value')

        return None

    def _render_multi_select(self, field: Dict[str, Any]) -> Optional[List[str]]:
        """Render a multi-select checklist."""
        label = field.get('label', 'Select options')
        state_key = field.get('state_key', '')
        options = field.get('options', [])
        current = self._get_state_value(state_key) or []

        if isinstance(current, str):
            current = [current]

        # Build checklist items
        state_dict = self.state.get_all()
        items: List[Tuple[str, str, bool]] = []

        for opt in options:
            condition = opt.get('condition')
            if condition and not self.skeleton.evaluate_condition(condition, state_dict):
                continue

            value = opt.get('value')
            opt_label = opt.get('label', str(value))
            is_selected = str(value) in [str(c) for c in current]
            items.append((str(value), opt_label, is_selected))

        if not items:
            self.ui.msgbox("No options available", title=label)
            return None

        result = self.ui.checklist(label, items, title=label)

        if result is not None:
            self._set_state_value(state_key, result)
            return result

        return None

    def _render_serial_select(self, field: Dict[str, Any]) -> Optional[str]:
        """Render a serial device selection with auto-detection."""
        label = field.get('label', 'Select serial device')
        state_key = field.get('state_key', '')
        current = self._get_state_value(state_key)
        pattern = field.get('auto_detect_pattern', 'Klipper')

        # Detect serial devices
        devices = self._detect_serial_devices(pattern)

        if not devices:
            # Offer manual entry
            result = self.ui.inputbox(
                f"{label}\n\nNo devices detected. Enter path manually:",
                default=current or "/dev/serial/by-id/",
                title=label
            )
            if result:
                self._set_state_value(state_key, result)
                return result
            return None

        # Build selection items
        items: List[Tuple[str, str, bool]] = []
        for path, display_name in devices:
            is_selected = (path == current)
            items.append((path, display_name, is_selected))

        # Add manual entry option
        items.append(("manual", "Enter manually...", False))

        result = self.ui.radiolist(label, items, title=label)

        if result == "manual":
            result = self.ui.inputbox(
                f"{label}\n\nEnter device path:",
                default=current or "/dev/serial/by-id/",
                title=label
            )

        if result and result != "manual":
            self._set_state_value(state_key, result)
            return result

        return None

    def _detect_serial_devices(self, pattern: str = None) -> List[Tuple[str, str]]:
        """Detect available serial devices.

        Args:
            pattern: Optional pattern to filter devices (e.g., 'Klipper', 'Beacon')

        Returns:
            List of (path, display_name) tuples
        """
        devices = []
        by_id_dir = "/dev/serial/by-id"

        if os.path.isdir(by_id_dir):
            for name in os.listdir(by_id_dir):
                path = os.path.join(by_id_dir, name)

                # Filter by pattern if specified
                if pattern:
                    if isinstance(pattern, dict):
                        # Pattern is probe-type specific
                        # Just include all for now
                        pass
                    elif isinstance(pattern, str):
                        if pattern.lower() not in name.lower():
                            continue

                # Format display name
                display_name = self._format_serial_name(name)
                devices.append((path, display_name))

        return devices

    def _format_serial_name(self, name: str) -> str:
        """Format a serial device name for display."""
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
                short_serial = serial[-4:] if len(serial) > 4 else serial
                return f"Klipper {mcu} (...{short_serial})"

        # Parse Beacon format
        if "Beacon" in name:
            parts = name.split("_")
            if len(parts) >= 3:
                rev = parts[2] if len(parts) > 2 else ""
                serial = parts[-1] if len(parts) > 3 else ""
                short_serial = serial[-4:] if len(serial) > 4 else serial
                return f"Beacon {rev} (...{short_serial})"

        # Truncate long names
        if len(name) > 50:
            return name[:25] + "..." + name[-15:]

        return name

    def _render_port_select(self, field: Dict[str, Any]) -> Optional[str]:
        """Render a board port selection with conflict detection."""
        label = field.get('label', 'Select port')
        state_key = field.get('state_key', '')
        port_type = field.get('port_type', 'motor_ports')
        current = self._get_state_value(state_key)

        # Build a descriptive title from state_key (e.g., "stepper_x.motor_port" -> "Stepper X: Motor Port")
        title = label
        if '.' in state_key:
            prefix = state_key.rsplit('.', 1)[0]
            # Format prefix: stepper_x -> Stepper X, stepper_y1 -> Stepper Y1
            section_name = prefix.replace('_', ' ').title()
            title = f"{section_name}: {label}"

        # Get board data
        state_dict = self.state.get_all()
        location = self._determine_port_location(field, state_dict)

        if location == 'toolboard':
            board_type = self.state.get('mcu.toolboard.board_type')
            board_data = self._load_board_data(board_type, 'toolboards')
        else:
            board_type = self.state.get('mcu.main.board_type')
            board_data = self._load_board_data(board_type, 'boards')

        if not board_data:
            self.ui.msgbox(f"Board not selected. Please configure MCU first.", title=title)
            return None

        # Get ports of the requested type
        ports = board_data.get(port_type, {})

        if not ports:
            self.ui.msgbox(f"No {port_type} available on selected board.", title=title)
            return None

        # Build selection items with conflict detection
        items: List[Tuple[str, str, bool]] = []
        for port_id, port_info in ports.items():
            port_label = port_info.get('label', port_id)
            pin = port_info.get('pin', port_info.get('step_pin', ''))

            # Check for conflicts via PinManager
            conflict_warning = ""
            if self.pin_manager:
                used_by = self.pin_manager.get_used_by(location, port_id)
                if used_by and state_key not in used_by:
                    conflict_warning = f" [!{used_by}]"

            display = f"{port_label} ({pin}){conflict_warning}"
            is_selected = (port_id == current)
            items.append((port_id, display, is_selected))

        result = self.ui.radiolist(label, items, title=title)

        if result is not None:
            self._set_state_value(state_key, result)

            # Update PinManager if available
            if self.pin_manager:
                self.pin_manager.assign_port(location, result, state_key)

            return result

        return None

    def _determine_port_location(self, field: Dict[str, Any], state: Dict[str, Any]) -> str:
        """Determine which board (mainboard/toolboard) a port should come from."""
        state_key = field.get('state_key', '')

        # Check if field has explicit location_key
        location_key = field.get('location_key')
        if location_key:
            location = self._get_state_value(location_key)
            if location:
                return location

        # Extract prefix and field name (e.g., 'stepper_x' and 'endstop_port')
        if '.' in state_key:
            prefix, field_name = state_key.rsplit('.', 1)

            # Try specific location keys based on field name pattern
            location_candidates = []

            # For endstop_port, check endstop_location
            if 'endstop' in field_name:
                location_candidates.append(f"{prefix}.endstop_location")

            # For sensor_port, check sensor_location
            if 'sensor' in field_name:
                location_candidates.append(f"{prefix}.sensor_location")

            # For heater_port, check heater_location
            if 'heater' in field_name:
                location_candidates.append(f"{prefix}.heater_location")

            # Generic location key
            location_candidates.append(f"{prefix}.location")

            for loc_key in location_candidates:
                location = self._get_state_value(loc_key)
                if location:
                    return location

        return 'mainboard'

    def _render_board_select(self, field: Dict[str, Any]) -> Optional[str]:
        """Render a board selection from templates."""
        label = field.get('label', 'Select board')
        state_key = field.get('state_key', '')
        source = field.get('source', 'templates/boards/')
        current = self._get_state_value(state_key)

        # Determine board type from source
        if 'toolboards' in source:
            board_type = 'toolboards'
        else:
            board_type = 'boards'

        # Load available boards
        boards = self._load_available_boards(board_type)

        if not boards:
            self.ui.msgbox(f"No boards found in {source}", title=label)
            return None

        # Build selection items
        items: List[Tuple[str, str, bool]] = []
        for board_id, board_name in boards:
            is_selected = (board_id == current)
            items.append((board_id, board_name, is_selected))

        result = self.ui.radiolist(label, items, title=label)

        if result is not None:
            self._set_state_value(state_key, result)
            return result

        return None

    def _load_available_boards(self, board_type: str = 'boards') -> List[Tuple[str, str]]:
        """Load list of available boards from templates.

        Args:
            board_type: 'boards' or 'toolboards'

        Returns:
            List of (board_id, board_name) tuples
        """
        boards = []
        boards_dir = REPO_ROOT / "templates" / board_type

        if not boards_dir.is_dir():
            return []

        for json_file in sorted(boards_dir.glob("*.json")):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    board_id = data.get('id', json_file.stem)
                    board_name = data.get('name', board_id)
                    manufacturer = data.get('manufacturer', '')
                    if manufacturer:
                        board_name = f"{manufacturer} {board_name}"
                    boards.append((board_id, board_name))
            except (json.JSONDecodeError, IOError):
                continue

        return boards

    def _load_board_data(self, board_id: str, board_type: str = 'boards') -> Dict[str, Any]:
        """Load full board JSON data.

        Args:
            board_id: Board identifier
            board_type: 'boards' or 'toolboards'

        Returns:
            Board data dict or empty dict if not found
        """
        if not board_id:
            return {}

        boards_dir = REPO_ROOT / "templates" / board_type

        # Try exact match
        json_file = boards_dir / f"{board_id}.json"
        if json_file.exists():
            try:
                with open(json_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}

        # Try to find by ID field in all files
        for json_file in boards_dir.glob("*.json"):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    if data.get('id') == board_id:
                        return data
            except (json.JSONDecodeError, IOError):
                continue

        return {}
