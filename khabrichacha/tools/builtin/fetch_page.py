import re
from typing import Dict, Any, List
from khabrichacha.tools.base import BaseTool
from loguru import logger

# Below this many extracted characters, the static fetch is treated as
# "probably a JS shell" and worth retrying with a real headless browser.
# Most JS-rendered SPA/dashboard pages return a near-empty <body> to a
# plain requests.get() — a few hundred characters of nav/boilerplate text
# at most — while actual articles/pages are almost always well over this.
_MIN_USEFUL_CHARS = 500


def _run_playwright_fetch_in_subprocess(url: str, result_queue) -> None:
    """
    Runs entirely inside a separate, throwaway OS process (spawned by
    FetchPageTool._fetch_rendered via multiprocessing) — never in the
    same process/thread as the main NiceGUI/Uvicorn application. Must be
    a plain module-level function (not a method) so it can be pickled
    and re-imported by the 'spawn' start method, including on Windows.

    Puts ("ok", result_dict) or ("error", message) onto `result_queue`.
    Any exception here — including a hard crash of this process — is
    fully contained to this child process and cannot affect the parent
    application; see the isolation rationale in _fetch_rendered's
    docstring.
    """
    try:
        from playwright.sync_api import sync_playwright

        try:
            has_readability = True
            import readability  # noqa: F401
        except ImportError:
            has_readability = False

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                page.set_default_timeout(20000)
                page.goto(url, wait_until="networkidle")
                html_content = page.content()
            finally:
                browser.close()

        result = FetchPageTool._extract_from_html(url, html_content, has_readability)
        result_queue.put(("ok", result))
    except Exception as e:
        try:
            result_queue.put(("error", str(e)))
        except Exception:
            # If even putting the error on the queue fails (e.g. the
            # queue/pipe itself is broken), there's nothing more this
            # process can safely do -- it will simply exit, and the
            # parent's process.exitcode / queue-timeout checks handle
            # that case too.
            pass


