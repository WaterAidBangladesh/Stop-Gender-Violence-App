"""Chunks the corpus into corpus/chunks.json. Run when the corpus changes.

    python build_corpus.py

This writes TEXT ONLY — no vectors, no binary, nothing whose provenance cannot
be read in a diff. The 37 chunks are embedded at startup by the service itself
(a local ONNX model does them in a second or two), which is why there is no
vectors file, no fingerprint and no dimension-mismatch failure mode: the corpus
text is the single source of truth.

EACH CHUNK IS A PAIR: {"en": ..., "bn": ...}. Only the English side is ever
embedded — the retrieval model has a 30k English vocabulary and cannot represent
Bangla — but the Bangla side is what gets handed to the model when the user wrote
in Bangla. That separation is the point: retrieval stays cheap and English, while
Bangla answers can come from human-authored WaterAid Bangla rather than being
translated on the fly by a 20B model, which would put a quality ceiling on the
app's primary language.

Every "bn" is null today because no Bangla source text exists yet. The structure
is here so that dropping it in later is a data change, not a refactor.

Two deviations from Probahini's notebook, both agreed:

1. IT CHUNKS. That notebook imports RecursiveCharacterTextSplitter and never
   calls it, so one whole PDF page became one document and a question about a
   single sentence retrieved a page of unrelated text with it. 700 characters,
   130 overlap, with "।" in the separator list so Bangla is not cut mid-sentence.
2. Sources are attributed per chunk, so answers can credit WaterAid or MJF the
   way the app already credits each topic.

The 25 policy pages shipped inside the app are scanned images and deliberately
absent: Bangla OCR is not reliable enough for a safety-critical corpus.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "app"))

from langchain_text_splitters import RecursiveCharacterTextSplitter  # noqa: E402
from pypdf import PdfReader  # noqa: E402

import knowledge_source  # noqa: E402

CORPUS_DIR = ROOT / "corpus"
CHUNKS_PATH = CORPUS_DIR / "chunks.json"

CHUNK_SIZE = 700
CHUNK_OVERLAP = 130
SEPARATORS = ["\n\n", "\n", "। ", "।", ". ", "? ", "! ", "; ", ", ", " ", ""]

PDF_SOURCES = {
    "wateraid-global-safeguarding-framework.pdf": (
        "WaterAid Global Safeguarding Framework 2023-2028"
    ),
}


def splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=SEPARATORS,
        length_function=len,
    )


def knowledge_hub_chunks() -> list[dict]:
    split = splitter()
    chunks: list[dict] = []
    sections = knowledge_source.load_sections()
    if knowledge_source.DEFAULT_DART_PATH.exists():
        knowledge_source.save_snapshot(sections)
        print(f"  snapshot refreshed: {knowledge_source.SNAPSHOT_PATH.name}")
    for section in sections:
        header = f"{section.topic_title} — {section.section_title}\n\n"
        for i, piece in enumerate(split.split_text(section.content)):
            chunks.append(
                {
                    "id": f"hub-{section.topic_id}-{section.section_title[:24]}-{i}",
                    # The heading rides along in the embedded text: a chunk from
                    # the middle of a topic otherwise has no idea what it covers.
                    "en": header + piece,
                    # Awaiting WaterAid's Bangla source text. Null means answers
                    # to Bangla questions are generated from the English side.
                    "bn": None,
                    "source": section.source,
                    "origin": "knowledge_hub",
                }
            )
    return chunks


def pdf_chunks() -> list[dict]:
    split = splitter()
    chunks: list[dict] = []
    for filename, source_label in PDF_SOURCES.items():
        path = CORPUS_DIR / filename
        if not path.exists():
            print(f"  ! missing {path.name} — skipping")
            continue
        reader = PdfReader(str(path))
        extracted = 0
        for page_number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            extracted += 1
            for i, piece in enumerate(split.split_text(text)):
                chunks.append(
                    {
                        "id": f"{path.stem}-p{page_number}-{i}",
                        "en": piece,
                        "bn": None,
                        "source": f"{source_label} (p. {page_number})",
                        "origin": "pdf",
                    }
                )
        print(f"  {path.name}: text from {extracted}/{len(reader.pages)} pages")
        if extracted == 0:
            print("  ! no text at all — probably scanned. Do not OCR it; ask "
                  "WaterAid for the digital original.")
    return chunks


def main() -> int:
    chunks = knowledge_hub_chunks() + pdf_chunks()
    if not chunks:
        print("No chunks produced.")
        return 1

    CHUNKS_PATH.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    sizes = [len(c["en"]) for c in chunks]
    with_bangla = sum(1 for c in chunks if c.get("bn"))
    print(
        f"\nWrote {len(chunks)} chunks to {CHUNKS_PATH.relative_to(ROOT)}\n"
        f"  chunk length: min {min(sizes)}, mean {sum(sizes) // len(sizes)}, "
        f"max {max(sizes)}\n"
        f"  sources: {len({c['source'] for c in chunks})}\n"
        f"  Bangla text present: {with_bangla}/{len(chunks)}"
        f"{'  <-- answers to Bangla questions come from the English side' if with_bangla < len(chunks) else ''}\n\n"
        "No vectors are written. The service embeds these at startup.\n"
        "Next: python check_retrieval.py"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
