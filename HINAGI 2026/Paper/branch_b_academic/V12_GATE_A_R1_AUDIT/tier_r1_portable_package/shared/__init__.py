"""Shared ARC-AGI utilities and tools."""

from shared.grid_utils import ConnectedComponent, DihedralD4, compute_frame_diff, find_components
from shared.palette import (
    ARC_COLOR_NAMES,
    ARC_PALETTE_HEX,
    generate_color_permutations,
    get_color_histogram,
    remap_colors,
    render_ascii_grid,
)
from shared.rhae_evaluator import GameEvaluationSummary, LevelResult, RHAEEvaluator

__all__ = [
    "ARC_COLOR_NAMES",
    "ARC_PALETTE_HEX",
    "ConnectedComponent",
    "DihedralD4",
    "GameEvaluationSummary",
    "LevelResult",
    "RHAEEvaluator",
    "compute_frame_diff",
    "find_components",
    "generate_color_permutations",
    "get_color_histogram",
    "remap_colors",
    "render_ascii_grid",
]
