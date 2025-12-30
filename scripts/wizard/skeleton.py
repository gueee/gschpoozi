"""
skeleton.py - Skeleton-driven configuration wizard core

Provides SkeletonLoader and SkeletonValidator classes for loading
and validating the skeleton.json schema.
"""

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class ValidationResult:
    """Result of a single validation check."""
    valid: bool
    field_id: str
    message: str = ""


@dataclass
class ConflictResult:
    """Result of a conflict check."""
    id: str
    type: str  # 'error' or 'warning'
    message: str
    condition: str


class SkeletonLoader:
    """Loads and provides access to skeleton.json.

    The skeleton is the single source of truth for:
    - Menu structure and navigation
    - Section and field definitions
    - Exclusive groups (mutually exclusive options)
    - Conflict rules
    - Value implications (auto-set values)
    """

    def __init__(self, skeleton_path: Path = None):
        """Initialize the skeleton loader.

        Args:
            skeleton_path: Path to skeleton.json. If None, searches default locations.
        """
        self.skeleton_path = skeleton_path or self._find_skeleton_file()
        self.skeleton: Dict[str, Any] = {}
        self._load_skeleton()

    def _find_skeleton_file(self) -> Path:
        """Find skeleton.json in the schema directory."""
        module_dir = Path(__file__).parent
        candidates = [
            module_dir.parent.parent / "schema" / "skeleton.json",
            module_dir.parent / "schema" / "skeleton.json",
            Path.home() / "gschpoozi" / "schema" / "skeleton.json",
        ]

        for path in candidates:
            if path.exists():
                return path

        raise FileNotFoundError(
            "Could not find skeleton.json. "
            "Searched: " + ", ".join(str(p) for p in candidates)
        )

    def _load_skeleton(self) -> None:
        """Load skeleton from JSON file."""
        with open(self.skeleton_path, 'r') as f:
            self.skeleton = json.load(f)

    @property
    def version(self) -> str:
        """Get skeleton version."""
        return self.skeleton.get('version', '0.0.0')

    @property
    def metadata(self) -> Dict[str, Any]:
        """Get skeleton metadata."""
        return self.skeleton.get('metadata', {})

    # =========================================================================
    # Menu access
    # =========================================================================

    def get_menu(self, menu_id: str) -> Optional[Dict[str, Any]]:
        """Get a menu definition by ID.

        Args:
            menu_id: Menu identifier (e.g., 'main', 'hardware_setup')

        Returns:
            Menu definition dict or None if not found
        """
        return self.skeleton.get('menus', {}).get(menu_id)

    def get_menu_items(self, menu_id: str, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get available menu items for a menu, filtered by conditions.

        Args:
            menu_id: Menu identifier
            state: Current wizard state for condition evaluation

        Returns:
            List of menu items that pass their conditions
        """
        menu = self.get_menu(menu_id)
        if not menu:
            return []

        items = []
        for item in menu.get('items', []):
            condition = item.get('condition')
            if condition and not self.evaluate_condition(condition, state):
                continue
            items.append(item)

        return items

    # =========================================================================
    # Section access
    # =========================================================================

    def get_section(self, section_id: str) -> Optional[Dict[str, Any]]:
        """Get a section definition by ID.

        Args:
            section_id: Section identifier (e.g., 'mcu', 'probe')

        Returns:
            Section definition dict or None if not found
        """
        return self.skeleton.get('sections', {}).get(section_id)

    def get_section_fields(
        self,
        section_id: str,
        state: Dict[str, Any],
        subsection_id: str = None
    ) -> List[Dict[str, Any]]:
        """Get fields for a section, filtered by conditions.

        Args:
            section_id: Section identifier
            state: Current wizard state for condition evaluation
            subsection_id: Optional subsection identifier

        Returns:
            List of fields that pass their conditions
        """
        section = self.get_section(section_id)
        if not section:
            return []

        # If subsection requested, find it
        if subsection_id:
            subsections = section.get('subsections', [])
            section = next(
                (s for s in subsections if s.get('id') == subsection_id),
                None
            )
            if not section:
                return []

        # Check section-level condition
        section_condition = section.get('condition')
        if section_condition and not self.evaluate_condition(section_condition, state):
            return []

        # Filter fields by condition
        fields = []
        for field in section.get('fields', []):
            condition = field.get('condition')
            if condition and not self.evaluate_condition(condition, state):
                continue
            fields.append(field)

        return fields

    def get_subsections(
        self,
        section_id: str,
        state: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get subsections for a section, filtered by conditions.

        Args:
            section_id: Section identifier
            state: Current wizard state for condition evaluation

        Returns:
            List of subsections that pass their conditions
        """
        section = self.get_section(section_id)
        if not section:
            return []

        subsections = []
        for sub in section.get('subsections', []):
            condition = sub.get('condition')
            if condition and not self.evaluate_condition(condition, state):
                continue
            subsections.append(sub)

        return subsections

    # =========================================================================
    # Exclusive groups
    # =========================================================================

    def get_exclusive_group(self, group_id: str) -> Optional[Dict[str, Any]]:
        """Get an exclusive group definition by ID.

        Args:
            group_id: Group identifier (e.g., 'probe_types', 'leveling_types')

        Returns:
            Exclusive group definition dict or None if not found
        """
        return self.skeleton.get('exclusive_groups', {}).get(group_id)

    def get_available_options(
        self,
        group_id: str,
        state: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get available options for an exclusive group, filtered by conditions.

        Args:
            group_id: Group identifier
            state: Current wizard state for condition evaluation

        Returns:
            List of options that pass their conditions
        """
        group = self.get_exclusive_group(group_id)
        if not group:
            return []

        options = []
        for option in group.get('options', []):
            condition = option.get('condition')
            if condition and not self.evaluate_condition(condition, state):
                continue
            options.append(option)

        return options

    def get_probe_metadata(self, probe_type: str) -> Optional[Dict[str, Any]]:
        """Get probe-specific metadata from the probe_types exclusive group.

        Args:
            probe_type: Probe type value (e.g., 'beacon', 'bltouch')

        Returns:
            Probe option dict with all metadata or None if not found
        """
        group = self.get_exclusive_group('probe_types')
        if not group:
            return None

        for option in group.get('options', []):
            if option.get('value') == probe_type:
                return option

        return None

    # =========================================================================
    # Field types
    # =========================================================================

    def get_field_type(self, type_id: str) -> Optional[Dict[str, Any]]:
        """Get a field type definition.

        Args:
            type_id: Field type identifier (e.g., 'text', 'int', 'choice')

        Returns:
            Field type definition dict or None if not found
        """
        return self.skeleton.get('field_types', {}).get(type_id)

    # =========================================================================
    # Conflicts
    # =========================================================================

    def get_logical_conflicts(self) -> List[Dict[str, Any]]:
        """Get all logical conflict definitions.

        Returns:
            List of logical conflict definitions
        """
        conflicts = self.skeleton.get('conflicts', {})
        return conflicts.get('logical_conflicts', [])

    # =========================================================================
    # Implications
    # =========================================================================

    def get_implications(self) -> Dict[str, Dict[str, Any]]:
        """Get all implication definitions.

        Returns:
            Dict of implication ID to implication definition
        """
        return self.skeleton.get('implications', {})

    def get_active_implications(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Get values that should be auto-set based on current state.

        Args:
            state: Current wizard state

        Returns:
            Dict of state_key -> value for all active implications
        """
        result = {}

        for impl_id, impl in self.get_implications().items():
            condition = impl.get('condition')
            if condition and self.evaluate_condition(condition, state):
                for key, value in impl.get('set', {}).items():
                    result[key] = value

        return result

    # =========================================================================
    # Condition evaluation
    # =========================================================================

    def evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate a condition string against context.

        Supports:
        - Attribute chains: probe.probe_type
        - Comparisons: ==, !=, <, <=, >, >=, in, not in
        - Boolean operators: and, or, not
        - Lists: ['value1', 'value2']

        Args:
            condition: Condition expression string
            context: State dict for variable resolution

        Returns:
            True if condition passes, False otherwise
        """
        if not condition:
            return True

        def _get_path(obj: Any, path: List[str]) -> Any:
            """Traverse a nested dict/object by path."""
            cur = obj
            for part in path:
                if isinstance(cur, dict):
                    cur = cur.get(part)
                else:
                    cur = getattr(cur, part, None)
                if cur is None:
                    return None
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
                parts: List[str] = []
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
                        ok = (left < right) if left is not None and right is not None else False
                    elif isinstance(op, ast.LtE):
                        ok = (left <= right) if left is not None and right is not None else False
                    elif isinstance(op, ast.Gt):
                        ok = (left > right) if left is not None and right is not None else False
                    elif isinstance(op, ast.GtE):
                        ok = (left >= right) if left is not None and right is not None else False
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

            raise ValueError(f"Unsupported expression: {node.__class__.__name__}")

        try:
            tree = ast.parse(condition, mode="eval")
            value = _eval(tree.body)
            return bool(value)
        except Exception:
            # Fail safe: if we can't evaluate a condition, return False
            return False


class SkeletonValidator:
    """Validates wizard state against skeleton rules.

    Checks:
    - Required fields are present
    - Field values are within valid ranges
    - Exclusive groups have exactly one selection
    - Logical conflicts
    """

    def __init__(self, skeleton: SkeletonLoader, state: Dict[str, Any]):
        """Initialize the validator.

        Args:
            skeleton: Loaded skeleton
            state: Current wizard state
        """
        self.skeleton = skeleton
        self.state = state

    def _get_state_value(self, key: str) -> Any:
        """Get a value from state by dot-notation key.

        Args:
            key: Dot-notation key (e.g., 'probe.probe_type')

        Returns:
            Value at key or None if not found
        """
        parts = key.split('.')
        cur = self.state
        for part in parts:
            if isinstance(cur, dict):
                cur = cur.get(part)
            else:
                return None
            if cur is None:
                return None
        return cur

    def validate_field(self, field: Dict[str, Any]) -> ValidationResult:
        """Validate a single field.

        Args:
            field: Field definition from skeleton

        Returns:
            ValidationResult with valid status and any error message
        """
        field_id = field.get('id', 'unknown')
        state_key = field.get('state_key', '')
        value = self._get_state_value(state_key)

        # Check required
        if field.get('required') and value is None:
            return ValidationResult(
                valid=False,
                field_id=field_id,
                message=f"Required field '{field.get('label', field_id)}' is not set"
            )

        # Skip further validation if value is None
        if value is None:
            return ValidationResult(valid=True, field_id=field_id)

        # Check range for numeric fields
        range_def = field.get('range')
        if range_def and len(range_def) == 2:
            min_val, max_val = range_def
            try:
                num_val = float(value)
                if num_val < min_val or num_val > max_val:
                    return ValidationResult(
                        valid=False,
                        field_id=field_id,
                        message=f"'{field.get('label', field_id)}' must be between {min_val} and {max_val}"
                    )
            except (TypeError, ValueError):
                pass

        # Check choice options
        field_type = field.get('type')
        if field_type in ('choice', 'exclusive_choice'):
            options = field.get('options', [])
            if options:
                valid_values = [opt.get('value') for opt in options]
                if value not in valid_values:
                    return ValidationResult(
                        valid=False,
                        field_id=field_id,
                        message=f"'{field.get('label', field_id)}' has invalid value: {value}"
                    )

        return ValidationResult(valid=True, field_id=field_id)

    def validate_section(self, section_id: str) -> List[ValidationResult]:
        """Validate all fields in a section.

        Args:
            section_id: Section identifier

        Returns:
            List of validation results (including failures)
        """
        results = []
        fields = self.skeleton.get_section_fields(section_id, self.state)

        for field in fields:
            result = self.validate_field(field)
            if not result.valid:
                results.append(result)

        # Also check subsections
        for sub in self.skeleton.get_subsections(section_id, self.state):
            sub_fields = self.skeleton.get_section_fields(
                section_id,
                self.state,
                sub.get('id')
            )
            for field in sub_fields:
                result = self.validate_field(field)
                if not result.valid:
                    results.append(result)

        return results

    def check_conflicts(self) -> List[ConflictResult]:
        """Check all logical conflicts against current state.

        Returns:
            List of active conflicts (errors and warnings)
        """
        conflicts = []

        for conflict in self.skeleton.get_logical_conflicts():
            condition = conflict.get('condition', '')
            if self.skeleton.evaluate_condition(condition, self.state):
                conflicts.append(ConflictResult(
                    id=conflict.get('id', 'unknown'),
                    type=conflict.get('type', 'warning'),
                    message=conflict.get('message', ''),
                    condition=condition
                ))

        return conflicts

    def is_section_complete(self, section_id: str) -> bool:
        """Check if a section has all required fields set.

        Args:
            section_id: Section identifier

        Returns:
            True if all required fields are set, False otherwise
        """
        fields = self.skeleton.get_section_fields(section_id, self.state)

        for field in fields:
            if field.get('required'):
                state_key = field.get('state_key', '')
                value = self._get_state_value(state_key)
                if value is None:
                    return False

        return True

    def get_missing_required_fields(self, section_id: str) -> List[str]:
        """Get list of missing required fields for a section.

        Args:
            section_id: Section identifier

        Returns:
            List of missing field labels
        """
        missing = []
        fields = self.skeleton.get_section_fields(section_id, self.state)

        for field in fields:
            if field.get('required'):
                state_key = field.get('state_key', '')
                value = self._get_state_value(state_key)
                if value is None:
                    missing.append(field.get('label', field.get('id', 'Unknown')))

        return missing

    def validate_all(self) -> Dict[str, Any]:
        """Run all validations and return a summary.

        Returns:
            Dict with 'valid', 'errors', 'warnings', 'incomplete_sections'
        """
        errors = []
        warnings = []
        incomplete_sections = []

        # Check all conflicts
        for conflict in self.check_conflicts():
            if conflict.type == 'error':
                errors.append(conflict.message)
            else:
                warnings.append(conflict.message)

        # Check all sections
        for section_id in self.skeleton.skeleton.get('sections', {}).keys():
            section = self.skeleton.get_section(section_id)
            if not section:
                continue

            # Skip sections that don't meet their condition
            condition = section.get('condition')
            if condition and not self.skeleton.evaluate_condition(condition, self.state):
                continue

            # Check required fields
            if section.get('required') and not self.is_section_complete(section_id):
                incomplete_sections.append(section.get('title', section_id))

            # Validate individual fields
            for result in self.validate_section(section_id):
                if not result.valid:
                    errors.append(result.message)

        return {
            'valid': len(errors) == 0 and len(incomplete_sections) == 0,
            'errors': errors,
            'warnings': warnings,
            'incomplete_sections': incomplete_sections
        }
