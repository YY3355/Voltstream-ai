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
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
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


MERGE_SYSTEM = (
    "You merge several validated knowledge items that are all about ONE concept into ONE canonical "
    "object. This is DEDUPLICATION of existing content — you MUST NOT write new claims, formulas, "
    "numbers, or market rules that are not already in the provided items.\n"
    "SCOPE RULE (critical): the definition and all prose must restate ONLY what the items say. Do NOT "
    "generalize, broaden scope, or add cases/examples/claims not explicitly in a source item. When items "
    "describe a BOUNDED case (e.g. 'within X'), NEVER widen it (e.g. 'between X'). Prefer a source item's "
    "own phrasing over a new synthesis. Every clause of the definition and every key_point must be "
    "traceable to at least one item. Add NO cross-concept associations, superlatives, or bridges (e.g. "
    "linking one concept to another, or calling something 'the most important') unless a source item "
    "states it.\n"
    "Return ONLY a JSON object with: definition (one concise definition, source-faithful), core_idea, "
    "key_points (merged + de-duplicated; each supported by >=1 item), relationships, trading_implications, "
    "caveats, and contradictions.\n"
    "contradictions: if two items give CONFLICTING definitions or formulas for the same thing, do NOT "
    "resolve, average, or pick one — add {\"field\":..., \"versions\":[{\"statement\":..., "
    "\"from_item\":<topic>}], \"note\":...}. If none, use [].\n"
    "Do not restate the formulas in your output (preserved separately). Combine only; when in doubt, keep "
    "less rather than invent."
)

JUDGE_MERGE_SYSTEM = (
    "You check a MERGED canonical knowledge object against the exact source items it was built from. Find "
    "any statement in the object's definition, core_idea, key_points, relationships, trading_implications, "
    "or caveats that is NOT supported by any source item — a new fact, number, invented bridging claim, or "
    "SCOPE-BROADENING (a bounded case widened, e.g. 'within X' turned into 'between X'). Rewritten/merged "
    "wording is fine as long as the substance exists in some item.\n"
    "Return ONLY JSON: {\"status\": \"CLEAN\"|\"FLAGGED\", \"unsupported\": [{\"field\":..., \"claim\":..., "
    "\"reason\":...}]}. If nothing is unsupported, status CLEAN and unsupported []."
)


def load_full(kb):
    cache = {}
    for f in glob.glob(str(kb / "raw/ch*/chunk_*.json")):
        cache[f.replace(str(kb) + "/", "")] = json.loads(Path(f).read_text())
    return cache


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:50]


