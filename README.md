# Alphacraft

> A probabilistic stock valuation engine that estimates fair value ranges using DCF, relative valuation, and Monte Carlo simulation — built by a dev who trades.

---

## What It Does

Alphacraft runs a full valuation pipeline across all S&P 500 stocks and ranks them by how mispriced they appear relative to their estimated fair value.

Instead of producing a single price target, it models uncertainty — giving you a **fair value range** (P10 to P90) and a **mispricing Z-score** that tells you how far the current market price sits from the expected fair value distribution.

The output is a ranked screener: the most undervalued and most overvalued stocks in the S&P 500, updated daily.

---

## Why I Built This

Most retail valuation tools give you a single number — "fair value is $142." That's false precision. Every input to a valuation model is uncertain: earnings growth, discount rate, macro conditions. A single number hides all of that uncertainty.

Alphacraft treats valuation as a probability distribution, not a point estimate. The question it answers is:

> *"Given all available information and uncertainty, what is the probability that this stock is mispriced?"*

---

## How It Works

```
S&P 500 Universe
      ↓
Data Ingestion
  → Price & market data      (yfinance)
  → Fundamentals             (yfinance)
  → Macro indicators         (FRED API)
      ↓
Feature Engineering
  → WACC computation
  → FCF growth rate
  → Sector-relative multiples
  → Piotroski F-Score
      ↓
Valuation Engine  (three independent models)
  → DCF Model                (40% weight)
  → Relative Valuation       (35% weight)
  → Earnings-based Model     (25% weight)
      ↓
Monte Carlo Simulation
  → 10,000 simulations per stock
  → Randomized growth rate, WACC, macro shocks
  → Output: fair value distribution (P10 / P50 / P90)
      ↓
Mispricing Detection
  → Z-score: (Market Price - P50) / σ
  → Undervalued / Overvalued / Fair signal
  → Quality filter via Piotroski Score
      ↓
Ranked Screener + Dashboard
```

---

## Valuation Models

### 1. DCF (Discounted Cash Flow)
Projects free cash flow over 10 years, discounts at WACC, adds terminal value.

```
Intrinsic Value = Σ [FCF_t / (1 + WACC)^t] + Terminal Value
Terminal Value  = FCF_n × (1 + g) / (WACC - g)
WACC            = Risk-Free Rate + β × Equity Risk Premium
```

### 2. Relative Valuation
Compares the stock's P/E against its sector median P/E to estimate a sector-justified price.

### 3. Earnings-Based Model
Uses forward EPS and a growth-justified P/E (Peter Lynch method) to estimate fair value.

```
Justified P/E  = EPS Growth Rate (%)
Fair Value     = Forward EPS × Justified P/E
```

### Monte Carlo Layer
Each of the 10,000 simulations draws:
- FCF growth rate from `N(μ, σ=0.08)`
- WACC from `N(μ, σ=0.015)`

Producing a distribution of fair values, not a single number.

### Mispricing Score
```
Z-Score = (Market Price - P50) / σ(fair value distribution)

Z < -1.5  →  UNDERVALUED
-1.5 to +1.5  →  FAIRLY VALUED
Z > +1.5  →  OVERVALUED
```

---

## Project Structure

```
alphacraft/
├── data/
│   ├── ingestion/
│   │   ├── universe.py        # S&P 500 ticker list
│   │   ├── price.py           # price & market data
│   │   ├── fundamentals.py    # EPS, FCF, ratios
│   │   └── macro.py           # treasury yield, CPI
│   └── store.py               # DB read/write layer
├── features/
│   └── builder.py             # raw → feature transformation
├── valuation/
│   ├── dcf.py
│   ├── relative.py
│   ├── earnings.py
│   └── ensemble.py
├── simulation/
│   └── montecarlo.py
├── signals/
│   └── mispricing.py
├── scheduler/
│   └── jobs.py
├── dashboard/
│   └── app.py
├── db/
│   └── schema.sql
├── config.py
├── main.py
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
| Parallelism | ThreadPoolExecutor, joblib |

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

**4. Initialize the database**
```bash
sqlite3 db/alphacraft.db < db/schema.sql
```

**5. Run the pipeline**
```bash
python main.py
```

First run fetches fundamentals for all 500 stocks — expect 15–25 minutes depending on your connection. Subsequent daily runs are faster (price-only refresh).

**6. Launch the dashboard**
```bash
streamlit run dashboard/app.py
```

---

## Configuration

All key parameters live in `config.py`:

```python
MONTE_CARLO_RUNS = 10000       # simulations per stock
DCF_WEIGHT = 0.40              # ensemble weights
RELATIVE_WEIGHT = 0.35
EARNINGS_WEIGHT = 0.25
UNDERVALUED_THRESHOLD = -1.5   # Z-score cutoffs
OVERVALUED_THRESHOLD = 1.5
```

---

## Data Sources

| Data | Source | Refresh |
|---|---|---|
| Price, beta, multiples | yfinance | Daily |
| FCF, EPS, revenue, debt | yfinance | Quarterly |
| 10yr treasury yield | FRED API | Weekly |
| CPI, fed funds rate | FRED API | Weekly |
| Sector P/E medians | Computed from universe | Weekly |

---

## Limitations & Honest Caveats

- **DCF is assumption-sensitive.** Small changes in growth rate or WACC swing fair value significantly. The Monte Carlo layer partially addresses this by modeling that uncertainty explicitly.
- **This is a screening tool, not a prediction system.** A low Z-score means a stock looks cheap relative to its modeled fundamentals — it does not mean the stock will go up.
- **S&P 500 stocks are heavily analyzed.** Persistent mispricing in large-caps is rare. Signals are more meaningful as relative comparisons than as absolute calls.
- **yfinance is unofficial.** It works well but occasionally returns missing or stale data. The pipeline handles missing data with fallbacks but results for data-sparse stocks should be treated with more skepticism.
- **Not financial advice.** This is a quantitative modeling project. Use it to inform your own research, not as a buy/sell signal.

---

## Roadmap

- [ ] Backtesting engine — validate historical mispricing signals against forward returns
- [ ] Regime switching — adjust model weights in bull vs bear environments
- [ ] Jump diffusion — model earnings shock events
- [ ] Volatility clustering — time-varying σ in Monte Carlo
- [ ] Portfolio-level extension — multi-stock correlation modeling
- [ ] Expand universe to Russell 1000

---

## License

MIT