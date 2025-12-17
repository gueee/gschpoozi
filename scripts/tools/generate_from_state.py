#!/usr/bin/env python3
"""
Generate gschpoozi config files from a WizardState directory.

This tiny helper avoids brittle shell heredocs/quoting when running generation
in automated compare scripts.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.wizard.state import WizardState  # noqa: E402
from scripts.generator.generator import ConfigGenerator  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate config files from wizard state")
    parser.add_argument("--state-dir", required=True, help="Directory containing .gschpoozi_state.json")
    parser.add_argument("--out-dir", required=True, help="Output directory for generated configs")
    args = parser.parse_args()

    state_dir = Path(args.state_dir).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    state = WizardState(state_dir=state_dir)
    gen = ConfigGenerator(state=state, output_dir=out_dir)
    files = gen.generate()
    gen.write_files(files)
    print(f"WROTE {len(files)} files into {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


