# Needs implementation and acceptance audit

Run: 2026-10-30. Season 2025-26; snapshot 2026-07-06. Defaults remain Arsenal/top4. West Ham/title is the case-study override. See NEEDS_DIAGNOSIS.md for the historical diagnosis.

Need = shortfall against the selected ambition (primary), plus depth, age and contract urgency within the remaining range (secondary).

## Acceptance: all 20 clubs


| check | name | passed | observed | requirement |
| --- | --- | --- | --- | --- |
| a | Ambition monotonicity | True | 0 decreases / 420 comparisons | 0 decreases / 420 comparisons |
| b | Independent club-strength correlation | False | Spearman -0.36883726935549355; complete results: True | PPG rho <= -0.6; all clubs, full season |
| c | Meaning of ambition levels | True | title 46.67%; survive 1.48% used cells Medium/High | title >= 30%; survive <= 10% |
| d | Strongest clubs | True | Arsenal FC: 0 High; Manchester City: 0 High | Top 2 PPG clubs: <= 1 High each |
| e | Evidence coverage | True | 132/135 sufficient (97.78%) | >= 95% used cells sufficient |


Check b fails. Parameters, bands and weights were not tuned after seeing results. No commit was made. All 20 clubs have 38 completed games in the local results (380 games / 760 club-game rows). Points are 3/1/0 from results; administrative deductions are outside this measure.


| points_per_game | goal_difference | market_value_secondary | matched_clubs |
| --- | --- | --- | --- |
| -0.369 | -0.555 | -0.716 | 20 |



| club_id | club | played | points | goals_for | goals_against | points_per_game | goal_difference | high_positions |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | Arsenal FC | 38 | 85 | 71 | 27 | 2.237 | 44 | 0 |
| 281 | Manchester City | 38 | 78 | 77 | 35 | 2.053 | 42 | 0 |



| club | position_group | rated_share | imputed_stats |
| --- | --- | --- | --- |
| Sunderland AFC | W | 0.370 | [] |
| West Ham United | ST | 0.369 | [] |
| West Ham United | AM | 0.000 | ["successful_dribbles", "accurate_passes_pct", "shots"] |


Options for a later, separately approved experiment: (1) compare alternative squad-quality summaries and coherent club benchmarks against independent results across multiple held-out seasons; (2) audit position/stat validity and current-club availability before adding any new signal. Neither option is implemented. A small 20-club correlation is not an objective to optimize in-sample.

## Part 1: evidence before the formula

Rows combine each player's analysis-season adjusted per-90 values using available-stat minutes. Qualified profiles retain their existing pool percentiles exactly; a non-pool profile needs 600 combined minutes for empirical placement on that same fixed pool. Exact ties use average rank; between observations use the fraction below; missing stats remain missing. A partial placement is flagged but is not fully rated. Rated share counts combined minutes of profiles with all required role percentiles.

The matches rule remains at 50%: 183 rows pass minutes but fail matches (20 PL rows); none has all required role stats. Relaxing it would admit missing-stat candidates and change the fixed pool. There is no explicit loan-status field in local players/transfers tables. Current-club selection remains; other-club minutes are flagged without inferring current loan status.


| position | before rated % | after rated % | evidence |
| --- | --- | --- | --- |
| ST | 19.965 | 36.910 | insufficient |
| W | 83.868 | 83.868 | sufficient |
| AM | 0.000 | 0.000 | insufficient |
| CM | 67.712 | 71.944 | sufficient |
| DM | 50.495 | 65.186 | sufficient |
| FB | 90.357 | 90.357 | sufficient |
| CB | 77.025 | 77.025 | sufficient |


Used cells: 132/135 sufficient; three insufficient. Those positions keep provisional scores, get grey badges and are excluded from ranking. Median-club substitution is retained only with an explicit insufficient flag.

## West Ham: survive


| position_group | depth_gap | quality_gap | age_risk | contract_risk | need_score | priority | rated_share | evidence | before need | evidence-only old formula |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ST | 0.000 | 0.000 | 36.910 | 20.896 | 8.671 | Low | 0.369 | insufficient | 8.671 | 8.671 |
| W | 0.000 | 0.000 | 5.373 | 0.000 | 0.806 | Low | 0.839 | sufficient | 0.806 | 0.806 |
| AM | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | Low | 0.000 | insufficient | 0.000 | 0.000 |
| CM | 27.519 | 0.000 | 24.541 | 24.541 | 12.866 | Low | 0.719 | sufficient | 12.866 | 12.866 |
| DM | 0.000 | 18.111 | 55.267 | 32.983 | 28.951 | Low | 0.652 | sufficient | 26.186 | 22.293 |
| FB | 6.694 | 4.169 | 0.000 | 0.000 | 5.452 | Low | 0.904 | sufficient | 3.194 | 3.423 |
| CB | 0.000 | 0.685 | 0.000 | 1.344 | 0.885 | Low | 0.770 | sufficient | 0.544 | 0.544 |


## West Ham: midtable


