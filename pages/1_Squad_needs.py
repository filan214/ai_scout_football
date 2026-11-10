"""Squad needs page: need score per position group and its components."""

import json

import altair as alt
import pandas as pd
import streamlit as st

from scout import needs, ui

c = ui.controls()
s = ui.current_settings()
nd = ui.club_needs(c["club"], c["ambition"]).copy()
nd["display_priority"] = [ui.need_label(r.evidence, r.priority) for r in nd.itertuples()]

ui.page_header("Step 1 · Squad needs", f"Where does {c['club']} need help?",
               needs.NEED_DEFINITION)
k = s.ambition_club_rank[c["ambition"]]
ordinal = "best" if k == 1 else f"{ui.ordinal(k)}-best"
st.caption(f"Benchmark for {ui.AMBITION_LABELS[c['ambition']].lower()}: the {ordinal} Premier League "
           "squad, compared separately for each statistic.")

standing = ui.club_standing(c["club"])
if standing is not None:
    st.subheader(f"Where {c['club']} stands now")
    played = int(standing["played"])
    pos, pts, mp, xg = st.columns(4)
    pos.metric("League position", ui.ordinal(int(standing["position"])))
    pts.metric("Points", int(standing["points"]),
               help=f"{int(standing['wins'])} wins, {int(standing['draws'])} draws, {int(standing['losses'])} losses")
    mp.metric("Matches played", played)
    if pd.notna(standing["xg"]) and played:
        per_match = f"{standing['xg'] / played:.2f} / {standing['xg_conceded'] / played:.2f}"
        xg.metric("xG for / against per match", per_match, help="Expected goals created and conceded (FotMob).")
    suggested = ui.suggested_ambition(c["club"])
    note = ("The table is context only. It suggests the sidebar ambition but does not change the need score, which "
            "compares squad quality with the benchmark.")
    if suggested is not None and suggested != c["ambition"]:
        st.info(f"The current table suggests **{ui.AMBITION_LABELS[suggested].lower()}**; this brief uses "
                f"**{ui.AMBITION_LABELS[c['ambition']].lower()}**. {note}")
    else:
        st.caption(note)
    with st.expander("Full Premier League table"):
        table = ui.standings()
        shown = pd.DataFrame({
            "Pos": table["position"].astype(int), "Club": table["club"], "P": table["played"].astype(int),
            "W": table["wins"].astype(int), "D": table["draws"].astype(int), "L": table["losses"].astype(int),
            "GF": table["goals_for"], "GA": table["goals_against"], "Pts": table["points"].astype(int),
            "xG": table["xg"].round(1), "xGA": table["xg_conceded"].round(1),
        })
        st.dataframe(shown.style.apply(lambda r: ["font-weight: 700" if r["Club"] == c["club"] else ""] * len(r),
                                       axis=1),
                     hide_index=True, width="stretch")

used = nd[nd["used"]].sort_values("need_score", ascending=False)
unused = nd[~nd["used"]]
if not used.empty:
    top = used.iloc[0]
    a, b, c_metric = st.columns(3)
    a.metric("Biggest squad need", top["position_group"])
    a.caption(ui.POSITION_NAMES[top["position_group"]])
    b.metric("Need score", f"{top['need_score']:.1f} / 100", help="Higher means a larger squad gap.")
    with c_metric:
        st.caption("Evidence and priority")
        ui.evidence_badge(top["evidence"], top["priority"])
    if (used["display_priority"] == "Low").all():
        st.info("Every position is currently Low priority. The target list still shows the two highest-need "
                "positions so you can explore options; Low does not mean a signing is required.")

st.subheader("Need by position")
st.caption("The scale always runs from 0 to 100. Higher bars mean greater need, not better players.")
chart_data = used.assign(display_group=used["position_group"].map(ui.position_label),
                         label=used["need_score"].map(lambda value: f"{value:.1f} / 100"))
base = alt.Chart(chart_data).encode(
    x=alt.X("need_score:Q", title="Need score (0-100)", scale=alt.Scale(domain=[0, 100]),
            axis=alt.Axis(values=list(range(0, 101, 20)))),
    y=alt.Y("display_group:N", sort=chart_data["display_group"].tolist(), title=None,
            axis=alt.Axis(labelLimit=220)),
)
bars = base.mark_bar(cornerRadiusEnd=4, height=22).encode(
    color=alt.Color("display_priority:N", title="Evidence / priority", scale=alt.Scale(domain=list(ui.PRIORITY_COLORS),
                                                                    range=list(ui.PRIORITY_COLORS.values()))),
    tooltip=[alt.Tooltip("display_group:N", title="Position"),
             alt.Tooltip("need_score:Q", title="Need score", format=".1f"), "display_priority:N",
             alt.Tooltip("rated_share:Q", title="Rated-minute share", format=".1%"),
             alt.Tooltip("depth_gap:Q", title="Depth gap", format=".1f"),
             alt.Tooltip("quality_gap:Q", title="Quality gap", format=".1f"),
             alt.Tooltip("age_risk:Q", title="Age risk", format=".1f"),
             alt.Tooltip("contract_risk:Q", title="Contract risk", format=".1f")],
)
label_color = {"dark": "#c3c2b7", "light": "#52514e"}.get(st.context.theme.type, "#8f8e88")
labels = base.mark_text(align="left", dx=6, color=label_color).encode(text="label:N")
st.altair_chart((bars + labels).properties(height=36 * len(used) + 40), width="stretch")

