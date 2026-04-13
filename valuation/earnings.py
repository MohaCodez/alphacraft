# valuation/earnings.py

def run_earnings(eps_forward, growth_rate, risk_free_rate):
    if not eps_forward:
        return None
    # Peter Lynch: justified P/E ≈ growth rate (as percentage)
    growth_pct = (growth_rate or 0.05) * 100
    justified_pe = max(growth_pct, 8)  # floor at 8
    return eps_forward * justified_pe