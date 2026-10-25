"""What a call costs, for the record kept with every answer."""

# Dollars per million tokens, (input, output): Anthropic's first-party prices as cached on
# 2026-10-06. Check the pricing page before relying on them. A model that is not listed
# (a free one) has no cost recorded.
PRICES: dict[str, tuple[float, float]] = {
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-haiku-5-5": (0.10, 0.50),
}


def estimate_cost_usd(model: str | None, input_tokens: int, output_tokens: int) -> float | None:
    if model not in PRICES:
        return None
    input_price, output_price = PRICES[model]
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000
