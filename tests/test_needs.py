"""§6.5 needs: each component, league-relative benchmark, M = 0, stat weights. Synthetic data, no network."""

import json

import numpy as np
import pandas as pd
import pytest

from scout import needs
from scout.config import Squad, load_settings


@pytest.fixture
def settings():
    s = load_settings()
    return s.model_copy(update={
        "target_league": "premier_league",
        "ambition_club_rank": {"survive": 3, "midtable": 2, "top4": 2, "title": 1},
        "squad": Squad(reliable_minutes=900, depth_targets={"ST": 2, "CB": 4}),
        "position_stats": {"ST": ["xg", "shots"], "CB": ["tackles"]},
        "ambition": "title",
    })


def _player(fid, group, minutes, age, months, xg=None, shots=None, club="Club FC", team="T1"):
    return {"fotmob_id": fid, "current_club": club, "team_id": team, "league": "premier_league",
            "position_group": group, "minutes": minutes, "age": age, "contract_months_left": months,
            "xg_pct": xg, "shots_pct": shots, "tackles_pct": None}


@pytest.fixture
def league():
    """Club FC squad pct: xg 84, shots 54. Other FC: 10 / 10. Third FC: 95 / 95."""
    return pd.DataFrame([
        _player("a", "ST", 2000, 25, 6.0, xg=90, shots=50),
        _player("b", "ST", 500, 31, np.nan, xg=60, shots=70),
        _player("c", "ST", 300, 34, 2.0),                                       # not qualifying: no percentiles
        _player("k", None, 3000, 35, 1.0),                                      # goalkeeper: ignored
        _player("x", "ST", 3000, 33, 1.0, xg=10, shots=10, club="Other FC", team="T2"),
        _player("y", "ST", 2500, 24, 30.0, xg=95, shots=95, club="Third FC", team="T3"),
    ]).astype({"age": "Int64"})


def test_components_and_score(settings, league):
    st = needs.compute_needs(league, "Club FC", settings).set_index("position_group").loc["ST"]
    assert st["reliable"] == 1 and st["squad_players"] == 3 and st["minutes"] == 2800
    regulars = 1 + 500 / 900 + 300 / 900                                  # fractional regulars
    assert st["regulars"] == pytest.approx(regulars)
    assert st["depth_gap"] == pytest.approx(100 * (2 - regulars) / 2)
    assert st["used"] and st["usage"] == 1.0                              # ST is a core group
    pct = json.loads(st["squad_pct"])
    assert pct["xg"] == pytest.approx((2000 * 90 + 500 * 60) / 2500)     # 84: unrated player c left out
    assert pct["shots"] == pytest.approx((2000 * 50 + 500 * 70) / 2500)  # 54
    assert json.loads(st["benchmark"]) == {"xg": 95.0, "shots": 95.0}     # title = best club per stat
    quality = 100 * ((95 - 84) / 95 + (95 - 54) / 95) / 2
    assert st["quality_gap"] == pytest.approx(quality)
    assert st["age_risk"] == pytest.approx(100 * (500 + 300) / 2800)      # b and c are 30+
    assert st["contract_risk"] == pytest.approx(100 * (2000 + 300) / 2800)  # b unknown = not at risk
    w = settings.need_weights
    urgency = (w["depth"] * 100 * (2 - regulars) / 2 + w["age"] * 100 * 800 / 2800
               + w["contract"] * 100 * 2300 / 2800)
    expected = quality + (1 - quality / 100) * urgency
    assert st["need_score"] == pytest.approx(expected)
    weights = json.loads(st["stat_weights"])
    assert weights == {"xg": pytest.approx(0.7 * 11 / 52 + 0.15), "shots": pytest.approx(0.7 * 41 / 52 + 0.15)}


def test_benchmark_is_kth_best_club(settings, league):
    top2 = settings.model_copy(update={"ambition": "top4"})              # k = 2 in this 3-club league
    assert needs.benchmarks(league, top2)["ST"] == {"xg": 84.0, "shots": 54.0}
    st = needs.compute_needs(league, "Club FC", top2).set_index("position_group").loc["ST"]
    assert st["quality_gap"] == 0                                         # Club FC is the 2nd-best squad
    worst = needs.compute_needs(league, "Other FC", top2).set_index("position_group").loc["ST"]
    assert worst["quality_gap"] == pytest.approx(100 * ((84 - 10) / 84 + (54 - 10) / 54) / 2)
    survive = settings.model_copy(update={"ambition": "survive"})        # k = 3 = last club
    assert needs.benchmarks(league, survive)["ST"] == {"xg": 10.0, "shots": 10.0}


def test_unrated_squad_uses_league_median_level(settings, league):
    unrated = pd.concat([league, pd.DataFrame([_player("u", "ST", 1500, 26, 30.0, club="Fourth FC", team="T4")])])
    unrated = unrated.astype({"age": "Int64"})
    st = needs.compute_needs(unrated, "Fourth FC", settings).set_index("position_group").loc["ST"]
    assert json.loads(st["squad_pct"]) == {"xg": None, "shots": None}
    median_xg, median_shots = 84.0, 54.0                                  # median of rated clubs 84/10/95, 54/10/95
    assert st["quality_gap"] == pytest.approx(100 * ((95 - median_xg) / 95 + (95 - median_shots) / 95) / 2)
    assert st["evidence"] == "insufficient" and st["rated_share"] == 0
    assert json.loads(st["imputed_stats"]) == ["xg", "shots"]


