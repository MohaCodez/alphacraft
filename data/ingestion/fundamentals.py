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

        # Direct from income statement
        ebitda = ebit = net_income = None
        inc = stock.income_stmt
        if inc is not None and not inc.empty:
            if "EBITDA" in inc.index:
                ebitda = inc.loc["EBITDA"].iloc[0]
            if "EBIT" in inc.index:
                ebit = inc.loc["EBIT"].iloc[0]
            if "Net Income" in inc.index:
                net_income = inc.loc["Net Income"].iloc[0]

        # Direct from balance sheet
        total_assets = total_equity = None
        bs = stock.balance_sheet
        if bs is not None and not bs.empty:
            if "Total Assets" in bs.index:
                total_assets = bs.loc["Total Assets"].iloc[0]
            for key in ["Stockholders Equity", "Total Equity Gross Minority Interest"]:
                if key in bs.index:
                    total_equity = bs.loc[key].iloc[0]
                    break

        total_debt = info.get("totalDebt", 0) or 0
        total_cash = info.get("totalCash", 0) or 0

        return {
            "ticker": ticker,
            "eps_ttm": info.get("trailingEps"),
            "eps_forward": info.get("forwardEps"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "fcf": fcf,
            "operating_cash_flow": op_cf,
            "capex": capex,
            "ebitda": ebitda,
            "ebit": ebit,
            "net_income": net_income,
            "total_assets": total_assets,
            "total_equity": total_equity,
            "total_debt": total_debt,
            "total_cash": total_cash,
            "net_debt": total_debt - total_cash,
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
