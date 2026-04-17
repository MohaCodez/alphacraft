import os
from dotenv import load_dotenv

load_dotenv()

# --- Monte Carlo ---
MONTE_CARLO_RUNS = 10000
MC_GROWTH_SIGMA = 0.08
MC_WACC_SIGMA = 0.15
MC_GROWTH_MIN = -0.05
MC_GROWTH_MAX = 0.40
# Regime-based correlation defaults (overridden per-sector in montecarlo.py)
MC_RHO_STABLE = 0.2
MC_RHO_CYCLICAL = 0.4
MC_RHO_SPECULATIVE = 0.6
MC_CORRELATION_RHO = 0.3      # fallback
MC_GROWTH_SKEW_ALPHA = -2.0   # negative = fatter left tail

# --- DCF ---
DCF_PROJECTION_YEARS = 10
DCF_HIGH_GROWTH_YEARS = 5
DCF_TERMINAL_GROWTH = 0.025
DCF_TV_HAIRCUT_MIN = 0.60
DCF_TV_HAIRCUT_MAX = 0.90
DCF_TV_MAX_CONTRIBUTION = 0.75
DCF_GROWTH_DECAY_K = 0.5      # exponential decay constant for growth fade
DCF_ROIC_TERMINAL = 0.08      # long-run ROIC convergence target

# --- Ensemble ---
DCF_WEIGHT = 0.40
RELATIVE_WEIGHT = 0.35
EARNINGS_WEIGHT = 0.25
ENSEMBLE_WEIGHT_FLOOR = 0.10
ENSEMBLE_ENTROPY_GAMMA = 0.1  # entropy regularization strength

# --- Relative valuation ---
RELATIVE_PE_WEIGHT = 0.50
RELATIVE_EV_EBITDA_WEIGHT = 0.35
RELATIVE_PB_WEIGHT = 0.15
PEG_ADJUSTMENT_MIN = 0.5
PEG_ADJUSTMENT_MAX = 2.0

# --- Earnings ---
EARNINGS_GROWTH_BUFFER = 0.02  # δ: min gap between r and g
EARNINGS_SHORT_TERM_WEIGHT = 0.6
EARNINGS_LONG_TERM_WEIGHT = 0.4

# --- Mispricing (percentile-based) ---
UNDERVALUED_PERCENTILE = 0.15
OVERVALUED_PERCENTILE = 0.85
UNDERVALUED_THRESHOLD = -1.5
OVERVALUED_THRESHOLD = 1.5

# --- Capital efficiency ---
ROIC_WACC_SPREAD_FULL_CREDIT = 0.05

# --- Quality ---
PIOTROSKI_MIN_QUALITY = 4
ACCRUAL_PENALTY_THRESHOLD = 0.10  # flag if |accrual ratio| > 10%

# --- Sector classification for regime-based correlation ---
CYCLICAL_SECTORS = {
    "Consumer Discretionary", "Financials", "Materials",
    "Energy", "Industrials", "Real Estate",
}
SPECULATIVE_SECTORS = {
    "Information Technology", "Communication Services",
}
# Everything else is "stable"

# --- General ---
RISK_FREE_RATE_DEFAULT = 0.045
EQUITY_RISK_PREMIUM = 0.055
DB_PATH = os.path.join(os.path.dirname(__file__), "db", "alphacraft.db")
FRED_API_KEY = os.getenv("FRED_API_KEY", "your_key_here")
