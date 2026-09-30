# What a person can type, and what Bharosha does with it

Every earlier failure in this chatbot was found the same way: a screenshot, a
probe, an accident. "kemon acho?" once returned an apology, a five-item topic
list and two emergency helpline numbers, and nobody knew until somebody typed
it. This document is the alternative: every kind of message a person can send,
what happens to it today, and the gaps. Everything marked **handled** has test
cases in both languages in `tools/export_shared.py`, which both `pytest` and
`flutter test` run, so the table is checked by the suite rather than merely
written down.

---

## The rule

**Safety decides, the AI speaks.** Pattern matching, on the phone and again on
the server, decides what the situation is. The five emergencies are answered
on the phone from fixed text. For everything else the model writes the reply,
and for every recognised safety category code appends a **referral block** —
the contacts and the one sentence of limit — from `referrals.py`. Numbers never
come from the model.

The block is **full** the first time a category's contacts appear in a
conversation and **one line** every time after. The call buttons for 999 and
109 are on screen throughout.

## How to read the table

| Column | Means |
|---|---|
| **Decided by** | Who classifies the message. "phone" means the bundled rules, in microseconds, offline. "both" means the phone classifies, sends the category along, and the server classifies again and trusts only itself. |
| **Written by** | Who writes the words she reads. |
| **Appended** | What code adds under the model's words. |
| **If the server can't be reached** | What the phone shows after 8 seconds for a recognised category, or 30 for an ordinary question. |

---

## The table

### Danger — answered on the phone, from fixed text

| # | Input | Example (EN / BN) | Category | Written by | If unreachable |
|---|---|---|---|---|---|
| 1 | Violence happening now | "he is beating me right now" / "আমাকে মারছে" | `active_violence` | fixed text: 999, 109, safeguarding contacts | same |
| 2 | In danger, hiding, afraid now | "I am scared right now" / "আমি এখনই বিপদে আছি" | `immediate_danger` | same script | same |
| 3 | Threat to life | "he said he will kill me" · "will my husband kill me" / "সে আমাকে মেরে ফেলবে বলেছে" | `threat_to_life` | same script | same |
| 4 | Suicide risk | "I want to die" / "আমি আর বাঁচতে চাই না" | `suicide_risk` | fixed text: 999 first, then Kaan Pete Roi with its 3pm–3am hours | same |
| 5 | A child at risk | "they want to marry off my daughter" / "একটি শিশুকে ধর্ষণ করা হয়েছে" | `child_disclosure` | fixed text: 1098 plus 999 | same |

These never reach the server. A model call for "he is going to kill me" would
mean seconds instead of milliseconds, a network she may not have, and words
that drift when the model is updated. After showing the reply the phone sends
`POST /chat/note` with the **category only** — never her words — so the next
message does not arrive at a model that has no idea she just said she was in
danger.

### Her own situation — the model writes, code appends the block

| # | Input | Example (EN / BN) | Category | Written by | Appended | If unreachable |
|---|---|---|---|---|---|---|
| 6 | Describing harm done to her | "my boss touches me at work" / "আমার স্বামী আমাকে গালি দেয়" | `personal_disclosure` | the model: acknowledges, says it is not her fault and she needs no proof; no advice | 109, 999, 1098 if under 18, WaterAid safeguarding; "I can't advise you on what to do next" | full fixed text |
| 7 | Control of money, phone, movement, work, documents | "he controls my money" · "he does not let me go out" / "সে আমার ফোন চেক করে" | `coercive_control` | the model: acknowledges the specific things she named; may say this is recognised as violence | 109, 999; "I can't advise you on the money, the documents or the restrictions" | full fixed text |
| 8 | Feeling bad, no cause given | "I feel so alone" · "amar mon ta kharap" / "মন খারাপ" | `low_distress` | the model: brief, gentle, no diagnosis, does not ask what happened | Kaan Pete Roi with its hours | full fixed text |
| 9 | Asking about someone else | "my friend is being abused by her husband" / "আমার বান্ধবী নির্যাতনের শিকার" | `third_party_concern` | the model: it matters that she noticed; supporting-someone material in prose if retrieved | 109, 999, 1098 if under 18 | full fixed text |

