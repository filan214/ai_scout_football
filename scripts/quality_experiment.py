"""Pre-register stat selection without outcomes, then evaluate V0/V1 once; V2 requires Sofascore data."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scout import evaluate, needs, rank, sources  # noqa: E402
from scout.config import load_leagues, load_settings, transfermarkt_db_path  # noqa: E402

WORK = ROOT / "data/interim/quality_experiment"
OUT = ROOT / "data/processed/eval/quality_experiment"
DOC = ROOT / "docs/QUALITY_EXPERIMENT.md"
ATTACK = ["goals", "assists", "xg", "xgot", "xa", "shots", "key_passes",
          "big_chances_created", "successful_dribbles"]
PASS = ["accurate_passes", "accurate_passes_pct", "accurate_long_balls"]
DEFENCE = ["tackles", "interceptions", "clearances", "blocks", "ball_recoveries", "defensive_actions"]
UNIVERSE = {
    "ST": ATTACK + ["accurate_passes_pct"],
    "W": ATTACK + PASS + ["possession_won_final_third"],
    "AM": ATTACK + PASS + ["possession_won_final_third"],
    "CM": ATTACK + PASS + DEFENCE + ["possession_won_final_third"],
    "DM": PASS + DEFENCE + ["xa", "key_passes", "successful_dribbles", "possession_won_final_third"],
    "FB": PASS + DEFENCE + ["xa", "key_passes", "successful_dribbles", "big_chances_created"],
    "CB": PASS + DEFENCE + ["goals", "xg", "xa", "key_passes"],
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def md(frame):
    def fmt(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "N/A"
        return f"{v:.4f}" if isinstance(v, float) else str(v).replace("|", "/")
    return ("\n| " + " | ".join(frame.columns) + " |\n| " + " | ".join(["---"] * len(frame.columns))
            + " |\n" + "\n".join("| " + " | ".join(fmt(v) for v in row) + " |"
                                  for row in frame.itertuples(index=False, name=None)) + "\n")


def settings():
    coverage = read(ROOT / "data/processed/coverage.json")
    return load_settings().model_copy(update={"position_stats": coverage["position_stats"],
                                              "target_club": "West Ham United", "ambition": "title"})


def inputs():
    paths = ["data/interim/perf.parquet", "data/processed/id_map.parquet",
             "data/interim/tm_players.parquet", "data/interim/tm_valuations.parquet",
             "data/interim/team_stats.parquet"]
    return [pd.read_parquet(ROOT / path) for path in paths]


def season(perf, tables, s, year, date):
    return evaluate.season_table(perf, *tables, load_leagues(), s, year, date)[0]


def definitions():
    result = {}
    for base in sorted(set(sum(UNIVERSE.values(), []))):
        result[base] = (base, "current")
        if base in DEFENCE:
            result[base + "__raw"] = (base, "raw")
        elif base != "accurate_passes_pct":
            result[base + "__per_possession"] = (base, "own_possession")
    return result


def add_definitions(ps):
    out = ps.copy()
    for name, (base, mode) in definitions().items():
        if mode == "current":
            continue
        value = out[base + "_p90"] * out.league_factor
        if mode == "own_possession":
            value = value * 0.5 / out.team_possession
        out[name + "_adj"] = value
        out[name + "_p90"] = value / out.league_factor
        qualified = out[out.qualifies]
        out[name + "_pct"] = qualified.groupby("position_group")[name + "_adj"].rank(pct=True) * 100
    return out


def correlation(x, y):
    frame = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna()
    value = frame.x.rank().corr(frame.y.rank()) if len(frame) > 1 else np.nan
    return None if pd.isna(value) else float(value)


def player_values(ps, group, stat, s):
    rows = ps[(ps.position_group == group) & (ps.minutes_share >= s.pool.min_minutes_share)]
    rows = rows.dropna(subset=[stat + "_adj"])
    num = (rows[stat + "_adj"] * rows.minutes).groupby(rows.fotmob_id).sum()
    return num / rows.groupby("fotmob_id").minutes.sum()


def prepare():
    if DOC.exists():
        raise RuntimeError("Registration already exists; do not change selected sets after outcomes")
    WORK.mkdir(parents=True, exist_ok=True)
    s = settings()
    perf, *tables = inputs()
    p24 = add_definitions(season(perf, tables, s, s.backtest.season_n, s.backtest.as_of_date))
    p25 = add_definitions(pd.read_parquet(ROOT / "data/processed/player_season.parquet"))
    p24.to_parquet(WORK / "2024-25.parquet", index=False)
    p25.to_parquet(WORK / "2025-26.parquet", index=False)
    records, selected = [], {}
    for group, candidates in UNIVERSE.items():
        group_rows = []
        for stat, (base, mode) in definitions().items():
            if base not in candidates:
                continue
            a, b = player_values(p24, group, stat, s), player_values(p25, group, stat, s)
            pair = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
            repeat = correlation(pair.a, pair.b)
            old = p24[(p24.position_group == group) & (p24.minutes_share >= s.pool.min_minutes_share)]
            style = correlation(old[stat + "_adj"], old.team_possession)
            coverage = min(float(p.loc[p.qualifies].groupby("league")[stat + "_adj"].apply(
                lambda v: v.notna().mean()).min()) for p in (p24, p25))
            group_rows.append({"position": group, "stat": stat, "base": base, "definition": mode,
                               "paired_players": len(pair), "repeatability": repeat,
                               "abs_possession_rho": None if style is None else abs(style),
                               "min_coverage": coverage})
        frame = pd.DataFrame(group_rows)
        eligible = frame.dropna(subset=["repeatability", "abs_possession_rho"])
        eligible = eligible[eligible.min_coverage >= s.coverage_threshold].copy()
        eligible["rank_sum"] = (eligible.repeatability.rank(ascending=False, method="min")
                                + eligible.abs_possession_rho.rank(method="min"))
        ordered = eligible.sort_values(["rank_sum", "repeatability", "abs_possession_rho", "stat"],
                                       ascending=[True, False, True, True])
        picks = ordered.drop_duplicates("base").head(6).stat.tolist()
        if len(picks) != 6:
            raise RuntimeError("Fewer than six eligible stats; do not invent or relax eligibility")
        selected[group] = picks
        frame["selected"] = frame.stat.isin(picks)
        records.extend(json.loads(frame.to_json(orient="records")))
    probe = read(ROOT / "data/interim/sofascore_experiment_probe.json")
    registration = {"V0": s.position_stats, "V1": selected, "V2": None,
                    "V2_status": "unavailable: no Sofascore ratings; live API probe failed",
                    "sofascore_probe": probe, "candidates": records}
    save(WORK / "registration.json", registration)
    save(OUT / "registration.json", registration)
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in [ROOT / "config/settings.yaml", ROOT / "data/processed/player_season.parquet"]}
    save(WORK / "input_hashes.json", hashes)
    text = """# Quality estimator experiment: pre-registration

