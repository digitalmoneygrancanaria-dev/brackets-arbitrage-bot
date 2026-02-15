"""Trump Truth Social Posts — Tier 1 Strategy Page"""

from core.page_builder import render_strategy_page, social_media_widgets

render_strategy_page(
    strategy_name="trump_posts",
    page_title="Trump Posts",
    tier=1,
    extra_widgets=social_media_widgets("realDonaldTrump", "Trump Truth Social"),
)
