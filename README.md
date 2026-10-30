# AI Scout — explainable football recruitment

**From a squad weakness to a shortlist you can inspect.** AI Scout helps explore where a Premier League club needs reinforcement, which players fit its brief, and why. It covers players from 10 European leagues in a five-page Streamlit dashboard.

> **Project status:** Local app updated; need calibration has an open failed check and new report generation is blocked by gateway access. A public demo has not been deployed.

[![Watch the AI Scout portfolio walkthrough](docs/demo/thumbnail.png)](docs/demo/ai-scout-portfolio-demo.mp4)

[Watch the 2-minute narrated walkthrough](docs/demo/ai-scout-portfolio-demo.mp4). It captures the previous dashboard version and its historical evaluation, before the evidence/need update. Current behavior and results are documented below.

## Explore the product

1. **[Squad needs](docs/img/app_needs.png):** Choose a Premier League club and ambition level; see which positions need attention and what drives each score.
2. **[Player targets](docs/img/app_targets.png):** Set a budget and age range; compare candidates against the club's position-specific gaps.
3. **[Scouting report](docs/img/app_scouting_report.png):** Read a concise, evidence-cited summary, strengths, and risks for a shortlisted player.
4. **[Evaluation](docs/img/app_evaluation.png):** Inspect report faithfulness, historical picks, sensitivity, and league-strength validation.

The analytics make the decisions. Deterministic pandas functions calculate needs, rankings, and verdicts; the LLM only explains a supplied fact sheet. Its numeric claims and cited fact keys are checked before a report is shown.

## Results at a glance

The current run uses 2025–26 statistics and the 2026-07-06 squad/value snapshot. Backtesting uses 2024–25 → 2025–26. The West Ham/title case study and all 20-club acceptance tables are in [NEEDS_IMPLEMENTATION.md](docs/NEEDS_IMPLEMENTATION.md); [NEEDS_DIAGNOSIS.md](docs/NEEDS_DIAGNOSIS.md) preserves the earlier diagnosis.

| Check | Current finding |
|---|---|
| Need calibration | **4/5 pass.** PPG correlation is **−0.369**, failing the required ≤−0.6. Goal difference: −0.555; market value (secondary, non-independent): −0.716. |
| Ambition and evidence | Zero decreases / 420 comparisons; 132/135 used cells have sufficient evidence (97.8%). |
| Level meaning | At title, 46.7% of used cells are Medium/High; at survive, 1.5%. Arsenal and Manchester City have zero High positions at title. |
| Reports | New evidence/upgrade prompt v2: **0/20 generated, faithfulness unavailable**. ZenMux rejected access with HTTP 402. Historical 311/311 checks do not validate the new contract. |
| Backtest | Pooled uplift **+51.7%** (95% CI 48.6% to 54.5%; 340/439 scored). |
| Simple baseline | **Still better on next-season output:** +53.0% uplift; median outcome 80.1 vs model 79.5. |
| Cost proxy | Median value €18m model vs €30m baseline; both median age 24. |
| Stability | Mean league top-ten Jaccard across ten variants 0.856 (previously 0.849); floor −0.1 worsened from 0.843 to 0.656. |
| League-strength check | UEFA five-season Pearson 0.933 / Spearman 0.867 across nine leagues. ClubElo's single retry returned 502; its correlation is unavailable. |

No parameters were tuned after seeing acceptance results. The work remains uncommitted because calibration and new live-report requirements have not all passed. Backtest selection grew from 400 to 439 picks, so the before/after figures are pipeline comparisons over different selections, not paired causal improvements.

![Backtest of model and naive picks](docs/img/backtest.png)

![League-strength index compared with UEFA coefficients](docs/img/league_strength_uefa.png)

## How it works

```text
Offline pipeline                           Streamlit app
FotMob + Transfermarkt                     Choose club, ambition, budget, ages
        ↓                                          ↓
Clean data + cross-source identity map      Recompute needs and shortlists
        ↓                                          ↓
League-adjusted player features             Inspect player facts and cached reports
        ↓
Processed data → needs → rankings → grounded reports → evaluation
```

The app reads prepared files from `data/processed/`; it does not scrape during a session. Changing the brief recomputes needs and rankings with the same deterministic functions used by the offline pipeline. Reports are generated from a bounded fact sheet, checked against it, and cached by a hash of the facts, prompt version, and model.

### Data and decisions

