# V0 report examples

Actual generated reports, copied verbatim with exact fact-key citations. Numeric verification is not semantic validation.

## Equi Fernández (DM)

Model: dots-studio/dots-3-note-preview:free

Summary: Equi Fernández is a 23-year-old defensive midfielder with a fit score of 91.5. He offers a 26.7 upgrade margin for West Ham's title ambition.

### Strengths

- Outstanding defensive metrics, including 99th percentile ball recoveries and 97th percentile tackles. — stats.ball_recoveries.pct, stats.tackles.pct

- Strong passing with 97th percentile accurate passes and 89th percentile long balls. — stats.accurate_passes.pct, stats.accurate_long_balls.pct

- Ranked first with a fit score of 91.5 and perfect age score. — fit.rank, fit.score, fit.age_score

### Risks

- Small sample size of 987 minutes across 20 matches limits statistical reliability. — player.small_sample, player.minutes, player.matches

- Currently below the ambition benchmark of 98.8 composite fit. — fit.below_ambition_benchmark, fit.benchmark_composite

Numeric verification: 11/11; automated flag: False

## Hugo Bueno (FB)

Model: dots-studio/dots-3-note-preview:free

Summary: Hugo Bueno is a 23‑year‑old left‑back with 89th‑percentile tackles, 92nd‑percentile interceptions, 94th‑percentile key passes and 96th‑percentile dribbles, and a fit score of 90.9 ranked first. However, he falls below the 89.0 composite ambition benchmark and his contract ends in 23.8 months.

### Strengths

- Tackles and interceptions are in the 89th and 92nd percentiles respectively. — stats.tackles.pct, stats.interceptions.pct

- Key passes and successful dribbles rank in the 94th and 96th percentiles. — stats.key_passes.pct, stats.successful_dribbles.pct

- Overall fit score is 90.9, rank 1, with perfect age and high value scores. — fit.score, fit.rank, fit.age_score, fit.value_score

### Risks

- Despite high scores, the player falls below the 89.0 composite benchmark for title ambition. — fit.below_ambition_benchmark, fit.benchmark_composite

- With 23.8 months remaining, contract uncertainty could affect long‑term planning. — player.contract_months_left

Numeric verification: 16/16; automated flag: False

## Manual-review limitation

Equi calls the benchmark performance composite a fit score. In another cached report, Nico describes an upgrade in percent rather than percentile points. Contract/planning judgments are also not established by numeric checks. These outputs are preserved, not silently rewritten; a human should review units and judgments before recruitment use.