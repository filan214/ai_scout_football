"""Evaluation page: faithfulness, backtest, sensitivity, league strength vs UEFA.

All numbers are read from data/processed/eval/*.json (written by `python pipeline.py --stage eval`).
"""

import pandas as pd
import streamlit as st

from scout import ui

ui.page_header("Step 4 · Evaluation", "How well does AI Scout hold up?",
               "The checks below test whether reports match their facts, whether past picks performed well "
               "a season later, and how sensitive the results are to the scoring settings.")
st.caption("These are saved historical evaluation results; each table identifies its club and season. "
           "Changing the sidebar "
           "updates live needs and targets, but does not rerun this backtest.")

faith = ui.eval_json("faithfulness")
bt = ui.eval_json("backtest")
if faith and bt:
    model, naive = bt["league_pooled"], bt["naive_baseline"]["league_pooled"]
    a, b, c = st.columns(3)
    a.metric("Scouting reports checked", faith["reports"],
             help=f"Cached reports for {faith['club']}.")
    b.metric("Model vs eligible players", f"{100 * model['uplift']:+.1f}%",
             help="Next-season median performance compared with the eligible-player median, across 20 clubs.")
    c.metric("Simple baseline vs eligible players", f"{100 * naive['uplift']:+.1f}%",
             help="A picker using last season's performance only.")
    comparison = ("The simple baseline performed better on next-season output."
                  if model["median_outcome_season_n1"] < naive["median_outcome_season_n1"]
                  else "The model matched or exceeded the simple baseline on next-season output.")
    st.info(comparison + f" Median market values: model €{model['median_market_value_m']:.0f}m; "
            f"baseline €{naive['median_market_value_m']:.0f}m. One season pair cannot establish future results.")

st.header("1. Can we trust the report numbers?")
access = ui.eval_json("fallback_probe")
if access:
    st.caption(f"Latest report API access check: HTTP {access.get('http_status', 'not tested')} · "
               f"{access.get('status', 'unknown')} · {access.get('model', '')}. "
               "Access success and report verification are separate checks.")
if faith:
    if faith.get("status", "ok") != "ok":
        st.warning(f"Report verification is {faith['status']}: {faith['reports']}/"
                   f"{faith.get('expected_reports', 0)} current reports generated. "
                   + (faith.get("error") or ""))
    a, b, c = st.columns(3)
    a.metric("Numbers matching the facts", f"{faith['verified']}/{faith['numbers']}")
    b.metric("Reports passing all checks", f"{faith['fully_verified_reports']}/{faith['reports']}")
    c.metric("Reports reviewed", faith["reports"])
    st.caption("The automatic check compares every report number with its fact sheet and checks all cited "
               "fact keys. It cannot assess every football judgment in the prose.")
    with st.expander("See the verification method and model details"):
        st.write(f"{faith['club']} shortlist · prompt {faith['prompt_version']} · {faith['model']} · "
                 f"{faith.get('tokens', {}).get('total', 'n/a')} tokens for all reports.")
        st.write("Integers must match exactly; decimals may differ by max(0.05, 2%).")

st.header("2. Did past picks perform well a season later?")
if bt:
    st.write(f"We built shortlists using {bt['season_n']} data, then measured those players in "
             f"{bt['season_n1']}. **Uplift** compares their median score with the median eligible player. "
             "A positive result means the picks did better than that comparison group.")
    st.caption("The 95% interval shows uncertainty in the measured uplift. Picks without enough "
               "next-season minutes count toward attrition, not the scored-pick median.")

    def row(label: str, r: dict) -> dict:
        pct100 = {k: None if r.get(src) is None else 100 * r[src] for k, src in
                  (("uplift", "uplift"), ("CI low", "ci_low"), ("CI high", "ci_high"), ("hit rate", "hit_rate"),
                   ("attrition", "attrition"))}
        return {"Pick set": label, **pct100, "Picks scored": f"{r['picks_scored']}/{r['picks']}"}

    rows = [row(f"{bt['club']} {g} ({r['priority']} need)", r) for g, r in bt["groups"].items()]
    rows += [row(f"{bt['club']} overall", bt["overall"]),
             row(f"All {bt['league_pooled']['clubs']} PL clubs pooled", bt["league_pooled"]),
             row("Naive: last-season performance only (pooled)", bt["naive_baseline"]["league_pooled"])]
    pct = st.column_config.NumberColumn(format="%.1f%%")
    with st.expander("Compare all backtest results and uncertainty ranges"):
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                     column_config={k: pct for k in ("uplift", "CI low", "CI high", "hit rate", "attrition")})
        st.caption("Hit rate is the share of scored picks above the eligible-player median; attrition is "
                   "the share without enough next-season minutes.")
    model, naive = bt["league_pooled"], bt["naive_baseline"]["league_pooled"]
    st.markdown(f"**What this tells us:** across 20 clubs, the model's next-season median score was "
                f"{model['median_outcome_season_n1']:.1f}, compared with "
                f"{naive['median_outcome_season_n1']:.1f} for a simple performance-only picker. "
                f"The model's picks had a lower median market value (€{model['median_market_value_m']:.1f}m "
                f"versus €{naive['median_market_value_m']:.1f}m), with the same median age "
                f"({model['median_age']:.0f}).")
    image = ui.image_path("backtest.png")
    if image:
        with st.expander("See the backtest chart"):
            st.image(image, width="stretch")

