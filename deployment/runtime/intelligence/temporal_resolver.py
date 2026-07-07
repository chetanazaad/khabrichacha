import re
from datetime import datetime
from pydantic import BaseModel, Field

class TemporalContext(BaseModel):
    """Holds parsed temporal metadata representing dates, time ranges, and fiscal years."""
    original: str
    time_range_start: str = ""
    time_range_end: str = ""
    reference_date: str = ""
    is_financial_year: bool = False
    is_relative: bool = False

class TemporalResolver:
    """Detects, parses, and normalizes temporal expressions in queries or search queries."""

    def resolve(self, text: str) -> TemporalContext:
        cleaned_text = text.strip().lower()
        now = datetime.now()
        current_year = now.year
        
        ctx = TemporalContext(
            original=text,
            reference_date=now.strftime("%Y-%m-%d")
        )

        # 1. Check for range patterns like "2020-2025" or "2020 to 2025"
        range_match = re.search(r'\b(20\d{2})\s*(?:-|to)\s*(20\d{2})\b', cleaned_text)
        if range_match:
            ctx.time_range_start = f"{range_match.group(1)}-01-01"
            ctx.time_range_end = f"{range_match.group(2)}-12-31"
            return ctx

        # 2. Check for Fiscal Year like "fy2024", "fy 2025" or "fy 24"
        fy_match = re.search(r'\bfy\s*(20\d{2}|\d{2})\b', cleaned_text)
        if fy_match:
            year_str = fy_match.group(1)
            # Expand "24" to "2024"
            if len(year_str) == 2:
                year_str = "20" + year_str
            year = int(year_str)
            ctx.time_range_start = f"{year-1}-04-01"
            ctx.time_range_end = f"{year}-03-31"
            ctx.is_financial_year = True
            return ctx

        # 3. Check for relative dates
        if "today" in cleaned_text or "current" in cleaned_text or "latest" in cleaned_text:
            ctx.time_range_start = now.strftime("%Y-%m-%d")
            ctx.time_range_end = now.strftime("%Y-%m-%d")
            ctx.is_relative = True
            return ctx
            
        if "last year" in cleaned_text:
            ctx.time_range_start = f"{current_year-1}-01-01"
            ctx.time_range_end = f"{current_year-1}-12-31"
            ctx.is_relative = True
            return ctx

        if "last quarter" in cleaned_text:
            # Simple approximation
            ctx.time_range_start = f"{current_year}-01-01"
            ctx.time_range_end = f"{current_year}-03-31"
            ctx.is_relative = True
            return ctx

        # 4. Check for single year match e.g. "2024"
        year_match = re.search(r'\b(20\d{2})\b', cleaned_text)
        if year_match:
            year = year_match.group(1)
            ctx.time_range_start = f"{year}-01-01"
            ctx.time_range_end = f"{year}-12-31"
            return ctx

        return ctx
