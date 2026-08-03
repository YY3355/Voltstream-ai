# Tail focus (Task 4) — does coverage hold in the spike head?

Regime split by realized |spread|: **tail = top decile (|spread| ≥ $13.09)**, calm = the rest. Threshold
from the 1676 unique delivery-hours (168 tail hours). Reproduce: `python research/kardashev_eval/tail.py`.

| forecast | bucket | n | cover80 (t 0.80) | pin_avg | PIT_p10 (t .10) | PIT_p50 (t .50) | PIT_p90 (t .90) |
|---|---|---|---|---|---|---|---|
| **tft-2026q3** | calm | 1411 | 0.787 | 1.244 | 0.137 | 0.563 | 0.923 |
| **tft-2026q3** | **tail** | 165 | **0.600** | 6.449 | 0.255 | 0.667 | 0.855 |
| climatology | calm | 1411 | 0.908 | 1.375 | 0.072 | 0.647 | 0.979 |
| climatology | **tail** | 165 | **0.200** | 9.179 | 0.582 | 0.782 | 0.782 |
| **tft-v2-2026q3** | calm | 1221 | 0.869 | 1.436 | 0.084 | 0.603 | 0.952 |
| **tft-v2-2026q3** | **tail** | 159 | **0.616** | 8.278 | 0.283 | 0.742 | 0.899 |
| climatology | calm | 1221 | 0.900 | 1.397 | 0.078 | 0.649 | 0.978 |
| climatology | **tail** | 159 | **0.220** | 9.222 | 0.604 | 0.818 | 0.824 |

(All buckets have events ≥ 5; the tail buckets are n≈160, adequate for a coverage fraction but small —
no significance claimed, constraint 4.)

## Findings
1. **Coverage holds on average but COLLAPSES in the tail.** Both models fall from ~0.79–0.87 (calm) to
   **~0.60 (tail)** — a ~19–25 pt drop. The clip-then-widen interval holds its 80% target on average
   (Task 3) but **not in the spike head**. This confirms their admitted pain empirically.
2. **Yet both models vastly outperform the naive baseline exactly where it matters.** In the tail,
   climatology covers only **0.20** (a static hourly distribution can't anticipate spikes) with pinball
   ~9.2; the models cover ~0.60 with pinball 6.4–8.3. So the models *do* capture much of the spike
   behavior — they under-cover it, they don't miss it.
3. **The tail miss is asymmetric — a downside-magnitude miss.** In the tail, PIT_p10 rises to
   **0.26–0.28** (nominal 0.10): ~1-in-4 tail spreads fall *below* the p10 floor, i.e. the models
   under-predict how far the RT-DA spread swings on the big-move hours. PIT_p90 stays near/just-below
   nominal, so the upper edge is closer to right — the lower edge is where the tail leaks.
4. **v2's extra width buys calm coverage, not tail coverage.** tft-v2 is wider everywhere (calm cover
   0.869 vs v1's 0.787) but its tail coverage (0.616) is essentially the same as v1's (0.600). The
   widening is spent on the calm bucket; it does not specifically defend the tail.

## One-line takeaway
Both Kardashev models are calibrated on average and clearly beat climatology/persistence, including in the
tail — but their 80% interval under-covers the top-decile spike hours (~0.60 vs 0.80), and the leak is on
the downside (p10) side. Small window (168 tail hours); reported as observation, not significance.
