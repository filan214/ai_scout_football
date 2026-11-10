"""Evaluation helpers: backtest metrics, sensitivity, UEFA coefficient correlation, charts. No network."""

import numpy as np
import pandas as pd
import pytest

from scout import evaluate
from scout.config import load_leagues, load_settings


@pytest.fixture
def settings():
    return load_settings()


def test_compare_uplift_hit_rate_attrition_and_ci(settings):
    picks = pd.Series([80.0, 90.0, 70.0, np.nan])
    pool = pd.Series([40.0, 50.0, 60.0, 80.0, 90.0, np.nan])
    out = evaluate.compare(picks, pool, settings, np.random.default_rng(0))
    assert out["uplift"] == pytest.approx(80 / 60 - 1) and out["hit_rate"] == 1.0
    assert out["attrition"] == pytest.approx(0.25) and (out["picks_scored"], out["pool_scored"]) == (3, 5)
    assert out["ci_low"] <= out["uplift"] <= out["ci_high"]
    again = evaluate.compare(picks, pool, settings, np.random.default_rng(0))
    assert again == out
    empty = evaluate.compare(pd.Series([np.nan]), pool, settings, np.random.default_rng(0))
    assert empty["uplift"] is None and empty["attrition"] == 1.0


def test_outcome_scores_use_qualifying_row_with_most_minutes():
    ps = pd.DataFrame({"fotmob_id": ["a", "a", "b", "c"], "qualifies": [True, True, True, False],
                       "minutes": [900, 2000, 1500, 3000], "xg_pct": [10.0, 80.0, 50.0, 99.0],
                       "shots_pct": [10.0, 40.0, 50.0, 99.0]})
    out = evaluate.outcome_scores(ps, {"xg": 0.75, "shots": 0.25})
    assert out.to_dict() == {"a": pytest.approx(70.0), "b": pytest.approx(50.0)}


def test_backtest_settings_drop_contract_without_changing_other_urgency(settings):
    w = evaluate.backtest_settings(settings).need_weights
    assert w["contract"] == 0
    assert w["depth"] == settings.need_weights["depth"] and w["age"] == settings.need_weights["age"]


def test_season_results_draw_win_loss_and_duplicates():
    rows = pd.DataFrame({"club_id": ["1", "1", "1"], "club": ["A"] * 3, "game_id": ["a", "b", "c"],
                         "own_goals": [2, 1, 0], "opponent_goals": [0, 1, 3]})
    result = evaluate.season_results(rows).iloc[0]
    assert result["played"] == 3 and result["points"] == 4
    assert result["points_per_game"] == pytest.approx(4 / 3)
    assert result["goal_difference"] == -1
    with pytest.raises(ValueError, match="duplicate"):
        evaluate.season_results(pd.concat([rows, rows.iloc[:1]]))


def test_calibration_reports_failure_without_tuning(settings):
    rows = []
    clubs = [f"Club {i:02}" for i in range(20)]
    for a, offset in zip(("survive", "midtable", "top4", "title"), (0, 10, 20, 30), strict=True):
        for i, club in enumerate(clubs):
            for group in settings.position_stats:
                score = i + offset
                rows.append({"club": club, "position_group": group, "ambition": a, "need_score": score,
                             "priority": "Medium" if score >= 35 else "Low", "used": True,
                             "evidence": "sufficient", "rated_share": 1.0, "imputed_stats": "[]"})
    nd = pd.DataFrame(rows)
    strength = pd.DataFrame({"club": clubs, "played": 38, "points_per_game": np.arange(20),
                             "goal_difference": np.arange(20), "goals_for": np.arange(20)})
    strength = strength.sort_values("points_per_game", ascending=False)
    values = pd.Series(np.arange(20), index=pd.Index(clubs, name="club"))
    result = evaluate.calibrate_needs(nd, strength, values, settings, 38)
    checks = {c["check"]: c for c in result["checks"]}
    assert result["comparisons"] == 420 and checks["a"]["passed"]
    assert not checks["b"]["passed"] and result["status"] == "failed"
    assert checks["c"]["passed"] and checks["e"]["passed"]
    nd.loc[(nd.club == clubs[0]) & (nd.ambition == "title") & (nd.position_group == "ST"), "need_score"] = 0
    broken = evaluate.calibrate_needs(nd, strength, values, settings, 38)
    assert len(broken["decreases"]) == 1 and not broken["checks"][0]["passed"]


