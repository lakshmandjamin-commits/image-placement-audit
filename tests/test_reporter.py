"""Tests for JSON reporter."""
import json
from src.models import CapturedPage, Violation
from src.reporter import report, to_json


def test_report_builds_summary():
    page = CapturedPage(
        url="https://example.com", title="Test", status="ok", error=None,
        viewport="1280x720", page_text="", images=[], h1_rect=None,
        tables=[], ctas=[], viewport_height=720, scroll_y=0,
    )
    violations = [
        Violation("R1", "critical", "T1", "img1.jpg", "desc", "fix"),
        Violation("R6", "minor", "T1", "img2.jpg", "desc", "fix"),
        Violation("R9", "major", "P", "img3.jpg", "desc", "fix"),
    ]
    r = report(page, "comparison", violations)
    assert r.page_type == "comparison"
    assert r.summary == {"critical": 1, "minor": 1, "major": 1}


def test_to_json_produces_valid_json():
    page = CapturedPage(
        url="https://example.com", title="Test", status="ok", error=None,
        viewport="1280x720", page_text="", images=[], h1_rect=None,
        tables=[], ctas=[], viewport_height=720, scroll_y=0,
    )
    violations = [Violation("R1", "critical", "T1", "img.jpg", "Hero above table", "Move hero")]
    r = report(page, "comparison", violations)
    json_str = to_json(r)
    data = json.loads(json_str)
    assert data["page_type"] == "comparison"
    assert len(data["violations"]) == 1
    assert data["violations"][0]["rule_id"] == "R1"
