# Quality estimator experiment: pre-registration

Hypothesis: defensive volume can reflect team style more than player quality. Stat selection below used
no points, PPG, goals conceded, goal difference or standings of either season.

## Frozen protocol

- Timebox: 90 minutes of experiment execution after registration commit. Evaluate V0 and V1 once;
  V2 once only if actual Sofascore ratings can be obtained within the source-access check.
- V0 is the current six-stat sets. V1 selects six distinct base statistics per position using the sum of
  descending-repeatability rank and ascending-absolute-possession-correlation rank (equal criterion weight).
  Break ties by higher repeatability, lower absolute style correlation, then lexical stat name.
  Keep only stats passing the existing 95% per-league pool coverage rule in both seasons.
  Consider at most one definition per base statistic, greedily in that fixed order; no correlated
  duplicate definitions of the same stat may fill multiple slots.
- Repeatability: player-level Spearman 2024-25 versus 2025-26 for players passing the minutes rule
  in both seasons; combine observed same-season rows by minutes. Do not add a matches filter
  to this selection cohort; missing stat pairs are excluded and paired n is shown.
- Style: absolute Spearman with team possession in 2024-25 among minutes-eligible role rows.
- Candidate universes are football-role lists in scripts/quality_experiment.py, fixed before calibration.
  No stat is chosen by a club outcome. Current definitions retain existing league and possession adjustment.
  Defensive raw alternatives remove the existing opponent-possession adjustment. Other counting-stat
  alternatives divide by team possession relative to 0.5. Pass accuracy remains a success rate.
- Actual tackle-success %, duel-win % and aerial-win % cannot be reconstructed: denominators are absent
  in the downloaded source. They are unavailable candidates, not zero values.
- V2 = V1 plus Sofascore average rating. No Sofascore ratings are cached, and the installed-adapter
  season endpoint failed its single live availability check. V2 is therefore UNAVAILABLE, not substituted
  with FotMob rating, not treated as V1, and not counted as passing or failing.
- Keep original qualifying flags/cohort and existing percentile columns exactly unchanged. Derived
  definitions receive percentile ranks within the SAME qualifying role pool. There is one percentile
  system per variant for squad and targets; no PL-only reference or relaxed eligibility.
- Candidate A, urgency coefficients, evidence rules, bands, target filters/upgrade margins, and
  acceptance a-e stay fixed. Production files and V0 reports are not overwritten by V1.
- Run existing backtest and ten fixed sensitivity perturbations for each available variant.
  Sensitivity perturbations are diagnostics, not extra quality variants or tuning.
- Bias = share of West Ham/title shortlist rows from the six highest-value clubs in the ORIGINAL
  qualifying pool: sum market values of unique qualifying player IDs by current_club, all ages/positions.
  Fix those six club names before evaluating V0/V1; do not redefine for each shortlist.
- STOP: if no alternative passes b without failing another check OR increasing bias over V0,
  retain V0 and document b as a limitation. No additional variants, thresholds or outcome-driven
  reselection in this session. Otherwise recommend the passing alternative and wait for user approval.
- 2025-26 is NOT an untouched holdout: its aggregate calibration was already inspected, and its
  player stat values are explicitly used in the requested repeatability criterion.

## Frozen stat sets

