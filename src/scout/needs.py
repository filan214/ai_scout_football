"""Squad need scores and need-driven stat weights (pure). Implements IMPLEMENTATION_GUIDE §6.5."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from scout import features
from scout.config import Settings

NEED_DEFINITION = ("Need = shortfall against the selected ambition (primary), plus depth, age and contract "
                   "urgency within the remaining range (secondary).")

NEEDS_COLUMNS = [
    "club", "ambition", "position_group", "used", "usage", "squad_players", "reliable", "regulars", "minutes",
    "depth_gap", "quality_gap", "age_risk", "contract_risk", "need_score", "priority", "squad_pct", "benchmark",
    "stat_weights", "rated_minutes", "rated_share", "evidence", "squad_pct_used", "imputed_stats",
    "current_best_regular", "current_best_regular_id", "current_best_composite",
]


def team_clubs(player_season: pd.DataFrame, league: str) -> pd.Series:
    """FotMob team_id -> Transfermarkt club name in `league`: most common current club of the team's players."""
    rows = player_season[(player_season["league"] == league) & player_season["current_club"].notna()]
    return rows.groupby("team_id")["current_club"].agg(lambda c: c.value_counts().sort_index().idxmax())


def league_clubs(player_season: pd.DataFrame, league: str) -> list[str]:
    """Transfermarkt names of the clubs in `league` (see `team_clubs`)."""
    return sorted(team_clubs(player_season, league).unique())


def squad_quality(group_rows: pd.DataFrame, stats: list[str]) -> dict[str, float | None]:
    """Minutes-weighted squad percentile per stat over players that have one; None when nobody has."""
    out: dict[str, float | None] = {}
    for stat in stats:
        pct = group_rows[f"{stat}_pct"]
        rated = group_rows["minutes"].where(pct.notna(), 0)
        out[stat] = float((rated * pct.fillna(0)).sum() / rated.sum()) if rated.sum() > 0 else None
    return out


def league_levels(
    player_season: pd.DataFrame, settings: Settings, profiles: pd.DataFrame | None = None,
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]]]:
    """§6.5 squad levels of the target league's clubs per group and stat: (benchmark B_s, median club level).

    B_s = level of the k-th best club, k from the ambition. Clubs without a rated player for a stat are not
    ranked; with fewer rated clubs than k the last one counts; with none, both levels are 100.
    """
    k = settings.ambition_club_rank[settings.ambition]
    clubs = league_clubs(player_season, settings.target_league)
    profiles = features.squad_profiles(player_season, settings) if profiles is None else profiles
    rows = profiles[profiles["current_club"].isin(clubs) & profiles["position_group"].notna()]
    bench: dict[str, dict[str, float]] = {}
    median: dict[str, dict[str, float]] = {}
    for group, stats in settings.position_stats.items():
        g = rows[rows["position_group"] == group]
        per_club = [squad_quality(g[g["current_club"] == club], stats) for club in clubs]
        bench[group], median[group] = {}, {}
        for stat in stats:
            levels = sorted((q[stat] for q in per_club if q[stat] is not None), reverse=True)
            bench[group][stat] = levels[min(k, len(levels)) - 1] if levels else 100.0
            median[group][stat] = float(np.median(levels)) if levels else 100.0
    return bench, median


def benchmarks(player_season: pd.DataFrame, settings: Settings) -> dict[str, dict[str, float]]:
    """§6.5 B_s per group and stat (see `league_levels`)."""
    return league_levels(player_season, settings)[0]


def stat_weights(gaps: dict[str, float], blend: float) -> dict[str, float]:
    """§6.5: w_s = blend × gap_s / Σ gap + (1 − blend) / k; equal weights when every gap is 0."""
    k = len(gaps)
    total = sum(gaps.values())
    return {s: blend * (g / total if total > 0 else 1 / k) + (1 - blend) / k for s, g in gaps.items()}


def combine_need(depth: float, quality: float, age: float, contract: float, weights: dict[str, float]) -> float:
    """§6.5 Candidate A: quality shortfall plus secondary urgency within the remaining range."""
    urgency = weights["depth"] * depth + weights["age"] * age + weights["contract"] * contract
    return float(quality + (1 - quality / 100) * urgency)


