"""
battery_dispatch.py  —  Phase 1 of the Base-shaped project.

Single home-battery dispatch optimizer for ERCOT energy arbitrage,
SUBJECT TO a homeowner backup-reserve floor.

The whole point: a naive revenue maximizer drains the battery to sell into a
price spike, then the family loses power during an outage. Base's real problem
is to earn grid revenue WHILE always keeping enough charge in reserve to back
up the house. This model encodes exactly that tension.

Formulation (a Mixed-Integer Linear Program):

  Indices
    t = 0 .. T-1            hourly periods, each dt hours long

  Decision variables
    c[t] >= 0              charge power drawn from grid           (kW)
    d[t] >= 0              discharge power delivered to grid      (kW)
    soc[t]                 state of charge at END of period t     (kWh)
    mode[t] in {0,1}       1 = charging, 0 = discharging          (binary -> MILP)

  Objective  (maximize arbitrage revenue, $)
    max  sum_t price[t] * (d[t] - c[t]) * dt

  Subject to
    soc[t] = soc[t-1] + eta_c * c[t] * dt - (1/eta_d) * d[t] * dt   (energy balance)
    backup_reserve <= soc[t] <= usable_capacity                    (<-- the key line)
    0 <= c[t] <= P_max * mode[t]                                    (no simultaneous
    0 <= d[t] <= P_max * (1 - mode[t])                              (charge + discharge)
    soc[T-1] >= soc_initial                                         (no end-of-horizon dump)

The `backup_reserve <= soc[t]` constraint is the homeowner-protection floor and
the conceptual heart of the whole project. Raise it and the family is safer but
you earn less. `sweep_backup_reserve()` quantifies that tradeoff — which is the
sendable insight.
"""

from dataclasses import dataclass
import numpy as np
import cvxpy as cp


@dataclass
class Battery:
    """Physical parameters of one home battery (defaults loosely match a large
    residential unit; override freely)."""
    usable_capacity_kwh: float = 25.0     # usable energy capacity
    max_power_kw: float = 12.5            # max charge / discharge power
    round_trip_efficiency: float = 0.90   # AC-to-AC round trip
    initial_soc_kwh: float = 12.5         # starting charge

    @property
    def eta(self) -> float:
        # split the round-trip loss evenly across charge and discharge legs
        return float(np.sqrt(self.round_trip_efficiency))


def optimize_dispatch(
    prices_per_mwh: np.ndarray,
    battery: Battery,
    backup_reserve_kwh: float,
    dt_hours: float = 1.0,
    require_end_soc: bool = True,
    solver: str = "HIGHS",
):
    """
    Solve the single-battery dispatch MILP.

    prices_per_mwh : array of ERCOT energy prices ($/MWh), one per period.
    backup_reserve_kwh : the floor SoC must never drop below (the family's reserve).

    Returns a dict with the optimal schedule and the resulting revenue.
    """
    prices = np.asarray(prices_per_mwh, dtype=float) / 1000.0  # $/MWh -> $/kWh
    T = len(prices)
    eta = battery.eta
    cap = battery.usable_capacity_kwh
    pmax = battery.max_power_kw
    soc0 = battery.initial_soc_kwh

    if backup_reserve_kwh > cap:
        raise ValueError("Backup reserve cannot exceed usable capacity.")
    if not (backup_reserve_kwh <= soc0 <= cap):
        raise ValueError("Initial SoC must sit between the backup floor and capacity.")

    c = cp.Variable(T, nonneg=True)        # charge power (kW)
    d = cp.Variable(T, nonneg=True)        # discharge power (kW)
    soc = cp.Variable(T)                   # state of charge (kWh)
    mode = cp.Variable(T, boolean=True)    # 1=charge, 0=discharge  -> makes it a MILP

    constraints = []

    # --- energy balance, period by period ---
    for t in range(T):
        prev = soc0 if t == 0 else soc[t - 1]
        constraints += [soc[t] == prev + eta * c[t] * dt_hours - (1.0 / eta) * d[t] * dt_hours]

    # --- THE backup-reserve floor (and capacity ceiling) ---
    constraints += [soc >= backup_reserve_kwh]
    constraints += [soc <= cap]

    # --- power limits + no simultaneous charge/discharge (the integer part) ---
    constraints += [c <= pmax * mode]
    constraints += [d <= pmax * (1 - mode)]

    # --- don't just drain the battery in the final hour ---
    if require_end_soc:
        constraints += [soc[T - 1] >= soc0]

    # --- objective: maximize arbitrage revenue ---
    revenue = cp.sum(cp.multiply(prices, (d - c)) * dt_hours)
    prob = cp.Problem(cp.Maximize(revenue), constraints)
    prob.solve(solver=solver)

    if prob.status not in ("optimal", "optimal_inaccurate"):
        raise RuntimeError(f"Solver did not converge: {prob.status}")

    return {
        "status": prob.status,
        "revenue": float(prob.value),
        "charge_kw": np.round(np.maximum(c.value, 0), 4),
        "discharge_kw": np.round(np.maximum(d.value, 0), 4),
        "soc_kwh": np.round(soc.value, 4),
        "prices_per_mwh": prices * 1000.0,
        "backup_reserve_kwh": backup_reserve_kwh,
    }


