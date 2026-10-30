# Follow-up: calibration and report access

Checked 2026-10-30 after the evidence/Candidate A implementation.

## Report access

Both configured ZenMux models were tested against the existing account:

| Model | Result |
|---|---|
| deepseek/deepseek-v4.1-flash | HTTP 402 reject_no_credit |
| deepseek/deepseek-v4-flash | HTTP 402 reject_no_credit |

The fallback result is recorded in data/processed/eval/fallback_probe.json. No credit was purchased or provider configuration replaced. Account/model access must be enabled before generation can succeed.

Fixed the dashboard's uncaught report-generation failure: rejected requests now show an actionable message and leave player facts accessible. Provider internals are not displayed. Streamlit AppTest clicked Generate under a simulated HTTP 402: zero uncaught exceptions. No reports or faithfulness results were fabricated.

## Why calibration still fails

Correlations of club mean title components against full-season PPG:

| Component | Spearman vs PPG |
|---|---:|
| Quality gap | -0.460670 |
| Depth gap | 0.280768 |
| Age risk | 0.328190 |
| Contract risk | 0.123448 |
| Final need | -0.368837 |

Urgency can occur at successful clubs. Removing urgency still fails the -0.6 requirement and violates the approved definition. Historical playing-team squad selection also fails: rho -0.357546. That alternative was evaluated in memory only.

| Position | Need rho | Quality-gap rho |
|---|---:|---:|
| AM | -0.117870 | -0.210050 |
| CB | -0.287543 | -0.452390 |
| CM | -0.093338 | -0.198720 |
| DM | -0.415506 | -0.461423 |
| FB | -0.117426 | -0.150546 |
| ST | -0.621002 | -0.674445 |
| W | -0.254422 | -0.317652 |

The shortfall is mainly in quality estimation across midfield/defensive groups, rather than reversed scoring or a PPG join error. These descriptive results on 20 clubs do not establish that a replacement will pass.

## Next modelling decision

The proposed next experiment develops a revised quality estimator on downloaded 2024–25 data, freezes its design before evaluating 2025–26, retains Candidate A's outer formula and urgency coefficients, preserves the percentile pool, and keeps all acceptance thresholds fixed. The 2025–26 aggregate results have already been inspected, so they cannot honestly be called an untouched holdout. Passing is not guaranteed.

Do not inject same-season PPG/GD into the score merely to pass the independent check. Do not change the -0.6 requirement or hide the failed result. The quality-model boundary and account access are pending user responses.

## Verification

- python -m pytest -q: **86 passed in 6.61s**.
- python -m ruff check .: **All checks passed**.
- Failure-path AppTest: **PASS**, actionable HTTP 402 message, no uncaught exception.
- Calibration b remains failed; live faithfulness remains unavailable. No commit.
