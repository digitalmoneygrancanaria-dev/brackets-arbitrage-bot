"""
Strategy analysis content for expandable sections on each page.
Drawn from ANNICA_STRATEGY_ANALYSIS.md section 12.
"""

STRATEGY_CONTENT = {
    "trump_posts": """
### Trump Truth Social Posts — Strategy Analysis

**Market Structure:**
- Brackets: ~8 outcomes (e.g., 60-79, 80-99, 100-119, ... 200+)
- Frequency: Weekly
- Volume: ~$193K/week
- Liquidity: ~$52.8K
- Data source: xtracker.polymarket.com tracking @realDonaldTrump

**Edge Assessment: MODERATE-HIGH**

Much less competition than Musk tweet markets, identical NegRisk bracket structure.
Trump's posting cadence is more erratic than Musk's, creating higher variance but also
cheaper tail brackets when uncertainty is high.

**Smart Selection:** XTracker velocity projection estimates final post count. The bot
auto-selects up to 8 brackets centered around the projected outcome. When no prediction
is available, falls back to even-spread selection across the full bracket range.

**Entry Rules:**
- Only enter when total bracket cost < $0.95 (sum of all YES prices)
- Auto-select up to 8 brackets at 1-10 cents via "Buy Bracket Spread"
- Selection centered on XTracker velocity estimate (posts/hr * remaining hours)
- Use limit-order simulation (walk asks) with 10% depth cap
- Minimum volume > $1,000 per bracket

**Exit Rules (automated every scan cycle):**
- **Resolution**: Gamma API checked for `resolved=True` → WON ($1.00/share) or LOST ($0.00/share)
- **Take-profit**: Auto-sell when best bid ≥ $0.30 (simulated market sell with slippage)
- **Mark-to-market**: Unrealized P&L updated from CLOB orderbook bids each cycle

**Risk Factors:**
- Trump's posting is more erratic → harder to forecast
- Lower liquidity means larger spreads and harder fills
- Political events can cause sudden posting binges or silences
- Fewer brackets means less spread coverage

**Data Sources:**
- XTracker: Real-time post count + velocity projection from @realDonaldTrump
- Gamma API: Market prices and resolution status
- CLOB API: Live orderbook for fill simulation
""",

    "mrbeast_views": """
### MrBeast YouTube Views — Strategy Analysis

**Market Structure:**
- Brackets: Multiple ranges for Day 1, Day 6, Week 1 views per video
- Frequency: Per-video (irregular, ~2-4x per month)
- Active markets: ~9 at any time
- Data source: YouTube view counts (public, near-real-time)

**Edge Assessment: HIGH**

Newer market category with less quant attention. YouTube view counts are publicly
trackable in near-real-time, providing an information advantage similar to XTracker
for tweet counts. View velocity in the first hours after upload is highly predictive.

**Smart Selection:** No real-time predictor yet — selects up to 8 brackets evenly spread
across the full bracket range for maximum coverage. Batch buy places all trades in one click.

**Entry Rules:**
- Only enter when total bracket cost < $0.95
- Auto-select up to 8 brackets via "Buy Bracket Spread" (even spread)
- Focus on Day 1 and Day 6 view count brackets
- Check YT view velocity before entering

**Exit Rules (automated every scan cycle):**
- **Resolution**: Auto-detected via Gamma API → WON ($1.00) or LOST ($0.00)
- **Take-profit**: Auto-sell when best bid ≥ $0.30 (simulated with slippage)
- Hold to resolution for brackets in the winning range

**Risk Factors:**
- Irregular timing depends on MrBeast's upload schedule
- Lower liquidity on some brackets
- Viral videos can exceed all bracket ranges
- Algorithm changes can affect view counts unpredictably

**Data Sources:**
- YouTube: Public view count (real-time tracking via page)
- Gamma API: Market prices and resolution
- CLOB API: Orderbook data
""",

    "kaito_ai": """
### Kaito AI Attention Markets — Strategy Analysis

**LAUNCHING MARCH 2026**

**Market Structure (Expected):**
- Markets on social media mindshare and sentiment
- Resolution via Kaito AI-computed metrics
- Data sources: X, TikTok, Instagram, YouTube
- Verification: Zero-knowledge proofs via Brevis, EigenCloud auditing

**Edge Assessment: POTENTIALLY HIGHEST**

Brand new market category launching in early March 2026. No established bot
infrastructure, unfamiliar resolution metric, first-mover opportunity.

**Smart Selection:** No predictor available yet. At launch, will auto-select up to 8
brackets evenly spread across the full range and batch buy the spread in one click.

**Strategy:**
- Be first mover — evaluate bracket structure immediately at launch
- Look for mispriced brackets where Kaito AI metric behavior is poorly understood
- Use "Buy Bracket Spread" to enter positions across multiple brackets instantly

**Risk Factors:**
- Opaque AI model — resolution mechanics uncertain until launch
- Unknown bracket structure
- May attract sophisticated AI/ML traders quickly
- Kaito metric could be manipulable

**Action:**
- Monitor for launch in early March 2026
- Auto-poll Gamma API for new Kaito-related markets
- Paper trade immediately when brackets appear via batch buy
""",

    "temperature": """
### Daily City Temperature — Strategy Analysis

**Market Structure:**
- Brackets: ~7-8 temperature ranges per city per day (e.g., ≤31F, 32-33F, 34-35F, ... ≥42F)
- Frequency: **DAILY** — new markets every single day for 10+ cities
- Cities: NYC, London, Chicago, Seoul, Miami, Atlanta, Toronto, Dallas, Paris, Seattle
- Combined daily volume: $2.8M+ across all cities
- Individual city volume: $62K-$458K/day
- Data source: Weather Underground (airport station data)

**Edge Assessment: MODERATE**

NegRisk netting on Polymarket makes the "buy all brackets" approach viable (unlike Kalshi
where spreads always sum >$1.00). Best during high-uncertainty weather patterns.

**Smart Selection:** No real-time weather predictor integrated yet. Selects up to 6
brackets evenly spread across the temperature range per city. Batch buy places all trades in one click.

**Entry Rules:**
- Only enter when total bracket cost < $0.95
- Auto-select up to 6 brackets via "Buy Bracket Spread" (even spread)
- Target high-uncertainty days (cold fronts, storms, transitional seasons)
- Focus on cities with widest temperature uncertainty in forecasts

**Exit Rules (automated every scan cycle):**
- Same-day resolution — auto-detected via Gamma API → WON ($1.00) or LOST ($0.00)
- **Take-profit**: Auto-sell when best bid ≥ $0.30 mid-day

**Risk Factors:**
- Bot competition exists (open-source weather bots on GitHub)
- Same-day resolution means fast-moving prices
- Weather models are well-calibrated on average
- Some cities more efficient than others

**Data Sources:**
- Weather Underground: Real-time airport station data
- NWS: National Weather Service forecasts
- Open-Meteo: Free weather API
- Gamma API: Market prices
""",

    "tate_posts": """
### Andrew Tate Posts — Strategy Analysis

**Market Structure:**
- Brackets: **22 outcomes** (most of any post-count market: <100, 100-129, 130-159, ... 700+)
- Frequency: Weekly
- Volume: ~$53.7K/week
- Liquidity: ~$71K
- Data source: xtracker.polymarket.com tracking @Cobratate on X

**Edge Assessment: HIGH**

Very low competition compared to Musk tweets. The 22-bracket structure provides
extensive spread coverage, and tail bracket prices are ultra-cheap (0.3-0.8 cents).
Tate's posting behavior is somewhat predictable (prolific poster, 200-400+ per week).

**Smart Selection:** XTracker velocity projection estimates final post count. The bot
auto-selects up to 15 brackets centered around the projected outcome — with 22 brackets
and ultra-cheap prices, this covers the vast majority of the range.

**Entry Rules:**
- Only enter when total bracket cost < $0.95 (with 22 brackets, likely achievable)
- Auto-select up to 15 brackets via "Buy Bracket Spread"
- Selection centered on XTracker velocity estimate (posts/hr * remaining hours)
- Total cost target: $0.15-$0.25 per complete set

**Exit Rules (automated every scan cycle):**
- **Take-profit**: Auto-sell when best bid ≥ $0.30 (simulated with slippage)
- **Resolution**: Auto-detected via Gamma API → WON ($1.00) or LOST ($0.00)
- With 22 brackets, expect 18-20 to expire worthless
- The 2-3 winners should pay for all losses plus profit

**Risk Factors:**
- Low volume means harder to fill large orders
- Tate could get suspended/banned → market disruption
- XTracker count methodology may differ from resolution
- Platform risk (X account status)

**Data Sources:**
- XTracker: Real-time post count + velocity projection from @Cobratate
- Gamma API: Market prices and resolution
- CLOB API: Orderbook data
""",

    "box_office": """
### Box Office Opening Weekend — Strategy Analysis

**Market Structure:**
- Brackets: 4-5 revenue ranges per movie (e.g., <$14M, $14-17M, $17-20M, $20-23M, >$23M)
- Frequency: Every 1-2 weeks (new movie releases)
- Volume: $60-$333K per movie
- Liquidity: $52-$128K
- Data source: The Numbers (opening weekend domestic box office)

**Edge Assessment: MODERATE**

Less quant attention than crypto/weather markets. Partial real-time tracking is
possible via Friday/Saturday box office estimates (BoxOfficeMojo, The Numbers).
Opening day numbers typically become available Saturday morning.

**Smart Selection:** No real-time predictor yet. With only 4-5 brackets per movie, the
bot auto-selects up to 4 brackets evenly spread across the range — effectively buying the full spread.

**Entry Rules:**
- Only enter when total bracket cost < $0.95
- Auto-select up to 4 brackets via "Buy Bracket Spread" (even spread)
- Focus on high-profile releases with wider bracket ranges
- Enter before Thursday night previews

**Exit Rules (automated every scan cycle):**
- **Take-profit**: Auto-sell when best bid ≥ $0.30 (e.g., after strong Friday actuals)
- **Resolution**: Auto-detected via Gamma API → WON ($1.00) or LOST ($0.00)
- Friday evening: Re-evaluate based on Thursday preview numbers
- Saturday: Sell/hold based on Friday actuals

**Risk Factors:**
- Only 4-5 brackets limits the spread coverage
- Fewer movies = less frequent trading
- Preview numbers can be misleading
- Weather and competing releases affect box office unpredictably

**Data Sources:**
- The Numbers: Official box office data
- BoxOfficeMojo: Real-time estimates
- Gamma API: Market prices
""",

    "musk_tweets": """
### Elon Musk Tweets — Strategy Analysis (Baseline)

**Market Structure:**
- Brackets: ~12-22 outcomes per market (20-tweet-wide ranges)
- Frequency: Weekly (3-day + 7-day windows run simultaneously)
- Volume: ~$14.8M/week
- Liquidity: ~$862K
- Data source: xtracker.polymarket.com/user/elonmusk

**Edge Assessment: DECLINING**

This is the original Annica strategy. The edge has compressed significantly as of
Feb 2026 due to media coverage and copycat traders. Bracket costs now sum to $0.80-$0.95
on many markets, leaving only 5-20% theoretical edge.

**Smart Selection:** XTracker velocity projection estimates final tweet count. The bot
auto-selects up to 10 brackets centered around the projected outcome. With declining
edge, smart selection is critical to avoid buying overpriced brackets.

**Entry Rules:**
- Only enter when total bracket cost < $0.95 (becoming rare)
- Auto-select up to 10 brackets via "Buy Bracket Spread"
- Selection centered on XTracker velocity estimate (tweets/hr * remaining hours)
- Target 7-day markets for more time and data

**Exit Rules (automated every scan cycle):**
- **Take-profit**: Auto-sell when best bid ≥ $0.30 mid-week as tweet count narrows range
- **Resolution**: Auto-detected via Gamma API → WON ($1.00) or LOST ($0.00)
- Merge opportunities: buy cheap NO + merge with YES for $1.00

**Risk Factors:**
- Heavy competition from other traders running same strategy
- Musk's posting behavior is volatile (binges, quiet periods)
- Edge may be fully eroded — monitor bracket costs carefully
- Consider rotating capital to Tier 1 strategies

**Why Tier 2:**
Demoted from primary strategy due to edge compression. Continue monitoring at reduced
size while validating Tier 1 alternatives.

**Data Sources:**
- XTracker: Real-time tweet count + velocity projection
- Gamma API: Market prices and resolution
- CLOB API: Orderbook data
""",

    "album_sales": """
### First Week Album Sales — Strategy Analysis

**Market Structure:**
- Brackets: 7-8 sales ranges per album (e.g., <50K, 50-75K, 75-100K, 100-125K, ... 200K+)
- Frequency: Per major album release (~4-6 per month)
- Active markets: ~12 at any time
- Data source: Billboard/Luminate (official), Spotify/Apple Music streaming (real-time proxy)

**Edge Assessment: HIGH**

Newest bracket category with very little quant attention. Music fans trade these markets,
not algorithmic traders. Streaming velocity in the first 24-48 hours is highly predictive
of final first-week numbers, giving a real-time data advantage.

**Smart Selection:** Uses Apple Music chart rank as a rough sales estimate (top 1 ~200K,
top 5 ~100K, top 10 ~50K). Auto-selects up to 8 brackets centered around the estimate.
Batch buy places all trades in one click.

**Entry Rules:**
- Only enter when total bracket cost < $0.95
- Auto-select up to 8 brackets via "Buy Bracket Spread"
- Selection centered on Apple Music chart rank heuristic estimate
- Focus on high-profile releases (BTS, BlackPink, Taylor Swift, Drake, etc.)

**Exit Rules (automated every scan cycle):**
- **Take-profit**: Auto-sell when best bid ≥ $0.30 (streaming trajectory clarifies)
- **Resolution**: Auto-detected via Gamma API → WON ($1.00) or LOST ($0.00)
- By day 3-4 of release week, the winning bracket is usually clear

**Risk Factors:**
- Release dates can shift, affecting market timing
- Physical sales (vinyl, CD bundles) harder to track real-time vs streaming
- Different counting methodologies between platforms
- Lower liquidity on some smaller artist markets

**Real-Time Data Sources:**
- Apple Music: Daily album chart positions (used for outcome prediction)
- Spotify Charts: Daily top albums chart + stream counts via kworb.net
- Billboard: Official first-week projections (usually published mid-week)
- Spotify API: Track play counts (updated ~daily)
""",

    "gpu_prices": """
### GPU Rental Prices (H100) — Strategy Analysis

**Market Structure:**
- Brackets: 11-12 price ranges for monthly H100 rental averages
- Frequency: Monthly
- Data source: Cloud GPU marketplace pricing (vast.ai, SF Compute, RunPod)

**Edge Assessment: MODERATE (niche)**

Very few traders understand GPU rental market dynamics. Price movements are driven by
AI model training demand, new GPU launches, and supply constraints — factors most
prediction market participants don't track. The market is small but inefficient.

**Smart Selection:** Uses the latest H100 price from United Compute GPU Tracker as the
outcome estimate. Auto-selects up to 6 brackets centered around the current price.
Batch buy places all trades in one click.

**Entry Rules:**
- Only enter when total bracket cost < $0.95
- Auto-select up to 6 brackets via "Buy Bracket Spread"
- Selection centered on latest H100 price from United Compute tracker
- Track demand signals: new model releases, training runs, compute shortages

**Exit Rules (automated every scan cycle):**
- **Take-profit**: Auto-sell when best bid ≥ $0.30 (price trend clear mid-month)
- **Resolution**: Auto-detected via Gamma API → WON ($1.00) or LOST ($0.00)
- GPU prices tend to be sticky (don't move fast), so mid-month trends are predictive

**Risk Factors:**
- Niche market with lower liquidity
- GPU price data sources may not match Polymarket resolution source exactly
- Sudden supply changes (e.g., new H200 availability) can move prices quickly
- Only monthly resolution — slower trading cycle

**Real-Time Data Sources:**
- United Compute GPU Tracker: Latest H100 price (used for outcome prediction)
- vast.ai: Public search API for GPU offers (no auth needed)
- SF Compute: GPU pricing index
- RunPod: Community cloud pricing
""",
}

