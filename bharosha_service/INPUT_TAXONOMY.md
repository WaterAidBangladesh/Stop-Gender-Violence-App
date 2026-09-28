> **OUT OF DATE — read this first.**
>
> This describes the architecture before the conversational rewrite, when most
> categories were answered from fixed text and anything that missed the
> retrieval gate got a hardcoded wall. That is no longer how it works:
>
> * Only `safety.DEVICE_CATEGORIES` is answered from fixed text on the device —
>   the five emergencies, the six refusals, `personal_disclosure`,
>   `coercive_control`, `reporting_request`, `low_distress`, `identity` and
>   `privacy`. Everything else reaches the model.
> * The relevance floor no longer decides whether there is a reply. It decides
>   what the model may ASSERT (`GROUNDED` / `UNGROUNDED` in `chain.py`), and the
>   passages are shown to it either way.
> * Below the floor, the generated reply is scanned by `app/assertions.py` and
>   discarded if it gives advice anyway.
> * The hardcoded text is now the FALLBACK for every category that has one, used
>   when the model or the network is unavailable.
>
> The taxonomy of inputs below is still accurate. The "what it returns" and
> "gaps" columns are not. Rewriting it is outstanding work.

# What a person can type, and what Bharosha does with it

Every previous failure in this chatbot was found the same way: a screenshot, a
probe, an accident. "kemon acho?" returned an apology, a five-item topic list
and two emergency helpline numbers, and nobody knew until somebody typed it.

This document is the alternative. It enumerates the kinds of message a user can
send, states what each one returns today, and names the gaps. Everything marked
**handled** has test cases in both languages in
`tools/export_shared.py`, which both `pytest` and `flutter test` run — so the
table below is checked by the suite, not merely written down.

Counts as of this revision: **154 shared cases**, 191 Python tests, 189 Dart
tests, all green. Dart and Python agree on every one of the 154.

---

## How to read the table

**Where** says which side answers:

| | |
|---|---|
| **device** | Answered on the phone from bundled text. No network, no model, no wait, works with the radio off and with the server asleep. |
| **server** | Goes to the service: rate limit → retrieval → gate → model. The only column where an answer is generated rather than chosen. |

**Kind** is the value `safety.classify()` returns. It decides both the text and
how the bubble looks: emergency styling (red edge), refusal styling (amber
edge), or plain conversation.

---

## The table

### Danger — answered on the device, before anything else runs

| # | Input | Example (EN / BN) | Kind | Returns | Status |
|---|---|---|---|---|---|
| 1 | Violence happening now | "he is beating me right now" / "আমাকে মারছে" | `emergency` / `active_violence` | 999 first, then 109, then the safeguarding contacts | **handled** |
| 2 | In danger, hiding, afraid now | "I am scared right now" / "আমি এখনই বিপদে আছি" | `emergency` / `immediate_danger` | same script | **handled** |
| 3 | Threat to life | "he said he will kill me" / "সে আমাকে মেরে ফেলবে বলেছে" | `emergency` / `threat_to_life` | same script | **handled** |
| 4 | Suicide risk | "I want to die" / "আমি আর বাঁচতে চাই না" | `emergency` / `suicide_risk` | 999 first, then Kaan Pete Roi with its 3pm–3am hours | **handled** |
| 5 | A child at risk | "they want to marry off my daughter" / "একটি শিশুকে ধর্ষণ করা হয়েছে" | `emergency` / `child_disclosure` | 1098 Child Helpline plus 999 | **handled** |

These are matched deliberately broadly. A false positive shows someone a number
she did not need. A false negative is a person in danger reading a paragraph
about safeguarding principles.

### Her own situation — answered on the device

