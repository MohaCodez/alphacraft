# simulation/montecarlo.py
"""Combined Monte Carlo: simulates DCF + relative + earnings jointly, blends per-simulation."""

import numpy as np
from scipy.stats import skewnorm, norm
from config import (
    MONTE_CARLO_RUNS, MC_GROWTH_SIGMA, MC_WACC_SIGMA,
    MC_GROWTH_MIN, MC_GROWTH_MAX, MC_GROWTH_SKEW_ALPHA,
    MC_RHO_STABLE, MC_RHO_CYCLICAL, MC_RHO_SPECULATIVE, MC_CORRELATION_RHO,
    CYCLICAL_SECTORS, SPECULATIVE_SECTORS,
    DCF_PROJECTION_YEARS, DCF_HIGH_GROWTH_YEARS, DCF_TERMINAL_GROWTH,
    DCF_TV_HAIRCUT_MIN, DCF_TV_HAIRCUT_MAX, DCF_TV_MAX_CONTRIBUTION,
    DCF_GROWTH_DECAY_K, DCF_ROIC_TERMINAL,
)
from valuation.ensemble import inverse_variance_weights, capital_efficiency_multiplier


def _get_sector_rho(sector):
    if sector in SPECULATIVE_SECTORS:
        return MC_RHO_SPECULATIVE
    elif sector in CYCLICAL_SECTORS:
        return MC_RHO_CYCLICAL
    return MC_RHO_STABLE


def _correlated_normals(n, rho):
    z1 = np.random.standard_normal(n)
    z2 = rho * z1 + np.sqrt(1 - rho ** 2) * np.random.standard_normal(n)
    return z1, z2


def _skewed_truncated_draws(z, mu, sigma, lo, hi, alpha):
    u = norm.cdf(z)
    u = np.clip(u, 1e-6, 1 - 1e-6)
    raw = skewnorm.ppf(u, alpha, loc=mu, scale=sigma)
    return np.clip(raw, lo, hi)


def _lognormal_draws(z, target_mean, sigma_ln):
    mu_ln = np.log(target_mean) - 0.5 * sigma_ln ** 2
    return np.exp(mu_ln + sigma_ln * z)


def _growth_schedule_vec(g_high, g_inf, years, fade_start, k,
                         roic=None, reinvestment_rate=None):
    n = len(g_high)
    schedule = np.empty((n, years))
    use_roic = (roic is not None and reinvestment_rate is not None
                and roic > 0 and reinvestment_rate > 0)
    for t in range(years):
        if use_roic:
            m = 0.15
            roic_t = roic * np.exp(-m * t) + DCF_ROIC_TERMINAL * (1 - np.exp(-m * t))
            g_implied = roic_t * reinvestment_rate
        else:
            g_implied = None
        if t < fade_start:
            base = g_high
        else:
            decay = np.exp(-k * (t - fade_start))
            base = g_inf + (g_high - g_inf) * decay
        schedule[:, t] = np.minimum(base, g_implied) if g_implied is not None else base
    return schedule


def _dcf_sim(base_fcf, g_draws, wacc_draws, tv_haircut, net_debt, shares,
             terminal_growth, roic, reinvestment_rate):
    """Vectorized DCF across all simulations. Returns per-share fair values array."""
    years = DCF_PROJECTION_YEARS
    schedule = _growth_schedule_vec(g_draws, terminal_growth, years,
                                    DCF_HIGH_GROWTH_YEARS, DCF_GROWTH_DECAY_K,
                                    roic=roic, reinvestment_rate=reinvestment_rate)
    cum_growth = np.cumprod(1 + schedule, axis=1)
    t_arr = np.arange(1, years + 1)
    discount = (1 + wacc_draws[:, None]) ** t_arr
    pv_fcf = base_fcf * cum_growth / discount
    sum_pv = pv_fcf.sum(axis=1)

    last_fcf = base_fcf * cum_growth[:, -1]
    tv = last_fcf * (1 + terminal_growth) / (wacc_draws - terminal_growth) * tv_haircut
    tv_pv = tv / (1 + wacc_draws) ** years

    total = sum_pv + tv_pv
    tv_frac = np.where(total > 0, tv_pv / total, 0)
    over_cap = tv_frac > DCF_TV_MAX_CONTRIBUTION
    if np.any(over_cap):
        capped_tv = sum_pv[over_cap] * DCF_TV_MAX_CONTRIBUTION / (1 - DCF_TV_MAX_CONTRIBUTION)
        tv_pv[over_cap] = capped_tv
        total[over_cap] = sum_pv[over_cap] + capped_tv

    equity = total - (net_debt or 0)
    return equity / shares


