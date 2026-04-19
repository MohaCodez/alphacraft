import sys
from data.ingestion.universe import get_sp500_tickers
from data.ingestion.fundamentals import fetch_fundamentals
from data.ingestion.macro import fetch_macro
from data.store import (init_db, save_universe, save_fundamentals, save_macro,
                        save_features, save_valuation, save_signal)
from features.builder import build_features, compute_sector_medians
from valuation.dcf import run_dcf
from valuation.relative import run_relative
from valuation.earnings import run_earnings
from valuation.ensemble import ensemble, capital_efficiency_multiplier
from simulation.montecarlo import run_simulation, run_ensemble_simulation
from signals.mispricing import compute_signal
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date


def fetch_all_fundamentals(tickers, workers=5):
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
        total_debt = fundamentals.get("total_debt", 0) or 0
        total_cash = fundamentals.get("total_cash", 0) or 0
        sector = fundamentals.get("sector")
        sector_stats = sector_medians.get(sector, {})
        price = fundamentals.get("current_price")
        roic = features.get("roic")
        rr = features.get("reinvestment_rate")
        wacc = features["wacc"]
        cost_of_equity = features["cost_of_equity"]
        growth = features["fcf_growth_rate"]
        long_term_growth = features.get("long_term_growth")
        accrual_ratio = features.get("accrual_ratio")

        # --- DCF (exponential decay, ROIC fade) ---
        dcf_result = run_dcf(fcf, growth, wacc,
                             shares_outstanding=shares, net_debt=net_debt,
                             roic=roic, reinvestment_rate=rr)
        dcf_val = dcf_result["value"] if dcf_result else None
        tv_contribution = dcf_result["tv_contribution"] if dcf_result else None

        if dcf_val and price and dcf_val < price * 0.10:
            dcf_val = None

        # --- Relative (multi-metric, PEG-adjusted, EV bridge) ---
        # Fix 1: Use direct EBITDA, not derived from EV/EBITDA ratio
        ebitda = fundamentals.get("ebitda")

        # Fix 2: BVPS = TotalEquity / Shares (no Price dependency)
        bvps = None
        total_equity = fundamentals.get("total_equity")
        if total_equity and total_equity > 0 and shares and shares > 0:
            bvps = total_equity / shares

        rel_val = run_relative(
            fundamentals.get("pe_trailing"), fundamentals.get("eps_ttm"),
            sector_stats.get("pe", 20),
            pe_forward=fundamentals.get("pe_forward"),
            eps_forward=fundamentals.get("eps_forward"),
            ev_ebitda=fundamentals.get("ev_ebitda"),
            sector_ev_ebitda=sector_stats.get("ev_ebitda", 12),
            ebitda=ebitda,
            total_debt=total_debt,
            cash=total_cash,
            shares_outstanding=shares,
            pb=fundamentals.get("pb"), sector_pb=sector_stats.get("pb", 2.5), bvps=bvps,
            growth_rate=growth,
            sector_growth=sector_stats.get("growth", 0.05),
        )

        # --- Earnings (Gordon Growth, blended horizons) ---
        earn_val = run_earnings(fundamentals.get("eps_forward"), growth,
                                cost_of_equity, long_term_growth=long_term_growth)

        # --- Deterministic ensemble ---
        ens_val = ensemble(dcf_val, rel_val, earn_val)

        # --- Capital efficiency ---
        alpha = capital_efficiency_multiplier(roic, wacc)

        # --- Monte Carlo (combined: DCF + relative + earnings jointly) ---
        sim = run_simulation(fcf, growth, wacc,
                             net_debt=net_debt, shares=shares,
                             roic=roic, reinvestment_rate=rr,
                             sector=sector,
                             rel_val=rel_val, earn_val=earn_val)

        if sim and price and sim["p50"] < price * 0.10:
            sim = None

        if not sim:
            sim = run_ensemble_simulation(dcf_val, rel_val, earn_val,
                                          roic=roic, wacc=wacc)

        # Extract weights if available
        mc_weights = sim.get("weights", [None, None, None]) if sim else [None, None, None]

        save_valuation({
            "ticker": ticker, "run_date": run_dt,
            "dcf": dcf_val, "relative": rel_val, "earnings": earn_val,
            "ensemble": ens_val,
            "p10": sim["p10"] if sim else None,
            "p25": sim.get("p25") if sim else None,
            "p50": sim["p50"] if sim else None,
            "p75": sim.get("p75") if sim else None,
            "p90": sim["p90"] if sim else None,
            "std": sim["std"] if sim else None,
            "skew": sim.get("skew") if sim else None,
            "tv_contribution": tv_contribution,
            "dcf_weight": mc_weights[0],
            "rel_weight": mc_weights[1],
            "earn_weight": mc_weights[2],
            "capital_efficiency_alpha": alpha,
        })

        # --- Signal (with accrual penalty) ---
        signal = compute_signal(price, sim, features["piotroski_score"],
                                accrual_ratio=accrual_ratio)
        if signal:
            signal["ticker"] = ticker
            signal["run_date"] = run_dt
            save_signal(signal)
            return signal
    except Exception as e:
        print(f"\n  {ticker} processing error: {e}")
    return None


def run_pipeline(progress_callback=None):
    def _report(step, total, msg, pct):
        print(msg)
        if progress_callback:
            progress_callback(step, total, msg, pct)

    _report(1, 5, "=== Alphacraft v3 Pipeline ===", 0.0)
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
        print(f"  {s}: P/E={v['pe']:.1f}(±{v['pe_iqr']:.1f})  EV/EBITDA={v['ev_ebitda']:.1f}  P/B={v['pb']:.1f}  g={v['growth']:.1%}")
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
        top = sorted(under, key=lambda x: x["conviction"], reverse=True)[:5]
        print("\n  Top undervalued (by conviction):")
        for s in top:
            print(f"    {s['ticker']:6s} conv={s['conviction']:.3f}  Z={s['mispricing_zscore']:+.2f}"
                  f"  price=${s['current_price']:.0f}  fair=${s['fair_value_p50']:.0f}"
                  f"  DR={s['downside_risk']:.2f}  TA={s.get('tail_asymmetry', 0):.2f}")


if __name__ == "__main__":
    run_pipeline()
