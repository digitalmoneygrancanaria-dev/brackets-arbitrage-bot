"""GPU Rental Prices (H100) — Tier 2 Strategy Page"""

from core.page_builder import render_strategy_page, gpu_price_widgets

render_strategy_page(
    strategy_name="gpu_prices",
    page_title="GPU Prices",
    tier=2,
    extra_widgets=gpu_price_widgets,
)
