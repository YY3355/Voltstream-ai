"""
tail.py — Kardashev-eval Task 4: does coverage hold in the TAIL, or only on average?

Their admitted pain is the spike head. Split scored delivery-hours by regime and re-score:
  calm  = |realized spread| below the top decile
  tail  = |realized spread| in the top decile (the big RT-DA divergences)
The tail bucket is a property of the delivery HOUR (its realized |spread|), so the same threshold
buckets every model + baseline. Reports per (model, bucket): n, 80%-interval coverage, avg pinball, and
a reliability triple (empirical P(y<=p10 / p50 / p90); nominal 0.10/0.50/0.90). Climatology shown per
bucket for comparison. Buckets with <5 events are flagged "insufficient events (k)" (constraint 4).
Reuses score.build_scored() so the join/dedup/timing logic is identical to Task 3.
"""
import numpy as np
import pandas as pd

import score
from score import MODELS, pinball

TAIL_Q = 0.90            # top decile by |realized spread|


def block(sub, qcols, label):
    n = len(sub)
    if n < 5:
        return {"who": label, "n": n, "note": f"insufficient events ({n})"}
    y = sub["y"].values
    p10, p50, p90 = sub[qcols[0]].values, sub[qcols[1]].values, sub[qcols[2]].values
    return {"who": label, "n": n,
            "cover80": np.mean((y >= p10) & (y <= p90)),
            "pin_avg": np.mean([pinball(0.1, a, b) for a, b in zip(p10, y)]
                               + [pinball(0.5, a, b) for a, b in zip(p50, y)]
                               + [pinball(0.9, a, b) for a, b in zip(p90, y)]),
            "PIT_p10": np.mean(y <= p10), "PIT_p50": np.mean(y <= p50), "PIT_p90": np.mean(y <= p90)}


def main():
    _, H, _ = score.build_scored()
    H = H.copy()
    for q in ("clim_p10", "clim_p50", "clim_p90"):
        H[q] = [x[["clim_p10", "clim_p50", "clim_p90"].index(q)] for x in H["clim"]]
    # tail threshold from UNIQUE delivery hours (hub, ts), so it's model-independent
    uniq = H.drop_duplicates(["hub", "ts"])
    thr = float(np.quantile(uniq["y"].abs(), TAIL_Q))
    H["bucket"] = np.where(H["y"].abs() >= thr, "tail", "calm")
    print(f"tail threshold |spread| >= {thr:.2f} $  (top decile of {len(uniq)} unique delivery-hours; "
          f"tail hours={int((uniq['y'].abs()>=thr).sum())})\n")

    rows = []
    for m in MODELS:
        for bucket in ["calm", "tail"]:
            sub = H[(H["model"] == m) & (H["bucket"] == bucket)]
            rows.append({**block(sub, ["p10", "p50", "p90"], f"{m}"), "bucket": bucket})
        # climatology on this model's coords, per bucket (baseline reference)
        for bucket in ["calm", "tail"]:
            sub = H[(H["model"] == m) & (H["bucket"] == bucket)]
            rows.append({**block(sub, ["clim_p10", "clim_p50", "clim_p90"], "  climatology"), "bucket": bucket})
    res = pd.DataFrame(rows)
    pd.set_option("display.width", 220, "display.float_format", lambda v: f"{v:.3f}")
    cols = ["who", "bucket", "n", "cover80", "pin_avg", "PIT_p10", "PIT_p50", "PIT_p90"]
    for c in cols:
        if c not in res:
            res[c] = np.nan
    print(res[cols].to_string(index=False))
    print("\nreading: cover80 target = 0.80; PIT_p10 target 0.10, PIT_p50 0.50, PIT_p90 0.90.")
    print("the tail question: does cover80 hold from calm -> tail, or collapse?")


if __name__ == "__main__":
    main()
