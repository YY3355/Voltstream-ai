"""
kb_review_queue.py — KB Pass 2 T3: the human-review queue + validation report.

Reads each item's `_validation` (Pass 2) and emits kb/knowledge/review_queue.md:
  - summary + the deterministic-PASS blind spot named honestly
  - per-chapter flag breakdown
  - the review queue = UNSUPPORTED + UNCLEAR only, FORMULAS-FIRST, each with why-flagged + judge reason
  - sampled PASSED formulas from notation-heavy chapters (the blind-spot insurance)
Every figure comes from disk (the annotated raw JSONs). Read-only; changes nothing in the KB.
"""
import argparse
import glob
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

NOTATION = {12: "3.3 Statistics", 14: "3.5 Option Pricing", 30: "6.2 Value at Risk"}


def why(v):
    parts = []
    if v.get("pages_ok") is False:
        parts.append("page-attribution")
    if v.get("formula_in_source") is False:
        parts.append("formula-tokens-missing")
    return "+".join(parts) or "flagged"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", required=True)
    a = ap.parse_args()
    kb = Path(a.kb)
    chapters = {c["n"]: c["title"] for c in json.loads((kb / "chapters.json").read_text())}

    items = []
    for f in sorted(glob.glob(str(kb / "raw/ch*/chunk_*.json"))):
        d = json.loads(Path(f).read_text())
        if d.get("skip"):
            continue
        for it in d.get("items", []):
            if "_validation" in it:
                items.append(it)

    tot = len(items)
    detpass = sum(1 for it in items if not it["_validation"].get("judge_verdict"))
    vc = Counter(it["_validation"]["judge_verdict"] for it in items if it["_validation"].get("judge_verdict"))
    queue = [it for it in items if it["_validation"].get("judge_verdict") in ("UNSUPPORTED", "UNCLEAR")]
    # formulas-first, then UNSUPPORTED before UNCLEAR, then by chapter/page
    queue.sort(key=lambda it: (0 if it.get("formulas") else 1,
                               0 if it["_validation"]["judge_verdict"] == "UNSUPPORTED" else 1,
                               it.get("source", {}).get("chapter", 0)))

    perch = defaultdict(Counter)
    for it in items:
        perch[it["source"]["chapter"]][it["_validation"].get("judge_verdict") or "det-pass"] += 1

    L = []
    L.append("# KB Pass 2 — Validation review queue (Pass 1 items, source-checked)\n")
    L.append(f"**{tot} items validated.** {detpass} deterministic-pass (provisional); "
             f"{sum(vc.values())} flagged → judged: "
             f"{vc.get('SUPPORTED',0)} SUPPORTED, {vc.get('UNSUPPORTED',0)} UNSUPPORTED, {vc.get('UNCLEAR',0)} UNCLEAR. "
             f"**Human-review queue = {len(queue)}** (UNSUPPORTED + UNCLEAR).\n")
    L.append("## Read this first — the deterministic-PASS blind spot\n"
             "A deterministic PASS only means *the formula's tokens appear on the source pages* — it "
             "**cannot** catch a formula whose tokens are all present but **assembled wrong** (inverted "
             "ratio, dropped term). PASS = provisionally trusted, not proven. So the queue below is "
             "*flagged* items; the sampled-passed-formulas section adds a few PASSED formulas from "
             "notation-heavy chapters for your eyeball. Also note: **most flags are page-attribution "
             "(the item's claimed pages drift), not content fabrication** — triage those faster than a "
             "formula or content flag.\n")

    L.append("## Per-chapter flags\n")
    L.append("| ch | title | det-pass | SUPPORTED | UNSUPPORTED | UNCLEAR |")
    L.append("|---|---|---|---|---|---|")
    for ch in sorted(perch):
        c = perch[ch]
        if c.get("UNSUPPORTED") or c.get("UNCLEAR"):
            L.append(f"| {ch} | {chapters.get(ch,'')[:34]} | {c.get('det-pass',0)} | "
                     f"{c.get('SUPPORTED',0)} | {c.get('UNSUPPORTED',0)} | {c.get('UNCLEAR',0)} |")

    L.append(f"\n## Review queue ({len(queue)}) — FORMULAS FIRST\n")
    for i, it in enumerate(queue, 1):
        v = it["_validation"]
        src = it.get("source", {})
        tag = "⚠FORMULA" if it.get("formulas") else "prose"
        L.append(f"### {i}. [{v['judge_verdict']} · {tag}] {it.get('topic','')[:70]}")
        L.append(f"- source: ch{src.get('chapter')} p{src.get('pages')} · flagged: **{why(v)}** · "
                 f"file has {len(it.get('formulas',[]))} formula(s)")
        if it.get("formulas"):
            for fm in it["formulas"]:
                L.append(f"  - formula: `{fm.get('formula','')}`")
        L.append(f"- judge: {v.get('judge_reason','')}\n")

    L.append("## Blind-spot insurance — sampled PASSED formulas in notation-heavy chapters\n"
             "(These PASSED deterministically; eyeball that they're assembled correctly, per the blind spot above.)\n")
    rng = random.Random(20260821)  # fixed seed → reproducible sample
    for ch, title in NOTATION.items():
        passed = [(it["source"]["pages"], fm.get("formula", ""))
                  for it in items if it["source"]["chapter"] == ch
                  and not it["_validation"].get("judge_verdict") for fm in it.get("formulas", [])]
        pick = passed if len(passed) <= 3 else rng.sample(passed, 3)
        L.append(f"**ch{ch} {title}** ({len(passed)} passed formulas):")
        for pg, fo in pick:
            L.append(f"- p{pg}: `{fo}`")
        if not pick:
            L.append("- (no passed formulas in this chapter)")
        L.append("")

    out = kb / "review_queue.md"
    out.write_text("\n".join(L))
    print(f"wrote {out}: {len(queue)} queue items, {vc.get('UNSUPPORTED',0)} UNSUPPORTED / {vc.get('UNCLEAR',0)} UNCLEAR")


if __name__ == "__main__":
    main()
