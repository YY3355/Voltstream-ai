"""Task 1 — DART forecast dataset assembly (per-hub hourly frame).

Target (CANONICAL for this research):  dart = DA - RT  ($/MWh), positive = DA settled rich.
This matches dart_engine.py:56 and the live signal rules. The climatology snapshot
(clim_result.json) uses the OPPOSITE sign (RT - DA) — see clim_features() for the tested adapter.

Information timing (lookahead-free, EXACTLY the live decision):
  delivery_date Dg = date of the target hour (day "D+1" in the live notation).
  decision_time = 16:00 ET / 15:00 CT on (Dg - 1 day) = day D, the live commit leg. Features use ONLY
  data with timestamp <= decision_time. The freshest same-hour datum is day Dg-1 for delivery hours
  H<=14 (the 14:00 CT hour is complete by 15:00 CT) and day Dg-2 for H>=15 (not yet realized). This
  MATCHES the live system exactly (its 15:00 CT pull sees the partial current day), so results
  represent the ACTUAL decision, not a more-conservative D-2 approximation. The DA curve for Dg is
  allowed (the DAM clears ~13:30 CT, before decision_time).

No synthetic data. Bad rows are DROPPED and COUNTED per hub (constraint 3). Deterministic.
Reads only committed stores (see DATA_SOURCES.md). NEVER writes journal/. No LLM.
"""
from __future__ import annotations
import os, glob, json, subprocess
import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .../voltstream-ai
HUBS = ["HB_HOUSTON", "HB_NORTH", "HB_SOUTH", "HB_WEST"]
RT_DECADE_HUB = "HB_HOUSTON"           # the only hub with a decade RT store
SEED = 42
Q_KEYS = ["0.05", "0.25", "0.5", "0.75", "0.95"]

def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "-C", REPO, "rev-parse", "HEAD"],
                                       text=True).strip()
    except Exception:
        return "UNKNOWN"

def _naive(idx) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(idx)
    return idx.tz_localize(None) if idx.tz is not None else idx

# ----------------------------- raw loaders (committed stores) -----------------------------
def load_da_hourly() -> pd.DataFrame:
    """Hourly DA by hub (naive Central). dam_decade (2018..2026) + dart_cache recency, dedup=last."""
    frames = []
    for f in sorted(glob.glob(os.path.join(REPO, "data_archive/dam_decade/*.pkl"))):
        df = pd.read_pickle(f)
        df.index = _naive(df.index)
        frames.append(df[[h for h in HUBS if h in df.columns]])
    # recent DA from dart_cache (long-format Location/SPP)
    rec = []
    for f in sorted(glob.glob(os.path.join(REPO, "dart_cache/DAY_AHEAD_HOURLY_*.pkl"))):
        d = pd.read_pickle(f)
        tcol = "Interval Start" if "Interval Start" in d.columns else "Time"
        d = d.copy()
        d["ts"] = _naive(pd.to_datetime(d[tcol]))
        d["hub"] = d["Location"].astype(str).str.upper()
        d = d[d["hub"].isin(HUBS)]
        rec.append(d.pivot_table(index="ts", columns="hub", values="SPP", aggfunc="mean"))
    if rec:
        frames.append(pd.concat(rec))
    da = pd.concat(frames)
    da = da[~da.index.duplicated(keep="last")].sort_index()
    return da

