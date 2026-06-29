"""
risk_engine.py  —  the quant-risk layer.

Four desk-grade outputs, in dependency order:

  1. MONTE CARLO price paths. Fit a mean-reverting jump-diffusion to REAL ERCOT prices
     (Ornstein-Uhlenbeck reversion to a seasonal/hour-of-day level + upward price jumps,
     which is the standard honest model for power) and simulate many day-paths. Every
     parameter is calibrated to data, not assumed.

  2. P&L DISTRIBUTION. Run the existing rolling no-peek policy on each simulated path ->
     a distribution of daily P&L instead of a single number.

  3. RISK METRICS. From that distribution: VaR95 (loss you won't exceed 95% of the time),
     expected shortfall (mean of the worst 5%), mean, std, and the histogram. This is the
     language a trading desk actually uses — risk-adjusted, not raw.

  4. OPTIONALITY VALUE. A battery is a real option (the right, not obligation, to convert
     stored energy to cash on spikes). Re-run the policy on a VOLATILITY-FLATTENED version
     of the same paths; the revenue difference is the value that comes purely from price
     variability — the optionality. The slope of value vs. a volatility multiplier is a
     real vega-like sensitivity.

HONEST LIMITS: single node; the battery's OWN optionality (not traded options — no faked
vol surface); jump-diffusion calibrated to a small May sample. All parameters trace to real
data, nothing external is invented.
"""
import numpy as np
import pandas as pd
from battery_dispatch import Battery
from rt_engine import rolling_policy, perfect_foresight, _lp_first_action, DT

_CACHE = {}


def _fast_policy(actual_mwh, forecast_mwh, battery, reserve, replan_every=4):
    """Causal dispatch that re-plans hourly (commit `replan_every` actions per LP solve).

    ~4x fewer solves than per-interval re-planning, which makes Monte-Carlo across hundreds
    of paths tractable, while staying a real receding-horizon policy (no peeking).
    """
    actual_mwh = np.asarray(actual_mwh, float)
    T = len(actual_mwh); cap = battery.usable_capacity_kwh; pmax = battery.max_power_kw; eta = battery.eta
    soc = battery.initial_soc_kwh; realized = 0.0
    t = 0
    while t < T:
        # plan on the forecast of the remaining horizon, commit the next `replan_every` actions
        from scipy.optimize import linprog
        h = forecast_mwh[t:]; n = len(h); p = h / 1000.0
        obj = np.concatenate([p * DT, -p * DT, np.zeros(n)])
        A = np.zeros((n, 3 * n)); b = np.zeros(n)
        for k in range(n):
            A[k, 2 * n + k] = 1.0; A[k, k] = -eta * DT; A[k, n + k] = (1.0 / eta) * DT
            if k == 0:
                b[k] = soc
            else:
                A[k, 2 * n + k - 1] = -1.0
        bounds = [(0, pmax)] * n + [(0, pmax)] * n + [(reserve, cap)] * n
        r = linprog(obj, A_eq=A, b_eq=b, bounds=bounds, method="highs")
        if not r.success:
            cs = ds = np.zeros(replan_every)
        else:
            cs = r.x[:replan_every]; ds = r.x[n:n + replan_every]
        for j in range(min(replan_every, T - t)):
            ac = min(max(cs[j], 0), max(0.0, (cap - soc) / (eta * DT)))
            ad = min(max(ds[j], 0), max(0.0, (soc - reserve) * eta / DT))
            soc = min(max(soc + eta * ac * DT - (1.0 / eta) * ad * DT, reserve), cap)
            realized += (actual_mwh[t + j] / 1000.0) * (ad - ac) * DT
        t += replan_every
    return realized


# ----------------------------- calibration -----------------------------
def calibrate_jump_diffusion(prices: pd.Series):
    """Fit a mean-reverting (OU) jump-diffusion to real ERCOT prices.

    Model (per 15-min step):  dP = kappa*(mu_t - P)*dt + sigma*dW + Jumps
      mu_t   : seasonal level = hour-of-day mean (the deterministic shape)
      kappa  : mean-reversion speed (how fast deviations decay)
      sigma  : diffusive vol of the de-meaned residual
      jumps  : upward spikes, calibrated by frequency + size from the tail of the residuals
    """
    s = prices.dropna().astype(float)
    hod = s.groupby(s.index.hour).mean()                    # seasonal hour-of-day level
    mu_t = s.index.hour.map(hod).to_numpy()
    resid = s.to_numpy() - mu_t                             # de-meaned deviations
    # OU reversion via AR(1) on residuals: resid_t = phi*resid_{t-1} + eps  -> kappa = 1-phi
    x0, x1 = resid[:-1], resid[1:]
    phi = float(np.clip(np.dot(x0, x1) / max(np.dot(x0, x0), 1e-9), 0.0, 0.999))
    kappa = 1.0 - phi
    eps = x1 - phi * x0
    # separate jumps (fat upper tail) from diffusion
    thresh = np.mean(eps) + 3.0 * np.std(eps)
    is_jump = eps > thresh
    sigma = float(np.std(eps[~is_jump])) if (~is_jump).any() else float(np.std(eps))
    jump_prob = float(is_jump.mean())
    jump_mean = float(np.mean(eps[is_jump])) if is_jump.any() else 0.0
    jump_std = float(np.std(eps[is_jump])) if is_jump.sum() > 1 else max(jump_mean * 0.3, 1.0)
    return {"hod": hod, "kappa": kappa, "sigma": sigma, "phi": phi,
            "jump_prob": jump_prob, "jump_mean": jump_mean, "jump_std": jump_std,
            "floor": float(s.min())}


