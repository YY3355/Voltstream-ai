#!/usr/bin/env python3
"""
kb_extract.py — Pass 1 of the VoltStream book->KB loop.

PDF (or .txt fixture) -> chapter map -> paragraph-boundary chunks ->
per-chunk Claude extraction (strict JSON schema) -> knowledge/raw/chNN/chunk_NNN.json
with a resumable processing_state.json written after EVERY chunk.

Modes (run in this order — do not skip straight to a full burn):
  --probe          no API calls: print detected chapter map + chunk counts + rough cost.
                   If chapter detection looks wrong, write chapters.json (see below) and re-probe.
  --dry-run        no API calls: writes chunk_*.txt previews so you can eyeball what
                   would be sent to the model.
  --max-chunks 5   PILOT: real API calls on the first 5 pending chunks only.
                   Human-review the JSON before authorizing the full run.
  (no flag)        full resumable run over all pending chunks.

Manual chapter override (recommended for real textbooks — auto-detection is a heuristic):
  chapters.json in --out dir:  [{"n": 1, "title": "...", "start_page": 9, "end_page": 34}, ...]
  (1-indexed PDF pages, inclusive.)

Env: ANTHROPIC_API_KEY required for non-probe/non-dry runs.

Honesty rules enforced in the extraction prompt:
  - rewrite in original language; never copy long passages (hard cap enforced post-hoc too)
  - never invent formulas/definitions not supported by the chunk
  - separate author claims from inference; keep qualifiers
  - every item tagged with chapter + page range for audit
  - a chunk with no substantive concepts returns {"skip": true} — that is a valid answer
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

MODEL = "claude-sonnet-4-6"
TARGET_CHUNK_CHARS = 9000        # ~2.2k tokens of book text per call
MAX_VERBATIM_WORDS = 25          # post-hoc guard: longest string copied verbatim from source
COST_PER_MTOK_IN = 3.00          # rough Sonnet pricing, $/M input tokens (estimate only)
COST_PER_MTOK_OUT = 15.00

SYSTEM_PROMPT = """You are extracting structured knowledge from a section of the textbook
"Energy Trading & Investing" (2nd ed., Davis Edwards) to build a retrieval knowledge base
for an ERCOT-focused energy analytics platform.

Return ONLY a JSON object, no markdown fences, no preamble. Schema:

{
  "skip": false,
  "items": [
    {
      "topic": "...",
      "category": "...",              // e.g. "Power Markets", "Natural Gas", "Risk", "Derivatives"
      "subcategory": "...",
      "type": "concept|formula|market_mechanic|trading_strategy|risk|definition|example",
      "definition": "...",            // your own words
      "core_idea": "...",             // your own words, 1-3 sentences
      "key_points": ["..."],
      "formulas": [                   // only if the source actually states one
        {"name": "...", "formula": "...", "variables": {"var": "units/meaning"}}
      ],
      "relationships": ["..."],
      "trading_implications": ["..."],
      "common_misunderstandings": ["..."],
      "author_states_vs_inference": "state clearly if any point is your inference rather than the author's claim, else \\"all from source\\"",
      "related_topics": ["..."],
      "source": {"chapter": <int>, "pages": "<start>-<end>", "section_hint": "..."}
    }
  ]
}

Hard rules:
- REWRITE everything in your own words. Never copy sentences from the source. Formulas and
  standard technical terms are fine verbatim; prose is not.
- NEVER invent a formula, number, or definition the source does not support. Omit rather than guess.
- Preserve qualifiers, exceptions, and caveats the author gives.
- Prefer several precise items over one giant summary. Typical chunk yields 1-6 items.
- If the chunk is front matter, exercises, an index, or otherwise has no extractable knowledge,
  return exactly {"skip": true, "items": []}.