def merge_group(kb, group, full, run_llm):
    """Merge one multi-item group -> canonical object. Formulas + source refs + validation rollup are
    assembled DETERMINISTICALLY (guaranteed verbatim + complete); the LLM only merges prose + flags
    contradictions."""
    members = [full[m["file"]]["items"][m["idx"]] for m in group["members"]]
    # deterministic: every formula kept verbatim with its own source; all source refs; validation rollup
    formulas = [{**fm, "source": it.get("source", {})} for it in members for fm in it.get("formulas", [])]
    source_refs = [{"chapter": it["source"]["chapter"], "pages": it["source"]["pages"]}
                   for it in members if "source" in it]
    roll = Counter((it.get("_validation") or {}).get("judge_verdict") or "det-pass" for it in members)
    contributing = [{"file": m["file"], "idx": m["idx"], "topic": full[m["file"]]["items"][m["idx"]].get("topic")}
                    for m in group["members"]]

    merged_prose = {"definition": "", "core_idea": "", "key_points": [], "relationships": [],
                    "trading_implications": [], "caveats": [], "contradictions": []}
    if run_llm:
        payload = [{"topic": it.get("topic"), "definition": it.get("definition"),
                    "key_points": it.get("key_points"), "relationships": it.get("relationships"),
                    "trading_implications": it.get("trading_implications"),
                    "formulas": [f.get("formula") for f in it.get("formulas", [])],
                    "source": it.get("source")} for it in members]
        prompt = (MERGE_SYSTEM + f"\n\nCONCEPT: {group['canonical_topic']}\n\nITEMS ({len(members)}):\n"
                  + json.dumps(payload, indent=1))
        for attempt in (1, 2):
            r = subprocess.run(["claude", "-p", prompt, "--model", "sonnet"],
                               capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                raise RuntimeError(f"claude CLI rc={r.returncode}: {r.stderr[:200]}")
            txt = re.sub(r"^```(?:json)?|```$", "", r.stdout.strip(), flags=re.M).strip()
            try:
                d = json.loads(txt)
                for k in merged_prose:
                    if k in d:
                        merged_prose[k] = d[k]
                break
            except json.JSONDecodeError:
                if attempt == 2:
                    raise
                prompt += "\n\nReturn ONLY the JSON object."

    return {"canonical_topic": group["canonical_topic"], "type": "concept", "n_merged": len(members),
            **merged_prose, "formulas": formulas, "source_refs": source_refs,
            "validation_rollup": dict(roll), "contributing_items": contributing}


def merge_judge(kb, obj, full):
    """MANDATORY post-merge check: does the synthesized prose introduce any claim not in the source
    items (invented fact/number/bridging claim, or scope-broadening)? Returns _synth_validation."""
    members = [full[c["file"]]["items"][c["idx"]] for c in obj["contributing_items"]]
    # include source formulas so the judge can verify formula-restatements against the actual source
    # formulas (a key_point that restates a source formula must NOT be flagged as unsupported).
    payload = [{"topic": it.get("topic"), "definition": it.get("definition"),
                "key_points": it.get("key_points"), "relationships": it.get("relationships"),
                "trading_implications": it.get("trading_implications"),
                "formulas": [f.get("formula") for f in it.get("formulas", [])]} for it in members]
    prose = {k: obj.get(k) for k in ("definition", "core_idea", "key_points", "relationships",
                                     "trading_implications", "caveats")}
    prompt = (JUDGE_MERGE_SYSTEM + "\n\nMERGED OBJECT PROSE:\n" + json.dumps(prose, indent=1)
              + "\n\nSOURCE ITEMS:\n" + json.dumps(payload, indent=1))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for attempt in (1, 2):
        r = subprocess.run(["claude", "-p", prompt, "--model", "sonnet"],
                           capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise RuntimeError(f"claude CLI rc={r.returncode}: {r.stderr[:200]}")
        txt = re.sub(r"^```(?:json)?|```$", "", r.stdout.strip(), flags=re.M).strip()
        try:
            d = json.loads(txt)
            uns = d.get("unsupported") or []
            status = "FLAGGED" if (str(d.get("status", "")).upper() == "FLAGGED" or uns) else "CLEAN"
            return {"status": status, "unsupported": uns, "checked_at": now}
        except json.JSONDecodeError:
            if attempt == 2:
                return {"status": "FLAGGED", "unsupported": [{"reason": "judge non-JSON twice"}],
                        "checked_at": now}
            prompt += "\n\nReturn ONLY the JSON object."


def run_merge(kb, lo, hi):
    plan_data = json.loads((kb / "merge_plan.json").read_text())
    full = load_full(kb)
    outdir = kb / "canonical"
    outdir.mkdir(exist_ok=True)
    state_path = kb / "synth_state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {"done": {}}
    rng = range(lo, hi + 1)
    targets = [g for g in plan_data["groups"] if g["n_items"] > 1
               and any(m["chapter"] in rng for m in g["members"])]
    def process(g):
        slug = _slug(g["canonical_topic"])
        obj = merge_group(kb, g, full, run_llm=True)
        obj["_synth_validation"] = merge_judge(kb, obj, full)         # MANDATORY post-merge judge
        (outdir / f"{slug}.json").write_text(json.dumps(obj, indent=1))
        state["done"][slug] = {"n_merged": obj["n_merged"], "formulas": len(obj["formulas"]),
                               "contradictions": len(obj.get("contradictions", [])),
                               "synth_status": obj["_synth_validation"]["status"]}
        state_path.write_text(json.dumps(state, indent=1))
        return obj

    def is_done(slug):
        v = state["done"].get(slug)
        return v is not None and "error" not in v

    print(f"merging {len(targets)} multi-item groups touching ch{lo}-{hi} ...")
    for g in targets:
        slug = _slug(g["canonical_topic"])
        if is_done(slug):
            print(f"  skip {slug} (done)")
            continue
        try:                                                          # transient rc=1 -> record + continue
            obj = process(g)
            print(f"  {slug}: merged {obj['n_merged']}, {len(obj['formulas'])} formulas, "
                  f"{len(obj.get('contradictions',[]))} contradictions, synth-judge={obj['_synth_validation']['status']}")
            judged = [v for v in state["done"].values() if "synth_status" in v]
            fl = [v for v in judged if v["synth_status"] == "FLAGGED"]
            if len(judged) >= 8 and len(fl) / len(judged) > 0.5:      # circuit-breaker (pilot was ~1/3)
                print(f"\n!! CIRCUIT-BREAKER: flag rate {len(fl)}/{len(judged)} > 50% — stopping. That's "
                      f"well past the pilot's ~1/3, so something changed (not noise). Resume after review.")
                return
        except RuntimeError as e:
            state["done"][slug] = {"error": str(e)[:200]}
            state_path.write_text(json.dumps(state, indent=1))
            print(f"  {slug}: ERROR {str(e)[:70]} (recorded, continuing)")

    # retry-once at end: clear error entries + reprocess (mirrors Pass 1); twice-failed stays an error scar
    errored = [g for g in targets if not is_done(_slug(g["canonical_topic"]))]
    if errored:
        print(f"retrying {len(errored)} errored group(s) once ...")
        for g in errored:
            slug = _slug(g["canonical_topic"])
            state["done"].pop(slug, None)
            try:
                obj = process(g)
                print(f"  {slug}: retry OK (synth-judge={obj['_synth_validation']['status']})")
            except RuntimeError as e:
                state["done"][slug] = {"error": str(e)[:200]}
                state_path.write_text(json.dumps(state, indent=1))
                print(f"  {slug}: retry FAILED — {str(e)[:70]} (honest scar)")

    done = {k: v for k, v in state["done"].items() if "error" not in v}
    errs = {k: v for k, v in state["done"].items() if "error" in v}
    flagged = [k for k, v in done.items() if v.get("synth_status") == "FLAGGED"]
    print(f"\ncanonical objects: {len(done)} | errors (scars): {len(errs)} | synth-judge FLAGGED: {len(flagged)}")
    for k in errs:
        print(f"  ERROR (scar): {k}")
    for k in flagged:
        uns = json.loads((outdir / f"{k}.json").read_text())["_synth_validation"]["unsupported"]
        print(f"  FLAGGED {k}: {json.dumps(uns)[:220]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", required=True)
    ap.add_argument("--plan", action="store_true", help="T1: dry grouping, no LLM")
    ap.add_argument("--merge", action="store_true", help="T2/T3: claude -p merge")
    ap.add_argument("--chapters", help="merge groups touching this chapter range, e.g. 16-25")
    a = ap.parse_args()
    if a.plan:
        plan(Path(a.kb))
    elif a.merge:
        lo, hi = (int(x) for x in a.chapters.split("-")) if a.chapters else (1, 34)
        run_merge(Path(a.kb), lo, hi)
    else:
        ap.error("specify a stage (--plan or --merge)")


if __name__ == "__main__":
    main()
