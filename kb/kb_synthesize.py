"""
kb_synthesize.py — KB Pass 3: chapter synthesis + global dedup -> canonical knowledge base.

Input contract (recomputed every run, so Pass 3 re-runs cleanly when the review queue clears):
  TRUSTED  = items whose _validation is deterministic-pass OR judge SUPPORTED  -> synthesized
  EXCLUDED = UNSUPPORTED / UNCLEAR                                              -> excluded, NOT deleted,
             listed in kb/knowledge/excluded_from_pass3.json (nothing silently vanishes)

Stages:
  --plan   T1 (no LLM): normalize topics, group into a proposed merge map -> merge_plan.json + summary.
  --merge  T2/T3 (claude -p): merge each group into one canonical object (combine-only, never invent;
           all source refs kept; conflicting formulas/defs -> contradiction flag, never resolved).
"""
import argparse
import glob
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

# Curated seed concepts (canonical -> phrase variants). CONSERVATIVE: only specific named concepts where
# real duplication occurs across the book — NOT commodities (crude oil), NOT broad umbrellas (volatility).
# Assignment is longest-match + WHOLE-WORD (a topic is assigned to the longest seed variant it contains as
# whole words), so "dark/spark/crack spread" never cross and "market implied heat rate" routes to
# implied-heat-rate (4-word variant beats plain "heat rate"). Singletons are a correct, honest outcome.
SEEDS = {
    "implied heat rate": ["implied heat rate", "market implied heat rate", "implied market heat rate"],
    "heat rate": ["heat rate"],
    "spark spread": ["spark spread"],
    "dark spread": ["dark spread"],
    "crack spread": ["crack spread"],
    "clean/green spread": ["clean spread", "green spread"],
    "spread option": ["spread option", "spread options"],
    "mark to market": ["mark to market"],
    "hedge accounting": ["hedge accounting"],
    "historical cost accounting": ["historical cost accounting"],
    "value at risk": ["value at risk", "var"],
    "credit risk": ["credit risk", "counterparty credit risk", "counterparty credit"],
    "model risk": ["model risk"],
    "black scholes": ["black scholes"],
    "cap and trade": ["cap and trade"],
    "carbon tax": ["carbon tax", "carbon taxes"],
    "natural gas storage": ["natural gas storage"],
    "liquefied natural gas": ["liquefied natural gas"],
    "natural gas liquids": ["natural gas liquids"],
    "tolling agreement": ["tolling agreement", "tolling agreements"],
    "wheeling": ["wheeling power", "wheeling"],
    "financial transmission rights": ["financial transmission right", "financial transmission rights"],
    "load forecasting": ["load forecasting", "spatial load forecasting"],
    "generation stack": ["generation stack"],
    "levelized cost": ["levelized cost"],
    "weather derivative": ["weather derivative", "weather derivatives"],
    "put call parity": ["put call parity"],
    "hedging": ["hedging"],
}
# flat (variant, canonical, wordlen) sorted longest-first so the most specific match wins
_SEED_MATCH = sorted(((v, canon, len(v.split())) for canon, vs in SEEDS.items() for v in vs),
                     key=lambda x: -x[2])


