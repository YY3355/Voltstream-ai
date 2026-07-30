# DART forecast — baseline results (walk-forward, no model yet)

- git SHA: `2a4920a80af94fc9e4fba46b68056136d8fa41b9`  · seed: 42  · generated: 2026-07-30T02:59:25.632370+00:00
- target: **dart = DA - RT ($/MWh)**  · quantiles: [0.1, 0.25, 0.5, 0.75, 0.9]  · spike T: $20.0/MWh
- ⚠ HB_NORTH/SOUTH/WEST: ~28-day RT coverage, single holdout, small-sample — NEVER averaged into a headline with Houston.

## HB_HOUSTON

| method | n | mean pinball | pin q10 | pin q25 | pin q50 | pin q75 | pin q90 | 10–90 cov | spike Brier | spike base |
|---|---|---|---|---|---|---|---|---|---|---|
| zero_spread | 64952 | 12.1886 | 11.4983 | 11.7571 | 12.1886 | 12.6200 | 12.8789 | 0.0001 | 0.0466 | 0.047 |
| persistence | 64952 | 19.1136 | 19.1131 | 19.1133 | 19.1136 | 19.1139 | 19.1141 | 0.0000 | 0.0836 | 0.047 |
| climatology | 64952 | 11.0990 | 10.8849 | 11.7000 | 11.9063 | 11.1856 | 9.8183 | 0.6938 | 0.0441 | 0.047 |

_span: 2018-01-04..2026-06-30_

## HB_NORTH  _(small sample — never averaged with Houston)_

| method | n | mean pinball | pin q10 | pin q25 | pin q50 | pin q75 | pin q90 | 10–90 cov | spike Brier | spike base |
|---|---|---|---|---|---|---|---|---|---|---|
| zero_spread | 336 | 3.4264 | 2.5896 | 2.9034 | 3.4264 | 3.9494 | 4.2632 | 0.0000 | 0.0268 | 0.027 |
| persistence | 336 | 5.1485 | 5.2151 | 5.1901 | 5.1485 | 5.1068 | 5.0818 | 0.0000 | 0.0506 | 0.027 |
| climatology | 336 | 2.7806 | 2.0465 | 2.8314 | 3.3541 | 3.2045 | 2.4666 | 0.7232 | 0.0266 | 0.027 |

_span: 2026-07-01..2026-07-28_

## HB_SOUTH  _(small sample — never averaged with Houston)_

| method | n | mean pinball | pin q10 | pin q25 | pin q50 | pin q75 | pin q90 | 10–90 cov | spike Brier | spike base |
|---|---|---|---|---|---|---|---|---|---|---|
| zero_spread | 336 | 3.6308 | 2.9896 | 3.2301 | 3.6308 | 4.0316 | 4.2721 | 0.0000 | 0.0417 | 0.042 |
| persistence | 336 | 5.7115 | 5.5811 | 5.6300 | 5.7115 | 5.7931 | 5.8420 | 0.0000 | 0.0833 | 0.042 |
| climatology | 336 | 2.8175 | 2.5060 | 3.2024 | 3.4552 | 2.9196 | 2.0044 | 0.6994 | 0.0417 | 0.042 |

_span: 2026-07-01..2026-07-28_

## HB_WEST  _(small sample — never averaged with Houston)_

| method | n | mean pinball | pin q10 | pin q25 | pin q50 | pin q75 | pin q90 | 10–90 cov | spike Brier | spike base |
|---|---|---|---|---|---|---|---|---|---|---|
| zero_spread | 336 | 3.4540 | 2.7105 | 2.9893 | 3.4540 | 3.9187 | 4.1975 | 0.0000 | 0.0238 | 0.024 |
| persistence | 336 | 5.4424 | 5.4711 | 5.4604 | 5.4424 | 5.4245 | 5.4137 | 0.0000 | 0.0476 | 0.024 |
| climatology | 336 | 2.7018 | 2.0249 | 2.8568 | 3.3754 | 3.0502 | 2.2015 | 0.7351 | 0.0237 | 0.024 |

_span: 2026-07-01..2026-07-28_
