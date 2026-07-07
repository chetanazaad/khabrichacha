import json
import re
from typing import List, Dict, Any
from loguru import logger
from deployment.runtime.models.structured_document import StructuredDocument
from deployment.runtime.extraction.table_normalizer import TableNormalizer

class StructuredExtractor:
    """Detects, parses, and extracts structured documents (CSV, JSON, HTML tables) from raw text."""

    def __init__(self):
        self.normalizer = TableNormalizer()

    def extract(self, content: str, url: str) -> StructuredDocument:
        """
        Parses page content and extracts structured data (such as tables or JSON).
        """
        if not content:
            return StructuredDocument(document_type="text", source_url=url, is_structured=False)

        cleaned_content = content.strip()

        # 1. Check if content is pure JSON
        if (cleaned_content.startswith("{") and cleaned_content.endswith("}")) or \
           (cleaned_content.startswith("[") and cleaned_content.endswith("]")):
            try:
                parsed_json = json.loads(cleaned_content)
                return StructuredDocument(
                    document_type="json",
                    source_url=url,
                    normalized_json=parsed_json if isinstance(parsed_json, dict) else {"data": parsed_json},
                    raw_content=content,
                    is_structured=True,
                    confidence=1.0
                )
            except Exception:
                pass

        # 2. Check for HTML tables (in case raw HTML is passed)
        if "<table" in cleaned_content:
            html_tables = self.normalizer.from_html(content)
            if html_tables:
                table = html_tables[0]
                return StructuredDocument(
                    document_type="table",
                    title=f"Extracted Table from {url}",
                    headers=table.headers,
                    rows=table.rows,
                    source_url=url,
                    raw_content=content,
                    is_structured=True,
                    confidence=0.85
                )

        # 3. Check for Markdown tables
        md_tables = self.normalizer.from_markdown(content)
        if md_tables:
            table = md_tables[0]
            return StructuredDocument(
                document_type="table",
                title=f"Extracted Markdown Table from {url}",
                headers=table.headers,
                rows=table.rows,
                source_url=url,
                raw_content=content,
                is_structured=True,
                confidence=0.90
            )

        # 4. Check for CSV-like structure (multiple lines with comma separation)
        # Simple heuristic: at least 3 lines, each having the same number of commas (>= 2 commas per line)
        lines = [line.strip() for line in cleaned_content.splitlines() if line.strip()]
        if len(lines) >= 3:
            comma_counts = [line.count(",") for line in lines[:5]]
            if len(comma_counts) >= 3 and len(set(comma_counts)) == 1 and comma_counts[0] >= 2:
                try:
                    table = self.normalizer.from_csv(cleaned_content)
                    if table.rows:
                        return StructuredDocument(
                            document_type="csv",
                            title=f"Extracted CSV from {url}",
                            headers=table.headers,
                            rows=table.rows,
                            source_url=url,
                            raw_content=content,
                            is_structured=True,
                            confidence=0.85
                        )
                except Exception:
                    pass

        # Determine document type category based on keywords if text-only
        doc_type = "text"
        content_lower = cleaned_content.lower()
        if "budget" in content_lower:
            doc_type = "budget"
        elif "gdp" in content_lower:
            doc_type = "gdp"
        elif "population" in content_lower:
            doc_type = "population"
        elif "election" in content_lower:
            doc_type = "election"
        elif "weather" in content_lower:
            doc_type = "weather"
        elif "financial" in content_lower or "balance sheet" in content_lower:
            doc_type = "financials"

        return StructuredDocument(
            document_type=doc_type,
            source_url=url,
            raw_content=content,
            is_structured=False,
            confidence=0.5
        )
