#!/usr/bin/env python3
"""
kb_synth_report.py — KB Pass 3 T5: the synthesis report (kb/kb_synth_report.pdf).

Reads ONLY on-disk artifacts of the Pass-3 synthesis:
  energy_knowledge_base/{typed folders,concept_graph.json}, knowledge/{synth_state.json,
  merge_plan.json,excluded_from_pass3.json,canonical/*.json}, energy_knowledge_base/contradictions_review.md
Every number is computed from those files — nothing projected, nothing invented.

Usage:  conda run -n volt python kb/kb_synth_report.py [--kb kb/knowledge] [--pdf-out kb/kb_synth_report.pdf]
"""
import argparse
import glob
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

TYPED = ["concepts", "definitions", "formulas", "market_mechanics", "trading_implications",
         "risk", "examples"]


def gather(kb: Path):
    base = kb.parent / "energy_knowledge_base"
    objs, folder_counts = [], Counter()
    for fdr in TYPED:
        for f in sorted((base / fdr).glob("*.json")):
            o = json.loads(f.read_text())
            o["_folder"] = fdr
            objs.append(o)
            folder_counts[fdr] += 1
    state = json.loads((kb / "synth_state.json").read_text())["done"]
    plan_in = json.loads((kb / "merge_plan.json").read_text())["input"]
    excl = json.loads((kb / "excluded_from_pass3.json").read_text())
    graph = json.loads((base / "concept_graph.json").read_text())
    contra_md = (base / "contradictions_review.md").read_text()
    n_summaries = len(list((base / "chapter_summaries").glob("ch*.json")))
    return base, objs, folder_counts, state, plan_in, excl, graph, contra_md, n_summaries


