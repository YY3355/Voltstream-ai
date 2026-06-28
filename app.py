"""
app.py  —  Volt Co-Pilot live backend (FastAPI).

Wraps the SAME modules you already built and verified:
    forecast_engine  (probabilistic GBM forecast)
    battery_dispatch (Bolt MILP optimizer)
    copilot          (agentic router + RAG + confidence layer)

and serves the live dashboard frontend. Engines recompute server-side against
whatever ercot_live.get_prices() returns (live feed in prod, cached CSVs locally).

Run:   uvicorn app:app --reload --port 8000
Open:  http://localhost:8000
"""
import os
import time
import numpy as np
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from ercot_live import get_prices, data_source, get_as_prices
from forecast_engine import build_features, fit_predict_gbm, DAY
from battery_dispatch import Battery, optimize_dispatch
from copilot import NOTICES, NoticeStore, route, HIGH_IMPACT, _llm_answer
from cooptimize import Battery as CoBattery, cooptimize, make_as_prices, DEFAULT_AS

app = FastAPI(title="Volt Co-Pilot API")
STORE = NoticeStore(NOTICES)
_CACHE = {"t": 0, "val": None}
TTL = float(os.environ.get("FORECAST_TTL", "60"))  # seconds


# ----------------------------- core compute (cached) -----------------------------
def compute_state(reserve_kwh: float = 10.0):
    now = time.time()
    if _CACHE["val"] and now - _CACHE["t"] < TTL and _CACHE["val"]["reserve"] == reserve_kwh:
        return _CACHE["val"]

    s = get_prices()
    feat = build_features(s).dropna()
    days = sorted({d.date() for d in feat.index})
    full = [d for d in days if (feat.index.date == d).sum() >= DAY]
    target = full[-1]
    test = feat[feat.index.date == target]
    train = feat[feat.index.date < target]
    q = fit_predict_gbm(train, test)
    p10, p50, p90 = q[0.1], q[0.5], q[0.9]
    actual = test["y"].values
    hours = [t.strftime("%H:%M") for t in test.index]
    peak = int(np.argmax(p50))
    rel_band = float(np.mean((p90 - p10) / np.maximum(p50, 1e-6)))

    bat = Battery()
    dt = 0.25
    sched = optimize_dispatch(p50, bat, reserve_kwh, dt_hours=dt)
    perfect = optimize_dispatch(actual, bat, reserve_kwh, dt_hours=dt)
    settled = float(np.sum((actual / 1000.0) * (sched["discharge_kw"] - sched["charge_kw"]) * dt))
    net0 = float(sched["discharge_kw"][0] - sched["charge_kw"][0])

    val = {
        "reserve": reserve_kwh,
        "source": data_source(),
        "target_date": str(target),
        "forecast": {"hours": hours,
                     "p10": [round(float(x), 1) for x in p10],
                     "p50": [round(float(x), 1) for x in p50],
                     "p90": [round(float(x), 1) for x in p90],
                     "actual": [round(float(x), 1) for x in actual],
                     "peak_idx": peak, "peak_time": hours[peak],
                     "peak_price": round(float(p50[peak]), 1),
                     "rel_band_pct": round(rel_band * 100)},
        "dispatch": {"charge_kw": [round(float(x), 2) for x in sched["charge_kw"]],
                     "discharge_kw": [round(float(x), 2) for x in sched["discharge_kw"]],
                     "soc_kwh": [round(float(x), 2) for x in sched["soc_kwh"]],
                     "reserve_kwh": reserve_kwh, "capacity_kwh": bat.usable_capacity_kwh,
                     "action_now": ("DISCHARGE" if net0 > 0.1 else "CHARGE" if net0 < -0.1 else "HOLD"),
                     "revenue_forecast": round(settled, 2),
                     "revenue_perfect": round(perfect["revenue"], 2),
                     "capture_pct": round(100 * settled / perfect["revenue"]) if perfect["revenue"] else 0},
        "notices": [{"id": n["id"], "title": n["title"], "type": n["type"]} for n in NOTICES],
        "_rel_band": rel_band,
    }
    _CACHE.update(t=now, val=val)
    return val


# ----------------------------- API -----------------------------
class Ask(BaseModel):
    question: str
    reserve_kwh: float = 10.0


@app.get("/api/state")
def api_state(reserve_kwh: float = 10.0):
    st = compute_state(reserve_kwh)
    return {k: v for k, v in st.items() if not k.startswith("_")}