- **Coverage:** FotMob season statistics and team possession for 2024–25 and 2025–26 across the Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Primeira Liga, Eredivisie, Belgian Pro League, EFL Championship, and Süper Lig. A Transfermarkt dataset snapshot supplies identity, club, contract, and market-value data for nine leagues; FotMob player profiles bridge the Championship. The cross-source match covers **99.79% of minutes** in the nine Transfermarkt leagues. [Data audit](docs/DATA_REALITY.md).
- **Player features:** Per-90 statistics are adjusted for league strength; defensive volume is also adjusted for team possession. Players must meet the minute and match thresholds before position-group percentiles are calculated across the 10 leagues.
- **Squad needs:** Need = shortfall against the selected ambition (primary), plus depth, age and contract urgency within the remaining range (secondary). N = Q + (1−Q/100) × (0.20D+0.15A+0.15C). Bands remain 35/60. Combined squad profiles use the unchanged pool; ≥600-minute non-pool players can be placed on it. Under 50% fully rated minutes produces a grey insufficient-evidence badge and excludes that position from ranking. Missing stats are never invented.
- **Targets:** Eligible players match the position, age, and market-value brief. They must beat the best current rated regular by ≥5 weighted percentile points. Fit combines need-weighted performance, age, and value; title/top4 benchmark deficits are flagged. The ranking and verdict are computed, not authored by the LLM.
- **Reports:** The LLM writes a summary, strengths, and risks from a fact sheet. Numeric claims must match facts and cited keys must exist; a failed report is retried once and then flagged.

Weights, thresholds, and league settings live in [`config/settings.yaml`](config/settings.yaml). The decision code is in [`src/scout/needs.py`](src/scout/needs.py), [`src/scout/rank.py`](src/scout/rank.py), and [`src/scout/report.py`](src/scout/report.py). For the detailed design and documented deviations, see [`PRD.md`](PRD.md) and [`IMPLEMENTATION_GUIDE.md`](IMPLEMENTATION_GUIDE.md).

## Limitations

- This is decision support, not a transfer recommendation or a forecast of fees. Market value is a proxy for affordability; there is no injury, tactical-video, wage, or scouting-observation input.
- The Transfermarkt snapshot, squads, and values are frozen at **2026-07-06**. Later transfers are not reflected. Championship values use FotMob/SciSports estimates calibrated to Transfermarkt on average; individual estimates can differ substantially.
- FotMob does not publish every desired statistic (including aerial/duel success and crosses). Some features use available substitutes, and the minute/match thresholds exclude some rotation players.
- The backtest covers **one season pair** and uses 2026 position labels, which can leak later information into eligibility. It does not establish causal improvement over the naive baseline.
- Contract dates for Championship players are current rather than aligned with the frozen snapshot, and many are missing. Three used positions lack sufficient evidence: West Ham ST/AM and Sunderland W. Other-club minutes are flagged; the local dataset has no explicit loan-status field.

## Run locally

Requires Windows PowerShell and Python 3.11. This working copy has prepared `data/processed/` files and cached `data/reports/` reports, so you can launch the dashboard without an API key or a new ingest:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local URL printed by Streamlit. The default brief is Arsenal FC, top-four ambition, a €60m market-value limit, and ages 18–27. Other briefs work for needs and targets; a report without a current cached match requires `ZENMUX_API_KEY` and enabled gateway access. Report regeneration currently returns HTTP 402.

To rebuild the data and reports, copy `.env.example` to `.env`, set `ZENMUX_API_KEY`, then run `python pipeline.py --stage all`. You can also run one stage with `--stage ingest|clean|features|needs|rank|reports|eval`. Use `python pipeline.py --stage reports --club "West Ham United" --ambition title` to resume the case-study reports once access is enabled. A first ingest takes about two hours because FotMob requests are rate-limited; cached raw responses are skipped on later runs. Raw data is not redistributed. If preparing a public repository, include the generated `data/processed/` and `data/reports/` artifacts needed for the no-key demo.

```powershell
python -m pytest -q
python -m ruff check .
```

## Repository map

| Path | Purpose |
|---|---|
| [`pipeline.py`](pipeline.py) | Offline ingest, feature, ranking, report, and evaluation stages |
| [`app.py`](app.py), [`pages/`](pages/) | Streamlit dashboard and its four analysis pages |
| [`src/scout/`](src/scout/) | Data preparation, deterministic decisions, report verification, evaluation, and UI helpers |
| [`config/`](config/) | Leagues, weights, thresholds, and model settings |
| [`tests/`](tests/) | Offline unit and integration checks |
| [`docs/DATA_REALITY.md`](docs/DATA_REALITY.md) | Source coverage and data-quality audit |

## Data and attribution

Performance data © FotMob (Opta); market data from [transfermarkt-datasets](https://github.com/dcaribou/transfermarkt-datasets) (Transfermarkt); UEFA association coefficients © UEFA. This is an educational, non-commercial portfolio project. Raw source data is not included for redistribution.
