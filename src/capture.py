"""Capture page data via Playwright — single JS evaluation pass.

All DOM measurement happens in one page.evaluate() call while the page is live.
Returns a CapturedPage with absolute document coordinates for every element.
"""

from __future__ import annotations

import asyncio
from playwright.async_api import async_playwright

from .models import CapturedPage, ImageData


# JavaScript that runs inside the browser to extract all page data.
# Returns a JSON-serializable dict with absolute document coordinates.
CAPTURE_JS = """
(() => {
    const VH = window.innerHeight;
    const scrollY = window.scrollY;

    function docRect(el) {
        const r = el.getBoundingClientRect();
        return { x: r.left, y: r.top + window.scrollY, w: r.width, h: r.height };
    }

    function isVisible(el) {
        if (!el.checkVisibility) return el.offsetParent !== null;
        return el.checkVisibility({ opacityProperty: true, visibilityProperty: true });
    }

    function getAncestorClasses(el) {
        const classes = [];
        let current = el;
        while (current && current !== document.body) {
            if (current.className && typeof current.className === 'string') {
                for (const c of current.className.split(/\\s+/)) {
                    if (c) classes.push(c.toLowerCase());
                }
            }
            current = current.parentElement;
        }
        return classes;
    }

    function contextText(el, chars) {
        // Get surrounding text from parent's text content
        const parent = el.closest('p, div, section, article, li, td');
        if (!parent) return '';
        const text = (parent.textContent || '').replace(/\\s+/g, ' ').trim();
        return text.slice(0, chars || 100);
    }

    // --- Capture all <img> elements ---
    const images = [];
    const seenSrcs = new Set();
    const imgs = document.querySelectorAll('img');
    for (const img of imgs) {
        const src = img.currentSrc || img.src || '';
        if (!src || seenSrcs.has(src)) continue;
        seenSrcs.add(src);

        const rect = docRect(img);
        images.push({
            src,
            alt: img.hasAttribute('alt') ? img.alt : null,
            loading: img.loading || null,
            fetchpriority: img.fetchPriority || null,
            has_dim_attrs: img.hasAttribute('width') && img.hasAttribute('height'),
            ancestor_classes: getAncestorClasses(img),
            x: rect.x, y: rect.y, width: rect.w, height: rect.h,
            visible: isVisible(img),
            source_type: 'img',
            context_text: contextText(img, 100),
        });

        // If this <img> is inside a <picture>, also capture the <picture>'s sources
        const picture = img.closest('picture');
        if (picture) {
            const sources = picture.querySelectorAll('source');
            for (const srcEl of sources) {
                const srcsetVal = srcEl.srcset || '';
                if (!srcsetVal) continue;
                // Extract first URL from srcset
                const firstUrl = srcsetVal.split(',')[0]?.trim()?.split(' ')[0] || '';
                if (firstUrl && !seenSrcs.has(firstUrl)) {
                    seenSrcs.add(firstUrl);
                    const srect = docRect(picture);
                    images.push({
                        src: firstUrl,
                        alt: img.hasAttribute('alt') ? img.alt : null,
                        loading: null,
                        fetchpriority: null,
                        has_dim_attrs: false,
                        ancestor_classes: getAncestorClasses(picture),
                        x: srect.x, y: srect.y, width: srect.w, height: srect.h,
                        visible: isVisible(picture),
                        source_type: 'picture',
                        context_text: contextText(picture, 100),
                    });
                }
            }
        }
    }

    // --- Capture CSS background-images ---
    const allEls = document.querySelectorAll('*');
    for (const el of allEls) {
        const bg = getComputedStyle(el).backgroundImage;
        if (!bg || bg === 'none') continue;
        const match = bg.match(/url\\(["']?([^"')]+)["']?\\)/);
        if (!match) continue;
        const url = match[1];
        if (seenSrcs.has(url)) continue;
        seenSrcs.add(url);

        const rect = docRect(el);
        // Only capture if element has meaningful size (>50px in either dimension)
        if (rect.w < 50 && rect.h < 50) continue;

        images.push({
            src: url,
            alt: null,
            loading: null,
            fetchpriority: null,
            has_dim_attrs: false,
            ancestor_classes: getAncestorClasses(el),
            x: rect.x, y: rect.y, width: rect.w, height: rect.h,
            visible: isVisible(el),
            source_type: 'css-bg',
            context_text: contextText(el, 100),
        });
    }

    // --- Capture heading, tables, CTAs ---
    const h1 = document.querySelector('h1');
    const h1Data = h1 ? { ...docRect(h1), text: (h1.textContent || '').trim() } : null;

    const tables = [];
    for (const t of document.querySelectorAll('table, [class*="comparison"], [class*="product-card"], [class*="product-grid"]')) {
        if (isVisible(t)) tables.push(docRect(t));
    }

    const ctas = [];
    for (const a of document.querySelectorAll('a[href*="viator"], a[href*="partner"], a[href*="affiliate"], a[class*="cta"], a[class*="button"], a.btn')) {
        if (isVisible(a)) {
            ctas.push({ ...docRect(a), href: a.href });
        }
    }

    // --- Page text for classification ---
    const bodyText = (document.body.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 5000);

    return {
        title: document.title,
        page_text: bodyText,
        images,
        h1_rect: h1Data,
        tables,
        ctas,
        viewport_height: VH,
        scroll_y: scrollY,
    };
})()
"""


