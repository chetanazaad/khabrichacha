import json
import csv
import re
from io import StringIO
from typing import List, Dict, Any
from deployment.runtime.response_planner import ResponsePlan
from deployment.runtime.models.structured_document import StructuredDocument
from deployment.runtime.intelligence.citation_builder import Citation

class AdvancedResultBuilder:
    """Formats raw outputs, extracted tables, and LLM reasoning into structured responses."""

    def build(self, plan: ResponsePlan, content: Dict[str, Any], citations: List[Citation]) -> str:
        output_format = plan.output_format
        
        # Dispatch
        if output_format == "table":
            body = self._build_table(content)
        elif output_format == "comparison":
            body = self._build_comparison(content)
        elif output_format == "timeline":
            body = self._build_timeline(content)
        elif output_format == "bullet_list":
            body = self._build_bullets(content)
        elif output_format == "json":
            body = self._build_json(content)
        elif output_format == "csv":
            body = self._build_csv(content)
        elif output_format == "summary":
            body = self._build_summary(content)
        else:
            body = self._build_paragraph(content)

        # Append Citations if requested and present
        if plan.include_sources and citations:
            from deployment.runtime.intelligence.citation_builder import CitationBuilder
            cb = CitationBuilder()
            body += "\n\n" + cb.to_markdown(citations)

        return body

    def _build_paragraph(self, content: Dict[str, Any]) -> str:
        text = content.get("text", "") or content.get("reasoning", "")
        return text

    def _build_table(self, content: Dict[str, Any]) -> str:
        # Check if table data is present
        headers = content.get("headers", [])
        rows = content.get("rows", [])
        title = content.get("title", "Extracted Data Table")
        
        if not headers or not rows:
            # Fallback to paragraph if no tabular data
            return self._build_paragraph(content)

        # Validation: Repair headers
        headers = [str(h).strip().replace("|", "") for h in headers]
        
        md = f"### {title}\n\n"
        md += "| " + " | ".join(headers) + " |\n"
        md += "| " + " | ".join(["---"] * len(headers)) + " |\n"
        for row in rows:
            # Repair rows: truncate excess, pad missing, clean characters
            cells = [str(cell).strip().replace("|", "") for cell in row]
            if len(cells) < len(headers):
                cells += [""] * (len(headers) - len(cells))
            elif len(cells) > len(headers):
                cells = cells[:len(headers)]
            md += "| " + " | ".join(cells) + " |\n"
            
        # Evidence Mapping
        evidence_ids = content.get("evidence_ids", [])
        if evidence_ids:
            citations_str = ", ".join([f"[{eid}]" for eid in evidence_ids])
            md += f"\n*Data aggregated from sources: {citations_str}*\n"
            
        # If numerical validation warnings exist
        warnings = content.get("validation_warnings", [])
        if warnings:
            md += "\n> [!WARNING]\n"
            md += "> **Data Validation Warnings:**\n"
            for w in warnings:
                md += f"> - {w}\n"
                
        return md

    def _build_comparison(self, content: Dict[str, Any]) -> str:
        # Comparison matrix formatting
        # Expects: {"entities": ["A", "B"], "comparison": [{"parameter": "price", "val_a": "x", "val_b": "y"}]}
        entities = content.get("entities", ["Entity A", "Entity B"])
        comparison = content.get("comparison", [])
        
        if not comparison:
            # Fallback to paragraph
            return self._build_paragraph(content)

        md = f"### Comparison: {entities[0]} vs {entities[1]}\n\n"
        md += f"| Parameter | {entities[0]} | {entities[1]} |\n"
        md += "| --- | --- | --- |\n"
        for item in comparison:
            param = item.get("parameter", "Unknown")
            val_a = item.get("val_a", "N/A")
            val_b = item.get("val_b", "N/A")
            md += f"| **{param}** | {val_a} | {val_b} |\n"
            
        summary = content.get("summary", "")
        if summary:
            md += f"\n**Summary Comparison:**\n{summary}\n"
            
        evidence_ids = content.get("evidence_ids", [])
        if evidence_ids:
            citations_str = ", ".join([f"[{eid}]" for eid in evidence_ids])
            md += f"\n*Comparison based on sources: {citations_str}*\n"
            
        return md

    def _build_timeline(self, content: Dict[str, Any]) -> str:
        events = content.get("events", []) # list of {"year": int/str, "event": str}
        if not events:
            return self._build_paragraph(content)

        md = "### Chronological Timeline\n\n"
        # Sort events by year if numerical
        try:
            sorted_events = sorted(events, key=lambda x: int(re.sub(r'\D', '', str(x.get("year", 0)))))
        except Exception:
            sorted_events = events

        for e in sorted_events:
            year = e.get("year", "Unknown")
            desc = e.get("event", "")
            md += f"- **{year}**: {desc}\n"
            
        return md

    def _build_bullets(self, content: Dict[str, Any]) -> str:
        items = content.get("items", [])
        title = content.get("title", "Key Findings")
        
        if not items:
            return self._build_paragraph(content)

        md = f"### {title}\n\n"
        for i in items:
            md += f"- {i}\n"
        return md

    def _build_json(self, content: Dict[str, Any]) -> str:
        # Wrap JSON in markdown block
        json_data = content.get("json_data", content)
        return "```json\n" + json.dumps(json_data, indent=2) + "\n```"

    def _build_csv(self, content: Dict[str, Any]) -> str:
        headers = content.get("headers", [])
        rows = content.get("rows", [])
        if not headers or not rows:
            return ""
            
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(rows)
        return "```csv\n" + output.getvalue() + "```"

    def _build_summary(self, content: Dict[str, Any]) -> str:
        title = content.get("title", "Executive Summary")
        summary = content.get("summary", "") or content.get("text", "")
        key_points = content.get("key_points", [])
        
        md = f"### {title}\n\n"
        md += f"{summary}\n\n"
        if key_points:
            md += "**Key Insights:**\n"
            for pt in key_points:
                md += f"- {pt}\n"
        return md
