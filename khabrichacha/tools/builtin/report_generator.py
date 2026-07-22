import datetime
from typing import Dict, Any, List
from khabrichacha.tools.base import BaseTool
from loguru import logger

class ReportGeneratorTool(BaseTool):
    """
    Generate a structured Markdown research report from collected evidence.
    """

    @property
    def name(self) -> str:
        return "generate_report"

    @property
    def description(self) -> str:
        return "Generate a structured Markdown research report from collected evidence."

    @property
    def category(self) -> str:
        return "report"

    @property
    def version(self) -> str:
        return "1.0"

    @property
    def inputs(self) -> List[str]:
        return ["title", "objective", "findings", "sources", "evidence"]

    @property
    def outputs(self) -> List[str]:
        return ["markdown"]

    @property
    def supports_streaming(self) -> bool:
        return False

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, str]:
        """
        Generates a clean Markdown report based on structural inputs.
        """
        logger.info("ReportGeneratorTool execution started.")
        
        # 1. Validate arguments
        for req in self.inputs:
            if req not in arguments:
                error_msg = f"Missing required field: '{req}'"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
        title = arguments["title"]
        objective = arguments["objective"]
        findings = arguments["findings"]
        sources = arguments["sources"]
        evidence = arguments.get("evidence")
        
        # Type validations
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Field 'title' must be a non-empty string.")
        if not isinstance(objective, str) or not objective.strip():
            raise ValueError("Field 'objective' must be a non-empty string.")
        if not isinstance(findings, list):
            raise ValueError("Field 'findings' must be a list of strings.")
        if not isinstance(sources, list):
            raise ValueError("Field 'sources' must be a list of dictionaries.")
            
        logger.info(f"Generating report: '{title}' with {len(findings)} findings and {len(sources)} sources.")
        
        # 2. Synthesize Executive Summary
        # Take up to the first 3 findings to form a cohesive summary paragraph
        summary_points = [str(f).strip().rstrip(".") + "." for f in findings[:3] if str(f).strip()]
        
        if summary_points:
            summary_paragraph = "This report consolidates key research findings regarding the objective. "
            summary_paragraph += "Based on the gathered evidence, highlights indicate that: "
            summary_paragraph += " ".join(summary_points)
        else:
            summary_paragraph = "No conclusive findings were recorded during this investigation."

        # 3. Assemble Markdown sections
        lines = []
        
        # Title
        lines.append(f"# {title.strip()}")
        lines.append("")
        
        # Executive Summary
        lines.append("## Executive Summary")
        lines.append(summary_paragraph)
        lines.append("")
        
        # Objective
        lines.append("## Objective")
        lines.append(str(objective).strip())
        lines.append("")
        
        # Key Findings
        lines.append("## Key Findings")
        if findings:
            for idx, finding in enumerate(findings, 1):
                lines.append(f"{idx}. {str(finding).strip()}")
        else:
            lines.append("No findings provided.")
        lines.append("")
        
        # Sources
        lines.append("## Sources")
        if sources:
            for source in sources:
                if isinstance(source, dict):
                    src_title = source.get("title", "Untitled Source").strip()
                    src_url = source.get("url", "#").strip()
                    lines.append(f"- [{src_title}]({src_url})")
                else:
                    lines.append(f"- {source}")
        else:
            lines.append("No sources provided.")
        lines.append("")

        if evidence:
            lines.append("## Evidence")
            lines.append(str(evidence))
            lines.append("")
        
        # Research Statistics
        generated_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines.append("## Research Statistics")
        lines.append(f"- **Total Findings**: {len(findings)}")
        lines.append(f"- **Total Sources**: {len(sources)}")
        lines.append(f"- **Generated Timestamp**: {generated_timestamp}")
        
        markdown_output = "\n".join(lines)
        
        logger.info("Successfully generated markdown report.")
        
        return {
            "markdown": markdown_output
        }