| position_group | depth_gap | quality_gap | age_risk | contract_risk | need_score | priority | rated_share | evidence | before need | evidence-only old formula |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ST | 0.000 | 7.816 | 36.910 | 20.896 | 15.809 | Low | 0.369 | insufficient | 16.083 | 12.579 |
| W | 0.000 | 3.073 | 5.373 | 0.000 | 3.854 | Low | 0.839 | sufficient | 3.053 | 2.343 |
| AM | 0.000 | 0.154 | 0.000 | 0.000 | 0.154 | Low | 0.000 | insufficient | 0.000 | 0.077 |
| CM | 27.519 | 0.000 | 24.541 | 24.541 | 12.866 | Low | 0.719 | sufficient | 13.627 | 12.866 |
| DM | 0.000 | 36.877 | 55.267 | 32.983 | 45.233 | Medium | 0.652 | sufficient | 35.523 | 31.676 |
| FB | 6.694 | 19.423 | 0.000 | 0.000 | 20.502 | Low | 0.904 | sufficient | 11.433 | 11.050 |
| CB | 0.000 | 11.404 | 0.000 | 1.344 | 11.582 | Low | 0.770 | sufficient | 5.903 | 5.903 |


## West Ham: top4


| position_group | depth_gap | quality_gap | age_risk | contract_risk | need_score | priority | rated_share | evidence | before need | evidence-only old formula |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ST | 0.000 | 22.690 | 36.910 | 20.896 | 29.393 | Low | 0.369 | insufficient | 19.520 | 20.016 |
| W | 0.000 | 16.948 | 5.373 | 0.000 | 17.617 | Low | 0.839 | sufficient | 9.453 | 9.280 |
| AM | 0.000 | 22.927 | 0.000 | 0.000 | 22.927 | Low | 0.000 | insufficient | 7.652 | 11.464 |
| CM | 27.519 | 6.510 | 24.541 | 24.541 | 18.539 | Low | 0.719 | sufficient | 16.326 | 16.121 |
| DM | 0.000 | 48.437 | 55.267 | 32.983 | 55.263 | Medium | 0.652 | sufficient | 40.653 | 37.456 |
| FB | 6.694 | 29.558 | 0.000 | 0.000 | 30.501 | Low | 0.904 | sufficient | 16.724 | 16.118 |
| CB | 0.000 | 27.828 | 0.000 | 1.344 | 27.973 | Low | 0.770 | sufficient | 14.058 | 14.115 |


## West Ham: title


| position_group | depth_gap | quality_gap | age_risk | contract_risk | need_score | priority | rated_share | evidence | before need | evidence-only old formula |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ST | 0.000 | 31.076 | 36.910 | 20.896 | 37.053 | Medium | 0.369 | insufficient | 22.675 | 24.209 |
| W | 0.000 | 27.909 | 5.373 | 0.000 | 28.490 | Low | 0.839 | sufficient | 14.654 | 14.760 |
| AM | 0.000 | 32.572 | 0.000 | 0.000 | 32.572 | Low | 0.000 | insufficient | 13.239 | 16.286 |
| CM | 27.519 | 11.950 | 24.541 | 24.541 | 23.279 | Low | 0.719 | sufficient | 20.753 | 18.841 |
| DM | 0.000 | 52.183 | 55.267 | 32.983 | 58.512 | Medium | 0.652 | sufficient | 42.330 | 39.329 |
| FB | 6.694 | 34.816 | 0.000 | 0.000 | 35.688 | Medium | 0.904 | sufficient | 19.540 | 18.747 |
| CB | 0.000 | 34.530 | 0.000 | 1.344 | 34.662 | Low | 0.770 | sufficient | 17.467 | 17.467 |


## Corrected West Ham per-stat diagnosis


