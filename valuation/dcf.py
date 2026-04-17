# valuation/dcf.py
"""Multi-stage DCF with exponential growth decay, ROIC fade, and terminal value haircut."""

import numpy as np
from config import (
    DCF_PROJECTION_YEARS, DCF_HIGH_GROWTH_YEARS, DCF_TERMINAL_GROWTH,
    DCF_TV_HAIRCUT_MIN, DCF_TV_HAIRCUT_MAX, DCF_TV_MAX_CONTRIBUTION,
    DCF_GROWTH_DECAY_K, DCF_ROIC_TERMINAL,
)


def _growth_schedule(g_high, g_inf, years, fade_start, k=None,
                     roic=None, reinvestment_rate=None):
    """
    Exponential decay growth schedule with optional ROIC fade.

    Years 1-fade_start: g = min(g_high, ROIC_t × RR_t)
    Years fade_start+1 to end: g decays exponentially toward g_inf

    g_t = g_inf + (g_high - g_inf) × exp(-k × (t - fade_start))
    """
    k = k or DCF_GROWTH_DECAY_K
    g = np.empty(years)

    # ROIC fade: ROIC_t converges from current ROIC to terminal ROIC
    roic_terminal = DCF_ROIC_TERMINAL
    use_roic_fade = (roic is not None and reinvestment_rate is not None
                     and roic > 0 and reinvestment_rate > 0)

    for t in range(years):
        if use_roic_fade:
            # ROIC decays: ROIC_t = ROIC_0 × exp(-m×t) + ROIC_terminal × (1 - exp(-m×t))
            m = 0.15  # ROIC mean-reversion speed
            roic_t = roic * np.exp(-m * t) + roic_terminal * (1 - np.exp(-m * t))
            rr_t = reinvestment_rate  # assume stable reinvestment
            g_implied = roic_t * rr_t
        else:
            g_implied = g_high

        if t < fade_start:
            g[t] = min(g_high, g_implied)
        else:
            # Exponential (convex) decay — snaps down faster than linear
            decay = np.exp(-k * (t - fade_start))
            g_base = g_inf + (g_high - g_inf) * decay
            g[t] = min(g_base, g_implied) if use_roic_fade else g_base

    return g


def run_dcf(fcf, growth_rate, wacc, shares_outstanding=1, net_debt=0,
            terminal_growth=None, projection_years=None, tv_haircut=None,
            roic=None, reinvestment_rate=None):
    if not fcf or not wacc or fcf <= 0:
        return None

    terminal_growth = terminal_growth or DCF_TERMINAL_GROWTH
    projection_years = projection_years or DCF_PROJECTION_YEARS
    tv_haircut = tv_haircut if tv_haircut is not None else (DCF_TV_HAIRCUT_MIN + DCF_TV_HAIRCUT_MAX) / 2

    if terminal_growth >= wacc - 0.02:
        terminal_growth = wacc - 0.02

    # Reinvestment constraint on initial growth
    g_high = growth_rate
    if roic and reinvestment_rate and roic > 0:
        implied_g = roic * reinvestment_rate
        g_high = min(g_high, implied_g + 0.02)

    schedule = _growth_schedule(g_high, terminal_growth, projection_years,
                                DCF_HIGH_GROWTH_YEARS,
                                roic=roic, reinvestment_rate=reinvestment_rate)

    cumulative_growth = np.cumprod(1 + schedule)
    discount = np.array([(1 + wacc) ** (t + 1) for t in range(projection_years)])
    pv_fcf = fcf * cumulative_growth / discount
    sum_pv = float(np.sum(pv_fcf))

    last_fcf = fcf * cumulative_growth[-1]
    tv = last_fcf * (1 + terminal_growth) / (wacc - terminal_growth) * tv_haircut
    tv_pv = tv / (1 + wacc) ** projection_years

    total = sum_pv + tv_pv
    if total > 0 and tv_pv / total > DCF_TV_MAX_CONTRIBUTION:
        tv_pv = sum_pv * DCF_TV_MAX_CONTRIBUTION / (1 - DCF_TV_MAX_CONTRIBUTION)
        total = sum_pv + tv_pv

    equity_value = total - (net_debt or 0)
    if equity_value <= 0 or not shares_outstanding:
        return None

    per_share = equity_value / shares_outstanding
    tv_pct = tv_pv / total if total > 0 else 0
    return {"value": per_share, "tv_contribution": tv_pct}
