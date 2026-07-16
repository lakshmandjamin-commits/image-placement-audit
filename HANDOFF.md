# Image Placement Audit Tool — Agent Handoff

> **For:** Saraswati, Hanumanhermes, Lakshman
> **Date:** 2026-07-16
> **Author:** Lakshman (Hermes profile)
> **Project:** `~/.hermes/profiles/lakshman/home/audit_image_placement/`

## What This Tool Does

Crawls travel affiliate pages, captures every image with live browser geometry, classifies the page type, and flags image placement violations against evidence-based research from Hypatia's `travel-image-strategy-deep-research-2026`.

**One command gives you a JSON report of every image placement problem on a page.**

```
Porto home page: 24 images → 22 violations found
  ❌ critical: Hero image above comparison table (hurts conversion)
  ⚠️ major:   Images between headline and first CTA (steals attention)
  ℹ️ minor:   19 small images / missing alt text / missing dimensions
```

## Why This Exists

Hypatia's deep research found a **23x CTR delta** between best and worst image placement on travel pages. Where an image sits on the page matters more than which image it is. The research also found that comparison pages with hero images *above* the comparison table actually hurt conversion — the exact opposite of conventional wisdom.

This tool automates checking 11 evidence-based rules against live pages so the fleet agents don't have to manually audit image placement.

## The Research Basis

Two primary sources in Hypatia's gbrain:

| Page | What It Contains |
|------|-----------------|
| `travel-image-strategy-deep-research-2026` | **Authoritative.** Evidence-based image placement rules per page type. Uses T1/T2/A1/A2/P/N evidence classification. Corrects Hypatia's earlier research on several points. |
| `travel-image-monetization-research-2026` | Superseded by the above. Still valid on some points (lifestyle images beat stock, sidebars are dead zones). |

### Key Findings (from the research)

| Finding | Evidence Tier | Impact |
|---------|--------------|--------|
| Hero before comparison table **hurts** conversion on affiliate pages | T1 (travel, business outcome) | Critical |
| Image before CTA steals attention from primary conversion driver | T1 | Major |
| Hero below headline/dek on destination guides | T2 (travel, proxy) | Major |
| Auto-rotating galleries reduce user control and discoverability | P (practitioner) | Major |
| Text-image incongruence → cognitive dissonance → lower booking intention | T1/A1 | Major |
| AI-generated documentary images are a trust gamble for travel | P | Minor |
| Human presence in photos is conditional: small photos + people = good, large photos + people = bad | T1 | Minor |
| Stock photos damage trust/attention (not SEO rankings — no ranking penalty evidence) | P | Minor |
| Eager-load the hero image, specify dimensions on all images | P | Major |
| Google Discover requires at least one image >1200px wide | P | Minor |

### Evidence Tier Definitions

| Tier | Meaning | Example |
|------|---------|---------|
| **T1** | Travel-specific, measures actual business outcome (booking, CTR, conversion) | "Hero before table → 23x lower CTR on comparison pages" |
| **T2** | Travel-specific, measures proxy (intention, willingness-to-pay) | "Hero below headline improves engagement metrics" |
| **P** | Practitioner evidence, industry case data | "Auto-rotating galleries reduce discoverability" |

### How This Corrects Hypatia's Earlier Research

Hypatia's earlier synthesis was broadly correct but overstated several claims. The deep research report corrected:

- **Hero at top:** Hypatia said "highest ROI." Reality: page-type dependent. On comparison pages, hero above table often **hurts** conversion.
- **Stock photos:** Hypatia said "damage SEO." Reality: no evidence of ranking penalty. Damage is to trust/attention only.
- **Captions:** Hypatia gave captions high SEO weight. Reality: helpful but moderate effect.
- **Image before CTA:** Hypatia endorsed this. Reality: on comparison pages, images before table steal attention from the primary conversion driver.

## How It Works (Architecture)

```
URL → Playwright renders page (1280x720 viewport)
    → Scrolls 3× to trigger lazy images
    → One JS evaluation captures geometry for every image, heading, table, CTA
    → Page type classifier: comparison | destination-guide | review | blog
    → 11 rules check geometry, attributes, relationships
    → JSON report with violations by severity
```

