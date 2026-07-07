from typing import List, Dict, Any, Tuple
from loguru import logger
from deployment.runtime.extraction.structured_extractor import StructuredExtractor
from deployment.runtime.intelligence.numerical_validator import NumericalValidator
from deployment.runtime.models.structured_document import StructuredDocument

class StructuredResolver:
    """
    Resolves, extracts, validates, and optionally merges structured data (tables/JSON)
    from multiple fetched documents without using an LLM. 
    Bypasses narrative LLM generation.
    """
    
    def __init__(self):
        self.extractor = StructuredExtractor()
        self.validator = NumericalValidator()

    def resolve(self, documents: List[Dict[str, Any]]) -> Tuple[List[StructuredDocument], List[str]]:
        """
        Extracts structured data from documents and validates them.
        Returns a tuple of (List of StructuredDocuments, List of warnings).
        """
        structured_docs = []
        warnings = []
        
        for doc_info in documents:
            url = doc_info.get("url", "")
            content = doc_info.get("content", "")
            
            doc = self.extractor.extract(content, url)
            
            if doc.is_structured:
                val_res = self.validator.validate(doc)
                if val_res.warnings:
                    warnings.extend(val_res.warnings)
                structured_docs.append(doc)
                
        # Future improvement: Merge tables with matching headers here
        
        return structured_docs, warnings

    def build_unified_table(self, docs: List[StructuredDocument]) -> Dict[str, Any]:
        """
        Builds a unified representation of the first valid table, or a merged one.
        """
        if not docs:
            return None
            
        # For now, we take the largest or first table.
        # Let's find the table with the most rows
        best_doc = docs[0]
        max_rows = len(best_doc.rows) if best_doc.rows else 0
        
        for doc in docs[1:]:
            if doc.rows and len(doc.rows) > max_rows:
                best_doc = doc
                max_rows = len(doc.rows)
                
        return {
            "title": best_doc.title or "Extracted Numerical Data",
            "headers": best_doc.headers,
            "rows": best_doc.rows
        }
