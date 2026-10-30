"""Fact sheet, prompt, output schema, cached report generation. Implements IMPLEMENTATION_GUIDE §6.7."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, Field

from scout import faithfulness, needs
from scout.config import Settings
from scout.llm import USAGE_KEYS, Usage, add_usage

PROMPT_VERSION = "v2"


class Claim(BaseModel):
    text: str
    fact_keys: list[str]


class ScoutingReport(BaseModel):
    summary: str
    strengths: list[Claim] = Field(min_length=2, max_length=3)
    risks: list[Claim] = Field(min_length=1, max_length=2)


# User-requested evidence/upgrade prompt v2 supersedes the earlier v4 contract (§15).
# Club context and player evidence are explicitly distinguished; verdict remains deterministic.
SYSTEM_PROMPT = """Write a scouting report from the JSON facts. Reply with JSON only:
{"summary":"","strengths":[{"text":"","fact_keys":[""]}],"risks":[{"text":"","fact_keys":[""]}]}
Rules:
- Use only the facts. Copy numbers exactly; never calculate or round.
- fact_keys: dotted paths of the facts a claim uses, e.g. "stats.tackles.pct".
- Input keys are exact flat dotted keys. Copy each cited key verbatim; never shorten or invent a key.
- Strengths and risks are about the player: stats, age, minutes, contract, value. small_sample true means few \
minutes: state it as a risk.
- Club need describes the squad, never a weakness of the candidate. Mention ambition and the supplied \
upgrade margin; benchmark warnings use the supplied flag, never your own calculation.
- Insufficient evidence is an uncertainty about the club assessment, not proof of poor player quality.
- Plain words, never key names: "tackles per 90", "91st percentile", "€20.0m".
- summary at most 2 sentences; 2-3 strengths, 1-2 risks; each at most 25 words.
- No fees, wages, predictions or outside knowledge."""


def build_fact_sheet(
    player: Mapping, target: Mapping, need: Mapping, settings: Settings, league_name: str
) -> dict:
    """Display-ready facts with stable dotted keys (§6.7): € millions 1 dp, per-90 2 dp, percentiles integers.

    Sections: player, stats (the need group's stats; rate stats as `.value` %), fit, club_need (club,
    position, ambition, budget, definition, evidence, benchmarks). Club facts explain the shortlist;
    they are not player weaknesses. player: player_season row;
    target: shortlist row; need: needs row of the same group.
    """
    group = target["position_group"]
    stats = list(json.loads(need["stat_weights"]))
    share = float(player["minutes_share"])
    fs: dict = {
        "player.name": player["player_name"],
        "player.age": int(player["age"]),
        "player.position": group,
        "player.team": player["team_name"],
        "player.league": league_name,
        "player.market_value_m": round(float(player["market_value_m"]), 1),
        "player.minutes": int(player["minutes"]),
        "player.matches": int(player["matches"]),
        "player.minutes_share_pct": int(round(100 * share)),
        "player.small_sample": share < settings.reports.small_sample_minutes_share,
    }
    if pd.notna(player.get("contract_months_left")):
        fs["player.contract_months_left"] = round(float(player["contract_months_left"]), 1)
    for stat in stats:
        if stat in settings.rate_stats:
            fs[f"stats.{stat}.value"] = round(float(player[f"{stat}_p90"]), 1)
        else:
            fs[f"stats.{stat}.p90"] = round(float(player[f"{stat}_p90"]), 2)
        fs[f"stats.{stat}.pct"] = int(round(float(player[f"{stat}_pct"])))
    fs |= {
        "fit.score": round(float(target["fit"]), 1),
        "fit.rank": int(target["rank"]),
        "fit.performance": round(float(target["performance"]), 1),
        "fit.age_score": int(round(float(target["age_score"]))),
        "fit.value_score": round(float(target["value_score"]), 1),
        "club_need.club": need["club"],
        "club_need.ambition": settings.ambition,
        "club_need.budget_m": settings.pool.budget_m,
        "club_need.position": group,
        "club_need.definition": needs.NEED_DEFINITION,
        "club_need.evidence": need["evidence"],
        "club_need.rated_share_pct": round(100 * float(need["rated_share"]), 1),
        "fit.current_best_regular": target["current_best_regular"],
        "fit.current_best_composite": round(float(target["current_best_composite"]), 1),
        "fit.upgrade_margin": round(float(target["upgrade_vs_current"]), 1),
        "fit.required_upgrade_margin": float(settings.upgrade_margin),
        "fit.benchmark_composite": round(float(target["benchmark_composite"]), 1),
        "fit.below_ambition_benchmark": bool(target["below_ambition_benchmark"]),
    }
    for stat, weight in json.loads(need["stat_weights"]).items():
        fs[f"club_need.benchmark.{stat}"] = round(float(json.loads(need["benchmark"])[stat]), 1)
        fs[f"club_need.stat_weight.{stat}"] = round(float(weight), 4)
    if pd.notna(player.get("sub_position")):
        fs["player.sub_position"] = player["sub_position"]
    return fs


def nest(fact_sheet: dict) -> dict:
    """Dotted keys -> nested dict, so the prompt does not repeat key prefixes."""
    out: dict = {}
    for key, value in fact_sheet.items():
        *parents, leaf = key.split(".")
        node = out
        for p in parents:
            node = node.setdefault(p, {})
        node[leaf] = value
    return out


def build_messages(fact_sheet: dict) -> tuple[str, str]:
    """(system, user) prompt; preserve exact dotted keys so small models can copy citations verbatim."""
    return SYSTEM_PROMPT, json.dumps(fact_sheet, ensure_ascii=False, separators=(",", ":"))


def cache_key(fact_sheet: dict, primary_model: str) -> str:
    """sha256(fact sheet JSON + PROMPT_VERSION + primary model) (§6.7)."""
    payload = (json.dumps(fact_sheet, sort_keys=True, ensure_ascii=False)
               + PROMPT_VERSION + SYSTEM_PROMPT + primary_model)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generation_summary(checks: list[dict], expected: int, error: str | None = None) -> dict:
    """§7.1 failed/partial batches must not inherit old faithfulness or claim 100% from zero reports."""
    summary = faithfulness.aggregate(checks)
    if not checks:
        summary["verified_rate"] = None
    status = "ok" if len(checks) == expected and expected > 0 and error is None else (
        "incomplete" if checks else "unavailable")
    return {**summary, "status": status, "expected_reports": expected, "error": error}


def generate_report(
    fact_sheet: dict, settings: Settings, complete: Callable[[str, str], tuple[ScoutingReport, str, Usage]],
    cache_dir: Path,
) -> tuple[dict, bool]:
    """Cached report for one fact sheet: (record, cache_hit). Implements §6.7 generation.

    On a miss: call the LLM, verify (§7.1), regenerate once if not fully verified, save
    data/reports/{key}.json with the faithfulness check, `flagged` and the token usage of all calls.
    """
    key = cache_key(fact_sheet, settings.llm.primary_model)
    path = cache_dir / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8")), True
    system, user = build_messages(fact_sheet)
    usage: Usage = dict.fromkeys(USAGE_KEYS, 0)
    attempts = 0
    while True:
        attempts += 1
        result, model_used, used = complete(system, user)
        usage = add_usage(usage, used)
        check = faithfulness.verify(result.model_dump(), fact_sheet)
        if check["fully_verified"] or attempts == 2:
            break
    record = {
        "key": key,
        "prompt_version": PROMPT_VERSION,
        "model_requested": settings.llm.primary_model,
        "model_used": model_used,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "attempts": attempts,
        "usage": usage,
        "fact_sheet": fact_sheet,
        "report": result.model_dump(),
        "faithfulness": check,
        "flagged": not check["fully_verified"],
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return record, False