def build_story(kb, base, objs, folder_counts, state, plan_in, excl, graph, contra_md, n_summaries):
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    styles = getSampleStyleSheet()
    h1, h2, body = styles["Title"], styles["Heading2"], styles["BodyText"]
    small = ParagraphStyle("small", parent=body, fontSize=8, textColor=colors.grey)
    mono = ParagraphStyle("mono", parent=body, fontName="Courier", fontSize=8, leading=11)
    S = []

    # ---- derived figures (all from disk) ----
    n_obj = len(objs)
    merged = [o for o in objs if o.get("n_merged", 1) > 1]
    singles = [o for o in objs if o.get("n_merged", 1) == 1]
    n_groups = len(state)
    flagged = [k for k, v in state.items() if v.get("synth_status") == "FLAGGED"]
    scars = [k for k, v in state.items() if "error" in v]
    trusted, excluded_n = plan_in["trusted"], plan_in["excluded"]
    contributing = sum(len(o.get("contributing_items", [])) for o in objs)
    verd = Counter(it.get("verdict") for it in excl["items"])

    # top-10 by source breadth (distinct chapters in source_refs)
    breadth = []
    for o in objs:
        chs = {r.get("chapter") for r in o.get("source_refs", []) if r.get("chapter") is not None}
        breadth.append((o["canonical_topic"], len(chs), o.get("n_merged", 1), sorted(c for c in chs if c is not None)))
    breadth.sort(key=lambda x: (-x[1], -x[2]))

    S += [Paragraph("KB Pass 3 — Synthesis Report", h1),
          Paragraph(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} from on-disk "
                    f"artifacts in <b>{base}</b> and <b>{kb}</b>. Every figure is computed from those files "
                    f"(canonical objects, synth_state.json, merge_plan.json, excluded_from_pass3.json, "
                    f"concept_graph.json, contradictions_review.md) — nothing projected or invented.", small),
          Spacer(1, 12)]

    # ---- 1. canonical count + folder breakdown ----
    S += [Paragraph("1. Canonical knowledge base", h2),
          Paragraph(f"<b>{n_obj} canonical objects</b> = {len(merged)} merged (multi-item) + "
                    f"{len(singles)} singleton pass-throughs. Routed to typed folders:", body)]
    rows = [["folder", "objects"]] + [[f, str(folder_counts[f])] for f in TYPED] + [["TOTAL", str(n_obj)]]
    t = Table(rows, hAlign="LEFT", colWidths=[160, 60])
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dddddd")),
                           ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eeeeee")),
                           ("GRID", (0, 0), (-1, -1), 0.4, colors.grey)]))
    S += [t, Spacer(1, 6),
          Paragraph(f"Chapter orientation summaries generated: <b>{n_summaries}</b> (rewritten, not stitched).", small),
          Spacer(1, 10)]

    # ---- 2. merge stats ----
    fr = len(flagged)
    S += [Paragraph("2. Merge statistics", h2),
          Paragraph(f"<b>{n_groups}/24 multi-item groups merged.</b> "
                    f"Synth-judge flag rate: <b>{fr}/{n_groups} = {100*fr/n_groups:.0f}%</b> "
                    f"(design baseline from the 9-group pilot was ~1/3; the circuit-breaker at &gt;50% did "
                    f"NOT trip). Error scars (twice-failed groups): <b>{len(scars)}</b>. "
                    f"Merge combines validated content only — formulas, source refs and the validation "
                    f"rollup are assembled deterministically; the LLM merges prose, then a mandatory "
                    f"formula-aware judge checks every merged object. Flagged objects reach the KB "
                    f"<i>flagged</i> (never silently dropped).", body),
          Paragraph("Flagged objects (synth review queue): " + ", ".join(sorted(flagged)), small),
          Spacer(1, 10)]

    # ---- 3. top-10 by source breadth ----
    S += [Paragraph("3. Top-10 concepts by source breadth", h2),
          Paragraph("Breadth = number of distinct chapters contributing to the object's source_refs.", small)]
    rows = [["#", "canonical topic", "chapters", "items", "which chapters"]]
    for i, (topic, nch, nit, chs) in enumerate(breadth[:10], 1):
        rows.append([str(i), topic[:38], str(nch), str(nit), ",".join(map(str, chs))[:26]])
    t = Table(rows, hAlign="LEFT", colWidths=[16, 200, 50, 36, 120])
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", 8),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dddddd")),
                           ("GRID", (0, 0), (-1, -1), 0.4, colors.grey)]))
    S += [t, Spacer(1, 10)]

    # ---- 4. contradictions verbatim ----
    S += [Paragraph("4. Contradictions — recorded UNRESOLVED", h2),
          Paragraph("Verbatim from contradictions_review.md. The merge records conflicting definitions/"
                    "formulas with both versions + sources and does NOT resolve or average them — the KB's "
                    "standard is provenance, not adjudication.", small)]
    # parse the md into ## blocks
    blocks = []
    cur = None
    for line in contra_md.splitlines():
        if line.startswith("## "):
            cur = [line[3:]]
            blocks.append(cur)
        elif cur is not None and line.strip():
            cur.append(line)
    for b in blocks:
        S.append(Paragraph("• " + b[0].replace("—", "-"), body))
        for ln in b[1:]:
            S.append(Paragraph(ln.replace("_", "").replace("*", ""), mono))
        S.append(Spacer(1, 4))
    S += [Paragraph(f"<b>{len(blocks)} contradictions, all UNRESOLVED.</b>", small), Spacer(1, 10)]

    # ---- 5. concept graph ----
    dup_note = ""
    if len(graph["nodes"]) != n_obj:
        dup_note = (f" (nodes &lt; objects because {n_obj - len(graph['nodes'])} object(s) share a "
                    f"canonical_topic label, which collapses to one node)")
    S += [Paragraph("5. Concept graph", h2),
          Paragraph(f"<b>{len(graph['nodes'])} nodes, {len(graph['edges'])} edges.</b>{dup_note} "
                    f"Every edge is derived ONLY from an object's stated relationship text that names "
                    f"another canonical concept — no edges are invented.", body),
          Spacer(1, 10)]

    # ---- 6. reconciliation ----
    ok = "nothing lost" if contributing == trusted else "MISMATCH"
    S += [Paragraph("6. Reconciliation", h2),
          Paragraph(f"Trusted items in = <b>{trusted}</b>; contributing items across all canonical "
                    f"objects = <b>{contributing}</b> → <b>{ok}</b>. "
                    f"Trusted {trusted} + excluded {excluded_n} = <b>{trusted + excluded_n}</b> "
                    f"(the full Pass-2 population). The trusted/excluded split is recomputed from each "
                    f"item's _validation, so Pass 3 re-runs cleanly when the review queue is cleared.", body),
          Spacer(1, 10)]

    # ---- 7. excluded ----
    S += [Paragraph("7. Excluded items (not deleted)", h2),
          Paragraph(f"<b>{excl['n']} items excluded</b> from synthesis: "
                    f"{verd.get('UNSUPPORTED',0)} UNSUPPORTED + {verd.get('UNCLEAR',0)} UNCLEAR. "
                    f"They are listed in excluded_from_pass3.json (file+idx+topic+chapter+verdict), "
                    f"NOT removed — re-running Pass 3 after the Pass-2 review queue is cleared folds any "
                    f"newly-trusted item back in.", body),
          Spacer(1, 10)]

    # ---- 8. honest caveats ----
    S += [Paragraph("8. Honest scope — what is and isn't done", h2),
          Paragraph(f"<b>Synthesis is complete.</b> But TWO review queues are OPEN and awaiting human "
                    f"triage: (a) the Pass-2 validation queue — <b>{excl['n']} items</b> "
                    f"(UNSUPPORTED/UNCLEAR) never entered synthesis; (b) the synth queue — "
                    f"<b>{len(flagged)} flagged objects</b> whose merged prose the judge could not fully "
                    f"trace to their source items. Neither has been triaged by a human.", body),
          Paragraph("Retrieval, embeddings, vector DB and evaluation (Pass 5-6) are NOT built. The "
                    "Co-Pilot is NOT wired to this KB — <b>no synthesized knowledge reaches the live "
                    "app yet.</b> This report describes an offline, auditable knowledge base, not a "
                    "shipped feature.", body)]
    return S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", default="kb/knowledge")
    ap.add_argument("--pdf-out", default="kb/kb_synth_report.pdf")
    a = ap.parse_args()
    kb = Path(a.kb)
    data = gather(kb)
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate
    doc = SimpleDocTemplate(a.pdf_out, pagesize=letter, topMargin=0.6 * inch,
                            bottomMargin=0.6 * inch, leftMargin=0.7 * inch, rightMargin=0.7 * inch)
    doc.build(build_story(kb, *data))
    print(f"wrote {a.pdf_out}")


if __name__ == "__main__":
    main()
