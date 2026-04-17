import pandas as pd
import requests
from io import StringIO

def get_sp500_tickers():
    """Fetch S&P 500 tickers and sectors from Wikipedia. Returns (tickers, sector_map)."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    resp = requests.get(url, headers={"User-Agent": "alphacraft/1.0"})
    resp.raise_for_status()
    table = pd.read_html(StringIO(resp.text))[0]
    table["Symbol"] = table["Symbol"].str.replace(".", "-", regex=False)
    tickers = table["Symbol"].tolist()
    sector_map = dict(zip(table["Symbol"], table["GICS Sector"]))
    return tickers, sector_map
