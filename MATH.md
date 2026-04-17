# Alphacraft — Mathematical Specification

*Every formula below maps directly to implemented code.*

---

## 0. Notation & Data Sources

| Symbol | Definition | Source |
|---|---|---|
| FCF₀ | Most recent annual free cash flow | Operating CF + CapEx (yfinance) |
| EPS_ttm | Trailing twelve-month EPS | yfinance |
| EPS_fwd | Consensus forward EPS | yfinance |
| Rf | 10-year US Treasury yield | FRED DGS10 |
| β | Stock beta vs S&P 500 | yfinance |
| D | Total debt | yfinance balance sheet |
| Cash | Total cash and equivalents | yfinance |
| NetDebt | D − Cash | Derived |
| E_mkt | Market capitalization | yfinance |
| Rd | Cost of debt = Rf + 0.02 | Derived |
| T | Tax rate = 0.21 | Constant |
| N | Shares outstanding | yfinance |
| EBITDA | Earnings before interest, taxes, depreciation, amortization | yfinance income statement (direct) |
| EBIT | Earnings before interest and taxes | yfinance income statement (direct) |
| BVPS | Book value per share = Total Equity / N | yfinance balance sheet |
| ERP | Equity risk premium = 0.055 | Constant |

---

## 1. Feature Engineering

### 1.1 WACC

```
WACC = (E/(D+E)) × (Rf + β × ERP) + (D/(D+E)) × Rd × (1 − T)
```

If D/E = 0: WACC = Rf + β × ERP.

### 1.2 Cost of Equity

```
r = Rf + β × ERP
```

### 1.3 ROIC

```
NOPAT = EBIT × (1 − T)
Invested Capital = Total Equity + max(NetDebt, 0)
ROIC = NOPAT / Invested Capital
```

Fallback if EBIT missing: NOPAT = Operating Cash Flow × (1 − T).

### 1.4 Reinvestment Rate

```
RR = 1 − (FCF / NOPAT)
Clamped to [0, 1]
```

### 1.5 Smart Growth Estimation

```
trailing_g = reported revenue growth
implied_eps_g = (EPS_fwd / EPS_ttm) − 1     (capped at 100%)

If implied_eps_g > trailing_g:
    g = 0.6 × min(implied_eps_g, 1.0) + 0.4 × max(trailing_g, 0)
Elif trailing_g > 0:
    g = trailing_g
Else:
    g = max(trailing_g, −0.05)

Final: g = clamp(g, −0.10, 0.40)
```

Long-term growth:

```
g_long = clamp(g × 0.4, 0.02, 0.04)
```

### 1.6 Accrual Ratio

```
Accrual = (Net Income − FCF) / Total Assets
```

High |accrual| > 10% flags accounting noise → 30% conviction penalty.

### 1.7 Piotroski F-Score (6-point)

```
+1 if ROE > 0
+1 if Operating Margin > 0
+1 if FCF > 0
+1 if Revenue Growth > 0
+1 if D/E < 100%
+1 if FCF > Net Income
```

### 1.8 Sector Medians

Computed from S&P 500 universe per sector (with outlier filtering):

```
PE_sector      = median(PE_trailing)      where 0 < PE < 200
EV/EBITDA_sec  = median(EV/EBITDA)        where 0 < EV/EBITDA < 100
PB_sector      = median(P/B)              where 0 < P/B < 50
g_sector       = median(revenue_growth)
PE_IQR         = P75(PE) − P25(PE)
```

---

## 2. DCF Model — Multi-Stage with Exponential Decay

### 2.1 Growth Schedule

Years 1–5 (high growth):

```
g_t = min(g_high, ROIC_t × RR)
```

Years 6–10 (exponential decay):

```
g_t = g_∞ + (g_high − g_∞) × exp(−k × (t − 5))
```

k = 0.5 (decay constant). Constrained: `g_t = min(g_base_t, ROIC_t × RR)`.

### 2.2 ROIC Mean-Reversion

```
ROIC_t = ROIC₀ × exp(−m × t) + ROIC_terminal × (1 − exp(−m × t))

m = 0.15              (mean-reversion speed)
ROIC_terminal = 0.08  (long-run convergence)
```

