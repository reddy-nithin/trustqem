# Running Stage 4 on IBM hardware

Stage 4 runs the experiment on a real IBM Heron device. The analysis needs only the folders these commands write,
so everything except the four commands below can happen elsewhere. Hypotheses and pass rules for Stage 4 are in
Amendment 3 of [HYPOTHESES.md](HYPOTHESES.md); they were committed before any hardware job ran.

## What runs, and what it costs

Each session (one day on the device) runs 180 circuits: 60 test circuits, 60 oracle circuits (random circuits whose
ideal values we compute classically, to give a labeled baseline) and 60 near-Clifford twins with 8 non-Clifford
rotations each. Every circuit runs at fold scales 1, 3 and 5 with 1000 shots: 540 circuit executions and 540,000
shots per session. IBM's documented formula (about 2 s per job plus 250 µs reset time and the circuit time per shot)
puts that at about 140 s of QPU time. Two sessions use about 280 s of the Open Plan's 600 s. `submit` refuses to send
a job estimated above 200 s unless you add `--force`.

The model is never trained on hardware data: "Monday" is simulated from the device's calibration on the first
session's day. Session 2 runs the same circuits on the same qubits at least 3 days later.

## One-time setup

1. Create an account on [IBM Quantum Platform](https://quantum.cloud.ibm.com) and an Open Plan instance.
2. Copy your API key from the dashboard and your instance CRN from the Instances page.
3. Save them on your own machine (once). Never paste the key into the repo, a notebook that gets committed, or chat.

   ```bash
   uv run python -c "from qiskit_ibm_runtime import QiskitRuntimeService as S; \
   S.save_account(channel='ibm_quantum_platform', token='YOUR_API_KEY', instance='YOUR_CRN', set_as_default=True)"
   ```

   The key is stored in `~/.qiskit/qiskit-ibm.json`, outside the repo. Check IBM's
   [save credentials guide](https://quantum.cloud.ibm.com/docs/guides/save-credentials) if the call has changed.

4. Confirm access and pick the device:

   ```bash
   uv run trustqem hardware check --backend ibm_fez
   ```

   It lists the Heron devices your plan can use, their queues, and your remaining usage. If `ibm_fez` is not listed,
   use one that is (for example `ibm_marrakesh` or `ibm_torino`) and pass the same `--backend` to every command.

## Session 1

```bash
uv run trustqem hardware prepare --session S1 --backend ibm_fez
uv run trustqem hardware submit  --session S1
uv run trustqem hardware fetch   --session S1      # waits until the job has finished
```

`prepare` records the day's calibration and picks the 4-qubit line with the lowest summed two-qubit and readout
error. `submit` returns as soon as the job is queued (its id is saved in `jobs.json`), so you can close the laptop;
run `fetch` later. Then commit and push `results/hardware/S1/`.

## Session 2 (3 or more days later)

```bash
uv run trustqem hardware prepare --session S2 --pair-with S1
uv run trustqem hardware submit  --session S2
uv run trustqem hardware fetch   --session S2
```

`--pair-with S1` reuses the circuits and qubits of session 1 and records the new day's calibration. Commit and push
`results/hardware/S2/`.

## Analysis

```bash
uv run trustqem hardware analyze
```

This simulates Monday (about 4 minutes), scores every method on each session with circuit-bootstrap confidence
intervals, and writes `summary.json` per session, `results/hardware/verdict.md` and `coverage_by_session.png`.

## Rehearsal without an account

Add `--dry-run` to any command to use FakeFez in local mode instead of the device. Dry runs write to
`results/hardware/dryrun/`, which git ignores. In local mode the error-suppression options are ignored, and IBM
reports zero usage.

## If something goes wrong

- A job fails or is cancelled: run `submit` once more for the same session (the circuits are unchanged) and note it
  in the research log. Amendment 3 allows one re-run and excludes no data.
- The chosen qubits look worse on session 2 than on session 1: run it anyway. That change is part of what is tested.