Hypothesis: defensive volume can reflect team style more than player quality. Stat selection below used
no points, PPG, goals conceded, goal difference or standings of either season.

## Frozen protocol

- Timebox: 90 minutes of experiment execution after registration commit. Evaluate V0 and V1 once;
  V2 once only if actual Sofascore ratings can be obtained within the source-access check.
- V0 is the current six-stat sets. V1 selects six distinct base statistics per position using the sum of
  descending-repeatability rank and ascending-absolute-possession-correlation rank (equal criterion weight).
  Break ties by higher repeatability, lower absolute style correlation, then lexical stat name.
  Keep only stats passing the existing 95% per-league pool coverage rule in both seasons.
  Consider at most one definition per base statistic, greedily in that fixed order; no correlated
  duplicate definitions of the same stat may fill multiple slots.
- Repeatability: player-level Spearman 2024-25 versus 2025-26 for players passing the minutes rule
  in both seasons; combine observed same-season rows by minutes. Do not add a matches filter
  to this selection cohort; missing stat pairs are excluded and paired n is shown.
- Style: absolute Spearman with team possession in 2024-25 among minutes-eligible role rows.
- Candidate universes are football-role lists in scripts/quality_experiment.py, fixed before calibration.
  No stat is chosen by a club outcome. Current definitions retain existing league and possession adjustment.
  Defensive raw alternatives remove the existing opponent-possession adjustment. Other counting-stat
  alternatives divide by team possession relative to 0.5. Pass accuracy remains a success rate.
- Actual tackle-success %, duel-win % and aerial-win % cannot be reconstructed: denominators are absent
  in the downloaded source. They are unavailable candidates, not zero values.
- V2 = V1 plus Sofascore average rating. No Sofascore ratings are cached, and the installed-adapter
  season endpoint failed its single live availability check. V2 is therefore UNAVAILABLE, not substituted
  with FotMob rating, not treated as V1, and not counted as passing or failing.
