# main.py
from data.ingestion.universe import get_sp500_tickers
from data.ingestion.fundamentals import fetch_fundamentals
from data.ingestion.price import fetch_all_prices
from data.ingestion.macro import fetch_macro
from features.builder import build_features
from valuation.dcf import run_dcf
from valuation.relative import run_relative
from valuation.earnings import run_earnings
from valuation.ensemble import ensemble
from simulation.montecarlo import run_simulation
from signals.mispricing import compute_signal
from data.store import save_signal
from concurrent.futures import ThreadPoolExecutor
from datetime import date

def process_ticker(ticker, macro, sector_medians):
    fundamentals = fetch_fundamentals(ticker)
    if not fundamentals:
        return

    features = build_features(fundamentals, macro, sector_medians)
    fcf = fundamentals.get("fcf")
    shares = fundamentals.get("market_cap", 1) / (fundamentals.get("current_price") or 1)

    dcf = run_dcf(fcf, features["fcf_growth_rate"], features["wacc"], net_debt=fundamentals.get("net_debt", 0), shares_outstanding=shares)
    relative = run_relative(fundamentals.get("pe_trailing"), fundamentals.get("eps_ttm"), sector_medians.get(fundamentals.get("sector"), {}).get("pe", 20), None, None)
    earnings = run_earnings(fundamentals.get("eps_forward"), features["revenue_growth"], macro["treasury_10yr"])
    ens = ensemble(dcf, relative, earnings)
    sim = run_simulation(fcf, features["fcf_growth_rate"], features["wacc"], net_debt=fundamentals.get("net_debt", 0), shares=shares)
    signal = compute_signal(fundamentals.get("current_price"), sim, features["piotroski_score"])

    if signal:
        signal["ticker"] = ticker
        signal["run_date"] = date.today().isoformat()
        save_signal(signal)
        print(f"{ticker} → {signal['signal']} (Z: {signal['mispricing_zscore']})")

def run_pipeline():
    tickers, sectors = get_sp500_tickers()
    macro = fetch_macro()
    sector_medians = {}  # compute from universe on first run

    with ThreadPoolExecutor(max_workers=10) as ex:
        ex.map(lambda t: process_ticker(t, macro, sector_medians), tickers)

if __name__ == "__main__":
    run_pipeline()