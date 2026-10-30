"""P2 tests: league strength, player_season p90/adj, coverage check, percentiles. Synthetic data, no network."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from scout import features
from scout.config import League, load_settings


def test_squad_values_missing_values_are_not_zero():
    perf = pd.DataFrame({"league": ["a"] * 3, "team_id": ["1"] * 3, "team_name": ["X"] * 3,
                         "fotmob_id": ["p", "q", "r"]})
    id_map = pd.DataFrame({"fotmob_id": ["p", "q"], "tm_id": ["tp", "tq"]})
    values = pd.DataFrame({"tm_id": ["tp"], "market_value_eur": [5e6]})
    out = features.squad_values(perf, id_map, values).iloc[0]
    assert (out["squad_value_eur"], out["players"], out["valued"]) == (5e6, 3, 1)


def test_league_strength_median_log_index_and_factor():
    squads = pd.DataFrame({
        "league": ["rich"] * 3 + ["mid"] * 3 + ["poor"] * 3,
        "team_id": list("abcdefghi"),
        # one rich outlier, one club without values
        "squad_value_eur": [100e6, 400e6, 9_000e6, 50e6, 60e6, 70e6, 10e6, 10e6, 0.0],
    })
    out = features.league_strength(squads, floor=0.6).set_index("league")
    assert out.loc["rich", "median_log_squad_value"] == pytest.approx(np.log(400e6))   # median, not the 9bn outlier
    assert out.loc["poor", "clubs"] == 2                                              # zero-value club skipped
    assert (out.loc["rich", "index_0_100"], out.loc["poor", "index_0_100"]) == (100.0, 0.0)
    expected_mid = 100 * (np.log(60e6) - np.log(10e6)) / (np.log(400e6) - np.log(10e6))
    assert out.loc["mid", "index_0_100"] == pytest.approx(expected_mid)
    assert out.loc["mid", "factor"] == pytest.approx(0.6 + 0.4 * expected_mid / 100)
    assert (out.loc["rich", "factor"], out.loc["poor", "factor"]) == (1.0, 0.6)


def test_full_years_birthday_edges():
    dob = pd.Series(pd.to_datetime(["2000-07-06", "2000-07-07", None]))
    ages = features.full_years(dob, date(2026, 7, 6))
    assert ages.iloc[0] == 26 and ages.iloc[1] == 25 and pd.isna(ages.iloc[2])


@pytest.fixture
def settings():
    return load_settings()


def _perf(rows):
    """rows: (fotmob_id, league, minutes, matches, tackles_total, pass_pct)."""
    return pd.DataFrame([
        {"league": lg, "season": "2025-26", "fotmob_id": fid, "player_name": fid, "team_id": "1", "team_name": "T",
         "minutes": m, "matches": n, "fotmob_position": "34", "tackles": t, "accurate_passes_pct": pp}
        for fid, lg, m, n, t, pp in rows
    ])


def test_build_player_season_p90_adj_shares_and_profile(settings):
    perf = _perf([("a", "x", 1800, 20, 40.0, 88.0), ("b", "y", 900, 10, 10.0, 80.0), ("c", "x", 3000, 15, 30.0, 70.0)])
    id_map = pd.DataFrame({"fotmob_id": ["a", "b", "c"], "tm_id": ["ta", "tb", "tc"]})
    tm_players = pd.DataFrame({"tm_id": ["ta", "tb", "tc"], "sub_position": ["Centre-Back", "Right-Back", "Goalkeeper"],
                               "date_of_birth": pd.to_datetime(["2001-01-01", "1990-12-31", "1995-05-05"]),
                               "current_club": ["X FC", "Y FC", "X FC"],
                               "contract_expiration_date": pd.to_datetime(["2027-07-06", "2026-06-30", None])})
    tm_vals = pd.DataFrame({"tm_id": ["ta", "ta", "tb"], "market_value_eur": [3e6, 9e6, 1e6],
                            "date": pd.to_datetime(["2026-01-01", "2026-08-01", "2025-12-01"])})
    strength = pd.DataFrame({"league": ["x", "y"], "factor": [1.0, 0.6]})
    team_stats = pd.DataFrame({"league": ["x", "y"], "season": ["2025-26"] * 2, "team_id": ["1", "1"],
                               "possession": [0.6, 0.4]})
    leagues = [League(key="x", name="X", tier=1, fotmob_id=1, transfermarkt_id="X1", matches_per_season=38),
               League(key="y", name="Y", tier=2, fotmob_id=2, transfermarkt_id="Y1", matches_per_season=20)]
    ps = features.build_player_season(perf, id_map, tm_players, tm_vals, team_stats, strength, leagues, settings,
                                      "2025-26", date(2026, 7, 6)).set_index("fotmob_id")
    assert ps.loc["a", "tackles_p90"] == pytest.approx(2.0)               # 40 / 1800 × 90 (raw, unadjusted)
    assert ps.loc["a", "tackles_adj"] == pytest.approx(2.0 * 1.0 * 0.5 / 0.4)   # 60% possession side: × 1.25
    assert ps.loc["b", "tackles_adj"] == pytest.approx(1.0 * 0.6 * 0.5 / 0.6)   # factor 0.6, 40% possession
    assert ps.loc["b", "accurate_passes_pct_adj"] == 80.0                 # rate stat copied, not adjusted
    assert ps.loc["a", "minutes_share"] == pytest.approx(1800 / (38 * 90))
    assert ps.loc["b", "matches_share"] == pytest.approx(0.5)
    assert ps.loc["a", "market_value_m"] == 3.0                           # latest value on or before as_of
    assert (ps.loc["a", "age"], ps.loc["b", "age"]) == (25, 35)
    assert ps.loc["a", "contract_months_left"] == pytest.approx(12.0, abs=0.1)
    assert ps.loc["b", "contract_months_left"] == 0                       # expired contract clipped at 0
    assert pd.isna(ps.loc["c", "contract_months_left"])                   # unknown stays unknown
    assert ps.loc["a", "qualifies"] and ps.loc["b", "qualifies"]
    assert not ps.loc["c", "qualifies"]                                   # goalkeeper (and < half the matches)


def _ps(rows):
    """rows: (league, position_group, qualifies, xg_p90, npxg_p90)."""
    return pd.DataFrame([{"league": lg, "position_group": g, "qualifies": q, "xg_p90": x, "xg_adj": x,
                          "shots_p90": s, "shots_adj": s} for lg, g, q, x, s in rows])


def test_coverage_check_drops_low_coverage_and_uses_fallback():
    ps = _ps([("a", "ST", True, 0.5, 2.0)] * 19 + [("a", "ST", True, 0.4, np.nan)]
             + [("b", "ST", True, 0.3, 1.0)] * 10 + [("b", "ST", False, np.nan, np.nan)] * 5)
    final, cov = features.coverage_check(ps, {"ST": ["npxg", "shots", "xg"]}, {"npxg": "xg"}, 0.95, 4)
    assert cov.loc["shots", "a"] == pytest.approx(0.95) and cov.loc["xg", "b"] == 1.0   # non-qualifying ignored
    assert cov.loc["npxg"].tolist() == [0.0, 0.0]
    assert final == {"ST": ["xg", "shots"]}                                           # npxg -> xg once, shots kept

    final, _ = features.coverage_check(ps, {"ST": ["shots"]}, {}, 0.96, 1)
    assert final == {"ST": []}


def test_add_percentiles_within_group_among_qualifying():
    ps = _ps([("a", "ST", True, 0.1, 1.0), ("a", "ST", True, 0.3, 1.0), ("b", "ST", True, 0.2, 3.0),
              ("a", "CB", True, 0.9, 0.0), ("a", "ST", False, 0.9, 9.0)])
    out = features.add_percentiles(ps, ["xg", "shots"])
    assert out["xg_pct"].tolist()[:3] == pytest.approx([100 / 3, 100, 200 / 3])
    assert out.loc[3, "xg_pct"] == 100                                    # alone in its group
    assert np.isnan(out.loc[4, "xg_pct"])                                 # not qualifying
    assert out["shots_pct"].tolist()[:2] == pytest.approx([50, 50])       # ties share the average rank
