"""Fixture tests. REMINDER (banked lesson): fixtures prove the math and the
contracts on SYNTHETIC data. They do NOT prove behavior on the real archive —
that's what the verify-loop on the real repo is for."""
import math
import numpy as np
import pandas as pd
from vol_engine import realized_vol, vol_cone, TRADING_DAYS
from options_engine import black76, bachelier

rng = np.random.default_rng(42)
FAILS = []

def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name} {detail}")
    if not cond:
        FAILS.append(name)

# ---------- vol_engine ----------
# 1. GBM series with known annual log vol 0.80 -> estimator should recover it
true_vol = 0.80
n = 4000
dt = 1.0 / TRADING_DAYS
lr = rng.normal(-0.5 * true_vol**2 * dt, true_vol * math.sqrt(dt), n)
prices = 50.0 * np.exp(np.cumsum(lr))
idx = pd.date_range("2015-01-01", periods=n, freq="D")
s = pd.Series(prices, index=idx)
r1 = realized_vol(s, label="synthetic GBM")
check("log_vol recovers 0.80 within 5%", abs(r1.log_vol - true_vol) / true_vol < 0.05,
      f"got {r1.log_vol:.4f}")
check("no excluded days on positive series", r1.n_excluded_nonpos == 0)

# 2. Normal-model series with known $ vol 300 $/MWh/sqrt-yr, incl. negatives
true_nvol = 300.0
diffs = rng.normal(0, true_nvol * math.sqrt(dt), n)
p2 = 25.0 + np.cumsum(diffs)  # wanders negative
s2 = pd.Series(p2, index=idx)
r2 = realized_vol(s2, label="synthetic normal")
check("normal_vol recovers 300 within 5%", abs(r2.normal_vol - true_nvol) / true_nvol < 0.05,
      f"got {r2.normal_vol:.1f}")
check("negative days counted, not hidden", r2.n_excluded_nonpos == int((s2 <= 0).sum()),
      f"excluded={r2.n_excluded_nonpos}")

# 3. Windowed call uses only trailing window
r3 = realized_vol(s, window_days=60)
check("windowed n_obs == 60", r3.n_obs == 60, f"got {r3.n_obs}")

# 4. Vol cone: current value sits within [min, max] by construction
cone = vol_cone(s, windows=(20, 60, 250))
ok = all(w["min"] - 1e-9 <= w["current"] <= w["max"] + 1e-9 for w in cone["windows"])
check("vol cone current within envelope", ok and len(cone["windows"]) == 3)

# ---------- options_engine: Black-76 ----------
F, K, T, vol, r = 50.0, 50.0, 0.25, 0.80, 0.05
c = black76("call", F, K, T, vol, r)
p = black76("put", F, K, T, vol, r)
df = math.exp(-r * T)
parity_gap = abs((c.value - p.value) - df * (F - K))
check("B76 put-call parity", parity_gap < 1e-10, f"gap={parity_gap:.2e}")
# hand-computed reference: d1=0.5*0.8*0.5=0.2, d2=-0.2
d1 = 0.5 * vol * math.sqrt(T)
ref_call = df * F * (math.erfc(-d1/math.sqrt(2))/2 - math.erfc(d1/math.sqrt(2))/2)
check("B76 ATM call matches closed-form ref", abs(c.value - ref_call) < 1e-10,
      f"{c.value:.6f} vs {ref_call:.6f}")
# Greeks vs central finite differences of value
eps = 1e-4
dV = (black76("call", F+eps, K, T, vol, r).value - black76("call", F-eps, K, T, vol, r).value) / (2*eps)
check("B76 delta ~= dV/dF", abs(c.delta - dV) < 1e-6, f"{c.delta:.6f} vs {dV:.6f}")
dG = (black76("call", F+eps, K, T, vol, r).delta - black76("call", F-eps, K, T, vol, r).delta) / (2*eps)
check("B76 gamma ~= dDelta/dF", abs(c.gamma - dG) < 1e-6)
dVe = (black76("call", F, K, T, vol+eps, r).value - black76("call", F, K, T, vol-eps, r).value) / (2*eps)
check("B76 vega ~= dV/dvol", abs(c.vega - dVe) < 1e-5, f"{c.vega:.6f} vs {dVe:.6f}")
dTh = (black76("call", F, K, T+eps, vol, r).value - black76("call", F, K, T-eps, vol, r).value) / (2*eps)
check("B76 theta ~= -dV/dT", abs(c.theta + dTh) < 1e-5, f"{c.theta:.6f} vs {-dTh:.6f}")
# refusal contract
try:
    black76("call", -5.0, K, T, vol); check("B76 refuses F<=0", False)
except ValueError:
    check("B76 refuses F<=0", True)

# ---------- options_engine: Bachelier ----------
cb = bachelier("call", -5.0, -10.0, 0.5, 40.0, 0.03)
pb = bachelier("put", -5.0, -10.0, 0.5, 40.0, 0.03)
dfb = math.exp(-0.03 * 0.5)
gapb = abs((cb.value - pb.value) - dfb * (-5.0 - (-10.0)))
check("Bachelier parity with negative F,K", gapb < 1e-10, f"gap={gapb:.2e}")
dVb = (bachelier("call", -5+eps, -10, 0.5, 40, 0.03).value
       - bachelier("call", -5-eps, -10, 0.5, 40, 0.03).value) / (2*eps)
check("Bachelier delta ~= dV/dF", abs(cb.delta - dVb) < 1e-6)
# deep ITM call -> value ~ df*(F-K)
deep = bachelier("call", 500.0, 0.0, 0.1, 30.0)
check("Bachelier deep ITM ~ intrinsic", abs(deep.value - 500.0) < 0.01,
      f"{deep.value:.4f}")

# ---------- desk_climatology ----------
from desk_climatology import build_climatology, desk_rows
hours = pd.date_range("2023-01-01", "2024-12-31 23:00", freq="h")
da = pd.Series(30.0, index=hours)
# construct known truth: in month 7 hour 17, RT > DA exactly 60% of the time
rt = da.copy()
mask = (hours.month == 7) & (hours.hour == 17)
m_idx = np.where(mask)[0]
rt.iloc[m_idx] = 30.0 - 10.0
k = int(round(0.60 * len(m_idx)))
rt.iloc[m_idx[:k]] = 30.0 + 10.0
other = ~mask
rt[other] = 30.0 - 1.0  # DART negative elsewhere
df_ = pd.DataFrame({"ts": hours, "da": da.values, "rt": rt.values})
clim = build_climatology(df_, label="fixture")
cell = clim["cells"]["7-17"]
check("clim P(RT>DA) == 0.60 in planted cell", abs(cell["p_rt_gt_da"] - 0.60) < 0.01,
      f"got {cell['p_rt_gt_da']:.3f}")
check("clim n counted correctly", cell["n"] == len(m_idx), f"n={cell['n']}")
rows = desk_rows(clim, month=7, da_prices={17: 41.5})
r17 = rows[17]
check("desk row carries real DA and clim, None elsewhere",
      r17["da_price"] == 41.5 and r17["model_p"] is None and r17["load_fcst"] is None
      and abs(r17["clim_p_rt_gt_da"] - 0.60) < 0.01)
check("kind label is climatology_baseline", clim["kind"] == "climatology_baseline")

print()
print("ALL PASS" if not FAILS else f"FAILURES: {FAILS}")
raise SystemExit(0 if not FAILS else 1)
