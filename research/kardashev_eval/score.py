"""
score.py — Kardashev-eval Task 3: join their forecasts to OUR realized spread and score.

Scored quantity = the spread in THEIR convention (RT - DA), computed from OUR prices (dart_cache DA +
RT), so pinball/coverage read directly against their published p10/p50/p90 (no sign juggling; the sign
gate proved realized_spread = RT - DA = -dart). Scoring is independent: OUR realized, never their `rt`/
`spread`/`da`. NO LLM.

Metrics (n beside every one):
  - pinball loss per published quantile (0.1, 0.5, 0.9), lower better
  - empirical coverage of their 80% interval [p10, p90] vs the 80% target
Baselines on IDENTICAL (node, ts) coordinates:
  - climatology  : deep-history spread quantiles by (hub, hour-of-day) — a real probabilistic baseline
  - zero         : spread = 0 (point)
  - persistence  : realized spread at ts-24h (point)
Each MODEL (tft-2026q3, tft-v2-2026q3) scored separately. Unsettled/uncovered delivery hours excluded
with a count.
"""
import glob
import json
import os
import numpy as np
import pandas as pd

HUBS = ["HB_HOUSTON", "HB_NORTH", "HB_SOUTH", "HB_WEST"]      # our verified coverage
MODELS = ["tft-2026q3", "tft-v2-2026q3"]
HERE = os.path.dirname(__file__)
SNAP = os.path.join(HERE, "snapshot_2026-08-02")


def pinball(tau, q, y):
    d = y - q
    return tau * d if d >= 0 else (tau - 1) * d


# ---- OUR realized spread (RT - DA), keyed (hub, ts_utc), from dart_cache (gridstatus) ----
def build_realized():
    real = {}
    for da_path in sorted(glob.glob("dart_cache/DAY_AHEAD_HOURLY_*.pkl")):
        day = da_path[-14:-4]
        rt_path = f"dart_cache/REAL_TIME_15_MIN_{day}.pkl"
        if not os.path.exists(rt_path):
            continue
        da = pd.read_pickle(da_path)
        rt = pd.read_pickle(rt_path)
        for hub in HUBS:
            dh = da[da["Location"].astype(str).str.upper() == hub]
            da_u = {pd.Timestamp(t).tz_convert("UTC"): float(v) for t, v in zip(dh["Interval Start"], dh["SPP"])}
            rh = rt[rt["Location"].astype(str).str.upper() == hub].copy()
            rh["h"] = pd.to_datetime(rh["Interval Start"]).dt.tz_convert("UTC").dt.floor("h")
            rt_h = rh.groupby("h")["SPP"].mean()
            for ts_utc, da_v in da_u.items():
                if ts_utc in rt_h.index:
                    real[(hub, ts_utc)] = float(rt_h[ts_utc]) - da_v      # RT - DA (their convention)
    return real


# ---- climatology: deep-history spread quantiles by (hub, hour-of-day CDT), pre-window training ----
def build_climatology(train_start="2026-05-01", train_end="2026-07-07"):
    dam = pd.read_pickle("data_archive/dam_decade/2026.pkl")            # DA, naive CDT hour-beginning
    dam = dam[(dam.index >= train_start) & (dam.index <= train_end)]
    clim = {}
    for hub in HUBS:
        rt = pd.read_pickle(f"data_archive/locational/{hub}.pkl")        # RT 15-min, naive CDT
        rt = rt[(rt.index >= train_start) & (rt.index <= train_end)]
        rt_h = rt.groupby([rt.index.date, rt.index.hour]).mean()          # hourly mean, hour-beginning
        da_h = dam[hub]
        spreads_by_hour = {h: [] for h in range(24)}
        for (d, h), rtv in rt_h.items():
            key = pd.Timestamp(d) + pd.Timedelta(hours=h)
            if key in da_h.index:
                spreads_by_hour[h].append(rtv - da_h[key])                 # RT - DA
        for h in range(24):
            arr = np.array(spreads_by_hour[h], dtype=float)
            if len(arr) >= 10:
                clim[(hub, h)] = (np.quantile(arr, 0.1), np.quantile(arr, 0.5), np.quantile(arr, 0.9), len(arr))
    return clim


