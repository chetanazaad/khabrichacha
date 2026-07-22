"""
Research Controller

Coordinates the execution of research queries by routing them to the minimum necessary
execution pipeline (Strategies: FAST, LOOKUP, STRUCTURED, COMPARISON, ANALYSIS, RESEARCH, DEEP_RESEARCH)
using QueryClassifier, retrieval intelligence, and research intelligence stages.
"""

import os
import re
import time
import json
from typing import Dict, Any, Optional, List

from loguru import logger

from deployment.runtime.models.research_request import ResearchRequest
from deployment.runtime.models.research_result import ResearchResult
from deployment.runtime.models.research_statistics import ResearchStatistics
from deployment.runtime.models.error_info import ErrorInfo
from deployment.runtime.event_bus import EventBus
from deployment.runtime.tool_executor import ToolExecutor
from deployment.workspace.workspace_manager import WorkspaceManager
from khabrichacha.core.session import Session
from khabrichacha.llm.manager import LLMManager
from khabrichacha.providers.provider_manager import ProviderManager
from khabrichacha.tools.registry import ToolRegistry

from deployment.runtime.runtime_profiler import RuntimeProfiler

from deployment.workspace.workspace_schema import (
    RuntimeState, ResearchState as SchemaResearchState, PlannerState, ReferenceIndex, ReferenceEntry
)

# New intelligence layer imports
from deployment.runtime.query_classifier import QueryClassifier
from deployment.runtime.query_understanding import QueryUnderstandingEngine
from deployment.runtime.retrieval.knowledge_retriever import KnowledgeRetriever
from deployment.runtime.retrieval.retriever import Retriever
from deployment.runtime.retrieval.trust_evaluator import TrustEvaluator
from deployment.runtime.extraction.structured_extractor import StructuredExtractor
from deployment.runtime.intelligence.numerical_validator import NumericalValidator
from deployment.runtime.intelligence.consensus_engine import ConsensusEngine
from deployment.runtime.intelligence.citation_builder import CitationBuilder
from deployment.runtime.intelligence.confidence_aggregator import ConfidenceAggregator
from deployment.runtime.intelligence.entity_resolver import EntityResolver
from deployment.runtime.intelligence.temporal_resolver import TemporalResolver
from deployment.runtime.intelligence.context_optimizer import ContextOptimizer
from deployment.runtime.intelligence.query_decomposer import QueryDecomposer
from deployment.runtime.intelligence.tool_selector import ToolSelector
from deployment.runtime.intelligence.model_selector import ModelSelector
from deployment.runtime.intelligence.failure_recovery import FailureRecovery
from deployment.runtime.response_planner import ResponsePlanner, ResponsePlan
from deployment.runtime.advanced_result_builder import AdvancedResultBuilder
from deployment.runtime.intelligence.execution_trace import ExecutionTraceRecorder


