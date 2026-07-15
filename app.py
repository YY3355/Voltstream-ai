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
from datetime import timedelta
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
    # cap the GBM training window: the rolling store holds ~30 days, and fitting 3 quantile
    # models over all of it makes /api/state ~40s+ (too slow for the landing tab / cloud timeouts).
    # Recent days carry the hour-of-day pattern; keep it snappy. Tunable via FORECAST_TRAIN_DAYS.
    train_days = int(os.environ.get("FORECAST_TRAIN_DAYS", "10"))
    lo = target - timedelta(days=train_days)
    train = feat[(feat.index.date < target) & (feat.index.date >= lo)]
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


@app.get("/api/risk")
def api_risk():
    """Quant-risk layer: Monte-Carlo P&L distribution, VaR/ES, and battery optionality.

    First call runs the Monte Carlo (~25s); risk_engine caches the result thereafter."""
    from risk_engine import run_risk
    try:
        return run_risk(os.environ.get("ERCOT_DATA_DIR", "data"))
    except Exception as e:
        return {"error": f"risk engine failed ({e})"}


@app.get("/api/qse")
def api_qse():
    """Dynamic QSE loop experiment: cost of stale telemetry + MW/MWh coordination.

    Models the concept from Habitat's QSE write-up on simulated paths (NOT a real QSE).
    First call runs the Monte Carlo (~25-30s); qse_loop caches the result thereafter."""
    from qse_loop import run_qse
    try:
        return run_qse(os.environ.get("ERCOT_DATA_DIR", "data"))
    except Exception as e:
        return {"error": f"qse loop failed ({e})"}


@app.on_event("startup")
def _prewarm_dart():
    """Kick off the (slow, live) DART fetch in the background at startup so the panel is
    warm by the time anyone loads it. Non-blocking: the server accepts requests immediately.
    With the on-disk cache, complete past days aren't re-scraped, so restarts warm fast."""
    import threading

    def _warm():
        try:
            from dart_engine import run_dart, prune_cache
            prune_cache(30)          # drop cached day-files older than 30 days
            try:
                from ercot_archiver import backfill_prices_to_cache, backfill_constraints_to_cache
                backfill_prices_to_cache(30)      # fast (~3s): 30 real days of HB_HOUSTON RT SPP
                backfill_constraints_to_cache(14)  # fast: 14 days of SCED constraints for bind counts
            except Exception:
                pass
            run_dart()                        # DART warms + caches its own recent gridstatus days
        except Exception:
            pass

    threading.Thread(target=_warm, name="dart-prewarm", daemon=True).start()


@app.get("/api/dart")
def api_dart():
    """DART spreads (Day-Ahead minus Real-Time) + hub-basis congestion proxy.

    LIVE ERCOT data via gridstatus (DA hourly + RT 15-min, Trading Hubs). First call
    fetches several days (~slow); dart_engine caches for 30 min. No synthetic fallback:
    returns an honest error dict if the live pull fails."""
    from dart_engine import run_dart
    try:
        return run_dart()
    except Exception as e:
        return {"error": f"dart engine failed ({e})"}


@app.get("/api/map")
def api_map():
    """Geospatial DART map: real ERCOT hub coordinates joined to the live DART result.

    Calls dart_engine.run_dart() (reuses DART's gridstatus cache — fast once warm) and
    map_data.build_map() to attach each hub's live DART spread to an honest regional marker.
    Passes DART errors through unchanged (no fake map): hub markers are REGIONAL centers, not
    physical buses. Points without live data are omitted rather than fabricated."""
    from dart_engine import run_dart
    import map_data
    try:
        return map_data.build_map(run_dart())
    except Exception as e:
        return {"error": f"map build failed ({e})", "points": []}


