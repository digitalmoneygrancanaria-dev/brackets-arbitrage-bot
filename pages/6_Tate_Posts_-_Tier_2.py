"""Andrew Tate Posts — Tier 2 Strategy Page"""

from core.page_builder import render_strategy_page, social_media_widgets

render_strategy_page(
    strategy_name="tate_posts",
    page_title="Tate Posts",
    tier=2,
    extra_widgets=social_media_widgets("Cobratate", "Andrew Tate"),
)
