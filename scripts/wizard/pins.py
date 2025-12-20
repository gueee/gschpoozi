"""
pins.py - Unified pin selection and conflict management for gschpoozi wizard

Provides a consistent interface for:
- Digital input pin selection (endstops, filament sensors) with pullup/invert toggles
- Analog input pin selection (thermistors) with sensor type and pullup resistor
- Output pin selection (fans, heaters) with capability display
- Multi-pin output selection (multiple pins as one logical output)
- Pin conflict detection and tracking
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple


class PinManager:
    """Centralized pin selection and conflict tracking."""

    # Common pullup resistor values
    PULLUP_RESISTOR_OPTIONS = [
        ("2200", "2.2kΩ (most toolboards: EBB, SHT36, Nitehawk)"),
        ("4700", "4.7kΩ (most mainboards)"),
        ("1000", "1kΩ (some PT1000 boards)"),
        ("10000", "10kΩ (rare)"),
        ("none", "None (omit from config)"),
        ("custom", "Custom value..."),
    ]

    # Common thermistor types
    THERMISTOR_TYPES = [
        ("Generic 3950", "Generic 3950 (most common)"),
        ("NTC 100K beta 3950", "NTC 100K beta 3950"),
        ("ATC Semitec 104GT-2", "ATC Semitec 104GT-2"),
        ("ATC Semitec 104NT-4-R025H42G", "ATC Semitec 104NT-4 (Rapido, Dragon UHF)"),
        ("PT1000", "PT1000 (high temp)"),
        ("SliceEngineering 450", "SliceEngineering 450°C"),
        ("EPCOS 100K B57560G104F", "EPCOS 100K B57560G104F"),
        ("Honeywell 100K 135-104LAG-J01", "Honeywell 100K"),
    ]

    def __init__(self, state, ui, board_data: Dict[str, Any], toolboard_data: Dict[str, Any] = None):
        """
        Initialize PinManager.

        Args:
            state: WizardState instance for reading/writing configuration
            ui: WizardUI instance for user interaction
            board_data: Main board definition dict (from JSON template)
            toolboard_data: Optional toolboard definition dict
        """
        self.state = state
        self.ui = ui
        self.board_data = board_data or {}
        self.toolboard_data = toolboard_data or {}
        # {location: {port_id: purpose}}
        self._used_pins: Dict[str, Dict[str, str]] = {"mainboard": {}, "toolboard": {}}
        # Load already-assigned pins from state
        self.load_used_from_state()

    # -------------------------------------------------------------------------
    # Pin tracking and conflict detection
    # -------------------------------------------------------------------------

    def load_used_from_state(self) -> None:
        """Load currently assigned pins from wizard state."""
        self._used_pins = {"mainboard": {}, "toolboard": {}}

        # Steppers / motors (mainboard motor ports)
        for stepper in ("stepper_x", "stepper_y", "stepper_z", "stepper_x1", "stepper_y1",
                        "stepper_z1", "stepper_z2", "stepper_z3"):
            port = self.state.get(f"{stepper}.motor_port", "")
            if port:
                self._used_pins["mainboard"][port] = f"{stepper} motor"
            # Endstops (mainboard)
            endstop_port = self.state.get(f"{stepper}.endstop_port", "")
            if endstop_port:
                self._used_pins["mainboard"][endstop_port] = f"{stepper} endstop"
            # Endstops (toolboard)
            endstop_port_tb = self.state.get(f"{stepper}.endstop_port_toolboard", "")
            if endstop_port_tb:
                self._used_pins["toolboard"][endstop_port_tb] = f"{stepper} endstop"

        # Extruder motor
        motor_location = self.state.get("extruder.location", "mainboard") or "mainboard"
        if motor_location == "mainboard":
            port = self.state.get("extruder.motor_port_mainboard", "")
            if port:
                self._used_pins["mainboard"][port] = "Extruder motor"
        else:
            port = self.state.get("extruder.motor_port_toolboard", "")
            if port:
                self._used_pins["toolboard"][port] = "Extruder motor"

        # Extruder heater
        heater_location = self.state.get("extruder.heater_location", "mainboard") or "mainboard"
        if heater_location == "mainboard":
            port = self.state.get("extruder.heater_port_mainboard", "")
            if port:
                self._used_pins["mainboard"][port] = "Extruder heater"
        else:
            port = self.state.get("extruder.heater_port_toolboard", "")
            if port:
                self._used_pins["toolboard"][port] = "Extruder heater"

        # Extruder sensor
        sensor_location = self.state.get("extruder.sensor_location", "mainboard") or "mainboard"
        if sensor_location == "mainboard":
            port = self.state.get("extruder.sensor_port_mainboard", "")
            if port:
                self._used_pins["mainboard"][port] = "Extruder thermistor"
        else:
            port = self.state.get("extruder.sensor_port_toolboard", "")
            if port:
                self._used_pins["toolboard"][port] = "Extruder thermistor"

        # Heater bed
        bed_heater = self.state.get("heater_bed.heater_pin", "")
        if bed_heater:
            self._used_pins["mainboard"][bed_heater] = "Heated bed heater"
        bed_sensor = self.state.get("heater_bed.sensor_port", "")
        if bed_sensor:
            self._used_pins["mainboard"][bed_sensor] = "Bed thermistor"

        # Fans (mainboard)
        part_loc = self.state.get("fans.part_cooling.location", "mainboard") or "mainboard"
        if part_loc == "mainboard":
            pin = self.state.get("fans.part_cooling.pin_mainboard", "")
            if pin:
                self._used_pins["mainboard"][pin] = "Part cooling fan"
        else:
            pin = self.state.get("fans.part_cooling.pin_toolboard", "")
            if pin:
                self._used_pins["toolboard"][pin] = "Part cooling fan"

        hotend_loc = self.state.get("fans.hotend.location", "mainboard") or "mainboard"
        if hotend_loc == "mainboard":
            pin = self.state.get("fans.hotend.pin_mainboard", "")
            if pin:
                self._used_pins["mainboard"][pin] = "Hotend fan"
        else:
            pin = self.state.get("fans.hotend.pin_toolboard", "")
            if pin:
                self._used_pins["toolboard"][pin] = "Hotend fan"

        controller_pin = self.state.get("fans.controller.pin", "")
        if controller_pin:
            self._used_pins["mainboard"][controller_pin] = "Controller fan"

        # Additional fans
        additional_fans = self.state.get("fans.additional_fans", [])
        if isinstance(additional_fans, list):
            for idx, fan in enumerate(additional_fans, start=1):
                if not isinstance(fan, dict):
                    continue
                loc = (fan.get("location") or "mainboard").strip()
                pin = (fan.get("pin") or "").strip()
                if pin:
                    self._used_pins[loc][pin] = f"Additional fan #{idx}"
                # Multi-pin fans
                pins = fan.get("pins")
                if isinstance(pins, list):
                    for p in pins:
                        if isinstance(p, str) and p.strip():
                            self._used_pins[loc][p.strip()] = f"Additional fan #{idx} (multi_pin)"

        # LEDs
        leds = self.state.get("leds", [])
        if isinstance(leds, list):
            for led in leds:
                if not isinstance(led, dict):
                    continue
                pin = led.get("pin")
                name = (led.get("name") or "led").strip()
                if isinstance(pin, str) and pin.strip():
                    self._used_pins["mainboard"][pin.strip()] = f"LED ({name})"

        # Filament sensors
        filament_sensors = self.state.get("filament_sensors", [])
        if isinstance(filament_sensors, list):
            for sensor in filament_sensors:
                if not isinstance(sensor, dict):
                    continue
                pin = sensor.get("pin")
                name = (sensor.get("name") or "filament").strip()
                if isinstance(pin, str) and pin.strip():
                    self._used_pins["mainboard"][pin.strip()] = f"Filament sensor ({name})"

        # Temperature sensors
        temp_sensors = self.state.get("temperature_sensors.additional", [])
        if isinstance(temp_sensors, list):
            for sensor in temp_sensors:
                if not isinstance(sensor, dict):
                    continue
                pin = sensor.get("sensor_pin")
                name = (sensor.get("name") or "additional").strip()
                if isinstance(pin, str) and pin.strip():
                    self._used_pins["mainboard"][pin.strip()] = f"Temp sensor ({name})"

    def mark_used(self, location: str, port_id: str, purpose: str) -> None:
        """Mark a pin/port as used."""
        if location not in self._used_pins:
            self._used_pins[location] = {}
        self._used_pins[location][port_id] = purpose

    def mark_unused(self, location: str, port_id: str) -> None:
        """Remove a pin/port from the used list."""
        if location in self._used_pins and port_id in self._used_pins[location]:
            del self._used_pins[location][port_id]

    def is_available(self, location: str, port_id: str) -> bool:
        """Check if a pin/port is available (not already used)."""
        return port_id not in self._used_pins.get(location, {})

    def get_used_by(self, location: str, port_id: str) -> Optional[str]:
        """Get what a pin/port is used for, or None if available."""
        return self._used_pins.get(location, {}).get(port_id)

    def get_all_used(self, location: str = None) -> Dict[str, str]:
        """Get all used pins for a location (or all if location is None)."""
        if location:
            return self._used_pins.get(location, {}).copy()
        result = {}
        for loc_pins in self._used_pins.values():
            result.update(loc_pins)
        return result

    # -------------------------------------------------------------------------
    # Pin listing and resolution
    # -------------------------------------------------------------------------

    def _get_board_for_location(self, location: str) -> Dict[str, Any]:
        """Get the appropriate board data for a location."""
        if location == "toolboard":
            return self.toolboard_data
        return self.board_data

    def get_available_pins(
        self,
        location: str,
        groups: List[str],
        exclude_ports: Set[str] = None
    ) -> List[Tuple[str, str, Dict[str, Any]]]:
        """
        Get available pins from specified groups.

        Args:
            location: "mainboard" or "toolboard"
            groups: List of port group names (e.g., ["fan_ports", "heater_ports"])
            exclude_ports: Additional ports to exclude

        Returns:
            List of (port_id, label, port_info) tuples for available pins
        """
        board = self._get_board_for_location(location)
        if not board:
            return []

        exclude = exclude_ports or set()
        used = self._used_pins.get(location, {})
        available = []

        for group in groups:
            group_data = board.get(group, {})
            if not isinstance(group_data, dict):
                continue

            for port_id, port_info in group_data.items():
                # Skip if already used or explicitly excluded
                if port_id in used or port_id in exclude:
                    continue

                # Build label
                if isinstance(port_info, dict):
                    pin = port_info.get("pin") or port_info.get("signal_pin") or ""
                    label = port_info.get("label", port_id)
                    # Add capability info if available
                    capabilities = []
                    if port_info.get("pwm"):
                        capabilities.append("PWM")
                    if port_info.get("max_current_amps"):
                        capabilities.append(f"{port_info['max_current_amps']}A")
                    if pin:
                        label = f"{label} ({pin})"
                    if capabilities:
                        label = f"{label} [{', '.join(capabilities)}]"
                    label = f"{label} [{group}]"
                else:
                    label = f"{port_id} [{group}]"
                    port_info = {"pin": str(port_info) if port_info else ""}

                available.append((port_id, label, port_info))

        return available

    def resolve_pin(self, location: str, port_id: str, group: str = None) -> str:
        """
        Resolve a port ID to the actual pin name.

        Args:
            location: "mainboard" or "toolboard"
            port_id: Port ID (e.g., "FAN0", "T0")
            group: Optional group name to search in

        Returns:
            Pin name (e.g., "PA8") or empty string if not found
        """
        board = self._get_board_for_location(location)
        if not board:
            return port_id if self._looks_like_raw_pin(port_id) else ""

        # If group specified, search only that group
        groups = [group] if group else list(board.keys())

        for g in groups:
            group_data = board.get(g, {})
            if not isinstance(group_data, dict):
                continue
            if port_id in group_data:
                info = group_data[port_id]
                if isinstance(info, dict):
                    return info.get("pin") or info.get("signal_pin") or ""
                elif isinstance(info, str):
                    return info

        # Fallback: return as-is if it looks like a raw pin
        return port_id if self._looks_like_raw_pin(port_id) else ""

    def _looks_like_raw_pin(self, value: str) -> bool:
        """Check if a string looks like a raw MCU pin (e.g., PA1, gpio26)."""
        s = (value or "").strip()
        if not s or ":" in s:
            return False
        if re.match(r"^P[A-Z]\d+$", s):
            return True
        if re.match(r"^gpio\d+$", s, flags=re.IGNORECASE):
            return True
        return False

    # -------------------------------------------------------------------------
    # Digital input selection (endstops, filament sensors, etc.)
    # -------------------------------------------------------------------------

    def select_digital_input(
        self,
        location: str,
        purpose: str,
        groups: List[str] = None,
        current_port: str = "",
        current_pullup: bool = True,
        current_invert: bool = False,
        title: str = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Select a digital input pin with pullup/invert options.

        Args:
            location: "mainboard" or "toolboard"
            purpose: Description of what this pin is for
            groups: Port groups to show (default: endstop_ports, misc_ports)
            current_port: Currently selected port ID
            current_pullup: Current pullup setting
            current_invert: Current invert setting
            title: Dialog title

        Returns:
            {
                'port': port_id,
                'pullup': bool,  # ^ modifier
                'invert': bool,  # ! modifier
            }
            or None if cancelled
        """
        if groups is None:
            groups = ["endstop_ports", "misc_ports", "probe_ports"]

        title = title or f"Select {purpose} Pin"

        # Get available pins
        available = self.get_available_pins(location, groups)
        if not available:
            # No board pins available - offer manual entry
            port = self.ui.inputbox(
                f"Enter pin for {purpose}:",
                default=current_port or "",
                title=title
            )
            if port is None:
                return None
        else:
            # Build radiolist options
            options = []
            for port_id, label, _ in available:
                is_selected = (port_id == current_port)
                options.append((port_id, label, is_selected))

            # Add manual entry option
            options.append(("manual", "Manual entry...", not current_port))

            # Ensure something is selected
            if not any(x[2] for x in options):
                options[0] = (options[0][0], options[0][1], True)

            port = self.ui.radiolist(
                f"Select pin for {purpose}:",
                options,
                title=title
            )

            if port is None:
                return None

            if port == "manual":
                port = self.ui.inputbox(
                    f"Enter pin for {purpose}:",
                    default=current_port or "",
                    title=title
                )
                if port is None:
                    return None

        # Pullup toggle
        pullup = self.ui.yesno(
            f"Enable internal pullup for {purpose}?\n\n"
            "This adds the '^' pin modifier.\n"
            "Recommended for most mechanical switches.",
            title=f"{purpose} - Pullup",
            default_no=not current_pullup
        )

        # Invert toggle
        invert = self.ui.yesno(
            f"Invert signal for {purpose}?\n\n"
            "This adds the '!' pin modifier.\n"
            "Enable if the signal is active when you expect it to be inactive.",
            title=f"{purpose} - Invert",
            default_no=not current_invert
        )

        return {
            'port': port,
            'pullup': pullup,
            'invert': invert,
        }

    # -------------------------------------------------------------------------
    # Analog input selection (thermistors, temperature sensors)
    # -------------------------------------------------------------------------

    def select_pullup_resistor(
        self,
        default: int = 4700,
        title: str = "Pullup Resistor"
    ) -> Optional[int]:
        """
        Select pullup resistor value.

        Args:
            default: Default value in ohms (or None for "omit")
            title: Dialog title

        Returns:
            int: Resistance in ohms (e.g., 2200, 4700)
            None: Omit pullup_resistor from config
        """
        options = []
        for value, label in self.PULLUP_RESISTOR_OPTIONS:
            if value == "none":
                is_selected = (default is None)
            elif value == "custom":
                is_selected = False
            else:
                is_selected = (default == int(value))
            options.append((value, label, is_selected))

        # Ensure something is selected
        if not any(x[2] for x in options):
            # Default to 4700 if no match
            for i, (value, label, _) in enumerate(options):
                if value == "4700":
                    options[i] = (value, label, True)
                    break

        choice = self.ui.radiolist(
            "Select pullup resistor value:\n\n"
            "(Check your board - wrong value = wrong temperature readings!)",
            options,
            title=title
        )

        if choice is None:
            return default  # Keep current on cancel

        if choice == "none":
            return None
        if choice == "custom":
            value = self.ui.inputbox(
                "Enter pullup resistance (Ω):",
                default=str(default) if default else "4700",
                title=title
            )
            if value is None:
                return default
            try:
                return int(value)
            except ValueError:
                return default

        return int(choice)

    def select_sensor_type(
        self,
        current: str = "Generic 3950",
        title: str = "Sensor Type"
    ) -> Optional[str]:
        """
        Select thermistor/sensor type.

        Returns:
            Sensor type string or None if cancelled
        """
        options = []
        for value, label in self.THERMISTOR_TYPES:
            is_selected = (value == current)
            options.append((value, label, is_selected))

        # Ensure something is selected
        if not any(x[2] for x in options):
            options[0] = (options[0][0], options[0][1], True)

        choice = self.ui.radiolist(
            "Select thermistor/sensor type:",
            options,
            title=title
        )

        return choice

    def select_analog_input(
        self,
        location: str,
        purpose: str,
        current_port: str = "",
        current_sensor_type: str = "Generic 3950",
        current_pullup_resistor: int = 4700,
        current_pin_pullup: bool = False,
        title: str = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Select an analog input pin (thermistor) with sensor type and pullup.

        Args:
            location: "mainboard" or "toolboard"
            purpose: Description (e.g., "Bed Thermistor")
            current_port: Currently selected port ID
            current_sensor_type: Current sensor type
            current_pullup_resistor: Current pullup resistor value (ohms) or None
            current_pin_pullup: Current pin ^ modifier setting
            title: Dialog title

        Returns:
            {
                'port': port_id,
                'sensor_type': str,
                'pullup_resistor': int | None,
                'pin_pullup': bool,  # ^ modifier for the pin itself
            }
            or None if cancelled
        """
        title = title or f"Select {purpose}"

        # Get available thermistor pins
        available = self.get_available_pins(location, ["thermistor_ports", "misc_ports"])

        if not available:
            # Manual entry fallback
            port = self.ui.inputbox(
                f"Enter thermistor pin for {purpose}:",
                default=current_port or "",
                title=title
            )
            if port is None:
                return None
        else:
            # Build radiolist
            options = []
            for port_id, label, _ in available:
                is_selected = (port_id == current_port)
                options.append((port_id, label, is_selected))

            options.append(("manual", "Manual entry...", not current_port))

            if not any(x[2] for x in options):
                options[0] = (options[0][0], options[0][1], True)

            port = self.ui.radiolist(
                f"Select thermistor port for {purpose}:",
                options,
                title=title
            )

            if port is None:
                return None

            if port == "manual":
                port = self.ui.inputbox(
                    f"Enter thermistor pin for {purpose}:",
                    default=current_port or "",
                    title=title
                )
                if port is None:
                    return None

        # Sensor type selection
        sensor_type = self.select_sensor_type(current_sensor_type, f"{purpose} - Sensor Type")
        if sensor_type is None:
            return None

        # Pullup resistor selection
        pullup_resistor = self.select_pullup_resistor(
            current_pullup_resistor,
            f"{purpose} - Pullup Resistor"
        )

        # Pin pullup toggle (^ modifier)
        # Default based on location - toolboards usually need it
        default_pin_pullup = current_pin_pullup if current_port else (location == "toolboard")
        pin_pullup = self.ui.yesno(
            f"Enable internal pullup on thermistor pin?\n\n"
            "This adds the '^' pin modifier to the sensor_pin.\n\n"
            "Most toolboards (EBB, SHT36, Nitehawk) need this enabled.\n"
            "Most mainboards have hardware pullups and don't need this.",
            title=f"{purpose} - Pin Pullup",
            default_no=not default_pin_pullup
        )

        return {
            'port': port,
            'sensor_type': sensor_type,
            'pullup_resistor': pullup_resistor,
            'pin_pullup': pin_pullup,
        }

    # -------------------------------------------------------------------------
    # Output pin selection (fans, heaters)
    # -------------------------------------------------------------------------

    def select_output_pin(
        self,
        location: str,
        purpose: str,
        output_type: str = "pwm",
        groups: List[str] = None,
        current_port: str = "",
        exclude_ports: Set[str] = None,
        title: str = None,
    ) -> Optional[str]:
        """
        Select an output pin (fan, heater, etc.).

        Args:
            location: "mainboard" or "toolboard"
            purpose: Description of what this pin is for
            output_type: "pwm", "mosfet", or "signal"
            groups: Port groups to show (default based on output_type)
            current_port: Currently selected port ID
            exclude_ports: Additional ports to exclude
            title: Dialog title

        Returns:
            Selected port ID or None if cancelled
        """
        if groups is None:
            if output_type == "mosfet":
                groups = ["heater_ports", "fan_ports", "misc_ports"]
            else:
                groups = ["fan_ports", "heater_ports", "misc_ports"]

        title = title or f"Select {purpose} Pin"

        available = self.get_available_pins(location, groups, exclude_ports)

        if not available:
            return self.ui.inputbox(
                f"Enter pin for {purpose}:",
                default=current_port or "",
                title=title
            )

        # Build radiolist
        options = []
        for port_id, label, _ in available:
            is_selected = (port_id == current_port)
            options.append((port_id, label, is_selected))

        options.append(("manual", "Manual entry...", not current_port))

        if not any(x[2] for x in options):
            options[0] = (options[0][0], options[0][1], True)

        # Sort: relevant ports first
        def sort_key(item):
            tag, label, _ = item
            if tag == "manual":
                return (2, "zzz")
            # Prioritize ports that match the output type
            is_heater = "heater" in tag.lower() or "hb" == tag.lower() or "he" in tag.lower()
            is_fan = "fan" in tag.lower()
            if output_type == "mosfet" and is_heater:
                return (0, tag.lower())
            if output_type == "pwm" and is_fan:
                return (0, tag.lower())
            return (1, tag.lower())

        options.sort(key=sort_key)

        port = self.ui.radiolist(
            f"Select pin for {purpose}:",
            options,
            title=title
        )

        if port is None:
            return None

        if port == "manual":
            return self.ui.inputbox(
                f"Enter pin for {purpose}:",
                default=current_port or "",
                title=title
            )

        return port

    # -------------------------------------------------------------------------
    # Multi-pin output selection
    # -------------------------------------------------------------------------

    def select_multi_pin_output(
        self,
        location: str,
        purpose: str,
        groups: List[str] = None,
        current_pin_type: str = "single",
        current_single_pin: str = "",
        current_multi_pins: List[str] = None,
        title: str = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Select single or multi-pin output.

        Args:
            location: "mainboard" or "toolboard"
            purpose: Description (used for naming multi_pin section)
            groups: Port groups to show
            current_pin_type: "single" or "multi_pin"
            current_single_pin: Current single pin selection
            current_multi_pins: Current multi-pin selections
            title: Dialog title

        Returns:
            For single pin:
                {'pin_type': 'single', 'pin': 'FAN2'}
            For multi-pin:
                {
                    'pin_type': 'multi_pin',
                    'multi_pin_name': 'multi_pin:exhaust_fans',
                    'pins': ['FAN2', 'FAN3', 'FAN4']
                }
            or None if cancelled
        """
        if groups is None:
            groups = ["fan_ports", "heater_ports", "misc_ports"]

        title = title or f"Select {purpose} Output"

        # Pin type selection
        pin_type = self.ui.radiolist(
            "Output pin type:",
            [
                ("single", "Single pin", current_pin_type == "single"),
                ("multi_pin", "Multi-pin (combine multiple outputs)", current_pin_type == "multi_pin"),
            ],
            title=title
        )

        if pin_type is None:
            return None

        if pin_type == "multi_pin":
            # Multi-pin selection via checklist
            available = self.get_available_pins(location, groups)

            if len(available) < 2:
                self.ui.msgbox(
                    "Multi-pin requires at least 2 available pins.\n"
                    "Not enough pins available on this board.",
                    title="Multi-Pin Error"
                )
                return None

            # Build checklist
            current_multi = set(current_multi_pins or [])
            items = []
            for port_id, label, _ in available:
                is_selected = (port_id in current_multi)
                items.append((port_id, label, is_selected))

            selected = self.ui.checklist(
                "Select pins to combine (select at least 2):",
                items,
                title=f"{purpose} - Multi-Pin Selection"
            )

            if selected is None:
                return None

            if len(selected) < 2:
                self.ui.msgbox(
                    "Multi-pin requires at least 2 pins.\n"
                    "Please select 2 or more pins.",
                    title="Multi-Pin Error"
                )
                return None

            # Generate multi_pin section name
            safe_name = purpose.lower().replace(" ", "_").replace("-", "_")
            multi_pin_name = f"multi_pin:{safe_name}"

            return {
                'pin_type': 'multi_pin',
                'multi_pin_name': multi_pin_name,
                'pins': list(selected),
            }
        else:
            # Single pin selection
            pin = self.select_output_pin(
                location, purpose, "pwm", groups,
                current_port=current_single_pin,
                title=title
            )

            if pin is None:
                return None

            return {
                'pin_type': 'single',
                'pin': pin,
            }

    # -------------------------------------------------------------------------
    # Motor port selection (compound port with step/dir/enable/etc.)
    # -------------------------------------------------------------------------

    def select_motor_port(
        self,
        location: str,
        purpose: str,
        current_port: str = "",
        exclude_ports: Set[str] = None,
        title: str = None,
    ) -> Optional[str]:
        """
        Select a motor port (compound port with step/dir/enable pins).

        Args:
            location: "mainboard" or "toolboard"
            purpose: Description of what this motor is for
            current_port: Currently selected port ID
            exclude_ports: Additional ports to exclude
            title: Dialog title

        Returns:
            Selected motor port ID or None if cancelled
        """
        title = title or f"Select {purpose} Motor Port"

        board = self._get_board_for_location(location)
        motor_ports = board.get("motor_ports", {})

        if not motor_ports:
            return self.ui.inputbox(
                f"Enter motor port for {purpose}:",
                default=current_port or "",
                title=title
            )

        exclude = exclude_ports or set()
        used = self._used_pins.get(location, {})

        options = []
        for port_id, port_info in motor_ports.items():
            if port_id in used or port_id in exclude:
                continue

            if isinstance(port_info, dict):
                label = port_info.get("label", port_id)
                step_pin = port_info.get("step_pin", "")
                if step_pin:
                    label = f"{label} (step: {step_pin})"
            else:
                label = port_id

            is_selected = (port_id == current_port)
            options.append((port_id, label, is_selected))

        if not options:
            return self.ui.inputbox(
                f"No motor ports available. Enter port for {purpose}:",
                default=current_port or "",
                title=title
            )

        options.append(("manual", "Manual entry...", False))

        if not any(x[2] for x in options):
            options[0] = (options[0][0], options[0][1], True)

        port = self.ui.radiolist(
            f"Select motor port for {purpose}:",
            options,
            title=title
        )

        if port is None:
            return None

        if port == "manual":
            return self.ui.inputbox(
                f"Enter motor port for {purpose}:",
                default=current_port or "",
                title=title
            )

        return port

