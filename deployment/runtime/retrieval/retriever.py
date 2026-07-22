import time
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
from loguru import logger

from deployment.runtime.models.research_strategy import ResearchStrategy
from deployment.runtime.models.retrieval_result import RetrievalResult, CandidateSource
from deployment.runtime.retrieval.deduplicator import Deduplicator
from deployment.runtime.retrieval.source_ranker import SourceRanker

class Retriever:
    """Coordinates search execution across multiple tools, merges, deduplicates, and ranks sources."""

    def __init__(self, tool_registry: Any, strategy: ResearchStrategy):
        self.tool_registry = tool_registry
        self.strategy = strategy
        self.deduplicator = Deduplicator()
        self.ranker = SourceRanker()

    def classify_intent(self, query: str) -> str:
        q = query.lower()
        if any(w in q for w in ["who is", "biography", "born", "died", "president", "prime minister", "ceo", "governor", "founder"]):
            return "Person"
        if any(w in q for w in ["company", "corporation", "inc", "microsoft", "google", "apple", "nvidia", "meta", "tesla"]):
            return "Organization"
        if any(w in q for w in ["capital of", "population of", "country", "nation", "map of"]):
            return "Country"
        if any(w in q for w in ["timeline", "history", "chronology", "years", "century"]):
            return "Timeline"
        if any(w in q for w in ["budget", "revenue", "fiscal", "finance", "gdp", "earnings", "stocks", "quarterly", "inflation"]):
            return "Financial"
        if any(w in q for w in ["statistics", "percent", "average", "median", "survey", "data table", "figures"]):
            return "Statistical"
        if any(w in q for w in ["versus", "vs", "compare", "comparison", "difference between"]):
            return "Comparison"
        if any(w in q for w in ["regulation", "act", "law", "policy", "guidelines", "compliance", "sebi", "rbi", "sec"]):
            return "Regulation"
        if any(w in q for w in ["news", "latest", "today", "recent", "announcement"]):
            return "News"
        if any(w in q for w in ["research", "study", "arxiv", "nature", "science", "scientific", "journal"]):
            return "Scientific"
        if any(w in q for w in ["syntax", "code", "programming", "python", "javascript", "function", "compile", "error"]):
            return "Programming"
        if any(w in q for w in ["what is", "define", "meaning", "explanation"]):
            return "Fact Lookup"
        return "General Research"

    def extract_direct_answer(self, query: str, snippets: List[str]) -> Optional[str]:
        """
        Scans snippets for direct deterministic factual answers like "CEO", "Capital".
        Returns the answer directly if found with high confidence (>95%), otherwise None.
        """
        import re
        q_lower = query.lower()
        # Direct regex patterns for factual extraction
        patterns = []
        if "capital" in q_lower:
            patterns.append(r'(?i)(?:the capital of [a-zA-Z\s]+ is|is the capital of)\s+([A-Z][a-zA-Z\s]+?)(?:,|\.)')
        if "ceo" in q_lower or "chief executive" in q_lower:
            patterns.append(r'(?i)([A-Z][a-zA-Z\s]+?)\s+is the CEO of')
            patterns.append(r'(?i)CEO(?: of)? [a-zA-Z\s]+ (?:is|was) ([A-Z][a-zA-Z\s]+?)(?:,|\.)')
        if "prime minister" in q_lower:
            patterns.append(r'(?i)(?:prime minister of [a-zA-Z\s]+ is)\s+([A-Z][a-zA-Z\s]+?)(?:,|\.)')
            
        if not patterns:
            return None
            
        for snippet in snippets:
            for pattern in patterns:
                match = re.search(pattern, snippet)
                if match:
                    answer = match.group(1).strip()
                    if len(answer) > 2 and len(answer) < 30:
                        logger.info(f"Deterministic extraction matched answer: {answer}")
                        return answer
                        
        return None

    def retrieve(self, query: str, max_results: int = 10) -> RetrievalResult:
        """
        Runs search queries, merges, deduplicates, ranks, and returns structured RetrievalResult.
        Does NOT download pages. Classifies query intent and handles failures explicitly.
        """
        start_time = time.time()
        intent = self.classify_intent(query)
        logger.info(f"Classified query intent: {intent}")
        
        # 1. Determine which search tools to run based on strategy and intent
        search_tools = []
        for t in self.strategy.enabled_tools:
            if t in ["search_web", "search_news"] and self.tool_registry.has_tool(t):
                search_tools.append(t)
                
        if not search_tools:
            if self.tool_registry.has_tool("search_web"):
                search_tools.append("search_web")
                
        # Limit max results for LOOKUP strategy
        if self.strategy.strategy_name == "LOOKUP":
            limit = min(5, max(3, self.strategy.execution_budget.max_searches or 3))
        else:
            limit = self.strategy.execution_budget.max_searches or max_results

        # 1b. Enhance queries with OfficialSourceResolver (skip for LOOKUP to keep simple)
        queries_to_run = [query]
        if self.strategy.strategy_name != "LOOKUP":
            from deployment.runtime.intelligence.official_source_resolver import OfficialSourceResolver
            resolver = OfficialSourceResolver()
            queries_to_run = resolver.enhance_search_queries([query])

        # Entity splitting for Comparison intent
        if intent == "Comparison":
            import re
            parts = re.split(r'\s+vs\s+|\s+versus\s+|\s+compare\s+|\s+and\s+', query, flags=re.IGNORECASE)
            sub_queries = [p.strip() for p in parts if p.strip()]
            if len(sub_queries) > 1:
                queries_to_run = sub_queries

        raw_results = []
        search_time = 0.0
        last_error = None
        error_category = "None"

        # Search execution helper
        def run_search(t_name, q):
            logger.info(f"Running search tool '{t_name}' for query: '{q}'")
            try:
                res = self.tool_registry.execute(t_name, {"query": q, "max_results": limit})
                results = []
                if isinstance(res, list):
                    for item in res:
                        if isinstance(item, dict):
                            item_copy = item.copy()
                            item_copy["source_tool"] = t_name
                            item_copy["search_query"] = q
                            results.append(item_copy)
                return results, None
            except Exception as e:
                logger.error(f"Search tool '{t_name}' failed for query '{q}': {e}")
                return [], e

        # Parallel search runner
        def execute_parallel(q_list, tools):
            import concurrent.futures
            p_results = []
            errors = []
            
            # Adaptive Parallelism based on Strategy
            s_name = self.strategy.strategy_name
            if s_name in ["FAST", "LOOKUP"]:
                max_workers = 1
            elif s_name in ["COMPARISON"]:
                max_workers = min(4, len(tools) * len(q_list))
            else:
                max_workers = min(8, len(tools) * len(q_list))
            max_workers = max(1, max_workers)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for t_name in tools:
                    for q in q_list:
                        futures.append(executor.submit(run_search, t_name, q))
                for future in concurrent.futures.as_completed(futures):
                    res, err = future.result()
                    if err:
                        errors.append(err)
                    p_results.extend(res)
            return p_results, errors

        # Attempt 1: Standard Parallel Search
        search_start = time.time()
        raw_results, errors = execute_parallel(queries_to_run, search_tools)
        search_time += time.time() - search_start

        # Classify errors if execution failed
        if errors:
            last_error = errors[0]
            from khabrichacha.tools.builtin.search_web import SearchNetworkError, SearchProviderError, SearchParserError
            if isinstance(last_error, SearchNetworkError):
                error_category = "Network Failure"
            elif isinstance(last_error, SearchProviderError):
                error_category = "Provider Failure"
            else:
                error_category = "Parser Failure"

        # Fallbacks & Retries if zero results
        if not raw_results:
            logger.warning(f"First search attempt yielded zero results (Category: {error_category}). Initiating retry pipeline...")
            
            # Retry #1: Simplify query terms and use fallback DDG HTML search
            logger.info("Search Retry #1: Simplified query with HTML fallback...")
            search_start = time.time()
            try:
                try:
                    from ddgs import DDGS
                except ImportError:
                    from duckduckgo_search import DDGS
                with DDGS() as ddgs:
                    results = ddgs.text(query, max_results=limit, backend="html")
                    if results:
                        for r in results:
                            raw_results.append({
                                "title": r.get("title", ""),
                                "url": r.get("href", ""),
                                "snippet": r.get("body", ""),
                                "source_tool": "search_web_html",
                                "search_query": query
                            })
            except Exception as e:
                logger.error(f"HTML fallback failed: {e}")
            search_time += time.time() - search_start

        if not raw_results:
            # Retry #2: news search
            logger.info("Search Retry #2: Querying news search...")
            search_start = time.time()
            raw_results, _ = run_search("search_news", query)
            search_time += time.time() - search_start

        if not raw_results:
            # Official source enhance fallback
            logger.info("Retry #3: Official source query fallback...")
            search_start = time.time()
            from deployment.runtime.intelligence.official_source_resolver import OfficialSourceResolver
            resolver = OfficialSourceResolver()
            enhanced = resolver.enhance_search_queries([query])
            if len(enhanced) > 1:
                raw_results, _ = run_search("search_web", enhanced[1])
            search_time += time.time() - search_start

        if not raw_results:
            # If still zero, raise or classify as Legitimate No Results
            if last_error:
                raise ValueError(f"Search failed ({error_category}): {last_error}")
            else:
                error_category = "Legitimate No Results"
                raise ValueError(f"Search failed (Legitimate No Results): No documents found for query '{query}'")

        # 3. Deduplicate
        dedup_start = time.time()
        unique_raw, duplicate_raw = self.deduplicator.deduplicate(raw_results)
        dedup_time = time.time() - dedup_start

        # 4. Rank with intent context
        rank_start = time.time()
        ranked_raw = self.ranker.rank(unique_raw, query, intent=intent)
        rank_time = time.time() - rank_start

        # Convert to CandidateSource models
        candidate_sources = []
        for r in raw_results:
            candidate_sources.append(self._to_candidate_source(r))

        ranked_sources = []
        for r in ranked_raw:
            ranked_sources.append(self._to_candidate_source(r))

        duplicate_sources = []
        for r in duplicate_raw:
            duplicate_sources.append(self._to_candidate_source(r, is_duplicate=True))

        # Select filtered top sources based on budget, filtering low-quality (<40.0)
        # AND now also filtering sources that aren't actually on-topic for
        # this query -- rank_score reflects trust/authority/freshness, but
        # says nothing about whether a source is still about what was
        # asked. Without this, a highly "trusted" domain that happens to
        # return an off-topic page (e.g. a government portal's unrelated
        # homepage) can still outrank genuinely relevant results.
        from khabrichacha.core.relevance import RelevanceScorer
        relevance_scorer = RelevanceScorer(query)
        max_sources = self.strategy.execution_budget.max_sources or 5
        quality_passed = [s for s in ranked_sources if s.rank_score >= 40.0]
        relevant_passed = [
            s for s in quality_passed
            if relevance_scorer.is_relevant(f"{s.title} {s.snippet}", threshold=0.12)
        ]
        filtered_sources = relevant_passed[:max_sources]
        relevance_rejected_count = len(quality_passed) - len(relevant_passed)

        # Quality and trust estimation
        avg_quality = sum(s.rank_score for s in filtered_sources) / len(filtered_sources) if filtered_sources else 0.0
        avg_trust = sum(s.trust_score for s in filtered_sources) / len(filtered_sources) if filtered_sources else 0.0

        # Try to extract direct deterministic answer from snippets
        extracted_answer = None
        if self.strategy.strategy_name in ["FAST", "LOOKUP"]:
            snippets = [s.snippet for s in filtered_sources]
            extracted_answer = self.extract_direct_answer(query, snippets)

        return RetrievalResult(
            candidate_sources=candidate_sources,
            ranked_sources=ranked_sources,
            duplicate_sources=duplicate_sources,
            filtered_sources=filtered_sources,
            estimated_quality=avg_quality,
            estimated_trust=avg_trust,
            recommended_fetch_count=min(len(filtered_sources), max_sources),
            search_time=search_time,
            dedup_time=dedup_time,
            rank_time=rank_time,
            extracted_answer=extracted_answer,
            diagnostics={
                "error_category": error_category,
                "latency_ms": search_time * 1000,
                "engines_used": search_tools,
                "results_returned": len(raw_results),
                "filtered": len(ranked_sources) - len(filtered_sources),
                "relevance_rejected": relevance_rejected_count,
                "duplicates": len(duplicate_sources),
                "selected": len(filtered_sources),
                "last_error": str(last_error) if last_error else None
            }
        )

    def _to_candidate_source(self, r: Dict[str, Any], is_duplicate: bool = False) -> CandidateSource:
        url = r.get("url", "")
        domain = ""
        if url:
            try:
                domain = urlparse(url).netloc.lower()
            except Exception:
                pass
                
        return CandidateSource(
            url=url,
            title=r.get("title", ""),
            snippet=r.get("snippet", ""),
            domain=domain,
            rank_score=r.get("rank_score", 0.0),
            trust_score=r.get("trust_score", 50.0),
            is_duplicate=is_duplicate or r.get("is_duplicate", False),
            duplicate_reason=r.get("duplicate_reason", ""),
            source_tool=r.get("source_tool", ""),
            domain_category=r.get("domain_category", "general")
        )
