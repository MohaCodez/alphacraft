# valuation/dcf.py

def run_dcf(fcf, growth_rate, wacc, terminal_growth=0.025, projection_years=10, shares_outstanding=1, net_debt=0):
    if not fcf or not wacc or wacc <= terminal_growth:
        return None

    projected_fcf = []
    for t in range(1, projection_years + 1):
        projected_fcf.append(fcf * (1 + growth_rate) ** t / (1 + wacc) ** t)

    terminal_value = (projected_fcf[-1] * (1 + terminal_growth)) / (wacc - terminal_growth)
    terminal_pv = terminal_value / (1 + wacc) ** projection_years

    total_value = sum(projected_fcf) + terminal_pv - net_debt
    return total_value / shares_outstanding if shares_outstanding else total_value