"""Rule engine — checks CapturedPage against Hypatia's image placement rules.

All rules use live Playwright geometry (absolute document coordinates).
Each rule is a standalone function: check_RX(page, page_type) -> list[Violation]
"""

from __future__ import annotations

from .models import CapturedPage, Violation, ImageData

# Configurable thresholds
RULES_CONFIG = {
    "VERTICAL_DISTANCE_PX": 300,    # R4: image within 300px of CTA
    "SMALL_IMAGE_PX": 300,           # R8: flag images smaller than this
    "LARGE_IMAGE_PX": 1200,          # R11: Discover needs at least one this wide
    "KNOWN_STOCK_DOMAINS": [
        "shutterstock.com", "istockphoto.com", "gettyimages.com",
        "depositphotos.com", "alamy.com", "dreamstime.com",
    ],
}


def _hero_image(images: list[ImageData], viewport_height: int = 720) -> ImageData | None:
    """Find the hero image: largest-area image within first viewport."""
    above_fold = [img for img in images if img.y < viewport_height and img.visible]
    if not above_fold:
        return None
    return max(above_fold, key=lambda img: img.width * img.height)


def _first_viewport_image(images: list[ImageData], viewport_height: int = 720) -> ImageData | None:
    """First visible image in document order within viewport."""
    viewport = sorted(
        [img for img in images if img.y < viewport_height and img.visible],
        key=lambda img: img.y,
    )
    return viewport[0] if viewport else None


def check_all(page: CapturedPage, page_type: str) -> list[Violation]:
    """Run all applicable rules against a page."""
    vh = page.viewport_height or 720
    violations = []
    for rule_func in [
        check_R1, check_R2, check_R3, check_R4, check_R5,
        check_R6, check_R7, check_R8, check_R9, check_R10, check_R11,
        check_R12,
    ]:
        violations.extend(rule_func(page, page_type, vh))
    return violations


# ── Page-type-specific rules ──

def check_R1(page: CapturedPage, page_type: str, vh: int = 720) -> list[Violation]:
    """R1: Hero above comparison table (comparison pages only)."""
    if page_type != "comparison":
        return []
    if not page.tables or page.h1_rect is None:
        return []

    hero = _hero_image(page.images, vh)
    if hero is None:
        return []

    first_table_y = min(t["y"] for t in page.tables)
    if hero.y < first_table_y:
        return [Violation(
            rule_id="R1",
            severity="critical",
            evidence_tier="T1",
            image_src=hero.src,
            description=f"Hero image (y={hero.y:.0f}) appears above comparison table (y={first_table_y:.0f}). "
                        "Evidence: hero before comparison table hurts conversion on travel affiliate pages.",
            suggestion="Move hero image below the comparison table, or replace with a smaller contextual image after the table.",
        )]
    return []


def check_R2(page: CapturedPage, page_type: str, vh: int = 720) -> list[Violation]:
    """R2: Images between H1 and first CTA (comparison pages)."""
    if page_type != "comparison":
        return []
    if not page.ctas or page.h1_rect is None:
        return []

    h1_y = page.h1_rect["y"]
    first_cta_y = min(c["y"] for c in page.ctas)
    violations = []

    for img in page.images:
        if h1_y < img.y < first_cta_y and img.visible:
            violations.append(Violation(
                rule_id="R2",
                severity="major",
                evidence_tier="T1",
                image_src=img.src,
                description=f"Image between H1 (y={h1_y:.0f}) and first CTA (y={first_cta_y:.0f}). "
                            "Images before CTA can steal attention from the primary conversion driver.",
                suggestion="Move image after the first CTA, or remove decorative images before the call-to-action.",
            ))
    return violations


def check_R3(page: CapturedPage, page_type: str, vh: int = 720) -> list[Violation]:
    """R3: Hero above headline (destination-guide pages)."""
    if page_type != "destination-guide":
        return []
    if page.h1_rect is None:
        return []

    hero = _hero_image(page.images, vh)
    if hero is None:
        return []

    h1_y = page.h1_rect["y"]
    if hero.y < h1_y:
        return [Violation(
            rule_id="R3",
            severity="major",
            evidence_tier="T2",
            image_src=hero.src,
            description=f"Hero image (y={hero.y:.0f}) appears above headline (y={h1_y:.0f}). "
                        "On destination guides, hero should appear below the headline and dek.",
            suggestion="Place the hero image after the H1 headline and article dek/subtitle.",
        )]
    return []


def check_R4(page: CapturedPage, page_type: str, vh: int = 720) -> list[Violation]:
    """R4: No images near verdict/CTA (review pages)."""
    if page_type != "review":
        return []
    if not page.ctas:
        return []

    threshold = RULES_CONFIG["VERTICAL_DISTANCE_PX"]
    for cta in page.ctas:
        cta_y = cta["y"]
        has_nearby = any(
            abs(img.y - cta_y) < threshold and img.visible
            for img in page.images
        )
        if not has_nearby:
            return [Violation(
                rule_id="R4",
                severity="minor",
                evidence_tier="T1",
                image_src=None,
                description=f"No images within {threshold}px of CTA at y={cta_y:.0f}. "
                            "Review pages should have images near the verdict/CTA for visual reinforcement.",
                suggestion=f"Add a product/destination image within {threshold}px of the call-to-action.",
            )]
    return []


# ── Universal rules ──