| ambition | position | stat | observed squad pct | score input pct | benchmark pct |
| --- | --- | --- | --- | --- | --- |
| survive | ST | xg | 61.917 | 61.917 | 51.283 |
| survive | ST | shots | 73.640 | 73.640 | 55.514 |
| survive | ST | xa | 56.011 | 56.011 | 17.644 |
| survive | ST | key_passes | 70.950 | 70.950 | 31.983 |
| survive | ST | successful_dribbles | 60.818 | 60.818 | 38.657 |
| survive | ST | xgot | 59.367 | 59.367 | 48.213 |
| survive | W | xa | 58.147 | 58.147 | 35.563 |
| survive | W | key_passes | 55.448 | 55.448 | 42.431 |
| survive | W | successful_dribbles | 82.641 | 82.641 | 36.202 |
| survive | W | xg | 65.804 | 65.804 | 38.032 |
| survive | W | shots | 81.403 | 81.403 | 45.946 |
| survive | W | big_chances_created | 58.005 | 58.005 | 32.310 |
| survive | AM | xa | 57.527 | 57.527 | 11.290 |
| survive | AM | key_passes | 67.204 | 67.204 | 20.968 |
| survive | AM | xg | 59.677 | 59.677 | 11.290 |
| survive | AM | successful_dribbles | N/A | 73.047 | 27.606 |
| survive | AM | accurate_passes_pct | N/A | 56.188 | 10.215 |
| survive | AM | shots | N/A | 74.314 | 10.215 |
| survive | CM | accurate_passes_pct | 79.839 | 79.839 | 39.170 |
| survive | CM | accurate_long_balls | 97.849 | 97.849 | 32.782 |
| survive | CM | key_passes | 78.065 | 78.065 | 44.858 |
| survive | CM | tackles | 95.430 | 95.430 | 59.010 |
| survive | CM | interceptions | 77.957 | 77.957 | 60.846 |
| survive | CM | xa | 65.121 | 65.121 | 44.355 |
| survive | DM | tackles | 71.245 | 71.245 | 51.701 |
| survive | DM | interceptions | 49.700 | 49.700 | 51.103 |
| survive | DM | ball_recoveries | 24.506 | 24.506 | 65.809 |
| survive | DM | accurate_passes_pct | 21.734 | 21.734 | 38.238 |
| survive | DM | accurate_passes | 60.009 | 60.009 | 60.009 |
| survive | DM | accurate_long_balls | 56.629 | 56.629 | 41.316 |
| survive | FB | tackles | 48.798 | 48.798 | 54.656 |
| survive | FB | interceptions | 68.973 | 68.973 | 59.012 |
| survive | FB | xa | 31.908 | 31.908 | 36.363 |
| survive | FB | key_passes | 58.415 | 58.415 | 47.679 |
| survive | FB | ball_recoveries | 57.958 | 57.958 | 59.170 |
| survive | FB | successful_dribbles | 85.284 | 85.284 | 38.817 |
| survive | CB | blocks | 82.425 | 82.425 | 60.889 |
| survive | CB | clearances | 79.341 | 79.341 | 70.152 |
| survive | CB | interceptions | 53.360 | 53.360 | 55.647 |
| survive | CB | tackles | 60.457 | 60.457 | 49.497 |
| survive | CB | accurate_passes_pct | 40.655 | 40.655 | 34.668 |
| survive | CB | accurate_long_balls | 51.468 | 51.468 | 48.836 |
| midtable | ST | xg | 61.917 | 61.917 | 78.953 |
| midtable | ST | shots | 73.640 | 73.640 | 78.539 |
| midtable | ST | xa | 56.011 | 56.011 | 52.862 |
| midtable | ST | key_passes | 70.950 | 70.950 | 61.991 |
| midtable | ST | successful_dribbles | 60.818 | 60.818 | 62.259 |
| midtable | ST | xgot | 59.367 | 59.367 | 71.324 |
| midtable | W | xa | 58.147 | 58.147 | 61.430 |
| midtable | W | key_passes | 55.448 | 55.448 | 63.803 |
| midtable | W | successful_dribbles | 82.641 | 82.641 | 52.570 |
| midtable | W | xg | 65.804 | 65.804 | 65.804 |
| midtable | W | shots | 81.403 | 81.403 | 69.159 |
| midtable | W | big_chances_created | 58.005 | 58.005 | 56.513 |
| midtable | AM | xa | 57.527 | 57.527 | 58.065 |
| midtable | AM | key_passes | 67.204 | 67.204 | 61.290 |
| midtable | AM | xg | 59.677 | 59.677 | 55.039 |
| midtable | AM | successful_dribbles | N/A | 73.047 | 68.777 |
| midtable | AM | accurate_passes_pct | N/A | 56.188 | 53.144 |
| midtable | AM | shots | N/A | 74.314 | 66.651 |
| midtable | CM | accurate_passes_pct | 79.839 | 79.839 | 61.028 |
| midtable | CM | accurate_long_balls | 97.849 | 97.849 | 60.081 |
| midtable | CM | key_passes | 78.065 | 78.065 | 74.071 |
| midtable | CM | tackles | 95.430 | 95.430 | 80.411 |
| midtable | CM | interceptions | 77.957 | 77.957 | 73.283 |
| midtable | CM | xa | 65.121 | 65.121 | 62.000 |
| midtable | DM | tackles | 71.245 | 71.245 | 83.578 |
| midtable | DM | interceptions | 49.700 | 49.700 | 70.221 |
| midtable | DM | ball_recoveries | 24.506 | 24.506 | 83.088 |
| midtable | DM | accurate_passes_pct | 21.734 | 21.734 | 71.324 |
| midtable | DM | accurate_passes | 60.009 | 60.009 | 87.183 |
| midtable | DM | accurate_long_balls | 56.629 | 56.629 | 60.294 |
| midtable | FB | tackles | 48.798 | 48.798 | 80.905 |
| midtable | FB | interceptions | 68.973 | 68.973 | 72.400 |
| midtable | FB | xa | 31.908 | 31.908 | 56.374 |
| midtable | FB | key_passes | 58.415 | 58.415 | 58.948 |
| midtable | FB | ball_recoveries | 57.958 | 57.958 | 80.294 |
| midtable | FB | successful_dribbles | 85.284 | 85.284 | 59.122 |
| midtable | CB | blocks | 82.425 | 82.425 | 81.172 |
| midtable | CB | clearances | 79.341 | 79.341 | 83.487 |
| midtable | CB | interceptions | 53.360 | 53.360 | 63.324 |
| midtable | CB | tackles | 60.457 | 60.457 | 66.255 |
| midtable | CB | accurate_passes_pct | 40.655 | 40.655 | 50.516 |
| midtable | CB | accurate_long_balls | 51.468 | 51.468 | 63.895 |
| top4 | ST | xg | 61.917 | 61.917 | 93.425 |
| top4 | ST | shots | 73.640 | 73.640 | 93.555 |
| top4 | ST | xa | 56.011 | 56.011 | 68.608 |
| top4 | ST | key_passes | 70.950 | 70.950 | 73.634 |
| top4 | ST | successful_dribbles | 60.818 | 60.818 | 80.597 |
| top4 | ST | xgot | 59.367 | 59.367 | 90.746 |
| top4 | W | xa | 58.147 | 58.147 | 77.101 |
| top4 | W | key_passes | 55.448 | 55.448 | 84.343 |
| top4 | W | successful_dribbles | 82.641 | 82.641 | 82.641 |
| top4 | W | xg | 65.804 | 65.804 | 84.881 |
| top4 | W | shots | 81.403 | 81.403 | 82.247 |
| top4 | W | big_chances_created | 58.005 | 58.005 | 71.916 |
| top4 | AM | xa | 57.527 | 57.527 | 85.484 |
| top4 | AM | key_passes | 67.204 | 67.204 | 88.960 |
| top4 | AM | xg | 59.677 | 59.677 | 74.500 |
| top4 | AM | successful_dribbles | N/A | 73.047 | 85.644 |
| top4 | AM | accurate_passes_pct | N/A | 56.188 | 83.871 |
| top4 | AM | shots | N/A | 74.314 | 85.215 |
| top4 | CM | accurate_passes_pct | 79.839 | 79.839 | 79.839 |
| top4 | CM | accurate_long_balls | 97.849 | 97.849 | 77.864 |
| top4 | CM | key_passes | 78.065 | 78.065 | 87.507 |
| top4 | CM | tackles | 95.430 | 95.430 | 90.856 |
| top4 | CM | interceptions | 77.957 | 77.957 | 89.909 |
| top4 | CM | xa | 65.121 | 65.121 | 76.594 |
| top4 | DM | tackles | 71.245 | 71.245 | 94.853 |
| top4 | DM | interceptions | 49.700 | 49.700 | 90.809 |
| top4 | DM | ball_recoveries | 24.506 | 24.506 | 95.588 |
| top4 | DM | accurate_passes_pct | 21.734 | 21.734 | 89.522 |
| top4 | DM | accurate_passes | 60.009 | 60.009 | 94.118 |
| top4 | DM | accurate_long_balls | 56.629 | 56.629 | 85.984 |
| top4 | FB | tackles | 48.798 | 48.798 | 92.536 |
| top4 | FB | interceptions | 68.973 | 68.973 | 88.481 |
| top4 | FB | xa | 31.908 | 31.908 | 67.508 |
| top4 | FB | key_passes | 58.415 | 58.415 | 74.455 |
| top4 | FB | ball_recoveries | 57.958 | 57.958 | 87.492 |
| top4 | FB | successful_dribbles | 85.284 | 85.284 | 83.905 |
| top4 | CB | blocks | 82.425 | 82.425 | 89.008 |
| top4 | CB | clearances | 79.341 | 79.341 | 95.649 |
| top4 | CB | interceptions | 53.360 | 53.360 | 83.177 |
| top4 | CB | tackles | 60.457 | 60.457 | 83.865 |
| top4 | CB | accurate_passes_pct | 40.655 | 40.655 | 77.045 |
| top4 | CB | accurate_long_balls | 51.468 | 51.468 | 75.167 |
| title | ST | xg | 61.917 | 61.917 | 97.612 |
| title | ST | shots | 73.640 | 73.640 | 98.863 |
| title | ST | xa | 56.011 | 56.011 | 81.852 |
| title | ST | key_passes | 70.950 | 70.950 | 85.596 |
| title | ST | successful_dribbles | 60.818 | 60.818 | 99.104 |
| title | ST | xgot | 59.367 | 59.367 | 94.328 |
| title | W | xa | 58.147 | 58.147 | 93.887 |
| title | W | key_passes | 55.448 | 55.448 | 92.614 |
| title | W | successful_dribbles | 82.641 | 82.641 | 92.040 |
| title | W | xg | 65.804 | 65.804 | 92.658 |
| title | W | shots | 81.403 | 81.403 | 96.389 |
| title | W | big_chances_created | 58.005 | 58.005 | 88.578 |
| title | AM | xa | 57.527 | 57.527 | 93.548 |
| title | AM | key_passes | 67.204 | 67.204 | 95.080 |
| title | AM | xg | 59.677 | 59.677 | 100.000 |
| title | AM | successful_dribbles | N/A | 73.047 | 94.086 |
| title | AM | accurate_passes_pct | N/A | 56.188 | 94.360 |
| title | AM | shots | N/A | 74.314 | 98.387 |
| title | CM | accurate_passes_pct | 79.839 | 79.839 | 92.131 |
| title | CM | accurate_long_balls | 97.849 | 97.849 | 97.849 |
| title | CM | key_passes | 78.065 | 78.065 | 89.479 |
| title | CM | tackles | 95.430 | 95.430 | 95.430 |
| title | CM | interceptions | 77.957 | 77.957 | 92.204 |
| title | CM | xa | 65.121 | 65.121 | 93.231 |
| title | DM | tackles | 71.245 | 71.245 | 99.265 |
| title | DM | interceptions | 49.700 | 49.700 | 100.000 |
| title | DM | ball_recoveries | 24.506 | 24.506 | 99.439 |
| title | DM | accurate_passes_pct | 21.734 | 21.734 | 97.426 |
| title | DM | accurate_passes | 60.009 | 60.009 | 99.071 |
| title | DM | accurate_long_balls | 56.629 | 56.629 | 97.794 |
| title | FB | tackles | 48.798 | 48.798 | 94.556 |
| title | FB | interceptions | 68.973 | 68.973 | 97.147 |
| title | FB | xa | 31.908 | 31.908 | 77.043 |
| title | FB | key_passes | 58.415 | 58.415 | 82.500 |
| title | FB | ball_recoveries | 57.958 | 57.958 | 94.146 |
| title | FB | successful_dribbles | 85.284 | 85.284 | 90.043 |
| title | CB | blocks | 82.425 | 82.425 | 94.257 |
| title | CB | clearances | 79.341 | 79.341 | 98.236 |
| title | CB | interceptions | 53.360 | 53.360 | 97.683 |
| title | CB | tackles | 60.457 | 60.457 | 88.466 |
| title | CB | accurate_passes_pct | 40.655 | 40.655 | 95.155 |
| title | CB | accurate_long_balls | 51.468 | 51.468 | 87.358 |


