"""Elon Musk Tweets — Tier 2 Strategy Page"""

from core.page_builder import render_strategy_page, social_media_widgets

render_strategy_page(
    strategy_name="musk_tweets",
    page_title="Musk Tweets",
    tier=2,
    extra_widgets=social_media_widgets("elonmusk", "Elon Musk"),
)
