#!/usr/bin/env python3
"""
kb_report.py — turn a kb_extract.py run into a PDF report (kb_report.pdf).

Reads ONLY what exists on disk: processing_state.json + knowledge/raw/**.json.
Every number in the report comes from those files — nothing is projected or invented.

Usage:  python kb_report.py --kb knowledge [--pdf-out kb_report.pdf] [--samples 5]
Needs:  pip install reportlab
"""

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

COST_PER_MTOK_IN = 3.00   # same rough Sonnet rates as kb_extract.py — labeled estimate
COST_PER_MTOK_OUT = 15.00


def gather(kb: Path):
    state_f = kb / "processing_state.json"
    state = json.loads(state_f.read_text()) if state_f.exists() else {"chunks": {}, "usage": {"in": 0, "out": 0}}
    items, per_chapter, flagged = [], Counter(), []
    for f in sorted((kb / "raw").glob("ch*/chunk_*.json")) if (kb / "raw").exists() else []:
        data = json.loads(f.read_text())
        ch = f.parent.name  # chNN
        for it in data.get("items", []):
            it["_file"] = str(f.relative_to(kb))
            items.append(it)
            per_chapter[ch] += 1
        if data.get("_verbatim_flags"):
            flagged.append((str(f.relative_to(kb)), data["_verbatim_flags"]))
    return state, items, per_chapter, flagged


def build_story(kb, state, items, per_chapter, flagged, n_samples):
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak

    styles = getSampleStyleSheet()
    h1, h2, body = styles["Title"], styles["Heading2"], styles["BodyText"]
    small = ParagraphStyle("small", parent=body, fontSize=8, textColor=colors.grey)
    story = []

    chunks = state.get("chunks", {})
    done = sum(1 for v in chunks.values() if v == "done")
    errs = {k: v for k, v in chunks.items() if str(v).startswith("error")}
    usage = state.get("usage", {"in": 0, "out": 0})
    cost = usage["in"] / 1e6 * COST_PER_MTOK_IN + usage["out"] / 1e6 * COST_PER_MTOK_OUT

    story += [Paragraph("Book → KB Extraction Report (Pass 1)", h1),
              Paragraph(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} "
                        f"from on-disk state in <b>{kb}</b>. All figures read from "
                        f"processing_state.json and saved chunk JSONs — no projections.", small),
              Spacer(1, 14), Paragraph("Run status", h2)]

    rows = [["Chunks recorded in state", str(len(chunks))],
            ["Chunks done", str(done)],
            ["Chunks errored", str(len(errs))],
            ["Knowledge items extracted", str(len(items))],
            ["API tokens (in / out, from usage fields)", f"{usage['in']:,} / {usage['out']:,}"],
            ["Engine / spend", (f"api — ≈ ${cost:,.2f} at listed rates" if usage["in"]
                                else "claude-cli (subscription) — per-token spend not metered")]]
    t = Table(rows, colWidths=[3.4 * inch, 2.6 * inch])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                           ("FONTSIZE", (0, 0), (-1, -1), 9),
                           ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke)]))
    story += [t, Spacer(1, 14)]

    if per_chapter:
        story.append(Paragraph("Items per chapter", h2))
        rows = [["Chapter", "Items"]] + [[c, str(n)] for c, n in sorted(per_chapter.items())]
        t = Table(rows, colWidths=[2 * inch, 1 * inch])
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                               ("FONTSIZE", (0, 0), (-1, -1), 9),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke)]))
        story += [t, Spacer(1, 14)]

    if items:
        story.append(Paragraph("Items by type / top categories / top topics", h2))
        by_type = Counter(i.get("type", "unspecified") for i in items)
        by_cat = Counter(i.get("category", "unspecified") for i in items).most_common(10)
        by_topic = Counter(i.get("topic", "?") for i in items).most_common(15)
        story.append(Paragraph("Types: " + ", ".join(f"{k} ({v})" for k, v in by_type.most_common()), body))
        story.append(Paragraph("Top categories: " + ", ".join(f"{k} ({v})" for k, v in by_cat), body))
        story.append(Paragraph("Top topics (dup counts here = Pass-4 dedup workload): "
                               + ", ".join(f"{k} ({v})" for k, v in by_topic), body))
        story.append(Spacer(1, 14))

    story.append(Paragraph("Needs human review", h2))
    if errs:
        story.append(Paragraph(f"Errored chunks ({len(errs)}):", body))
        for k, v in list(errs.items())[:20]:
            story.append(Paragraph(f"• {k} — {v}", small))
    if flagged:
        story.append(Paragraph(f"Verbatim-guard flags ({len(flagged)} files) — items copying 25+ "
                               f"consecutive source words; rewrite or discard before these enter the KB:", body))
        for f, idxs in flagged[:20]:
            story.append(Paragraph(f"• {f} items {idxs}", small))
    if not errs and not flagged:
        story.append(Paragraph("None recorded (errors and verbatim flags both empty).", body))
    story.append(Spacer(1, 14))

    if items and n_samples:
        story += [PageBreak(), Paragraph(f"Sample items (first {min(n_samples, len(items))}, verbatim from saved JSON)", h2)]
        for it in items[:n_samples]:
            src = it.get("source", {})
            story.append(Paragraph(f"<b>{it.get('topic','?')}</b> — {it.get('type','?')} · "
                                   f"{it.get('category','?')} · ch{src.get('chapter','?')} p{src.get('pages','?')}", body))
            story.append(Paragraph(it.get("definition", "") or it.get("core_idea", ""), body))
            for fm in it.get("formulas", []):
                story.append(Paragraph(f"Formula — {fm.get('name','')}: {fm.get('formula','')}", small))
            story.append(Paragraph(f"file: {it.get('_file','')} · source-vs-inference: "
                                   f"{it.get('author_states_vs_inference','not recorded')}", small))
            story.append(Spacer(1, 8))

    story += [Spacer(1, 14), Paragraph("Scope caveats (honest labels)", h2),
              Paragraph("This report covers Pass 1 (extraction) only. Validation against source "
                        "(Pass 2), chapter synthesis (Pass 3), global dedup/canonical concepts "
                        "(Pass 4), typed RAG chunks (Pass 5), and retrieval evaluation (Pass 6) "
                        "have NOT been run unless separately documented. Items are model-extracted "
                        "and unverified; formulas must be source-checked before entering the "
                        "production knowledge layer.", body)]
    return story


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", default="knowledge")
    ap.add_argument("--pdf-out", default="kb_report.pdf")
    ap.add_argument("--samples", type=int, default=5)
    args = ap.parse_args()

    kb = Path(args.kb)
    state, items, per_chapter, flagged = gather(kb)
    if not state.get("chunks") and not items:
        raise SystemExit(f"Nothing to report in {kb} — run kb_extract.py first.")

    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate
    doc = SimpleDocTemplate(args.pdf_out, pagesize=letter)
    doc.build(build_story(kb, state, items, per_chapter, flagged, args.samples))
    print(f"wrote {args.pdf_out}: {len(items)} items, "
          f"{sum(1 for v in state['chunks'].values() if v == 'done')} chunks done, "
          f"{len(flagged)} verbatim-flag files")


if __name__ == "__main__":
    main()
