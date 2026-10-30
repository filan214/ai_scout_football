"""Combined squad evidence on an unchanged percentile pool (§6.4–§6.5)."""

import numpy as np
import pandas as pd
import pytest

from scout import features
from scout.config import load_settings


def sample():
    rows = [
        ("a", 1200, 10, True, "Home"),
        ("b", 1300, 20, True, "Home"),
        ("c", 1400, 20, True, "Home"),
        ("d", 1500, 40, True, "Home"),
        ("placed", 200, 10, False, "Home"),
        ("placed", 400, 40, False, "Away"),
        ("short", 599, 30, False, "Home"),
        ("missing", 900, np.nan, False, "Home"),
    ]
    ps = pd.DataFrame(rows, columns=["fotmob_id", "minutes", "xg_adj", "qualifies", "current_club"])
    ps["current_club"] = "Home"
    ps["position_group"] = "ST"
    ps["xg_pct"] = np.nan
    ps.loc[ps.qualifies, "xg_pct"] = ps.loc[ps.qualifies, "xg_adj"].rank(pct=True) * 100
    s = load_settings().model_copy(update={"position_stats": {"ST": ["xg"]}})
    return ps, s


def test_empirical_placement_ties_between_and_tails():
    ref = pd.Series([10, 20, 20, 40])
    values = pd.Series([0, 10, 20, 30, 40, 50, np.nan])
    got = features.empirical_percentile(values, ref)
    assert got.iloc[:6].tolist() == [0, 25, 62.5, 75, 100, 100]
    assert pd.isna(got.iloc[6])
    assert features.empirical_percentile(values, pd.Series(dtype=float)).isna().all()


def test_combining_and_placement_leave_pool_exactly_unchanged():
    ps, s = sample()
    before = ps.copy(deep=True)
    profiles = features.squad_profiles(ps, s).set_index("fotmob_id")
    pd.testing.assert_frame_equal(ps, before)
    for fid in ("a", "b", "c", "d"):
        assert profiles.loc[fid, "xg_pct"] == ps.set_index("fotmob_id").loc[fid, "xg_pct"]
        assert not profiles.loc[fid, "rated_by_placement"]
    row = profiles.loc["placed"]
    assert row["minutes"] == 600 and row["source_rows"] == 2
    assert row["xg_adj"] == pytest.approx(30)
    assert row["xg_pct"] == 75 and row["rated_by_placement"]
    assert not row["qualifies"] and row["fully_rated"]
    assert pd.isna(profiles.loc["short", "xg_pct"])
    assert pd.isna(profiles.loc["missing", "xg_pct"])
    assert not profiles.loc["missing", "fully_rated"]


def test_partial_stats_never_become_full_evidence_or_zeroes():
    ps, s = sample()
    ps["shots_adj"] = ps["xg_adj"]
    ps["shots_pct"] = ps["xg_pct"]
    ps.loc[ps.fotmob_id == "placed", "shots_adj"] = np.nan
    s = s.model_copy(update={"position_stats": {"ST": ["xg", "shots"]}})
    row = features.squad_profiles(ps, s).set_index("fotmob_id").loc["placed"]
    assert row["rated_by_placement"] and not row["fully_rated"]
    assert pd.isna(row["shots_pct"]) and row["rated_minutes"] == 0


def test_profiles_are_independent_of_input_order():
    ps, s = sample()
    cols = ["fotmob_id", "minutes", "xg_adj", "xg_pct", "fully_rated", "rated_by_placement"]
    pd.testing.assert_frame_equal(features.squad_profiles(ps, s)[cols],
                                  features.squad_profiles(ps.sample(frac=1, random_state=7), s)[cols])
