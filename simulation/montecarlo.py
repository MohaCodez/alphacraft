import numpy as np
from config import MONTE_CARLO_RUNS

def run_simulation(base_fcf, growth_rate, wacc, net_debt=0, shares=1, n=None, terminal_growth=0.025, projection_years=10):
    """FCF-based Monte Carlo — returns None if base_fcf is missing/invalid."""
    if not base_fcf or not shares or base_fcf <= 0:
        return None
    n = n or MONTE_CARLO_RUNS

    sim_growth = np.random.normal(growth_rate, 0.08, n)
    sim_wacc = np.clip(np.random.normal(wacc, 0.015, n), terminal_growth + 0.005, None)

    years = np.arange(1, projection_years + 1)
    growth_factors = (1 + sim_growth[:, None]) ** years
    discount_factors = (1 + sim_wacc[:, None]) ** years
    pv_fcf = base_fcf * growth_factors / discount_factors

    last_pv_fcf = pv_fcf[:, -1]
    tv = last_pv_fcf * (1 + terminal_growth) / (sim_wacc - terminal_growth)
    tv_pv = tv / (1 + sim_wacc) ** projection_years

    total = pv_fcf.sum(axis=1) + tv_pv - net_debt
    fair_values = total / shares

    return _stats(fair_values)

def run_ensemble_simulation(dcf_val, rel_val, earn_val, dcf_w=0.4, rel_w=0.35, earn_w=0.25, n=None):
    """Monte Carlo around ensemble fair value — perturbs each model's output with noise."""
    values, weights = [], []
    for v, w in [(dcf_val, dcf_w), (rel_val, rel_w), (earn_val, earn_w)]:
        if v and v > 0:
            values.append(v)
            weights.append(w)
    if not values:
        return None
    n = n or MONTE_CARLO_RUNS
    total_w = sum(weights)
    weights = [w / total_w for w in weights]

    # Each sim: perturb each model value by ±20% noise, then weighted average
    sims = np.zeros(n)
    for v, w in zip(values, weights):
        noise = np.random.normal(1.0, 0.20, n)  # ±20% uncertainty per model
        sims += v * noise * w

    return _stats(sims)

def _stats(arr):
    arr = arr[np.isfinite(arr)]
    if len(arr) < 100:
        return None
    return {
        "p10": float(np.percentile(arr, 10)),
        "p50": float(np.percentile(arr, 50)),
        "p90": float(np.percentile(arr, 90)),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
    }
