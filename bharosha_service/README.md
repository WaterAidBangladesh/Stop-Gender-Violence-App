# Bharosha (ভরসা) — RAG service

The safeguarding and GBV assistant for the Shomota Shurokkha app. A front door
that connects someone to a human, not a counsellor, not a legal adviser, and
not a reporting channel.

Separate from the Flutter app on purpose: this folder is a sibling of
`stop_gender_violence_fresh_ui/`, so Flutter never bundles Python, and the
service can be deployed and rolled back on its own.

## The design rule

**The model is never the safety layer.** `app/safety.py` runs plain pattern
matching in both languages before anything else. On a match it returns
hardcoded text from `app/referrals.py` and the turn ends — no retrieval, no LLM
call. Only messages that pass it reach the corpus, and only passages that clear
a relevance floor reach the model.

```
message
   ↓
safety.classify()  ── emergency ──→ hardcoded referral   (no model)
   │                └─ refuse ────→ hardcoded refusal    (no model)
   ↓ proceed
retrieval.retrieve()  ── nothing above the floor ──→ "I don't know" + referrals
   ↓ passages
model, answering only from those passages, citing their source
```

## Layout

```
app/
  safety.py           deterministic bilingual detection — no model, no I/O
  referrals.py        contacts + every hardcoded response, hand-written en/bn
  embeddings.py       the one embedding function, shared by index and query
  knowledge_source.py parses the app's Dart topic texts (no second copy)
  retrieval.py        Chroma query + relevance floor
index/
  build_index.py      chunk → embed → persist
  check_retrieval.py  prints real bilingual results for a human to judge
tests/
  test_safety.py      the layer that can be tested, in both languages
corpus/
  wateraid-global-safeguarding-framework.pdf
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

**The index is not fit to serve yet, and no model may be connected to it.**
Measured 2026-09-26 with `index/check_retrieval.py`:

| Model | Bangla topic match | relevant top-1 | off-topic top-1 | margin |
|---|---|---|---|---|
| paraphrase-multilingual-MiniLM-L12-v2 | wrong topic, most questions | en 0.11–0.47 · bn 0.44–0.73 | en 0.83–0.96 · bn 0.71–0.85 | overlaps |
| sentence-transformers/LaBSE | right topic | 0.47–0.75 | 0.60–0.82 | **inverted** |
| **intfloat/multilingual-e5-base** | **right topic, matches English twin** | **0.081–0.222** | **0.235–0.296** | **+0.013** |

Measured over 14 genuine questions and 14 off-topic controls, half in each
language. E5 fixed cross-lingual retrieval outright: every Bangla question now
retrieves the same topic as its English twin, and the ranking is perfect —
every genuine question scores nearer than every off-topic one.

What is still unresolved is the **gate**, not the retrieval. E5 compresses
cosine distances into a narrow band, so the boundary is correctly ordered but
only 0.013 wide. `RELEVANCE_FLOOR = 0.23` classifies all 28 sample queries
correctly and is nonetheless a coincidence, not a safety mechanism: an unseen
question sits anywhere in that gap. Dropping the framework PDF
(`BHAROSHA_HUB_ONLY=1`) widens it only to 0.019, so the corpus is not the cause.

Before a model is connected, the no-context decision needs a **cross-encoder
reranker** (`BAAI/bge-reranker-v2-m3`, multilingual) scoring the retrieved
passages. A reranker produces a calibrated relevance score with a wide margin,
which is what requirement 7 — never improvise when nothing relevant was found —
actually needs. A **human-translated Bangla corpus** remains worth having
regardless: it removes on-the-fly translation from the answers.

Built:

- Safety layer, referral and refusal text, tests (79 passing).
- Embedding, chunking, indexing and retrieval with a relevance floor.

Not built yet:

- `app/chain.py` — the Groq call and system prompt.
- `app/api.py` — FastAPI, ephemeral sessions, rate limiting, counter-only logging.
- `Dockerfile`, deployment instructions.
- The Flutter chat screen and the shared Dart referral list.

Open items needing WaterAid's answer, recorded in code comments where they bite:

- **16263** is labelled a GBV hotline in the app but appears to be Shastho
  Batayan, the national health line. It stays in the contacts list and is
  excluded from every emergency script until confirmed (`referrals.NOTE_16263`).
- **Child disclosure** response text is written to be safe in every direction
  but needs policy and legal sign-off (`referrals.CHILD_DISCLOSURE_EN`).
- **A mental-health helpline** (e.g. Kaan Pete Roi) is a gap in the suicide-risk
  response. No number is added without approval.
- **Three hidden topic texts** exist in the Dart file, including Reporting
  Mechanisms, commented out of the app's own hub
  (`knowledge_source.INCLUDE_HIDDEN_TOPICS`).
- **Bangla corpus.** The corpus is English, so Bangla answers are the model
  rendering English passages. Referral text is hand-written in both languages
  and never model-translated; explanatory content is the residual risk.

## Secrets

`GROQ_API_KEY` comes from the environment, nowhere else. Create a **new** key
for this project — the key in the reference project's committed notebook should
be treated as compromised and revoked.
