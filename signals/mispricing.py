# signals/mispricing.py
"""Percentile-based mispricing signal with EV gap, tail asymmetry, and conviction."""

import numpy as np
from config import UNDERVALUED_PERCENTILE, OVERVALUED_PERCENTILE, PIOTROSKI_MIN_QUALITY


def compute_signal(current_price, simulation_result, piotroski_score, accrual_ratio=None):
    """
    Percentile-rank signal with:
    - EV gap: (E[V] - Price) / Price — magnitude of mispricing
    - Tail asymmetry: (P90 - P50) / (P50 - P10) — upside vs downside skew
    - Conviction: symmetric for under/overvalued
    - Accrual quality penalty
    """
    if not simulation_result or not current_price:
        return None

    p10 = simulation_result["p10"]
    p50 = simulation_result["p50"]
    p90 = simulation_result["p90"]
    std = simulation_result["std"]
    mean = simulation_result.get("mean", p50)

    if p50 <= 0 or std <= 0:
        return None

    # Percentile rank via interpolation + extrapolation
    percentiles = [
        (10, p10),
        (25, simulation_result.get("p25", (p10 + p50) / 2)),
        (50, p50),
        (75, simulation_result.get("p75", (p50 + p90) / 2)),
        (90, p90),
    ]

    if current_price <= percentiles[0][1]:
        dist_below = (percentiles[0][1] - current_price) / std if std > 0 else 0
        signal_pct = max(0.01, 0.10 - dist_below * 0.05)
    elif current_price >= percentiles[-1][1]:
        dist_above = (current_price - percentiles[-1][1]) / std if std > 0 else 0
        signal_pct = min(0.99, 0.90 + dist_above * 0.05)
    else:
        signal_pct = 0.5
        for i in range(len(percentiles) - 1):
            lo_p, lo_v = percentiles[i]
            hi_p, hi_v = percentiles[i + 1]
            if lo_v <= current_price <= hi_v:
                frac = (current_price - lo_v) / (hi_v - lo_v) if hi_v != lo_v else 0.5
                signal_pct = (lo_p + frac * (hi_p - lo_p)) / 100
                break

    if signal_pct < UNDERVALUED_PERCENTILE:
        signal = "UNDERVALUED"
    elif signal_pct > OVERVALUED_PERCENTILE:
        signal = "OVERVALUED"
    else:
        signal = "FAIR"

    # Downside risk
    downside_risk = (p50 - p10) / p50 if p50 > 0 else 0

    # Z-score (legacy)
    z = (current_price - p50) / std

    # Margin of safety
    margin_of_safety = (p50 - current_price) / p50 if p50 > 0 else 0

    # Expected Value Gap: magnitude of mispricing relative to price
    ev_gap = (mean - current_price) / current_price if current_price > 0 else 0

    # Tail asymmetry: >1 = upside skew (good for longs), <1 = downside skew (value trap risk)
    upside = p90 - p50
    downside = p50 - p10
    tail_asymmetry = upside / downside if downside > 0 else 2.0

    # Conviction
    f_norm = min(piotroski_score, 6) / 6.0 if piotroski_score else 0
    signal_strength = abs(signal_pct - 0.5) * 2
    distribution_tightness = 1 - min(downside_risk, 0.8)

    # Accrual quality penalty
    accrual_penalty = 1.0
    if accrual_ratio is not None and abs(accrual_ratio) > 0.10:
        accrual_penalty = 0.7  # 30% conviction haircut for accounting noise

    if signal_pct < 0.5:
        conviction = signal_strength * distribution_tightness * f_norm * accrual_penalty
    else:
        conviction = signal_strength * distribution_tightness * accrual_penalty

    return {
        "current_price": current_price,
        "fair_value_p50": round(p50, 2),
        "fair_value_p10": round(p10, 2),
        "fair_value_p90": round(p90, 2),
        "mispricing_zscore": round(z, 3),
        "signal_percentile": round(signal_pct, 4),
        "downside_risk": round(downside_risk, 4),
        "conviction": round(conviction, 4),
        "margin_of_safety": round(margin_of_safety, 4),
        "ev_gap": round(ev_gap, 4),
        "tail_asymmetry": round(tail_asymmetry, 4),
        "undervalued_prob": round((1 - signal_pct) * 100, 1),
        "overvalued_prob": round(signal_pct * 100, 1),
        "quality_flag": 1 if (piotroski_score or 0) >= PIOTROSKI_MIN_QUALITY else 0,
        "signal": signal,
    }
