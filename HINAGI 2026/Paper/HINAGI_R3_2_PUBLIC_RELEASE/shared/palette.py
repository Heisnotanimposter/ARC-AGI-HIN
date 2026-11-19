"""ARC Color Palette and Visualization Utilities.

Standard 10 colors for ARC-AGI tasks:
  0: Black (#000000)
  1: Blue (#1E77B4)
  2: Red (#D62728)
  3: Green (#2CA02C)
  4: Yellow (#FFD700)
  5: Gray (#7F7F7F)
  6: Magenta (#E377C2)
  7: Orange (#FF7F0E)
  8: Teal (#17BECF)
  9: Maroon (#8C564B)
"""

from __future__ import annotations

import itertools
from typing import Dict, List, Sequence, Tuple

ARC_PALETTE_HEX: Dict[int, str] = {
    0: "#000000",  # Background / Black
    1: "#1E77B4",  # Blue
    2: "#D62728",  # Red
    3: "#2CA02C",  # Green
    4: "#FFD700",  # Yellow
    5: "#7F7F7F",  # Gray
    6: "#E377C2",  # Magenta
    7: "#FF7F0E",  # Orange
    8: "#17BECF",  # Teal
    9: "#8C564B",  # Maroon
}

ARC_COLOR_NAMES: Dict[int, str] = {
    0: "black",
    1: "blue",
    2: "red",
    3: "green",
    4: "yellow",
    5: "gray",
    6: "magenta",
    7: "orange",
    8: "teal",
    9: "maroon",
}

ANSI_COLORS: Dict[int, str] = {
    0: "\033[40m  \033[0m",  # Black
    1: "\033[44m  \033[0m",  # Blue
    2: "\033[41m  \033[0m",  # Red
    3: "\033[42m  \033[0m",  # Green
    4: "\033[43m  \033[0m",  # Yellow
    5: "\033[47m  \033[0m",  # Gray
    6: "\033[45m  \033[0m",  # Magenta
    7: "\033[48;5;208m  \033[0m",  # Orange
    8: "\033[46m  \033[0m",  # Teal
    9: "\033[48;5;95m  \033[0m",  # Maroon
}


def render_ascii_grid(grid: Sequence[Sequence[int]], use_ansi: bool = False) -> str:
    """Render a 2D integer grid into string representation."""
    lines: List[str] = []
    for row in grid:
        if use_ansi:
            line = "".join(ANSI_COLORS.get(val, "??") for val in row)
        else:
            line = " ".join(str(val) for val in row)
        lines.append(line)
    return "\n".join(lines)


def get_color_histogram(grid: Sequence[Sequence[int]]) -> Dict[int, int]:
    """Return counts of each color present in the grid."""
    hist: Dict[int, int] = {c: 0 for c in range(10)}
    for row in grid:
        for val in row:
            if 0 <= val <= 9:
                hist[val] += 1
    return {c: count for c, count in hist.items() if count > 0}


def remap_colors(
    grid: Sequence[Sequence[int]], color_map: Dict[int, int]
) -> List[List[int]]:
    """Remap colors in grid according to color_map."""
    return [[color_map.get(val, val) for val in row] for row in grid]


def generate_color_permutations(
    present_colors: Sequence[int], preserve_zero: bool = True, max_perms: int = 8
) -> List[Dict[int, int]]:
    """Generate color permutation mappings preserving background (0) by default."""
    colors = [c for c in present_colors if not (preserve_zero and c == 0)]
    if not colors:
        return [{}]

    perms: List[Dict[int, int]] = []
    for p in itertools.permutations(colors):
        mapping = {orig: target for orig, target in zip(colors, p)}
        if preserve_zero:
            mapping[0] = 0
        perms.append(mapping)
        if len(perms) >= max_perms:
            break
    return perms
