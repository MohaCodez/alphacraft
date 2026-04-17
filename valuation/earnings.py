# valuation/earnings.py
"""Gordon Growth justified P/E with stabilized growth input and blended horizons."""

from config import EARNINGS_GROWTH_BUFFER, EARNINGS_SHORT_TERM_WEIGHT, EARNINGS_LONG_TERM_WEIGHT


def run_earnings(eps_forward, growth_rate, cost_of_equity, long_term_growth=None):
    """
    Fair value = EPS_forward × justified P/E
    Justified P/E = g_adj / (r - g_adj)

    Upgrades over v2:
    - Stabilized: g_adj = min(g, r - δ) where δ = 2%, prevents singularity
    - Blended horizons: g = 0.6 × g_short + 0.4 × g_long
    """
    if not eps_forward or eps_forward <= 0:
        return None

    g_short = growth_rate if growth_rate else 0.05
    g_long = long_term_growth if long_term_growth else min(g_short * 0.5, 0.04)
    r = cost_of_equity if cost_of_equity else 0.10

    # Blend growth horizons
    g = EARNINGS_SHORT_TERM_WEIGHT * g_short + EARNINGS_LONG_TERM_WEIGHT * g_long

    # Stabilize: enforce minimum buffer between r and g
    g_adj = min(g, r - EARNINGS_GROWTH_BUFFER)

    # Floor: g_adj can't be negative for this model to make sense
    if g_adj <= 0:
        g_adj = 0.01

    justified_pe = g_adj / (r - g_adj)
    justified_pe = max(justified_pe, 5)

    return eps_forward * justified_pe
