# simulation/montecarlo.py
import numpy as np

def run_simulation(base_fcf, growth_rate, wacc, net_debt=0, shares=1, n=10000, terminal_growth=0.025, projection_years=10):
    if not base_fcf:
        return None

    sigma_growth = 0.08   # uncertainty in growth rate
    sigma_wacc = 0.015    # uncertainty in discount rate

    fair_values = []

    for _ in range(n):
        sim_growth = np.random.normal(growth_rate, sigma_growth)
        sim_wacc = max(np.random.normal(wacc, sigma_wacc), terminal_growth + 0.01)

        projected = []
        for t in range(1, projection_years + 1):
            projected.append(base_fcf * (1 + sim_growth) ** t / (1 + sim_wacc) ** t)

        tv = (projected[-1] * (1 + terminal_growth)) / (sim_wacc - terminal_growth)
        tv_pv = tv / (1 + sim_wacc) ** projection_years

        total = sum(projected) + tv_pv - net_debt
        fair_values.append(total / shares if shares else total)

    arr = np.array(fair_values)
    return {
        "p10": np.percentile(arr, 10),
        "p50": np.percentile(arr, 50),
        "p90": np.percentile(arr, 90),
        "mean": np.mean(arr),
        "std": np.std(arr),
        "distribution": arr.tolist()
    }