## Combined player evidence

Regular proxy means 900 combined minutes; actual starting-XI data is not used. All profile percentiles below use the single fixed pool.

### AM


| player_name | sub_position | minutes | fully_rated | rated_by_placement | other_club_minutes | xa_pct | key_passes_pct | xg_pct | successful_dribbles_pct | accurate_passes_pct_pct | shots_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| George Earthy | Attacking Midfield | 278 | False | False | 270 | N/A | N/A | N/A | N/A | N/A | N/A |
| Lucas Paquetá | Attacking Midfield | 1521 | False | True | 0 | 57.527 | 67.204 | 59.677 | N/A | N/A | N/A |


### CB


| player_name | sub_position | minutes | fully_rated | rated_by_placement | other_club_minutes | blocks_pct | clearances_pct | interceptions_pct | tackles_pct | accurate_passes_pct_pct | accurate_long_balls_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Kaelan Casey | Centre-Back | 290 | False | False | 290 | N/A | N/A | N/A | N/A | N/A | N/A |
| Ezra Mayers | Centre-Back | 113 | False | False | 0 | N/A | N/A | N/A | N/A | N/A | N/A |
| Axel Disasi | Centre-Back | 1255 | False | False | 0 | N/A | N/A | N/A | N/A | N/A | N/A |
| Konstantinos Mavropanos | Centre-Back | 2528 | True | False | 0 | 93.321 | 90.909 | 96.289 | 63.265 | 18.367 | 91.187 |
| Igor Julio | Centre-Back | 103 | False | False | 0 | N/A | N/A | N/A | N/A | N/A | N/A |
| Max Kilman | Centre-Back | 1559 | True | False | 0 | 98.330 | 85.158 | 4.638 | 25.603 | 59.740 | 31.911 |
| Jean-Clair Todibo | Centre-Back | 1817 | True | False | 0 | 53.618 | 58.256 | 35.436 | 86.456 | 55.288 | 12.987 |