def load_rt_hourly() -> pd.DataFrame:
    """Hourly RT by hub (naive Central). Houston: decade 15-min store. Others: dart_cache 15-min."""
    # Houston decade (Series HB_HOUSTON_rt_spp, 15-min)
    hous = []
    for f in sorted(glob.glob(os.path.join(REPO, "data_archive/decade/*.pkl"))):
        s = pd.read_pickle(f)
        if isinstance(s, pd.Series) and len(s):
            s.index = _naive(s.index)
            hous.append(s)
    hh = pd.concat(hous).sort_index() if hous else pd.Series(dtype=float)
    hh = hh[~hh.index.duplicated(keep="last")].resample("1h").mean()
    cols = {RT_DECADE_HUB: hh}
    # NORTH/SOUTH/WEST RT: REPOINTED to the decade LOCATIONAL store (data_archive/locational/{hub}.pkl,
    # 15-min RT SPP 2018-2026), replacing the old ~28-day dart_cache source. Houston is verified
    # byte-identical between data_archive/decade/ and locational/ (Task 0 check), so Houston's path is
    # left untouched here and its assembled frame is unchanged.
    for h in HUBS:
        if h == RT_DECADE_HUB:
            continue
        p = os.path.join(REPO, f"data_archive/locational/{h}.pkl")
        if os.path.exists(p):
            s = pd.read_pickle(p)
            if isinstance(s, pd.Series) and len(s):
                s.index = _naive(s.index)
                cols[h] = s[~s.index.duplicated(keep="last")].resample("1h").mean()
    return pd.DataFrame(cols).sort_index()

def load_clim() -> dict:
    with open(os.path.join(REPO, "clim_result.json")) as fh:
        return json.load(fh)

# ----------------------------- climatology adapter (SIGN FLIP) -----------------------------
def clim_features(hub: str, months: np.ndarray, hours: np.ndarray, clim: dict) -> pd.DataFrame:
    """Per-(month,hour) climatology forecast of our target dart = DA - RT.

    clim stores quantiles of (RT - DA). Adapter to DA - RT:
        target_q[q] = -( clim_q[1 - q] )   and   P(DA>RT) = 1 - clim.p_rt_gt_da.
    Insufficient cells (n<30) -> NaN (dropped-and-counted downstream), never a flimsy estimate.
    """
    cells = clim.get("hubs", {}).get(hub, {}).get("cells", {})
    flip = {"0.05": "0.95", "0.25": "0.75", "0.5": "0.5", "0.75": "0.25", "0.95": "0.05"}
    rows = []
    for m, h in zip(months, hours):
        c = cells.get(f"{int(m)}-{int(h)}", {})
        ok = ("p_rt_gt_da" in c) and (not c.get("insufficient", False))
        q = c.get("dart_q", {}) if ok else {}
        rows.append({
            "clim_q05": -q["0.95"] if ok else np.nan,
            "clim_q25": -q["0.75"] if ok else np.nan,
            "clim_q50": -q["0.5"]  if ok else np.nan,
            "clim_q75": -q["0.25"] if ok else np.nan,
            "clim_q95": -q["0.05"] if ok else np.nan,
            "clim_dart_mean": -c["dart_mean"] if ok else np.nan,     # E[RT-DA] -> E[DA-RT]
            "clim_p_da_gt_rt": (1.0 - c["p_rt_gt_da"]) if ok else np.nan,
        })
    return pd.DataFrame(rows, index=range(len(months)))

