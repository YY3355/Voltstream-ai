"""
alert_engine.py  —  Phase 3: turn the platform from something you LOOK AT into something
that TELLS you. Threshold rules over data VoltStream already pulls honestly.

Each rule is a plain, inspectable condition on real data, and each carries a `rationale` —
the market reason it matters — so an alert is never a mystery number. Rules are declarative
data, not code, so the set is auditable and easy to extend.

DESIGN HONESTY:
  * Every alert cites the real value that triggered it and the threshold it crossed.
  * Rules encode market mechanisms we've actually established in this project:
      - light wind in the wind belt -> higher net load -> afternoon RT spike risk
        (this is the setup that preceded the -$320 paper-book day).
      - wide hub basis -> congestion between regions.
      - high shadow price -> a constraint is expensive right now.
  * Severity is explicit and ordered (info < watch < alert). No hidden scoring.
  * Nothing here predicts prices. Alerts describe CONDITIONS, not forecasts.
"""
import numpy as np

SEVERITY = {"info": 0, "watch": 1, "alert": 2}

# Declarative rule set. Each: id, source, severity, a check(fn)->(bool, value, detail), rationale.
# check functions read a `ctx` dict assembled by evaluate() from the live engines.
RULES = [
    {
        "id": "wind_belt_light",
        "source": "weather",
        "severity": "watch",
        "threshold": "wind-belt avg < 10 mph",
        "rationale": ("Light wind in the belt -> less wind generation -> higher net load. "
                      "This is the setup that precedes afternoon RT price spikes."),
        "check": lambda c: (
            (c.get("wind_belt_mph") is not None and c["wind_belt_mph"] < 10.0),
            c.get("wind_belt_mph"),
            f"wind belt {c.get('wind_belt_mph')} mph",
        ),
    },
    {
        "id": "wide_basis",
        "source": "dart",
        "severity": "watch",
        "threshold": "|hub basis vs North| > $10/MWh",
        "rationale": "A wide hub basis signals transmission congestion separating the regions.",
        "check": lambda c: (
            (c.get("max_abs_basis") is not None and c["max_abs_basis"] > 10.0),
            c.get("max_abs_basis"),
            f"max |basis| ${c.get('max_abs_basis')}/MWh at {c.get('max_basis_hub')}",
        ),
    },
    {
        "id": "dart_rich_peak",
        "source": "dart",
        "severity": "info",
        "threshold": "any hub DART mean > $5/MWh",
        "rationale": ("DA running rich to RT. Selling DA collects on average but is SHORT the "
                      "afternoon tail — the exposure that caused the paper book's worst day."),
        "check": lambda c: (
            (c.get("max_dart") is not None and c["max_dart"] > 5.0),
            c.get("max_dart"),
            f"max hub DART ${c.get('max_dart')}/MWh at {c.get('max_dart_hub')}",
        ),
    },
    {
        "id": "high_shadow_price",
        "source": "constraints",
        "severity": "alert",
        "threshold": "any binding constraint shadow price > $500/MWh",
        "rationale": ("A constraint is very expensive right now — large congestion value on a "
                      "specific line. Where basis blows out and batteries on the right side win."),
        "check": lambda c: (
            (c.get("max_shadow") is not None and c["max_shadow"] > 500.0),
            c.get("max_shadow"),
            f"${c.get('max_shadow')}/MWh on {c.get('max_shadow_constraint')}",
        ),
    },
    {
        "id": "constraint_binding_now",
        "source": "constraints",
        "severity": "info",
        "threshold": "any constraint binding this SCED run",
        "rationale": "At least one transmission constraint is actively binding right now.",
        "check": lambda c: (
            (c.get("n_binding") is not None and c["n_binding"] > 0),
            c.get("n_binding"),
            f"{c.get('n_binding')} constraint(s) binding now",
        ),
    },
]


# ----------------------------- context assembly (pure) -----------------------------
def context_from_sources(dart=None, weather=None, constraints=None):
    """Flatten the live engine outputs into the scalar ctx the rules read. Pure/testable."""
    c = {}
    if dart and "stats" in dart:
        darts = {h: s.get("mean") for h, s in dart["stats"].items() if s.get("mean") is not None}
        if darts:
            hub = max(darts, key=lambda h: darts[h])
            c["max_dart"] = round(darts[hub], 2); c["max_dart_hub"] = hub
        basis = dart.get("basis", {})
        if basis:
            k = max(basis, key=lambda b: abs(basis[b].get("last", basis[b].get("mean", 0))))
            v = basis[k].get("last", basis[k].get("mean"))
            c["max_abs_basis"] = round(abs(float(v)), 2); c["max_basis_hub"] = k
    if weather and weather.get("signal"):
        c["wind_belt_mph"] = weather["signal"].get("wind_belt_avg_mph")
    if constraints:
        arcs = constraints.get("arcs", [])
        sp = [a.get("shadow_price", 0) for a in arcs] + \
             [u.get("shadow_price", 0) for u in constraints.get("unplaced", [])]
        binding = [x for x in sp if x and x > 0]
        c["n_binding"] = len(binding)
        if binding:
            c["max_shadow"] = round(max(binding), 2)
            top = max(arcs, key=lambda a: a.get("shadow_price", 0)) if arcs else None
            c["max_shadow_constraint"] = (top or {}).get("constraint")
    return c


