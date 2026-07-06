"""
rt_engine.py  —  the real-time decision-under-uncertainty layer.

The optimizer in battery_dispatch.py has PERFECT FORESIGHT: it sees the whole day's
prices and finds the best possible schedule. That is a planning ceiling, not trading.
A real-time desk never knows the next price. This module models that honestly:

  * perfect_foresight  : optimize on ACTUAL prices -> the ceiling (can't be beaten).
  * rolling_policy      : at each interval, see only the past + a P50 forecast of the rest,
                          decide this interval's action, then REALIZE at the actual price.
                          This is receding-horizon / model-predictive control — how storage
                          desks actually run. No peeking.
  * open_loop           : plan the whole day once on the forecast, then live with it.
  * naive               : simple threshold rule on the forecast.

Headline numbers a trader cares about:
  * capture ratio = realized P&L / perfect-foresight ceiling  ("how much of the optimum
    did the policy capture without knowing the future").
  * regret = ceiling - realized.
  * risk = the SPREAD of capture across days (best / mean / worst), because a desk lives
    and dies by the bad days, not the average.

Honest limits: still a single node, deterministic forecast path (P50), energy-only here,
small sample of days. It demonstrates the STRUCTURE of RT decision-making, not a live desk.
"""
import numpy as np
import cvxpy as cp
import pandas as pd
from scipy.optimize import linprog
from battery_dispatch import Battery, optimize_dispatch

DT = 0.25  # 15-min intervals
_CACHE = {}


# ---------- fast LP horizon solve (scipy linprog -> low per-call overhead) ----------
def _lp_first_action(prices_mwh, cap, pmax, eta, soc0, reserve, dt):
    T = len(prices_mwh)
    p = np.asarray(prices_mwh, float) / 1000.0
    # vars: c[0:T], d[T:2T], soc[2T:3T].  minimize -sum p*dt*(d-c)
    obj = np.concatenate([p * dt, -p * dt, np.zeros(T)])
    # soc dynamics: soc_t - soc_{t-1} - eta*dt*c_t + (1/eta)*dt*d_t = 0  (soc_{-1}=soc0)
    A = np.zeros((T, 3 * T)); b = np.zeros(T)
    for t in range(T):
        A[t, 2 * T + t] = 1.0
        A[t, t] = -eta * dt
        A[t, T + t] = (1.0 / eta) * dt
        if t == 0:
            b[t] = soc0
        else:
            A[t, 2 * T + t - 1] = -1.0
    bounds = [(0, pmax)] * T + [(0, pmax)] * T + [(reserve, cap)] * T
    r = linprog(obj, A_eq=A, b_eq=b, bounds=bounds, method="highs")
    if not r.success:
        return 0.0, 0.0
    return float(max(r.x[0], 0)), float(max(r.x[T], 0))


def rolling_policy(actual_mwh, forecast_mwh, battery, reserve, dt=DT, adapt=False):
    """Receding-horizon: decide on a forecast of the remaining horizon, realize at actual.

    adapt=True applies a causal intraday correction (lift/cut the near-term view by how far
    realized prices ran from forecast over the last hour). On this calm, mean-reverting
    sample it didn't reliably beat the static plan, so it's OFF by default — an honest
    finding in itself: naive intraday extrapolation is a wash here. Left in for transparency.
    """
    actual_mwh = np.asarray(actual_mwh, float); forecast_mwh = np.asarray(forecast_mwh, float)
    T = len(actual_mwh); cap = battery.usable_capacity_kwh; pmax = battery.max_power_kw; eta = battery.eta
    soc = battery.initial_soc_kwh
    C = np.zeros(T); D = np.zeros(T); S = np.zeros(T); realized = 0.0
    for t in range(T):
        fc = forecast_mwh[t:].copy()
        if adapt and t >= 4:
            bias = actual_mwh[t - 4:t].mean() - forecast_mwh[t - 4:t].mean()  # recent error, causal
            k = min(len(fc), 8)                                               # correct next ~2h
            fc[:k] = fc[:k] + bias * np.exp(-np.arange(k) / 4.0)
        ac, ad = _lp_first_action(fc, cap, pmax, eta, soc, reserve, dt)
        ac = min(ac, max(0.0, (cap - soc) / (eta * dt)))
        ad = min(ad, max(0.0, (soc - reserve) * eta / dt))
        soc = min(max(soc + eta * ac * dt - (1.0 / eta) * ad * dt, reserve), cap)
        realized += (actual_mwh[t] / 1000.0) * (ad - ac) * dt
        C[t] = ac; D[t] = ad; S[t] = soc
    return {"realized": realized, "charge_kw": C, "discharge_kw": D, "soc_kwh": S}


def naive_policy(actual_mwh, forecast_mwh, battery, reserve, dt=DT):
    """Charge when the forecast is cheap, discharge when rich — decided on forecast, paid at actual."""
    T = len(actual_mwh); cap = battery.usable_capacity_kwh; pmax = battery.max_power_kw; eta = battery.eta
    lo, hi = np.percentile(forecast_mwh, 33), np.percentile(forecast_mwh, 66)
    soc = battery.initial_soc_kwh; realized = 0.0
    for t in range(T):
        f = forecast_mwh[t]; ac = ad = 0.0
        if f <= lo:
            ac = min(pmax, max(0.0, (cap - soc) / (eta * dt)))
        elif f >= hi:
            ad = min(pmax, max(0.0, (soc - reserve) * eta / dt))
        soc = min(max(soc + eta * ac * dt - (1.0 / eta) * ad * dt, reserve), cap)
        realized += (actual_mwh[t] / 1000.0) * (ad - ac) * dt
    return {"realized": realized}


