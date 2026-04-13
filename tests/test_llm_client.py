"""Tests for LLM client — validates cost calculation and model resolution."""

from backend.utils.llm_client import LLMClient, _calculate_cost, _inject_images


def test_calculate_cost_opus():
    """Opus cost should match the rate table: $15/MTok in, $75/MTok out."""
    cost = _calculate_cost("claude-opus-4-6", 1000, 500)
    expected = (1000 / 1_000_000) * 15.00 + (500 / 1_000_000) * 75.00
    assert abs(cost - expected) < 0.000001


def test_calculate_cost_sonnet():
    """Sonnet cost should match: $3/MTok in, $15/MTok out."""
    cost = _calculate_cost("claude-sonnet-4-6", 1000, 500)
    expected = (1000 / 1_000_000) * 3.00 + (500 / 1_000_000) * 15.00
    assert abs(cost - expected) < 0.000001


def test_calculate_cost_haiku():
    """Haiku cost should match: $0.80/MTok in, $4.00/MTok out."""
    cost = _calculate_cost("claude-haiku-4-5-20251001", 1000, 500)
    expected = (1000 / 1_000_000) * 0.80 + (500 / 1_000_000) * 4.00
    assert abs(cost - expected) < 0.000001


def test_calculate_cost_unknown_model():
    """Unknown model should return 0 — don't block the pipeline."""
    cost = _calculate_cost("unknown-model", 1000, 500)
    assert cost == 0.0


def test_resolve_model_aliases():
    """Aliases should map to full model IDs."""
    client = LLMClient()
    assert client.resolve_model("opus") == "claude-opus-4-6"
    assert client.resolve_model("sonnet") == "claude-sonnet-4-6"
    assert client.resolve_model("haiku") == "claude-haiku-4-5-20251001"


def test_resolve_model_passthrough():
    """Full model IDs should pass through unchanged."""
    client = LLMClient()
    assert client.resolve_model("claude-opus-4-6") == "claude-opus-4-6"


def test_inject_images_into_text_message():
    """Images should be prepended to the last user message as content blocks."""
    messages = [
        {"role": "user", "content": "Analyse this image"},
    ]
    result = _inject_images(messages, [b"fake_png_bytes"])

    # Last user message should now be a list with image + text blocks
    assert isinstance(result[0]["content"], list)
    assert result[0]["content"][0]["type"] == "image"
    assert result[0]["content"][-1]["type"] == "text"
    assert result[0]["content"][-1]["text"] == "Analyse this image"


def test_inject_images_preserves_other_messages():
    """System and assistant messages should not be modified."""
    messages = [
        {"role": "assistant", "content": "I see..."},
        {"role": "user", "content": "Check this"},
    ]
    result = _inject_images(messages, [b"image_data"])

    # Only the user message should be modified
    assert isinstance(result[0]["content"], str)
    assert isinstance(result[1]["content"], list)


def test_inject_images_does_not_mutate_original():
    """Image injection should not modify the original messages list."""
    messages = [{"role": "user", "content": "Test"}]
    _inject_images(messages, [b"data"])
    assert isinstance(messages[0]["content"], str)