def evaluate(ctx, rules=RULES):
    """Run the rule set over a context. Returns fired alerts, severity-sorted."""
    fired = []
    for r in rules:
        try:
            ok, value, detail = r["check"](ctx)
        except Exception:
            ok = False
        if ok:
            fired.append({
                "id": r["id"], "source": r["source"], "severity": r["severity"],
                "severity_rank": SEVERITY[r["severity"]],
                "threshold": r["threshold"], "value": value, "detail": detail,
                "rationale": r["rationale"],
            })
    fired.sort(key=lambda a: -a["severity_rank"])
    return {
        "alerts": fired,
        "n": len(fired),
        "max_severity": (fired[0]["severity"] if fired else "none"),
        "context": ctx,
        "note": ("Alerts describe conditions on real ERCOT data crossing stated thresholds. "
                 "They are not price forecasts."),
    }


def run_alerts(dart=None, weather=None, constraints=None):
    return evaluate(context_from_sources(dart, weather, constraints))


# ----------------------------- fixture self-test -----------------------------
if __name__ == "__main__":
    # A "calm" world: nothing should fire except maybe info-level.
    calm = run_alerts(
        dart={"stats": {"HB_HOUSTON": {"mean": 1.0}, "HB_NORTH": {"mean": 0.5}},
              "basis": {"WEST-NORTH": {"last": -3.0}}},
        weather={"signal": {"wind_belt_avg_mph": 18.0}},
        constraints={"arcs": [], "unplaced": []},
    )
    assert calm["max_severity"] in ("none", "info"), calm["max_severity"]
    assert not any(a["severity"] == "alert" for a in calm["alerts"]), "calm world has no alerts"

    # A "stressed" world: light wind, wide basis, rich DART, expensive constraint.
    stress = run_alerts(
        dart={"stats": {"HB_HOUSTON": {"mean": 8.3}, "HB_WEST": {"mean": -2.0}},
              "basis": {"WEST-NORTH": {"last": -14.5}}},
        weather={"signal": {"wind_belt_avg_mph": 7.4}},
        constraints={"arcs": [{"constraint": "MGSES_CATSW", "shadow_price": 900.0}],
                     "unplaced": [{"constraint": "X", "shadow_price": 120.0}]},
    )
    ids = {a["id"] for a in stress["alerts"]}
    assert "wind_belt_light" in ids, "light wind must fire"
    assert "wide_basis" in ids, "wide basis must fire"
    assert "dart_rich_peak" in ids, "rich DART must fire"
    assert "high_shadow_price" in ids, "expensive constraint must fire"
    assert stress["max_severity"] == "alert", "shadow-price rule is alert-level"
    assert stress["alerts"][0]["severity"] == "alert", "must sort most-severe first"
    # every alert cites a value and a rationale
    assert all(a["value"] is not None and a["rationale"] for a in stress["alerts"])
    wb = next(a for a in stress["alerts"] if a["id"] == "wind_belt_light")
    assert wb["value"] == 7.4 and "net load" in wb["rationale"]
    hs = next(a for a in stress["alerts"] if a["id"] == "high_shadow_price")
    assert hs["value"] == 900.0 and "MGSES" in hs["detail"]

    # missing sources must never crash — rules just don't fire
    partial = run_alerts(dart=None, weather={"signal": {"wind_belt_avg_mph": 6.0}}, constraints=None)
    assert any(a["id"] == "wind_belt_light" for a in partial["alerts"])
    assert partial["context"].get("max_dart") is None

    print("fixture self-test PASSED")
    print(f"  calm world: {calm['n']} alert(s), max severity '{calm['max_severity']}'")
    print(f"  stressed world: {stress['n']} alerts, max '{stress['max_severity']}'")
    for a in stress["alerts"]:
        print(f"    [{a['severity'].upper():5}] {a['id']}: {a['detail']}")
    print("  (fixture verifies rule logic + graceful missing-source handling)")
