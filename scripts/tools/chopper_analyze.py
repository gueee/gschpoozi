#!/usr/bin/env python3
"""
TMC Chopper Tuning Analyzer

Analyzes accelerometer data from chopper tuning runs and recommends
optimal driver settings for TMC5160/TMC2240 drivers.

Designed to be called from macros via gcode_shell_command.

Usage:
    python3 chopper_analyze.py [--mode MODE] [--csv-dir /tmp] [--output-dir ~/printer_data/config/chopper_results]

Modes:
    find_resonance  - Analyze speed sweep to find problem speeds
    optimize        - Analyze parameter sweep and recommend settings
    report          - Generate full report with graphs (default)

Output:
    - PNG graphs showing vibration levels per parameter set
    - JSON recommendations file with optimal settings
    - Klipper config snippet with recommended driver settings
"""

import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Try to import required libraries
try:
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend for server use
    import matplotlib.pyplot as plt
except ImportError as e:
    print(f"ERROR: Missing required library: {e}")
    print("Install with: pip3 install numpy matplotlib")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_CSV_DIR = '/tmp'
DEFAULT_OUTPUT_DIR = os.path.expanduser('~/printer_data/config/chopper_results')

# Parameter descriptions for reports
PARAM_INFO = {
    'tpfd': 'Passive Fast Decay (mid-range resonance damping)',
    'tbl': 'Comparator Blanking Time (noise immunity)',
    'toff': 'Off Time (chopper frequency)',
    'hstrt': 'Hysteresis Start (current ripple control)',
    'hend': 'Hysteresis End (current ripple control)',
}


# ─────────────────────────────────────────────────────────────────────────────
# CSV Parsing
# ─────────────────────────────────────────────────────────────────────────────

def find_chopper_csvs(csv_dir: str, axis: str = None) -> list:
    """Find chopper tuning CSV files."""
    patterns = [
        'chopper_*.csv',
        'resonance_sweep_*.csv',
    ]

    all_files = []
    for pattern in patterns:
        all_files.extend(glob.glob(os.path.join(csv_dir, pattern)))

    if axis:
        axis = axis.lower()
        all_files = [f for f in all_files if f'_{axis}_' in f.lower() or f'_{axis}.' in f.lower()]

    # Sort by modification time (newest first)
    all_files.sort(key=os.path.getmtime, reverse=True)
    return all_files


def parse_filename_params(filename: str) -> dict:
    """
    Extract chopper parameters from filename.

    Expected formats:
        chopper_x_tpfd4_tbl2_toff3_s75.csv
        chopper_y_tpfd8_tbl1_toff4_s100.csv
    """
    params = {
        'axis': None,
        'tpfd': None,
        'tbl': None,
        'toff': None,
        'hstrt': None,
        'hend': None,
        'speed': None,
    }

    basename = os.path.basename(filename).replace('.csv', '')

    # Extract axis
    axis_match = re.search(r'chopper_([xy])', basename, re.IGNORECASE)
    if axis_match:
        params['axis'] = axis_match.group(1).upper()

    # Extract parameters
    for param in ['tpfd', 'tbl', 'toff', 'hstrt', 'hend']:
        match = re.search(rf'{param}(\d+)', basename, re.IGNORECASE)
        if match:
            params[param] = int(match.group(1))

    # Extract speed
    speed_match = re.search(r's(\d+)', basename)
    if speed_match:
        params['speed'] = int(speed_match.group(1))

    return params


def parse_accel_csv(csv_path: str) -> np.ndarray:
    """
    Parse Klipper accelerometer CSV file.

    Returns array of [time, x, y, z] data.
    """
    try:
        # Klipper CSVs have header: #time,accel_x,accel_y,accel_z
        data = np.loadtxt(csv_path, delimiter=',', skiprows=1)
        return data
    except Exception as e:
        print(f"Warning: Could not parse {csv_path}: {e}")
        return None


