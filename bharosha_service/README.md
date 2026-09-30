# Bharosha (ভরসা) — RAG service

The safeguarding and GBV assistant for the Shomota Shurokkha app. A front door
that connects someone to a human, not a counsellor, not a legal adviser, and
not a reporting channel.

Separate from the Flutter app on purpose: this folder is a sibling of
`stop_gender_violence_fresh_ui/`, so Flutter never bundles Python, and the
service can be deployed and rolled back on its own.

## The design rule

**Safety decides, the AI speaks.** `app/safety.py` runs plain pattern
matching in Bangla, romanised Bangla and English before anything else — on
the phone first, then again on the server. It decides what the situation is.
The five emergencies are answered on the phone from fixed text in
milliseconds, with no network and no model. For every other message the model
writes the reply, and for every recognised safety category code appends a
referral block from `app/referrals.py`: the contacts and the one sentence of
limit. Numbers never come from the model.

```
message
   ↓
safety.classify()  ── one of the 5 emergencies ──→ fixed text, on the phone
   │                                                 (then POST /chat/note, category only)
   ↓ everything else, category attached
rate limit
   ↓
retrieval  ── nearest 4 of 418 passages; a Bangla or romanised query is
              translated to an English search key first
   ↓
the gate (0.62): may the model ASSERT from these passages, or only listen?
   ↓
one prompt: who you are, how you talk, what you know, what the app will show
            ({app_note}: the category, and the block that will follow),
            your limits, the raw message, the last 12 turns
   ↓
output check: no digits, no "@"; no advice or step lists when a category
              matched or the reply is below the floor → one retry → fixed text
   ↓
model text  +  referral block (full the first time, one line after)
```

Any failure on the way — no key, no network, corpus still embedding, a bad
retry — lands on the category's complete fixed text. The floor did not move;
a better ceiling was put above it.

## Layout

```
app/
  safety.py           the deterministic layer: 23 categories, 249 patterns,
                      6 co-occurrence rules, language detection. The author of
                      the rules the app bundles.
  referrals.py        every number, every fixed reply, every referral block,
                      hand-written en/bn. The single source of numbers.
  chain.py            retrieval, translation, the prompt and its slots, the
                      model call, the truncation guard
  assertions.py       the output check and its counters
  api.py              the pipeline in the order that is the safety design
  sessions.py         capped, expiring, in-memory history; block-mode score;
                      emergency notes
  ratelimit.py        token buckets keyed from the right of X-Forwarded-For
  embedding.py        the ONNX embedder
  knowledge_source.py reads the Knowledge Hub out of the Flutter source
tools/
  export_shared.py    Python → JSON for the app; refuses if a case disagrees
  console.html        the developer console (BHAROSHA_DEV_CONSOLE=on)
  probe.py            fires every case, writes probe_results.md
  feel_review.py      old vs new, side by side, for blind review
  verification_list.py, import_knowledge_pack.py, measure_off_topic.py,
  translate_corpus.py, build_guide.py
tests/
  test_safety, test_blocks, test_prompt, test_memory, test_language,
  test_output_check, test_referrals, test_startup, test_model_failures,
  test_shared_export — offline, seconds
  test_live_behaviour — against a running server, opt-in
corpus/               418 bilingual passages; see "The corpus is awaiting
                      WaterAid review" below
shared/               the generated JSON, mirrored into the Flutter assets
```

## Setup

Needs Python 3.11+. On Windows:

```
winget install Python.Python.3.12
```