@app.post("/api/ask")
def api_ask(body: Ask):
    st = compute_state(body.reserve_kwh)
    fc, dp = st["forecast"], st["dispatch"]
    tools = sorted(route(body.question))
    fires = {"router": True, "forecast": ("forecast" in tools or "dispatch" in tools),
             "dispatch": "dispatch" in tools, "retrieve": "retrieve" in tools}
    hits = STORE.retrieve(body.question, k=2) if fires["retrieve"] else []
    severe = any(n["type"] in HIGH_IMPACT for n, _ in hits)
    wide = st["_rel_band"] > 0.6
    verdict = "ESCALATE" if (severe or (wide and fires["forecast"])) else "AUTO"
    why = []
    if wide and fires["forecast"]: why.append(f"forecast uncertainty high (~{fc['rel_band_pct']}% spread)")
    if severe: why.append("a high-impact market notice is in play")
    if not why: why.append(f"forecast tight (~{fc['rel_band_pct']}% spread), no high-impact notices")
    why = "; ".join(why)

    # grounded brief — real LLM server-side if ANTHROPIC_API_KEY set, else template
    ctx_lines = []
    if fires["forecast"]:
        ctx_lines.append(f"- Forecast ({st['target_date']}): P50 peaks ~${fc['peak_price']}/MWh at "
                         f"{fc['peak_time']}; P10-P90 spread ~{fc['rel_band_pct']}% of P50.")
    if fires["dispatch"]:
        ctx_lines.append(f"- Bolt optimizer: action now = {dp['action_now']}; schedule captures "
                         f"{dp['capture_pct']}% of the perfect-foresight ceiling.")
    if fires["retrieve"]:
        if hits:
            for n, _ in hits:
                ctx_lines.append(f"- ERCOT notice [{n['id']}] ({n['type']}): {n['body']}")
        else:
            ctx_lines.append("- No ERCOT notices crossed the relevance threshold.")
    context = (f"Trader question: {body.question}\n\nEngine outputs the router gathered:\n"
               + "\n".join(ctx_lines) + f"\n\nConfidence layer verdict: {verdict} — {why}.")

    try:
        answer = _llm_answer(body.question, context) if os.getenv("ANTHROPIC_API_KEY") else context
        mode = "live · Claude" if os.getenv("ANTHROPIC_API_KEY") else "grounded template"
    except Exception:
        answer, mode = context, "grounded template (LLM unavailable)"

    return {"question": body.question, "tools": tools, "fires": fires,
            "retrieved": [{"id": n["id"], "title": n["title"], "type": n["type"],
                           "body": n["body"], "score": round(sc, 2)} for n, sc in hits],
            "verdict": verdict, "why": why, "answer": answer, "answer_mode": mode}


@app.get("/api/cooptimize")
def api_cooptimize(reserve_kwh: float = 10.0, ancillary: bool = True):
    """Live energy+AS co-optimization. Recomputes on each call (reserve / AS toggle)."""
    s = get_prices()
    energy = s.values[-96:] if len(s) >= 96 else s.values
    idx = s.index[-96:] if len(s) >= 96 else s.index
    real_as = get_as_prices(idx)
    if real_as is not None:
        asp = {k: (real_as[k][-len(energy):]) for k in real_as}
        as_source = "real ERCOT MCPC, day-ahead (gridstatus)"
    else:
        asp = make_as_prices(energy)
        as_source = "synthetic placeholder"
    if not ancillary:
        asp = {k: (v * 0) for k, v in asp.items()}
    bat = CoBattery()
    bat = CoBattery(initial_soc_kwh=min(bat.usable_capacity_kwh, max(bat.initial_soc_kwh, reserve_kwh)))
    try:
        res = cooptimize(energy, asp, bat, reserve_kwh)
        eo = cooptimize(energy, {k: (v * 0) for k, v in asp.items()}, bat, reserve_kwh)
    except Exception as e:
        return {"error": f"infeasible at reserve={reserve_kwh} kWh ({e})", "reserve_kwh": reserve_kwh}
    up = [p.name for p in DEFAULT_AS if p.direction == "up"]
    return {
        "ancillary": ancillary,
        "reserve_kwh": reserve_kwh,
        "capacity_kw": bat.max_power_kw,
        "hours": [round(i * 0.25, 2) for i in range(len(energy))],
        "energy_price": [round(float(x), 1) for x in energy],
        "discharge_kw": [round(float(x), 2) for x in res["discharge_kw"]],
        "charge_kw": [round(float(x), 2) for x in res["charge_kw"]],
        "as_award_kw": {k: [round(float(x), 2) for x in res["as_award_kw"][k]] for k in up},
        "energy_revenue": round(res["energy_revenue"], 2),
        "as_revenue": round(res["as_revenue"], 2),
        "total_revenue": round(res["total_revenue"], 2),
        "energy_only_total": round(eo["total_revenue"], 2),
        "data_source": data_source(),
        "as_source": as_source,
    }


