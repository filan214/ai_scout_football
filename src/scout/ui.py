"""Shared Streamlit helpers: cached data, sidebar, live needs and shortlist. Implements IMPLEMENTATION_GUIDE §9.

The app only reads data/processed/ and data/reports/ (rule 2); needs and ranking are recomputed live with the
same pure functions as the pipeline.
"""

from __future__ import annotations

import json
import os
from html import escape

import pandas as pd
import streamlit as st

from scout import llm, needs, rank
from scout.config import DOCS_DIR, PROCESSED_DIR, Settings, load_leagues, load_settings

# Status palette (dataviz skill): priority is a state, always shown with its label.
PRIORITY_COLORS = {"High": "#d03b3b", "Medium": "#fab219", "Low": "#2e8b73",
                   "Insufficient evidence": "#6b7280"}
AMBITIONS = ["survive", "midtable", "top4", "title"]
AMBITION_LABELS = {"survive": "Stay in the league", "midtable": "Finish mid-table",
                   "top4": "Reach the top four", "title": "Challenge for the title"}
POSITION_NAMES = {"ST": "Striker", "W": "Winger", "AM": "Attacking midfield",
                  "CM": "Central midfield", "DM": "Defensive midfield", "FB": "Full-back", "CB": "Centre-back"}
STAT_NAMES = {"xg": "Expected goals", "xgot": "Expected goals on target", "xa": "Expected assists",
              "shots": "Shots", "key_passes": "Key passes", "successful_dribbles": "Successful dribbles",
              "big_chances_created": "Big chances created", "accurate_passes_pct": "Pass accuracy",
              "accurate_passes": "Accurate passes", "accurate_long_balls": "Accurate long passes",
              "tackles": "Tackles", "interceptions": "Interceptions", "ball_recoveries": "Ball recoveries",
              "blocks": "Blocks", "clearances": "Clearances"}
STATE_KEY = "scout_controls"


def apply_style() -> None:
    """Add the presentation styles used by the Streamlit pages (§9)."""
    st.markdown("""<style>
    .block-container {max-width: 1180px; padding-top: 2rem; padding-bottom: 4rem;}
    .scout-hero {background: linear-gradient(120deg, #123a32, #225d4d); border-radius: 20px;
                 padding: 1.6rem 2rem; margin-bottom: 1.4rem; color: #fff;}
    .scout-hero h1 {color: #fff; font-size: clamp(2rem, 4vw, 2.8rem); line-height: 1.12;
                    letter-spacing: -.03em; margin: .2rem 0 .6rem;}
    .scout-hero p {color: #e8f3ef; line-height: 1.55; max-width: 760px; margin: 0;}
    .scout-kicker {color: #b9e9d9 !important; font-weight: 700; font-size: .78rem;
                   text-transform: uppercase; letter-spacing: .12em;}
    [data-testid="stMetric"] {border: 1px solid rgba(120, 140, 130, .22); border-radius: 14px;
                               padding: .85rem 1rem; background: rgba(120, 140, 130, .06);}
    [data-testid="stSidebar"] {border-right: 1px solid rgba(120, 140, 130, .2);}
    </style>""", unsafe_allow_html=True)


def page_header(kicker: str, title: str, description: str) -> None:
    """Render a consistent plain-language page heading (§9)."""
    st.markdown(f'<div class="scout-hero"><p class="scout-kicker">{escape(kicker)}</p>'
                f'<h1>{escape(title)}</h1><p>{escape(description)}</p></div>', unsafe_allow_html=True)


def position_label(group: str) -> str:
    """Show a readable position name alongside its abbreviation (§9)."""
    return f"{POSITION_NAMES.get(group, group)} ({group})"


def stat_label(stat: str) -> str:
    """Show a readable name for a player statistic (§9)."""
    return STAT_NAMES.get(stat, stat.replace("_", " ").capitalize())


def need_label(evidence: str, priority: str) -> str:
    """§9 evidence takes precedence over a score's ordinary priority band."""
    return "Insufficient evidence" if evidence == "insufficient" else priority


def evidence_badge(evidence: str, priority: str) -> None:
    """§9 distinct grey, text-labelled badge for insufficient evidence."""
    label = need_label(evidence, priority)
    color = PRIORITY_COLORS.get(label, "#6b7280")
    st.markdown(f'<span style="display:inline-block;border-radius:6px;padding:3px 9px;'
                f'border:1px solid {color};background:{color}22;color:inherit;font-weight:600">'
                f'{escape(label)}</span>', unsafe_allow_html=True)


