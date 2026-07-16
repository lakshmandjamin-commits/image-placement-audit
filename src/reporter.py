"""JSON reporter — produces AuditReport from captured page and rule violations."""

from __future__ import annotations

import json
from .models import CapturedPage, Violation, AuditReport


def report(
    page: CapturedPage,
    page_type: str,
    violations: list[Violation],
) -> AuditReport:
    """Build an audit report from page data, type, and violations."""
    summary: dict[str, int] = {}
    for v in violations:
        summary[v.severity] = summary.get(v.severity, 0) + 1

    return AuditReport(
        url=page.url,
        status=page.status,
        page_type=page_type,
        total_images=len(page.images),
        violations=violations,
        summary=summary,
    )


def to_json(report: AuditReport) -> str:
    """Serialize an AuditReport to JSON string."""
    return json.dumps(_serialize(report), indent=2, default=str)


def _serialize(obj):
    """Convert dataclass to dict for JSON serialization."""
    if hasattr(obj, "__dataclass_fields__"):
        return {f: _serialize(getattr(obj, f)) for f in obj.__dataclass_fields__}
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    return obj
