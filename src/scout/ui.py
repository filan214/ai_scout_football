"""Shared Streamlit helpers: cached data, sidebar, live needs and shortlist.

The app only reads data/processed/ and data/reports/ (rule 2); needs and ranking are recomputed live with the
same pure functions as the pipeline. When the weekly live overlay exists (processed/live/), clubs,
market values, ages and contracts come from it; stats stay those of the analysis season.
"""

from __future__ import annotations

import json
import os
from datetime import date
from html import escape

import pandas as pd
import streamlit as st

from scout import features, llm, needs, rank
from scout.config import DOCS_DIR, LIVE_DIR, PROCESSED_DIR, Settings, load_leagues, load_settings

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
VIEW_KEY = "scout_view"
LIVE_VIEW, FROZEN_VIEW = "Live", "Frozen snapshot"


def apply_style() -> None:
    """Add the presentation styles used by the Streamlit pages."""
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
    """Render a consistent plain-language page heading."""
    st.markdown(f'<div class="scout-hero"><p class="scout-kicker">{escape(kicker)}</p>'
                f'<h1>{escape(title)}</h1><p>{escape(description)}</p></div>', unsafe_allow_html=True)


def ordinal(n: int) -> str:
    """1 -> "1st", 12 -> "12th", 22 -> "22nd"."""
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def position_label(group: str) -> str:
    """Show a readable position name alongside its abbreviation."""
    return f"{POSITION_NAMES.get(group, group)} ({group})"


def stat_label(stat: str) -> str:
    """Show a readable name for a player statistic."""
    return STAT_NAMES.get(stat, stat.replace("_", " ").capitalize())


def need_label(evidence: str, priority: str) -> str:
    """Evidence takes precedence over a score's ordinary priority band."""
    return "Insufficient evidence" if evidence == "insufficient" else priority


def evidence_badge(evidence: str, priority: str) -> None:
    """Distinct grey, text-labelled badge for insufficient evidence."""
    label = need_label(evidence, priority)
    color = PRIORITY_COLORS.get(label, "#6b7280")
    st.markdown(f'<span style="display:inline-block;border-radius:6px;padding:3px 9px;'
                f'border:1px solid {color};background:{color}22;color:inherit;font-weight:600">'
                f'{escape(label)}</span>', unsafe_allow_html=True)


def fact_label(key: str) -> str:
    """Translate a report fact key into a reader-facing label."""
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
    """settings.yaml with position_stats replaced by the lists that passed the coverage check."""
    coverage = json.loads((PROCESSED_DIR / "coverage.json").read_text(encoding="utf-8"))
    return load_settings().model_copy(update={"position_stats": coverage["position_stats"]})


@st.cache_data
def live_meta() -> dict | None:
    """meta.json of the weekly live overlay, or None when it has not been built."""
    path = LIVE_DIR / "meta.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def use_live() -> bool:
    """True when the live overlay exists and the sidebar shows live squads (the default)."""
    return live_meta() is not None and st.session_state.get(VIEW_KEY, LIVE_VIEW) == LIVE_VIEW


@st.cache_data
def _player_season(live: bool) -> pd.DataFrame:
    base = pd.read_parquet(PROCESSED_DIR / "player_season.parquet")
    if not live:
        return base
    return features.live_player_season(base, pd.read_parquet(LIVE_DIR / "squads.parquet"),
                                       pd.read_parquet(LIVE_DIR / "contracts.parquet"),
                                       date.fromisoformat(live_meta()["checked_on"]))


def player_season() -> pd.DataFrame:
    return _player_season(use_live())


@st.cache_data
def _squad_profiles(live: bool) -> pd.DataFrame:
    if not live:
        return pd.read_parquet(PROCESSED_DIR / "squad_profiles.parquet")
    return features.squad_profiles(_player_season(True), base_settings())


def squad_profiles() -> pd.DataFrame:
    return _squad_profiles(use_live())


@st.cache_data
def _standings() -> pd.DataFrame | None:
    path = LIVE_DIR / "standings.parquet"
    return pd.read_parquet(path) if path.exists() else None


def standings() -> pd.DataFrame | None:
    """Current target-league table in the live view; None in the frozen view or before the first refresh."""
    table = _standings() if use_live() else None
    if table is None:
        return None
    return table[table["league"] == base_settings().target_league].sort_values("position")


def club_standing(club: str) -> pd.Series | None:
    """The club's row of the current table, or None."""
    table = standings()
    rows = table[table["club"] == club] if table is not None else None
    return rows.iloc[0] if rows is not None and len(rows) else None


def suggested_ambition(club: str) -> str | None:
    """Ambition suggested by the current table (`needs.suggest_ambition`), or None."""
    table = standings()
    return needs.suggest_ambition(table, club, base_settings()) if table is not None else None


