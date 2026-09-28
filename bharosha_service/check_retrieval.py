"""Measures the relevance gate.

    python check_retrieval.py              # as the service runs today
    python check_retrieval.py --proxy      # perfect-translation upper bound
    python check_retrieval.py --translate   # real Groq translation (needs a key)

The gate is a cosine-distance threshold. The only question that matters is
whether genuine questions and off-topic ones occupy separate distance ranges. If
they do not, no threshold works, and the honest outcome is to report the numbers.

Both query sets are twinned English/Bangla, which is what makes the translation
question measurable:

* --proxy scores each Bangla query's English twin instead of the Bangla text.
  A faithful translation would produce roughly that twin, so this is the best
  case the translation approach could reach — an upper bound, not a measurement
  of any translator.
* --translate runs the real thing: chain.to_english() via Groq, then embeds the
  result. That is the number to trust, and it needs GROQ_API_KEY.
"""

from __future__ import annotations

import functools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "app"))

import chain  # noqa: E402
import embedding  # noqa: E402
import safety  # noqa: E402

# (English, Bangla) twins of the same question.
PAIRS: list[tuple[str, str]] = [
    ("What is safeguarding?", "সেফগার্ডিং কী?"),
    ("What is gender-based violence?", "জেন্ডারভিত্তিক সহিংসতা কী?"),
    ("Who is responsible for safeguarding?", "সেফগার্ডিংয়ের দায়িত্ব কার?"),
    ("How can gender-based violence be prevented?", "জেন্ডারভিত্তিক সহিংসতা কীভাবে প্রতিরোধ করা যায়?"),
    ("Is violence against women a private family matter?",
     "নারীর প্রতি সহিংসতা কি পরিবারের ব্যক্তিগত বিষয়?"),
    ("What are the core principles of safeguarding?", "সুরক্ষার মূল নীতিগুলো কী?"),
    ("What counts as economic violence?", "অর্থনৈতিক সহিংসতা কী?"),
    # Moved here from the controls when the knowledge pack arrived. It was never
    # off-topic — the pack deliberately includes grounding and breathing
    # techniques for exactly this, and retrieval finds them. A control that the
    # corpus legitimately covers is a stale control, not a leak.
    ("I feel anxious all the time", "আমি সব সময় দুশ্চিন্তায় থাকি"),
    ("How can I calm down when I panic?", "আতঙ্কিত হলে কীভাবে শান্ত হব?"),
]

# Trivially off topic. These were never going to leak; they are the sanity floor.
TRIVIAL_CONTROLS: list[tuple[str, str]] = [
    ("How do I cook rice?", "ভাত কীভাবে রান্না করব?"),
    ("What is the capital of France?", "ফ্রান্সের রাজধানী কোথায়?"),
    ("Who won the cricket match yesterday?", "গতকালের ক্রিকেট খেলার ফল কী?"),
    ("Can you write me a poem about rain?", "বৃষ্টি নিয়ে একটা কবিতা লিখে দিন"),
    ("How do I open a bank account?", "কীভাবে ব্যাংক অ্যাকাউন্ট খুলব?"),
    ("How do I apply for a passport?", "পাসপোর্ট করতে কত টাকা লাগে?"),
    ("How do I find a job?", "চাকরি কীভাবে খুঁজব?"),
]

# NEAR-TOPIC. These are the ones that will actually leak: adjacent to
# safeguarding, health, family and law without being answerable from a corpus of
# WaterAid safeguarding material.
#
# Read the results with one thing in mind: several of these are questions a
# person might reasonably bring to this app. If one lands inside the genuine
# range, the answer is not to tune the floor until it disappears — it is to
# decide whether that question deserves a referral of its own.
NEAR_CONTROLS: list[tuple[str, str]] = [
    ("What are a woman's inheritance rights in Bangladesh?",
     "বাংলাদেশে নারীর উত্তরাধিকার অধিকার কী?"),
    ("How do I get a divorce in Bangladesh?", "বাংলাদেশে তালাক কীভাবে নেব?"),
    ("How do I file a police complaint?", "থানায় অভিযোগ কীভাবে করব?"),
    ("What is the punishment for theft?", "চুরির শাস্তি কী?"),
    ("How do I treat a burn on my hand?", "হাতে পোড়া জায়গার চিকিৎসা কীভাবে করব?"),
    ("My child has a fever, what should I do?", "আমার বাচ্চার জ্বর, কী করব?"),
    ("What vaccines does a newborn need?", "নবজাতকের কী কী টিকা দরকার?"),
    ("Where is the nearest hospital?", "নিকটস্থ হাসপাতাল কোথায়?"),
    ("What are normal period symptoms?", "স্বাভাবিক মাসিকের লক্ষণ কী?"),
    ("How much maternity leave am I entitled to?",
     "মাতৃত্বকালীন ছুটি কত দিন পাওয়া যায়?"),
    ("My daughter is being bullied at school", "আমার মেয়েকে স্কুলে উত্যক্ত করা হয়"),
    ("How do I talk to my teenage daughter?",
     "আমার কিশোরী মেয়ের সঙ্গে কীভাবে কথা বলব?"),
    ("My husband drinks too much", "আমার স্বামী অতিরিক্ত মদ্যপান করেন"),
    ("What are the symptoms of dengue fever?", "ডেঙ্গু জ্বরের লক্ষণ কী?"),
]