### CM


| player_name | sub_position | minutes | fully_rated | rated_by_placement | other_club_minutes | accurate_passes_pct_pct | accurate_long_balls_pct | key_passes_pct | tackles_pct | interceptions_pct | xa_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Mateus Fernandes | Central Midfield | 3213 | True | False | 189 | 79.839 | 97.849 | 71.774 | 95.430 | 77.957 | 57.258 |
| James Ward-Prowse | Central Midfield | 1096 | False | True | 1096 | N/A | N/A | 96.505 | N/A | N/A | 88.172 |
| Andy Irving | Central Midfield | 157 | False | False | 0 | N/A | N/A | N/A | N/A | N/A | N/A |


### DM


| player_name | sub_position | minutes | fully_rated | rated_by_placement | other_club_minutes | tackles_pct | interceptions_pct | ball_recoveries_pct | accurate_passes_pct_pct | accurate_passes_pct | accurate_long_balls_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Freddie Potts | Defensive Midfield | 1167 | True | False | 0 | 78.676 | 80.515 | 13.603 | 43.199 | 69.853 | 75.735 |
| Soungoutou Magassa | Defensive Midfield | 979 | True | True | 0 | 98.529 | 88.235 | 76.838 | 23.897 | 59.191 | 60.294 |
| Mohamadou Kanté | Defensive Midfield | 67 | False | False | 0 | N/A | N/A | N/A | N/A | N/A | N/A |
| Tomás Souček | Defensive Midfield | 2198 | True | False | 0 | 55.147 | 16.176 | 6.985 | 9.375 | 55.147 | 44.853 |
| Guido Rodríguez | Defensive Midfield | 1485 | False | False | 1308 | N/A | N/A | N/A | N/A | N/A | N/A |
| Edson Álvarez | Defensive Midfield | 768 | False | False | 768 | N/A | N/A | N/A | N/A | N/A | N/A |


### FB