```
cd bharosha_service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Run, in order

```
python -m pytest -q                 # safety layer — must pass before anything else
python app/knowledge_source.py      # confirm the Dart topics parse
python index/build_index.py         # ~470 MB model download on first run
python index/check_retrieval.py     # judge Bangla + English retrieval BEFORE the model
```

`check_retrieval.py` is a gate, not a formality. Its control queries are off
topic and must all be rejected by the floor; its paired queries must retrieve
the same passages in Bangla as in English. If Bangla diverges, try
`BHAROSHA_EMBEDDING_MODEL=LaBSE` and rebuild. Do not connect a model until this
reads well — a model answering from mismatched passages sounds just as
confident as one answering from the right ones.

## Status

Working end to end on a developer machine. Not deployed. The app must be
built with `--dart-define=BHAROSHA_URL=...` to use a server at all.

What a person gets, by kind of message:

| She types | Decided by | Written by | Appended by code |
|---|---|---|---|
| one of the 5 emergencies | the phone | fixed text | — |
| a disclosure, coercive control, a refusal topic, reporting, low distress, a friend in trouble | the phone and the server | the model | the category's referral block — full, then one line |
| identity, privacy | the phone and the server | the model, from a fixed note of facts | nothing |
| a greeting, thanks, "hmm", frustration, "ki korbo" | the phone and the server | the model | nothing |
| an ordinary question | — | the model, from the corpus | nothing |
| anything, with the server unreachable | the phone | the category's fixed text | — |

Measured behaviour — paths, numbers, the prohibition, and the feel — is
asserted by `tests/test_live_behaviour.py` and recorded in `probe_results.md`.

Still open, and recorded where it bites:

- **No referral number has been dialled.** `REFERRAL_VERIFICATION.md`;
  `referrals.VERIFICATION_STATUS`.
- **Ten fixed replies and every referral block await WaterAid sign-off**, and
  no Bangla text — including the prompt's examples — has been read by a native
  speaker. `feel_review.md` is the blind review.
- **The prompt changed how disclosures are answered.** WaterAid safeguarding
  must sign off the prompt, the category notes and the split blocks before
  launch.
- **The output check is a pattern list.** It catches the shapes of advice it
  knows; a new shape could pass it. The retry and fallback counts at `/health`
  are the measure.
- **Conversation history is in one process's memory.** A restart or a second
  instance loses a conversation mid-clarification.
- **iOS has no screenshot protection.** Whether iOS ships is undecided.

## Testing it without the app

    .\dev.ps1

Then open **http://127.0.0.1:8000/console**.

A browser page for asking questions and reading the answers, so a change can be
checked in seconds instead of by launching the Flutter app. It shows what the
app deliberately hides: which category fired, whether the phone or the model
answered, the nearest chunk's distance against the gate, and which sources the
answer came from. Presets down the right-hand side cover every row of
[INPUT_TAXONOMY.md](INPUT_TAXONOMY.md) in both languages; "Run every preset"
sweeps the lot.

It is a browser page rather than a terminal script for one concrete reason: a
Windows terminal renders Bangla as boxes, and Bangla is this app's primary
language.

`tools/probe.py` fires the same messages and writes `probe_results.md` for
reading. `tests/test_live_behaviour.py` fires them and ASSERTS — the path taken,
that a generated reply contains no phone number the model wrote, and that
nothing below the relevance floor gives advice. It is skipped unless
`BHAROSHA_BASE` is set:

    $env:BHAROSHA_BASE = "http://127.0.0.1:8000"
    python -m pytest tests/test_live_behaviour.py -v

`GET /health` reports how often the output check had to act: `output_retries`
and `output_fallbacks` over `output_checks`. A retry means the model's first
draft gave advice, a step list or a contact and was asked once to rewrite; a
fallback means the rewrite failed too and the fixed text was sent instead.
They are different findings — a retry means the prompt is slightly loose, a
fallback means the model could not be steered. The measured rates are in
`probe_results.md`.

The console calls the same `_answer()` the phone calls — it does not
re-implement the pipeline — and the routes exist only when
`BHAROSHA_DEV_CONSOLE=on`, which `dev.ps1` sets and nothing else does. A
deployed instance does not serve them at all. `tests/test_startup.py` asserts
both: that the routes are absent by default, and that `/chat` still returns
exactly `{response, kind}`.

## Choosing the model

The default is `openai/gpt-oss-20b` on Groq, with `reasoning_effort="low"` and
the truncation guard in `chain.reject_if_unusable` — both of which fixed real
failures (empty and cut-off replies) and must stay whatever the model.

`openai/gpt-oss-120b` is worth trying if it is available on the account. Do
**not** switch the default on impression. Run the comparison:

1. Start the service with `BHAROSHA_MODEL=openai/gpt-oss-120b`.
2. Run `python tools/probe.py` and the live suite
   (`python -m pytest tests/test_live_behaviour.py`) against it.
3. Read `/health` after the live suite: `output_retries` and
   `output_fallbacks` over `output_checks`. The 20B baseline is recorded in
   `probe_results.md`.
4. Regenerate `feel_review.md` (`python tools/feel_review.py`) and put both
   versions in front of the same blind reviewers.

Switch only if the larger model retries less, falls back less, and reads
better to the reviewers — all three. Cost and latency go up with it, and a
recognised category on the phone waits eight seconds before showing the
fixed text.

## Known dependencies outside this service

Things Bharosha's text depends on that are not in this repository. Each one has
been written around rather than assumed, and each needs someone else to close it.

### The app's incident report form is not usable

`/reportForm` in the Flutter app requires a login and is not reachable. Until
that changes, **Bharosha must not mention it.** This is not a style preference:
the model, left to answer "I want to report this" from the corpus, replied that
a report could be made anonymously — which would have told a woman something had
been done when nothing had.

That is why `reporting_request` is a hardcoded, on-device category whose first
sentence is "I cannot take a report", and why the prompt forbids the model from
naming any in-app reporting route. When the form works and someone confirms who
reads it, this is the note to revisit.

### The referral numbers have not been dialled

See [REFERRAL_VERIFICATION.md](REFERRAL_VERIFICATION.md), generated from
`app/referrals.py`. `VERIFICATION_STATUS` says `UNVERIFIED` and a test keeps it
honest.

### The corpus is awaiting WaterAid review

345 of 418 chunks are `knowledge_pack_pending_review` and 36 more are
`external_pending_review`. 133 of the pack's 459 rows are indexed; the 198 legal
rows are excluded and legal questions are refused before retrieval, so that
material is unreachable twice over.

## Secrets

`GROQ_API_KEY` comes from the environment, nowhere else. Create a **new** key
for this project — the key in the reference project's committed notebook should
be treated as compromised and revoked.
