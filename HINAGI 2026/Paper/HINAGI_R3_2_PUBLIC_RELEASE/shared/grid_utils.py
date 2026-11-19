"""ARC Grid Manipulations, Geometric Symmetries, and Difference Analysis."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

Grid = List[List[int]]


class DihedralD4:
    """The 8 operations of the Dihedral D4 group on 2D grids."""

    NAMES = (
        "rot0",
        "rot90",
        "rot180",
        "rot270",
        "flip_h",
        "flip_v",
        "transpose",
        "anti_transpose",
    )

    @staticmethod
    def rot0(g: Grid) -> Grid:
        return [row[:] for row in g]

    @staticmethod
    def rot90(g: Grid) -> Grid:
        h, w = len(g), len(g[0])
        return [[g[h - 1 - r][c] for r in range(h)] for c in range(w)]

    @staticmethod
    def rot180(g: Grid) -> Grid:
        return [row[::-1] for row in g[::-1]]

    @staticmethod
    def rot270(g: Grid) -> Grid:
        h, w = len(g), len(g[0])
        return [[g[r][w - 1 - c] for r in range(h)] for c in range(w)]

    @staticmethod
    def flip_h(g: Grid) -> Grid:
        return [row[::-1] for row in g]

    @staticmethod
    def flip_v(g: Grid) -> Grid:
        return g[::-1]

    @staticmethod
    def transpose(g: Grid) -> Grid:
        h, w = len(g), len(g[0])
        return [[g[r][c] for r in range(h)] for c in range(w)]

    @staticmethod
    def anti_transpose(g: Grid) -> Grid:
        h, w = len(g), len(g[0])
        return [[g[h - 1 - r][w - 1 - c] for r in range(h)] for c in range(w)]

    # Inverses for each transformation
    INVERSES = {
        "rot0": "rot0",
        "rot90": "rot270",
        "rot180": "rot180",
        "rot270": "rot90",
        "flip_h": "flip_h",
        "flip_v": "flip_v",
        "transpose": "transpose",
        "anti_transpose": "anti_transpose",
    }

    @classmethod
    def apply(cls, name: str, g: Grid) -> Grid:
        fn = getattr(cls, name, None)
        if fn is None:
            raise ValueError(f"Unknown D4 operation: {name}")
        return fn(g)

    @classmethod
    def invert(cls, name: str, g: Grid) -> Grid:
        inv_name = cls.INVERSES.get(name, "rot0")
        return cls.apply(inv_name, g)

    @classmethod
    def all_transforms(cls, g: Grid) -> List[Tuple[str, Grid]]:
        return [(name, cls.apply(name, g)) for name in cls.NAMES]


@dataclass
class ConnectedComponent:
    color: int
    cells: List[Tuple[int, int]]  # (r, c)
    min_r: int
    max_r: int
    min_c: int
    max_c: int

    @property
    def height(self) -> int:
        return self.max_r - self.min_r + 1

    @property
    def width(self) -> int:
        return self.max_c - self.min_c + 1

    @property
    def area(self) -> int:
        return len(self.cells)

    @property
    def bbox(self) -> Tuple[int, int, int, int]:
        return (self.min_r, self.min_c, self.max_r, self.max_c)

    @property
    def centroid(self) -> Tuple[float, float]:
        r_sum = sum(r for r, _ in self.cells)
        c_sum = sum(c for _, c in self.cells)
        n = len(self.cells)
        return (r_sum / n, c_sum / n)

    def crop_mask(self) -> List[List[int]]:
        """Extract a tight normalized grid of this component."""
        h, w = self.height, self.width
        mask = [[0 for _ in range(w)] for _ in range(h)]
        for r, c in self.cells:
            mask[r - self.min_r][c - self.min_c] = self.color
        return mask


def find_components(
    grid: Sequence[Sequence[int]],
    ignore_colors: Sequence[int] = (0,),
    connectivity: int = 4,
) -> List[ConnectedComponent]:
    """Find connected components in grid using BFS flood fill.
    connectivity: 4 or 8.
    """
    if not grid or not grid[0]:
        return []

    h, w = len(grid), len(grid[0])
    visited: Set[Tuple[int, int]] = set()
    components: List[ConnectedComponent] = []

    neighbor_deltas = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if connectivity == 8:
        neighbor_deltas += [(-1, -1), (-1, 1), (1, -1), (1, 1)]

    ignore_set = set(ignore_colors)

    for r in range(h):
        for c in range(w):
            if (r, c) in visited:
                continue
            color = grid[r][c]
            if color in ignore_set:
                continue

            # BFS flood fill
            cells: List[Tuple[int, int]] = []
            queue = deque([(r, c)])
            visited.add((r, c))
            min_r, max_r = r, r
            min_c, max_c = c, c

            while queue:
                curr_r, curr_c = queue.popleft()
                cells.append((curr_r, curr_c))
                min_r = min(min_r, curr_r)
                max_r = max(max_r, curr_r)
                min_c = min(min_c, curr_c)
                max_c = max(max_c, curr_c)

                for dr, dc in neighbor_deltas:
                    nr, nc = curr_r + dr, curr_c + dc
                    if 0 <= nr < h and 0 <= nc < w:
                        if (nr, nc) not in visited and grid[nr][nc] == color:
                            visited.add((nr, nc))
                            queue.append((nr, nc))

            components.append(
                ConnectedComponent(
                    color=color,
                    cells=cells,
                    min_r=min_r,
                    max_r=max_r,
                    min_c=min_c,
                    max_c=max_c,
                )
            )

    return components


@dataclass
class FrameDiffResult:
    total_changed_cells: int
    gameplay_changed_cells: int
    board_changed: bool
    gameplay_changed: bool
    changed_coords: List[Tuple[int, int]]
    old_values: List[int]
    new_values: List[int]


def compute_frame_diff(
    before: Sequence[Sequence[int]],
    after: Sequence[Sequence[int]],
    border_width: int = 4,
) -> FrameDiffResult:
    """Compute exact cell-by-cell difference between two frames.
    Distinguishes whole-board changes from interior gameplay-area changes.
    """
    if len(before) != len(after) or len(before[0]) != len(after[0]):
        # Shape mismatch / full redraw
        return FrameDiffResult(
            total_changed_cells=-1,
            gameplay_changed_cells=-1,
            board_changed=True,
            gameplay_changed=True,
            changed_coords=[],
            old_values=[],
            new_values=[],
        )

    h, w = len(before), len(before[0])
    total_changed = 0
    gameplay_changed_count = 0
    changed_coords: List[Tuple[int, int]] = []
    old_vals: List[int] = []
    new_vals: List[int] = []

    for r in range(h):
        for c in range(w):
            if before[r][c] != after[r][c]:
                total_changed += 1
                changed_coords.append((r, c))
                old_vals.append(before[r][c])
                new_vals.append(after[r][c])

                # Check if inside gameplay area (excluding outer border)
                is_interior = (
                    border_width <= r < (h - border_width)
                    and border_width <= c < (w - border_width)
                )
                if is_interior:
                    gameplay_changed_count += 1

    return FrameDiffResult(
        total_changed_cells=total_changed,
        gameplay_changed_cells=gameplay_changed_count,
        board_changed=(total_changed > 0),
        gameplay_changed=(gameplay_changed_count > 0),
        changed_coords=changed_coords,
        old_values=old_vals,
        new_values=new_vals,
    )