# Full strategy overview for the home page
OVERVIEW_CONTENT = """
## Brackets Arbitrage Bot — Strategy Overview

### The Core Strategy: Multi-Bracket Spread

This bot paper trades the **Annica bracket spread strategy** across 9 Polymarket markets.
The strategy exploits a structural mispricing in multi-bracket NegRisk markets:

1. **Structure**: Markets have 5-30+ mutually exclusive brackets. Exactly ONE resolves YES ($1.00).
2. **Smart Selection**: Real-time data (XTracker velocity, GPU prices, chart ranks) estimates the likely outcome. Brackets closest to the estimate are auto-selected.
3. **Batch Buy**: One-click "Buy Bracket Spread" places trades across all selected brackets simultaneously.
4. **Edge**: Since one bracket MUST win ($1.00 payout), and total cost < $0.95, the spread is profitable.
5. **Active Management**: Sell appreciating brackets mid-period at 30-60 cents for early profit.

### Trade Settlement (Automated)

Every scan cycle (5 minutes), the bot automatically settles open positions:

1. **Resolution Detection** — Checks Gamma API for `resolved=True` + `outcomePrices`. If the trade's side matches the winner → **WON** ($1.00/share). Otherwise → **LOST** ($0.00/share).
2. **Take-Profit** — Fetches CLOB orderbook for each open position. If best bid ≥ $0.30 → simulates a market sell (with realistic slippage) → **SOLD** at the fill price.
3. **Mark-to-Market** — Collects current bid prices to compute unrealized P&L for all remaining open positions. Portfolio equity reflects live orderbook values.

### Market Suitability Criteria

A market qualifies for this strategy when:
- Multi-bracket NegRisk structure (mutually exclusive outcomes)
- Quantitative/countable resolution (objective, not subjective)
- Real-time data source for mid-period tracking
- Recurring (weekly or more frequent)
- Cheap tail brackets available (total spread < $0.95)

### Tier 1 — Highest Expected Edge
| # | Market | Why |
|---|--------|-----|
| 1 | Trump Truth Social Posts | Same structure as Musk, much less competition |
| 2 | MrBeast YouTube Views | Newer category, less quant attention, real-time data |
| 3 | Kaito AI Attention | Brand new March 2026, first-mover opportunity |
| 4 | First Week Album Sales | Music fans not bots, streaming data = real-time edge |

### Tier 2 — Moderate Edge
| # | Market | Why |
|---|--------|-----|
| 5 | Daily Temperature | NegRisk netting works, daily frequency, 10+ cities |
| 6 | Andrew Tate Posts | 22 brackets, ultra-low competition |
| 7 | Box Office Weekends | NegRisk, partial real-time tracking |
| 8 | GPU Rental Prices | Niche market, few understand GPU pricing dynamics |
| 9 | Elon Musk Tweets | Original strategy, declining edge |

### Simulation Parameters
- **Starting capital**: $1,000 per strategy ($9,000 total)
- **Bet size**: 1% of equity (~$10 per bracket per batch)
- **Entry threshold**: Total bracket cost < $0.95
- **Qualifying range**: 1-10 cents per bracket
- **Take-profit**: Auto-sell when bid ≥ $0.30
- **Volume filter**: > $1,000 per bracket
- **Settlement cycle**: Every 5 minutes (resolution + take-profit + mark-to-market)

### Smart Selection Predictors
| Strategy | Predictor | Source |
|----------|-----------|--------|
| Trump Posts | Velocity projection | XTracker @realDonaldTrump |
| Tate Posts | Velocity projection | XTracker @Cobratate |
| Musk Tweets | Velocity projection | XTracker @elonmusk |
| Album Sales | Chart rank heuristic | Apple Music RSS |
| GPU Prices | Latest H100 price | United Compute tracker |
| Temperature | None (even spread) | — |
| Box Office | None (even spread) | — |
| MrBeast | None (even spread) | — |
| Kaito AI | None (even spread) | — |
"""