def norm_light(s):
    """lowercase + punctuation->space + collapse whitespace. No stopword drop / no singularization, so
    multi-word seed phrases match intact."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(s).lower())).strip()


def assign_seed(topic):
    """Return (canonical_seed, matched_variant) for the LONGEST whole-word seed the topic contains, or
    (None, None) -> the item is its own singleton concept."""
    t = " " + norm_light(topic) + " "
    for variant, canon, _ in _SEED_MATCH:
        if f" {variant} " in t or re.search(rf"\b{re.escape(variant)}\b", t):
            return canon, variant
    return None, None


def load_items(kb):
    """Return (trusted, excluded). Trusted = det-pass or SUPPORTED; both carry file+idx provenance."""
    trusted, excluded = [], []
    for f in sorted(glob.glob(str(kb / "raw/ch*/chunk_*.json"))):
        d = json.loads(Path(f).read_text())
        if d.get("skip"):
            continue
        rel = f.replace(str(kb) + "/", "")
        for i, it in enumerate(d.get("items", [])):
            v = it.get("_validation") or {}
            verd = v.get("judge_verdict")
            rec = {"file": rel, "idx": i, "topic": it.get("topic", ""),
                   "chapter": it.get("source", {}).get("chapter"),
                   "pages": it.get("source", {}).get("pages"),
                   "has_formula": bool(it.get("formulas")), "verdict": verd or "det-pass"}
            (trusted if (verd is None or verd == "SUPPORTED") else excluded).append(rec)
    return trusted, excluded


def plan(kb):
    trusted, excluded = load_items(kb)
    (kb / "excluded_from_pass3.json").write_text(json.dumps(
        {"n": len(excluded), "note": "UNSUPPORTED/UNCLEAR — excluded from Pass 3, not deleted; "
         "re-run Pass 3 after clearing the review queue to fold cleared items in.",
         "items": excluded}, indent=1))

    seed_groups = defaultdict(list)
    singletons = []
    for r in trusted:
        canon, variant = assign_seed(r["topic"])
        if canon:
            r["_matched_variant"] = variant
            seed_groups[canon].append(r)
        else:
            singletons.append(r)

    out = []
    for canon, members in seed_groups.items():
        chapters = sorted(set(m["chapter"] for m in members))
        out.append({"canonical_topic": canon, "seed": True, "n_items": len(members),
                    "chapters": chapters, "cross_chapter": len(chapters) > 1,
                    "has_formula": any(m["has_formula"] for m in members), "members": members})
    for r in singletons:
        out.append({"canonical_topic": r["topic"], "seed": False, "n_items": 1,
                    "chapters": [r["chapter"]], "cross_chapter": False,
                    "has_formula": r["has_formula"], "members": [r]})
    out.sort(key=lambda g: (-g["n_items"], g["canonical_topic"]))

    multi = [g for g in out if g["n_items"] > 1]
    (kb / "merge_plan.json").write_text(json.dumps(
        {"input": {"trusted": len(trusted), "excluded": len(excluded)},
         "seeds": list(SEEDS.keys()),
         "stats": {"n_canonical": len(out), "seed_concepts": len(seed_groups),
                   "multi_item_groups": len(multi), "singletons": len(singletons),
                   "cross_chapter_groups": sum(1 for g in out if g["cross_chapter"])},
         "groups": out}, indent=1))

    # scannable gate artifact: the seed list + the assigned topic strings under each top-10 group
    L = [f"# Pass 3 T1 — merge plan (grouping gate)\n",
         f"INPUT: {len(trusted)} trusted, {len(excluded)} excluded.\n",
         f"GROUPING: {len(trusted)} items -> {len(out)} canonical concepts "
         f"({len(seed_groups)} seed concepts w/ {len(multi)} multi-item, {len(singletons)} singletons).\n",
         f"## Seed list ({len(SEEDS)})\n" + ", ".join(SEEDS.keys()) + "\n",
         "## Top groups — assigned topic strings (scan for false merges)\n"]
    for g in [x for x in out if x["seed"]][:12]:
        L.append(f"### {g['n_items']}x  **{g['canonical_topic']}**  (ch{g['chapters']})")
        for m in g["members"]:
            L.append(f"- ch{m['chapter']} p{m['pages']}: {m['topic']}  _[matched: {m.get('_matched_variant')}]_")
        L.append("")
    (kb / "merge_plan_review.md").write_text("\n".join(L))

    print(f"INPUT: {len(trusted)} trusted, {len(excluded)} excluded (-> excluded_from_pass3.json)")
    print(f"GROUPING: {len(trusted)} items -> {len(out)} canonical concepts "
          f"({len(seed_groups)} seed concepts, {len(multi)} multi-item merges, {len(singletons)} singletons).")
    print("\nSeed concepts by size (the merge head):")
    for g in [x for x in out if x['seed']][:14]:
        print(f"  {g['n_items']:>2} items · ch{g['chapters']} · \"{g['canonical_topic']}\"")
    print(f"\nseeds that matched 0 items: {[s for s in SEEDS if s not in seed_groups]}")
    print("-> gate artifact: kb/knowledge/merge_plan_review.md")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", required=True)
    ap.add_argument("--plan", action="store_true", help="T1: dry grouping, no LLM")
    a = ap.parse_args()
    if a.plan:
        plan(Path(a.kb))
    else:
        ap.error("specify a stage (--plan)")


if __name__ == "__main__":
    main()
