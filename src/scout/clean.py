"""Canonical stats, position groups, interim tables, Championship gap-fill."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from scout.config import League, fotmob_raw_path, fotmob_teams_raw_path
from scout.sources import FOTMOB_TO_CANONICAL, query_transfermarkt

TM_SUBPOSITION_GROUPS: dict[str, str | None] = {
    "Centre-Forward": "ST", "Second Striker": "ST",
    "Left Winger": "W", "Right Winger": "W",
    "Attacking Midfield": "AM",
    "Central Midfield": "CM", "Left Midfield": "CM", "Right Midfield": "CM",
    "Defensive Midfield": "DM",
    "Left-Back": "FB", "Right-Back": "FB",
    "Centre-Back": "CB",
    "Goalkeeper": None,
}

FOTMOB_SHORT_TO_SUBPOSITION = {
    "ST": "Centre-Forward", "LW": "Left Winger", "RW": "Right Winger", "AM": "Attacking Midfield",
    "CM": "Central Midfield", "LM": "Left Midfield", "RM": "Right Midfield", "DM": "Defensive Midfield",
    "LB": "Left-Back", "RB": "Right-Back", "LWB": "Left-Back", "RWB": "Right-Back",
    "CB": "Centre-Back", "GK": "Goalkeeper",
}
FOTMOB_GENERIC_TO_SUBPOSITION = {
    "forward": "Centre-Forward", "midfielder": "Central Midfield", "defender": "Centre-Back", "keeper": "Goalkeeper",
}

FOTMOB_POSITION_GROUPS: dict[str, str | None] = {
    "0": None, "11": None, "1": "CB", "2": "CM", "3": "ST",
    "32": "FB", "33": "CB", "34": "CB", "35": "CB", "36": "CB", "37": "CB", "38": "FB",
    "51": "FB", "52": "FB", "53": "FB", "59": "FB",
    "62": "FB", "63": "CM", "64": "DM", "65": "DM", "66": "CM", "67": "AM", "68": "FB",
    "71": "FB", "72": "W", "73": "CM", "74": "CM", "75": "DM", "76": "CM", "77": "CM", "78": "W", "79": "FB",
    "82": "W", "83": "W", "84": "AM", "85": "AM", "86": "AM", "87": "W", "88": "W",
    "95": "ST", "103": "W", "104": "ST", "105": "ST", "106": "ST", "107": "W", "114": "ST", "115": "ST",
}

PERF_KEYS = ["league", "season", "fotmob_id"]


def season_of(day: pd.Series) -> pd.Series:
    """Season label of a date; seasons run 1 July - 30 June ('2025-26')."""
    day = pd.to_datetime(day)
    start = day.dt.year - (day.dt.month < 7).astype(int)
    return start.astype(str) + "-" + ((start + 1) % 100).astype(str).str.zfill(2)


def season_window(season: str) -> tuple[date, date]:
    """First and last day of a season label."""
    start = int(season[:4])
    return date(start, 7, 1), date(start + 1, 6, 30)


def position_group(sub_position: str | None) -> str | None:
    """Transfermarkt sub_position -> position group; None for goalkeepers and unknown labels."""
    return TM_SUBPOSITION_GROUPS.get(sub_position) if isinstance(sub_position, str) else None


def assign_position_groups(perf: pd.DataFrame, id_map: pd.DataFrame, tm_players: pd.DataFrame) -> pd.DataFrame:
    """Perf rows + position_group (from sub_position, else FotMob position id) and position_fallback.

    Goalkeepers get position_group None (excluded in v1).
    """
    out = perf.merge(id_map[["fotmob_id", "tm_id"]], on="fotmob_id", how="left").merge(
        tm_players[["tm_id", "sub_position"]], on="tm_id", how="left")
    known = out["sub_position"].notna()
    out["position_group"] = out["sub_position"].map(position_group)
    out["position_fallback"] = ~known
    out.loc[~known, "position_group"] = out.loc[~known, "fotmob_position"].map(FOTMOB_POSITION_GROUPS)
    return out.drop(columns=["sub_position"])


def read_fotmob_raw(leagues: list[League], seasons: list[str], stat_name: str | None = None) -> pd.DataFrame:
    """Concatenate the raw FotMob files that exist for these league-seasons, optionally one stat list."""
    frames = []
    for league in leagues:
        for season in seasons:
            path = fotmob_raw_path(league.key, season)
            if path.exists():
                df = pd.read_parquet(path)
                frames.append(df[df["stat_name"] == stat_name] if stat_name else df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def read_fotmob_teams_raw(leagues: list[League], seasons: list[str]) -> pd.DataFrame:
    """Concatenate the raw FotMob club lists that exist for these league-seasons."""
    paths = [fotmob_teams_raw_path(lg.key, s) for lg in leagues for s in seasons]
    frames = [pd.read_parquet(p) for p in paths if p.exists()]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def build_team_stats(raw_teams: pd.DataFrame) -> pd.DataFrame:
    """Club lists -> one row per club × league × season with possession as a share 0-1."""
    poss = raw_teams[raw_teams["stat_name"] == "possession_percentage_team"]
    out = poss[["league", "season", "team_id", "team_name"]].assign(possession=poss["stat_value"] / 100)
    return out.sort_values(["league", "season", "team_id"]).reset_index(drop=True)


def select_profile_ids(
    mins: pd.DataFrame,
    gap_leagues: list[str],
    covered_leagues: list[str],
    calibration_season: str,
    min_minutes: int,
    per_league: int,
    seed: int,
) -> list[str]:
    """FotMob ids needing a profile: every player of a gap league plus a seeded calibration sample.

    `mins` is the raw `mins_played` list (league, season, player_id, minutes_played). The sample takes
    `per_league` players with at least `min_minutes` in `calibration_season` from each covered league.
    """
    gap_ids = mins.loc[mins["league"].isin(gap_leagues), "player_id"]
    pool = mins[
        mins["league"].isin(covered_leagues)
        & (mins["season"] == calibration_season)
        & (mins["minutes_played"] >= min_minutes)
    ].sort_values(["league", "player_id"])
    sample = pool.groupby("league").sample(n=per_league, random_state=seed)
    return sorted(set(gap_ids) | set(sample["player_id"]))


def build_perf(raw: pd.DataFrame) -> pd.DataFrame:
    """Raw FotMob lists -> one row per player x league x season with canonical stats (interim/perf).

    Counting stats are season totals: published totals where FotMob has them, else per-90 x minutes / 90.
    A player missing from a counting-stat list with at least that list's minimum matches played has a
    count of 0; below it the value is unknown (NaN). FotMob's per-90 lists only include players with at
    least half of the league's matches, so their minimum is that threshold (docs/DATA_REALITY.md).
    Percentage stats are copied; missing = NaN.
    """
    base = raw.loc[raw["stat_name"] == "mins_played"].rename(
        columns={"player_id": "fotmob_id", "stat_value": "minutes", "sub_stat_value": "matches"}
    )
    perf = base[[*PERF_KEYS, "player_name", "team_id", "team_name", "minutes", "matches"]].copy()
    perf["fotmob_position"] = base["positions"].str.split(",").str[0]
    perf[["minutes", "matches"]] = perf[["minutes", "matches"]].astype(int)

    for (stat, column), (canonical, unit) in FOTMOB_TO_CANONICAL.items():
        if stat == "mins_played":
            continue
        rows = raw.loc[raw["stat_name"] == stat, ["league", "season", "player_id", "matches_played", column]]
        floors = rows.groupby(["league", "season"])["matches_played"].min().rename("floor").reset_index()
        values = rows.rename(columns={"player_id": "fotmob_id", column: canonical})[[*PERF_KEYS, canonical]]
        merged = perf[PERF_KEYS + ["minutes", "matches"]].merge(values, on=PERF_KEYS, how="left").merge(
            floors, on=["league", "season"], how="left"
        )
        value = merged[canonical]
        if unit == "per90":
            value = value * merged["minutes"] / 90
        if unit != "pct":
            value = value.where(value.notna() | ~(merged["matches"] >= merged["floor"]), 0.0)
        perf[canonical] = value.to_numpy()
    return perf.sort_values(PERF_KEYS).reset_index(drop=True)


def load_tm_roster(db_path: Path, leagues: list[League], seasons: list[str]) -> pd.DataFrame:
    """TM appearances aggregated to player x club x league x season."""
    by_comp = {lg.transfermarkt_id: lg.key for lg in leagues}
    first, last = season_window(min(seasons))[0], season_window(max(seasons))[1]
    comps = ", ".join(f"'{c}'" for c in by_comp)
    df = query_transfermarkt(db_path, f"""
        SELECT a.player_id, p.name AS player_name, a.player_club_id, a.competition_id, a.date, a.minutes_played
        FROM appearances a JOIN players p USING (player_id)
        WHERE a.competition_id IN ({comps}) AND a.date BETWEEN '{first}' AND '{last}'""")
    df["season"] = season_of(df["date"])
    df["league"] = df["competition_id"].map(by_comp)
    keys = ["league", "season", "player_club_id", "player_id", "player_name"]
    out = df[df["season"].isin(seasons)].groupby(keys, as_index=False)["minutes_played"].sum()
    out = out.rename(columns={"player_club_id": "club_id", "player_id": "tm_id", "minutes_played": "tm_minutes"})
    out[["club_id", "tm_id"]] = out[["club_id", "tm_id"]].astype(str)
    return out


def load_tm_players(db_path: Path, min_last_season: int, as_of: date) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Interim tm_players and tm_valuations from transfermarkt-datasets, market value as of `as_of`."""
    players = query_transfermarkt(db_path, f"""
        SELECT player_id AS tm_id, name AS player_name, date_of_birth, sub_position,
               current_club_name AS current_club, current_club_id, contract_expiration_date
        FROM players WHERE last_season >= {min_last_season}""")
    vals = query_transfermarkt(db_path, f"""
        SELECT v.player_id AS tm_id, v.date, v.market_value_in_eur AS market_value_eur
        FROM player_valuations v JOIN players p USING (player_id) WHERE p.last_season >= {min_last_season}""")
    for df in (players, vals):
        df["tm_id"] = df["tm_id"].astype(str)
    players["current_club_id"] = players["current_club_id"].astype("Int64").astype(str)
    vals["date"] = pd.to_datetime(vals["date"])
    vals["source"] = "transfermarkt"
    players = players.merge(value_as_of(vals, as_of), on="tm_id", how="left")
    players["source"] = "transfermarkt"
    return players, vals


