"""Targets page: shortlist per ranked need group with the fit breakdown. Implements IMPLEMENTATION_GUIDE §9."""

import json

import streamlit as st

from scout import ui

c = ui.controls()
s = ui.current_settings()
nd = ui.club_needs(c["club"], c["ambition"]).set_index("position_group")
sl = ui.club_shortlist(c["club"], c["ambition"], c["budget_m"], c["age_min"], c["age_max"])
names = ui.league_names()

ui.page_header("Step 2 · Player targets", f"Who fits {c['club']}?",
               "Compare players for the positions this squad needs most. The fit score combines "
               "position-specific performance, age and market value within your chosen limits.")
st.caption(f"Your filters: market value up to €{c['budget_m']:.0f}m · ages {c['age_min']}–{c['age_max']} "
           f"· preferred ages {s.pool.ideal_age[0]}–{s.pool.ideal_age[1]}.")
skipped = nd[nd["used"] & (nd["evidence"] == "insufficient")]
if not skipped.empty:
    st.warning("Skipped for insufficient squad evidence: "
               + ", ".join(ui.position_label(group) for group in skipped.index))
st.caption(f"An upgrade must beat the current best rated regular by at least {s.upgrade_margin:g} "
           "percentile points on the same need-weighted performance score.")

if sl.empty:
    st.info("No verified upgrades meet this brief. A position needs sufficient evidence and a rated regular "
            "for comparison; candidate age, value and upgrade requirements must also pass.")
else:
    a, b, c_metric = st.columns(3)
    a.metric("Positions with a shortlist", sl["position_group"].nunique())
    b.metric("Players shown", len(sl))
    c_metric.metric("Search area", "10 leagues")
    st.info("A higher fit score means a closer match to this squad's measured gaps. Market value is an "
            "estimate, not a transfer-fee prediction. The recommendation labels follow fixed rules; "
            "the language model does not choose players.")
for group, rows in sl.groupby("position_group", sort=False):
    need = nd.loc[group]
    st.subheader(ui.position_label(group))
    st.caption(f"Squad need {need['need_score']:.1f} / 100 · {need['priority']} priority · "
               f"{len(rows)} targets within your filters")
    st.caption(f"Current best rated regular: {need['current_best_regular']} · "
               f"need-weighted composite {need['current_best_composite']:.1f} / 100")
    weights = json.loads(need["stat_weights"])
    view = rows.assign(league=rows["league"].map(names))
    top = view.iloc[0]
    with st.container(border=True):
        left, right = st.columns([3, 1])
        left.markdown(f"**Top fit: {top['player_name']}** · {top['team_name']} · {top['league']}")
        left.caption(f"Age {top['age']:.0f} · market value €{top['market_value_m']:.1f}m · "
                     f"{top['verdict'].capitalize()}")
        right.metric("Fit / 100", f"{top['fit']:.1f}")
        left.caption(f"Upgrade vs current: +{top['upgrade_vs_current']:.1f} percentile points")
        if top["below_ambition_benchmark"]:
            st.warning("This player improves the current squad but remains below the ambition benchmark "
                       "in one or more weighted statistics.")
    st.dataframe(view[["rank", "player_name", "team_name", "league", "age", "market_value_m", "fit", "verdict"]],
                 hide_index=True, width="stretch",
                 column_config={
                     "rank": "#", "player_name": "Player", "team_name": "Club", "league": "League", "age": "Age",
                     "market_value_m": st.column_config.NumberColumn("Market value (€m)", format="%.1f"),
                     "fit": st.column_config.ProgressColumn("Fit", min_value=0, max_value=100, format="%.1f"),
                     "verdict": st.column_config.TextColumn("Verdict",
                                                            help="A fixed label based on need priority and rank.")})
    with st.expander(f"How were {ui.position_label(group)} players ranked?"):
        st.write("Performance uses the statistics where this squad trails its ambition benchmark most. "
                 "Those statistics are adjusted for league strength; defensive volume stats are also "
                 "adjusted for team possession.")
        st.caption("Statistics and their share of the performance score: " +
                   ", ".join(f"{ui.stat_label(stat)} {weight:.0%}"
                             for stat, weight in sorted(weights.items(), key=lambda item: -item[1])))
        st.write("Overall fit = 60% performance + 20% age score + 20% market-value score. "
                 "A 'priority target' requires High squad need and a top-three rank; the other labels "
                 "describe shortlist position.")
        st.dataframe(view[["rank", "player_name", "sub_position", "minutes", "performance",
                           "current_best_composite", "upgrade_vs_current", "age_score", "value_score", "fit",
                           "below_ambition_benchmark"]],
                     hide_index=True, width="stretch", column_config={
                         "rank": "#", "player_name": "Player",
                         "performance": st.column_config.NumberColumn("Performance / 100", format="%.1f"),
                         "sub_position": "Sub-position", "minutes": "Minutes",
                         "current_best_composite": st.column_config.NumberColumn("Current best / 100", format="%.1f"),
                         "upgrade_vs_current": st.column_config.NumberColumn("Upgrade vs current", format="+%.1f"),
                         "below_ambition_benchmark": "Below ambition benchmark",
                         "age_score": st.column_config.NumberColumn("Age / 100", format="%.1f"),
                         "value_score": st.column_config.NumberColumn("Value / 100", format="%.1f"),
                         "fit": st.column_config.NumberColumn("Fit / 100", format="%.1f")})