def fact_label(key: str) -> str:
    """Translate a report fact key into a reader-facing label (§9)."""
    parts = key.split(".")
    if len(parts) == 3 and parts[0] == "stats":
        unit = {"p90": " per 90 minutes", "pct": " percentile", "value": ""}.get(parts[2], "")
        return stat_label(parts[1]) + unit
    labels = {"market_value_m": "Market value (€m)", "minutes_share_pct": "Share of available minutes (%)",
              "fit": "Fit", "rank": "Shortlist rank", "age_score": "Age score", "value_score": "Value score",
              "performance": "Performance score", "score": "Fit score", "small_sample": "Small sample"}
    return labels.get(parts[-1], parts[-1].replace("_", " ").capitalize())


@st.cache_resource
def base_settings() -> Settings:
    """settings.yaml with position_stats replaced by the lists that passed the coverage check (§6.2)."""
    coverage = json.loads((PROCESSED_DIR / "coverage.json").read_text(encoding="utf-8"))
    return load_settings().model_copy(update={"position_stats": coverage["position_stats"]})


@st.cache_data
def player_season() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED_DIR / "player_season.parquet")


@st.cache_data
def squad_profiles() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED_DIR / "squad_profiles.parquet")


@st.cache_data
def league_names() -> dict[str, str]:
    return {lg.key: lg.name for lg in load_leagues()}


@st.cache_data
def clubs() -> list[str]:
    return needs.league_clubs(player_season(), base_settings().target_league)


@st.cache_data
def eval_json(name: str) -> dict | None:
    path = PROCESSED_DIR / "eval" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def image_path(name: str) -> str | None:
    path = DOCS_DIR / "img" / name
    return str(path) if path.exists() else None


def settings_for(club: str, ambition: str, budget_m: float, age_min: int, age_max: int) -> Settings:
    """Base settings with the sidebar choices applied."""
    base = base_settings()
    pool = base.pool.model_copy(update={"budget_m": budget_m, "age_min": age_min, "age_max": age_max})
    return base.model_copy(update={"target_club": club, "ambition": ambition, "pool": pool})


def sidebar() -> dict:
    """Render the shared sidebar controls (club, ambition, budget, age range) and remember the choices."""
    base = base_settings()
    st.sidebar.title("AI Scout")
    st.sidebar.caption("Set your recruitment brief. Changes update the needs and target lists across pages.")
    st.sidebar.subheader("Club and ambition")
    club_list = clubs()
    club = st.sidebar.selectbox("Premier League club", club_list, index=club_list.index(base.target_club)
                                if base.target_club in club_list else 0,
                                help="Choose the squad whose needs and targets you want to explore.")
    ambition = st.sidebar.select_slider("Season ambition", AMBITIONS, value=base.ambition,
                                        format_func=lambda value: AMBITION_LABELS[value],
                                        help="Quality benchmark = squad level of the 17th / 10th / 4th / 1st best "
                                             "club in the league, per stat")
    st.sidebar.subheader("Target filters")
    budget = st.sidebar.slider("Maximum market value (€m)", 5, 150, int(base.pool.budget_m), step=5,
                               help="Market value is an estimate, not a predicted transfer fee.")
    age_min, age_max = st.sidebar.slider("Player age range", 16, 36, (base.pool.age_min, base.pool.age_max))
    controls = {"club": club, "ambition": ambition, "budget_m": float(budget), "age_min": int(age_min),
                "age_max": int(age_max)}
    st.session_state[STATE_KEY] = controls
    st.sidebar.divider()
    st.sidebar.caption(f"Player stats: {base.analysis_season} season. Squad and market value snapshot: "
                       f"{base.as_of_date}.")
    return controls


def controls() -> dict:
    """Current sidebar choices (set by app.py before the page runs)."""
    return st.session_state[STATE_KEY]


@st.cache_data(show_spinner="Scoring squad needs…")
def club_needs(club: str, ambition: str) -> pd.DataFrame:
    """Live §6.5 needs for one club and ambition."""
    s = settings_for(club, ambition, base_settings().pool.budget_m, base_settings().pool.age_min,
                     base_settings().pool.age_max)
    return needs.compute_needs(player_season(), club, s, profiles=squad_profiles())


@st.cache_data(show_spinner="Ranking targets…")
def club_shortlist(club: str, ambition: str, budget_m: float, age_min: int, age_max: int) -> pd.DataFrame:
    """Live §6.6 shortlist for one club under the sidebar brief."""
    s = settings_for(club, ambition, budget_m, age_min, age_max)
    return rank.rank_targets(player_season(), club_needs(club, ambition), s)


def current_settings() -> Settings:
    c = controls()
    return settings_for(c["club"], c["ambition"], c["budget_m"], c["age_min"], c["age_max"])


def api_key_available() -> bool:
    """True when the LLM key is set (environment, .env, or Streamlit secrets)."""
    name = base_settings().llm.api_key_env
    try:
        if name in st.secrets and not os.environ.get(name):
            os.environ[name] = st.secrets[name]
    except Exception:  # no secrets file locally
        pass
    return llm.api_key(base_settings()) is not None