@app.get("/api/geo")
def api_geo():
    """Geography layers for the Map tab: EIA-860M batteries + power plants (asset-exact
    coordinates), embedded TX cities (Census centroids), and a per-county battery MW rollup.

    Served from the cached geo pickles (data_archive/geo/, built by `python geo_data.py fetch`
    with an EIA_API_KEY). Cities are always available (embedded); batteries/plants appear once
    the EIA cache exists. Honest empty-state — no fabricated coordinates, points without a real
    lat/lon are already dropped upstream."""
    import geo_data
    try:
        batteries, plants, cities = geo_data.load_geo()
        if (cities is None or cities.empty):
            cities = geo_data.cities_table()          # embedded fallback (never needs the fetch)

        def recs(df, cols):
            if df is None or df.empty:
                return []
            keep = [c for c in cols if c in df.columns]
            return df[keep].to_dict("records")

        batt = recs(batteries, ["plant_id", "plant", "operator", "tech", "county", "mw", "lat", "lon", "precision"])
        plnt = recs(plants, ["plant_id", "plant", "operator", "tech", "county", "mw", "lat", "lon", "precision"])
        city = recs(cities, ["name", "county", "population", "lat", "lon", "precision"])
        rollup = recs(geo_data.county_rollup(batteries) if (batteries is not None and not batteries.empty) else None,
                      ["county", "assets", "mw", "lat", "lon"])

        assets_cached = bool(batt or plnt)
        return {
            "available": True,
            "assets_cached": assets_cached,
            "batteries": batt, "plants": plnt, "cities": city, "county_rollup": rollup,
            "counts": {"batteries": len(batt), "plants": len(plnt), "cities": len(city),
                       "battery_counties": len(rollup)},
            "note": ("Battery & power-plant markers are EIA-860M asset coordinates (exact). City "
                     "markers are Census centroids, NOT load-delivery points. Data centers and "
                     "city-level load are deliberately absent — no authoritative public dataset."),
            "assets_note": (None if assets_cached else
                            "EIA generator inventory not cached yet — run `python geo_data.py "
                            "fetch` (needs a valid EIA_API_KEY) to populate batteries & plants."),
        }
    except Exception as e:
        return {"available": False, "error": f"geo load failed ({e})",
                "batteries": [], "plants": [], "cities": [], "county_rollup": []}


@app.get("/api/dcopf")
def api_dcopf():
    """Toy 3-bus DC optimal power flow: nodal prices (LMPs) and congestion as duals.

    Returns a congested case (WEST-NORTH line tight), an uncongested case (roomy lines ->
    one price everywhere), and a transmission-upgrade sweep. A learning model with made-up
    costs, not calibrated to the real grid."""
    from dcopf import solve_dcopf, sweep_transmission
    try:
        return {
            "congested": solve_dcopf(),
            "uncongested": solve_dcopf(limit_scale=20.0),
            "sweep": sweep_transmission(),
        }
    except Exception as e:
        return {"error": f"dcopf failed ({e})"}


@app.get("/api/constraints")
def api_constraints():
    """Live SCED binding transmission constraints (NP6-86-CD, official ERCOT API): today's
    binding constraints with shadow prices sorted by severity, plus how many recent cached
    days each constraint has bound. Reads REAL constraint data — it is NOT a grid model (no
    topology, no shift factors); it's the reality counterpart to the toy DCOPF."""
    import pandas as pd
    from ercot_archiver import most_recent_day, ensure_day, cached_days, CACHE_DIR, _day_path
    emil = "NP6-86-CD"
    try:
        day = most_recent_day(emil)
        if not day:
            return {"error": "no SCED shadow-price archive available"}
        df = ensure_day(emil, day).copy()
        if not len(df):
            return {"error": f"no constraint rows for {day}"}
    except Exception as e:
        return {"error": f"constraints unavailable ({e})"}
    df["ShadowPrice"] = pd.to_numeric(df["ShadowPrice"], errors="coerce")
    binding = df[df["ShadowPrice"] > 0]

    # recent bind-frequency: over all cached NP6-86-CD days, count days each constraint bound
    days = cached_days(emil)
    freq = {}
    for d in days:
        try:
            dd = pd.read_pickle(_day_path(emil, d))
            dd["ShadowPrice"] = pd.to_numeric(dd["ShadowPrice"], errors="coerce")
            for c in dd.loc[dd["ShadowPrice"] > 0, "ConstraintName"].astype(str).unique():
                freq[c] = freq.get(c, 0) + 1
        except Exception:
            pass

    def mode(s):
        m = s.astype(str).mode()
        return m.iloc[0] if len(m) else ""

    g = (binding.groupby("ConstraintName")
         .agg(max_shadow=("ShadowPrice", "max"), mean_shadow=("ShadowPrice", "mean"),
              intervals=("ShadowPrice", "size"), contingency=("ContingencyName", mode))
         .sort_values("max_shadow", ascending=False).reset_index())
    constraints = [{"name": r["ConstraintName"], "contingency": r["contingency"],
                    "max_shadow": round(float(r["max_shadow"]), 2),
                    "mean_shadow": round(float(r["mean_shadow"]), 2),
                    "intervals": int(r["intervals"]),
                    "bound_days_recent": int(freq.get(r["ConstraintName"], 0))}
                   for _, r in g.iterrows()]
    return {
        "as_of_day": day,
        "n_docs": int(df["_docId"].nunique()) if "_docId" in df.columns else None,
        "n_binding": int(binding["ConstraintName"].nunique()),
        "n_constraints_seen": int(df["ConstraintName"].nunique()),
        "cached_days": len(days),
        "constraints": constraints,
        "source": "LIVE ERCOT SCED shadow prices (NP6-86-CD) via official API",
    }


