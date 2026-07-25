"""Generate tests/fixtures/dart_hist.csv — a DETERMINISTIC realized-DART history for tests.

No RNG: the P&L is hand-checkable. Pattern (per day, every day in range):
  HB_A: DART = +2.0 at hour 7, -2.0 at hour 20, 0.0 elsewhere
  HB_B: DART = +3.0 at hour 10, 0.0 elsewhere

=> trailing hour-of-day bias gives positions: HB_A h7=+1, HB_A h20=-1, HB_B h10=+1 (all |bias|=2 or 3 > $1).
=> settling any full day scores exactly 3 nonzero positions:
     HB_A h7 : +1 * (+2) = +2
     HB_A h20: -1 * (-2) = +2
     HB_B h10: +1 * (+3) = +3
   day P&L = +7.00 exactly.
"""
import os
import pandas as pd

OUT = os.path.join(os.path.dirname(__file__), "fixtures", "dart_hist.csv")


def make():
    idx = pd.date_range("2026-07-12", "2026-07-24 23:00", freq="1h")
    df = pd.DataFrame(index=idx)
    df["HB_A"] = 0.0
    df.loc[df.index.hour == 7, "HB_A"] = 2.0
    df.loc[df.index.hour == 20, "HB_A"] = -2.0
    df["HB_B"] = 0.0
    df.loc[df.index.hour == 10, "HB_B"] = 3.0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df.to_csv(OUT)
    return df


if __name__ == "__main__":
    df = make()
    print(f"wrote {OUT}: {len(df)} hourly rows, hubs {list(df.columns)}, "
          f"{df.index[0]} .. {df.index[-1]}")