def build_scored():
    """Join their frozen forecasts to OUR realized spread + baselines. Returns (df, H, excluded):
    df = all timing-valid deduped rows with realized; H = head-to-head subset (realized + persistence-
    prior + climatology all defined). Shared by score.main() and tail.py so both use ONE join."""
    real = build_realized()
    clim = build_climatology()
    their = {hub: json.load(open(os.path.join(SNAP, f"history_{hub}.json"))) for hub in HUBS}

    excluded = {"no_realized": 0, "untimely": 0, "duplicates_collapsed": 0}
    # DEDUP: the API returns exact duplicate rows; and in general a delivery hour could be re-forecast
    # by multiple issuances. Keep ONE record per (hub, ts, model) = the LATEST issued_at (the best
    # forecast available before delivery). One delivery-hour is scored once.
    scored = []
    for hub in HUBS:
        latest = {}
        for r in their[hub]:
            if r["model"] not in MODELS:
                continue
            key = (r["ts"], r["model"])
            if key not in latest or r["issued_at"] > latest[key]["issued_at"]:
                if key in latest:
                    excluded["duplicates_collapsed"] += 1
                latest[key] = r
            else:
                excluded["duplicates_collapsed"] += 1
        for r in latest.values():
            ts = pd.Timestamp(r["ts"]).tz_convert("UTC")
            if r["issued_at"] >= r["ts"]:                                   # timing gate (constraint 3)
                excluded["untimely"] += 1
                continue
            if (hub, ts) not in real:                                       # unsettled / not in our store
                excluded["no_realized"] += 1
                continue
            y = real[(hub, ts)]
            cdt_hour = (ts - pd.Timedelta(hours=5)).hour                    # CDT hour-of-day
            persist_key = (hub, ts - pd.Timedelta(days=1))
            scored.append({"hub": hub, "ts": ts, "model": r["model"], "y": y,
                           "p10": r["p10"], "p50": r["p50"], "p90": r["p90"],
                           "cdt_hour": cdt_hour,
                           "persist": real.get(persist_key), "clim": clim.get((hub, cdt_hour))})
    df = pd.DataFrame(scored)
    # identical-coordinate set for head-to-head: realized + persistence-prior + climatology all defined
    ok = df["persist"].notna() & df["clim"].notna()
    excluded["no_persistence"] = int((~df["persist"].notna()).sum())
    excluded["no_clim"] = int((df["persist"].notna() & df["clim"].isna()).sum())
    H = df[ok].copy()                                                      # head-to-head coordinates
    return df, H, excluded


def main():
    df, H, excluded = build_scored()

    def quantile_block(sub, label, qcols):
        """Score a probabilistic forecast (3 quantile columns) on subframe `sub`."""
        y = sub["y"].values
        out = {"who": label, "n_nodehours": len(sub)}
        p10v, p50v, p90v = (sub[qcols[0]].values, sub[qcols[1]].values, sub[qcols[2]].values)
        out["pin10"] = np.mean([pinball(0.1, q, yy) for q, yy in zip(p10v, y)])
        out["pin50"] = np.mean([pinball(0.5, q, yy) for q, yy in zip(p50v, y)])
        out["pin90"] = np.mean([pinball(0.9, q, yy) for q, yy in zip(p90v, y)])
        out["pin_avg"] = np.mean([out["pin10"], out["pin50"], out["pin90"]])
        out["cover80"] = np.mean((y >= p10v) & (y <= p90v))
        return out

    def point_block(sub, label, qvals):
        """Score a POINT forecast (same value at every quantile); coverage n/a (no interval)."""
        y = sub["y"].values
        out = {"who": label, "n_nodehours": len(sub)}
        out["pin10"] = np.mean([pinball(0.1, qvals[j], y[j]) for j in range(len(y))])
        out["pin50"] = np.mean([pinball(0.5, qvals[j], y[j]) for j in range(len(y))])
        out["pin90"] = np.mean([pinball(0.9, qvals[j], y[j]) for j in range(len(y))])
        out["pin_avg"] = np.mean([out["pin10"], out["pin50"], out["pin90"]])
        out["cover80"] = float("nan")
        return out

    pd.set_option("display.width", 200, "display.float_format", lambda v: f"{v:.3f}")
    cols = ["who", "n_nodehours", "pin10", "pin50", "pin90", "pin_avg", "cover80"]
    print("PER-MODEL scoring — each MODEL vs baselines on ITS OWN identical coordinates")
    print(f"(realized + persistence-prior + climatology all defined). Hubs: {HUBS}. Coverage TARGET = 0.80.\n")
    for m in MODELS:
        c = H[H["model"] == m].copy()                                       # this model's coordinate set
        c["clim_p10"] = [x[0] for x in c["clim"]]
        c["clim_p50"] = [x[1] for x in c["clim"]]
        c["clim_p90"] = [x[2] for x in c["clim"]]
        rows = [quantile_block(c, m, ["p10", "p50", "p90"]),
                quantile_block(c, "climatology", ["clim_p10", "clim_p50", "clim_p90"]),
                point_block(c, "zero", np.zeros(len(c))),
                point_block(c, "persistence", c["persist"].values.astype(float))]
        print(f"--- {m}  (n={len(c)} node-hours) ---")
        print(pd.DataFrame(rows)[cols].to_string(index=False))
        # per-hub coverage + n for this model (constraint 5)
        ph = c.groupby("hub").apply(lambda g: pd.Series({
            "n": len(g), "cover80": np.mean((g["y"] >= g["p10"]) & (g["y"] <= g["p90"])),
            "pin_avg": np.mean([pinball(0.1, a, y) for a, y in zip(g["p10"], g["y"])]
                               + [pinball(0.5, a, y) for a, y in zip(g["p50"], g["y"])]
                               + [pinball(0.9, a, y) for a, y in zip(g["p90"], g["y"])])}),
            include_groups=False)
        print("  per-hub:", {h: (int(r["n"]), round(r["cover80"], 3)) for h, r in ph.iterrows()}, "\n")
    print(f"excluded (delivery hours dropped): {excluded}")
    print(f"total timing-valid model-rows with realized: {len(df)}; head-to-head rows: {len(H)}")


if __name__ == "__main__":
    main()
