"""Tests for page type classifier."""
from src.models import CapturedPage
from src.classifier import classify


def _page(text: str = "", h1_text: str = "", tables: int = 0, ctas: int = 0, images: int = 3) -> CapturedPage:
    """Helper to build a minimal CapturedPage for classifier tests."""
    return CapturedPage(
        url="https://example.com/test",
        title="Test Page",
        status="ok",
        error=None,
        viewport="1280x720",
        page_text=text,
        images=[],
        h1_rect={"x": 0, "y": 100, "w": 800, "h": 40, "text": h1_text} if h1_text else None,
        tables=[{"x": 0, "y": 500, "w": 800, "h": 300}] * tables,
        ctas=[{"x": 0, "y": 900, "w": 200, "h": 40, "href": "https://viator.com/test"}] * ctas,
        viewport_height=720,
        scroll_y=0,
    )


class TestClassifier:
    def test_comparison_with_table_and_keywords(self):
        page = _page(
            text="best snorkeling tours compared to other options. Our top pick winner vs runner-up. price $50.",
            tables=1,
        )
        assert classify(page) == "comparison"

    def test_comparison_with_product_cards(self):
        page = _page(
            text="product-card top 5 picks best compared to alternatives. price $99.",
            tables=0,
        )
        assert classify(page) == "comparison"

    def test_review_with_rating(self):
        page = _page(
            text="review rating 4.5/5 our verdict bottom line conclusion recommendation. is it worth it?",
            h1_text="Sunset Cruise Review",
        )
        assert classify(page) == "review"

    def test_destination_guide_with_location(self):
        page = _page(
            text="things to do attractions where to stay visitor guide. best time to visit exploring the island.",
            h1_text="Guide to Bali",
        )
        assert classify(page) == "destination-guide"

    def test_blog_default(self):
        page = _page(text="some random article about travel experiences")
        assert classify(page) == "blog"

    def test_comparison_beats_review(self):
        page = _page(
            text="best top vs compared review rating 4.5/5 verdict conclusion. product-card price $99.",
            tables=1,
        )
        assert classify(page) == "comparison"

    def test_review_beats_guide(self):
        page = _page(
            text="review rating 4.2/5 verdict conclusion. things to do attractions.",
            h1_text="Hotel Review",
        )
        assert classify(page) == "review"

    def test_guide_beats_blog(self):
        page = _page(
            text="things to do attractions where to stay guide to visiting.",
            h1_text="Guide to Paris",
        )
        assert classify(page) == "destination-guide"

    def test_no_h1_still_classifies(self):
        page = _page(
            text="best top vs compared alternatives price $50. product-card.",
            h1_text="",
            tables=1,
        )
        assert classify(page) == "comparison"
