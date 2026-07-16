# Image Placement Audit Tool — Implementation Plan v3

> **v3:** Merged fetcher+extractor into single Playwright pass. All DOM capture happens before page closes. Fixed rule numbering, R8 split, R6 severity, R10 OR-logic, viewport pinned, evidence tiers defined.

**Goal:** Crawl affiliate pages, capture all visible images with live geometry in one Playwright pass, classify page type, flag violations against Hypatia's evidence-based image placement rules.

**Tech Stack:** Python 3.11+, Playwright (async), pytest (TDD). No BeautifulSoup needed — all DOM work happens in browser JS.

---

## Architecture (simplified)

```
audit_image_placement/
  src/
    __init__.py
    capture.py       — Single Playwright pass: navigate → evaluate JS → return CapturedPage (all data)
    classifier.py    — Page type classifier (4 types from CapturedPage)
    rules.py         — Rule engine (11 rules, page-type-aware)
    reporter.py      — JSON report
    cli.py           — argparse CLI
    models.py        — Shared dataclasses
  tests/
    test_capture.py, test_classifier.py, test_rules.py, test_reporter.py
    conftest.py
    fixtures/        — Saved CapturedPage JSON snapshots
  pyproject.toml
```

## Core Design: Everything in One JS Pass

```
capture.py::capture(url, viewport="1280x720") → CapturedPage:
  1. Launch Playwright, set viewport to 1280x720
  2. Navigate to URL, wait domcontentloaded
  3. Scroll 3× viewport-height to trigger lazy images
  4. Wait 2s for lazy-loaded images to render
  5. Run ONE page.evaluate() that returns JSON with ALL data:
     - **Scroll back to top** before measurement to ensure consistent document coords
     - For every <img>: src, alt, loading, fetchpriority, getBoundingClientRect() + scrollY (absolute doc coords), computed visibility
     - For <picture>/<source>: resolve currentSrc, capture <img> fallback geometry at doc coords
     - For elements with CSS background-image: extract url(), capture element rect at doc coords
     - For <h1>: text content + rect at doc coords
     - For <table> + comparison-card containers: rect at doc coords
     - For Viator/affiliate links (a[href*="viator"], a[href*="partner"]): rect at doc coords + href
     - Surrounding text context (100 chars) for each image from DOM text nodes
     - Document title, page text (first 5000 chars for classification)
  6. Close browser. Return CapturedPage dataclass.
```

**This eliminates the fetcher/extractor boundary problem.** All data is live at capture time. No BeautifulSoup needed.

## Data Models

```python
@dataclass
class ImageData:
    src: str
    alt: str | None           # None = missing attribute, "" = empty/decorative
    loading: str | None
    fetchpriority: str | None
    has_dim_attrs: bool       # True if HTML width+height attributes present (for R9 CLS check)
    ancestor_classes: list[str]  # class names of element + parents (for R5 carousel detection)
    x: float; y: float; width: float; height: float
    visible: bool
    source_type: str          # "img" | "picture" | "srcset" | "css-bg"
    context_text: str         # surrounding DOM text

@dataclass
class CapturedPage:
    url: str
    title: str
    status: str               # "ok" | "blocked" | "timeout" | "error"
    error: str | None
    viewport: str             # "1280x720"
    page_text: str            # first 5000 chars for classification
    images: list[ImageData]
    h1_rect: dict | None      # {x, y, w, h, text}
    tables: list[dict]        # [{x, y, w, h}]
    ctas: list[dict]          # [{x, y, w, h, href}]
    viewport_height: int
    scroll_y: int

@dataclass
class Violation:
    rule_id: str
    severity: str             # "critical" | "major" | "minor"
    evidence_tier: str        # "T1" | "T2" | "P"
    image_src: str | None
    description: str
    suggestion: str

@dataclass
class AuditReport:
    url: str
    status: str
    page_type: str
    total_images: int
    violations: list[Violation]
    summary: dict[str, int]
```

## Evidence Tier Definitions

| Tier | Meaning |
|------|---------|
| T1 | Travel-specific, measures actual business outcome (booking, CTR, conversion) |
| T2 | Travel-specific, measures proxy (intention, willingness-to-pay) |
| P | Practitioner evidence, industry case data |

## Page Types (4)

| Type | Detection (from CapturedPage) |
|------|-------------------------------|
| **comparison** | Multiple product rows in tables or card grids + keywords ("vs", "compared", "best", "top N") |
| **destination-guide** | Location name in H1 + keywords ("things to do", "attractions", "guide to", "visiting") |
| **review** | Single product focus + score/rating element in text + verdict/conclusion language |
| **blog** | Default. Tie-break: comparison > review > destination-guide > blog |

## Rules (11 total, all using live geometry)

