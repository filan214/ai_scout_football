"""OpenAI-compatible report client with free-only OpenRouter routing. Implements IMPLEMENTATION_GUIDE §6.7.

openai 3.36.1 (checked): OpenAI(base_url, api_key, timeout).chat.completions.create(model, messages,
temperature, response_format, extra_body). ZenMux (docs checked 2026-10-23, zenmux.ai/docs):
base URL https://zenmux.ai/api/v1, Bearer key; per-request fallback is
extra_body={"provider": {"fallback": "<model>"}} (one model; used on 5xx, timeouts, 401/403, 404,
rate limits); the response's `model` field names the model that answered. GET /models lists slugs.
Chat API (docs checked 2026-10-23): `reasoning: {"enabled": bool}` switches explicit reasoning;
`max_completion_tokens` caps output incl. reasoning; usage.completion_tokens_details.reasoning_tokens.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from typing import Any, TypeVar

from dotenv import dotenv_values
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from scout.config import ROOT, Settings

T = TypeVar("T", bound=BaseModel)
FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$")



def api_key(settings: Settings) -> str | None:
    """Resolve the configured key: explicit local .env first, OS environment second (§6.7)."""
    return _resolve_api_key(settings)[0]


def _resolve_api_key(settings: Settings) -> tuple[str | None, str]:
    name = settings.llm.api_key_env
    local = dotenv_values(ROOT / ".env").get(name)
    if local:
        return local, ".env"
    value = os.environ.get(name) or None
    return value, "OS environment" if value else "unavailable"


def api_key_status(settings: Settings) -> dict:
    """Safe key provenance for access checks; never return the full credential."""
    key, source = _resolve_api_key(settings)
    masked = key[:4] + "…" + key[-4:] if key and len(key) > 8 else "****" if key else None
    return {"env_var": settings.llm.api_key_env, "source": source, "masked": masked,
            "os_key_differs": bool(key and os.environ.get(settings.llm.api_key_env)
                                   and key != os.environ[settings.llm.api_key_env])}


Usage = dict[str, int]
USAGE_KEYS = ("prompt", "completion", "reasoning", "total")


def usage_of(resp: Any) -> Usage:
    """Token counts of one response: prompt, completion (incl. reasoning), reasoning, total."""
    u = getattr(resp, "usage", None)
    details = getattr(u, "completion_tokens_details", None)
    return {
        "prompt": getattr(u, "prompt_tokens", 0) or 0,
        "completion": getattr(u, "completion_tokens", 0) or 0,
        "reasoning": getattr(details, "reasoning_tokens", 0) or 0,
        "total": getattr(u, "total_tokens", 0) or 0,
    }


def add_usage(a: Usage, b: Usage) -> Usage:
    return {k: a.get(k, 0) + b.get(k, 0) for k in USAGE_KEYS}


def report_error_message(error: Exception) -> str:
    """§9 actionable report-access errors without displaying provider internals or hiding player evidence."""
    if getattr(error, "status_code", None) == 402:
        return ("The report provider rejected access. Check the API key's account and free-model access; "
                "the app will not switch to a paid model. No new report was generated; "
                "the player facts remain available below.")
    if getattr(error, "status_code", None) == 429:
        return ("The free report service reached a rate or daily usage limit. Wait for the limit to reset, "
                "then retry. Cached reports and player facts remain available.")
    if getattr(error, "status_code", None) in (401, 403):
        return ("The report provider rejected authentication or model access. Check the configured API key "
                "and account permissions, then retry. The player facts remain available below.")
    return ("Report generation failed. Check the provider connection and application logs, then retry. "
            "No new report was generated; the player facts remain available below.")


def make_completer(
    settings: Settings, schema: type[T], client: Any = None
) -> Callable[[str, str], tuple[T, str, Usage]]:
    """Return complete(system, user) -> (parsed schema object, model that answered, token usage).

    JSON mode, ZenMux fallback model, reasoning switch and output cap from settings.llm; one retry
    with the validation error when the reply does not parse into `schema` (usage of both calls summed).
    """
    llm = settings.llm
    if client is None:
        key = api_key(settings)
        if not key:
            raise RuntimeError(f"{llm.api_key_env} is not set (environment or .env)")
        client = OpenAI(base_url=llm.base_url, api_key=key, timeout=llm.timeout_seconds)
    extra: dict[str, Any] = {"reasoning": {"enabled": llm.reasoning}}
    if llm.provider == "openrouter":
        extra["provider"] = {"require_parameters": True}
        if llm.free_only:
            extra["provider"]["max_price"] = {"prompt": 0, "completion": 0, "request": 0}
    elif llm.fallback_models:
        extra["provider"] = {"fallback": llm.fallback_models[0]}

    def complete(system: str, user: str) -> tuple[T, str, Usage]:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        used: Usage = dict.fromkeys(USAGE_KEYS, 0)
        for attempt in (1, 2):
            cap = {"max_tokens" if llm.provider == "openrouter" else "max_completion_tokens":
                   llm.max_completion_tokens}
            resp = client.chat.completions.create(
                model=llm.primary_model,
                messages=messages,
                temperature=llm.temperature,
                **cap,
                response_format={"type": "json_object"},
                extra_body=extra,
            )
            used = add_usage(used, usage_of(resp))
            content = resp.choices[0].message.content or ""
            try:
                return schema.model_validate_json(FENCE_RE.sub("", content)), resp.model, used
            except ValidationError as exc:
                if attempt == 2:
                    raise
                messages += [
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": f"That JSON is invalid: {exc}. Reply with corrected JSON only."},
                ]
        raise AssertionError("unreachable")

    return complete