### 2.3 Reinvestment Constraint

```
g_high ≤ ROIC × RR + 0.02
```

### 2.4 Projected FCF

```
FCF_t = FCF₀ × ∏(1 + g_i)  for i = 1..t
```

### 2.5 Present Value

```
PV = Σ [FCF_t / (1 + WACC)^t]  for t = 1..10
```

### 2.6 Terminal Value

```
TV = FCF₁₀ × (1 + g_∞) / (WACC − g_∞) × λ

λ ∈ [0.60, 0.90]  (terminal confidence haircut)
TV_PV = TV / (1 + WACC)^10
```

Constraints:

```
g_∞ < WACC − 0.02  (enforced; auto-corrected if violated)
TV_PV / Total ≤ 0.75  (capped mechanically)
```

### 2.7 Intrinsic Value

```
V_DCF = (PV + TV_PV − NetDebt) / N
```

---

## 3. Relative Valuation — Multi-Metric PEG-Adjusted

### 3.1 PEG-Adjusted P/E

```
PEG_adj = clamp(g_stock / g_sector, 0.5, 2.0)
V_PE = EPS × PE_sector × PEG_adj
```

### 3.2 EV/EBITDA → Per-Share Equity

```
Implied EV = EBITDA × (EV/EBITDA)_sector
Equity = Implied EV − Debt − Minority Interest − Leases + Cash
V_EV = Equity / N
```

EBITDA sourced directly from income statement. If missing, this component is excluded and weights renormalize.

### 3.3 P/B

```
V_PB = BVPS × (P/B)_sector

BVPS = Total Equity / N    (no Price dependency)
```

### 3.4 Weighted Blend

```
V_rel = (0.50 × V_PE + 0.35 × V_EV + 0.15 × V_PB) / Σ active weights
```

Only available metrics participate.

---

## 4. Earnings Model — Gordon Growth

### 4.1 Blended Growth

```
g = 0.6 × g_short + 0.4 × g_long
```

### 4.2 Stabilized Growth

```
g_adj = min(g, r − δ)       δ = 0.02
g_adj = max(g_adj, 0.01)
```

### 4.3 Justified P/E

```
PE = g_adj / (r − g_adj)
PE = max(PE, 5)
```

### 4.4 Fair Value

```
V_earn = EPS_fwd × PE
```

---

## 5. Ensemble — CV-Based Inverse-Variance

### 5.1 Coefficient of Variation Weighting

```
CV_i = σ_i / μ_i
w_i ∝ 1 / CV_i²
```

Falls back to 1/σ² when means unavailable.

### 5.2 Entropy Regularization

```
w_i = w_i × (1 − γ) + γ / N_active

γ = 0.1
```

### 5.3 Weight Floor

```
min_weight = min(0.10, 1 / N_active)
```

### 5.4 Static Fallback

```
DCF = 0.40, Relative = 0.35, Earnings = 0.25
```

---

## 6. Capital Efficiency

### 6.1 Sigmoid Multiplier

```
Spread = ROIC − WACC
α = 0.7 + 0.35 / (1 + exp(−25 × Spread))

Spread = +10%  →  α ≈ 1.05
Spread = 0%    →  α ≈ 0.875
Spread = −5%   →  α ≈ 0.78
No data        →  α = 1.0
```

---

## 7. Monte Carlo — Combined, Correlated, Skewed

### 7.1 Gaussian Copula

```
z₁ ~ N(0, 1)
z₂ = ρ × z₁ + √(1 − ρ²) × N(0, 1)
```

Regime-based ρ:

```
Stable sectors (Utilities, Staples, Health Care):     ρ = 0.2
Cyclical (Financials, Energy, Industrials, etc.):     ρ = 0.4
Speculative (Tech, Communication Services):           ρ = 0.6
```

### 7.2 Growth — Skewed Truncated Normal

```
g ~ SkewNorm(α = −2, μ = g_base, σ = 0.08)
Truncated to [−0.05, 0.40]
```

α = −2: fatter left tail (downside shocks > upside surprises).

