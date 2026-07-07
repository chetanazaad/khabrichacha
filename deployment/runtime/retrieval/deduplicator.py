import hashlib
from typing import List, Dict, Any, Tuple
from urllib.parse import urlparse, urlunparse
from loguru import logger

class Deduplicator:
    """Detects and removes duplicate search results and fetched documents."""

    @staticmethod
    def clean_url(url: str) -> str:
        """Normalizes a URL to its canonical form to detect duplicate pages."""
        try:
            parsed = urlparse(url.strip())
            # Convert netloc to lowercase
            netloc = parsed.netloc.lower()
            # Remove www. from netloc for mirroring detection
            if netloc.startswith("www."):
                netloc = netloc[4:]
            
            # Normalize path (remove trailing slash)
            path = parsed.path
            if path.endswith("/"):
                path = path[:-1]
                
            # Reconstruct without fragment and tracking query parameters
            # Keep important query params (like id, v for youtube, page)
            query_params = []
            if parsed.query:
                for param in parsed.query.split("&"):
                    if any(param.startswith(k + "=") for k in ["id", "v", "p", "page", "article"]):
                        query_params.append(param)
            
            normalized_query = "&".join(sorted(query_params))
            
            return urlunparse((
                parsed.scheme,
                netloc,
                path,
                parsed.params,
                normalized_query,
                ""  # Remove fragments
            ))
        except Exception as e:
            logger.warning(f"Failed to clean URL '{url}': {e}")
            return url

    def deduplicate(self, results: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Deduplicates search results by normalized URL, title + domain, and content hashes (if present).
        Returns a tuple: (unique_results, duplicate_results)
        """
        unique_results = []
        duplicate_results = []
        
        seen_urls = set()
        seen_title_domains = set()
        seen_content_hashes = set()
        
        for r in results:
            url = r.get("url", "")
            title = r.get("title", "").strip().lower()
            content = r.get("content", "")
            
            if not url:
                continue
                
            normalized_url = self.clean_url(url)
            
            # 1. Exact or normalized URL duplication
            if normalized_url in seen_urls:
                r["duplicate_reason"] = "duplicate_url"
                duplicate_results.append(r)
                continue
                
            # 2. Same domain + same/very similar title (mirror articles)
            try:
                domain = urlparse(url).netloc.lower()
            except Exception:
                domain = ""
            
            # Simple title normalization to remove punctuation and extra spaces
            title_clean = "".join(c for c in title if c.isalnum() or c.isspace())
            title_clean = " ".join(title_clean.split())
            
            title_domain_key = (domain, title_clean)
            if title_clean and title_domain_key in seen_title_domains:
                r["duplicate_reason"] = "mirror_article"
                duplicate_results.append(r)
                continue
                
            # 3. Content hash duplication (if page content was fetched)
            if content:
                content_hash = hashlib.md5(content.strip().encode("utf-8")).hexdigest()
                if content_hash in seen_content_hashes:
                    r["duplicate_reason"] = "duplicate_content"
                    duplicate_results.append(r)
                    continue
                seen_content_hashes.add(content_hash)
            
            # Mark as unique
            seen_urls.add(normalized_url)
            if title_clean:
                seen_title_domains.add(title_domain_key)
            unique_results.append(r)
            
        return unique_results, duplicate_results
