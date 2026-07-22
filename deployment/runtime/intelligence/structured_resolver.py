import re
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
from deployment.runtime.extraction.structured_extractor import StructuredExtractor
from deployment.runtime.intelligence.numerical_validator import NumericalValidator
from deployment.runtime.intelligence.consensus_engine import ConsensusEngine
from deployment.runtime.models.structured_document import StructuredDocument
from deployment.runtime.models.consensus_result import ConsensusResult

# Generic words that shouldn't count as "topic keywords" when deciding
# whether a number found in a document is actually relevant to the
# mission (see StructuredResolver.extract_numeric_consensus).
_GENERIC_STOPWORDS = {
    "find", "give", "show", "tell", "please", "total", "number", "numbers",
    "worldwide", "world", "wide", "happened", "happen", "have", "has", "had",
    "been", "with", "since", "that", "this", "there", "about", "over", "many",
    "much", "into", "from", "what", "when", "where", "which", "does", "doing",
}


class StructuredResolver:
    """
    Resolves, extracts, validates, and optionally merges structured data (tables/JSON)
    from multiple fetched documents without using an LLM. 
    Bypasses narrative LLM generation.
    """
    
    def __init__(self):
        self.extractor = StructuredExtractor()
        self.validator = NumericalValidator()
        self.consensus_engine = ConsensusEngine()

    def resolve(self, documents: List[Dict[str, Any]]) -> Tuple[List[StructuredDocument], List[str]]:
        """
        Extracts structured data from documents and validates them.
        Returns a tuple of (List of StructuredDocuments, List of warnings).
        """
        structured_docs = []
        warnings = []
        
        for doc_info in documents:
            url = doc_info.get("url", "")

            # Prefer real, raw HTML tables when fetch_page.py preserved any
            # (see khabrichacha/tools/builtin/fetch_page.py) -- the plain
            # "content" field has already had all table structure stripped
            # out by soup.get_text(), so StructuredExtractor could never
            # find a literal "<table" there even when the source page
            # genuinely had one.
            found_any_table = False
            for table_html in doc_info.get("tables_html", []) or []:
                table_doc = self.extractor.extract(table_html, url)
                if table_doc.is_structured:
                    val_res = self.validator.validate(table_doc)
                    if val_res.warnings:
                        warnings.extend(val_res.warnings)
                    structured_docs.append(table_doc)
                    found_any_table = True

            if found_any_table:
                continue

            content = doc_info.get("content", "")
            doc = self.extractor.extract(content, url)
            
            if doc.is_structured:
                val_res = self.validator.validate(doc)
                if val_res.warnings:
                    warnings.extend(val_res.warnings)
                structured_docs.append(doc)
                
        return structured_docs, warnings

    def build_unified_table(self, docs: List[StructuredDocument]) -> Optional[Dict[str, Any]]:
        """
        Merges tables that share the same header shape across multiple
        source documents into one combined table, instead of keeping only
        the single largest table and silently discarding every other
        source's rows. Tables with a different shape aren't dropped either
        — they're returned under "additional_tables" so nothing found is
        lost, even if it couldn't be merged into the primary table.
        """
        if not docs:
            return None

        def _norm_headers(headers: List[str]) -> Tuple[str, ...]:
            return tuple(h.strip().lower() for h in headers) if headers else ("__no_header__",)

        groups: Dict[Tuple[str, ...], List[StructuredDocument]] = {}
        for doc in docs:
            groups.setdefault(_norm_headers(doc.headers), []).append(doc)

        # Merge whichever group has the most *combined* rows across all its
        # source documents — this is the key change from "keep the single
        # biggest table" to "combine agreeing sources".
        best_key = max(groups, key=lambda k: sum(len(d.rows) for d in groups[k]))
        best_group = groups[best_key]

        merged_rows: List[List[str]] = []
        sources: List[str] = []
        for doc in best_group:
            merged_rows.extend(doc.rows)
            if doc.source_url:
                sources.append(doc.source_url)

        primary_headers = next((d.headers for d in best_group if d.headers), [])
        primary_title = next((d.title for d in best_group if d.title), "Extracted Numerical Data")

        additional_tables = []
        for key, group in groups.items():
            if key == best_key:
                continue
            for doc in group:
                if doc.rows:
                    additional_tables.append({
                        "title": doc.title or "Additional data (different shape)",
                        "headers": doc.headers,
                        "rows": doc.rows,
                        "source_url": doc.source_url,
                    })

        result = {
            "title": primary_title,
            "headers": primary_headers,
            "rows": merged_rows,
            "sources": sources,
        }
        if additional_tables:
            result["additional_tables"] = additional_tables
        return result

    def count_entity_occurrences_in_table(self, mission: str, table: Optional[Dict[str, Any]]) -> Optional[str]:
        """
        For "how many times has X done Y" style questions where a genuine
        table was actually extracted (e.g. a Wikipedia list of winners by
        year), derive the count directly from the table instead of leaving
        it to be manually counted from a rendered table, or -- worse --
        letting the numeric-consensus mechanism grab an unrelated number.

        General approach, no hardcoded subject knowledge: extract the
        mission's own keywords (the same way RelevanceScorer does), then
        count how many table rows contain each keyword in any cell. The
        keyword with the most matching rows is treated as the "entity"
        being counted (e.g. "India" as a value in a "Winner" column) --
        this works for any table/mission pairing where the answer is
        "how many rows mention X", not just this one example.
        """
        if not table or not table.get("rows"):
            return None

        from khabrichacha.core.relevance import RelevanceScorer
        keywords = RelevanceScorer(mission).keywords
        if not keywords:
            return None

        rows = table["rows"]
        best_keyword, best_count = None, 0
        for kw in keywords:
            count = 0
            for row in rows:
                row_text = " ".join(str(c) for c in row).lower()
                if kw in row_text or (len(kw) >= 6 and any(kw[:6] == w[:6] for w in row_text.split() if len(w) >= 6)):
                    count += 1
            if count > best_count:
                best_keyword, best_count = kw, count

        if best_keyword and best_count > 0:
            return (
                f"**Based on the extracted table below, \"{best_keyword.title()}\" appears "
                f"in {best_count} row(s) — i.e. {best_count} occurrence(s) found in the data.**"
            )
        return None

    # A bare (no comma-grouping, no unit) 4-digit number in this range is
    # treated as a probable calendar-year reference rather than a real
    # quantity -- source articles reporting a statistic overwhelmingly
    # also mention the year it was measured in right next to it (e.g.
    # "As of 2016, the network spanned..."), so a plain "closest
    # keyword-adjacent number" search regularly finds the year sitting
    # closer to the topic's keywords than the actual figure. A number
    # WITH a unit (km, %, million...) or WITH comma-grouping is never
    # excluded by this check, even if its digits fall in this range,
    # since either is strong evidence it's a genuine quantity rather
    # than a date -- e.g. "1,900 km" or "1900 km" are still accepted,
    # only a bare "1900" with nothing else attached is treated as
    # probably a year.
    _PLAUSIBLE_YEAR_RANGE = (1500, 2099)

    @classmethod
    def _looks_like_bare_year(cls, raw_number_str: str, unit: str) -> bool:
        if unit or "," in raw_number_str or "." in raw_number_str or len(raw_number_str) != 4:
            return False
        try:
            year = int(raw_number_str)
        except ValueError:
            return False
        return cls._PLAUSIBLE_YEAR_RANGE[0] <= year <= cls._PLAUSIBLE_YEAR_RANGE[1]

    def extract_numeric_consensus(self, mission: str, documents: List[Dict[str, Any]]) -> Optional[ConsensusResult]:
        """
        Cross-source numeric aggregation for queries like "total aviation
        accidents worldwide" that don't neatly present as an HTML/markdown
        table anywhere. Scans each document's raw text for numbers that
        appear near one of the mission's distinctive keywords, weights each
        candidate by the source's trust score, and reconciles them through
        ConsensusEngine — so the final answer states a resolved value plus
        which sources agree or conflict, instead of an LLM silently picking
        whichever number happened to be first in its context window.

        Returns None if no keyword-adjacent numbers were found in at least
        one document (nothing to reconcile).
        """
        keywords = [w.strip(".,()?!:;\"'").lower() for w in mission.split()]
        keywords = [w for w in keywords if len(w) > 3 and w not in _GENERIC_STOPWORDS]
        if not keywords:
            return None

        number_pattern = re.compile(
            r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*"
            r"(%|percent|million|billion|thousand|crore|lakh|km|kilometers?|kilometres?|miles?)?",
            re.IGNORECASE,
        )

        source_values = []
        for doc in documents:
            content = doc.get("content", "") or doc.get("snippet", "")
            if not content:
                continue
            lower = content.lower()
            best_val = None
            best_score = 0
            for match in number_pattern.finditer(content):
                raw_number_str = match.group(1)
                unit = (match.group(2) or "").lower()
                if self._looks_like_bare_year(raw_number_str, unit):
                    continue
                start, end = match.span()
                window = lower[max(0, start - 60): end + 60]
                score = sum(1 for kw in keywords if kw in window)
                if score <= 0:
                    continue
                # Small preference for numbers that carry a unit or
                # comma-grouping over bare unit-less ones at the same
                # keyword-adjacency score -- genuine quantities are
                # usually written with one or the other.
                if unit or "," in raw_number_str:
                    score += 0.5
                try:
                    val = float(raw_number_str.replace(",", ""))
                except Exception:
                    continue
                if unit == "thousand":
                    val *= 1_000
                elif unit == "million":
                    val *= 1_000_000
                elif unit == "billion":
                    val *= 1_000_000_000
                if score > best_score or best_val is None:
                    best_score = score
                    best_val = val
            if best_val is not None:
                trust = doc.get("trust_score", 50.0) / 100.0
                source_values.append({
                    "source_name": doc.get("url", "unknown source"),
                    "value": best_val,
                    "weight": trust,
                })

        if not source_values:
            return None

        return self.consensus_engine.verify_numerical(mission, source_values)