### 7.3 WACC — Lognormal

```
μ_ln = ln(WACC) − σ²/2
WACC ~ LogNormal(μ_ln, σ = 0.15)
WACC = max(WACC, 0.04)    (floor)
```

### 7.4 TV Haircut — Uncertainty-Linked

```
λ = clamp(0.9 − 2.0 × |g_draw − g_base|, 0.60, 0.90)
```

### 7.5 Constraints Per Simulation

```
Reject if g_∞ ≥ WACC_draw − 0.02
Cap TV contribution at 75%
Cap g at ROIC × RR + 0.02
```

### 7.6 Combined Simulation

Each of 10,000 simulations produces:

```
DCF_k:  full multi-stage DCF with draw-specific g, WACC, λ
Rel_k:  V_rel × N(1.0, 0.15)
Earn_k: V_earn × N(1.0, 0.20)

V_k = w_DCF × DCF_k + w_Rel × Rel_k + w_Earn × Earn_k
V_k = V_k × α(ROIC, WACC)
```

Weights via CV-based inverse-variance (§5).

### 7.7 Output

```
P10, P25, P50, P75, P90, Mean, σ, Skewness
```

---

## 8. Mispricing Signal

### 8.1 Percentile Rank

```
S = fraction of simulated fair values ≤ market price
```

Interpolated across P10/P25/P50/P75/P90. Extrapolated beyond tails using σ.

### 8.2 Classification

```
S < 0.15  →  UNDERVALUED
0.15 ≤ S ≤ 0.85  →  FAIR
S > 0.85  →  OVERVALUED
```

### 8.3 Derived Metrics

```
Z-Score         = (Price − P50) / σ
Margin of Safety = (P50 − Price) / P50
EV Gap          = (Mean − Price) / Price
Tail Asymmetry  = (P90 − P50) / (P50 − P10)
Downside Risk   = (P50 − P10) / P50
```

### 8.4 Conviction Score

```
strength  = |S − 0.5| × 2
tightness = 1 − min(DR, 0.8)
f_norm    = Piotroski / 6
accrual_penalty = 0.7 if |accrual| > 10%, else 1.0

Undervalued: Conviction = strength × tightness × f_norm × accrual_penalty
Overvalued:  Conviction = strength × tightness × accrual_penalty
```

---

## 9. Configuration Constants

| Parameter | Value | Section |
|---|---|---|
| MONTE_CARLO_RUNS | 10,000 | §7 |
| MC_GROWTH_SIGMA | 0.08 | §7.2 |
| MC_WACC_SIGMA | 0.15 | §7.3 |
| MC_GROWTH_SKEW_ALPHA | −2.0 | §7.2 |
| DCF_PROJECTION_YEARS | 10 | §2 |
| DCF_HIGH_GROWTH_YEARS | 5 | §2.1 |
| DCF_TERMINAL_GROWTH | 0.025 | §2.6 |
| DCF_GROWTH_DECAY_K | 0.5 | §2.1 |
| DCF_ROIC_TERMINAL | 0.08 | §2.2 |
| DCF_TV_HAIRCUT | [0.60, 0.90] | §2.6 |
| DCF_TV_MAX_CONTRIBUTION | 0.75 | §2.6 |
| RELATIVE weights | 0.50 / 0.35 / 0.15 | §3.4 |
| PEG clamp | [0.5, 2.0] | §3.1 |
| EARNINGS_GROWTH_BUFFER | 0.02 | §4.2 |
| EARNINGS horizon weights | 0.6 / 0.4 | §4.1 |
| ENSEMBLE_ENTROPY_GAMMA | 0.1 | §5.2 |
| ENSEMBLE_WEIGHT_FLOOR | 0.10 | §5.3 |
| UNDERVALUED_PERCENTILE | 0.15 | §8.2 |
| OVERVALUED_PERCENTILE | 0.85 | §8.2 |
| ACCRUAL_PENALTY_THRESHOLD | 0.10 | §8.4 |
| PIOTROSKI_MIN_QUALITY | 4 | §9 |
| ERP | 0.055 | §1.1 |
| Tax rate | 0.21 | §1.1 |
