"""Tests for Dana QA agent — validates result parsing and structure."""

from backend.agents.dana import DanaAgent


def test_fail_result_structure():
    """Fail result should have all 3 checks with consistent structure."""
    # DanaAgent needs a session but _fail_result is a pure method
    dana = DanaAgent.__new__(DanaAgent)
    result = dana._fail_result("test failure reason")

    assert result["overall_pass"] is False
    assert result["recommendation"] == "escalate"

    for check_key in ("check1_layout", "check2_brief", "check3_spec"):
        assert check_key in result
        assert result[check_key]["pass"] is False
        assert result[check_key]["score"] == 0
        assert "test failure reason" in result[check_key]["issues"]


def test_validate_qa_structure_fills_missing():
    """Validator should add missing checks with conservative defaults."""
    dana = DanaAgent.__new__(DanaAgent)
    partial_result = {
        "check1_layout": {"pass": True, "score": 85, "issues": []},
        # check2 and check3 missing
    }
    dana._validate_qa_structure(partial_result)

    assert "check2_brief" in partial_result
    assert partial_result["check2_brief"]["pass"] is False
    assert "Check missing" in partial_result["check2_brief"]["issues"]

    assert "check3_spec" in partial_result
    assert partial_result["overall_pass"] is False


def test_validate_qa_structure_all_pass():
    """When all 3 checks pass, overall_pass should be True."""
    dana = DanaAgent.__new__(DanaAgent)
    full_result = {
        "check1_layout": {"pass": True, "score": 90, "issues": []},
        "check2_brief": {"pass": True, "score": 88, "issues": []},
        "check3_spec": {"pass": True, "score": 95, "issues": []},
    }
    dana._validate_qa_structure(full_result)

    assert full_result["overall_pass"] is True
    assert full_result["recommendation"] == "send_to_user"


def test_validate_qa_structure_partial_fail():
    """When any check fails, overall_pass should be False."""
    dana = DanaAgent.__new__(DanaAgent)
    result = {
        "check1_layout": {"pass": True, "score": 80, "issues": []},
        "check2_brief": {"pass": False, "score": 60, "issues": ["Headline too small"]},
        "check3_spec": {"pass": True, "score": 90, "issues": []},
    }
    dana._validate_qa_structure(result)

    assert result["overall_pass"] is False
