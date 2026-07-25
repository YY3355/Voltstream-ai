"""options_engine.py — governed option valuation for VoltStream Quant tab.

Design follows the "governed record" discipline:
- model policy is DECLARED on every result (black76 | bachelier), never implicit
- Greeks come from the SAME analytic run as the value (no second engine)
- every result is stamped with all inputs + vol provenance passed in by caller
- Black-76 requires F>0 and K>0; the engine REFUSES rather than guessing,
  and Bachelier is the declared alternative for near/below-zero regimes.

HONEST SCOPE: values here are model outputs under realized vol — an estimate
of option value, not a market quote. There is no traded ERCOT vanilla we can
calibrate to, and we say so on the record.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

SQRT2PI = math.sqrt(2.0 * math.pi)

def _phi(x):  # standard normal pdf
    return math.exp(-0.5 * x * x) / SQRT2PI

def _Phi(x):  # standard normal cdf
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


@dataclass
class OptionResult:
    model_policy: str          # "black76" or "bachelier"
    opt_type: str              # "call" or "put"
    F: float                   # forward ($/MWh)
    K: float                   # strike
    T: float                   # years to expiry
    r: float                   # discount rate
    vol: float                 # log vol (black76) or $/MWh normal vol (bachelier)
    value: float
    delta: float
    gamma: float
    vega: float                # per 1.00 of vol (caller may scale to /1%)
    theta: float               # per year (caller may scale to /day)
    vol_source: str            # provenance string from vol_engine result
    asof: str

    def to_dict(self):
        return asdict(self)


def black76(opt_type: str, F: float, K: float, T: float, vol: float,
            r: float = 0.0, vol_source: str = "unspecified") -> OptionResult:
    if F <= 0 or K <= 0:
        raise ValueError("black76 requires F>0 and K>0; use bachelier() for "
                         "near-zero/negative regimes — do not shift prices silently")
    if T <= 0 or vol <= 0:
        raise ValueError("T and vol must be positive")
    df = math.exp(-r * T)
    sd = vol * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sd * sd) / sd
    d2 = d1 - sd
    if opt_type == "call":
        value = df * (F * _Phi(d1) - K * _Phi(d2))
        delta = df * _Phi(d1)
    elif opt_type == "put":
        value = df * (K * _Phi(-d2) - F * _Phi(-d1))
        delta = -df * _Phi(-d1)
    else:
        raise ValueError("opt_type must be call|put")
    gamma = df * _phi(d1) / (F * sd)
    vega = df * F * _phi(d1) * math.sqrt(T)
    # theta via total derivative wrt T (holding F, r): standard Black-76 theta
    theta = -df * F * _phi(d1) * vol / (2 * math.sqrt(T)) + r * value
    return OptionResult("black76", opt_type, F, K, T, r, vol, value, delta,
                        gamma, vega, theta, vol_source,
                        datetime.now(timezone.utc).isoformat(timespec="seconds"))


def bachelier(opt_type: str, F: float, K: float, T: float, vol: float,
              r: float = 0.0, vol_source: str = "unspecified") -> OptionResult:
    """Normal-model pricer; vol in $/MWh per sqrt(yr). Valid for any F, K sign."""
    if T <= 0 or vol <= 0:
        raise ValueError("T and vol must be positive")
    df = math.exp(-r * T)
    sd = vol * math.sqrt(T)
    d = (F - K) / sd
    sign = 1.0 if opt_type == "call" else -1.0
    if opt_type not in ("call", "put"):
        raise ValueError("opt_type must be call|put")
    value = df * (sign * (F - K) * _Phi(sign * d) + sd * _phi(d))
    delta = df * sign * _Phi(sign * d)
    gamma = df * _phi(d) / sd
    vega = df * _phi(d) * math.sqrt(T)
    theta = -df * vol * _phi(d) / (2 * math.sqrt(T)) + r * value
    return OptionResult("bachelier", opt_type, F, K, T, r, vol, value, delta,
                        gamma, vega, theta, vol_source,
                        datetime.now(timezone.utc).isoformat(timespec="seconds"))
