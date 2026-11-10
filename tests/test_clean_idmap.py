"""P1 tests: perf table, position mapping, gap-fill calibration, name normalization, ID matching. No network."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from scout import clean, idmap


def _raw(stat: str, rows: list[tuple]) -> pd.DataFrame:
    """Rows: (player_id, minutes_played, matches_played, stat_value, sub_stat_value)."""
    return pd.DataFrame(
        [{"league": "la_liga", "season": "2025-26", "stat_name": stat, "player_id": pid, "player_name": pid.upper(),
          "team_id": "1", "team_name": "Club", "positions": "115,104", "minutes_played": m, "matches_played": n,
          "stat_value": v, "sub_stat_value": s} for pid, m, n, v, s in rows]
    )


def test_build_perf_totals_per90_and_absent_rule():
    raw = pd.concat([
        _raw("mins_played", [("p1", 1800, 20, 1800, 20), ("p2", 100, 3, 100, 3), ("p3", 900, 12, 900, 12),
                             ("p4", 500, 10, 500, 10), ("p5", 1500, 9, 1500, 9)]),
        _raw("total_scoring_att", [("p1", 1800, 20, 2.0, 15.0), ("p4", 500, 10, 0.9, 10.0)]),
        _raw("interception", [("p1", 1800, 20, 1.5, 30.0)]),
        _raw("accurate_pass", [("p1", 1800, 20, 40.0, 85.5)]),
    ])
    perf = clean.build_perf(raw).set_index("fotmob_id")
    assert perf.loc["p1", "shots"] == pytest.approx(40.0)
    assert perf.loc["p3", "shots"] == 0.0
    assert np.isnan(perf.loc["p2", "shots"])
    assert np.isnan(perf.loc["p5", "shots"])
    assert perf.loc["p1", "interceptions"] == 30.0
    assert perf.loc["p1", "accurate_passes_pct"] == 85.5
    assert np.isnan(perf.loc["p3", "accurate_passes_pct"])
    assert np.isnan(perf.loc["p1", "xg"])
    assert tuple(perf.loc["p1", ["minutes", "matches", "fotmob_position"]]) == (1800, 20, "115")


def test_build_team_stats_possession_share():
    raw = pd.DataFrame({"league": ["la_liga"] * 2, "season": ["2025-26"] * 2,
                        "stat_name": ["possession_percentage_team"] * 2, "team_id": ["9", "8"],
                        "team_name": ["A", "B"], "stat_value": [61.5, 38.5]})
    out = clean.build_team_stats(raw)
    assert out["team_id"].tolist() == ["8", "9"] and out["possession"].tolist() == pytest.approx([0.385, 0.615])


def test_season_of_and_window():
    days = pd.Series(pd.to_datetime(["2025-06-30", "2025-07-01", "2026-01-15"]))
    assert clean.season_of(days).tolist() == ["2024-25", "2025-26", "2025-26"]
    assert clean.season_window("1999-00") == (date(1999, 7, 1), date(2000, 6, 30))


def test_position_group_mapping():
    assert clean.position_group("Left Midfield") == "CM"
    assert clean.position_group("Second Striker") == "ST"
    assert clean.position_group("Right-Back") == "FB"
    assert clean.position_group("Goalkeeper") is None
    assert clean.position_group(None) is None
    assert set(clean.FOTMOB_SHORT_TO_SUBPOSITION.values()) <= set(clean.TM_SUBPOSITION_GROUPS)
    assert set(clean.FOTMOB_GENERIC_TO_SUBPOSITION.values()) <= set(clean.TM_SUBPOSITION_GROUPS)


def test_assign_position_groups_with_fotmob_fallback():
    perf = pd.DataFrame({"fotmob_id": ["1", "2", "3", "4"], "fotmob_position": ["115", "34", "11", "999"]})
    id_map = pd.DataFrame({"fotmob_id": ["1"], "tm_id": ["t1"]})
    tm_players = pd.DataFrame({"tm_id": ["t1"], "sub_position": ["Left Winger"]})
    out = clean.assign_position_groups(perf, id_map, tm_players).set_index("fotmob_id")
    assert out.loc["1", "position_group"] == "W" and not out.loc["1", "position_fallback"]
    assert out.loc["2", "position_group"] == "CB" and out.loc["2", "position_fallback"]
    assert pd.isna(out.loc["3", "position_group"])
    assert pd.isna(out.loc["4", "position_group"])


def _profile(pid, short=None, generic="", values=()):
    positions = [{"strPosShort": {"label": short}, "isMainPosition": True}] if short else []
    market = [{"date": d, "value": v, "teamName": t, "currency": "EUR"} for d, v, t in values]
    return {"id": pid, "name": f"P{pid}", "birthDate": {"utcTime": "2001-02-03T00:00:00.000Z"}, "contractEnd": None,
            "primaryTeam": {"teamName": "Club Today"},
            "positionDescription": {"positions": positions, "primaryPosition": {"label": generic}},
            "marketValues": {"values": market}}


def test_parse_profiles_positions_and_club_as_of():
    profiles, vals = clean.parse_profiles([
        _profile(1, short="RB", values=[("2026-05-31T00:00:00+00:00", 2_000_000, "Old Club"),
                                        ("2026-08-31T00:00:00+00:00", 3_000_000, "New Club")]),
        _profile(2, generic="forward"),
    ], as_of=date(2026, 7, 6))
    p = profiles.set_index("fotmob_id")
    assert p.loc["1", "sub_position"] == "Right-Back" and p.loc["1", "current_club"] == "Old Club"
    assert p.loc["2", "sub_position"] == "Centre-Forward" and p.loc["2", "current_club"] == "Club Today"
    assert p.loc["1", "date_of_birth"] == pd.Timestamp("2001-02-03") and pd.isna(p.loc["1", "contract_expiration_date"])
    assert len(vals) == 2


def test_fit_value_ratio_compares_same_dates():
    pairs = pd.DataFrame({"fotmob_id": ["a", "b", "c"], "tm_id": ["1", "2", "3"]})
    tm_vals = pd.DataFrame({"tm_id": ["1", "2", "3"], "market_value_eur": [8e6, 1e6, 5e6],
                            "date": pd.to_datetime(["2026-06-01", "2026-06-01", "2026-06-01"])})
    fm_vals = pd.DataFrame({"fotmob_id": ["a", "a", "b", "c"], "market_value_eur": [99e6, 10e6, 1.25e6, 5e6],
                            "date": pd.to_datetime(["2026-06-30", "2026-05-31", "2026-05-31", "2025-01-31"])})
    fit = clean.fit_value_ratio(pairs, tm_vals, fm_vals, date(2026, 7, 6), max_gap_days=92)
    assert fit["n"] == 2
    assert fit["ratio"] == pytest.approx(0.8)


def test_gap_fill_rows_scale_values_and_use_synthetic_ids():
    profiles, vals = clean.parse_profiles([_profile(7, short="CB", values=[("2026-06-30T00:00:00+00:00", 1e6, "X")])],
                                          as_of=date(2026, 7, 6))
    players, scaled = clean.gap_fill_rows(profiles, vals, {"7"}, ratio=0.8, as_of=date(2026, 7, 6))
    assert players.loc[0, "tm_id"] == "fotmob-7" and players.loc[0, "market_value_eur"] == 800_000
    assert scaled["source"].unique().tolist() == ["fotmob_calibrated"]


def test_normalize_name():
    assert idmap.normalize_name("Martin Ødegaard") == "martin odegaard"
    assert idmap.normalize_name("Evan N'Dicka") == "evan ndicka"
    assert idmap.normalize_name("  Heung-min  Son ") == "heung min son"


def _names(id_col, rows):
    return pd.DataFrame(rows, columns=[id_col, "name_norm"])


def test_pair_clubs_by_shared_players_not_club_names():
    fm = pd.DataFrame({"team_id": ["inter"] * 3 + ["milan"] * 3,
                       "name_norm": ["lautaro martinez", "nicolo barella", "hakan calhanoglu",
                                     "rafael leao", "christian pulisic", "mike maignan"]})
    tm = pd.DataFrame({"club_id": ["46"] * 3 + ["5"] * 3,
                       "name_norm": ["lautaro martinez", "nicolo barella", "hakan calhanoglu",
                                     "rafael leao", "christian pulisic", "mike maignan"]})
    assert idmap.pair_clubs(fm, tm, name_threshold=88, min_overlap=2) == {"inter": "46", "milan": "5"}
    assert idmap.pair_clubs(fm, tm, name_threshold=88, min_overlap=4) == {}


def test_match_players_three_passes_and_ambiguity():
    fm = _names("fotmob_id", [("1", "bukayo saka"), ("2", "idrissa gana gueye"), ("3", "max kilman"),
                              ("4", "gabriel"), ("5", "unknown person")])
    tm = _names("tm_id", [("a", "bukayo saka"), ("b", "idrissa gueye"), ("c", "maximilian kilman"),
                          ("d", "gabriel jesus"), ("e", "gabriel magalhaes")])
    got = idmap.match_players(fm, tm, name_threshold=88).set_index("fotmob_id")
    assert got.loc["1", "tm_id"] == "a" and got.loc["1", "method"] == "token_sort"
    assert got.loc["2", "tm_id"] == "b" and got.loc["2", "method"] == "subset"
    assert got.loc["3", "tm_id"] == "c" and got.loc["3", "method"] == "surname"
    assert "4" not in got.index
    assert "5" not in got.index
    assert got["tm_id"].is_unique


def test_match_players_skips_namesakes_at_one_club():
    fm = _names("fotmob_id", [("1", "joao mendes"), ("2", "joao mendes"), ("3", "tiago silva")])
    tm = _names("tm_id", [("a", "joao mendes"), ("b", "joao mendes"), ("c", "tiago silva")])
    got = idmap.match_players(fm, tm, name_threshold=88)
    assert got[["fotmob_id", "tm_id"]].values.tolist() == [["3", "c"]]


def test_consolidate_keeps_most_frequent_tm_id_one_to_one():
    matches = pd.DataFrame({"fotmob_id": ["1", "1", "1", "2"], "tm_id": ["a", "a", "b", "a"],
                            "match_score": [90.0, 95.0, 100.0, 100.0], "method": ["token_sort"] * 4})
    out = idmap.consolidate(matches)
    assert out[["fotmob_id", "tm_id"]].values.tolist() == [["1", "a"]]


def test_choose_gap_fill_ids_unmatched_and_stale_tm():
    id_map = pd.DataFrame({"fotmob_id": ["fresh", "stale", "elsewhere"], "tm_id": ["1", "2", "3"]})
    tm_players = pd.DataFrame({"tm_id": ["1", "2", "3"],
                               "value_date": pd.to_datetime(["2026-06-01", "2025-06-01", "2024-01-01"])})
    gap = {"fresh", "stale", "new", "no_profile"}
    got = clean.choose_gap_fill_ids(id_map, tm_players, gap, {"fresh", "stale", "new", "elsewhere"},
                                    as_of=date(2026, 7, 6), max_gap_days=92)
    assert got == {"stale", "new"}


def test_overrides_win():
    auto = pd.DataFrame({"fotmob_id": ["1", "2"], "tm_id": ["a", "b"], "match_score": [90.0, 92.0],
                         "method": ["token_sort", "subset"]})
    overrides = pd.DataFrame({"fotmob_id": ["1", "3"], "tm_id": ["z", "c"], "note": ["wrong auto match", "missed"]})
    out = idmap.apply_overrides(auto, overrides).set_index("fotmob_id")
    assert out.loc["1", "tm_id"] == "z" and out.loc["1", "method"] == "override"
    assert out.loc["2", "tm_id"] == "b"
    assert out.loc["3", "tm_id"] == "c"


def test_match_rates_minutes_weighted():
    perf = pd.DataFrame({"fotmob_id": ["1", "2", "3"], "league": ["x", "x", "y"], "minutes": [3000, 1000, 1000]})
    rates = idmap.match_rates(perf, {"1", "3"})
    assert rates.loc["all", "match_rate"] == pytest.approx(2 / 3)
    assert rates.loc["all", "minutes_weighted"] == pytest.approx(0.8)
    assert rates.loc["x", "minutes_weighted"] == pytest.approx(0.75)
