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
from deployment.config_loader import load_config
from deployment.runtime.event_bus import EventBus, ResearchEvent
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
from deployment.runtime.retrieval.knowledge_retriever import KnowledgeRetriever
from deployment.runtime.retrieval.retriever import Retriever
from deployment.runtime.retrieval.trust_evaluator import TrustEvaluator
from deployment.runtime.extraction.structured_extractor import StructuredExtractor
from deployment.runtime.intelligence.numerical_validator import NumericalValidator
from deployment.runtime.intelligence.consensus_engine import ConsensusEngine
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
from deployment.runtime.intelligence.citation_builder import CitationBuilder
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

        # Singleton ToolRegistry — all tools registered once at init
        t0 = time.time()
        self._tool_registry = ToolRegistry()
        from khabrichacha.tools.builtin.search_web import SearchWebTool
        from khabrichacha.tools.builtin.search_news import SearchNewsTool
        from khabrichacha.tools.builtin.fetch_page import FetchPageTool
        self._tool_registry.register_tool(SearchWebTool())
        self._tool_registry.register_tool(SearchNewsTool())
        self._tool_registry.register_tool(FetchPageTool())
        profiler.record_init("ToolRegistry", "ResearchController", "Singleton", (time.time() - t0) * 1000)

        # Singleton LLMManager — one instance shared across all lightweight handlers
        t0 = time.time()
        config = load_config()
        self._llm_config = config.to_legacy_dict()
        self._llm_manager = LLMManager(self._llm_config)
        profiler.record_init("LLMManager", "ResearchController", "Singleton", (time.time() - t0) * 1000)

        self._query_classifier = QueryClassifier()
        import threading
        self._cancel_event = threading.Event()

    def _get_provider(self, request: ResearchRequest):
        """Get a validated LLM provider for the given request, using the singleton LLMManager."""
        if "providers" not in self._llm_config:
            self._llm_config["providers"] = {}
        self._llm_config["providers"][request.provider] = {"model": request.model}

        provider_obj = self._llm_manager.get_provider(request.provider)
        actual_model = provider_obj.model_identifier
        if actual_model != request.model:
            raise ValueError(f"Model mismatch: requested '{request.model}', but provider instantiated '{actual_model}'")
        return provider_obj

    def stop(self):
        """Signals the active research task to cancel execution."""
        logger.info("Cancellation signal received by ResearchController.")
        self._cancel_event.set()

    def enforce_prompt_budget(self, prompt: str, max_tokens: int) -> str:
        # safe approximation: 1 token ≈ 4 characters.
        max_chars = max_tokens * 4
        if len(prompt) > max_chars:
            logger.warning(f"Prompt length ({len(prompt)} chars) exceeds budget ({max_chars} chars). Truncating context.")
            return prompt[:max_chars]
        return prompt

    def enforce_adaptive_prompt_budget(self, query: str, evidence: List[str], instructions: str, max_tokens: int) -> str:
        max_chars = max_tokens * 4
        q_limit = int(max_chars * 0.20)
        e_limit = int(max_chars * 0.60)
        i_limit = int(max_chars * 0.20)
        
        truncated_query = query[:q_limit]
        truncated_instructions = instructions[:i_limit]
        
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
        self._cancel_event.clear()
        start_time = time.time()
        
        # 1. Classify Query
        class_start = time.time()
        strategy = self._query_classifier.classify(request.mission, request.strategy_override)
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
        
        if "providers" not in self._llm_config:
            self._llm_config["providers"] = {}
        self._llm_config["providers"][request.provider] = {"model": request.model}
        
        tracer = ExecutionTraceRecorder()
        tracer.set_query_info(request.mission, strategy.strategy_name, strategy.confidence, strategy.complexity)
        tracer.record_runtime_info(
            config_source="cached",
            tool_registry_source="singleton",
            session_created=strategy.strategy_name in ("RESEARCH", "DEEP_RESEARCH"),
        )
        tracer.record_module("QueryClassifier", class_time * 1000)
        
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
        try:
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
            qe = QualityEvaluator(llm_manager=self._llm_manager)
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
            
            # Auto-Regeneration logic
            if scores.get("overall_score", 100) < 80.0 and strategy.strategy_name != "DEEP_RESEARCH" and not request.metadata.get("auto_regenerated"):
                self.event_bus.warn("Controller", f"Low quality score ({scores.get('overall_score')}/100). Auto-regenerating with higher strategy...")
                request.metadata["auto_regenerated"] = True
                # Escalate strategy
                new_strat = "RESEARCH" if strategy.strategy_name in ["FAST", "LOOKUP", "ANALYSIS"] else "DEEP_RESEARCH"
                request.strategy_override = new_strat
                return self.start_research(request)
            elif scores.get("overall_score", 100) < 80.0:
                self.event_bus.warn("Controller", f"Final answer quality score is low ({scores.get('overall_score')}/100). Adding warning to answer.")
                if final_result.direct_answer:
                    final_result.direct_answer += f"\n\n> [!WARNING]\n> The generated answer has a low confidence/quality score ({scores.get('overall_score')}/100) and might be incomplete or hallucinated."

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
            import traceback
            logger.error(f"ResearchController execution error: {e}", exc_info=True)
            result.success = False
            result.errors.append(ErrorInfo(
                code="EXECUTION_ERROR",
                component="ResearchController",
                message=str(e),
                details=traceback.format_exc(),
                recoverable=False
            ))
            return result

    def _setup_session(self, request: ResearchRequest, strategy: Any, result: ResearchResult, tracer: ExecutionTraceRecorder):
        """Sets up the session (temporary or persistent) based on the strategy."""
        is_temp_session = (
            strategy.strategy_name not in ["RESEARCH", "DEEP_RESEARCH"]
            and not request.metadata.get("project_mode", False)
            and not request.project_id
        )
        from deployment.workspace.project_manager import ProjectManager
        pm = ProjectManager(self.workspace_manager)
        
        if is_temp_session:
            manifest = pm.create_project(
                title=f"Research: {request.mission[:30]}",
                mission=request.mission,
                provider=request.provider,
                model=request.model,
                research_depth=strategy.strategy_name.lower(),
                is_temp=True
            )
            result.project_id = manifest.project_id
            result.project_path = str(self.workspace_manager.temp / result.project_id)
            tracer.project_path = result.project_path
        else:
            # Persistent Session via ProjectManager
            manifest = pm.create_project(
                title=f"Research: {request.mission[:30]}",
                mission=request.mission,
                provider=request.provider,
                model=request.model,
                research_depth=strategy.strategy_name.lower(),
                is_temp=False
            )
            result.project_id = manifest.project_id
            result.project_path = str(self.workspace_manager.get_project_path(manifest.project_id))
            tracer.project_path = result.project_path
            pm.lock_project(manifest.project_id)
            
        return pm, manifest, is_temp_session

    # ── Dispatch Handlers ─────────────────────────────────────

    def _execute_fast(self, request: ResearchRequest, strategy: Any, result: ResearchResult, start_time: float, tracer: ExecutionTraceRecorder) -> ResearchResult:
        """FAST strategy: LLM direct reasoning without web search or project files."""
        self.event_bus.info("Controller", "Executing FAST answering pipeline...")
        tracer.record_module("Planner", skipped=True, reason="Strategy FAST bypasses planner.")
        tracer.record_module("Retriever", skipped=True, reason="Strategy FAST bypasses web search.")
        
        pm, manifest, is_temp = self._setup_session(request, strategy, result, tracer)

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
            self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="Fast answer resolved via local cache.", metadata={"progress": 1.0}))
            return result

        if self._cancel_event.is_set():
            result.success = False
            result.errors.append(ErrorInfo(code="CANCELLED", component="Controller", message="Task stopped by user."))
            return result

        # 2. LLM reasoning query
        self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="Generating LLM response...", metadata={"progress": 0.5}))
        provider_obj = self._get_provider(request)

        # Prompt budget for FAST is 500 tokens
        prompt = f"Provide a concise, direct answer to the following question:\n{request.mission}"
        prompt = self.enforce_prompt_budget(prompt, 500)
        ans = provider_obj.generate(prompt)
        
        tracer.record_llm_call(request.provider, request.model, len(prompt)/4, len(ans)/4)
        
        result.direct_answer = ans
        result.success = True
        result.statistics.llm_calls = 1
        result.statistics.reasoning_time = time.time() - reasoning_start
        result.elapsed_time = time.time() - start_time
        result.statistics.elapsed_time = result.elapsed_time
        
        self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="FAST pipeline completed.", metadata={"progress": 1.0}))
        return result

    def _execute_lookup(self, request: ResearchRequest, strategy: Any, result: ResearchResult, start_time: float, tracer: ExecutionTraceRecorder) -> ResearchResult:
        """LOOKUP strategy: Web search only, direct answer with minimal reasoning."""
        self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="Executing LOOKUP pipeline...", metadata={"progress": 0.1}))
        tracer.record_module("Planner", skipped=True, reason="Strategy LOOKUP bypasses planner.")
        
        pm, manifest, is_temp = self._setup_session(request, strategy, result, tracer)

        retRetrieval_start = time.time()
        registry = self._tool_registry
        
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
            self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="Lookup resolved via local cache.", metadata={"progress": 1.0}))
            return result

        if self._cancel_event.is_set():
            result.success = False
            result.errors.append(ErrorInfo(code="CANCELLED", component="Controller", message="Task stopped by user."))
            return result

        # Small Question Fast Path Detection
        is_fast_path = (
            strategy.strategy_name == "LOOKUP"
            and (len(request.mission.split()) < 8 or any(request.mission.lower().startswith(w) for w in ["who", "what", "where", "capital", "ceo", "governor"]))
        )
        
        if is_fast_path:
            self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="Executing Small Question Fast Path...", metadata={"progress": 0.3}))
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
            
            if self._cancel_event.is_set():
                result.success = False
                result.errors.append(ErrorInfo(code="CANCELLED", component="Controller", message="Task stopped by user."))
                return result

            # Simple direct answer prompt (Question + Top Source facts + Instructions)
            prompt = (
                f"Question: {request.mission}\n\n"
                f"Source Content:\n{top_source_text}\n\n"
                f"Instructions: Provide an extremely concise, direct answer to the question using only the source facts above."
            )
            prompt = self.enforce_prompt_budget(prompt, 1000)
            
            self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="Generating direct answer...", metadata={"progress": 0.7}))
            provider_obj = self._get_provider(request)
            ans = provider_obj.generate(prompt)
            tracer.record_llm_call(request.provider, request.model, len(prompt)/4, len(ans)/4)
            
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
            self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="LOOKUP completed via fast path.", metadata={"progress": 1.0}))
            return result

        # 2. Run Retriever & deduplicate (Normal Lookup Path)
        self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="Searching web for sources...", metadata={"progress": 0.3}))
        ret_start = time.time()
        retriever = Retriever(registry, strategy)
        ret_res = retriever.retrieve(request.mission, max_results=strategy.execution_budget.max_searches)
        tracer.record_module("Retriever", (time.time()-ret_start)*1000)
        tracer.record_retrieval(len(ret_res.filtered_sources), len(ret_res.duplicate_sources), 0, 0, 0, [])

        if self._cancel_event.is_set():
            result.success = False
            result.errors.append(ErrorInfo(code="CANCELLED", component="Controller", message="Task stopped by user."))
            return result

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
            self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="LOOKUP completed via deterministic extraction.", metadata={"progress": 1.0}))
            return result

        # Evidence Sufficiency check
        sufficiency = self.calculate_evidence_sufficiency(ret_res.filtered_sources, request.mission)
        self.event_bus.info("Controller", f"Evidence sufficiency score: {sufficiency:.1f}/100")
        
        if sufficiency < 40.0:
            # Escalate LOOKUP query to ANALYSIS
            self.event_bus.info("Controller", "Evidence insufficient. Escalating LOOKUP to ANALYSIS...")
            from deployment.runtime.models.research_strategy import ResearchStrategy
            escalated_strategy = self._query_classifier.classify(request.mission, strategy_override="ANALYSIS")
            return self._execute_analysis(request, escalated_strategy, result, start_time, tracer)

        if self._cancel_event.is_set():
            result.success = False
            result.errors.append(ErrorInfo(code="CANCELLED", component="Controller", message="Task stopped by user."))
            return result

        # 3. Fast extraction & LLM Synthesizer (General Lookup)
        self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="Synthesizing direct answer...", metadata={"progress": 0.6}))
        provider_obj = self._get_provider(request)
        
        snippets = [s.snippet for s in ret_res.filtered_sources]
        instructions = "Provide a synthesized direct answer based on the facts provided."
        prompt = self.enforce_prompt_budget(
            self.enforce_adaptive_prompt_budget(request.mission, snippets, instructions, 2000),
            2000
        )
        
        ans = provider_obj.generate(prompt)
        tracer.record_llm_call(request.provider, request.model, len(prompt)/4, len(ans)/4)

        cb = CitationBuilder()
        citations = cb.build([s.model_dump() for s in ret_res.filtered_sources])
        
        result.direct_answer = ans + "\n\n" + cb.to_markdown(citations)
        result.success = True
        result.source_count = len(ret_res.filtered_sources)
        result.statistics.sources_downloaded = 0
        result.statistics.search_time = ret_res.search_time
        result.statistics.dedup_time = ret_res.dedup_time
        result.statistics.retrieval_time = time.time() - retRetrieval_start
        result.elapsed_time = time.time() - start_time
        result.statistics.elapsed_time = result.elapsed_time
        
        self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="LOOKUP completed.", metadata={"progress": 1.0}))
        return result

    def _execute_structured(self, request: ResearchRequest, strategy: Any, result: ResearchResult, start_time: float, tracer: ExecutionTraceRecorder) -> ResearchResult:
        """STRUCTURED strategy: Search → Fetch → extraction → table normalizing. Bypasses planner."""
        self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="Executing STRUCTURED pipeline...", metadata={"progress": 0.1}))
        tracer.record_module("Planner", skipped=True, reason="Strategy STRUCTURED bypasses planner.")
        
        pm, manifest, is_temp = self._setup_session(request, strategy, result, tracer)
        
        # 1. Run Search & Fetch
        registry = self._tool_registry
        
        ret_start = time.time()
        retriever = Retriever(registry, strategy)
        ret_res = retriever.retrieve(request.mission)
        tracer.record_module("Retriever", (time.time()-ret_start)*1000)
        tracer.record_retrieval(len(ret_res.filtered_sources), len(ret_res.duplicate_sources), 0, 0, 0, [])
        
        if self._cancel_event.is_set():
            result.success = False
            result.errors.append(ErrorInfo(code="CANCELLED", component="Controller", message="Task stopped by user."))
            return result

        # Fetch top trusted sources
        self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="Fetching trusted sources...", metadata={"progress": 0.3}))
        fetch_tool = registry.get_tool("fetch_page")
        fetched_docs = []
        
        # Limit fetches based on budget
        limit = strategy.execution_budget.max_fetches
        for src in ret_res.filtered_sources[:limit]:
            if self._cancel_event.is_set():
                break
            try:
                res = fetch_tool.execute({"url": src.url})
                if isinstance(res, dict) and res.get("content"):
                    res["trust_score"] = src.trust_score
                    res["url"] = src.url
                    fetched_docs.append(res)
            except Exception:
                pass

        if self._cancel_event.is_set():
            result.success = False
            result.errors.append(ErrorInfo(code="CANCELLED", component="Controller", message="Task stopped by user."))
            return result

        # Run Consensus Engine on the fetched documents
        self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="Analyzing numerical consensus...", metadata={"progress": 0.5}))
        source_values = []
        provider_obj = self._get_provider(request)
        for doc in fetched_docs:
            if self._cancel_event.is_set():
                break
            url = doc.get("url", "Unknown")
            trust = doc.get("trust_score", 50.0)
            content = doc.get("content", "")[:4000] # Limit content size for LLM call
            
            # Ask LLM to extract the specific value
            extract_prompt = (
                f"Task: Extract the numerical value answering the query: '{request.mission}' from the text below.\n\n"
                f"Text:\n{content}\n\n"
                "Instructions: Find the exact numeric value (as a float/integer) that represents the answer. "
                "Return ONLY a JSON object in this format (do not wrap in markdown code blocks, do not include any other text):\n"
                "{\"value\": <float or null>, \"description\": \"<description of value>\"}"
            )
            try:
                response_text = provider_obj.generate(extract_prompt)
                response_text = response_text.strip()
                if response_text.startswith("```"):
                    response_text = re.sub(r'^```(?:json)?\n|```$', '', response_text, flags=re.MULTILINE).strip()
                parsed = json.loads(response_text)
                val = parsed.get("value")
                desc = parsed.get("description", "")
                if val is not None:
                    try:
                        val_float = float(val)
                        source_values.append({
                            "source_name": url,
                            "value": val_float,
                            "weight": trust / 100.0,
                            "description": desc
                        })
                    except (ValueError, TypeError):
                        pass
            except Exception as e:
                logger.warning(f"Failed to extract consensus value from {url}: {e}")

        consensus_md = ""
        consensus_score_val = 0.0
        if source_values:
            ce = ConsensusEngine()
            consensus_result = ce.verify_numerical(request.mission, source_values)
            if consensus_result and consensus_result.resolution != "unresolved":
                consensus_score_val = consensus_result.confidence
                consensus_md = (
                    f"### Consensus Verification\n"
                    f"- **Resolved Value**: {consensus_result.weighted_value}\n"
                    f"- **Resolution Strategy**: {consensus_result.resolution.replace('_', ' ').title()}\n"
                    f"- **Confidence Score**: {consensus_result.confidence:.0%}\n"
                    f"- **Agreement**: {consensus_result.agreement_percentage:.1f}% of sources agree\n\n"
                    f"#### Sources in Agreement\n"
                )
                for src in consensus_result.agreeing_sources:
                    consensus_md += f"- [{src}]({src})\n"
                if consensus_result.conflicting_sources:
                    consensus_md += f"\n#### Conflicting Sources\n"
                    for conflict in consensus_result.conflicts:
                        src = conflict["source"]
                        val = conflict["value"]
                        diff = conflict["difference"]
                        consensus_md += f"- [{src}]({src}): Value = {val} (Difference = {diff:.2f})\n"
                consensus_md += "\n---\n"

        result.retrieval_stats["consensus_score"] = consensus_score_val
        avg_trust = sum(s.trust_score for s in ret_res.filtered_sources) / len(ret_res.filtered_sources) if ret_res.filtered_sources else 50.0
        result.retrieval_stats["avg_trust_score"] = avg_trust
        result.output_format = "table"

        # Structured resolver gate: check if tables or structured numbers exist
        import re
        has_structured = False
        for doc in fetched_docs:
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

        structured_docs = []
        if has_structured:
            # 2. Extract Structured data using StructuredResolver (Smart LLM Bypass)
            self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="Extracting structured tables...", metadata={"progress": 0.7}))
            from deployment.runtime.intelligence.structured_resolver import StructuredResolver
            sr_start = time.time()
            resolver = StructuredResolver()
            structured_docs, warnings = resolver.resolve(fetched_docs)
            tracer.record_module("StructuredResolver", (time.time()-sr_start)*1000)
            tracer.record_module("LLM Reasoning", skipped=True, reason="Bypassed via StructuredResolver.")
            tracer.record_llm_call(request.provider, request.model, 0, 0, skip_reason="Structured Extraction bypassing.")
                    
            # 3. Format result
            cb = CitationBuilder()
            citations = cb.build([s.model_dump() for s in ret_res.filtered_sources])
            
            builder = AdvancedResultBuilder()
            plan = ResponsePlanner().plan(strategy, structured_docs, request.mission)
            
            if structured_docs:
                table_content = resolver.build_unified_table(structured_docs)
                content = table_content or {"text": "Could not format tabular data."}
                if warnings:
                    content["validation_warnings"] = warnings
            else:
                content = {"text": "No structured data tables could be successfully extracted from sources."}
                
            ans = builder.build(plan, content, []) # Build without citations first
            if consensus_md:
                ans = consensus_md + "\n" + ans
            if citations:
                ans = ans + "\n\n" + cb.to_markdown(citations)
        else:
            self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="No structured tables detected. Synthesizing summary...", metadata={"progress": 0.7}))
            tracer.record_module("StructuredResolver", skipped=True, reason="No tables detected in retrieved documents.")
            
            # Normal synthesis fallback
            snippets = [s.snippet for s in ret_res.filtered_sources]
            instructions = "Provide a synthesized summary based on the retrieved facts since no tables were detected."
            prompt = self.enforce_prompt_budget(
                self.enforce_adaptive_prompt_budget(request.mission, snippets, instructions, 2000),
                2000
            )
            ans = provider_obj.generate(prompt)
            tracer.record_llm_call(request.provider, request.model, len(prompt)/4, len(ans)/4)

            cb = CitationBuilder()
            citations = cb.build([s.model_dump() for s in ret_res.filtered_sources])
            if consensus_md:
                ans = consensus_md + "\n" + ans
            ans = ans + "\n\n" + cb.to_markdown(citations)

        result.direct_answer = ans
        result.success = True
        result.source_count = len(fetched_docs)
        
        # Save project
        pm.save_project(
            manifest.project_id,
            report_md=ans,
            report_json={"answer": ans, "tables": [d.model_dump() for d in structured_docs] if has_structured else []}
        )
        if not is_temp:
            pm.update_manifest(manifest.project_id, status="completed")
            pm.unlock_project(manifest.project_id)
        
        result.elapsed_time = time.time() - start_time
        result.statistics.elapsed_time = result.elapsed_time
        self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="STRUCTURED pipeline completed.", metadata={"progress": 1.0}))
        return result

    def _execute_comparison(self, request: ResearchRequest, strategy: Any, result: ResearchResult, start_time: float, tracer: ExecutionTraceRecorder) -> ResearchResult:
        """COMPARISON strategy: Parallel search + comparison matrix, no planner."""
        self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="Executing COMPARISON pipeline...", metadata={"progress": 0.1}))
        tracer.record_module("Planner", skipped=True, reason="Strategy COMPARISON bypasses planner.")
        
        pm, manifest, is_temp = self._setup_session(request, strategy, result, tracer)

        # Map subtasks
        decomposer = QueryDecomposer()
        dq = decomposer.decompose(request.mission, strategy)
        
        # Parallel searches for both entities
        registry = self._tool_registry
        
        findings = []
        retrieved_sources = []
        
        # Simple execution of comparison entities
        ret_start = time.time()
        for idx, sub in enumerate(dq.subtasks[:2]):
            if self._cancel_event.is_set():
                break
            self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message=f"Running comparison subquery: {sub.description}", metadata={"progress": 0.2 + idx*0.2}))
            retriever = Retriever(registry, strategy)
            ret_res = retriever.retrieve(sub.description, max_results=3)
            retrieved_sources.extend([s.model_dump() for s in ret_res.filtered_sources])
            
            # Fetch content
            for src in ret_res.filtered_sources[:2]:
                if self._cancel_event.is_set():
                    break
                try:
                    res = registry.get_tool("fetch_page").execute({"url": src.url})
                    if isinstance(res, dict) and res.get("content"):
                        findings.append(res.get("content")[:1000]) # Keep snippets
                except:
                    pass
                    
        tracer.record_module("Retriever", (time.time()-ret_start)*1000)
        tracer.record_retrieval(len(retrieved_sources), 0, 0, 0, 0, [])
                    
        if self._cancel_event.is_set():
            result.success = False
            result.errors.append(ErrorInfo(code="CANCELLED", component="Controller", message="Task stopped by user."))
            return result

        # LLM Reasoning comparison synthesis
        self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="Synthesizing comparison matrix...", metadata={"progress": 0.6}))
        provider_obj = self._get_provider(request)

        # COMPARISON prompt budget is 3000 tokens
        instructions = "Format the response as a markdown table comparison matrix comparing features, specs, pros/cons."
        prompt = self.enforce_prompt_budget(
            self.enforce_adaptive_prompt_budget(request.mission, findings, instructions, 3000),
            3000
        )
        ans = provider_obj.generate(prompt)
        tracer.record_module("LLM Reasoning")
        tracer.record_llm_call(request.provider, request.model, len(prompt)/4, len(ans)/4)
        
        # Add citations
        cb = CitationBuilder()
        citations = cb.build(retrieved_sources)
        ans += "\n\n" + cb.to_markdown(citations)
        
        result.direct_answer = ans
        result.success = True
        
        # Save project
        pm.save_project(
            manifest.project_id,
            report_md=ans,
            report_json={"answer": ans}
        )
        if not is_temp:
            pm.update_manifest(manifest.project_id, status="completed")
            pm.unlock_project(manifest.project_id)
            
        result.elapsed_time = time.time() - start_time
        result.statistics.elapsed_time = result.elapsed_time
        self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="COMPARISON completed.", metadata={"progress": 1.0}))
        return result

    def _execute_analysis(self, request: ResearchRequest, strategy: Any, result: ResearchResult, start_time: float, tracer: ExecutionTraceRecorder) -> ResearchResult:
        """ANALYSIS strategy: Search → Fetch → LLM reasoning, no planner, no report."""
        self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="Executing ANALYSIS reasoning pipeline...", metadata={"progress": 0.1}))
        tracer.record_module("Planner", skipped=True, reason="Strategy ANALYSIS bypasses planner.")
        
        pm, manifest, is_temp = self._setup_session(request, strategy, result, tracer)

        registry = self._tool_registry
        
        # Retriever & Rank
        self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="Searching web for sources...", metadata={"progress": 0.2}))
        ret_start = time.time()
        retriever = Retriever(registry, strategy)
        ret_res = retriever.retrieve(request.mission)
        tracer.record_module("Retriever", (time.time()-ret_start)*1000)
        tracer.record_retrieval(len(ret_res.filtered_sources), len(ret_res.duplicate_sources), 0, 0, 0, [])
        
        if self._cancel_event.is_set():
            result.success = False
            result.errors.append(ErrorInfo(code="CANCELLED", component="Controller", message="Task stopped by user."))
            return result

        self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="Fetching source contents...", metadata={"progress": 0.4}))
        fetched_text = []
        limit = strategy.execution_budget.max_fetches
        for src in ret_res.filtered_sources[:limit]:
            if self._cancel_event.is_set():
                break
            try:
                res = registry.get_tool("fetch_page").execute({"url": src.url})
                if isinstance(res, dict) and res.get("content"):
                    fetched_text.append(res.get("content"))
            except:
                pass
                
        if self._cancel_event.is_set():
            result.success = False
            result.errors.append(ErrorInfo(code="CANCELLED", component="Controller", message="Task stopped by user."))
            return result

        # Optimize context size: ANALYSIS prompt budget is 6000 tokens
        opt_start = time.time()
        optimizer = ContextOptimizer()
        optimized_context = optimizer.optimize(fetched_text, request.mission, max_tokens=3600)
        tracer.record_module("ContextOptimizer", (time.time()-opt_start)*1000)
        
        # LLM Call
        self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="Analyzing context information...", metadata={"progress": 0.7}))
        provider_obj = self._get_provider(request)

        instructions = "Analyze the context information and answer the query comprehensively, resolving contradictions."
        prompt = self.enforce_prompt_budget(
            self.enforce_adaptive_prompt_budget(request.mission, [optimized_context], instructions, 6000),
            6000
        )
        ans = provider_obj.generate(prompt)
        tracer.record_module("LLM Reasoning")
        tracer.record_llm_call(request.provider, request.model, len(prompt)/4, len(ans)/4)
        
        # Citations
        cb = CitationBuilder()
        citations = cb.build([s.model_dump() for s in ret_res.filtered_sources])
        ans += "\n\n" + cb.to_markdown(citations)
        
        result.direct_answer = ans
        result.success = True
        result.source_count = len(fetched_text)
        
        # Save project
        pm.save_project(
            manifest.project_id,
            report_md=ans,
            report_json={"answer": ans}
        )
        if not is_temp:
            pm.update_manifest(manifest.project_id, status="completed")
            pm.unlock_project(manifest.project_id)

        result.elapsed_time = time.time() - start_time
        result.statistics.elapsed_time = result.elapsed_time
        self.event_bus.publish(ResearchEvent(level="INFO", component="Controller", message="ANALYSIS completed.", metadata={"progress": 1.0}))
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
        session.config["llm"] = {
            "default_provider": request.provider,
            "temperature": 0.7,
            "max_tokens": 2048,
        }
        if "providers" not in session.config:
            session.config["providers"] = {}
        session.config["providers"][request.provider] = {
            "model": request.model,
        }
        session.config["research"] = {
            "depth": request.depth.lower(),
            "max_sources": request.metadata.get("max_sources", 5),
            "max_iterations": strategy.max_iterations,
        }

        llm_manager = LLMManager(session.config)
        provider_obj = llm_manager.get_provider(request.provider)
        actual_model = provider_obj.model_identifier
        if actual_model != request.model:
            raise ValueError(f"Model mismatch: requested '{request.model}', but provider instantiated '{actual_model}'.")
            
        executor = ToolExecutor(self._tool_registry, project_id, result.project_path)
        
        orchestrator = Orchestrator(
            session=session,
            llm_manager=llm_manager,
            tool_registry=executor,
            tracer=tracer,
            adaptive_enabled=enable_adaptive,
            cancel_event=self._cancel_event
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
                provider_obj = llm_manager.get_provider()
                prompt = (
                    f"You are an expert research analyst. The user requested research on: '{request.mission}'.\n"
                    f"Based on the following raw findings extracted from various sources, please organize, synthesize, and present a well-structured summary. "
                    f"Arrange the information logically, provide clear insights, and eliminate redundancy.\n\n"
                    f"Raw Findings:\n" + "\n".join(findings)
                )
                evidence = provider_obj.generate(prompt)
                
                # LAZY KNOWLEDGE GRAPH GENERATION
                # Only runs for RESEARCH and DEEP_RESEARCH (handled via _run_core_orchestration)
                self.event_bus.info("KnowledgeGraph", "Generating lazy knowledge graph for deep research...")
                kg_start = time.time()
                kg = KnowledgeGraph()
                kg.build_from_findings(findings, request.mission)
                kg_data = kg.export_graph()
                tracer.record_module("KnowledgeGraph", (time.time()-kg_start)*1000)
                
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
        if "json" in request.output_formats:
            result.report_json_path = os.path.join(result.project_path, "report.json")
        if "pdf" in request.output_formats:
            result.report_pdf_path = os.path.join(result.project_path, "report.pdf")
        if "docx" in request.output_formats or not request.output_formats:
            result.report_docx_path = os.path.join(result.project_path, "report.docx")

        result.iterations = session.research_state.get("iteration", 0)
        result.evidence_count = len(findings)
        result.source_count = len(sources_list)
        
        result.statistics.elapsed_time = time.time() - start_time
        result.statistics.iterations = result.iterations
        result.elapsed_time = result.statistics.elapsed_time
        
        self.event_bus.info("Controller", "Research completed.")
        return result
