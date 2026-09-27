"""Embedding via fastembed. Quantized ONNX — no PyTorch, no transformers.

Probahini relies on Chroma's default embedder, all-MiniLM-L6-v2, which is
English-only. Measured on this corpus, a Bangla question under that model
retrieves the wrong topic for most questions, and the LLM then answers fluently
from unrelated source material. That is the one deviation worth its weight here.

fastembed does not ship multilingual-e5-small in its catalogue, but it can
register a custom ONNX model, and the official e5 repository publishes ONNX
exports — including an int8-quantized file roughly a quarter the size of the
float32 one, which is what makes this fit a 512 MB instance.

Quantization is a real trade: int8 weights shift distances slightly, so the
relevance threshold must be measured against this exact file rather than carried
over from the sentence-transformers numbers. BHAROSHA_EMBED_FILE switches to the
float32 export if the measurement ever justifies the extra memory.

E5 is asymmetric: queries are prefixed "query: " and documents "passage: ".
Dropping the prefixes costs real retrieval quality, and Chroma's embedding
function interface cannot express the distinction because it receives both
through one call — so both prefixes live here, and the index is built and queried
through this module alone.
"""

from __future__ import annotations

import os
from functools import lru_cache

MODEL_NAME = os.getenv("BHAROSHA_EMBED_MODEL", "intfloat/multilingual-e5-small")

# int8 by default: ~120 MB against ~470 MB for onnx/model.onnx.
MODEL_FILE = os.getenv(
    "BHAROSHA_EMBED_FILE", "onnx/model_qint8_avx512_vnni.onnx"
)

DIMENSION = 384

def _prefixes() -> tuple[str, str]:
    """(query, passage) prefixes. E5 is asymmetric and trained with them;
    all-MiniLM and most others are not, and prefixing them only adds noise."""
    if "e5" in MODEL_NAME.lower():
        return "query: ", "passage: "
    return "", ""


QUERY_PREFIX, PASSAGE_PREFIX = _prefixes()

# ONNX Runtime allocates a memory arena per thread, sized to the largest batch it
# has seen, and does not return it to the OS. Embedding all 37 chunks in one
# default-sized batch across every core measured 1.3 GB resident — worse than the
# vector database this replaced. One thread and a small batch cap that arena.
# A single-request-at-a-time service on a 512 MB instance wants neither
# intra-op parallelism nor a wide batch, so this costs a second of startup and
# nothing else.
THREADS = int(os.getenv("BHAROSHA_EMBED_THREADS", "1"))
BATCH_SIZE = int(os.getenv("BHAROSHA_EMBED_BATCH", "4"))


def _register() -> None:
    """Teach fastembed about e5-small. Idempotent, and a no-op for models it
    already ships (all-MiniLM-L6-v2 among them)."""
    from fastembed import TextEmbedding
    from fastembed.common.model_description import ModelSource, PoolingType

    known = {m["model"] for m in TextEmbedding.list_supported_models()}
    if MODEL_NAME in known:
        return
    TextEmbedding.add_custom_model(
        model=MODEL_NAME,
        pooling=PoolingType.MEAN,
        normalization=True,
        sources=ModelSource(hf=MODEL_NAME),
        dim=DIMENSION,
        model_file=MODEL_FILE,
    )


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding

    _register()
    return TextEmbedding(model_name=MODEL_NAME, threads=THREADS)


def embed_passages(texts: list[str]) -> list[list[float]]:
    return [
        vector.tolist()
        for vector in _model().embed(
            [PASSAGE_PREFIX + text for text in texts], batch_size=BATCH_SIZE
        )
    ]


def embed_query(text: str) -> list[float]:
    return next(iter(_model().query_embed(QUERY_PREFIX + text))).tolist()


def is_multilingual() -> bool:
    """Whether this model can embed Bangla at all.

    all-MiniLM-L6-v2 cannot: it is English-only, and a Bangla query against it
    retrieves near-arbitrary passages. That is safe only if Bangla questions are
    translated to English before embedding — see chain.TRANSLATE_QUERIES, which
    refuses to retrieve rather than retrieve badly.
    """
    return any(
        marker in MODEL_NAME.lower()
        for marker in ("multilingual", "labse", "e5-", "bge-m3", "paraphrase-multi")
    )


def fingerprint() -> str:
    """What is doing the embedding, for logs and for the retrieval report.

    Nothing depends on it now that vectors are embedded at startup rather than
    committed — but a line saying which model produced a set of distances is
    what stops a measured threshold being carried onto the wrong model.
    """
    return f"{MODEL_NAME}|dim={DIMENSION}|multilingual={is_multilingual()}"
