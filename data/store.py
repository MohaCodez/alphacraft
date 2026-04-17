import sqlite3
from datetime import datetime, date
from config import DB_PATH


def _conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    """Create tables from schema.sql if they don't exist."""
    import os
    schema_path = os.path.join(os.path.dirname(DB_PATH), "schema.sql")
    with open(schema_path) as f:
        sql = f.read()
    conn = _conn()
    conn.executescript(sql)
    conn.close()


def save_universe(tickers, sector_map):
    conn = _conn()
    now = datetime.now().isoformat()
    conn.executemany(
        "INSERT OR REPLACE INTO universe (ticker, sector, added_at) VALUES (?, ?, ?)",
        [(t, sector_map.get(t), now) for t in tickers],
    )
    conn.commit()
    conn.close()


def get_sector_map():
    conn = _conn()
    rows = conn.execute("SELECT ticker, sector FROM universe").fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


def save_price(data):
    conn = _conn()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO raw_prices (ticker, date, close, volume, beta, fetched_at) VALUES (?, ?, ?, ?, ?, ?)",
        (data["ticker"], date.today().isoformat(), data.get("current_price"), None, data.get("beta"), now),
    )
    conn.commit()
    conn.close()


def save_fundamentals(data):
    conn = _conn()
    now = datetime.now().isoformat()
    conn.execute(
        """INSERT OR REPLACE INTO raw_fundamentals
        (ticker, eps_ttm, eps_forward, revenue_growth, fcf, operating_cash_flow, capex,
         net_debt, debt_to_equity, roe, operating_margin, pe_trailing, pe_forward, pb,
         ev_ebitda, market_cap, shares_outstanding, fetched_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (data["ticker"], data.get("eps_ttm"), data.get("eps_forward"), data.get("revenue_growth"),
         data.get("fcf"), data.get("operating_cash_flow"), data.get("capex"),
         data.get("net_debt"), data.get("debt_to_equity"), data.get("roe"),
         data.get("operating_margin"), data.get("pe_trailing"), data.get("pe_forward"),
         data.get("pb"), data.get("ev_ebitda"), data.get("market_cap"),
         data.get("shares_outstanding"), now),
    )
    conn.commit()
    conn.close()


def save_macro(data):
    conn = _conn()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO raw_macro (date, treasury_10yr, cpi, fed_funds_rate, fetched_at) VALUES (?, ?, ?, ?, ?)",
        (date.today().isoformat(), data.get("treasury_10yr"), data.get("cpi"), data.get("fed_funds_rate"), now),
    )
    conn.commit()
    conn.close()


def save_features(data):
    conn = _conn()
    now = datetime.now().isoformat()
    conn.execute(
        """INSERT OR REPLACE INTO features
        (ticker, fcf_growth_rate, revenue_growth, wacc, cost_of_equity, roic,
         reinvestment_rate, value_creation_spread, fcf_yield, pe_vs_sector,
         piotroski_score, computed_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (data["ticker"], data.get("fcf_growth_rate"), data.get("revenue_growth"),
         data.get("wacc"), data.get("cost_of_equity"), data.get("roic"),
         data.get("reinvestment_rate"), data.get("value_creation_spread"),
         data.get("fcf_yield"), data.get("pe_vs_sector"),
         data.get("piotroski_score"), now),
    )
    conn.commit()
    conn.close()


def save_valuation(data):
    conn = _conn()
    conn.execute(
        """INSERT OR REPLACE INTO valuations
        (ticker, run_date, dcf_value, relative_value, earnings_value, ensemble_value,
         p10, p25, p50, p75, p90, fair_value_std, fair_value_skew,
         tv_contribution, dcf_weight, rel_weight, earn_weight, capital_efficiency_alpha)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (data["ticker"], data["run_date"], data.get("dcf"), data.get("relative"),
         data.get("earnings"), data.get("ensemble"),
         data.get("p10"), data.get("p25"), data.get("p50"), data.get("p75"),
         data.get("p90"), data.get("std"), data.get("skew"),
         data.get("tv_contribution"), data.get("dcf_weight"),
         data.get("rel_weight"), data.get("earn_weight"),
         data.get("capital_efficiency_alpha")),
    )
    conn.commit()
    conn.close()


def save_signal(data):
    conn = _conn()
    conn.execute(
        """INSERT OR REPLACE INTO signals
        (ticker, run_date, current_price, fair_value_p50, fair_value_p10, fair_value_p90,
         mispricing_zscore, signal_percentile, downside_risk, conviction, margin_of_safety,
         ev_gap, tail_asymmetry,
         undervalued_prob, overvalued_prob, quality_flag, signal)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (data["ticker"], data["run_date"], data.get("current_price"), data.get("fair_value_p50"),
         data.get("fair_value_p10"), data.get("fair_value_p90"),
         data.get("mispricing_zscore"), data.get("signal_percentile"),
         data.get("downside_risk"), data.get("conviction"), data.get("margin_of_safety"),
         data.get("ev_gap"), data.get("tail_asymmetry"),
         data.get("undervalued_prob"), data.get("overvalued_prob"),
         data.get("quality_flag"), data.get("signal")),
    )
    conn.commit()
    conn.close()


def get_latest_signals():
    conn = _conn()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM signals WHERE run_date = (SELECT MAX(run_date) FROM signals)"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_full():
    """Join signals + universe + valuations + features for the latest run."""
    conn = _conn()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT s.*, u.sector,
               v.dcf_value, v.relative_value, v.earnings_value, v.ensemble_value,
               v.p25, v.p75, v.fair_value_skew, v.tv_contribution,
               v.capital_efficiency_alpha,
               f.wacc, f.cost_of_equity, f.roic, f.reinvestment_rate,
               f.value_creation_spread, f.fcf_yield, f.fcf_growth_rate,
               f.piotroski_score
        FROM signals s
        LEFT JOIN universe u ON s.ticker = u.ticker
        LEFT JOIN valuations v ON s.ticker = v.ticker AND s.run_date = v.run_date
        LEFT JOIN features f ON s.ticker = f.ticker
        WHERE s.run_date = (SELECT MAX(run_date) FROM signals)
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]
