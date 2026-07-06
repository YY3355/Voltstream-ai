"""
vpp.py  —  a small virtual power plant (VPP) view on top of the single-battery co-optimizer.

A VPP is just many distributed batteries coordinated as one grid resource. This runs the
EXISTING co-optimizer (cooptimize.py) across a small, heterogeneous fleet and aggregates the
result, so you can see fleet-level dispatch and revenue, and the spread across units.

WHAT THIS HONESTLY IS:
  * Each battery is optimized against the same ERCOT price path with its own size, power,
    starting charge, and backup-reserve need. Fleet output = sum of the per-battery optima.
  * This shows the *economics* of aggregating distributed storage: how a mixed fleet behaves
    and earns versus the trends everyone is talking about (VPPs as grid infrastructure).

WHAT IT IS NOT (state this plainly so the post never overclaims):
  * Not a real VPP platform. No distribution-network limits, no feeder/transformer constraints,
    no device telemetry/comms, no real-time dispatch signal, no settlement with an aggregator.
  * Independent per-battery optimization (no inter-unit coupling beyond shared prices).
  * Same simplifications as the base model: deterministic, perfect-foresight planning, synthetic
    or day-ahead AS prices. A real deployment co-optimizes the fleet under network constraints.
"""
from dataclasses import dataclass
import numpy as np
from cooptimize import Battery, cooptimize, make_as_prices, DEFAULT_AS


@dataclass
class FleetUnit:
    name: str
    battery: Battery
    reserve_kwh: float


def default_fleet():
    """A small, deliberately heterogeneous home/C&I fleet (mixed sizes, power, backup needs).

    Names describe the site archetype, not real installations. Specs are realistic
    (13.5 kWh is Powerwall-class; 25 kWh a larger home system; 60 kWh a small C&I site).
    The two 25 kWh units are identical hardware with different reserve, to show the effect.
    """
    return [
        FleetUnit("Home (backup)",    Battery(25, 12.5, 0.90, 12.5), reserve_kwh=10),  # holds real backup
        FleetUnit("Powerwall",        Battery(13.5, 5.0, 0.90, 7.0), reserve_kwh=6),   # Powerwall-class home
        FleetUnit("Home (low res.)",  Battery(25, 12.5, 0.90, 12.5), reserve_kwh=4),   # same as #1, light backup
        FleetUnit("C&I site",         Battery(60, 30.0, 0.90, 30.0), reserve_kwh=10),  # small commercial site
        FleetUnit("Powerwall (arb.)", Battery(13.5, 5.0, 0.90, 7.0), reserve_kwh=0),   # pure arbitrage
    ]


def run_vpp(energy_price_mwh, fleet=None, ancillary=True, as_prices=None):
    """Optimize each unit, then aggregate into a fleet (VPP) result."""
    fleet = fleet or default_fleet()
    energy = np.asarray(energy_price_mwh, float)
    asp = as_prices if as_prices is not None else make_as_prices(energy)
    if not ancillary:
        asp = {k: (v * 0) for k, v in asp.items()}
    T = len(energy)

    agg = {"discharge_kw": np.zeros(T), "charge_kw": np.zeros(T),
           "as_award_kw": {p.name: np.zeros(T) for p in DEFAULT_AS if p.direction == "up"},
           "energy_revenue": 0.0, "as_revenue": 0.0, "total_revenue": 0.0}
    units, fleet_kwh, fleet_kw = [], 0.0, 0.0
    for u in fleet:
        r = cooptimize(energy, asp, u.battery, u.reserve_kwh)
        agg["discharge_kw"] += r["discharge_kw"]
        agg["charge_kw"] += r["charge_kw"]
        for k in agg["as_award_kw"]:
            agg["as_award_kw"][k] += r["as_award_kw"][k]
        agg["energy_revenue"] += r["energy_revenue"]
        agg["as_revenue"] += r["as_revenue"]
        agg["total_revenue"] += r["total_revenue"]
        fleet_kwh += u.battery.usable_capacity_kwh
        fleet_kw += u.battery.max_power_kw
        units.append({"name": u.name, "capacity_kwh": u.battery.usable_capacity_kwh,
                      "power_kw": u.battery.max_power_kw, "reserve_kwh": u.reserve_kwh,
                      "revenue": round(r["total_revenue"], 2)})
    agg["units"] = units
    agg["fleet_capacity_kwh"] = fleet_kwh
    agg["fleet_power_kw"] = fleet_kw
    agg["n_units"] = len(fleet)
    return agg


if __name__ == "__main__":
    try:
        from ercot_data import load_prices
        energy = load_prices("data").values[-96:]; src = "real ERCOT HB_HOUSTON"
    except Exception:
        rng = np.random.default_rng(3); hod = np.arange(96) * 0.25
        energy = np.clip(28 + 30 * np.exp(-((hod - 19) ** 2) / 5) + rng.normal(0, 4, 96), 8, None)
        src = "synthetic"
    r = run_vpp(energy)
    print(f"Fleet: {r['n_units']} batteries, {r['fleet_capacity_kwh']:.0f} kWh / {r['fleet_power_kw']:.0f} kW | prices: {src}\n")
    print(f"{'unit':<8}{'kWh':>7}{'kW':>7}{'reserve':>9}{'rev $':>9}")
    for u in r["units"]:
        print(f"{u['name']:<8}{u['capacity_kwh']:>7.0f}{u['power_kw']:>7.1f}{u['reserve_kwh']:>9.0f}{u['revenue']:>9.2f}")
    print(f"\nfleet energy ${r['energy_revenue']:.2f} | AS ${r['as_revenue']:.2f} | total ${r['total_revenue']:.2f}")
    print(f"AS share: {100*r['as_revenue']/r['total_revenue']:.0f}%")
