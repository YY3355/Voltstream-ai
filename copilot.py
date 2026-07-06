"""
copilot.py  —  Trader Co-Pilot (capstone that ties the whole stack together).

Architecture (the honest layering from our design):

  DETERMINISTIC CORE      forecast_engine (price + uncertainty)  +  Bolt (optimal move)
                          -> these compute the numbers. No LLM in the execution path.

  CONFIDENCE LAYER        reads the forecast's OWN P10-P90 spread + notice severity
                          -> decides AUTO-EXECUTE vs ESCALATE-TO-HUMAN.

  AGENTIC RAG LAYER       a router picks which tool(s) to call (forecast / Bolt /
                          retrieve), retrieves grounded ERCOT notices WITH CITATIONS,
                          and explains in plain English. This is the seat the trader
                          talks to. It REPORTS the core's numbers; it never computes them.

Honesty:
  * Retrieval (TF-IDF cosine over the notice store) and tool routing are REAL.
  * The natural-language generation degrades to a grounded template offline; if
    ANTHROPIC_API_KEY is set, _llm_answer() is the drop-in real-LLM path.
  * The router uses transparent keyword rules here; production would use an LLM
    or a small trained classifier. Labeled, not hidden.
"""
import os
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ercot_data import load_prices
from forecast_engine import build_features, fit_predict_gbm, DAY
from battery_dispatch import Battery, optimize_dispatch


# ============================ ERCOT notice store (RAG corpus) ============================
# Realistic ERCOT-style market notices (same style as VoltStream's notice_reader samples).
NOTICES = [
    {"id": "N20260518-001", "date": "2026-05-18", "type": "FORCED_OUTAGE",
     "title": "Forced Outage: Limestone Unit 2 (900 MW coal)",
     "body": "Limestone Unit 2 experienced a forced outage due to a boiler tube leak. "
             "Capacity 900 MW, Load Zone North, expected return 5-7 days. Reduced baseload "
             "in the North zone may raise HB_NORTH prices over the next 24-48 hours."},
    {"id": "N20260518-002", "date": "2026-05-18", "type": "TRANSMISSION_CONSTRAINT",
     "title": "Transmission Constraint: West-Houston 345 kV corridor",
     "body": "Scheduled maintenance reduces West-to-Houston transfer capability by 2,000 MW. "
             "Expect congestion and price separation between HB_WEST and HB_HOUSTON."},
    {"id": "N20260518-003", "date": "2026-05-18", "type": "ANCILLARY_METHODOLOGY",
     "title": "RRS procurement methodology update",
     "body": "ERCOT will increase Responsive Reserve Service (RRS) procurement during "
             "evening ramp hours (HE19-HE21) reflecting higher net-load ramps as solar "
             "rolls off. RRS clearing prices in those hours are expected to rise."},
    {"id": "N20260518-004", "date": "2026-05-18", "type": "WEATHER_ADVISORY",
     "title": "Heat advisory: above-normal temperatures statewide",
     "body": "Forecast highs 5-8 F above normal beginning 05/19. Elevated cooling demand "
             "into the evening peak; tighter reserves possible during HE18-HE21."},
    {"id": "N20260518-005", "date": "2026-05-18", "type": "CONSERVATION",
     "title": "Conservation appeal (voluntary) for evening peak",
     "body": "ERCOT requests voluntary conservation HE19-HE21 due to tight operating "
             "reserves. No emergency conditions declared. Scarcity-priced intervals possible "
             "if reserves fall further."},
]


class NoticeStore:
    """Real TF-IDF retrieval over the notice corpus (the RAG retriever)."""
    def __init__(self, notices):
        self.notices = notices
        self._docs = [f"{n['title']}. {n['body']}" for n in notices]
        self._vec = TfidfVectorizer(stop_words="english")
        self._M = self._vec.fit_transform(self._docs)

    def retrieve(self, query, k=2, min_score=0.05):
        q = self._vec.transform([query])
        sims = cosine_similarity(q, self._M)[0]
        order = np.argsort(sims)[::-1]
        hits = [(self.notices[i], float(sims[i])) for i in order[:k] if sims[i] >= min_score]
        return hits


# ============================ deterministic tools ============================
def tool_forecast():
    """Day-ahead probabilistic forecast for the last full day (held-out)."""
    s = load_prices("data")
    feat = build_features(s).dropna()
    days = sorted({d.date() for d in feat.index})
    full = [d for d in days if (feat.index.date == d).sum() >= DAY]
    target = full[-1]
    test = feat[feat.index.date == target]
    train = feat[feat.index.date < target]
    q = fit_predict_gbm(train, test)
    p50, p10, p90 = q[0.5], q[0.1], q[0.9]
    peak = int(np.argmax(p50))
    rel_band = float(np.mean((p90 - p10) / np.maximum(p50, 1e-6)))
    return {"date": str(target), "hours": test.index,
            "p10": p10, "p50": p50, "p90": p90,
            "peak_interval": peak, "peak_price": float(p50[peak]),
            "peak_time": test.index[peak].strftime("%H:%M"),
            "rel_band": rel_band}


