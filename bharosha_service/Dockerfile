# Bharosha's RAG service. Shaped after Probahini's Dockerfile.api.
#
# On Render: New > Web Service > this repository > Docker, with
#   Root Directory  = bharosha_service
#   Dockerfile Path = ./Dockerfile
#   Free tier is fine. Set GROQ_API_KEY in the service's environment; never bake
#   a key into the image.
#
# There is no vector store. build_corpus.py runs on a developer machine and
# commits corpus/chunks.json — text only — and the service embeds those 37 chunks
# into a numpy matrix in a background thread at startup. So the image needs
# neither a database, nor the chunking libraries, nor the Flutter project.
#
# The one thing the container would otherwise download on first use is the
# quantized e5-small ONNX file (~120 MB), fetched by fastembed into HF_HOME. On
# the free tier the filesystem is ephemeral, so that download would repeat after
# every spin-down — it is baked in below, so a user's first question never waits
# for it.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models \
    PYTHONPATH=/app/app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY corpus/chunks.json ./corpus/chunks.json

# Pre-fetch the embedding model into the image. Also fails the build rather than
# the first user if the model file or its tokenizer cannot be resolved.
RUN python -c "\
import sys; sys.path.insert(0, 'app');\
import embedding;\
v = embedding.embed_query('warmup');\
print('embedder ready:', embedding.fingerprint(), 'dim', len(v))"

EXPOSE 8000

# Shell form: Render supplies the port in $PORT and only the shell expands it.
# One worker on purpose — each worker loads its own copy of the embedder.
CMD uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