| ID | Page Type | Tier | Sev | Detection |
|----|-----------|------|-----|-----------|
| R1 | comparison | T1 | critical | Hero image y < first table y → flag |
| R2 | comparison | T1 | major | Any image between h1 y and first CTA y → flag |
| R3 | destination-guide | T2 | major | First image y < h1 y → flag |
| R4 | review | T1 | minor | No image within VERTICAL_DISTANCE_PX=300 of any CTA → flag |
| R5 | all | P | major | 3+ images with carousel/slider/gallery/swiper in `ancestor_classes` → flag |
| R6 | all* | T1 | minor | Image missing alt entirely (None, not ""). *Applies only to source_type="img" images (not css-bg/picture) |
| R7 | all | P | minor | Image src domain in KNOWN_STOCK_DOMAINS → flag (low recall, advisory only) |
| R8 | all | T1 | minor | Image width < SMALL_IMAGE_PX=300 → flag as potentially too small for impact |
| R9 | all | P | major | `has_dim_attrs == False` → flag (CLS risk from missing HTML dimensions) |
| R10 | all* | P | major | First viewport image where `loading` is "lazy" AND `fetchpriority` is not "high" → flag. `loading=None` is eager by default. *Applies only to source_type="img" |
| R11 | all | P | minor | Zero images with width > LARGE_IMAGE_PX=1200 → flag "no Discover-eligible large image" |

### Null-Anchor Behavior

| Rule | When anchor is missing | Behavior |
|------|----------------------|----------|
| R1 | `tables=[]` or `h1_rect=None` | Skip rule (cannot assess "above table" without a table) |
| R2 | `ctas=[]` or `h1_rect=None` | Skip rule (cannot assess "between h1 and CTA" without either) |
| R3 | `h1_rect=None` | Skip rule (cannot assess "above headline" without a headline) |
| R4 | `ctas=[]` | Skip rule (no CTA present → no proximity check needed, not a violation) |
| R10 | No image in first viewport | Skip rule (no above-fold image to check) |

### Image Deduplication

Images with identical `src` are deduplicated. The instance with the largest `width × height` (rendered area) is kept; others are discarded. This prevents duplicate violations from `<picture>` + `<img>` fallback while preserving the most prominent geometry for positional rules. Repeated logos/icons that share a src are naturally collapsed to one instance. `total_images` = count after dedup.

### Hero Image Definition

**Hero image** = the image with the largest rendered area (`width × height`) whose `y` position is within the first viewport-height (720px from document top). Rules R1, R3, R10 reference this.

**R6 note:** Lexical alt-context overlap (v2 R6) dropped — unreliable from DOM text alone. R6 now checks alt attribute presence only (accessibility baseline). Semantic incongruence detection needs vision model — future enhancement.

## Configurable Thresholds

```python
RULES_CONFIG = {
    "VERTICAL_DISTANCE_PX": 300,   # R4: image within 300px of CTA
    "SMALL_IMAGE_PX": 300,          # R8: flag images smaller than this
    "LARGE_IMAGE_PX": 1200,         # R11: Discover needs at least one this wide
    "KNOWN_STOCK_DOMAINS": [        # R7: advisory stock photo check
        "shutterstock.com", "istockphoto.com", "gettyimages.com",
        "depositphotos.com", "alamy.com", "dreamstime.com"
    ],
}
```

## Implementation Tasks

### Task 1: Scaffold + models (no blockers)

**Files:** `pyproject.toml`, `src/models.py`, `tests/conftest.py`

Deps: playwright, pytest, pytest-asyncio. Define all dataclasses. Write fixture loader for saved CapturedPage JSON snapshots.

### Task 2: Capture module (no blockers)

**Files:** `src/capture.py`, `tests/test_capture.py`

TDD. `capture(url, viewport="1280x720") → CapturedPage`.
- Single `page.evaluate()` returns JSON with all image/heading/table/CTA data
- Handles `<img>`, `<picture>`/`<source>` (resolves currentSrc), CSS `background-image` (getComputedStyle scan)
- Captures context_text per image from DOM text nodes
- Returns `status="blocked"` if response is 403/503 or Cloudflare challenge detected
- Returns `status="timeout"` on 30s timeout
- Returns `status="error"` with error message on other failures

### Task 3: Classifier (no blockers — parallel with Task 2)

**Files:** `src/classifier.py`, `tests/test_classifier.py`

TDD. `classify(page: CapturedPage) → str`. Uses page_text, h1, table presence. Tie-break order: comparison > review > destination-guide > blog.

### Task 4: Rules engine (blocked by Task 2 + 3)

**Files:** `src/rules.py`, `tests/test_rules.py`

TDD. 11 rule functions, each: `check_RX(page: CapturedPage, page_type: str) → list[Violation]`.

`check_all(page, page_type) → list[Violation]` runs all rules, filters page-type-specific ones.

### Task 5: Reporter + CLI (blocked by Task 4)

**Files:** `src/reporter.py`, `src/cli.py`, `tests/test_reporter.py`

TDD. Reporter produces JSON AuditReport. CLI supports `--url`, `--urls file.txt`, `--output file.json`, `--viewport 1280x720`, `--concurrency N`.

Batch mode: each URL isolated. Failed pages produce `status != "ok"` report entry; don't abort batch.

### Task 6: Integration test (blocked by Task 5)

**Files:** `tests/test_integration.py`

Test full pipeline with a real fleet page URL. Verify output shape, violation types, status field.

## Dependency Graph

```
Task 1 (scaffold+models)
  ├──→ Task 2 (capture) ──┐
  └──→ Task 3 (classifier)┼──→ Task 4 (rules) ──→ Task 5 (reporter+CLI) ──→ Task 6 (integration)
```

## Success Criteria

- [ ] Capture works on 3+ real fleet pages, returns geometry with pixel-accurate positions
- [ ] All 11 rules fire on fixture data
- [ ] Blocked pages produce `status="blocked"`, not zero-violation false pass
- [ ] CLI: `image-audit --url <real_page>` produces valid JSON in < 15s
- [ ] All tests green, ruff clean
