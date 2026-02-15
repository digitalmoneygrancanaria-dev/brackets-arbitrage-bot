"""MrBeast YouTube Views — Tier 1 Strategy Page"""

from core.page_builder import render_strategy_page, mrbeast_widgets

render_strategy_page(
    strategy_name="mrbeast_views",
    page_title="MrBeast Views",
    tier=1,
    extra_widgets=mrbeast_widgets,
)