async def capture(url: str, viewport: str = "1280x720") -> CapturedPage:
    """Capture a single page: navigate, render, extract all data.

    Returns CapturedPage with status="ok" on success, or status="blocked"/"timeout"/"error".
    """
    vp_w, vp_h = map(int, viewport.split("x"))

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": vp_w, "height": vp_h})

            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Detect blocked pages
                if response is None:
                    return CapturedPage(
                        url=url, title="", status="blocked",
                        error="No response (navigation failed)",
                        viewport=viewport, page_text="", images=[],
                        h1_rect=None, tables=[], ctas=[],
                        viewport_height=vp_h, scroll_y=0,
                    )

                status_code = response.status
                if status_code in (403, 503):
                    return CapturedPage(
                        url=url, title=await page.title(), status="blocked",
                        error=f"HTTP {status_code}",
                        viewport=viewport, page_text="", images=[],
                        h1_rect=None, tables=[], ctas=[],
                        viewport_height=vp_h, scroll_y=0,
                    )

                # Detect Cloudflare challenge
                content = await page.content()
                if "cf-challenge" in content.lower() or "checking your browser" in content.lower():
                    return CapturedPage(
                        url=url, title=await page.title(), status="blocked",
                        error="Cloudflare challenge detected",
                        viewport=viewport, page_text="", images=[],
                        h1_rect=None, tables=[], ctas=[],
                        viewport_height=vp_h, scroll_y=0,
                    )

                # Scroll to trigger lazy images
                for _ in range(3):
                    await page.evaluate(f"window.scrollBy(0, {vp_h})")
                    await asyncio.sleep(0.5)

                # Wait for lazy-loaded images
                await asyncio.sleep(2)

                # Scroll back to top for consistent document coordinates
                await page.evaluate("window.scrollTo(0, 0)")
                await asyncio.sleep(0.3)

                # Capture all data in one evaluate pass
                raw = await page.evaluate(CAPTURE_JS)

                # Build ImageData list with dedup (keep largest by area)
                images = _dedup_images(raw.get("images", []))

                return CapturedPage(
                    url=url,
                    title=raw.get("title", ""),
                    status="ok",
                    error=None,
                    viewport=viewport,
                    page_text=raw.get("page_text", ""),
                    images=images,
                    h1_rect=raw.get("h1_rect"),
                    tables=raw.get("tables", []),
                    ctas=raw.get("ctas", []),
                    viewport_height=vp_h,
                    scroll_y=raw.get("scroll_y", 0),
                )

            except asyncio.TimeoutError:
                return CapturedPage(
                    url=url, title="", status="timeout",
                    error="Page load timed out after 30s",
                    viewport=viewport, page_text="", images=[],
                    h1_rect=None, tables=[], ctas=[],
                    viewport_height=vp_h, scroll_y=0,
                )
            finally:
                await browser.close()

    except Exception as e:
        return CapturedPage(
            url=url, title="", status="error",
            error=str(e),
            viewport=viewport, page_text="", images=[],
            h1_rect=None, tables=[], ctas=[],
            viewport_height=vp_h, scroll_y=0,
        )


def _dedup_images(raw_images: list[dict]) -> list[ImageData]:
    """Deduplicate images by src, keeping the largest-area instance.

    For <picture>+<img> pairs, merge attributes from the real <img> into the kept instance.
    """
    by_src: dict[str, ImageData] = {}

    for r in raw_images:
        src = r.get("src", "")
        if not src:
            continue

        img = ImageData(
            src=src,
            alt=r.get("alt"),
            loading=r.get("loading"),
            fetchpriority=r.get("fetchpriority"),
            has_dim_attrs=r.get("has_dim_attrs", False),
            ancestor_classes=r.get("ancestor_classes", []),
            x=r.get("x", 0),
            y=r.get("y", 0),
            width=r.get("width", 0),
            height=r.get("height", 0),
            visible=r.get("visible", True),
            source_type=r.get("source_type", "img"),
            context_text=r.get("context_text", ""),
        )

        existing = by_src.get(src)
        if existing is None:
            by_src[src] = img
        else:
            # Keep larger image, merge attributes from real <img>
            existing_area = existing.width * existing.height
            new_area = img.width * img.height
            if new_area > existing_area:
                # New is larger — keep it but merge attrs from existing
                if existing.source_type == "img" and img.source_type != "img":
                    img.loading = img.loading or existing.loading
                    img.fetchpriority = img.fetchpriority or existing.fetchpriority
                    img.has_dim_attrs = img.has_dim_attrs or existing.has_dim_attrs
                    img.alt = img.alt if img.alt is not None else existing.alt
                by_src[src] = img
            else:
                # Existing is larger — merge attrs from new if new is the real <img>
                if img.source_type == "img" and existing.source_type != "img":
                    existing.loading = existing.loading or img.loading
                    existing.fetchpriority = existing.fetchpriority or img.fetchpriority
                    existing.has_dim_attrs = existing.has_dim_attrs or img.has_dim_attrs
                    existing.alt = existing.alt if existing.alt is not None else img.alt

    return list(by_src.values())