def run_combined_simulation(base_fcf, growth_rate, wacc, net_debt, shares,
                            rel_val, earn_val,
                            n=None, terminal_growth=None,
                            roic=None, reinvestment_rate=None, sector=None):
    """
    Combined Monte Carlo: runs DCF + perturbed relative + perturbed earnings
    in each simulation, then blends with inverse-variance weights.

    This ensures all three models contribute to the fair value distribution,
    not just DCF.
    """
    n = n or MONTE_CARLO_RUNS
    terminal_growth = terminal_growth or DCF_TERMINAL_GROWTH

    # Reinvestment constraint
    g_base = growth_rate
    if roic and reinvestment_rate and roic > 0:
        g_base = min(g_base, roic * reinvestment_rate + 0.02)

    # Correlated draws for DCF
    rho = _get_sector_rho(sector) if sector else MC_CORRELATION_RHO
    z1, z2 = _correlated_normals(n, rho)

    g_draws = _skewed_truncated_draws(z1, g_base, MC_GROWTH_SIGMA,
                                       MC_GROWTH_MIN, MC_GROWTH_MAX,
                                       MC_GROWTH_SKEW_ALPHA)
    wacc_draws = _lognormal_draws(z2, wacc, MC_WACC_SIGMA)
    wacc_draws = np.maximum(wacc_draws, 0.04)  # WACC floor

    per_sim_g_spread = np.abs(g_draws - g_base)
    tv_haircut = np.clip(0.9 - 2.0 * per_sim_g_spread, DCF_TV_HAIRCUT_MIN, DCF_TV_HAIRCUT_MAX)

    # Filter valid sims: g_inf must be < WACC - 0.02
    valid = (terminal_growth + 0.02) < wacc_draws
    g_draws, wacc_draws, tv_haircut = g_draws[valid], wacc_draws[valid], tv_haircut[valid]
    m = len(g_draws)
    if m < 100:
        return None

    # --- DCF path (may be None if no FCF) ---
    dcf_values = None
    if base_fcf and base_fcf > 0 and shares and shares > 0:
        dcf_values = _dcf_sim(base_fcf, g_draws, wacc_draws, tv_haircut,
                              net_debt, shares, terminal_growth, roic, reinvestment_rate)

    # --- Relative path (perturb with ±15% noise — comparables are more stable) ---
    rel_values = None
    if rel_val and rel_val > 0:
        rel_values = rel_val * np.random.normal(1.0, 0.15, m)

    # --- Earnings path (perturb with ±20% noise) ---
    earn_values = None
    if earn_val and earn_val > 0:
        earn_values = earn_val * np.random.normal(1.0, 0.20, m)

    # --- Inverse-variance blend (using CV, not raw σ) ---
    arrays = [dcf_values, rel_values, earn_values]
    active = [a is not None for a in arrays]
    if not any(active):
        return None

    sigmas = [None, None, None]
    means = [None, None, None]
    for i, a in enumerate(arrays):
        if a is not None:
            finite = a[np.isfinite(a)]
            if len(finite) > 0:
                sigmas[i] = float(np.std(finite))
                means[i] = float(np.mean(finite))

    weights = inverse_variance_weights(*sigmas, mean_dcf=means[0], mean_rel=means[1], mean_earn=means[2])

    # Blend per-simulation
    combined = np.zeros(m)
    for i, a in enumerate(arrays):
        if a is not None and weights[i] > 0:
            combined += a * weights[i]

    # Validate weights sum to 1
    assert abs(sum(weights) - 1.0) < 1e-6 or all(w == 0 for w in weights)

    # Capital efficiency
    alpha = capital_efficiency_multiplier(roic, wacc)
    combined *= alpha

    result = _stats(combined)
    if result:
        result["weights"] = weights
    return result


def run_simulation(base_fcf, growth_rate, wacc, net_debt=0, shares=1,
                   n=None, terminal_growth=None, roic=None, reinvestment_rate=None,
                   sector=None, rel_val=None, earn_val=None):
    """
    Main entry point. Runs combined simulation if any model value is available.
    Falls back to DCF-only if no relative/earnings values provided.
    """
    return run_combined_simulation(
        base_fcf, growth_rate, wacc, net_debt, shares,
        rel_val, earn_val,
        n=n, terminal_growth=terminal_growth,
        roic=roic, reinvestment_rate=reinvestment_rate, sector=sector,
    )


def run_ensemble_simulation(dcf_val, rel_val, earn_val, n=None,
                            roic=None, wacc=None):
    """Fallback: MC around deterministic model outputs (no FCF-based DCF path)."""
    entries = []
    for v in [dcf_val, rel_val, earn_val]:
        if v and v > 0:
            entries.append(v)
    if not entries:
        return None

    n = n or MONTE_CARLO_RUNS
    noisy = [v * np.random.normal(1.0, 0.20, n) for v in entries]
    sigmas = [float(np.std(a)) for a in noisy]
    means_arr = [float(np.mean(a)) for a in noisy]
    padded_s = [None, None, None]
    padded_m = [None, None, None]
    for i, (s, m) in enumerate(zip(sigmas, means_arr)):
        padded_s[i] = s
        padded_m[i] = m
    weights = inverse_variance_weights(*padded_s, mean_dcf=padded_m[0], mean_rel=padded_m[1], mean_earn=padded_m[2])

    sims = np.zeros(n)
    wi = 0
    for i in range(3):
        if weights[i] > 0 and wi < len(noisy):
            sims += noisy[wi] * weights[i]
            wi += 1

    alpha = capital_efficiency_multiplier(roic, wacc)
    sims *= alpha
    return _stats(sims)


def _stats(arr):
    arr = arr[np.isfinite(arr) & (arr > 0)]
    if len(arr) < 100:
        return None
    from scipy.stats import skew
    return {
        "p10": float(np.percentile(arr, 10)),
        "p25": float(np.percentile(arr, 25)),
        "p50": float(np.percentile(arr, 50)),
        "p75": float(np.percentile(arr, 75)),
        "p90": float(np.percentile(arr, 90)),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
        "skew": float(skew(arr)),
    }