class FetchPageTool(BaseTool):
    """
    Download a webpage and extract the clean readable article text.

    Uses a plain HTTP GET + readability/BeautifulSoup first (fast, no extra
    dependencies at runtime). If that comes back too thin — the classic
    sign of a JavaScript-rendered page that never sends its real content in
    the initial HTML — it retries with a headless Chromium browser via
    Playwright, which actually executes the page's JavaScript before
    reading the text. This is what turns a static scraper into something
    closer to a real browsing agent: it can read modern JS-heavy stats
    dashboards and interactive pages that a plain HTTP GET cannot.

    Playwright + its Chromium binary are already installed by
    colab_utils.py / deployment/launchers/install_colab.py — this was
    previously unused dead weight in the install; this is what wires it in.
    """

    @property
    def name(self) -> str:
        return "fetch_page"

    @property
    def description(self) -> str:
        return "Download a webpage (rendering JavaScript if needed) and extract the clean readable article text."

    @property
    def category(self) -> str:
        return "browser"

    @property
    def version(self) -> str:
        return "1.1"

    @property
    def inputs(self) -> List[str]:
        return ["url"]

    @property
    def outputs(self) -> List[str]:
        return ["url", "title", "content", "rendered"]

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
        Falls back to a real headless browser (Playwright) if the static
        fetch comes back suspiciously thin.
        """
        logger.info(f"Fetching page from URL: '{url}'")

        result = self._fetch_static(url)

        if len(result.get("content", "")) < _MIN_USEFUL_CHARS:
            logger.info(
                f"Static fetch of '{url}' returned only "
                f"{len(result.get('content', ''))} chars — retrying with a "
                f"headless browser in case this page needs JavaScript."
            )
            rendered = self._fetch_rendered(url)
            if rendered is not None and len(rendered.get("content", "")) > len(result.get("content", "")):
                rendered["rendered"] = True
                return rendered

        result.setdefault("rendered", False)
        return result

    # ── Static (fast) path ────────────────────────────────────

    def _fetch_static(self, url: str) -> Dict[str, str]:
        default_return = {"url": url, "title": "", "content": "", "rendered": False}

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

        return self._extract_from_html(url, html_content, has_readability)

    # ── Rendered (Playwright) path ────────────────────────────

    def _fetch_rendered(self, url: str) -> "Dict[str, str] | None":
        """
        Renders `url` with a headless browser, but does so in a fully
        separate OS process rather than calling Playwright's sync API
        directly in the calling thread.

        This tool is invoked from a background thread of a NiceGUI/
        Uvicorn app (via `run.io_bound`), whose main thread runs an
        asyncio event loop. Playwright's sync API is explicitly not
        meant to be used alongside an active asyncio loop, and on
        Windows in particular, the interaction between Playwright's own
        subprocess management (its Node-based driver + the Chromium
        process) and the asyncio ProactorEventLoop's child-process
        watching can be unstable -- reports include the whole host
        process terminating unexpectedly when the browser subprocess
        closes. Isolating the Playwright call in its own process means
        that whatever goes wrong there (a crash, a hang, an OS signal)
        is contained to that throwaway process and can never propagate
        up to kill the main application, regardless of the precise
        underlying mechanism.
        """
        try:
            import playwright  # noqa: F401
        except ImportError:
            logger.warning(
                "Playwright is not installed — cannot render JavaScript-heavy pages. "
                "Install with `pip install playwright && playwright install chromium`."
            )
            return None

        import multiprocessing

        # Force "spawn" on every platform (not just Windows, where it's
        # the only option anyway) so the child process always starts as a
        # genuinely fresh interpreter with no inherited event-loop/thread
        # state from the parent -- "fork" on Linux/Mac would duplicate the
        # parent's live asyncio loop and thread state into the child,
        # which risks reintroducing a milder version of the same class of
        # problem this isolation exists to avoid.
        ctx = multiprocessing.get_context("spawn")
        result_queue = ctx.Queue()
        process = ctx.Process(
            target=_run_playwright_fetch_in_subprocess,
            args=(url, result_queue),
            daemon=True,
        )

        try:
            process.start()
        except Exception as e:
            logger.error(f"Failed to start isolated Playwright process for '{url}': {e}")
            return None

        process.join(timeout=35)

        if process.is_alive():
            logger.warning(f"Playwright render of '{url}' timed out after 35s; terminating isolated process.")
            process.terminate()
            process.join(timeout=5)
            if process.is_alive():
                process.kill()
            return None

        if process.exitcode != 0:
            logger.error(
                f"Isolated Playwright process for '{url}' exited abnormally "
                f"(code {process.exitcode}) -- this is exactly the kind of failure "
                f"this isolation exists to contain; the main app is unaffected."
            )
            return None

        try:
            status, payload = result_queue.get(timeout=5)
        except Exception:
            logger.error(f"Isolated Playwright process for '{url}' produced no result.")
            return None

        if status == "error":
            logger.error(f"Playwright render of '{url}' failed inside the isolated process: {payload}")
            return None

        return payload

    # ── Shared HTML → clean text extraction ───────────────────

    @staticmethod
    def _extract_from_html(url: str, html_content: str, has_readability: bool) -> Dict[str, str]:
        from bs4 import BeautifulSoup

        title = ""
        extracted_html = html_content

        if has_readability:
            try:
                from readability import Document
                doc = Document(html_content)
                title = doc.short_title()
                extracted_html = doc.summary()
            except Exception as e:
                logger.error(f"Readability parsing failed: {e}. Falling back to BeautifulSoup.")
                extracted_html = html_content

        try:
            soup = BeautifulSoup(extracted_html, "html.parser")

            if not title:
                title_tag = soup.find("title")
                if title_tag:
                    title = title_tag.get_text(strip=True)

            # Capture raw <table> HTML BEFORE stripping tags below --
            # soup.get_text() discards all table structure entirely
            # (headers/rows collapse into unstructured lines of text with
            # no delimiters), which meant StructuredExtractor -- which
            # only recognizes literal "<table" markup or markdown-style
            # "|...|" pipes -- could never actually find a real table from
            # any page fetched through this tool, even when the source
            # page (e.g. a Wikipedia infobox/stats table) genuinely had
            # one. Keeping a few of the largest tables as raw HTML gives
            # the structured-extraction path something real to work with.
            tables_html: List[str] = []
            try:
                found_tables = soup.find_all("table")
                found_tables = sorted(found_tables, key=lambda t: len(t.find_all("tr")), reverse=True)
                for t in found_tables[:3]:
                    if len(t.find_all("tr")) >= 2:  # skip trivial/layout-only tables
                        html_str = str(t)
                        tables_html.append(html_str[:20000])
            except Exception as e:
                logger.warning(f"Table extraction from '{url}' failed: {e}")

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

            result = {"url": url, "title": title, "content": clean_text, "rendered": False}
            if tables_html:
                result["tables_html"] = tables_html
            return result

        except Exception as e:
            logger.error(f"Error during BeautifulSoup parsing/cleanup: {e}")
            return {"url": url, "title": "", "content": "", "rendered": False}
