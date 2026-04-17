from collections import defaultdict
import numpy as np
from config import EQUITY_RISK_PREMIUM, ACCRUAL_PENALTY_THRESHOLD


def compute_wacc(beta, risk_free_rate, equity_risk_premium=None,
                 debt_to_equity=0, tax_rate=0.21, cost_of_debt=0.04):
    erp = equity_risk_premium or EQUITY_RISK_PREMIUM
    cost_of_equity = risk_free_rate + beta * erp
    if debt_to_equity == 0:
        return cost_of_equity
    E = 1 / (1 + debt_to_equity)
    D = debt_to_equity / (1 + debt_to_equity)
    return E * cost_of_equity + D * cost_of_debt * (1 - tax_rate)


def compute_cost_of_equity(beta, risk_free_rate, equity_risk_premium=None):
    erp = equity_risk_premium or EQUITY_RISK_PREMIUM
    return risk_free_rate + beta * erp


def compute_roic(fundamentals):
    op_income = fundamentals.get("operating_cash_flow")
    tax_rate = 0.21
    if not op_income or op_income <= 0:
        return None
    nopat = op_income * (1 - tax_rate)

    total_debt = fundamentals.get("net_debt", 0) or 0
    market_cap = fundamentals.get("market_cap")
    if not market_cap:
        return None

    bvps = fundamentals.get("pb")
    shares = fundamentals.get("shares_outstanding")
    if bvps and shares and bvps > 0:
        equity_book = market_cap / bvps
        invested = equity_book + max(total_debt, 0)
    else:
        invested = market_cap + max(total_debt, 0)

    if invested <= 0:
        return None
    return nopat / invested


def compute_reinvestment_rate(fundamentals):
    fcf = fundamentals.get("fcf")
    op_cf = fundamentals.get("operating_cash_flow")
    if not op_cf or op_cf <= 0 or fcf is None:
        return None
    nopat = op_cf * (1 - 0.21)
    if nopat <= 0:
        return None
    rr = 1 - (fcf / nopat)
    return max(0, min(rr, 1.0))


def compute_accrual_ratio(fundamentals):
    """Accrual = (Net Income - FCF) / Total Assets. High = accounting noise."""
    # Proxy: use operating_cash_flow as rough net income proxy, FCF as cash
    # Better: net_income field, but yfinance doesn't always have it cleanly
    # Use: accrual ≈ (operating_cf - fcf) / market_cap as a rough proxy
    op_cf = fundamentals.get("operating_cash_flow")
    fcf = fundamentals.get("fcf")
    mcap = fundamentals.get("market_cap")
    if not op_cf or not fcf or not mcap or mcap <= 0:
        return None
    # (op_cf - fcf) = capex (already negative in yfinance), so this is |capex|/mcap
    # More useful: compare earnings quality
    # net_income proxy = eps_ttm × shares
    eps = fundamentals.get("eps_ttm")
    shares = fundamentals.get("shares_outstanding")
    if eps and shares and shares > 0:
        net_income = eps * shares
        accrual = (net_income - fcf) / mcap
        return accrual
    return None


def compute_piotroski(fundamentals):
    score = 0
    if (fundamentals.get("roe") or 0) > 0: score += 1
    if (fundamentals.get("operating_margin") or 0) > 0: score += 1
    if (fundamentals.get("fcf") or 0) > 0: score += 1
    if (fundamentals.get("revenue_growth") or 0) > 0: score += 1
    if (fundamentals.get("debt_to_equity") or 999) < 100: score += 1

    # Bonus: accrual quality (FCF > net income = good)
    eps = fundamentals.get("eps_ttm")
    shares = fundamentals.get("shares_outstanding")
    fcf = fundamentals.get("fcf")
    if eps and shares and fcf:
        net_income = eps * shares
        if fcf > net_income:
            score += 1  # cash earnings > accrual earnings

    return min(score, 9)


