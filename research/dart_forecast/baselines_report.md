# DART forecast — baseline results (walk-forward, no model yet)

- git SHA `fa6c18db310190942a4e2177c7094129918e4d5d` · seed 42 · target **dart = DA - RT ($/MWh)** · quantiles [0.1, 0.25, 0.5, 0.75, 0.9] · spike heads $[20.0, 100.0]
- clim_persist = climatology spread, level nudged 0.5x toward persistence
- PER-FOLD train-only (month,hour) quantiles; NOT the full-decade snapshot
- ⚠ HB_NORTH/SOUTH/WEST: ~28-day RT coverage, single holdout, small-sample — NEVER averaged into a headline with Houston.

## HB_HOUSTON
_walk-forward, 89 monthly folds, embargo 1d · n_test=64944 · span 2018-01-04..2026-06-30_

| baseline | mean pinball | q10 | q25 | q50 | q75 | q90 | 10–90 cov |
|---|---|---|---|---|---|---|
| zero_spread | 12.190 | 11.500 | 11.758 | 12.190 | 12.621 | 12.880 | 0.000 |
| persistence | 18.666 | 18.665 | 18.665 | 18.666 | 18.667 | 18.667 | 0.000 |
| climatology | 11.100 | 10.886 | 11.701 | 11.908 | 11.187 | 9.819 | 0.694 |
| clim_persist | 13.539 | 12.847 | 14.000 | 14.415 | 13.872 | 12.560 | 0.660 |

Spike heads (direct probabilities):

| baseline | Brier@$20 | logloss@$20 | Brier@$100 | logloss@$100 |
|---|---|---|---|---|
| zero_spread | 0.0467 | 1.611 | 0.0137 | 0.474 |
| persistence | 0.0816 | 2.818 | 0.0242 | 0.836 |
| climatology | 0.0441 | 0.295 | 0.0136 | 0.171 |
| clim_persist | 0.0441 | 0.295 | 0.0136 | 0.171 |

- spike@\$20: base rate 0.0467, total events 3030 across 89 folds. ⚠ 2/89 folds have <5 events (scores hollow there)
- spike@\$100: base rate 0.0137, total events 891 across 89 folds. ⚠ 41/89 folds have <5 events (scores hollow there)

## HB_NORTH  _(small sample — never averaged with Houston)_
_single 50/50 chronological holdout (small sample — NOT comparable to Houston) · n_test=336 · span 2026-07-01..2026-07-28_

| baseline | mean pinball | q10 | q25 | q50 | q75 | q90 | 10–90 cov |
|---|---|---|---|---|---|---|
| zero_spread | 3.426 | 2.590 | 2.903 | 3.426 | 3.949 | 4.263 | 0.000 |
| persistence | 4.952 | 5.011 | 4.989 | 4.952 | 4.915 | 4.893 | 0.000 |
| climatology | 2.781 | 2.047 | 2.831 | 3.354 | 3.205 | 2.467 | 0.723 |
| clim_persist | 3.219 | 2.486 | 3.361 | 3.822 | 3.586 | 2.838 | 0.708 |

Spike heads (direct probabilities):

| baseline | Brier@$20 | logloss@$20 | Brier@$100 | logloss@$100 |
|---|---|---|---|---|
| zero_spread | 0.0268 | 0.925 | 0.0000 | 0.000 |
| persistence | 0.0506 | 1.748 | 0.0000 | 0.000 |
| climatology | 0.0266 | 0.159 | 0.0000 | 0.000 |
| clim_persist | 0.0266 | 0.159 | 0.0000 | 0.000 |

- spike@\$20: base rate 0.0268, total events 9 across 1 folds.
- spike@\$100: base rate 0.0000, total events 0 across 1 folds. ⚠ 1/1 folds have <5 events (scores hollow there)

## HB_SOUTH  _(small sample — never averaged with Houston)_
_single 50/50 chronological holdout (small sample — NOT comparable to Houston) · n_test=336 · span 2026-07-01..2026-07-28_

| baseline | mean pinball | q10 | q25 | q50 | q75 | q90 | 10–90 cov |
|---|---|---|---|---|---|---|
| zero_spread | 3.631 | 2.990 | 3.230 | 3.631 | 4.032 | 4.272 | 0.000 |
| persistence | 5.216 | 5.123 | 5.158 | 5.216 | 5.274 | 5.309 | 0.000 |
| climatology | 2.818 | 2.506 | 3.202 | 3.455 | 2.920 | 2.004 | 0.699 |
| clim_persist | 3.438 | 2.898 | 3.743 | 4.160 | 3.672 | 2.720 | 0.661 |

Spike heads (direct probabilities):

| baseline | Brier@$20 | logloss@$20 | Brier@$100 | logloss@$100 |
|---|---|---|---|---|
| zero_spread | 0.0417 | 1.439 | 0.0000 | 0.000 |
| persistence | 0.0714 | 2.467 | 0.0000 | 0.000 |
| climatology | 0.0417 | 1.439 | 0.0000 | 0.000 |
| clim_persist | 0.0417 | 1.439 | 0.0000 | 0.000 |

- spike@\$20: base rate 0.0417, total events 14 across 1 folds.
- spike@\$100: base rate 0.0000, total events 0 across 1 folds. ⚠ 1/1 folds have <5 events (scores hollow there)

## HB_WEST  _(small sample — never averaged with Houston)_
_single 50/50 chronological holdout (small sample — NOT comparable to Houston) · n_test=336 · span 2026-07-01..2026-07-28_

| baseline | mean pinball | q10 | q25 | q50 | q75 | q90 | 10–90 cov |
|---|---|---|---|---|---|---|
| zero_spread | 3.454 | 2.711 | 2.989 | 3.454 | 3.919 | 4.198 | 0.000 |
| persistence | 5.222 | 5.255 | 5.242 | 5.222 | 5.201 | 5.189 | 0.000 |
| climatology | 2.702 | 2.025 | 2.857 | 3.375 | 3.050 | 2.202 | 0.735 |
| clim_persist | 3.288 | 2.535 | 3.475 | 4.037 | 3.688 | 2.707 | 0.664 |

Spike heads (direct probabilities):

| baseline | Brier@$20 | logloss@$20 | Brier@$100 | logloss@$100 |
|---|---|---|---|---|
| zero_spread | 0.0238 | 0.822 | 0.0030 | 0.103 |
| persistence | 0.0476 | 1.645 | 0.0060 | 0.206 |
| climatology | 0.0237 | 0.141 | 0.0030 | 0.103 |
| clim_persist | 0.0237 | 0.141 | 0.0030 | 0.103 |

- spike@\$20: base rate 0.0238, total events 8 across 1 folds.
- spike@\$100: base rate 0.0030, total events 1 across 1 folds. ⚠ 1/1 folds have <5 events (scores hollow there)
