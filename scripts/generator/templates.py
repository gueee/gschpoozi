"""
templates.py - Jinja2 template loading and rendering

Handles loading config-sections.yaml and rendering templates.
"""

import ast
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from jinja2 import Environment, BaseLoader, TemplateSyntaxError


class TemplateRenderer:
    """Renders Klipper config from Jinja2 templates."""

    def __init__(self, templates_file: Path = None):
        self.templates_file = templates_file or self._find_templates_file()
        self.templates: Dict[str, Any] = {}
        self.pin_config: Dict[str, str] = {}
        self._load_templates()

        # Set up Jinja2 environment
        self.env = Environment(
            loader=BaseLoader(),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add custom filters
        self.env.filters['abs'] = abs

    def _find_templates_file(self) -> Path:
        """Find config-sections.yaml in the schema directory."""
        # Try relative to this file
        module_dir = Path(__file__).parent
        candidates = [
            module_dir.parent.parent / "schema" / "config-sections.yaml",
            module_dir.parent / "schema" / "config-sections.yaml",
            Path.home() / "gschpoozi" / "schema" / "config-sections.yaml",
        ]

        for path in candidates:
            if path.exists():
                return path

        raise FileNotFoundError(
            "Could not find config-sections.yaml. "
            "Searched: " + ", ".join(str(p) for p in candidates)
        )

    def _load_templates(self) -> None:
        """Load templates from YAML file."""
        with open(self.templates_file, 'r') as f:
            data = yaml.safe_load(f)

        self.templates = data
        self.pin_config = data.get('pin_config', {})

    def evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate a condition string against context."""
        if not condition:
            return True

        def _get_path(obj: Any, path: list[str]) -> Any:
            cur = obj
            for part in path:
                if isinstance(cur, dict):
                    cur = cur.get(part)
                else:
                    # Support attribute access on objects if any appear in context
                    cur = getattr(cur, part, None)
            return cur

        def _eval(node: ast.AST) -> Any:
            # Constants
            if isinstance(node, ast.Constant):
                return node.value

            # Names (top-level dict keys)
            if isinstance(node, ast.Name):
                return context.get(node.id)

            # Attribute chain, e.g. probe.probe_type
            if isinstance(node, ast.Attribute):
                parts: list[str] = []
                cur: ast.AST = node
                while isinstance(cur, ast.Attribute):
                    parts.append(cur.attr)
                    cur = cur.value
                parts.reverse()
                base = _eval(cur)
                return _get_path(base, parts)

            # Boolean ops
            if isinstance(node, ast.BoolOp):
                if isinstance(node.op, ast.And):
                    return all(bool(_eval(v)) for v in node.values)
                if isinstance(node.op, ast.Or):
                    return any(bool(_eval(v)) for v in node.values)
                raise ValueError("Unsupported boolean operator")

            # Unary ops
            if isinstance(node, ast.UnaryOp):
                if isinstance(node.op, ast.Not):
                    return not bool(_eval(node.operand))
                raise ValueError("Unsupported unary operator")

            # Compare ops
            if isinstance(node, ast.Compare):
                left = _eval(node.left)
                for op, comp in zip(node.ops, node.comparators):
                    right = _eval(comp)
                    if isinstance(op, ast.In):
                        ok = left in right if right is not None else False
                    elif isinstance(op, ast.NotIn):
                        ok = left not in right if right is not None else True
                    elif isinstance(op, ast.Eq):
                        ok = left == right
                    elif isinstance(op, ast.NotEq):
                        ok = left != right
                    elif isinstance(op, ast.Lt):
                        ok = left < right
                    elif isinstance(op, ast.LtE):
                        ok = left <= right
                    elif isinstance(op, ast.Gt):
                        ok = left > right
                    elif isinstance(op, ast.GtE):
                        ok = left >= right
                    elif isinstance(op, ast.Is):
                        ok = left is right
                    elif isinstance(op, ast.IsNot):
                        ok = left is not right
                    else:
                        raise ValueError("Unsupported comparison operator")
                    if not ok:
                        return False
                    left = right
                return True

            # Lists / tuples / sets in conditions
            if isinstance(node, ast.List):
                return [_eval(e) for e in node.elts]
            if isinstance(node, ast.Tuple):
                return tuple(_eval(e) for e in node.elts)
            if isinstance(node, ast.Set):
                return set(_eval(e) for e in node.elts)

            # Parentheses are implicit in AST; no special handling needed

            raise ValueError(f"Unsupported expression: {node.__class__.__name__}")

        try:
            tree = ast.parse(condition, mode="eval")
            value = _eval(tree.body)
            return bool(value)
        except Exception:
            # Fail safe: if we can't evaluate a condition, do NOT render the section
            return False

    def render_template(
        self,
        template_str: str,
        context: Dict[str, Any]
    ) -> str:
        """Render a single template string with context."""
        try:
            # Add pin_config to context
            context['pin_config'] = self.pin_config

            template = self.env.from_string(template_str)
            result = template.render(**context)
            # Ensure result ends with at least one newline
            if not result.endswith('\n'):
                result += '\n'
            return result
        except TemplateSyntaxError as e:
            return f"# Template error: {e}\n"
        except Exception as e:
            return f"# Render error: {e}\n"

    def render_section(
        self,
        section_name: str,
        context: Dict[str, Any],
        subsection: str = None
    ) -> Optional[str]:
        """
        Render a config section.

        Args:
            section_name: Top-level section (e.g., 'mcu', 'stepper_x')
            context: Wizard state data
            subsection: Optional subsection (e.g., 'main' for mcu.main)

        Returns:
            Rendered config string or None if condition not met
        """
        section = self.templates.get(section_name)
        if not section:
            return None

        if subsection:
            section = section.get(subsection)
            if not section:
                return None

        # Check condition
        condition = section.get('condition')
        if condition and not self.evaluate_condition(condition, context):
            return None

        # Get template
        template_str = section.get('template')
        if not template_str:
            return None
        # Some templates (e.g., gcode macros) contain Klipper's own Jinja and must be emitted verbatim.
        if section.get("render") == "raw":
            return (template_str.rstrip() + "\n")

        return self.render_template(template_str, context)

    def render_all(self, context: Dict[str, Any]) -> Dict[str, str]:
        """
        Render all sections that apply to the given context.

        Returns:
            Dict mapping section names to rendered config strings
        """
        results = {}

        # Define section order for output
        section_order = [
            ('mcu', 'main'),
            ('mcu', 'toolboard'),
            ('mcu', 'host'),
            ('printer', None),
            # X/Y steppers (including AWD)
            ('stepper_x', None),
            ('tmc_stepper_x', None),
            ('stepper_x1', None),
            ('tmc_stepper_x1', None),
            ('stepper_y', None),
            ('tmc_stepper_y', None),
            ('stepper_y1', None),
            ('tmc_stepper_y1', None),
            # Z stepper
            ('stepper_z', None),
            ('tmc_stepper_z', None),
            # Extruder
            ('extruder', None),
            ('tmc_extruder', None),
            ('heater_bed', None),
            # Fans
            ('multi_pin', None),
            ('fan', None),
            ('heater_fan', None),
            ('controller_fan', None),
            ('fan_generic', None),
            # Probes (standard and eddy)
            ('probe', None),
            ('bltouch', None),
            ('beacon', None),
            ('cartographer', None),
            ('btt_eddy', None),
            # Homing and leveling
            ('safe_z_home', None),
            ('bed_mesh', None),
            ('z_tilt', None),
            ('quad_gantry_level', None),
            # Temperature sensors, LEDs, filament sensors
            ('temperature_sensor', None),
            ('neopixel', None),
            ('filament_switch_sensor', None),
            # Macros
            ('start_print', None),
            ('end_print', None),
        ]

        for section_name, subsection in section_order:
            key = f"{section_name}.{subsection}" if subsection else section_name
            result = self.render_section(section_name, context, subsection)
            if result:
                results[key] = result

        # Render common sections
        common = self.templates.get('common', {})
        for name, section in common.items():
            condition = section.get('condition')
            if condition and not self.evaluate_condition(condition, context):
                continue

            template_str = section.get('template')
            if template_str:
                if section.get("render") == "raw":
                    result = template_str.rstrip() + "\n"
                else:
                    result = self.render_template(template_str, context)
                if result:
                    results[f"common.{name}"] = result

        return results

