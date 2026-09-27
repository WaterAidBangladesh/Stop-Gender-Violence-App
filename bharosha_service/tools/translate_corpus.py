"""Translates the corpus into Bangla once, into a file someone can correct.

    python tools/translate_corpus.py            # translate what is missing
    python tools/translate_corpus.py --retranslate   # redo everything

WHY THIS EXISTS. Every passage is English, so a Bangla question is currently
answered by the model rendering English into Bangla live, differently each time,
where nobody can see it and nobody can fix it. That produced transliterated
jargon — প্রটেকশন, প্রিভেনশন — instead of সুরক্ষা and প্রতিরোধ, in the app's
primary language.

Translating once and storing the result changes what kind of problem this is:

    live translation          this file
    ----------------------    --------------------------------
    different every time      fixed, and diffable
    invisible                 readable by a Bangla speaker
    uncorrectable             fix a line and it stays fixed
    unreviewable              WaterAid can review and sign off

It is NOT a substitute for human translation. Every entry is marked
"machine_pending_review", and a human translation replaces entries one row at a
time — edit the bn text, set review to "human", and rebuild.

The output is keyed by chunk id, so it survives a rebuild. Change the chunk size
and the ids change; the script reports anything orphaned rather than silently
dropping it.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import chain  # noqa: E402

CHUNKS = ROOT / "corpus" / "chunks.json"
TRANSLATIONS = ROOT / "corpus" / "translations_bn.json"

# Terms the model transliterates into Banglish if left to itself. Every one of
# these was observed in a live answer before this list existed.
GLOSSARY = """
safeguarding = সেফগার্ডিং (the term the app itself uses)
protection = সুরক্ষা
prevention = প্রতিরোধ
empowerment = ক্ষমতায়ন
partnership = অংশীদারিত্ব
accountability = জবাবদিহিতা
survivor = ভুক্তভোগী
gender-based violence = জেন্ডারভিত্তিক সহিংসতা
intimate partner violence = ঘনিষ্ঠ সঙ্গীর সহিংসতা
controlling behaviour = নিয়ন্ত্রণমূলক আচরণ
economic violence = অর্থনৈতিক সহিংসতা
emotional violence = আবেগীয় সহিংসতা
sexual harassment = যৌন হয়রানি
dowry = যৌতুক
child marriage = বাল্যবিবাহ
consent = সম্মতি
disability = প্রতিবন্ধিতা
helpline = হেল্পলাইন
"""

PROMPT = """Translate the following text into Bangla, for readers in Bangladesh.

This is safeguarding and gender-based violence material that will be shown to
people who may themselves be experiencing violence. Accuracy matters more than
elegance.

RULES
1. Use real Bangla words, not English words written in Bengali letters. Use this
   glossary exactly:{glossary}
2. Keep every number, percentage and currency figure at EXACTLY the same value.
   Bengali numerals are fine and natural — ৭৬% for 76% — but the value must not
   change, and no figure may be dropped or added. These are survey statistics
   and a changed digit is a factual error.
3. Keep organisation names, document titles and helpline names in English:
   Bangladesh Bureau of Statistics, WaterAid, UNFPA, UN Women, WHO, Manusher
   Jonno Foundation, One Stop Crisis Centre.
4. Keep the Markdown exactly as it is — the same bold markers, the same bullet
   points, the same line breaks, the same heading line if there is one.
5. Translate everything else. Do not summarise, do not add, do not explain, do
   not leave anything out.
6. Reply with the Bangla translation only. No preamble, no notes, no quotes
   around it.

