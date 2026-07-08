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
        return "1.0"

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
        Executes a web search using duckduckgo_search and returns the extracted results.
        """
        logger.info("SearchWebTool execution started.")

        if "query" not in arguments or not arguments["query"]:
            error_msg = "Missing or empty 'query' argument."
            logger.error(error_msg)
            raise ValueError(error_msg)

        query = str(arguments["query"])
        max_results = arguments.get("max_results", 5)

        logger.info(f"Searching web for query: '{query}' with max_results={max_results}")
        
        results_formatted = []
        try:
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
            logger.info(f"Search successfully returned {len(results_formatted)} results.")
        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            err_str = str(e).lower()
            if "ratelimit" in err_str or "429" in err_str or "forbidden" in err_str or "403" in err_str:
                raise SearchProviderError(f"Search provider rate limit/block: {e}")
            elif "connection" in err_str or "timeout" in err_str or "unreachable" in err_str or "dns" in err_str:
                raise SearchNetworkError(f"Search network connection error: {e}")
            else:
                raise SearchParserError(f"Search parsing/generic error: {e}")
            
        return results_formatted
