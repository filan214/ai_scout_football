"""Streamlit entry point: shared sidebar, home page, navigation.

Run: streamlit run app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import streamlit as st  # noqa: E402

from scout import ui  # noqa: E402

st.set_page_config(page_title="AI Scout", page_icon="⚽", layout="wide")


def home() -> None:
    c = ui.controls()
    ui.page_header("Football recruitment, explained", "Find the right next signing",
                   "Choose a Premier League club and see where its squad needs help, which players fit the brief, "
                   "what the evidence says about each target, and how the method performed in a backtest.")
    st.caption(f"Current brief: {c['club']} · {ui.AMBITION_LABELS[c['ambition']]} · "
               f"market value up to €{c['budget_m']:.0f}m · ages {c['age_min']}–{c['age_max']}.")
    players = ui.player_season()
    faith, backtest = ui.eval_json("faithfulness"), ui.eval_json("backtest")
    cols = st.columns(3)
    cols[0].metric("Leagues searched", f"{players['league'].nunique()}",
                   help="Five major European leagues and five European feeder leagues.")
    cols[1].metric("Players with enough match time", f"{int(players['qualifies'].sum()):,}",
                   help="2025–26 player-season rows that meet the minutes and matches requirements.")
    if faith:
        cols[2].metric("Report numbers checked", f"{faith['verified']}/{faith['numbers']}",
                       help=f"Checked against report fact sheets for {faith['club']}.")

    st.subheader("Explore the decision, step by step")
    steps = [
        ("01", "Where does the squad need help?", "See where the club stands and the reasons behind each need score.",
         "pages/1_Squad_needs.py", "Explore squad needs", "📋"),
        ("02", "Who fits those needs?", "Compare affordable targets by fit, age and market value.",
         "pages/2_Targets.py", "Compare targets", "🎯"),
        ("03", "What supports a recommendation?", "Read a scouting report and inspect the facts it cites.",
         "pages/3_Scouting_report.py", "Read a scouting report", "📝"),
        ("04", "Did the approach hold up?", "See report checks, next-season results and key limitations.",
         "pages/4_Evaluation.py", "Review the evidence", "📊"),
    ]
    for start in (0, 2):
        left, right = st.columns(2)
        for col, (number, title, detail, path, label, icon) in zip((left, right), steps[start:start + 2],
                                                                    strict=True):
            with col, st.container(border=True):
                st.caption(f"STEP {number}")
                st.markdown(f"#### {title}")
                st.write(detail)
                st.page_link(path, label=label, icon=icon, width="stretch")

    with st.expander("New to these numbers? Start here"):
        st.markdown("""- **Squad need (0–100):** how strongly a position may need reinforcement. Higher means more need.
- **Fit (0–100):** how well an eligible player matches that squad's measured gaps, age brief and market-value limit.
- **Market value:** a public estimate of player value, not a predicted transfer fee.
- **Report check:** numbers and cited facts match a fact sheet; written judgments still need human review.
- **Backtest:** a look at how past picks performed a season later. It does not predict future transfers.""")

    st.subheader("What the checks say")
    if backtest:
        pooled, naive = backtest["league_pooled"], backtest["naive_baseline"]["league_pooled"]
        st.info(f"Across all 20 Premier League clubs in the 2024–25 → 2025–26 backtest, the model's picks scored "
                f"{100 * pooled['uplift']:+.1f}% above the eligible-player median. A simpler picker using last "
                f"season's performance scored {100 * naive['uplift']:+.1f}%. "
                f"Median market values were €{pooled['median_market_value_m']:.0f}m versus "
                f"€{naive['median_market_value_m']:.0f}m. These are historical comparisons, not predictions.")
    st.caption("Player stats: FotMob, 2025–26. Squads, market values and league table: see the sidebar. "
               "The sidebar changes the live needs and targets; the evaluation results use a fixed historical brief.")


ui.apply_style()
ui.sidebar()
pages = [
    st.Page(home, title="Home", icon="🏠", default=True),
    st.Page("pages/1_Squad_needs.py", title="Squad needs", icon="📋"),
    st.Page("pages/2_Targets.py", title="Targets", icon="🎯"),
    st.Page("pages/3_Scouting_report.py", title="Scouting report", icon="📝"),
    st.Page("pages/4_Evaluation.py", title="Evaluation", icon="📊"),
]
st.navigation(pages).run()