| player_name | sub_position | minutes | fully_rated | rated_by_placement | other_club_minutes | tackles_pct | interceptions_pct | xa_pct | key_passes_pct | ball_recoveries_pct | successful_dribbles_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Oliver Scarles | Left-Back | 659 | False | True | 0 | N/A | N/A | 16.916 | 50.321 | N/A | N/A |
| Malick Diouf | Left-Back | 2711 | True | False | 0 | 38.330 | 71.520 | 58.672 | 76.660 | 70.664 | 85.439 |
| Kyle Walker-Peters | Right-Back | 1380 | True | False | 0 | 92.934 | 19.700 | 4.925 | 21.199 | 61.670 | 92.184 |
| Aaron Wan-Bissaka | Right-Back | 2084 | True | False | 0 | 33.191 | 98.287 | 19.700 | 61.884 | 38.972 | 80.514 |


### ST


| player_name | sub_position | minutes | fully_rated | rated_by_placement | other_club_minutes | xg_pct | shots_pct | xa_pct | key_passes_pct | successful_dribbles_pct | xgot_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pablo | Centre-Forward | 1781 | False | True | 955 | 33.433 | N/A | 73.134 | 90.149 | N/A | 48.358 |
| Callum Marshall | Centre-Forward | 58 | False | False | 0 | N/A | N/A | N/A | N/A | N/A | N/A |
| Callum Wilson | Centre-Forward | 1243 | True | False | 0 | 96.716 | 91.045 | 24.179 | 33.731 | 85.075 | 91.642 |
| Niclas Füllkrug | Centre-Forward | 1055 | True | True | 647 | 69.254 | 53.134 | 56.119 | 93.433 | 32.239 | 25.075 |
| Valentín Castellanos | Centre-Forward | 2089 | False | True | 694 | 61.791 | N/A | 60.299 | 65.373 | N/A | 66.866 |


### W


| player_name | sub_position | minutes | fully_rated | rated_by_placement | other_club_minutes | xa_pct | key_passes_pct | successful_dribbles_pct | xg_pct | shots_pct | big_chances_created_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Luís Guilherme | Right Winger | 755 | False | True | 634 | 61.496 | 66.759 | N/A | 50.416 | N/A | 11.080 |
| Adama Traoré | Right Winger | 377 | False | False | 0 | N/A | N/A | N/A | N/A | N/A | N/A |
| Jarrod Bowen | Right Winger | 3405 | True | False | 0 | 61.219 | 59.834 | 76.454 | 69.529 | 82.687 | 89.474 |
| Crysencio Summerville | Left Winger | 2480 | True | False | 0 | 52.909 | 45.983 | 91.136 | 65.374 | 79.640 | 29.086 |


## League-wide bands


| version | ambition | High | Medium | Low | used cells |
| --- | --- | --- | --- | --- | --- |
| Before | title | 2 | 11 | 127 | 135 |
| Before | survive | 0 | 2 | 138 | 135 |
| After | title | 6 | 57 | 77 | 135 |
| After | survive | 0 | 2 | 138 | 135 |


Counts include provisional numeric bands for insufficient cells; the app replaces those labels with the evidence badge. Acceptance c uses all used cells as specified.

## West Ham title targets: DM and FB

Every row below passed the source sub-position → position-group check and the upgrade margin. Minutes are the qualifying candidate league row, not a fabricated combined candidate season. A benchmark warning means at least one weighted statistic is below its ambition target.


