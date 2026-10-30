"""FotMob <-> Transfermarkt ID matching. Implements IMPLEMENTATION_GUIDE §6.1 (club pairing and passes 2-3: §15)."""

from __future__ import annotations

import logging
import re

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process
from unidecode import unidecode

log = logging.getLogger(__name__)

ID_MAP_COLUMNS = ["fotmob_id", "tm_id", "match_score", "method"]


def normalize_name(name: str) -> str:
    """unidecode -> lowercase -> drop apostrophes and dots -> other punctuation to spaces -> collapse spaces."""
    text = re.sub(r"['’`.]", "", unidecode(str(name)).lower())
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text)).strip()


def _subset_score(a: str, b: str) -> float:
    """Pass-2 similarity: one name contained in the other, or the same letters with different spacing."""
    return max(fuzz.token_set_ratio(a, b), fuzz.ratio(a.replace(" ", ""), b.replace(" ", "")))


def pair_clubs(fm: pd.DataFrame, tm: pd.DataFrame, name_threshold: float, min_overlap: int) -> dict[str, str]:
    """Pair FotMob teams with TM clubs of one league-season by shared player names, greedy one-to-one.

    fm: team_id, name_norm. tm: club_id, name_norm. Overlap(team, club) = team players whose best
    token_sort_ratio against the club's players is >= name_threshold.
    """
    if fm.empty or tm.empty:
        return {}
    scores = process.cdist(fm["name_norm"].tolist(), tm["name_norm"].tolist(), scorer=fuzz.token_sort_ratio)
    clubs = tm["club_id"].to_numpy()
    teams = fm["team_id"].to_numpy()
    overlaps = []
    for club in np.unique(clubs):
        hit = scores[:, clubs == club].max(axis=1) >= name_threshold
        for team in np.unique(teams):
            overlaps.append((int(hit[teams == team].sum()), str(team), str(club)))
    pairs: dict[str, str] = {}
    used: set[str] = set()
    for overlap, team, club in sorted(overlaps, key=lambda x: (-x[0], x[1], x[2])):
        if overlap < min_overlap or team in pairs or club in used:
            continue
        pairs[team] = club
        used.add(club)
    return pairs


def match_players(fm: pd.DataFrame, tm: pd.DataFrame, name_threshold: float) -> pd.DataFrame:
    """Match one club-season's FotMob players to its TM players; each TM player is used at most once.

    Pass 1 (spec): best token_sort_ratio >= threshold, highest scores first; exact ties (two players
    with the same name at one club) are skipped as ambiguous.
    Pass 2: `_subset_score` >= threshold with exactly one remaining candidate.
    Pass 3: same last name with exactly one remaining candidate.
    fm: fotmob_id, name_norm. tm: tm_id, name_norm. Returns ID_MAP_COLUMNS.
    """
    left = dict(zip(tm["tm_id"], tm["name_norm"], strict=True))
    names = dict(zip(fm["fotmob_id"], fm["name_norm"], strict=True))
    found: dict[str, tuple[str, float, str]] = {}

    scores = {(fid, tid): fuzz.token_sort_ratio(n, tn) for fid, n in names.items() for tid, tn in left.items()}
    for (fid, tid), score in sorted(scores.items(), key=lambda x: (-x[1], x[0])):
        if score < name_threshold:
            break
        if fid in found or tid not in left:
            continue
        tied = any(t != tid and scores[fid, t] == score for t in left) or any(
            f != fid and f not in found and scores[f, tid] == score for f in names)
        if not tied:
            found[fid] = (tid, score, "token_sort")
            del left[tid]

    passes = [
        ("subset", lambda a, b: _subset_score(a, b) >= name_threshold, _subset_score),
        ("surname", lambda a, b: a.split()[-1:] == b.split()[-1:], fuzz.token_sort_ratio),
    ]
    for method, accept, score_fn in passes:
        for fid, n in sorted(names.items()):
            if fid in found or not n:
                continue
            hits = [tid for tid, tn in left.items() if tn and accept(n, tn)]
            if len(hits) == 1:
                found[fid] = (hits[0], score_fn(n, left[hits[0]]), method)
                del left[hits[0]]
    return pd.DataFrame(
        [(fid, tid, round(float(score), 1), method) for fid, (tid, score, method) in found.items()],
        columns=ID_MAP_COLUMNS,
    )


