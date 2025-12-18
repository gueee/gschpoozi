#!/usr/bin/env python3
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_ROOT = SCRIPT_DIR.parent

WIZARD_STATE_FILE = REPO_ROOT / '.wizard-state'
print('Looking for:', WIZARD_STATE_FILE)
print('Exists:', WIZARD_STATE_FILE.exists())

state = {}
if WIZARD_STATE_FILE.exists():
    with open(WIZARD_STATE_FILE) as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                state[key] = value

print('probe_serial from wizard_state:', repr(state.get('probe_serial')))

