"""
cooptimize.py  —  energy + ancillary-services co-optimization for an ERCOT battery.

This extends the energy-only Bolt optimizer to the thing that actually separates a
real ERCOT battery strategy post-RTC+B: co-optimizing energy arbitrage AND ancillary
services (AS) against a single, shared power-and-energy budget, with state-of-charge
awareness for the AS commitments.

WHY THIS IS THE RIGHT FORMULATION (the parts a desk would check):

1. Shared power headroom. In any interval the battery's inverter can only do so much.
   Energy dispatch and every AS award compete for the same +/-P_max envelope:
       up-direction   :  (d - c) + sum(up AS)   <=  P_max     (room to inject more)
       down-direction :  (d - c) - sum(down AS) >= -P_max     (room to absorb more)

2. SoC-aware AS (the RTC+B innovation for storage). You can't sell reserve you can't
   deliver. Each AS product must be *sustainable* for a required duration without
   violating the backup floor (up products) or the capacity ceiling (down products):
       up   :  soc - sum(up_k   * dur_k / eta)  >= backup_reserve
       down :  soc + sum(down_k * dur_k * eta)  <= usable_capacity

3. The household backup floor is preserved throughout — the differentiator from the
   utility-scale framing, carried over from the energy-only model.

HONEST ASSUMPTIONS (state these out loud; a real desk will ask):
   * Deterministic, perfect-foresight planning model over the horizon. NOT the live
     5-minute SCED. It computes an upper bound / strategy view, not real-time bids.
   * AS is paid as *capacity* (MCPC * MW * hours). Deployment is modeled only as an
     energy-sufficiency constraint, not as actual SoC movement (deployment is
     uncertain). This is the standard conservative simplification.
   * AS price series here are SYNTHETIC, calibrated to plausible ERCOT levels, with a
     CSV hook for real MCPC data. Energy prices are the real ERCOT data when available.
   * Single AS award per product per interval; no AS substitution/cascading.

WHAT A PRODUCTION VERSION ADDS (what we are NOT claiming to do):
   real-time SCED co-optimization, probabilistic deployment & opportunity cost,
   degradation cost, AS qualification/telemetry rules, price-forecast uncertainty,
   and bid-curve construction rather than a single cleared schedule.
"""
from dataclasses import dataclass, field
import numpy as np
import cvxpy as cp


@dataclass
class Battery:
    usable_capacity_kwh: float = 25.0
    max_power_kw: float = 12.5
    round_trip_efficiency: float = 0.90
    initial_soc_kwh: float = 12.5

    @property
    def eta(self) -> float:
        return float(np.sqrt(self.round_trip_efficiency))


@dataclass
class ASProduct:
    name: str
    direction: str          # "up" or "down"
    duration_h: float       # hours of sustained deployment the award must cover (energy sufficiency)


# ERCOT-style AS products (durations are modeling assumptions, clearly flagged).
DEFAULT_AS = [
    ASProduct("RegUp",   "up",   0.25),
    ASProduct("RegDown", "down", 0.25),
    ASProduct("RRS",     "up",   1.0),
    ASProduct("ECRS",    "up",   2.0),
    ASProduct("NonSpin", "up",   1.0),
]