| position_group | rank | player_name | sub_position | minutes | performance | age_score | value_score | fit | current_best_regular | current_best_composite | upgrade_vs_current | below_ambition_benchmark |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DM | 1 | Equi Fernández | Defensive Midfield | 987 | 91.353 | 100.000 | 83.333 | 91.479 | Soungoutou Magassa | 64.635 | 26.719 | True |
| DM | 2 | Nico González | Defensive Midfield | 1567 | 93.491 | 100.000 | 66.667 | 89.428 | Soungoutou Magassa | 64.635 | 28.856 | True |
| DM | 3 | Aidan Morris | Defensive Midfield | 3203 | 84.984 | 100.000 | 91.564 | 89.303 | Soungoutou Magassa | 64.635 | 20.349 | True |
| DM | 4 | Enzo Barrenechea | Defensive Midfield | 1798 | 83.360 | 100.000 | 90.000 | 88.016 | Soungoutou Magassa | 64.635 | 18.725 | True |
| DM | 5 | André | Defensive Midfield | 2766 | 83.123 | 100.000 | 79.167 | 85.707 | Soungoutou Magassa | 64.635 | 18.488 | True |
| DM | 6 | Antonio Blanco | Defensive Midfield | 3116 | 77.439 | 100.000 | 91.667 | 84.797 | Soungoutou Magassa | 64.635 | 12.804 | True |
| DM | 7 | Leon Avdullahu | Defensive Midfield | 2838 | 82.733 | 100.000 | 75.000 | 84.640 | Soungoutou Magassa | 64.635 | 18.099 | True |
| DM | 8 | Tyler Adams | Defensive Midfield | 1778 | 83.085 | 90.000 | 79.167 | 83.684 | Soungoutou Magassa | 64.635 | 18.451 | True |
| DM | 9 | Ethan Ampadu | Defensive Midfield | 3123 | 80.630 | 100.000 | 75.000 | 83.378 | Soungoutou Magassa | 64.635 | 15.995 | True |
| DM | 10 | Florentino | Defensive Midfield | 2112 | 76.669 | 100.000 | 86.667 | 83.335 | Soungoutou Magassa | 64.635 | 12.034 | True |
| FB | 1 | Hugo Bueno | Left-Back | 2364 | 88.184 | 100.000 | 90.000 | 90.910 | Malick Diouf | 62.753 | 25.430 | True |
| FB | 2 | Ian Maatsen | Left-Back | 1599 | 92.432 | 100.000 | 75.000 | 90.459 | Malick Diouf | 62.753 | 29.678 | True |
| FB | 3 | Arthur | Right-Back | 1132 | 82.641 | 100.000 | 93.333 | 88.251 | Malick Diouf | 62.753 | 19.888 | True |
| FB | 4 | Quentin Merlin | Left-Back | 2532 | 83.890 | 100.000 | 87.500 | 87.834 | Malick Diouf | 62.753 | 21.136 | True |
| FB | 5 | Malo Gusto | Right-Back | 2267 | 88.381 | 100.000 | 70.833 | 87.195 | Malick Diouf | 62.753 | 25.627 | True |
| FB | 6 | Neco Williams | Left-Back | 3206 | 86.262 | 100.000 | 76.667 | 87.091 | Malick Diouf | 62.753 | 23.509 | True |
| FB | 7 | Pedro Porro | Right-Back | 2798 | 87.718 | 100.000 | 70.833 | 86.797 | Malick Diouf | 62.753 | 24.965 | True |
| FB | 8 | Lucas Pires | Left-Back | 1406 | 79.086 | 100.000 | 96.667 | 86.785 | Malick Diouf | 62.753 | 16.332 | True |
| FB | 9 | Sergio Gómez | Left-Back | 2705 | 81.263 | 100.000 | 87.500 | 86.258 | Malick Diouf | 62.753 | 18.509 | True |
| FB | 10 | Mauro Júnior | Left-Back | 2086 | 84.945 | 90.000 | 85.000 | 85.967 | Malick Diouf | 62.753 | 22.191 | True |


## Evaluation before/after


| version | backtest uplift % | CI low % | CI high % | picks scored | mean Jaccard (10 variants) | faithfulness % |
| --- | --- | --- | --- | --- | --- | --- |
| Before | 50.900 | 47.183 | 54.075 | 309/400 | 0.849 | 100.000 |
| After | 51.739 | 48.608 | 54.454 | 340/439 | 0.856 | N/A |



| variant | before league mean | after league mean |
| --- | --- | --- |
| fit_weights.performance +0.1 | 0.917 | 0.939 |
| fit_weights.performance -0.1 | 0.873 | 0.892 |
| fit_weights.age +0.1 | 0.871 | 0.920 |
| fit_weights.age -0.1 | 0.917 | 0.913 |
| fit_weights.value +0.1 | 0.738 | 0.823 |
| fit_weights.value -0.1 | 0.782 | 0.830 |
| league_strength_floor +0.1 | 0.724 | 0.750 |
| stat_weight_blend +0.1 (extra) | 0.920 | 0.937 |
| league_strength_floor -0.1 | 0.843 | 0.656 |
| stat_weight_blend -0.1 (extra) | 0.904 | 0.898 |


Backtest groups changed 40 → 48 and picks 400 → 439; sensitivity High/Medium groups also changed. These are pipeline-level comparisons, not paired estimates on an identical selection population. Backtest contract urgency is zero without redistributing it; the other secondary coefficients stay fixed. Historical squad identity uses the season team; for a player with several teams the largest-minute row supplies roster metadata. Position labels remain the snapshot labels (known leakage).

Improvements: pooled uplift 50.90% → 51.74%; outcome median 78.71 → 79.45. The naive baseline still wins: 53.02% uplift versus 51.74%. Worse: floor −0.1 Jaccard 0.843 → 0.656; age −0.1 and blend −0.1 also decreased. Model median value rose €15m → €18m. New report faithfulness is unavailable, not verified at 100%.

League-strength validation reran: five-season UEFA Pearson 0.9326 / Spearman 0.8667 (9 leagues). ClubElo's single eval retry returned HTTP 502; its correlation is null.

## Reports and two review examples

PROMPT_VERSION is v2 for the new evidence/upgrade contract (the earlier contract was named v4). All 20 fact sheets are saved in data/processed/report_fact_sheets.json. ZenMux returned HTTP 402 reject_no_credit on 2026-10-29. Thus 0/20 new reports exist and the ≥95% faithfulness requirement is unresolved. Historical cached reports are preserved but are not counted as verification of the new contract. The two examples below are prepared fact sheets, not generated reports.

### Equi Fernández