def calculate_rms_vibration(data: np.ndarray) -> float:
    """
    Calculate RMS vibration magnitude from accelerometer data.

    Uses the vector magnitude of all three axes.
    """
    if data is None or len(data) == 0:
        return float('inf')

    # Calculate vector magnitude for each sample
    if data.ndim == 1:
        return float('inf')

    # Columns: time, x, y, z (or just x, y, z if time is separate)
    if data.shape[1] >= 4:
        x, y, z = data[:, 1], data[:, 2], data[:, 3]
    elif data.shape[1] == 3:
        x, y, z = data[:, 0], data[:, 1], data[:, 2]
    else:
        return float('inf')

    magnitude = np.sqrt(x**2 + y**2 + z**2)

    # Filter outliers (use 95th percentile)
    threshold = np.percentile(magnitude, 95)
    filtered = magnitude[magnitude <= threshold]

    if len(filtered) == 0:
        return float('inf')

    return np.sqrt(np.mean(filtered**2))


def calculate_peak_frequency(data: np.ndarray, sample_rate: float = 3200) -> float:
    """
    Calculate the dominant vibration frequency using FFT.

    Returns the frequency with highest power in the typical resonance range.
    """
    if data is None or len(data) < 100:
        return 0

    # Use magnitude
    if data.shape[1] >= 4:
        magnitude = np.sqrt(data[:, 1]**2 + data[:, 2]**2 + data[:, 3]**2)
    else:
        magnitude = np.sqrt(data[:, 0]**2 + data[:, 1]**2 + data[:, 2]**2)

    # Remove DC component
    magnitude = magnitude - np.mean(magnitude)

    # FFT
    n = len(magnitude)
    fft = np.fft.rfft(magnitude)
    freqs = np.fft.rfftfreq(n, 1.0/sample_rate)
    power = np.abs(fft)**2

    # Focus on typical resonance range (20-200 Hz)
    mask = (freqs >= 20) & (freqs <= 200)
    if not any(mask):
        return 0

    peak_idx = np.argmax(power[mask])
    return freqs[mask][peak_idx]


# ─────────────────────────────────────────────────────────────────────────────
# Analysis Functions
# ─────────────────────────────────────────────────────────────────────────────

def analyze_resonance_sweep(csv_dir: str, axis: str = 'x') -> dict:
    """
    Analyze speed sweep data to find problematic speeds.

    Returns dict with peak frequencies and problem speed ranges.
    """
    result = {
        'axis': axis.upper(),
        'success': False,
        'problem_speeds': [],
        'peak_frequency': 0,
        'data_points': [],
    }

    # Find resonance sweep file
    patterns = [
        f'resonance_sweep_{axis}*.csv',
        f'resonance_sweep_{axis.upper()}*.csv',
    ]

    files = []
    for pattern in patterns:
        files.extend(glob.glob(os.path.join(csv_dir, pattern)))

    if not files:
        print(f"No resonance sweep files found for {axis} axis")
        return result

    # Use most recent file
    csv_path = max(files, key=os.path.getmtime)
    print(f"Analyzing resonance sweep: {csv_path}")

    data = parse_accel_csv(csv_path)
    if data is None:
        return result

    result['peak_frequency'] = calculate_peak_frequency(data)
    result['rms_vibration'] = calculate_rms_vibration(data)
    result['success'] = True

    return result


def analyze_parameter_sweep(csv_dir: str, axis: str = 'x') -> dict:
    """
    Analyze chopper parameter test data and find optimal settings.

    Returns dict with ranked parameter combinations and recommendations.
    """
    result = {
        'axis': axis.upper(),
        'success': False,
        'tests': [],
        'best': None,
        'recommendations': {},
    }

    # Find all chopper test files for this axis
    files = find_chopper_csvs(csv_dir, axis)

    if not files:
        print(f"No chopper test files found for {axis} axis in {csv_dir}")
        return result

    print(f"Found {len(files)} chopper test files for {axis.upper()} axis")

    # Analyze each test file
    for csv_path in files:
        params = parse_filename_params(csv_path)
        if params['axis'] and params['axis'].lower() != axis.lower():
            continue

        data = parse_accel_csv(csv_path)
        if data is None:
            continue

        rms = calculate_rms_vibration(data)
        peak_freq = calculate_peak_frequency(data)

        test_result = {
            'file': os.path.basename(csv_path),
            'params': params,
            'rms_vibration': round(rms, 2),
            'peak_frequency': round(peak_freq, 1),
        }
        result['tests'].append(test_result)

        print(f"  TPFD={params['tpfd']:2} TBL={params['tbl']} "
              f"TOFF={params['toff']} -> RMS={rms:.2f}")

    if not result['tests']:
        return result

    # Sort by RMS vibration (lower is better)
    result['tests'].sort(key=lambda x: x['rms_vibration'])

    # Best result
    best = result['tests'][0]
    result['best'] = best
    result['success'] = True

    # Generate recommendations
    result['recommendations'] = {
        'tpfd': best['params']['tpfd'],
        'tbl': best['params']['tbl'],
        'toff': best['params']['toff'],
        'hstrt': best['params']['hstrt'],
        'hend': best['params']['hend'],
        'improvement': calculate_improvement(result['tests']),
    }

    return result


