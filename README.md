# Alphacraft

> A probabilistic stock valuation engine that estimates fair value distributions using multi-stage DCF, relative valuation, and correlated Monte Carlo simulation.

---

## What It Does

Alphacraft runs a full valuation pipeline across all S&P 500 stocks and ranks them by how mispriced they appear relative to their estimated fair value.

Instead of producing a single price target, it models uncertainty — giving you a **fair value range** (P10 to P90), a **conviction score**, and a **percentile-based mispricing signal** that tells you where the current market price sits within the modeled fair value distribution.

The output is a ranked screener with sector analysis, scatter plots, and deep-dive ticker lookup — updated daily.

---

## Why I Built This

Most retail valuation tools give you a single number — "fair value is $142." That's false precision. Every input to a valuation model is uncertain: earnings growth, discount rate, macro conditions. A single number hides all of that uncertainty.

Alphacraft treats valuation as a probability distribution, not a point estimate. The question it answers is:

> *"Given all available information and uncertainty, what is the probability that this stock is mispriced?"*

---

## How It Works

```
S&P 500 Universe (Wikipedia)
      ↓
Data Ingestion
  → Fundamentals: EPS, FCF, EBITDA, EBIT, balance sheet   (yfinance)
  → Macro: 10yr yield, CPI, fed funds rate                 (FRED API)
      ↓
Feature Engineering
  → Full WACC (debt + equity)
  → ROIC (EBIT-based) + reinvestment rate
  → Smart growth blending (forward EPS implied + trailing)
  → Sector medians with IQR (P/E, EV/EBITDA, P/B, growth)
  → Piotroski F-Score (6-point) + accrual quality
      ↓
Three Valuation Models (independent)
  → Multi-stage DCF         (exponential decay, ROIC fade, TV haircut)
  → Relative Valuation      (PEG-adjusted P/E + EV/EBITDA + P/B blend)
  → Earnings Model          (Gordon Growth justified P/E, blended horizons)
      ↓
Combined Monte Carlo Simulation
  → 10,000 simulations per stock
  → All three models run jointly per simulation
  → Skewed growth draws, lognormal WACC, regime-based correlation
  → CV-based inverse-variance blending with entropy regularization
  → Capital efficiency adjustment (ROIC-WACC sigmoid)
  → Output: fair value distribution (P10 / P25 / P50 / P75 / P90)
      ↓
Mispricing Detection
  → Percentile-rank signal (distribution-agnostic)
  → Conviction score (symmetric for under/overvalued)
  → EV gap, tail asymmetry, downside risk
  → Quality + accrual filter
      ↓
Dashboard: Screener, Sector Analysis, Scatter Plots, Ticker Lookup
```

For the complete mathematical specification, see **[MATH.md](MATH.md)**.

---

## Project Structure

```
alphacraft/
├── data/
│   ├── ingestion/
│   │   ├── universe.py        # S&P 500 ticker list
│   │   ├── price.py           # price & market data
│   │   ├── fundamentals.py    # EPS, FCF, EBITDA, EBIT, balance sheet
│   │   └── macro.py           # treasury yield, CPI
│   └── store.py               # DB read/write layer
├── features/
│   └── builder.py             # WACC, ROIC, growth, Piotroski, accrual
├── valuation/
│   ├── dcf.py                 # multi-stage DCF with exponential decay
│   ├── relative.py            # PEG-adjusted multi-metric relative
│   ├── earnings.py            # Gordon Growth justified P/E
│   └── ensemble.py            # CV-based inverse-variance + capital efficiency
├── simulation/
│   └── montecarlo.py          # combined correlated Monte Carlo
├── signals/
│   └── mispricing.py          # percentile signal, conviction, EV gap
├── scheduler/
│   └── jobs.py                # APScheduler daily runs
├── dashboard/
│   └── app.py                 # Streamlit + Plotly dashboard
├── db/
│   └── schema.sql
├── config.py                  # all tunable parameters
├── main.py                    # pipeline orchestrator
├── MATH.md                    # complete mathematical specification
└── requirements.txt
```

---

## Stack

| Layer | Technology |
|---|---|
| Data fetching | yfinance, FRED API |
| Computation | Python, NumPy, SciPy |
| Storage | SQLite |
| Dashboard | Streamlit + Plotly |
| Scheduling | APScheduler |
| Parallelism | ThreadPoolExecutor |

---

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/yourusername/alphacraft.git
cd alphacraft
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Add your FRED API key**

Get a free key at [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html), then create a `.env` file:
```
FRED_API_KEY=your_key_here
```

**4. Run the pipeline**
```bash
python3 main.py
```

First run fetches fundamentals for all 500 stocks — expect 15–25 minutes. The database is auto-initialized.

**5. Launch the dashboard**
```bash
streamlit run dashboard/app.py
```

---

## Configuration

All parameters live in `config.py`. Key ones:

| Parameter | Default | Purpose |
|---|---|---|
| `MONTE_CARLO_RUNS` | 10,000 | Simulations per stock |
| `DCF_GROWTH_DECAY_K` | 0.5 | Exponential growth fade speed |
| `DCF_TV_HAIRCUT range` | [0.60, 0.90] | Terminal value confidence discount |
| `MC_GROWTH_SKEW_ALPHA` | -2.0 | Left-tail fatness in growth draws |
| `ENSEMBLE_ENTROPY_GAMMA` | 0.1 | Anti-dominance regularization |
| `UNDERVALUED_PERCENTILE` | 0.15 | Signal threshold |
| `OVERVALUED_PERCENTILE` | 0.85 | Signal threshold |

---

## Data Sources

| Data | Source | Refresh |
|---|---|---|
| Price, beta, multiples | yfinance | Daily |
| FCF, EPS, EBITDA, EBIT, balance sheet | yfinance | Quarterly |
| 10yr treasury yield | FRED API | Weekly |
| CPI, fed funds rate | FRED API | Weekly |
| Sector medians (P/E, EV/EBITDA, P/B) | Computed from universe | Per run |

---

## Limitations & Honest Caveats

- **DCF is assumption-sensitive.** The Monte Carlo layer models this uncertainty explicitly, but small structural changes in growth or WACC still swing results.
- **This is a screening tool, not a prediction system.** A high conviction undervalued signal means a stock looks cheap relative to modeled fundamentals — it does not mean the stock will go up.
- **Optionality is invisible.** Stocks priced for future business lines (TSLA/robotaxi, biotech pipelines) will always look overvalued to a fundamentals model. The model correctly identifies the gap; interpreting it requires judgment.
- **S&P 500 stocks are heavily analyzed.** Persistent mispricing in large-caps is rare. Signals are more meaningful as relative comparisons than absolute calls.
- **yfinance is unofficial.** Occasionally returns missing or stale data. The pipeline handles missing data with fallbacks and model exclusion.
- **Not financial advice.** This is a quantitative modeling project.

---

## Roadmap

- [ ] Backtesting engine — validate historical signals against forward returns
- [ ] Regime switching — adjust model weights and correlation in bull vs bear
- [ ] Jump diffusion — model earnings shock events in MC
- [ ] Volatility clustering — time-varying σ in Monte Carlo
- [ ] Factor decomposition — separate alpha from known risk premia
- [ ] Portfolio-level extension — multi-stock correlation modeling
- [ ] Expand universe to Russell 1000

---

## License

MIT