def tool_dispatch(fc, reserve_kwh=10.0):
    """Bolt's recommended move given the P50 forecast."""
    bat = Battery()
    res = optimize_dispatch(fc["p50"], bat, backup_reserve_kwh=reserve_kwh, dt_hours=0.25)
    net = res["discharge_kw"] - res["charge_kw"]
    return {"revenue": res["revenue"],
            "action_now": ("DISCHARGE" if net[0] > 0.1 else "CHARGE" if net[0] < -0.1 else "HOLD"),
            "discharge_kwh": float(res["discharge_kw"].sum() * 0.25),
            "charge_kwh": float(res["charge_kw"].sum() * 0.25)}


# ============================ confidence / escalation ============================
HIGH_IMPACT = {"FORCED_OUTAGE", "TRANSMISSION_CONSTRAINT", "CONSERVATION", "EMERGENCY"}

def confidence_verdict(fc, hits):
    wide = fc["rel_band"] > 0.6                                   # forecast uncertain?
    severe = any(n["type"] in HIGH_IMPACT for n, _ in hits)       # market-moving notice?
    if wide or severe:
        why = []
        if wide:   why.append(f"forecast uncertainty is high (P10-P90 spread ~{fc['rel_band']*100:.0f}% of P50)")
        if severe: why.append("a high-impact market notice is in play")
        return "ESCALATE", "; ".join(why)
    return "AUTO", f"forecast is tight (spread ~{fc['rel_band']*100:.0f}% of P50) and no high-impact notices"


# ============================ agentic router ============================
def route(question):
    """Pick tools from intent. Transparent rules here; LLM/classifier in production."""
    ql = question.lower()
    tools = set()
    if any(w in ql for w in ["why", "explain", "congest", "spike", "clear", "rule",
                              "protocol", "methodology", "outage", "constraint", "notice"]):
        tools.add("retrieve")
    if any(w in ql for w in ["forecast", "tomorrow", "expect", "price", "spike", "evening", "peak"]):
        tools.add("forecast")
    if any(w in ql for w in ["should", "do", "charge", "discharge", "hold", "dispatch", "move", "position"]):
        tools.update({"forecast", "dispatch"})
    return tools or {"retrieve", "forecast"}


# ============================ explainer ============================
def _template_answer(question, fc, disp, hits, verdict, why):
    lines = []
    if fc:
        lines.append(f"Forecast ({fc['date']}): P50 peaks ~${fc['peak_price']:.0f}/MWh around "
                     f"{fc['peak_time']}; P10-P90 spread ~{fc['rel_band']*100:.0f}% of P50.")
    if disp:
        lines.append(f"Bolt's move now: {disp['action_now']} "
                     f"(plan discharges {disp['discharge_kwh']:.1f} kWh / charges {disp['charge_kwh']:.1f} kWh today).")
    if hits:
        cites = "; ".join(f"[{n['id']}] {n['title']}" for n, _ in hits)
        lines.append(f"Relevant ERCOT notices: {cites}.")
        top = hits[0][0]
        lines.append(f"Most relevant: {top['body']}")
    lines.append(f"Confidence layer: {verdict} — {why}.")
    return "\n".join(lines)


def _llm_answer(question, context):
    """Drop-in real-LLM path; used only if ANTHROPIC_API_KEY is set."""
    import anthropic
    client = anthropic.Anthropic()
    sys = ("You are a power-trading co-pilot. Answer the trader plainly using ONLY the "
           "provided context (forecast numbers, Bolt recommendation, retrieved ERCOT "
           "notices). Cite notices by their bracketed id. Never invent numbers. End with "
           "the confidence verdict verbatim.")
    msg = client.messages.create(model="claude-sonnet-4-5", max_tokens=400,
                                 system=sys, messages=[{"role": "user",
                                 "content": f"Trader question: {question}\n\nContext:\n{context}"}])
    return msg.content[0].text


def ask(question, store, reserve_kwh=10.0, verbose=True):
    tools = route(question)
    fc = tool_forecast() if ("forecast" in tools or "dispatch" in tools) else None
    disp = tool_dispatch(fc, reserve_kwh) if "dispatch" in tools else None
    hits = store.retrieve(question, k=2) if "retrieve" in tools else []
    verdict, why = confidence_verdict(fc, hits) if fc else (
        ("ESCALATE", "high-impact notice in play") if any(n["type"] in HIGH_IMPACT for n, _ in hits)
        else ("AUTO", "no high-impact notices"))

    context = _template_answer(question, fc, disp, hits, verdict, why)
    answer = _llm_answer(question, context) if os.getenv("ANTHROPIC_API_KEY") else context

    if verbose:
        print(f"\nQ: {question}")
        print(f"   router -> tools: {sorted(tools)}")
        if hits:
            print(f"   retrieved: {[n['id'] for n, _ in hits]} (scores {[round(s,2) for _, s in hits]})")
        print(f"   verdict: {verdict}")
        print("   ---")
        for ln in answer.split("\n"):
            print(f"   {ln}")
    return answer


if __name__ == "__main__":
    store = NoticeStore(NOTICES)
    mode = "LIVE LLM" if os.getenv("ANTHROPIC_API_KEY") else "offline (grounded template)"
    print(f"Trader Co-Pilot — generation mode: {mode}")
    for q in [
        "What should I do with the battery into the evening peak?",
        "Why might RRS clear high tonight?",
        "Should I hold my position given the Limestone unit outage and the West-Houston constraint?",
        "What's the price forecast and how confident are you?",
    ]:
        ask(q, store)
