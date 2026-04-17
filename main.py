import sys
from data.ingestion.universe import get_sp500_tickers
from data.ingestion.fundamentals import fetch_fundamentals
from data.ingestion.macro import fetch_macro
from data.store import init_db, save_universe, save_fundamentals, save_macro, save_features, save_valuation, save_signal
from features.builder import build_features, compute_sector_medians
from valuation.dcf import run_dcf
from valuation.relative import run_relative
from valuation.earnings import run_earnings
from valuation.ensemble import ensemble
from simulation.montecarlo import run_simulation, run_ensemble_simulation
from signals.mispricing import compute_signal
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

def fetch_all_fundamentals(tickers, workers=20):
    results = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(fetch_fundamentals, t): t for t in tickers}
        for i, future in enumerate(as_completed(futures), 1):
            t = futures[future]
            try:
                r = future.result()
                if r:
                    results.append(r)
                    save_fundamentals(r)
                sys.stdout.write(f"\r  Fetched {i}/{len(tickers)} fundamentals")
                sys.stdout.flush()
            except Exception as e:
                print(f"\n  {t} error: {e}")
    print()
    return results

def process_stock(fundamentals, macro, sector_medians, run_dt):
    ticker = fundamentals["ticker"]
    try:
        features = build_features(fundamentals, macro, sector_medians)
        save_features(features)

        fcf = fundamentals.get("fcf")
        shares = fundamentals.get("shares_outstanding")
        if not shares and fundamentals.get("market_cap") and fundamentals.get("current_price"):
            shares = fundamentals["market_cap"] / fundamentals["current_price"]
        if not shares:
            return None
        net_debt = fundamentals.get("net_debt", 0) or 0
        sector = fundamentals.get("sector")
        sector_pe = sector_medians.get(sector, {}).get("pe", 20)

        dcf_val = run_dcf(fcf, features["fcf_growth_rate"], features["wacc"],
                          shares_outstanding=shares, net_debt=net_debt)
        rel_val = run_relative(fundamentals.get("pe_trailing"), fundamentals.get("eps_ttm"),
                               sector_pe, fundamentals.get("pe_forward"), fundamentals.get("eps_forward"))
        earn_val = run_earnings(fundamentals.get("eps_forward"), features["revenue_growth"],
                                macro.get("treasury_10yr", 0.045))
        # Sanity: discard DCF if negative or <10% of current price
        price = fundamentals.get("current_price")
        if dcf_val and price and dcf_val < price * 0.10:
            dcf_val = None

        ens_val = ensemble(dcf_val, rel_val, earn_val)

        # Primary: FCF-based MC. Fallback: ensemble-based MC.
        sim = run_simulation(fcf, features["fcf_growth_rate"], features["wacc"],
                             net_debt=net_debt, shares=shares)
        # If FCF MC gives unreasonable result, fall back to ensemble MC
        if sim and price and sim["p50"] < price * 0.10:
            sim = None
        if not sim:
            sim = run_ensemble_simulation(dcf_val, rel_val, earn_val)

        save_valuation({"ticker": ticker, "run_date": run_dt, "dcf": dcf_val,
                        "relative": rel_val, "earnings": earn_val, "ensemble": ens_val,
                        "p10": sim["p10"] if sim else None, "p50": sim["p50"] if sim else None,
                        "p90": sim["p90"] if sim else None, "std": sim["std"] if sim else None})

        signal = compute_signal(fundamentals.get("current_price"), sim, features["piotroski_score"])
        if signal:
            signal["ticker"] = ticker
            signal["run_date"] = run_dt
            save_signal(signal)
            return signal
    except Exception as e:
        print(f"\n  {ticker} processing error: {e}")
    return None

def run_pipeline(progress_callback=None):
    """Run the full valuation pipeline.

    Args:
        progress_callback: Optional callable(step, total_steps, message, pct)
            where pct is 0.0-1.0 overall progress. Used by the dashboard for live updates.
    """
    def _report(step, total, msg, pct):
        print(msg)
        if progress_callback:
            progress_callback(step, total, msg, pct)

    _report(1, 5, "=== Alphacraft Pipeline ===", 0.0)
    init_db()

    _report(1, 5, "[1/5] Fetching S&P 500 universe...", 0.02)
    tickers, sector_map = get_sp500_tickers()
    save_universe(tickers, sector_map)
    _report(1, 5, f"  {len(tickers)} tickers loaded", 0.05)

    _report(2, 5, "[2/5] Fetching macro data...", 0.06)
    try:
        macro = fetch_macro()
    except Exception:
        print("  FRED API failed — using defaults")
        macro = {"treasury_10yr": 0.045, "cpi": 0.03, "fed_funds_rate": 0.05}
    save_macro(macro)
    _report(2, 5, f"  10yr: {macro['treasury_10yr']:.3f}, CPI: {macro['cpi']:.3f}", 0.10)

    _report(3, 5, "[3/5] Fetching fundamentals (this takes a while)...", 0.11)
    all_fundamentals = fetch_all_fundamentals(tickers)
    _report(3, 5, f"  Got data for {len(all_fundamentals)}/{len(tickers)} stocks", 0.50)

    _report(4, 5, "[4/5] Computing sector medians...", 0.51)
    sector_medians = compute_sector_medians(all_fundamentals)
    for s, v in sorted(sector_medians.items()):
        print(f"  {s}: median P/E = {v['pe']:.1f}")
    _report(4, 5, "  Sector medians computed", 0.55)

    _report(5, 5, "[5/5] Running valuation + Monte Carlo + signals...", 0.56)
    run_dt = date.today().isoformat()
    signals = []
    total = len(all_fundamentals)
    for i, f in enumerate(all_fundamentals, 1):
        sig = process_stock(f, macro, sector_medians, run_dt)
        if sig:
            signals.append(sig)
        pct = 0.56 + 0.44 * (i / total)
        if progress_callback:
            progress_callback(5, 5, f"  Processed {i}/{total} — {f.get('ticker', '?')}", pct)
        sys.stdout.write(f"\r  Processed {i}/{total}")
        sys.stdout.flush()
    print()

    under = [s for s in signals if s["signal"] == "UNDERVALUED"]
    over = [s for s in signals if s["signal"] == "OVERVALUED"]
    _report(5, 5, f"Done — {len(signals)} signals | {len(under)} undervalued | {len(over)} overvalued", 1.0)
    if under:
        top = sorted(under, key=lambda x: x["mispricing_zscore"])[:5]
        print("\n  Top undervalued:")
        for s in top:
            print(f"    {s['ticker']:6s} Z={s['mispricing_zscore']:+.2f}  price=${s['current_price']:.0f}  fair=${s['fair_value_p50']:.0f}")

if __name__ == "__main__":
    run_pipeline()