def test_empty_core_group_m_zero(settings, league):
    cb = needs.compute_needs(league, "Club FC", settings).set_index("position_group").loc["CB"]
    assert (cb["depth_gap"], cb["quality_gap"], cb["age_risk"], cb["contract_risk"]) == (100, 100, 0, 0)
    assert cb["need_score"] == 100 and cb["priority"] == "High"
    assert cb["evidence"] == "insufficient"
    assert json.loads(cb["stat_weights"]) == {"tackles": pytest.approx(1.0)}


def test_optional_group_scaled_by_usage(settings, league):
    s = settings.model_copy(update={
        "squad": Squad(reliable_minutes=900, depth_targets={"ST": 2, "AM": 2, "CB": 4}, optional_groups=["AM"],
                       min_usage=0.25),
        "position_stats": {"ST": ["xg", "shots"], "AM": ["xg"], "CB": ["tackles"]},
    })
    rare = pd.concat([league, pd.DataFrame([_player("m", "AM", 100, 24, 30.0, xg=50)])]).astype({"age": "Int64"})
    am = needs.compute_needs(rare, "Club FC", s).set_index("position_group").loc["AM"]
    usage = (100 / 2900) / (2 / 8)                                        # minutes share / typical share
    assert am["usage"] == pytest.approx(usage) and not am["used"]        # 0.14 < 0.25: club plays no #10
    assert am["need_score"] == 0 and am["priority"] == "Low"
    half = pd.concat([league, pd.DataFrame([_player("m", "AM", 450, 24, 30.0, xg=50)])]).astype({"age": "Int64"})
    am = needs.compute_needs(half, "Club FC", s).set_index("position_group").loc["AM"]
    usage = (450 / 3250) / (2 / 8)                                        # 0.55: target 2 × 0.55
    assert am["used"] and am["usage"] == pytest.approx(usage)
    assert am["depth_gap"] == pytest.approx(100 * (2 * usage - 450 / 900) / (2 * usage))


def test_stat_weights_blend_and_sum():
    w = needs.stat_weights({"xg": 0.0, "shots": 26.0}, blend=0.7)
    assert w == {"xg": pytest.approx(0.15), "shots": pytest.approx(0.85)}
    assert needs.stat_weights({"a": 0, "b": 0, "c": 0}, 0.7) == {k: pytest.approx(1 / 3) for k in "abc"}
    w = needs.stat_weights({"a": 3.0, "b": 1.0, "c": 6.0, "d": 0.0}, 0.7)
    assert sum(w.values()) == pytest.approx(1.0)


def test_league_clubs_uses_most_common_current_club():
    ps = pd.DataFrame({"league": ["premier_league"] * 5 + ["la_liga"],
                       "team_id": ["1", "1", "1", "2", "2", "3"],
                       "current_club": ["Arsenal FC", "Arsenal FC", "Porto", "Chelsea FC", None, "Real Madrid"]})
    assert needs.league_clubs(ps, "premier_league") == ["Arsenal FC", "Chelsea FC"]


def test_candidate_a_bounds_identity_and_component_monotonicity(settings):
    from itertools import product

    weights = settings.need_weights
    for values in product([0, 25, 50, 75, 100], repeat=4):
        score = needs.combine_need(*values, weights)
        assert 0 <= score <= 100
        for index in range(4):
            increased = list(values)
            increased[index] = min(100, increased[index] + 10)
            assert needs.combine_need(*increased, weights) >= score - 1e-12
    for quality in [0, 1, 35, 60, 99, 100]:
        assert needs.combine_need(0, quality, 0, 0, weights) == quality
    assert needs.combine_need(100, 100, 100, 100, weights) == 100


def test_ambition_never_reduces_need(settings, league):
    scores = [needs.compute_all_needs(league, settings.model_copy(update={"ambition": a}))
              .set_index(["club", "position_group"])["need_score"]
              for a in ("survive", "midtable", "top4", "title")]
    for low, high in zip(scores, scores[1:], strict=False):
        assert (high >= low - 1e-9).all()


def test_evidence_threshold_is_inclusive(settings, league):
    base = needs.compute_needs(league, "Club FC", settings).set_index("position_group").loc["ST"]
    share = base["rated_share"]
    assert 0 < share < 1
    exact = settings.model_copy(update={"min_rated_share": share})
    above = settings.model_copy(update={"min_rated_share": share + 0.001})
    assert needs.compute_needs(league, "Club FC", exact).iloc[0]["evidence"] == "sufficient"
    assert needs.compute_needs(league, "Club FC", above).iloc[0]["evidence"] == "insufficient"


def test_league_clubs_uses_live_current_league():
    ps = pd.DataFrame({"league": ["pl", "pl", "ch"], "team_id": ["1", "2", "3"],
                       "current_club": ["Stayed FC", None, "Promoted FC"],
                       "current_league": ["pl", None, "pl"]})
    assert needs.league_clubs(ps, "pl") == ["Promoted FC", "Stayed FC"]
    assert needs.league_clubs(ps.drop(columns="current_league"), "pl") == ["Stayed FC"]
