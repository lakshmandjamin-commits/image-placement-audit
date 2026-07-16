"""Tests for rule engine."""
from src.models import CapturedPage, ImageData
from src.rules import check_all, check_R1, check_R5, check_R6, check_R9, check_R10, check_R11, check_R12, _hero_image


def _img(src: str = "img.jpg", **kwargs) -> ImageData:
    """Helper to build ImageData with sensible defaults."""
    defaults = {
        "src": src, "alt": "", "loading": None, "fetchpriority": None,
        "has_dim_attrs": True, "ancestor_classes": [],
        "x": 0, "y": 0, "width": 800, "height": 600,
        "visible": True, "source_type": "img", "context_text": "",
    }
    defaults.update(kwargs)
    return ImageData(**defaults)


def _page(images=None, h1_rect=None, tables=None, ctas=None, page_type="blog", **kwargs):
    """Helper to build a CapturedPage."""
    defaults = {
        "url": "https://example.com/test", "title": "Test", "status": "ok",
        "error": None, "viewport": "1280x720", "page_text": "",
        "images": images or [], "h1_rect": h1_rect,
        "tables": tables or [], "ctas": ctas or [],
        "viewport_height": 720, "scroll_y": 0,
    }
    defaults.update(kwargs)
    return CapturedPage(**defaults)


class TestHeroImage:
    def test_largest_above_fold(self):
        images = [
            _img("small.jpg", width=200, height=150, y=100),
            _img("hero.jpg", width=1200, height=800, y=50),
            _img("below.jpg", width=900, height=600, y=800),
        ]
        hero = _hero_image(images)
        assert hero is not None
        assert hero.src == "hero.jpg"

    def test_none_when_no_above_fold(self):
        images = [_img("below.jpg", y=800), _img("also_below.jpg", y=1000)]
        assert _hero_image(images) is None


class TestR1:
    def test_flags_hero_above_table(self):
        page = _page(
            images=[_img("hero.jpg", y=100, width=1200, height=800)],
            tables=[{"x": 0, "y": 500, "w": 800, "h": 300}],
            h1_rect={"x": 0, "y": 50, "w": 800, "h": 40, "text": "Test"},
            page_type="comparison",
        )
        violations = check_R1(page, "comparison")
        assert len(violations) == 1
        assert violations[0].rule_id == "R1"
        assert violations[0].severity == "critical"

    def test_skips_when_hero_below_table(self):
        page = _page(
            images=[_img("hero.jpg", y=600)],
            tables=[{"x": 0, "y": 500, "w": 800, "h": 300}],
            h1_rect={"x": 0, "y": 50, "w": 800, "h": 40, "text": "Test"},
            page_type="comparison",
        )
        assert check_R1(page, "comparison") == []

    def test_skips_non_comparison(self):
        page = _page(page_type="blog", images=[_img()], tables=[{"x": 0, "y": 500, "w": 800, "h": 300}], h1_rect={"x": 0, "y": 50, "w": 800, "h": 40, "text": "Test"})
        assert check_R1(page, "blog") == []

    def test_skips_when_no_tables(self):
        page = _page(page_type="comparison", images=[_img()], h1_rect={"x": 0, "y": 50, "w": 800, "h": 40, "text": "Test"})
        assert check_R1(page, "comparison") == []


class TestR5:
    def test_flags_carousel(self):
        images = [
            _img("a.jpg", ancestor_classes=["carousel", "hero"]),
            _img("b.jpg", ancestor_classes=["carousel"]),
            _img("c.jpg", ancestor_classes=["carousel", "slide"]),
        ]
        page = _page(images=images)
        violations = check_R5(page, "blog")
        assert len(violations) == 1
        assert violations[0].rule_id == "R5"

    def test_skips_fewer_than_three(self):
        images = [
            _img("a.jpg", ancestor_classes=["carousel"]),
            _img("b.jpg", ancestor_classes=["carousel"]),
        ]
        page = _page(images=images)
        assert check_R5(page, "blog") == []


class TestR6:
    def test_flags_missing_alt(self):
        page = _page(images=[_img("a.jpg", alt=None, source_type="img")])
        violations = check_R6(page, "blog")
        assert len(violations) == 1

    def test_allows_empty_alt(self):
        page = _page(images=[_img("a.jpg", alt="", source_type="img")])
        assert check_R6(page, "blog") == []

    def test_skips_css_bg(self):
        page = _page(images=[_img("bg.jpg", alt=None, source_type="css-bg")])
        assert check_R6(page, "blog") == []


class TestR9:
    def test_flags_missing_dims(self):
        page = _page(images=[_img("a.jpg", has_dim_attrs=False)])
        violations = check_R9(page, "blog")
        assert len(violations) == 1

    def test_passes_with_dims(self):
        page = _page(images=[_img("a.jpg", has_dim_attrs=True)])
        assert check_R9(page, "blog") == []


class TestR10:
    def test_flags_lazy_above_fold(self):
        page = _page(images=[_img("hero.jpg", y=100, loading="lazy", fetchpriority=None, source_type="img")])
        violations = check_R10(page, "blog")
        assert len(violations) == 1

    def test_passes_eager_above_fold(self):
        page = _page(images=[_img("hero.jpg", y=100, loading="eager", source_type="img")])
        assert check_R10(page, "blog") == []

    def test_passes_with_fetchpriority_high(self):
        page = _page(images=[_img("hero.jpg", y=100, loading="lazy", fetchpriority="high", source_type="img")])
        assert check_R10(page, "blog") == []

    def test_skips_css_bg(self):
        page = _page(images=[_img("bg.jpg", y=100, loading="lazy", source_type="css-bg")])
        assert check_R10(page, "blog") == []


class TestR11:
    def test_flags_no_large_image(self):
        page = _page(images=[_img("small.jpg", width=800)])
        violations = check_R11(page, "blog")
        assert len(violations) == 1

    def test_passes_with_large_image(self):
        page = _page(images=[_img("big.jpg", width=1600)])
        assert check_R11(page, "blog") == []


class TestCheckAll:
    def test_runs_all_rules(self):
        page = _page(
            images=[_img("hero.jpg", y=100, alt=None, has_dim_attrs=False, loading="lazy", width=200, height=150)],
            page_type="blog",
        )
        violations = check_all(page, "blog")
        # Should fire: R6 (missing alt), R8 (small), R9 (no dims), R10 (lazy above fold)
        assert len(violations) >= 4


class TestR12:
    """R12: Zero images on non-blog pages."""

    def test_flags_comparison_page_with_no_images(self):
        page = _page(images=[], page_type="comparison")
        violations = check_R12(page, "comparison")
        assert len(violations) == 1
        assert violations[0].rule_id == "R12"
        assert violations[0].severity == "critical"
        assert "zero images" in violations[0].description.lower()

    def test_flags_destination_guide_with_no_images(self):
        page = _page(images=[], page_type="destination-guide")
        violations = check_R12(page, "destination-guide")
        assert len(violations) == 1

    def test_flags_review_with_no_images(self):
        page = _page(images=[], page_type="review")
        violations = check_R12(page, "review")
        assert len(violations) == 1

    def test_skips_blog_with_no_images(self):
        """Blog pages can legitimately have no images."""
        page = _page(images=[], page_type="blog")
        violations = check_R12(page, "blog")
        assert len(violations) == 0

    def test_passes_when_images_exist(self):
        page = _page(images=[_img("hero.jpg")], page_type="comparison")
        violations = check_R12(page, "comparison")
        assert len(violations) == 0
