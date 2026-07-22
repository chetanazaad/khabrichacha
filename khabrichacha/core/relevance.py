"""
khabrichacha/core/relevance.py

A general-purpose, dependency-free relevance scorer: given a mission/goal
string, decide whether some other piece of text (a search result's
title+snippet, a fetched page's content, or a planner-generated search
query) is still actually *about* that mission.

This exists because neither research pipeline in this codebase has any
notion of topical relevance today:
  - deployment/runtime/retrieval/retriever.py ranks sources by trust,
    authority, freshness, and popularity, but never checks whether a
    source is actually on-topic for the mission.
  - khabrichacha/core/orchestrator.py (the RESEARCH/DEEP_RESEARCH adaptive
    loop) appends every search result and every fetched page to the
    findings/sources list completely unconditionally.

Without a check like this, an adaptive multi-iteration research loop can
"follow its nose" through tangentially-mentioned topics across iterations
and end up citing sources that have nothing to do with the original
question (e.g. a query about a country's national budget can drift into
citing that country's farmer-subsidy portal, a car marketplace, a generic
job board, and a Q&A site homepage -- because those pages happened to
share a few incidental words with something mentioned two iterations
earlier). This module is intentionally query-agnostic: it works from
whatever mission text it's given, with no hardcoded topic/keyword lists,
so it applies uniformly to any question rather than being tuned for one.
"""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Set

# A general (not topic-specific) English stopword list, plus a handful of
# generic request-framing words ("find", "give", "show"...) that carry
# mission *intent* rather than mission *subject matter*. Filtering these
# out means the keyword set left behind is the actual subject of the
# question, regardless of how the person happened to phrase the request.
_STOPWORDS: Set[str] = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or",
    "but", "is", "are", "was", "were", "be", "been", "being", "this",
    "that", "these", "those", "with", "from", "by", "as", "it", "its",
    "into", "about", "over", "under", "than", "then", "so", "such",
    "not", "no", "nor", "if", "do", "does", "did", "doing", "has", "have",
    "had", "having", "can", "could", "will", "would", "shall", "should",
    "may", "might", "must", "there", "here", "what", "which", "who",
    "whom", "whose", "when", "where", "why", "how", "all", "any", "both",
    "each", "few", "more", "most", "other", "some", "such", "only",
    "own", "same", "just", "also",
    # generic evaluative/superlative words: these describe quality or
    # ranking, not subject matter, and recur across countless unrelated
    # queries ("best restaurants", "best laptops", "top universities"...),
    # so treating them as real keywords causes false-positive relevance
    # matches between otherwise-unrelated topics that both happen to use
    # ranking language.
    "best", "top", "good", "great", "worst", "better", "worse",
    "recommended", "popular", "cheap", "cheapest", "affordable",
    # request-framing words: signal intent, not subject
    "find", "give", "show", "tell", "please", "search", "look", "get",
    "provide", "list", "explain", "describe", "summarize", "help",
    "want", "need", "would", "like",
}

# General (not topic-specific) institutional/bureaucratic words that show
# up across an enormous range of unrelated government-, policy-, and
# news-adjacent pages regardless of actual subject matter (a budget page,
# a farmer-subsidy status page, and a job-vacancy notice can all
# legitimately contain "government" even though only one of them is
# actually about the mission). A single match on one of these alone isn't
# strong enough evidence of real topical relevance -- see `_word_matches`/
# `score` for how this changes the matching logic. This is a general
# category (bureaucratic/institutional vocabulary), not a list tuned to
# any one query's subject.
_WEAK_CONTEXT_WORDS: Set[str] = {
    "government", "national", "state", "central", "federal", "public",
    "official", "department", "ministry", "authority", "committee",
    "council", "policy", "administration", "agency", "bureau", "office",
    "notification", "notice", "portal", "scheme", "programme", "program",
}

