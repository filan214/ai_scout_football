"""Experiment definitions preserve the fixed cohort and all original percentile columns."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def experiment_module():
    path = Path(__file__).resolve().parents[1] / "scripts/quality_experiment.py"
    spec = importlib.util.spec_from_file_location("quality_experiment", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_new_stat_definitions_preserve_original_percentiles_and_eligibility():
    experiment = experiment_module()
    rows = pd.DataFrame({"position_group": ["CB"] * 3, "qualifies": [True, True, False],
                         "league_factor": [1.0, 0.8, 1.0], "team_possession": [0.4, 0.6, 0.5]})
    for base in {base for base, _ in experiment.definitions().values()}:
        rows[base + "_p90"] = [2.0, 4.0, 6.0]
        rows[base + "_adj"] = [2.0, 3.2, 6.0]
        rows[base + "_pct"] = [50.0, 100.0, np.nan]
    before = rows.copy(deep=True)
    after = experiment.add_definitions(rows)
    pd.testing.assert_frame_equal(rows, before)
    pd.testing.assert_frame_equal(after[before.columns], before)
    assert after["tackles__raw_adj"].tolist() == [2.0, 3.2, 6.0]
    assert after.loc[0, "accurate_passes__per_possession_adj"] == pytest.approx(2.5)
    assert pd.isna(after.loc[2, "accurate_passes__per_possession_pct"])
    assert after.loc[:1, "tackles__raw_pct"].tolist() == [50.0, 100.0]
