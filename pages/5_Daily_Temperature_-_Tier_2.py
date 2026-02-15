"""Daily City Temperature — Tier 2 Strategy Page"""

from core.page_builder import render_strategy_page, temperature_widgets

render_strategy_page(
    strategy_name="temperature",
    page_title="Daily Temperature",
    tier=2,
    extra_widgets=temperature_widgets,
)
