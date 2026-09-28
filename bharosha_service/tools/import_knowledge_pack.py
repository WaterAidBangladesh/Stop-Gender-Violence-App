"""Imports the Bhorosha Knowledge Base Pack into corpus/knowledge_pack.json.

    python tools/import_knowledge_pack.py

WHAT THE PACK IS. 459 question-and-answer pairs and 1,684 documents, written in
English and Bangla together, each with source URLs, a self-assessed confidence,
and a flag for whether it still needs expert review. It is the first corpus
material that matches how people actually ask, and the first with real Bangla
rather than machine translation.

FOUR THINGS THIS IMPORTER DOES, each because of a rule already enforced in code:

1. FILTERS BY REVIEW STATUS. Only rows marked in_chatbot=Yes, confidence=high
   and needs_expert_review=No are imported by default — 206 of 459. The rest are
   not rejected, they are waiting for WaterAid. Widen with --include-unreviewed
   once that review happens.

2. EXCLUDES LEGAL CATEGORIES. safety.py refuses legal questions before retrieval
   ever runs, so 43% of the pack is currently unreachable by design. Indexing it
   anyway would let legal claims surface inside answers to general questions,
   which is the same rule broken by a side door. The pack's own approach —
   general legal information plus a disclaimer plus a referral — is arguably
   better, but changing that is a decision for WaterAid, not for an importer.
   --include-legal turns it on the day they say yes.

3. STRIPS PHONE NUMBERS from the answer text. 317 of 459 answers name helplines
   inline. The model is forbidden from writing numbers so that a wrong digit is
   structurally impossible, and referral numbers are appended afterwards from
   referrals.py. Removing them at ingest keeps that guarantee without losing the
   meaning of a sentence.

4. ADDS THE QUESTION AND ITS VARIATIONS to the embedded text. This is what makes
   retrieval work for real phrasings: the corpus then contains questions, not
   only answers, so "what if my boss touches me" has something to match. Only
   Latin-script variations are embedded — the retrieval model is English-only.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT.parent / "knowledge_pack" / "Bhorosha_Knowledge_Base"
OUT = ROOT / "corpus" / "knowledge_pack.json"

INCLUDE_UNREVIEWED = "--include-unreviewed" in sys.argv
INCLUDE_LEGAL = "--include-legal" in sys.argv

LEGAL_CATEGORIES = {"Justice Process"}
LEGAL_PREFIX = "Law:"

# Numbers the pack names inline. Removed from indexed text, not from the app:
# referrals.py still gives every one of them to the user, in the footer and in
# every hardcoded safety reply.
PHONE = re.compile(
    r"\b(?:999|109|1098|333|16263|16430|16699|10921|16135|16670|"
    r"01[3-9]\d{8}|01[3-9]\d{2}-?\d{6}|\+?8801\d{9})\b"
)
BENGALI = re.compile(r"[ঀ-৿]")


def strip_numbers(text: str) -> str:
    """Remove helpline digits, leaving the sentence readable.

    "call 109 for help" becomes "call the national helpline for help" rather
    than "call for help", so the passage still says what it meant.
    """
    cleaned = PHONE.sub("the helpline", text)
    # Tidy the artefacts that leaves: "the helpline: the helpline" and similar.
    cleaned = re.sub(r"(the helpline[ :,-]*){2,}", "the helpline ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def latin_variations(raw: str) -> list[str]:
    """The English and romanised ways people ask the same thing.

    Bangla variations are skipped: they go to the Bangla side for generation,
    but embedding them would put Bangla into an English-only index.
    """
    out = []
    for part in (raw or "").split("|"):
        phrase = part.strip()
        if phrase and not BENGALI.search(phrase):
            out.append(phrase)
    return out


def main() -> int:
    if not PACK.exists():
        print(f"pack not found at {PACK}")
        return 1

    with (PACK / "bhorosha_qa_pairs.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    entries, skipped = [], {"in_chatbot": 0, "review": 0, "legal": 0, "no_bangla": 0}
    for row in rows:
        category = row["category"]
        is_legal = category in LEGAL_CATEGORIES or category.startswith(LEGAL_PREFIX)

        if row["in_chatbot"] != "Yes":
            skipped["in_chatbot"] += 1
            continue
        if is_legal and not INCLUDE_LEGAL:
            skipped["legal"] += 1
            continue
        if not INCLUDE_UNREVIEWED and (
            row["confidence"] != "high" or row["needs_expert_review"] != "No"
        ):
            skipped["review"] += 1
            continue
        if not row.get("answer_bn", "").strip():
            skipped["no_bangla"] += 1
            continue

        question = row["question_en"].strip()
        variations = latin_variations(row["other_ways_people_ask"])
        answer_en = strip_numbers(row["answer_en"].strip())
        answer_bn = strip_numbers(row["answer_bn"].strip())

        # The embedded side leads with the question and its variations, so a
        # user's phrasing has something of the same shape to match.
        embedded = question
        if variations:
            embedded += "\n(" + " / ".join(variations[:6]) + ")"
        embedded += "\n\n" + answer_en

        sources = [s.strip() for s in row["source_urls"].split("|") if s.strip()]
        entries.append(
            {
                "id": f"kb-{row['id']}",
                "en": embedded,
                # Generation reads this when the user wrote in Bangla: written
                # Bangla from the pack, not a machine rendering of English.
                "bn": f"{row['question_bn'].strip()}\n\n{answer_bn}"
                if row.get("question_bn", "").strip()
                else answer_bn,
                "source": f"Bhorosha Knowledge Base — {category}",
                "url": sources[0] if sources else None,
                "all_sources": sources,
                "category": category,
                "urgency": row["urgency"],
                "confidence": row["confidence"],
                "origin": "knowledge_pack_pending_review",
            }
        )

    OUT.write_text(
        json.dumps(
            {
                "_status": (
                    "Imported from the Bhorosha Knowledge Base Pack. Every entry "
                    "keeps its category, confidence and source URLs. Phone numbers "
                    "are stripped from the text on purpose — referrals.py is the "
                    "only source of those. Regenerate with "
                    "tools/import_knowledge_pack.py."
                ),
                "_filters": {
                    "in_chatbot": "Yes",
                    "confidence": "high" if not INCLUDE_UNREVIEWED else "any",
                    "needs_expert_review": "No" if not INCLUDE_UNREVIEWED else "any",
                    "legal_categories": "included" if INCLUDE_LEGAL else "excluded",
                },
                "entries": entries,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    bangla = sum(1 for e in entries if e["bn"])
    print(f"imported {len(entries)}/{len(rows)} Q&A pairs -> {OUT.name}")
    print(f"  with Bangla written by the pack: {bangla}/{len(entries)}")
    print(f"  skipped: {skipped}")
    print("\n  categories:")
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry["category"]] = counts.get(entry["category"], 0) + 1
    for category, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"    {count:>4}  {category}")
    print("\nNext: python build_corpus.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
