"""
kb_structure.py — KB Pass 3 T4: assemble the archetype's final /energy_knowledge_base layout.

Canonical objects = the 24 merged multi-item objects (kb/knowledge/canonical/) + every trusted item NOT
in a multi-item group, folded in as a pass-through canonical object (nothing lost). Each object is routed
to ONE typed folder by its type/category. Also builds taxonomy.json, concept_graph.json (nodes = canonical
concepts, edges ONLY from stated relationships — an edge exists when an object's relationship text names
another canonical concept; no invented edges), and contradictions_review.md. Deterministic; reconciles
counts (trusted in == canonical content out + excluded). NO LLM here (chapter summaries are a separate step).
"""
import argparse
import glob
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

FOLDERS = ["concepts", "definitions", "formulas", "market_mechanics", "trading_implications",
           "risk", "examples", "chapter_summaries", "source_provenance"]

SUMMARY_SYSTEM = (
    "You write a short ORIENTATION paragraph for a book chapter in an energy-trading knowledge base. "
    "You are given the chapter title and the list of concepts extracted from it (topic + one-line gist). "
    "Write 2-4 sentences that orient a reader to what the chapter covers and how its concepts relate. "
    "RULES: rewrite in your own words for orientation — do NOT stitch the gists together verbatim. "
    "Introduce NO new facts, numbers, formulas, or claims beyond what the concept list already states. "
    "No superlatives or cross-chapter bridges. Output ONLY the paragraph, no preamble, no markdown."
)


def _run_claude(system, user):
    r = subprocess.run(["claude", "-p", f"{system}\n\n{user}", "--model", "sonnet"],
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"claude rc={r.returncode}: {r.stderr[:200]}")
    return r.stdout.strip()


def route(obj):
    t = (obj.get("type") or "concept").lower().replace(" ", "_")
    cat = " ".join(str(obj.get(k, "")) for k in ("category", "subcategory")).lower()
    if t in ("formula",) or (obj.get("formulas") and t not in ("definition", "market_mechanic", "example")):
        return "formulas"
    if t == "definition":
        return "definitions"
    if t in ("market_mechanic", "market_mechanics"):
        return "market_mechanics"
    if t in ("example", "examples"):
        return "examples"
    if "risk" in cat or "risk" in t:
        return "risk"
    if t in ("trading_strategy", "strategy") or "trading" in t:
        return "trading_implications"
    return "concepts"


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")[:60]


def singleton_object(item, member):
    """Pass-through canonical object for a trusted item that wasn't merged (no LLM; content unchanged)."""
    return {"canonical_topic": item.get("topic"), "type": item.get("type", "concept"),
            "category": item.get("category"), "subcategory": item.get("subcategory"),
            "definition": item.get("definition"), "core_idea": item.get("core_idea"),
            "key_points": item.get("key_points", []), "relationships": item.get("relationships", []),
            "trading_implications": item.get("trading_implications", []),
            "caveats": item.get("caveats") or item.get("common_misunderstandings", []),
            "formulas": [{**f, "source": item.get("source", {})} for f in item.get("formulas", [])],
            "contradictions": [], "n_merged": 1,
            "source_refs": [{"chapter": item["source"]["chapter"], "pages": item["source"]["pages"]}]
            if "source" in item else [],
            "validation_rollup": {(item.get("_validation") or {}).get("judge_verdict") or "det-pass": 1},
            "contributing_items": [{"file": member["file"], "idx": member["idx"], "topic": item.get("topic")}],
            "_synth_validation": {"status": "SINGLETON", "unsupported": []}}


