#!/usr/bin/env python3
from pathlib import Path
state_file = Path('.wizard-state')
state = {}
with open(state_file) as f:
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            state[key] = value
print('probe_serial:', repr(state.get('probe_serial')))
print('mcu_serial:', repr(state.get('mcu_serial')))
print('toolboard_serial:', repr(state.get('toolboard_serial')))

