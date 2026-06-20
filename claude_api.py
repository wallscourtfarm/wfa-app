"""Anthropic API helper with automatic model fallback.

When Anthropic deprecates a model the first entry in MODEL_FALLBACKS will
start returning 404s. Add the new model ID at the top of the list and the
old ones stay as silent fallbacks — nothing else needs to change.
"""

import anthropic

MODEL_FALLBACKS = [
    "claude-sonnet-4-6",
    "claude-sonnet-4-5",
    "claude-3-5-sonnet-20241022",
]


def create_message(client: anthropic.Anthropic, **kwargs) -> anthropic.types.Message:
    """``client.messages.create`` with automatic model fallback.

    Pass any kwargs you would pass to ``messages.create`` — omit ``model``.
    """
    last_exc = None
    for model in MODEL_FALLBACKS:
        try:
            return client.messages.create(model=model, **kwargs)
        except anthropic.NotFoundError as exc:
            last_exc = exc
            continue
    raise last_exc
