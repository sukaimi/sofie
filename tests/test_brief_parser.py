"""Tests for brief parser — validates .docx field extraction."""

import asyncio
from pathlib import Path

import pytest

from backend.pipeline.brief_parser import parse_brief

TEST_BRIEF = Path(__file__).parent / "test_brief.docx"


@pytest.fixture
def brief_result():
    """Parse the test brief once for all tests in this module."""
    return asyncio.run(parse_brief(TEST_BRIEF))


def test_parse_returns_result(brief_result):
    """Parser should return a BriefParseResult with fields dict."""
    assert brief_result is not None
    assert isinstance(brief_result.fields, dict)


def test_brand_name_extracted(brief_result):
    """Brand name is a BLOCKER field — must be extracted."""
    assert brief_result.fields.get("brand_name") == "TestBrand Co"


def test_industry_extracted(brief_result):
    """Industry is extracted from Section 1."""
    assert brief_result.fields.get("industry") == "Technology"


def test_job_title_extracted(brief_result):
    """Job title is extracted from Section 2."""
    assert brief_result.fields.get("job_title") == "Q2 Social Banner"


def test_platform_extracted(brief_result):
    """Platform is a BLOCKER field — must be extracted."""
    assert brief_result.fields.get("platform") == "Instagram"


def test_output_sizes_extracted(brief_result):
    """Output sizes should be a list of dimension strings."""
    sizes = brief_result.fields.get("output_sizes")
    assert isinstance(sizes, list)
    assert len(sizes) == 2
    assert "1080x1080" in sizes
    assert "1080x1350" in sizes


def test_key_message_extracted(brief_result):
    """Key message is a BLOCKER field."""
    assert brief_result.fields.get("key_message") == "Innovation meets simplicity"


def test_headline_extracted(brief_result):
    """Headline is a BLOCKER field."""
    assert brief_result.fields.get("headline_text") == "The Future is Now"


def test_cta_extracted(brief_result):
    """CTA is optional but should be extracted when present."""
    assert brief_result.fields.get("cta_text") == "Learn More"


def test_brand_colours_extracted(brief_result):
    """Brand colours is a BLOCKER field."""
    colours = brief_result.fields.get("brand_colours")
    assert colours is not None
    assert "#1a1a2e" in colours


def test_logo_link_extracted(brief_result):
    """Logo link is a BLOCKER field."""
    assert "example.com/logo.png" in (brief_result.fields.get("logo_link") or "")


def test_hero_image_extracted(brief_result):
    """Hero image links should be extracted as a list."""
    hero = brief_result.fields.get("hero_image_links")
    assert hero is not None


def test_sub_copy_extracted(brief_result):
    """Sub-copy is optional but should be extracted."""
    assert brief_result.fields.get("sub_copy") == "Discover our latest innovation"


def test_restrictions_extracted(brief_result):
    """Restrictions should be captured."""
    restrictions = brief_result.fields.get("restrictions_dont")
    assert restrictions is not None
    assert "stock photography" in restrictions.lower()


def test_no_text_box_warning(brief_result):
    """Test brief has no text boxes — should not generate a warning."""
    assert not brief_result.has_text_boxes
