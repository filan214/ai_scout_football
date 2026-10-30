"""Scouting report page: cached LLM report with fact-key chips and a faithfulness badge. Implements
IMPLEMENTATION_GUIDE §9. Reports are generated only on request and only when the API key is set."""

import json

import streamlit as st

from scout import llm, report, ui
from scout.config import REPORTS_DIR

c = ui.controls()
s = ui.current_settings()
sl = ui.club_shortlist(c["club"], c["ambition"], c["budget_m"], c["age_min"], c["age_max"])
nd = ui.club_needs(c["club"], c["ambition"]).set_index("position_group")
ps = ui.player_season()

ui.page_header("Step 3 · Scouting report", "The case for each player",
               "Read the written assessment, then open its evidence to see which recorded facts support each point. "
               "The report explains a shortlist chosen by the scoring model.")
if sl.empty:
    st.info("No shortlisted players meet this brief. Adjust the market-value or age limits in the sidebar.")
    st.stop()

col_group, col_player = st.columns([1, 3])
group = col_group.selectbox("Position", list(dict.fromkeys(sl["position_group"])),
                            format_func=ui.position_label)
rows = sl[sl["position_group"] == group].reset_index(drop=True)
pick = col_player.selectbox("Shortlisted player", rows.index,
                            format_func=lambda i: f"#{rows.loc[i, 'rank']} {rows.loc[i, 'player_name']} "
                                                  f"({rows.loc[i, 'team_name']})")
target = rows.loc[pick]
player = ps[(ps["fotmob_id"] == target["fotmob_id"]) & (ps["league"] == target["league"])].iloc[0]
fact_sheet = report.build_fact_sheet(player, target, nd.loc[group], s, ui.league_names()[target["league"]])
path = REPORTS_DIR / f"{report.cache_key(fact_sheet, s.llm.primary_model)}.json"
record = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

st.subheader(target["player_name"])
st.caption(f"{ui.position_label(group)} · {target['team_name']} · "
           f"{ui.league_names()[target['league']]} · shortlist rank #{target['rank']}")
a, b, c_metric = st.columns(3)
a.metric("Fit score", f"{target['fit']:.1f} / 100")
b.metric("Market value", f"€{target['market_value_m']:.1f}m", help="An estimate, not a transfer fee.")
c_metric.metric("Minutes played", f"{target['minutes']:,.0f}",
                help="2025–26 league minutes; lower minutes mean a smaller evidence sample.")
st.caption(f"Recommendation label: {target['verdict'].capitalize()} — calculated from need priority and "
           "shortlist rank.")

if record is None:
    if ui.api_key_available():
        st.info("This player has no report for the current brief yet.")
        if st.button("Generate a scouting report", type="primary"):
            try:
                with st.spinner("Writing and verifying the report…"):
                    record, _ = report.generate_report(fact_sheet, s, llm.make_completer(s, report.ScoutingReport),
                                                       REPORTS_DIR)
            except Exception as exc:
                st.error(llm.report_error_message(exc))
    else:
        st.warning("This player has no cached report for the current brief. Creating a new one requires an "
                   "API key and an accessible gateway account. You can still inspect the facts below.")


def evidence(keys: list[str]) -> None:
    """Display the facts cited by one report statement."""
    with st.expander("See the facts behind this statement"):
        for key in keys:
            value = fact_sheet.get(key, "Missing from the fact sheet")
            st.markdown(f"**{ui.fact_label(key)}:** {value}")
            st.caption(f"Source key: {key}")


if record:
    check, rep = record["faithfulness"], record["report"]
    if record["flagged"]:
        st.warning(f"Verification needs review: {check['verified']}/{check['numbers']} report numbers "
                   "matched the fact sheet. Open the details below.")
    else:
        st.success(f"Fact check passed: all {check['numbers']} numbers matched the fact sheet.")
    st.caption("This automated check tests numbers and cited fact keys. It does not prove that every written "
               "judgment is correct.")
    st.subheader("At a glance")
    st.write(rep["summary"])
    st.subheader("What stands out")
    for claim in rep["strengths"]:
        with st.container(border=True):
            st.write(claim["text"])
            evidence(claim["fact_keys"])
    st.subheader("What to check further")
    for claim in rep["risks"]:
        with st.container(border=True):
            st.write(claim["text"])
            evidence(claim["fact_keys"])
    usage = record.get("usage", {})
    with st.expander("Report generation and verification details"):
        st.write(f"Model: {record['model_used']} · prompt version: {record['prompt_version']} · "
                 f"attempts: {record['attempts']} · tokens: {usage.get('total', 'n/a')} · "
                 f"generated: {record['generated_at']}")
        if record["flagged"]:
            st.write(f"Unverified numbers: {check['unverified']}")
            st.write(f"Missing fact keys: {check['missing_fact_keys']}")

with st.expander("Explore the full fact sheet"):
    st.caption("These are the recorded values sent to the report writer. Source keys let you trace each claim.")
    st.dataframe([{"Fact": ui.fact_label(key), "Value": str(value), "Source key": key}
                  for key, value in fact_sheet.items()], hide_index=True, width="stretch")