# ----------------------------- feature registry (available_at rules) -----------------------------
# group -> available_at rule (enforced by the Task-3 leakage gate). All <= decision_time by design.
FEATURE_REGISTRY = {
    # delivery-day DA curve — DAM for Dg clears before decision_time (15:00 CT, Dg-1)
    "da":            {"group": "da_d1",   "available_at": "DAM clear day (Dg-1) <= decision_time"},
    "da_day_mean":   {"group": "da_d1",   "available_at": "DAM clear day (Dg-1) <= decision_time"},
    "da_day_max":    {"group": "da_d1",   "available_at": "DAM clear day (Dg-1) <= decision_time"},
    "da_day_min":    {"group": "da_d1",   "available_at": "DAM clear day (Dg-1) <= decision_time"},
    "da_day_range":  {"group": "da_d1",   "available_at": "DAM clear day (Dg-1) <= decision_time"},
    # lagged / trailing DART & RT — settled data with date <= Dg-2 (end of day D-1)
    "dart_persist":       {"group": "lag", "available_at": "<= decision_time (15:00 CT Dg-1; freshest same-hour Dg-1 for H<=14 else Dg-2)"},
    "dart_lag48":         {"group": "lag", "available_at": "<= decision_time (15:00 CT Dg-1; freshest same-hour Dg-1 for H<=14 else Dg-2)"},
    "dart_lag72":         {"group": "lag", "available_at": "<= decision_time (15:00 CT Dg-1; freshest same-hour Dg-1 for H<=14 else Dg-2)"},
    "dart_lag168":        {"group": "lag", "available_at": "<= decision_time (15:00 CT Dg-1; freshest same-hour Dg-1 for H<=14 else Dg-2)"},
    "dart_trail7_mean":   {"group": "lag", "available_at": "<= decision_time (15:00 CT Dg-1; freshest same-hour Dg-1 for H<=14 else Dg-2)"},
    "dart_trail7_std":    {"group": "lag", "available_at": "<= decision_time (15:00 CT Dg-1; freshest same-hour Dg-1 for H<=14 else Dg-2)"},
    "dart_trail30_mean":  {"group": "lag", "available_at": "<= decision_time (15:00 CT Dg-1; freshest same-hour Dg-1 for H<=14 else Dg-2)"},
    "rt_trail7_mean":     {"group": "lag", "available_at": "<= decision_time (15:00 CT Dg-1; freshest same-hour Dg-1 for H<=14 else Dg-2)"},
    "rt_trail7_std":      {"group": "lag", "available_at": "<= decision_time (15:00 CT Dg-1; freshest same-hour Dg-1 for H<=14 else Dg-2)"},
    # climatology snapshot — static, month/hour keyed (sign-flipped)
    "clim_q05": {"group": "clim", "available_at": "static climatology"},
    "clim_q25": {"group": "clim", "available_at": "static climatology"},
    "clim_q50": {"group": "clim", "available_at": "static climatology"},
    "clim_q75": {"group": "clim", "available_at": "static climatology"},
    "clim_q95": {"group": "clim", "available_at": "static climatology"},
    "clim_dart_mean":  {"group": "clim", "available_at": "static climatology"},
    "clim_p_da_gt_rt": {"group": "clim", "available_at": "static climatology"},
    # calendar — known arbitrarily far ahead
    "hour": {"group": "cal", "available_at": "deterministic calendar"},
    "dow":  {"group": "cal", "available_at": "deterministic calendar"},
    "month":{"group": "cal", "available_at": "deterministic calendar"},
    "is_weekend": {"group": "cal", "available_at": "deterministic calendar"},
    "hour_sin": {"group": "cal", "available_at": "deterministic calendar"},
    "hour_cos": {"group": "cal", "available_at": "deterministic calendar"},
    "doy_sin":  {"group": "cal", "available_at": "deterministic calendar"},
    "doy_cos":  {"group": "cal", "available_at": "deterministic calendar"},
}
# Registered-but-DEFERRED feature groups (added at model stage with coverage labels; never lookahead):
DEFERRED_GROUPS = {
    "weather_wind": "Open-Meteo Historical FORECAST API (archived forecasts, coverage 2022+); "
                    "net-load proxy. available_at = forecast issue <= decision_time. Added at Task 6.",
    "constraint":   "NP6-86-CD binding-constraint LAGGED aggregates (coverage 2026-06+). "
                    "available_at = settled SCED <= Dg-2. Added at Task 6.",
}
REALIZED_FEATURES = [c for c in FEATURE_REGISTRY]
CORE_REQUIRED = ["da", "dart_persist", "dart_lag48"]   # rows missing any of these are dropped

