CREATE TABLE IF NOT EXISTS universe (
    ticker TEXT PRIMARY KEY,
    sector TEXT,
    added_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw_prices (
    ticker TEXT,
    date DATE,
    close REAL,
    volume INTEGER,
    beta REAL,
    fetched_at TIMESTAMP,
    PRIMARY KEY (ticker, date)
);

CREATE TABLE IF NOT EXISTS raw_fundamentals (
    ticker TEXT PRIMARY KEY,
    eps_ttm REAL,
    eps_forward REAL,
    revenue_growth REAL,
    fcf REAL,
    operating_cash_flow REAL,
    capex REAL,
    net_debt REAL,
    debt_to_equity REAL,
    roe REAL,
    operating_margin REAL,
    pe_trailing REAL,
    pe_forward REAL,
    pb REAL,
    ev_ebitda REAL,
    market_cap REAL,
    shares_outstanding REAL,
    fetched_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw_macro (
    date DATE PRIMARY KEY,
    treasury_10yr REAL,
    cpi REAL,
    fed_funds_rate REAL,
    fetched_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS features (
    ticker TEXT PRIMARY KEY,
    fcf_growth_rate REAL,
    revenue_growth REAL,
    wacc REAL,
    cost_of_equity REAL,
    roic REAL,
    reinvestment_rate REAL,
    value_creation_spread REAL,
    fcf_yield REAL,
    pe_vs_sector REAL,
    piotroski_score INTEGER,
    computed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS valuations (
    ticker TEXT,
    run_date DATE,
    dcf_value REAL,
    relative_value REAL,
    earnings_value REAL,
    ensemble_value REAL,
    p10 REAL,
    p25 REAL,
    p50 REAL,
    p75 REAL,
    p90 REAL,
    fair_value_std REAL,
    fair_value_skew REAL,
    tv_contribution REAL,
    dcf_weight REAL,
    rel_weight REAL,
    earn_weight REAL,
    capital_efficiency_alpha REAL,
    PRIMARY KEY (ticker, run_date)
);

CREATE TABLE IF NOT EXISTS signals (
    ticker TEXT,
    run_date DATE,
    current_price REAL,
    fair_value_p50 REAL,
    fair_value_p10 REAL,
    fair_value_p90 REAL,
    mispricing_zscore REAL,
    signal_percentile REAL,
    downside_risk REAL,
    conviction REAL,
    margin_of_safety REAL,
    ev_gap REAL,
    tail_asymmetry REAL,
    undervalued_prob REAL,
    overvalued_prob REAL,
    quality_flag INTEGER,
    signal TEXT,
    PRIMARY KEY (ticker, run_date)
);