@app.get("/api/journal")
def api_journal():
    """DART paper-trading P&L from journal/ledger.csv — a git-audited discipline record
    (calls committed in advance, virtual fills at settlement, no execution/fees). Honest
    empty state until the first settlement writes the ledger."""
    import pandas as pd
    EMPTY = {"n_days": 0, "total_pnl": 0.0, "hit_rate_pct": None, "by_hub": {},
             "cum_series": [], "note": "no settled days yet — first settlement 2026-07-05"}
    path = os.path.join(os.path.dirname(__file__), "journal", "ledger.csv")
    if not os.path.exists(path):
        return EMPTY
    try:
        df = pd.read_csv(path)
        if df.empty:
            return EMPTY
        daily = df.groupby("date")["pnl"].sum().sort_index()
        cum = daily.cumsum()
        cum_series = [{"date": str(d), "pnl": round(float(daily[d]), 2), "cum": round(float(cum[d]), 2)}
                      for d in daily.index]
        hit = float(((df["position"] * df["dart"]) > 0).mean())
        by_hub = {str(h): round(float(v), 2) for h, v in df.groupby("hub")["pnl"].sum().items()}
        return {"n_days": int(df["date"].nunique()),
                "total_pnl": round(float(df["pnl"].sum()), 2),
                "hit_rate_pct": round(100 * hit, 1),
                "by_hub": by_hub,
                "cum_series": cum_series,
                "n_positions": int(len(df))}
    except Exception as e:
        return {"error": f"journal read failed ({e})"}


@app.get("/api/decade")
def api_decade():
    """The Decade Study: a multi-year perfect-foresight battery-arbitrage backtest on real ERCOT
    HB_HOUSTON prices — yearly $/MW-year, revenue concentration, design-lever sweep, and a
    bootstrap forward scenario. Served from a pre-computed cache (data_archive/decade_result.json,
    minutes of compute); returns an honest note if the cache hasn't been built yet."""
    import json
    # committed 4KB summary at the repo root (ships in the image); override via DECADE_RESULT.
    path = os.environ.get("DECADE_RESULT",
                          os.path.join(os.path.dirname(__file__), "decade_result.json"))
    if not os.path.exists(path):
        return {"available": False,
                "note": "decade study not computed yet — run `python decade_run.py` to build "
                        "data_archive/decade_result.json from the bundle cache"}
    try:
        with open(path) as f:
            result = json.load(f)
        result["available"] = True
        return result
    except Exception as e:
        return {"error": f"decade result read failed ({e})"}


@app.get("/api/hedge")
def api_hedge():
    """The hedging layer on the Decade Study: how much of a battery's merchant revenue to sell
    forward as a flat fixed-for-floating swap. Serves a hedge-ratio sweep (0..1) with across-year
    mean/std/worst/best, the interior minimum-variance ratio, and per-year merchant-vs-hedged at
    full hedge. Strike is a STATED PROXY (across-years mean of realized hub averages), zero
    expected P&L by construction; energy-only, analysis not advice. Pre-computed cache
    (hedge_result.json); returns an honest note if not built yet."""
    import json
    # committed ~2.5KB summary at the repo root (ships in the image); override via HEDGE_RESULT.
    path = os.environ.get("HEDGE_RESULT",
                          os.path.join(os.path.dirname(__file__), "hedge_result.json"))
    if not os.path.exists(path):
        return {"available": False,
                "note": "hedge study not computed yet — run `python hedge_run.py` (after "
                        "`python decade_run.py`) to build hedge_result.json"}
    try:
        with open(path) as f:
            result = json.load(f)
        result["available"] = True
        return result
    except Exception as e:
        return {"error": f"hedge result read failed ({e})"}


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(os.path.dirname(__file__), "dashboard_live.html")) as f:
        return f.read()
