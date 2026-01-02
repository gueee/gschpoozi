#!/usr/bin/env python3
"""
Lightweight Input Shaper Graph Generator

Generates resonance graphs and shaper recommendations from Klipper's TEST_RESONANCES output.
Designed to be called from macros via gcode_shell_command.

Usage:
    python3 shaper_graphs.py axis [--csv-dir /tmp] [--output-dir ~/printer_data/config/plots]
    python3 shaper_graphs.py belts [--csv-dir /tmp] [--output-dir ~/printer_data/config/plots]

Arguments:
    axis   - Process axis resonance data (X or Y) and generate shaper recommendations
    belts  - Compare belt tensions (X vs Y at low frequency)

Output:
    - PNG graph files in output directory
    - JSON recommendations file for APPLY_SHAPER macro
    - Console output with recommendations
"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Try to import Klipper's calibration module
KLIPPER_PATH = os.environ.get('KLIPPER_PATH', os.path.expanduser('~/klipper'))
sys.path.insert(0, os.path.join(KLIPPER_PATH, 'scripts'))

try:
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend for server use
    import matplotlib.pyplot as plt
except ImportError as e:
    print(f"ERROR: Missing required library: {e}")
    print("Install with: pip3 install numpy matplotlib")
    sys.exit(1)

# Klipper's shaper calibration imports
try:
    from calibrate_shaper import ShaperCalibrate
except ImportError:
    # Fallback: minimal implementation if Klipper scripts not available
    ShaperCalibrate = None
    print("WARNING: Klipper calibrate_shaper.py not found, using basic analysis")


# ─────────────────────────────────────────────────────────────────────────────
# Shaper types and their characteristics
# ─────────────────────────────────────────────────────────────────────────────
SHAPER_TYPES = {
    'zv': {'name': 'ZV', 'smoothing': 'lowest', 'vibration_reduction': 'low'},
    'mzv': {'name': 'MZV', 'smoothing': 'low', 'vibration_reduction': 'medium'},
    'zvd': {'name': 'ZVD', 'smoothing': 'medium', 'vibration_reduction': 'medium'},
    'ei': {'name': 'EI', 'smoothing': 'medium', 'vibration_reduction': 'high'},
    '2hump_ei': {'name': '2HUMP_EI', 'smoothing': 'high', 'vibration_reduction': 'very high'},
    '3hump_ei': {'name': '3HUMP_EI', 'smoothing': 'highest', 'vibration_reduction': 'maximum'},
}


def find_latest_csv(csv_dir: str, axis: str) -> str:
    """Find the most recent resonance CSV file for a given axis."""
    patterns = [
        f'resonances_{axis.lower()}_*.csv',
        f'calibration_data_{axis.lower()}_*.csv',
        f'raw_data_{axis.lower()}_*.csv',
    ]

    all_files = []
    for pattern in patterns:
        all_files.extend(glob.glob(os.path.join(csv_dir, pattern)))

    if not all_files:
        raise FileNotFoundError(f"No resonance CSV files found for axis {axis} in {csv_dir}")

    # Return most recently modified
    return max(all_files, key=os.path.getmtime)


def parse_csv_data(csv_path: str) -> tuple:
    """Parse resonance CSV file and return frequency and power spectral density data."""
    data = np.loadtxt(csv_path, delimiter=',', skiprows=1)

    # CSV format: freq, psd_x, psd_y, psd_z (or just freq, psd for older format)
    freq = data[:, 0]

    if data.shape[1] >= 4:
        # Multi-axis format: use sum of all axes
        psd = np.sqrt(data[:, 1]**2 + data[:, 2]**2 + data[:, 3]**2)
    else:
        # Single axis format
        psd = data[:, 1]

    return freq, psd


def find_resonance_peak(freq: np.ndarray, psd: np.ndarray) -> tuple:
    """Find the main resonance frequency peak."""
    # Focus on typical resonance range (20-150 Hz)
    mask = (freq >= 20) & (freq <= 150)
    freq_range = freq[mask]
    psd_range = psd[mask]

    if len(psd_range) == 0:
        return 0, 0

    peak_idx = np.argmax(psd_range)
    peak_freq = freq_range[peak_idx]
    peak_power = psd_range[peak_idx]

    return peak_freq, peak_power


def calculate_shaper_recommendations(freq: np.ndarray, psd: np.ndarray,
                                     max_accel: float = 10000) -> list:
    """
    Calculate recommended input shaper settings.

    Uses Klipper's native algorithm if available, otherwise falls back to
    basic peak detection with standard shaper frequency multipliers.
    """
    recommendations = []
    peak_freq, _ = find_resonance_peak(freq, psd)

    if peak_freq < 20:
        print("WARNING: No clear resonance peak found in typical range")
        return recommendations

    if ShaperCalibrate is not None:
        # Use Klipper's native calibration
        try:
            calibrate = ShaperCalibrate(None)
            # Create calibration data in the format Klipper expects
            calibration_data = [(freq, psd)]

            for shaper_type in ['zv', 'mzv', 'zvd', 'ei', '2hump_ei', '3hump_ei']:
                try:
                    best_freq, vals, vibrs, smoothing = \
                        calibrate.find_best_shaper(calibration_data, max_accel, shaper_type)

                    # vals contains (shaper_freq, vibration, smoothing, score) or similar
                    if best_freq > 0:
                        recommendations.append({
                            'type': shaper_type,
                            'freq': round(best_freq, 1),
                            'vibration': round(min(vibrs) * 100, 1) if vibrs else 0,
                            'smoothing': round(smoothing, 4) if smoothing else 0,
                            'max_accel': int(max_accel),
                        })
                except Exception as e:
                    print(f"  Warning: Could not calculate {shaper_type}: {e}")

        except Exception as e:
            print(f"Klipper calibration failed, using basic method: {e}")
            ShaperCalibrate = None  # Fall through to basic method

    if not recommendations:
        # Basic fallback: use peak frequency with standard multipliers
        # These multipliers are approximations for each shaper type
        shaper_multipliers = {
            'zv': 1.0,
            'mzv': 0.85,
            'zvd': 0.75,
            'ei': 0.75,
            '2hump_ei': 0.65,
            '3hump_ei': 0.55,
        }

        for shaper_type, mult in shaper_multipliers.items():
            shaper_freq = peak_freq * mult
            recommendations.append({
                'type': shaper_type,
                'freq': round(shaper_freq, 1),
                'vibration': 0,  # Unknown without proper calculation
                'smoothing': 0,
                'max_accel': int(max_accel),
                'note': 'basic_calculation'
            })

    return recommendations


def generate_axis_graph(freq: np.ndarray, psd: np.ndarray, axis: str,
                        output_path: str, recommendations: list = None) -> None:
    """Generate resonance graph for a single axis."""
    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot PSD
    ax.plot(freq, psd, 'b-', linewidth=1.5, label='Vibration Power')

    # Find and mark peak
    peak_freq, peak_power = find_resonance_peak(freq, psd)
    if peak_freq > 0:
        ax.axvline(x=peak_freq, color='r', linestyle='--', alpha=0.7,
                   label=f'Peak: {peak_freq:.1f} Hz')
        ax.plot(peak_freq, peak_power, 'ro', markersize=10)

    # Mark recommended shaper frequency if available
    if recommendations:
        best = recommendations[0]  # First is usually MZV or best overall
        ax.axvline(x=best['freq'], color='g', linestyle=':', alpha=0.7,
                   label=f"Recommended ({best['type'].upper()}): {best['freq']:.1f} Hz")

    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('Power Spectral Density')
    ax.set_title(f'Input Shaper Calibration - {axis.upper()} Axis')
    ax.set_xlim(0, 200)
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper right')

    # Add timestamp
    ax.text(0.02, 0.98, datetime.now().strftime('%Y-%m-%d %H:%M'),
            transform=ax.transAxes, fontsize=8, verticalalignment='top', alpha=0.5)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Graph saved: {output_path}")


def generate_belt_comparison_graph(freq_x: np.ndarray, psd_x: np.ndarray,
                                   freq_y: np.ndarray, psd_y: np.ndarray,
                                   output_path: str) -> dict:
    """
    Generate belt tension comparison graph for CoreXY.

    For properly tensioned belts, X and Y should have similar resonance peaks.
    Significant difference indicates belt tension imbalance.
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    # Focus on belt frequency range (typically 50-150 Hz for belts)
    belt_range = (freq_x >= 30) & (freq_x <= 180)

    # Plot X axis (Belt A in CoreXY terms)
    ax1.plot(freq_x, psd_x, 'b-', linewidth=1.5, label='X Axis (Belt A+B)')
    peak_x, _ = find_resonance_peak(freq_x, psd_x)
    if peak_x > 0:
        ax1.axvline(x=peak_x, color='r', linestyle='--', alpha=0.7,
                    label=f'Peak: {peak_x:.1f} Hz')
    ax1.set_ylabel('Power (X)')
    ax1.set_title('Belt Tension Comparison - CoreXY')
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper right')

    # Plot Y axis (Belt A-B in CoreXY terms)
    ax2.plot(freq_y, psd_y, 'g-', linewidth=1.5, label='Y Axis (Belt A-B)')
    peak_y, _ = find_resonance_peak(freq_y, psd_y)
    if peak_y > 0:
        ax2.axvline(x=peak_y, color='r', linestyle='--', alpha=0.7,
                    label=f'Peak: {peak_y:.1f} Hz')
    ax2.set_xlabel('Frequency (Hz)')
    ax2.set_ylabel('Power (Y)')
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='upper right')

    ax2.set_xlim(0, 200)

    # Calculate and display belt difference
    freq_diff = abs(peak_x - peak_y) if peak_x > 0 and peak_y > 0 else 0
    freq_ratio = (peak_x / peak_y * 100 - 100) if peak_x > 0 and peak_y > 0 else 0

    status = "GOOD" if freq_diff < 3 else ("ACCEPTABLE" if freq_diff < 6 else "NEEDS ADJUSTMENT")
    status_color = 'green' if freq_diff < 3 else ('orange' if freq_diff < 6 else 'red')

    summary_text = (
        f"X Peak: {peak_x:.1f} Hz  |  Y Peak: {peak_y:.1f} Hz\n"
        f"Difference: {freq_diff:.1f} Hz ({freq_ratio:+.1f}%)\n"
        f"Status: {status}"
    )

    fig.text(0.5, 0.02, summary_text, ha='center', fontsize=10,
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    # Timestamp
    fig.text(0.02, 0.98, datetime.now().strftime('%Y-%m-%d %H:%M'),
             fontsize=8, verticalalignment='top', alpha=0.5)

    plt.tight_layout()
    plt.subplots_adjust(bottom=0.15)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Belt comparison graph saved: {output_path}")

    return {
        'peak_x': peak_x,
        'peak_y': peak_y,
        'difference_hz': round(freq_diff, 1),
        'difference_percent': round(freq_ratio, 1),
        'status': status,
    }


def process_axis(args) -> dict:
    """Process single axis resonance data."""
    csv_dir = os.path.expanduser(args.csv_dir)
    output_dir = os.path.expanduser(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    result = {'axis': args.axis.upper(), 'success': False}

    try:
        csv_path = find_latest_csv(csv_dir, args.axis)
        print(f"Processing: {csv_path}")

        freq, psd = parse_csv_data(csv_path)

        # Calculate recommendations
        recommendations = calculate_shaper_recommendations(freq, psd, args.max_accel)

        if recommendations:
            # Sort by vibration reduction (lower is better), prefer MZV if close
            def sort_key(r):
                type_priority = {'mzv': 0, 'ei': 1, 'zvd': 2, 'zv': 3, '2hump_ei': 4, '3hump_ei': 5}
                return (r.get('vibration', 0), type_priority.get(r['type'], 99))

            recommendations.sort(key=sort_key)

            result['recommendations'] = recommendations
            result['best'] = recommendations[0]

            # Print recommendations
            print(f"\n{'='*60}")
            print(f"INPUT SHAPER RECOMMENDATIONS - {args.axis.upper()} AXIS")
            print(f"{'='*60}")
            print(f"\nBest recommendation: {result['best']['type'].upper()} @ {result['best']['freq']} Hz")
            print(f"\nAll options:")
            for r in recommendations:
                print(f"  {r['type'].upper():12} freq={r['freq']:5.1f} Hz")

        # Generate graph
        graph_path = os.path.join(output_dir, f'shaper_{args.axis.lower()}.png')
        generate_axis_graph(freq, psd, args.axis, graph_path, recommendations)
        result['graph'] = graph_path
        result['success'] = True

    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        result['error'] = str(e)
    except Exception as e:
        print(f"ERROR: {e}")
        result['error'] = str(e)
        import traceback
        traceback.print_exc()

    return result


def process_belts(args) -> dict:
    """Process belt comparison (X vs Y resonance)."""
    csv_dir = os.path.expanduser(args.csv_dir)
    output_dir = os.path.expanduser(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    result = {'type': 'belt_comparison', 'success': False}

    try:
        csv_x = find_latest_csv(csv_dir, 'x')
        csv_y = find_latest_csv(csv_dir, 'y')

        print(f"Processing X: {csv_x}")
        print(f"Processing Y: {csv_y}")

        freq_x, psd_x = parse_csv_data(csv_x)
        freq_y, psd_y = parse_csv_data(csv_y)

        graph_path = os.path.join(output_dir, 'belt_comparison.png')
        comparison = generate_belt_comparison_graph(freq_x, psd_x, freq_y, psd_y, graph_path)

        result.update(comparison)
        result['graph'] = graph_path
        result['success'] = True

        # Print summary
        print(f"\n{'='*60}")
        print("BELT TENSION COMPARISON")
        print(f"{'='*60}")
        print(f"X Axis Peak: {comparison['peak_x']:.1f} Hz")
        print(f"Y Axis Peak: {comparison['peak_y']:.1f} Hz")
        print(f"Difference:  {comparison['difference_hz']:.1f} Hz ({comparison['difference_percent']:+.1f}%)")
        print(f"Status:      {comparison['status']}")

        if comparison['status'] != 'GOOD':
            print("\nTIP: For CoreXY, tighten the belt on the axis with LOWER frequency.")

    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("Make sure you've run TEST_RESONANCES for both X and Y axes.")
        result['error'] = str(e)
    except Exception as e:
        print(f"ERROR: {e}")
        result['error'] = str(e)
        import traceback
        traceback.print_exc()

    return result


def main():
    parser = argparse.ArgumentParser(
        description='Generate input shaper graphs and recommendations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Axis command
    axis_parser = subparsers.add_parser('axis', help='Process axis resonance data')
    axis_parser.add_argument('axis', choices=['x', 'y', 'X', 'Y'],
                            help='Axis to process')
    axis_parser.add_argument('--csv-dir', default='/tmp',
                            help='Directory containing resonance CSV files')
    axis_parser.add_argument('--output-dir', default='~/printer_data/config/plots',
                            help='Output directory for graphs')
    axis_parser.add_argument('--max-accel', type=float, default=10000,
                            help='Maximum acceleration for shaper calculation')

    # Belts command
    belts_parser = subparsers.add_parser('belts', help='Compare belt tensions')
    belts_parser.add_argument('--csv-dir', default='/tmp',
                             help='Directory containing resonance CSV files')
    belts_parser.add_argument('--output-dir', default='~/printer_data/config/plots',
                             help='Output directory for graphs')

    # Both command (for full calibration)
    both_parser = subparsers.add_parser('both', help='Process both axes')
    both_parser.add_argument('--csv-dir', default='/tmp',
                            help='Directory containing resonance CSV files')
    both_parser.add_argument('--output-dir', default='~/printer_data/config/plots',
                            help='Output directory for graphs')
    both_parser.add_argument('--max-accel', type=float, default=10000,
                            help='Maximum acceleration for shaper calculation')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    results = {}
    output_dir = os.path.expanduser(args.output_dir)

    if args.command == 'axis':
        results[args.axis.upper()] = process_axis(args)

    elif args.command == 'belts':
        results['belts'] = process_belts(args)

    elif args.command == 'both':
        for axis in ['x', 'y']:
            args.axis = axis
            results[axis.upper()] = process_axis(args)

    # Save results to JSON for APPLY_SHAPER macro
    json_path = os.path.join(output_dir, 'shaper_recommendations.json')
    os.makedirs(output_dir, exist_ok=True)

    with open(json_path, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'results': results
        }, f, indent=2)

    print(f"\nResults saved to: {json_path}")
    print(f"View graphs in Mainsail/Fluidd: config/plots/")


if __name__ == '__main__':
    main()

