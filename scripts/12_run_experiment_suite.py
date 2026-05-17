from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

from aaca_utils import ROOT


def load_suite() -> dict:
    path = ROOT / "config" / "experiment_suite.yml"
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def print_plan(suite: dict) -> None:
    project = suite["project"]
    print("Medellin EV readiness experiment suite")
    print(f"Study area: {project['study_area']}")
    print(f"Target: {project['journal_target']} / {project['article_type']}")
    print()
    for index, phase in enumerate(suite["workflow_phases"], start=1):
        print(f"{index}. {phase['phase']}")
        if phase.get("objective"):
            print(f"   objective: {phase['objective']}")
        for script in phase.get("scripts", []):
            print(f"   - {script}")
        print()


def run_scripts(suite: dict, start_at: str | None = None, stop_after: str | None = None) -> int:
    active = start_at is None
    for phase in suite["workflow_phases"]:
        phase_name = phase["phase"]
        if phase_name == start_at:
            active = True
        if not active:
            continue
        print(f"\n== {phase_name} ==")
        for script in phase.get("scripts", []):
            script_path = ROOT / script
            if not script_path.exists():
                print(f"Missing script: {script}")
                return 1
            result = subprocess.run([sys.executable, str(script_path)], cwd=ROOT)
            if result.returncode != 0:
                print(f"Stopped at {script} with exit code {result.returncode}")
                return int(result.returncode)
        if phase_name == stop_after:
            break
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run or print the Medellin AACA experiment suite.")
    parser.add_argument("--run", action="store_true", help="Run the Medellin scripts in suite order.")
    parser.add_argument("--start-at", help="Phase name to start at.")
    parser.add_argument("--stop-after", help="Phase name to stop after.")
    args = parser.parse_args()

    suite = load_suite()
    if not args.run:
        print_plan(suite)
        return
    raise SystemExit(run_scripts(suite, start_at=args.start_at, stop_after=args.stop_after))


if __name__ == "__main__":
    main()