def test_clubelo_failure_is_unavailable_and_one_attempt(settings, monkeypatch):
    import requests

    from scout import sources

    calls = []

    def fail(url, **kwargs):
        calls.append(url)
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(sources._session, "get", fail)
    result = sources.probe_clubelo(settings)
    assert result["status"] == "unavailable" and result["spearman"] is None
    assert len(calls) == 1 and result["attempts"] == 1


def test_clubs_as_played_uses_season_team():
    ps = pd.DataFrame({"league": ["premier_league"] * 3 + ["la_liga"], "team_id": ["1", "1", "1", "9"],
                       "team_name": ["Arsenal", "Arsenal", "Arsenal", "Real Sociedad"],
                       "current_club": ["Arsenal FC", "Arsenal FC", "Porto", "Arsenal FC"]})
    out = evaluate.clubs_as_played(ps, "premier_league")
    assert out["current_club"].tolist() == ["Arsenal FC"] * 3 + ["Real Sociedad"]


def test_jaccard_and_perturb():
    assert evaluate.jaccard({1, 2, 3}, {2, 3, 4}) == pytest.approx(0.5)
    assert evaluate.jaccard(set(), set()) == 1.0
    w = evaluate.perturb({"performance": 0.6, "age": 0.2, "value": 0.2}, "value", 0.1)
    assert sum(w.values()) == pytest.approx(1.0) and w["value"] == pytest.approx(0.3 / 1.1)
    assert evaluate.perturb({"a": 0.05, "b": 0.95}, "a", -0.1)["a"] == 0.0


def test_sensitivity_counts_dropped_groups():
    base = {("X", "ST"): {1, 2, 3, 4}, ("X", "DM"): {5, 6}}
    variants = {"v": lambda: {("X", "ST"): {1, 2, 3, 9}, ("X", "CM"): {7}}}
    row = evaluate.sensitivity(base, variants, [("X", "DM"), ("X", "ST")], [("X", "ST")])["v"]
    assert row["target_club"]["groups_dropped"] == 1 and row["target_club"]["min"] == 0.0
    assert row["target_club"]["players_mean"] == pytest.approx(3 / 5)
    assert row["league_high_medium"]["mean"] == pytest.approx(3 / 5)


def test_league_uefa_and_strength_validation():
    leagues = [lg for lg in load_leagues() if lg.key in ("premier_league", "championship", "la_liga", "eredivisie")]
    coeffs = pd.DataFrame({"country_code": ["ENG", "ESP", "NED", "POR"], "position": [1, 3, 7, 6],
                           "coefficient": [119.5, 97.0, 67.9, 73.2], "season_points": [28.7, 22.1, 10.0, 20.5]})
    uefa = evaluate.league_uefa(coeffs, leagues).set_index("league")
    assert "championship" not in uefa.index
    assert uefa.loc["la_liga", "uefa_coefficient"] == 97.0 and uefa.loc["eredivisie", "uefa_position"] == 7
    strength = pd.DataFrame({"league": ["premier_league", "la_liga", "eredivisie", "championship"],
                             "index_0_100": [100.0, 50.0, 0.0, 30.0]})
    v = evaluate.strength_validation(strength, uefa.reset_index(), "uefa_coefficient")
    assert v["n"] == 3 and v["spearman"] == pytest.approx(1.0) and v["pearson"] > 0.9
    assert v["measure"] == "uefa_coefficient"


def test_charts_render(tmp_path):
    r = {"uplift": 0.5, "ci_low": 0.3, "ci_high": 0.7, "picks_scored": 10}
    result = {"club": "Club FC", "groups": {"ST": r}, "overall": r, "league_pooled": {**r, "clubs": 20},
              "naive_baseline": {"league_pooled": r}}
    evaluate.plot_backtest(result, tmp_path / "b.png")
    validation = {"measure": "uefa_coefficient", "n": 2, "pearson": 0.9, "spearman": 1.0,
                  "table": [{"league": "a", "index_0_100": 0.0, "uefa_coefficient": 50.0},
                            {"league": "b", "index_0_100": 100.0, "uefa_coefficient": 120.0}]}
    evaluate.plot_league_strength(validation, {"a": "A", "b": "B"}, "UEFA country coefficient (5 seasons)",
                                  tmp_path / "s.png")
    assert (tmp_path / "b.png").stat().st_size > 1000 and (tmp_path / "s.png").stat().st_size > 1000
