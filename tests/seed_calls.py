"""Seed deterministic backlog calls files into a temp journal for settle tests.

Usage:  DART_FIXTURE=tests/fixtures/dart_hist.csv python tests/seed_calls.py <outdir> <date> [<date> ...]

Each calls_<date>.json is built by the REAL build_calls on the fixture, so its positions match the
fixture bias — settling any full day scores exactly +$7.00 (HB_A h7 +2, HB_A h20 +2, HB_B h10 +3).
"""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root
import pandas as pd
from dart_journal import build_calls

fix = os.environ["DART_FIXTURE"]
hist = pd.read_csv(fix, index_col=0, parse_dates=True)
outdir = sys.argv[1]
os.makedirs(outdir, exist_ok=True)
for d in sys.argv[2:]:
    calls = build_calls(hist, d, model_version="fixture", generated_by="manual",
                        generated_at=d + "T00:00:00+00:00")
    with open(os.path.join(outdir, f"calls_{d}.json"), "w") as f:
        json.dump(calls, f, indent=1)
    nz = sum(1 for h in calls["positions"].values() for v in h.values() if v != 0)
    print(f"seeded calls_{d}.json ({nz} nonzero positions)")
