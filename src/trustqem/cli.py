"""Command line entry point: `trustqem run <experiment> --profile <profile>` and `trustqem hardware <step>`."""

import argparse
import logging
from pathlib import Path

from trustqem import hardware
from trustqem.experiments import device, drift
from trustqem.experiments import hardware as hardware_experiment

EXPERIMENTS = {"device": device, "drift": drift}
HARDWARE_STEPS = ("check", "prepare", "submit", "fetch", "analyze")


def main() -> None:
    """Parse arguments and run the chosen experiment or hardware step."""
    parser = argparse.ArgumentParser(prog="trustqem")
    subcommands = parser.add_subparsers(dest="command", required=True)
    run_parser = subcommands.add_parser("run", help="run an experiment")
    run_parser.add_argument("experiment", choices=sorted(EXPERIMENTS))
    run_parser.add_argument("--profile", default="pilot")
    run_parser.add_argument("--results", type=Path, default=Path("results"))
    hardware_parser = subcommands.add_parser("hardware", help="run circuits on a real IBM device (docs/HARDWARE.md)")
    hardware_parser.add_argument("step", choices=HARDWARE_STEPS)
    hardware_parser.add_argument("--session", default="S1")
    hardware_parser.add_argument("--pair-with", help="reuse this session's chain and circuits (e.g. S1)")
    hardware_parser.add_argument("--backend", default="ibm_fez")
    hardware_parser.add_argument("--dry-run", action="store_true", help="use local FakeFez instead of the device")
    hardware_parser.add_argument("--force", action="store_true", help="submit even above the QPU budget cap")
    hardware_parser.add_argument("--results", type=Path, default=Path("results"))
    arguments = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("trustqem").setLevel(logging.INFO)
    if arguments.command == "hardware":
        run_hardware_step(arguments)
        return
    output_dir = EXPERIMENTS[arguments.experiment].run(arguments.profile, arguments.results)
    print(f"results in {output_dir}")
    print((output_dir / "verdict.md").read_text())


def run_hardware_step(arguments: argparse.Namespace) -> None:
    """One step of a hardware session. Dry runs live under results/hardware/dryrun/ (not committed)."""
    root = arguments.results / "hardware" / ("dryrun" if arguments.dry_run else "")
    session_dir = root / arguments.session
    if arguments.step == "check":
        print("\n".join(hardware.check_access(arguments.backend, arguments.dry_run)))
    elif arguments.step == "prepare":
        pair = root / arguments.pair_with if arguments.pair_with else None
        spec = hardware.prepare_session(session_dir, arguments.session, arguments.backend, arguments.dry_run, pair)
        print(f"prepared {spec.session} on {spec.backend_name}, qubits {spec.physical_qubits}: {session_dir}")
    elif arguments.step == "submit":
        job_id = hardware.submit_session(session_dir, force=arguments.force)
        print("dry run: counts saved" if arguments.dry_run else
              f"job {job_id} submitted; run `fetch` when it has finished")
    elif arguments.step == "fetch":
        print(f"counts saved to {hardware.fetch_session(session_dir)}")
    else:
        output = hardware_experiment.run(root)
        print((output / "verdict.md").read_text())


if __name__ == "__main__":
    main()