st.subheader("Why each position scored this way")
st.caption("Quality is the primary shortfall. Depth, age and contract urgency add to the remaining range. "
           "Grey positions keep a provisional score but are excluded from target ranking.")
progress = {k: st.column_config.ProgressColumn(k.replace("_", " ").capitalize(), min_value=0, max_value=100,
                                               format="%.1f")
            for k in ("depth_gap", "quality_gap", "age_risk", "contract_risk")}
table = used.assign(position_group=used["position_group"].map(ui.position_label),
                    rated_percent=100 * used["rated_share"])[[
              "position_group", "need_score", "display_priority", "rated_percent",
              "depth_gap", "quality_gap", "age_risk", "contract_risk"]]
st.dataframe(table, hide_index=True, width="stretch", column_config={
    "position_group": "Position", "need_score": st.column_config.NumberColumn("Need / 100", format="%.1f"),
    "display_priority": "Evidence / priority",
    "rated_percent": st.column_config.NumberColumn("Rated minutes (%)", format="%.1f%%"), **progress})
if not unused.empty:
    st.caption("Not scored because this club rarely uses the position: "
               + ", ".join(unused["position_group"].map(ui.position_label)))

with st.expander("How is the need score calculated?"):
    st.markdown("""- **Depth gap:** Does the club have enough players with substantial minutes in this position?
- **Quality gap:** How far does the squad trail the ambition benchmark across the position's statistics?
- **Age risk:** What share of minutes comes from players aged 30 or older?
- **Contract risk:** What share comes from players with 12 months or less on their contract?

The score is **Q + (1 − Q/100) × (0.20D + 0.15A + 0.15C)**. High starts at 60,
Medium at 35. These are recruitment prompts, not predictions of results.""")
    st.write(f"Evidence is insufficient below {s.min_rated_share:.0%} rated minutes. A rated profile has all "
             f"required role percentiles. Non-pool players need {s.squad_rating_min_minutes} combined minutes "
             "for placement on the same pool; missing stats stay missing.")

with st.expander("See squad-depth counts"):
    st.caption("A regular counts in proportion to minutes played, up to one full regular at 900 minutes.")
    st.dataframe(used.assign(position_group=used["position_group"].map(ui.position_label))[[
                     "position_group", "squad_players", "reliable", "regulars"]],
                 hide_index=True, width="stretch", column_config={
                     "position_group": "Position", "squad_players": "Players",
                     "reliable": "Players with 900+ minutes",
                     "regulars": st.column_config.NumberColumn("Equivalent regulars", format="%.1f")})

with st.expander("See the detailed statistics behind each position"):
    for r in used.itertuples():
        squad, bench = json.loads(r.squad_pct), json.loads(r.benchmark)
        st.markdown(f"**{ui.position_label(r.position_group)}**")
        ui.evidence_badge(r.evidence, r.priority)
        st.caption(f"Rated minutes: {r.rated_minutes:,.0f} / {r.minutes:,.0f} ({r.rated_share:.1%})")
        imputed = json.loads(r.imputed_stats)
        if imputed:
            st.warning("Provisional score uses median-club values for missing statistics: "
                       + ", ".join(ui.stat_label(stat) for stat in imputed))
        effective = json.loads(r.squad_pct_used)
        st.dataframe(pd.DataFrame({"Statistic": [ui.stat_label(stat) for stat in bench],
                                   "Squad percentile": [squad[stat] for stat in bench],
                                   "Value used in score": [effective[stat] for stat in bench],
                                   "Benchmark percentile": list(bench.values()),
                                   "Weight in ranking": [json.loads(r.stat_weights)[stat] for stat in bench]}).round(2),
                     hide_index=True, width="stretch")
    st.caption("A percentile compares players in the same position across the candidate pool. "
               "A larger ranking weight means the club has a larger gap in that statistic.")

with st.expander("See the squad players behind these scores"):
    ps = ui.squad_profiles()
    squad = ps[(ps["current_club"] == c["club"]) & ps["position_group"].notna()]
    st.dataframe(squad[["player_name", "position_group", "team_name", "minutes", "age", "contract_months_left",
                        "market_value_m", "sub_position", "rated_by_placement", "fully_rated",
                        "other_club_minutes", "other_club_flag", "loan_status"]]
                 .sort_values(["position_group", "minutes"], ascending=[True, False])
                 .assign(position_group=lambda frame: frame["position_group"].map(ui.position_label)),
                 hide_index=True, width="stretch", column_config={
                     "player_name": "Player", "position_group": "Position", "team_name": "2025–26 team",
                     "minutes": "Combined minutes", "age": "Age",
                     "sub_position": "Sub-position", "rated_by_placement": "Placed on existing pool",
                     "fully_rated": "All role stats rated", "other_club_minutes": "Other-club minutes",
                     "other_club_flag": "Away / other-club minutes", "loan_status": "Loan status",
                     "contract_months_left": "Contract months left",
                     "market_value_m": st.column_config.NumberColumn("Market value (€m)", format="%.1f")})
    st.caption("Analysis-season rows are combined per player. Other-club minutes are historical provenance, "
               "not proof of a current loan. The local dataset has no explicit loan-status field.")