```json
{
  "player.name": "Equi Fernández",
  "player.age": 23,
  "player.position": "DM",
  "player.team": "Bayer 04 Leverkusen",
  "player.league": "Bundesliga",
  "player.market_value_m": 20.0,
  "player.minutes": 987,
  "player.matches": 20,
  "player.minutes_share_pct": 32,
  "player.small_sample": true,
  "player.contract_months_left": 47.8,
  "stats.tackles.p90": 2.83,
  "stats.tackles.pct": 97,
  "stats.interceptions.p90": 1.09,
  "stats.interceptions.pct": 80,
  "stats.ball_recoveries.p90": 6.11,
  "stats.ball_recoveries.pct": 99,
  "stats.accurate_passes_pct.value": 89.5,
  "stats.accurate_passes_pct.pct": 88,
  "stats.accurate_passes.p90": 67.4,
  "stats.accurate_passes.pct": 97,
  "stats.accurate_long_balls.p90": 3.2,
  "stats.accurate_long_balls.pct": 89,
  "fit.score": 91.5,
  "fit.rank": 1,
  "fit.performance": 91.4,
  "fit.age_score": 100,
  "fit.value_score": 83.3,
  "club_need.club": "West Ham United",
  "club_need.ambition": "title",
  "club_need.budget_m": 60.0,
  "club_need.position": "DM",
  "club_need.definition": "Need = shortfall against the selected ambition (primary), plus depth, age and contract urgency within the remaining range (secondary).",
  "club_need.evidence": "sufficient",
  "club_need.rated_share_pct": 65.2,
  "fit.current_best_regular": "Soungoutou Magassa",
  "fit.current_best_composite": 64.6,
  "fit.upgrade_margin": 26.7,
  "fit.required_upgrade_margin": 5.0,
  "fit.benchmark_composite": 98.8,
  "fit.below_ambition_benchmark": true,
  "club_need.benchmark.tackles": 99.3,
  "club_need.stat_weight.tackles": 0.1134,
  "club_need.benchmark.interceptions": 100.0,
  "club_need.stat_weight.interceptions": 0.1639,
  "club_need.benchmark.ball_recoveries": 99.4,
  "club_need.stat_weight.ball_recoveries": 0.2197,
  "club_need.benchmark.accurate_passes_pct": 97.4,
  "club_need.stat_weight.accurate_passes_pct": 0.2214,
  "club_need.benchmark.accurate_passes": 99.1,
  "club_need.stat_weight.accurate_passes": 0.1384,
  "club_need.benchmark.accurate_long_balls": 97.8,
  "club_need.stat_weight.accurate_long_balls": 0.1432,
  "player.sub_position": "Defensive Midfield"
}
```

### Hugo Bueno

```json
{
  "player.name": "Hugo Bueno",
  "player.age": 23,
  "player.position": "FB",
  "player.team": "Wolverhampton Wanderers",
  "player.league": "Premier League",
  "player.market_value_m": 12.0,
  "player.minutes": 2364,
  "player.matches": 35,
  "player.minutes_share_pct": 69,
  "player.small_sample": false,
  "player.contract_months_left": 23.8,
  "stats.tackles.p90": 2.55,
  "stats.tackles.pct": 89,
  "stats.interceptions.p90": 1.45,
  "stats.interceptions.pct": 92,
  "stats.xa.p90": 0.13,
  "stats.xa.pct": 87,
  "stats.key_passes.p90": 1.45,
  "stats.key_passes.pct": 94,
  "stats.ball_recoveries.p90": 4.38,
  "stats.ball_recoveries.pct": 78,
  "stats.successful_dribbles.p90": 1.2,
  "stats.successful_dribbles.pct": 96,
  "fit.score": 90.9,
  "fit.rank": 1,
  "fit.performance": 88.2,
  "fit.age_score": 100,
  "fit.value_score": 90.0,
  "club_need.club": "West Ham United",
  "club_need.ambition": "title",
  "club_need.budget_m": 60.0,
  "club_need.position": "FB",
  "club_need.definition": "Need = shortfall against the selected ambition (primary), plus depth, age and contract urgency within the remaining range (secondary).",
  "club_need.evidence": "sufficient",
  "club_need.rated_share_pct": 90.4,
  "fit.current_best_regular": "Malick Diouf",
  "fit.current_best_composite": 62.8,
  "fit.upgrade_margin": 25.4,
  "fit.required_upgrade_margin": 5.0,
  "fit.benchmark_composite": 89.0,
  "fit.below_ambition_benchmark": true,
  "club_need.benchmark.tackles": 94.6,
  "club_need.stat_weight.tackles": 0.224,
  "club_need.benchmark.interceptions": 97.1,
  "club_need.stat_weight.interceptions": 0.1571,
  "club_need.benchmark.xa": 77.0,
  "club_need.stat_weight.xa": 0.2216,
  "club_need.benchmark.key_passes": 82.5,
  "club_need.stat_weight.key_passes": 0.1416,
  "club_need.benchmark.ball_recoveries": 94.1,
  "club_need.stat_weight.ball_recoveries": 0.1876,
  "club_need.benchmark.successful_dribbles": 90.0,
  "club_need.stat_weight.successful_dribbles": 0.0681,
  "player.sub_position": "Left-Back"
}
```

## Verification and resumption

Original player_season columns compare exactly, including every qualifying flag and percentile. Only sub_position was added. Streamlit AppTest rendered all five pages for West Ham/title with and without report access (10 page checks, zero exceptions). Final pytest/Ruff output was recorded in the project's handoff notes. No commit: calibration b fails and live reports remain blocked. No thresholds were adjusted.

After gateway access is enabled: run `python pipeline.py --stage reports --club 'West Ham United' --ambition title`, then rerun this audit. The requested two real report examples and faithfulness gate remain pending.