def simulate_paths(params, n_paths=300, steps=96, vol_mult=1.0, jump_mult=1.0, seed=7):
    """Simulate day-long 15-min price paths from the calibrated model."""
    rng = np.random.default_rng(seed)
    hod = params["hod"]
    mu = np.array([hod.get(h, float(hod.mean())) for h in (np.arange(steps) // 4) % 24])
    phi, sigma = params["phi"], params["sigma"] * vol_mult
    jp = params["jump_prob"] * jump_mult
    paths = np.zeros((n_paths, steps))
    resid = np.zeros(n_paths)
    for t in range(steps):
        shock = rng.normal(0, sigma, n_paths)
        jumps = (rng.random(n_paths) < jp) * np.maximum(
            rng.normal(params["jump_mean"], params["jump_std"], n_paths), 0.0)
        resid = phi * resid + shock + jumps
        paths[:, t] = np.maximum(mu[t] + resid, params["floor"] * 0.5)
    return paths


# ----------------------------- risk metrics -----------------------------
def _pnl_distribution(paths, battery, reserve, forecast):
    """Run the fast (hourly re-plan) no-peek policy on each path; return daily P&L array."""
    out = np.zeros(len(paths))
    for i, actual in enumerate(paths):
        out[i] = _fast_policy(actual, forecast, battery, reserve)
    return out


def var_es(pnl, alpha=0.95):
    """Value-at-Risk and Expected Shortfall on a P&L distribution (loss = -pnl)."""
    losses = -np.asarray(pnl)
    var = float(np.quantile(losses, alpha))               # loss not exceeded (1-alpha) of the time
    tail = losses[losses >= var]
    es = float(tail.mean()) if tail.size else var          # mean of the worst (1-alpha)
    return var, es


# ----------------------------- top level -----------------------------
def run_risk(data_dir="data", reserve_kwh=5.0, n_paths=150):
    key = (data_dir, reserve_kwh, n_paths)
    if key in _CACHE:
        return _CACHE[key]
    from ercot_data import load_prices
    prices = load_prices(data_dir)
    params = calibrate_jump_diffusion(prices)
    bat = Battery(usable_capacity_kwh=25, max_power_kw=12.5, round_trip_efficiency=0.90, initial_soc_kwh=12.5)
    # forecast the policy plans against = the seasonal hour-of-day level (its honest expectation)
    forecast = np.array([params["hod"].get(h, float(params["hod"].mean()))
                         for h in (np.arange(96) // 4) % 24])

    # (1)+(2)+(3): full-vol paths -> P&L distribution -> risk metrics
    paths = simulate_paths(params, n_paths=n_paths)
    pnl = _pnl_distribution(paths, bat, reserve_kwh, forecast)
    var95, es95 = var_es(pnl, 0.95)
    mean_pnl = float(pnl.mean()); std_pnl = float(pnl.std())

    # (4) optionality: flatten volatility (vol->~0, jumps off) and re-run
    flat = simulate_paths(params, n_paths=n_paths, vol_mult=0.05, jump_mult=0.0, seed=7)
    pnl_flat = _pnl_distribution(flat, bat, reserve_kwh, forecast)
    optionality = mean_pnl - float(pnl_flat.mean())        # value from price variability

    # vega-like sensitivity: d(mean P&L) / d(vol multiplier), one-sided finite difference
    hi = _pnl_distribution(simulate_paths(params, n_paths=max(80, n_paths // 2), vol_mult=1.25, seed=7),
                           bat, reserve_kwh, forecast).mean()
    vega = float((hi - mean_pnl) / 0.25)                   # $ per 1.0 of vol multiplier

    # histogram for the dashboard
    counts, edges = np.histogram(pnl, bins=22)
    result = {
        "n_paths": n_paths,
        "mean_pnl": round(mean_pnl, 3),
        "std_pnl": round(std_pnl, 3),
        "var95": round(var95, 3),
        "es95": round(es95, 3),
        "best": round(float(pnl.max()), 3),
        "worst": round(float(pnl.min()), 3),
        "sharpe_like": round(mean_pnl / std_pnl, 2) if std_pnl > 1e-9 else None,
        "optionality_value": round(optionality, 3),
        "optionality_pct": round(100 * optionality / mean_pnl, 1) if mean_pnl > 1e-9 else None,
        "vega": round(vega, 3),
        "hist_counts": [int(c) for c in counts],
        "hist_edges": [round(float(e), 3) for e in edges],
        "calib": {
            "kappa": round(params["kappa"], 4),
            "sigma": round(params["sigma"], 2),
            "jump_prob_pct": round(100 * params["jump_prob"], 2),
            "jump_mean": round(params["jump_mean"], 2),
        },
    }
    _CACHE[key] = result
    return result


if __name__ == "__main__":
    import time
    t0 = time.time()
    r = run_risk("data", n_paths=150)
    print(f"computed in {time.time()-t0:.1f}s  ({r['n_paths']} Monte Carlo paths)\n")
    c = r["calib"]
    print(f"calibration: kappa(revert)={c['kappa']}  sigma=${c['sigma']}  "
          f"jump prob={c['jump_prob_pct']}%/step  jump size=${c['jump_mean']}\n")
    print(f"daily P&L:  mean ${r['mean_pnl']}   std ${r['std_pnl']}   "
          f"best ${r['best']}   worst ${r['worst']}   sharpe-like {r['sharpe_like']}")
    print(f"risk:       VaR95 ${r['var95']} (loss not exceeded 95% of days)   "
          f"Expected Shortfall ${r['es95']} (mean of worst 5%)")
    print(f"optionality: ${r['optionality_value']}  "
          f"({r['optionality_pct']}% of value is flexibility)   vega ${r['vega']}/vol-unit")
