"""Facebook comment scraping. Anchors on ARIA roles (stable across Facebook's
frequent front-end rebuilds) rather than obfuscated/atomic CSS class names."""
import logging
import re
from typing import Callable

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from config import MAX_TOTAL_ROUNDS, NAVIGATION_TIMEOUT_MS, SCROLL_WAIT_MS, STALE_ROUNDS_LIMIT

logger = logging.getLogger(__name__)

ARTICLE_SELECTOR = 'div[role="article"]'
CLICKABLE_SELECTOR = 'div[role="button"], span[role="button"]'

# Bilingual (English/Thai) secondary heuristic — Facebook's UI language depends on
# the logged-in account's locale, and these structural roles alone can't fully
# disambiguate "load more comments" from unrelated buttons.
VIEW_MORE_PATTERNS = [
    re.compile(r"view\s+\d*\s*more\s+comments?", re.I),
    re.compile(r"view\s+\d*\s*more\s+repl(y|ies)", re.I),
    re.compile(r"^\d+\s+repl(y|ies)$", re.I),
    re.compile(r"ดูความคิดเห็นเพิ่มเติม"),
    re.compile(r"ดู.*ความคิดเห็นเพิ่มเติม"),
    re.compile(r"ดูการตอบกลับ"),
    re.compile(r"^\d+\s*การตอบกลับ"),
]

COMMENT_COUNT_PATTERN = re.compile(r"([\d,]+)\s*(comments?|ความคิดเห็น)", re.I)

LOGIN_URL_MARKERS = ("/login", "/checkpoint")


class PostNotFoundError(Exception):
    """The Facebook post could not be loaded or located."""


