"""Every constant for an experiment lives here. Defaults match Luke Miller's starter notebook #4."""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ExperimentConfig:
    """Settings for one run. Saved next to every result so a figure can be traced to the run that made it."""

    random_seed: int = 42

    # System
    qubit_count: int = 4

    # Random circuits: each has a random number of layers in [1, max_layers].
    # A layer is one random rotation on every qubit, then CX on a random subset of neighboring pairs.
    number_of_circuits: int = 400
    max_layers: int = 12
    cx_probability_per_pair: float = 0.5

    # Noise: depolarizing error after every one-qubit and two-qubit gate.
    one_qubit_depolarizing_rate: float = 0.003
    two_qubit_depolarizing_rate: float = 0.03
    noise_scale_factors: tuple[float, ...] = (1.0, 2.0, 3.0)

    # Shots per circuit per noise scale
    shots_per_circuit: int = 1000

    # Learning
    test_fraction: float = 0.25
    gradient_boosting_trees: int = 300
    gradient_boosting_depth: int = 3

    feature_names: tuple[str, ...] = field(
        default=("layer_count", "one_qubit_gate_count", "cx_count", "observable_weight"))

    def __post_init__(self) -> None:
        """Fail fast on settings that downstream code relies on."""
        if self.noise_scale_factors[0] != 1.0:
            raise ValueError("the first noise scale factor must be 1.0 (the base noise); code indexes column 0 as base")
        if self.qubit_count < 2:
            raise ValueError("need at least 2 qubits for the ZZ observables")

    @property
    def matched_budget_multiplier(self) -> int:
        """Shots multiplier that gives the unmitigated baseline the same total shots as all ZNE scales together."""
        return len(self.noise_scale_factors)

    def to_dict(self) -> dict:
        """Plain dict version for saving in result files."""
        return asdict(self)
