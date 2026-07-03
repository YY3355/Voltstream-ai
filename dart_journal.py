"""
dart_journal.py  —  an auditable DART paper-trading journal.

The point: a real P&L track record needs a desk, but a DISCIPLINED VIRTUAL one only needs
honesty about timing. The rules that make this journal worth showing anyone:

  1. Calls are committed BEFORE settlement. `commit` writes tomorrow's positions to a
     dated JSON with a creation timestamp; git-commit it the same day. No hindsight.
  2. Settlement is mechanical. `settle` scores past calls against realized DA-RT prices
     pulled live; results append to an immutable ledger CSV.
  3. Everything is on disk and in git. The git history IS the audit trail.

Strategy (deliberately simple and stated in advance): trailing hour-of-day DART bias.
For each hub and hour, look at the trailing mean of DART (= DA - RT). If DA has been
persistently rich for that hour (mean > +$1/MWh), SELL DA / BUY RT (+1); persistently
cheap (< -$1), the reverse (-1); otherwise flat. 1 MW per position. P&L per hour =
position x realized DART x 1 MW.

This is NOT real trading: no execution, fees, credit, or risk limits, and virtual fills
at settlement prices. It is a discipline record — evidence of process, not profit claims.
"""
import json
import os
import sys
import numpy as np
import pandas as pd

JDIR = "journal"
LEDGER = os.path.join(JDIR, "ledger.csv")
THRESH = 1.0     # $/MWh trailing bias needed to take a position
TRAIL_DAYS = 10


# ----------------------- pure, fixture-testable core -----------------------
def build_calls(dart_hist: pd.DataFrame, for_date: str):
    """dart_hist: hourly DataFrame (index=timestamps, cols=hubs) of realized DART.
    Returns the calls dict for `for_date` from trailing hour-of-day mean bias."""
    calls = {}
    for hub in dart_hist.columns:
        bias = dart_hist[hub].groupby(dart_hist.index.hour).mean()
        pos = {}
        for hour in range(24):
            b = float(bias.get(hour, 0.0))
            pos[str(hour)] = 1 if b > THRESH else (-1 if b < -THRESH else 0)
        calls[hub] = pos
    return {"for_date": for_date,
            "created_at": pd.Timestamp.now().isoformat(timespec="seconds"),
            "strategy": f"trailing {TRAIL_DAYS}d hour-of-day DART bias, threshold ${THRESH}/MWh, 1 MW",
            "positions": calls}


def score_calls(calls: dict, realized_dart: pd.DataFrame):
    """Score one day's calls against realized hourly DART. Pure function.
    P&L per hub-hour = position * DART ($/MWh) * 1 MW * 1 h."""
    day = calls["for_date"]
    rows = []
    for hub, pos in calls["positions"].items():
        if hub not in realized_dart.columns:
            continue
        d = realized_dart[realized_dart.index.strftime("%Y-%m-%d") == day][hub]
        for ts, dart in d.items():
            p = int(pos.get(str(ts.hour), 0))
            if p != 0 and not np.isnan(dart):
                rows.append({"date": day, "hub": hub, "hour": ts.hour,
                             "position": p, "dart": round(float(dart), 2),
                             "pnl": round(p * float(dart), 2)})
    return rows


# ----------------------- live plumbing (Mac) -----------------------
def _dart_history(days):
    from dart_engine import fetch_live
    da, rt = fetch_live(days=days)
    hubs = [h for h in da.columns if h in rt.columns]
    idx = da.index.intersection(rt.index)
    return (da.loc[idx, hubs] - rt.loc[idx, hubs]).dropna(how="all")