def cooptimize(energy_price_mwh, as_prices_mwh, battery: Battery, backup_reserve_kwh,
               products=DEFAULT_AS, dt_h=0.25, require_end_soc=True, solver="HIGHS"):
    """
    energy_price_mwh : array[T] energy price ($/MWh)
    as_prices_mwh    : dict{product_name: array[T]} AS capacity price ($/MW/h)
    Returns schedule + revenue split.
    """
    pe = np.asarray(energy_price_mwh, float) / 1000.0          # $/kWh
    T = len(pe)
    eta, P, E, soc0 = battery.eta, battery.max_power_kw, battery.usable_capacity_kwh, battery.initial_soc_kwh
    B = backup_reserve_kwh
    up = [p for p in products if p.direction == "up"]
    dn = [p for p in products if p.direction == "down"]

    c = cp.Variable(T, nonneg=True)        # charge kW
    d = cp.Variable(T, nonneg=True)        # discharge kW
    soc = cp.Variable(T)
    y = cp.Variable(T, boolean=True)       # 1=charge mode (no simultaneous c&d) -> MILP
    a = {p.name: cp.Variable(T, nonneg=True) for p in products}   # AS award kW

    cons = []
    n = d - c                              # net injection
    for t in range(T):
        prev = soc0 if t == 0 else soc[t - 1]
        cons += [soc[t] == prev + eta * c[t] * dt_h - (1.0 / eta) * d[t] * dt_h]

    cons += [c <= P * y, d <= P * (1 - y)]
    cons += [soc >= B, soc <= E]
    if up:
        up_sum = sum(a[p.name] for p in up)
        cons += [n + up_sum <= P]                                   # up power headroom
        cons += [soc - sum(a[p.name] * p.duration_h / eta for p in up) >= B]   # up energy sufficiency
    if dn:
        dn_sum = sum(a[p.name] for p in dn)
        cons += [n - dn_sum >= -P]                                  # down power headroom
        cons += [soc + sum(a[p.name] * p.duration_h * eta for p in dn) <= E]   # down energy sufficiency
    for p in products:
        cons += [a[p.name] <= P]
    if require_end_soc:
        cons += [soc[T - 1] >= soc0]

    energy_rev = cp.sum(cp.multiply(pe, n) * dt_h)
    as_rev = 0
    for p in products:
        pas = np.asarray(as_prices_mwh[p.name], float) / 1000.0     # $/kWh-cap-h
        as_rev = as_rev + cp.sum(cp.multiply(pas, a[p.name]) * dt_h)

    prob = cp.Problem(cp.Maximize(energy_rev + as_rev), cons)
    prob.solve(solver=solver)
    if prob.status not in ("optimal", "optimal_inaccurate"):
        raise RuntimeError(f"solver status: {prob.status}")

    return {
        "status": prob.status,
        "total_revenue": float(prob.value),
        "energy_revenue": float(energy_rev.value),
        "as_revenue": float(as_rev.value),
        "charge_kw": np.maximum(c.value, 0),
        "discharge_kw": np.maximum(d.value, 0),
        "soc_kwh": soc.value,
        "as_award_kw": {k: np.maximum(v.value, 0) for k, v in a.items()},
    }


# ---- synthetic-but-calibrated AS prices (clearly a placeholder; swap real MCPC via CSV) ----
def make_as_prices(energy_price_mwh, seed=11):
    rng = np.random.default_rng(seed)
    T = len(energy_price_mwh)
    hod = np.arange(T) % 96 * (24 / 96)        # assumes 15-min intervals
    ramp = np.exp(-((hod - 19) ** 2) / 6)      # evening ramp premium
    base = {"RegUp": 9, "RegDown": 6, "RRS": 7, "ECRS": 11, "NonSpin": 4}
    out = {}
    for k, b in base.items():
        series = b + 18 * ramp + rng.normal(0, 1.2, T)
        out[k] = np.clip(series, 1, None)
    return out


if __name__ == "__main__":
    # real ERCOT energy prices if available, else synthetic
    try:
        from ercot_data import load_prices
        s = load_prices("data")
        energy = s.values[-96:] if len(s) >= 96 else s.values
        src = "real ERCOT HB_HOUSTON"
    except Exception:
        rng = np.random.default_rng(3); hod = np.arange(96) * 0.25
        energy = np.clip(28 + 30 * np.exp(-((hod - 19) ** 2) / 5) + rng.normal(0, 4, 96), 8, None)
        src = "synthetic energy"
    asp = make_as_prices(energy)
    bat, reserve = Battery(), 10.0

    energy_only_asp = {k: np.zeros_like(v) for k, v in asp.items()}   # zero AS price = energy-only
    eo = cooptimize(energy, energy_only_asp, bat, reserve)
    co = cooptimize(energy, asp, bat, reserve)

    print(f"Energy prices: {src} | {len(energy)} intervals | AS prices: synthetic (placeholder)\n")
    print(f"{'strategy':<22}{'energy $':>12}{'AS $':>12}{'total $':>12}")
    print(f"{'energy-only':<22}{eo['energy_revenue']:>12.2f}{eo['as_revenue']:>12.2f}{eo['total_revenue']:>12.2f}")
    print(f"{'co-optimized E+AS':<22}{co['energy_revenue']:>12.2f}{co['as_revenue']:>12.2f}{co['total_revenue']:>12.2f}")
    uplift = 100 * (co['total_revenue'] - eo['total_revenue']) / abs(eo['total_revenue']) if eo['total_revenue'] else float('nan')
    print(f"\nco-optimization uplift over energy-only: {uplift:.0f}%")
    print(f"AS share of co-opt revenue: {100*co['as_revenue']/co['total_revenue']:.0f}%")
