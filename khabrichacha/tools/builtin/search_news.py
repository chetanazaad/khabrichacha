import urllib.parse
import urllib.request
import urllib.error
import socket
from typing import Dict, Any, List
from khabrichacha.tools.base import BaseTool
from loguru import logger

class SearchNewsTool(BaseTool):
    """
    Search the latest news articles related to a user query.
    """

    @property
    def name(self) -> str:
        return "search_news"

    @property
    def description(self) -> str:
        return "Search the latest news articles related to a user query."

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
        Executes a Google News RSS search using feedparser and returns the extracted results.
        """
        logger.info("SearchNewsTool execution started.")

        if "query" not in arguments or not arguments["query"]:
            error_msg = "Missing or empty 'query' argument."
            logger.error(error_msg)
            raise ValueError(error_msg)

        query = str(arguments["query"])
        max_results = arguments.get("max_results", 10)

        logger.info(f"Searching news for query: '{query}' with max_results={max_results}")
        
        try:
            import feedparser
        except ImportError:
            logger.error("feedparser package is not installed. Returning empty results.")
            return []

        # Encode query for URL
        encoded_query = urllib.parse.quote(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}"
        
        results_formatted = []
        try:
            # Enforce 15-second network timeout
            req = urllib.request.Request(
                rss_url, 
                headers={'User-Agent': 'Mozilla/5.0 KhabriChacha/1.0'}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                feed_content = response.read()
                
            feed = feedparser.parse(feed_content)
            
            # Map up to max_results entries
            for entry in feed.entries[:max_results]:
                source_title = ""
                if hasattr(entry, 'source') and hasattr(entry.source, 'title'):
                    source_title = entry.source.title
                elif 'source' in entry and isinstance(entry.source, dict) and 'title' in entry.source:
                    source_title = entry.source['title']
                    
                results_formatted.append({
                    "title": getattr(entry, 'title', ""),
                    "url": getattr(entry, 'link', ""),
                    "published": getattr(entry, 'published', ""),
                    "source": source_title,
                    "summary": getattr(entry, 'summary', "")
                })
                
            logger.info(f"News search successfully returned {len(results_formatted)} results.")
        except urllib.error.URLError as e:
            if isinstance(e.reason, socket.timeout):
                logger.error(f"Network timeout (15s) while fetching news for query '{query}'.")
            else:
                logger.error(f"Network error while fetching news for query '{query}': {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to parse or fetch news for query '{query}': {e}")
            return []
            
        return results_formatted