"""


# ---------------------------------------------------------------- text loading

def load_pages(path: Path):
    """Return list of (page_number_1indexed, text)."""
    if path.suffix.lower() == ".txt":
        # fixture mode: pages separated by lines of form '=== PAGE N ==='
        pages, cur, n = [], [], 0
        for line in path.read_text().splitlines():
            m = re.match(r"^=== PAGE (\d+) ===$", line.strip())
            if m:
                if n:
                    pages.append((n, "\n".join(cur)))
                n, cur = int(m.group(1)), []
            else:
                cur.append(line)
        if n:
            pages.append((n, "\n".join(cur)))
        return pages
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    return [(i + 1, (pg.extract_text() or "")) for i, pg in enumerate(reader.pages)]


# ------------------------------------------------------------ chapter mapping

CHAPTER_RE = re.compile(r"^\s*(?:CHAPTER|Chapter)\s+(\d{1,2})\b[\s.:—-]*(.{0,80})", re.M)

def detect_chapters(pages):
    """Heuristic: first page on which 'Chapter N' appears near top of page text."""
    found = {}
    for pageno, text in pages:
        head = text[:400]
        m = CHAPTER_RE.search(head)
        if m:
            n = int(m.group(1))
            if n not in found:
                found[n] = {"n": n, "title": m.group(2).strip() or f"Chapter {n}",
                            "start_page": pageno}
    chapters = [found[k] for k in sorted(found)]
    for i, ch in enumerate(chapters):
        ch["end_page"] = (chapters[i + 1]["start_page"] - 1) if i + 1 < len(chapters) \
            else pages[-1][0]
    return chapters


def load_chapter_map(pages, outdir: Path):
    manual = outdir / "chapters.json"
    if manual.exists():
        chapters = json.loads(manual.read_text())
        src = "chapters.json (manual — trusted)"
    else:
        chapters = detect_chapters(pages)
        src = "auto-detected (HEURISTIC — verify with --probe before burning API calls)"
    return chapters, src


# ----------------------------------------------------------------- chunking

def chunk_chapter(pages, ch):
    """Paragraph-boundary chunks of ~TARGET_CHUNK_CHARS within [start_page, end_page]."""
    span = [(n, t) for n, t in pages if ch["start_page"] <= n <= ch["end_page"]]
    paras = []  # (page, paragraph_text)
    for n, t in span:
        for p in re.split(r"\n\s*\n", t):
            p = p.strip()
            if p:
                paras.append((n, p))
    chunks, cur, cur_pages, size = [], [], set(), 0
    for n, p in paras:
        if size + len(p) > TARGET_CHUNK_CHARS and cur:
            chunks.append({"pages": (min(cur_pages), max(cur_pages)), "text": "\n\n".join(cur)})
            cur, cur_pages, size = [], set(), 0
        cur.append(p); cur_pages.add(n); size += len(p)
    if cur:
        chunks.append({"pages": (min(cur_pages), max(cur_pages)), "text": "\n\n".join(cur)})
    return chunks


# ------------------------------------------------------------------ API call

def extract_chunk(client, ch, chunk, engine="claude-cli"):
    user = (f"Chapter {ch['n']} (\"{ch['title']}\"), pages {chunk['pages'][0]}-{chunk['pages'][1]}.\n"
            f"Source text:\n\n{chunk['text']}")
    if engine == "claude-cli":
        # runs on the Claude Code SUBSCRIPTION login — no console API key, no per-token bill.
        # Constraint instead: subscription rate-limit windows; state file makes reruns safe.
        prompt = SYSTEM_PROMPT + "\n\n" + user
        for attempt in (1, 2):
            r = subprocess.run(["claude", "-p", prompt, "--model", "sonnet"],
                               capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                raise RuntimeError(f"claude CLI rc={r.returncode}: {r.stderr[:300]}")
            text = re.sub(r"^```(?:json)?|```$", "", r.stdout.strip(), flags=re.M).strip()
            try:
                return json.loads(text), (0, 0)   # CLI exposes no token usage fields
            except json.JSONDecodeError:
                if attempt == 2:
                    raise
                prompt += "\n\nYour last output was not valid JSON. Return ONLY the JSON object."
        raise RuntimeError("unreachable")


def _extract_chunk_api(client, ch, chunk):
    user = (f"Chapter {ch['n']} (\"{ch['title']}\"), pages {chunk['pages'][0]}-{chunk['pages'][1]}.\n"
            f"Source text:\n\n{chunk['text']}")
    for attempt in (1, 2):
        resp = client.messages.create(
            model=MODEL, max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user}] if attempt == 1 else [
                {"role": "user", "content": user},
                {"role": "assistant", "content": "{"},
            ],
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        if attempt == 2:
            text = "{" + text
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
        try:
            data = json.loads(text)
            usage = (resp.usage.input_tokens, resp.usage.output_tokens)
            return data, usage
        except json.JSONDecodeError:
            if attempt == 2:
                raise
    raise RuntimeError("unreachable")


def verbatim_guard(data, source_text):
    """Flag items containing long verbatim runs from the source (copyright + rewrite rule)."""
    flat_src = re.sub(r"\s+", " ", source_text).lower()
    flags = []
    for i, item in enumerate(data.get("items", [])):
        prose = " ".join(str(v) for k, v in item.items()
                         if k in ("definition", "core_idea") ) + " " + \
                " ".join(item.get("key_points", []))
        words = re.sub(r"\s+", " ", prose).lower().split()
        for start in range(0, max(0, len(words) - MAX_VERBATIM_WORDS)):
            run = " ".join(words[start:start + MAX_VERBATIM_WORDS])
            if len(run) > 60 and run in flat_src:
                flags.append(i)
                break
    return flags


# --------------------------------------------------------------------- state

def load_state(outdir: Path):
    f = outdir / "processing_state.json"
    return json.loads(f.read_text()) if f.exists() else {"chunks": {}, "usage": {"in": 0, "out": 0}}

def save_state(outdir: Path, state):
    tmp = outdir / "processing_state.json.tmp"
    tmp.write_text(json.dumps(state, indent=1))
    tmp.replace(outdir / "processing_state.json")


# ---------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, help="book PDF (or .txt fixture with === PAGE N === markers)")
    ap.add_argument("--out", default="knowledge", help="output dir")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-chunks", type=int, default=0, help="pilot cap on API chunks this run")
    ap.add_argument("--chapter", type=int, default=0, help="restrict to one chapter")
    ap.add_argument("--engine", choices=["claude-cli", "api"], default="claude-cli",
                    help="claude-cli = your Claude Code subscription login (default); api = console key, per-token billing")
    args = ap.parse_args()

    src = Path(args.pdf)
    outdir = Path(args.out); outdir.mkdir(parents=True, exist_ok=True)
    pages = load_pages(src)
    if not pages:
        sys.exit("No pages extracted — scanned/image PDF? Needs OCR first; do not proceed.")
    empty = sum(1 for _, t in pages if len(t.strip()) < 40)
    chapters, ch_src = load_chapter_map(pages, outdir)
    if args.chapter:
        chapters = [c for c in chapters if c["n"] == args.chapter]

    plan = []
    for ch in chapters:
        for j, chunk in enumerate(chunk_chapter(pages, ch)):
            plan.append((ch, j, chunk))

    est_in = sum(len(c["text"]) for _, _, c in plan) / 4 + len(plan) * 700  # chars/4 + prompt overhead
    est_out = len(plan) * 1500
    est_cost = est_in / 1e6 * COST_PER_MTOK_IN + est_out / 1e6 * COST_PER_MTOK_OUT

    print(f"pages: {len(pages)}  (near-empty text on {empty} — if large, PDF may be scanned)")
    print(f"chapter map [{ch_src}]:")
    for ch in chapters:
        print(f"  ch{ch['n']:>2}  p{ch['start_page']}-{ch['end_page']}  {ch['title'][:60]}")
    print(f"chunks planned: {len(plan)}   ROUGH cost estimate: ~${est_cost:,.2f} "
          f"(estimate, not a quote — verify on the pilot run)")

    if args.probe:
        return

    state = load_state(outdir)

    if args.dry_run:
        dd = outdir / "dry_run"; dd.mkdir(exist_ok=True)
        for ch, j, chunk in plan[:20]:
            (dd / f"ch{ch['n']:02d}_chunk{j:03d}.txt").write_text(
                f"# would send: ch{ch['n']} p{chunk['pages'][0]}-{chunk['pages'][1]}\n\n{chunk['text']}")
        print(f"dry-run previews written to {dd} (first 20 chunks). No API calls made.")
        return

    client = None
    if args.engine == "api":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit("--engine api needs ANTHROPIC_API_KEY (or use default --engine claude-cli).")
        import anthropic
        client = anthropic.Anthropic()
    state["engine"] = args.engine

    done_this_run = 0
    for ch, j, chunk in plan:
        cid = f"ch{ch['n']:02d}_chunk{j:03d}"
        if state["chunks"].get(cid) == "done":
            continue
        if args.max_chunks and done_this_run >= args.max_chunks:
            print(f"pilot cap reached ({args.max_chunks}). Review outputs before the full run.")
            break
        try:
            if args.engine == "api":
                data, (tin, tout) = _extract_chunk_api(client, ch, chunk)
            else:
                data, (tin, tout) = extract_chunk(client, ch, chunk, engine="claude-cli")
        except Exception as e:
            state["chunks"][cid] = f"error: {type(e).__name__}: {e}"[:200]
            save_state(outdir, state)
            print(f"  {cid}  ERROR {e} — recorded, continuing")
            continue
        flags = verbatim_guard(data, chunk["text"])
        if flags:
            data["_verbatim_flags"] = flags  # kept, flagged for human review — not silently accepted
        chdir = outdir / "raw" / f"ch{ch['n']:02d}"; chdir.mkdir(parents=True, exist_ok=True)
        (chdir / f"chunk_{j:03d}.json").write_text(json.dumps(data, indent=1))
        state["chunks"][cid] = "done"
        state["usage"]["in"] += tin; state["usage"]["out"] += tout
        save_state(outdir, state)
        done_this_run += 1
        n_items = len(data.get("items", []))
        print(f"  {cid}  done  items={n_items}"
              + ("  SKIP" if data.get("skip") else "")
              + (f"  VERBATIM-FLAGS={flags}" if flags else ""))
        time.sleep(0.5)

    done = sum(1 for v in state["chunks"].values() if v == "done")
    errs = sum(1 for v in state["chunks"].values() if str(v).startswith("error"))
    if state.get("engine") == "api" or state["usage"]["in"]:
        cost = state["usage"]["in"] / 1e6 * COST_PER_MTOK_IN + state["usage"]["out"] / 1e6 * COST_PER_MTOK_OUT
        spend = f"token spend ≈ ${cost:,.2f} (from API usage fields)"
    else:
        spend = "spend: subscription (claude-cli) — not metered per token; rate-limit window is the constraint"
    print(f"\nstate: {done}/{len(plan)} chunks done, {errs} errors, {spend}")


if __name__ == "__main__":
    main()
