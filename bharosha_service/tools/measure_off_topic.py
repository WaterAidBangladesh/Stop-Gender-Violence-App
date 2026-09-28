"""Measures where off-topic input sits, to set chain.OFF_TOPIC_DISTANCE.

    python tools/measure_off_topic.py

WHAT THIS NUMBER IS NOT. It is not a gate. Nothing is admitted or rejected by
it: everything it separates has already been rejected by RELEVANCE_FLOOR, and
the retrieval behaviour is identical whatever value it takes. It only decides
which of two refusals a person reads —

    the full no-context reply, for a question that belongs here and missed:
        honest, says what the corpus does hold, gives two helplines;
    one line, for a question about something else entirely.

So the cost of getting it wrong is tone, not safety, and it can be set by
looking at the two distributions rather than by biasing toward one error the way
the relevance floor is.

WHY IT EXISTS. Both groups were getting the crisis-weight reply, which made the
app sound like it could not tell a recipe from a disclosure.

English only, and deliberately: a Bangla query is translated to English before
it is embedded, so the distance being measured is the distance of its English
translation, and the boundary is the same one.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import chain  # noqa: E402

# Real questions about this subject that the corpus may or may not hold. These
# must get the full reply when they miss — they are the app's own subject, and
# answering them with "that's outside what I know about" would be a lie.
ON_TOPIC = [
    "what is safeguarding",
    "what counts as economic violence",
    "how can violence be prevented in a community",
    "what are the myths about gender based violence",
    "who is responsible for safeguarding",
    "what support exists for survivors in Bangladesh",
    "how do I make a safeguarding complaint",
    "what is a safeguarding focal point",
    "what does consent mean",
    "what is workplace sexual harassment",
    "how do I know if a relationship is abusive",
    "what happens after I call a helpline",
    "what is victim blaming",
    "how does violence affect children who witness it",
    "what is a safe space",
    "what is the difference between harassment and abuse",
    "how can men help prevent violence against women",
    "what is stalking",
    "what is online harassment",
    "what is trafficking",
]

# Nothing to do with this app. These must get one line.
OFF_TOPIC = [
    "how do I cook rice",
    "what is the weather today",
    "who won the cricket match",
    "how do I fix my phone screen",
    "what is the capital of France",
    "tell me a joke",
    "how do I get a passport",
    "what time does the bank open",
    "how do I install this app on iPhone",
    "recommend a good restaurant in Dhaka",
    "what is the price of rice",
    "how do I learn English",
    "write me a poem",
    "what is 2 plus 2",
    "how do I apply for a job at WaterAid",
    "when is the next public holiday",
    "how do I open a bank account",
    "what is photosynthesis",
]


def nearest(query: str) -> float:
    found = chain.search(query, n_results=1)
    return found[0].distance if found else 1.0


def main() -> int:
    chain.load()

    on = sorted((nearest(q), q) for q in ON_TOPIC)
    off = sorted((nearest(q), q) for q in OFF_TOPIC)

    print(f"\nrelevance floor (the actual gate) : {chain.RELEVANCE_FLOOR}")
    print(f"off-topic distance (tier only)    : {chain.OFF_TOPIC_DISTANCE}\n")

    print("ON TOPIC — must get the full no-context reply when they miss")
    for distance, query in on:
        gated = "answered" if distance <= chain.RELEVANCE_FLOOR else "missed"
        print(f"  {distance:.3f}  [{gated:8}]  {query}")

    print("\nOFF TOPIC — must get one line")
    for distance, query in off:
        print(f"  {distance:.3f}  {query}")

    missed = [d for d, _ in on if d > chain.RELEVANCE_FLOOR]
    worst_on = max(missed) if missed else None
    best_off = min(d for d, _ in off)

    print("\n--- boundary ---")
    print(f"  on-topic questions that missed the gate : {len(missed)}/{len(on)}")
    if worst_on is not None:
        print(f"  furthest on-topic miss                  : {worst_on:.3f}")
    print(f"  nearest off-topic question              : {best_off:.3f}")

    if worst_on is None:
        print("\n  Every on-topic question was answered, so the tier is")
        print("  unconstrained from that side. Set it just below the nearest")
        print(f"  off-topic question: {best_off:.3f}")
    elif worst_on < best_off:
        midpoint = (worst_on + best_off) / 2
        print(f"\n  They separate. Midpoint: {midpoint:.3f}")
        print(f"  Suggested OFF_TOPIC_DISTANCE: {midpoint:.2f}")
    else:
        print("\n  THEY OVERLAP. No single value separates them, so pick the")
        print("  error you prefer: below the overlap sends some real questions")
        print("  the short reply, above it sends some trivia the long one.")
        print("  Prefer the long one — telling someone her question is off")
        print("  topic when it is not is the worse of the two.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
