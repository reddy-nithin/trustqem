"""Command line entry point: `trustqem run <experiment> --profile <profile>`."""

import argparse
import logging
from pathlib import Path

from trustqem.experiments import drift

EXPERIMENTS = {"drift": drift}


def main() -> None:
    """Parse arguments and run the chosen experiment."""
    parser = argparse.ArgumentParser(prog="trustqem")
    subcommands = parser.add_subparsers(dest="command", required=True)
    run_parser = subcommands.add_parser("run", help="run an experiment")
    run_parser.add_argument("experiment", choices=sorted(EXPERIMENTS))
    run_parser.add_argument("--profile", default="pilot")
    run_parser.add_argument("--results", type=Path, default=Path("results"))
    arguments = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("trustqem").setLevel(logging.INFO)
    output_dir = EXPERIMENTS[arguments.experiment].run(arguments.profile, arguments.results)
    print(f"results in {output_dir}")
    print((output_dir / "verdict.md").read_text())


if __name__ == "__main__":
    main()
