# Progress — Book → KB Pass 1 extraction

Supervised. Max 10 iterations. ONE task = ONE commit. Verify fresh-eyes (marker≠maker). Never commit red;
same check ×3 = stop. Pause + report after every task. Engine=claude-cli (subscription). No app.py edits.

## Checklist
- [x] 0 — Setup: assembled kb/ from ~/Downloads/files(5) scripts + files(3) recipe; deps installed
      (pypdf 6.16.1, reportlab 5.0.1); book path confirmed with Mike; GOAL/PROGRESS written. ✔
- [x] 1 — PROBE. Auto-detect found 0 chapters (heuristic miss). Built kb/knowledge/chapters.json from
      the PDF's embedded outline (34 numbered sections 1.1-6.6, p18-610). Re-probe: map = TOC (manual-
      trusted), 129 chunks planned. 11/684 near-empty pages (1.6%) -> NOT scanned, no OCR. ⏸ STOP for go.
- [x] 2 — DRY-RUN: 129 chunks; read ch01 (prose) + ch14 (option pricing) previews. Coherent sections,
      chapter/page-tagged, paragraph-boundary (occasional mid-sentence prose split, NO mid-formula/table
      split seen), source tags correct. dry_run/ gitignored (raw verbatim book text — don't commit source).
- [ ] 3 — PILOT --max-chunks 5: real claude -p; marker-verify 5 JSONs (schema/rewritten/no-invented-
      formulas/source-tags/skip); report timing. ⏸ STOP for go.
- [ ] 4 — FULL RUN (explicit go): resumable; done/error counts; retry errored once.
- [ ] 5 — REPORT pdf: cross-check figures vs processing_state.json; caveat says Pass1/unvalidated.

## Append-only log
- setup (2026-08-21) — kb/ not in repo; found scripts across ~/Downloads/files(3,4,5) zips (all today).
  Canonical = files(5)/kb_extract.py (350L) + files(5)/kb_report.py (153L) + files(3)/KB_LOOP_RECIPE.md
  (only copy). Mike confirmed the book + pointed to these zips. Book:
  /Users/mikeoc/Downloads/_OceanofPDF.com_Energy_Trading_and_Investing_-_Davis_W_Edwards.pdf (27.6MB).
  Next: commit baseline, then T1 PROBE (pause for go).
