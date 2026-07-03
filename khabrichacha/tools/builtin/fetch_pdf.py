from typing import Dict, Any, List, Union
from khabrichacha.tools.base import BaseTool
from loguru import logger

class FetchPDFTool(BaseTool):
    """
    Download a PDF from a URL and extract readable text.
    """

    @property
    def name(self) -> str:
        return "fetch_pdf"

    @property
    def description(self) -> str:
        return "Download a PDF from a URL and extract readable text."

    @property
    def category(self) -> str:
        return "document"

    @property
    def version(self) -> str:
        return "1.0"

    @property
    def inputs(self) -> List[str]:
        return ["url"]

    @property
    def outputs(self) -> List[str]:
        return ["url", "title", "content", "pages"]

    @property
    def supports_streaming(self) -> bool:
        return False

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Union[str, int]]:
        """
        Downloads a PDF into memory and extracts text using PyMuPDF (fitz).
        """
        logger.info("FetchPDFTool execution started.")
        
        default_return = {
            "url": "",
            "title": "",
            "pages": 0,
            "content": ""
        }

        if "url" not in arguments or not arguments["url"]:
            error_msg = "Missing or empty 'url' argument."
            logger.error(error_msg)
            raise ValueError(error_msg)

        url = str(arguments["url"])
        default_return["url"] = url
        
        logger.info(f"Fetching PDF from URL: '{url}'")

        try:
            import requests
        except ImportError:
            logger.error("requests package is not installed.")
            return default_return
            
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.error("PyMuPDF (fitz) package is not installed.")
            return default_return

        try:
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=20
            )
            response.raise_for_status()
            pdf_bytes = response.content
        except Exception as e:
            logger.error(f"Network error while fetching PDF URL '{url}': {e}")
            return default_return

        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            page_count = len(doc)
            title = doc.metadata.get("title", "") if doc.metadata else ""
            if title is None:
                title = ""
                
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())
                
            full_text = "\n".join(text_parts).strip()
            
            if len(full_text) > 20000:
                full_text = full_text[:20000] + "\n...[TRUNCATED]"
                
            logger.info(f"Successfully extracted {len(full_text)} characters from {page_count} pages of PDF at {url}")
            
            return {
                "url": url,
                "title": title,
                "pages": page_count,
                "content": full_text
            }
            
        except Exception as e:
            logger.error(f"Failed to parse or extract PDF content: {e}")
            return default_return
