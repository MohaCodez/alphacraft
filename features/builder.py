# features/builder.py

def compute_wacc(beta, risk_free_rate, equity_risk_premium=0.055, debt_to_equity=0, tax_rate=0.21, cost_of_debt=0.04):
    cost_of_equity = risk_free_rate + beta * equity_risk_premium
    if debt_to_equity == 0:
        return cost_of_equity
    E = 1 / (1 + debt_to_equity)
    D = debt_to_equity / (1 + debt_to_equity)
    return E * cost_of_equity + D * cost_of_debt * (1 - tax_rate)

def compute_piotroski(fundamentals):
    score = 0
    if fundamentals.get("roe", 0) and fundamentals["roe"] > 0: score += 1
    if fundamentals.get("operating_margin", 0) and fundamentals["operating_margin"] > 0: score += 1
    if fundamentals.get("fcf", 0) and fundamentals["fcf"] > 0: score += 1
    if fundamentals.get("revenue_growth", 0) and fundamentals["revenue_growth"] > 0: score += 1
    if fundamentals.get("debt_to_equity", 1) and fundamentals["debt_to_equity"] < 1: score += 1
    # simplified — full Piotroski has 9 points, expand later
    return score

def build_features(fundamentals, macro, sector_medians):
    ticker = fundamentals["ticker"]
    beta = fundamentals.get("beta") or 1.0
    risk_free = macro["treasury_10yr"]
    wacc = compute_wacc(beta, risk_free, fundamentals.get("debt_to_equity", 0) or 0)
    sector = fundamentals.get("sector")
    sector_pe = sector_medians.get(sector, {}).get("pe", 20)
    pe_vs_sector = ((fundamentals.get("pe_trailing") or sector_pe) - sector_pe) / sector_pe

    return {
        "ticker": ticker,
        "fcf_growth_rate": fundamentals.get("revenue_growth") or 0.05,
        "revenue_growth": fundamentals.get("revenue_growth") or 0.05,
        "wacc": wacc,
        "fcf_yield": (fundamentals["fcf"] / fundamentals["market_cap"]) if fundamentals.get("fcf") and fundamentals.get("market_cap") else None,
        "pe_vs_sector": pe_vs_sector,
        "piotroski_score": compute_piotroski(fundamentals),
    }