# ----------------------------- frame builder -----------------------------
def build_hub_frame(hub: str, da: pd.DataFrame | None = None,
                    rt: pd.DataFrame | None = None, clim: dict | None = None):
    """Return (frame, meta). frame indexed by delivery ts (hourly); target col 'dart' = DA-RT."""
    da = load_da_hourly() if da is None else da
    rt = load_rt_hourly() if rt is None else rt
    clim = load_clim() if clim is None else clim
    drops = {}

    if hub not in da.columns or hub not in rt.columns:
        return None, {"hub": hub, "status": "no_data", "n": 0}

    # per-hub RT coverage window (RT is the binding constraint off-Houston)
    rt_h = rt[hub].dropna()
    rt_cov = ("", "") if not len(rt_h) else (str(rt_h.index.min()), str(rt_h.index.max()))
    if not len(rt_h):
        return None, {"hub": hub, "status": "no_rt", "n_samples": 0}
    # over the RT-coverage window, form DA+RT pairs; COUNT every hour that can't (missing/nonfinite side)
    union = da.index.union(rt.index)
    union = union[(union >= rt_h.index.min()) & (union <= rt_h.index.max())]
    da_u = da[hub].reindex(union); rt_u = rt[hub].reindex(union)
    bad_pair = ~np.isfinite(da_u) | ~np.isfinite(rt_u)
    drops["incomplete_or_nonfinite_pair"] = int(bad_pair.sum())
    d = pd.DataFrame({"da": da_u[~bad_pair], "rt": rt_u[~bad_pair]}).sort_index()
    n_raw = len(d)
    d["dart"] = d["da"] - d["rt"]                      # CANONICAL target

    # --- lag/rolling features via (date x hour) pivot, cutoff = end of day D-1 = date <= Dg-2 ---
    dd = d.copy()
    dd["date"] = dd.index.normalize()
    dd["hour"] = dd.index.hour
    piv_dart = dd.pivot_table(index="date", columns="hour", values="dart")   # date x 24
    piv_rt   = dd.pivot_table(index="date", columns="hour", values="rt")
    # per-hour trailing stats over settled days, then shift so the window ends at Dg-2
    t7m  = piv_dart.rolling(7,  min_periods=3).mean()
    t7s  = piv_dart.rolling(7,  min_periods=3).std()
    t30m = piv_dart.rolling(30, min_periods=10).mean()
    rt7m = piv_rt.rolling(7, min_periods=3).mean()
    rt7s = piv_rt.rolling(7, min_periods=3).std()

    # assemble per delivery row
    dates = dd["date"].values
    hours = dd["hour"].values
    ddates = pd.DatetimeIndex(dd["date"])
    rows = {
        "dart": d["dart"].values, "da": d["da"].values,
        "hour": hours, "dow": ddates.dayofweek.values, "month": ddates.month.values,
    }
    # DA delivery-day shape
    da_day = dd.groupby("date")["da"].agg(["mean", "max", "min"])
    rows["da_day_mean"]  = da_day["mean"].reindex(ddates).values
    rows["da_day_max"]   = da_day["max"].reindex(ddates).values
    rows["da_day_min"]   = da_day["min"].reindex(ddates).values
    rows["da_day_range"] = rows["da_day_max"] - rows["da_day_min"]
    # lag/persistence/trailing at the EXACT live decision_time cutoff = 15:00 CT on Dg-1.
    # The freshest same-hour datum <= cutoff is day Dg-1 for delivery hours H<=14 (settled by 15:00 CT)
    # and day Dg-2 for H>=15 (not yet realized at 15:00). back = 1 (H<=14) else 2. This MATCHES the
    # live 16:00-ET commit leg (fetch_live sees the partial current day through ~15:00 CT), so results
    # represent the actual decision — not a more-conservative approximation.
    def col_at(pivot_like, back):
        shifted = pivot_like.copy(); shifted.index = shifted.index + pd.Timedelta(days=back)
        return shifted.reindex(ddates)
    def gather(shift_frame):
        return np.array([shift_frame.iat[i, hours[i]] if 0 <= hours[i] < shift_frame.shape[1] else np.nan
                         for i in range(len(hours))])
    def gather_fresh(pivot_like):
        """value at the freshest same-hour day <= decision_time: back=1 for H<=14 else back=2."""
        g1 = gather(col_at(pivot_like, 1)); g2 = gather(col_at(pivot_like, 2))
        return np.where(hours <= 14, g1, g2)
    def gather_fixed(pivot_like, back):
        return gather(col_at(pivot_like, back))
    rows["dart_persist"]      = gather_fresh(piv_dart)              # live-matching freshest same-hour
    rows["dart_lag48"]        = gather_fixed(piv_dart, 2)           # fixed 48h same hour (always Dg-2)
    rows["dart_lag72"]        = gather_fixed(piv_dart, 3)
    rows["dart_lag168"]       = gather_fixed(piv_dart, 7)
    rows["dart_trail7_mean"]  = gather_fresh(t7m)                   # window ends at the freshest day
    rows["dart_trail7_std"]   = gather_fresh(t7s)
    rows["dart_trail30_mean"] = gather_fresh(t30m)
    rows["rt_trail7_mean"]    = gather_fresh(rt7m)
    rows["rt_trail7_std"]     = gather_fresh(rt7s)
    # calendar cyclic
    rows["is_weekend"] = (ddates.dayofweek.values >= 5).astype(int)
    rows["hour_sin"] = np.sin(2*np.pi*hours/24); rows["hour_cos"] = np.cos(2*np.pi*hours/24)
    doy = ddates.dayofyear.values
    rows["doy_sin"] = np.sin(2*np.pi*doy/365.25); rows["doy_cos"] = np.cos(2*np.pi*doy/365.25)

    frame = pd.DataFrame(rows, index=d.index)
    # climatology features (sign-flipped)
    cf = clim_features(hub, frame["month"].values, frame["hour"].values, clim)
    cf.index = frame.index
    frame = pd.concat([frame, cf], axis=1)

    # drop rows missing target or CORE realized features (early history warmup), COUNT
    bad_target = ~np.isfinite(frame["dart"])
    drops["nonfinite_target"] = int(bad_target.sum())
    core_missing = frame[CORE_REQUIRED].isna().any(axis=1) & ~bad_target
    drops["core_feature_warmup"] = int(core_missing.sum())
    keep = ~bad_target & ~core_missing
    frame = frame[keep]

    span = ("", "") if not len(frame) else (str(frame.index.min()), str(frame.index.max()))
    # per-column NaN counts (transparency): trailing features are legitimately MISSING at warmup/DST
    # edges and are handled as model-native missing (LightGBM), NEVER imputed to a value (constraint 3).
    realized_cols = [c for c in REALIZED_FEATURES if c in frame.columns]
    feat_nan = {c: int((~np.isfinite(frame[c])).sum()) for c in realized_cols
                if not np.isfinite(frame[c]).all()}
    meta = {
        "hub": hub, "status": "ok" if len(frame) else "empty",
        "n_raw_paired": int(n_raw), "n_samples": int(len(frame)),
        "span": span, "rt_coverage": rt_cov, "drop_counts": drops,
        "feature_nan_counts": feat_nan,
        "nan_policy": "bad rows (nonfinite target/price pair) dropped+counted; trailing-feature NaN "
                      "at warmup/DST edges kept as model-native missing, never imputed to a value",
        "target": "dart = DA - RT ($/MWh)", "seed": SEED, "git_sha": git_sha(),
        "features_realized": list(cf.columns) + [c for c in rows if c != "dart"],
        "feature_groups_deferred": list(DEFERRED_GROUPS),
        "small_sample": int(len(frame)) < 8760,   # <1yr of paired hours (n-based, not hub-name)
    }
    return frame, meta