def value_as_of(vals: pd.DataFrame, as_of: date, id_col: str = "tm_id") -> pd.DataFrame:
    """Latest valuation on or before `as_of` per player: id, market_value_eur, value_date."""
    v = vals[vals["date"] <= pd.Timestamp(as_of)].sort_values([id_col, "date"])
    v = v.drop_duplicates(id_col, keep="last")
    return v[[id_col, "market_value_eur", "date"]].rename(columns={"date": "value_date"})


def parse_profiles(profiles: list[dict], as_of: date) -> tuple[pd.DataFrame, pd.DataFrame]:
    """FotMob player profiles -> (one row per player in tm_players shape, SciSports valuation history).

    current_club is the club of the latest valuation on or before `as_of` (the profile's primaryTeam
    is today's club); sub_position comes from the main position, else the generic label.
    """
    players, values = [], []
    for p in profiles:
        fid = str(p["id"])
        for v in (p.get("marketValues") or {}).get("values") or []:
            values.append((fid, v["date"][:10], v["value"], v.get("teamName"), v.get("currency")))
        desc = p.get("positionDescription") or {}
        main = [x["strPosShort"]["label"] for x in desc.get("positions") or [] if x.get("isMainPosition")]
        generic = ((desc.get("primaryPosition") or {}).get("label") or "").lower()
        sub_position = FOTMOB_SHORT_TO_SUBPOSITION.get(main[0]) if main else FOTMOB_GENERIC_TO_SUBPOSITION.get(generic)
        players.append({
            "fotmob_id": fid,
            "player_name": p.get("name"),
            "date_of_birth": (p.get("birthDate") or {}).get("utcTime", "")[:10] or None,
            "sub_position": sub_position,
            "primary_team": (p.get("primaryTeam") or {}).get("teamName"),
            "contract_expiration_date": (p.get("contractEnd") or {}).get("utcTime", "")[:10] or None,
        })
    vals = pd.DataFrame(values, columns=["fotmob_id", "date", "market_value_eur", "team", "currency"])
    vals["date"] = pd.to_datetime(vals["date"])
    out = pd.DataFrame(players)
    for col in ("date_of_birth", "contract_expiration_date"):
        out[col] = pd.to_datetime(out[col])
    latest = vals[vals["date"] <= pd.Timestamp(as_of)].sort_values(["fotmob_id", "date"]).drop_duplicates(
        "fotmob_id", keep="last")[["fotmob_id", "team"]]
    out = out.merge(latest, on="fotmob_id", how="left")
    out["current_club"] = out["team"].fillna(out["primary_team"])
    return out.drop(columns=["team", "primary_team"]), vals


