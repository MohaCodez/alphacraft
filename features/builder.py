def compute_wacc(beta, risk_free_rate, equity_risk_premium=0.055, debt_to_equity=0, tax_rate=0.21, cost_of_debt=0.04):
    cost_of_equity = risk_free_rate + beta * equity_risk_premium
    if debt_to_equity == 0:
        return cost_of_equity
    E = 1 / (1 + debt_to_equity)
    D = debt_to_equity / (1 + debt_to_equity)
    return E * cost_of_equity + D * cost_of_debt * (1 - tax_rate)

def compute_piotroski(fundamentals):
    score = 0
    if (fundamentals.get("roe") or 0) > 0: score += 1
    if (fundamentals.get("operating_margin") or 0) > 0: score += 1
    if (fundamentals.get("fcf") or 0) > 0: score += 1
    if (fundamentals.get("revenue_growth") or 0) > 0: score += 1
    if (fundamentals.get("debt_to_equity") or 999) < 1: score += 1
    return score

def compute_sector_medians(all_fundamentals):
    """Compute median P/E per sector from all fetched fundamentals."""
    from collections import defaultdict
    import numpy as np
    sector_pes = defaultdict(list)
    for f in all_fundamentals:
        if f and f.get("sector") and f.get("pe_trailing") and f["pe_trailing"] > 0:
            sector_pes[f["sector"]].append(f["pe_trailing"])
    return {s: {"pe": float(np.median(v))} for s, v in sector_pes.items()}

def build_features(fundamentals, macro, sector_medians):
    ticker = fundamentals["ticker"]
    beta = fundamentals.get("beta") or 1.0
    risk_free = macro.get("treasury_10yr", 0.045)
    d_e = (fundamentals.get("debt_to_equity") or 0) / 100  # yfinance returns as percentage
    wacc = compute_wacc(beta, risk_free, debt_to_equity=d_e)

    sector = fundamentals.get("sector")
    sector_pe = sector_medians.get(sector, {}).get("pe", 20)
    stock_pe = fundamentals.get("pe_trailing") or sector_pe
    pe_vs_sector = (stock_pe - sector_pe) / sector_pe if sector_pe else 0

    fcf_yield = None
    if fundamentals.get("fcf") and fundamentals.get("market_cap"):
        fcf_yield = fundamentals["fcf"] / fundamentals["market_cap"]

    raw_growth = fundamentals.get("revenue_growth") or 0.05
    # Cap growth rate: no stock sustains >40% FCF growth for 10 years
    capped_growth = max(min(raw_growth, 0.40), -0.10)

    return {
        "ticker": ticker,
        "fcf_growth_rate": capped_growth,
        "revenue_growth": capped_growth,
        "wacc": wacc,
        "fcf_yield": fcf_yield,
        "pe_vs_sector": pe_vs_sector,
        "piotroski_score": compute_piotroski(fundamentals),
    }
