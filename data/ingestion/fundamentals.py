import yfinance as yf
import time


def _safe_lookup(df, key):
    """Safely get a value from a DataFrame index, handling None/empty/missing."""
    try:
        if df is not None and not df.empty and key in df.index:
            return df.loc[key].iloc[0]
    except Exception:
        pass
    return None


def fetch_fundamentals(ticker, max_retries=2):
    for attempt in range(max_retries + 1):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info or {}

            # Rate-limit guard: if info is empty/error, back off and retry
            if not info or "trailingPE" not in info:
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
                    continue
                # Last attempt — use whatever we got
                if not info:
                    return None

            cf = stock.cashflow
            op_cf = _safe_lookup(cf, "Operating Cash Flow")
            capex = _safe_lookup(cf, "Capital Expenditure")
            fcf = (op_cf + capex) if op_cf is not None and capex is not None else None

            # Income statement (wrapped — can 401)
            try:
                inc = stock.income_stmt
            except Exception:
                inc = None
            ebitda = _safe_lookup(inc, "EBITDA")
            ebit = _safe_lookup(inc, "EBIT")
            net_income = _safe_lookup(inc, "Net Income")

            # Balance sheet (wrapped — can 401)
            try:
                bs = stock.balance_sheet
            except Exception:
                bs = None
            total_assets = _safe_lookup(bs, "Total Assets")
            total_equity = (_safe_lookup(bs, "Stockholders Equity")
                           or _safe_lookup(bs, "Total Equity Gross Minority Interest"))

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
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            print(f"Fundamentals failed for {ticker}: {e}")
            return None
