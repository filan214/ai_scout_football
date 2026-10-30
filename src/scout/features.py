"""Coverage check, league strength, player_season table. Implements IMPLEMENTATION_GUIDE §6.2-§6.4."""

from __future__ import annotations

import logging
from datetime import date

import numpy as np
import pandas as pd

from scout import clean
from scout.config import League, Pool, Settings

log = logging.getLogger(__name__)

NON_STAT_COLUMNS = {*clean.PERF_KEYS, "player_name", "team_id", "team_name", "minutes", "matches", "fotmob_position"}
DAYS_PER_MONTH = 365.25 / 12


def stat_columns(perf: pd.DataFrame) -> list[str]:
    """Canonical stat columns of interim/perf."""
    return [c for c in perf.columns if c not in NON_STAT_COLUMNS]


def squad_values(perf_season: pd.DataFrame, id_map: pd.DataFrame, values: pd.DataFrame) -> pd.DataFrame:
    """§6.3 squad value per club: market values (as of as_of_date) of the players who played for it this season.

    perf_season: league, team_id, team_name, fotmob_id. values: tm_id, market_value_eur. Players without
    a value count as missing (column `valued`), not as zero.
    """
    df = perf_season.merge(id_map[["fotmob_id", "tm_id"]], on="fotmob_id", how="left").merge(
        values[["tm_id", "market_value_eur"]], on="tm_id", how="left")
    return df.groupby(["league", "team_id", "team_name"], as_index=False).agg(
        squad_value_eur=("market_value_eur", "sum"), players=("fotmob_id", "size"),
        valued=("market_value_eur", "count"))


def league_strength(squads: pd.DataFrame, floor: float) -> pd.DataFrame:
    """§6.3: median over clubs of log(squad value) -> index 0-100 across leagues -> factor floor..1."""
    sq = squads[squads["squad_value_eur"] > 0]
    out = sq.groupby("league")["squad_value_eur"].agg(
        clubs="size",
        median_log_squad_value=lambda v: float(np.median(np.log(v))),
        median_squad_value_m=lambda v: float(np.median(v)) / 1e6,
    ).reset_index()
    raw = out["median_log_squad_value"]
    spread = raw.max() - raw.min()
    out["index_0_100"] = 100 * (raw - raw.min()) / spread if spread > 0 else 100.0
    out["factor"] = floor + (1 - floor) * out["index_0_100"] / 100
    return out.sort_values(["index_0_100", "league"], ascending=[False, True]).reset_index(drop=True)


def full_years(dob: pd.Series, as_of: date) -> pd.Series:
    """Age in full years on `as_of`; NaN when the birth date is unknown."""
    dob = pd.to_datetime(dob)
    before_birthday = (dob.dt.month > as_of.month) | ((dob.dt.month == as_of.month) & (dob.dt.day > as_of.day))
    return (as_of.year - dob.dt.year - before_birthday.astype(int)).astype("Int64")


def qualifies(ps: pd.DataFrame, pool: Pool) -> pd.Series:
    """Percentile population: outfield players with enough minutes and matches (§6.4, matches rule §15)."""
    return (ps["minutes_share"] >= pool.min_minutes_share) & (ps["matches_share"] >= pool.min_matches_share) & \
        ps["position_group"].notna()


