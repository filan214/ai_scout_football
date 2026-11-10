# DATA_REALITY: what the data actually looks like (P1)

Written 2026-10-22 from the real P1 run (`python pipeline.py --stage ingest` + `--stage clean`). Seasons 2024-25 and 2025-26, 10 leagues. Section numbers (§) refer to the project's implementation spec, which is kept private; §15 is its deviation log.

## 1. Sources and snapshot dates

| Source | What | Snapshot |
|---|---|---|
| FotMob season stat lists (`data.fotmob.com/stats/...`) | Player performance, all 10 leagues | Fetched 2026-10-22; both seasons complete |
| transfermarkt-datasets (Kaggle mirror → local DuckDB) | Birth date, position, contract, club, market values, appearances (9 leagues) | Frozen upstream: `games` to 2026-07-06, `player_valuations` to 2026-06-12; `as_of_date` = 2026-07-06 |
| FotMob player profiles (`api/data/playerData`) | Championship gap-fill + calibration sample: 1,313 profiles | Fetched 2026-10-22; market values are SciSports, per month |

Sofascore and the official transfermarkt-datasets DuckDB host are blocked by the build machine's ISP; Transfermarkt's own site answers scrapers with an AWS WAF "Human Verification" page (HTTP 405).

## 2. FotMob stat lists

37-43 player lists per league-season (`mins_played`, goals, xG, xGOT, xA, shots, chances created, big chances, dribbles, passes, long balls, tackles, interceptions, clearances, blocks, recoveries, defensive actions, possession won in final third, discipline, keeper lists). Physical lists (`phys_*`) exist only for PL 2025-26; `lbp_total` (line-breaking passes) is missing in 7 of 20 league-seasons. Neither is used.

| League | Players 24-25 / 25-26 | Clubs | Max matches per player = config |
|---|---|---|---|
| Premier League | 562 / 537 | 20 / 20 | 38 |
| La Liga | 590 / 602 | 20 / 20 | 38 |
| Bundesliga | 481 / 501 | 18 / 18 | 34 |
| Serie A | 600 / 586 | 20 / 20 | 38 |
| Ligue 1 | 542 / 551 | 18 / 18 | 34 |
| Primeira Liga | 569 / 575 | 18 / 18 | 34 |
| Eredivisie | 519 / 531 | 18 / 18 | 34 |
| Belgian Pro League | 505 / 487 | 16 / 16 | 41 observed; config 40 (30 + 10 play-off; club maxima 32-41, mode 40) |
| EFL Championship | 738 / 748 | 24 / 24 | 46 |
| Süper Lig | 582 / 570 | 19 / 18 | 36 / 34 (`matches_by_season`) |

**Not published by FotMob:** aerial duels won %, duels won %, crosses, npxG. Substitutes are in `settings.yaml` (user-confirmed); npxG falls back to xG.

### List shapes (the important part)

- **Season-total lists** (goals, assists, xG, xGOT, xA, chances created, big chances) include every player with a non-zero value.
- **Per-90 lists** (shots, dribbles, passes, pass %, long balls, tackles, interceptions, clearances, blocks, recoveries, defensive actions, possession won) include **only players who appeared in at least half of the league's matches**. The rule holds exactly in all 20 league-seasons: listed minimum = 19 of 38 (PL), 17 of 34, 23 of 46, 20 of 40 (Belgium), 18 of 36 / 17 of 34 (Süper Lig); no unlisted player reaches it. Values are per 90, rounded to 1 dp; defensive lists also publish the season total.
- `clean.build_perf` therefore stores season totals (published totals, else per-90 × minutes / 90) and fills a missing count with **0 only when the player reaches that list's minimum matches**; otherwise NaN. Pass % is never filled.

### Coverage among qualifying outfield players

Qualifying = `minutes_share ≥ pool.min_minutes_share` (0.30) and a position group other than goalkeeper. 5,442 player-league-seasons.

| Stat family | Lowest non-null % over the 10 leagues |
|---|---|
| xG, xA, xGOT, chances created, big chances, goals, assists | 100.0 |
| Every per-90-derived stat (shots, dribbles, passes, pass %, long balls, tackles, interceptions, clearances, blocks, recoveries, defensive actions, possession won) | **90.3** (Ligue 1); other leagues 91.7-94.1 for pass % |