### The forbidden subjects — the model acknowledges, the block refuses

| # | Input | Example (EN / BN) | Category | Written by | Appended | If unreachable |
|---|---|---|---|---|---|---|
| 10 | Whether or when to leave | "should I leave my husband?" / "আমি কি স্বামীকে ছেড়ে চলে যাব" | `leave_decision` | the model: how heavy this is; one sentence that this is the one thing it can't advise on | why not, 109 with safety planning, 999 | full fixed text |
| 11 | How to get a divorce | "how do I get a divorce?" / "তালাক কীভাবে নেব?" | `divorce_process` | the model: a sensible, serious step to ask about | depends on which family law applies; 109 for free legal aid; 999 | full fixed text |
| 12 | Inheritance and property | "what are my inheritance rights?" | `economic_rights` | the model: acknowledges; states no entitlement | recognised as economic violence; entitlement needs a lawyer; 109; focal points | full fixed text |
| 13 | Legal advice, case outcomes | "will I win the case?" / "মামলা করলে কি জিতব" | `legal_advice` | the model: acknowledges; one sentence that a guess could cost her | "I can't give legal advice"; 109; focal points | full fixed text |
| 14 | Medical treatment | "how do I treat a burn on my hand?" / "লক্ষণ কী" | `medical_advice` | the model: acknowledges she is hurt; no treatment information | "I can't tell you how to treat an injury"; 999; hospital; 109 | full fixed text |
| 15 | Confronting, recording, evidence | "how do I collect evidence against him?" | `confront_or_evidence` | the model: acknowledges why she might want to; no method | "I won't suggest ways to…"; 109; 999 | full fixed text |
| 16 | How or where to report | "I want to report this" · "can I report anonymously" / "আমি অভিযোগ জানাতে চাই" | `reporting_request` | the model: acknowledges her wish to act; whether and when is her decision | "I can't take a report"; 109; 999; safeguarding email; 1098 | full fixed text |

Row 14 exists because "how do I treat a burn on my hand?" once retrieved
**acid-attack first aid** at a distance inside the range of genuine questions.
Row 16 exists because the model once answered "I want to report this" with
"you can report anonymously", pointing at an in-app form that needs a login
and does not work. Both stay deterministic in their substance: the model writes
the opening, never the refusal.

### Conversation — the model writes, nothing appended

| # | Input | Example | Category | Written by | If unreachable |
|---|---|---|---|---|---|
| 17 | Greeting, and "how are you" | "hi" · "kemon acho?" · "Assalamu alaikum" / "নমস্কার" | `greeting` | the model, mirroring her greeting | a fixed greeting that also mirrors: salam → ওয়ালাইকুম আসসালাম, নমস্কার → নমস্কার, else হ্যালো/Hello |
| 18 | Thanks | "thank you" / "ধন্যবাদ" | `thanks` | the model, one sentence | fixed text |
| 19 | Acknowledgement, farewell | "ok" · "hmm" · "bye" / "ঠিক আছে" | `acknowledgement` | the model, one sentence | fixed text |
| 20 | What are you? | "are you a real person" / "তুমি কে" | `identity` | the model, from a fixed note of facts: automated, not a counsellor/lawyer/doctor, made by WaterAid Bangladesh, no account needed | fixed text |
| 21 | Will he see this? | "will my husband know I used this" / "এটা কি গোপন থাকবে" | `privacy` | the model, from a fixed note of facts: nothing saved on the phone; the question is sent to be looked up and then forgotten; after an emergency only a topic label is sent; no notifications; Leave now; an unlocked phone can be read | fixed text |
| 22 | Frustration at the app | "you are useless" / "ফালতু" | `bot_abuse` | the model, not defensive; asks what she was looking for | fixed text |
| 23 | Too little to act on | "help" · "ki korbo" / "সাহায্য চাই" | `vague` | the model: connects to the conversation if there is one, else one gentle question and a mention of the call buttons | fixed clarifier with one number |

