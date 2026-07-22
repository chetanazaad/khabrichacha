"""
khabrichacha/core/grounding.py

A lightweight, general-purpose check for whether the numeric claims in a
synthesized answer are actually traceable to the retrieved evidence it was
supposedly built from. This exists because none of the LLM synthesis
prompts in this codebase enforced or verified per-claim grounding: a model
summarizing dozens of retrieved documents can (and, on small/local models
especially, does) state figures that sound plausible but don't trace back
to anything actually retrieved -- confident-sounding paraphrase rather
than a verifiable, sourced claim.

This is not a full fact-checker (no NLI/entailment model is used, so it
can't tell you a claim is *wrong* -- only that a specific number doesn't
appear anywhere in what was retrieved, which is a strong hint that it was
invented, misremembered, or pulled from the model's general training
knowledge rather than the provided sources). It's intentionally general
-- it works on any answer/evidence pair, with no topic-specific logic.
"""
from __future__ import annotations

import re
from typing import List, Tuple

# Fiscal-year-range identifiers like "2025-26" or "2026-27" are dates, not
# statistics -- strip them before number extraction so their trailing
# 2-digit half ("26", "27"...) never gets treated as a standalone claim
# needing grounding.
_YEAR_RANGE_PATTERN = re.compile(r"\b(19|20)\d{2}-\d{2}\b")

# Matches things like: 4.40%, 1,476,625,576, 55.6%, $1000, 30,254
_NUMBER_PATTERN = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*(%|percent|million|billion|thousand|crore|lakh)?",
    re.IGNORECASE,
)

# A bare (unit-less) 4-digit number that looks like a plain calendar year
# is almost always incidental ("the 2026 budget") rather than a factual
# claim worth grounding.
_SKIP_IF_BARE_YEAR = re.compile(r"^(19|20)\d{2}$")


def _normalize_number(raw: str) -> str:
    return raw.replace(",", "").rstrip(".")


def extract_numeric_claims(text: str) -> List[Tuple[str, str]]:
    """Returns a list of (number, matched_unit_or_empty) tuples found in `text`."""
    text = _YEAR_RANGE_PATTERN.sub(" ", text)
    claims = []
    for match in _NUMBER_PATTERN.finditer(text):
        number = _normalize_number(match.group(1))
        unit = (match.group(2) or "").strip()
        if not unit and _SKIP_IF_BARE_YEAR.match(number):
            continue
        claims.append((number, unit))
    return claims


def find_ungrounded_claims(answer: str, evidence: str, min_len: int = 2) -> List[str]:
    """
    Returns the distinct numeric claims (as display strings like "4.40%")
    found in `answer` that don't appear (in normalized form) anywhere in
    `evidence`. An empty list means every numeric claim in the answer was
    at least traceable to something in the retrieved evidence -- it does
    NOT mean the answer is otherwise accurate, just that this particular
    hallucination signal didn't fire.

    `min_len` only applies to bare, unit-less numbers (ambiguous with list
    markers, ordinals, page numbers, etc.) -- a number with an explicit
    unit like "%" or "million" is treated as a real claim worth checking
    regardless of how many digits it has, since e.g. "1%" is just as much
    a checkable statistic as "41%".
    """
    if not answer or not evidence:
        return []

    evidence_numbers = set()
    for number, _unit in extract_numeric_claims(evidence):
        evidence_numbers.add(number)

    ungrounded = []
    seen = set()
    for number, unit in extract_numeric_claims(answer):
        if number in seen:
            continue
        if not unit and len(number) < min_len:
            continue
        if number not in evidence_numbers:
            seen.add(number)
            display = f"{number}{'%' if unit == '%' else (' ' + unit if unit else '')}"
            ungrounded.append(display)
    return ungrounded


GROUNDING_INSTRUCTION = (
    "Ground every factual claim in the retrieved evidence provided above. "
    "Only state a specific number, statistic, or fact if it is explicitly "
    "present in that evidence -- do not fill in gaps from general/background "
    "knowledge, and do not estimate or infer figures that were not actually "
    "retrieved. If the evidence doesn't fully answer the question, say so "
    "plainly rather than completing the answer from memory."
)