def build_all():
    da, rt, clim = load_da_hourly(), load_rt_hourly(), load_clim()
    frames, metas = {}, {}
    for h in HUBS:
        fr, mt = build_hub_frame(h, da, rt, clim)
        metas[h] = mt
        if fr is not None and len(fr):
            frames[h] = fr
    return frames, metas

if __name__ == "__main__":
    frames, metas = build_all()
    out = {
        "kind": "dart_forecast_dataset_meta",
        "target_sign_convention": "dart = DA - RT ($/MWh); positive = DA rich",
        "decision_time": "15:00 CT on day D (Dg-1); uniform settled cutoff date <= Dg-2",
        "git_sha": git_sha(), "seed": SEED,
        "feature_registry": FEATURE_REGISTRY,
        "deferred_groups": DEFERRED_GROUPS,
        "hubs": metas,
    }
    dst = os.path.join(REPO, "research/dart_forecast/dataset_meta.json")
    with open(dst, "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    for h, m in metas.items():
        print(f"{h:12s} status={m['status']:5s} n={m.get('n_samples',0):>6} "
              f"span={m.get('span',('',''))[0][:10]}..{m.get('span',('',''))[1][:10]} "
              f"drops={m.get('drop_counts',{})} small_sample={m.get('small_sample')}")
    print("wrote", dst)
