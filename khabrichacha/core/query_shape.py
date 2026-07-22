"""
khabrichacha/core/query_shape.py

Lightweight, general-purpose detection of a mission's *answer shape* --
not its subject matter, but the kind of answer it's asking for. This
matters because different answer shapes need fundamentally different
extraction strategies:

  - "total X", "how many X are there", "what is the population of Y" ask
    for a QUANTITY, which is very often directly stated as a single
    number somewhere in a good source (e.g. "the population is 1.4
    billion"). Reconciling "the nearest topic-adjacent number across
    sources" works reasonably well here.

  - "how many times has X won Y", "how often does Z happen" ask for a
    COUNT OF DISCRETE OCCURRENCES, which source material almost always
    represents as a LIST of individual events/dates rather than a single
    stated summary number (e.g. a list of World Cup winners by year, not
    a sentence saying "India has won 2 times"). Blindly reconciling "the
    nearest topic-adjacent number across sources" for this shape tends to
    pick up unrelated numbers that happen to sit near the topic's
    keywords -- tournament years, list indices, dates -- rather than the
    actual count, because the count itself typically isn't written down
    anywhere; it has to be derived by counting list entries.

This is intentionally a shape/pattern classifier, not a subject-matter
one -- it works the same way regardless of whether the query is about
cricket, elections, hurricanes, or awards ceremonies.
"""
from __future__ import annotations

import re

_OCCURRENCE_COUNT_PATTERNS = [
    re.compile(r"\bhow many times\b", re.IGNORECASE),
    re.compile(r"\bhow often\b", re.IGNORECASE),
    re.compile(r"\bnumber of times\b", re.IGNORECASE),
    re.compile(r"\bhow many occasions\b", re.IGNORECASE),
    re.compile(r"\bcount of times\b", re.IGNORECASE),
    re.compile(r"\bhow many times (?:has|have|did|does)\b", re.IGNORECASE),
]


def is_occurrence_count_query(mission: str) -> bool:
    """
    True for questions asking "how many times has X happened/won/done Y"
    -- a count of discrete, individually-dated occurrences -- as opposed
    to a query asking for a directly-stated aggregate quantity ("total X",
    "how many X are there").
    """
    if not mission:
        return False
    return any(p.search(mission) for p in _OCCURRENCE_COUNT_PATTERNS)


OCCURRENCE_COUNT_INSTRUCTION = (
    "This question asks for a COUNT of how many times a specific event "
    "occurred (not a single number that's directly stated anywhere). "
    "Carefully read through the provided evidence, identify each "
    "individual instance/occurrence relevant to the question (e.g. each "
    "year or date the event happened), count them precisely, and state "
    "the final count clearly. List the specific instances you counted "
    "(e.g. the individual years) so the count can be verified. If the "
    "evidence doesn't contain enough information to count confidently, "
    "say so explicitly rather than guessing a number."
)
