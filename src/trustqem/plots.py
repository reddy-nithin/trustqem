"""Poster figures. One fixed colour per method so every figure reads the same way."""

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

METHOD_COLOURS = {
    "unmitigated": "#9a9a9a",
    "unmitigated, 3x shots": "#5f5f5f",
    "ZNE linear": "#e69f00",
    "ZNE quadratic": "#d55e00",
    "learned": "#0072b2",
    "ZNE linear, exact values": "#e69f00",
    "ZNE quadratic, exact values": "#d55e00",
}


def plot_error_versus_depth(
    test_errors: dict[str, np.ndarray],
    test_layer_counts: np.ndarray,
    title: str,
) -> Figure:
    """Mean absolute error per circuit depth, one line per method. Exact-value lines are dotted references."""
    unique_layer_counts = np.unique(test_layer_counts)
    figure, axis = plt.subplots(figsize=(11, 5))
    for method_name, errors in test_errors.items():
        error_by_depth = [errors[test_layer_counts == layer_count].mean() for layer_count in unique_layer_counts]
        colour = METHOD_COLOURS.get(method_name)
        if "exact values" in method_name:
            axis.plot(unique_layer_counts, error_by_depth, linestyle=":", color=colour,
                      label=method_name + " (reference)")
        else:
            axis.plot(unique_layer_counts, error_by_depth, marker="o", color=colour, label=method_name)
    axis.set_xlabel("circuit layers")
    axis.set_ylabel("mean absolute error vs ideal")
    axis.set_title(title)
    axis.legend(loc="center left", bbox_to_anchor=(1.01, 0.5))
    figure.tight_layout()
    return figure