- Keep original qualifying flags/cohort and existing percentile columns exactly unchanged. Derived
  definitions receive percentile ranks within the SAME qualifying role pool. There is one percentile
  system per variant for squad and targets; no PL-only reference or relaxed eligibility.
- Candidate A, urgency coefficients, evidence rules, bands, target filters/upgrade margins, and
  acceptance a-e stay fixed. Production files and V0 reports are not overwritten by V1.
- Run existing backtest and ten fixed sensitivity perturbations for each available variant.
  Sensitivity perturbations are diagnostics, not extra quality variants or tuning.
- Bias = share of West Ham/title shortlist rows from the six highest-value clubs in the ORIGINAL
  qualifying pool: sum market values of unique qualifying player IDs by current_club, all ages/positions.
  Fix those six club names before evaluating V0/V1; do not redefine for each shortlist.
- STOP: if no alternative passes b without failing another check OR increasing bias over V0,
  retain V0 and document b as a limitation. No additional variants, thresholds or outcome-driven
  reselection in this session. Otherwise recommend the passing alternative and wait for user approval.
- 2025-26 is NOT an untouched holdout: its aggregate calibration was already inspected, and its
  player stat values are explicitly used in the requested repeatability criterion.

## Frozen stat sets
"""
    text += md(pd.DataFrame([{"position": g, "V0": ", ".join(s.position_stats[g]),
                             "V1": ", ".join(selected[g]), "V2": "Unavailable"} for g in selected]))
    text += "\n## Every available candidate and selection criterion\n"
    text += md(pd.DataFrame(records))
    text += "\n## Unavailable candidates\n\nTackle-success %, duel-win %, aerial-win %: missing source denominators. "
    text += "Sofascore average rating: source unavailable; probe metadata below.\n\n"
    text += "```json\n" + json.dumps(probe, indent=2) + "\n```\n"
    DOC.write_text(text, encoding="utf-8")
    print("PREPARED; no calibration executed. Commit QUALITY_EXPERIMENT.md before --evaluate.")


def evaluate_variant(name, p24, p25, stats, s):
    s = s.model_copy(update={"position_stats": stats})
    path = OUT / (name + ".json")
    if path.exists():
        return read(path)  # resume saved results; never repeat a completed evaluation
    nd = pd.concat([needs.compute_all_needs(p25, s.model_copy(update={"ambition": a}))
                    for a in ("survive", "midtable", "top4", "title")], ignore_index=True)
    played = sources.load_club_games(transfermarkt_db_path(), "GB1", 2025)
    strength = evaluate.season_results(played)
    values = p25[p25.league == s.target_league].groupby("team_id").market_value_m.sum()
    values.index = values.index.map(needs.team_clubs(p25, s.target_league))
    values.index.name = "club"
    calibration = evaluate.calibrate_needs(nd, strength, values, s, 38)
    title = nd[nd.ambition == "title"]
    sl = rank.rank_targets(p25, title[title.club == s.target_club], s)
    leaders = (p25[p25.qualifies].drop_duplicates("fotmob_id").groupby("current_club").market_value_m.sum()
               .sort_values(ascending=False).head(6))
    quality = {g: correlation(rows.set_index("club").quality_gap,
                             strength.set_index("club").points_per_game)
               for g, rows in title.groupby("position_group")}
    historical = evaluate.clubs_as_played(p24, s.target_league)
    bt = evaluate.backtest(historical, p25, s.target_club, needs.league_clubs(historical, s.target_league), s)
    clubs = needs.league_clubs(p25, s.target_league)
    base_nd = needs.compute_all_needs(p25, s.model_copy(update={"ambition": "top4"}))
    sensitivity_s = s.model_copy(update={"ambition": "top4"})
    base = evaluate.shortlist_sets(p25, base_nd, clubs, sensitivity_s)
    target_keys = sorted(k for k in base if k[0] == s.target_club)
    league_keys = sorted(k for k in base if base_nd.set_index(["club", "position_group"]).loc[k, "priority"]
                         in ("High", "Medium"))
    perf, *tables = inputs()
    variants = {}
    step = s.evaluation.perturbation
    for key in s.fit_weights:
        for sign in (1, -1):
            sv = sensitivity_s.model_copy(update={"fit_weights": evaluate.perturb(s.fit_weights, key, sign * step)})
            variants[f"fit.{key} {sign}"] = lambda sv=sv: evaluate.shortlist_sets(p25, base_nd, clubs, sv)
    for sign in (1, -1):
        sv = sensitivity_s.model_copy(update={"stat_weight_blend": s.stat_weight_blend + sign * step})
        variants[f"blend {sign}"] = lambda sv=sv: evaluate.shortlist_sets(
            p25, needs.compute_all_needs(p25, sv), clubs, sv)
        sv = sensitivity_s.model_copy(update={"league_strength_floor": s.league_strength_floor + sign * step})

        def floor_variant(sv=sv):
            new = add_definitions(season(perf, tables, sv, sv.analysis_season, sv.as_of_date))
            return evaluate.shortlist_sets(new, needs.compute_all_needs(new, sv), clubs, sv)

        variants[f"floor {sign}"] = floor_variant
    sensitivity = evaluate.sensitivity(base, variants, target_keys, league_keys)
    means = [v["league_high_medium"]["mean"] for v in sensitivity.values()
             if v["league_high_medium"]["mean"] is not None]
    result = {"variant": name, "calibration": calibration, "quality_ppg_rho": quality,
              "bias_top_clubs": leaders.to_dict(), "shortlist_size": len(sl),
              "bias_share": float(sl.current_club.isin(leaders.index).mean()) if len(sl) else None,
              "backtest": bt, "sensitivity": sensitivity, "mean_jaccard": float(np.mean(means)) if means else None,
              "west_ham": json.loads(nd[nd.club == s.target_club].to_json(orient="records"))}
    save(path, result)
    print(name, "saved", flush=True)
    return result


def run():
    subprocess.run(["git", "ls-files", "--error-unmatch", "docs/QUALITY_EXPERIMENT.md"], check=True,
                   capture_output=True)
    subprocess.run(["git", "diff", "--exit-code", "HEAD", "--", "docs/QUALITY_EXPERIMENT.md"], check=True)
    s = settings()
    registration = read(OUT / "registration.json")
    p24, p25 = [pd.read_parquet(WORK / (year + ".parquet")) for year in ("2024-25", "2025-26")]
    results = [evaluate_variant(v, p24, p25, registration[v], s) for v in ("V0", "V1")]
    rows = []
    for r in results:
        checks = {c["check"]: c["passed"] for c in r["calibration"]["checks"]}
        bt = r["backtest"]["league_pooled"]
        rows.append({"variant": r["variant"], **checks, "PPG rho": r["calibration"]["correlations"]["points_per_game"],
                     **{g + " quality rho": v for g, v in r["quality_ppg_rho"].items()},
                     "bias share": r["bias_share"], "uplift": bt["uplift"], "CI low": bt["ci_low"],
                     "CI high": bt["ci_high"], "mean Jaccard": r["mean_jaccard"]})
    rows.append({"variant": "V2", **{key: "Unavailable" for key in rows[0] if key != "variant"}})
    passing = [r["variant"] for r in results[1:] if all(c["passed"] for c in r["calibration"]["checks"])
               and r["bias_share"] is not None and r["bias_share"] <= results[0]["bias_share"]]
    decision = "Recommend " + passing[0] + "; wait for approval" if passing else "Keep V0; stop rule triggered"
    save(OUT / "summary.json", {"results": rows, "decision": decision, "V2_status": registration["V2_status"]})
    report = "# Quality experiment results\n\n" + md(pd.DataFrame(rows)) + "\n" + decision + "\n"
    for r in results:
        report += "\n## " + r["variant"] + " West Ham: all ambitions\n"
        report += md(pd.DataFrame(r["west_ham"])[["ambition", "position_group", "quality_gap", "need_score",
                                                  "priority", "rated_share", "evidence"]])
        report += "\nTop-value reference clubs:\n" + md(pd.DataFrame(
            [{"club": k, "value_m": v} for k, v in r["bias_top_clubs"].items()]))
    report += "\nV2 unavailable: Sofascore source failed. No substitute, extra variants or thresholds were tried. "
    report += "Production stays V0; no V1/V2 reports were generated. All results include selection/coverage changes.\n"
    (ROOT / "docs/QUALITY_EXPERIMENT_RESULTS.md").write_text(report, encoding="utf-8")
    print(md(pd.DataFrame(rows)), decision)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--evaluate", action="store_true")
    args = parser.parse_args()
    if args.prepare == args.evaluate:
        parser.error("Choose exactly one of --prepare or --evaluate")
    prepare() if args.prepare else run()
