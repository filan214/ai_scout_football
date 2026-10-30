"""Backtest, sensitivity, UEFA-coefficient validation and charts. Implements IMPLEMENTATION_GUIDE §7.2-§7.4."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from scout import clean, features, needs, rank  # noqa: E402
from scout.config import League, Settings  # noqa: E402

# Reference palette (dataviz skill): one series, ink for text, recessive grid.
SURFACE, INK, INK_MUTED, SERIES, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#2a78d6", "#e4e3df"


# ---------------------------------------------------------------- shared
def season_table(
    perf: pd.DataFrame, id_map: pd.DataFrame, tm_players: pd.DataFrame, tm_vals: pd.DataFrame,
    team_stats: pd.DataFrame, leagues: list[League], settings: Settings, season: str, as_of: date,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(player_season with percentiles, league strength) for one season, valued as of `as_of` (§6.3-§6.4)."""
    squads = features.squad_values(perf[perf["season"] == season], id_map, clean.value_as_of(tm_vals, as_of))
    strength = features.league_strength(squads, settings.league_strength_floor)
    ps = features.build_player_season(perf, id_map, tm_players, tm_vals, team_stats, strength, leagues, settings,
                                      season, as_of)
    return features.add_percentiles(ps, features.stat_columns(perf)), strength


def clubs_as_played(player_season: pd.DataFrame, target_league: str) -> pd.DataFrame:
    """§7.2 step 2: each row's club = the team it played for that season (Transfermarkt name for teams of
    the target league, FotMob name elsewhere), instead of the 2026 current club."""
    out = player_season.copy()
    names = needs.team_clubs(out, target_league)
    in_league = out["league"] == target_league
    out["current_club"] = out["team_id"].map(names).where(in_league).fillna(out["team_name"])
    return out


# ---------------------------------------------------------------- §7.2 backtest
def backtest_settings(settings: Settings) -> Settings:
    """§7.2: no historical contract evidence; set its secondary urgency to zero, retain other coefficients."""
    return settings.model_copy(update={"need_weights": {**settings.need_weights, "contract": 0.0}})


def season_results(club_games: pd.DataFrame) -> pd.DataFrame:
    """§7.5 independent strength: played-game points per game and total goal difference."""
    if club_games.duplicated(["club_id", "game_id"]).any():
        raise ValueError("duplicate club-game result")
    rows = club_games.copy()
    rows["points"] = np.select([rows.own_goals > rows.opponent_goals,
                               rows.own_goals == rows.opponent_goals], [3, 1], default=0)
    out = rows.groupby(["club_id", "club"], as_index=False).agg(
        played=("game_id", "nunique"), points=("points", "sum"),
        goals_for=("own_goals", "sum"), goals_against=("opponent_goals", "sum"))
    out["points_per_game"] = out["points"] / out["played"]
    out["goal_difference"] = out["goals_for"] - out["goals_against"]
    return out.sort_values(["points_per_game", "goal_difference", "goals_for", "club"],
                           ascending=[False, False, False, True]).reset_index(drop=True)


