"""Settings and league loaders, data paths, logging setup. Implements IMPLEMENTATION_GUIDE §2-§3."""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = DATA_DIR / "reports"
MANUAL_DIR = DATA_DIR / "manual"
DOCS_DIR = ROOT / "docs"

SEASON_RE = re.compile(r"^\d{4}-\d{2}$")


def fotmob_raw_path(league_key: str, season: str) -> Path:
    """Raw FotMob stat lists for one league-season (§4)."""
    return RAW_DIR / "fotmob" / f"{league_key}_{season}.parquet"


def fotmob_profiles_path() -> Path:
    """Raw FotMob player profiles, one JSON object per line (§5 gap-fill)."""
    return RAW_DIR / "fotmob_players" / "players.jsonl"


def fotmob_teams_raw_path(league_key: str, season: str) -> Path:
    """Raw FotMob club stat lists (team possession) for one league-season (§5)."""
    return RAW_DIR / "fotmob_teams" / f"{league_key}_{season}.parquet"


def transfermarkt_db_path() -> Path:
    """Local transfermarkt-datasets DuckDB file (§5)."""
    return RAW_DIR / "transfermarkt" / "transfermarkt-datasets.duckdb"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _check_season(value: str) -> str:
    if not SEASON_RE.match(value) or (int(value[:4]) + 1) % 100 != int(value[5:]):
        raise ValueError(f"season must look like '2025-26', got {value!r}")
    return value


Season = Annotated[str, AfterValidator(_check_season)]


def _check_sums_to_one(name: str, weights: dict[str, float]) -> None:
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError(f"{name} must sum to 1, got {sum(weights.values())}")


class Backtest(_Strict):
    as_of_date: date
    season_n: Season
    season_n1: Season


class Squad(_Strict):
    reliable_minutes: int
    depth_targets: dict[str, int]
    optional_groups: list[str] = []
    min_usage: float = 0.0


class Pool(_Strict):
    min_minutes_share: float
    min_matches_share: float
    age_min: int
    age_max: int
    ideal_age: tuple[int, int]
    budget_m: float


class LLM(_Strict):
    provider: Literal["zenmux", "openrouter"] = "zenmux"
    free_only: bool = False
    base_url: str
    api_key_env: str
    primary_model: str
    fallback_models: list[str] = Field(default_factory=list, max_length=1)
    temperature: float
    timeout_seconds: float
    reasoning: bool
    max_completion_tokens: int

    @model_validator(mode="after")
    def _free_routing(self):
        if self.free_only:
            if self.provider != "openrouter":
                raise ValueError("free_only requires the supported OpenRouter free route")
            if not (self.primary_model == "openrouter/free" or self.primary_model.endswith(":free")):
                raise ValueError("free_only requires a free router or :free model")
            if self.fallback_models:
                raise ValueError("free_only requires empty fallback_models")
        return self


class Reports(_Strict):
    small_sample_minutes_share: float


class IdMap(_Strict):
    name_threshold: float
    min_club_overlap: int


class ValueCalibration(_Strict):
    sample_per_league: int
    seed: int
    max_date_gap_days: int


class PossessionAdjustment(_Strict):
    reference: float
    stats: list[str]


class Evaluation(_Strict):
    bootstrap_resamples: int
    ci: float
    seed: int
    perturbation: float
    clubelo_timeout_seconds: float = Field(default=10, gt=0)
    calibration_clubs: int = 20
    calibration_max_ppg_rho: float = -0.6
    calibration_title_min_share: float = 0.3
    calibration_survive_max_share: float = 0.1
    calibration_min_evidence_share: float = 0.95
    calibration_top_clubs: int = 2
    calibration_top_max_high: int = 1


class Settings(_Strict):
    target_club: str
    target_league: str
    as_of_date: date
    analysis_season: Season
    backtest: Backtest
    tiers_enabled: list[int]
    ambition: Literal["survive", "midtable", "top4", "title"]
    ambition_club_rank: dict[str, int]
    squad: Squad
    squad_rating_min_minutes: int = Field(default=600, gt=0)
    min_rated_share: float = Field(default=0.5, ge=0, le=1)
    upgrade_margin: float = Field(default=5.0, ge=0, le=100)
    need_weights: dict[Literal["depth", "age", "contract"], float]
    age_risk_threshold: int
    contract_risk_months: int
    priority_bands: dict[Literal["high", "medium"], float]
    stat_weight_blend: float
    pool: Pool
    fit_weights: dict[Literal["performance", "age", "value"], float]
    shortlist_size: int
    min_ranked_groups: int
    verdict_ranks: dict[Literal["priority_target", "strong_option"], int]
    league_strength_floor: float
    position_stats: dict[str, list[str]]
    rate_stats: list[str]
    stat_fallbacks: dict[str, str]
    possession_adjustment: PossessionAdjustment
    coverage_threshold: float
    min_stats_per_group: int
    llm: LLM
    reports: Reports
    evaluation: Evaluation
    idmap: IdMap
    value_calibration: ValueCalibration
    scraping_delay_seconds: float
    scraping_max_retries: int

    @model_validator(mode="after")
    def _consistency(self) -> Settings:
        if set(self.need_weights) != {"depth", "age", "contract"}:
            raise ValueError("need_weights must contain depth, age and contract")
        if any(w < 0 for w in self.need_weights.values()) or sum(self.need_weights.values()) > 1:
            raise ValueError("secondary need weights must be nonnegative and sum to at most 1")
        _check_sums_to_one("fit_weights", self.fit_weights)
        if self.ambition not in self.ambition_club_rank:
            raise ValueError(f"no ambition_club_rank entry for ambition {self.ambition!r}")
        if set(self.position_stats) != set(self.squad.depth_targets):
            raise ValueError("position_stats and squad.depth_targets must cover the same position groups")
        return self

    def ingest_seasons(self) -> list[str]:
        """Seasons the pipeline needs: analysis season plus both backtest seasons."""
        return sorted({self.analysis_season, self.backtest.season_n, self.backtest.season_n1})


class League(_Strict):
    key: str
    name: str
    tier: int
    fotmob_id: int
    transfermarkt_id: str
    matches_per_season: int
    matches_by_season: dict[str, int] = {}
    uefa_country: str | None = None

    def matches(self, season: str) -> int:
        """Matches per club in `season` (§6.4 minutes_share denominator)."""
        return self.matches_by_season.get(season, self.matches_per_season)


def load_settings(path: Path | None = None) -> Settings:
    """Load and validate config/settings.yaml (§3)."""
    with open(path or CONFIG_DIR / "settings.yaml", encoding="utf-8") as fh:
        return Settings.model_validate(yaml.safe_load(fh))


def load_leagues(path: Path | None = None) -> list[League]:
    """Load and validate config/leagues.yaml, in file order."""
    with open(path or CONFIG_DIR / "leagues.yaml", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)["leagues"]
    return [League.model_validate({"key": key, **fields}) for key, fields in raw.items()]


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logging once for CLI entry points."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