def check_R5(page: CapturedPage, page_type: str, vh: int = 720) -> list[Violation]:
    """R5: Auto-rotating galleries / carousels."""
    carousel_classes = {"carousel", "slider", "gallery", "swiper", "slideshow"}
    carousel_images = [
        img for img in page.images
        if carousel_classes & set(img.ancestor_classes)
    ]
    if len(carousel_images) >= 3:
        return [Violation(
            rule_id="R5",
            severity="major",
            evidence_tier="P",
            image_src=None,
            description=f"{len(carousel_images)} images found in carousel/gallery elements. "
                        "Auto-rotating galleries reduce discoverability and user control.",
            suggestion="Replace auto-rotating gallery with a user-controlled grid or single hero image with thumbnails.",
        )]
    return []


def check_R6(page: CapturedPage, page_type: str, vh: int = 720) -> list[Violation]:
    """R6: Missing alt text on <img> elements."""
    violations = []
    for img in page.images:
        if img.source_type != "img":
            continue  # Only check real <img> tags
        if img.alt is None:  # Missing attribute (not empty/decorative)
            violations.append(Violation(
                rule_id="R6",
                severity="minor",
                evidence_tier="T1",
                image_src=img.src,
                description="Image is missing alt attribute entirely.",
                suggestion="Add descriptive alt text or alt=\"\" if purely decorative.",
            ))
    return violations


def check_R7(page: CapturedPage, page_type: str, vh: int = 720) -> list[Violation]:
    """R7: Stock photo domains."""
    violations = []
    for img in page.images:
        for domain in RULES_CONFIG["KNOWN_STOCK_DOMAINS"]:
            if domain in img.src:
                violations.append(Violation(
                    rule_id="R7",
                    severity="minor",
                    evidence_tier="P",
                    image_src=img.src,
                    description=f"Image from stock photo domain: {domain}. "
                                "Stock photos can damage trust and attention on travel pages.",
                    suggestion="Replace with original photography or user-generated content.",
                ))
                break
    return violations


def check_R8(page: CapturedPage, page_type: str, vh: int = 720) -> list[Violation]:
    """R8: Images too small for impact."""
    threshold = RULES_CONFIG["SMALL_IMAGE_PX"]
    violations = []
    for img in page.images:
        if img.width < threshold and img.visible:
            violations.append(Violation(
                rule_id="R8",
                severity="minor",
                evidence_tier="T1",
                image_src=img.src,
                description=f"Image is very small ({img.width:.0f}x{img.height:.0f}px). "
                            "Small images have limited visual impact on travel pages.",
                suggestion="Use larger images (300px+ width) for product/destination photography.",
            ))
    return violations


def check_R9(page: CapturedPage, page_type: str, vh: int = 720) -> list[Violation]:
    """R9: Missing HTML dimensions (CLS risk)."""
    violations = []
    for img in page.images:
        if not img.has_dim_attrs and img.visible:
            violations.append(Violation(
                rule_id="R9",
                severity="major",
                evidence_tier="P",
                image_src=img.src,
                description="Image missing width/height HTML attributes — causes Cumulative Layout Shift (CLS).",
                suggestion="Add width and height attributes matching the image's intrinsic dimensions.",
            ))
    return violations


def check_R10(page: CapturedPage, page_type: str, vh: int = 720) -> list[Violation]:
    """R10: First viewport image not optimized for LCP."""
    first = _first_viewport_image(page.images, vh)
    if first is None:
        return []

    # Only applies to real <img> elements
    if first.source_type != "img":
        return []

    # loading="lazy" above the fold is the problem
    has_lazy = first.loading == "lazy"
    has_high_priority = first.fetchpriority == "high"

    if has_lazy and not has_high_priority:
        return [Violation(
            rule_id="R10",
            severity="major",
            evidence_tier="P",
            image_src=first.src,
            description=f"First viewport image (y={first.y:.0f}) has loading=\"lazy\" without fetchpriority=\"high\". "
                        "Dual-signal missing: LCP image should be eager-loaded with high fetch priority.",
            suggestion="Set loading=\"eager\" and fetchpriority=\"high\" on the above-fold hero image.",
        )]
    return []


def check_R11(page: CapturedPage, page_type: str, vh: int = 720) -> list[Violation]:
    """R11: No large image for Google Discover eligibility."""
    threshold = RULES_CONFIG["LARGE_IMAGE_PX"]
    has_large = any(img.width > threshold for img in page.images)
    if not has_large and page.images:
        return [Violation(
            rule_id="R11",
            severity="minor",
            evidence_tier="P",
            image_src=None,
            description=f"No images wider than {threshold}px. "
                        "Google Discover requires at least one image >1200px wide for large-image eligibility.",
            suggestion="Add at least one wide image (1200px+) to qualify for Google Discover large-image display.",
        )]
    return []


def check_R12(page: CapturedPage, page_type: str, vh: int = 720) -> list[Violation]:
    """R12: Zero images on page (non-blog pages only).

    Blog pages may legitimately have no images (pure informational).
    Comparison, destination-guide, and review pages without images are
    missing a critical element per Hypatia's T1/T2 evidence.
    """
    if page_type == "blog":
        return []
    if page.images:
        return []

    return [Violation(
        rule_id="R12",
        severity="critical",
        evidence_tier="T1",
        image_src=None,
        description=f"Page has zero images. {page_type.title()} pages should have at least one "
                    "image — hero images drive engagement on destination guides, product images "
                    "reinforce CTAs on review and comparison pages.",
        suggestion=f"Add at least one relevant image to this {page_type} page. "
                   "Destination guide: hero below headline. Review: product image near verdict. "
                   "Comparison: product images after the comparison table.",
    )]