def calculate_improvement(tests: list) -> float:
    """Calculate vibration improvement as percentage."""
    if len(tests) < 2:
        return 0

    # Compare best to worst
    best_rms = tests[0]['rms_vibration']
    worst_rms = tests[-1]['rms_vibration']

    if worst_rms == 0:
        return 0

    return round((1 - best_rms / worst_rms) * 100, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Report Generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_comparison_graph(result: dict, output_path: str) -> None:
    """Generate bar chart comparing parameter combinations."""
    if not result.get('tests'):
        return

    tests = result['tests'][:10]  # Top 10 results

    fig, ax = plt.subplots(figsize=(12, 6))

    # Create labels from parameters
    labels = []
    for t in tests:
        p = t['params']
        labels.append(f"TPFD={p['tpfd']}\nTBL={p['tbl']}")

    rms_values = [t['rms_vibration'] for t in tests]

    # Color bars: best is green, worst is red
    colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(tests)))

    bars = ax.bar(range(len(tests)), rms_values, color=colors)

    ax.set_xlabel('Parameter Combination')
    ax.set_ylabel('RMS Vibration')
    ax.set_title(f"TMC Chopper Tuning Results - {result['axis']} Axis\n"
                 f"(Lower is Better)")
    ax.set_xticks(range(len(tests)))
    ax.set_xticklabels(labels, fontsize=8)

    # Highlight best result
    bars[0].set_edgecolor('green')
    bars[0].set_linewidth(3)

    # Add value labels on bars
    for bar, val in zip(bars, rms_values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                f'{val:.1f}', ha='center', va='bottom', fontsize=8)

    # Add timestamp
    ax.text(0.02, 0.98, datetime.now().strftime('%Y-%m-%d %H:%M'),
            transform=ax.transAxes, fontsize=8, verticalalignment='top', alpha=0.5)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Comparison graph saved: {output_path}")


def generate_config_snippet(result: dict) -> str:
    """Generate Klipper config snippet with recommended settings."""
    if not result.get('recommendations'):
        return ""

    rec = result['recommendations']
    axis = result['axis'].lower()

    snippet = f"""
# ═══════════════════════════════════════════════════════════════════════════════
# TMC Chopper Tuning Results - {result['axis']} Axis
# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
# Vibration improvement: {rec.get('improvement', 0):.1f}%
# ═══════════════════════════════════════════════════════════════════════════════

# Add these to your [tmc5160 stepper_{axis}] or [tmc2240 stepper_{axis}] section:
#
# driver_tpfd: {rec.get('tpfd', 0)}
# driver_tbl: {rec.get('tbl', 2)}
# driver_toff: {rec.get('toff', 3)}
# driver_hstrt: {rec.get('hstrt', 5)}
# driver_hend: {rec.get('hend', 3)}
#
# Or use SET_TMC_FIELD to apply at runtime:
# SET_TMC_FIELD STEPPER=stepper_{axis} FIELD=tpfd VALUE={rec.get('tpfd', 0)}
# SET_TMC_FIELD STEPPER=stepper_{axis} FIELD=tbl VALUE={rec.get('tbl', 2)}
# SET_TMC_FIELD STEPPER=stepper_{axis} FIELD=toff VALUE={rec.get('toff', 3)}
# SET_TMC_FIELD STEPPER=stepper_{axis} FIELD=hstrt VALUE={rec.get('hstrt', 5)}
# SET_TMC_FIELD STEPPER=stepper_{axis} FIELD=hend VALUE={rec.get('hend', 3)}
"""
    return snippet


