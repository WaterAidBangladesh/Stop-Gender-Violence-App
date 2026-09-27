"""Builds the Chroma index. Run once on a developer machine; commit vectordb/.

Same shape as Probahini's notebook — load the corpus, add it to a persistent
Chroma collection, commit the directory — with the two agreed deviations:

1. IT CHUNKS. Probahini's notebook imports RecursiveCharacterTextSplitter and
   never calls it, so one whole PDF page became one document: a question about a
   single sentence retrieved a page of unrelated text alongside it. 700
   characters with 130 of overlap, and "।" in the separator list so a Bangla
   paragraph is not cut mid-sentence.

2. IT EMBEDS MULTILINGUALLY. See app/embedding.py. Chroma's default is
   English-only, and this app's users write Bangla.

    python build_index.py

The 25 policy pages shipped inside the app are scanned images and are
deliberately absent: Bangla OCR is not reliable enough for a safety-critical
corpus, and a silent OCR pass would have Bharosha quoting WaterAid policy that
WaterAid never wrote.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "app"))

import chromadb  # noqa: E402
from langchain_text_splitters import RecursiveCharacterTextSplitter  # noqa: E402
from pypdf import PdfReader  # noqa: E402

import embedding  # noqa: E402
import knowledge_source  # noqa: E402

CORPUS_DIR = ROOT / "corpus"
DB_PATH = ROOT / "vectordb"

CHUNK_SIZE = 700
CHUNK_OVERLAP = 130

# Paragraph, then line, then sentence. "।" is the Bangla full stop.
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
    """Chunks from the app's own topic texts, parsed out of the Dart source."""
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
                    "document": header + piece,
                    "metadata": {
                        "source": section.source,
                        "origin": "knowledge_hub",
                        "topic_id": section.topic_id,
                    },
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
                        "document": piece,
                        "metadata": {
                            "source": f"{source_label} (p. {page_number})",
                            "origin": "pdf",
                            "page": page_number,
                        },
                    }
                )
        print(f"  {path.name}: text from {extracted}/{len(reader.pages)} pages")
        if extracted == 0:
            print("  ! no text at all — probably scanned. Do not OCR it; ask "
                  "WaterAid for the digital original.")
    return chunks


def main() -> int:
    print(f"Embedding: {embedding.fingerprint()}")

    chunks = knowledge_hub_chunks() + pdf_chunks()
    if not chunks:
        print("No chunks produced — nothing to index.")
        return 1

    if DB_PATH.exists():
        # Rebuild from scratch: re-running with a different chunk size would
        # otherwise leave the old chunks behind next to the new ones.
        shutil.rmtree(DB_PATH)

    client = chromadb.PersistentClient(path=str(DB_PATH))
    collection = client.create_collection(
        name=embedding.COLLECTION_NAME,
        # No embedding_function: vectors are computed here so the "passage: "
        # prefix applies to documents only. The fingerprint lets the service
        # refuse an index built with a different model.
        metadata={
            "hnsw:space": "cosine",
            "embedding_fingerprint": embedding.fingerprint(),
        },
    )

    batch = 32
    for start in range(0, len(chunks), batch):
        window = chunks[start : start + batch]
        documents = [c["document"] for c in window]
        collection.add(
            ids=[c["id"] for c in window],
            documents=documents,
            metadatas=[c["metadata"] for c in window],
            embeddings=embedding.embed_passages(documents),
        )
        print(f"  indexed {min(start + batch, len(chunks))}/{len(chunks)}")

    sizes = [len(c["document"]) for c in chunks]
    print(
        f"\nDone. {collection.count()} chunks in {DB_PATH.name}/\n"
        f"  chunk length: min {min(sizes)}, mean {sum(sizes) // len(sizes)}, "
        f"max {max(sizes)}\n\n"
        "Commit vectordb/ — the container copies it rather than rebuilding.\n"
        "Next: python check_retrieval.py"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