CONTROL_PAIRS = TRIVIAL_CONTROLS + NEAR_CONTROLS

MODE = "live"
if "--proxy" in sys.argv:
    MODE = "proxy"
elif "--translate" in sys.argv:
    MODE = "translate"

_translation_failures: list[str] = []


@functools.lru_cache(maxsize=256)
def retrieval_key(query: str, twin: str | None) -> str:
    """What actually gets embedded, per mode.

    Cached because the report functions each ask for it — boundary, per-language,
    closest-controls and answer-rate all score the same queries — and in
    --translate mode an uncached call is a Groq request. Without this, one run
    translated every Bangla query five or six times over, which is slow and burns
    quota for nothing.
    """
    if MODE == "proxy" and twin is not None:
        return twin
    if MODE == "translate" and twin is not None:
        try:
            return chain.to_english(query)
        except chain.Unavailable as exc:
            _translation_failures.append(f"{query} -> {exc}")
            return query
    return query


def top_distance(query: str, twin: str | None = None) -> float:
    passages = chain.search(retrieval_key(query, twin), n_results=1)
    return passages[0].distance if passages else float("inf")


def show(query: str, twin: str | None = None, limit: int = 3) -> None:
    key = retrieval_key(query, twin)
    passages = chain.search(key, n_results=4)
    label = f"  Q: {query}"
    if key != query:
        label += f"\n     via: {key}"
    print(f"\n{label}")
    for passage in passages[:limit]:
        mark = "KEEP  " if passage.distance <= chain.RELEVANCE_FLOOR else "reject"
        snippet = " ".join(passage.text.split())[:110]
        print(f"     [{mark} d={passage.distance:.3f}] {passage.source}")
        print(f"              {snippet}…")


def intercepted_before_the_gate() -> None:
    """Which controls never reach retrieval at all.

    The deterministic layer runs first in production, so a control it refuses
    tells us nothing about the distance gate — and several of the near-topic ones
    (divorce, filing a case, punishment) are exactly what safety.py is built to
    refuse. Worth separating so the gate is judged on what actually reaches it.
    """
    rows = []
    for group, pairs in (("trivial", TRIVIAL_CONTROLS), ("near", NEAR_CONTROLS)):
        for pair in pairs:
            for query in pair:
                decision = safety.classify(query)
                if decision.kind != "proceed":
                    rows.append((group, decision.kind, decision.category, query))

    print("\n" + "=" * 72)
    print("INTERCEPTED BY THE SAFETY LAYER (never reach the gate)")
    print("=" * 72)
    if not rows:
        print("  none")
    for group, kind, category, query in rows:
        print(f"  [{group:<7} {kind:<9} {category}] {query}")


def closest_controls(limit: int = 8) -> None:
    """The controls nearest the floor — where leakage will start."""
    scored = []
    for group, pairs in (("trivial", TRIVIAL_CONTROLS), ("near", NEAR_CONTROLS)):
        for pair in pairs:
            for i, query in enumerate(pair):
                distance = top_distance(query, pair[0] if i else None)
                language = "bn" if i else "en"
                blocked = safety.classify(query).kind != "proceed"
                scored.append((distance, group, language, blocked, query))
    scored.sort()

    print("\n" + "=" * 72)
    print(f"CLOSEST CONTROLS TO THE FLOOR ({chain.RELEVANCE_FLOOR})")
    print("=" * 72)
    for distance, group, language, blocked, query in scored[:limit]:
        flag = "  <-- refused by safety first" if blocked else ""
        inside = " *** INSIDE GENUINE RANGE ***" if distance <= _genuine_max() else ""
        print(f"  d={distance:.3f}  {group:<7} {language}  {query}{flag}{inside}")


def _genuine_max() -> float:
    return max(
        top_distance(query, pair[0] if i else None)
        for pair in PAIRS
        for i, query in enumerate(pair)
    )


def by_language() -> None:
    """Per-language ranges, which is where the pooled overlap comes from."""
    print("\n" + "=" * 72)
    print("PER LANGUAGE")
    print("=" * 72)
    for name, index in (("English", 0), ("Bangla ", 1)):
        genuine = [top_distance(pair[index], pair[0] if index else None) for pair in PAIRS]
        controls = [
            top_distance(pair[index], pair[0] if index else None) for pair in CONTROL_PAIRS
        ]
        margin = min(controls) - max(genuine)
        print(
            f"  {name}: genuine {min(genuine):.3f}–{max(genuine):.3f}   "
            f"off-topic {min(controls):.3f}–{max(controls):.3f}   "
            f"margin {margin:+.4f}"
        )


