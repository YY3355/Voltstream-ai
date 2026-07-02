"""
dcopf.py  —  a toy DC Optimal Power Flow, built to LEARN nodal pricing by computing it.

The point: locational marginal prices (LMPs) are not set by anyone — they FALL OUT of an
optimization as the shadow prices (duals) of the bus power-balance constraints. When no
transmission line is at its limit, every bus has the same price. The moment a line binds,
prices split, and the difference between buses IS the congestion component.

Toy system (deliberately ERCOT-shaped):
    WEST    : cheap wind (marginal cost ~$2), small load        — "generation pocket"
    NORTH   : mid-cost gas, medium load                          — reference/hub
    HOUSTON : expensive peaker, big load                         — "load pocket"
    Lines   : WEST-NORTH (the interesting one), NORTH-HOUSTON, WEST-HOUSTON

DC power flow (lossless, linearized): flow on a line = susceptance x angle difference.
So LMP decomposes as  LMP_i = energy + congestion_i  (no loss term in DC).

This is a LEARNING model: 3 buses, made-up costs/limits, not calibrated to the real grid.
Its purpose is to make 'binding constraint', 'shadow price', and 'congestion component'
things you have computed rather than words you have read.
"""
import numpy as np
import cvxpy as cp

BUSES = ["WEST", "NORTH", "HOUSTON"]
# generators: (bus, marginal cost $/MWh, capacity MW)
GENS = [("WEST", 2.0, 400.0),      # wind
        ("NORTH", 35.0, 300.0),    # gas CC
        ("HOUSTON", 80.0, 200.0)]  # peaker
LOAD = {"WEST": 20.0, "NORTH": 150.0, "HOUSTON": 250.0}
# lines: (from, to, susceptance, limit MW)
LINES = [("WEST", "NORTH", 10.0, 120.0),
         ("NORTH", "HOUSTON", 10.0, 200.0),
         ("WEST", "HOUSTON", 10.0, 100.0)]


def solve_dcopf(wn_limit=None, wh_limit=None, load_scale=1.0, limit_scale=1.0):
    """Solve the DCOPF. Returns LMPs (from duals), dispatch, flows, binding lines."""
    over = {("WEST", "NORTH"): wn_limit, ("WEST", "HOUSTON"): wh_limit}
    lines = [(f, t, b, (over[(f, t)] if over.get((f, t)) is not None else lim * limit_scale))
             for (f, t, b, lim) in LINES]
    nb = len(BUSES); bi = {b: i for i, b in enumerate(BUSES)}
    p = cp.Variable(len(GENS), nonneg=True)          # generation
    th = cp.Variable(nb)                             # bus angles
    flows = [b * (th[bi[f]] - th[bi[t]]) for (f, t, b, _) in lines]

    balance = []
    for bus in BUSES:
        inj = sum(p[g] for g, (gb, _, _) in enumerate(GENS) if gb == bus)
        out = sum(fl for fl, (f, t, _, _) in zip(flows, lines) if f == bus)
        inn = sum(fl for fl, (f, t, _, _) in zip(flows, lines) if t == bus)
        balance.append(inj + inn - out == LOAD[bus] * load_scale)

    lims = []
    for fl, (_, _, _, lim) in zip(flows, lines):
        lims += [fl <= lim, fl >= -lim]

    caps = [p[g] <= cap for g, (_, _, cap) in enumerate(GENS)]
    ref = [th[bi["NORTH"]] == 0]                     # angle reference
    cost = sum(c * p[g] for g, (_, c, _) in enumerate(GENS))
    prob = cp.Problem(cp.Minimize(cost), balance + lims + caps + ref)
    prob.solve(solver="HIGHS")
    if prob.status != "optimal":
        raise RuntimeError(f"DCOPF not optimal: {prob.status}")

    lmp = {bus: round(-float(balance[i].dual_value), 2) for i, bus in enumerate(BUSES)}
    line_rows = []
    for k, (fl, (f, t, _, lim)) in enumerate(zip(flows, lines)):
        mu_hi = float(lims[2 * k].dual_value or 0.0)
        mu_lo = float(lims[2 * k + 1].dual_value or 0.0)
        val = float(fl.value)
        line_rows.append({"line": f"{f}-{t}", "flow": round(val, 1), "limit": lim,
                          "binding": bool(abs(abs(val) - lim) < 1e-4),
                          "shadow_price": round(mu_hi + mu_lo, 2)})
    dispatch = {f"{gb} (${c:.0f})": round(float(p[g].value), 1)
                for g, (gb, c, _) in enumerate(GENS)}
    energy = lmp["NORTH"]                             # reference-bus price
    decomp = {bus: {"lmp": lmp[bus], "energy": energy,
                    "congestion": round(lmp[bus] - energy, 2)} for bus in BUSES}
    return {"lmp": lmp, "decomp": decomp, "dispatch": dispatch, "lines": line_rows,
            "total_cost": round(float(prob.value), 1)}


def sweep_transmission(scales=None):
    """Upgrade ALL transmission together: nodal prices converge to a single system price.
    (Upgrading one line alone just moves the binding constraint elsewhere — Kirchhoff routes
    flow by impedance, not by preference. That lesson is itself half the point of DCOPF.)"""
    scales = scales if scales is not None else [0.4, 0.7, 1.0, 1.5, 2.0, 3.0, 5.0]
    rows = []
    for s in scales:
        r = solve_dcopf(limit_scale=float(s))
        rows.append({"scale": s, **{b: r["lmp"][b] for b in BUSES},
                     "any_binding": any(x["binding"] for x in r["lines"])})
    return rows


if __name__ == "__main__":
    print("=== Case 1: roomy lines (no congestion) ===")
    r = solve_dcopf(wn_limit=2000.0, limit_scale=20.0)
    print("  LMPs:", r["lmp"], " <- one price everywhere")
    assert max(r["lmp"].values()) - min(r["lmp"].values()) < 0.01, "uncongested must be one price"

    print("\n=== Case 2: WEST-NORTH tight (the ERCOT-West story) ===")
    r = solve_dcopf()   # default 120 MW
    for b in BUSES:
        d = r["decomp"][b]
        print(f"  {b:<8} LMP ${d['lmp']:>6.2f} = energy ${d['energy']:.2f} + congestion ${d['congestion']:>6.2f}")
    for x in r["lines"]:
        tag = "BINDING" if x["binding"] else "ok"
        print(f"  {x['line']:<14} flow {x['flow']:>6.1f} / {x['limit']:.0f}  {tag}"
              + (f"  shadow ${x['shadow_price']}" if x["binding"] else ""))
    print("  dispatch:", r["dispatch"])
    assert r["lmp"]["WEST"] < r["lmp"]["NORTH"] <= r["lmp"]["HOUSTON"], "west should be trapped-cheap"
    assert any(x["binding"] for x in r["lines"]), "expected a binding line"

    print("\n=== Sweep: upgrade ALL transmission -> nodal prices converge to one price ===")
    for row in sweep_transmission():
        print(f"  lines x{row['scale']:<4} : WEST ${row['WEST']:>6.2f}  NORTH ${row['NORTH']:>6.2f}  "
              f"HOUSTON ${row['HOUSTON']:>6.2f}  {'(congested)' if row['any_binding'] else '(one price)'}")
    conv = sweep_transmission([5.0])[0]
    assert abs(conv['WEST'] - conv['HOUSTON']) < 0.01, 'high transmission must converge to one price'
    print("\nall assertions passed — LMPs, congestion split, and shadow prices computed from duals")
