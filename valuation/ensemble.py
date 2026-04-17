# valuation/ensemble.py
"""Entropy-regularized inverse-variance ensemble with sigmoid capital efficiency."""

import numpy as np
from config import (
    DCF_WEIGHT, RELATIVE_WEIGHT, EARNINGS_WEIGHT,
    ENSEMBLE_WEIGHT_FLOOR, ENSEMBLE_ENTROPY_GAMMA,
    ROIC_WACC_SPREAD_FULL_CREDIT,
)


def inverse_variance_weights(sigma_dcf, sigma_rel, sigma_earn,
                             mean_dcf=None, mean_rel=None, mean_earn=None,
                             floor=None, gamma=None):
    """
    Weights ∝ 1/CV² (coefficient of variation) with entropy regularization.

    CV = σ/μ normalizes variance by scale, so a model producing $20 ± $3 (CV=15%)
    doesn't dominate over a model producing $130 ± $20 (CV=15%) just because
    its absolute σ is smaller.

    Falls back to 1/σ² when means aren't provided.
    """
    floor = floor or ENSEMBLE_WEIGHT_FLOOR
    gamma = gamma if gamma is not None else ENSEMBLE_ENTROPY_GAMMA

    sigmas = [s if s and s > 0 else None for s in [sigma_dcf, sigma_rel, sigma_earn]]
    means = [m if m and m > 0 else None for m in [mean_dcf, mean_rel, mean_earn]]
    active = [s is not None for s in sigmas]
    n_active = sum(active)

    if n_active == 0:
        return _static_weights(active)

    # Use CV when means available, else raw σ
    raw = []
    for s, m in zip(sigmas, means):
        if s is None:
            raw.append(0)
        elif m is not None and m > 0:
            cv = s / m  # coefficient of variation
            raw.append(1.0 / (cv ** 2) if cv > 0 else 0)
        else:
            raw.append(1.0 / (s ** 2))

    total = sum(raw)
    if total == 0:
        return _static_weights(active)

    weights = [r / total for r in raw]

    # Entropy regularization
    for i in range(3):
        if active[i]:
            weights[i] = weights[i] * (1 - gamma) + gamma / n_active
        else:
            weights[i] = 0

    total = sum(weights)
    weights = [w / total for w in weights] if total > 0 else [0, 0, 0]

    # Apply dynamic floor
    min_weight = min(floor, 1.0 / n_active) if n_active > 0 else floor
    if n_active > 1:
        for i in range(3):
            if weights[i] > 0 and weights[i] < min_weight:
                weights[i] = min_weight
        total = sum(weights)
        weights = [w / total for w in weights]

    return weights


def _static_weights(available):
    static = [DCF_WEIGHT, RELATIVE_WEIGHT, EARNINGS_WEIGHT]
    weights = [s if a else 0 for s, a in zip(static, available)]
    total = sum(weights)
    return [w / total for w in weights] if total > 0 else [0, 0, 0]


def capital_efficiency_multiplier(roic, wacc):
    """
    Sigmoid-based penalty: α = 1 / (1 + exp(-k × spread)), scaled to [0.7, 1.05].

    Smoother than the v2 piecewise function — no jumps at boundaries.
    """
    if roic is None or wacc is None:
        return 1.0

    spread = roic - wacc
    k = 25  # steepness
    raw = 1.0 / (1.0 + np.exp(-k * spread))
    # Scale from sigmoid [0,1] to [0.7, 1.05]
    return 0.7 + raw * 0.35


def ensemble(dcf, relative, earnings):
    """Simple weighted ensemble (static weights). Used for deterministic base case."""
    values, weights = [], []
    if dcf is not None:
        values.append(dcf); weights.append(DCF_WEIGHT)
    if relative is not None:
        values.append(relative); weights.append(RELATIVE_WEIGHT)
    if earnings is not None:
        values.append(earnings); weights.append(EARNINGS_WEIGHT)
    if not values:
        return None
    total_weight = sum(weights)
    return sum(v * w for v, w in zip(values, weights)) / total_weight
