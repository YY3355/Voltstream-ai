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

JDIR = os.environ.get("JOURNAL_DIR", "journal")   # tests point this at a temp dir
LEDGER = os.path.join(JDIR, "ledger.csv")
THRESH = 1.0     # $/MWh trailing bias needed to take a position
TRAIL_DAYS = 10
# The signal-logic files. model_version = their git blob SHAs, so it changes iff the
# rule (build_calls) or its data source (fetch_live) changes — not on unrelated commits.
SIGNAL_FILES = ["dart_journal.py", "dart_engine.py"]


# ----------------------- pure, fixture-testable core -----------------------
def build_calls(dart_hist: pd.DataFrame, for_date: str,
                model_version="unknown", generated_by="manual", generated_at=None):
    """dart_hist: hourly DataFrame (index=timestamps, cols=hubs) of realized DART.
    Returns the calls dict for `for_date` from trailing hour-of-day mean bias.

    Regime stamps (constraint 1): every file carries the model_version (git SHA of the
    signal-logic files at generation time), generated_by ("auto" = systematic rule, not
    hand-picked), and generated_at (UTC ISO). Pure: caller supplies the stamps."""
    calls = {}
    for hub in dart_hist.columns:
        bias = dart_hist[hub].groupby(dart_hist.index.hour).mean()
        pos = {}
        for hour in range(24):
            b = float(bias.get(hour, 0.0))
            pos[str(hour)] = 1 if b > THRESH else (-1 if b < -THRESH else 0)
        calls[hub] = pos
    if generated_at is None:
        generated_at = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
    return {"for_date": for_date,
            "created_at": pd.Timestamp.now().isoformat(timespec="seconds"),
            "generated_at": generated_at,      # UTC ISO — when the rule produced this file
            "generated_by": generated_by,      # "auto" (systematic) | "manual"
            "model_version": model_version,    # git blob SHA(s) of the signal-logic files
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
def model_version():
    """Combined short git blob SHA of the signal-logic files. 'unknown' if git is unavailable.
    Impure (shells to git) — kept out of the pure core so build_calls stays fixture-testable."""
    import subprocess
    try:
        out = subprocess.run(["git", "hash-object", *SIGNAL_FILES],
                             capture_output=True, text=True, check=True).stdout.split()
        return "+".join(s[:12] for s in out) if out else "unknown"
    except Exception:
        return "unknown"


def _asof():
    """Injectable 'now' as a normalized date. DART_ASOF (YYYY-MM-DD) for tests; else real now().
    Never backdate in production — this seam exists so the checker can drive a fixed date."""
    v = os.environ.get("DART_ASOF")
    return (pd.Timestamp(v) if v else pd.Timestamp.now()).normalize()


def _dart_history(days):
    # test seam: a CSV of realized hourly DART (index=timestamp, cols=hubs) — no network.
    fx = os.environ.get("DART_FIXTURE")
    if fx:
        return pd.read_csv(fx, index_col=0, parse_dates=True).dropna(how="all")
    from dart_engine import fetch_live
    da, rt = fetch_live(days=days)
    hubs = [h for h in da.columns if h in rt.columns]
    idx = da.index.intersection(rt.index)
    return (da.loc[idx, hubs] - rt.loc[idx, hubs]).dropna(how="all")


def cmd_commit():
    os.makedirs(JDIR, exist_ok=True)
    tomorrow = (_asof() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    path = os.path.join(JDIR, f"calls_{tomorrow}.json")
    if os.path.exists(path):
        print(f"calls for {tomorrow} already committed ({path}) — not overwriting"); return
    hist = _dart_history(TRAIL_DAYS)
    calls = build_calls(hist, tomorrow,
                        model_version=model_version(),
                        generated_by=os.environ.get("GENERATED_BY", "auto"),
                        generated_at=pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"))
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
    today = _asof().strftime("%Y-%m-%d")
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


def _sparkline(vals):
    blocks = "▁▂▃▄▅▆▇█"
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    return "".join(blocks[int((v - lo) / rng * (len(blocks) - 1))] for v in vals)


def _unsettled_backlog():
    """Committed call-days (date < today) with no ledger rows yet — the always-visible backlog."""
    if not os.path.isdir(JDIR):
        return []
    done = set()
    if os.path.exists(LEDGER):
        done = set(pd.read_csv(LEDGER)["date"].astype(str).unique())
    today = _asof().strftime("%Y-%m-%d")
    return sorted(f[6:16] for f in os.listdir(JDIR)
                  if f.startswith("calls_") and f[6:16] < today and f[6:16] not in done)


def cmd_report():
    backlog = _unsettled_backlog()
    if not os.path.exists(LEDGER):
        print("no ledger yet — commit calls today, settle tomorrow")
        if backlog:
            print(f"  ⚠ committed but UNSETTLED ({len(backlog)}): {', '.join(backlog)}   (run: settle)")
        return
    df = pd.read_csv(LEDGER)
    daily = df.groupby("date")["pnl"].sum().sort_index()
    cum = daily.cumsum()
    hit = float((df["position"] * df["dart"] > 0).mean())
    print(f"DART paper book — {df['date'].nunique()} settled days, {len(df)} positions")
    # one book, honestly labeled — same rule throughout, only the trigger changed
    print("  regime: manual execution of the rule through 2026-07-22 · same rule auto-committed")
    print("          from 2026-07-24 (each auto calls file stamped model_version / generated_at UTC).")
    print(f"  cumulative P&L : ${df['pnl'].sum():+.2f}   (1 MW hour clips, no fees/execution)")
    print(f"  hit rate       : {100*hit:.1f}%")
    print(f"  best / worst day: ${daily.max():+.2f} / ${daily.min():+.2f}")
    print(f"  by hub: " + ", ".join(f"{h} ${v:+.1f}" for h, v in df.groupby('hub')['pnl'].sum().items()))
    # equity curve = cumulative P&L over the settled days
    print(f"  equity curve   : {_sparkline(list(cum))}   (${cum.iloc[0]:+.2f} → ${cum.iloc[-1]:+.2f})")
    for d, c in cum.items():
        print(f"      {d}  day ${daily[d]:+7.2f}   cum ${c:+8.2f}")
    print("  NOT real trading: virtual fills at settlement, no execution/fees/risk limits.")
    # backlog is ALWAYS visible at the bottom — committed-but-unsettled days never hide
    if backlog:
        print(f"  ⚠ committed but UNSETTLED ({len(backlog)}): {', '.join(backlog)}   (run: settle)")
    else:
        print("  ✓ all committed past days are settled.")


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
        calls = build_calls(dart[dart.index < "2026-06-29"], "2026-06-29",
                            model_version="testsha123", generated_by="auto",
                            generated_at="2026-06-28T12:00:00+00:00")
        assert calls["positions"]["HB_A"]["7"] == 1, "should sell DA where DA runs rich"
        assert calls["positions"]["HB_B"]["19"] == -1, "should buy DA where DA runs cheap"
        assert calls["positions"]["HB_A"]["14"] == 0, "no bias -> flat"
        # regime stamps (constraint 1) must be embedded
        assert calls["model_version"] == "testsha123", "model_version stamp"
        assert calls["generated_by"] == "auto", "generated_by stamp"
        assert calls["generated_at"] == "2026-06-28T12:00:00+00:00", "generated_at (UTC ISO) stamp"
        rows = score_calls(calls, dart)
        pnl = sum(r["pnl"] for r in rows)
        assert pnl > 0, "aligned-bias fixture should score positive"
        assert all(r["pnl"] == r["position"] * r["dart"] for r in rows), "pnl math"
        print(f"fixture self-test PASSED — {len(rows)} scored positions, fixture P&L ${pnl:+.2f}")
        print("(fixture verifies call-building and scoring; live flow runs on the Mac:")
        print("  python dart_journal.py commit  |  settle  |  report)")
