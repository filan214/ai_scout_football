"""Fact sheet, prompt v2, cached generation, regenerate-once, LLM JSON retry and usage. Fake LLM, no network."""

import json
from types import SimpleNamespace

import pandas as pd
import pytest

from scout import llm, report
from scout.config import load_settings


@pytest.fixture
def settings():
    return load_settings()


PLAYER = pd.Series({"player_name": "Equi Fernández", "age": 23, "team_name": "Bayer 04 Leverkusen",
                    "market_value_m": 20.04, "minutes": 987, "matches": 20, "minutes_share": 0.3225,
                    "contract_months_left": float("nan"),
                    "ball_recoveries_p90": 6.4137, "ball_recoveries_pct": 90.6,
                    "accurate_passes_pct_p90": 88.43, "accurate_passes_pct_pct": 70.2})
TARGET = pd.Series({"position_group": "DM", "fit": 92.17, "rank": 1, "performance": 92.46, "age_score": 100.0,
                    "value_score": 83.3, "current_best_regular": "Regular", "current_best_composite": 70.1,
                    "upgrade_vs_current": 22.36, "benchmark_composite": 79.76, "below_ambition_benchmark": True})
NEED = pd.Series({"club": "Arsenal FC", "need_score": 17.23, "priority": "Low",
                  "evidence": "sufficient", "rated_share": 0.9,
                  "stat_weights": json.dumps({"ball_recoveries": 0.6, "accurate_passes_pct": 0.4}),
                  "squad_pct": json.dumps({"ball_recoveries": 55.4, "accurate_passes_pct": None}),
                  "benchmark": json.dumps({"ball_recoveries": 81.6, "accurate_passes_pct": 77.0})})


def test_fact_sheet_rounding_sections_and_flags(settings):
    fs = report.build_fact_sheet(PLAYER, TARGET, NEED, settings, "Bundesliga")
    assert fs["player.market_value_m"] == 20.0 and fs["player.minutes"] == 987 and fs["player.league"] == "Bundesliga"
    assert fs["player.minutes_share_pct"] == 32 and fs["player.small_sample"] is True
    assert fs["stats.ball_recoveries.p90"] == 6.41 and fs["stats.ball_recoveries.pct"] == 91
    assert fs["stats.accurate_passes_pct.value"] == 88.4 and "stats.accurate_passes_pct.p90" not in fs
    assert fs["club_need.club"] == "Arsenal FC" and fs["club_need.position"] == "DM"
    assert fs["club_need.benchmark.ball_recoveries"] == 81.6
    assert fs["club_need.ambition"] == settings.ambition and fs["club_need.evidence"] == "sufficient"
    assert fs["fit.upgrade_margin"] == 22.4 and fs["fit.current_best_composite"] == 70.1
    assert fs["club_need.definition"].startswith("Need = shortfall")
    assert report.PROMPT_VERSION == "v2"
    assert "club_need.score" not in fs and "club_need.priority" not in fs
    assert fs["fit.rank"] == 1 and fs["fit.age_score"] == 100
    assert "player.contract_months_left" not in fs
    assert json.loads(json.dumps(fs)) == fs
    regular = PLAYER.copy()
    regular["minutes_share"] = 0.8
    assert report.build_fact_sheet(regular, TARGET, NEED, settings, "Bundesliga")["player.small_sample"] is False


def test_messages_are_compact_nested_json(settings):
    fs = report.build_fact_sheet(PLAYER, TARGET, NEED, settings, "Bundesliga")
    system, user = report.build_messages(fs)
    facts = json.loads(user)
    assert facts["stats.ball_recoveries.pct"] == 91 and facts["club_need.position"] == "DM"
    assert ": " not in user and "\n" not in user
    assert "small_sample" in system and "verdict" not in system
    assert report.nest({"a.b.c": 1, "a.b.d": 2, "e": 3}) == {"a": {"b": {"c": 1, "d": 2}}, "e": 3}


def _report_obj(number: str, key: str = "stats.ball_recoveries.p90"):
    return report.ScoutingReport.model_validate({
        "summary": "Ball-winning midfielder.",
        "strengths": [{"text": f"Recovers the ball {number} times per 90.", "fact_keys": [key]},
                      {"text": "Ranked first on fit.", "fact_keys": ["fit.rank"]}],
        "risks": [{"text": "Pass accuracy is only average for the group.",
                   "fact_keys": ["stats.accurate_passes_pct.pct"]}],
    })


USAGE = {"prompt": 600, "completion": 250, "reasoning": 0, "total": 850}


class FakeLLM:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), 0

    def __call__(self, system, user):
        self.calls += 1
        return self.replies.pop(0), "fake/model", USAGE


def test_generate_then_cache_hit_without_llm_call(settings, tmp_path):
    fs = report.build_fact_sheet(PLAYER, TARGET, NEED, settings, "Bundesliga")
    fake = FakeLLM([_report_obj("6.41")])
    record, hit = report.generate_report(fs, settings, fake, tmp_path)
    assert not hit and fake.calls == 1 and not record["flagged"] and record["attempts"] == 1
    assert record["usage"] == USAGE and record["prompt_version"] == report.PROMPT_VERSION
    assert (tmp_path / f"{report.cache_key(fs, settings.llm.primary_model)}.json").exists()
    again, hit = report.generate_report(fs, settings, fake, tmp_path)
    assert hit and fake.calls == 1 and again == record


