-- db/schema.sql

CREATE TABLE universe (
    ticker TEXT PRIMARY KEY,
    sector TEXT,
    added_at TIMESTAMP
);

CREATE TABLE raw_prices (
    ticker TEXT,
    date DATE,
    close REAL,
    volume INTEGER,
    beta REAL,
    fetched_at TIMESTAMP
);

CREATE TABLE raw_fundamentals (
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
    fetched_at TIMESTAMP
);

CREATE TABLE raw_macro (
    date DATE PRIMARY KEY,
    treasury_10yr REAL,
    cpi REAL,
    fed_funds_rate REAL,
    fetched_at TIMESTAMP
);

CREATE TABLE features (
    ticker TEXT PRIMARY KEY,
    fcf_growth_rate REAL,
    revenue_growth REAL,
    wacc REAL,
    fcf_yield REAL,
    pe_vs_sector REAL,
    piotroski_score INTEGER,
    computed_at TIMESTAMP
);

CREATE TABLE valuations (
    ticker TEXT,
    run_date DATE,
    dcf_value REAL,
    relative_value REAL,
    earnings_value REAL,
    ensemble_value REAL,
    p10 REAL,
    p50 REAL,
    p90 REAL,
    fair_value_std REAL,
    PRIMARY KEY (ticker, run_date)
);

CREATE TABLE signals (
    ticker TEXT,
    run_date DATE,
    current_price REAL,
    fair_value_p50 REAL,
    mispricing_zscore REAL,
    undervalued_prob REAL,
    overvalued_prob REAL,
    quality_flag INTEGER,
    signal TEXT,
    PRIMARY KEY (ticker, run_date)
);