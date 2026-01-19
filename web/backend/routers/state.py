"""
API endpoints for wizard state management.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# State filename (same as CLI wizard)
STATE_FILENAME = ".gschpoozi_state.json"


def get_default_state_dir() -> Path:
    """
    Get the default state directory.

    Priority:
    1. GSCHPOOZI_STATE_DIR environment variable
    2. Repo root (to match CLI wizard behavior)

    The CLI wizard stores state in the repo root, so we align with that
    to allow seamless state transfer between web and CLI wizards.
    """
    # Check environment variable first
    env_dir = os.environ.get("GSCHPOOZI_STATE_DIR")
    if env_dir:
        return Path(env_dir)

    # Default to repo root (web/backend/routers -> web/backend -> web -> repo root)
    repo_root = Path(__file__).parent.parent.parent.parent
    return repo_root


# Computed default - use function to allow runtime override via env var
DEFAULT_STATE_DIR = get_default_state_dir()


class StateResponse(BaseModel):
    """Response containing wizard state."""
    state: Dict[str, Any]
    metadata: Dict[str, Any] = {}


class SaveStateRequest(BaseModel):
    """Request to save wizard state."""
    state: Dict[str, Any]
    state_dir: Optional[str] = None  # Override default location


class SaveStateResponse(BaseModel):
    """Response from saving state."""
    success: bool
    path: str
    message: str = ""


class BackupInfo(BaseModel):
    """Information about a state backup."""
    filename: str
    created: str
    size: int


class BackupListResponse(BaseModel):
    """Response listing available backups."""
    backups: List[BackupInfo]


def flatten_state(nested: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """
    Flatten nested state dict to dot-notation keys.
    {"stepper_x": {"motor_port": "M0"}} -> {"stepper_x.motor_port": "M0"}
    """
    result = {}
    for key, value in nested.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(flatten_state(value, full_key))
        else:
            result[full_key] = value
    return result


@router.get("/state")
async def get_state(state_dir: Optional[str] = None) -> StateResponse:
    """
    Load saved wizard state from disk.

    Args:
        state_dir: Optional path to look for state file
    """
    search_dir = Path(state_dir) if state_dir else DEFAULT_STATE_DIR
    state_file = search_dir / STATE_FILENAME

    if not state_file.exists():
        # Return empty state if file doesn't exist
        return StateResponse(
            state={},
            metadata={
                "version": "3.0",
                "created": datetime.now().isoformat(),
                "source": "new",
            }
        )

    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # The file stores nested config under "config" key
        config = data.get("config", {})
        wizard_meta = data.get("wizard", {})

        # Flatten to dot notation for frontend
        flat_state = flatten_state(config)

        return StateResponse(
            state=flat_state,
            metadata={
                "version": wizard_meta.get("version", "3.0"),
                "created": wizard_meta.get("created"),
                "last_modified": wizard_meta.get("last_modified"),
                "source": "file",
                "path": str(state_file),
            }
        )

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Invalid state file: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading state: {e}")


@router.post("/state")
async def save_state(request: SaveStateRequest) -> SaveStateResponse:
    """
    Save wizard state to disk.

    Creates a backup of the existing state before overwriting.
    """
    save_dir = Path(request.state_dir) if request.state_dir else DEFAULT_STATE_DIR
    state_file = save_dir / STATE_FILENAME

    try:
        # Ensure directory exists
        save_dir.mkdir(parents=True, exist_ok=True)

        # Create backup if file exists
        if state_file.exists():
            backup_name = f".gschpoozi_state.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            backup_file = save_dir / backup_name
            state_file.rename(backup_file)

        # Transform flat state to nested format for storage
        nested_state = {}
        for key, value in request.state.items():
            if value is None:
                continue
            parts = key.split(".")
            current = nested_state
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            if parts:
                current[parts[-1]] = value

        # Build full state structure
        full_state = {
            "wizard": {
                "version": "3.0",
                "created": request.state.get("created", datetime.now().isoformat()),
                "last_modified": datetime.now().isoformat(),
            },
            "config": nested_state,
        }

        # Write state file
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(full_state, f, indent=2)

        return SaveStateResponse(
            success=True,
            path=str(state_file),
            message="State saved successfully",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving state: {e}")


@router.get("/state/backups")
async def list_backups(state_dir: Optional[str] = None) -> BackupListResponse:
    """List available state backups."""
    search_dir = Path(state_dir) if state_dir else DEFAULT_STATE_DIR

    if not search_dir.exists():
        return BackupListResponse(backups=[])

    backups = []
    for f in search_dir.glob(".gschpoozi_state.backup.*.json"):
        try:
            stat = f.stat()
            backups.append(BackupInfo(
                filename=f.name,
                created=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                size=stat.st_size,
            ))
        except Exception:
            continue

    # Sort by creation time, newest first
    backups.sort(key=lambda x: x.created, reverse=True)

    return BackupListResponse(backups=backups)


@router.post("/state/restore/{backup_name}")
async def restore_backup(backup_name: str, state_dir: Optional[str] = None) -> SaveStateResponse:
    """Restore state from a backup file."""
    search_dir = Path(state_dir) if state_dir else DEFAULT_STATE_DIR
    backup_file = search_dir / backup_name
    state_file = search_dir / STATE_FILENAME

    if not backup_file.exists():
        raise HTTPException(status_code=404, detail=f"Backup not found: {backup_name}")

    try:
        # Backup current state first
        if state_file.exists():
            pre_restore_backup = f".gschpoozi_state.pre_restore.{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            state_file.rename(search_dir / pre_restore_backup)

        # Copy backup to state file
        with open(backup_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Update timestamp
        if "wizard" in data:
            data["wizard"]["last_modified"] = datetime.now().isoformat()

        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        return SaveStateResponse(
            success=True,
            path=str(state_file),
            message=f"Restored from {backup_name}",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error restoring backup: {e}")


@router.delete("/state")
async def clear_state(state_dir: Optional[str] = None) -> SaveStateResponse:
    """Clear wizard state (creates backup first)."""
    search_dir = Path(state_dir) if state_dir else DEFAULT_STATE_DIR
    state_file = search_dir / STATE_FILENAME

    if not state_file.exists():
        return SaveStateResponse(
            success=True,
            path=str(state_file),
            message="No state to clear",
        )

    try:
        # Backup before clearing
        backup_name = f".gschpoozi_state.cleared.{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        backup_file = search_dir / backup_name
        state_file.rename(backup_file)

        return SaveStateResponse(
            success=True,
            path=str(backup_file),
            message=f"State cleared. Backup saved as {backup_name}",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing state: {e}")


@router.post("/state/import")
async def import_config(config_text: str) -> StateResponse:
    """
    Import an existing Klipper config file and parse it to wizard state.

    This is the reverse engineering feature - parse printer.cfg into wizard state.
    """
    # TODO: Implement full config parsing
    # For now, return a stub showing the feature exists

    parsed_state = {}
    errors = []

    lines = config_text.strip().split('\n')
    current_section = None

    for line in lines:
        line = line.strip()

        # Skip comments and empty lines
        if not line or line.startswith('#'):
            continue

        # Section header
        if line.startswith('[') and line.endswith(']'):
            current_section = line[1:-1]
            continue

        # Key-value pair
        if ':' in line and current_section:
            key, _, value = line.partition(':')
            key = key.strip()
            value = value.strip()

            # Map to wizard state
            if current_section == 'printer':
                if key == 'kinematics':
                    parsed_state['printer.kinematics'] = value
                elif key == 'max_velocity':
                    parsed_state['printer.max_velocity'] = int(value)
                elif key == 'max_accel':
                    parsed_state['printer.max_accel'] = int(value)

            elif current_section == 'mcu':
                if key == 'serial':
                    parsed_state['mcu.main.serial'] = value

            elif current_section.startswith('stepper_'):
                axis = current_section.replace('stepper_', '')
                if key == 'microsteps':
                    parsed_state[f'stepper_{axis}.microsteps'] = int(value)
                elif key == 'rotation_distance':
                    parsed_state[f'stepper_{axis}.rotation_distance'] = float(value)

            elif current_section.startswith('tmc'):
                # Parse TMC sections like [tmc2209 stepper_x]
                parts = current_section.split()
                if len(parts) == 2:
                    driver_type = parts[0]
                    stepper = parts[1]
                    if key == 'run_current':
                        parsed_state[f'{stepper}.driver_type'] = driver_type
                        parsed_state[f'{stepper}.run_current'] = float(value)

            elif current_section == 'extruder':
                if key == 'nozzle_diameter':
                    parsed_state['extruder.nozzle_diameter'] = float(value)
                elif key == 'sensor_type':
                    parsed_state['extruder.sensor_type'] = value
                elif key == 'max_temp':
                    parsed_state['extruder.max_temp'] = int(value)

            elif current_section == 'heater_bed':
                if key == 'sensor_type':
                    parsed_state['heater_bed.sensor_type'] = value
                elif key == 'max_temp':
                    parsed_state['heater_bed.max_temp'] = int(value)

    return StateResponse(
        state=parsed_state,
        metadata={
            "source": "import",
            "parsed_sections": len(set(k.split('.')[0] for k in parsed_state.keys())),
            "notes": "Partial import - some values may need manual verification",
        }
    )