def open_loop(actual_mwh, forecast_mwh, battery, reserve, dt=DT):
    """Plan the whole day once on the forecast, then settle that fixed schedule at actual."""
    sched = optimize_dispatch(forecast_mwh, battery, reserve, dt_hours=dt, require_end_soc=False)
    p = np.asarray(actual_mwh, float) / 1000.0
    realized = float(np.sum(p * (sched["discharge_kw"] - sched["charge_kw"]) * dt))
    return {"realized": realized}


def perfect_foresight(actual_mwh, battery, reserve, dt=DT):
    # require_end_soc=False so the ceiling plays by the SAME terminal rules as the rolling
    # policy (both may end at the reserve floor) -> a true upper bound, capture <= 100%.
    r = optimize_dispatch(actual_mwh, battery, reserve, dt_hours=dt, require_end_soc=False)
    return {"ceiling": r["revenue"], "charge_kw": r["charge_kw"],
            "discharge_kw": r["discharge_kw"], "soc_kwh": r["soc_kwh"]}


# ----------------------------- walk-forward forecasts -----------------------------
def _forecasts_by_day(data_dir, test_days=4):
    """Train GBM on history strictly before each test day; return (day, actual, p50) tuples."""
    from ercot_data import load_prices
    from forecast_engine import build_features, fit_predict_gbm, DAY
    s = load_prices(data_dir)
    feat = build_features(s).dropna()
    days = [d for d, n in feat.groupby(feat.index.normalize()).size().items() if n >= 90]
    out = []
    for day in days[-test_days:]:
        test = feat[feat.index.normalize() == day]
        train = feat[feat.index < test.index.min()]
        if len(train) < DAY or len(test) < 90:
            continue
        preds = fit_predict_gbm(train, test)
        out.append((pd.Timestamp(day).strftime("%b %d"),
                    test["y"].values, preds[0.5]))
    return out


# ----------------------------- top-level run (cached) -----------------------------
def run_rt(data_dir="data", reserve_kwh=5.0):
    key = (data_dir, reserve_kwh)
    if key in _CACHE:
        return _CACHE[key]
    bat = Battery(usable_capacity_kwh=25, max_power_kw=12.5, round_trip_efficiency=0.90, initial_soc_kwh=12.5)
    fc = _forecasts_by_day(data_dir)
    per_day, detail = [], None
    for name, actual, p50 in fc:
        pf = perfect_foresight(actual, bat, reserve_kwh)
        roll = rolling_policy(actual, p50, bat, reserve_kwh)
        nai = naive_policy(actual, p50, bat, reserve_kwh)
        ol = open_loop(actual, p50, bat, reserve_kwh)
        ceil = pf["ceiling"] if pf["ceiling"] > 1e-6 else 1e-6
        per_day.append({
            "day": name,
            "ceiling": round(pf["ceiling"], 2),
            "rolling": round(roll["realized"], 2),
            "open_loop": round(ol["realized"], 2),
            "naive": round(nai["realized"], 2),
            "capture_pct": round(100 * roll["realized"] / ceil, 1),
            "naive_pct": round(100 * nai["realized"] / ceil, 1),
        })
        detail = {  # keep the last day for the chart
            "day": name,
            "price": [round(float(x), 1) for x in actual],
            "forecast": [round(float(x), 1) for x in p50],
            "roll_charge": [round(float(x), 2) for x in roll["charge_kw"]],
            "roll_discharge": [round(float(x), 2) for x in roll["discharge_kw"]],
            "roll_soc": [round(float(x), 2) for x in roll["soc_kwh"]],
            "pf_soc": [round(float(x), 2) for x in pf["soc_kwh"]],
            "capacity_kwh": bat.usable_capacity_kwh,
            "reserve_kwh": reserve_kwh,
        }
    caps = [d["capture_pct"] for d in per_day] or [0]
    ncaps = [d["naive_pct"] for d in per_day] or [0]
    result = {
        "per_day": per_day,
        "summary": {
            "mean_capture": round(float(np.mean(caps)), 1),
            "worst_capture": round(float(np.min(caps)), 1),
            "best_capture": round(float(np.max(caps)), 1),
            "mean_naive": round(float(np.mean(ncaps)), 1),
            "mean_regret": round(float(np.mean([d["ceiling"] - d["rolling"] for d in per_day])), 2) if per_day else 0,
            "n_days": len(per_day),
        },
        "detail": detail,
    }
    _CACHE[key] = result
    return result


if __name__ == "__main__":
    import time
    t0 = time.time()
    r = run_rt("data")
    print(f"computed in {time.time()-t0:.1f}s\n")
    print(f"{'day':<8}{'ceiling':>9}{'rolling':>9}{'open':>8}{'naive':>8}{'capture%':>10}")
    for d in r["per_day"]:
        print(f"{d['day']:<8}{d['ceiling']:>9.2f}{d['rolling']:>9.2f}{d['open_loop']:>8.2f}{d['naive']:>8.2f}{d['capture_pct']:>9.1f}%")
    s = r["summary"]
    print(f"\nRolling policy captured {s['mean_capture']}% of perfect foresight on average "
          f"(worst {s['worst_capture']}%, best {s['best_capture']}%) across {s['n_days']} days.")
    print(f"Mean regret vs perfect foresight: ${s['mean_regret']}/day.")