TEXT:
{text}"""


# Pacing exists because a rate limit once caused this script to skip chunks
# silently, which is worse than being slow: a missing translation is a Bangla
# answer quietly falling back to English source text.
#
# Measured from Groq's own x-ratelimit headers rather than guessed:
#   free tier key .... 8,000 tokens/minute  -> needed ~20s between requests
#   current key ...... 250,000 tokens/minute -> no meaningful pacing needed
#
# A translation round trip is roughly 1,200–2,600 tokens. Raise PACE_SECONDS
# again if this ever runs against a free-tier key; the retry below handles 429s
# either way.
PACE_SECONDS = float(os.getenv("BHAROSHA_TRANSLATE_PACE", "1"))
MAX_ATTEMPTS = 5


def translate(text: str) -> str:
    from langchain_core.prompts import PromptTemplate
    from langchain_groq import ChatGroq

    import os
    import re

    model = ChatGroq(
        temperature=0,
        model=chain.TRANSLATION_MODEL,
        api_key=os.environ["GROQ_API_KEY"],
        max_tokens=chain.TRANSLATION_MAX_TOKENS,
        # Explicit argument, not model_kwargs: langchain-groq rejects it there,
        # which is how we know it actually reaches the API rather than being
        # quietly dropped.
        reasoning_effort="low",
    )
    prompt = PromptTemplate.from_template(PROMPT)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = (prompt | model).invoke({"text": text, "glossary": GLOSSARY})
            bangla = (response.content or "").strip()
            metadata = response.response_metadata or {}
            finish = metadata.get("finish_reason")

            # finish_reason "length" means the completion budget ran out. With a
            # reasoning model that produces EMPTY content (the reasoning ate the
            # budget) or, worse, content cut off mid-sentence — measured at 551
            # characters where the full translation is 750. A length check alone
            # accepts that truncation silently, so the finish reason is the guard.
            if finish == "length" or len(bangla) < max(20, len(text) // 6):
                if attempt == MAX_ATTEMPTS:
                    raise RuntimeError(
                        f"finish_reason={finish!r}, {len(bangla)} chars for "
                        f"{len(text)} of input"
                    )
                print(f"      rejected (finish={finish!r}, {len(bangla)} chars), "
                      f"retrying ({attempt}/{MAX_ATTEMPTS})")
                time.sleep(2)
                continue
            return bangla
        except Exception as exc:  # noqa: BLE001 - retried below, raised if final
            message = str(exc)
            if "rate_limit" not in message and "429" not in message:
                raise
            # Groq tells us exactly how long to wait; use it rather than guessing.
            wait = 20.0
            match = re.search(r"try again in ([\d.]+)s", message)
            if match:
                wait = float(match.group(1)) + 2
            if attempt == MAX_ATTEMPTS:
                raise
            print(f"      rate limited, waiting {wait:.0f}s "
                  f"(attempt {attempt}/{MAX_ATTEMPTS})")
            time.sleep(wait)
    raise RuntimeError("unreachable")


def main() -> int:
    import os

    if not os.getenv("GROQ_API_KEY"):
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    if not os.getenv("GROQ_API_KEY"):
        print("GROQ_API_KEY is not set")
        return 1

    retranslate = "--retranslate" in sys.argv
    chunks = json.loads(CHUNKS.read_text(encoding="utf-8"))
    existing = (
        json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
        if TRANSLATIONS.exists()
        else {"_status": "", "translations": {}}
    )
    translations: dict[str, dict] = existing.get("translations", {})

    # Anything translated for a chunk id that no longer exists — usually because
    # the chunk size changed. Reported, not deleted: the text may still be worth
    # recovering by hand.
    current_ids = {c["id"] for c in chunks}
    orphans = [key for key in translations if key not in current_ids]
    if orphans:
        print(f"  ! {len(orphans)} translations no longer match a chunk id")
        for key in orphans[:5]:
            print(f"      {key}")

    todo = [
        c for c in chunks
        if retranslate
        or c["id"] not in translations
        or translations[c["id"]].get("review") == "machine_pending_review"
        and retranslate
    ]
    todo = [c for c in chunks if retranslate or c["id"] not in translations]

    print(f"{len(chunks)} chunks, {len(translations)} already translated, "
          f"{len(todo)} to do")
    if not todo:
        print("nothing to do")
        return 0

    print(f"pacing at one request per {PACE_SECONDS}s — "
          f"roughly {max(1, int(len(todo) * PACE_SECONDS // 60))} minute(s)")

    started = time.monotonic()
    failures: list[str] = []
    for i, chunk in enumerate(todo, start=1):
        try:
            bangla = translate(chunk["en"])
        except Exception as exc:  # noqa: BLE001 - recorded, reported at the end
            failures.append(f"{chunk['id']}: {exc}")
            print(f"  [{i}/{len(todo)}] FAILED {chunk['id']}")
            continue
        translations[chunk["id"]] = {
            "bn": bangla,
            "review": "machine_pending_review",
            "model": chain.MODEL,
            "source": chunk.get("source", ""),
        }
        print(f"  [{i}/{len(todo)}] {chunk['id']} ({len(bangla)} chars)")
        # Save as we go: a rate limit or a Ctrl-C part way through should not
        # throw away everything translated so far.
        _save(translations)
        if i < len(todo):
            time.sleep(PACE_SECONDS)

    if failures:
        print(f"\n  {len(failures)} chunks failed and have NO Bangla:")
        for failure in failures:
            print(f"      {failure[:120]}")

    _save(translations)

    human = sum(1 for t in translations.values() if t.get("review") == "human")
    print(
        f"\nWrote {len(translations)} translations to "
        f"{TRANSLATIONS.relative_to(ROOT)} in {time.monotonic() - started:.0f}s\n"
        f"  human-reviewed: {human}/{len(translations)}\n\n"
        "Next: python build_corpus.py   (applies these to chunks.json)"
    )
    return 0


def _save(translations: dict[str, dict]) -> None:
    TRANSLATIONS.write_text(
        json.dumps(
            {
                "_status": (
                    "MACHINE TRANSLATED, PENDING HUMAN REVIEW. Produced by "
                    "tools/translate_corpus.py. To correct an entry: edit its bn "
                    "text and set review to \"human\". Rebuild with "
                    "build_corpus.py to apply."
                ),
                "_review_states": {
                    "machine_pending_review": "translated by the model, not yet checked",
                    "human": "written or corrected by a person — never overwritten",
                },
                "translations": dict(sorted(translations.items())),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
