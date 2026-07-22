import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from deployment.runtime.models.structured_document import StructuredDocument

class ValidationResult(BaseModel):
    """Holds results of numerical validation on structured tables."""
    is_valid: bool = True
    warnings: List[str] = Field(default_factory=list)
    corrections: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = 1.0

class NumericalValidator:
    """Validates numerical integrity of extracted tables (sums, percentages, averages, growth)."""

    def validate(self, doc: StructuredDocument) -> ValidationResult:
        warnings = []
        corrections = []
        
        if not doc.is_structured or not doc.rows or not doc.headers:
            return ValidationResult(is_valid=True)

        # 1. Identify numeric columns
        numeric_col_indices = []
        for col_idx in range(len(doc.headers)):
            # Check if majority of rows in this column contain numbers
            num_count = 0
            for row in doc.rows:
                if col_idx < len(row):
                    cell = row[col_idx].replace(",", "").replace("$", "").replace("%", "").strip()
                    # Check if cell matches a numeric float/int
                    if re.match(r'^\-?\d+(?:\.\d+)?$', cell):
                        num_count += 1
            if len(doc.rows) > 0 and (num_count / len(doc.rows)) >= 0.7:
                numeric_col_indices.append(col_idx)

        # 2. Check for duplicate rows
        seen_rows = set()
        for idx, row in enumerate(doc.rows):
            row_str = str(row)
            if row_str in seen_rows:
                warnings.append(f"Row {idx+1} is a exact duplicate of a previous row.")
            seen_rows.add(row_str)

        # 3. Sum Validation (check if any row represents a 'Total' that matches the sum of others)
        for col_idx in numeric_col_indices:
            total_row_idx = -1
            other_values = []
            reported_total = 0.0
            
            for row_idx, row in enumerate(doc.rows):
                if col_idx < len(row):
                    cell_val = self._parse_float(row[col_idx])
                    if cell_val is None:
                        continue
                        
                    # Check if the row title suggests a total
                    row_title = str(row[0]).lower() if len(row) > 0 else ""
                    if "total" in row_title or "sum" in row_title:
                        total_row_idx = row_idx
                        reported_total = cell_val
                    else:
                        other_values.append(cell_val)
                        
            if total_row_idx != -1 and other_values:
                calculated_sum = sum(other_values)
                # Check for floating point tolerance (1% tolerance)
                diff = abs(calculated_sum - reported_total)
                tolerance = 0.01 * max(abs(reported_total), 1.0)
                if diff > tolerance:
                    warnings.append(
                        f"Inconsistent total in column '{doc.headers[col_idx]}'. "
                        f"Reported total: {reported_total}, Calculated sum of rows: {calculated_sum:.2f}."
                    )
                    corrections.append({
                        "column": doc.headers[col_idx],
                        "type": "total_mismatch",
                        "reported": reported_total,
                        "calculated": calculated_sum
                    })

        # 4. Percentage validation (check if columns indicating percentage sum to ~100%)
        pct_col_indices = []
        for col_idx in numeric_col_indices:
            header_lower = doc.headers[col_idx].lower()
            if "percent" in header_lower or "%" in header_lower or "share" in header_lower:
                pct_col_indices.append(col_idx)

        for col_idx in pct_col_indices:
            pct_sum = 0.0
            for row in doc.rows:
                if col_idx < len(row):
                    val = self._parse_float(row[col_idx])
                    if val is not None:
                        # Normalize 0.0-1.0 to percent if needed (simple check)
                        if val <= 1.0 and any(self._parse_float(r[col_idx]) > 1.0 for r in doc.rows if col_idx < len(r) and self._parse_float(r[col_idx]) is not None):
                            val = val * 100.0
                        pct_sum += val
            
            # Check if sum is close to 100% (within 5% tolerance to allow rounding errors/other categories)
            if pct_sum > 0.0 and abs(pct_sum - 100.0) > 5.0 and abs(pct_sum - 1.0) > 0.05:
                warnings.append(
                    f"Percentage column '{doc.headers[col_idx]}' sums to {pct_sum:.1f}% instead of 100%."
                )

        confidence = 1.0 - (len(warnings) * 0.15)
        confidence = max(confidence, 0.3)

        return ValidationResult(
            is_valid=len(warnings) == 0,
            warnings=warnings,
            corrections=corrections,
            confidence=confidence
        )

    def _parse_float(self, val_str: str) -> Optional[float]:
        try:
            clean = val_str.replace(",", "").replace("$", "").replace("%", "").strip()
            return float(clean)
        except Exception:
            return None
