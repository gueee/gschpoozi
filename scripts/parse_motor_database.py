#!/usr/bin/env python3
"""Parse klipper_tmc_autotune motor_database.cfg and convert to JSON"""

import re
import json
import sys

def parse_motor_database(input_file):
    motors_by_vendor = {}
    current_vendor = None
    current_motor = None

    with open(input_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # Check if it's a vendor header
            if line.startswith('###') and line.endswith('###'):
                vendor_name = line.replace('###', '').strip()
                # Clean up vendor name
                vendor_name = vendor_name.replace(' Motors', '').replace(' motors', '')
                if vendor_name == 'Other manufacturers':
                    vendor_name = 'Other'
                current_vendor = vendor_name
                if current_vendor and current_vendor not in motors_by_vendor:
                    motors_by_vendor[current_vendor] = []
                continue

            # Skip comment lines
            if line.startswith('#'):
                continue

            # Check for motor_constants section
            match = re.match(r'\[motor_constants\s+([^\]]+)\]', line)
            if match:
                motor_id = match.group(1)
                # Create a readable name from the ID
                motor_name = motor_id.replace('-', ' ').replace('_', ' ').title()
                current_motor = {
                    'id': motor_id,
                    'name': motor_name
                }
                if current_vendor:
                    motors_by_vendor[current_vendor].append(current_motor)
                continue

            # Parse motor properties
            if current_motor and ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                # Try to convert numeric values
                try:
                    if '.' in value:
                        value = float(value)
                    else:
                        value = int(value)
                except ValueError:
                    pass
                current_motor[key] = value

    # Remove empty vendors
    cleaned_vendors = {k: v for k, v in motors_by_vendor.items() if k and v}

    return cleaned_vendors

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: parse_motor_database.py <motor_database.cfg>", file=sys.stderr)
        sys.exit(1)

    input_file = sys.argv[1]
    motors = parse_motor_database(input_file)

    print(json.dumps(motors, indent=2))