def calibrate_needs(
    all_needs: pd.DataFrame, results: pd.DataFrame, values: pd.Series, settings: Settings, expected_matches: int,
) -> dict:
    """§7.5 fixed acceptance checks a–e; no fitting, threshold search or silent exclusion of failed clubs."""
    ev = settings.evaluation
    ambitions = ["survive", "midtable", "top4", "title"]
    pivot = all_needs.pivot(index=["club", "position_group"], columns="ambition", values="need_score")
    decreases = []
    comparisons = 0
    for low, high in zip(ambitions, ambitions[1:], strict=False):
        paired = pivot[[low, high]].dropna()
        comparisons += len(paired)
        for (club, group), row in paired[paired[high] < paired[low] - 1e-9].iterrows():
            decreases.append({"club": club, "position": group, "from": low, "to": high,
                              "before": float(row[low]), "after": float(row[high])})
    title = all_needs[all_needs.ambition == "title"]
    mean = title.groupby("club").need_score.mean().rename("mean_title_need")
    joined = results.merge(mean, on="club", how="right").merge(values.rename("squad_value_m"), on="club", how="left")
    complete = (len(joined) == ev.calibration_clubs and joined.points_per_game.notna().all()
                and joined.played.eq(expected_matches).all())

    def rho(column: str) -> float | None:
        pair = joined[["mean_title_need", column]].dropna()
        corr = pair.iloc[:, 0].rank().corr(pair.iloc[:, 1].rank()) if len(pair) > 1 else np.nan
        return None if pd.isna(corr) else float(corr)

    shares, counts = {}, {}
    for ambition in ("title", "survive"):
        rows = all_needs[all_needs.ambition == ambition]
        used = rows[rows.used]
        positive = int(used.priority.isin(["Medium", "High"]).sum())
        shares[ambition] = positive / len(used) if len(used) else 0.0
        counts[ambition] = {"all_cells": len(rows), "used_cells": len(used), "medium_or_high_used": positive,
                            "medium_or_high_share": shares[ambition],
                            **{p: int((rows.priority == p).sum()) for p in ("High", "Medium", "Low")},
                            "insufficient": int((used.evidence == "insufficient").sum())}
    top = results.head(ev.calibration_top_clubs).copy()
    high = title[title.priority == "High"].groupby("club").size()
    top["high_positions"] = top.club.map(high).fillna(0).astype(int)
    used = title[title.used]
    insufficient = used[used.evidence != "sufficient"][["club", "position_group", "rated_share", "imputed_stats"]]
    sufficient_share = float((used.evidence == "sufficient").mean()) if len(used) else 0.0
    corr = rho("points_per_game")
    expected_comparisons = ev.calibration_clubs * len(settings.position_stats) * 3
    checks = [
        {"check": "a", "name": "Ambition monotonicity", "passed": not decreases and comparisons == expected_comparisons,
         "observed": f"{len(decreases)} decreases / {comparisons} comparisons",
         "requirement": f"0 decreases / {expected_comparisons} comparisons"},
        {"check": "b", "name": "Independent club-strength correlation",
         "passed": bool(complete and corr is not None and corr <= ev.calibration_max_ppg_rho),
         "observed": f"Spearman {corr}; complete results: {complete}",
         "requirement": f"PPG rho <= {ev.calibration_max_ppg_rho}; all clubs, full season"},
        {"check": "c", "name": "Meaning of ambition levels",
         "passed": (shares["title"] >= ev.calibration_title_min_share
                    and shares["survive"] <= ev.calibration_survive_max_share),
         "observed": f"title {shares['title']:.2%}; survive {shares['survive']:.2%} used cells Medium/High",
         "requirement": (f"title >= {ev.calibration_title_min_share:.0%}; "
                         f"survive <= {ev.calibration_survive_max_share:.0%}")},
        {"check": "d", "name": "Strongest clubs",
         "passed": bool(complete and len(top) == ev.calibration_top_clubs
                        and (top.high_positions <= ev.calibration_top_max_high).all()),
         "observed": "; ".join(f"{r.club}: {r.high_positions} High" for r in top.itertuples()),
         "requirement": f"Top {ev.calibration_top_clubs} PPG clubs: <= {ev.calibration_top_max_high} High each"},
        {"check": "e", "name": "Evidence coverage", "passed": sufficient_share >= ev.calibration_min_evidence_share,
         "observed": f"{len(used) - len(insufficient)}/{len(used)} sufficient ({sufficient_share:.2%})",
         "requirement": f">= {ev.calibration_min_evidence_share:.0%} used cells sufficient"},
    ]
    return {"status": "passed" if all(c["passed"] for c in checks) else "failed",
            "definition": needs.NEED_DEFINITION, "season": settings.analysis_season, "checks": checks,
            "strength_source": "transfermarkt-datasets games + club_games; played-game points, no point deductions",
            "complete_results": bool(complete), "correlations": {"points_per_game": corr,
                "goal_difference": rho("goal_difference"), "market_value_secondary": rho("squad_value_m"),
                "matched_clubs": int(joined.points_per_game.notna().sum())},
            "bands": counts, "decreases": decreases, "comparisons": comparisons,
            "insufficient_cells": json.loads(insufficient.to_json(orient="records")),
            "strongest_clubs": json.loads(top.to_json(orient="records")),
            "clubs": json.loads(joined.sort_values("points_per_game", ascending=False).to_json(orient="records")),
            "needs": json.loads(all_needs.to_json(orient="records"))}


