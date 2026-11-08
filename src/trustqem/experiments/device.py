"""Experiment (Stage 3): do the drift results hold on IBM Heron noise with noise amplified by gate folding?

Same design as experiments/drift.py, whose repeat logic is reused unchanged. What differs: Monday is the FakeFez
calibration of the best 4-qubit chain, circuits run in native gates folded to scales 1, 3 and 5, and Tuesday
scenarios perturb that calibration the way real devices drift (Amendment 2, docs/HYPOTHESES.md).
"""

import json
import logging
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np

from trustqem.circuits import build_random_records
from trustqem.config import ExperimentConfig
from trustqem.device import (
    DeviceCalibration,
    DeviceCondition,
    build_timing_target,
    degrade_qubit,
    fold_gates,
    load_calibration,
    scale_coherence,
    scale_gate_errors,
    scale_readout,
    transpile_to_device,
)
from trustqem.experiments.drift import DriftProfile, _bootstrap_by_pool, run_repeat, scale_profile
from trustqem.experiments.pools import PoolSizes, load_or_build_pools
from trustqem.experiments.report import (
    _lookup,
    plot_coverage_by_scenario,
    plot_recalibration_budget,
    summarize,
    write_verdict,
)

logger = logging.getLogger(__name__)

FOLD_SCALES = (1.0, 3.0, 5.0)
BAD_QUBIT = 1           # an interior qubit of the chain, so two cz edges touch it

# Tuesday perturbations, frozen in Amendment 2 before the pilot. Sources and reasoning are in docs/HYPOTHESES.md.
SCENARIO_RECIPES: dict[str, str] = {
    "E0_no_drift": "Monday calibration unchanged",
    "E1_coherence_drop": "T1 and T2 x0.5 on all four qubits",
    "E2_bad_qubit": f"chain qubit {BAD_QUBIT}: T1 x0.2, cz error on its two edges x3",
    "E3_readout": "readout flip probabilities x2 on all four qubits",
    "E4_gate_errors": "sx, x and cz errors x1.5 on all qubits and edges",
    "E5_combined": f"T1/T2 x0.7, gate errors x1.3, readout x1.5, chain qubit {BAD_QUBIT}: T1 x0.5 and cz x1.5",
}


def build_scenarios(monday: DeviceCalibration) -> dict[str, DeviceCondition]:
    """Every Tuesday device state, derived from Monday's calibration."""
    combined = scale_readout(scale_gate_errors(scale_coherence(monday, 0.7), 1.3), 1.5)
    calibrations = {
        "E0_no_drift": monday,
        "E1_coherence_drop": scale_coherence(monday, 0.5),
        "E2_bad_qubit": degrade_qubit(monday, BAD_QUBIT, t1_factor=0.2, cz_factor=3.0),
        "E3_readout": scale_readout(monday, 2.0),
        "E4_gate_errors": scale_gate_errors(monday, 1.5),
        "E5_combined": degrade_qubit(combined, BAD_QUBIT, t1_factor=0.5, cz_factor=1.5),
    }
    return {name: DeviceCondition(name, calibration) for name, calibration in calibrations.items()}


@dataclass(frozen=True)
class DeviceProfile:
    """A drift-style profile plus the hardware-budget question it answers."""

    drift: DriftProfile
    budget_test_circuits: int = 40
    budget_twin_circuits: int = 40
    budget_monday_circuits: int = 400          # train + calibration, if Monday data were also taken on hardware


PROFILES = {
    "smoke": DeviceProfile(DriftProfile(
        sizes=PoolSizes(monday_circuits=60, monday_twin_sources=20, tuesday_circuits=40,
                        twin_non_clifford_counts=(0, 2), scenarios=("E0_no_drift", "E5_combined")),
        train_circuits=30, calibration_circuits=15, test_circuits=15, recalibration_counts=(10,), repeats=2,
        bootstrap_resamples=50, random_seed=3000)),
    "pilot": DeviceProfile(DriftProfile(
        sizes=PoolSizes(monday_circuits=500, monday_twin_sources=150, tuesday_circuits=300,
                        twin_non_clifford_counts=(0, 2, 4, 8), scenarios=tuple(SCENARIO_RECIPES)),
        train_circuits=300, calibration_circuits=100, test_circuits=100, recalibration_counts=(25, 50, 100),
        repeats=5, random_seed=3003, retrain_counts=(50, 100))),
    "full": DeviceProfile(DriftProfile(
        sizes=PoolSizes(monday_circuits=500, monday_twin_sources=200, tuesday_circuits=400,
                        twin_non_clifford_counts=(0, 2, 4, 8), scenarios=tuple(SCENARIO_RECIPES)),
        train_circuits=300, calibration_circuits=100, test_circuits=100,
        recalibration_counts=(10, 25, 50, 100, 200), repeats=20, random_seed=3030, retrain_counts=(50, 100, 200))),
    # Amendment 4: the device track at 12 qubits, same sizes as the drift scaling study, its own seed
    "scale_q12": DeviceProfile(replace(scale_profile(12), random_seed=6062,
                                       sizes=replace(scale_profile(12).sizes, scenarios=tuple(SCENARIO_RECIPES)))),
}

