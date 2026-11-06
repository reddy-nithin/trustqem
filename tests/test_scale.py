"""Amendment 4 plumbing: parallel workers give the same pools, interrupted runs resume, 12-qubit chains exist."""

from dataclasses import replace

import numpy as np
import pytest

from trustqem.config import ExperimentConfig
from trustqem.device import choose_chain, load_calibration
from trustqem.experiments.drift import PROFILES
from trustqem.experiments.pools import PoolSizes, build_pools
from trustqem.simulate import aer_device_options

TINY = PoolSizes(monday_circuits=6, monday_twin_sources=3, tuesday_circuits=4, twin_non_clifford_counts=(2,),
                 scenarios=("D0_no_drift", "D2_depolarizing_x2"))


def _same_pools(first, second) -> None:
    assert np.array_equal(first.monday.probabilities, second.monday.probabilities)
    for key in first.tuesday_twins:
        assert np.array_equal(first.tuesday_twins[key].probabilities, second.tuesday_twins[key].probabilities)
    for key in first.tuesday:
        assert np.array_equal(first.tuesday[key].row_noisy_values, second.tuesday[key].row_noisy_values)


def test_worker_count_does_not_change_the_pools(monkeypatch) -> None:
    config = replace(ExperimentConfig(), random_seed=7)
    monkeypatch.setenv("TRUSTQEM_WORKERS", "1")
    serial = build_pools(config, TINY)
    monkeypatch.setenv("TRUSTQEM_WORKERS", "2")
    parallel = build_pools(config, TINY)
    _same_pools(serial, parallel)


def test_interrupted_build_resumes_from_saved_parts(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TRUSTQEM_WORKERS", "1")
    config = replace(ExperimentConfig(), random_seed=8)
    reference = build_pools(config, TINY)
    build_pools(config, TINY, parts_dir=tmp_path)
    parts = sorted(tmp_path.glob("*.pkl"))
    assert len(parts) == 1 + 1 + 2 + 2          # monday, monday twins, 2 tuesday, 2 tuesday twins
    # as if the run died after the first few pools: drop the later parts and build again
    for part in parts[3:]:
        part.unlink()
    resumed = build_pools(config, TINY, parts_dir=tmp_path)
    _same_pools(reference, resumed)


def test_saved_part_with_other_settings_is_not_reused(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TRUSTQEM_WORKERS", "1")
    build_pools(replace(ExperimentConfig(), random_seed=9), TINY, parts_dir=tmp_path)
    other = replace(ExperimentConfig(), random_seed=9, shots_per_circuit=500)
    fresh = build_pools(other, TINY)
    reused_dir = build_pools(other, TINY, parts_dir=tmp_path)
    _same_pools(fresh, reused_dir)


def test_twelve_qubit_chain_on_fakefez_is_a_connected_line() -> None:
    from qiskit_ibm_runtime.fake_provider import FakeFez
    backend = FakeFez()
    chain = choose_chain(backend, 12)
    assert len(chain) == 12 and len(set(chain)) == 12
    edges = {frozenset(edge) for edge in backend.target["cz"]}
    assert all(frozenset(pair) in edges for pair in zip(chain, chain[1:], strict=False))
    assert len(load_calibration(backend, length=12).t1) == 12


def test_scale_profiles_follow_amendment_4() -> None:
    for n in (4, 6, 8, 10, 12):
        profile = PROFILES[f"scale_q{n}"]
        assert profile.qubit_count == n and profile.random_seed == 5050 + n
        assert profile.sizes.monday_circuits == 1000 and profile.sizes.tuesday_circuits == 800
        assert profile.train_circuits + profile.calibration_circuits + profile.test_circuits == 1000
    assert PROFILES["scale_q4"].sizes.twin_non_clifford_counts == (0, 2, 4, 8)
    assert PROFILES["scale_q12"].sizes.twin_non_clifford_counts == (2, 4)


def test_aer_device_options(monkeypatch) -> None:
    monkeypatch.delenv("TRUSTQEM_AER_DEVICE", raising=False)
    monkeypatch.delenv("TRUSTQEM_AER_PRECISION", raising=False)
    assert aer_device_options() == {}
    monkeypatch.setenv("TRUSTQEM_AER_DEVICE", "gpu")
    monkeypatch.setenv("TRUSTQEM_AER_PRECISION", "single")
    assert aer_device_options() == {"device": "GPU", "precision": "single"}
    monkeypatch.setenv("TRUSTQEM_AER_DEVICE", "tpu")
    with pytest.raises(ValueError):
        aer_device_options()


def test_smoke_run_writes_results_when_the_cache_lives_elsewhere(tmp_path, monkeypatch) -> None:
    from trustqem.experiments import drift
    monkeypatch.setenv("TRUSTQEM_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("TRUSTQEM_WORKERS", "1")
    output = drift.run("smoke", tmp_path / "results")
    assert (output / "verdict.md").exists()
    assert (tmp_path / "cache" / "drift_smoke" / "pools.pkl").exists()
    assert not (output / "pools.pkl").exists()


def test_nonzero_rerun_reuses_drift_pools_and_reproduces_r1w(tmp_path, monkeypatch) -> None:
    import json

    from trustqem.experiments import drift, nonzero
    monkeypatch.setenv("TRUSTQEM_CACHE", str(tmp_path / "cache"))
    first = json.loads((drift.run("smoke", tmp_path / "results") / "rows.json").read_text())
    pools_written = (tmp_path / "cache" / "drift_smoke" / "pools.pkl").stat().st_mtime
    output = nonzero.run("smoke", tmp_path / "results")
    assert output == tmp_path / "results" / "nonzero" / "smoke"
    assert (tmp_path / "cache" / "drift_smoke" / "pools.pkl").stat().st_mtime == pools_written
    second = json.loads((output / "rows.json").read_text())
    assert second == first                          # same seeds and splits, so the rerun is identical
    assert any(r["method"] == "R1N_nonzero_weighted" for r in second)
