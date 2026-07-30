# DART forecast — baseline results (walk-forward, no model yet)

- git SHA `437f80aaa7c8f16eb26d79009ca8d640285b2e42` · seed 42 · target **dart = DA - RT ($/MWh)** · quantiles [0.1, 0.25, 0.5, 0.75, 0.9] · spike heads $[20.0, 100.0]
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

## HB_NORTH
_walk-forward, 89 monthly folds, embargo 1d · n_test=64944 · span 2018-01-04..2026-06-30_

| baseline | mean pinball | q10 | q25 | q50 | q75 | q90 | 10–90 cov |
|---|---|---|---|---|---|---|
| zero_spread | 11.806 | 11.112 | 11.372 | 11.806 | 12.240 | 12.501 | 0.000 |
| persistence | 18.244 | 18.243 | 18.243 | 18.244 | 18.245 | 18.245 | 0.000 |
| climatology | 10.770 | 10.451 | 11.301 | 11.580 | 10.924 | 9.594 | 0.693 |
| clim_persist | 13.184 | 12.426 | 13.620 | 14.080 | 13.558 | 12.237 | 0.653 |

Spike heads (direct probabilities):

| baseline | Brier@$20 | logloss@$20 | Brier@$100 | logloss@$100 |
|---|---|---|---|---|
| zero_spread | 0.0462 | 1.595 | 0.0126 | 0.435 |
| persistence | 0.0821 | 2.835 | 0.0224 | 0.774 |
| climatology | 0.0437 | 0.289 | 0.0125 | 0.165 |
| clim_persist | 0.0437 | 0.289 | 0.0125 | 0.165 |

- spike@\$20: base rate 0.0462, total events 3000 across 89 folds. ⚠ 2/89 folds have <5 events (scores hollow there)
- spike@\$100: base rate 0.0126, total events 818 across 89 folds. ⚠ 38/89 folds have <5 events (scores hollow there)

## HB_SOUTH
_walk-forward, 89 monthly folds, embargo 1d · n_test=64944 · span 2018-01-04..2026-06-30_

| baseline | mean pinball | q10 | q25 | q50 | q75 | q90 | 10–90 cov |
|---|---|---|---|---|---|---|
| zero_spread | 11.344 | 10.547 | 10.846 | 11.344 | 11.843 | 12.142 | 0.000 |
| persistence | 17.512 | 17.511 | 17.511 | 17.512 | 17.513 | 17.514 | 0.000 |
| climatology | 10.362 | 9.901 | 10.795 | 11.141 | 10.591 | 9.380 | 0.691 |
| clim_persist | 12.662 | 11.862 | 13.042 | 13.521 | 13.055 | 11.828 | 0.653 |

Spike heads (direct probabilities):

| baseline | Brier@$20 | logloss@$20 | Brier@$100 | logloss@$100 |
|---|---|---|---|---|
| zero_spread | 0.0451 | 1.559 | 0.0125 | 0.432 |
| persistence | 0.0798 | 2.755 | 0.0221 | 0.765 |
| climatology | 0.0428 | 0.274 | 0.0124 | 0.156 |
| clim_persist | 0.0428 | 0.274 | 0.0124 | 0.156 |

- spike@\$20: base rate 0.0451, total events 2932 across 89 folds. ⚠ 1/89 folds have <5 events (scores hollow there)
- spike@\$100: base rate 0.0125, total events 813 across 89 folds. ⚠ 37/89 folds have <5 events (scores hollow there)

## HB_WEST
_walk-forward, 89 monthly folds, embargo 1d · n_test=64944 · span 2018-01-04..2026-06-30_

| baseline | mean pinball | q10 | q25 | q50 | q75 | q90 | 10–90 cov |
|---|---|---|---|---|---|---|
| zero_spread | 12.448 | 11.742 | 12.006 | 12.448 | 12.889 | 13.154 | 0.000 |
| persistence | 19.214 | 19.212 | 19.213 | 19.214 | 19.214 | 19.215 | 0.000 |
| climatology | 11.247 | 10.853 | 11.897 | 12.209 | 11.402 | 9.875 | 0.695 |
| clim_persist | 13.751 | 12.865 | 14.280 | 14.822 | 14.164 | 12.622 | 0.648 |

Spike heads (direct probabilities):

| baseline | Brier@$20 | logloss@$20 | Brier@$100 | logloss@$100 |
|---|---|---|---|---|
| zero_spread | 0.0562 | 1.942 | 0.0135 | 0.467 |
| persistence | 0.0991 | 3.424 | 0.0242 | 0.837 |
| climatology | 0.0527 | 0.311 | 0.0134 | 0.168 |
| clim_persist | 0.0527 | 0.311 | 0.0134 | 0.168 |

- spike@\$20: base rate 0.0562, total events 3651 across 89 folds. ⚠ 1/89 folds have <5 events (scores hollow there)
- spike@\$100: base rate 0.0135, total events 878 across 89 folds. ⚠ 32/89 folds have <5 events (scores hollow there)