def compute_needs(
    player_season: pd.DataFrame, club: str, settings: Settings, *, profiles: pd.DataFrame | None = None,
    levels: tuple[dict, dict] | None = None,
) -> pd.DataFrame:
    """Need score per position group for `club` (§6.5); one row per group in settings.squad.depth_targets.

    Squad = combined profiles whose current Transfermarkt club is `club`, weighted by season minutes.
    Depth counts fractional regulars, Σ min(1, minutes / reliable_minutes). For squad.optional_groups the
    target is scaled by usage = min(1, club share of outfield minutes / typical share); below
    squad.min_usage the club does not play that position and its need is 0 (§15).
    Quality compares the squad's minutes-weighted percentile per stat with B_s (`league_levels`):
    quality_gap = 100 × mean_s(max(0, B_s − squad_pct_s) / B_s). A stat nobody in the squad is rated on
    takes the league's median club level only behind an explicit insufficient-evidence state (§15).
    Unknown age or contract = not at risk.
    """
    profiles = features.squad_profiles(player_season, settings) if profiles is None else profiles
    squad = profiles[(profiles["current_club"] == club) & profiles["position_group"].notna()]
    bench, median = league_levels(player_season, settings, profiles) if levels is None else levels
    w = settings.need_weights
    rm = settings.squad.reliable_minutes
    outfield_minutes = float(squad["minutes"].sum())
    total_target = sum(settings.squad.depth_targets.values())
    rows = []
    for group, target in settings.squad.depth_targets.items():
        g = squad[squad["position_group"] == group]
        stats = settings.position_stats[group]
        total_minutes = float(g["minutes"].sum())
        per_player = g.groupby("fotmob_id")["minutes"].sum()
        reliable = int((per_player >= rm).sum())
        regulars = float(per_player.clip(upper=rm).sum() / rm)
        usage = 1.0
        if group in settings.squad.optional_groups:
            share = total_minutes / outfield_minutes if outfield_minutes > 0 else 0.0
            usage = min(1.0, share / (target / total_target))
        used = usage >= settings.squad.min_usage
        squad_pct = squad_quality(g, stats)
        rated_minutes = float(g["rated_minutes"].sum())
        rated_share = rated_minutes / total_minutes if total_minutes > 0 else 0.0
        imputed = [s for s in stats if squad_pct[s] is None]
        evidence = ("not_used" if not used else "insufficient"
                    if rated_share < settings.min_rated_share or imputed else "sufficient")
        level = {s: median[group][s] if squad_pct[s] is None else squad_pct[s] for s in stats}
        gaps = {s: max(0.0, bench[group][s] - level[s]) for s in stats}
        relative = [gaps[s] / bench[group][s] if bench[group][s] > 0 else 0.0 for s in stats]

        if not used:
            depth_gap, quality_gap, age_risk, contract_risk = 0.0, 0.0, 0.0, 0.0
        elif total_minutes == 0:
            depth_gap, quality_gap, age_risk, contract_risk = 100.0, 100.0, 0.0, 0.0
        else:
            effective_target = target * usage
            depth_gap = float(np.clip(100 * (effective_target - regulars) / effective_target, 0, 100))
            quality_gap = float(np.clip(100 * np.mean(relative), 0, 100))
            old = (g["age"] >= settings.age_risk_threshold).fillna(False).astype(bool)
            expiring = (g["contract_months_left"] <= settings.contract_risk_months).fillna(False).astype(bool)
            age_risk = float(100 * g.loc[old, "minutes"].sum() / total_minutes)
            contract_risk = float(100 * g.loc[expiring, "minutes"].sum() / total_minutes)

        need_score = combine_need(depth_gap, quality_gap, age_risk, contract_risk, w)
        bands = settings.priority_bands
        priority = "High" if need_score >= bands["high"] else "Medium" if need_score >= bands["medium"] else "Low"
        weights = stat_weights(gaps, settings.stat_weight_blend)
        regular = g[(g["minutes"] >= rm) & g["fully_rated"]].copy()
        regular["composite"] = sum(weight * regular[f"{stat}_pct"] for stat, weight in weights.items())
        regular = regular.sort_values(["composite", "fotmob_id"], ascending=[False, True])
        best = regular.iloc[0] if len(regular) else None
        rows.append({
            "club": club, "ambition": settings.ambition, "position_group": group, "used": used,
            "usage": usage, "squad_players": int(g["fotmob_id"].nunique()), "reliable": reliable,
            "regulars": regulars, "minutes": int(total_minutes),
            "depth_gap": depth_gap, "quality_gap": quality_gap, "age_risk": age_risk, "contract_risk": contract_risk,
            "need_score": float(need_score), "priority": priority, "squad_pct": json.dumps(squad_pct),
            "benchmark": json.dumps(bench[group]),
            "stat_weights": json.dumps(weights),
            "rated_minutes": rated_minutes, "rated_share": rated_share, "evidence": evidence,
            "squad_pct_used": json.dumps(level), "imputed_stats": json.dumps(imputed),
            "current_best_regular": best.get("player_name", best["fotmob_id"]) if best is not None else None,
            "current_best_regular_id": best["fotmob_id"] if best is not None else None,
            "current_best_composite": float(best["composite"]) if best is not None else None,
        })
    return pd.DataFrame(rows, columns=NEEDS_COLUMNS)


def compute_all_needs(player_season: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    """§6.5 all target-league clubs, sharing the same combined profiles and benchmark."""
    profiles = features.squad_profiles(player_season, settings)
    levels = league_levels(player_season, settings, profiles)
    return pd.concat([compute_needs(player_season, club, settings, profiles=profiles, levels=levels)
                      for club in league_clubs(player_season, settings.target_league)], ignore_index=True)
