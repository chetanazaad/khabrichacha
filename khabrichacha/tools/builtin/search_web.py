import os
import urllib.parse
import urllib.request
import urllib.error
import socket
from typing import Dict, Any, List
from khabrichacha.tools.base import BaseTool
from loguru import logger

class SearchNetworkError(Exception):
    """Exception raised when there are network connection issues during web search."""
    pass

class SearchProviderError(Exception):
    """Exception raised when the search provider blocks or ratelimits the request."""
    pass

class SearchParserError(Exception):
    """Exception raised when the response format changes or fails to parse."""
    pass

class SearchWebTool(BaseTool):
    """
    Search the web for relevant pages related to a user query.

    Uses DuckDuckGo (via `ddgs`) by default -- no setup required. If a
    SearxNG instance is configured (env var SEARXNG_URL, e.g. a
    self-hosted `docker run searxng/searxng`), results from both are
    merged and deduplicated by URL for meaningfully broader coverage:
    SearxNG itself aggregates across many backend search engines, so
    combining it with DuckDuckGo gets closer to the breadth that
    metasearch-based tools rely on, rather than depending on a single
    engine's index and ranking. This is entirely optional -- with no
    SEARXNG_URL set, behavior is unchanged from DuckDuckGo-only.
    """

    @property
    def name(self) -> str:
        return "search_web"

    @property
    def description(self) -> str:
        return "Search the web for relevant pages related to a user query."

    @property
    def category(self) -> str:
        return "search"

    @property
    def version(self) -> str:
        return "1.1"

    @property
    def inputs(self) -> List[str]:
        return ["query"]

    @property
    def outputs(self) -> List[str]:
        return ["results"]

    @property
    def supports_streaming(self) -> bool:
        return False

    def execute(self, arguments: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Executes a web search (DuckDuckGo, plus SearxNG if configured) and
        returns the merged, deduplicated results.
        """
        logger.info("SearchWebTool execution started.")

        if "query" not in arguments or not arguments["query"]:
            error_msg = "Missing or empty 'query' argument."
            logger.error(error_msg)
            raise ValueError(error_msg)

        query = str(arguments["query"])
        max_results = arguments.get("max_results", 5)

        logger.info(f"Searching web for query: '{query}' with max_results={max_results}")

        ddg_results, ddg_error = self._search_ddg(query, max_results)
        searxng_results = self._search_searxng(query, max_results)

        if not ddg_results and not searxng_results:
            # Neither backend produced anything -- surface the DuckDuckGo
            # error (SearxNG failures are logged but treated as a
            # best-effort supplement, not a hard dependency).
            if ddg_error is not None:
                raise ddg_error
            return []

        merged = self._merge_and_dedupe(ddg_results, searxng_results, max_results)
        logger.info(
            f"Search returned {len(merged)} results "
            f"(DuckDuckGo: {len(ddg_results)}, SearxNG: {len(searxng_results)})."
        )
        return merged

    # ── DuckDuckGo (default, always available) ────────────────

    def _search_ddg(self, query: str, max_results: int):
        results_formatted = []
        try:
            # "duckduckgo_search" was frozen by its maintainer in mid-2025 and
            # renamed to "ddgs" (identical DDGS class/API) -- prefer the
            # maintained package, but fall back for older installs.
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = ddgs.text(query, max_results=max_results, backend="lite")
                if results is None:
                    raise SearchParserError("Search engine returned empty/invalid response.")
                for r in results:
                    results_formatted.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", "")
                    })
            return results_formatted, None
        except Exception as e:
            logger.error(f"DuckDuckGo search failed for query '{query}': {e}")
            err_str = str(e).lower()
            if "ratelimit" in err_str or "429" in err_str or "forbidden" in err_str or "403" in err_str:
                error = SearchProviderError(f"Search provider rate limit/block: {e}")
            elif "connection" in err_str or "timeout" in err_str or "unreachable" in err_str or "dns" in err_str:
                error = SearchNetworkError(f"Search network connection error: {e}")
            else:
                error = SearchParserError(f"Search parsing/generic error: {e}")
            return [], error

    # ── SearxNG (optional, additive) ───────────────────────────

    def _search_searxng(self, query: str, max_results: int) -> List[Dict[str, str]]:
        searxng_url = os.getenv("SEARXNG_URL")
        if not searxng_url:
            try:
                from deployment.config_loader import load_config
                config = load_config()
                searxng_url = config.model_dump().get("search", {}).get("searxng_url")
            except Exception:
                pass
        if not searxng_url:
            return []
        try:
            import requests
            resp = requests.get(
                f"{searxng_url.rstrip('/')}/search",
                params={"q": query, "format": "json"},
                timeout=10,
            )
            if resp.status_code != 200:
                logger.debug(f"SearxNG returned status {resp.status_code}; skipping.")
                return []
            data = resp.json()
            results = []
            for r in data.get("results", [])[:max_results]:
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", ""),
                })
            return results
        except Exception as e:
            # SearxNG is a best-effort supplement -- if it's misconfigured,
            # unreachable, or times out, log it and just proceed with
            # whatever DuckDuckGo returned rather than failing the search.
            logger.debug(f"SearxNG search failed (continuing with other backends): {e}")
            return []

    # ── Merge ───────────────────────────────────────────────────

    @staticmethod
    def _merge_and_dedupe(
        primary: List[Dict[str, str]],
        secondary: List[Dict[str, str]],
        max_results: int,
    ) -> List[Dict[str, str]]:
        def _norm(url: str) -> str:
            return url.strip().rstrip("/").lower()

        seen = set()
        merged = []
        for r in primary + secondary:
            key = _norm(r.get("url", ""))
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(r)
        return merged[:max_results]
