"""CLI entry point for image audit tool."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .capture import capture
from .classifier import classify
from .rules import check_all
from .reporter import report, to_json


async def audit_single(url: str, viewport: str = "1280x720") -> dict:
    """Audit a single URL and return the report dict."""
    page = await capture(url, viewport=viewport)
    if page.status != "ok":
        return {
            "url": url,
            "status": page.status,
            "error": page.error,
            "page_type": "unknown",
            "total_images": 0,
            "violations": [],
            "summary": {},
        }

    page_type = classify(page)
    violations = check_all(page, page_type)
    r = report(page, page_type, violations)
    return json.loads(to_json(r))


async def audit_batch(
    urls: list[str],
    viewport: str = "1280x720",
    concurrency: int = 3,
) -> list[dict]:
    """Audit multiple URLs with bounded concurrency."""
    semaphore = asyncio.Semaphore(concurrency)

    async def bounded(url: str) -> dict:
        async with semaphore:
            return await audit_single(url, viewport)

    return await asyncio.gather(*[bounded(u) for u in urls])


def main():
    parser = argparse.ArgumentParser(
        description="Image Placement Audit — audit travel affiliate pages for image placement violations."
    )
    parser.add_argument("--url", help="Single URL to audit")
    parser.add_argument("--urls", help="File with URLs (one per line)")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    parser.add_argument("--viewport", default="1280x720", help="Viewport size (default: 1280x720)")
    parser.add_argument("--concurrency", type=int, default=3, help="Concurrent pages (default: 3)")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")

    args = parser.parse_args()

    if not args.url and not args.urls:
        parser.error("Either --url or --urls is required")

    urls = []
    if args.url:
        urls.append(args.url)
    if args.urls:
        urls.extend(
            line.strip()
            for line in Path(args.urls).read_text().splitlines()
            if line.strip() and not line.startswith("#")
        )

    if not urls:
        print("No URLs to audit.", file=sys.stderr)
        sys.exit(0)

    results = asyncio.run(audit_batch(urls, args.viewport, args.concurrency))

    output = results[0] if len(results) == 1 else results
    json_str = json.dumps(output, indent=2 if args.pretty else None, default=str)

    if args.output:
        Path(args.output).write_text(json_str + "\n")
        print(f"Report saved to {args.output}")
    else:
        print(json_str)


if __name__ == "__main__":
    main()
