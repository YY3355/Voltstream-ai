"""
kb_validate.py — KB Pass 2: independent validation of Pass-1 items (the extracting model is NOT the
final authority). Deterministic-first (high-precision, low-recall) + a claude -p judge ONLY on flags.
Annotates `_validation` in place + writes validation_state.json (resumable). NEVER edits/deletes content.

Per item:
  pages_ok           deterministic: claimed pages fall inside the item's chapter span AND >=half the
                     topic's key terms appear on those pages.
  formula_in_source  deterministic: every formula's signature tokens (words>=3 chars + numbers, after
                     aggressive normalization) appear in the source-page text. None if the item has no
                     formulas. PASS = provisionally trusted; FAIL = a review candidate, never a verdict.
  judge_verdict      claude -p, ONLY when a deterministic check FAILS: SUPPORTED | UNSUPPORTED | UNCLEAR
                     (three-way so it never guesses) + a one-line reason. The judge is told to NEVER
                     rewrite a formula to make it match — a mismatch is a flag, full stop.

Rules: validation never edits/fixes/deletes knowledge; UNSUPPORTED items stay, marked untrusted.

CLI:
    python kb_validate.py --kb kb/knowledge --pdf <book> [--chapter N] [--engine claude-cli]
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

JUDGE_SYSTEM = (
    "You are an independent fact-checker for a knowledge base built from a book. You are given ONE "
    "extracted knowledge item and the EXACT source-page text it claims to come from. Decide whether the "
    "item's claims and any formulas are SUPPORTED by that source text.\n"
    "Rules: (1) Return ONLY a JSON object {\"verdict\": \"SUPPORTED\"|\"UNSUPPORTED\"|\"UNCLEAR\", "
    "\"reason\": \"<one line>\"}. (2) Use UNCLEAR when the text is insufficient to decide — never guess. "
    "(3) NEVER rewrite or 'fix' a formula to make it match; if a formula is not clearly present/derivable "
    "in the source text, that is UNSUPPORTED (or UNCLEAR), not SUPPORTED. (4) Rewritten prose is fine as "
    "long as the substance is supported; you are checking substance, not wording."
)


def load_pages(pdf_path):
    return {i + 1: (pg.extract_text() or "") for i, pg in enumerate(PdfReader(pdf_path).pages)}


def norm(s):
    s = str(s).lower()
    for a, b in (("×", "*"), ("·", "*"), ("∗", "*"), ("÷", "/"), ("–", "-"), ("—", "-"), ("−", "-")):
        s = s.replace(a, b)
    return re.sub(r"[,\s]", "", s)                      # drop commas + all whitespace


def sig_tokens(formula_str):
    """Signature tokens of a formula: numbers, and words of >=3 chars (operators/short vars dropped)."""
    toks = re.findall(r"[a-z0-9.]+", str(formula_str).lower())
    return [t for t in toks if any(c.isdigit() for c in t) or len(t) >= 3]


def parse_pages(pgs):
    m = re.findall(r"\d+", str(pgs))
    return (int(m[0]), int(m[-1])) if m else None


def page_text(pages, a, b):
    return "\n".join(pages.get(p, "") for p in range(a, b + 1))


def check_pages_ok(item, chapters, pages):
    src = item.get("source", {})
    pr = parse_pages(src.get("pages"))
    ch = src.get("chapter")
    if not pr or ch is None:
        return False
    chap = next((c for c in chapters if c["n"] == ch), None)
    if not chap or not (chap["start_page"] <= pr[0] and pr[1] <= chap["end_page"]):
        return False
    txt = norm(page_text(pages, pr[0], pr[1]))
    terms = set(re.findall(r"[a-z]{4,}", item.get("topic", "").lower()))
    if not terms:
        return True
    hits = sum(1 for w in terms if w in txt)
    return hits >= max(1, len(terms) // 2)             # >= half the topic's key terms present


def check_formula_in_source(formula_str, src_norm):
    toks = sig_tokens(formula_str)
    return all(t in src_norm for t in toks) if toks else True


def judge(item, source_text):
    """claude -p three-way verdict on a flagged item. Returns (verdict, reason)."""
    payload = {k: item.get(k) for k in ("topic", "type", "definition", "core_idea", "key_points",
                                        "formulas", "source") if k in item}
    prompt = (JUDGE_SYSTEM + "\n\nITEM:\n" + json.dumps(payload, indent=1)
              + "\n\nSOURCE PAGES (verbatim):\n" + source_text[:12000])
    for attempt in (1, 2):
        r = subprocess.run(["claude", "-p", prompt, "--model", "sonnet"],
                           capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise RuntimeError(f"claude CLI rc={r.returncode}: {r.stderr[:200]}")
        text = re.sub(r"^```(?:json)?|```$", "", r.stdout.strip(), flags=re.M).strip()
        try:
            d = json.loads(text)
            v = str(d.get("verdict", "")).upper()
            if v not in ("SUPPORTED", "UNSUPPORTED", "UNCLEAR"):
                v = "UNCLEAR"
            return v, str(d.get("reason", ""))[:200]
        except json.JSONDecodeError:
            if attempt == 2:
                return "UNCLEAR", "judge returned non-JSON twice"
            prompt += "\n\nReturn ONLY the JSON object."
    return "UNCLEAR", "unreachable"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", required=True)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--chapter", type=int, help="validate only this chapter n (pilot)")
    ap.add_argument("--engine", choices=["claude-cli"], default="claude-cli")
    a = ap.parse_args()

    kb = Path(a.kb)
    chapters = json.loads((kb / "chapters.json").read_text())
    pages = load_pages(a.pdf)
    state_path = kb / "validation_state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {"items": {}}

    files = sorted((kb / "raw").glob("ch*/chunk_*.json"))
    counts = {"pass": 0, "judged": 0, "SUPPORTED": 0, "UNSUPPORTED": 0, "UNCLEAR": 0, "skip_item": 0}
    for f in files:
        data = json.loads(f.read_text())
        if data.get("skip"):
            continue
        dirty = False
        for idx, item in enumerate(data.get("items", [])):
            ch = item.get("source", {}).get("chapter")
            if a.chapter and ch != a.chapter:
                continue
            key = f"{f.parent.name}/{f.name}#{idx}"
            if "_validation" in item and state["items"].get(key):        # resumable: already done
                continue
            pr = parse_pages(item.get("source", {}).get("pages")) or (0, -1)
            src_text = page_text(pages, pr[0], pr[1])
            src_n = norm(src_text)
            pages_ok = check_pages_ok(item, chapters, pages)
            forms = item.get("formulas", [])
            f_in_src = None if not forms else all(check_formula_in_source(x.get("formula", ""), src_n)
                                                  for x in forms)
            flagged = (pages_ok is False) or (f_in_src is False)
            verdict, reason = None, "deterministic pass (provisional)"
            if flagged:
                verdict, reason = judge(item, src_text)
                counts["judged"] += 1
                counts[verdict] += 1
            else:
                counts["pass"] += 1
            item["_validation"] = {"formula_in_source": f_in_src, "pages_ok": pages_ok,
                                   "judge_verdict": verdict, "judge_reason": reason,
                                   "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            state["items"][key] = {"pages_ok": pages_ok, "formula_in_source": f_in_src,
                                   "judge_verdict": verdict, "has_formula": bool(forms)}
            dirty = True
        if dirty:
            f.write_text(json.dumps(data, indent=1))
            state_path.write_text(json.dumps(state, indent=1))
    print(f"validated: {sum(1 for _ in state['items'])} items tracked | this run: "
          f"det-pass={counts['pass']} judged={counts['judged']} "
          f"(SUPPORTED={counts['SUPPORTED']} UNSUPPORTED={counts['UNSUPPORTED']} UNCLEAR={counts['UNCLEAR']})")
    print("validation never edits content; UNSUPPORTED/UNCLEAR items stay in the KB, marked untrusted.")


if __name__ == "__main__":
    main()
