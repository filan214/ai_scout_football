# Squad needs diagnosis: West Ham United and the Premier League

Diagnosis date: 2026-10-28. Analysis season: **2025-26**. Configured roster/value snapshot: **2026-07-06**. This report diagnoses the existing processed snapshot; it is not a claim about today's squads or results.

**No application code, configuration, or processed data was changed.** The candidate formulas below were evaluated in memory only. The four project documents were read before the analysis.

## 1. Findings

West Ham's reported title result is reproducible: **DM 42.33 (Medium)**; all six other groups are Low. The issue combines a restrictive score scale, ambition-independent depth, limited quality coverage, and an upward shift of Premier League percentiles. It is not a reversed ambition calculation.

Across the 20 clubs at title ambition, **127/140 cells are Low, 11 Medium, and 2 High**. Of 135 used positions, **96 cannot reach High even if quality_gap is set to 100 while the other components stay fixed**. That is a structural constraint of this score, separate from whether a club really needs a signing.

| Suspected cause | Verdict | Evidence |
| --- | --- | --- |
| (a) Ambition only changes quality, weighted 0.35 | **Mechanism confirmed; stated weight outdated.** | Current quality weight is **0.50**, not 0.35. Quality alone contributes at most 50 points, still below High = 60. Five West Ham groups cannot reach High through quality alone with their present other components. |
| (b) Depth counts ≥900-minute players without considering quality | **Quality/ambition independence confirmed; binary-count description outdated.** | Current depth sums fractional regulars, min(1, minutes/900). It includes sub-900 players and is unchanged across ambitions. West Ham DM gets 4.93 regular equivalents against a target of 2, so depth_gap is zero despite a 58.19 title quality gap. |
| (c) Averaging hides weak starters | **Partly confirmed, with a larger coverage caveat.** | The implementation averages rated players per stat, then relative deficits across six stats. Individual weaknesses are diluted, but simply taking each player's gap before averaging changes West Ham title quality by at most 0.50 points. More seriously, ST quality represents only 19.96% of minutes and AM uses a median-club fallback with no rated player. |
| (d) Ten-league adjusted percentiles compress PL players near the top | **Upward shift and smaller gaps confirmed; “all near the top” is too strong.** | PL role medians are 67.66–76.08 vs 46.78–48.66 elsewhere, with broad lower tails. Removing the league multiplier or using a PL reference increases needs, but West Ham still has only DM at Medium under the existing score. |
| Benchmark differs from §6.5 and is unlogged | **Rejected for the current files.** | §6.5 already specifies a separately ranked club benchmark per stat. §15 logs the change on 2026-10-22 and the later weights/depth/imputation changes on 2026-10-23. |

The baseline title mean need correlates negatively with squad market value (Spearman **−0.651**, n=20): stronger-value clubs generally have lower needs, even though the absolute score scale is low. **ClubElo correlation is unavailable** because no Elo cache exists and the official sources did not yield ratings; details and attempted endpoints are recorded below.

## 2. What the current implementation actually computes

