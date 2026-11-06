"""Run circuits on a real IBM device: session files, mapping onto physical qubits, submission and results.

A session is one day on the device. `prepare` fixes the circuits and records that day's calibration, `submit`
sends one job, `fetch` stores the measured counts. Every file lands in the session folder, so the analysis needs
only that folder. With `dry_run`, FakeFez in qiskit-ibm-runtime's local mode stands in for the device, so the
whole path can be tested without an account.
"""

import json
import logging
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit, qpy, transpile

from trustqem.circuits import CircuitRecord, build_clifford_twin, build_random_records
from trustqem.device import choose_chain, fold_gates, load_calibration, transpile_to_device

logger = logging.getLogger(__name__)

ROLES = ("test", "oracle", "twin")
SUB_JOB_OVERHEAD_SECONDS = 2.0      # IBM docs, "Estimate job run time"
DEFAULT_BUDGET_CAP_SECONDS = 200.0  # a third of the Open Plan's 600 s per rolling 28 days


@dataclass(frozen=True)
class HardwareSession:
    """What one hardware day runs. Circuits are ordered test, then oracle, then twins; each runs at every scale."""

    session: str
    backend_name: str
    physical_qubits: tuple[int, ...]
    seed: int = 4004
    test_circuits: int = 60
    oracle_circuits: int = 60
    twin_circuits: int = 60
    twin_non_clifford_count: int = 8
    shots: int = 1000
    fold_scales: tuple[float, ...] = (1.0, 3.0, 5.0)
    qubit_count: int = 4
    max_layers: int = 12
    cx_probability_per_pair: float = 0.5
    dry_run: bool = False

    @property
    def circuit_count(self) -> int:
        """Logical circuits in the session (each runs once per fold scale)."""
        return self.test_circuits + self.oracle_circuits + self.twin_circuits

    def role_ids(self, role: str) -> np.ndarray:
        """Indices of the logical circuits with this role."""
        sizes = {"test": self.test_circuits, "oracle": self.oracle_circuits, "twin": self.twin_circuits}
        start = sum(sizes[r] for r in ROLES[:ROLES.index(role)])
        return np.arange(start, start + sizes[role])


def get_backend(backend_name: str, dry_run: bool):
    """The real device through the saved IBM account, or FakeFez for a dry run."""
    if dry_run:
        from qiskit_ibm_runtime.fake_provider import FakeFez
        return FakeFez()
    from qiskit_ibm_runtime import QiskitRuntimeService
    return QiskitRuntimeService().backend(backend_name)


def build_session_records(session: HardwareSession) -> list[CircuitRecord]:
    """Test and oracle circuits are fresh random circuits; twins are near-Clifford copies of further ones."""
    rng = np.random.default_rng(session.seed)

    def random_records(count: int) -> list[CircuitRecord]:
        return build_random_records(count, session.qubit_count, session.max_layers, session.cx_probability_per_pair,
                                    rng)

    test, oracle, sources = (random_records(n) for n in
                             (session.test_circuits, session.oracle_circuits, session.twin_circuits))
    twins = [build_clifford_twin(record, session.twin_non_clifford_count, rng) for record in sources]
    return test + oracle + twins


def map_to_device(circuit: QuantumCircuit, scale: float, backend, physical_qubits: tuple[int, ...]) -> QuantumCircuit:
    """Native gates, folded, measured, then laid onto the physical chain with no optimisation (folds survive)."""
    folded = fold_gates(transpile_to_device(circuit), scale)
    folded.measure_all()
    return transpile(folded, backend, initial_layout=list(physical_qubits), optimization_level=0)


def _record_dict(record: CircuitRecord) -> dict:
    return {"layer_count": record.layer_count, "cx_count": record.cx_count,
            "non_clifford_count": record.non_clifford_count}


