"""
map_layers.py  —  Phase 2 (final): county heat + an honest day-ahead forecast.

TWO LAYERS, BOTH DERIVED FROM DATA WE ALREADY HAVE HONESTLY.

1) COUNTY HEAT.  235 real EIA batteries, each with a real county and coordinate -> MW by
   county. This is a rollup of facts, not an interpolation. (We deliberately do NOT paint a
   price surface across Texas: we have 4 hub prices, and smearing 4 points into a colored
   map would be interpolation dressed as data.)

2) DAY-AHEAD FORECAST.  IMPORTANT DISTINCTION, and the reason this module exists:
   forecast_engine.py is a NOWCASTER — its features (lag1 = 15 min ago, lag4 = 1 hour ago,
   roll1h) only exist for the NEXT interval. That is exactly right for the RT engine's
   receding-horizon loop, which re-plans each step with fresh lags. But it CANNOT honestly
   forecast 24 hours ahead: those features are unknown at that horizon, and feeding
   predictions back in (recursive forecasting) compounds error and produces a confident-
   looking fake.

   So this uses a day-ahead-legitimate feature set: ONLY lags >= 24h (same time yesterday,
   2 days ago, 7 days ago) plus calendar terms. Every feature is genuinely known at forecast
   time. Quantiles P10/P50/P90 via gradient boosting, same family as the existing engine.

   It is a weaker model than the nowcaster, and it should be: forecasting tomorrow is
   harder than forecasting the next 15 minutes. The honest number is the one that admits it.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

DAY = 96          # 15-min intervals per day
QUANTILES = (0.1, 0.5, 0.9)
FEATS = ["sin_d", "cos_d", "sin_w", "cos_w", "lag96", "lag192", "lag672", "roll_d"]


# ----------------------------- day-ahead features (all known 24h out) -----------------------------
def day_ahead_features(s: pd.Series) -> pd.DataFrame:
    """Causal features that are ALL available at least 24h before the target interval."""
    s = s.astype(float)
    df = pd.DataFrame(index=s.index)
    df["y"] = s.values
    tod = s.index.hour * 4 + s.index.minute // 15                 # interval-of-day
    df["sin_d"] = np.sin(2 * np.pi * tod / DAY)
    df["cos_d"] = np.cos(2 * np.pi * tod / DAY)
    dow = s.index.dayofweek
    df["sin_w"] = np.sin(2 * np.pi * dow / 7)
    df["cos_w"] = np.cos(2 * np.pi * dow / 7)
    df["lag96"] = s.shift(DAY)                                    # same time yesterday
    df["lag192"] = s.shift(2 * DAY)                               # same time 2 days ago
    df["lag672"] = s.shift(7 * DAY)                               # same time last week
    df["roll_d"] = s.shift(DAY).rolling(DAY).mean()               # yesterday's daily mean
    return df


def fit_forecast(train: pd.DataFrame, future: pd.DataFrame):
    """Train quantile GBMs on `train`, predict the `future` feature rows."""
    X, y = train[FEATS].values, train["y"].values
    out = {}
    for q in QUANTILES:
        m = GradientBoostingRegressor(loss="quantile", alpha=q, n_estimators=120,
                                      max_depth=3, learning_rate=0.08, random_state=7)
        m.fit(X, y)
        out[q] = m.predict(future[FEATS].values)
    # enforce monotone quantiles (GBMs fit independently can cross)
    p10, p50, p90 = out[0.1], out[0.5], out[0.9]
    lo = np.minimum.reduce([p10, p50, p90])
    hi = np.maximum.reduce([p10, p50, p90])
    mid = np.median(np.vstack([p10, p50, p90]), axis=0)
    return {0.1: lo, 0.5: mid, 0.9: hi}


def build_future_rows(s: pd.Series, horizon=DAY) -> pd.DataFrame:
    """Feature rows for the next `horizon` intervals, using ONLY known history."""
    freq = pd.Timedelta("15min")
    future_idx = pd.date_range(s.index.max() + freq, periods=horizon, freq=freq)
    ext = pd.concat([s, pd.Series(np.nan, index=future_idx)])
    f = day_ahead_features(ext)
    fut = f.loc[future_idx]
    return fut.dropna(subset=[c for c in FEATS])


def forecast_hub(prices: pd.Series, horizon=DAY, min_train=DAY * 10):
    """Honest next-24h P10/P50/P90 for one hub. Raises if history is too thin."""
    s = prices.dropna().astype(float).sort_index()
    feat = day_ahead_features(s).dropna()
    if len(feat) < min_train:
        raise RuntimeError(f"need >= {min_train} feature rows for a day-ahead model, have {len(feat)}")
    fut = build_future_rows(s, horizon)
    if fut.empty:
        raise RuntimeError("cannot build future feature rows (history gap)")
    preds = fit_forecast(feat, fut)
    return {
        "times": [t.strftime("%Y-%m-%d %H:%M") for t in fut.index],
        "p10": [round(float(x), 2) for x in preds[0.1]],
        "p50": [round(float(x), 2) for x in preds[0.5]],
        "p90": [round(float(x), 2) for x in preds[0.9]],
        "train_rows": int(len(feat)),
        "history_end": str(s.index.max()),
        "model": "gradient-boosted quantile regression, day-ahead feature set (lags >= 24h)",
        "caveat": ("A DAY-AHEAD model, deliberately separate from the platform's nowcaster: "
                   "it uses only features known 24h in advance (same-time yesterday / 2 days / "
                   "last week + calendar). Weaker than the nowcaster by design — forecasting "
                   "tomorrow is harder than forecasting the next 15 minutes."),
    }


# ----------------------------- county heat -----------------------------
def county_heat(batteries: pd.DataFrame, top_n=25):
    """MW by county from real assets. A rollup of facts — not an interpolated surface."""
    if batteries is None or batteries.empty:
        return {"counties": [], "total_mw": 0, "n_counties": 0,
                "note": "no battery geography cached — run geo_data.py fetch"}
    g = (batteries.groupby("county")
         .agg(mw=("mw", "sum"), assets=("mw", "size"),
              lat=("lat", "mean"), lon=("lon", "mean"))
         .reset_index().sort_values("mw", ascending=False))
    total = float(g["mw"].sum())
    rows = [{"county": r.county, "mw": round(float(r.mw), 1), "assets": int(r.assets),
             "lat": round(float(r.lat), 4), "lon": round(float(r.lon), 4),
             "share_pct": round(100 * float(r.mw) / total, 1) if total else 0.0}
            for r in g.itertuples()]
    return {
        "counties": rows[:top_n],
        "all_counties": rows,
        "n_counties": int(len(rows)),
        "total_mw": round(total, 1),
        "top_share_pct": round(sum(r["share_pct"] for r in rows[:5]), 1),
        "note": ("Battery MW aggregated by county from EIA asset coordinates. County points "
                 "are the mean position of that county's assets — a marker, not a boundary. "
                 "This is a rollup of real assets, not an interpolated surface."),
    }


# ----------------------------- fixture self-test -----------------------------
if __name__ == "__main__":
    # ---- forecast: build a series with a strong daily shape + weekly effect ----
    idx = pd.date_range("2026-06-01", periods=DAY * 30, freq="15min")
    tod = idx.hour * 4 + idx.minute // 15
    base = 30 + 12 * np.sin(2 * np.pi * (tod - 20) / DAY)
    weekend = np.where(idx.dayofweek >= 5, -6.0, 0.0)
    rng = np.random.default_rng(3)
    s = pd.Series(base + weekend + rng.normal(0, 2.0, len(idx)), index=idx)

    f = forecast_hub(s)
    assert len(f["p50"]) == DAY, f"expected 96 forecast points, got {len(f['p50'])}"
    assert all(a <= b <= c for a, b, c in zip(f["p10"], f["p50"], f["p90"])), "quantiles must not cross"
    # the model should recover the daily shape: peak forecast > trough forecast
    assert max(f["p50"]) - min(f["p50"]) > 8, "should capture the daily swing"
    # sanity: forecasts land in a plausible range of the training data
    assert 10 < np.mean(f["p50"]) < 55, f"forecast mean off: {np.mean(f['p50'])}"
    # honesty: every feature used must be knowable 24h ahead
    assert all(x in ("sin_d", "cos_d", "sin_w", "cos_w", "lag96", "lag192", "lag672", "roll_d")
               for x in FEATS), "no sub-24h lag may appear in a day-ahead model"
    assert "lag1" not in FEATS and "lag4" not in FEATS and "roll1h" not in FEATS

    thin = s.iloc[: DAY * 3]
    try:
        forecast_hub(thin); raise AssertionError("should refuse to forecast on thin history")
    except RuntimeError:
        pass

    # ---- county heat ----
    batt = pd.DataFrame([
        {"county": "Brazoria", "mw": 700.0, "lat": 29.1, "lon": -95.4},
        {"county": "Brazoria", "mw": 552.0, "lat": 29.2, "lon": -95.5},
        {"county": "Ector", "mw": 300.0, "lat": 31.8, "lon": -102.4},
        {"county": "Harris", "mw": 100.0, "lat": 29.8, "lon": -95.4},
    ])
    ch = county_heat(batt)
    assert ch["n_counties"] == 3 and ch["total_mw"] == 1652.0
    assert ch["counties"][0]["county"] == "Brazoria" and ch["counties"][0]["assets"] == 2
    assert ch["counties"][0]["mw"] == 1252.0, "Brazoria must aggregate both assets"
    assert abs(sum(c["share_pct"] for c in ch["all_counties"]) - 100.0) < 0.5, "shares must sum ~100"
    assert abs(ch["counties"][0]["lat"] - 29.15) < 0.01, "county point = mean of its assets"
    empty = county_heat(pd.DataFrame())
    assert empty["counties"] == [] and "run geo_data.py fetch" in empty["note"]

    print("fixture self-test PASSED")
    print(f"  forecast: 96 pts, quantiles ordered, daily swing "
          f"${min(f['p50']):.1f}-${max(f['p50']):.1f}, day-ahead features only")
    print(f"  county heat: {ch['n_counties']} counties, {ch['total_mw']:.0f} MW, "
          f"top = {ch['counties'][0]['county']} ({ch['counties'][0]['mw']:.0f} MW, 2 assets)")
    print("  (fixture verifies the MATH + honesty rules; live runs on the Mac)")
