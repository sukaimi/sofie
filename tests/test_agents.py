"""Tests for agent logic — validates Marcus state machine and Priya field checks."""

from backend.agents.marcus import MarcusAgent
from backend.agents.priya import PriyaAgent
from backend.models import Job


def test_marcus_valid_transitions():
    """Marcus should define transitions for all job states."""
    assert "pending" in MarcusAgent._VALID_TRANSITIONS
    assert "validating" in MarcusAgent._VALID_TRANSITIONS["pending"]
    assert "delivered" not in MarcusAgent._VALID_TRANSITIONS["pending"]


def test_marcus_delivered_is_terminal():
    """Delivered state should have no valid transitions."""
    assert MarcusAgent._VALID_TRANSITIONS["delivered"] == set()


def test_marcus_failed_is_terminal():
    """Failed state should have no valid transitions."""
    assert MarcusAgent._VALID_TRANSITIONS["failed"] == set()


def test_priya_blocker_fields_complete():
    """Priya's BLOCKER fields should match PRD section 7."""
    expected = {
        "brand_name",
        "key_message",
        "output_sizes",
        "logo_link",
        "brand_font_link",
        "brand_colours",
        "headline_text",
        "platform",
    }
    assert PriyaAgent._BLOCKER_FIELDS == expected


def test_priya_local_check_catches_missing():
    """Local blocker check should catch missing required fields."""
    priya = PriyaAgent.__new__(PriyaAgent)
    brief = {"brand_name": "Test", "key_message": "Hello"}
    blockers = priya._check_blockers_locally(brief)

    # Should catch missing: output_sizes, logo_link, brand_font_link,
    # brand_colours, headline_text, platform
    missing_fields = {b["field"] for b in blockers}
    assert "output_sizes" in missing_fields
    assert "logo_link" in missing_fields
    assert "platform" in missing_fields


def test_priya_local_check_passes_complete():
    """Complete brief should produce no blockers."""
    priya = PriyaAgent.__new__(PriyaAgent)
    brief = {
        "brand_name": "TestBrand",
        "key_message": "Innovation meets simplicity",
        "output_sizes": ["1080x1080"],
        "logo_link": "https://example.com/logo.png",
        "brand_font_link": "https://example.com/font.otf",
        "brand_colours": "#1a1a2e, #e94560",
        "headline_text": "The Future is Now",
        "platform": "Instagram",
    }
    blockers = priya._check_blockers_locally(brief)
    assert len(blockers) == 0


def test_priya_parse_json_response():
    """Priya should parse valid JSON responses correctly."""
    priya = PriyaAgent.__new__(PriyaAgent)
    response = '{"has_blockers": false, "blockers": [], "warnings": [], "strategic_issues": [], "approved": true}'
    result = priya._parse_validation_response(response)
    assert result["approved"] is True
    assert result["has_blockers"] is False


def test_priya_parse_markdown_wrapped_json():
    """Priya should handle JSON wrapped in markdown code blocks."""
    priya = PriyaAgent.__new__(PriyaAgent)
    response = '```json\n{"has_blockers": false, "approved": true}\n```'
    result = priya._parse_validation_response(response)
    assert result["approved"] is True


def test_priya_parse_invalid_json():
    """Invalid JSON should return a safe default, not crash."""
    priya = PriyaAgent.__new__(PriyaAgent)
    result = priya._parse_validation_response("this is not json at all")
    assert result["approved"] is True  # Proceed with caution
    assert len(result["warnings"]) > 0