def sweep_backup_reserve(prices_per_mwh, battery, reserve_levels, dt_hours=1.0):
    """Run the optimizer across several backup-floor levels and return the
    revenue-vs-resilience tradeoff. THIS is the headline result."""
    out = []
    for r in reserve_levels:
        # start each scenario at a feasible SoC: at least the floor, at most capacity
        feasible_start = min(battery.usable_capacity_kwh, max(battery.initial_soc_kwh, r))
        b = Battery(
            usable_capacity_kwh=battery.usable_capacity_kwh,
            max_power_kw=battery.max_power_kw,
            round_trip_efficiency=battery.round_trip_efficiency,
            initial_soc_kwh=feasible_start,
        )
        res = optimize_dispatch(prices_per_mwh, b, backup_reserve_kwh=r, dt_hours=dt_hours)
        out.append({"backup_reserve_kwh": r, "revenue": res["revenue"]})
    return out


def make_synthetic_ercot_prices(days=7, seed=7):
    """A stand-in ERCOT-like hourly price series ($/MWh): low overnight, a soft
    morning bump, a sharp evening peak, plus a couple of scarcity spikes.

    NOTE: this is synthetic so the model runs anywhere. Swapping in real ERCOT
    settlement-point prices (e.g. from your VoltStream puller, or a CSV) is a
    one-line change — see load_prices_csv(). Being honest about this assumption
    is itself a point in the memo.
    """
    rng = np.random.default_rng(seed)
    hours = np.arange(24 * days)
    hod = hours % 24
    # diurnal base shape
    base = (
        28
        + 10 * np.exp(-((hod - 8) ** 2) / 6)        # morning bump
        + 38 * np.exp(-((hod - 19) ** 2) / 5)       # evening peak
        - 8 * np.exp(-((hod - 3) ** 2) / 8)         # overnight trough
    )
    noise = rng.normal(0, 4, size=base.shape)
    prices = np.clip(base + noise, 8, None)
    # inject a few afternoon scarcity spikes on random days
    for _ in range(max(1, days // 3)):
        day = rng.integers(0, days)
        hr = rng.integers(16, 20)
        idx = day * 24 + hr
        if idx < len(prices):
            prices[idx] += rng.uniform(250, 900)
    return prices


def load_prices_csv(path, column="price"):
    """Drop-in real data: a CSV with a price column in $/MWh."""
    import pandas as pd
    return pd.read_csv(path)[column].to_numpy(dtype=float)


if __name__ == "__main__":
    bat = Battery()
    prices = make_synthetic_ercot_prices(days=7)

    # 1) Baseline solve with a 10 kWh family reserve
    res = optimize_dispatch(prices, bat, backup_reserve_kwh=10.0)
    print(f"Solver status        : {res['status']}")
    print(f"7-day arbitrage revenue (10 kWh reserve): ${res['revenue']:.2f}")
    print(f"SoC range observed   : {res['soc_kwh'].min():.1f} -> {res['soc_kwh'].max():.1f} kWh")
    print(f"Min SoC vs floor      : {res['soc_kwh'].min():.2f} kWh  (floor = 10.00)")

    # 2) The headline: revenue vs. resilience tradeoff
    print("\nRevenue vs. backup-reserve floor (the tradeoff):")
    print(f"{'reserve (kWh)':>14} | {'7-day revenue':>14} | {'vs. zero floor':>14}")
    sweep = sweep_backup_reserve(prices, bat, reserve_levels=[0, 5, 10, 15, 20])
    base_rev = sweep[0]["revenue"]
    for row in sweep:
        delta = row["revenue"] - base_rev
        print(f"{row['backup_reserve_kwh']:>14.0f} | ${row['revenue']:>12.2f} | ${delta:>12.2f}")