| position | V0 | V1 | V2 |
| --- | --- | --- | --- |
| ST | xg, shots, xa, key_passes, successful_dribbles, xgot | successful_dribbles, shots__per_possession, key_passes__per_possession, xa__per_possession, accurate_passes_pct, xg__per_possession | Unavailable |
| W | xa, key_passes, successful_dribbles, xg, shots, big_chances_created | successful_dribbles__per_possession, shots__per_possession, accurate_passes__per_possession, accurate_long_balls__per_possession, key_passes__per_possession, xg__per_possession | Unavailable |
| AM | xa, key_passes, xg, successful_dribbles, accurate_passes_pct, shots | successful_dribbles, accurate_passes__per_possession, accurate_long_balls, shots__per_possession, key_passes__per_possession, possession_won_final_third__per_possession | Unavailable |
| CM | accurate_passes_pct, accurate_long_balls, key_passes, tackles, interceptions, xa | accurate_long_balls__per_possession, tackles__raw, successful_dribbles, key_passes__per_possession, ball_recoveries__raw, xa__per_possession | Unavailable |
| DM | tackles, interceptions, ball_recoveries, accurate_passes_pct, accurate_passes, accurate_long_balls | accurate_long_balls__per_possession, ball_recoveries__raw, tackles__raw, key_passes__per_possession, xa__per_possession, clearances | Unavailable |
| FB | tackles, interceptions, xa, key_passes, ball_recoveries, successful_dribbles | ball_recoveries__raw, successful_dribbles__per_possession, key_passes__per_possession, defensive_actions, accurate_long_balls, xa__per_possession | Unavailable |
| CB | blocks, clearances, interceptions, tackles, accurate_passes_pct, accurate_long_balls | clearances, accurate_long_balls, tackles__raw, accurate_passes__per_possession, defensive_actions, key_passes__per_possession | Unavailable |

## Every available candidate and selection criterion