sens = ui.eval_json("sensitivity")
st.header("3. Do small scoring changes reshuffle the shortlist?")
if sens:
    st.write("We changed one scoring weight at a time and compared the resulting top-ten lists. "
             "An overlap of 1.00 means the list stayed the same; 0.00 means it did not overlap at all.")
    st.caption(f"Each weight moved by ±{sens['perturbation']}. A position that drops out counts as zero "
               "overlap and is also listed as dropped.")
    table = pd.DataFrame([
        {"variant": name, "target mean": v["target_club"]["mean"], "target min": v["target_club"]["min"],
         "target groups dropped": v["target_club"]["groups_dropped"],
         "league High/Medium mean": v["league_high_medium"]["mean"],
         "league High/Medium min": v["league_high_medium"]["min"]}
        for name, v in sens["variants"].items()])
    with st.expander("See the detailed ranking-stability results"):
        st.dataframe(table, hide_index=True, width="stretch",
                     column_config={k: st.column_config.NumberColumn(format="%.2f")
                                    for k in ("target mean", "target min", "league High/Medium mean",
                                              "league High/Medium min")})
        st.caption("Target = the saved evaluation brief; league High/Medium = those priority groups "
                   "across the 20 Premier League clubs.")

val = ui.eval_json("league_strength_validation")
st.header("4. Does the league adjustment reflect wider results?")
if val and val.get("status") == "ok":
    five, one = val["five_season"], val["single_season"]
    st.write("The league-strength adjustment comes from squad market values. We compared it with UEFA "
             "country coefficients, an independent measure based on clubs' European results. A value "
             "closer to 1 indicates a stronger relationship.")
    a, b, c, d = st.columns(4)
    a.metric("Value relationship · 5 seasons", f"{five['pearson']:.2f}",
             help="Pearson correlation across nine league countries.")
    b.metric("Rank relationship · 5 seasons", f"{five['spearman']:.2f}",
             help="Spearman correlation across nine league countries.")
    c.metric("Value relationship · last season", f"{one['pearson']:.2f}")
    d.metric("Rank relationship · last season", f"{one['spearman']:.2f}")
    st.caption(f"{five['n']} leagues have a UEFA coefficient; the Championship does not. This checks the "
               "league adjustment broadly, not the quality of an individual player recommendation.")
    image = ui.image_path("league_strength_uefa.png")
    if image:
        st.image(image, width="stretch")
    names = ui.league_names()
    with st.expander("See the league-by-league values"):
        st.dataframe(pd.DataFrame(five["table"]).assign(league=lambda d: d["league"].map(names)),
                     hide_index=True, width="stretch")
elif val:
    st.warning(f"UEFA coefficients were unavailable at the last run: {val.get('error', '')}")

st.header("5. Need calibration")
calibration = ui.eval_json("need_calibration")
if calibration:
    st.write(calibration["definition"])
    st.caption("Fixed acceptance checks across all 20 Premier League clubs. Independent strength uses "
               "2025–26 points per game and goal difference from local match results. Market value is secondary.")
    checks = pd.DataFrame(calibration["checks"])
    checks["Result"] = checks["passed"].map({True: "PASS", False: "FAIL"})
    st.dataframe(checks[["check", "name", "Result", "observed", "requirement"]],
                 hide_index=True, width="stretch")
    if calibration["status"] != "passed":
        st.warning("This model has not passed every need-calibration acceptance check. "
                   "Parameters were not changed after seeing these results.")
    corr = calibration["correlations"]
    st.write(f"Spearman vs points per game: **{corr['points_per_game']:.3f}**; "
             f"goal difference: **{corr['goal_difference']:.3f}**; "
             f"market value (non-independent): **{corr['market_value_secondary']:.3f}**.")
    with st.expander("See all clubs and remaining evidence gaps"):
        st.dataframe(pd.DataFrame(calibration["clubs"]), hide_index=True, width="stretch")
        st.dataframe(pd.DataFrame(calibration["insufficient_cells"]), hide_index=True, width="stretch")
    elo = calibration.get("clubelo", {"status": "unavailable"})
    st.caption(f"ClubElo: {elo['status']}. Independent need calibration uses league results. "
               + elo.get("error", ""))

experiment = ui.eval_json("quality_experiment/summary")
if experiment:
    with st.expander("Quality-stat experiment: frozen selection and stop-rule result"):
        st.write(experiment["decision"])
        st.caption("Stat sets were selected by repeatability and possession correlation, without match-result "
                   "labels. V2 is unavailable because Sofascore ratings could not be accessed. "
                   "The current model remains V0.")
        results = pd.DataFrame(experiment["results"])
        view = results.astype(str)
        st.dataframe(view, hide_index=True, width="stretch")