def build_player_season(
    perf: pd.DataFrame, id_map: pd.DataFrame, tm_players: pd.DataFrame, tm_vals: pd.DataFrame,
    team_stats: pd.DataFrame, strength: pd.DataFrame, leagues: list[League], settings: Settings, season: str,
    as_of: date,
) -> pd.DataFrame:
    """§6.4 one row per player × league in `season` with profile fields as of `as_of`, <stat>_p90 and <stat>_adj.

    Counting stats: _p90 = season_total / minutes × 90; _adj = _p90 × factor(league), and for
    settings.possession_adjustment.stats also × reference / (1 − team possession) (§15). Rate stats
    are copied unchanged into both columns. Percentiles: `add_percentiles`.
    """
    matches_by_league = {lg.key: lg.matches(season) for lg in leagues}
    ps = clean.assign_position_groups(perf[perf["season"] == season], id_map, tm_players)
    league_matches = ps["league"].map(matches_by_league)
    ps["minutes_share"] = ps["minutes"] / (league_matches * 90)
    ps["matches_share"] = ps["matches"] / league_matches
    poss = team_stats[["league", "season", "team_id", "possession"]].rename(columns={"possession": "team_possession"})
    ps = ps.merge(poss, on=["league", "season", "team_id"], how="left")
    ps["possession_factor"] = settings.possession_adjustment.reference / (1 - ps["team_possession"])
    info = tm_players[["tm_id", "date_of_birth", "current_club", "contract_expiration_date", "sub_position"]]
    ps = ps.merge(info, on="tm_id", how="left").merge(clean.value_as_of(tm_vals, as_of), on="tm_id", how="left")
    ps["age"] = full_years(ps["date_of_birth"], as_of)
    ps["market_value_m"] = ps["market_value_eur"] / 1e6
    months = (pd.to_datetime(ps["contract_expiration_date"]) - pd.Timestamp(as_of)).dt.days / DAYS_PER_MONTH
    ps["contract_months_left"] = months.clip(lower=0).round(1)
    ps["league_factor"] = ps["league"].map(strength.set_index("league")["factor"])

    stats = stat_columns(perf)
    possession_stats = set(settings.possession_adjustment.stats)
    derived = {}
    for stat in stats:
        if stat in settings.rate_stats:
            derived[f"{stat}_p90"] = derived[f"{stat}_adj"] = ps[stat]
        else:
            p90 = ps[stat] / ps["minutes"].where(ps["minutes"] > 0) * 90
            derived[f"{stat}_p90"] = p90
            adj = p90 * ps["league_factor"]
            derived[f"{stat}_adj"] = adj * ps["possession_factor"] if stat in possession_stats else adj
    ps = pd.concat([ps.drop(columns=[*stats, "market_value_eur", "date_of_birth"]), pd.DataFrame(derived)], axis=1)
    ps["qualifies"] = qualifies(ps, settings.pool)
    return ps.sort_values(["league", "fotmob_id"]).reset_index(drop=True)


def coverage_check(
    ps: pd.DataFrame, position_stats: dict[str, list[str]], fallbacks: dict[str, str], threshold: float,
    min_stats: int,
) -> tuple[dict[str, list[str]], pd.DataFrame]:
    """§6.2: keep a stat if non-null for >= threshold of qualifying players in every league; else try its fallback.

    Returns (final position_stats, coverage table stat × league as shares).
    """
    q = ps[ps["qualifies"]]
    candidates = sorted({s for stats in position_stats.values() for s in stats} | set(fallbacks.values()))
    coverage = pd.DataFrame({
        s: q.groupby("league")[f"{s}_p90"].apply(lambda v: v.notna().mean()) if f"{s}_p90" in q else 0.0
        for s in candidates
    }, index=sorted(q["league"].unique())).T
    usable = {s for s in candidates if (coverage.loc[s] >= threshold).all()}
    final: dict[str, list[str]] = {}
    for group, stats in position_stats.items():
        chosen: list[str] = []
        for stat in stats:
            pick = stat if stat in usable else fallbacks.get(stat) if fallbacks.get(stat) in usable else None
            if pick is None:
                log.warning("coverage: %s dropped from %s (min coverage %.1f%%)", stat, group,
                            100 * coverage.loc[stat].min())
            elif pick not in chosen:
                if pick != stat:
                    log.info("coverage: %s -> fallback %s for %s", stat, pick, group)
                chosen.append(pick)
        if len(chosen) < min_stats:
            log.warning("coverage: %s keeps only %d stats: %s", group, len(chosen), chosen)
        final[group] = chosen
    return final, coverage


def add_percentiles(ps: pd.DataFrame, stats: list[str]) -> pd.DataFrame:
    """§6.4 <stat>_pct = rank(<stat>_adj, pct=True) × 100 within position_group among qualifying players; else NaN."""
    q = ps[ps["qualifies"]]
    pct = {f"{s}_pct": q.groupby("position_group")[f"{s}_adj"].rank(pct=True) * 100 for s in stats}
    return pd.concat([ps, pd.DataFrame(pct, index=q.index).reindex(ps.index)], axis=1)


def empirical_percentile(values: pd.Series, reference: pd.Series) -> pd.Series:
    """§6.4 placement on a fixed pool: average rank for exact ties, fraction below between observations."""
    ref = np.sort(reference.dropna().to_numpy(float))
    out = pd.Series(np.nan, index=values.index, dtype=float)
    valid = values.dropna()
    if len(ref):
        left = np.searchsorted(ref, valid.to_numpy(float), side="left")
        right = np.searchsorted(ref, valid.to_numpy(float), side="right")
        out.loc[valid.index] = (left + right + (right > left)) / (2 * len(ref)) * 100
    return out


