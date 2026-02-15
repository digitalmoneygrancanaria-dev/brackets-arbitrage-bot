"""Kaito AI Attention Markets — Tier 1 Strategy Page"""

from core.page_builder import render_strategy_page, kaito_placeholder_widgets

render_strategy_page(
    strategy_name="kaito_ai",
    page_title="Kaito AI",
    tier=1,
    extra_widgets=kaito_placeholder_widgets,
)