def build_id_map(
    perf: pd.DataFrame, roster: pd.DataFrame, name_threshold: float, min_club_overlap: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Match every perf row whose league-season has a TM roster. Implements §6.1 steps 1-3.

    perf: fotmob_id, player_name, team_id, league, season. roster: tm_id, player_name, club_id, league, season
    (TM appearances). Returns (id_map with one row per fotmob_id, row-level matches incl. league/season).
    """
    perf = perf.assign(name_norm=perf["player_name"].map(normalize_name))
    roster = roster.assign(name_norm=roster["player_name"].map(normalize_name))
    rows = []
    for (league, season), fm in perf.groupby(["league", "season"]):
        tm = roster[(roster["league"] == league) & (roster["season"] == season)]
        if tm.empty:
            continue
        pairs = pair_clubs(fm[["team_id", "name_norm"]], tm[["club_id", "name_norm"]], name_threshold, min_club_overlap)
        unpaired = sorted(set(fm["team_id"]) - set(pairs))
        if unpaired:
            log.warning("%s %s: %d FotMob teams without a TM club: %s", league, season, len(unpaired), unpaired)
        for team, club in pairs.items():
            matched = match_players(
                fm.loc[fm["team_id"] == team, ["fotmob_id", "name_norm"]],
                tm.loc[tm["club_id"] == club, ["tm_id", "name_norm"]].drop_duplicates("tm_id"),
                name_threshold,
            )
            rows.append(matched.assign(league=league, season=season))
    empty = pd.DataFrame(columns=[*ID_MAP_COLUMNS, "league", "season"])
    matches = pd.concat(rows, ignore_index=True) if rows else empty
    return consolidate(matches), matches


def consolidate(matches: pd.DataFrame) -> pd.DataFrame:
    """One-to-one FotMob <-> TM ids: per pair, league-seasons matched then best score decide conflicts."""
    if matches.empty:
        return pd.DataFrame(columns=ID_MAP_COLUMNS)
    counts = matches.groupby(["fotmob_id", "tm_id"]).agg(n=("tm_id", "size"), match_score=("match_score", "max"),
                                                          method=("method", "first")).reset_index()
    ranked = counts.sort_values(["n", "match_score", "fotmob_id", "tm_id"], ascending=[False, False, True, True])
    kept = ranked.drop_duplicates("fotmob_id").drop_duplicates("tm_id")
    dropped = counts["fotmob_id"].nunique() - kept["fotmob_id"].nunique()
    if (counts["fotmob_id"].duplicated() | counts["tm_id"].duplicated()).any():
        log.warning("%d id conflicts across league-seasons; %d FotMob ids left unmatched", int(
            counts["fotmob_id"].duplicated().sum() + counts["tm_id"].duplicated().sum()), dropped)
    return kept.sort_values("fotmob_id")[ID_MAP_COLUMNS].reset_index(drop=True)


def apply_overrides(id_map: pd.DataFrame, overrides: pd.DataFrame) -> pd.DataFrame:
    """Manual overrides (fotmob_id, tm_id) replace automatic matches. Implements §6.1 step 4."""
    if overrides.empty:
        return id_map
    manual = overrides[["fotmob_id", "tm_id"]].astype(str).assign(match_score=100.0, method="override")
    kept = id_map[~id_map["fotmob_id"].isin(manual["fotmob_id"])]
    return pd.concat([kept, manual], ignore_index=True).sort_values("fotmob_id").reset_index(drop=True)


def unmatched_report(perf: pd.DataFrame, roster: pd.DataFrame, matched_ids: set[str], top_n: int) -> pd.DataFrame:
    """Top unmatched perf rows by minutes with the closest TM name in the same league-season (§6.1 step 5)."""
    todo = perf[~perf["fotmob_id"].isin(matched_ids)].nlargest(top_n, "minutes")
    rows = []
    for r in todo.itertuples():
        cand = roster[(roster["league"] == r.league) & (roster["season"] == r.season)].drop_duplicates("tm_id")
        best = process.extractOne(normalize_name(r.player_name), cand["player_name"].map(normalize_name).tolist(),
                                  scorer=fuzz.token_sort_ratio) if not cand.empty else None
        rows.append({
            "fotmob_id": r.fotmob_id, "player_name": r.player_name, "team_name": r.team_name, "league": r.league,
            "season": r.season, "minutes": r.minutes,
            "closest_tm_id": cand["tm_id"].iloc[best[2]] if best else None,
            "closest_tm_name": cand["player_name"].iloc[best[2]] if best else None,
            "closest_score": round(best[1], 1) if best else None,
        })
    return pd.DataFrame(rows)


def match_rates(perf: pd.DataFrame, matched_ids: set[str]) -> pd.DataFrame:
    """Row and minutes-weighted match rate per league and overall. Implements §6.1 step 5."""
    df = perf.assign(matched=perf["fotmob_id"].isin(matched_ids))
    df["matched_minutes"] = df["minutes"].where(df["matched"], 0)

    def summarize(g: pd.DataFrame) -> pd.Series:
        return pd.Series({
            "players": len(g),
            "match_rate": g["matched"].mean(),
            "minutes_weighted": g["matched_minutes"].sum() / g["minutes"].sum(),
        })

    per_league = df.groupby("league")[["matched", "minutes", "matched_minutes"]].apply(summarize)
    overall = summarize(df).to_frame("all").T
    return pd.concat([per_league, overall])
