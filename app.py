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
from datetime import timedelta, datetime, timezone
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
        "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),  # when this solve ran
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
                     "capture_pct": round(100 * settled / perfect["revenue"]) if perfect["revenue"] else 0,
                     # solve provenance surfaced from the actual solution / config (not a new source)
                     "status": sched["status"],
                     "initial_soc_kwh": bat.initial_soc_kwh,
                     "max_power_kw": bat.max_power_kw,
                     "round_trip_efficiency": bat.round_trip_efficiency,
                     "dt_hours": dt,
                     "hub": "HB_HOUSTON",
                     "price_source": "P50 forecast (GBM) of HB_HOUSTON RT settlement, "
                                     f"decided pre-dispatch; settled at realized RT ({str(target)})"},
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
    with an EIA_API_KEY). When that live cache is absent (e.g. on the deployed box) it falls
    back to the committed geo_result.json snapshot so the map ships with real assets. Cities are
    always available (embedded). Honest empty-state — no fabricated coordinates, points without a
    real lat/lon are already dropped upstream."""
    import geo_data, json
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
        if not assets_cached:
            # no live pkl cache (deployed box): serve the committed EIA-860M snapshot if present
            snap = os.path.join(os.path.dirname(__file__), "geo_result.json")
            if os.path.exists(snap):
                with open(snap) as f:
                    payload = json.load(f)
                payload["available"] = True
                payload["assets_cached"] = bool(payload.get("batteries") or payload.get("plants"))
                payload["source"] = "committed EIA-860M snapshot"
                return payload
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


_COUNTYWX_GEO = {"v": None}


@app.get("/api/countyweather")
def api_countyweather():
    """County weather layer: real Texas county polygons, each shaded by its OWN live Open-Meteo
    reading at the county centroid (run_county_weather -> county_weather.build_county_weather).
    TRUE per-county now — one real measurement per county, none left gray. Returns a render-ready
    GeoJSON FeatureCollection (geometry + per-county weather props merged) for all 254 counties,
    plus the wind-belt signal (mean real wind over the wind-belt counties) for the banner."""
    import json
    import county_weather
    import weather_data
    # county polygons (committed build input)
    if _COUNTYWX_GEO["v"] is None:
        path = os.path.join(os.path.dirname(__file__), "data_archive", "geo", "tx_counties.geojson")
        if not os.path.exists(path):
            return {"available": False, "error": "tx_counties.geojson missing", "features": []}
        with open(path) as f:
            _COUNTYWX_GEO["v"] = json.load(f)
    geo = _COUNTYWX_GEO["v"]
    try:
        wx = weather_data.run_county_weather()
        cw = county_weather.build_county_weather(wx)
        by_county = {c["county"]: c for c in cw.get("counties", [])}
        feats = []
        for f in geo.get("features", []):
            name = f["properties"].get("NAME")
            c = by_county.get(name)
            props = {"NAME": name,
                     "temp_f": c["temp_f"] if c else None,
                     "wind_mph": c["wind_mph"] if c else None,
                     "precip_mm": c["precip_mm"] if c else None,
                     "raining": c["raining"] if c else False,
                     "fill": c["fill"] if c else None}          # null fill only if a county reading is missing
            feats.append({"type": "Feature", "geometry": f["geometry"], "properties": props})
        colored = sorted(f["properties"]["NAME"] for f in feats if f["properties"]["fill"] is not None)
        uncolored = sorted(f["properties"]["NAME"] for f in feats if f["properties"]["fill"] is None)
        return {
            "available": True, "type": "FeatureCollection", "features": feats,
            "label": cw.get("label", ""), "wind_signal": cw.get("wind_signal"),
            "coverage": {"total": len(feats), "colored": len(colored), "uncolored": len(uncolored)},
            "uncolored": uncolored,
            "source": wx.get("source"), "note": wx.get("note"),
        }
    except Exception as e:
        return {"available": False, "error": f"county weather failed ({e})", "features": []}


_TXLINES_GEO = {"v": None}


@app.get("/api/txlines")
def api_txlines():
    """Transmission CONTEXT layer: real HIFLD transmission-line geometry (Texas bbox, 69kV+),
    voltage-tiered for the map. GEOMETRY ONLY — this is where the lines are, not their live loading.
    Constraint/congestion status is shown ONLY by the measured ERCOT SCED arcs, never inferred here.
    Source: HIFLD 'Electric Power Transmission Lines' (public ArcGIS FeatureServer). Cached geojson."""
    import json
    if _TXLINES_GEO["v"] is None:
        path = os.path.join(os.path.dirname(__file__), "data_archive", "geo", "tx_lines.geojson")
        if not os.path.exists(path):
            return {"available": False, "error": "tx_lines.geojson missing", "features": []}
        with open(path) as f:
            _TXLINES_GEO["v"] = json.load(f)
    fc = _TXLINES_GEO["v"]
    return {
        "available": True, "type": "FeatureCollection", "features": fc.get("features", []),
        "count": len(fc.get("features", [])),
        "label": ("transmission context (HIFLD geometry) — constraint status shown only by the "
                  "measured SCED arcs."),
        "source": "HIFLD Electric Power Transmission Lines (public), Texas bbox, 69kV+",
    }


@app.get("/api/weather")
def api_weather():
    """Weather layer for the Map tab: live conditions + 48h forecast at each of ERCOT's eight
    weather-zone centroids, plus the wind-belt signal (the weather->net-load mechanism).

    LIVE via Open-Meteo (free, no API key); weather_data.run_weather() self-caches for 30 min.
    Zone points are REGIONAL centroids (a sample, not a weather field), and nothing here is a
    price forecast. Honest error passthrough if the pull fails and no cache exists."""
    import weather_data
    try:
        return weather_data.run_weather()
    except Exception as e:
        return {"error": f"weather engine failed ({e})", "zones": []}


@app.get("/api/countyheat")
def api_countyheat():
    """Battery MW by county — a rollup of real EIA assets, NOT an interpolated surface.

    load_geo() batteries -> map_layers.county_heat(). County points are the mean position of
    that county's assets (a marker, not a boundary). Honest empty-state if geography isn't
    cached. We deliberately do not paint a price heatmap: 4 hub prices can't honestly color a
    statewide surface."""
    import geo_data, map_layers, json
    import pandas as pd
    try:
        batteries, _plants, _cities = geo_data.load_geo()
        if batteries is None or batteries.empty:
            # deployed box has no live pkl cache — rebuild batteries from the committed
            # geo_result.json snapshot (same source /api/geo falls back to)
            snap = os.path.join(os.path.dirname(__file__), "geo_result.json")
            if os.path.exists(snap):
                with open(snap) as f:
                    batteries = pd.DataFrame(json.load(f).get("batteries", []))
        return map_layers.county_heat(batteries)
    except Exception as e:
        return {"error": f"county heat failed ({e})", "counties": []}


_FORECAST_CACHE = {}   # hub -> (monotonic_ts, result); GBM fit is seconds, cache ~30 min
_VOL_CACHE = {}        # (hub,bucket) -> (monotonic_ts, result); realized-vol read of the archive
_CURVE_CACHE = {}      # data_dir -> (monotonic_ts, curve_result, version)


def _forward_curve():
    """Cached forward-curve build + a content-hash version string (pass-through provenance)."""
    import time, json, hashlib
    from forward_curve import build_forward_curve
    dd = os.environ.get("ERCOT_DATA_DIR", "data")
    hit = _CURVE_CACHE.get(dd)
    if hit and time.monotonic() - hit[0] < 1800:
        return hit[1], hit[2]
    r = build_forward_curve(dd)
    payload = json.dumps({"months": r["months"], "blocks": r["blocks"],
                          "level_source": r["level_source"]}, sort_keys=True, default=str)
    version = "fc-" + hashlib.sha1(payload.encode()).hexdigest()[:10]
    _CURVE_CACHE[dd] = (time.monotonic(), r, version)
    return r, version


@app.get("/api/forecast")
def api_forecast(hub: str = "HB_HOUSTON"):
    """Honest next-24h day-ahead P10/P50/P90 for one hub.

    price_store.get_prices_rolling(hub, days=30) -> map_layers.forecast_hub(). A DAY-AHEAD model
    (features known 24h out only), deliberately separate from the platform's nowcaster and weaker
    by design. forecast_hub RAISES on thin history — surfaced here as an honest error, never a
    fabricated forecast (the deployed box may have a thin store)."""
    import time, price_store, map_layers
    hub = (hub or "HB_HOUSTON").upper()
    hit = _FORECAST_CACHE.get(hub)
    if hit and time.monotonic() - hit[0] < 1800:
        return hit[1]
    try:
        s, _meta = price_store.get_prices_rolling(hub, days=30, include_today=False,
                                                  fetch_missing=False)
        out = map_layers.forecast_hub(s)
        out["hub"] = hub
        _FORECAST_CACHE[hub] = (time.monotonic(), out)
        return out
    except Exception as e:
        return {"error": f"day-ahead forecast unavailable for {hub}: {e}", "hub": hub}


@app.get("/api/vol")
def api_vol(hub: str = "HB_HOUSTON", bucket: str = "peak"):
    """REALIZED volatility from VoltStream's own price archive — NOT implied vol.

    No power-option quotes are available to us, so there is no market vol surface here; this is an
    input estimate measured from archived ERCOT settlements, not a market price of risk. For the given
    hub and bucket (peak = HE 07-22 / offpeak = rest, ALL days — declared in the payload) it returns
    realized_vol at 20/60/250d + a vol cone, for BOTH DA and RT daily bucket-average series. Depth is
    whatever the archive holds — n_obs and excluded-day counts are reported, never hidden or fabricated.
    """
    import time, json, logging, desk_data, vol_engine
    from datetime import datetime, timezone
    hub = (hub or "HB_HOUSTON").upper()
    bucket = (bucket or "peak").lower()
    key = (hub, bucket)
    hit = _VOL_CACHE.get(key)
    if hit and time.monotonic() - hit[0] < 1800:
        return hit[1]
    log = logging.getLogger("uvicorn.error")
    # prefer the committed DEEP snapshot (built offline from the merged decade archive, which the
    # deployed /data volume can't reach); fall back to a live read of the thin rolling store.
    snap = None
    try:
        snap = json.load(open(os.path.join(os.path.dirname(__file__), "vol_result.json"))).get("hubs", {}).get(hub, {}).get("markets", {})
    except Exception:
        snap = None
    try:
        markets = {}
        for market in ("da", "rt"):
            sb = (snap or {}).get(market, {}).get(bucket) if snap else None
            if sb and "windows" in sb:
                markets[market] = {**sb, "source": "committed deep snapshot (vol_result.json, "
                                   "merged decade archive)"}
                continue
            daily, meta = desk_data.daily_bucket(hub, market, bucket)   # live fallback
            if len(daily) < 3:
                markets[market] = {**meta, "error": f"archive too thin ({len(daily)} days)"}
                continue
            windows = [vol_engine.realized_vol(daily, window_days=w,
                                               label=f"{hub} {market} {bucket}").to_dict()
                       for w in (20, 60, 250)]
            cone = vol_engine.vol_cone(daily, windows=(20, 60, 120, 250, 500), label=f"{hub} {market} {bucket}")
            full = vol_engine.realized_vol(daily, label=f"{hub} {market} {bucket}")
            log.info(f"/api/vol {hub} {market} {bucket} (live): n_days={meta['n_days']} "
                     f"normal_vol=${full.normal_vol:,.1f}/sqrt-yr excluded_nonpos={full.n_excluded_nonpos}")
            markets[market] = {**meta, "n_days": meta["n_days"], "windows": windows, "cone": cone,
                               "n_excluded_nonpos": full.n_excluded_nonpos,
                               "source": "live rolling store (thin)"}
        return_val = {
            "hub": hub, "bucket": bucket, "bucket_definition": desk_data.BUCKET_DEF,
            "label": ("realized, not implied — no option quotes available. Measured from archived "
                      "ERCOT settlements; an input estimate, not a market price of risk."),
            "convention": "normal_vol = $/MWh per sqrt-yr (Bachelier); log_vol excludes non-positive days",
            "source": "committed deep snapshot" if snap else "live rolling store",
            "markets": markets,
            "asof": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        _VOL_CACHE[key] = (time.monotonic(), return_val)
        return return_val
    except Exception as e:
        return {"error": f"vol unavailable for {hub}/{bucket}: {e}", "hub": hub, "bucket": bucket}


@app.get("/api/option")
def api_option(hub: str = "HB_HOUSTON", month: str = "", strike: float = None,
               type: str = "call", policy: str = "black76", bucket: str = "peak",
               window: int = 60, market: str = "rt"):
    """Governed vanilla pricer — a MODEL VALUE under realized vol, NOT a market quote.

    F is the monthly block from the existing bootstrapped forward curve (its version string is passed
    through). vol is realized vol from the archive (task-2 path; caller picks the window, echoed in
    vol_source). model policy is DECLARED: black76 (lognormal) or bachelier (normal). If a forward is
    <= 0 (or strike <= 0), black76 RETURNS ITS REFUSAL VERBATIM and flags offer_bachelier — prices are
    never silently shifted. Defaults: front month, ATM strike, peak bucket, RT vol, 60d window.
    """
    import desk_data, vol_engine, options_engine
    from datetime import datetime, timezone
    import pandas as pd
    hub = (hub or "HB_HOUSTON").upper()
    type = (type or "call").lower(); policy = (policy or "black76").lower()
    bucket = (bucket or "peak").lower(); market = (market or "rt").lower()
    label = "model value under realized vol — not a market quote."
    try:
        curve, version = _forward_curve()
        months = curve["months"]
        month = month or months[0]
        if month not in curve["blocks"]:
            return {"error": f"month {month} not in curve (available: {months})",
                    "hub": hub, "months": months, "label": label}
        F = float(curve["blocks"][month][bucket])
        K = float(strike) if strike is not None else F        # default ATM
        T = max((pd.Period(month, freq="M").start_time - pd.Timestamp.now()).days, 1) / 365.0

        daily, vmeta = desk_data.daily_bucket(hub, market, bucket)
        vr = vol_engine.realized_vol(daily, window_days=window, label=f"{hub} {market} {bucket}")
        vol_source = (f"realized {market} {bucket} vol, {window}d window ({hub}); "
                      f"n_obs={vr.n_obs}; {vr.convention_note}")
        provenance = {"model_policy": policy, "curve_version": version,
                      "curve_level_source": curve["level_source"], "vol_source": vol_source,
                      "vol_window_days": window, "vol_market": market, "vol_n_obs": vr.n_obs,
                      "F": F, "K": K, "T_years": round(T, 4), "hub": hub, "month": month,
                      "bucket": bucket, "asof": datetime.now(timezone.utc).isoformat(timespec="seconds")}

        if policy == "black76":
            if vr.log_vol is None:
                return {"error": "log_vol unavailable (too few positive days) — use policy=bachelier",
                        "offer_bachelier": True, **provenance, "label": label}
            try:
                res = options_engine.black76(type, F, K, T, vr.log_vol, vol_source=vol_source)
            except ValueError as e:                            # F<=0 or K<=0 -> refuse VERBATIM
                return {"error": str(e), "refused_by": "black76", "offer_bachelier": True,
                        **provenance, "label": label}
        elif policy == "bachelier":
            res = options_engine.bachelier(type, F, K, T, vr.normal_vol, vol_source=vol_source)
        else:
            return {"error": f"policy must be black76|bachelier, got {policy!r}", **provenance,
                    "label": label}

        out = res.to_dict()
        out.update({**provenance, "label": label})
        return out
    except Exception as e:
        return {"error": f"option pricing failed: {e}", "hub": hub, "month": month, "label": label}


def _desk_da_prices(hub, day):
    """{hour: DA price} for hub+day from the DA cache; {} if that day's DAM isn't published/cached."""
    import glob
    import pandas as pd
    p = os.path.join(os.environ.get("PRICE_CACHE_DIR", "dart_cache"), f"DAY_AHEAD_HOURLY_{day}.pkl")
    if not os.path.exists(p):
        return {}
    try:
        df = pd.read_pickle(p)
    except Exception:
        return {}
    d = df[df["Location"].astype(str).str.upper() == hub.upper()]
    out = {}
    for _, r in d.iterrows():
        out[int(pd.to_datetime(r["Interval Start"]).hour)] = round(float(r["SPP"]), 2)
    return out


def _desk_your_call(hub, day):
    """{hour: 'long'|'short'} from the dart_journal calls file — READ ONLY (never writes journal/)."""
    import json
    p = os.path.join("journal", f"calls_{day}.json")
    if not os.path.exists(p):
        return {}
    try:
        pos = json.load(open(p)).get("positions", {}).get(hub, {})
    except Exception:
        return {}
    return {int(h): ("long" if v > 0 else "short") for h, v in pos.items() if v != 0}


@app.get("/api/desk")
def api_desk(hub: str = "HB_HOUSTON"):
    """Per-hour desk table for today + tomorrow: real DA (from cache, '—' until DAM publishes),
    the CLIMATOLOGY baseline (Clim P(RT>DA) + DART q05/q50/q95 + n — '—' where n<30, never a flimsy
    number), your committed dart_journal call, and three RESERVED '—' columns (model_p/load/wind) held
    for the future eval-harnessed forecast model / ERCOT forecast products. NOT a forecast: the word
    'Model' never labels a probability here. Reads the committed clim snapshot + caches; never writes."""
    import json
    from datetime import datetime, timezone
    import pandas as pd
    from desk_climatology import desk_rows
    hub = (hub or "HB_HOUSTON").upper()
    try:
        clim_all = json.load(open(os.path.join(os.path.dirname(__file__), "clim_result.json")))
    except Exception as e:
        return {"error": f"climatology snapshot unavailable ({e}); run build_clim.py", "hub": hub}
    clim = clim_all.get("hubs", {}).get(hub)
    if not clim:
        return {"error": f"no climatology for {hub}", "hub": hub}
    today = pd.Timestamp.now().normalize()
    days = []
    for d in (today, today + pd.Timedelta(days=1)):
        dstr = d.strftime("%Y-%m-%d")
        da = _desk_da_prices(hub, dstr)
        rows = desk_rows(clim, month=int(d.month), da_prices=da, journal_calls=_desk_your_call(hub, dstr))
        days.append({"date": dstr, "da_published": bool(da), "rows": rows})
    return {
        "hub": hub,
        "days": days,
        "climatology": {"kind": clim["kind"], "date_range": clim["date_range"],
                        "n_hours_total": clim["n_hours_total"], "min_samples_rule": clim["min_samples_rule"]},
        "coverage_note": clim_all.get("coverage_note", ""),
        "reserved_note": ("model_p / load_fcst / wind_fcst are reserved for the eval-harnessed forecast "
                          "model / ERCOT forecast products — roadmap, not built."),
        "columns_note": "Clim P(RT>DA) is a measured climatology, NOT a model. DA is real or '—' until DAM.",
        "asof": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


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


@app.get("/api/locational")
def api_locational():
    """Phase 3 — locational decade revenue: what a 1 MW / 2h battery would have earned per YEAR
    at each ERCOT trading hub, 2018–2025, on real history (perfect-foresight energy arbitrage).
    Powers the Map tab's year-playback slider. Served from a pre-computed cache
    (locational_result.json, minutes of bundle compute); honest note if not built yet.

    HUB-LEVEL (regional), a revenue ceiling, energy-only, nominal $, history not forecast —
    the labels{} block carries these verbatim to the UI."""
    import json
    path = os.environ.get("LOCATIONAL_RESULT",
                          os.path.join(os.path.dirname(__file__), "locational_result.json"))
    if not os.path.exists(path):
        return {"available": False,
                "note": "locational study not computed yet — run `python locational_run.py` to "
                        "build locational_result.json from the ERCOT SPP bundles"}
    try:
        with open(path) as f:
            result = json.load(f)
        result["available"] = True
        return result
    except Exception as e:
        return {"error": f"locational result read failed ({e})"}


_ARCS_LIVE_CACHE = {"t": 0, "v": None}
_ALERTS_CACHE = {"t": 0, "v": None}


def _live_constraint_arcs():
    """Live SCED snapshot placed against the committed resolved-station table -> build_arcs
    output ({arcs, unplaced, ...} with shadow_price). Shared by /api/alerts and constraintarcs
    live-now. Returns None on failure (callers degrade honestly)."""
    import json
    import pandas as pd
    import ercot_archiver
    import constraint_arcs
    path = os.environ.get("CONSTRAINTARCS_RESULT",
                          os.path.join(os.path.dirname(__file__), "constraintarcs_result.json"))
    with open(path) as f:
        resolved = json.load(f).get("resolved_stations", {})
    reg = pd.DataFrame([{"name": k, "lat": v[0], "lon": v[1]} for k, v in resolved.items()])
    cons = constraint_arcs.parse_constraints(ercot_archiver.fetch_constraints_query(days=2))
    return constraint_arcs.build_arcs(cons, reg)


@app.get("/api/alerts")
def api_alerts():
    """Live threshold alerts over the data VoltStream already pulls — wind-belt state, hub DART,
    hub basis, and binding-constraint shadow prices. Each fired alert cites the real value, the
    threshold it crossed, and the market rationale (verbatim from alert_engine). Describes
    CONDITIONS on real ERCOT data, not price forecasts. 60s cache (the UI polls at that rate)."""
    import time
    import alert_engine
    if time.time() - _ALERTS_CACHE["t"] < 60 and _ALERTS_CACHE["v"] is not None:
        return _ALERTS_CACHE["v"]
    dart = weather = cons = None
    try:
        from dart_engine import run_dart
        dart = run_dart()
    except Exception:
        dart = None
    try:
        import weather_data
        weather = weather_data.run_weather()
    except Exception:
        weather = None
    try:
        cons = _live_constraint_arcs()
    except Exception:
        cons = None
    res = alert_engine.run_alerts(dart, weather, cons)
    res["available"] = True
    res["sources"] = {"dart": bool(dart and "stats" in dart),
                      "weather": bool(weather and weather.get("signal")),
                      "constraints": bool(cons)}
    _ALERTS_CACHE.update(t=time.time(), v=res)
    return res


@app.get("/api/intraday")
def api_intraday():
    """Intraday replay: one recent day of real NP6-86-CD SCED snapshots as placeable
    constraint-arc frames (~every 5 min). Powers the Map tab's time scrubber — which lines were
    binding through the day. Served from the committed intraday_result.json; snapshots with no
    placeable binding constraint are honestly empty."""
    import json
    path = os.environ.get("INTRADAY_RESULT",
                          os.path.join(os.path.dirname(__file__), "intraday_result.json"))
    if not os.path.exists(path):
        return {"available": False, "note": "intraday replay not computed — run "
                "`python intraday_run.py`"}
    with open(path) as f:
        res = json.load(f)
    res["available"] = True
    return res


@app.get("/api/constraintarcs")
def api_constraintarcs(mode: str = "aggregate"):
    """Measured ERCOT transmission-constraint flow arcs (NP6-86-CD SCED shadow prices).

    mode=aggregate (default): 90-day BINDING-FREQUENCY arcs from the committed summary — width =
    how often the line bound, color = mean shadow price. Always populated (the congested
    corridors). mode=live: places the CURRENT SCED snapshot and is honestly empty when nothing
    placeable is binding. Only constraints whose BOTH endpoints resolve to a real substation are
    drawn (station match ~39%); the unresolved list ships as the roadmap. Measured facts, not a
    model; no guessed coordinates."""
    import json, time
    path = os.environ.get("CONSTRAINTARCS_RESULT",
                          os.path.join(os.path.dirname(__file__), "constraintarcs_result.json"))
    if not os.path.exists(path):
        return {"available": False, "note": "constraint arcs not computed — run "
                "`python constraintarcs_run.py` to build constraintarcs_result.json"}
    with open(path) as f:
        agg = json.load(f)
    agg["available"] = True
    if mode != "live":
        return agg

    # live-now: place the current SCED snapshot using the committed resolved-station table
    # (no need to ship the full registry). Honest empty when nothing placeable is binding.
    if time.time() - _ARCS_LIVE_CACHE["t"] < 300 and _ARCS_LIVE_CACHE["v"] is not None:
        return _ARCS_LIVE_CACHE["v"]
    try:
        import pandas as pd, ercot_archiver, constraint_arcs
        reg = pd.DataFrame([{"name": k, "lat": v[0], "lon": v[1]}
                            for k, v in agg.get("resolved_stations", {}).items()])
        cons = constraint_arcs.parse_constraints(ercot_archiver.fetch_constraints_query(days=2))
        built = constraint_arcs.build_arcs(cons, reg)
        live = {"available": True, "mode": "live", "arcs": built.get("arcs", []),
                "n_constraints": built.get("n_constraints", 0), "n_placed": built.get("n_placed", 0),
                "timestamp": built.get("timestamp"), "labels": agg.get("labels", {}),
                "note": ("Live SCED snapshot. Empty is honest — often only 1-2 constraints bind, "
                         "and only placeable ones are drawn. The 90-day aggregate is the fuller view.")}
        _ARCS_LIVE_CACHE.update(t=time.time(), v=live)
        return live
    except Exception as e:
        return {"available": True, "mode": "live", "arcs": [], "error": f"live constraint pull failed ({e})"}


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