def fit_value_ratio(
    pairs: pd.DataFrame, tm_vals: pd.DataFrame, fm_vals: pd.DataFrame, as_of: date, max_gap_days: int
) -> dict:
    """Transfermarkt / SciSports value ratio on players in both sources, compared on the same date.

    pairs: fotmob_id, tm_id. For each pair: latest TM value on or before `as_of` (date d) against the latest
    FotMob value on or before d, if no more than `max_gap_days` older. Returns the median ratio and spread.
    """
    tm_now = value_as_of(tm_vals, as_of).merge(pairs, on="tm_id")
    rows = []
    for r in tm_now.itertuples():
        fm = fm_vals[(fm_vals["fotmob_id"] == r.fotmob_id) & (fm_vals["date"] <= r.value_date)]
        if fm.empty or r.market_value_eur <= 0:
            continue
        last = fm.sort_values("date").iloc[-1]
        if (r.value_date - last["date"]) <= timedelta(days=max_gap_days) and last["market_value_eur"] > 0:
            rows.append((r.market_value_eur, last["market_value_eur"]))
    if not rows:
        raise ValueError("no players with both a Transfermarkt and a FotMob value to calibrate on")
    tm_v, fm_v = np.array(rows, dtype=float).T
    ratio = tm_v / fm_v
    bands = {"under_2m": tm_v < 2e6, "2m_to_10m": (tm_v >= 2e6) & (tm_v < 10e6), "10m_plus": tm_v >= 10e6}
    return {
        "ratio": float(np.median(ratio)),
        "n": int(len(ratio)),
        "q25": float(np.quantile(ratio, 0.25)),
        "q75": float(np.quantile(ratio, 0.75)),
        "median_by_tm_value": {k: (float(np.median(ratio[m])) if m.any() else None) for k, m in bands.items()},
        "n_by_tm_value": {k: int(m.sum()) for k, m in bands.items()},
    }