| # | Input | Example (EN / BN) | Kind | Returns | Status |
|---|---|---|---|---|---|
| 6 | Describing harm being done to her | "my boss touches me at work" / "আমার স্বামী আমাকে গালি দেয়" | `disclosure` / `personal_disclosure` | names it as gender-based violence, says she needs no proof, hands over 109 | **handled** |
| 7 | Asking about someone else | "my friend is being abused by her husband" / "আমার বান্ধবী নির্যাতনের শিকার" | `third_party` / `third_party_concern` | how to support without taking over, what not to do, 109 / 999 / 1098 | **handled (new)** |
| 7b | Feeling bad, no cause given | "amar mon ta kharap" · "I feel so alone" / "মন খারাপ" · "একা লাগে" | `low_distress` / `low_distress` | sits with it, does not diagnose or ask what happened, names Kaan Pete Roi with its hours, and OFFERS the corpus rather than prescribing it | **handled (new)** |

Retrieval is the wrong tool for row 6, and that was measured rather than
assumed: her phrasings sit *further* from the corpus than a cooking question
does, because the corpus is written as explanation and she is describing her
life. See the note above `DISCLOSURE_CATEGORIES` in `app/safety.py`.

Row 7 is checked *before* row 6, so "my sister's husband hits her" is not read
as her own account. It is also checked *after* the emergencies, so a friend in
immediate danger still gets the emergency script.

### The forbidden subjects — answered on the device

| # | Input | Example (EN / BN) | Kind | Returns | Status |
|---|---|---|---|---|---|
| 8 | Whether or when to leave | "should I leave my husband?" / "আমি কি স্বামীকে ছেড়ে চলে যাব" | `refuse` / `leave_decision` | explains why it will not answer, refers to 109 | **handled** |
| 9 | How to get a divorce | "how do I get a divorce?" / "তালাক কীভাবে নেব?" | `refuse` / `divorce_process` | different tone from row 8 — she has already decided | **handled** |
| 10 | Confronting, recording, gathering evidence | "how do I collect evidence against him?" | `refuse` / `confront_or_evidence` | refuses; those steps raise the danger | **handled** |
| 11 | Inheritance and property | "what are a woman's inheritance rights?" | `refuse` / `economic_rights` | names it as economic violence first, then refers | **handled** |
| 12 | Legal advice, case outcomes | "will I win the case?" / "মামলা করলে কি জিতব" | `refuse` / `legal_advice` | refuses to predict, refers | **handled** |
| 13 | Medical treatment | "how do I treat a burn?" / "লক্ষণ কী" | `refuse` / `medical_advice` | refuses, refers to 999 and health services | **handled** |

Row 13 exists because "how do I treat a burn on my hand?" retrieved **acid
attack first aid** at distance 0.384 — well inside the range of genuine
questions, so no threshold could have excluded it.

### Conversation — answered on the device

| # | Input | Example (EN / BN) | Kind | Returns | Status |
|---|---|---|---|---|---|
| 14 | Greeting, and "how are you" | "hi" · "kemon acho?" / "নমস্কার" · "কেমন আছো?" | `social` / `greeting` | two lines: answers the greeting, says what it is for. No topic list, no numbers | **handled (new)** |
| 15 | Thanks | "thank you" / "ধন্যবাদ" | `social` / `thanks` | two lines | **handled (new)** |
| 16 | Acknowledgement, farewell | "ok" · "hmm" · "bye" / "ঠিক আছে" · "বুঝেছি" | `social` / `acknowledgement` | "Understood. Take your time." | **handled (new)** |
| 17 | What are you? | "are you a real person" / "তুমি কে" | `social` / `identity` | says it is automated, not a counsellor/lawyer/doctor, and where a human is | **handled (new)** |
| 18 | "Will he see this?" | "will my husband know I used this" / "এটা কি গোপন থাকবে" | `social` / `privacy` | six factual claims about this app, each checked against the code | **handled (new)** |
| 19 | Frustration at the app | "you are useless" / "ফালতু" | `social` / `bot_abuse` | one flat line, no lecture, door left open | **handled (new)** |
| 20 | Too little to act on, **as the first message** | "help" · "what should I do" / "কি করবো" · "সাহায্য চাই" | `vague` / `vague` | one question back, plus one number (999) — not the referral block | **handled (new)** |
| 20b | The same, **mid-conversation** | "ki korbo?" after two turns about her office | `vague` → the conversational path | goes to the model, which can see the transcript. A clarifying question is worthless if the next turn has forgotten what was being clarified | **handled (new)** |

