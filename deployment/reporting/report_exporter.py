"""
KhabriChacha — Report Exporter

Creates report.md, report.json, and a professional A4 report.pdf.
Uses reportlab for PDF generation.

This module ONLY creates files. It never manages project folders.
ProjectManager is responsible for storing the output.
"""

import json
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional
from loguru import logger

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, HRFlowable,
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("reportlab not installed — PDF generation will be skipped.")


class ReportExporter:
    """
    Generates research deliverables from orchestrator results.

    Returns a dict with keys:
        "report_md": str
        "report_json": dict
        "report_pdf_bytes": bytes | None
    """

    def generate(
        self,
        *,
        title: str,
        mission: str,
        provider: str = "",
        model: str = "",
        findings: List[str],
        sources: List[Dict[str, str]],
        evidence: str = "",
        research_state: Optional[Dict[str, Any]] = None,
        timeline: str = "",
    ) -> Dict[str, Any]:
        """Produce all three report formats plus Word export."""

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ── Markdown ─────────────────────────────────────────
        report_md = self._build_markdown(
            title=title, mission=mission, provider=provider,
            model=model, findings=findings, sources=sources,
            evidence=evidence, timeline=timeline, timestamp=timestamp,
        )

        # ── JSON ─────────────────────────────────────────────
        report_json = {
            "title": title,
            "mission": mission,
            "provider": provider,
            "model": model,
            "generated": timestamp,
            "findings": findings,
            "sources": sources,
            "evidence_summary": evidence[:500] if evidence else "",
            "timeline": timeline,
            "research_state": research_state or {},
        }

        # ── PDF ──────────────────────────────────────────────
        report_pdf_bytes = None
        if REPORTLAB_AVAILABLE:
            try:
                report_pdf_bytes = self._build_pdf(
                    title=title, mission=mission, provider=provider,
                    model=model, findings=findings, sources=sources,
                    evidence=evidence, timeline=timeline, timestamp=timestamp,
                )
            except Exception as e:
                logger.error(f"PDF generation failed: {e}")
        else:
            logger.warning("Skipping PDF generation — reportlab not available.")

        # ── Word DOCX ────────────────────────────────────────
        report_docx_bytes = self._build_docx(
            title=title, mission=mission, provider=provider,
            model=model, findings=findings, sources=sources,
            evidence=evidence, timeline=timeline, timestamp=timestamp,
        )

        return {
            "report_md": report_md,
            "report_json": report_json,
            "report_pdf_bytes": report_pdf_bytes,
            "report_docx_bytes": report_docx_bytes,
        }

    # ── Markdown builder ─────────────────────────────────────

    @staticmethod
    def _build_markdown(
        *, title, mission, provider, model, findings,
        sources, evidence, timeline, timestamp,
    ) -> str:
        lines = [
            f"# {title}",
            "",
            "## Executive Summary",
        ]
        summary_points = [s.strip().rstrip(".") + "." for s in findings[:3] if s.strip()]
        if summary_points:
            lines.append(
                "This report consolidates key research findings. "
                "Highlights include: " + " ".join(summary_points)
            )
        else:
            lines.append("No conclusive findings were recorded.")
        lines.append("")

        lines += ["## Research Mission", mission or "(not specified)", ""]
        lines += ["## Methodology",
                  f"- **Provider**: {provider or 'N/A'}",
                  f"- **Model**: {model or 'N/A'}",
                  f"- **Generated**: {timestamp}", ""]

        if timeline:
            lines += ["## Research Timeline", timeline, ""]

        lines.append("## Key Findings")
        if findings:
            for i, f in enumerate(findings, 1):
                lines.append(f"{i}. {f}")
        else:
            lines.append("No findings provided.")
        lines.append("")

        if evidence:
            lines += ["## Evidence Summary", evidence, ""]

        lines.append("## Sources")
        if sources:
            for s in sources:
                t = s.get("title", "Untitled")
                u = s.get("url", "#")
                lines.append(f"- [{t}]({u})")
        else:
            lines.append("No sources provided.")
        lines.append("")

        lines += [
            "## Research Statistics",
            f"- **Total Findings**: {len(findings)}",
            f"- **Total Sources**: {len(sources)}",
            f"- **Generated**: {timestamp}",
        ]
        return "\n".join(lines)

    # ── PDF builder ──────────────────────────────────────────

    @staticmethod
    def _build_pdf(
        *, title, mission, provider, model, findings,
        sources, evidence, timeline, timestamp,
    ) -> bytes:
        import html
        def esc(val):
            if not val:
                return ""
            return html.escape(str(val))

        title_esc = esc(title)
        mission_esc = esc(mission)
        provider_esc = esc(provider)
        model_esc = esc(model)
        timestamp_esc = esc(timestamp)
        timeline_esc = esc(timeline)
        findings_esc = [esc(f) for f in findings]
        evidence_esc = esc(evidence)
        sources_esc = []
        for s in sources:
            sources_esc.append({
                "title": esc(s.get("title", "Untitled")),
                "url": esc(s.get("url", ""))
            })

        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=2 * cm, rightMargin=2 * cm,
            topMargin=2 * cm, bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()
        # Custom styles
        styles.add(ParagraphStyle(
            "CoverTitle", parent=styles["Title"],
            fontSize=28, leading=34,
            textColor=HexColor("#1a1a2e"),
            alignment=TA_CENTER, spaceAfter=12,
        ))
        styles.add(ParagraphStyle(
            "CoverSub", parent=styles["Normal"],
            fontSize=14, leading=18,
            textColor=HexColor("#4a4a6a"),
            alignment=TA_CENTER, spaceAfter=6,
        ))
        styles.add(ParagraphStyle(
            "SectionHead", parent=styles["Heading2"],
            fontSize=16, leading=20,
            textColor=HexColor("#16213e"),
            spaceBefore=18, spaceAfter=8,
        ))
        styles.add(ParagraphStyle(
            "BodyText2", parent=styles["BodyText"],
            fontSize=10, leading=14,
            alignment=TA_JUSTIFY,
        ))
        styles.add(ParagraphStyle(
            "BulletItem", parent=styles["BodyText"],
            fontSize=10, leading=14, leftIndent=18,
            bulletIndent=6,
        ))

        story = []

        # ── Cover Page ───────────────────────────────────────
        story.append(Spacer(1, 6 * cm))
        story.append(Paragraph(title_esc, styles["CoverTitle"]))
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph(f"Research Mission: {mission_esc}", styles["CoverSub"]))
        story.append(Paragraph(f"Generated: {timestamp_esc}", styles["CoverSub"]))
        story.append(Paragraph(f"Provider: {provider_esc}  |  Model: {model_esc}", styles["CoverSub"]))
        story.append(PageBreak())

        # ── Executive Summary ────────────────────────────────
        story.append(Paragraph("Executive Summary", styles["SectionHead"]))
        summary_points = [s.strip().rstrip(".") + "." for s in findings_esc[:3] if s.strip()]
        if summary_points:
            summary_text = (
                "This report consolidates key research findings. "
                "Highlights include: " + " ".join(summary_points)
            )
        else:
            summary_text = "No conclusive findings were recorded."
        story.append(Paragraph(summary_text, styles["BodyText2"]))
        story.append(Spacer(1, 0.5 * cm))

        # ── Methodology ──────────────────────────────────────
        story.append(Paragraph("Methodology", styles["SectionHead"]))
        story.append(Paragraph(f"<b>Provider:</b> {provider_esc}", styles["BodyText2"]))
        story.append(Paragraph(f"<b>Model:</b> {model_esc}", styles["BodyText2"]))
        story.append(Paragraph(f"<b>Generated:</b> {timestamp_esc}", styles["BodyText2"]))
        story.append(Spacer(1, 0.3 * cm))

        # ── Research Timeline ────────────────────────────────
        if timeline_esc:
            story.append(Paragraph("Research Timeline", styles["SectionHead"]))
            for line in timeline_esc.split("\n"):
                if line.strip():
                    story.append(Paragraph(line.strip(), styles["BodyText2"]))
            story.append(Spacer(1, 0.3 * cm))

        # ── Key Findings ─────────────────────────────────────
        story.append(Paragraph("Key Findings", styles["SectionHead"]))
        if findings_esc:
            for i, f in enumerate(findings_esc, 1):
                # Truncate extremely long findings for the PDF
                text = f[:500] + "..." if len(f) > 500 else f
                story.append(Paragraph(f"{i}. {text}", styles["BulletItem"]))
        else:
            story.append(Paragraph("No findings provided.", styles["BodyText2"]))
        story.append(Spacer(1, 0.3 * cm))

        # ── Evidence Summary ─────────────────────────────────
        if evidence_esc:
            story.append(Paragraph("Evidence Summary", styles["SectionHead"]))
            # Keep evidence reasonable for the PDF
            ev_text = evidence_esc[:2000] + "..." if len(evidence_esc) > 2000 else evidence_esc
            for line in ev_text.split("\n"):
                if line.strip():
                    story.append(Paragraph(line.strip(), styles["BodyText2"]))
            story.append(Spacer(1, 0.3 * cm))

        # ── Evidence Statistics ──────────────────────────────
        story.append(Paragraph("Evidence Statistics", styles["SectionHead"]))
        stats_data = [
            ["Metric", "Value"],
            ["Total Findings", str(len(findings_esc))],
            ["Total Sources", str(len(sources_esc))],
            ["Generated", timestamp_esc],
        ]
        stats_table = Table(stats_data, colWidths=[8 * cm, 8 * cm])
        stats_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#16213e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#f8f8f8"), HexColor("#ffffff")]),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(stats_table)
        story.append(Spacer(1, 0.5 * cm))

        # ── References ───────────────────────────────────────
        story.append(Paragraph("References", styles["SectionHead"]))
        if sources_esc:
            for s in sources_esc:
                t = s.get("title", "Untitled")
                u = s.get("url", "")
                ref_text = f"<b>{t}</b>"
                if u:
                    ref_text += f"<br/><font size='8' color='#4a4a6a'>{u}</font>"
                story.append(Paragraph(ref_text, styles["BulletItem"]))
        else:
            story.append(Paragraph("No references collected.", styles["BodyText2"]))

        # ── Build ────────────────────────────────────────────
        doc.build(story)
        return buf.getvalue()

    # ── Word DOCX builder ────────────────────────────────────

    @staticmethod
    def _build_docx(
        *, title, mission, provider, model, findings,
        sources, evidence, timeline, timestamp,
    ) -> Optional[bytes]:
        try:
            import docx
            from docx import Document
            from docx.shared import Pt, RGBColor
            from docx.enum.text import WD_ALIGN_PARAGRAPH
        except ImportError:
            logger.warning("python-docx not installed — skipping Word export.")
            return None
            
        doc = Document()
        
        # Styles / Fonts
        style_normal = doc.styles['Normal']
        font = style_normal.font
        font.name = 'Arial'
        font.size = Pt(10.5)
        font.color.rgb = RGBColor(0x33, 0x33, 0x33)
        
        # Document Title
        p_title = doc.add_paragraph()
        p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_title = p_title.add_run(title)
        run_title.font.size = Pt(26)
        run_title.font.bold = True
        run_title.font.color.rgb = RGBColor(0x1a, 0x1a, 0x2e)
        
        # Subtitle
        p_sub = doc.add_paragraph()
        p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_sub = p_sub.add_run(f"Research Mission: {mission or 'N/A'}\nGenerated: {timestamp}\nProvider: {provider or 'N/A'} | Model: {model or 'N/A'}")
        run_sub.font.size = Pt(11)
        run_sub.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
        
        doc.add_page_break()
        
        # Executive Summary Section
        h_exec = doc.add_paragraph()
        run_h_exec = h_exec.add_run("Executive Summary")
        run_h_exec.font.size = Pt(16)
        run_h_exec.font.bold = True
        run_h_exec.font.color.rgb = RGBColor(0x16, 0x21, 0x3e)
        
        summary_points = [s.strip().rstrip(".") + "." for s in findings[:3] if s.strip()]
        summary_text = (
            "This report consolidates key research findings. "
            "Highlights include: " + " ".join(summary_points)
        ) if summary_points else "No conclusive findings were recorded."
        doc.add_paragraph(summary_text)
        
        # Methodology Section
        h_meth = doc.add_paragraph()
        run_h_meth = h_meth.add_run("Methodology")
        run_h_meth.font.size = Pt(16)
        run_h_meth.font.bold = True
        run_h_meth.font.color.rgb = RGBColor(0x16, 0x21, 0x3e)
        
        doc.add_paragraph(f"Provider: {provider or 'N/A'}\nModel: {model or 'N/A'}\nGenerated: {timestamp}")
        
        # Timeline Section
        if timeline:
            h_time = doc.add_paragraph()
            run_h_time = h_time.add_run("Research Timeline")
            run_h_time.font.size = Pt(16)
            run_h_time.font.bold = True
            run_h_time.font.color.rgb = RGBColor(0x16, 0x21, 0x3e)
            doc.add_paragraph(timeline)
            
        # Key Findings Section
        h_find = doc.add_paragraph()
        run_h_find = h_find.add_run("Key Findings")
        run_h_find.font.size = Pt(16)
        run_h_find.font.bold = True
        run_h_find.font.color.rgb = RGBColor(0x16, 0x21, 0x3e)
        
        if findings:
            for i, f in enumerate(findings, 1):
                p = doc.add_paragraph(style='List Bullet')
                run = p.add_run(f"{i}. {f}")
                run.font.size = Pt(10.5)
        else:
            doc.add_paragraph("No findings provided.")
            
        # Evidence Section
        if evidence:
            h_ev = doc.add_paragraph()
            run_h_ev = h_ev.add_run("Evidence Summary")
            run_h_ev.font.size = Pt(16)
            run_h_ev.font.bold = True
            run_h_ev.font.color.rgb = RGBColor(0x16, 0x21, 0x3e)
            doc.add_paragraph(evidence)
            
        # References Section
        h_ref = doc.add_paragraph()
        run_h_ref = h_ref.add_run("References")
        run_h_ref.font.size = Pt(16)
        run_h_ref.font.bold = True
        run_h_ref.font.color.rgb = RGBColor(0x16, 0x21, 0x3e)
        
        if sources:
            for s in sources:
                p = doc.add_paragraph(style='List Bullet')
                run_t = p.add_run(s.get("title", "Untitled"))
                run_t.font.bold = True
                if s.get("url"):
                    run_u = p.add_run(f" ({s.get('url')})")
                    run_u.font.italic = True
                    run_u.font.color.rgb = RGBColor(0x55, 0x55, 0x88)
        else:
            doc.add_paragraph("No references collected.")
            
        # Save to buffer
        buf = BytesIO()
        doc.save(buf)
        return buf.getvalue()