# IBM's documented estimate (docs: "Estimate job run time"): about 2 s overhead per sub-job, plus
# (rep_delay + circuit duration) per shot. rep_delay comes from the backend configuration.
SUB_JOB_OVERHEAD_SECONDS = 2.0


def circuit_durations(calibration: DeviceCalibration, config: ExperimentConfig, sample_size: int = 200,
                      seed: int = 0) -> dict[float, dict[str, float]]:
    """Mean and longest gate-sequence duration (seconds, before readout) of the random circuits, per fold scale."""
    target = build_timing_target(calibration)
    records = build_random_records(sample_size, config.qubit_count, config.max_layers,
                                   config.cx_probability_per_pair, np.random.default_rng(seed))
    natives = [transpile_to_device(record.circuit) for record in records]
    durations = {}
    for scale in FOLD_SCALES:
        values = np.array([fold_gates(native, scale).estimate_duration(target) for native in natives])
        durations[scale] = {"mean": float(values.mean()), "max": float(values.max())}
    return durations


def hardware_budget(profile: DeviceProfile, calibration: DeviceCalibration, config: ExperimentConfig) -> dict:
    """Circuits x shots x fold scales for a Stage 4 day, and the QPU time IBM's formula predicts for it."""
    from qiskit_ibm_runtime.fake_provider import FakeFez
    backend = FakeFez()
    rep_delay = float(backend.configuration().default_rep_delay)
    readout = float(backend.target["measure"][(calibration.physical_qubits[0],)].duration)
    durations = circuit_durations(calibration, config)
    mean_duration = float(np.mean([durations[scale]["mean"] for scale in FOLD_SCALES]))

    def block(circuits: int, jobs: int = 1) -> dict:
        executions = circuits * len(FOLD_SCALES)
        shots = executions * config.shots_per_circuit
        seconds = jobs * SUB_JOB_OVERHEAD_SECONDS + shots * (rep_delay + mean_duration + readout)
        return {"circuits": circuits, "fold_scales": len(FOLD_SCALES), "circuit_executions": executions,
                "shots_per_execution": config.shots_per_circuit, "total_shots": shots,
                "estimated_qpu_seconds": round(seconds, 1)}

    day = block(profile.budget_test_circuits + profile.budget_twin_circuits)
    return {
        "assumptions": {"rep_delay_seconds": rep_delay, "readout_seconds": readout,
                        "sub_job_overhead_seconds": SUB_JOB_OVERHEAD_SECONDS,
                        "circuit_duration_seconds_by_scale": {str(s): d for s, d in durations.items()},
                        "formula": "jobs x overhead + shots x (rep_delay + mean circuit duration + readout)",
                        "source": "IBM Quantum docs, 'Estimate job run time' (quantum.cloud.ibm.com/docs)"},
        "stage4_day_test_plus_twins": {"test_circuits": profile.budget_test_circuits,
                                       "twin_circuits": profile.budget_twin_circuits, **day},
        "monday_training_on_hardware": block(profile.budget_monday_circuits),
        "open_plan_limits_seconds": {"per_28_days": 600},
    }


