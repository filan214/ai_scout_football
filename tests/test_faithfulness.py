"""Faithfulness: tolerance, integers, missing fact keys, injected wrong number. No network."""

import pytest

from scout import faithfulness

FACTS = {
    "player.name": "Equi Fernández", "player.age": 23, "player.team": "Bayer 04 Leverkusen",
    "player.market_value_m": 20.0, "player.minutes": 2640, "stats.ball_recoveries.p90": 6.41,
    "stats.ball_recoveries.pct": 91, "stats.accurate_passes_pct.value": 88.4, "fit.score": 92.2,
    "context.season": "2025-26",
}


def _report(*texts, keys=("stats.ball_recoveries.pct",), summary="Ball-winning midfielder."):
    claims = [{"text": t, "fact_keys": list(keys)} for t in texts]
    return {"summary": summary, "strengths": claims[:-1] or claims, "risks": claims[-1:], "verdict": "strong option"}


GOOD = _report(
    "Wins the ball back 6.41 times per 90 (91st percentile).",
    "Completes 88.4% of passes; valued at €20.0m in the 2025-26 season.",
    "Played 2,640 minutes at age 23 for Bayer 04 Leverkusen.",
)


def test_faithful_report_fully_verified():
    check = faithfulness.verify(GOOD, FACTS)
    assert check["numbers"] == 6
    assert check["verified_rate"] == 1.0 and check["fully_verified"]


def test_extract_numbers_units_and_strings():
    got = faithfulness.extract_numbers("€42.0m, 91%, 2,640 minutes, 0.58 per 90, U21, 2025-26", FACTS)
    assert got == [(42.0, False), (91.0, True), (2640.0, True), (0.58, False)]


def test_decimal_tolerance_and_integer_exactness():
    facts = [6.41, 20.0, 91.0, 0.58]
    assert faithfulness.number_matches(6.5, False, facts)
    assert not faithfulness.number_matches(6.6, False, facts)
    assert faithfulness.number_matches(0.62, False, facts)
    assert not faithfulness.number_matches(0.64, False, facts)
    assert faithfulness.number_matches(20, True, facts)
    assert not faithfulness.number_matches(92, True, facts)
    assert not faithfulness.number_matches(6, True, facts)


def test_injected_wrong_number_is_caught():
    bad = _report(
        "Wins the ball back 7.9 times per 90 (91st percentile).",
        "Completes 88.4% of passes.",
    )
    check = faithfulness.verify(bad, FACTS)
    assert check["unverified"] == [7.9] and not check["fully_verified"]
    assert check["verified_rate"] == pytest.approx(2 / 3)


def test_missing_fact_key_is_caught():
    check = faithfulness.verify(_report("Strong passer.", "Young.", keys=("stats.tackles.pct",)), FACTS)
    assert check["missing_fact_keys"] == ["stats.tackles.pct"] and not check["fully_verified"]
    assert check["verified_rate"] == 1.0


def test_summary_numbers_are_checked_too():
    check = faithfulness.verify(_report("Fine.", "Fine.", summary="A 25-year-old midfielder."), FACTS)
    assert check["unverified"] == [25.0]


def test_aggregate():
    a = faithfulness.verify(GOOD, FACTS)
    b = faithfulness.verify(_report("7.9 per 90.", "88.4%."), FACTS)
    agg = faithfulness.aggregate([a, b])
    assert (agg["reports"], agg["numbers"], agg["verified"], agg["fully_verified_reports"]) == (2, 8, 7, 1)
    assert agg["verified_rate"] == pytest.approx(7 / 8)
