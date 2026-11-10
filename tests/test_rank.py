"""Ranking: filters, score formulas, tie-breaks, determinism. Synthetic data, no network."""

import hashlib
import json

import pandas as pd
import pytest

from scout import rank
from scout.config import load_settings


@pytest.fixture
def settings():
    s = load_settings()
    return s.model_copy(update={"shortlist_size": 3, "min_ranked_groups": 0})


def _cand(fid, xg, shots, age=24, value=10.0, group="ST", qualifies=True, club="Other FC"):
    return {"fotmob_id": fid, "tm_id": f"t{fid}", "player_name": f"P{fid}", "team_name": "T", "league": "la_liga",
            "current_club": club, "position_group": group, "qualifies": qualifies, "age": age,
            "market_value_m": value, "minutes": 2500, "xg_pct": xg, "shots_pct": shots}


NEEDS = pd.DataFrame([
    {"club": "Club FC", "position_group": "ST", "need_score": 70.0, "priority": "High",
     "stat_weights": json.dumps({"xg": 0.75, "shots": 0.25}), "evidence": "sufficient",
     "current_best_regular": "Incumbent", "current_best_composite": 50.0,
     "benchmark": json.dumps({"xg": 95, "shots": 95})},
    {"club": "Club FC", "position_group": "CB", "need_score": 10.0, "priority": "Low",
     "stat_weights": json.dumps({"xg": 1.0}), "evidence": "sufficient",
     "current_best_regular": "Incumbent CB", "current_best_composite": 50.0,
     "benchmark": json.dumps({"xg": 95})},
])


def _pool():
    return pd.DataFrame([
        _cand("1", 80, 40),
        _cand("2", 60, 100, age=21, value=0.0),
        _cand("3", 90, 90, qualifies=False),
        _cand("4", 90, 90, age=28),
        _cand("5", 90, 90, value=61.0),
        _cand("6", 90, 90, value=None),
        _cand("7", 90, 90, club="Club FC"),
        _cand("8", 90, 90, group="CB"),
        _cand("9", 100, 0, age=27, value=30.0),
    ]).astype({"age": "Int64"})


def test_filters_scores_and_order(settings):
    out = rank.rank_targets(_pool(), NEEDS, settings)
    assert out["fotmob_id"].tolist() == ["1", "2", "9"]
    assert out["position_group"].unique().tolist() == ["ST"] and out["rank"].tolist() == [1, 2, 3]
    r = out.set_index("fotmob_id")
    assert r.loc["1", "performance"] == pytest.approx(0.75 * 80 + 0.25 * 40)
    assert (r.loc["2", "age_score"], r.loc["9", "age_score"], r.loc["1", "age_score"]) == (90, 90, 100)
    assert r.loc["1", "value_score"] == pytest.approx(100 * (1 - 0.5 * 10 / 60))
    assert r.loc["2", "value_score"] == 100
    assert r.loc["9", "fit"] == pytest.approx(0.6 * 75 + 0.2 * 90 + 0.2 * 75)


def test_verdict_is_computed_from_rank_and_need():
    ranks = {"priority_target": 3, "strong_option": 5}
    assert rank.verdict(3, "High", ranks) == "priority target"
    assert rank.verdict(4, "High", ranks) == "strong option"
    assert rank.verdict(1, "Low", ranks) == "strong option"
    assert rank.verdict(6, "Medium", ranks) == "monitor"


def test_shortlist_carries_verdict(settings):
    out = rank.rank_targets(_pool(), NEEDS, settings)
    assert out["verdict"].tolist() == ["priority target"] * 3


def test_age_score_outside_ideal():
    ages = pd.Series([18, 22, 26, 27, 40], dtype="Int64")
    assert rank.age_score(ages, (22, 26)).tolist() == [60, 100, 100, 90, 0]


def test_tie_breaks_performance_then_value_then_id(settings):
    s = settings.model_copy(update={"fit_weights": {"performance": 0.5, "age": 0.5, "value": 0.0}})
    pool = pd.DataFrame([
        _cand("b", 80, 80, value=20.0),
        _cand("a", 80, 80, value=20.0),
        _cand("c", 80, 80, value=10.0),
        _cand("d", 100, 20, age=21),
        _cand("e", 90, 90, age=20),
    ]).astype({"age": "Int64"})
    out = rank.rank_targets(pool, NEEDS, s.model_copy(update={"shortlist_size": 10}))
    assert out["fotmob_id"].tolist() == ["c", "a", "b", "e", "d"]


def _digest(df: pd.DataFrame) -> str:
    return hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()


def test_determinism_two_runs_identical_hash(settings):
    pool = _pool()
    first = rank.rank_targets(pool, NEEDS, settings)
    second = rank.rank_targets(pool, NEEDS, settings)
    shuffled = rank.rank_targets(pool.sample(frac=1, random_state=3), NEEDS.iloc[::-1], settings)
    assert _digest(first) == _digest(second) == _digest(shuffled)


def test_no_high_or_medium_needs_gives_empty_shortlist(settings):
    out = rank.rank_targets(_pool(), NEEDS.assign(priority="Low"), settings)
    assert out.empty and list(out.columns) == rank.SHORTLIST_COLUMNS


def test_min_ranked_groups_ranks_top_needs_even_when_low(settings):
    low = NEEDS.assign(priority="Low")
    one = rank.rank_targets(_pool(), low, settings.model_copy(update={"min_ranked_groups": 1}))
    assert one["position_group"].unique().tolist() == ["ST"]
    two = rank.rank_targets(_pool(), low, settings.model_copy(update={"min_ranked_groups": 2}))
    assert two["position_group"].unique().tolist() == ["ST", "CB"]
    assert two.loc[two["position_group"] == "CB", "fotmob_id"].tolist() == ["8"]
    high = rank.rank_targets(_pool(), NEEDS, settings.model_copy(update={"min_ranked_groups": 1}))
    assert high["position_group"].unique().tolist() == ["ST"]
    unused = low.assign(used=[True, False])
    out = rank.rank_targets(_pool(), unused, settings.model_copy(update={"min_ranked_groups": 2}))
    assert out["position_group"].unique().tolist() == ["ST"]


def test_upgrade_filter_inclusive_and_benchmark_flags(settings):
    need = NEEDS.copy()
    need.loc[need.position_group == "ST", "current_best_composite"] = 65
    out = rank.rank_targets(_pool(), need, settings)
    assert set(out.fotmob_id) == {"1", "2", "9"}
    assert out.set_index("fotmob_id").loc["1", "upgrade_vs_current"] == 5
    assert out.below_ambition_benchmark.all()
    need.loc[need.position_group == "ST", "current_best_composite"] = 65.1
    out = rank.rank_targets(_pool(), need, settings)
    assert out.fotmob_id.tolist() == ["9"]
    out = rank.rank_targets(_pool(), need, settings.model_copy(update={"ambition": "survive"}))
    assert not out.below_ambition_benchmark.any()


def test_insufficient_evidence_or_unknown_incumbent_never_ranks(settings):
    assert rank.rank_targets(_pool(), NEEDS.assign(evidence="insufficient"), settings).empty
    assert rank.rank_targets(_pool(), NEEDS.assign(current_best_composite=None), settings).empty