def _headline_lines(summary: dict, scenarios: list[str], count: int) -> list[str]:
    """Fixed cells reported next to the verdict: k = 4 and k = 8 at one K, against frozen and oracle."""
    lines = ["", f"## Fixed cells at K = {count} (coverage / mean width)", "",
             "| scenario | MAE | frozen | ZNE+bootstrap | R1 k=4 | R2 k=4 | R1W k=4 | R1W k=8 | oracle |",
             "|---|---|---|---|---|---|---|---|---|"]

    def cell(method: str, keep: int, cell_count: int) -> str:
        entry = _lookup(summary, scenario, method, cell_count, keep)
        if entry is None:
            return "n/a"
        return f"{entry['coverage']['mean']:.3f} / {entry['mean_width']['mean']:.3f}"

    for scenario in scenarios:
        frozen = _lookup(summary, scenario, "R0_frozen", 0, -1)
        lines.append(f"| {scenario} | {frozen['model_mae']['mean']:.4f} | {cell('R0_frozen', -1, 0)} | "
                     f"{cell('zne_bootstrap', -1, 0)} | {cell('R1_clifford_direct', 4, count)} | "
                     f"{cell('R2_clifford_ratio', 4, count)} | {cell('R1W_clifford_weighted', 4, count)} | "
                     f"{cell('R1W_clifford_weighted', 8, count)} | {cell('R3_oracle', -1, count)} |")
    return lines


def _budget_lines(budget: dict) -> list[str]:
    """Plain-language summary of the hardware budget."""
    lines = ["", "## Hardware budget (IBM Open Plan: 600 s per rolling 28 days)", ""]
    for name in ("stage4_day_test_plus_twins", "monday_training_on_hardware"):
        block = budget[name]
        lines.append(f"- {name}: {block['circuits']} circuits x {block['fold_scales']} fold scales x "
                     f"{block['shots_per_execution']} shots = {block['total_shots']} shots, about "
                     f"{block['estimated_qpu_seconds']} s of QPU time")
    return lines


def run(profile_name: str, results_root: Path) -> Path:
    """Run every repeat of the device experiment and write results, figures, the verdict and the budget."""
    device_profile = PROFILES[profile_name]
    profile = device_profile.drift
    config = replace(ExperimentConfig(), random_seed=profile.random_seed, noise_scale_factors=FOLD_SCALES,
                     qubit_count=profile.qubit_count)
    output_dir = results_root / "device" / profile_name
    output_dir.mkdir(parents=True, exist_ok=True)
    calibration = load_calibration(length=profile.qubit_count)
    scenarios = build_scenarios(calibration)
    monday = DeviceCondition("monday", calibration)
    pools = load_or_build_pools(config, profile.sizes, output_dir / "pools.pkl", monday, scenarios)
    bootstrap = _bootstrap_by_pool(pools, profile)

    all_rows, all_alarms = [], []
    for repeat in range(profile.repeats):
        rows, alarms = run_repeat(pools, profile, repeat, bootstrap)
        all_rows.extend(rows)
        all_alarms.extend(alarms)
        logger.info("repeat %d/%d done", repeat + 1, profile.repeats)

    summary = summarize([asdict(row) for row in all_rows], all_alarms, profile.alpha)
    budget = hardware_budget(device_profile, calibration, config)
    (output_dir / "config.json").write_text(json.dumps(
        {"config": config.to_dict(), "profile": asdict(device_profile), "calibration": calibration.to_dict(),
         "scenarios": {name: SCENARIO_RECIPES[name] for name in profile.sizes.scenarios},
         "scenario_calibrations": {name: scenarios[name].calibration.to_dict() for name in profile.sizes.scenarios}},
        indent=2, default=str))
    (output_dir / "rows.json").write_text(json.dumps([asdict(row) for row in all_rows]))
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    (output_dir / "budget.json").write_text(json.dumps(budget, indent=2))
    headline_count = 100 if 100 in profile.recalibration_counts else max(profile.recalibration_counts)
    plot_coverage_by_scenario(summary, profile.alpha, headline_count).savefig(
        output_dir / "coverage_by_scenario.png", dpi=200)
    plot_recalibration_budget(summary, profile.alpha).savefig(output_dir / "recalibration_budget.png", dpi=200)
    write_device_verdict(summary, budget, profile, output_dir / "verdict.md")
    return output_dir


def write_device_verdict(summary: dict, budget: dict, profile: DriftProfile, path: Path) -> None:
    """The pre-registered verdict, then the fixed cells and the hardware budget."""
    write_verdict(summary, profile.alpha, path, title="Verdict, device track (Amendment 2, docs/HYPOTHESES.md)")
    headline_count = 100 if 100 in profile.recalibration_counts else max(profile.recalibration_counts)
    extra = _headline_lines(summary, list(profile.sizes.scenarios), headline_count) + _budget_lines(budget)
    path.write_text(path.read_text() + "\n".join(extra) + "\n")
