"""
sign_gate.py — Kardashev-eval Task 2: the SIGN + ALIGNMENT gate (constraint 2).

Their target is "RT-DA spread"; ours is dart = DA - RT. A sign flip silently inverts every downstream
result, so we PROVE the mapping empirically before any scoring: reconstruct known delivery hours from OUR
raw prices and match against their published `da` and `spread`.

OUR prices (independent of their API):
  DA  <- dart_cache/DAY_AHEAD_HOURLY_<day>.pkl   (gridstatus DAM SPP; Interval Start tz-aware CDT, hour-beginning)
  RT  <- data_archive/archive_cache/NP6-905-CD_<day>.pkl (ERCOT RT SPP; DeliveryHour 1..24 HOUR-ENDING, 4x15min)
(The deep locational/ + dam_decade/ stores end ~2026-07-01, before the forecast window, so the window
rides our gridstatus-fed caches — still ours, never their API.)

Alignment (pinned empirically below): their `ts` is a UTC hour-START. CDT = UTC-5 all summer (no DST in
window). our DA Interval Start (CDT) -> UTC == their ts. our RT hour-ending HE=h covers CDT [h-1, h);
its UTC hour-start = (h-1) CDT + 5h. Reconstructed dart = DA - hourly_mean(RT).

PROOF CRITERIA: our_da == their_da (alignment) AND our_dart == -(their_spread) (sign), to the cent.
"""
import json
import os
import sys
import pandas as pd

HUB = "HB_HOUSTON"
DAYS = ["2026-07-15", "2026-07-20", "2026-07-26"]
SNAP = os.path.join(os.path.dirname(__file__), "snapshot_2026-08-02", f"history_{HUB}.json")


def our_da_utc(day):
    """UTC hour-start -> our DA SPP for HUB (from gridstatus DAM cache)."""
    da = pd.read_pickle(f"dart_cache/DAY_AHEAD_HOURLY_{day}.pkl")
    da = da[da["Location"].astype(str).str.upper() == HUB]
    return {pd.Timestamp(t).tz_convert("UTC"): float(s) for t, s in zip(da["Interval Start"], da["SPP"])}


def our_rt_utc(day):
    """UTC hour-start -> our RT hourly mean for HUB (ERCOT NP6-905, 4x15min per hour-ending)."""
    rt = pd.read_pickle(f"data_archive/archive_cache/NP6-905-CD_{day}.pkl")
    rt = rt[rt["SettlementPointName"].astype(str).str.upper() == HUB].copy()
    rt["SettlementPointPrice"] = pd.to_numeric(rt["SettlementPointPrice"], errors="coerce")
    hourly = rt.groupby("DeliveryHour")["SettlementPointPrice"].mean()
    out = {}
    for he, v in hourly.items():
        cdt_start = pd.Timestamp(f"{day} {int(he) - 1:02d}:00:00")     # HE h -> CDT hour-start h-1
        out[(cdt_start + pd.Timedelta(hours=5)).tz_localize("UTC")] = float(v)  # CDT->UTC (+5)
    return out


def main():
    their_all = json.load(open(SNAP))
    rows, max_da_err, max_sign_err, n = [], 0.0, 0.0, 0
    for day in DAYS:
        da_u, rt_u = our_da_utc(day), our_rt_utc(day)
        seen = set()
        for r in their_all:
            if r["ts"][:10] != day or r["model"] != "tft-v2-2026q3" or r["ts"] in seen:
                continue
            seen.add(r["ts"])
            k = pd.Timestamp(r["ts"]).tz_convert("UTC")
            if k not in da_u or k not in rt_u:
                continue
            our_da, our_rt = da_u[k], rt_u[k]
            our_dart = our_da - our_rt            # OUR dart = DA - RT
            da_err = abs(our_da - r["da"])
            sign_err = abs(our_dart - (-r["spread"]))   # expect our_dart == -(their spread)
            max_da_err, max_sign_err = max(max_da_err, da_err), max(max_sign_err, sign_err)
            n += 1
            rows.append((r["ts"], r["da"], our_da, r["spread"], our_dart, -r["spread"], da_err, sign_err))

    print(f"SIGN + ALIGNMENT GATE — {HUB}, days {DAYS}, model tft-v2-2026q3\n")
    print(f"{'ts (UTC hour-start)':22} {'their_da':>8} {'our_DA':>7} {'their_spr':>9} "
          f"{'our_dart':>8} {'-their_spr':>10} {'da_err':>6} {'sign_err':>8}")
    for ts, tda, oda, tsp, odart, negspr, dae, se in rows:
        print(f"{ts:22} {tda:8.2f} {oda:7.2f} {tsp:9.3f} {odart:8.3f} {negspr:10.3f} {dae:6.3f} {se:8.3f}")
    print(f"\nn hours matched: {n}")
    print(f"max |our_DA - their_da|      = {max_da_err:.4f}  (alignment: tz + hour convention)")
    print(f"max |our_dart - (-their_spr)|= {max_sign_err:.4f}  (sign: their spread = RT-DA = -dart)")
    ok = n >= 3 and max_da_err < 0.01 and max_sign_err < 0.01
    print(f"\nMAPPING PROVEN: {ok}  ->  dart = DA - RT = -(their 'spread'); "
          f"their [P10,P90] on spread -> dart in [-P90,-P10]")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
