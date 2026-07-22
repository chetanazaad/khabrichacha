"""
khabrichacha/core/embeddings.py

Optional semantic-similarity layer that augments the lexical
RelevanceScorer (khabrichacha/core/relevance.py) with real embeddings --
closing the gap where keyword/phrase overlap can't recognize that two
different phrasings mean the same thing (e.g. "vehicle collision" vs
"car crash"). This mirrors the reranking step used by tools like
Perplexica, which convert query and sources into vectors and rank by
cosine similarity, instead of relying on literal word overlap.

This is deliberately an ENHANCEMENT, not a requirement. If no embedding
backend is reachable -- no embedding-capable Ollama model pulled, and no
OPENAI_API_KEY/GEMINI_API_KEY set -- everything falls back cleanly to
the lexical-only scoring that already exists (see relevance.py). The
system must keep working with zero extra setup; embeddings just make
relevance filtering better when available.

To enable the free/local path: `ollama pull nomic-embed-text` (a small,
fast, ~270MB embedding model). Nothing else to configure -- it's tried
automatically.
"""
from __future__ import annotations

import os
import math
import hashlib
from typing import Optional, List, Dict, Tuple

from loguru import logger
import requests


class Embedder:
    """
    Provider-agnostic text embedder. On first use, tries backends in this
    order and remembers whichever one works for the rest of this
    Embedder's lifetime:

      1. Ollama's local /api/embeddings endpoint (default model
         "nomic-embed-text") -- the free/local path, consistent with
         this project's Ollama-first default.
      2. OpenAI's embeddings API (text-embedding-3-small), if
         OPENAI_API_KEY is set.
      3. Gemini's embedding API (text-embedding-004), if GEMINI_API_KEY
         is set.

    If none are reachable, embed() returns None every time and callers
    should fall back to lexical-only scoring -- see RelevanceScorer.

    Embeddings are cached in-memory (keyed by a hash of the text) for
    this Embedder's lifetime, so re-checking the same mission or the same
    source text doesn't re-embed it. A single shared instance is used
    process-wide via get_shared_embedder() below.
    """

    def __init__(self, ollama_base_url: Optional[str] = None, ollama_model: str = "nomic-embed-text"):
        self.ollama_base_url = ollama_base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model = ollama_model
        self._cache: Dict[str, List[float]] = {}
        # Remembers which backend actually worked (or that none did) after
        # the first call, so later calls don't re-attempt dead backends
        # one by one on every single source checked in a run.
        self._known_backend: Optional[str] = None  # "ollama" | "openai" | "gemini" | "none"

    @staticmethod
    def _cache_key(text: str, backend: str) -> str:
        return f"{backend}:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"

    def embed(self, text: str) -> Optional[List[float]]:
        if not text:
            return None

        if self._known_backend == "none":
            return None

        if self._known_backend is not None:
            # Already know which backend works for this run -- use it
            # directly. If it fails just this once (a transient network
            # blip), return None for this call without permanently
            # downgrading to "none" -- it may well succeed next time.
            method = {
                "ollama": self._embed_ollama,
                "openai": self._embed_openai,
                "gemini": self._embed_gemini,
            }[self._known_backend]
            return method(text)

        # First call: discover which backend (if any) is available.
        for backend, method in (
            ("ollama", self._embed_ollama),
            ("openai", self._embed_openai),
            ("gemini", self._embed_gemini),
        ):
            vec = method(text)
            if vec is not None:
                self._known_backend = backend
                logger.info(f"Embedding backend available: {backend}. Semantic relevance scoring enabled.")
                return vec

        logger.info(
            "No embedding backend available (pull an Ollama embedding model with "
            "`ollama pull nomic-embed-text`, or set OPENAI_API_KEY/GEMINI_API_KEY) -- "
            "relevance filtering will use lexical scoring only."
        )
        self._known_backend = "none"
        return None

    def _embed_ollama(self, text: str) -> Optional[List[float]]:
        key = self._cache_key(text, "ollama")
        if key in self._cache:
            return self._cache[key]
        try:
            resp = requests.post(
                f"{self.ollama_base_url}/api/embeddings",
                json={"model": self.ollama_model, "prompt": text[:8000]},
                timeout=15,
            )
            if resp.status_code == 200:
                vec = resp.json().get("embedding")
                if vec:
                    self._cache[key] = vec
                    return vec
        except Exception as e:
            logger.debug(f"Ollama embedding call failed: {e}")
        return None

    def _embed_openai(self, text: str) -> Optional[List[float]]:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        key = self._cache_key(text, "openai")
        if key in self._cache:
            return self._cache[key]
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            resp = client.embeddings.create(model="text-embedding-3-small", input=text[:8000])
            vec = list(resp.data[0].embedding)
            self._cache[key] = vec
            return vec
        except Exception as e:
            logger.debug(f"OpenAI embedding call failed: {e}")
            return None

    def _embed_gemini(self, text: str) -> Optional[List[float]]:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None
        key = self._cache_key(text, "gemini")
        if key in self._cache:
            return self._cache[key]
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            resp = genai.embed_content(model="models/text-embedding-004", content=text[:8000])
            vec = list(resp["embedding"]) if isinstance(resp, dict) else list(resp.embedding)
            self._cache[key] = vec
            return vec
        except Exception as e:
            logger.debug(f"Gemini embedding call failed: {e}")
            return None


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Pure-Python cosine similarity -- no numpy dependency needed for
    comparing a handful of vectors per retrieval pass."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


_shared_embedder: Optional[Embedder] = None


def get_shared_embedder() -> Embedder:
    """
    One Embedder per process, shared across every RelevanceScorer
    instance -- this is what makes the backend-discovery and per-text
    embedding cache actually useful across a whole run (and across
    multiple strategy calls), rather than re-discovering and re-embedding
    from scratch every time a new RelevanceScorer is constructed.
    """
    global _shared_embedder
    if _shared_embedder is None:
        _shared_embedder = Embedder()
    return _shared_embedder