def print_results(result: dict) -> None:
    """Print analysis results to console."""
    print(f"\n{'='*60}")
    print(f"TMC CHOPPER TUNING RESULTS - {result['axis']} AXIS")
    print(f"{'='*60}")

    if not result.get('success'):
        print("Analysis failed - no valid data found")
        return

    if result.get('best'):
        best = result['best']
        params = best['params']

        print(f"\nBest configuration found:")
        print(f"  TPFD:  {params.get('tpfd', 'N/A'):3}  ({PARAM_INFO.get('tpfd', '')})")
        print(f"  TBL:   {params.get('tbl', 'N/A'):3}  ({PARAM_INFO.get('tbl', '')})")
        print(f"  TOFF:  {params.get('toff', 'N/A'):3}  ({PARAM_INFO.get('toff', '')})")
        print(f"  HSTRT: {params.get('hstrt', 'N/A'):3}  ({PARAM_INFO.get('hstrt', '')})")
        print(f"  HEND:  {params.get('hend', 'N/A'):3}  ({PARAM_INFO.get('hend', '')})")
        print(f"\n  RMS Vibration: {best['rms_vibration']:.2f}")

        if result.get('recommendations', {}).get('improvement'):
            print(f"  Improvement: {result['recommendations']['improvement']:.1f}% reduction")

    if result.get('tests'):
        print(f"\nAll {len(result['tests'])} tests ranked by vibration level:")
        for i, test in enumerate(result['tests'][:5], 1):
            p = test['params']
            print(f"  {i}. TPFD={p.get('tpfd', '?'):2} TBL={p.get('tbl', '?')} "
                  f"TOFF={p.get('toff', '?')} -> RMS={test['rms_vibration']:.2f}")

        if len(result['tests']) > 5:
            print(f"  ... and {len(result['tests']) - 5} more")


# ─────────────────────────────────────────────────────────────────────────────
# Main Entry Point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Analyze TMC chopper tuning data and generate recommendations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('--mode', choices=['find_resonance', 'optimize', 'report'],
                        default='report',
                        help='Analysis mode (default: report)')
    parser.add_argument('--axis', choices=['x', 'y', 'X', 'Y', 'both'],
                        default='both',
                        help='Axis to analyze (default: both)')
    parser.add_argument('--csv-dir', default=DEFAULT_CSV_DIR,
                        help=f'Directory containing CSV files (default: {DEFAULT_CSV_DIR})')
    parser.add_argument('--output-dir', default=DEFAULT_OUTPUT_DIR,
                        help=f'Output directory for results (default: {DEFAULT_OUTPUT_DIR})')

    args = parser.parse_args()

    # Expand paths
    csv_dir = os.path.expanduser(args.csv_dir)
    output_dir = os.path.expanduser(args.output_dir)

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    print(f"TMC Chopper Tuning Analyzer")
    print(f"Mode: {args.mode}")
    print(f"CSV directory: {csv_dir}")
    print(f"Output directory: {output_dir}")

    results = {}
    axes = ['x', 'y'] if args.axis.lower() == 'both' else [args.axis.lower()]

    for axis in axes:
        print(f"\n{'─'*60}")
        print(f"Analyzing {axis.upper()} axis...")
        print(f"{'─'*60}")

        if args.mode == 'find_resonance':
            result = analyze_resonance_sweep(csv_dir, axis)
        else:
            result = analyze_parameter_sweep(csv_dir, axis)

        results[axis.upper()] = result

        # Generate outputs
        if result.get('success'):
            print_results(result)

            # Generate graph
            graph_path = os.path.join(output_dir, f'chopper_{axis}_comparison.png')
            generate_comparison_graph(result, graph_path)
            result['graph'] = graph_path

            # Generate config snippet
            snippet = generate_config_snippet(result)
            if snippet:
                snippet_path = os.path.join(output_dir, f'chopper_{axis}_config.txt')
                with open(snippet_path, 'w') as f:
                    f.write(snippet)
                print(f"Config snippet saved: {snippet_path}")

    # Save combined results
    json_path = os.path.join(output_dir, 'chopper_results.json')
    with open(json_path, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'mode': args.mode,
            'results': results,
        }, f, indent=2, default=str)

    print(f"\n{'='*60}")
    print(f"Analysis complete!")
    print(f"{'='*60}")
    print(f"Results saved to: {output_dir}")
    print(f"  - chopper_results.json (machine-readable)")
    for axis in axes:
        if results.get(axis.upper(), {}).get('success'):
            print(f"  - chopper_{axis}_comparison.png (visual)")
            print(f"  - chopper_{axis}_config.txt (Klipper config)")


if __name__ == '__main__':
    main()