def boundary() -> tuple[float, float]:
    genuine = {
        q: top_distance(q, pair[0] if i else None)
        for pair in PAIRS
        for i, q in enumerate(pair)
    }
    controls = {
        q: top_distance(q, pair[0] if i else None)
        for pair in CONTROL_PAIRS
        for i, q in enumerate(pair)
    }

    worst_genuine = max(genuine.items(), key=lambda kv: kv[1])
    best_control = min(controls.items(), key=lambda kv: kv[1])
    margin = best_control[1] - worst_genuine[1]

    print("\n" + "=" * 72)
    print(f"BOUNDARY  (cosine distance, lower is better) · mode = {MODE}")
    print("=" * 72)
    print(f"  genuine   top-1: min {min(genuine.values()):.4f}  max {worst_genuine[1]:.4f}")
    print(f"  off-topic top-1: min {best_control[1]:.4f}  max {max(controls.values()):.4f}")
    print(f"  worst genuine  : {worst_genuine[1]:.4f}  {worst_genuine[0]}")
    print(f"  best off-topic : {best_control[1]:.4f}  {best_control[0]}")
    print(f"  margin         : {margin:+.4f}")

    midpoint = (worst_genuine[1] + best_control[1]) / 2
    if margin <= 0:
        print("\n  VERDICT: the ranges overlap. No threshold separates them.")
    elif margin < 0.02:
        print(f"\n  VERDICT: ordered but only {margin:.4f} apart. A floor of "
              f"{midpoint:.3f} fits this sample and will leak in production.")
    else:
        print(f"\n  VERDICT: separated by {margin:.4f}. A floor at {midpoint:.3f} "
              "sits between them with room on both sides.")
    return worst_genuine[1], best_control[1]


def answer_rate(floor: float) -> None:
    """How many genuine questions get an answer at a given floor."""
    genuine = [
        (q, top_distance(q, pair[0] if i else None))
        for pair in PAIRS
        for i, q in enumerate(pair)
    ]
    controls = [
        (q, top_distance(q, pair[0] if i else None))
        for pair in CONTROL_PAIRS
        for i, q in enumerate(pair)
    ]
    answered = [q for q, d in genuine if d <= floor]
    # Two leakage numbers, because they answer different questions. The gate's
    # own performance counts every control that clears the threshold; what a user
    # would actually experience excludes the ones the deterministic layer refuses
    # before retrieval ever runs.
    leaked_gate = [q for q, d in controls if d <= floor]
    leaked_live = [
        q for q, d in controls if d <= floor and safety.classify(q).kind == "proceed"
    ]

    print("\n" + "=" * 72)
    print(f"ANSWER RATE at floor {floor:.3f}")
    print("=" * 72)
    print(f"  answered from the corpus  : {len(answered)}/{len(genuine)}")
    print(f"  fell through to referral  : {len(genuine) - len(answered)}/{len(genuine)}")
    for query, distance in genuine:
        if distance > floor:
            print(f"     no context (d={distance:.3f}): {query}")
    print(f"  gate leakage              : {len(leaked_gate)}/{len(controls)}")
    print(f"  leakage a user would see  : {len(leaked_live)}/{len(controls)}"
          "   (safety refuses the rest first)")
    for query, distance in controls:
        if distance <= floor:
            blocked = safety.classify(query).kind != "proceed"
            tag = "refused by safety" if blocked else "REACHES THE MODEL"
            print(f"     d={distance:.3f} [{tag}]: {query}")


def main() -> int:
    chain.load()
    if not chain.ready():
        print("corpus failed to load:", chain.status())
        return 1
    print(f"Corpus: {chain.status()['chunks']} chunks embedded in "
          f"{chain.status()['load_seconds']}s · {embedding.fingerprint()}")
    print(f"Mode:   {MODE}")

    print("\n" + "=" * 72)
    print("PAIRED QUERIES")
    print("=" * 72)
    for english, bangla in PAIRS:
        show(english)
        show(bangla, twin=english)
        print("  " + "-" * 68)

    print("\n" + "=" * 72)
    print("NEAR-TOPIC CONTROLS — the ones that will actually leak")
    print("=" * 72)
    for english, bangla in NEAR_CONTROLS:
        show(english, limit=1)
        show(bangla, twin=english, limit=1)

    intercepted_before_the_gate()
    closest_controls()
    by_language()
    worst_genuine, best_control = boundary()

    # Report at the current floor and, when separated, at the midpoint the
    # numbers actually support.
    answer_rate(chain.RELEVANCE_FLOOR)
    if best_control > worst_genuine:
        answer_rate(round((worst_genuine + best_control) / 2, 3))

    if _translation_failures:
        print("\nTRANSLATION FAILURES (fell back to the untranslated query):")
        for failure in _translation_failures:
            print("   ", failure)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