**362 qualifying rows (6.7%) played ≥ 30% of the minutes but < 50% of the matches**, so FotMob gives them no per-90 stats. With the §6.2 rule (≥ 95% non-null in every league) the per-90-derived stats would be dropped. Adding "≥ 50% of matches" to the qualifying rule gives 100% coverage for every stat on 5,080 rows; the lost rows are mostly rotation centre-backs (CB 172, FB 59, ST 35, W 33, CM 28, DM 25, AM 10; median minutes share 0.35). **Decision (user, P2): option B**, `pool.min_matches_share: 0.5`.

## 3. Transfermarkt coverage

`competitions` covers 9 of 10 leagues; **EFL Championship (GB2) is missing** (no competition row, no clubs). 28,367 TM players with `last_season ≥ 2024`; latest valuation 2026-06-12.

## 4. ID mapping (FotMob ↔ Transfermarkt)

Clubs pair per league-season by shared player names (10/10 leagues, every club paired; the smallest overlap is ≥ 5 players). Players: spec pass (`token_sort_ratio ≥ 88`), pass 2 (subset / spacing, unique), pass 3 (unique surname), namesake ties skipped, one-to-one, 5 birth-date-verified overrides.

| League | Rows matched | Minutes-weighted |
|---|---|---|
| Premier League | 100.00% | 100.00% |
| Serie A | 99.92% | 100.00% |
| Bundesliga | 99.80% | 99.99% |
| Super Lig | 99.83% | 99.91% |
| Ligue 1 | 99.45% | 99.90% |
| Eredivisie | 99.71% | 99.84% |
| La Liga | 99.58% | 99.70% |
| Belgian Pro League | 95.46% | 99.51% |
| Primeira Liga | 98.16% | 99.13% |
| **9 TM leagues** | **99.14%** | **99.79%** (target ≥ 95%) |
| All 10 incl. Championship profiles | 99.25% | 99.82% |

Methods: 6,049 spec pass, 217 subset, 54 surname, 5 override. The spec pass alone reached 95.9% minutes-weighted (Primeira Liga 88.9%).

**Precision check:** of the 381 TM matches that also have a FotMob profile, 378 (99.2%) have the same birth date in both sources (subset 15/15, surname 2/2). The 3 differences share name and birth year with a different day or month (data-entry differences, not different players). Remaining unmatched players are mostly absent from TM's lineup data or use unrelated nicknames; the top 30 (23,504 minutes) are in `data/interim/unmatched.csv` with the closest TM name.

## 5. Championship gap-fill and value calibration

- 931 players use their FotMob profile (`tm_id = fotmob-<id>`): 814 without any TM match, 117 whose TM values were older than 92 days before `as_of_date` (TM stops updating players who leave its leagues).
- Profiles: birth date 100%, position mapped for 1,312 of 1,313, **contract end missing 36.4%** (treated as not at risk) and it reflects 2026-10, not `as_of_date`. 43 profiles have no value on or before `as_of_date`; 38 gap-fill rows have no market value.
- **Calibration** (`data/interim/value_calibration.json`): TM / SciSports on the same date, 483 players with both values: **median ratio 1.001** (IQR 0.78-1.30); by TM value: < €2m 0.96 (n 124), €2-10m 1.08 (n 224), ≥ €10m 0.96 (n 135). SciSports agrees with Transfermarkt on average but individual players differ by ±25%; an early 10-player spot check (~1.15) overstated the gap.
- Gap-fill median market value €1.06m.

## 6. Position groups

From Transfermarkt `sub_position` (FotMob profile main position for gap-fill). Qualifying outfield rows: CB 1,240 · FB 980 · CM 788 · W 777 · ST 692 · DM 573 · AM 392. Only **0.2%** use the FotMob position-id fallback (`clean.FOTMOB_POSITION_GROUPS`, majority group of matched players per pitch-grid id; back-line ids are 81-97% pure, forward ids 69-94%, midfield ids 49-65%). 846 perf rows are goalkeepers (excluded).

## 7. Known limitations

- Per-90 stats unavailable for players with < 50% of matches (above); per-90 values carry 1-dp rounding.
- Squads and values are as of 2026-07-06: summer-2026 transfers are out of scope.
- Championship values come from SciSports (calibrated), not Transfermarkt; contracts from FotMob are current, not as of `as_of_date`.
- Players who moved league mid-season appear once per league-season (442 such player-seasons).
