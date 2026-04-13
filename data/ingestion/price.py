import yfinance as yf
from concurrent.futures import ThreadPoolExecutor

def fetch_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            "ticker" : ticker,
            "current_price" : info.get("currentPrice"),
            "beta": info.get("beta"),
            "market_cap": info.get("marketCap"),
            "52wk_high": info.get("fiftyTwoWeekHigh"),
            "52wk_low": info.get("fiftyTwoWeekLow"),
        }
    except Exception as e:
        print(f"Print fetch failed for {ticker} : {e}")
        return None
    
def fetch_all_prices(tickers, workers=20):
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results =  list(ex.map(fetch_price, tickers))
    return [r for r in results if r is not None]

