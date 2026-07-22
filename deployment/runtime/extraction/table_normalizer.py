import re
import csv
from io import StringIO
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup
from loguru import logger

class NormalizedTable(BaseModel):
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)
    source_format: str = ""   # "html" | "csv" | "markdown"

class TableNormalizer:
    """Parses various raw text formats and extracts cleanly normalized tables."""

    def from_html(self, html: str) -> List[NormalizedTable]:
        """Extracts tables from raw HTML content."""
        normalized_tables = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            tables = soup.find_all("table")
            
            for table in tables:
                headers = []
                rows = []
                
                # Check thead
                thead = table.find("thead")
                if thead:
                    th_tags = thead.find_all("th")
                    headers = [tag.get_text(strip=True) for tag in th_tags]
                
                # Find all table rows
                tr_tags = table.find_all("tr")
                for tr in tr_tags:
                    # If th tags inside tr and headers is empty
                    th_tags = tr.find_all("th")
                    if th_tags and not headers:
                        headers = [tag.get_text(strip=True) for tag in th_tags]
                        continue
                        
                    td_tags = tr.find_all("td")
                    if td_tags:
                        row = [tag.get_text(strip=True) for tag in td_tags]
                        rows.append(row)
                        
                if rows:
                    # If no headers found, generate default column headers
                    if not headers:
                        headers = [f"Column_{i+1}" for i in range(len(rows[0]))]
                    normalized_tables.append(NormalizedTable(
                        headers=headers,
                        rows=rows,
                        source_format="html"
                    ))
        except Exception as e:
            logger.error(f"Failed to parse HTML tables: {e}")
            
        return normalized_tables

    def from_csv(self, csv_text: str) -> NormalizedTable:
        """Extracts a table from CSV text."""
        headers = []
        rows = []
        try:
            f = StringIO(csv_text.strip())
            reader = csv.reader(f)
            for idx, row in enumerate(reader):
                if idx == 0:
                    headers = row
                else:
                    rows.append(row)
        except Exception as e:
            logger.error(f"Failed to parse CSV table: {e}")

        # If headers is empty but rows has data
        if not headers and rows:
            headers = [f"Column_{i+1}" for i in range(len(rows[0]))]
            
        return NormalizedTable(
            headers=headers,
            rows=rows,
            source_format="csv"
        )

    def from_markdown(self, md_text: str) -> List[NormalizedTable]:
        """Extracts tables from Markdown formatted text."""
        normalized_tables = []
        try:
            # Markdown table regex detection
            # Find groups of lines starting/ending with |
            lines = md_text.splitlines()
            current_table_lines = []
            
            for line in lines:
                cleaned = line.strip()
                if cleaned.startswith("|") and cleaned.endswith("|"):
                    current_table_lines.append(cleaned)
                else:
                    if len(current_table_lines) >= 3: # Must include header, separator, row
                        table = self._parse_md_table_lines(current_table_lines)
                        if table:
                            normalized_tables.append(table)
                    current_table_lines = []
                    
            # Parse final table if exists
            if len(current_table_lines) >= 3:
                table = self._parse_md_table_lines(current_table_lines)
                if table:
                    normalized_tables.append(table)
        except Exception as e:
            logger.error(f"Failed to parse Markdown tables: {e}")
            
        return normalized_tables

    def _parse_md_table_lines(self, lines: List[str]) -> Optional[NormalizedTable]:
        try:
            headers = [cell.strip() for cell in lines[0].split("|")[1:-1]]
            rows = []
            # Line 1 is separator (e.g. |---|---|)
            for line in lines[2:]:
                row = [cell.strip() for cell in line.split("|")[1:-1]]
                rows.append(row)
            return NormalizedTable(
                headers=headers,
                rows=rows,
                source_format="markdown"
            )
        except Exception:
            return None
