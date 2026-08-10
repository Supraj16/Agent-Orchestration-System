from orchestrator.observability.cost import compute_cost


def test_compute_cost_exact_model_match():
    cost = compute_cost("gpt-4o-mini", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == 0.15 + 0.60


def test_compute_cost_matches_dated_model_string_by_prefix():
    # Providers often return a dated/versioned string instead of the bare alias we price by.
    cost = compute_cost("gpt-4o-mini-2024-07-18", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == 0.15 + 0.60


def test_compute_cost_unknown_model_is_zero_not_an_error():
    assert compute_cost("some-unpriced-model", input_tokens=1_000_000, output_tokens=1_000_000) == 0.0


def test_compute_cost_scales_with_token_count():
    cost = compute_cost("claude-sonnet-5", input_tokens=500_000, output_tokens=0)
    assert cost == 1.50
