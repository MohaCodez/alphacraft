# data/ingestion/macro.py
from fredapi import Fred
from config import FRED_API_KEY

def fetch_macro():
    fred = Fred(api_key=FRED_API_KEY)
    return {
        "treasury_10yr": fred.get_series("DGS10").iloc[-1] / 100,
        "cpi": fred.get_series("CPIAUCSL").pct_change(12).iloc[-1],
        "fed_funds_rate": fred.get_series("FEDFUNDS").iloc[-1] / 100,
    }