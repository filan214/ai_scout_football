"""Check the configured report API with one minimal request, never retry or switch providers."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from scout import llm, sources  # noqa: E402
from scout.config import PROCESSED_DIR, load_settings  # noqa: E402


def main() -> int:
    settings = load_settings()
    key = llm.api_key(settings)
    status = llm.api_key_status(settings)
    if not key:
        print(json.dumps({"status": "not_configured", "key_source": status,
                          "message": f"Set {settings.llm.api_key_env} in .env; no request made."}))
        return 2
    result = sources.probe_llm_access(settings, key)
    result["key_source"] = status
    path = PROCESSED_DIR / "eval/fallback_probe.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