def cmd_commit():
    os.makedirs(JDIR, exist_ok=True)
    tomorrow = (pd.Timestamp.now().normalize() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    path = os.path.join(JDIR, f"calls_{tomorrow}.json")
    if os.path.exists(path):
        print(f"calls for {tomorrow} already committed ({path}) — not overwriting"); return
    hist = _dart_history(TRAIL_DAYS)
    calls = build_calls(hist, tomorrow)
    with open(path, "w") as f:
        json.dump(calls, f, indent=1)
    n = sum(1 for h in calls["positions"].values() for v in h.values() if v != 0)
    print(f"committed {path}: {n} hub-hour positions for {tomorrow}")
    print("now run:  git add journal && git commit -m 'DART calls " + tomorrow + "'")


def cmd_settle():
    if not os.path.isdir(JDIR):
        print("no journal dir"); return
    done = set()
    if os.path.exists(LEDGER):
        done = set(pd.read_csv(LEDGER)["date"].astype(str).unique())
    today = pd.Timestamp.now().normalize().strftime("%Y-%m-%d")
    pending = [f for f in sorted(os.listdir(JDIR)) if f.startswith("calls_")
               and f[6:16] < today and f[6:16] not in done]
    if not pending:
        print("nothing to settle"); return
    hist = _dart_history(TRAIL_DAYS + 2)
    all_rows = []
    for f in pending:
        calls = json.load(open(os.path.join(JDIR, f)))
        rows = score_calls(calls, hist)
        if not rows:
            print(f"{f}: no realized data yet — skipping"); continue
        all_rows += rows
        day_pnl = sum(r["pnl"] for r in rows)
        print(f"settled {calls['for_date']}: {len(rows)} positions, day P&L ${day_pnl:+.2f} (1 MW clips)")
    if all_rows:
        df = pd.DataFrame(all_rows)
        header = not os.path.exists(LEDGER)
        df.to_csv(LEDGER, mode="a", index=False, header=header)
        print(f"appended {len(all_rows)} rows to {LEDGER}")
        print("now run:  git add journal && git commit -m 'DART settlement'")


def cmd_report():
    if not os.path.exists(LEDGER):
        print("no ledger yet — commit calls today, settle tomorrow"); return
    df = pd.read_csv(LEDGER)
    daily = df.groupby("date")["pnl"].sum()
    hit = float((df["position"] * df["dart"] > 0).mean())
    print(f"DART paper book — {df['date'].nunique()} settled days, {len(df)} positions")
    print(f"  cumulative P&L : ${df['pnl'].sum():+.2f}   (1 MW hour clips, no fees/execution)")
    print(f"  hit rate       : {100*hit:.1f}%")
    print(f"  best / worst day: ${daily.max():+.2f} / ${daily.min():+.2f}")
    print(f"  by hub: " + ", ".join(f"{h} ${v:+.1f}" for h, v in df.groupby('hub')['pnl'].sum().items()))
    print("  NOT real trading: virtual fills at settlement, no execution/fees/risk limits.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "commit":
        cmd_commit()
    elif cmd == "settle":
        cmd_settle()
    elif cmd == "report":
        cmd_report()
    else:
        # fixture self-test of the pure core (no network)
        hrs = pd.date_range("2026-06-20", periods=240, freq="1h")
        rng = np.random.default_rng(5)
        # hub A: DA rich +$2 in hours 6-10 only; hub B: DA cheap -$2 in hours 18-21
        dart = pd.DataFrame(index=hrs)
        dart["HB_A"] = rng.normal(0, 0.3, 240) + np.where(np.isin(hrs.hour, range(6, 11)), 2.0, 0.0)
        dart["HB_B"] = rng.normal(0, 0.3, 240) - np.where(np.isin(hrs.hour, range(18, 22)), 2.0, 0.0)
        calls = build_calls(dart[dart.index < "2026-06-29"], "2026-06-29")
        assert calls["positions"]["HB_A"]["7"] == 1, "should sell DA where DA runs rich"
        assert calls["positions"]["HB_B"]["19"] == -1, "should buy DA where DA runs cheap"
        assert calls["positions"]["HB_A"]["14"] == 0, "no bias -> flat"
        rows = score_calls(calls, dart)
        pnl = sum(r["pnl"] for r in rows)
        assert pnl > 0, "aligned-bias fixture should score positive"
        assert all(r["pnl"] == r["position"] * r["dart"] for r in rows), "pnl math"
        print(f"fixture self-test PASSED — {len(rows)} scored positions, fixture P&L ${pnl:+.2f}")
        print("(fixture verifies call-building and scoring; live flow runs on the Mac:")
        print("  python dart_journal.py commit  |  settle  |  report)")