def compute_sector_medians(all_fundamentals):
    """Compute median + IQR for P/E, EV/EBITDA, P/B, and growth per sector."""
    sector_data = defaultdict(lambda: {"pe": [], "ev_ebitda": [], "pb": [], "growth": []})
    for f in all_fundamentals:
        if not f or not f.get("sector"):
            continue
        s = f["sector"]
        if f.get("pe_trailing") and 0 < f["pe_trailing"] < 200:
            sector_data[s]["pe"].append(f["pe_trailing"])
        if f.get("ev_ebitda") and 0 < f["ev_ebitda"] < 100:
            sector_data[s]["ev_ebitda"].append(f["ev_ebitda"])
        if f.get("pb") and 0 < f["pb"] < 50:
            sector_data[s]["pb"].append(f["pb"])
        if f.get("revenue_growth"):
            sector_data[s]["growth"].append(f["revenue_growth"])

    result = {}
    for s, d in sector_data.items():
        def _med_iqr(arr, default_med):
            if not arr:
                return default_med, 0
            return float(np.median(arr)), float(np.percentile(arr, 75) - np.percentile(arr, 25))

        pe_med, pe_iqr = _med_iqr(d["pe"], 20)
        ev_med, ev_iqr = _med_iqr(d["ev_ebitda"], 12)
        pb_med, pb_iqr = _med_iqr(d["pb"], 2.5)
        g_med, _ = _med_iqr(d["growth"], 0.05)

        result[s] = {
            "pe": pe_med, "pe_iqr": pe_iqr,
            "ev_ebitda": ev_med, "ev_ebitda_iqr": ev_iqr,
            "pb": pb_med, "pb_iqr": pb_iqr,
            "growth": g_med,
        }
    return result


def build_features(fundamentals, macro, sector_medians):
    ticker = fundamentals["ticker"]
    beta = fundamentals.get("beta") or 1.0
    risk_free = macro.get("treasury_10yr", 0.045)

    d_e_raw = fundamentals.get("debt_to_equity") or 0
    d_e = d_e_raw / 100 if d_e_raw > 5 else d_e_raw

    cost_of_debt = risk_free + 0.02
    wacc = compute_wacc(beta, risk_free, debt_to_equity=d_e, cost_of_debt=cost_of_debt)
    cost_of_equity = compute_cost_of_equity(beta, risk_free)

    sector = fundamentals.get("sector")
    sector_stats = sector_medians.get(sector, {})
    sector_pe = sector_stats.get("pe", 20)
    stock_pe = fundamentals.get("pe_trailing") or sector_pe
    pe_vs_sector = (stock_pe - sector_pe) / sector_pe if sector_pe else 0

    fcf_yield = None
    if fundamentals.get("fcf") and fundamentals.get("market_cap"):
        fcf_yield = fundamentals["fcf"] / fundamentals["market_cap"]

    # --- Smart growth estimation ---
    # 1. Trailing revenue growth (backward-looking, can be noisy)
    trailing_g = fundamentals.get("revenue_growth") or 0

    # 2. Implied earnings growth from forward vs trailing EPS
    #    If forward EPS >> trailing EPS, analysts expect a big jump
    eps_fwd = fundamentals.get("eps_forward")
    eps_ttm = fundamentals.get("eps_ttm")
    implied_eps_g = None
    if eps_fwd and eps_ttm and eps_ttm > 0 and eps_fwd > 0:
        implied_eps_g = (eps_fwd / eps_ttm) - 1  # e.g., 2.77/1.09 - 1 = 1.54

    # 3. Blend: prefer forward-implied when available, temper with trailing
    if implied_eps_g is not None and implied_eps_g > trailing_g:
        # Forward consensus is more optimistic than trailing — weight it heavily
        # But cap the implied growth to avoid absurd numbers (e.g., EPS going from $0.01 to $1)
        implied_eps_g_capped = min(implied_eps_g, 1.0)  # cap at 100% YoY
        blended_growth = 0.6 * implied_eps_g_capped + 0.4 * max(trailing_g, 0)
    elif trailing_g > 0:
        blended_growth = trailing_g
    else:
        # Both negative or missing — use trailing but don't let it go too negative
        blended_growth = max(trailing_g, -0.05)

    # Final cap
    capped_growth = max(min(blended_growth, 0.40), -0.10)

    # Long-term growth: fade toward GDP-like growth, but floor at 2% for profitable companies
    if capped_growth > 0:
        long_term_growth = min(capped_growth * 0.4, 0.04)
        long_term_growth = max(long_term_growth, 0.02)
    else:
        long_term_growth = 0.02

    roic = compute_roic(fundamentals)
    reinvestment_rate = compute_reinvestment_rate(fundamentals)
    value_creation_spread = (roic - wacc) if roic else None
    accrual_ratio = compute_accrual_ratio(fundamentals)

    return {
        "ticker": ticker,
        "fcf_growth_rate": capped_growth,
        "long_term_growth": long_term_growth,
        "revenue_growth": capped_growth,
        "wacc": wacc,
        "cost_of_equity": cost_of_equity,
        "roic": roic,
        "reinvestment_rate": reinvestment_rate,
        "value_creation_spread": value_creation_spread,
        "accrual_ratio": accrual_ratio,
        "fcf_yield": fcf_yield,
        "pe_vs_sector": pe_vs_sector,
        "piotroski_score": compute_piotroski(fundamentals),
    }