def outcome_scores(ps_next: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """§7.2 step 5: Σ w_s × <stat>_pct next season per fotmob_id, qualifying rows only (most minutes wins)."""
    q = ps_next[ps_next["qualifies"]].sort_values(["minutes", "fotmob_id"], ascending=[False, True])
    q = q.drop_duplicates("fotmob_id")
    score = sum(w * q[f"{s}_pct"] for s, w in weights.items())
    return pd.Series(np.asarray(score, dtype=float), index=q["fotmob_id"].to_numpy()).dropna()


def compare(picks: pd.Series, pool: pd.Series, settings: Settings, rng: np.random.Generator) -> dict:
    """§7.2 step 6: uplift = median(picks) / median(pool) − 1, hit rate, attrition, bootstrap CI.

    picks / pool: next-season outcome per player, NaN when he lacked the minutes (attrition).
    """
    ev = settings.evaluation
    p, q = picks.dropna().to_numpy(float), pool.dropna().to_numpy(float)
    out = {"picks": int(len(picks)), "picks_scored": int(len(p)), "pool": int(len(pool)), "pool_scored": int(len(q)),
           "attrition": float(1 - len(p) / len(picks)) if len(picks) else None,
           "median_picks": None, "median_pool": None, "uplift": None, "hit_rate": None, "ci_low": None,
           "ci_high": None}
    if len(p) == 0 or len(q) == 0:
        return out
    med_pool = float(np.median(q))
    boot = (np.median(rng.choice(p, (ev.bootstrap_resamples, len(p))), axis=1)
            / np.median(rng.choice(q, (ev.bootstrap_resamples, len(q))), axis=1) - 1)
    alpha = (1 - ev.ci) / 2
    low, high = np.quantile(boot, [alpha, 1 - alpha])
    return out | {"median_picks": float(np.median(p)), "median_pool": med_pool,
                  "uplift": float(np.median(p) / med_pool - 1), "hit_rate": float(np.mean(p > med_pool)),
                  "ci_low": float(low), "ci_high": float(high)}


NAIVE_FIT = {"performance": 1.0, "age": 0.0, "value": 0.0}


def club_samples(ps_n: pd.DataFrame, ps_next: pd.DataFrame, club: str, settings: Settings) -> list[dict]:
    """§7.2 steps 3-5 for one club: needs + rank on season_n (backtest settings), outcomes in season_n1.

    Also records the picks of a naive baseline (fit = last season's performance only) and each pick's
    season_n performance, age and market value (§15).
    """
    s = backtest_settings(settings)
    naive_s = s.model_copy(update={"fit_weights": NAIVE_FIT})
    club_needs = needs.compute_needs(ps_n, club, s)
    samples = []
    for need in rank.ranked_groups(club_needs, s).itertuples():
        weights = json.loads(need.stat_weights)
        pool = rank.eligible_pool(ps_n, need.position_group, club, weights, s)
        picks = rank.eligible_pool(ps_n, need.position_group, club, weights, s, need._asdict()).head(s.shortlist_size)
        naive = rank.eligible_pool(ps_n, need.position_group, club, weights, naive_s,
                                   need._asdict()).head(s.shortlist_size)
        outcome = outcome_scores(ps_next, weights)
        samples.append({
            "club": club, "group": need.position_group, "need_score": float(need.need_score),
            "priority": need.priority, "picks": picks["fotmob_id"].map(outcome), "pool": pool["fotmob_id"].map(outcome),
            "naive": naive["fotmob_id"].map(outcome), "profile": picks[["performance", "age", "market_value_m"]],
            "naive_profile": naive[["performance", "age", "market_value_m"]],
            "picked": [{"player": r.player_name, "team": r.team_name, "league": r.league,
                        "outcome": None if pd.isna(o) else round(float(o), 1)}
                       for r, o in zip(picks.itertuples(), picks["fotmob_id"].map(outcome), strict=True)],
        })
    return samples


def _profile(picks: pd.Series, profile: pd.DataFrame) -> dict:
    """Median season_n performance, next-season outcome, age and market value of a set of picks."""
    return {"median_performance_season_n": float(profile["performance"].median()),
            "median_outcome_season_n1": float(picks.median()) if picks.notna().any() else None,
            "median_age": float(profile["age"].astype(float).median()),
            "median_market_value_m": float(profile["market_value_m"].median())}


def backtest(ps_n: pd.DataFrame, ps_next: pd.DataFrame, club: str, clubs: list[str], settings: Settings) -> dict:
    """§7.2: the target club per group and overall, plus every club of the target league pooled, each
    compared with a naive performance-only picker (§15)."""
    rng = np.random.default_rng(settings.evaluation.seed)
    target = club_samples(ps_n, ps_next, club, settings)
    groups = {s["group"]: {"need_score": s["need_score"], "priority": s["priority"],
                           **compare(s["picks"], s["pool"], settings, rng), "picked": s["picked"]} for s in target}
    league = [s for c in clubs for s in club_samples(ps_n, ps_next, c, settings)]

    def pooled(samples: list[dict], picks_key: str = "picks") -> dict:
        if not samples:
            return compare(pd.Series(dtype=float), pd.Series(dtype=float), settings, rng)
        picks = pd.concat([s[picks_key] for s in samples])
        prof = pd.concat([s["profile" if picks_key == "picks" else "naive_profile"] for s in samples])
        return {**compare(picks, pd.concat([s["pool"] for s in samples]), settings, rng), **_profile(picks, prof)}

    return {"club": club, "groups": groups, "overall": pooled(target),
            "league_pooled": {"clubs": len(clubs), "groups": len(league), **pooled(league)},
            "naive_baseline": {"rule": "top shortlist_size by season_n performance only (fit weights 1/0/0)",
                               "target_club": pooled(target, "naive"), "league_pooled": pooled(league, "naive")}}


# ---------------------------------------------------------------- §7.3 sensitivity
def jaccard(a: set, b: set) -> float:
    """|a ∩ b| / |a ∪ b|; 1.0 for two empty sets."""
    return len(a & b) / len(a | b) if a | b else 1.0


def perturb(weights: dict[str, float], key: str, delta: float) -> dict[str, float]:
    """weights[key] + delta (floored at 0), all weights renormalized to sum 1 (§7.3)."""
    w = dict(weights)
    w[key] = max(0.0, w[key] + delta)
    total = sum(w.values())
    return {k: v / total for k, v in w.items()}


def shortlist_sets(ps: pd.DataFrame, needs_df: pd.DataFrame, clubs: list[str], settings: Settings) -> dict:
    """(club, group) -> set of fotmob_ids on the shortlist."""
    out = {}
    for club in clubs:
        sl = rank.rank_targets(ps, needs_df[needs_df["club"] == club], settings)
        for group, rows in sl.groupby("position_group"):
            out[(club, group)] = set(rows["fotmob_id"])
    return out


def sensitivity(
    base: dict, variants: dict[str, Callable[[], dict]], target_keys: list, league_keys: list
) -> dict:
    """§7.3: top-10 Jaccard of each variant against the baseline, mean and minimum over groups.

    A baseline group the variant no longer ranks counts as 0 in mean/min and is also counted in
    `groups_dropped`; `players_mean` is the Jaccard over groups ranked in both (§15).
    """
    out = {}
    for name, make in variants.items():
        sets = make()
        row = {}
        for label, keys in (("target_club", target_keys), ("league_high_medium", league_keys)):
            vals = [jaccard(base[k], sets.get(k, set())) for k in keys]
            kept = [jaccard(base[k], sets[k]) for k in keys if k in sets]
            row[label] = {"groups": len(vals), "mean": float(np.mean(vals)) if vals else None,
                          "min": float(np.min(vals)) if vals else None, "groups_dropped": len(vals) - len(kept),
                          "players_mean": float(np.mean(kept)) if kept else None}
        out[name] = row
    return out


# ---------------------------------------------------------------- §7.4 league strength vs UEFA coefficients
def league_uefa(coeffs: pd.DataFrame, leagues: list[League]) -> pd.DataFrame:
    """UEFA country coefficient (5 seasons) and that season's points for each league with a uefa_country."""
    by_code = coeffs.set_index("country_code")
    rows = [{"league": lg.key, "uefa_country": lg.uefa_country,
             "uefa_position": int(by_code.loc[lg.uefa_country, "position"]),
             "uefa_coefficient": float(by_code.loc[lg.uefa_country, "coefficient"]),
             "uefa_season_points": float(by_code.loc[lg.uefa_country, "season_points"])}
            for lg in leagues if lg.uefa_country and lg.uefa_country in by_code.index]
    return pd.DataFrame(rows)


def strength_validation(strength: pd.DataFrame, external: pd.DataFrame, column: str) -> dict:
    """§7.4: Pearson and Spearman (Pearson on ranks) between index_0_100 and an external measure."""
    df = strength[["league", "index_0_100"]].merge(external, on="league").dropna(subset=[column])
    return {
        "measure": column,
        "n": int(len(df)),
        "pearson": float(df["index_0_100"].corr(df[column])),
        "spearman": float(df["index_0_100"].rank().corr(df[column].rank())),
        "table": df.round(3).to_dict(orient="records"),
    }


# ---------------------------------------------------------------- charts
def _style(ax: plt.Axes) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_MUTED, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plot_backtest(result: dict, path: Path) -> None:
    """Uplift of the picks over the eligible-pool median with its bootstrap CI, one row per group."""
    rows = [(f"{result['club']} {g}", r) for g, r in result["groups"].items()]
    rows += [(f"{result['club']} overall", result["overall"]),
             (f"All {result['league_pooled']['clubs']} clubs pooled", result["league_pooled"]),
             ("Naive: last-season performance only", result["naive_baseline"]["league_pooled"])]
    rows = [(label, r) for label, r in rows if r.get("uplift") is not None]
    fig, ax = plt.subplots(figsize=(7.5, 0.6 * len(rows) + 1.4), facecolor=SURFACE)
    _style(ax)
    for i, (label, r) in enumerate(reversed(rows)):
        color = INK_MUTED if label.startswith("Naive") else SERIES   # the baseline is a reference, not a result
        ax.plot([100 * r["ci_low"], 100 * r["ci_high"]], [i, i], color=color, linewidth=2, solid_capstyle="round")
        ax.plot(100 * r["uplift"], i, "o", color=color, markersize=8, markeredgecolor=SURFACE, markeredgewidth=2)
        ax.annotate(f"{100 * r['uplift']:+.0f}%  (n={r['picks_scored']})", (100 * r["ci_high"], i),
                    xytext=(8, 0), textcoords="offset points", va="center", color=INK, fontsize=9)
    ax.axvline(0, color=INK_MUTED, linewidth=1)
    ax.set_yticks(range(len(rows)), [label for label, _ in reversed(rows)], color=INK, fontsize=9)
    ax.set_xlabel("Next-season performance vs eligible-pool median (%), 95% bootstrap CI", color=INK_MUTED)
    ax.set_title("Backtest: picks from 2024-25 data, judged on 2025-26", color=INK, loc="left", fontsize=11)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def plot_league_strength(validation: dict, names: dict[str, str], ylabel: str, path: Path) -> None:
    """Scatter of the market-value league-strength index against an external measure, direct-labelled."""
    df = pd.DataFrame(validation["table"])
    y = validation["measure"]
    fig, ax = plt.subplots(figsize=(7.5, 5), facecolor=SURFACE)
    _style(ax)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.scatter(df["index_0_100"], df[y], s=64, color=SERIES, edgecolors=SURFACE, linewidths=2, zorder=3)
    for r in df.itertuples():
        ax.annotate(names.get(r.league, r.league), (r.index_0_100, getattr(r, y)), xytext=(6, 4),
                    textcoords="offset points", color=INK, fontsize=8)
    ax.set_xlabel("League strength index (median log squad value, 0-100)", color=INK_MUTED)
    ax.set_ylabel(ylabel, color=INK_MUTED)
    ax.set_title(f"League strength vs {ylabel.split(' (')[0]}: Pearson {validation['pearson']:.2f}, "
                 f"Spearman {validation['spearman']:.2f} (n={validation['n']})", color=INK, loc="left", fontsize=11)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