# Common English demonym/nationality-adjective suffixes (Indian, British,
# Chinese, Japanese, Israeli, American...). This is a general linguistic
# pattern, not a list of specific countries -- it exists because a
# nationality adjective narrows down "this is about country X" (extremely
# broad; thousands of unrelated pages about any given country all contain
# its demonym) without narrowing down the mission's actual subject matter
# nearly as much as the mission's other keywords usually do. Like
# `_WEAK_CONTEXT_WORDS`, a match on a demonym-shaped word alone isn't
# treated as sufficient evidence of real relevance.
_DEMONYM_SUFFIXES = ("ian", "ese", "ish")


def _looks_like_demonym(word: str) -> bool:
    return len(word) >= 6 and word.endswith(_DEMONYM_SUFFIXES)


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z\-']{1,}", text.lower())


class RelevanceScorer:
    """
    Scores arbitrary text for topical relevance against a mission string.

    Two signals are combined:
      1. Lexical/phrase overlap (unigrams + weak-word/demonym filtering) --
         dependency-free, always available, works offline.
      2. Semantic similarity via embeddings, when a backend is reachable
         (see khabrichacha/core/embeddings.py) -- catches genuinely
         relevant text that shares almost no literal words with the
         mission (paraphrases, synonyms), which the lexical signal alone
         structurally cannot recognize. This mirrors the embedding-based
         reranking step used by tools like Perplexica.

    Embeddings are an enhancement, not a requirement: if no backend is
    configured (no Ollama embedding model pulled, no OPENAI_API_KEY/
    GEMINI_API_KEY set), semantic_score() returns None immediately and
    is_relevant() falls back to the lexical-only behavior that already
    existed, unchanged.
    """

    def __init__(self, mission: str, min_keyword_len: int = 3, use_embeddings: bool = True):
        self.mission = mission or ""
        self.keywords = self._extract_keywords(self.mission, min_keyword_len)
        self._use_embeddings = use_embeddings
        # None = not yet attempted; False = attempted and unavailable;
        # a list = the mission's cached embedding vector.
        self._mission_embedding: "Optional[List[float]] | bool" = None

    @staticmethod
    def _extract_keywords(text: str, min_len: int) -> List[str]:
        words = _tokenize(text)
        return [w for w in words if len(w) >= min_len and w not in _STOPWORDS]

    @staticmethod
    def _word_matches(keyword: str, text_words: Set[str]) -> bool:
        if keyword in text_words:
            return True
        # Cheap stemming heuristic: treat a shared 6+ character prefix as a
        # match, so simple morphological variants line up (e.g. "accident"
        # / "accidents", "govern" / "governmental") without a real stemmer
        # dependency. The minimum was deliberately raised from 4 to 6
        # characters after 4 proved too short in practice: short words
        # sharing just a 4-char prefix (e.g. "India" / "Indian") matched
        # far too eagerly, letting completely unrelated content (a car
        # marketplace, a Q&A site) through on that single coincidental
        # match alone. Requiring 6+ shared characters still catches real
        # morphological variants while no longer treating "India"/"Indian"
        # or similarly short pairs as equivalent.
        if len(keyword) >= 6:
            prefix = keyword[:6]
            for w in text_words:
                if len(w) >= 6 and w[:6] == prefix:
                    return True
        return False

    def _matched_keywords(self, text_words: Set[str]) -> List[str]:
        return [kw for kw in self.keywords if self._word_matches(kw, text_words)]

    def _get_mission_embedding(self):
        if not self._use_embeddings or not self.mission:
            return None
        if self._mission_embedding is None:
            from khabrichacha.core.embeddings import get_shared_embedder
            vec = get_shared_embedder().embed(self.mission)
            self._mission_embedding = vec if vec is not None else False
        return self._mission_embedding or None

    def semantic_score(self, text: str) -> Optional[float]:
        """
        Cosine similarity between the mission and `text`, or None if no
        embedding backend is available (or `text` is empty). Callers
        should treat None as "couldn't judge semantically" and fall back
        to lexical scoring, not as "definitely irrelevant."
        """
        mission_vec = self._get_mission_embedding()
        if not mission_vec or not text:
            return None
        from khabrichacha.core.embeddings import get_shared_embedder, cosine_similarity
        text_vec = get_shared_embedder().embed(text)
        if not text_vec:
            return None
        return cosine_similarity(mission_vec, text_vec)

    def score(self, text: str) -> float:
        """
        Returns the fraction (0.0-1.0) of the mission's keywords that
        appear (or closely match) somewhere in `text`. This is the
        lexical signal only (see semantic_score() for the embedding-based
        one) -- kept separate because callers like the numeric-consensus
        keyword extraction want the raw lexical keyword set, not a
        blended relevance verdict. A mission with no extractable keywords
        (e.g. empty string) always scores 0.0 for any non-empty text,
        which callers should treat as "can't judge, don't filter" rather
        than "definitely irrelevant" -- see `is_relevant`'s
        `default_if_no_keywords`.
        """
        if not text or not self.keywords:
            return 0.0
        text_words = set(_tokenize(text))
        if not text_words:
            return 0.0
        hits = len(self._matched_keywords(text_words))
        return hits / len(self.keywords)

    def is_relevant(
        self,
        text: str,
        threshold: float = 0.2,
        default_if_no_keywords: bool = True,
        semantic_high: float = 0.42,
        semantic_low: float = 0.15,
    ) -> bool:
        """
        Checks semantic similarity first when an embedding backend is
        available: a confidently HIGH score (>= semantic_high) accepts
        the text outright, and a confidently LOW one (<= semantic_low)
        rejects it outright, since a real embedding model recognizing
        "this text is about something else entirely" is stronger
        evidence than a coincidental keyword match either way. Scores in
        between are genuinely ambiguous (or no embedding backend is
        configured at all), so those fall through to the lexical check
        below -- unchanged from before embeddings existed.

        Note: cosine-similarity thresholds vary somewhat by embedding
        model; 0.42/0.15 are reasonable starting points for short
        text (nomic-embed-text, OpenAI text-embedding-3-small) but may
        need light tuning for a different model.

        threshold=0.2 (for the lexical fallback) means "at least a fifth
        of the mission's distinct subject-matter keywords show up in this
        text." That's deliberately forgiving -- the goal is to catch
        content that's plainly about a different topic altogether, not
        to demand near-total keyword overlap.

        On top of the fractional threshold, at least one matched keyword
        must be neither a generic institutional word (`_WEAK_CONTEXT_WORDS`)
        nor a demonym/nationality adjective (`_looks_like_demonym`) --
        unless every one of the mission's own keywords happens to fall into
        those categories, in which case there's nothing stronger to
        require. Matching only "government", "central", and "Indian"
        (however many of them) isn't sufficient evidence that a source is
        really about the mission's actual subject rather than merely
        adjacent to it -- e.g. a country's farmer-subsidy portal will
        legitimately contain "Indian" and "Central Government" without
        being about that country's budget at all.
        """
        if not self.keywords:
            return default_if_no_keywords
        if not text:
            return False

        sem_score = self.semantic_score(text)
        if sem_score is not None:
            if sem_score >= semantic_high:
                return True
            if sem_score <= semantic_low:
                return False
            # Ambiguous zone -- fall through to the lexical check.

        text_words = set(_tokenize(text))
        if not text_words:
            return False
        matched = self._matched_keywords(text_words)
        if len(matched) / len(self.keywords) < threshold:
            return False

        def _is_weak(kw: str) -> bool:
            return kw in _WEAK_CONTEXT_WORDS or _looks_like_demonym(kw)

        strong_keywords_exist = any(not _is_weak(kw) for kw in self.keywords)
        if not strong_keywords_exist:
            # Every mission keyword happens to be generic/institutional or
            # demonym-shaped -- nothing stronger to require beyond the
            # fractional threshold already checked above.
            return True
        return any(not _is_weak(kw) for kw in matched)

    def filter_relevant(
        self,
        items: Iterable[str],
        threshold: float = 0.2,
    ) -> List[int]:
        """Convenience: returns the indices of `items` that pass the relevance bar."""
        return [i for i, text in enumerate(items) if self.is_relevant(text, threshold=threshold)]
