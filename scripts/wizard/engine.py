"""
engine.py - Generic menu engine for skeleton-driven wizard

The MenuEngine renders menus and sections from the skeleton.json schema,
delegating field rendering to the FieldRenderer.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple

from .skeleton import SkeletonLoader, SkeletonValidator
from .state import WizardState
from .ui import WizardUI


class MenuEngine:
    """Generic menu rendering engine driven by skeleton.json.

    The MenuEngine is responsible for:
    - Rendering menus from skeleton definitions
    - Running sections (sequences of fields)
    - Managing navigation flow
    - Showing validation warnings
    """

    def __init__(
        self,
        skeleton: SkeletonLoader,
        state: WizardState,
        ui: WizardUI,
        field_renderer: 'FieldRenderer' = None,
        action_handlers: Dict[str, Callable] = None
    ):
        """Initialize the menu engine.

        Args:
            skeleton: Loaded skeleton
            state: Wizard state manager
            ui: UI wrapper for dialogs
            field_renderer: Optional field renderer (created if not provided)
            action_handlers: Dict of action_id -> handler function for special actions
        """
        self.skeleton = skeleton
        self.state = state
        self.ui = ui
        self.action_handlers = action_handlers or {}

        # Import here to avoid circular imports
        if field_renderer is None:
            from .fields import FieldRenderer
            self.field_renderer = FieldRenderer(skeleton, state, ui)
        else:
            self.field_renderer = field_renderer

    def _get_state_value(self, key: str) -> Any:
        """Get a value from state by dot-notation key."""
        if not key:
            return None
        return self.state.get(key)

    def _format_status(self, status_key: str) -> str:
        """Format a status indicator for a menu item.

        Args:
            status_key: State key to check for status

        Returns:
            Status string like "[OK]" or "[...]"
        """
        if not status_key:
            return ""

        value = self._get_state_value(status_key)
        if value is not None and value != "":
            return "[OK]"
        return "[...]"

    def run_menu(self, menu_id: str) -> Optional[str]:
        """Run a menu loop until user exits.

        Args:
            menu_id: Menu identifier from skeleton

        Returns:
            'back' if user pressed back, 'quit' if user quit, None on error
        """
        menu = self.skeleton.get_menu(menu_id)
        if not menu:
            self.ui.msgbox(f"Menu '{menu_id}' not found in skeleton.")
            return None

        while True:
            # Get available menu items based on current state
            state_dict = self.state.get_all()
            items = self.skeleton.get_menu_items(menu_id, state_dict)

            if not items:
                self.ui.msgbox("No menu items available.")
                return 'back'

            # Build menu item list with status indicators
            menu_items: List[Tuple[str, str]] = []
            for item in items:
                item_id = item.get('id', '')
                label = item.get('label', item_id)
                description = item.get('description', '')

                # Add status indicator if status_key is defined
                status = self._format_status(item.get('status_key'))
                if status:
                    label = f"{label} {status}"

                menu_items.append((item_id, f"{label}: {description}" if description else label))

            # Add back option
            menu_items.append(('B', 'Back'))

            # Show menu
            choice = self.ui.menu(
                menu.get('title', 'Menu'),
                menu_items,
                title=menu.get('title', 'Menu')
            )

            if choice is None or choice == 'B':
                return 'back'

            # Find the selected item
            selected_item = next((i for i in items if i.get('id') == choice), None)
            if not selected_item:
                continue

            # Handle the selection
            action = selected_item.get('action')
            section = selected_item.get('section')

            if action:
                # Call action handler
                handler = self.action_handlers.get(action)
                if handler:
                    result = handler()
                    if result == 'quit':
                        return 'quit'
                else:
                    self.ui.msgbox(f"Action '{action}' not implemented.")

            elif section:
                # Check if it's a submenu or a section
                submenu = self.skeleton.get_menu(section)
                if submenu:
                    # It's a submenu, recurse
                    result = self.run_menu(section)
                    if result == 'quit':
                        return 'quit'
                else:
                    # It's a section, run the section wizard
                    self.run_section(section)

    def run_section(self, section_id: str) -> bool:
        """Run through a section's fields.

        Args:
            section_id: Section identifier from skeleton

        Returns:
            True if section completed, False if cancelled
        """
        section = self.skeleton.get_section(section_id)
        if not section:
            self.ui.msgbox(f"Section '{section_id}' not found in skeleton.")
            return False

        state_dict = self.state.get_all()

        # Check section-level condition
        condition = section.get('condition')
        if condition and not self.skeleton.evaluate_condition(condition, state_dict):
            self.ui.msgbox(
                f"Section '{section.get('title', section_id)}' is not available "
                "based on current configuration."
            )
            return False

        # Handle automatic inheritance (e.g., stepper_x1 inherits from stepper_x)
        copied_fields = set()
        inherit_from = section.get('inherit_from')
        if inherit_from:
            inherited_fields = section.get('inherited_fields', [])
            self._copy_section_fields(inherit_from, section_id, inherited_fields)
            copied_fields.update(inherited_fields)

        # Handle optional copy (e.g., stepper_y can optionally copy from stepper_x)
        copy_option = section.get('copy_from_option')
        if copy_option:
            source = copy_option.get('source')
            label = copy_option.get('label', f'Copy settings from {source}?')
            help_text = copy_option.get('help', '')
            copy_fields = copy_option.get('fields', [])

            prompt = label
            if help_text:
                prompt = f"{label}\n\n{help_text}"

            if self.ui.yesno(prompt, title=section.get('title', section_id)):
                self._copy_section_fields(source, section_id, copy_fields)
                copied_fields.update(copy_fields)

        # Get fields for main section
        fields = self.skeleton.get_section_fields(section_id, state_dict)

        # Show section title
        title = section.get('title', section_id)

        # Run through each field (skip if copied)
        for field in fields:
            # Skip fields that were copied
            if field.get('skip_if_copied') and field.get('id') in copied_fields:
                continue

            result = self.field_renderer.render_field(field)
            if result is None:
                # User cancelled
                return False

        # Run through subsections
        subsections = self.skeleton.get_subsections(section_id, state_dict)
        for sub in subsections:
            sub_id = sub.get('id')
            sub_title = sub.get('title', sub_id)

            # Get subsection fields
            sub_fields = self.skeleton.get_section_fields(section_id, state_dict, sub_id)

            if sub_fields:
                # Optionally show subsection header
                # self.ui.msgbox(f"Configuring: {sub_title}")

                for field in sub_fields:
                    result = self.field_renderer.render_field(field)
                    if result is None:
                        return False

        # Apply implications based on new state
        self._apply_implications()

        # Show any warnings
        self._show_warnings(section_id)

        return True

    def run_section_menu(self, section_id: str) -> Optional[str]:
        """Run a section as a menu where each field is a menu item.

        This is useful for sections where the user should be able to
        configure individual fields in any order.

        Args:
            section_id: Section identifier from skeleton

        Returns:
            'back' if user pressed back, None on error
        """
        section = self.skeleton.get_section(section_id)
        if not section:
            self.ui.msgbox(f"Section '{section_id}' not found in skeleton.")
            return None

        while True:
            state_dict = self.state.get_all()

            # Build menu from fields
            fields = self.skeleton.get_section_fields(section_id, state_dict)
            menu_items: List[Tuple[str, str]] = []

            for field in fields:
                field_id = field.get('id', '')
                label = field.get('label', field_id)
                state_key = field.get('state_key', '')
                current_value = self._get_state_value(state_key)

                # Format value display
                if current_value is not None:
                    value_str = str(current_value)
                    if len(value_str) > 30:
                        value_str = value_str[:27] + "..."
                    status = f"[{value_str}]"
                else:
                    status = "[not set]" if field.get('required') else "[optional]"

                menu_items.append((field_id, f"{label} {status}"))

            # Add subsections as menu items
            subsections = self.skeleton.get_subsections(section_id, state_dict)
            for sub in subsections:
                sub_id = sub.get('id')
                sub_title = sub.get('title', sub_id)
                menu_items.append((f"sub:{sub_id}", f">> {sub_title}"))

            # Add back option
            menu_items.append(('B', 'Back'))

            # Show menu
            title = section.get('title', section_id)
            choice = self.ui.menu(
                f"Configure: {title}",
                menu_items,
                title=title
            )

            if choice is None or choice == 'B':
                # Apply implications before leaving
                self._apply_implications()
                return 'back'

            # Handle subsection navigation
            if choice.startswith('sub:'):
                sub_id = choice[4:]
                self._run_subsection_menu(section_id, sub_id)
                continue

            # Find and render the selected field
            selected_field = next((f for f in fields if f.get('id') == choice), None)
            if selected_field:
                self.field_renderer.render_field(selected_field)

    def _run_subsection_menu(self, section_id: str, subsection_id: str) -> Optional[str]:
        """Run a subsection as a menu.

        Args:
            section_id: Parent section identifier
            subsection_id: Subsection identifier

        Returns:
            'back' if user pressed back
        """
        section = self.skeleton.get_section(section_id)
        if not section:
            return None

        subsections = section.get('subsections', [])
        subsection = next((s for s in subsections if s.get('id') == subsection_id), None)
        if not subsection:
            return None

        while True:
            state_dict = self.state.get_all()

            # Build menu from subsection fields
            fields = self.skeleton.get_section_fields(section_id, state_dict, subsection_id)
            menu_items: List[Tuple[str, str]] = []

            for field in fields:
                field_id = field.get('id', '')
                label = field.get('label', field_id)
                state_key = field.get('state_key', '')
                current_value = self._get_state_value(state_key)

                if current_value is not None:
                    value_str = str(current_value)
                    if len(value_str) > 30:
                        value_str = value_str[:27] + "..."
                    status = f"[{value_str}]"
                else:
                    status = "[not set]" if field.get('required') else "[optional]"

                menu_items.append((field_id, f"{label} {status}"))

            menu_items.append(('B', 'Back'))

            title = subsection.get('title', subsection_id)
            choice = self.ui.menu(
                f"Configure: {title}",
                menu_items,
                title=title
            )

            if choice is None or choice == 'B':
                return 'back'

            selected_field = next((f for f in fields if f.get('id') == choice), None)
            if selected_field:
                self.field_renderer.render_field(selected_field)

    def _copy_section_fields(self, source_section: str, target_section: str, field_ids: List[str]) -> None:
        """Copy field values from one section to another.

        Args:
            source_section: Source section ID (e.g., 'stepper_x')
            target_section: Target section ID (e.g., 'stepper_y')
            field_ids: List of field IDs to copy (e.g., ['driver_type', 'microsteps'])
        """
        for field_id in field_ids:
            source_key = f"{source_section}.{field_id}"
            target_key = f"{target_section}.{field_id}"
            value = self._get_state_value(source_key)
            if value is not None:
                self.state.set(target_key, value)

    def _apply_implications(self) -> None:
        """Apply auto-set values based on current state."""
        state_dict = self.state.get_all()
        implications = self.skeleton.get_active_implications(state_dict)

        for key, value in implications.items():
            # Only set if not already set or if it's an auto-select
            current = self._get_state_value(key)
            if current is None or current == "":
                self.state.set(key, value)

    def _show_warnings(self, section_id: str) -> None:
        """Show any warnings related to the current configuration.

        Args:
            section_id: Section that was just configured
        """
        state_dict = self.state.get_all()
        validator = SkeletonValidator(self.skeleton, state_dict)

        conflicts = validator.check_conflicts()
        warnings = [c for c in conflicts if c.type == 'warning']

        if warnings:
            warning_text = "Configuration warnings:\n\n"
            for w in warnings:
                warning_text += f"- {w.message}\n"
            self.ui.msgbox(warning_text, title="Warnings")

    def validate_section(self, section_id: str) -> bool:
        """Validate a section and show errors.

        Args:
            section_id: Section to validate

        Returns:
            True if valid, False if there are errors
        """
        state_dict = self.state.get_all()
        validator = SkeletonValidator(self.skeleton, state_dict)

        results = validator.validate_section(section_id)
        errors = [r for r in results if not r.valid]

        if errors:
            error_text = "Please fix the following:\n\n"
            for e in errors:
                error_text += f"- {e.message}\n"
            self.ui.msgbox(error_text, title="Validation Errors")
            return False

        return True

    def validate_all(self) -> bool:
        """Run full validation and show results.

        Returns:
            True if valid, False if there are errors
        """
        state_dict = self.state.get_all()
        validator = SkeletonValidator(self.skeleton, state_dict)

        result = validator.validate_all()

        if not result['valid']:
            error_text = "Configuration has errors:\n\n"
            for e in result['errors']:
                error_text += f"- {e}\n"
            if result['incomplete_sections']:
                error_text += "\nIncomplete sections:\n"
                for s in result['incomplete_sections']:
                    error_text += f"- {s}\n"
            self.ui.msgbox(error_text, title="Validation Failed")
            return False

        if result['warnings']:
            warning_text = "Configuration warnings:\n\n"
            for w in result['warnings']:
                warning_text += f"- {w}\n"
            self.ui.msgbox(warning_text, title="Warnings")

        return True