### Questions — the model answers from the corpus

| # | Input | Example | Route | Written by | Appended |
|---|---|---|---|---|---|
| 24 | On topic, in the corpus | "what is gender based violence?" | grounded (nearest passage ≤ 0.62) | the model, from the passages, crediting the source | nothing — the call buttons are on screen |
| 25 | On topic, corpus misses it | "what is stalking" (0.637) | ungrounded | the model, listening only: may reflect, ask one question, point to the buttons; asserts no fact | nothing |
| 26 | Off topic | "how do I cook rice" (0.810) | ungrounded | the model: one kind sentence that it only covers safeguarding and GBV; no apology, no helpline | nothing |
| 27 | Server unreachable | anything, no network | — | the phone: the category's fixed text, or "I could not reach the service" for an ordinary question | — |
| 28 | Corpus still embedding | an ordinary question in the first ~30 s after a restart | — | fixed text: "I am still starting up"; a recognised category gets its own text instead | — |

---

## Languages

| She writes | Detected as | Reply in | Search key |
|---|---|---|---|
| Bangla script | `bn` | Bangla | translated to English |
| Bangla in Latin letters — two or more hits from a shared word list | `bn_roman` | **Bangla script** | translated to English |
| anything else | `en` | English | as typed |

Romanised Bangla used to get English fixed text. She typed Latin letters
because that is what her keyboard offered; she reads Bangla.

## The output check

Every model-written reply is scanned. A run of three or more digits or an "@"
fails, always — the model may never write a contact. Advisory phrasing and
step lists fail when a safety category matched or the reply is below the
floor, not on an ordinary grounded answer, because WaterAid's material has
legitimate numbered steps in it. On a failure the model is asked once to
rewrite; if that fails too, the fixed text is sent. `/health` reports retries
and fallbacks separately.

---

## Gaps

| Input | Example | What happens now | What it should probably do |
|---|---|---|---|
| **A question the corpus holds only in the excluded legal rows** | "what does the law say about dowry?" | Refused as `legal_advice`, and the 198 legal rows are not indexed. Unreachable twice over. | A product decision: whether recognition questions ("is this a form of violence?") may be answered while entitlement questions ("what am I owed?") stay refused. |
| **The output check is a pattern list** | a new shape of advice | Passes if it matches none of the patterns. | The retry and fallback counts at `/health` are the measure; the patterns grow from what the live suite finds. |
| **Streaming** | any long reply | The whole reply arrives at once after the model finishes. | Phase 2 of the brief: stream the model text, then append the block; the output check must run on the complete text before the bubble is final. Not done. |
| **"😢" on its own** | an emoji | Ungrounded conversation. | Arguably `low_distress`; nobody has decided. |
| **A follow-up whose subject scrolled out** | the 13th turn | The model has the last 12. | Fine for now; raise `BHAROSHA_MAX_TURNS` if reviewers find otherwise. |

## What the tests pin

- **Both sides classify all 195 shared cases identically**, in three languages
  (`safety_cases.json`).
- **Exactly five categories are on the device** (`test_startup.py`, the Dart
  suite).
- **Every model-answered category has a referral block or is listed as needing
  none**, and the service refuses to start otherwise (`test_blocks.py`).
- **Every category has a fixed fallback in both languages**, and 16263 appears
  in none of the crisis text or blocks.
- **The prompt still carries all seven limits**, and the reference project's
  escape hatch is not in it (`test_prompt.py`).
- **The output check passes gentle sentences and catches instruction, numbers
  and emails** (`test_output_check.py`).
- **Against a live server** (`test_live_behaviour.py`): the path, the numbers,
  the prohibition, and the feel — varied openings, no "Thank you for telling
  me", Bangla script for romanised Bangla, a salam answered with a salam, and
  memory across turns including an emergency the phone answered itself.