class ResearchController:
    """Coordinates the entire lifecycle of a research request with adaptive strategy dispatching."""

    def __init__(self, workspace_manager: WorkspaceManager, provider_manager: ProviderManager, event_bus: Optional[EventBus] = None):
        profiler = RuntimeProfiler()
        t0 = time.time()
        self.workspace_manager = workspace_manager
        profiler.record_init("WorkspaceManager", "ResearchController", "Injected Dependency", (time.time() - t0) * 1000)
        
        t0 = time.time()
        self.provider_manager = provider_manager
        profiler.record_init("ProviderManager", "ResearchController", "Injected Dependency", (time.time() - t0) * 1000)
        
        t0 = time.time()
        self.event_bus = event_bus or EventBus()
        profiler.record_init("EventBus", "ResearchController", "Injected or Created", (time.time() - t0) * 1000)

    def _get_verified_provider(self, provider_name: str, model_name: str, extra_config: Optional[Dict[str, Any]] = None):
        session = Session()
        session.config.setdefault("providers", {})[provider_name] = {
            "model": model_name,
            **(extra_config or {}),
        }
        llm_manager = LLMManager(session.config)
        provider_obj = llm_manager.get_provider(provider_name)

        actual_model = provider_obj.model_identifier
        if actual_model and actual_model != model_name:
            logger.warning(f"Model identifier discrepancy: requested '{model_name}', got '{actual_model}'.")
        return llm_manager, provider_obj

    def _get_verified_dual_providers(self, request: ResearchRequest):
        session = Session()
        ing_prov = request.ingestion_provider or request.provider
        ing_mod = request.ingestion_model or request.model
        ana_prov = request.analysis_provider or request.provider
        ana_mod = request.analysis_model or request.model

        session.config.setdefault("providers", {})[ing_prov] = {"model": ing_mod}
        session.config["providers"][ana_prov] = {"model": ana_mod}
        session.config["llm"] = {
            "default_provider": ana_prov,
            "ingestion_provider": ing_prov,
            "analysis_provider": ana_prov,
        }

        llm_manager = LLMManager(session.config)
        ingestion_obj = llm_manager.get_ingestion_provider()
        analysis_obj = llm_manager.get_analysis_provider()

        return llm_manager, ingestion_obj, analysis_obj


    def _format_consensus_section(self, cr: Any) -> str:
        """Render a ConsensusEngine result as a readable markdown block."""
        lines = ["### Cross-Source Consensus", ""]
        label = "Best estimate" if cr.resolution == "unresolved" else "Resolved value"
        if cr.weighted_value is not None:
            try:
                pretty_val = f"{float(cr.weighted_value):,.0f}"
            except (TypeError, ValueError):
                pretty_val = str(cr.weighted_value)
            lines.append(f"**{label}:** {pretty_val}")
        resolution_display = (
            "unresolved — sources disagree" if cr.resolution == "unresolved" else cr.resolution
        )
        lines.append(
            f"**Resolution:** {resolution_display} &nbsp;|&nbsp; "
            f"**Confidence:** {cr.confidence:.0%} &nbsp;|&nbsp; "
            f"**Source agreement:** {cr.agreement_percentage:.0f}%"
        )
        lines.append("")
        if cr.agreeing_sources or cr.conflicts:
            lines.append("| Source | Reported value | Agreement |")
            lines.append("|---|---|---|")
            for s in cr.agreeing_sources:
                lines.append(f"| {s} | — | ✔ Agrees with resolved value |")
            for c in cr.conflicts:
                src = c.get("source", "unknown")
                val = c.get("value")
                try:
                    val_str = f"{float(val):,.0f}"
                except (TypeError, ValueError):
                    val_str = str(val)
                lines.append(f"| {src} | {val_str} | ✗ Differs |")
            lines.append("")
        lines.append(
            "*Figures for aggregated statistics like this often vary between sources due to "
            "differing definitions, scope, or time periods — check the sources below for exact context.*"
        )
        return "\n".join(lines)

    def _finalize_and_persist(
        self,
        request: ResearchRequest,
        result: ResearchResult,
        pm: Any,
        manifest: Any,
        sources: Optional[List[Dict[str, Any]]] = None,
        extra_json: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Shared "save the answer to disk in every requested format, update
        the manifest, unlock the project, and populate result paths" tail,
        used by every strategy. This is what gives the UI's Downloads tab
        (PDF / Word / Markdown / JSON) something to point at regardless of
        which strategy actually answered the question — previously only
        the RESEARCH/DEEP_RESEARCH path persisted anything to disk at all.
        """
        from deployment.reporting.report_exporter import ReportExporter

        try:
            exporter = ReportExporter()
            exports = exporter.generate(
                title=manifest.title,
                mission=manifest.mission,
                provider=request.provider,
                model=request.model,
                findings=[result.direct_answer] if result.direct_answer else [],
                sources=sources or [],
                evidence=result.direct_answer or "",
                research_state={},
                timeline="",
            )
            report_json = exports.get("report_json") or {}
            if extra_json:
                report_json.update(extra_json)

            pm.save_project(
                manifest.project_id,
                report_md=exports.get("report_md"),
                report_json=report_json,
                report_pdf_bytes=exports.get("report_pdf_bytes"),
                report_docx_bytes=exports.get("report_docx_bytes"),
            )
        except Exception as e:
            logger.error(f"Failed to generate/save report exports: {e}")
            result.warnings.append(f"Report export failed: {e}")

        pm.update_manifest(manifest.project_id, status="completed" if result.success else "failed")
        pm.unlock_project(manifest.project_id)

        project_path = self.workspace_manager.get_project_path(manifest.project_id)
        fmt_files = {
            "md": ("report.md", "report_md_path"),
            "txt": ("report.txt", "report_txt_path"),
            "json": ("report.json", "report_json_path"),
            "pdf": ("report.pdf", "report_pdf_path"),
            "docx": ("report.docx", "report_docx_path"),
        }
        for fmt, (filename, attr) in fmt_files.items():
            candidate = project_path / filename
            if fmt in request.output_formats and candidate.exists() and hasattr(result, attr):
                setattr(result, attr, str(candidate))

    def _annotate_if_ungrounded(self, answer: str, evidence_snippets: List[str]) -> str:
        """
        Shared post-hoc grounding check used after every LLM synthesis
        call: flags numeric claims in `answer` that don't appear anywhere
        in the retrieved evidence it was supposedly built from, and
        appends a plain-language caveat if any are found. A heuristic
        signal, not a full fact-checker -- see khabrichacha.core.grounding.
        """
        from khabrichacha.core.grounding import find_ungrounded_claims
        if not answer or not evidence_snippets:
            return answer
        combined_evidence = "\n".join(evidence_snippets)
        ungrounded = find_ungrounded_claims(answer, combined_evidence)
        if ungrounded:
            logger.warning(f"Answer contains {len(ungrounded)} numeric claim(s) not traceable to retrieved evidence: {ungrounded}")
            answer += (
                "\n\n> **Note:** The following figures could not be directly verified "
                f"against the retrieved sources and may be estimated: {', '.join(ungrounded)}."
            )
        return answer

    def _is_content_relevant(self, mission: str, content: str, threshold: float = 0.08) -> bool:
        """
        Second-pass relevance check on a page's actual fetched content,
        used at every fetch site in this file. Retriever already filters
        by title+snippet before a URL is even fetched, but a page's real
        content can still turn out to be off-topic despite a plausible-
        looking snippet -- this catches that case before the content is
        added to the evidence used for synthesis/citations.
        """
        from khabrichacha.core.relevance import RelevanceScorer
        return RelevanceScorer(mission).is_relevant(content, threshold=threshold)

    def enforce_prompt_budget(self, prompt: str, max_tokens: int) -> str:
        # safe approximation: 1 token ≈ 4 characters.
        max_chars = max_tokens * 4
        if len(prompt) > max_chars:
            logger.warning(f"Prompt length ({len(prompt)} chars) exceeds budget ({max_chars} chars). Truncating context.")
            return prompt[:max_chars]
        return prompt

    def enforce_adaptive_prompt_budget(self, query: str, evidence: List[str], instructions: str, max_tokens: int) -> str:
        from khabrichacha.core.grounding import GROUNDING_INSTRUCTION
        max_chars = max_tokens * 4
        q_limit = int(max_chars * 0.20)
        e_limit = int(max_chars * 0.55)
        i_limit = int(max_chars * 0.25)
        
        truncated_query = query[:q_limit]
        truncated_instructions = (instructions + " " + GROUNDING_INSTRUCTION)[:i_limit]
        
        evidence_text = ""
        if evidence:
            avg_limit = int(e_limit / len(evidence))
            truncated_evidence = [item[:avg_limit] for item in evidence]
            evidence_text = "\n---\n".join(truncated_evidence)
            
        prompt = (
            f"Question:\n{truncated_query}\n\n"
            f"Retrieved Evidence:\n{evidence_text}\n\n"
            f"Instructions:\n{truncated_instructions}"
        )
        return prompt

    def _verify_answer(self, mission: str, answer: str, evidence_snippets: List[str], answer_type: str) -> tuple[bool, float, str]:
        """Apply a lightweight Stage 2 verification policy: traceability + answer-type satisfaction."""
        if not answer or not answer.strip():
            return False, 0.0, "No answer produced"

        evidence_text = "\n".join(evidence_snippets).lower()
        evidence_coverage = 0.0
        if evidence_snippets:
            evidence_coverage = min(1.0, len([token for token in re.findall(r"[A-Za-z0-9]+", answer) if token.lower() in evidence_text]) / max(1, min(10, len(re.findall(r"[A-Za-z0-9]+", answer)))))

        answer_lower = answer.lower()
        satisfaction = 1.0
        if answer_type == "count":
            satisfaction = 1.0 if re.search(r"\b\d+\b", answer_lower) else 0.0
        elif answer_type == "comparison":
            satisfaction = 1.0 if re.search(r"\b(vs|versus|compare|difference)\b", answer_lower) or "vs" in answer_lower else 0.0
        elif answer_type == "analysis":
            satisfaction = 1.0 if any(k in answer_lower for k in ["because", "therefore", "however", "impact", "explain"]) else 0.0
        elif answer_type == "list":
            satisfaction = 1.0 if re.search(r"\b(1\.|2\.|- |\* )\b", answer_lower) else 0.0

        confidence = max(0.0, min(1.0, (0.6 * evidence_coverage) + (0.4 * satisfaction)))
        passed = confidence >= 0.6 and evidence_coverage >= 0.3
        if not passed:
            return False, confidence, "Answer did not satisfy the verification policy"
        return True, confidence, "Answer verified"

    def calculate_consensus(self, query: str, filtered_sources: List[Any]) -> float:
        """
        Calculates consensus by comparing factual or numerical entities across snippets.
        Returns a score between 0.0 and 25.0
        """
        snippets = [s.snippet for s in filtered_sources if s.snippet]
        if not snippets:
            return 0.0
            
        import re
        # Extremely basic entity overlap for consensus (numbers and capitalized phrases)
        def extract_entities(text):
            numbers = set(re.findall(r'\b\d+(?:\.\d+)?\b', text))
            caps = set(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text))
            return numbers.union(caps)

        entity_sets = [extract_entities(s) for s in snippets]
        if not entity_sets:
            return 0.0
            
        # Check intersection across top sources
        common_entities = set.intersection(*entity_sets) if entity_sets else set()
        
        # If there are common entities across multiple sources, consensus is high.
        consensus_ratio = min(1.0, len(common_entities) / max(1, len(entity_sets[0])))
        
        # Also factor in domain diversity
        unique_domains = len(set(s.domain for s in filtered_sources))
        domain_factor = min(1.0, unique_domains / 3.0)
        
        consensus_score = (consensus_ratio * 0.7 + domain_factor * 0.3) * 25.0
        return min(25.0, max(0.0, consensus_score))

    def calculate_evidence_sufficiency(self, filtered_sources: List[Any], query: str = "") -> float:
        if not filtered_sources:
            return 0.0
        coverage_score = min(5, len(filtered_sources)) * 5.0
        avg_quality = sum(s.rank_score for s in filtered_sources) / len(filtered_sources)
        quality_score = (avg_quality / 100.0) * 25.0
        avg_freshness = sum(s.quality_score_breakdown.get("Freshness", 50.0) for s in filtered_sources) / len(filtered_sources) if filtered_sources else 50.0
        freshness_score = (avg_freshness / 100.0) * 25.0
        
        # Calculate consensus based on factual agreement
        agreement_score = self.calculate_consensus(query, filtered_sources)
        
        total_score = coverage_score + quality_score + freshness_score + agreement_score
        return min(100.0, max(0.0, total_score))

    def start_research(self, request: ResearchRequest) -> ResearchResult:
        """
        Main entry point for UI or CLI. Classifies query and dispatches to appropriate strategy handler.
        """
        start_time = time.time()
        # Placeholder result so that even a failure during classification or
        # provider validation (before the "real" result below exists) still
        # comes back as a populated ResearchResult with a real error message,
        # instead of letting the exception propagate and leaving the caller
        # with nothing but "Unknown error".
        result = ResearchResult(provider=request.provider, model=request.model)

        try:
            # 1. Classify Query
            class_start = time.time()
            classifier = QueryClassifier()
            strategy = classifier.classify(request.mission, request.strategy_override)
            class_time = time.time() - class_start
            
            # Provider & Model Validation
            usable_providers = self.provider_manager.discover_providers()
            if request.provider not in usable_providers or not usable_providers[request.provider]["available"]:
                suggested = self.provider_manager.get_available_models()
                raise ValueError(f"Provider '{request.provider}' is not available.\nSuggested models:\n" + "\n".join(suggested))
                
            models_list = [m["name"] for m in usable_providers[request.provider]["models"]]
            if request.model not in models_list:
                suggested = self.provider_manager.get_available_models()
                raise ValueError(f"Model '{request.model}' is not available on provider '{request.provider}'.\nSuggested models:\n" + "\n".join(suggested))
            
            tracer = ExecutionTraceRecorder()
            tracer.set_query_info(request.mission, strategy.strategy_name, strategy.confidence, strategy.complexity)
            tracer.record_module("QueryClassifier", class_time * 1000)

            understanding_engine = QueryUnderstandingEngine()
            understanding = understanding_engine.understand(request.mission)
            request.metadata.setdefault("query_understanding", understanding.to_dict())
            
            self.event_bus.info("Classifier", f"Query classified. Strategy: {strategy.strategy_name} (Confidence: {strategy.confidence:.0%})")

            # 2. Setup standard result model
            result = ResearchResult(
                provider=request.provider,
                model=request.model,
                strategy_used=strategy.strategy_name,
                strategy_confidence=strategy.confidence,
                classification_time=class_time
            )
            
            result.statistics.classification_time = class_time
            result.statistics.strategy_selected = strategy.strategy_name
            result.statistics.strategy_confidence = strategy.confidence
            result.statistics.execution_budget_used = {
                "max_searches": strategy.execution_budget.max_searches,
                "max_fetches": strategy.execution_budget.max_fetches,
                "max_llm_calls": strategy.execution_budget.max_llm_calls
            }

            # 3. Dispatch to specific execution handler
            dispatch = {
                "FAST": self._execute_fast,
                "LOOKUP": self._execute_lookup,
                "STRUCTURED": self._execute_structured,
                "COMPARISON": self._execute_comparison,
                "ANALYSIS": self._execute_analysis,
                "RESEARCH": self._execute_research,
                "DEEP_RESEARCH": self._execute_deep_research,
            }
            
            handler = dispatch.get(strategy.strategy_name, self._execute_research)
            final_result = handler(request, strategy, result, start_time, tracer)
            
            # Post-execution Quality Evaluation
            from deployment.runtime.intelligence.quality_evaluator import QualityEvaluator
            qe = QualityEvaluator()
            scores = qe.evaluate(
                query=request.mission,
                answer=final_result.direct_answer or "",
                source_count=final_result.source_count,
                strategy=strategy.strategy_name,
                provider=request.provider,
                model=request.model
            )
            final_result.statistics.quality_scores = scores
            
            # Dump trace to statistics and write execution_trace.json
            trace_dump = tracer.dump_trace()
            
            # Auto-Regeneration logic.
            #
            # QUALITY_THRESHOLD was previously 80.0, averaged across five
            # roughly-equally-weighted dimensions (completeness, correctness,
            # citation_quality, structure, relevance). In practice, clearing
            # an 80-point average requires nearly every dimension to hit its
            # maximum simultaneously -- a perfectly reasonable answer that's
            # missing a literal markdown table (structure=80, not 100) or
            # whose self-graded completeness lands at a realistic-but-good
            # 70 would still often fall under 80. That miscalibration meant
            # this check fired on most non-trivial answers regardless of
            # whether they were actually poor, silently kicking them up to
            # the heaviest, slowest, most drift-prone strategy every time.
            # 50.0 still reliably catches genuinely poor answers (no
            # sources, no citations, thin text) while not escalating
            # ordinary decent ones.
            QUALITY_THRESHOLD = 50.0
            overall_score = scores.get("overall_score", 100)
            already_escalated = bool(request.metadata.get("auto_regenerated"))

            self.event_bus.info(
                "Controller",
                f"Quality check for {strategy.strategy_name}: overall={overall_score:.0f}/100 "
                f"(completeness={scores.get('completeness')}, correctness={scores.get('correctness')}, "
                f"citation={scores.get('citation_quality')}, structure={scores.get('structure')}, "
                f"relevance={scores.get('relevance')}, grading={scores.get('grading_method')})"
            )

            user_overrode = bool(request.strategy_override)
            if overall_score < QUALITY_THRESHOLD and strategy.strategy_name != "DEEP_RESEARCH" and not already_escalated and not user_overrode:
                # Escalate incrementally -- step up to RESEARCH first for
                # every strategy, rather than jumping straight to the
                # heaviest DEEP_RESEARCH tier from STRUCTURED/COMPARISON.
                # DEEP_RESEARCH is reserved for cases where the request was
                # already classified there (a single escalation is allowed
                # per request; auto_regenerated prevents any further hops).
                new_strat = "DEEP_RESEARCH" if strategy.strategy_name == "RESEARCH" else "RESEARCH"
                reason = (
                    f"Quality score {overall_score:.0f}/100 was below the {QUALITY_THRESHOLD:.0f} threshold"
                )
                self.event_bus.warn(
                    "Controller",
                    f"{reason}. Escalating from {strategy.strategy_name} to {new_strat}..."
                )
                request.metadata["auto_regenerated"] = True
                request.strategy_override = new_strat

                escalation_record = {
                    "from_strategy": strategy.strategy_name,
                    "to_strategy": new_strat,
                    "overall_score": overall_score,
                    "threshold": QUALITY_THRESHOLD,
                    "reason": reason,
                    "scores": scores,
                }
                escalated_result = self.start_research(request)
                # Preserve this attempt's record even though the recursive
                # call produces its own fresh ResearchResult -- otherwise
                # the fact that a first attempt happened at all (and why)
                # is lost the moment escalation occurs.
                escalated_result.statistics.escalation_history = (
                    [escalation_record] + list(escalated_result.statistics.escalation_history)
                )
                return escalated_result
            elif overall_score < QUALITY_THRESHOLD:
                self.event_bus.warn("Controller", f"Final answer quality score is low ({overall_score:.0f}/100) even after escalation. Adding warning to answer.")
                if final_result.direct_answer:
                    final_result.direct_answer += f"\n\n> [!WARNING]\n> The generated answer has a low confidence/quality score ({overall_score:.0f}/100) and might be incomplete or hallucinated."

            final_result.statistics.trace_data = trace_dump
            final_result.statistics.llm_audit = tracer.trace_data["llm_audit"]
            final_result.statistics.retrieval_audit = tracer.trace_data["retrieval_audit"]
            
            # Write trace file to project path
            if final_result.project_id:
                try:
                    p_path = self.workspace_manager.get_project_path(final_result.project_id)
                    p_path.mkdir(parents=True, exist_ok=True)
                    with open(p_path / "execution_trace.json", "w", encoding="utf-8") as f:
                        json.dump(trace_dump, f, indent=2)
                        
                    # Also dump runtime initialization trace
                    profiler = RuntimeProfiler()
                    profiler.set_strategy(strategy.strategy_name)
                    profiler.dump_trace(str(p_path))
                except Exception as e:
                    logger.warning(f"Failed to write traces: {e}")
            
            return final_result
            
        except Exception as e:
            logger.error(f"ResearchController execution error: {e}", exc_info=True)
            result.success = False
            # A previous version left result.errors empty here, so the UI's
            # "\n".join([e.message for e in result.errors]) produced a blank
            # string and every failure just showed "Research failed:" with
            # no reason at all.
            result.errors.append(ErrorInfo(component="ResearchController", message=str(e)))
            result.elapsed_time = time.time() - start_time
            result.statistics.elapsed_time = result.elapsed_time
            # Best-effort cleanup: if a project was created before the
            # failure, unlock it so it doesn't stay stuck as "running"/locked.
            if result.project_id:
                try:
                    from deployment.workspace.project_manager import ProjectManager
                    ProjectManager(self.workspace_manager).unlock_project(result.project_id)
                except Exception:
                    pass
            return result

    def _setup_session(self, request: ResearchRequest, strategy: Any, result: ResearchResult, tracer: ExecutionTraceRecorder):
        """
        Sets up the session (temporary or persistent) based on the strategy,
        and returns (pm, manifest) so callers can persist their answer at the
        end via _finalize_and_persist(...).

        Both temp sessions and permanent projects now go through
        ProjectManager.create_project(...) so every run gets a real
        manifest.json — a previous version hand-rolled the temp-session
        directory with raw os.makedirs() and never wrote a manifest at all,
        which meant "Save Project" on a temp session had no title/mission/
        provider/model to promote.
        """
        from deployment.workspace.project_manager import ProjectManager

        is_temp_session = (
            strategy.strategy_name not in ["RESEARCH", "DEEP_RESEARCH"]
            and not request.metadata.get("project_mode", False)
            and not request.project_id
        )
        pm = ProjectManager(self.workspace_manager)
        manifest = pm.create_project(
            title=f"{strategy.strategy_name.title()}: {request.mission[:30]}",
            mission=request.mission,
            provider=request.provider,
            model=request.model,
            research_depth=strategy.strategy_name.lower(),
            is_temp=is_temp_session,
        )
        result.project_id = manifest.project_id
        result.project_path = str(self.workspace_manager.get_project_path(manifest.project_id))
        tracer.project_path = result.project_path
        return pm, manifest

    # ── Dispatch Handlers ─────────────────────────────────────

    def _execute_fast(self, request: ResearchRequest, strategy: Any, result: ResearchResult, start_time: float, tracer: ExecutionTraceRecorder) -> ResearchResult:
        """FAST strategy: LLM direct reasoning without web search."""
        self.event_bus.info("Controller", "Executing FAST answering pipeline...")
        tracer.record_module("Planner", skipped=True, reason="Strategy FAST bypasses planner.")
        tracer.record_module("Retriever", skipped=True, reason="Strategy FAST bypasses web search.")
        
        pm, manifest = self._setup_session(request, strategy, result, tracer)

        reasoning_start = time.time()
        
        # 1. Local knowledge lookup first
        kr = KnowledgeRetriever(self.workspace_manager)
        local_res = kr.retrieve_local(request.mission)
        if local_res.reusable_content:
            result.direct_answer = local_res.reusable_content[0].get("content", "")
            result.success = True
            result.statistics.knowledge_cache_hits = 1
            result.statistics.reasoning_time = time.time() - reasoning_start
            result.elapsed_time = time.time() - start_time
            result.statistics.elapsed_time = result.elapsed_time
            self._finalize_and_persist(request, result, pm, manifest)
            return result

        # 2. LLM reasoning query
        llm_manager, ingestion_obj, provider_obj = self._get_verified_dual_providers(request)

        # Prompt budget for FAST is 500 tokens
        table_fmt = "\nIMPORTANT: Format the answer as a clean markdown table." if ("table" in request.mission.lower() or "tabular" in request.mission.lower()) else ""
        prompt = f"Provide a direct answer to the following query:{table_fmt}\n{request.mission}"
        prompt = self.enforce_prompt_budget(prompt, 1000)
        ans = provider_obj.generate(prompt)
        
        tracer.record_llm_call(request.provider, request.model, len(prompt)/4, len(ans)/4)
        
        result.direct_answer = ans
        result.success = True
        result.statistics.llm_calls = 1
        result.statistics.reasoning_time = time.time() - reasoning_start
        result.elapsed_time = time.time() - start_time
        result.statistics.elapsed_time = result.elapsed_time
        self._finalize_and_persist(request, result, pm, manifest)
        return result

    def _execute_lookup(self, request: ResearchRequest, strategy: Any, result: ResearchResult, start_time: float, tracer: ExecutionTraceRecorder) -> ResearchResult:
        """LOOKUP strategy: Web search only, direct answer with minimal reasoning."""
        self.event_bus.info("Controller", "Executing LOOKUP pipeline...")
        tracer.record_module("Planner", skipped=True, reason="Strategy LOOKUP bypasses planner.")
        
        pm, manifest = self._setup_session(request, strategy, result, tracer)

        retRetrieval_start = time.time()
        registry = ToolRegistry()
        from khabrichacha.tools.builtin.search_web import SearchWebTool
        from khabrichacha.tools.builtin.search_news import SearchNewsTool
        from khabrichacha.tools.builtin.fetch_page import FetchPageTool
        registry.register_tool(SearchWebTool())
        registry.register_tool(SearchNewsTool())
        registry.register_tool(FetchPageTool())
        
        # 1. Search Local cache/workspace memory first
        kr = KnowledgeRetriever(self.workspace_manager)
        local_res = kr.retrieve_local(request.mission)
        if not local_res.needs_web_search and local_res.reusable_content:
            result.direct_answer = local_res.reusable_content[0].get("content", "")
            result.success = True
            result.statistics.knowledge_cache_hits = len(local_res.reusable_content)
            result.statistics.retrieval_time = time.time() - retRetrieval_start
            result.elapsed_time = time.time() - start_time
            result.statistics.elapsed_time = result.elapsed_time
            self._finalize_and_persist(request, result, pm, manifest)
            return result

        # Small Question Fast Path Detection
        is_fast_path = (
            strategy.strategy_name == "LOOKUP"
            and (len(request.mission.split()) < 8 or any(request.mission.lower().startswith(w) for w in ["who", "what", "where", "capital", "ceo", "governor"]))
        )
        
        if is_fast_path:
            self.event_bus.info("Controller", "Executing Small Question Fast Path...")
            tracer.record_module("FastPathLookup", execution_time_ms=0.0)
            
            # Search & fetch top source content
            retriever = Retriever(registry, strategy)
            ret_res = retriever.retrieve(request.mission, max_results=1)
            
            top_source_text = ""
            if ret_res.filtered_sources:
                top_src = ret_res.filtered_sources[0]
                try:
                    fetch_res = registry.get_tool("fetch_page").execute({"url": top_src.url})
                    if isinstance(fetch_res, dict) and fetch_res.get("content"):
                        top_source_text = fetch_res.get("content")[:2000]
                except:
                    top_source_text = top_src.snippet
            
            # Simple direct answer prompt (Question + Top Source facts + Instructions)
            prompt = (
                f"Question: {request.mission}\n\n"
                f"Source Content:\n{top_source_text}\n\n"
                f"Instructions: Provide an extremely concise, direct answer to the question using only the source facts above."
            )
            prompt = self.enforce_prompt_budget(prompt, 1000)
            
            llm_manager, ingestion_obj, provider_obj = self._get_verified_dual_providers(request)
                
            ans = provider_obj.generate(prompt)
            tracer.record_llm_call(request.provider, request.model, len(prompt)/4, len(ans)/4)
            ans = self._annotate_if_ungrounded(ans, [top_source_text])
            
            final_conf = (ret_res.estimated_quality + 90.0 + 80.0 + 80.0) / 400.0
            
            result.direct_answer = ans
            result.success = True
            result.strategy_confidence = final_conf
            result.source_count = len(ret_res.filtered_sources)
            result.statistics.sources_downloaded = len(ret_res.filtered_sources)
            result.statistics.search_time = ret_res.search_time
            result.statistics.dedup_time = ret_res.dedup_time
            result.statistics.retrieval_time = time.time() - retRetrieval_start
            result.elapsed_time = time.time() - start_time
            result.statistics.elapsed_time = result.elapsed_time
            self._finalize_and_persist(request, result, pm, manifest, sources=[s.model_dump() for s in ret_res.filtered_sources])
            return result

        # 2. Run Retriever & deduplicate (Normal Lookup Path)
        ret_start = time.time()
        retriever = Retriever(registry, strategy)
        ret_res = retriever.retrieve(request.mission, max_results=strategy.execution_budget.max_searches)
        tracer.record_module("Retriever", (time.time()-ret_start)*1000)
        tracer.record_retrieval(len(ret_res.filtered_sources), len(ret_res.duplicate_sources), 0, 0, 0, [])

        if ret_res.extracted_answer:
            self.event_bus.info("Controller", f"Deterministic direct answer found: {ret_res.extracted_answer}")
            result.direct_answer = f"**{ret_res.extracted_answer}**\n\n*(Extracted directly from search snippets)*"
            result.success = True
            result.strategy_confidence = 1.0
            result.source_count = len(ret_res.filtered_sources)
            result.statistics.sources_downloaded = 0
            result.statistics.search_time = ret_res.search_time
            result.statistics.dedup_time = ret_res.dedup_time
            result.statistics.retrieval_time = time.time() - retRetrieval_start
            result.elapsed_time = time.time() - start_time
            result.statistics.elapsed_time = result.elapsed_time
            self._finalize_and_persist(request, result, pm, manifest, sources=[s.model_dump() for s in ret_res.filtered_sources])
            return result

        # Evidence Sufficiency check
        sufficiency = self.calculate_evidence_sufficiency(ret_res.filtered_sources, request.mission)
        self.event_bus.info("Controller", f"Evidence sufficiency score: {sufficiency:.1f}/100")
        
        if sufficiency < 40.0:
            # Escalate LOOKUP query to ANALYSIS
            self.event_bus.info("Controller", "Evidence insufficient. Escalating LOOKUP to ANALYSIS...")
            # This LOOKUP attempt never produced an answer, and _execute_analysis
            # creates its own project — drop the empty one rather than leaving
            # it locked and dangling in the workspace.
            pm.unlock_project(manifest.project_id)
            pm.delete_project(manifest.project_id)
            escalated_strategy = QueryClassifier().classify(request.mission, strategy_override="ANALYSIS")
            return self._execute_analysis(request, escalated_strategy, result, start_time, tracer)
            
        instructions = "Synthesize a concise answer based on the retrieved facts."
        if sufficiency >= 80.0:
            instructions = "Directly format the facts to answer the question. Bypasses heavy synthesis reasoning."
            
        snippets = [f"- **{s.title}** ({s.url}): {s.snippet}" for s in ret_res.filtered_sources]
        prompt = self.enforce_prompt_budget(
            self.enforce_adaptive_prompt_budget(request.mission, snippets, instructions, 1000),
            1000
        )
        
        llm_manager, ingestion_obj, provider_obj = self._get_verified_dual_providers(request)
            
        ans = provider_obj.generate(prompt)
        tracer.record_llm_call(request.provider, request.model, len(prompt)/4, len(ans)/4)
        ans = self._annotate_if_ungrounded(ans, snippets)

        cb = CitationBuilder()
        citations = cb.build([s.model_dump() for s in ret_res.filtered_sources])
        
        result.direct_answer = ans + "\n\n" + cb.to_markdown(citations)
        result.success = True
        result.strategy_confidence = sufficiency / 100.0
        result.source_count = len(ret_res.filtered_sources)
        result.statistics.sources_downloaded = len(ret_res.filtered_sources)
        result.statistics.search_time = ret_res.search_time
        result.statistics.dedup_time = ret_res.dedup_time
        result.statistics.retrieval_time = time.time() - retRetrieval_start
        result.elapsed_time = time.time() - start_time
        result.statistics.elapsed_time = result.elapsed_time
        self._finalize_and_persist(request, result, pm, manifest, sources=[s.model_dump() for s in ret_res.filtered_sources])
        return result

    def _execute_structured(self, request: ResearchRequest, strategy: Any, result: ResearchResult, start_time: float, tracer: ExecutionTraceRecorder) -> ResearchResult:
        """STRUCTURED strategy: Search → Fetch → extraction → table normalizing → cross-source
        numeric consensus. Bypasses planner."""
        self.event_bus.info("Controller", "Executing STRUCTURED pipeline...")
        tracer.record_module("Planner", skipped=True, reason="Strategy STRUCTURED bypasses planner.")
        
        pm, manifest = self._setup_session(request, strategy, result, tracer)
        
        # 1. Run Search & Fetch
        registry = ToolRegistry()
        from khabrichacha.tools.builtin.search_web import SearchWebTool
        from khabrichacha.tools.builtin.fetch_page import FetchPageTool
        registry.register_tool(SearchWebTool())
        registry.register_tool(FetchPageTool())
        
        ret_start = time.time()
        retriever = Retriever(registry, strategy)
        ret_res = retriever.retrieve(request.mission)
        tracer.record_module("Retriever", (time.time()-ret_start)*1000)
        tracer.record_retrieval(len(ret_res.filtered_sources), len(ret_res.duplicate_sources), 0, 0, 0, [])
        
        # Fetch top trusted sources
        fetch_tool = registry.get_tool("fetch_page")
        fetched_docs = []
        
        # Limit fetches based on budget
        limit = strategy.execution_budget.max_fetches
        for src in ret_res.filtered_sources[:limit]:
            try:
                res = fetch_tool.execute({"url": src.url})
                if isinstance(res, dict) and res.get("content"):
                    if not self._is_content_relevant(request.mission, res["content"]):
                        continue
                    res.setdefault("url", src.url)
                    res.setdefault("trust_score", getattr(src, "trust_score", 50.0))
                    fetched_docs.append(res)
            except Exception:
                pass
                
        # Structured resolver gate: check if literal tables exist (this only
        # decides whether the (more expensive) table extractor runs — numeric
        # consensus below always runs regardless, since a lot of the numbers
        # we actually want ("total accidents worldwide", etc.) are stated in
        # ordinary prose, not a <table>).
        import re
        has_structured = False
        for doc in fetched_docs:
            if doc.get("tables_html"):  # Real HTML table preserved by fetch_page.py
                has_structured = True
                break
            content = doc.get("content", "")
            if "|" in content and "-" in content:  # Markdown table
                has_structured = True
                break
            if "<table" in content.lower() or "tr class=" in content.lower():  # HTML table
                has_structured = True
                break
            if len(re.findall(r'\b\d+(?:\.\d+)?\b', content)) > 20:  # Numerical patterns
                has_structured = True
                break

        from deployment.runtime.intelligence.structured_resolver import StructuredResolver
        resolver = StructuredResolver()

        structured_docs, warnings = [], []
        if has_structured:
            sr_start = time.time()
            structured_docs, warnings = resolver.resolve(fetched_docs)
            tracer.record_module("StructuredResolver", (time.time()-sr_start)*1000)
        else:
            tracer.record_module("StructuredResolver", skipped=True, reason="No literal tables detected in retrieved documents.")

        # 2. Cross-source numeric consensus — reconciles a number (e.g. "total
        # aviation accidents worldwide") across every fetched source instead
        # of trusting whichever single document happened to have a table, or
        # letting an LLM silently pick one number out of its context window.
        #
        # This is deliberately SKIPPED for "how many times has X done Y"
        # style questions. Those ask for a count of discrete occurrences,
        # which source material almost always represents as a list of
        # individual events/dates rather than a single stated summary
        # number -- searching for "the nearest topic-adjacent number" in
        # that case tends to grab an unrelated number that just happens to
        # sit near the topic's keywords (a tournament year, a list index),
        # since the actual count usually isn't written down anywhere at
        # all. See khabrichacha/core/query_shape.py.
        from khabrichacha.core.query_shape import is_occurrence_count_query, OCCURRENCE_COUNT_INSTRUCTION
        is_count_query = is_occurrence_count_query(request.mission)

        consensus_result = None
        if not is_count_query:
            try:
                consensus_result = resolver.extract_numeric_consensus(request.mission, fetched_docs)
            except Exception as e:
                logger.warning(f"Numeric consensus extraction failed: {e}")
        else:
            tracer.record_module("ConsensusEngine", skipped=True, reason="Query asks for a count of occurrences, not a stated aggregate value.")

        cb = CitationBuilder()
        citations = cb.build([s.model_dump() for s in ret_res.filtered_sources])

        sections = []
        # NOTE: ConsensusEngine's "unresolved" resolution is not "nothing was
        # found" -- it means sources disagree enough that no confident
        # majority/average could be computed, and it still returns a
        # best-guess weighted_value plus the full list of conflicts. That
        # disagreement is itself valuable, sourced information (this is
        # exactly the "why sources differ" transparency the feature exists
        # for), so it should still be shown rather than suppressed. Only
        # skip this section when extract_numeric_consensus found no
        # keyword-adjacent numbers in any source at all (returns None).
        has_consensus = bool(consensus_result and consensus_result.weighted_value is not None)
        if has_consensus:
            tracer.record_module("ConsensusEngine", execution_time_ms=0.0)
            sections.append(self._format_consensus_section(consensus_result))
        elif not is_count_query:
            tracer.record_module("ConsensusEngine", skipped=True, reason="No keyword-adjacent numeric claims found across sources.")

        if structured_docs:
            tracer.record_module("LLM Reasoning", skipped=True, reason="Bypassed via StructuredResolver.")
            tracer.record_llm_call(request.provider, request.model, 0, 0, skip_reason="Structured Extraction bypassing.")
            builder = AdvancedResultBuilder()
            plan = ResponsePlanner().plan(strategy, structured_docs, request.mission)
            table_content = resolver.build_unified_table(structured_docs)
            content = table_content or {"text": "Could not format tabular data."}
            if warnings:
                content["validation_warnings"] = warnings
            if is_count_query and table_content:
                count_note = resolver.count_entity_occurrences_in_table(request.mission, table_content)
                if count_note:
                    sections.append(count_note)
            sections.append(builder.build(plan, content, citations))
        else:
            # When no literal HTML/Markdown tables are found in raw HTML,
            # fallback to LLM synthesis to format and answer the request into a clear table/response.
            self.event_bus.info("Controller", "No structured HTML tables detected. Running LLM synthesis...")
            full_texts = [d.get("content", "") for d in fetched_docs if d.get("content")]
            snippets = full_texts if full_texts else [s.snippet for s in ret_res.filtered_sources]
            if "table" in request.mission.lower() or "tabular" in request.mission.lower():
                instructions = "Format the response strictly as a clear, detailed Markdown Table with explicit columns matching the user request (e.g. Year, Export Value, Category). Include all retrieved data points across the requested years."
            elif is_count_query:
                instructions = OCCURRENCE_COUNT_INSTRUCTION
            else:
                instructions = "Provide a synthesized summary based on the retrieved facts since no tables or consensus figures were detected."
            prompt = self.enforce_prompt_budget(
                self.enforce_adaptive_prompt_budget(request.mission, snippets, instructions, 2000),
                2000
            )
            llm_manager, ingestion_obj, provider_obj = self._get_verified_dual_providers(request)
            llm_ans = provider_obj.generate(prompt)
            tracer.record_llm_call(request.provider, request.model, len(prompt)/4, len(llm_ans)/4)
            llm_ans = self._annotate_if_ungrounded(llm_ans, snippets)
            sections.append(llm_ans)

        # AdvancedResultBuilder.build() already renders citations internally
        # when structured_docs is truthy (see its `plan.include_sources`
        # check) -- appending cb.to_markdown(citations) again afterward for
        # that branch would duplicate the whole references list.
        if not structured_docs:
            sections.append(cb.to_markdown(citations))
        ans = "\n\n---\n\n".join(s for s in sections if s and str(s).strip())

        result.direct_answer = ans
        result.success = True
        result.source_count = len(fetched_docs)
        
        self._finalize_and_persist(
            request, result, pm, manifest,
            sources=[s.model_dump() for s in ret_res.filtered_sources],
            extra_json={
                "tables": [d.model_dump() for d in structured_docs] if structured_docs else [],
                "consensus": consensus_result.model_dump() if consensus_result else None,
            },
        )
        
        result.elapsed_time = time.time() - start_time
        result.statistics.elapsed_time = result.elapsed_time
        return result

    def _execute_comparison(self, request: ResearchRequest, strategy: Any, result: ResearchResult, start_time: float, tracer: ExecutionTraceRecorder) -> ResearchResult:
        """COMPARISON strategy: Parallel search + comparison matrix, no planner."""
        self.event_bus.info("Controller", "Executing COMPARISON pipeline...")
        tracer.record_module("Planner", skipped=True, reason="Strategy COMPARISON bypasses planner.")
        
        pm, manifest = self._setup_session(request, strategy, result, tracer)

        # Map subtasks
        decomposer = QueryDecomposer()
        dq = decomposer.decompose(request.mission, strategy)
        
        # Parallel searches for both entities
        registry = ToolRegistry()
        from khabrichacha.tools.builtin.search_web import SearchWebTool
        from khabrichacha.tools.builtin.fetch_page import FetchPageTool
        registry.register_tool(SearchWebTool())
        registry.register_tool(FetchPageTool())
        
        findings = []
        retrieved_sources = []
        
        # Simple execution of comparison entities
        ret_start = time.time()
        for sub in dq.subtasks[:2]:
            self.event_bus.info("Controller", f"Running comparison query task: {sub.description}")
            retriever = Retriever(registry, strategy)
            ret_res = retriever.retrieve(sub.description, max_results=3)
            retrieved_sources.extend([s.model_dump() for s in ret_res.filtered_sources])
            
            # Fetch content
            for src in ret_res.filtered_sources[:2]:
                try:
                    res = registry.get_tool("fetch_page").execute({"url": src.url})
                    if isinstance(res, dict) and res.get("content"):
                        if not self._is_content_relevant(sub.description, res["content"]):
                            continue
                        findings.append(res.get("content")[:1000]) # Keep snippets
                except:
                    pass
        tracer.record_module("Retriever", (time.time()-ret_start)*1000)
        tracer.record_retrieval(len(retrieved_sources), 0, 0, 0, 0, [])
                    
        # LLM Reasoning comparison synthesis
        llm_manager, ingestion_obj, provider_obj = self._get_verified_dual_providers(request)

        # COMPARISON prompt budget is 3000 tokens
        instructions = "Format the response as a markdown table comparison matrix comparing features, specs, pros/cons."
        prompt = self.enforce_prompt_budget(
            self.enforce_adaptive_prompt_budget(request.mission, findings, instructions, 3000),
            3000
        )
        ans = provider_obj.generate(prompt)
        tracer.record_module("LLM Reasoning")
        tracer.record_llm_call(request.provider, request.model, len(prompt)/4, len(ans)/4)
        ans = self._annotate_if_ungrounded(ans, findings)
        
        # Add citations
        cb = CitationBuilder()
        citations = cb.build(retrieved_sources)
        ans += "\n\n" + cb.to_markdown(citations)
        
        result.direct_answer = ans
        result.success = True
        result.source_count = len(retrieved_sources)
        self._finalize_and_persist(request, result, pm, manifest, sources=retrieved_sources)
        result.elapsed_time = time.time() - start_time
        result.statistics.elapsed_time = result.elapsed_time
        return result

    def _execute_analysis(self, request: ResearchRequest, strategy: Any, result: ResearchResult, start_time: float, tracer: ExecutionTraceRecorder) -> ResearchResult:
        """ANALYSIS strategy: Search → Fetch → LLM reasoning, no planner, no report."""
        self.event_bus.info("Controller", "Executing ANALYSIS reasoning pipeline...")
        tracer.record_module("Planner", skipped=True, reason="Strategy ANALYSIS bypasses planner.")
        
        pm, manifest = self._setup_session(request, strategy, result, tracer)

        registry = ToolRegistry()
        from khabrichacha.tools.builtin.search_web import SearchWebTool
        from khabrichacha.tools.builtin.fetch_page import FetchPageTool
        registry.register_tool(SearchWebTool())
        registry.register_tool(FetchPageTool())
        
        # Retriever & Rank
        ret_start = time.time()
        retriever = Retriever(registry, strategy)
        ret_res = retriever.retrieve(request.mission)
        tracer.record_module("Retriever", (time.time()-ret_start)*1000)
        tracer.record_retrieval(len(ret_res.filtered_sources), len(ret_res.duplicate_sources), 0, 0, 0, [])
        
        fetched_text = []
        fetched_docs = []
        limit = strategy.execution_budget.max_fetches
        for src in ret_res.filtered_sources[:limit]:
            try:
                res = registry.get_tool("fetch_page").execute({"url": src.url})
                if isinstance(res, dict) and res.get("content"):
                    if not self._is_content_relevant(request.mission, res["content"]):
                        continue
                    fetched_text.append(res.get("content"))
                    res.setdefault("url", src.url)
                    res.setdefault("trust_score", getattr(src, "trust_score", 50.0))
                    fetched_docs.append(res)
            except:
                pass

        # Cross-source numeric consensus, same mechanism as STRUCTURED —
        # ANALYSIS is where a natural-language aggregation question like
        # "total aviation accidents worldwide" lands by default (it doesn't
        # match the STRUCTURED keyword list), so it needs this too, not just
        # a single LLM paragraph that silently picks one number.
        #
        # Skipped for "how many times has X done Y" style questions -- see
        # khabrichacha/core/query_shape.py for why that shape needs actual
        # counting rather than nearest-number reconciliation.
        from khabrichacha.core.query_shape import is_occurrence_count_query, OCCURRENCE_COUNT_INSTRUCTION
        is_count_query = is_occurrence_count_query(request.mission)

        consensus_section = ""
        if not is_count_query:
            try:
                from deployment.runtime.intelligence.structured_resolver import StructuredResolver
                consensus_result = StructuredResolver().extract_numeric_consensus(request.mission, fetched_docs)
                # See the note in _execute_structured: "unresolved" still carries
                # a useful best-guess value plus the conflict list, so it should
                # be shown, not suppressed.
                if consensus_result and consensus_result.weighted_value is not None:
                    consensus_section = self._format_consensus_section(consensus_result)
            except Exception as e:
                logger.warning(f"Numeric consensus extraction failed in ANALYSIS: {e}")
                
        # Optimize context size: ANALYSIS prompt budget is 6000 tokens
        opt_start = time.time()
        optimizer = ContextOptimizer()
        optimized_context = optimizer.optimize(fetched_text, request.mission, max_tokens=3600)
        tracer.record_module("ContextOptimizer", (time.time()-opt_start)*1000)
        
        # LLM Call
        llm_manager, ingestion_obj, provider_obj = self._get_verified_dual_providers(request)

        if is_count_query:
            instructions = OCCURRENCE_COUNT_INSTRUCTION
        else:
            instructions = "Analyze the context information and answer the query comprehensively, resolving contradictions."
        prompt = self.enforce_prompt_budget(
            self.enforce_adaptive_prompt_budget(request.mission, [optimized_context], instructions, 6000),
            6000
        )
        ans = provider_obj.generate(prompt)
        tracer.record_module("LLM Reasoning")
        tracer.record_llm_call(request.provider, request.model, len(prompt)/4, len(ans)/4)
        ans = self._annotate_if_ungrounded(ans, [optimized_context])
        
        # Citations
        cb = CitationBuilder()
        citations = cb.build([s.model_dump() for s in ret_res.filtered_sources])
        if consensus_section:
            ans = consensus_section + "\n\n---\n\n" + ans
        ans += "\n\n" + cb.to_markdown(citations)
        
        result.direct_answer = ans
        result.success = True
        result.source_count = len(fetched_text)
        self._finalize_and_persist(request, result, pm, manifest, sources=[s.model_dump() for s in ret_res.filtered_sources])
        result.elapsed_time = time.time() - start_time
        result.statistics.elapsed_time = result.elapsed_time
        return result

    def _execute_research(self, request: ResearchRequest, strategy: Any, result: ResearchResult, start_time: float, tracer: ExecutionTraceRecorder) -> ResearchResult:
        """RESEARCH strategy: Core planner-driven research but with adaptive iterations cap."""
        self.event_bus.info("Controller", "Executing RESEARCH planner pipeline...")
        return self._run_core_orchestration(request, strategy, result, start_time, tracer, enable_adaptive=False)

    def _execute_deep_research(self, request: ResearchRequest, strategy: Any, result: ResearchResult, start_time: float, tracer: ExecutionTraceRecorder) -> ResearchResult:
        """DEEP_RESEARCH strategy: Complete multi-loop adaptive engine with evidence evaluation."""
        self.event_bus.info("Controller", "Executing DEEP_RESEARCH adaptive pipeline...")
        return self._run_core_orchestration(request, strategy, result, start_time, tracer, enable_adaptive=True)

    # ── Core Engine Runner ────────────────────────────────────

    def _run_core_orchestration(
        self, request: ResearchRequest, strategy: Any, result: ResearchResult, start_time: float, tracer: ExecutionTraceRecorder, enable_adaptive: bool = False
    ) -> ResearchResult:
        from deployment.workspace.project_manager import ProjectManager
        from khabrichacha.core.orchestrator import Orchestrator
        from deployment.reporting.report_exporter import ReportExporter
        from deployment.runtime.intelligence.knowledge_graph import KnowledgeGraph
        
        pm = ProjectManager(self.workspace_manager)
        
        if request.resume and request.project_id:
            manifest = pm.resume_project(request.project_id)
        else:
            manifest = pm.create_project(
                title=f"Research: {request.mission[:30]}",
                mission=request.mission,
                provider=request.provider,
                model=request.model,
                research_depth=request.depth
            )
            
        project_id = manifest.project_id
        result.project_id = project_id
        result.project_path = str(self.workspace_manager.projects / project_id)
        tracer.project_path = result.project_path
        
        self.event_bus.info("Controller", f"Project {project_id} ready.")

        # Session setup
        session = Session()
        ing_prov = request.ingestion_provider or request.provider
        ing_mod = request.ingestion_model or request.model
        ana_prov = request.analysis_provider or request.provider
        ana_mod = request.analysis_model or request.model

        session.config["llm"] = {
            "default_provider": ana_prov,
            "ingestion_provider": ing_prov,
            "analysis_provider": ana_prov,
            "temperature": 0.7,
            "max_tokens": 2048,
        }
        if "providers" not in session.config:
            session.config["providers"] = {}
        session.config["providers"][ing_prov] = {"model": ing_mod}
        session.config["providers"][ana_prov] = {"model": ana_mod}

        session.config["research"] = {
            "depth": request.depth.lower(),
            "max_sources": request.metadata.get("max_sources", 5),
            "max_iterations": strategy.max_iterations,
        }

        llm_manager = LLMManager(session.config)
        provider_obj = llm_manager.get_analysis_provider()

            
        registry = ToolRegistry()
        executor = ToolExecutor(registry, project_id, result.project_path)
        
        orchestrator = Orchestrator(
            session=session,
            llm_manager=llm_manager,
            tool_registry=executor
        )
        
        self.event_bus.info("Orchestrator", "Starting execution phase")
        orch_start = time.time()
        try:
            # Overrides iterations in session configurations
            session.config["research"]["max_iterations"] = strategy.max_iterations
            orchestrator.run(request.mission)
        except Exception as orch_e:
            logger.error(f"Orchestration interrupted: {orch_e}")
            result.errors.append(ErrorInfo(component="Orchestrator", message=str(orch_e)))
            result.warnings.append("Research was interrupted but partial results may exist.")
        tracer.record_module("Orchestrator", (time.time()-orch_start)*1000)

        # Extract Findings and Sources
        findings = session.research_state.get("findings", [])
        sources_list = []
        for t in session.state.tasks:
            if t.status == "completed" and t.result:
                try:
                    parsed = json.loads(t.result)
                    if isinstance(parsed, list):
                        for item in parsed:
                            if isinstance(item, dict) and "url" in item:
                                sources_list.append({"title": item.get("title", "Untitled"), "url": item["url"]})
                except Exception:
                    pass

        # Generate insights using LLM
        evidence = ""
        kg_data = {}
        try:
            if findings:
                from khabrichacha.core.grounding import GROUNDING_INSTRUCTION, find_ungrounded_claims

                provider_obj = llm_manager.get_analysis_provider()
                findings_text = "\n".join(findings)
                
                table_instruction = ""
                if "table" in request.mission.lower() or "tabular" in request.mission.lower():
                    table_instruction = "\nIMPORTANT: The user explicitly requested a TABULAR response. You MUST include a clean, comprehensive Markdown Table (with columns such as Year, Export Value (in Billion USD), Growth/Notes) presenting all data points from 2015 to 2025."

                prompt = (
                    f"You are an expert research analyst. The user requested research on: '{request.mission}'.\n"
                    f"Based on the following raw findings extracted from various sources, please organize, synthesize, and present a well-structured response.{table_instruction}\n"
                    f"Arrange the information logically, provide clear insights, and eliminate redundancy.\n\n"
                    f"{GROUNDING_INSTRUCTION}\n\n"
                    f"Raw Findings:\n" + findings_text
                )
                evidence = provider_obj.generate(prompt)

                ungrounded = find_ungrounded_claims(evidence, findings_text)
                if ungrounded:
                    logger.warning(f"Evidence summary contains {len(ungrounded)} numeric claim(s) not traceable to retrieved findings: {ungrounded}")
                    evidence += (
                        "\n\n> **Note:** The following figures in this summary could not be "
                        "directly verified against the retrieved sources and may be "
                        f"estimated or drawn from general knowledge: {', '.join(ungrounded)}."
                    )
                
                # LAZY KNOWLEDGE GRAPH GENERATION
                self.event_bus.info("KnowledgeGraph", "Generating lazy knowledge graph for deep research...")
                kg_start = time.time()
                kg = KnowledgeGraph()
                kg.build_from_findings(findings, request.mission)
                kg_data = kg.export_graph()
                tracer.record_module("KnowledgeGraph", (time.time()-kg_start)*1000)
            else:
                # Direct reasoning fallback when no search findings were collected
                provider_obj = llm_manager.get_analysis_provider()
                prompt = f"Provide a concise, direct, and factual answer to the following question:\n{request.mission}"
                evidence = provider_obj.generate(prompt)
                findings = [evidence]
                
        except Exception as e:
            logger.error(f"Failed to generate LLM insights or knowledge graph: {e}")

        # Build timeline
        timeline_parts = []
        for i in range(1, session.research_state.get("iteration", 0) + 1):
            s = session.runtime.get(f"iteration_{i}_summary")
            if s:
                timeline_parts.append(s)
        timeline = "\n\n".join(timeline_parts)

        # Report Generation
        self.event_bus.info("Report", "Generating output reports")
        exporter = ReportExporter()
        exports = exporter.generate(
            title=manifest.title,
            mission=manifest.mission,
            provider=request.provider,
            model=request.model,
            findings=findings,
            sources=sources_list,
            evidence=evidence,
            research_state=session.research_state,
            timeline=timeline
        )
        
        # Save Everything
        runtime_state = RuntimeState(
            session_id=session.session_id,
            variables={k: str(v)[:500] for k, v in session.runtime.items()},
        )
        research_st = SchemaResearchState(**session.research_state)
        planner_st = PlannerState(steps=session.state.variables.get("plan_steps", []))
        ref_entries = [ReferenceEntry(title=s.get("title", ""), url=s.get("url", "")) for s in sources_list]
        ref_index = ReferenceIndex(entries=ref_entries, total=len(ref_entries))

        result.success = len(result.errors) == 0
        pm.update_manifest(
            project_id,
            status="completed" if result.success else "failed",
            iterations=session.research_state.get("iteration", 0),
            source_count=len(sources_list),
            evidence_count=len(findings),
        )

        pm.save_project(
            project_id,
            runtime=runtime_state,
            research_state=research_st,
            planner_state=planner_st,
            references=ref_index,
            report_md=exports["report_md"],
            report_json=exports["report_json"],
            report_pdf_bytes=exports.get("report_pdf_bytes"),
            report_docx_bytes=exports.get("report_docx_bytes"),
        )
        pm.unlock_project(project_id)
        
        # Populate final result paths
        if "md" in request.output_formats:
            result.report_md_path = os.path.join(result.project_path, "report.md")
        if "txt" in request.output_formats:
            result.report_txt_path = os.path.join(result.project_path, "report.txt")
        if "json" in request.output_formats:
            result.report_json_path = os.path.join(result.project_path, "report.json")
        if "pdf" in request.output_formats:
            result.report_pdf_path = os.path.join(result.project_path, "report.pdf")
        if "docx" in request.output_formats:
            result.report_docx_path = os.path.join(result.project_path, "report.docx")

        result.iterations = session.research_state.get("iteration", 0)
        result.evidence_count = len(findings)
        result.source_count = len(sources_list)
        
        result.statistics.elapsed_time = time.time() - start_time
        result.statistics.iterations = result.iterations
        result.elapsed_time = result.statistics.elapsed_time
        
        self.event_bus.info("Controller", "Research completed.")
        return result
