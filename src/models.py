"""Shared data models for the image audit tool."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ImageData:
    """An image extracted from a page with live geometry."""
    src: str
    alt: str | None               # None = missing attribute, "" = empty/decorative
    loading: str | None            # "eager" | "lazy" | None (= eager by default)
    fetchpriority: str | None      # "high" | "low" | "auto" | None
    has_dim_attrs: bool            # True if HTML width+height attributes present
    ancestor_classes: list[str]    # class names of element + parent chain
    x: float
    y: float                        # absolute document coordinates
    width: float
    height: float
    visible: bool
    source_type: str               # "img" | "picture" | "srcset" | "css-bg"
    context_text: str              # surrounding DOM text (100 chars)


@dataclass
class CapturedPage:
    """All data captured from a single Playwright page visit."""
    url: str
    title: str
    status: str                    # "ok" | "blocked" | "timeout" | "error"
    error: str | None
    viewport: str                  # "1280x720"
    page_text: str                 # first 5000 chars for classification
    images: list[ImageData]        # deduplicated by src (largest kept)
    h1_rect: dict | None           # {x, y, w, h, text}
    tables: list[dict]             # [{x, y, w, h}]
    ctas: list[dict]               # [{x, y, w, h, href}]
    viewport_height: int
    scroll_y: int


@dataclass
class Violation:
    """A single rule violation found during audit."""
    rule_id: str                   # "R1" through "R11"
    severity: str                  # "critical" | "major" | "minor"
    evidence_tier: str             # "T1" | "T2" | "P"
    image_src: str | None
    description: str
    suggestion: str


@dataclass
class AuditReport:
    """Complete audit report for a single page."""
    url: str
    status: str
    page_type: str
    total_images: int
    violations: list[Violation] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)
