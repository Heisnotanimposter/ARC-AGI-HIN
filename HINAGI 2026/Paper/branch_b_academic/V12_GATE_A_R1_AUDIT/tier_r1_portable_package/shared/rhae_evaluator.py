"""ARC-AGI-3 Relative Human Action Efficiency (RHAE) Evaluator.

RHAE measures agent proficiency on interactive environments:
  - Task completion (binary per level, sequential advancement)
  - Action efficiency relative to human upper-median baseline:
    S_{l,e} = min(115.0, (human_actions / agent_actions) ** 2 * 100.0)

Official Scorer Parity Contract:
  - Exactly mirrors official TAAF GameRun._compute_final_score() (taaf/game.py:381)
    and arc_agi.scorecard.EnvironmentScoreCalculator (v0.9.8).
  - 1-indexed level weighting: level 0 -> weight 1, level 1 -> weight 2, etc.
  - Completion cap = (max_weights / total_weights) * 100.0, where max_weights
    sums only levels that achieved score > 0.
  - Final game score = min(raw_weighted_score, completion_cap).
  - Fail-closed: Heuristic 30-action default is eliminated. Missing baselines
    raise ValueError in strict mode or return 0.0 in non-strict mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Union


def compute_taaf_final_score(
    base_actions_per_level: Optional[Sequence[int]],
    actions_per_level: Sequence[int],
    number_of_levels: int,
    levels_completed: int,
) -> float:
    """Official ARC-AGI-3 RHAE score formula.

    Mirrors ``arc_agi.scorecard.EnvironmentScoreCalculator`` (v0.9.8) and
    official TAAF ``GameRun._compute_final_score()`` (taaf/game.py:381).

    Per level: ``min(115.0, (baseline / actions) ** 2 * 100.0)`` if completed
    with >= 1 action and baseline > 0, else 0.0. Weights are 1-indexed (level 0 -> 1).
    Final score is ``total_score / total_weights`` capped at
    ``max_weights / total_weights * 100.0``, where ``max_weights``
    sums only levels that scored > 0.

    Returns 0.0 if base_actions_per_level is None or number_of_levels == 0.
    """
    if base_actions_per_level is None or number_of_levels == 0:
        return 0.0
    total_score = 0.0
    total_weights = 0
    max_weights = 0
    for level_idx in range(number_of_levels):
        weight = level_idx + 1
        total_weights += weight
        completed = level_idx < levels_completed
        actions = actions_per_level[level_idx] if level_idx < len(actions_per_level) else 0
        baseline = base_actions_per_level[level_idx] if level_idx < len(base_actions_per_level) else 0
        if completed and actions > 0 and baseline > 0:
            level_score = min(115.0, (baseline / actions) ** 2 * 100.0)
        else:
            level_score = 0.0
        if level_score > 0:
            max_weights += weight
        total_score += level_score * weight
    if total_weights == 0:
        return 0.0
    score = total_score / total_weights
    max_score = (max_weights / total_weights) * 100.0
    return min(score, max_score)


@dataclass
class LevelResult:
    game_id: str
    level_index: int
    completed: bool
    agent_actions: int
    human_baseline_actions: int  # Mandatory human baseline; no heuristic default
    weight: int = 1
    level_score: float = 0.0

    def __post_init__(self):
        if self.weight <= 0:
            self.weight = self.level_index + 1
        if self.level_score == 0.0 and self.completed and self.agent_actions > 0 and self.human_baseline_actions > 0:
            ratio = self.human_baseline_actions / self.agent_actions
            self.level_score = min(115.0, float((ratio ** 2) * 100.0))

    @property
    def rhae(self) -> float:
        """Returns RHAE score on 0.0..115.0 scale."""
        return self.level_score

    @property
    def rhae_ratio(self) -> float:
        """Returns RHAE ratio on 0.0..1.15 scale for backward compatibility."""
        return self.level_score / 100.0


@dataclass
class GameEvaluationSummary:
    game_id: str
    total_levels: int
    levels_completed: int
    sequential_completed_k: int
    total_agent_actions: int
    total_human_actions: int
    raw_game_score: float  # Scale 0.0..115.0
    completion_cap: float  # Scale 0.0..100.0
    game_score: float      # Scale 0.0..100.0 (Official final score)
    average_rhae: float    # Identical to game_score (0.0..100.0)
    level_details: List[LevelResult] = field(default_factory=list)

    @property
    def final_score(self) -> float:
        """Official final score alias matching TAAF GameRun.final_score."""
        return self.game_score

    @property
    def raw_game_score_ratio(self) -> float:
        """Scale 0.0..1.15 for backward compatibility."""
        return self.raw_game_score / 100.0

    @property
    def completion_cap_ratio(self) -> float:
        """Scale 0.0..1.0 for backward compatibility."""
        return self.completion_cap / 100.0

    @property
    def game_score_ratio(self) -> float:
        """Scale 0.0..1.0 for backward compatibility."""
        return self.game_score / 100.0


class RHAEEvaluator:
    """Evaluates ARC-AGI-3 agent performance across games and levels according to official methodology."""

    def __init__(
        self,
        human_baselines: Optional[Dict[str, Union[Dict[int, int], Sequence[int]]]] = None,
        strict: bool = False,
    ):
        """
        human_baselines: dict mapping game_id -> {level_index: human_action_count} or list of action counts
        strict: If True, raises ValueError when baseline actions are missing (for offline scorer parity verification).
                If False (default for runtime agent execution), scores 0.0 when baseline is missing,
                ensuring live submission runs in hidden test environments (where baselines are None)
                never abort or crash gameplay.
                Default 30-action heuristic fallback is strictly ELIMINATED in both modes.
        """
        self.human_baselines = human_baselines or {}
        self.strict = strict

    def get_human_actions(self, game_id: str, level_index: int) -> int:
        """Retrieve human baseline actions for game and level.
        
        Raises ValueError if baseline is missing in strict mode (fail-closed).
        """
        if game_id in self.human_baselines:
            game_base = self.human_baselines[game_id]
            if isinstance(game_base, dict) and level_index in game_base:
                return int(game_base[level_index])
            elif isinstance(game_base, (list, tuple)) and level_index < len(game_base):
                return int(game_base[level_index])

        if self.strict:
            raise ValueError(
                f"Missing human baseline actions for game '{game_id}', level {level_index}. "
                "Official evaluation fails closed: no heuristic 30-action fallback is permitted."
            )
        return 0

    def evaluate_game(
        self,
        game_id: str,
        level_completions: Sequence[bool],
        level_actions: Sequence[int],
        base_actions_per_level: Optional[Sequence[int]] = None,
    ) -> GameEvaluationSummary:
        total_levels = len(level_completions)
        results: List[LevelResult] = []
        total_agent_acts = sum(level_actions)
        total_human_acts = 0

        # Resolve baselines
        resolved_baselines: List[int] = []
        if base_actions_per_level is not None:
            resolved_baselines = list(base_actions_per_level)
            while len(resolved_baselines) < total_levels:
                resolved_baselines.append(0)
        elif game_id in self.human_baselines:
            for idx in range(total_levels):
                resolved_baselines.append(self.get_human_actions(game_id, idx))
        else:
            if self.strict:
                raise ValueError(
                    f"Missing human baseline actions for game '{game_id}'. "
                    "Official evaluation fails closed: no heuristic 30-action fallback is permitted."
                )
            resolved_baselines = [0] * total_levels

        # Sequential completion count (k contiguous levels completed from index 0)
        seq_k = 0
        for done in level_completions:
            if done:
                seq_k += 1
            else:
                break

        total_weights = 0
        max_weights = 0
        total_score = 0.0

        for idx in range(total_levels):
            weight = idx + 1
            total_weights += weight
            completed = idx < seq_k
            acts = level_actions[idx] if idx < len(level_actions) else 0
            h_acts = resolved_baselines[idx] if idx < len(resolved_baselines) else 0
            total_human_acts += h_acts

            if completed and acts > 0 and h_acts > 0:
                level_score = min(115.0, (h_acts / acts) ** 2 * 100.0)
            else:
                level_score = 0.0

            if level_score > 0.0:
                max_weights += weight

            total_score += level_score * weight

            res = LevelResult(
                game_id=game_id,
                level_index=idx,
                completed=completed,
                agent_actions=acts,
                human_baseline_actions=h_acts,
                weight=weight,
                level_score=level_score,
            )
            results.append(res)

        if total_weights == 0:
            raw_game_score = 0.0
            completion_cap = 0.0
            final_game_score = 0.0
        else:
            raw_game_score = total_score / total_weights
            completion_cap = (max_weights / total_weights) * 100.0
            final_game_score = min(raw_game_score, completion_cap)

        return GameEvaluationSummary(
            game_id=game_id,
            total_levels=total_levels,
            levels_completed=seq_k,
            sequential_completed_k=seq_k,
            total_agent_actions=total_agent_acts,
            total_human_actions=total_human_acts,
            raw_game_score=raw_game_score,
            completion_cap=completion_cap,
            game_score=final_game_score,
            average_rhae=final_game_score,
            level_details=results,
        )

    def evaluate_benchmark(
        self, game_results: Sequence[GameEvaluationSummary]
    ) -> Dict[str, float]:
        if not game_results:
            return {
                "mean_rhae": 0.0,
                "score_sum": 0.0,
                "progressed_games": 0,
                "completion_rate": 0.0,
                "total_completed_levels": 0,
                "total_levels": 0,
            }

        score_sum = sum(g.game_score for g in game_results)
        total_completed = sum(g.levels_completed for g in game_results)
        total_levels = sum(g.total_levels for g in game_results)
        progressed = sum(1 for g in game_results if g.game_score > 0.0)

        return {
            "mean_rhae": score_sum / len(game_results),
            "score_sum": score_sum,
            "progressed_games": progressed,
            "completion_rate": (total_completed / max(1, total_levels)) * 100.0,
            "total_completed_levels": total_completed,
            "total_levels": total_levels,
        }