Sources: [needs.py](../src/scout/needs.py), [features.py](../src/scout/features.py), [settings.yaml](../config/settings.yaml), [coverage.json](../data/processed/coverage.json), [IMPLEMENTATION_GUIDE §6.5](../IMPLEMENTATION_GUIDE.md#65-needs--needspy), and [§15](../IMPLEMENTATION_GUIDE.md#15-deviation-log). The final coverage-selected stats are used, including the npxg → xg fallback.

Let D, Q, A and C be depth_gap, quality_gap, age_risk and contract_risk, all on 0–100 scales:

```text
regulars = sum over unique players of min(1, total analysis-season minutes / 900)
D = clip(100 * (effective_target - regulars) / effective_target, 0, 100)

S_s = minutes-weighted mean of non-null player percentiles for statistic s
      (if nobody is rated: use the median rated PL-club profile for that stat)
B_s = kth highest rated PL-club S_s for this position and statistic
Q = 100 * mean over stats of max(0, B_s - S_s) / B_s

A = percentage of group minutes from players aged >=30
C = percentage of group minutes from players with <=12 contract months left
N = 0.20*D + 0.50*Q + 0.15*A + 0.15*C
High: N >= 60; Medium: 35 <= N < 60; Low: N < 35
```

The zero-benchmark branch contributes zero relative gap. Unknown age/contract is treated as not at risk. An empty used group gets D=Q=100 and A=C=0. For optional AM/W, the target is multiplied by usage (group share of outfield minutes divided by its configured typical share, capped at 1). Usage below 0.25 makes the group unused and all its components zero.

**Roster and eligibility are different.** The squad selects rows whose `current_club` matches the club, including analysis-season minutes at other clubs/leagues. Depth aggregates those rows by player ID. Percentiles exist only for rows meeting both the 30% available-minutes and 50% matches rules (for a 38-match PL season: ≥1,026 minutes and ≥19 matches). A 900-minute regular can therefore have no percentiles. Current-club membership is not evidence that a player was available in a particular starting XI.

### Benchmark audit and deviation log

| Ambition | k | Meaning |
| --- | --- | --- |
| survive | 17 | 17th-highest rated club profile, independently for each position/stat |
| midtable | 10 | 10th-highest profile |
| top4 | 4 | 4th-highest profile |
| title | 1 | Highest profile |

The app's “best Premier League squad, compared separately for each statistic” describes a **composite of per-stat maxima**, not one champion club's complete profile and not the top-ranked individual player. For example, West Ham's title ST comparison uses Manchester City for xg/shots/xgot, Liverpool for xa/dribbling, and Bournemouth for key passes. This composite is at least as demanding per stat as any one club's profile; it does not make the title target softer.

The target-league club identities are inferred from the most common current-club name within each PL team ID. Their profiles use all current-club rows, including minutes in other leagues. The underlying percentiles remain relative to the ten-league position pool.

The exact historical change is present in **§15, 2026-10-22, “§6.4, §6.5, §6.6 (P3 review)”**: fixed B=50/65/80/90 was replaced by the kth-best target-league squad **per stat** and relative gaps. **§15, 2026-10-23, “§3, §6.5 (P3 review, part 2)”** records fractional depth, optional positions, weights 0.20/0.50/0.15/0.15, and median imputation for unrated groups. The checked-in §6.5 matches these changes.

One wording detail deserves care in a future documentation pass: unrated clubs are excluded from a stat's ranking and k is clamped to the number of rated clubs (explicit in the `league_levels` docstring, less explicit in §6.5). AM has **14** rated clubs, W **19**, and the other groups **20**. Thus the survive AM target is the weakest of 14 rated clubs, not an independently identified 17th-place club. “17th best” is a rank of that statistic, not league-table position.


## 3. West Ham: all four ambitions

Values below are raw components, before their weights. Calculations use full precision; displayed components are rounded to two decimals. Only Q changes with ambition; D, A, C and usage stay fixed. Position keys: ST striker; W winger; AM attacking midfield; CM central midfield; DM defensive midfield; FB full-back/wing-back; CB centre-back.

### survive

| Position | depth_gap | quality_gap | age_risk | contract_risk | need_score | Priority |
| --- | --- | --- | --- | --- | --- | --- |
| ST | 0.00 | 0.00 | 36.91 | 20.90 | 8.67 | Low |
| W | 0.00 | 0.00 | 5.37 | 0.00 | 0.81 | Low |
| AM | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | Low |
| CM | 27.52 | 0.00 | 24.54 | 24.54 | 12.87 | Low |
| DM | 0.00 | 25.90 | 55.27 | 32.98 | 26.19 | Low |
| FB | 6.69 | 3.71 | 0.00 | 0.00 | 3.19 | Low |
| CB | 0.00 | 0.69 | 0.00 | 1.34 | 0.54 | Low |

### midtable

| Position | depth_gap | quality_gap | age_risk | contract_risk | need_score | Priority |
| --- | --- | --- | --- | --- | --- | --- |
| ST | 0.00 | 14.82 | 36.91 | 20.90 | 16.08 | Low |
| W | 0.00 | 4.49 | 5.37 | 0.00 | 3.05 | Low |
| AM | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | Low |
| CM | 27.52 | 1.52 | 24.54 | 24.54 | 13.63 | Low |
| DM | 0.00 | 44.57 | 55.27 | 32.98 | 35.52 | Medium |
| FB | 6.69 | 20.19 | 0.00 | 0.00 | 11.43 | Low |
| CB | 0.00 | 11.40 | 0.00 | 1.34 | 5.90 | Low |

### top4

| Position | depth_gap | quality_gap | age_risk | contract_risk | need_score | Priority |
| --- | --- | --- | --- | --- | --- | --- |
| ST | 0.00 | 21.70 | 36.91 | 20.90 | 19.52 | Low |
| W | 0.00 | 17.30 | 5.37 | 0.00 | 9.45 | Low |
| AM | 0.00 | 15.30 | 0.00 | 0.00 | 7.65 | Low |
| CM | 27.52 | 6.92 | 24.54 | 24.54 | 16.33 | Low |
| DM | 0.00 | 54.83 | 55.27 | 32.98 | 40.65 | Medium |
| FB | 6.69 | 30.77 | 0.00 | 0.00 | 16.72 | Low |
| CB | 0.00 | 27.71 | 0.00 | 1.34 | 14.06 | Low |

### title

| Position | depth_gap | quality_gap | age_risk | contract_risk | need_score | Priority |
| --- | --- | --- | --- | --- | --- | --- |
| ST | 0.00 | 28.01 | 36.91 | 20.90 | 22.67 | Low |
| W | 0.00 | 27.70 | 5.37 | 0.00 | 14.65 | Low |
| AM | 0.00 | 26.48 | 0.00 | 0.00 | 13.24 | Low |
| CM | 27.52 | 15.77 | 24.54 | 24.54 | 20.75 | Low |
| DM | 0.00 | 58.19 | 55.27 | 32.98 | 42.33 | Medium |
| FB | 6.69 | 36.40 | 0.00 | 0.00 | 19.54 | Low |
| CB | 0.00 | 34.53 | 0.00 | 1.34 | 17.47 | Low |

### What limits the title score

The contribution columns below are already weighted need-score points. The “Q=100 ceiling” holds D/A/C fixed and shows the maximum achievable score through ambition/quality alone. A required Q above 100 means that band is unreachable with those fixed other components.

| Position | 0.20D | 0.50Q | 0.15A | 0.15C | Need | Q=100 ceiling | Q needed for Medium | Q needed for High |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ST | 0.00 | 14.00 | 5.54 | 3.13 | 22.67 | 58.67 | 52.66 | 102.66 |
| W | 0.00 | 13.85 | 0.81 | 0.00 | 14.65 | 50.81 | 68.39 | 118.39 |
| AM | 0.00 | 13.24 | 0.00 | 0.00 | 13.24 | 50.00 | 70.00 | 120.00 |
| CM | 5.50 | 7.89 | 3.68 | 3.68 | 20.75 | 62.87 | 44.27 | 94.27 |
| DM | 0.00 | 29.09 | 8.29 | 4.95 | 42.33 | 63.24 | 43.52 | 93.52 |
| FB | 1.34 | 18.20 | 0.00 | 0.00 | 19.54 | 51.34 | 67.32 | 117.32 |
| CB | 0.00 | 17.27 | 0.00 | 0.20 | 17.47 | 50.20 | 69.60 | 119.60 |

For DM, **29.09 quality points + 8.29 age + 4.95 contract + 0 depth = 42.33**. Its non-quality contribution is 13.24, so Q would need to reach **93.52** to cross High; the measured Q is 58.19. For W/AM, little or no non-quality risk leaves their scores close to half their quality gap. ST, W, AM, FB and CB cannot reach High even at Q=100 with their current other risks.

This is not necessarily an arithmetic bug: the current score is a weighted combination of four distinct risks. It is, however, a poor match for interpreting “Low” as “good enough for the selected ambition.” A young, numerically full, long-contract squad can be far below the target and still remain Low/Medium.

### Depth and quality coverage

“Regulars” are fractional 900-minute credits. “Rated minutes” are minutes whose player-stat rows actually enter the percentile profile. Effective targets incorporate usage; all seven West Ham groups are used, with AM usage **0.4423** and all other usage values 1.

| Position | Players | ≥900-minute regulars | Fractional regulars | Effective target | Total minutes | Rated minutes | Rated share % | Minutes at other clubs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ST | 5 | 4 | 4.06 | 2.00 | 6226 | 1243 | 19.96 | 2296 |
| W | 4 | 2 | 3.26 | 3.00 | 7017 | 5885 | 83.87 | 634 |
| AM | 2 | 1 | 1.31 | 0.88 | 1799 | 0 | 0.00 | 270 |
| CM | 3 | 2 | 2.17 | 3.00 | 4466 | 3024 | 67.71 | 1285 |
| DM | 6 | 4 | 4.93 | 2.00 | 6664 | 3365 | 50.50 | 2076 |
| FB | 4 | 3 | 3.73 | 4.00 | 6834 | 6175 | 90.36 | 0 |
| CB | 7 | 4 | 4.56 | 4.00 | 7665 | 5904 | 77.03 | 290 |

West Ham's selected outfield rows contain **6,851 of 40,671 minutes (16.85%) at other teams**. Examples include Ward-Prowse at Burnley, Álvarez at Fenerbahçe and Casey at Swansea. This follows the current-club definition, but those rows do not establish match-day availability. Quality-blind depth can credit these players even when their percentiles are absent. No loan-status or lineup inference is made here.

At ST, **only Callum Wilson** is rated. Castellanos has 1,395 PL minutes but 18 PL appearances, so misses the 19-match rule; his Lazio row also fails eligibility. Pablo and Füllkrug have enough combined minutes to count as regulars but no qualifying league row. At AM, **Paquetá's 1,521 minutes across 18 matches are excluded from percentiles**, and Earthy is also unrated, so the entire quality comparison uses median-club values. A Low AM score is therefore not an assessment that Paquetá meets the ambition.

Across the league, five used cells have under 50% rated minutes:

| Club | Position | Rated minutes % |
| --- | --- | --- |
| Brighton & Hove Albion | AM | 0.00 |
| Sunderland AFC | W | 36.99 |
| Tottenham Hotspur | CM | 32.92 |
| West Ham United | ST | 19.96 |
| West Ham United | AM | 0.00 |

### How much does averaging hide?

“Player-first mean” computes each rated regular's average relative stat gap and then weights those gaps by rated minutes. “Worst rated regular” takes the highest such gap. This is an averaging diagnostic, not a claim about the actual starting lineup. AM has no rated regular; its fallback is shown explicitly.

| Position | Current Q | Player-first mean Q | Worst rated regular Q | Rated regulars represented |
| --- | --- | --- | --- | --- |
| ST | 28.01 | 28.01 | 28.01 | Callum Wilson |
| W | 27.70 | 27.79 | 35.74 | Jarrod Bowen; Crysencio Summerville |
| AM | 26.48 | N/A (median fallback) | N/A | None |
| CM | 15.77 | 15.77 | 15.77 | Mateus Fernandes |
| DM | 58.19 | 58.19 | 68.35 | Freddie Potts; Tomás Souček |
| FB | 36.40 | 36.47 | 48.33 | Malick Diouf; Kyle Walker-Peters; Aaron Wan-Bissaka |
| CB | 34.53 | 35.03 | 46.72 | Konstantinos Mavropanos; Max Kilman; Jean-Clair Todibo |

Changing only the order of the player/stat averaging has little effect here: the largest title Q increase is **0.50 at CB**. At title ambition most individual values are below the benchmark, so the positive-part operator often behaves linearly. This rejects averaging order as the main explanation for West Ham's low total scores.

There is still dilution of weak individuals and specific skills: Souček's overall title gap is **68.35** vs DM's 58.19; Walker-Peters' is **48.33** vs FB's 36.40; Kilman's is **46.72** vs CB's 34.53. Wilson's ST xa and key-pass relative deficits are **74.37** and **60.59**, but the six-stat mean Q is only 28.01. DM ball recoveries have a **90.67** relative deficit. The detailed percentile tables below show these weaknesses directly. Giving the worst player or skill more weight is a different design objective, not a correction to a mistaken mean.

### Sensitivity to missing player percentiles

The following is a deliberately extreme bound, not an imputation recommendation. Keep the existing title benchmarks and D/A/C fixed, include all group minutes in the profile, and replace missing percentiles with either 100 (best bound) or 0 (worst bound). The range tests how much the unrated portion could matter; it does not estimate a likely score or recompute the league benchmarks.

| Position | Current title need | All missing pct=100 | All missing pct=0 |
| --- | --- | --- | --- |
| ST | 22.67 | 9.88 | 51.48 |
| W | 14.65 | 11.89 | 20.49 |
| AM | 13.24 | 0.00 | 50.00 |
| CM | 20.75 | 17.43 | 34.35 |
| DM | 42.33 | 27.63 | 52.68 |
| FB | 19.54 | 17.34 | 22.61 |
| CB | 17.47 | 12.68 | 24.99 |

ST's possible range is wide, and AM has no observed percentile evidence at all. This should be resolved or clearly surfaced before treating any candidate's output as a validated recruitment recommendation.


## 4. West Ham benchmarks, squad profiles and individual percentiles

### Per-stat squad profile and all ambition benchmarks

Each value is a percentile on the current ten-league scale, except the last column, which is a relative deficit percentage. `Squad observed` is the stored minutes-weighted profile; `Squad used` shows the median-club substitution where the observed value is missing. These squad profiles do not change with ambition. `S/M/T4/T` benchmark columns mean survive/midtable/top4/title. The six-stat mean of the last column is the title Q shown above. Each benchmark's source club can differ by stat.

#### ST

| Stat | Squad observed | Squad used | B S | B M | B T4 | B T | Rated clubs | Title benchmark source | Title relative gap % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| xg | 96.72 | 96.72 | 54.24 | 86.09 | 96.42 | 99.70 | 20 | Manchester City | 2.99 |
| shots | 91.04 | 91.04 | 56.97 | 79.83 | 93.88 | 98.81 | 20 | Manchester City | 7.85 |
| xa | 24.18 | 24.18 | 24.18 | 46.33 | 70.35 | 94.33 | 20 | Liverpool FC | 74.37 |
| key_passes | 33.73 | 33.73 | 33.73 | 57.30 | 83.58 | 85.60 | 20 | AFC Bournemouth | 60.59 |
| successful_dribbles | 85.07 | 85.07 | 38.66 | 64.28 | 85.07 | 99.10 | 20 | Liverpool FC | 14.16 |
| xgot | 91.64 | 91.64 | 54.40 | 75.26 | 93.41 | 99.70 | 20 | Manchester City | 8.08 |

#### W

| Stat | Squad observed | Squad used | B S | B M | B T4 | B T | Rated clubs | Title benchmark source | Title relative gap % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| xa | 57.72 | 57.72 | 34.86 | 57.78 | 77.52 | 94.06 | 19 | Chelsea FC | 38.64 |
| key_passes | 54.00 | 54.00 | 42.43 | 73.82 | 83.98 | 93.31 | 19 | Chelsea FC | 42.13 |
| successful_dribbles | 82.64 | 82.64 | 24.04 | 53.34 | 82.64 | 92.72 | 19 | Manchester City | 10.87 |
| xg | 67.78 | 67.78 | 34.35 | 67.78 | 90.24 | 98.61 | 19 | Crystal Palace | 31.27 |
| shots | 81.40 | 81.40 | 41.55 | 78.35 | 87.21 | 96.39 | 19 | Liverpool FC | 15.55 |
| big_chances_created | 64.03 | 64.03 | 22.99 | 58.00 | 71.92 | 88.58 | 19 | Arsenal FC | 27.72 |

#### AM

| Stat | Squad observed | Squad used | B S | B M | B T4 | B T | Rated clubs | Title benchmark source | Title relative gap % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| xa | N/A | 74.10 | 7.84 | 54.30 | 85.48 | 99.46 | 14 | Manchester United | 25.50 |
| key_passes | N/A | 77.39 | 29.41 | 50.68 | 89.25 | 100.00 | 14 | Manchester United | 22.61 |
| xg | N/A | 64.51 | 8.06 | 52.77 | 74.50 | 100.00 | 14 | Chelsea FC | 35.49 |
| successful_dribbles | N/A | 74.16 | 22.58 | 68.78 | 87.10 | 94.09 | 14 | Wolverhampton Wanderers | 21.18 |
| accurate_passes_pct | N/A | 65.46 | 10.22 | 25.44 | 81.16 | 94.36 | 14 | Manchester City | 30.63 |
| shots | N/A | 75.30 | 14.78 | 66.65 | 91.40 | 98.39 | 14 | Chelsea FC | 23.46 |

#### CM

| Stat | Squad observed | Squad used | B S | B M | B T4 | B T | Rated clubs | Title benchmark source | Title relative gap % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| accurate_passes_pct | 79.84 | 79.84 | 39.60 | 61.03 | 79.84 | 92.13 | 20 | Manchester City | 13.34 |
| accurate_long_balls | 97.85 | 97.85 | 33.88 | 60.08 | 78.51 | 97.85 | 20 | West Ham United | 0.00 |
| key_passes | 71.77 | 71.77 | 49.54 | 71.88 | 80.66 | 93.92 | 20 | Aston Villa | 23.58 |
| tackles | 95.43 | 95.43 | 59.01 | 80.65 | 94.62 | 96.22 | 20 | Nottingham Forest | 0.82 |
| interceptions | 77.96 | 77.96 | 60.85 | 77.96 | 91.14 | 95.43 | 20 | Leeds United | 18.31 |
| xa | 57.26 | 57.26 | 44.62 | 62.90 | 68.21 | 93.23 | 20 | Arsenal FC | 38.59 |

#### DM

| Stat | Squad observed | Squad used | B S | B M | B T4 | B T | Rated clubs | Title benchmark source | Title relative gap % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| tackles | 63.31 | 63.31 | 51.70 | 83.58 | 94.85 | 99.26 | 20 | Chelsea FC | 36.22 |
| interceptions | 38.49 | 38.49 | 51.10 | 70.22 | 90.81 | 100.00 | 20 | Chelsea FC | 61.51 |
| ball_recoveries | 9.28 | 9.28 | 65.81 | 83.09 | 95.59 | 99.44 | 20 | Manchester City | 90.67 |
| accurate_passes_pct | 21.11 | 21.11 | 38.24 | 71.32 | 89.52 | 97.43 | 20 | Chelsea FC | 78.34 |
| accurate_passes | 60.25 | 60.25 | 60.25 | 87.18 | 94.12 | 99.07 | 20 | Manchester City | 39.19 |
| accurate_long_balls | 55.56 | 55.56 | 41.32 | 60.29 | 86.03 | 97.79 | 20 | Sunderland AFC | 43.18 |

#### FB

| Stat | Squad observed | Squad used | B S | B M | B T4 | B T | Rated clubs | Title benchmark source | Title relative gap % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| tackles | 48.80 | 48.80 | 54.44 | 82.04 | 92.54 | 94.56 | 20 | Crystal Palace | 48.39 |
| interceptions | 68.97 | 68.97 | 59.01 | 73.10 | 88.48 | 97.15 | 20 | Fulham FC | 29.00 |
| xa | 33.51 | 33.51 | 37.17 | 60.97 | 73.43 | 81.09 | 20 | Newcastle United | 58.68 |
| key_passes | 59.28 | 59.28 | 48.84 | 60.56 | 81.47 | 87.79 | 20 | Newcastle United | 32.47 |
| ball_recoveries | 57.96 | 57.96 | 59.17 | 80.29 | 87.42 | 94.15 | 20 | Chelsea FC | 38.44 |
| successful_dribbles | 85.28 | 85.28 | 38.82 | 59.12 | 85.28 | 96.29 | 20 | Brentford FC | 11.43 |

#### CB

| Stat | Squad observed | Squad used | B S | B M | B T4 | B T | Rated clubs | Title benchmark source | Title relative gap % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| blocks | 82.42 | 82.42 | 60.89 | 81.17 | 89.01 | 94.26 | 20 | Aston Villa | 12.55 |
| clearances | 79.34 | 79.34 | 70.15 | 83.49 | 95.65 | 98.24 | 20 | Liverpool FC | 19.23 |
| interceptions | 53.36 | 53.36 | 55.65 | 63.32 | 83.18 | 97.68 | 20 | AFC Bournemouth | 45.37 |
| tackles | 60.46 | 60.46 | 49.50 | 66.25 | 83.86 | 88.47 | 20 | AFC Bournemouth | 31.66 |
| accurate_passes_pct | 40.65 | 40.65 | 34.67 | 50.52 | 76.05 | 95.15 | 20 | Chelsea FC | 57.28 |
| accurate_long_balls | 51.47 | 51.47 | 50.01 | 63.90 | 75.17 | 87.36 | 20 | AFC Bournemouth | 41.08 |

### Player-level audit, including every regular

The processed data has **minutes and appearances, not starting-XI/starts data**. A dagger (†) therefore identifies the explicit **starter proxy: at least 900 combined analysis-season minutes**, not a verified starter. Every selected West Ham player is included so unrated regulars and bench depth remain visible. Rows combine a player's league records by ID; percentiles average only rated rows using rated minutes. Actual club quality follows those same rated-minute contributions.

`Total/WH min` gives combined selected minutes and minutes recorded for West Ham. `Rated min` is the subset entering the percentiles. `Matches` follows the listed teams in the same order. **N/A means no qualifying percentile; it is not zero.** No individual percentile changes with ambition, so the tables apply to all four levels and should be read against the benchmark tables above.

#### ST: players

| Player | FotMob ID | Total/WH min | Rated min | Teams | Matches | xg | shots | xa | key_passes | successful_dribbles | xgot |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Valentín Castellanos † | 823658 | 2089/1395 | 0 | West Ham United; Lazio | 18; 11 | N/A | N/A | N/A | N/A | N/A | N/A |
| Pablo † | 1227326 | 1781/826 | 0 | West Ham United; Gil Vicente | 14; 13 | N/A | N/A | N/A | N/A | N/A | N/A |
| Callum Wilson † | 184321 | 1243/1243 | 1243 | West Ham United | 32 | 96.7 | 91.0 | 24.2 | 33.7 | 85.1 | 91.6 |
| Niclas Füllkrug † | 276791 | 1055/408 | 0 | West Ham United; Milan | 8; 20 | N/A | N/A | N/A | N/A | N/A | N/A |
| Callum Marshall | 1327325 | 58/58 | 0 | West Ham United | 2 | N/A | N/A | N/A | N/A | N/A | N/A |

#### W: players

| Player | FotMob ID | Total/WH min | Rated min | Teams | Matches | xa | key_passes | successful_dribbles | xg | shots | big_chances_created |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Jarrod Bowen † | 523825 | 3405/3405 | 3405 | West Ham United | 38 | 61.2 | 59.8 | 76.5 | 69.5 | 82.7 | 89.5 |
| Crysencio Summerville † | 941213 | 2480/2480 | 2480 | West Ham United | 31 | 52.9 | 46.0 | 91.1 | 65.4 | 79.6 | 29.1 |
| Luís Guilherme | 1458757 | 755/121 | 0 | West Ham United; Sporting Lisbon | 5; 13 | N/A | N/A | N/A | N/A | N/A | N/A |
| Adama Traoré | 493647 | 377/377 | 0 | West Ham United | 24 | N/A | N/A | N/A | N/A | N/A | N/A |

#### AM: players

| Player | FotMob ID | Total/WH min | Rated min | Teams | Matches | xa | key_passes | xg | successful_dribbles | accurate_passes_pct | shots |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Lucas Paquetá † | 766435 | 1521/1521 | 0 | West Ham United | 18 | N/A | N/A | N/A | N/A | N/A | N/A |
| George Earthy | 1211806 | 278/8 | 0 | Bristol City; West Ham United | 10; 1 | N/A | N/A | N/A | N/A | N/A | N/A |

#### CM: players

| Player | FotMob ID | Total/WH min | Rated min | Teams | Matches | accurate_passes_pct | accurate_long_balls | key_passes | tackles | interceptions | xa |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Mateus Fernandes † | 1356312 | 3213/3024 | 3024 | Southampton; West Ham United | 3; 36 | 79.8 | 97.8 | 71.8 | 95.4 | 78.0 | 57.3 |
| James Ward-Prowse † | 279490 | 1096/0 | 0 | Burnley | 18 | N/A | N/A | N/A | N/A | N/A | N/A |
| Andy Irving | 863359 | 157/157 | 0 | West Ham United | 7 | N/A | N/A | N/A | N/A | N/A | N/A |

#### DM: players

| Player | FotMob ID | Total/WH min | Rated min | Teams | Matches | tackles | interceptions | ball_recoveries | accurate_passes_pct | accurate_passes | accurate_long_balls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Tomás Souček † | 524437 | 2198/2198 | 2198 | West Ham United | 35 | 55.1 | 16.2 | 7.0 | 9.4 | 55.1 | 44.9 |
| Guido Rodríguez † | 586768 | 1485/177 | 0 | Valencia CF; West Ham United | 16; 6 | N/A | N/A | N/A | N/A | N/A | N/A |
| Freddie Potts † | 1206287 | 1167/1167 | 1167 | West Ham United | 22 | 78.7 | 80.5 | 13.6 | 43.2 | 69.9 | 75.7 |
| Soungoutou Magassa † | 1385894 | 979/979 | 0 | West Ham United | 22 | N/A | N/A | N/A | N/A | N/A | N/A |
| Edson Álvarez | 783505 | 768/0 | 0 | Fenerbahçe | 12 | N/A | N/A | N/A | N/A | N/A | N/A |
| Mohamadou Kanté | 1529203 | 67/67 | 0 | West Ham United | 11 | N/A | N/A | N/A | N/A | N/A | N/A |

#### FB: players

| Player | FotMob ID | Total/WH min | Rated min | Teams | Matches | tackles | interceptions | xa | key_passes | ball_recoveries | successful_dribbles |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Malick Diouf † | 1451265 | 2711/2711 | 2711 | West Ham United | 32 | 38.3 | 71.5 | 58.7 | 76.7 | 70.7 | 85.4 |
| Aaron Wan-Bissaka † | 760320 | 2084/2084 | 2084 | West Ham United | 25 | 33.2 | 98.3 | 19.7 | 61.9 | 39.0 | 80.5 |
| Kyle Walker-Peters † | 734042 | 1380/1380 | 1380 | West Ham United | 23 | 92.9 | 19.7 | 4.9 | 21.2 | 61.7 | 92.2 |
| Oliver Scarles | 1315319 | 659/659 | 0 | West Ham United | 13 | N/A | N/A | N/A | N/A | N/A | N/A |

#### CB: players

| Player | FotMob ID | Total/WH min | Rated min | Teams | Matches | blocks | clearances | interceptions | tackles | accurate_passes_pct | accurate_long_balls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Konstantinos Mavropanos † | 719219 | 2528/2528 | 2528 | West Ham United | 31 | 93.3 | 90.9 | 96.3 | 63.3 | 18.4 | 91.2 |
| Jean-Clair Todibo † | 955214 | 1817/1817 | 1817 | West Ham United | 23 | 53.6 | 58.3 | 35.4 | 86.5 | 55.3 | 13.0 |
| Max Kilman † | 865931 | 1559/1559 | 1559 | West Ham United | 21 | 98.3 | 85.2 | 4.6 | 25.6 | 59.7 | 31.9 |
| Axel Disasi † | 696646 | 1255/1255 | 0 | West Ham United | 14 | N/A | N/A | N/A | N/A | N/A | N/A |
| Kaelan Casey | 1302814 | 290/0 | 0 | Swansea City | 8 | N/A | N/A | N/A | N/A | N/A | N/A |
| Ezra Mayers | 1624950 | 113/113 | 0 | West Ham United | 6 | N/A | N/A | N/A | N/A | N/A | N/A |
| Igor Julio | 768331 | 103/103 | 0 | West Ham United | 4 | N/A | N/A | N/A | N/A | N/A | N/A |


## 5. All 20 Premier League clubs

All league distributions use **20 clubs × 7 position groups = 140 cells**, with equal weight per cell. Quantiles use pandas' linear interpolation; bands use unrounded scores. Club mean need is the unweighted mean of its seven cells. This deliberately includes unused positions to match the full app output; an active-only correlation is also reported.

Five cells are unused and zero at every ambition: Everton AM, Newcastle AM, Sunderland AM, Tottenham AM and Wolves W. They are counted as Low in the requested total; among the 135 used cells, title has **122 Low / 11 Medium / 2 High**.

### Baseline distribution

| Ambition | n | Min | p10 | Median | p90 | Max | High | Medium | Low | Mean Q |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| survive | 140 | 0.00 | 0.00 | 6.67 | 19.31 | 54.06 | 0 | 2 | 138 | 3.29 |
| title | 140 | 0.00 | 9.79 | 20.84 | 34.07 | 64.33 | 2 | 11 | 127 | 29.49 |

At title, the only High cells are Burnley CM (**64.33**) and Crystal Palace CM (**61.83**). There are **81 used cells with zero depth_gap** and **96/135 used cells whose fixed-other-component Q=100 ceiling is below 60**. The scarcity of High scores is therefore partly structural, not merely a West Ham anomaly.

### title: full club × position matrix

Cells show score and band (H = High, M = Medium, L = Low); * marks an unused zero. Means use full-precision values.

| Club | ST | W | AM | CM | DM | FB | CB | Mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AFC Bournemouth | 13.9 L | 11.1 L | 8.4 L | 17.2 L | 17.7 L | 30.2 L | 11.3 L | 15.70 |
| Arsenal FC | 17.2 L | 17.1 L | 15.1 L | 16.6 L | 20.1 L | 16.0 L | 16.0 L | 16.88 |
| Aston Villa | 37.7 M | 28.6 L | 28.4 L | 23.3 L | 13.9 L | 21.3 L | 28.5 L | 25.96 |
| Brentford FC | 22.7 L | 22.9 L | 22.1 L | 28.4 L | 28.9 L | 21.5 L | 21.9 L | 24.07 |
| Brighton & Hove Albion | 31.4 L | 18.5 L | 13.2 L | 28.4 L | 24.0 L | 15.9 L | 20.0 L | 21.65 |
| Burnley FC | 28.1 L | 22.9 L | 22.2 L | 64.3 H | 21.1 L | 41.1 M | 21.1 L | 31.56 |
| Chelsea FC | 12.0 L | 7.4 L | 12.3 L | 16.4 L | 7.6 L | 6.3 L | 9.0 L | 10.15 |
| Crystal Palace | 34.4 L | 28.7 L | 43.5 M | 61.8 H | 27.4 L | 24.5 L | 19.0 L | 34.19 |
| Everton FC | 29.6 L | 29.8 L | 0.0 L * | 28.7 L | 18.1 L | 39.5 M | 40.1 M | 26.56 |
| Fulham FC | 24.5 L | 34.0 L | 22.8 L | 41.4 M | 23.1 L | 27.3 L | 25.5 L | 28.36 |
| Leeds United | 20.1 L | 14.3 L | 28.6 L | 18.9 L | 19.3 L | 18.5 L | 20.9 L | 20.09 |
| Liverpool FC | 4.5 L | 11.7 L | 9.4 L | 23.0 L | 20.1 L | 19.1 L | 32.3 L | 17.15 |
| Manchester City | 9.8 L | 12.3 L | 21.4 L | 40.3 M | 17.4 L | 9.9 L | 13.2 L | 17.76 |
| Manchester United | 12.7 L | 12.8 L | 32.5 L | 25.5 L | 19.7 L | 26.6 L | 24.2 L | 21.98 |
| Newcastle United | 16.8 L | 23.4 L | 0.0 L * | 14.5 L | 23.0 L | 19.3 L | 24.2 L | 17.31 |
| Nottingham Forest | 36.2 M | 21.1 L | 15.3 L | 9.5 L | 22.5 L | 7.9 L | 15.2 L | 18.26 |
| Sunderland AFC | 27.3 L | 39.0 M | 0.0 L * | 23.6 L | 39.5 M | 29.3 L | 20.7 L | 25.63 |
| Tottenham Hotspur | 26.1 L | 29.1 L | 0.0 L * | 16.8 L | 23.2 L | 14.2 L | 19.9 L | 18.48 |
| West Ham United | 22.7 L | 14.7 L | 13.2 L | 20.8 L | 42.3 M | 19.5 L | 17.5 L | 21.52 |
| Wolverhampton Wanderers | 28.7 L | 0.0 L * | 19.4 L | 17.6 L | 18.5 L | 19.4 L | 24.8 L | 18.35 |

### survive: full club × position matrix

Cells show score and band (H = High, M = Medium, L = Low); * marks an unused zero. Means use full-precision values.

| Club | ST | W | AM | CM | DM | FB | CB | Mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AFC Bournemouth | 0.0 L | 0.0 L | 2.0 L | 3.0 L | 10.0 L | 17.0 L | 9.5 L | 5.94 |
| Arsenal FC | 4.6 L | 11.4 L | 0.0 L | 10.4 L | 9.9 L | 4.0 L | 2.4 L | 6.09 |
| Aston Villa | 25.0 L | 13.9 L | 10.0 L | 12.8 L | 0.0 L | 8.8 L | 19.2 L | 12.81 |
| Brentford FC | 10.0 L | 5.2 L | 0.7 L | 9.5 L | 15.2 L | 7.0 L | 5.8 L | 7.62 |
| Brighton & Hove Albion | 15.0 L | 7.4 L | 0.0 L | 10.7 L | 2.6 L | 2.6 L | 10.2 L | 6.93 |
| Burnley FC | 4.5 L | 0.0 L | 0.0 L | 54.1 M | 2.2 L | 24.0 L | 5.5 L | 12.89 |
| Chelsea FC | 0.0 L | 0.0 L | 1.0 L | 6.7 L | 5.5 L | 0.0 L | 3.0 L | 2.31 |
| Crystal Palace | 24.4 L | 14.3 L | 15.0 L | 45.8 M | 8.8 L | 13.5 L | 8.3 L | 18.57 |
| Everton FC | 13.2 L | 11.2 L | 0.0 L * | 11.5 L | 5.7 L | 22.6 L | 28.0 L | 13.17 |
| Fulham FC | 10.2 L | 13.8 L | 0.0 L | 33.6 L | 10.7 L | 15.8 L | 13.5 L | 13.93 |
| Leeds United | 5.2 L | 0.0 L | 7.0 L | 6.7 L | 2.9 L | 5.2 L | 3.2 L | 4.31 |
| Liverpool FC | 2.2 L | 5.5 L | 0.3 L | 12.8 L | 15.3 L | 5.2 L | 22.3 L | 9.09 |
| Manchester City | 2.2 L | 0.0 L | 9.8 L | 26.9 L | 14.8 L | 0.0 L | 4.4 L | 8.30 |
| Manchester United | 0.0 L | 0.0 L | 22.3 L | 13.4 L | 12.0 L | 11.6 L | 10.1 L | 9.92 |
| Newcastle United | 4.3 L | 7.2 L | 0.0 L * | 1.8 L | 12.3 L | 8.8 L | 12.2 L | 6.66 |
| Nottingham Forest | 16.1 L | 1.4 L | 0.0 L | 0.0 L | 10.0 L | 5.0 L | 0.0 L | 4.64 |
| Sunderland AFC | 5.6 L | 20.3 L | 0.0 L * | 0.4 L | 25.9 L | 9.5 L | 9.4 L | 10.17 |
| Tottenham Hotspur | 11.0 L | 2.3 L | 0.0 L * | 1.5 L | 5.5 L | 4.4 L | 2.1 L | 3.82 |
| West Ham United | 8.7 L | 0.8 L | 0.0 L | 12.9 L | 26.2 L | 3.2 L | 0.5 L | 7.47 |
| Wolverhampton Wanderers | 8.9 L | 0.0 L * | 2.3 L | 0.0 L | 9.8 L | 5.6 L | 8.4 L | 4.99 |

### Club strength correlations

Spearman is the Pearson correlation of average-tie ranks, calculated on the 20 matched clubs. A negative value means higher-value clubs tend to have lower need.

The primary strength proxy is the sum of `market_value_m` over the analysis-season PL team rows, including goalkeepers, mapped from `team_id` to the canonical club names using the same mapping as needs. This follows the project's as-played squad-value convention in §6.3; it is not a fresh Transfermarkt website lookup. Missing values contribute no value to the sum. As a sensitivity check, the second value definition sums unique player IDs selected by `current_club` across all leagues, also including goalkeepers.

| Ambition | Mean need vs as-played value ρ | Mean need vs current-club value ρ | Used-only mean vs as-played value ρ | n | ClubElo ρ |
| --- | --- | --- | --- | --- | --- |
| survive | -0.307 | -0.395 | -0.257 | 20 | N/A (0 ratings) |
| title | -0.651 | -0.704 | -0.620 | 20 | N/A (0 ratings) |

| Club | As-played squad value €m | Current-club unique value €m | Title mean need | Survive mean need |
| --- | --- | --- | --- | --- |
| AFC Bournemouth | 571.75 | 523.75 | 15.70 | 5.94 |
| Arsenal FC | 1280.00 | 1280.00 | 16.88 | 6.09 |
| Aston Villa | 572.18 | 456.50 | 25.96 | 12.81 |
| Brentford FC | 484.53 | 483.20 | 24.07 | 7.62 |
| Brighton & Hove Albion | 548.40 | 512.83 | 21.65 | 6.93 |
| Burnley FC | 223.97 | 213.65 | 31.56 | 12.89 |
| Chelsea FC | 1103.80 | 1143.80 | 10.15 | 2.31 |
| Crystal Palace | 545.80 | 425.28 | 34.19 | 18.57 |
| Everton FC | 433.70 | 413.70 | 26.56 | 13.17 |
| Fulham FC | 354.50 | 283.50 | 28.36 | 13.93 |
| Leeds United | 357.10 | 360.86 | 20.09 | 4.31 |
| Liverpool FC | 908.00 | 945.00 | 17.15 | 9.09 |
| Manchester City | 1307.27 | 1388.30 | 17.76 | 8.30 |
| Manchester United | 748.40 | 732.14 | 21.98 | 9.92 |
| Newcastle United | 692.38 | 694.75 | 17.31 | 6.66 |
| Nottingham Forest | 619.50 | 536.84 | 18.26 | 4.64 |
| Sunderland AFC | 419.30 | 375.20 | 25.63 | 10.17 |
| Tottenham Hotspur | 676.00 | 755.91 | 18.48 | 3.82 |
| West Ham United | 447.67 | 453.61 | 21.52 | 7.47 |
| Wolverhampton Wanderers | 333.25 | 258.25 | 18.35 | 4.99 |

Market value is also an input to the league-strength multiplier, so this check is **not independent external validation** of the needs model. It is a useful sign/rank sanity check, not proof that the scale or bands are calibrated. The primary title correlation remains negative when unused positions are excluded (−0.620).

### ClubElo: requested check could not be completed

No cached ClubElo club ratings were found. An attempt was made to obtain ratings for **2026-07-06**, matching the configured snapshot, without changing project data. On 2026-10-28 the official sources returned:

| Official source attempted | Observed result |
| --- | --- |
| [ClubElo dated CSV over HTTP](http://api.clubelo.com/2026-07-06) | HTTP 502, empty body |
| [ClubElo dated CSV over HTTPS](https://api.clubelo.com/2026-07-06) | Connection timeout after 10 seconds |
| [ClubElo England dated page](http://clubelo.com/2026-07-06/ENG) | Redirect to HTTPS, then HTTP 403 challenge |
| [ClubElo data page](http://clubelo.com/Data) | HTTP 403 challenge |

The existing [HANDOFF](../HANDOFF.md) and §15 also record earlier ClubElo unavailability. **The baseline and all previews have ClubElo correlation N/A, n=0**. Zero was not substituted, and UEFA country coefficients were not used as club Elo. Completing that specific independent check requires accessible date-matched club ratings and an explicit club-name join.

### Ambition monotonicity

All four ambition levels were computed for all 20 clubs, even though only title/survive distributions are requested. Across **420 adjacent comparisons** (140 cells × survive→midtable, midtable→top4, top4→title), **zero scores decreased**, using a tolerance of 1e−9. There are no club × position exceptions to list.

This also follows from the implementation: decreasing k can only increase B_s; for a fixed nonnegative profile S_s and positive B_s, max(0, 1 − S_s/B_s) is nondecreasing. D/A/C, rated membership, median fallback and usage do not change with ambition. Equal scores are expected where no deficit exists or a group is unused.


## 6. Testing percentile-pool compression

These tables use **qualifying players only**, comparing rows whose league is Premier League with all nine other leagues combined. There are **274 PL and 2,258 other qualifying rows** (2,532 unique player IDs), so there is no qualifying-player duplication in this snapshot. For each role, all six configured `*_pct` columns are pooled as equally weighted player-stat observations. They are not minutes-weighted and are not six independent football samples. This is a distribution diagnostic, not an inferential test.

### Role-level distributions of stored _pct values

| Position | Pool | Players | Stat observations | Min | p10 | p25 | Median | p75 | p90 | Max | Mean | % ≥90 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ST | PL | 32 | 192 | 0.3 | 13.8 | 38.7 | 71.2 | 90.3 | 95.7 | 100.0 | 62.3 | 25.5 |
| ST | Other 9 | 303 | 1818 | 0.3 | 10.1 | 24.5 | 48.7 | 72.8 | 88.4 | 100.0 | 48.9 | 8.5 |
| W | PL | 46 | 276 | 0.7 | 20.4 | 42.8 | 67.7 | 87.8 | 96.1 | 100.0 | 63.4 | 22.5 |
| W | Other 9 | 315 | 1890 | 0.3 | 9.1 | 23.4 | 47.6 | 72.6 | 88.4 | 100.0 | 48.2 | 8.5 |
| AM | PL | 21 | 126 | 5.9 | 22.8 | 46.9 | 76.1 | 91.4 | 97.3 | 100.0 | 68.1 | 29.4 |
| AM | Other 9 | 165 | 990 | 0.5 | 9.6 | 23.7 | 47.6 | 71.7 | 87.6 | 100.0 | 48.0 | 7.8 |
| CM | PL | 36 | 216 | 2.4 | 21.4 | 41.4 | 68.1 | 89.8 | 95.4 | 100.0 | 63.9 | 24.5 |
| CM | Other 9 | 336 | 2016 | 0.3 | 9.5 | 23.9 | 48.1 | 73.2 | 88.4 | 100.0 | 48.7 | 8.6 |
| DM | PL | 32 | 192 | 1.1 | 27.8 | 55.1 | 75.6 | 90.4 | 97.4 | 100.0 | 69.3 | 27.1 |
| DM | Other 9 | 240 | 1440 | 0.4 | 9.6 | 23.4 | 46.8 | 71.0 | 87.5 | 100.0 | 47.6 | 8.1 |
| FB | PL | 55 | 330 | 0.9 | 19.6 | 46.7 | 72.8 | 90.3 | 96.4 | 100.0 | 65.4 | 26.4 |
| FB | Other 9 | 412 | 2472 | 0.2 | 9.4 | 23.7 | 47.4 | 71.9 | 87.8 | 100.0 | 48.1 | 7.9 |
| CB | PL | 52 | 312 | 4.6 | 27.2 | 51.0 | 70.8 | 90.6 | 96.8 | 100.0 | 67.4 | 26.0 |
| CB | Other 9 | 487 | 2922 | 0.2 | 9.3 | 23.6 | 47.5 | 72.9 | 88.0 | 100.0 | 48.2 | 8.3 |

### Per-stat distributions

Median and p10/p90 are shown separately to prevent a role-wide pooled median from hiding a particular statistic. All values below are percentiles on the original ten-league scale.

| Position | Stat | PL p10 | PL median | PL p90 | Other p10 | Other median | Other p90 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ST | xg | 12.1 | 75.8 | 96.7 | 10.2 | 47.8 | 86.8 |
| ST | shots | 29.1 | 80.9 | 95.7 | 9.6 | 47.2 | 87.1 |
| ST | xa | 6.8 | 43.0 | 93.6 | 11.1 | 51.0 | 89.5 |
| ST | key_passes | 10.8 | 59.4 | 90.7 | 10.5 | 49.0 | 89.8 |
| ST | successful_dribbles | 27.8 | 66.4 | 97.8 | 9.7 | 47.9 | 89.0 |
| ST | xgot | 15.2 | 77.0 | 94.9 | 9.9 | 48.7 | 87.4 |
| W | xa | 15.2 | 65.5 | 95.3 | 9.5 | 46.8 | 88.5 |
| W | key_passes | 39.6 | 70.2 | 96.3 | 9.0 | 45.7 | 87.8 |
| W | successful_dribbles | 16.4 | 63.5 | 97.1 | 8.9 | 48.8 | 88.3 |
| W | xg | 23.1 | 66.3 | 94.3 | 9.3 | 48.5 | 87.9 |
| W | shots | 38.4 | 76.7 | 94.5 | 9.0 | 46.4 | 88.0 |
| W | big_chances_created | 12.2 | 59.0 | 96.3 | 10.1 | 48.8 | 88.0 |
| AM | xa | 28.5 | 75.8 | 94.6 | 10.4 | 46.2 | 86.3 |
| AM | key_passes | 31.2 | 79.6 | 97.8 | 9.4 | 47.3 | 85.8 |
| AM | xg | 12.9 | 64.0 | 95.2 | 9.9 | 48.9 | 88.8 |
| AM | successful_dribbles | 42.7 | 80.4 | 94.1 | 9.4 | 46.2 | 86.3 |
| AM | accurate_passes_pct | 19.6 | 73.1 | 94.1 | 9.4 | 48.1 | 89.0 |
| AM | shots | 39.2 | 82.3 | 97.8 | 9.4 | 48.1 | 86.3 |
| CM | accurate_passes_pct | 20.4 | 61.4 | 89.2 | 9.2 | 48.8 | 89.9 |
| CM | accurate_long_balls | 15.5 | 56.3 | 95.1 | 10.1 | 49.3 | 88.8 |
| CM | key_passes | 22.8 | 66.3 | 94.8 | 9.3 | 48.0 | 88.6 |
| CM | tackles | 42.5 | 86.2 | 97.6 | 9.8 | 46.6 | 86.2 |
| CM | interceptions | 32.1 | 79.3 | 94.6 | 9.5 | 47.4 | 88.0 |
| CM | xa | 24.6 | 61.6 | 96.2 | 9.5 | 49.1 | 88.6 |
| DM | tackles | 37.9 | 86.9 | 98.8 | 9.5 | 46.3 | 84.2 |
| DM | interceptions | 21.0 | 79.8 | 98.1 | 9.9 | 46.7 | 86.8 |
| DM | ball_recoveries | 38.3 | 81.3 | 97.8 | 9.5 | 46.1 | 86.1 |
| DM | accurate_passes_pct | 15.0 | 61.3 | 91.3 | 9.9 | 49.3 | 89.6 |
| DM | accurate_passes | 49.9 | 82.7 | 94.8 | 9.2 | 45.0 | 86.9 |
| DM | accurate_long_balls | 17.3 | 62.7 | 92.5 | 10.3 | 47.6 | 89.8 |
| FB | tackles | 34.7 | 85.0 | 97.9 | 9.2 | 46.1 | 85.4 |
| FB | interceptions | 33.6 | 76.9 | 97.9 | 9.0 | 46.7 | 86.5 |
| FB | xa | 9.4 | 58.7 | 88.5 | 10.5 | 48.7 | 90.1 |
| FB | key_passes | 17.3 | 69.2 | 93.1 | 9.4 | 47.6 | 88.8 |
| FB | ball_recoveries | 39.3 | 83.5 | 97.3 | 9.2 | 46.1 | 85.4 |
| FB | successful_dribbles | 11.8 | 61.0 | 96.9 | 10.3 | 50.1 | 88.1 |
| CB | blocks | 48.3 | 83.7 | 98.1 | 9.4 | 46.2 | 86.3 |
| CB | clearances | 47.6 | 89.1 | 98.5 | 9.2 | 45.8 | 85.1 |
| CB | interceptions | 28.0 | 68.8 | 97.0 | 9.4 | 48.4 | 88.2 |
| CB | tackles | 26.4 | 70.8 | 94.2 | 9.2 | 46.9 | 89.2 |
| CB | accurate_passes_pct | 13.8 | 54.2 | 92.4 | 9.5 | 49.7 | 89.8 |
| CB | accurate_long_balls | 15.3 | 65.7 | 93.3 | 9.6 | 47.7 | 89.3 |

### Isolating the league multiplier

For this ablation only, each qualifying counting-stat `_adj` is divided by its stored league factor, keeping per-90 values and possession adjustment intact; rate stats remain unchanged. The same ten-league, within-position percentile ranks are then recomputed. These are in-memory alternative percentiles, not modifications to player_season.parquet.

| Position | PL stored median | PL without factor | Other stored median | Other without factor |
| --- | --- | --- | --- | --- |
| ST | 71.19 | 47.16 | 48.66 | 50.30 |
| W | 67.66 | 43.56 | 47.65 | 50.69 |
| AM | 76.08 | 57.26 | 47.58 | 50.00 |
| CM | 68.08 | 53.43 | 48.12 | 49.73 |
| DM | 75.55 | 53.49 | 46.78 | 49.63 |
| FB | 72.81 | 47.43 | 47.43 | 50.54 |
| CB | 70.78 | 48.10 | 47.50 | 50.28 |

Removing the factor reduces PL role medians from **67.66–76.08** to **43.56–57.26**, while other-league medians are close to 50. This demonstrates a large contribution from the league adjustment. It does not prove that the adjustment is wrong: the intended purpose is to recognize league difficulty.

### Does changing the reference pool fix the needs?

Two controlled alternatives keep the original need formula, D/A/C, eligibility, roster membership and thresholds, and recompute club profiles and benchmarks:

1. **PL reference:** rank each qualifying adjusted stat against only the PL players in that position. PL ties use pandas-equivalent average percentile ranks. Other-league rows that belong to current PL squads are mapped to that same empirical PL distribution; values between PL observations use the fraction below them, and exact ties use average ranks. This keeps every squad row on one comparison scale.
2. **No league factor:** use the ablation above, reranking all ten leagues. Possession adjustment remains.

Neither alternative is an implemented proposal to create a second percentile system; any future reference change would need consistent treatment in both needs and ranking.

| Variant | Ambition | Min | p10 | Median | p90 | Max | H | M | L | Need/value ρ | Decreases/420 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Current | survive | 0.00 | 0.00 | 6.67 | 19.31 | 54.06 | 0 | 2 | 138 | -0.307 | 0 |
| Current | title | 0.00 | 9.79 | 20.84 | 34.07 | 64.33 | 2 | 11 | 127 | -0.651 | 0 |
| PL reference | survive | 0.00 | 0.00 | 6.91 | 22.11 | 55.53 | 0 | 2 | 138 | -0.304 | 0 |
| PL reference | title | 0.00 | 14.12 | 27.40 | 38.46 | 70.48 | 2 | 24 | 114 | -0.684 | 0 |
| No league factor | survive | 0.00 | 0.00 | 6.67 | 22.33 | 55.91 | 0 | 2 | 138 | -0.323 | 0 |
| No league factor | title | 0.00 | 14.00 | 28.11 | 39.09 | 68.77 | 2 | 26 | 112 | -0.681 | 0 |

The correlation above uses that row's ambition and the primary as-played squad-value definition. The paired West Ham title results are:

| Position | Current | PL reference | No league factor |
| --- | --- | --- | --- |
| ST | 22.7 L | 26.7 L | 29.7 L |
| W | 14.7 L | 21.9 L | 22.2 L |
| AM | 13.2 L | 23.5 L | 21.3 L |
| CM | 20.8 L | 24.8 L | 24.6 L |
| DM | 42.3 M | 51.6 M | 51.9 M |
| FB | 19.5 L | 27.2 L | 28.5 L |
| CB | 17.5 L | 23.2 L | 23.1 L |

Both alternatives materially increase title gaps and scores, yet **West Ham still has six Low groups and only DM Medium**. Neither produces an ambition reversal. Cause (d) is a contributing factor, but changing the percentile reference alone does not resolve the score ceiling or the missing-player problem.

The role-level lower tails also reject a literal interpretation that PL players are all at the top: substantial low-percentile observations remain. Relative gaps on a percentile scale are a design choice; percentiles are ranks, not a ratio scale of football ability. “Half the percentile” does not mean “half the playing quality.”


## 7. Three candidate formula changes — offline previews only

All three retain the original player percentiles, club benchmarks, eligibility, roster selection, optional-position usage and 35/60 bands. No ranking, data, settings or app output was changed. The constants below are explicit experimental choices, not learned parameters or approved implementation settings. Each candidate was run for all 20 clubs at all four ambition levels.

The objective is to distinguish an ambition-related quality shortfall from secondary depth/age/contract pressure. There is no requirement that every West Ham group be High; raising scores is not evidence of better football decisions.

### A. Make quality the baseline, then add other risks within the remaining range

```text
R = 0.20*D + 0.15*A + 0.15*C
N_A = Q + (1 - Q/100)*R
```

This removes quality's 50-point ceiling. R uses the original non-quality contributions and is at most 50. N_A is bounded by 0–100, nondecreasing in each component, and equals Q when other risks are zero. It retains a limited extra contribution from depth/age/contract without allowing the sum to exceed 100.

**Trade-off:** this changes the meaning and calibration of the score. It is not a probability and has no outcome-based calibration. It preserves quality-blind depth, weak-player averaging and the missing-stat fallback. The existing High/Medium thresholds are held fixed solely to compare behavior.

### B. Candidate A plus ambition-sensitive depth credits

For each unique player i, combine rated league rows by minutes per stat. If a stat is missing, substitute the same median PL-club profile used by the current implementation. Use all selected analysis-season minutes for the base depth credit.

```text
q_i = 100 * mean_s(max(0, B_s - player_pct_i,s) / B_s)
credit_i = min(1, total_minutes_i/900) * (1 - q_i/100)
D_B = clip(100 * (effective_target - sum_i credit_i) / effective_target, 0, 100)
N_B = Q + (1 - Q/100)*(0.20*D_B + 0.15*A + 0.15*C)
```

Q stays the original club-profile quality gap. A player's depth credit decreases as the ambition benchmark rises. The score is bounded and monotone because each q_i is nondecreasing with ambition, D_B is nondecreasing, and the outer formula is increasing in Q and D_B.

**Trade-off:** quality now contributes through both Q and depth. This may double-count a weakness, and low-quality player quantity can still compensate for individual weakness. Unknown percentiles receive a median-profile credit, which is an assumption rather than evidence. Existing current-club/other-team minutes still count. In West Ham DM, title-adjusted credits remain **3.09 for a target of 2**, so D_B is still zero; this variant alone cannot solve that roster/availability question.

### C. Candidate A plus emphasis on the weakest rated regular

Use q_i as defined above, but evaluate only players with ≥900 combined minutes **and at least one rated row**. Weight the mean by their rated minutes.

```text
Q_C = 0.50 * minutes_weighted_mean(q_i of rated regulars)
    + 0.50 * max(q_i of rated regulars)
N_C = Q_C + (1 - Q_C/100)*(0.20*D + 0.15*A + 0.15*C)
```

If no rated regular exists, retain the original Q/fallback. Unused groups stay zero; empty used groups retain full D/Q. D, A and C otherwise stay at baseline. Eligibility does not change by ambition, so both the maximum and the mean are nondecreasing as B rises.

**Trade-off:** this makes one weak rated regular influential even if they are a reserve or their role differs from others in the group. The maximum is sensitive to noise, and unrated regulars remain invisible. It deliberately does not claim to select a starting XI. A genuine starter or low-quantile model would need validated availability/lineup information and an explicit coverage policy.

### West Ham before/after: all four ambitions

Each cell shows score and H/M/L band. The current column is the existing implementation; A/B/C are independent alternatives, with B and C each building on A as described above.

#### survive: formula previews

| Position | Current | A: quality baseline | B: ambition depth | C: weakest regular |
| --- | --- | --- | --- | --- |
| ST | 8.7 L | 8.7 L | 8.7 L | 8.7 L |
| W | 0.8 L | 0.8 L | 0.8 L | 0.8 L |
| AM | 0.0 L | 0.0 L | 0.0 L | 0.0 L |
| CM | 12.9 L | 12.9 L | 12.9 L | 12.9 L |
| DM | 26.2 L | 35.7 M | 35.7 M | 44.1 M |
| FB | 3.2 L | 5.0 L | 7.9 L | 26.9 L |
| CB | 0.5 L | 0.9 L | 1.1 L | 24.0 L |

#### midtable: formula previews

| Position | Current | A: quality baseline | B: ambition depth | C: weakest regular |
| --- | --- | --- | --- | --- |
| ST | 16.1 L | 22.2 L | 22.2 L | 22.2 L |
| W | 3.1 L | 5.3 L | 5.3 L | 13.4 L |
| AM | 0.0 L | 0.0 L | 0.0 L | 0.0 L |
| CM | 13.6 L | 14.2 L | 14.4 L | 14.2 L |
| DM | 35.5 M | 51.9 M | 51.9 M | 59.0 M |
| FB | 11.4 L | 21.3 L | 24.7 L | 34.3 L |
| CB | 5.9 L | 11.6 L | 12.6 L | 28.9 L |

#### top4: formula previews

| Position | Current | A: quality baseline | B: ambition depth | C: weakest regular |
| --- | --- | --- | --- | --- |
| ST | 19.5 L | 28.5 L | 28.5 L | 28.5 L |
| W | 9.5 L | 18.0 L | 20.4 L | 25.2 L |
| AM | 7.7 L | 15.3 L | 15.3 L | 15.3 L |
| CM | 16.3 L | 18.9 L | 20.5 L | 18.9 L |
| DM | 40.7 M | 60.8 H | 60.8 H | 65.6 H |
| FB | 16.7 L | 31.7 L | 35.8 M | 39.6 M |
| CB | 14.1 L | 27.9 L | 30.7 L | 36.9 M |

#### title: formula previews

| Position | Current | A: quality baseline | B: ambition depth | C: weakest regular |
| --- | --- | --- | --- | --- |
| ST | 22.7 L | 34.3 L | 34.3 L | 34.3 L |
| W | 14.7 L | 28.3 L | 31.7 L | 32.3 L |
| AM | 13.2 L | 26.5 L | 26.5 L | 26.5 L |
| CM | 20.8 L | 26.6 L | 29.3 L | 26.6 L |
| DM | 42.3 M | 63.7 H | 63.7 H | 68.1 H |
| FB | 19.5 L | 37.3 M | 41.6 M | 43.2 M |
| CB | 17.5 L | 34.7 L | 38.0 M | 41.0 M |

### Why the title previews differ

| Position | Current Q | Current D | B adjusted depth credits | B D | C Q |
| --- | --- | --- | --- | --- | --- |
| ST | 28.01 | 0.00 | 2.85 | 0.00 | 28.01 |
| W | 27.70 | 0.00 | 2.29 | 23.68 | 31.77 |
| AM | 26.48 | 0.00 | 0.96 | 0.00 | 26.48 |
| CM | 15.77 | 27.52 | 1.69 | 43.67 | 15.77 |
| DM | 58.19 | 0.00 | 3.09 | 0.00 | 63.27 |
| FB | 36.40 | 6.69 | 2.38 | 40.55 | 42.40 |
| CB | 34.53 | 0.00 | 2.99 | 25.34 | 40.88 |

Candidate A makes DM High and FB Medium. B additionally makes CB Medium because its ambition-adjusted depth is insufficient. C also makes CB Medium and increases the DM/FB gaps by emphasizing weaker rated regulars. None resolves the AM evidence gap; its unchanged underlying Q remains an imputed value.

### League-wide before/after distributions

All rows use the same 140 cells and five unused zeros. Bands still use unrounded scores; rounding a displayed number to a threshold does not alter its band.

| Variant | Ambition | Min | p10 | Median | p90 | Max | High | Medium | Low |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Current | survive | 0.00 | 0.00 | 6.67 | 19.31 | 54.06 | 0 | 2 | 138 |
| Current | title | 0.00 | 9.79 | 20.84 | 34.07 | 64.33 | 2 | 11 | 127 |
| A | survive | 0.00 | 0.00 | 7.37 | 22.51 | 58.70 | 0 | 5 | 135 |
| A | title | 0.00 | 18.34 | 33.81 | 49.95 | 73.62 | 6 | 54 | 80 |
| B | survive | 0.00 | 0.00 | 8.76 | 23.12 | 60.21 | 1 | 5 | 134 |
| B | title | 0.00 | 20.35 | 35.75 | 53.10 | 75.06 | 7 | 70 | 63 |
| C | survive | 0.00 | 1.72 | 15.50 | 34.09 | 58.70 | 0 | 14 | 126 |
| C | title | 0.00 | 19.56 | 37.51 | 58.25 | 73.62 | 12 | 66 | 62 |

### League-wide rank and monotonicity checks

| Variant | Ambition | Need/as-played value ρ | Need/current-club value ρ | Used-only need/as-played value ρ | Matched clubs | ClubElo ρ |
| --- | --- | --- | --- | --- | --- | --- |
| Current | survive | -0.307 | -0.395 | -0.257 | 20 | N/A |
| Current | title | -0.651 | -0.704 | -0.620 | 20 | N/A |
| A | survive | -0.311 | -0.397 | -0.332 | 20 | N/A |
| A | title | -0.752 | -0.774 | -0.734 | 20 | N/A |
| B | survive | -0.325 | -0.402 | -0.347 | 20 | N/A |
| B | title | -0.747 | -0.770 | -0.741 | 20 | N/A |
| C | survive | -0.519 | -0.529 | -0.532 | 20 | N/A |
| C | title | -0.732 | -0.731 | -0.755 | 20 | N/A |

| Variant | Adjacent ambition decreases | Comparisons | Unused cells preserved | Observed range across title/survive |
| --- | --- | --- | --- | --- |
| Current | 0 | 420 | 5 | 0.00–64.33 |
| A | 0 | 420 | 5 | 0.00–73.62 |
| B | 0 | 420 | 5 | 0.00–75.06 |
| C | 0 | 420 | 5 | 0.00–73.62 |

All three strengthen the negative title correlation with the primary value proxy compared with −0.651, but that is a small, related-data sanity check on **20 clubs**, not a model-selection target. ClubElo remains unavailable for every variant. Candidate C also raises survive needs appreciably (median **15.50**, 14 Medium vs baseline median 6.67, 2 Medium), showing the cost of emphasizing the weakest rated player rather than typical team strength.

### Club mean title need: before/after

| Club | Current | A | B | C |
| --- | --- | --- | --- | --- |
| AFC Bournemouth | 15.70 | 25.30 | 27.33 | 31.61 |
| Arsenal FC | 16.88 | 27.81 | 30.24 | 32.13 |
| Aston Villa | 25.96 | 37.96 | 40.44 | 40.96 |
| Brentford FC | 24.07 | 38.83 | 41.63 | 44.00 |
| Brighton & Hove Albion | 21.65 | 35.20 | 38.45 | 41.48 |
| Burnley FC | 31.56 | 49.78 | 52.67 | 55.03 |
| Chelsea FC | 10.15 | 18.16 | 19.99 | 22.39 |
| Crystal Palace | 34.19 | 48.12 | 50.33 | 49.51 |
| Everton FC | 26.56 | 40.62 | 43.56 | 44.69 |
| Fulham FC | 28.36 | 40.16 | 43.65 | 42.71 |
| Leeds United | 20.09 | 34.69 | 37.12 | 38.74 |
| Liverpool FC | 17.15 | 24.90 | 27.60 | 26.81 |
| Manchester City | 17.76 | 26.43 | 27.71 | 31.43 |
| Manchester United | 21.98 | 32.10 | 34.31 | 34.73 |
| Newcastle United | 17.31 | 27.45 | 29.31 | 32.56 |
| Nottingham Forest | 18.26 | 31.94 | 34.48 | 35.89 |
| Sunderland AFC | 25.63 | 43.20 | 45.93 | 46.88 |
| Tottenham Hotspur | 18.48 | 34.34 | 35.43 | 41.78 |
| West Ham United | 21.52 | 35.89 | 37.86 | 38.85 |
| Wolverhampton Wanderers | 18.35 | 32.23 | 34.49 | 37.03 |

### Suggested next experiment, without implementation

A is the clearest first formula experiment because it addresses the score ceiling while leaving the observed quality evidence visible. Before selecting or tuning it, clarify whether “need” means shortfall against ambition, urgency to recruit, or both; establish a policy for unrated players and current-club availability. An explicit “insufficient quality evidence” state would be more honest than treating West Ham AM's fallback as a measured assessment.

B is useful if ambition-adjusted squad depth is the intended concept, but its credit/imputation rule needs validation. C tests sensitivity to weaker regulars and should not become a starter model without lineup evidence. Compare any approved change against independent club strength and subsequent recruitment/performance evidence; do not tune thresholds merely to make West Ham red or maximize these 20-club correlations. The current guide's one-percentile-system rule would also need to be preserved in any later reference-pool experiment.


## 8. Reproducibility and verification

Inputs were the existing `data/processed/player_season.parquet`, `coverage.json`, and `config/settings.yaml`. The loaded settings were copied **in memory** with the final `coverage["position_stats"]`, then with each of `survive`, `midtable`, `top4`, and `title`. `needs.league_clubs` supplied the 20 canonical club names. The baseline called the existing `needs.compute_needs` for each club/ambition; no replacement implementation was used for baseline numbers.

The baseline can be reproduced from the repository root using its virtual environment and the following read-only Python calculation (display only; do not run a pipeline stage to reproduce it):

```python
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")
from scout import needs
from scout.config import load_settings

players = pd.read_parquet("data/processed/player_season.parquet")
coverage = json.loads(Path("data/processed/coverage.json").read_text())
settings = load_settings().model_copy(
    update={"position_stats": coverage["position_stats"]}
)
clubs = needs.league_clubs(players, settings.target_league)
tables = {
    ambition: pd.concat(
        [
            needs.compute_needs(
                players, club, settings.model_copy(update={"ambition": ambition})
            )
            for club in clubs
        ],
        ignore_index=True,
    )
    for ambition in ("survive", "midtable", "top4", "title")
}
print(pd.concat(tables.values(), ignore_index=True).to_string(index=False))
```

For the report's percentile tables, reshape the six role-specific percentile columns from qualifying rows and calculate pandas quantiles, separately for PL and other leagues. For the candidate previews, apply the explicit equations in section 7 to the same baseline rows and player profiles; do not change or persist the input tables. All computation used unrounded values; figures in this document are rounded only for presentation.

Verification completed during this diagnosis:

- Fresh top4 baseline versus the existing `needs.parquet`: **140 matched club-position cells, maximum absolute score difference 0.0**.
- Existing regression suite via `.venv\Scripts\python.exe -m pytest -q`: **72 passed in 6.72 s**, exit 0.
- Existing lint check via `.venv\Scripts\python.exe -m ruff check .`: **All checks passed**, exit 0.
- Baseline, both percentile counterfactuals and all three candidate formulas: **zero decreases across 420 adjacent ambition comparisons each**.
- SHA-256 verification of **41 existing source/configuration/test/script/processed-input files** found **no changes** after the calculations and checks.
- The pipeline portion of HANDOFF's resume command was intentionally not run: it can rewrite processed outputs, and this task requested diagnosis only. The exact cached-output comparison above verifies the current needs computation without that mutation.

Key input/source fingerprints:

| File | SHA-256 |
| --- | --- |
| data/processed/player_season.parquet | 62bb3d14f6de55e781127330cfd5c9d2d86bc4250f9b4f842da721b09bd67278 |
| data/processed/coverage.json | f45638ab887a72b1a0d921660b12ea9bc52894bb7cbd8712e8e29651152b0b11 |
| config/settings.yaml | 910f92bc58a1532f97c2b9d5e059bb41ccb8a26fe02c8a85992748a2152e59de |
| src/scout/needs.py | cb6c2fa094c25ef31c3bce73541ebc3dc9958f5dacf883334524853d43146615 |
| src/scout/features.py | 5afdab36844e424fecae157ff816e533f1769be1ecfd431ec59f29d6fb8e9973 |

**Deliverable:** this diagnosis document only. No candidate is implemented, and no documentation outside this file is updated. The outstanding requested measurement is the ClubElo correlation, which remains unavailable for the reasons recorded in section 5.