def summaries(kb):
    """Generate one rewritten orientation paragraph per chapter (LLM). Resumable: skips existing chNN.json."""
    base = kb.parent / "energy_knowledge_base"
    outdir = base / "chapter_summaries"
    outdir.mkdir(parents=True, exist_ok=True)
    chapters = {c["n"]: c["title"] for c in json.loads((kb / "chapters.json").read_text())}
    by_ch = defaultdict(list)                        # group canonical objects by their (first) source chapter
    for f in glob.glob(str(base / "*/*.json")):
        if "/chapter_summaries/" in f:
            continue
        o = json.loads(Path(f).read_text())
        ch = (o.get("source_refs") or [{}])[0].get("chapter")
        if ch is not None:
            by_ch[ch].append(o)
    done = errs = 0
    for ch in sorted(by_ch):
        out = outdir / f"ch{ch:02d}.json"
        if out.exists():
            continue
        objs = by_ch[ch]
        gists = "\n".join(f"- {o['canonical_topic']}: {(o.get('definition') or o.get('core_idea') or '')[:160]}"
                          for o in objs[:60])
        user = f"Chapter {ch}: {chapters.get(ch,'')}\nConcepts ({len(objs)}):\n{gists}"
        try:
            para = _run_claude(SUMMARY_SYSTEM, user)
            out.write_text(json.dumps({"chapter": ch, "title": chapters.get(ch, ""),
                                       "n_concepts": len(objs), "summary": para,
                                       "provenance": "rewritten orientation from this chapter's concept set; no new claims"}, indent=1))
            done += 1
            print(f"  ch{ch:02d} ({len(objs)} concepts): {para[:90]}...")
        except RuntimeError as e:
            errs += 1
            print(f"  ch{ch:02d} ERROR: {e}")
    print(f"chapter summaries: {done} written, {errs} errors, {len(list(outdir.glob('ch*.json')))} total on disk "
          f"(of {len(by_ch)} chapters with content). Rerun to fill errors.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", required=True)
    ap.add_argument("--summaries", action="store_true", help="generate chapter orientation paragraphs (LLM)")
    a = ap.parse_args()
    kb = Path(a.kb)
    if a.summaries:
        summaries(kb)
        return
    plan = json.loads((kb / "merge_plan.json").read_text())
    full = {f.replace(str(kb) + "/", ""): json.loads(Path(f).read_text())
            for f in glob.glob(str(kb / "raw/ch*/chunk_*.json"))}

    objects = []
    merged_members = 0
    for g in plan["groups"]:
        if g["n_items"] > 1:                          # merged multi-item -> load the canonical object
            obj = json.loads((kb / "canonical" / f"{_slug(g['canonical_topic'])}.json").read_text())
            objects.append(obj)
            merged_members += obj["n_merged"]
        else:                                         # singleton -> pass-through (nothing lost)
            m = g["members"][0]
            objects.append(singleton_object(full[m["file"]]["items"][m["idx"]], m))

    # ---- write the typed layout ----
    base = kb.parent / "energy_knowledge_base"
    for fdr in FOLDERS:
        (base / fdr).mkdir(parents=True, exist_ok=True)
    routed = defaultdict(int)
    slugs = {}
    for obj in objects:
        fdr = route(obj)
        slug = _slug(obj["canonical_topic"])
        i = 1
        while (base / fdr / f"{slug}.json").exists():   # avoid slug collisions
            slug = f"{_slug(obj['canonical_topic'])}_{i}"
            i += 1
        (base / fdr / f"{slug}.json").write_text(json.dumps(obj, indent=1))
        slugs[obj["canonical_topic"]] = (fdr, slug)
        routed[fdr] += 1

    # ---- taxonomy ----
    tax = defaultdict(lambda: defaultdict(list))
    for obj in objects:
        tax[obj.get("category") or "Uncategorized"][obj.get("subcategory") or "General"].append(obj["canonical_topic"])
    (base / "taxonomy.json").write_text(json.dumps(tax, indent=1))

    # ---- concept graph: edges ONLY from stated relationships that name another canonical concept ----
    names = {re.sub(r"[^a-z0-9 ]", "", n.lower()): n for n in slugs}   # normalized canonical name -> name
    edges = []
    for obj in objects:
        src = obj["canonical_topic"]
        for rel in obj.get("relationships", []):
            rl = re.sub(r"[^a-z0-9 ]", " ", str(rel).lower())
            for nk, nm in names.items():
                if nm != src and len(nk) >= 5 and re.search(rf"\b{re.escape(nk)}\b", rl):
                    edges.append({"from": src, "to": nm, "stated_in": str(rel)[:160]})
    (base / "concept_graph.json").write_text(json.dumps(
        {"nodes": list(slugs.keys()), "edges": edges,
         "note": "edges derived only from objects' stated relationships; no invented edges"}, indent=1))

    # ---- contradictions review ----
    L = ["# Synthesis contradictions — human review (Pass 3)\n",
         "Conflicting definitions/formulas the merge recorded WITHOUT resolving. Standard is provenance:\n"]
    ncontra = 0
    for obj in objects:
        for c in obj.get("contradictions", []):
            ncontra += 1
            L.append(f"## {obj['canonical_topic']} — {c.get('field','')}")
            for v in c.get("versions", []):
                L.append(f"- \"{v.get('statement','')}\"  _(from: {v.get('from_item','')})_")
            L.append(f"note: {c.get('note','')}\n")
    (base / "contradictions_review.md").write_text("\n".join(L))

    # ---- reconciliation ----
    trusted_in = plan["input"]["trusted"]
    canonical_members = sum(len(o.get("contributing_items", [])) for o in objects)
    flagged = sum(1 for o in objects if o.get("_synth_validation", {}).get("status") == "FLAGGED")
    print("=== energy_knowledge_base assembled ===")
    print("routed:", dict(routed), "| total objects:", len(objects))
    print(f"RECONCILE: trusted items in = {trusted_in}; contributing items across canonical objects = "
          f"{canonical_members}  -> {'OK (nothing lost)' if canonical_members == trusted_in else 'MISMATCH!'}")
    print(f"canonical objects = {len(objects)} ({sum(1 for o in objects if o['n_merged']>1)} merged + "
          f"{sum(1 for o in objects if o['n_merged']==1)} singletons) | excluded = {plan['input']['excluded']} "
          f"| trusted+excluded = {trusted_in + plan['input']['excluded']}")
    print(f"synth-flagged objects (review queue): {flagged} | contradictions: {ncontra} | graph edges: {len(edges)}")
    print("NOTE: chapter_summaries/ still to be generated (separate LLM step).")


if __name__ == "__main__":
    main()
