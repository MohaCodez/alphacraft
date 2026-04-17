import yfinance as yf

def fetch_fundamentals(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        cf = stock.cashflow

        op_cf = capex = None
        if cf is not None and not cf.empty:
            if "Operating Cash Flow" in cf.index:
                op_cf = cf.loc["Operating Cash Flow"].iloc[0]
            if "Capital Expenditure" in cf.index:
                capex = cf.loc["Capital Expenditure"].iloc[0]
        fcf = (op_cf + capex) if op_cf is not None and capex is not None else None

        return {
            "ticker": ticker,
            "eps_ttm": info.get("trailingEps"),
            "eps_forward": info.get("forwardEps"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "fcf": fcf,
            "operating_cash_flow": op_cf,
            "capex": capex,
            "net_debt": (info.get("totalDebt", 0) or 0) - (info.get("totalCash", 0) or 0),
            "debt_to_equity": info.get("debtToEquity"),
            "roe": info.get("returnOnEquity"),
            "operating_margin": info.get("operatingMargins"),
            "pe_trailing": info.get("trailingPE"),
            "pe_forward": info.get("forwardPE"),
            "pb": info.get("priceToBook"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "market_cap": info.get("marketCap"),
            "current_price": info.get("currentPrice"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "sector": info.get("sector"),
            "beta": info.get("beta"),
        }
    except Exception as e:
        print(f"Fundamentals failed for {ticker}: {e}")
        return None