def test_unfaithful_report_regenerated_once_then_flagged(settings, tmp_path):
    fs = report.build_fact_sheet(PLAYER, TARGET, NEED, settings, "Bundesliga")
    fixed = FakeLLM([_report_obj("7.9"), _report_obj("6.41")])
    record, _ = report.generate_report(fs, settings, fixed, tmp_path)
    assert fixed.calls == 2 and record["attempts"] == 2 and not record["flagged"]
    assert record["usage"]["total"] == 2 * USAGE["total"]
    stubborn = FakeLLM([_report_obj("7.9"), _report_obj("7.9", key="stats.tackles.pct")])
    record, _ = report.generate_report(fs | {"fit.rank": 2}, settings, stubborn, tmp_path)
    assert stubborn.calls == 2 and record["flagged"]
    assert record["faithfulness"]["unverified"] == [7.9]
    assert record["faithfulness"]["missing_fact_keys"] == ["stats.tackles.pct"]


def test_cache_key_changes_with_facts_and_model(settings):
    fs = report.build_fact_sheet(PLAYER, TARGET, NEED, settings, "Bundesliga")
    key = report.cache_key(fs, "a/model")
    assert key == report.cache_key(dict(reversed(list(fs.items()))), "a/model")
    assert key != report.cache_key(fs | {"fit.rank": 2}, "a/model") != report.cache_key(fs, "b/model")


def test_prompt_text_change_invalidates_cache_even_when_version_is_unchanged(settings, monkeypatch):
    fs = report.build_fact_sheet(PLAYER, TARGET, NEED, settings, "Bundesliga")
    before = report.cache_key(fs, "same/model")
    monkeypatch.setattr(report, "SYSTEM_PROMPT", report.SYSTEM_PROMPT + "\nCopy citation keys exactly.")
    assert report.cache_key(fs, "same/model") != before


def test_failed_batch_has_no_faithfulness_claim():
    result = report.generation_summary([], 20, "gateway rejected access")
    assert result["status"] == "unavailable" and result["verified_rate"] is None
    assert result["reports"] == 0 and result["expected_reports"] == 20


def test_report_access_errors_are_actionable_without_provider_internals():
    class AccessError(Exception):
        status_code = 402

    text = llm.report_error_message(AccessError("sensitive provider response"))
    assert "free-model access" in text and "facts remain available" in text
    assert "sensitive" not in text
    assert "connection" in llm.report_error_message(ConnectionError("private transport detail"))


def test_local_key_overrides_stale_environment_without_mutating_it(settings, tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "ROOT", tmp_path)
    name = settings.llm.api_key_env
    monkeypatch.setenv(name, "old-environment-credential")
    (tmp_path / ".env").write_text(name + "=test-current-local-credential", encoding="utf-8")
    assert llm.api_key(settings) == "test-current-local-credential"
    status = llm.api_key_status(settings)
    assert status["source"] == ".env" and status["os_key_differs"]
    assert status["masked"] == "test…tial"
    assert "test-current-local-credential" not in json.dumps(status)
    (tmp_path / ".env").unlink()
    assert llm.api_key(settings) == "old-environment-credential"
    assert llm.api_key_status(settings)["source"] == "OS environment"


class FakeClient:
    """Mimics openai's client.chat.completions.create."""

    def __init__(self, contents):
        self.contents, self.kwargs = list(contents), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.kwargs.append(kwargs)
        message = SimpleNamespace(content=self.contents.pop(0))
        usage = SimpleNamespace(prompt_tokens=600, completion_tokens=200, total_tokens=800,
                                completion_tokens_details=SimpleNamespace(reasoning_tokens=0))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], model="deepseek/x", usage=usage)


def test_completer_retries_invalid_json_sums_usage_and_sends_options(settings):
    valid = _report_obj("6.41").model_dump_json()
    client = FakeClient(["not json", "```json\n" + valid + "\n```"])
    parsed, model, usage = llm.make_completer(settings, report.ScoutingReport, client=client)("sys", "user")
    assert parsed == _report_obj("6.41") and model == "deepseek/x"
    assert usage == {"prompt": 1200, "completion": 400, "reasoning": 0, "total": 1600}
    assert len(client.kwargs) == 2 and client.kwargs[1]["messages"][-1]["role"] == "user"
    first = client.kwargs[0]
    assert first["model"] == settings.llm.primary_model and first["response_format"] == {"type": "json_object"}
    assert first["max_tokens"] == settings.llm.max_completion_tokens
    assert first["extra_body"] == {
        "provider": {"require_parameters": True, "max_price": {"prompt": 0, "completion": 0, "request": 0}}}


def test_only_confirmed_configured_fallback_is_sent(settings):
    configured = settings.model_copy(update={
        "llm": settings.llm.model_copy(update={
            "provider": "zenmux", "free_only": False, "fallback_models": ["confirmed/model"]})})
    client = FakeClient([_report_obj("6.41").model_dump_json()])
    llm.make_completer(configured, report.ScoutingReport, client=client)("sys", "user")
    assert client.kwargs[0]["extra_body"]["provider"] == {"fallback": "confirmed/model"}


def test_free_only_configuration_rejects_paid_model_and_fallback(settings):
    from scout.config import LLM

    data = settings.llm.model_dump()
    with pytest.raises(ValueError, match="free_only"):
        LLM.model_validate({**data, "primary_model": "paid/model"})
    with pytest.raises(ValueError, match="fallback"):
        LLM.model_validate({**data, "fallback_models": ["paid/model"]})


def test_completer_gives_up_after_one_retry(settings):
    client = FakeClient(["{}", "{}"])
    with pytest.raises(ValueError):
        llm.make_completer(settings, report.ScoutingReport, client=client)("sys", "user")
    assert len(client.kwargs) == 2
