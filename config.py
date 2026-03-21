# ============================================================
# QULLAMAGGIE SWING TRADING SYSTEM - CONFIGURATION
# ============================================================
# All tunable parameters live here. Nothing is hardcoded elsewhere.
# Inspired by Kristjan Kullamägi's swing trading methodology.

# ── Market Mode ───────────────────────────────────────────────
# Set MARKET = "IN" for Indian (NSE/Nifty) or "US" for US markets
MARKET = "IN"
CURRENCY_SYMBOL = "Rs." if MARKET == "IN" else "$"

# ── Account ──────────────────────────────────────────────────
# India: think in lakhs — 10,00,000 = 10 lakhs is a solid starting capital
# US:    100,000 = $1 lakh USD
ACCOUNT_SIZE = 1_000_000       # Rs. 10,00,000 (10 lakhs) for India
RISK_PER_TRADE = 0.01           # Risk 1% of account per trade
MAX_POSITION_PCT = 0.25         # Never more than 25% of account in one position
MAX_OPEN_POSITIONS = 8          # Maximum simultaneous open trades

# ── Trend Filters ─────────────────────────────────────────────
SMA_SHORT = 50                  # Short-term SMA (50-day)
SMA_LONG = 150                  # Long-term SMA (150-day)
EMA_TRAIL = 10                  # Trailing stop EMA (10-day)
PRICE_FROM_52W_HIGH_MAX = 0.25  # Must be within 25% of 52-week high

# ── Breakout Setup (Tight Consolidation Pattern) ──────────────
CONSOLIDATION_DAYS_MIN = 15     # Min base length (3 weeks)
CONSOLIDATION_DAYS_MAX = 60     # Max base length (12 weeks)
CONSOLIDATION_RANGE_MAX = 0.20  # Max high-to-low range in base = 20%
ATR_CONTRACTION_RATIO = 0.85    # Base ATR must be <= 85% of prior-period ATR
BREAKOUT_VOLUME_MULTIPLIER = 1.5  # Volume must be 1.5x 50-day average

# ── Episodic Pivot (Gap-Up on Catalyst) ───────────────────────
EP_GAP_MIN = 0.04               # Minimum gap-up = 4%
EP_VOLUME_MULTIPLIER = 2.0      # Volume must be 2x average
EP_CLOSE_IN_TOP_HALF = True     # Must close in top 50% of the day's range

# ── Entry ──────────────────────────────────────────────────────
ENTRY_ON_NEXT_OPEN = True       # True = buy next open, False = buy same-day close

# ── Exit / Risk Rules ─────────────────────────────────────────
STOP_MAX_PCT = 0.08             # Hard cap: never risk more than 8% below entry
TRAIL_ACTIVATE_R = 1.0          # Activate 10-EMA trail only after 1R in profit
HOLD_MAX_DAYS = 90              # Safety valve: max holding period

# ── Position Sizing Controls ──────────────────────────────────
# Compounding guard: risk amount can grow at most N× the initial risk.
# e.g., initial Rs.10,000 risk × 5 = Rs.50,000 max risk/trade ever.
# This prevents runaway position sizes after a big run-up.
RISK_CAP_MULTIPLIER = 5.0       # Max growth of risk per trade vs initial

# Drawdown circuit breaker: if portfolio drops > X% from its peak,
# pause new trades for DRAWDOWN_PAUSE_DAYS days, then try again.
# Mirrors Qullamaggie: "if I'm down big, I stop for the month, then reset."
DRAWDOWN_PAUSE_PCT  = 0.20      # Pause if drawdown > 20% from peak
DRAWDOWN_PAUSE_DAYS = 30        # Days to pause before retrying (1 month)

# ── Transaction Costs (India realistic) ───────────────────────
# NSE delivery trades (Zerodha / Groww flat brokerage):
#   Brokerage: Rs.20 flat or 0.03% (use 0.03% for mid/small caps)
#   STT (Securities Transaction Tax): 0.1% on buy + sell
#   Exchange charges + SEBI: ~0.004%
#   GST on brokerage: 18%
#   Stamp duty: 0.015%
# Total realistic round-trip cost: ~0.25% to 0.50%
# We use 0.30% per trade (conservative realistic estimate)
TRANSACTION_COST_PCT = 0.003    # 0.3% per trade (round-trip inclusive)
# Set to 0.0 to see raw strategy performance without costs

# ── Data ──────────────────────────────────────────────────────
CACHE_DIR = "data"
OUTPUT_DIR = "output"
DEFAULT_START = "2020-01-01"
DEFAULT_END = "2024-12-31"
VOLUME_AVG_PERIOD = 50          # Days for average volume calculation
ATR_PERIOD = 14                 # ATR lookback period

# ── Default Watchlist ─────────────────────────────────────────
# For India (MARKET="IN"): Nifty 500 universe is loaded automatically.
# For US (MARKET="US"): high-growth momentum leaders.
# You can override at the command line: --universe nifty500 | momentum | us

# India defaults — loaded from nifty500_universe.py
from nifty500_universe import get_nifty500, get_momentum_universe
DEFAULT_WATCHLIST = get_momentum_universe()  # ~200 curated tickers

# US watchlist (used when MARKET="US")
US_WATCHLIST = [
    "NVDA", "AMD", "AVGO", "ANET", "SMCI",
    "CRWD", "AXON", "DDOG", "MNDY", "ZS",
    "CELH", "CROX", "ELF", "LULU", "ONON",
    "DXCM", "INSP", "PODD", "TMDX",
    "COIN", "SOFI", "AFRM",
    "ENPH", "FSLR", "HIMS",
    "META", "TSLA", "SHOP", "TTD", "DUOL",
    "PAYC", "BILL", "RELY", "APP", "IOT",
]
