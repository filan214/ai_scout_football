"""Write the fixed-parameter before/after audit; baseline snapshots stay in ignored interim storage."""

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scout import clean, needs, rank  # noqa: E402
from scout.config import load_settings  # noqa: E402


def table(frame):
    def cell(value):
        if value is None:
            return "N/A"
        if isinstance(value, float):
            return "N/A" if pd.isna(value) else f"{value:.3f}"
        return str(value).replace("|", "/").replace("\n", " ")
    return ("\n| " + " | ".join(frame.columns) + " |\n| " + " | ".join(["---"] * len(frame.columns))
            + " |\n" + "\n".join("| " + " | ".join(cell(v) for v in row) + " |"
                                  for row in frame.itertuples(index=False, name=None)) + "\n")


def main():
    before_dir = ROOT / "data/interim/needs_update_before"
    processed = ROOT / "data/processed"
    read = lambda path: json.loads(path.read_text(encoding="utf-8"))  # noqa: E731
    s = load_settings().model_copy(update={
        "position_stats": read(processed / "coverage.json")["position_stats"],
        "target_club": "West Ham United", "ambition": "title"})
    ps = pd.read_parquet(processed / "player_season.parquet")
    old_ps = pd.read_parquet(before_dir / "data/processed/player_season.parquet")
    pd.testing.assert_frame_equal(old_ps, ps[old_ps.columns], check_exact=True)
    before = pd.read_parquet(before_dir / "all_ambitions.parquet")
    evidence = pd.read_parquet(before_dir / "evidence_only.parquet")
    calibration = read(processed / "eval/need_calibration.json")
    after = pd.DataFrame(calibration["needs"])
    profiles = pd.read_parquet(processed / "squad_profiles.parquet")
    wh = after[after.club == s.target_club]
    shortlist = rank.rank_targets(ps, wh[wh.ambition == "title"], s)
    shortlist.to_parquet(processed / "shortlist_west_ham.parquet", index=False)
    assert len(shortlist) == 20
    assert (shortlist.upgrade_vs_current >= s.upgrade_margin).all()
    assert (shortlist.sub_position.map(clean.position_group) == shortlist.position_group).all()
    bt_old = read(before_dir / "data/processed/eval/backtest.json")
    bt_new = read(processed / "eval/backtest.json")
    sens_old = read(before_dir / "data/processed/eval/sensitivity.json")
    sens_new = read(processed / "eval/sensitivity.json")
    faith_old = read(before_dir / "data/processed/eval/faithfulness.json")
    faith_new = read(processed / "eval/faithfulness.json")
    out = ["# Needs implementation and acceptance audit",
           "Run: 2026-10-30. Season 2025-26; snapshot 2026-07-06. Defaults remain Arsenal/top4. "
           "West Ham/title is the case-study override. See NEEDS_DIAGNOSIS.md for the historical diagnosis.",
           needs.NEED_DEFINITION,
           "## Acceptance: all 20 clubs",
           table(pd.DataFrame(calibration["checks"])),
           "Check b fails. Parameters, bands and weights were not tuned after seeing results. No commit was made. "
           "All 20 clubs have 38 completed games in the local results (380 games / 760 club-game rows). "
           "Points are 3/1/0 from results; administrative deductions are outside this measure.",
           table(pd.DataFrame([calibration["correlations"]])),
           table(pd.DataFrame(calibration["strongest_clubs"])),
           table(pd.DataFrame(calibration["insufficient_cells"])),
           "Options for a later, separately approved experiment: (1) compare alternative squad-quality summaries "
           "and coherent club benchmarks against independent results across multiple held-out seasons; "
           "(2) audit position/stat validity and current-club availability before adding any new signal. "
           "Neither option is implemented. A small 20-club correlation is not an objective to optimize in-sample.",
           "## Part 1: evidence before the formula",
           "Rows combine each player's analysis-season adjusted per-90 values using available-stat minutes. "
           "Qualified profiles retain their existing pool percentiles exactly; a non-pool profile needs 600 combined "
           "minutes for empirical placement on that same fixed pool. Exact ties use average rank; between observations "
           "use the fraction below; missing stats remain missing. "
           "A partial placement is flagged but is not fully rated. "
           "Rated share counts combined minutes of profiles with all required role percentiles.",
           "The matches rule remains at 50%: 183 rows pass minutes but fail matches (20 PL rows); "
           "none has all required role stats. Relaxing it would admit missing-stat candidates "
           "and change the fixed pool. "
           "There is no explicit loan-status field in local players/transfers tables. Current-club selection remains; "
           "other-club minutes are flagged without inferring current loan status."]
    shares = []
    for r in wh[wh.ambition == "title"].itertuples():
        old = old_ps[(old_ps.current_club == s.target_club) & (old_ps.position_group == r.position_group)]
        shares.append({"position": r.position_group, "before rated %": 100 * old.loc[old.qualifies, "minutes"].sum()
                       / old.minutes.sum(), "after rated %": 100 * r.rated_share, "evidence": r.evidence})
    out += [table(pd.DataFrame(shares)), "Used cells: 132/135 sufficient; three insufficient. "
            "Those positions keep provisional scores, get grey badges and are excluded from ranking. "
            "Median-club substitution is retained only with an explicit insufficient flag."]
    for ambition in ("survive", "midtable", "top4", "title"):
        frame = wh[wh.ambition == ambition]
        out += ["## West Ham: " + ambition]
        old = before[(before.club == s.target_club) & (before.ambition == ambition)]
        ev = evidence[(evidence.club == s.target_club) & (evidence.ambition == ambition)]
        comparison = frame[["position_group", "depth_gap", "quality_gap", "age_risk", "contract_risk",
                            "need_score", "priority", "rated_share", "evidence"]].copy()
        comparison["before need"] = comparison.position_group.map(old.set_index("position_group").need_score)
        comparison["evidence-only old formula"] = comparison.position_group.map(
            ev.set_index("position_group").need_score)
        out += [table(comparison)]
    stat_rows = []
    for r in wh.itertuples():
        observed, used, benchmark = map(json.loads, (r.squad_pct, r.squad_pct_used, r.benchmark))
        for stat in benchmark:
            stat_rows.append({"ambition": r.ambition, "position": r.position_group, "stat": stat,
                              "observed squad pct": observed[stat], "score input pct": used[stat],
                              "benchmark pct": benchmark[stat]})
    out += ["## Corrected West Ham per-stat diagnosis", table(pd.DataFrame(stat_rows)),
            "## Combined player evidence", "Regular proxy means 900 combined minutes; actual starting-XI data "
            "is not used. All profile percentiles below use the single fixed pool."]
    squad = profiles[(profiles.current_club == s.target_club) & profiles.position_group.notna()]
    for group, rows in squad.groupby("position_group"):
        cols = ["player_name", "sub_position", "minutes", "fully_rated", "rated_by_placement",
                "other_club_minutes"] + [stat + "_pct" for stat in s.position_stats[group]]
        out += ["### " + group, table(rows[cols])]
    band_rows = []
    for name, df in [("Before", before), ("After", after)]:
        for ambition in ("title", "survive"):
            rows = df[df.ambition == ambition]
            band_rows.append({"version": name, "ambition": ambition,
                              **{p: int((rows.priority == p).sum()) for p in ("High", "Medium", "Low")},
                              "used cells": int(rows.used.sum())})
    out += ["## League-wide bands", table(pd.DataFrame(band_rows)),
            "Counts include provisional numeric bands for insufficient cells; the app replaces those labels "
            "with the evidence badge. Acceptance c uses all used cells as specified.",
            "## West Ham title targets: DM and FB",
            "Every row below passed the source sub-position → position-group check and the upgrade margin. "
            "Minutes are the qualifying candidate league row, not a fabricated combined candidate season. "
            "A benchmark warning means at least one weighted statistic is below its ambition target.",
            table(shortlist[["position_group", "rank", "player_name", "sub_position", "minutes", "performance",
                             "age_score", "value_score", "fit", "current_best_regular", "current_best_composite",
                             "upgrade_vs_current", "below_ambition_benchmark"]])]
    metrics = []
    for name, bt, sens, faith in [("Before", bt_old, sens_old, faith_old), ("After", bt_new, sens_new, faith_new)]:
        pooled = bt["league_pooled"]
        means = [v["league_high_medium"]["mean"] for v in sens["variants"].values()]
        metrics.append({"version": name, "backtest uplift %": 100 * pooled["uplift"],
                        "CI low %": 100 * pooled["ci_low"], "CI high %": 100 * pooled["ci_high"],
                        "picks scored": f"{pooled['picks_scored']}/{pooled['picks']}",
                        "mean Jaccard (10 variants)": sum(means) / len(means),
                        "faithfulness %": None if faith["verified_rate"] is None else 100 * faith["verified_rate"]})
    sensitivity = pd.DataFrame([{"variant": k,
                                 "before league mean": sens_old["variants"][k]["league_high_medium"]["mean"],
                                 "after league mean": v["league_high_medium"]["mean"]}
                                for k, v in sens_new["variants"].items()])
    out += ["## Evaluation before/after", table(pd.DataFrame(metrics)), table(sensitivity),
            "Backtest groups changed 40 → 48 and picks 400 → 439; sensitivity High/Medium groups also changed. "
            "These are pipeline-level comparisons, not paired estimates on an identical selection population. "
            "Backtest contract urgency is zero without redistributing it; the other secondary coefficients stay fixed. "
            "Historical squad identity uses the season team; for a player with several teams the largest-minute "
            "row supplies roster metadata. Position labels remain the snapshot labels (known leakage).",
            "Improvements: pooled uplift 50.90% → 51.74%; outcome median 78.71 → 79.45. "
            "The naive baseline still wins: 53.02% uplift versus 51.74%. "
            "Worse: floor −0.1 Jaccard 0.843 → 0.656; age −0.1 and blend −0.1 also decreased. "
            "Model median value rose €15m → €18m. New report faithfulness is unavailable, not verified at 100%.",
            "League-strength validation reran: five-season UEFA Pearson 0.9326 / Spearman 0.8667 (9 leagues). "
            "ClubElo's single eval retry returned HTTP 502; its correlation is null.",
            "## Reports and two review examples",
            "PROMPT_VERSION is v2 for the new evidence/upgrade contract (the earlier contract was named v4). "
            "All 20 fact sheets are saved in data/processed/report_fact_sheets.json. "
            "ZenMux returned HTTP 402 reject_no_credit on 2026-10-29. Thus 0/20 new reports exist and the ≥95% "
            "faithfulness requirement is unresolved. Historical cached reports are preserved but are not counted as "
            "verification of the new contract. The two examples below are prepared fact sheets, not generated reports."]
    sheets = read(processed / "report_fact_sheets.json")["sheets"]
    for group in ("DM", "FB"):
        sheet = next(x for x in sheets if x["player.position"] == group)
        out += ["### " + sheet["player.name"], "```json\n" + json.dumps(sheet, indent=2, ensure_ascii=False) + "\n```"]
    out += ["## Verification and resumption",
            "Original player_season columns compare exactly, including every qualifying flag and percentile. "
            "Only sub_position was added. Streamlit AppTest rendered all five pages for West Ham/title "
            "with and without report access (10 page checks, zero exceptions). "
            "Final pytest/Ruff output is recorded in HANDOFF.md. No commit: calibration b fails and live reports "
            "remain blocked. No thresholds were adjusted.",
            "After gateway access is enabled: run "
            "`python pipeline.py --stage reports --club 'West Ham United' --ambition title`, "
            "then rerun this audit. The requested two real report examples and faithfulness gate remain pending."]
    (ROOT / "docs/NEEDS_IMPLEMENTATION.md").write_text("\n\n".join(out), encoding="utf-8")
    (processed / "eval/needs_update_comparison.json").write_text(json.dumps({
        "metrics": metrics, "bands": band_rows, "evidence_shares": shares,
        "sensitivity": sensitivity.to_dict(orient="records"), "acceptance": calibration["checks"],
        "reports_status": faith_new.get("status"), "committed": False}, indent=2), encoding="utf-8")
    print(table(pd.DataFrame(calibration["checks"])))
    print(table(pd.DataFrame(metrics)))
    print(table(shortlist[["position_group", "rank", "player_name", "sub_position", "minutes",
                           "performance", "age_score", "value_score", "fit", "upgrade_vs_current"]]))


if __name__ == "__main__":
    main()
