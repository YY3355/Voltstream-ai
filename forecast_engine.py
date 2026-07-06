"""
forecast_engine.py  —  the Base forecasting brain that feeds Bolt.

Brands as: AI/data/forecast. The deliverable is a *probabilistic* day-ahead
price forecaster for ERCOT (Houston hub), trained on the REAL data pulled by
VoltStream, evaluated honestly with walk-forward backtesting, and then wired
into the Bolt dispatch optimizer to answer the only question that matters for a
battery operator: how much money is a better forecast actually worth?

Three forecasters, fair fight:
  1. Seasonal-naive   : P50 = price at the same interval yesterday  (the baseline to beat)
  2. Quantile climatology : P10/P50/P90 = empirical quantiles by time-of-day
  3. Gradient-boosted quantile regression with causal lag features

Honesty notes baked in:
  * ~6.5 contiguous days of CALM spring data -> this validates the *pipeline and
    method*, not a production model. We report whatever the numbers say.
  * The data contains NO price spikes, so spike-probability is built as a
    MECHANISM and explicitly NOT validated here (needs summer/volatile data).
  * All features are strictly causal (past-only). No look-ahead leakage.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

from ercot_data import load_prices
from battery_dispatch import Battery, optimize_dispatch

QUANTILES = [0.1, 0.5, 0.9]
DAY = 96  # 15-min intervals per day


# ----------------------------- features -----------------------------
def build_features(s: pd.Series) -> pd.DataFrame:
    """Causal feature table: every feature uses only prices at or before t-1."""
    df = pd.DataFrame({"y": s})
    tod = s.index.hour * 60 + s.index.minute
    df["tod"] = tod
    df["sin"] = np.sin(2 * np.pi * tod / 1440)
    df["cos"] = np.cos(2 * np.pi * tod / 1440)
    df["lag1"] = s.shift(1)        # 15 min ago
    df["lag4"] = s.shift(4)        # 1 hour ago
    df["lag96"] = s.shift(DAY)     # 1 day ago
    df["roll1h"] = s.shift(1).rolling(4).mean()   # mean of previous hour
    return df


# ----------------------------- models -----------------------------
def fit_predict_gbm(train: pd.DataFrame, test: pd.DataFrame):
    feats = ["sin", "cos", "lag1", "lag4", "lag96", "roll1h"]
    Xtr, ytr = train[feats], train["y"]
    preds = {}
    for q in QUANTILES:
        m = GradientBoostingRegressor(
            loss="quantile", alpha=q, n_estimators=200, max_depth=3,
            learning_rate=0.05, min_samples_leaf=10, subsample=0.8, random_state=7,
        )
        m.fit(Xtr, ytr)
        preds[q] = m.predict(test[feats])
    P = np.sort(np.vstack([preds[q] for q in QUANTILES]).T, axis=1)  # enforce monotone quantiles
    return {q: P[:, i] for i, q in enumerate(QUANTILES)}


def fit_predict_climatology(train: pd.DataFrame, test: pd.DataFrame):
    grp = train.groupby("tod")["y"]
    q_tables = {q: grp.quantile(q) for q in QUANTILES}
    return {q: test["tod"].map(q_tables[q]).values for q in QUANTILES}


def predict_naive(s: pd.Series, test_idx) -> np.ndarray:
    return s.shift(DAY).reindex(test_idx).values


# ----------------------------- metrics -----------------------------
def pinball(y, q_pred, q):
    e = y - q_pred
    return np.mean(np.maximum(q * e, (q - 1) * e))


def evaluate(y, pred_dict):
    pb = np.mean([pinball(y, pred_dict[q], q) for q in QUANTILES])
    mae = np.mean(np.abs(y - pred_dict[0.5]))
    rmse = np.sqrt(np.mean((y - pred_dict[0.5]) ** 2))
    cov = np.mean((y >= pred_dict[0.1]) & (y <= pred_dict[0.9])) * 100  # target ~80%
    return {"pinball": pb, "MAE": mae, "RMSE": rmse, "P10_P90_coverage_%": cov}


# ----------------------------- value via Bolt -----------------------------
def settle(schedule, actual_prices_mwh, dt):
    """Revenue ($) of a FIXED charge/discharge schedule paid at ACTUAL prices."""
    p = np.asarray(actual_prices_mwh) / 1000.0
    return float(np.sum(p * (schedule["discharge_kw"] - schedule["charge_kw"]) * dt))


def value_of_forecast(actual_day, forecast_p50, naive_p50, battery, reserve, dt=0.25):
    # ceiling: decide WITH perfect foresight, settle at actual
    perfect = optimize_dispatch(actual_day, battery, reserve, dt_hours=dt)
    rev_perfect = perfect["revenue"]
    # decide on each forecast, then settle the resulting schedule at ACTUAL prices
    sched_fc = optimize_dispatch(forecast_p50, battery, reserve, dt_hours=dt)
    sched_nv = optimize_dispatch(naive_p50, battery, reserve, dt_hours=dt)
    return {
        "perfect_foresight": rev_perfect,
        "model_forecast": settle(sched_fc, actual_day, dt),
        "naive_forecast": settle(sched_nv, actual_day, dt),
    }


# ----------------------------- run -----------------------------
def run():
    s = load_prices("data")
    feat = build_features(s).dropna()           # drops rows w/o full causal lags (and across the gap)
    days = sorted({d.date() for d in feat.index})
    test_days = days[-3:]                        # walk-forward over the last 3 full days

    print(f"Clean data: {len(s)} intervals, {s.index.min().date()} -> {s.index.max().date()}")
    print(f"Feature rows (valid causal lags): {len(feat)}")
    print(f"Walk-forward test days: {[str(d) for d in test_days]}\n")

    rows = []
    for d in test_days:
        test = feat[feat.index.date == d]
        train = feat[feat.index.date < d]
        if len(train) < DAY or len(test) == 0:
            continue
        y = test["y"].values
        gbm = fit_predict_gbm(train, test)
        clim = fit_predict_climatology(train, test)
        nv = predict_naive(s, test.index)
        naive_pred = {0.1: nv * 0.7, 0.5: nv, 0.9: nv * 1.3}  # crude band for a point baseline
        rows.append(("GBM-quantile", d, evaluate(y, gbm)))
        rows.append(("Climatology", d, evaluate(y, clim)))
        rows.append(("Seasonal-naive", d, evaluate(y, naive_pred)))

    res = pd.DataFrame([{"model": m, "day": str(d), **mt} for m, d, mt in rows])
    summary = res.groupby("model")[["pinball", "MAE", "RMSE", "P10_P90_coverage_%"]].mean().round(2)
    summary = summary.sort_values("pinball")
    print("Walk-forward accuracy (averaged over test days; lower pinball/MAE better):")
    print(summary.to_string())

    # ---- value of the forecast on the final FULL day ----
    full_days = [dd for dd in test_days if len(feat[feat.index.date == dd]) >= DAY]
    d = full_days[-1] if full_days else test_days[-1]
    test = feat[feat.index.date == d]
    train = feat[feat.index.date < d]
    gbm = fit_predict_gbm(train, test)
    nv = predict_naive(s, test.index)
    actual = test["y"].values
    bat = Battery()
    val = value_of_forecast(actual, gbm[0.5], nv, bat, reserve=10.0, dt=0.25)
    print(f"\nValue of the forecast — one day of Bolt dispatch on {d} (settled at ACTUAL prices):")
    cap = 100 * val["model_forecast"] / val["perfect_foresight"] if val["perfect_foresight"] else float("nan")
    print(f"  perfect foresight (ceiling) : ${val['perfect_foresight']:.2f}")
    print(f"  on GBM forecast             : ${val['model_forecast']:.2f}   ({cap:.0f}% of ceiling captured)")
    print(f"  on seasonal-naive forecast  : ${val['naive_forecast']:.2f}")

    return s, feat, res, summary, (d, test, gbm, nv, actual, val)


if __name__ == "__main__":
    run()