def prepare_session(session_dir: Path, session: str, backend_name: str, dry_run: bool = False,
                    reuse_from: Path | None = None, **sizes) -> HardwareSession:
    """Write manifest, today's calibration and all circuits. With `reuse_from`, reuse that session's chain and
    circuits (so two days are paired) but record today's calibration."""
    backend = get_backend(backend_name, dry_run)
    if reuse_from is not None:
        earlier = load_manifest(reuse_from)
        spec = replace(earlier, session=session, dry_run=dry_run)
        records = load_records(reuse_from)
    else:
        chain = choose_chain(backend, sizes.get("qubit_count", HardwareSession.qubit_count))
        spec = HardwareSession(session=session, backend_name=backend.name, physical_qubits=chain,
                               dry_run=dry_run, **sizes)
        records = build_session_records(spec)
    calibration = load_calibration(backend, spec.physical_qubits)
    physical = [map_to_device(record.circuit, scale, backend, spec.physical_qubits)
                for record in records for scale in spec.fold_scales]

    session_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"session": asdict(spec), "prepared_at": datetime.now(UTC).isoformat(),
                "records": [_record_dict(record) for record in records],
                "estimated_qpu_seconds": estimate_qpu_seconds(physical, backend, spec.shots)}
    (session_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (session_dir / "calibration.json").write_text(json.dumps(calibration.to_dict(), indent=2))
    with open(session_dir / "circuits_logical.qpy", "wb") as file:
        qpy.dump([record.circuit for record in records], file)
    with open(session_dir / "circuits_physical.qpy", "wb") as file:
        qpy.dump(physical, file)
    logger.info("prepared %s: %d circuits x %d scales on qubits %s, estimate %.0f s", session, len(records),
                len(spec.fold_scales), spec.physical_qubits, manifest["estimated_qpu_seconds"])
    return spec


def load_manifest(session_dir: Path) -> HardwareSession:
    """The session spec saved by prepare."""
    data = json.loads((session_dir / "manifest.json").read_text())["session"]
    return HardwareSession(**{**data, "physical_qubits": tuple(data["physical_qubits"]),
                              "fold_scales": tuple(data["fold_scales"])})


def load_records(session_dir: Path) -> list[CircuitRecord]:
    """Logical circuits with their structural features, in session order."""
    with open(session_dir / "circuits_logical.qpy", "rb") as file:
        circuits = qpy.load(file)
    metadata = json.loads((session_dir / "manifest.json").read_text())["records"]
    return [CircuitRecord(circuit, **fields) for circuit, fields in zip(circuits, metadata, strict=True)]


def estimate_qpu_seconds(physical: list[QuantumCircuit], backend, shots: int, jobs: int = 1) -> float:
    """IBM's documented estimate: overhead per job + shots x (rep_delay + circuit duration incl. readout)."""
    rep_delay = float(backend.configuration().default_rep_delay)
    durations = sum(circuit.estimate_duration(backend.target) for circuit in physical)
    return round(jobs * SUB_JOB_OVERHEAD_SECONDS + shots * (len(physical) * rep_delay + durations), 1)


def _sampler(backend, shots: int):
    """SamplerV2 with error suppression off, so the device runs the circuits exactly as folded."""
    from qiskit_ibm_runtime import SamplerV2
    sampler = SamplerV2(mode=backend)
    sampler.options.default_shots = shots
    sampler.options.dynamical_decoupling.enable = False
    sampler.options.twirling.enable_gates = False
    sampler.options.twirling.enable_measure = False
    return sampler


def submit_session(session_dir: Path, budget_cap_seconds: float = DEFAULT_BUDGET_CAP_SECONDS,
                   force: bool = False) -> str:
    """Send every circuit as one job and save its id. A dry run also stores the counts straight away."""
    spec = load_manifest(session_dir)
    estimate = json.loads((session_dir / "manifest.json").read_text())["estimated_qpu_seconds"]
    if estimate > budget_cap_seconds and not force:
        raise RuntimeError(f"estimated {estimate:.0f} s of QPU time is over the {budget_cap_seconds:.0f} s cap; "
                           "rerun with --force if that is intended")
    with open(session_dir / "circuits_physical.qpy", "rb") as file:
        physical = qpy.load(file)
    backend = get_backend(spec.backend_name, spec.dry_run)
    job = _sampler(backend, spec.shots).run(physical)
    jobs = {"job_id": job.job_id(), "backend": backend.name, "submitted_at": datetime.now(UTC).isoformat(),
            "estimated_qpu_seconds": estimate, "dry_run": spec.dry_run}
    (session_dir / "jobs.json").write_text(json.dumps(jobs, indent=2))
    logger.info("submitted job %s to %s", job.job_id(), backend.name)
    if spec.dry_run:
        _write_counts(session_dir, job)
    return job.job_id()


def fetch_session(session_dir: Path) -> Path:
    """Download the finished job's counts (blocks until the job is done)."""
    from qiskit_ibm_runtime import QiskitRuntimeService
    job_id = json.loads((session_dir / "jobs.json").read_text())["job_id"]
    return _write_counts(session_dir, QiskitRuntimeService().job(job_id))


def _write_counts(session_dir: Path, job) -> Path:
    """Counts per circuit in submission order, plus the usage IBM reports for the job."""
    result = job.result()
    counts = [pub.data.meas.get_counts() for pub in result]
    try:
        usage = job.metrics().get("usage", {})
    except Exception as error:      # local jobs and older servers report usage differently; record, don't fail
        usage = {"error": str(error)}
    path = session_dir / "counts.json"
    path.write_text(json.dumps({"job_id": job.job_id(), "fetched_at": datetime.now(UTC).isoformat(),
                                "usage": usage, "counts": counts}))
    return path


def load_probabilities(session_dir: Path) -> np.ndarray:
    """Measured fractions as (circuits, scales, 2**n), the layout pool_from_probabilities expects."""
    spec = load_manifest(session_dir)
    counts = json.loads((session_dir / "counts.json").read_text())["counts"]
    probabilities = np.zeros((spec.circuit_count * len(spec.fold_scales), 2 ** spec.qubit_count))
    for index, circuit_counts in enumerate(counts):
        total = sum(circuit_counts.values())
        for bitstring, count in circuit_counts.items():
            probabilities[index, int(bitstring, 2)] = count / total
    return probabilities.reshape(spec.circuit_count, len(spec.fold_scales), -1)


def check_access(backend_name: str, dry_run: bool) -> list[str]:
    """Confirm the saved account works: list operational devices, the chosen one's queue, and usage left."""
    if dry_run:
        backend = get_backend(backend_name, dry_run=True)
        return [f"dry run: {backend.name}, {backend.num_qubits} qubits (local simulator, no account needed)"]
    from qiskit_ibm_runtime import QiskitRuntimeService
    service = QiskitRuntimeService()
    lines = [f"account: channel {service.channel}, instance {service.active_instance()}"]
    for backend in service.backends(simulator=False, operational=True):
        lines.append(f"  {backend.name}: {backend.num_qubits} qubits, {backend.status().pending_jobs} jobs queued")
    if backend_name not in {b.name for b in service.backends(simulator=False)}:
        lines.append(f"WARNING: {backend_name} is not available to this account; pick one above with --backend")
    try:
        lines.append(f"usage: {service.usage()}")
    except Exception as error:      # usage reporting differs between plans; informative only
        lines.append(f"usage: not available ({error})")
    return lines
