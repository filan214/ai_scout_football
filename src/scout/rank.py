"""Need-driven target ranking (pure). Implements IMPLEMENTATION_GUIDE §6.6."""

from __future__ import annotations

import json
from collections.abc import Mapping

import pandas as pd

from scout.config import Settings

SHORTLIST_COLUMNS = [
    "club", "position_group", "need_score", "priority", "rank", "verdict", "fotmob_id", "tm_id", "player_name",
    "team_name", "league", "current_club", "age", "market_value_m", "minutes", "performance", "age_score",
    "value_score", "fit", "sub_position", "evidence", "current_best_regular", "current_best_composite",
    "upgrade_vs_current", "required_upgrade_margin", "benchmark_composite",
    "below_ambition_benchmark", "below_benchmark_stats",
]


def verdict(fit_rank: int, need_priority: str, verdict_ranks: dict[str, int]) -> str:
    """Computed verdict (§15): High need and fit rank ≤ priority_target -> "priority target";
    fit rank ≤ strong_option -> "strong option"; else "monitor"."""
    if need_priority == "High" and fit_rank <= verdict_ranks["priority_target"]:
        return "priority target"
    return "strong option" if fit_rank <= verdict_ranks["strong_option"] else "monitor"


def age_score(age: pd.Series, ideal: tuple[int, int]) -> pd.Series:
    """100 inside the ideal age range, else 100 − 10 per year outside it, floored at 0."""
    age = age.astype(float)
    outside = (ideal[0] - age).clip(lower=0) + (age - ideal[1]).clip(lower=0)
    return (100 - 10 * outside).clip(lower=0)


def eligible_pool(
    player_season: pd.DataFrame, group: str, club: str, weights: dict[str, float], settings: Settings,
    need: Mapping | None = None,
) -> pd.DataFrame:
    """Every eligible candidate for one need group, scored and sorted best first (§6.6 steps 1-6).

    Eligible: same position group, qualifying (minutes and matches, §6.4), age_min ≤ age ≤ age_max,
    market value known and ≤ budget, current club ≠ `club`. performance = Σ w_s × <stat>_pct.
    Sort fit ↓, performance ↓, market value ↑, fotmob_id ↑; a player listed in two leagues keeps his best row.
    """
    pool, fw = settings.pool, settings.fit_weights
    c = player_season[
        (player_season["position_group"] == group)
        & player_season["qualifies"]
        & player_season["age"].between(pool.age_min, pool.age_max).fillna(False).astype(bool)
        & (player_season["market_value_m"] <= pool.budget_m).fillna(False).astype(bool)
        & (player_season["current_club"] != club).fillna(True).astype(bool)
    ].copy()
    c["performance"] = sum(w * c[f"{s}_pct"] for s, w in weights.items())
    c = c[c["performance"].notna()]
    if need is not None:
        best = need.get("current_best_composite")
        c["evidence"] = need.get("evidence", "insufficient")
        c["current_best_regular"] = need.get("current_best_regular")
        c["current_best_composite"] = best
        c["upgrade_vs_current"] = c["performance"] - best if pd.notna(best) else float("nan")
        c["required_upgrade_margin"] = settings.upgrade_margin
        c = c[(c["evidence"] == "sufficient") & (c["upgrade_vs_current"] >= settings.upgrade_margin)].copy()
        bench = json.loads(need["benchmark"])
        c["benchmark_composite"] = sum(w * bench[stat] for stat, w in weights.items())
        below = [[stat for stat, w in weights.items() if w > 0 and row[f"{stat}_pct"] < bench[stat]]
                 for _, row in c.iterrows()]
        c["below_benchmark_stats"] = [json.dumps(stats) for stats in below]
        c["below_ambition_benchmark"] = [settings.ambition in ("title", "top4") and bool(stats) for stats in below]
    if "sub_position" not in c:
        c["sub_position"] = None
    c["age_score"] = age_score(c["age"], pool.ideal_age)
    c["value_score"] = 100 * (1 - 0.5 * c["market_value_m"] / pool.budget_m)
    c["fit"] = fw["performance"] * c["performance"] + fw["age"] * c["age_score"] + fw["value"] * c["value_score"]
    c = c.sort_values(["fit", "performance", "market_value_m", "fotmob_id"], ascending=[False, False, True, True])
    return c.drop_duplicates("fotmob_id")


def ranked_groups(needs_for_club: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    """Need rows to rank: High/Medium groups plus the `min_ranked_groups` highest-need used groups (§15)."""
    ordered = needs_for_club.sort_values(["need_score", "position_group"], ascending=[False, True])
    if "used" in ordered:
        ordered = ordered[ordered["used"].astype(bool)]
    if "evidence" in ordered:
        ordered = ordered[ordered["evidence"] == "sufficient"]
    top = set(ordered["position_group"].head(settings.min_ranked_groups))
    return ordered[ordered["priority"].isin(["High", "Medium"]) | ordered["position_group"].isin(top)]


def rank_targets(player_season: pd.DataFrame, needs_for_club: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    """Top `shortlist_size` targets for each ranked need group of one club (§6.6): High/Medium groups plus
    the `min_ranked_groups` highest-need groups whatever their priority (§15). See `eligible_pool`.
    """
    out = []
    for need in ranked_groups(needs_for_club, settings).itertuples():
        c = eligible_pool(player_season, need.position_group, need.club, json.loads(need.stat_weights), settings,
                          need._asdict())
        c = c.head(settings.shortlist_size)
        c = c.assign(club=need.club, need_score=need.need_score, priority=need.priority, rank=range(1, len(c) + 1))
        c["verdict"] = [verdict(r, need.priority, settings.verdict_ranks) for r in c["rank"]]
        out.append(c)
    if not out:
        return pd.DataFrame(columns=SHORTLIST_COLUMNS)
    return pd.concat(out, ignore_index=True)[SHORTLIST_COLUMNS]