@app.get("/api/vpp")
def api_vpp():
    """Fleet (VPP) view: runs the co-optimizer across a small heterogeneous fleet, aggregated."""
    from vpp import run_vpp, default_fleet
    s = get_prices()
    energy = s.values[-96:] if len(s) >= 96 else s.values
    idx = s.index[-96:] if len(s) >= 96 else s.index
    real_as = get_as_prices(idx)
    if real_as is not None:
        asp = {k: (real_as[k][-len(energy):]) for k in real_as}
        as_source = "real ERCOT MCPC, day-ahead (gridstatus)"
    else:
        asp = make_as_prices(energy)
        as_source = "synthetic placeholder"
    try:
        r = run_vpp(energy, default_fleet(), ancillary=True, as_prices=asp)
    except Exception as e:
        return {"error": f"vpp failed ({e})"}
    return {
        "n_units": r["n_units"],
        "fleet_capacity_kwh": round(r["fleet_capacity_kwh"], 1),
        "fleet_power_kw": round(r["fleet_power_kw"], 1),
        "energy_revenue": round(r["energy_revenue"], 2),
        "as_revenue": round(r["as_revenue"], 2),
        "total_revenue": round(r["total_revenue"], 2),
        "units": r["units"],
        "data_source": data_source(),
        "as_source": as_source,
    }


@app.get("/api/rt")
def api_rt():
    """Real-time decision-under-uncertainty: rolling no-peek policy vs perfect foresight."""
    from rt_engine import run_rt
    try:
        return run_rt(os.environ.get("ERCOT_DATA_DIR", "data"), reserve_kwh=5.0)
    except Exception as e:
        return {"error": f"rt engine failed ({e})"}


@app.get("/api/curve")
def api_curve():
    """Electricity forward curve: peak/off-peak monthly blocks + shaped hourly sample."""
    from forward_curve import build_forward_curve, is_onpeak
    try:
        r = build_forward_curve(os.environ.get("ERCOT_DATA_DIR", "data"))
    except Exception as e:
        return {"error": f"curve build failed ({e})"}
    months = r["months"]
    peak = [round(r["blocks"][m]["peak"], 2) for m in months]
    offpeak = [round(r["blocks"][m]["offpeak"], 2) for m in months]
    # a representative week (hourly) from the peak month, to show shaping granularity
    curve = r["curve"]
    peak_month = months[int(np.argmax(peak))]
    seg = curve[curve.index.to_period("M").astype(str) == peak_month].iloc[:168]
    return {
        "months": months,
        "peak": peak,
        "offpeak": offpeak,
        "spread": round(float(np.mean(peak)) - float(np.mean(offpeak)), 2),
        "low": round(float(curve.min()), 1),
        "high": round(float(curve.max()), 1),
        "n_hours": int(len(curve)),
        "reaggregation_ok": bool(r["reaggregation_ok"]),
        "sample_month": peak_month,
        "sample_hourly": [round(float(x), 1) for x in seg.values],
        "level_source": r["level_source"],
        "shape_source": r["shape_source"],
    }


@app.get("/api/swap")
def api_swap(strike: float = None, volume_mw: float = 10.0,
             start: str = None, end: str = None, product: str = "7x24"):
    """Fixed-for-floating power swap: mark-to-market vs the forward curve.

    MtM (fixed-payer perspective) = (forward_avg - strike) * volume_mw * hours.
    Defaults: full curve horizon, 7x24, 10 MW, strike set ~10% below the forward
    average so the demo MtM is non-trivial (override via query params)."""
    from forward_curve import build_forward_curve, value_swap
    try:
        r = build_forward_curve(os.environ.get("ERCOT_DATA_DIR", "data"))
    except Exception as e:
        return {"error": f"curve build failed ({e})"}
    curve, months = r["curve"], r["months"]
    s = start or months[0]
    e = end or months[-1]
    if strike is None:
        base = value_swap(curve, 0.0, volume_mw, s, e, product)["forward_avg"]
        strike = round(base * 0.9, 2)
    try:
        v = value_swap(curve, strike, volume_mw, s, e, product)
    except Exception as ex:
        return {"error": f"swap valuation failed ({ex})"}
    return {
        "strike": round(v["strike"], 2),
        "volume_mw": round(v["volume_mw"], 2),
        "product": v["product"],
        "start": s, "end": e,
        "forward_avg": round(v["forward_avg"], 2),
        "basis": round(v["basis"], 2),
        "hours": v["hours"],
        "notional_mwh": round(v["notional_mwh"], 1),
        "mtm": round(v["mtm"], 2),
        "months": months,
        "level_source": r["level_source"],
        "shape_source": r["shape_source"],
    }


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(os.path.dirname(__file__), "dashboard_live.html")) as f:
        return f.read()
