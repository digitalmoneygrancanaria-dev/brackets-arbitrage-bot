"""Box Office Opening Weekend — Tier 2 Strategy Page"""

from core.page_builder import render_strategy_page, box_office_widgets

render_strategy_page(
    strategy_name="box_office",
    page_title="Box Office",
    tier=2,
    extra_widgets=box_office_widgets,
)
