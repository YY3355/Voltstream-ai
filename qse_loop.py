"""
qse_loop.py  —  a controlled experiment on the "dynamic QSE loop" idea.

Habitat's QSE write-up makes two concrete, testable claims about the real-time loop that
links a battery's telemetry to its market bids:

  (A) STALE TELEMETRY ERODES REVENUE. If the state-of-charge the bidder acts on lags the
      asset's true state, decisions are made on stale information and money leaks away.
  (B) MW / MWh MUST BE COORDINATED. Offering power (MW) without checking sustainable energy
      (MWh) makes the asset "exhaust flexibility too early or fail to capture short-lived
      price spikes."

This module isolates and quantifies BOTH on simulated ERCOT-like price paths (the jump-
diffusion calibrated to real data in risk_engine), so the spikes where these effects bite
actually occur.

HONEST SCOPE: this models the *concept* with simulated telemetry and simple dispatch
heuristics chosen to isolate each effect cleanly. It is NOT a real QSE: no physical asset,
no live telemetry feed, no certified ERCOT market interface. It quantifies the economic
argument the article makes — it does not implement the pipeline.
"""
import numpy as np
from battery_dispatch import Battery
from risk_engine import calibrate_jump_diffusion, simulate_paths

DT = 0.25
_CACHE = {}


def _greedy(actual, forecast, bat, reserve, lag=0, coupled=True, dt=DT):
    """Real-time, price-reactive dispatch where the market OFFER is sized from the SoC reading.

    lag     : telemetry staleness in intervals -- the bid is built from SoC as of `lag` ago.
    coupled : True  -> offer sized to available energy and saved for the richest prices
                       (MW coordinated with MWh).
              False -> offer max power on a broad price signal, ignoring sustainable energy.

    Returns (revenue, commitment_error_MWh, soc_path). Commitment error = the MWh gap between
    what was OFFERED (built on the SoC reading) and what could PHYSICALLY be delivered -- i.e.
    bidding power the asset can't back, the penalty/reliability risk the article describes.
    """
    p = np.asarray(actual, float)
    T = len(p); cap = bat.usable_capacity_kwh; pmax = bat.max_power_kw; eta = bat.eta
    lo = np.percentile(p, 35)
    hi = np.percentile(p, 85) if coupled else np.percentile(p, 68)
    true_soc = bat.initial_soc_kwh
    hist = [true_soc]
    rev = 0.0; cerr = 0.0; soc_path = np.zeros(T); dlv = np.zeros(T)
    for t in range(T):
        believed = hist[max(0, len(hist) - 1 - lag)]
        f = p[t]; off_c = off_d = 0.0
        if f <= lo:
            off_c = min(pmax, (cap - believed) / (eta * dt))
        elif f >= hi:
            off_d = (min(pmax, (believed - reserve) * eta / dt) if coupled else pmax)
        del_c = min(off_c, max(0.0, (cap - true_soc) / (eta * dt)))
        del_d = min(off_d, max(0.0, (true_soc - reserve) * eta / dt))
        cerr += (abs(off_c - del_c) + abs(off_d - del_d)) * dt
        true_soc = min(max(true_soc + eta * del_c * dt - (1.0 / eta) * del_d * dt, reserve), cap)
        hist.append(true_soc)
        rev += (f / 1000.0) * (del_d - del_c) * dt
        soc_path[t] = true_soc; dlv[t] = del_d - del_c
    return rev, cerr, soc_path, dlv


def _mean(paths, forecast, bat, reserve, lag=0, coupled=True):
    rs, es = [], []
    for p in paths:
        r, e, _, _ = _greedy(p, forecast, bat, reserve, lag, coupled)
        rs.append(r); es.append(e)
    return float(np.mean(rs)), float(np.mean(es))


def _spike_capture(paths, forecast, bat, reserve, coupled, top_frac=0.05):
    """Mean revenue earned specifically during each path's highest-price intervals."""
    caps = []
    for p in paths:
        _, _, _, dlv = _greedy(p, forecast, bat, reserve, lag=0, coupled=coupled)
        k = max(1, int(len(p) * top_frac))
        top = np.argsort(p)[-k:]                       # the spike intervals
        caps.append(float(np.sum((p[top] / 1000.0) * np.maximum(dlv[top], 0.0) * DT)))
    return float(np.mean(caps))