| position | stat | base | definition | paired_players | repeatability | abs_possession_rho | min_coverage | selected |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ST | accurate_passes_pct | accurate_passes_pct | current | 166 | 0.7859 | 0.4169 | 1.0000 | True |
| ST | assists | assists | current | 181 | 0.3038 | 0.3284 | 1.0000 | False |
| ST | assists__per_possession | assists | own_possession | 181 | 0.2681 | 0.2022 | 1.0000 | False |
| ST | big_chances_created | big_chances_created | current | 181 | 0.3223 | 0.3621 | 1.0000 | False |
| ST | big_chances_created__per_possession | big_chances_created | own_possession | 181 | 0.2690 | 0.2215 | 1.0000 | False |
| ST | goals | goals | current | 181 | 0.4407 | 0.4193 | 1.0000 | False |
| ST | goals__per_possession | goals | own_possession | 181 | 0.3782 | 0.2284 | 1.0000 | False |
| ST | key_passes | key_passes | current | 181 | 0.6328 | 0.2821 | 1.0000 | False |
| ST | key_passes__per_possession | key_passes | own_possession | 181 | 0.5718 | 0.0278 | 1.0000 | True |
| ST | shots | shots | current | 166 | 0.6993 | 0.3326 | 1.0000 | False |
| ST | shots__per_possession | shots | own_possession | 166 | 0.6486 | 0.0068 | 1.0000 | True |
| ST | successful_dribbles | successful_dribbles | current | 166 | 0.6530 | 0.0150 | 1.0000 | True |
| ST | successful_dribbles__per_possession | successful_dribbles | own_possession | 166 | 0.6326 | 0.1810 | 1.0000 | False |
| ST | xa | xa | current | 181 | 0.5773 | 0.3227 | 1.0000 | False |
| ST | xa__per_possession | xa | own_possession | 181 | 0.5521 | 0.1547 | 1.0000 | True |
| ST | xg | xg | current | 181 | 0.5932 | 0.4654 | 1.0000 | False |
| ST | xg__per_possession | xg | own_possession | 181 | 0.5484 | 0.2273 | 1.0000 | True |
| ST | xgot | xgot | current | 181 | 0.4923 | 0.4134 | 1.0000 | False |
| ST | xgot__per_possession | xgot | own_possession | 181 | 0.4301 | 0.1946 | 1.0000 | False |
| W | accurate_long_balls | accurate_long_balls | current | 203 | 0.7180 | 0.1617 | 1.0000 | False |
| W | accurate_long_balls__per_possession | accurate_long_balls | own_possession | 203 | 0.6858 | 0.0234 | 1.0000 | True |
| W | accurate_passes | accurate_passes | current | 203 | 0.8420 | 0.4442 | 1.0000 | False |
| W | accurate_passes__per_possession | accurate_passes | own_possession | 203 | 0.8161 | 0.1536 | 1.0000 | True |
| W | accurate_passes_pct | accurate_passes_pct | current | 203 | 0.7031 | 0.4277 | 1.0000 | False |
| W | assists | assists | current | 214 | 0.2598 | 0.3021 | 1.0000 | False |
| W | assists__per_possession | assists | own_possession | 214 | 0.2126 | 0.1569 | 1.0000 | False |
| W | big_chances_created | big_chances_created | current | 214 | 0.3852 | 0.2674 | 1.0000 | False |
| W | big_chances_created__per_possession | big_chances_created | own_possession | 214 | 0.3320 | 0.0959 | 1.0000 | False |
| W | goals | goals | current | 214 | 0.3745 | 0.3240 | 1.0000 | False |
| W | goals__per_possession | goals | own_possession | 214 | 0.3268 | 0.1720 | 1.0000 | False |
| W | key_passes | key_passes | current | 214 | 0.6351 | 0.2713 | 1.0000 | False |
| W | key_passes__per_possession | key_passes | own_possession | 214 | 0.5669 | 0.0129 | 1.0000 | True |
| W | possession_won_final_third | possession_won_final_third | current | 203 | 0.3578 | 0.1566 | 1.0000 | False |
| W | possession_won_final_third__per_possession | possession_won_final_third | own_possession | 203 | 0.2942 | 0.1140 | 1.0000 | False |
| W | shots | shots | current | 203 | 0.7158 | 0.2859 | 1.0000 | False |
| W | shots__per_possession | shots | own_possession | 203 | 0.6940 | 0.0171 | 1.0000 | True |
| W | successful_dribbles | successful_dribbles | current | 203 | 0.7646 | 0.1728 | 1.0000 | False |
| W | successful_dribbles__per_possession | successful_dribbles | own_possession | 203 | 0.7237 | 0.0363 | 1.0000 | True |
| W | xa | xa | current | 214 | 0.6293 | 0.3525 | 1.0000 | False |
| W | xa__per_possession | xa | own_possession | 214 | 0.5972 | 0.1420 | 1.0000 | False |
| W | xg | xg | current | 214 | 0.6085 | 0.2797 | 1.0000 | False |
| W | xg__per_possession | xg | own_possession | 214 | 0.5932 | 0.0639 | 1.0000 | True |
| W | xgot | xgot | current | 214 | 0.4691 | 0.3137 | 1.0000 | False |
| W | xgot__per_possession | xgot | own_possession | 214 | 0.4285 | 0.1313 | 1.0000 | False |
| AM | accurate_long_balls | accurate_long_balls | current | 113 | 0.7910 | 0.1302 | 1.0000 | True |
| AM | accurate_long_balls__per_possession | accurate_long_balls | own_possession | 113 | 0.7575 | 0.0625 | 1.0000 | False |
| AM | accurate_passes | accurate_passes | current | 113 | 0.8747 | 0.3582 | 1.0000 | False |
| AM | accurate_passes__per_possession | accurate_passes | own_possession | 113 | 0.8463 | 0.0800 | 1.0000 | True |
| AM | accurate_passes_pct | accurate_passes_pct | current | 113 | 0.6802 | 0.3889 | 1.0000 | False |
| AM | assists | assists | current | 121 | 0.4038 | 0.2524 | 1.0000 | False |
| AM | assists__per_possession | assists | own_possession | 121 | 0.3449 | 0.1117 | 1.0000 | False |
| AM | big_chances_created | big_chances_created | current | 121 | 0.5710 | 0.3317 | 1.0000 | False |
| AM | big_chances_created__per_possession | big_chances_created | own_possession | 121 | 0.5097 | 0.1808 | 1.0000 | False |
| AM | goals | goals | current | 121 | 0.4304 | 0.3532 | 1.0000 | False |
| AM | goals__per_possession | goals | own_possession | 121 | 0.3459 | 0.1974 | 1.0000 | False |
| AM | key_passes | key_passes | current | 121 | 0.6807 | 0.2781 | 1.0000 | False |
| AM | key_passes__per_possession | key_passes | own_possession | 121 | 0.5853 | 0.0202 | 1.0000 | True |
| AM | possession_won_final_third | possession_won_final_third | current | 113 | 0.5636 | 0.2817 | 1.0000 | False |
| AM | possession_won_final_third__per_possession | possession_won_final_third | own_possession | 113 | 0.5497 | 0.0292 | 1.0000 | True |
| AM | shots | shots | current | 113 | 0.7768 | 0.3244 | 1.0000 | False |
| AM | shots__per_possession | shots | own_possession | 113 | 0.6766 | 0.0336 | 1.0000 | True |
| AM | successful_dribbles | successful_dribbles | current | 113 | 0.7631 | 0.0015 | 1.0000 | True |
| AM | successful_dribbles__per_possession | successful_dribbles | own_possession | 113 | 0.7194 | 0.1819 | 1.0000 | False |
| AM | xa | xa | current | 121 | 0.6977 | 0.3920 | 1.0000 | False |
| AM | xa__per_possession | xa | own_possession | 121 | 0.6405 | 0.2114 | 1.0000 | False |
| AM | xg | xg | current | 121 | 0.6472 | 0.3714 | 1.0000 | False |
| AM | xg__per_possession | xg | own_possession | 121 | 0.5871 | 0.1674 | 1.0000 | False |
| AM | xgot | xgot | current | 121 | 0.5391 | 0.3698 | 1.0000 | False |
| AM | xgot__per_possession | xgot | own_possession | 121 | 0.4771 | 0.1899 | 1.0000 | False |
| CM | accurate_long_balls | accurate_long_balls | current | 230 | 0.7298 | 0.2230 | 1.0000 | False |
| CM | accurate_long_balls__per_possession | accurate_long_balls | own_possession | 230 | 0.7017 | 0.0213 | 1.0000 | True |
| CM | accurate_passes | accurate_passes | current | 230 | 0.8793 | 0.5491 | 1.0000 | False |
| CM | accurate_passes__per_possession | accurate_passes | own_possession | 230 | 0.8617 | 0.3018 | 1.0000 | False |
| CM | accurate_passes_pct | accurate_passes_pct | current | 230 | 0.7977 | 0.6110 | 1.0000 | False |
| CM | assists | assists | current | 243 | 0.4657 | 0.2585 | 1.0000 | False |
| CM | assists__per_possession | assists | own_possession | 243 | 0.4244 | 0.1528 | 1.0000 | False |
| CM | ball_recoveries | ball_recoveries | current | 230 | 0.7889 | 0.4731 | 1.0000 | False |
| CM | ball_recoveries__raw | ball_recoveries | raw | 230 | 0.7267 | 0.1154 | 1.0000 | True |
| CM | big_chances_created | big_chances_created | current | 243 | 0.5852 | 0.2680 | 1.0000 | False |
| CM | big_chances_created__per_possession | big_chances_created | own_possession | 243 | 0.5532 | 0.1365 | 1.0000 | False |
| CM | blocks | blocks | current | 230 | 0.4644 | 0.0954 | 1.0000 | False |
| CM | blocks__raw | blocks | raw | 230 | 0.4636 | 0.0505 | 1.0000 | False |
| CM | clearances | clearances | current | 230 | 0.5675 | 0.0508 | 1.0000 | False |
| CM | clearances__raw | clearances | raw | 230 | 0.5631 | 0.1968 | 1.0000 | False |
| CM | defensive_actions | defensive_actions | current | 230 | 0.7015 | 0.1969 | 1.0000 | False |
| CM | defensive_actions__raw | defensive_actions | raw | 230 | 0.6636 | 0.1477 | 1.0000 | False |
| CM | goals | goals | current | 243 | 0.3932 | 0.2202 | 1.0000 | False |
| CM | goals__per_possession | goals | own_possession | 243 | 0.3702 | 0.1204 | 1.0000 | False |
| CM | interceptions | interceptions | current | 230 | 0.6359 | 0.1823 | 1.0000 | False |
| CM | interceptions__raw | interceptions | raw | 230 | 0.6004 | 0.0644 | 1.0000 | False |
| CM | key_passes | key_passes | current | 243 | 0.6904 | 0.2142 | 1.0000 | False |
| CM | key_passes__per_possession | key_passes | own_possession | 243 | 0.6436 | 0.0039 | 1.0000 | True |
| CM | possession_won_final_third | possession_won_final_third | current | 230 | 0.4297 | 0.1781 | 1.0000 | False |
| CM | possession_won_final_third__per_possession | possession_won_final_third | own_possession | 230 | 0.3804 | 0.0468 | 1.0000 | False |
| CM | shots | shots | current | 230 | 0.6950 | 0.1141 | 1.0000 | False |
| CM | shots__per_possession | shots | own_possession | 230 | 0.6691 | 0.1127 | 1.0000 | False |
| CM | successful_dribbles | successful_dribbles | current | 230 | 0.6569 | 0.0209 | 1.0000 | True |
| CM | successful_dribbles__per_possession | successful_dribbles | own_possession | 230 | 0.6463 | 0.1623 | 1.0000 | False |
| CM | tackles | tackles | current | 230 | 0.7383 | 0.2166 | 1.0000 | False |
| CM | tackles__raw | tackles | raw | 230 | 0.7064 | 0.0933 | 1.0000 | True |
| CM | xa | xa | current | 243 | 0.7194 | 0.2903 | 1.0000 | False |
| CM | xa__per_possession | xa | own_possession | 243 | 0.6960 | 0.1081 | 1.0000 | True |
| CM | xg | xg | current | 243 | 0.6099 | 0.1512 | 1.0000 | False |
| CM | xg__per_possession | xg | own_possession | 243 | 0.6080 | 0.0100 | 1.0000 | False |
| CM | xgot | xgot | current | 243 | 0.4992 | 0.1918 | 1.0000 | False |
| CM | xgot__per_possession | xgot | own_possession | 243 | 0.4827 | 0.0621 | 1.0000 | False |
| DM | accurate_long_balls | accurate_long_balls | current | 177 | 0.6967 | 0.1861 | 1.0000 | False |
| DM | accurate_long_balls__per_possession | accurate_long_balls | own_possession | 177 | 0.6849 | 0.0552 | 1.0000 | True |
| DM | accurate_passes | accurate_passes | current | 177 | 0.7990 | 0.5554 | 1.0000 | False |
| DM | accurate_passes__per_possession | accurate_passes | own_possession | 177 | 0.7489 | 0.2839 | 1.0000 | False |
| DM | accurate_passes_pct | accurate_passes_pct | current | 177 | 0.7281 | 0.5685 | 1.0000 | False |
| DM | ball_recoveries | ball_recoveries | current | 177 | 0.7670 | 0.4502 | 1.0000 | False |
| DM | ball_recoveries__raw | ball_recoveries | raw | 177 | 0.6685 | 0.0789 | 1.0000 | True |
| DM | blocks | blocks | current | 177 | 0.4829 | 0.0081 | 1.0000 | False |
| DM | blocks__raw | blocks | raw | 177 | 0.4652 | 0.2161 | 1.0000 | False |
| DM | clearances | clearances | current | 177 | 0.6032 | 0.0821 | 1.0000 | True |
| DM | clearances__raw | clearances | raw | 177 | 0.5794 | 0.1857 | 1.0000 | False |
| DM | defensive_actions | defensive_actions | current | 177 | 0.6915 | 0.2020 | 1.0000 | False |
| DM | defensive_actions__raw | defensive_actions | raw | 177 | 0.6600 | 0.1905 | 1.0000 | False |
| DM | interceptions | interceptions | current | 177 | 0.5417 | 0.1621 | 1.0000 | False |
| DM | interceptions__raw | interceptions | raw | 177 | 0.5173 | 0.1366 | 1.0000 | False |
| DM | key_passes | key_passes | current | 188 | 0.5923 | 0.2358 | 1.0000 | False |
| DM | key_passes__per_possession | key_passes | own_possession | 188 | 0.5744 | 0.0449 | 1.0000 | True |
| DM | possession_won_final_third | possession_won_final_third | current | 177 | 0.3770 | 0.1332 | 1.0000 | False |
| DM | possession_won_final_third__per_possession | possession_won_final_third | own_possession | 177 | 0.3367 | 0.0816 | 1.0000 | False |
| DM | successful_dribbles | successful_dribbles | current | 177 | 0.4935 | 0.0262 | 1.0000 | False |
| DM | successful_dribbles__per_possession | successful_dribbles | own_possession | 177 | 0.4796 | 0.1929 | 1.0000 | False |
| DM | tackles | tackles | current | 177 | 0.7363 | 0.2290 | 1.0000 | False |
| DM | tackles__raw | tackles | raw | 177 | 0.6950 | 0.0942 | 1.0000 | True |
| DM | xa | xa | current | 188 | 0.6432 | 0.2699 | 1.0000 | False |
| DM | xa__per_possession | xa | own_possession | 188 | 0.6181 | 0.0903 | 1.0000 | True |
| FB | accurate_long_balls | accurate_long_balls | current | 290 | 0.5909 | 0.0082 | 1.0000 | True |
| FB | accurate_long_balls__per_possession | accurate_long_balls | own_possession | 290 | 0.5567 | 0.2342 | 1.0000 | False |
| FB | accurate_passes | accurate_passes | current | 290 | 0.8065 | 0.5613 | 1.0000 | False |
| FB | accurate_passes__per_possession | accurate_passes | own_possession | 290 | 0.7920 | 0.2615 | 1.0000 | False |
| FB | accurate_passes_pct | accurate_passes_pct | current | 290 | 0.7157 | 0.6151 | 1.0000 | False |
| FB | ball_recoveries | ball_recoveries | current | 290 | 0.7550 | 0.4709 | 1.0000 | False |
| FB | ball_recoveries__raw | ball_recoveries | raw | 290 | 0.6847 | 0.0763 | 1.0000 | True |
| FB | big_chances_created | big_chances_created | current | 321 | 0.3805 | 0.1576 | 1.0000 | False |
| FB | big_chances_created__per_possession | big_chances_created | own_possession | 321 | 0.3463 | 0.0239 | 1.0000 | False |
| FB | blocks | blocks | current | 290 | 0.4249 | 0.0243 | 1.0000 | False |
| FB | blocks__raw | blocks | raw | 290 | 0.4381 | 0.1581 | 1.0000 | False |
| FB | clearances | clearances | current | 290 | 0.5911 | 0.0785 | 1.0000 | False |
| FB | clearances__raw | clearances | raw | 290 | 0.6194 | 0.3942 | 1.0000 | False |
| FB | defensive_actions | defensive_actions | current | 290 | 0.6463 | 0.1018 | 1.0000 | True |
| FB | defensive_actions__raw | defensive_actions | raw | 290 | 0.6439 | 0.3113 | 1.0000 | False |
| FB | interceptions | interceptions | current | 290 | 0.5196 | 0.1757 | 1.0000 | False |
| FB | interceptions__raw | interceptions | raw | 290 | 0.5059 | 0.1335 | 1.0000 | False |
| FB | key_passes | key_passes | current | 321 | 0.6547 | 0.1621 | 1.0000 | False |
| FB | key_passes__per_possession | key_passes | own_possession | 321 | 0.6215 | 0.0569 | 1.0000 | True |
| FB | successful_dribbles | successful_dribbles | current | 290 | 0.6883 | 0.1098 | 1.0000 | False |
| FB | successful_dribbles__per_possession | successful_dribbles | own_possession | 290 | 0.6780 | 0.0660 | 1.0000 | True |
| FB | tackles | tackles | current | 290 | 0.6338 | 0.2486 | 1.0000 | False |
| FB | tackles__raw | tackles | raw | 290 | 0.6086 | 0.0833 | 1.0000 | False |
| FB | xa | xa | current | 321 | 0.6199 | 0.2254 | 1.0000 | False |
| FB | xa__per_possession | xa | own_possession | 321 | 0.5932 | 0.0360 | 1.0000 | True |
| CB | accurate_long_balls | accurate_long_balls | current | 307 | 0.6870 | 0.1100 | 1.0000 | True |
| CB | accurate_long_balls__per_possession | accurate_long_balls | own_possession | 307 | 0.6794 | 0.1834 | 1.0000 | False |
| CB | accurate_passes | accurate_passes | current | 307 | 0.8216 | 0.6333 | 1.0000 | False |
| CB | accurate_passes__per_possession | accurate_passes | own_possession | 307 | 0.7864 | 0.3504 | 1.0000 | True |
| CB | accurate_passes_pct | accurate_passes_pct | current | 307 | 0.7170 | 0.6105 | 1.0000 | False |
| CB | ball_recoveries | ball_recoveries | current | 307 | 0.7695 | 0.5938 | 1.0000 | False |
| CB | ball_recoveries__raw | ball_recoveries | raw | 307 | 0.7112 | 0.2790 | 1.0000 | False |
| CB | blocks | blocks | current | 307 | 0.3947 | 0.0820 | 1.0000 | False |
| CB | blocks__raw | blocks | raw | 307 | 0.4000 | 0.2079 | 1.0000 | False |
| CB | clearances | clearances | current | 307 | 0.6510 | 0.0082 | 1.0000 | True |
| CB | clearances__raw | clearances | raw | 307 | 0.6691 | 0.3955 | 1.0000 | False |
| CB | defensive_actions | defensive_actions | current | 307 | 0.6596 | 0.1717 | 1.0000 | True |
| CB | defensive_actions__raw | defensive_actions | raw | 307 | 0.6268 | 0.3693 | 1.0000 | False |
| CB | goals | goals | current | 381 | 0.2488 | 0.0117 | 1.0000 | False |
| CB | goals__per_possession | goals | own_possession | 381 | 0.2578 | 0.0623 | 1.0000 | False |
| CB | interceptions | interceptions | current | 307 | 0.4958 | 0.2452 | 1.0000 | False |
| CB | interceptions__raw | interceptions | raw | 307 | 0.4451 | 0.0975 | 1.0000 | False |
| CB | key_passes | key_passes | current | 381 | 0.4442 | 0.1816 | 1.0000 | False |
| CB | key_passes__per_possession | key_passes | own_possession | 381 | 0.4149 | 0.0162 | 1.0000 | True |
| CB | tackles | tackles | current | 307 | 0.6683 | 0.2429 | 1.0000 | False |
| CB | tackles__raw | tackles | raw | 307 | 0.6112 | 0.0637 | 1.0000 | True |
| CB | xa | xa | current | 381 | 0.4741 | 0.2673 | 1.0000 | False |
| CB | xa__per_possession | xa | own_possession | 381 | 0.4434 | 0.1191 | 1.0000 | False |
| CB | xg | xg | current | 381 | 0.3998 | 0.0999 | 1.0000 | False |
| CB | xg__per_possession | xg | own_possession | 381 | 0.4090 | 0.0691 | 1.0000 | False |

## Unavailable candidates

Tackle-success %, duel-win %, aerial-win %: missing source denominators. Sofascore average rating: source unavailable; probe metadata below.

```json
{
  "url": "https://api.sofascore.com/api/v1/unique-tournament/17/seasons/",
  "available": false,
  "error": "HTTPSConnectionPool(host='api.sofascore.com', port=443): Max retries exceeded with url: /api/v1/unique-tournament/17/seasons/ (Caused by SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING] EO"
}
```
