"""First Week Album Sales — Tier 1 Strategy Page"""

from core.page_builder import render_strategy_page, album_sales_widgets

render_strategy_page(
    strategy_name="album_sales",
    page_title="Album Sales",
    tier=1,
    extra_widgets=album_sales_widgets,
)