def squad_profiles(player_season: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    """§6.4: one profile per player; combine adjusted stats, preserve pool ratings, place non-pool players.

    Input pool rows and percentiles are never changed. Missing stats remain missing. Fully rated
    profiles have every required role percentile; partial placements remain visible as partial evidence.
    Other-club minutes are a provenance flag, never an inferred loan status.
    """
    ps = player_season.copy()
    if "season" in ps and ps["season"].nunique() > 1:
        raise ValueError("squad_profiles requires one analysis season")
    ps = ps.sort_values(["fotmob_id", "minutes"], ascending=[True, False], kind="stable")
    profiles = ps.drop_duplicates("fotmob_id").set_index("fotmob_id").copy()
    ids = ps["fotmob_id"]
    grouped = ps.groupby("fotmob_id", sort=True)
    profiles["minutes"] = grouped["minutes"].sum()
    profiles["source_rows"] = grouped.size()
    if "matches" in ps:
        profiles["matches"] = grouped["matches"].sum()
    if "team_name" in ps:
        profiles["team_name"] = grouped["team_name"].agg(lambda v: "; ".join(sorted(set(v.dropna()))))
    if {"league", "team_id", "team_name"} <= set(ps):
        mapping = ps.dropna(subset=["current_club"]).groupby(["league", "team_id"])["current_club"].agg(
            lambda v: v.value_counts().sort_index().idxmax())
        played = pd.Series([mapping.get((r.league, r.team_id), r.team_name) for r in ps.itertuples()],
                           index=ps.index)
        other = ps["minutes"].where(played != ps["current_club"], 0)
        profiles["other_club_minutes"] = other.groupby(ids).sum()
    else:
        profiles["other_club_minutes"] = 0
    profiles["other_club_flag"] = np.where(profiles["other_club_minutes"] > 0, "Other-club minutes", "")
    profiles["loan_status"] = "unavailable"  # local players/transfers tables have no explicit loan-status field
    q = ps.get("qualifies", ps[[c for c in ps if c.endswith("_pct")]].notna().any(axis=1)).astype(bool)
    profiles["qualifies"] = q.groupby(ids).any()
    profiles["rated_by_placement"] = False
    stats = sorted({stat for group in settings.position_stats.values() for stat in group})
    for stat in stats:
        for suffix in ("_adj", "_p90"):
            col = stat + suffix
            if col in ps:
                minutes = ps["minutes"].where(ps[col].notna(), 0)
                denom = minutes.groupby(ids).sum().replace(0, np.nan)
                profiles[col] = (ps[col].fillna(0) * minutes).groupby(ids).sum() / denom
        col = stat + "_pct"
        if col not in ps:
            profiles[col] = np.nan
            continue
        minutes = ps["minutes"].where(q & ps[col].notna(), 0)
        denom = minutes.groupby(ids).sum().replace(0, np.nan)
        rated = (ps[col].fillna(0) * minutes).groupby(ids).sum() / denom
        counts = (q & ps[col].notna()).groupby(ids).sum()
        # Copy a single qualifying row exactly, without a floating-point multiply/divide round trip.
        first = ps.loc[q & ps[col].notna()].groupby("fotmob_id")[col].first()
        profiles[col] = rated.where(counts != 1, first)
        if stat + "_adj" not in ps:
            continue
        for group, role_stats in settings.position_stats.items():
            if stat not in role_stats:
                continue
            mask = ((profiles["position_group"] == group) & ~profiles["qualifies"]
                    & (profiles["minutes"] >= settings.squad_rating_min_minutes))
            ref = ps.loc[q & (ps["position_group"] == group), stat + "_adj"]
            placed = empirical_percentile(profiles.loc[mask, stat + "_adj"], ref)
            profiles.loc[mask, col] = placed
            profiles.loc[placed.dropna().index, "rated_by_placement"] = True
    profiles["fully_rated"] = False
    for group, role_stats in settings.position_stats.items():
        mask = profiles["position_group"] == group
        profiles.loc[mask, "fully_rated"] = profiles.loc[mask, [s + "_pct" for s in role_stats]].notna().all(axis=1)
    profiles["rated_minutes"] = profiles["minutes"].where(profiles["fully_rated"], 0)
    return profiles.reset_index().sort_values("fotmob_id").reset_index(drop=True)