class FacebookCommentScraper:
    def __init__(self, page: Page, progress_callback: Callable[[int], None] | None = None):
        self.page = page
        self.progress_callback = progress_callback or (lambda count: None)

    def navigate_to_post(self, post_url: str) -> None:
        try:
            self.page.goto(post_url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        except PlaywrightTimeoutError as exc:
            raise PostNotFoundError(f"Navigation timed out: {exc}") from exc

        if any(marker in self.page.url for marker in LOGIN_URL_MARKERS):
            raise PostNotFoundError("Redirected to login/checkpoint — session invalid")

        try:
            self.page.locator(ARTICLE_SELECTOR).first.wait_for(
                state="attached", timeout=NAVIGATION_TIMEOUT_MS
            )
        except PlaywrightTimeoutError as exc:
            raise PostNotFoundError(f"No comment content found on page: {exc}") from exc

    def get_total_comment_count(self) -> int | None:
        """Best-effort only — not load-bearing for correctness, just for the
        progress display, since Facebook doesn't reliably expose this value."""
        try:
            text_locator = self.page.get_by_text(COMMENT_COUNT_PATTERN).first
            text = text_locator.inner_text(timeout=3000)
        except PlaywrightTimeoutError:
            return None
        match = COMMENT_COUNT_PATTERN.search(text)
        if not match:
            return None
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            return None

    # JS patterns mirror VIEW_MORE_PATTERNS — kept in sync manually if patterns change.
    # Uses textContent (not innerText) so we never force a layout reflow while
    # iterating potentially hundreds of role="button" nodes on a busy Facebook page.
    _JS_FIND_EXPAND_BUTTON = """() => {
        const patterns = [
            /view\\s+\\d*\\s*more\\s+comments?/i,
            /view\\s+\\d*\\s*more\\s+repl(?:y|ies)/i,
            /^\\d+\\s+repl(?:y|ies)$/i,
            /\\u0e14\\u0e39\\u0e04\\u0e27\\u0e32\\u0e21\\u0e04\\u0e34\\u0e14\\u0e40\\u0e2b\\u0e47\\u0e19\\u0e40\\u0e1e\\u0e34\\u0e48\\u0e21\\u0e40\\u0e15\\u0e34\\u0e21/,
            /\\u0e14\\u0e39.*\\u0e04\\u0e27\\u0e32\\u0e21\\u0e04\\u0e34\\u0e14\\u0e40\\u0e2b\\u0e47\\u0e19\\u0e40\\u0e1e\\u0e34\\u0e48\\u0e21\\u0e40\\u0e15\\u0e34\\u0e21/,
            /\\u0e14\\u0e39\\u0e01\\u0e32\\u0e23\\u0e15\\u0e2d\\u0e1a\\u0e01\\u0e25\\u0e31\\u0e1a/,
            /^\\d+\\s*\\u0e01\\u0e32\\u0e23\\u0e15\\u0e2d\\u0e1a\\u0e01\\u0e25\\u0e31\\u0e1a/,
        ];
        const els = document.querySelectorAll('div[role="button"], span[role="button"]');
        for (const el of els) {
            if (!el.offsetParent) continue;
            const text = (el.textContent || '').trim();
            if (text && text.length <= 60 && patterns.some(p => p.test(text))) return el;
        }
        return null;
    }"""

    # Clicks the button entirely in JS to avoid Playwright per-element round-trips
    # and scroll_into_view timeouts that added 1-3 s per expand attempt.
    _JS_CLICK_ELEMENT = "(el) => el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}))"

    def _click_all_visible_expand_buttons(self) -> bool:
        """Find and click expand buttons via a single JS DOM query per attempt."""
        clicked_any = False
        for _ in range(50):
            try:
                handle = self.page.evaluate_handle(self._JS_FIND_EXPAND_BUTTON)
                el = handle.as_element()
                if el is None:
                    break
                self.page.evaluate(self._JS_CLICK_ELEMENT, el)
                clicked_any = True
                self.page.wait_for_timeout(80)
            except Exception as exc:
                logger.debug("Expand-button click failed: %s", exc)
                break
        return clicked_any

    def expand_all_comments(self) -> None:
        stale_rounds = 0
        last_count = 0

        for round_num in range(MAX_TOTAL_ROUNDS):
            clicked_any = self._click_all_visible_expand_buttons()
            # Use mouse.wheel (not window.scrollTo) — Facebook renders comments
            # inside a scrollable container, not the document body, so only
            # dispatching a real wheel event triggers its IntersectionObserver
            # lazy-load.  Large delta covers more of the thread per round.
            self.page.mouse.wheel(0, 8000)
            # Avoid networkidle: Facebook keeps long-lived connections open
            # (chat/presence) so networkidle rarely resolves and would hang.
            self.page.wait_for_timeout(SCROLL_WAIT_MS)

            current_count = self.page.locator(ARTICLE_SELECTOR).count()
            self.progress_callback(current_count)

            if current_count <= last_count and not clicked_any:
                stale_rounds += 1
            else:
                stale_rounds = 0
            last_count = current_count

            logger.debug("Round %d: %d comments, stale_rounds=%d", round_num, current_count, stale_rounds)

            if stale_rounds >= STALE_ROUNDS_LIMIT:
                break

    def extract_raw_comments(self) -> list[dict]:
        """Returns a list of {facebook_name, raw_comment, comment_timestamp} dicts.
        Reads all articles in a single JS evaluate call instead of per-element round-trips."""
        try:
            return self.page.evaluate("""() => {
                const articles = document.querySelectorAll('div[role="article"]');
                const results = [];
                for (const article of articles) {
                    const lines = (article.innerText || '').split('\\n').filter(l => l.trim());
                    if (!lines.length) continue;
                    const facebook_name = lines[0].trim();
                    const raw_comment = lines.slice(1).join('\\n').trim();
                    const abbr = article.querySelector('a[role="link"] abbr');
                    const comment_timestamp = abbr ? (abbr.getAttribute('title') || '') : '';
                    results.push({ facebook_name, raw_comment, comment_timestamp });
                }
                return results;
            }""")
        except Exception as exc:
            logger.warning("Batch comment extract failed, falling back: %s", exc)
            return self._extract_raw_comments_fallback()

    def _extract_raw_comments_fallback(self) -> list[dict]:
        results = []
        articles = self.page.locator(ARTICLE_SELECTOR)
        count = articles.count()
        for i in range(count):
            article = articles.nth(i)
            try:
                text = article.inner_text(timeout=2000)
            except Exception as exc:
                logger.debug("Could not read comment #%d: %s", i, exc)
                continue
            lines = [line for line in text.split("\n") if line.strip()]
            if not lines:
                continue
            facebook_name = lines[0].strip()
            raw_comment = "\n".join(lines[1:]).strip()
            timestamp = ""
            try:
                timestamp = article.locator('a[role="link"] abbr').first.get_attribute(
                    "title", timeout=500
                ) or ""
            except Exception:
                pass
            results.append({
                "facebook_name": facebook_name,
                "raw_comment": raw_comment,
                "comment_timestamp": timestamp,
            })
        return results
