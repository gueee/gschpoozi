"""
ui.py - Whiptail UI wrapper for gschpoozi wizard

Provides a clean abstraction over whiptail dialogs.
Can be swapped for different implementations if needed.
"""

import subprocess
import shutil
from typing import List, Tuple, Optional, Any


class WizardUI:
    """Whiptail-based UI for the configuration wizard."""

    def __init__(self, title: str = "gschpoozi", backtitle: str = "Klipper Configuration Wizard"):
        self.title = title
        self.backtitle = backtitle
        self._check_whiptail()

    def _check_whiptail(self) -> None:
        """Verify whiptail is available."""
        if not shutil.which("whiptail"):
            raise RuntimeError(
                "whiptail not found. Install with: sudo apt-get install whiptail"
            )

    def _run(self, args: List[str], input_text: str = None) -> Tuple[int, str]:
        """Run whiptail command and return (returncode, output)."""
        cmd = ["whiptail", "--backtitle", self.backtitle] + args

        # whiptail needs direct terminal access for its UI
        # It writes the UI to /dev/tty and returns selection via stderr
        try:
            with open("/dev/tty", "r+") as tty:
                result = subprocess.run(
                    cmd,
                    stdin=tty,
                    stdout=tty,
                    stderr=subprocess.PIPE,
                    text=True
                )
                # whiptail outputs selection to stderr
                return result.returncode, result.stderr.strip()
        except OSError:
            # Fallback if /dev/tty not available (unlikely on Linux)
            result = subprocess.run(
                cmd,
                stderr=subprocess.PIPE,
                text=True
            )
            return result.returncode, result.stderr.strip()

    def menu(
        self,
        text: str,
        items: List[Tuple[str, str]],
        title: str = None,
        height: int = 0,
        width: int = 0,
        menu_height: int = 0
    ) -> Optional[str]:
        """
        Display a menu and return selected item tag.

        Args:
            text: Menu description text
            items: List of (tag, description) tuples
            title: Optional title override
            height/width/menu_height: Dimensions (0 = auto)

        Returns:
            Selected tag or None if cancelled
        """
        # Auto-calculate dimensions if not specified
        # Use generous defaults - modern terminals are large!
        if height == 0:
            height = min(len(items) + 15, 50)
        if width == 0:
            max_desc = max(len(d) for _, d in items) if items else 40
            width = min(max(100, max_desc + 30), 140)
        if menu_height == 0:
            menu_height = min(len(items), 35)

        args = [
            "--title", title or self.title,
            "--menu", text,
            str(height), str(width), str(menu_height)
        ]

        for tag, desc in items:
            args.extend([tag, desc])

        code, output = self._run(args)

        if code == 0:
            return output
        return None  # Cancelled or error

    def radiolist(
        self,
        text: str,
        items: List[Tuple[str, str, bool]],
        title: str = None,
        height: int = 0,
        width: int = 0,
        list_height: int = 0
    ) -> Optional[str]:
        """
        Display a radiolist (single selection with ON/OFF states).

        Args:
            items: List of (tag, description, is_selected) tuples

        Returns:
            Selected tag or None if cancelled
        """
        # whiptail radiolist behaves poorly if multiple entries are pre-selected (ON).
        # Enforce exactly one ON item: keep the first ON, or default to first item if none.
        if items:
            first_on = None
            for i, (_, _, selected) in enumerate(items):
                if selected:
                    first_on = i
                    break
            # If no item was pre-selected, select the first one
            if first_on is None:
                first_on = 0
            items = [
                (tag, desc, (idx == first_on))
                for idx, (tag, desc, _sel) in enumerate(items)
            ]

        # Use generous defaults - modern terminals are large!
        if height == 0:
            height = min(len(items) + 15, 50)
        if width == 0:
            max_desc = max(len(d) for _, d, _ in items) if items else 40
            width = min(max(100, max_desc + 30), 140)
        if list_height == 0:
            list_height = min(len(items), 35)

        args = [
            "--title", title or self.title,
            "--radiolist", text,
            str(height), str(width), str(list_height)
        ]

        for tag, desc, selected in items:
            args.extend([tag, desc, "ON" if selected else "OFF"])

        code, output = self._run(args)
        return output if code == 0 else None

    def checklist(
        self,
        text: str,
        items: List[Tuple[str, str, bool]],
        title: str = None,
        height: int = 0,
        width: int = 0,
        list_height: int = 0
    ) -> Optional[List[str]]:
        """
        Display a checklist (multiple selection).

        Returns:
            List of selected tags or None if cancelled
        """
        # Use generous defaults - modern terminals are large!
        if height == 0:
            height = min(len(items) + 15, 50)
        if width == 0:
            max_desc = max(len(d) for _, d, _ in items) if items else 40
            width = min(max(100, max_desc + 30), 140)
        if list_height == 0:
            list_height = min(len(items), 35)

        args = [
            "--title", title or self.title,
            "--checklist", text,
            str(height), str(width), str(list_height)
        ]

        for tag, desc, selected in items:
            args.extend([tag, desc, "ON" if selected else "OFF"])

        code, output = self._run(args)

        if code == 0 and output:
            # Output is space-separated quoted tags: "tag1" "tag2"
            # Parse them
            tags = []
            for part in output.split('" "'):
                tags.append(part.strip('"'))
            return tags
        return None if code != 0 else []

    def inputbox(
        self,
        text: str,
        default: str = "",
        title: str = None,
        height: int = 8,
        width: int = 60
    ) -> Optional[str]:
        """
        Display an input box.

        Returns:
            Entered text or None if cancelled
        """
        args = [
            "--title", title or self.title,
            "--inputbox", text,
            # Whiptail incorrectly treats a default value that starts with '-' (e.g. '-4')
            # as a CLI option unless we end option parsing explicitly.
            str(height), str(width), "--", default
        ]

        code, output = self._run(args)
        return output if code == 0 else None

    def passwordbox(
        self,
        text: str,
        title: str = None,
        height: int = 8,
        width: int = 60
    ) -> Optional[str]:
        """Display a password input box (masked input)."""
        args = [
            "--title", title or self.title,
            "--passwordbox", text,
            str(height), str(width)
        ]

        code, output = self._run(args)
        return output if code == 0 else None

    def yesno(
        self,
        text: str,
        title: str = None,
        height: int = 8,
        width: int = 60,
        default_no: bool = False
    ) -> bool:
        """
        Display a yes/no dialog.

        Returns:
            True for Yes, False for No
        """
        args = [
            "--title", title or self.title,
            "--yesno", text,
            str(height), str(width)
        ]

        if default_no:
            args.insert(0, "--defaultno")

        code, _ = self._run(args)
        return code == 0

    def msgbox(
        self,
        text: str,
        title: str = None,
        height: int = 8,
        width: int = 60
    ) -> None:
        """Display a message box."""
        args = [
            "--title", title or self.title,
            "--msgbox", text,
            str(height), str(width)
        ]
        self._run(args)

    def infobox(
        self,
        text: str,
        title: str = None,
        height: int = 8,
        width: int = 60
    ) -> None:
        """Display an info box (no OK button, disappears immediately)."""
        args = [
            "--title", title or self.title,
            "--infobox", text,
            str(height), str(width)
        ]
        self._run(args)

    def gauge(
        self,
        text: str,
        percent: int,
        title: str = None,
        height: int = 8,
        width: int = 60
    ) -> None:
        """Display a progress gauge."""
        args = [
            "--title", title or self.title,
            "--gauge", text,
            str(height), str(width), str(percent)
        ]
        self._run(args)

    def textbox(
        self,
        filepath: str,
        title: str = None,
        height: int = 20,
        width: int = 70
    ) -> None:
        """Display contents of a file in a scrollable box."""
        args = [
            "--title", title or self.title,
            "--textbox", filepath,
            str(height), str(width)
        ]
        self._run(args)


# Convenience function
def create_ui() -> WizardUI:
    """Create and return a WizardUI instance."""
    return WizardUI()

