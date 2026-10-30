"""Summarize completed V0 reports and the frozen experiment without rerunning either."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scout import report  # noqa: E402
from scout.config import load_settings  # noqa: E402


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    s = load_settings()
    processed = ROOT / "data/processed"
    sheets = read(processed / "report_fact_sheets.json")["sheets"]
    records = []
    for sheet in sheets:
        path = ROOT / "data/reports" / (report.cache_key(sheet, s.llm.primary_model) + ".json")
        if not path.exists():
            raise RuntimeError("Report batch incomplete; do not publish a complete-generation summary")
        records.append(read(path))
    summary = read(processed / "eval/faithfulness.json")
    if summary.get("status") != "ok" or len(records) != len(sheets):
        raise RuntimeError("Report stage has not completed")
    counts = {"reports": len(records), "regenerated_once": sum(r["attempts"] == 2 for r in records),
              "flagged": sum(r["flagged"] for r in records),
              "tokens": sum(r["usage"]["total"] for r in records),
              "numbers": summary["numbers"], "verified": summary["verified"],
              "verified_rate": summary["verified_rate"],
              "models_used": sorted({r["model_used"] for r in records}),
              "scope": "current V0 batch; excludes earlier abandoned/uncached attempts"}
    (processed / "eval/report_generation_summary.json").write_text(json.dumps(counts, indent=2), encoding="utf-8")
    access = read(processed / "eval/fallback_probe.json")
    access["report_generation"] = counts
    (processed / "eval/fallback_probe.json").write_text(json.dumps(access, indent=2, ensure_ascii=False),
                                                      encoding="utf-8")
    experiment = read(processed / "eval/quality_experiment/summary.json")
    verification = read(processed / "eval/verification.json")
    assert experiment["decision"] == "Keep V0; stop rule triggered"
    handoff = ROOT / "HANDOFF.md"
    old = handoff.read_text(encoding="utf-8")
    marker = "## Historical handoff (2026-10-23; superseded where it conflicts above)"
    history = old[old.index(marker):] if marker in old else ""
    current = f"""# HANDOFF: AI Scout — 2026-10-31

## Current state

Branch needs-candidate-a; nothing merged or pushed. Checkpoint dbd5376 saved Candidate A + evidence
fix with failed PPG calibration and old-key HTTP 402. af0aa84 committed QUALITY_EXPERIMENT.md,
candidate metrics, selected stat sets and runner BEFORE calibration.

Production remains **V0**. Candidate A N = Q + (1−Q/100)R, R=0.20D+0.15A+0.15C; bands 35/60.
The single percentile pool, evidence rules and upgrade requirement (5 points vs best rated regular)
are unchanged. Defaults remain Arsenal/top4; the case study uses West Ham/title overrides.

## Access and reports

OpenRouter access test succeeded (HTTP 200; 68 tokens; cost 0). OPENROUTER_API_KEY is read from
the ignored .env; local values take priority over stale OS values. Do not print or commit the key.
The free-only router enforces zero prompt/completion/request prices; no paid fallback.

Current V0 batch: **{counts['reports']}/20 reports**, **{counts['verified']}/{counts['numbers']} numbers verified
({100 * counts['verified_rate']:.2f}%)**, **{counts['regenerated_once']} regenerated once** at report verification,
**{counts['flagged']} flagged**, approximately **{counts['tokens']:,} tokens**. These token counts cover this batch,
not abandoned earlier calls. See eval/report_generation_summary.json and docs/REPORT_EXAMPLES.md.
Numeric/key verification does not establish semantic correctness; the examples document unit-wording issues.

Compatibility fixes: flat exact dotted fact keys aid citation copying; prompt text participates in the cache
hash. Reasoning can be null for endpoints where it is mandatory; the output cap includes reasoning.
The earlier random-route empty responses and pinned-model upstream rate limits are not hidden successes.
Free-tier limits still apply. The report model actually answering each request is saved in its record.

## Frozen quality experiment and stop rule

V0/V1 evaluated once. V2 unavailable: no Sofascore ratings cached and its API failed a live access check.
Candidate selection used only repeatability and possession correlation; no points/PPG/GD/standings.
2025-26 is not an untouched holdout. No V1/V2 reports were generated.

| Variant | a | b | c | d | e | PPG rho | Top-six club bias | Backtest uplift (95% CI) | Mean Jaccard |
|---|---|---|---|---|---|---:|---:|---|---:|
| V0 | PASS | FAIL | PASS | PASS | PASS | −0.369 | 10% | 51.17% [49.17%, 53.65%] | 0.856 |
| V1 | PASS | FAIL | PASS | PASS | PASS | +0.207 | 5% | 56.87% [52.53%, 59.66%] | 0.850 |
| V2 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |

**Keep V0; stop rule triggered.** Calibration b (required rho ≤−0.6) remains a documented limitation.
No further variants or threshold changes. V1's higher backtest uplift uses a different stat composite
and does not demonstrate better independent club-need calibration. Experiment backtests use WH/title
for both variants; sensitivity uses the existing top4 protocol. Prior pipeline backtests were Arsenal/top4.

Full candidate/criterion tables and frozen sets: docs/QUALITY_EXPERIMENT.md.
All checks, per-position quality rhos, bias and West Ham needs at four ambitions:
docs/QUALITY_EXPERIMENT_RESULTS.md; data/processed/eval/quality_experiment/.
Production player_season/features/needs/rank remain unchanged from the registration commit.

## Checks and next action

{verification['tests_passed']} tests passed; Ruff clean. AppTest: all five pages under West Ham/title,
with and without report access, 10 checks and zero exceptions. Test output is recorded in the session.

Wait for the user's decision before any merge to main. The user must update OPENROUTER_API_KEY
in Streamlit Cloud secrets themselves for deployment. Never publish .env, raw or interim data.

---

"""
    handoff.write_text(current + history, encoding="utf-8")
    p = ROOT / "README.md"
    text = p.read_text(encoding="utf-8")
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("| Reports |"):
            lines[i] = (f"| Reports | V0 prompt v2: **{counts['verified']}/{counts['numbers']} numeric claims verified "
                        f"({100 * counts['verified_rate']:.1f}%)** across {len(records)} reports; "
                        f"{counts['regenerated_once']} regenerated once, {counts['flagged']} flagged. "
                        "Free API access verified; model/unit judgments still need review. "
                        "[Examples and citations](docs/REPORT_EXAMPLES.md). |")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