"How are you" is a greeting in Bangla, not a question about the software's
health, which is why it lives in row 14 and not row 17.

Row 20's boundary is the one that matters: **"help" is vague, "help me now" is
an emergency** — in both languages. The Bangla half of that pair
("আমাকে সাহায্য করুন এখনই") was missing until these cases were written.

Row 18 was added because every one of those questions was reaching the model,
where the corpus has nothing about this app's own behaviour. In a GBV app,
"will he see this?" decides whether she types the next sentence.

### Questions — answered by the server

| # | Input | Example | Kind | Returns | Status |
|---|---|---|---|---|---|
| 21 | On-topic, in the corpus | "what is safeguarding?" | `proceed` → `answer` | model answer from retrieved passages, with the helpline footer appended | **handled** |
| 22 | Anything else that misses the gate | "ekta proshno kori tomake?" (0.682) · "how do I cook rice" (0.810) · "asdfgh" (0.838) | `proceed` → `conversation` | **the conversational path.** The model sees the message raw and the rejected passages labelled weak. It may hold a conversation and ask one clarifying question; it may not state a fact it was not given | **handled (new)** |
| 22b | The same, when the model is unreachable | any of the above, offline | `no_context` or `off_topic` | the tiered hardcoded text, which is exactly what row 22 used to be | **handled** |
| 24 | Server unreachable | anything, with no network | `unreachable` | says the question was never asked — a claim about the connection, not about her question | **handled** |
| 25 | Too many messages | anything, past the token bucket | `rate_limited` | asks her to wait, still gives numbers | **handled** |

Rows 22 and 23 used to be the same reply. Tiering them is what stops the app
handing a crisis leaflet to someone who asked the time. **The gate did not
change**: retrieval still admits at 0.62 and nothing else. The nearest distance
is a number the search already computed, and it now picks which refusal she
reads. Measured with `tools/measure_off_topic.py`; see the note on
`OFF_TOPIC_DISTANCE` in `app/chain.py`.

---

## Gaps

Everything below reaches the model today. None of it is a retrieval problem and
none of it is fixed by moving a threshold.

| Input | Example | What happens now | What it should probably do |
|---|---|---|---|
| **Coercive control** | "he does not let me go out" (0.594) · "he controls my money" (0.608) | `proceed` → the model answers from the corpus, which does hold economic and psychological violence material. But it is not recognised as a disclosure, so she gets an explanation instead of 109 — and at 0.608 against a 0.62 gate, she is one corpus edit away from getting the no-context reply instead. | Add `control`, `allow`, `let me`, `permission`, `took my`, `locked` to the `personal_disclosure` co-occurrence rule. One-line change, needs sign-off because it widens a category that is already approved. |
| **Asking for a human** | "I want to talk to someone" (0.430) · "can you connect me to a counsellor" | `proceed` → the model answers from the corpus. It clears the gate comfortably, so the answer is usually about support services in general — a paragraph, where she asked for a person. | A direct referral category. The answer is known and fixed: 109, and Kaan Pete Roi with its hours. |
| **Wanting to report** | "I want to report this" (0.530) · "আমি অভিযোগ জানাতে চাই" | `proceed` → the model answers from the corpus about reporting routes in general. | Needs a product decision first. The app has a Report screen (`/reportForm`), but Bharosha must never describe *itself* as a reporting channel. Pointing at the app's own form is only safe once someone confirms that form is monitored. |
| **Follow-ups with no subject** | "and then what" (0.873) · "tell me more" (0.828) | `proceed` → retrieval on the bare phrase, which matches nothing → `off_topic`, i.e. "that's outside what I know about" in answer to a follow-up about safeguarding. There is no coreference: the server keeps conversation history for the model, but the *retrieval key* is the new message alone. | Either fold the previous question into the retrieval key, or treat a bare follow-up as `vague`. The first is better and is a real change to how retrieval is keyed — which is why it is listed here rather than done. |
| ~~**Gibberish, emoji, punctuation**~~ | "asdfgh" · "😢" · "..." | **Fixed.** Conversational path. "asdfgh" gets "Hello! How can I help you today?" rather than a crisis leaflet. | "😢" on its own is still not gibberish; whether it should be `low_distress` is a judgement call nobody has made. |
| **Questions about the corpus** | "what is your source" · "who made you" | `proceed` → retrieval. | Belongs in `identity`. Low risk; not added because it was not in scope. |
| ~~**Emotional states**~~ | "I am depressed" · "I feel anxious all the time" | **Changed.** They were reaching the corpus, which answered a feeling with a technique she had not asked for. They are now `low_distress` (row 7b), which acknowledges first and offers the material second. | The corpus is still one sentence away; she is the one who reaches for it. |