**All image geometry is captured live** — the tool uses `getBoundingClientRect()` in the browser before the page closes. This means pixel-accurate positions, not byte-offset guesses from static HTML.

## The 11 Rules

### Page-Type-Specific (only fire on matching page types)

| Rule | Page Type | Severity | What It Checks |
|------|-----------|----------|---------------|
| **R1** | comparison | critical | Hero image above comparison table |
| **R2** | comparison | major | Images between H1 and first CTA |
| **R3** | destination-guide | major | Hero above headline |
| **R4** | review | minor | No images near verdict/CTA |

### Universal (fire on all page types)

| Rule | Severity | What It Checks |
|------|----------|---------------|
| **R5** | major | 3+ images in carousel/gallery/slider elements |
| **R6** | minor | `<img>` tags missing alt attribute (accessibility) |
| **R7** | minor | Images from known stock photo domains |
| **R8** | minor | Images smaller than 300px (limited visual impact) |
| **R9** | major | Images missing HTML width/height (causes CLS) |
| **R10** | major | First viewport image lazy-loaded without fetchpriority=high (LCP signal) |
| **R11** | minor | No image >1200px wide (Google Discover eligibility) |

### When Rules Skip

Rules don't fire false positives when elements are missing:

| Situation | Behavior |
|-----------|----------|
| No `<h1>` on page | R1, R2, R3 skip (can't check "above headline") |
| No tables/cards on comparison page | R1 skips (no table to compare against) |
| No CTA links found | R2, R4 skip (no CTA to measure distance from) |
| No above-fold images | R10 skips (nothing to check LCP on) |
| Page is blocked (403/Cloudflare) | Report returns status="blocked", not false-clean |

## How Each Agent Should Use This

### Saraswati

**You run the placement audit engine against real pages.** This tool is complementary:

```bash
cd ~/.hermes/profiles/lakshman/home/audit_image_placement

# Audit a single page
.venv/bin/python -m src.cli --url https://www.porto-wine-tours.com/

# Audit all pages in your fleet
.venv/bin/python -m src.cli --urls ~/fleet-urls.txt --output fleet-image-report.json
```

**Interpretation guide:**
- **R1 critical → fix immediately.** Hero above comparison table on Porto/Tenerife/Yogyakarta/etc. comparison pages is actively hurting conversion per T1 evidence.
- **R2 major → fix soon.** Images between headline and CTA steal attention. Move them after the first call-to-action.
- **R9 major → fix in next deploy.** Missing image dimensions cause Cumulative Layout Shift. Add `width` and `height` attributes matching the actual image size.
- **Minor violations → backlog.** Small images, stock photos, missing alt text. Fix opportunistically.

### Hanumanhermes

**You generate pages and manage the 8-site fleet.** This tool audits pages post-generation:

```bash
cd ~/.hermes/profiles/lakshman/home/audit_image_placement

# Audit a recently generated page
.venv/bin/python -m src.cli --url https://www.onsenexperiences.com/hakone-onsen-guide/

# Batch audit new pages after a content drip
.venv/bin/python -m src.cli \
  --urls ~/data/generated-urls.txt \
  --output ~/data/image-audit-$(date +%Y-%m-%d).json
```

**Key findings for your fleet:**
- **Glacier Ice Tours** had 6 images, 1 minor violation — well-optimized. Use as a reference for other sites.
- **Auto-rotating galleries (R5)** — if your templates use carousels, this rule will flag them. Hypatia's research: galleries reduce user control. Replace with user-controlled grids.
- **Stock photos (R7)** — your generated pages may use stock images. Advisory only — no SEO penalty, but trust/attention damage is real.

**Integration opportunity:** Wire image audit into the content generation pipeline. After `page_generator.py` creates a page, run the audit before deploying. Flag pages with critical/major violations for review.

### Lakshman

**You built this and maintain the codebase.** Project at:

```
~/.hermes/profiles/lakshman/home/audit_image_placement/
```

Key files:
- `src/capture.py` — Playwright page capture with live geometry
- `src/classifier.py` — Page type classification
- `src/rules.py` — 11 rule functions
- `src/cli.py` — argparse CLI
- `tests/` — 31 tests

**Development commands:**
```bash
cd ~/.hermes/profiles/lakshman/home/audit_image_placement
.venv/bin/python -m pytest tests/ -v     # run tests
.venv/bin/python -m ruff check src/ tests/  # lint
```

**Extending the tool:**
- **Add a new rule:** Write `check_R12(page, page_type, vh) → list[Violation]` in `rules.py`. Add it to the `check_all()` dispatch list. Add tests in `test_rules.py`.
- **Add human presence detection (future):** R8 (v1) was dropped because HTML can't detect people in images. Needs a vision model (Ollama or API). The rule skeleton is ready — just needs the detection function.
- **Add semantic incongruence detection (future):** R6 (v2) was downgraded from alt-text congruence check to simple alt-presence check. Actual semantic matching between image content and surrounding text needs a vision model.

### Hypatia

**You're the research agent.** The research that powers this tool lives in your gbrain:

- `travel-image-strategy-deep-research-2026` — The authoritative image placement research
- `travel-image-monetization-research-2026` — Superseded but still referenced
- `image-pipeline-gap-analysis` — The existing page generation pipeline doesn't inject images
- `hardening-plan-current` — Topic verification plan (deferred)

**Research gaps to fill (if asked):**
- Image effectiveness metrics (CTR on images, engagement time) — no travel-specific data exists
- Visual saliency detection (which images draw attention) — eye-tracking in travel context
- Image format benchmarks (WebP vs AVIF impact on travel site Core Web Vitals)
- Mobile vs desktop image placement — the tool audits at 1280x720; mobile viewport audit is a separate pass

## Report Format

The JSON output follows this schema:

```json
{
  "url": "https://www.porto-wine-tours.com/",
  "status": "ok",
  "page_type": "comparison",
  "total_images": 24,
  "violations": [
    {
      "rule_id": "R1",
      "severity": "critical",
      "evidence_tier": "T1",
      "image_src": "https://.../hero.jpg",
      "description": "Hero image (y=148) appears above comparison table (y=508)...",
      "suggestion": "Move hero image below the comparison table..."
    }
  ],
  "summary": {"critical": 1, "major": 2, "minor": 19}
}
```

**Status values:**
- `"ok"` — page loaded, audit completed
- `"blocked"` — 403, 503, or Cloudflare challenge detected (no false-clean pass)
- `"timeout"` — page didn't load within 30s
- `"error"` — unexpected failure

## Limitations (What This Tool Does NOT Do)

| Limitation | Why |
|------------|-----|
| Cannot detect human presence in images | Needs vision model. R8 (human presence) from v1 plan deferred |
| Cannot detect text-image semantic incongruence | Needs vision model. R6 checks alt *presence* only, not content match |
| Cannot detect CSS `aspect-ratio` as CLS prevention | R9 fires on missing HTML dims even if CSS prevents CLS. Downgrade to minor if this gets noisy |
| Does not handle pages behind login/auth walls | Playwright opens pages as a fresh browser session |
| Stock photo detection is URL-substring only (low recall) | Self-hosted stock photos via CDN won't be caught |
| Single viewport size (1280x720 desktop) | Mobile audit would need a separate pass. The `--viewport` flag exists but mobile-specific rules aren't implemented |

## Related Projects

| Project | Relationship |
|---------|-------------|
| `viator-placement-engine` | Same architecture pattern (parse → classify → rule-check → report). Position detection, page type classification shared concepts |
| `image-pipeline-gap-analysis` (Hypatia) | The fleet's page generator doesn't inject images. This tool audits what exists now; the pipeline fix is a separate project |
| `hardening-plan-current` (Hypatia) | Topic verification for image injection. Complements this audit tool for the *generation* side |

## Changelog

- **2026-07-16:** Initial implementation. 7 tasks, 31 tests, 950 source lines. Plan: 5 Claude Opus cycles (final 8/10). Verified on 3 fleet pages.
