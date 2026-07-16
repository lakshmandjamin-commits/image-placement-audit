"""Page type classifier.

Classifies pages into 4 types based on Hypatia's research:
- comparison: multiple products + comparison language
- destination-guide: location name + guide keywords
- review: single product + rating/verdict
- blog: default catch-all
"""

from __future__ import annotations

import re
from .models import CapturedPage


# Signals for each page type
COMPARISON_KEYWORDS = {
    "vs", "versus", "compared", "better than", "best", "top", "ranking",
    "pick", "choice", "winner", "runner-up", "alternative", "instead of",
    "or", "difference between", "which is better",
}

GUIDE_KEYWORDS = {
    "things to do", "attractions", "where to stay", "visitor guide",
    "travel guide", "what to see", "places to visit", "getting around",
    "when to visit", "best time to", "how to get", "where to eat",
    "guide to", "visiting", "explore", "destination", "trip to",
}

REVIEW_KEYWORDS = {
    "review", "verdict", "rating", "score", "our take", "bottom line",
    "conclusion", "recommendation", "pros and cons", "what we think",
    "would i recommend", "is it worth",
}


def classify(page: CapturedPage) -> str:
    """Classify a captured page into one of 4 types.

    Tie-break order: comparison > review > destination-guide > blog
    """
    text = page.page_text.lower()
    tables = page.tables or []
    images = page.images or []

    # Check comparison first (strongest signal: tables + keywords)
    comparison_score = 0
    if len(tables) > 0 or _has_product_cards(text):
        comparison_score += 3
    comparison_score += _keyword_hits(text, COMPARISON_KEYWORDS)
    if _has_multiple_products(text, images):
        comparison_score += 2

    if comparison_score >= 4:
        return "comparison"

    # Check review
    review_score = 0
    if _has_rating_element(text):
        review_score += 3
    review_score += _keyword_hits(text, REVIEW_KEYWORDS)
    if _has_verdict_section(text):
        review_score += 2

    if review_score >= 3:
        return "review"

    # Check destination-guide
    guide_score = 0
    if page.h1_rect and _is_location_heading(page.h1_rect.get("text", "")):
        guide_score += 3
    guide_score += _keyword_hits(text, GUIDE_KEYWORDS)

    if guide_score >= 3:
        return "destination-guide"

    return "blog"


def _keyword_hits(text: str, keywords: set[str]) -> int:
    """Count how many keywords appear in text."""
    return sum(1 for kw in keywords if kw in text)


def _has_product_cards(text: str) -> bool:
    """Detect product card / comparison card patterns."""
    patterns = [
        r"product.card", r"comparison.card", r"price.*\$", r"\$\d+",
    ]
    return any(re.search(p, text) for p in patterns)


def _has_multiple_products(text: str, images: list) -> bool:
    """Check if page discusses multiple products/tours."""
    # Count Viator-style product codes or numbered items
    codes = len(re.findall(r"\d{4,}[A-Z]+P\d+", text))
    if codes >= 2:
        return True
    # Count numbered list items that look like products
    numbered = len(re.findall(r"\b\d+\.\s+\w{3,}", text))
    return numbered >= 3


def _has_rating_element(text: str) -> bool:
    """Detect rating/score patterns."""
    patterns = [
        r"\d+\.?\d*\s*/\s*5", r"\d+\.?\d*\s*out of\s*5",
        r"\d+\.?\d*\s*/\s*10", r"rating.*\d+\.?\d*",
        r"score.*\d+\.?\d*", r"\b\d+\.\d+\s*stars?\b",
    ]
    return any(re.search(p, text) for p in patterns)


def _has_verdict_section(text: str) -> bool:
    """Detect verdict/conclusion section."""
    patterns = [
        r"verdict", r"conclusion", r"bottom line", r"final thought",
        r"our take", r"should you", r"is it worth",
    ]
    return any(re.search(p, text) for p in patterns)


def _is_location_heading(h1_text: str) -> bool:
    """Check if H1 looks like a location name (city, region, country)."""
    # Contains a place-like word or pattern
    location_patterns = [
        r"guide to", r"visiting", r"things to do in", r"travel",
        r"trip to", r"vacation", r"holiday", r"bucket list",
        r"destination", r"city", r"island", r"beach", r"mountain",
    ]
    return any(re.search(p, h1_text.lower()) for p in location_patterns)