@st.cache_data
def league_names() -> dict[str, str]:
    return {lg.key: lg.name for lg in load_leagues()}


@st.cache_data
def _clubs(live: bool) -> list[str]:
    return needs.league_clubs(_player_season(live), base_settings().target_league)


def clubs() -> list[str]:
    return _clubs(use_live())


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
    meta = live_meta()
    if meta is not None:
        st.sidebar.radio("Squads, market values and table", [LIVE_VIEW, FROZEN_VIEW], key=VIEW_KEY,
                         help=f"Live: current clubs, SciSports values and league table from FotMob, checked "
                              f"{meta['checked_on']}. "
                              f"Frozen: the {base.as_of_date} Transfermarkt snapshot that the evaluation used.")
    st.sidebar.subheader("Club and ambition")
    club_list = clubs()
    club = st.sidebar.selectbox("Premier League club", club_list, index=club_list.index(base.target_club)
                                if base.target_club in club_list else 0,
                                help="Choose the squad whose needs and targets you want to explore.")
    suggested = suggested_ambition(club)
    ambition = st.sidebar.select_slider("Season ambition", AMBITIONS, value=suggested or base.ambition,
                                        format_func=lambda value: AMBITION_LABELS[value],
                                        help="Quality benchmark = squad level of the 17th / 10th / 4th / 1st best "
                                             "club in the league, per stat")
    standing = club_standing(club)
    if suggested is not None:
        st.sidebar.caption(f"Suggested from the current table: {AMBITION_LABELS[suggested].lower()} "
                           f"({ordinal(int(standing['position']))}, {int(standing['points'])} points after "
                           f"{int(standing['played'])} matches). You can change it.")
    elif standing is not None:
        st.sidebar.caption(f"Only {int(standing['played'])} matches played, too early to suggest an ambition "
                           "from the table.")
    st.sidebar.subheader("Target filters")
    budget = st.sidebar.slider("Maximum market value (€m)", 5, 150, int(base.pool.budget_m), step=5,
                               help="Market value is an estimate, not a predicted transfer fee.")
    age_min, age_max = st.sidebar.slider("Player age range", 16, 36, (base.pool.age_min, base.pool.age_max))
    controls = {"club": club, "ambition": ambition, "budget_m": float(budget), "age_min": int(age_min),
                "age_max": int(age_max)}
    st.session_state[STATE_KEY] = controls
    st.sidebar.divider()
    if not use_live():
        st.sidebar.caption(f"Player stats: {base.analysis_season} season. Squad and market value snapshot: "
                           f"{base.as_of_date}.")
    else:
        st.sidebar.caption(f"Player stats: {base.analysis_season} season. Clubs, squads, market values "
                           f"(FotMob, SciSports estimates) and league table: {meta['checked_on']}, "
                           f"{meta['fotmob_season']} season.")
    return controls


def controls() -> dict:
    """Current sidebar choices (set by app.py before the page runs)."""
    return st.session_state[STATE_KEY]


@st.cache_data(show_spinner="Scoring squad needs…")
def _club_needs(club: str, ambition: str, live: bool) -> pd.DataFrame:
    s = settings_for(club, ambition, base_settings().pool.budget_m, base_settings().pool.age_min,
                     base_settings().pool.age_max)
    return needs.compute_needs(_player_season(live), club, s, profiles=_squad_profiles(live))


def club_needs(club: str, ambition: str) -> pd.DataFrame:
    """Recomputed needs for one club and ambition."""
    return _club_needs(club, ambition, use_live())


@st.cache_data(show_spinner="Ranking targets…")
def _club_shortlist(club: str, ambition: str, budget_m: float, age_min: int, age_max: int,
                    live: bool) -> pd.DataFrame:
    s = settings_for(club, ambition, budget_m, age_min, age_max)
    return rank.rank_targets(_player_season(live), _club_needs(club, ambition, live), s)


def club_shortlist(club: str, ambition: str, budget_m: float, age_min: int, age_max: int) -> pd.DataFrame:
    """Recomputed shortlist for one club under the sidebar brief."""
    return _club_shortlist(club, ambition, budget_m, age_min, age_max, use_live())


def current_settings() -> Settings:
    c = controls()
    return settings_for(c["club"], c["ambition"], c["budget_m"], c["age_min"], c["age_max"])


def api_key_available() -> bool:
    """True when the LLM key is set (environment, .env, or Streamlit secrets)."""
    name = base_settings().llm.api_key_env
    try:
        if name in st.secrets and not os.environ.get(name):
            os.environ[name] = st.secrets[name]
    except Exception:
        pass
    return llm.api_key(base_settings()) is not None
