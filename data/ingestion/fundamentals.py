import yfinance as yf

def fetch_fundamentals(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        cf = stock.cashflow

        # FCF = Operating Cash FLow - Capex
        op_cf = cf.loc["Operating Cash Flow"].iloc[0] if "Operating Cash FLow" in cf.index else None
        capex = cf.loc["Capital Expenditure"].iloc[0] if "Capital Expenditure" in cf.index else None
        fcf = (op_cf + capex) if op_cf else None

        return {
            "ticker": ticker,
            "eps_ttm": info.get("trailingEps"),
            "eps_forward": info.get("forwardEps"),
            "revenue_growth": info.get("revenueGrowth"),
            "fcf": fcf,
            "net_debt": (info.get("totalDebt", 0) or 0) - (info.get("totalCash", 0) or 0),
            "debt_to_equity": info.get("debtToEquity"),
            "roe": info.get("returnOnEquity"),
            "operating_margin": info.get("operatingMargins"),
            "pe_trailing": info.get("trailingPE"),
            "pe_forward": info.get("forwardPE"),
            "pb": info.get("priceToBook"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "market_cap": info.get("marketCap"),
        }
    
    except Exception as e:
        print(f"Fundamentals failed for {ticker} : {e}")
        return None
    