def run_qse(data_dir="data", reserve_kwh=5.0, n_paths=200):
    key = (data_dir, reserve_kwh, n_paths)
    if key in _CACHE:
        return _CACHE[key]
    from ercot_data import load_prices
    prices = load_prices(data_dir)
    params = calibrate_jump_diffusion(prices)
    bat = Battery(usable_capacity_kwh=25, max_power_kw=12.5, round_trip_efficiency=0.90, initial_soc_kwh=12.5)
    forecast = np.array([params["hod"].get(h, float(params["hod"].mean()))
                         for h in (np.arange(96) // 4) % 24])
    paths = simulate_paths(params, n_paths=n_paths)

    # ---- (A) telemetry-lag decay: commitment error (offered-but-undeliverable MWh) vs staleness ----
    lags = [0, 1, 2, 4, 8]                          # intervals -> 0/15/30/60/120 min
    fresh_rev, fresh_err = _mean(paths, forecast, bat, reserve_kwh, lag=0, coupled=True)
    lag_curve = []
    for L in lags:
        rev, err = _mean(paths, forecast, bat, reserve_kwh, lag=L, coupled=True)
        lag_curve.append({"lag_min": L * 15, "revenue": round(rev, 3),
                          "commit_err_mwh": round(err, 4),
                          "pct_of_fresh": round(100 * rev / fresh_rev, 1) if fresh_rev else None})

    # ---- (B) MW/MWh coordination: revenue captured DURING the top price spikes ----
    coupled_spike = _spike_capture(paths, forecast, bat, reserve_kwh, coupled=True)
    power_spike = _spike_capture(paths, forecast, bat, reserve_kwh, coupled=False)
    coord_gain_pct = round(100 * (coupled_spike - power_spike) / power_spike, 1) if power_spike else None
    coupled_rev, _ = _mean(paths, forecast, bat, reserve_kwh, lag=0, coupled=True)
    power_only_rev, _ = _mean(paths, forecast, bat, reserve_kwh, lag=0, coupled=False)
    # pick an illustrative path: largest single late-day price spike
    late_peak = np.array([p[48:].max() for p in paths])
    ip = int(np.argmax(late_peak))
    _, _, soc_c, _ = _greedy(paths[ip], forecast, bat, reserve_kwh, lag=0, coupled=True)
    _, _, soc_p, _ = _greedy(paths[ip], forecast, bat, reserve_kwh, lag=0, coupled=False)

    result = {
        "lag_curve": lag_curve,
        "commit_err_2h": lag_curve[-1]["commit_err_mwh"],
        "coupled_spike": round(coupled_spike, 3),
        "power_spike": round(power_spike, 3),
        "coord_gain_pct": coord_gain_pct,
        "coupled_rev": round(coupled_rev, 3),
        "power_only_rev": round(power_only_rev, 3),
        "n_paths": n_paths,
        "illustration": {
            "price": [round(float(x), 1) for x in paths[ip]],
            "soc_coupled": [round(float(x), 2) for x in soc_c],
            "soc_power_only": [round(float(x), 2) for x in soc_p],
            "capacity_kwh": bat.usable_capacity_kwh,
            "reserve_kwh": reserve_kwh,
        },
        "calib_jump_pct": round(100 * params["jump_prob"], 2),
    }
    _CACHE[key] = result
    return result


if __name__ == "__main__":
    import time
    t0 = time.time()
    r = run_qse("data", n_paths=200)
    print(f"computed in {time.time()-t0:.2f}s  ({r['n_paths']} simulated paths)\n")
    print("(A) Cost of stale telemetry -- commitment error (MWh offered but undeliverable) vs SoC age:")
    for row in r["lag_curve"]:
        print(f"    {row['lag_min']:>3} min old : commit-error {row['commit_err_mwh']:.4f} MWh   "
              f"(rev ${row['revenue']:.3f}, {row['pct_of_fresh']}% of fresh)")
    print(f"    => 2-hour-stale telemetry creates {r['commit_err_2h']:.4f} MWh of bids the asset can't back.\n")
    print("(B) MW/MWh coordination -- revenue captured DURING the top 5% price spikes:")
    print(f"    coupled (saves energy for spikes): ${r['coupled_spike']:.3f}")
    print(f"    power-only (spends broadly)       : ${r['power_spike']:.3f}")
    print(f"    => coordinating MW with MWh captures {r['coord_gain_pct']}% more spike revenue.")