def choose_gap_fill_ids(
    id_map: pd.DataFrame, tm_players: pd.DataFrame, gap_ids: set[str], profile_ids: set[str], as_of: date,
    max_gap_days: int,
) -> set[str]:
    """Gap-league players described by their FotMob profile instead of Transfermarkt.

    Unmatched players, plus TM matches whose latest TM value is more than `max_gap_days` before `as_of`
    (Transfermarkt stops updating players who leave its leagues). Only players with a profile qualify.
    """
    tm = id_map[id_map["fotmob_id"].isin(gap_ids)].merge(tm_players[["tm_id", "value_date"]], on="tm_id", how="left")
    cutoff = pd.Timestamp(as_of) - pd.Timedelta(days=max_gap_days)
    stale = set(tm.loc[tm["value_date"].isna() | (tm["value_date"] < cutoff), "fotmob_id"])
    unmatched = gap_ids - set(id_map["fotmob_id"])
    return (unmatched | stale) & profile_ids


def gap_fill_rows(
    profiles: pd.DataFrame, fm_vals: pd.DataFrame, fotmob_ids: set[str], ratio: float, as_of: date
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """tm_players / tm_valuations rows for players without Transfermarkt data, values scaled by `ratio`.

    The synthetic tm_id is 'fotmob-<fotmob_id>'; source = 'fotmob_calibrated'.
    """
    prof = profiles[profiles["fotmob_id"].isin(fotmob_ids)].copy()
    vals = fm_vals[fm_vals["fotmob_id"].isin(fotmob_ids)].copy()
    vals["market_value_eur"] = (vals["market_value_eur"] * ratio).round()
    for df in (prof, vals):
        df["tm_id"] = "fotmob-" + df["fotmob_id"]
        df["source"] = "fotmob_calibrated"
    prof = prof.merge(value_as_of(vals, as_of), on="tm_id", how="left")
    prof["current_club_id"] = None
    return prof.drop(columns=["fotmob_id"]), vals[["tm_id", "date", "market_value_eur", "source"]]
