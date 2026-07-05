import re
from typing import Dict, Any, List
from khabrichacha.tools.base import BaseTool
from loguru import logger

class FetchPageTool(BaseTool):
    """
    Download a webpage and extract the clean readable article text.
    """

    @property
    def name(self) -> str:
        return "fetch_page"

    @property
    def description(self) -> str:
        return "Download a webpage and extract the clean readable article text."

    @property
    def category(self) -> str:
        return "browser"

    @property
    def version(self) -> str:
        return "1.0"

    @property
    def inputs(self) -> List[str]:
        return ["url"]

    @property
    def outputs(self) -> List[str]:
        return ["url", "title", "content"]

    @property
    def supports_streaming(self) -> bool:
        return False

    def execute(self, arguments: Dict[str, Any]) -> Any:
        """
        Downloads one or more webpages and extracts clean readable article text.
        """
        logger.info("FetchPageTool execution started.")
        
        urls = arguments.get("url")
        if not urls:
            error_msg = "Missing or empty 'url' argument."
            logger.error(error_msg)
            raise ValueError(error_msg)

        if isinstance(urls, list):
            results = []
            for u in urls:
                # Handle cases where the list contains dicts (e.g. from search_news results)
                url_str = u.get("url") if isinstance(u, dict) else str(u)
                results.append(self._fetch_single(url_str))
            return results
        else:
            url_str = urls.get("url") if isinstance(urls, dict) else str(urls)
            return self._fetch_single(url_str)

    def _fetch_single(self, url: str) -> Dict[str, str]:
        """
        Downloads a webpage and extracts clean readable article text.
        """
        logger.info("FetchPageTool execution started.")
        
        default_return = {
            "url": url,
            "title": "",
            "content": ""
        }
        
        logger.info(f"Fetching page from URL: '{url}'")

        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("requests or beautifulsoup4 package is not installed.")
            return default_return

        try:
            from readability import Document
            has_readability = True
        except ImportError:
            has_readability = False
            logger.warning("readability-lxml is not installed. Will fallback to BeautifulSoup.")

        try:
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=20
            )
            response.raise_for_status()
            html_content = response.text
        except Exception as e:
            logger.error(f"Network error while fetching URL '{url}': {e}")
            return default_return

        title = ""
        extracted_html = ""
        
        if has_readability:
            try:
                doc = Document(html_content)
                title = doc.short_title()
                extracted_html = doc.summary()
            except Exception as e:
                logger.error(f"Readability parsing failed: {e}. Falling back to BeautifulSoup.")
                extracted_html = html_content
        else:
            extracted_html = html_content

        try:
            soup = BeautifulSoup(extracted_html, "html.parser")
            
            if not title:
                title_tag = soup.find("title")
                if title_tag:
                    title = title_tag.get_text(strip=True)
            
            # Remove unwanted tags
            for tag in soup(["script", "style", "header", "footer", "nav", "aside", "noscript", "svg", "iframe"]):
                tag.decompose()
                
            raw_text = soup.get_text(separator="\n")
            
            # Collapse multiple blank lines and whitespace
            clean_text = re.sub(r'\n\s*\n', '\n\n', raw_text)
            clean_text = clean_text.strip()
            
            # Limit output to 10000 characters
            if len(clean_text) > 10000:
                clean_text = clean_text[:10000] + "\n...[TRUNCATED]"
                
            logger.info(f"Successfully extracted {len(clean_text)} characters from {url}")
            
            return {
                "url": url,
                "title": title,
                "content": clean_text
            }
            
        except Exception as e:
            logger.error(f"Error during BeautifulSoup parsing/cleanup: {e}")
            return default_return