---

## The conversational path

Rows 20b and 22 are the only two that reach a model without a corpus answer
behind them. It is built from Probahini's mechanics, minus the one that lets it
invent:

**Copied.** The two-mode clause, granting conversation as well as answering —
the answering prompt has only the second mode, which is why every reply used to
read as a lookup. The whole capped transcript, every turn. The raw message,
unmodified and untranslated, so "kemon acho" reaches a model that understands
romanised Bangla instead of an English translation of it. `(NO PREAMBLE)`. No
length constraint, so a short message gets a short reply. And the rejected
passages, labelled as possibly irrelevant — **the gate decides whether the model
may ANSWER FROM them, not whether it may SEE them.**

**Not copied.** Probahini's prompt says: *"If no relevant information exists,
refer to the Flow of Chat for context to create an informed and relevant
response."* That sentence is both why it feels alive and why it can invent. The
two are separable. Where Probahini has an escape hatch, `CONVERSE_PROMPT` has a
wall: it may acknowledge, answer a social or procedural turn, and ask one
clarifying question; it may not state any safeguarding, health, legal or
procedural fact it was not given, advise, or speculate about her situation. If a
reply would need information it does not have, it says so and points at the
helpline buttons.

**No footer on this path.** Appending *"To talk to a person: 109 · 999"* to
*"Yes, of course — ask"* is the canned wall arriving by another route, and the
app keeps both numbers on screen as buttons for the whole conversation. The
prompt points at those buttons instead. This is a judgement call and the one
place a reviewer should push back if they disagree.

**Nothing about the ordering changed.** The safety layer runs first, on the
device. Emergencies, disclosures, third-party concerns, refusals and low
distress cannot reach this path — the shared case corpus asserts it for all 170
cases, on both sides.

## The rules this table is built on

1. **The model is never the safety layer.** Rows 1–20 are pattern matching in
   Python and Dart, running before anything is loaded or called. An LLM asked to
   spot an emergency will sometimes miss one.
2. **Every social pattern is anchored end to end** (`^…$`). That is why
   "hi" is a greeting and "hi, he is beating me" is an emergency. The priority
   order is the second line of defence, not the first.
3. **Order is evaluation order, not severity.** Emergencies, then refusals, then
   third party, then her own disclosure, then social, then vague. First match
   wins, so the outcome never depends on dict ordering.
4. **Python authors, Dart consumes.** The patterns, the responses and these test
   cases are generated by `tools/export_shared.py`. A Python test fails while
   the generated files are stale, and the Dart suite runs the identical cases.
5. **`\b` next to Bangla is always a bug** and now raises at import. Most Bangla
   words end in a combining vowel sign, which is not a word character, so there
   is no boundary after it and the pattern silently never matches. Writing this
   check turned up a `medical_advice` rule ("লক্ষণ কী") that had never once
   fired.

## Two emergency misses this document found

Neither was found by a probe or a screenshot. Both were found by writing the
rows out and testing every cell.

- **"will my husband kill me"** reached the model. Every threat pattern assumed
  `will` and `kill` were adjacent, so a subject between them walked past all of
  them. Now matched on bare `kill me`.
- **"my friend's husband is beating her right now"** was filed as a support
  question rather than an emergency. The active-violence patterns only
  recognised violence in progress when the subject was a pronoun and the object
  was "me". The Bangla side never had this gap, because "মারছে" carries the
  tense without needing either.
