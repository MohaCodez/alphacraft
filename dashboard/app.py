import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.store import get_latest_signals, get_latest_full
from main import run_pipeline

st.set_page_config(page_title="Alphacraft", page_icon="⚡", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1400px; }
h1 { font-size: 1.6rem !important; font-weight: 800 !important; letter-spacing: -0.5px; }
h3 { font-size: 1.05rem !important; font-weight: 700 !important; margin-bottom: 0.3rem !important; }
div[data-testid="stMetric"] {
    background: linear-gradient(135deg, #0f1729 0%, #162040 100%);
    border: 1px solid rgba(255,255,255,0.05); border-radius: 14px; padding: 18px 22px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
}
div[data-testid="stMetric"] label { font-size: 0.7rem !important; text-transform: uppercase; letter-spacing: 1.2px; opacity: 0.45; }
div[data-testid="stMetric"] [data-testid="stMetricValue"] { font-size: 1.9rem !important; font-weight: 700 !important; }
div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
button[data-baseweb="tab"] { font-weight: 600 !important; font-size: 0.85rem !important; }
.divider { border: none; border-top: 1px solid rgba(255,255,255,0.05); margin: 1.8rem 0; }
div[data-testid="stTextInput"] input { background: #0f1729 !important; border: 1px solid rgba(255,255,255,0.08) !important; border-radius: 10px !important; }
.pill { display: inline-block; padding: 3px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 600; }
.pill-under { background: rgba(0,212,170,0.15); color: #00d4aa; }
.pill-over { background: rgba(255,107,107,0.15); color: #ff6b6b; }
.pill-fair { background: rgba(148,163,184,0.1); color: #94a3b8; }
.card { background: linear-gradient(135deg,#0f1729,#162040); border-radius: 16px; padding: 24px; border: 1px solid rgba(255,255,255,0.05); }
.card-label { opacity: 0.4; font-size: 0.68rem; text-transform: uppercase; letter-spacing: 1px; }
.card-value { font-weight: 700; font-size: 1.1rem; margin-top: 2px; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ──
with st.sidebar:
    st.markdown("### ⚙️ Pipeline")

    with st.expander("🎛️ Parameters", expanded=False):
        import config as cfg
        cfg.MONTE_CARLO_RUNS = st.slider("MC Simulations", 1000, 50000, cfg.MONTE_CARLO_RUNS, step=1000)
        cfg.MC_GROWTH_SIGMA = st.slider("Growth σ", 0.02, 0.20, cfg.MC_GROWTH_SIGMA, step=0.01)
        cfg.MC_WACC_SIGMA = st.slider("WACC σ", 0.02, 0.30, cfg.MC_WACC_SIGMA, step=0.01)
        tv_range = st.slider("TV Haircut", 0.40, 1.0, (cfg.DCF_TV_HAIRCUT_MIN, cfg.DCF_TV_HAIRCUT_MAX), step=0.05)
        cfg.DCF_TV_HAIRCUT_MIN, cfg.DCF_TV_HAIRCUT_MAX = tv_range
        cfg.UNDERVALUED_PERCENTILE = st.slider("Undervalued Pctl", 0.05, 0.40, cfg.UNDERVALUED_PERCENTILE, step=0.05)
        cfg.OVERVALUED_PERCENTILE = st.slider("Overvalued Pctl", 0.60, 0.95, cfg.OVERVALUED_PERCENTILE, step=0.05)
        st.caption("Applied on next pipeline run")

    if "pipeline_running" not in st.session_state:
        st.session_state.pipeline_running = False
    if st.button("🚀 Run Pipeline", disabled=st.session_state.pipeline_running, use_container_width=True):
        st.session_state.pipeline_running = True
        import time as _time
        stage_times = {}
        stage_start = [_time.time()]
        stage_names = {1: "Universe", 2: "Macro", 3: "Fundamentals", 4: "Sector Medians", 5: "Valuation + MC"}
        prev_step = [0]
        bar = st.progress(0, text="Starting...")
        status_area = st.empty()
        log_area = st.empty()
        logs = []
        skipped = []
        processed_count = [0]
        signal_count = [0]

        try:
            def _cb(step, total, msg, pct):
                now = _time.time()
                if step != prev_step[0]:
                    if prev_step[0] > 0:
                        stage_times[prev_step[0]] = now - stage_start[0]
                    stage_start[0] = now
                    prev_step[0] = step
                elapsed = now - stage_start[0]
                label = stage_names.get(step, f"Step {step}")
                bar.progress(min(pct, 1.0), text=f"**{label}** ({step}/{total}) — {elapsed:.0f}s")
                logs.append(msg)
                log_area.code("\n".join(logs[-8:]), language=None)

            run_pipeline(progress_callback=_cb)
            # Record last stage
            if prev_step[0] > 0:
                stage_times[prev_step[0]] = _time.time() - stage_start[0]

            bar.progress(1.0, text="✅ Done")

            # Stage summary
            summary_lines = []
            for s in sorted(stage_times):
                summary_lines.append(f"**{stage_names.get(s, f'Step {s}')}**: {stage_times[s]:.1f}s")
            status_area.success(" · ".join(summary_lines))

        except Exception as e:
            bar.progress(1.0, text="❌ Failed")
            st.error(str(e))
        finally:
            st.session_state.pipeline_running = False
            _time.sleep(1)
            st.rerun()

# ── Load data ──
try:
    raw = get_latest_full()
except Exception:
    raw = get_latest_signals()
if not raw:
    st.warning("No data. Run `python3 main.py` first.")
    st.stop()

df = pd.DataFrame(raw)
run_date = df["run_date"].iloc[0] if "run_date" in df.columns else "—"

num_cols = ["current_price", "fair_value_p50", "fair_value_p10", "fair_value_p90",
            "mispricing_zscore", "signal_percentile", "downside_risk", "conviction",
            "margin_of_safety", "ev_gap", "tail_asymmetry", "roic", "wacc",
            "fcf_growth_rate", "piotroski_score", "dcf_value", "relative_value",
            "earnings_value", "capital_efficiency_alpha", "tv_contribution"]
for col in num_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

if "margin_of_safety" in df.columns:
    df["margin_pct"] = (df["margin_of_safety"] * 100).round(1)
else:
    df["margin_pct"] = ((df["fair_value_p50"] - df["current_price"]) / df["fair_value_p50"] * 100).round(1)

if "ev_gap" in df.columns:
    df["ev_gap_pct"] = (df["ev_gap"] * 100).round(1)

if "sector" not in df.columns:
    df["sector"] = "Unknown"

def _sfmt(val, fmt=".2f", prefix="", suffix=""):
    """Safely format a value that might be NaN/None."""
    if pd.isna(val) or val is None:
        return "—"
    return f"{prefix}{val:{fmt}}{suffix}"

# ── Header + KPIs ──
col_t, col_d = st.columns([3, 1])
with col_t:
    st.markdown("# ⚡ Alphacraft")
    st.caption("Probabilistic fair value screener · S&P 500")
with col_d:
    st.markdown(f"<div style='text-align:right;padding-top:1rem;opacity:0.4;font-size:0.8rem;'>Run: {run_date}</div>", unsafe_allow_html=True)

with st.expander("ℹ️ How to read this dashboard", expanded=False):
    st.markdown("""
Alphacraft estimates a **fair value distribution** for each S&P 500 stock using three independent models (DCF, Relative, Earnings) blended through 10,000 Monte Carlo simulations.

**Key columns explained:**
- **Signal** — UNDERVALUED (price below P15 of distribution), OVERVALUED (above P85), or FAIR
- **Margin %** — how far price is from the median fair value (positive = cheap)
- **Conviction** — confidence in the signal (0–1), combining distribution tightness, Piotroski quality, and accrual quality
- **Z-Score** — standard deviations from median fair value (negative = cheap)
- **Pctl** — where market price sits in the simulated distribution (0.05 = very cheap, 0.95 = very expensive)
- **DR (Downside Risk)** — width of the left tail; high DR = fragile valuation, low confidence
- **EV Gap %** — expected value gap between mean fair value and price
- **Tail Asym** — upside/downside skew ratio; >1 = more upside potential, <1 = value trap risk

⚠️ *This is a screening tool, not a prediction system. High conviction ≠ the stock will move. Stocks priced for optionality (TSLA, biotech) will always look overvalued to a fundamentals model.*
""")

n_under = len(df[df["signal"] == "UNDERVALUED"])
n_over = len(df[df["signal"] == "OVERVALUED"])
n_fair = len(df[df["signal"] == "FAIR"])
med_z = df["mispricing_zscore"].median()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Analyzed", len(df))
c2.metric("🟢 Under", n_under)
c3.metric("⚪ Fair", n_fair)
c4.metric("🔴 Over", n_over)
c5.metric("Med Z", f"{med_z:+.2f}")

st.markdown("<hr class='divider'>", unsafe_allow_html=True)

# ── Tabs ──
tab_screener, tab_sectors, tab_scatter, tab_lookup = st.tabs(["📊 Screener", "🏢 Sectors", "🔬 Analysis", "🔍 Lookup"])

# ── Screener Tab ──
with tab_screener:
    st.caption("Ranked list of S&P 500 stocks by mispricing signal. Filter by signal type, sector, or quality score. Sort by any metric.")
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        sig_filter = st.multiselect("Signal", ["UNDERVALUED", "FAIR", "OVERVALUED"],
                                     default=["UNDERVALUED", "OVERVALUED"], key="sig_f")
    with fc2:
        sectors = sorted(df["sector"].dropna().unique())
        sec_filter = st.multiselect("Sector", sectors, default=[], key="sec_f", placeholder="All sectors")
    with fc3:
        quality_only = st.checkbox("Quality only (F≥4)", value=False, key="q_f")
    with fc4:
        sort_options = ["conviction", "mispricing_zscore", "margin_pct", "signal_percentile", "downside_risk"]
        if "ev_gap_pct" in df.columns:
            sort_options.append("ev_gap_pct")
        if "tail_asymmetry" in df.columns:
            sort_options.append("tail_asymmetry")
        sort_col = st.selectbox("Sort by", sort_options, key="sort_f")

    filtered = df.copy()
    if sig_filter:
        filtered = filtered[filtered["signal"].isin(sig_filter)]
    if sec_filter:
        filtered = filtered[filtered["sector"].isin(sec_filter)]
    if quality_only:
        filtered = filtered[filtered["quality_flag"] == 1]

    ascending = sort_col in ["signal_percentile", "downside_risk", "mispricing_zscore"]
    filtered = filtered.sort_values(sort_col, ascending=ascending, na_position="last")

    display_cols = ["ticker", "sector", "signal", "current_price", "fair_value_p50",
                    "margin_pct", "conviction", "mispricing_zscore", "signal_percentile",
                    "downside_risk"]
    if "ev_gap_pct" in filtered.columns:
        display_cols.append("ev_gap_pct")
    if "tail_asymmetry" in filtered.columns:
        display_cols.append("tail_asymmetry")
    display_cols = [c for c in display_cols if c in filtered.columns]

    col_cfg = {
        "ticker": st.column_config.TextColumn("Ticker", width="small"),
        "sector": st.column_config.TextColumn("Sector", width="medium"),
        "signal": st.column_config.TextColumn("Signal", width="small"),
        "current_price": st.column_config.NumberColumn("Price", format="$%.2f"),
        "fair_value_p50": st.column_config.NumberColumn("Fair (P50)", format="$%.2f"),
        "margin_pct": st.column_config.NumberColumn("Margin %", format="%.1f%%"),
        "conviction": st.column_config.NumberColumn("Conviction", format="%.3f"),
        "mispricing_zscore": st.column_config.NumberColumn("Z-Score", format="%+.2f"),
        "signal_percentile": st.column_config.NumberColumn("Pctl", format="%.2f"),
        "downside_risk": st.column_config.NumberColumn("DR", format="%.2f"),
        "ev_gap_pct": st.column_config.NumberColumn("EV Gap %", format="%+.1f%%"),
        "tail_asymmetry": st.column_config.NumberColumn("Tail Asym", format="%.2f"),
    }

    st.dataframe(filtered[display_cols], use_container_width=True, hide_index=True,
                  column_config={k: v for k, v in col_cfg.items() if k in display_cols}, height=620)
    st.caption(f"Showing {len(filtered)} of {len(df)} stocks")

# ── Sectors Tab ──
with tab_sectors:
    st.caption("Signal distribution by sector. Sectors with more green bars have more stocks trading below modeled fair value.")
    sector_agg = df.groupby("sector").agg(
        count=("ticker", "size"),
        undervalued=("signal", lambda x: (x == "UNDERVALUED").sum()),
        overvalued=("signal", lambda x: (x == "OVERVALUED").sum()),
        med_z=("mispricing_zscore", "median"),
        med_margin=("margin_pct", "median"),
        med_conviction=("conviction", "median"),
    ).reset_index().sort_values("med_z")

    sector_melt = df.groupby(["sector", "signal"]).size().reset_index(name="count")
    color_map = {"UNDERVALUED": "#00d4aa", "FAIR": "#475569", "OVERVALUED": "#ff6b6b"}
    fig_sec = px.bar(sector_melt, x="count", y="sector", color="signal", orientation="h",
                      color_discrete_map=color_map,
                      category_orders={"signal": ["UNDERVALUED", "FAIR", "OVERVALUED"]})
    fig_sec.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=500, margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(title="Stocks", gridcolor="rgba(255,255,255,0.04)"),
        yaxis=dict(title="", categoryorder="total ascending"),
        legend=dict(orientation="h", y=1.02, x=0.5, xanchor="center", title=""), bargap=0.25)
    st.plotly_chart(fig_sec, use_container_width=True)

    st.dataframe(sector_agg.rename(columns={
        "sector": "Sector", "count": "Stocks", "undervalued": "🟢 Under",
        "overvalued": "🔴 Over", "med_z": "Med Z", "med_margin": "Med Margin %",
        "med_conviction": "Med Conv"}),
        use_container_width=True, hide_index=True,
        column_config={"Med Z": st.column_config.NumberColumn(format="%+.2f"),
                        "Med Margin %": st.column_config.NumberColumn(format="%.1f%%"),
                        "Med Conv": st.column_config.NumberColumn(format="%.3f")})

# ── Analysis Tab ──
with tab_scatter:
    st.caption("Visual analysis. Price vs Fair Value shows where stocks sit relative to the 45° line. Z-Score distribution shows the overall market skew. Conviction vs EV Gap highlights the strongest opportunities.")
    sc1, sc2 = st.columns(2)

    with sc1:
        st.markdown("### Price vs Fair Value")
        plot_df = df[df["fair_value_p50"].notna() & df["current_price"].notna()].copy()
        cap = plot_df["fair_value_p50"].quantile(0.95)
        plot_df = plot_df[(plot_df["fair_value_p50"] < cap * 2) & (plot_df["current_price"] < cap * 2)]
        fig_pv = go.Figure()
        for sig, color in [("UNDERVALUED", "#00d4aa"), ("FAIR", "#475569"), ("OVERVALUED", "#ff6b6b")]:
            sub = plot_df[plot_df["signal"] == sig]
            fig_pv.add_trace(go.Scatter(x=sub["fair_value_p50"], y=sub["current_price"],
                mode="markers", name=sig, marker=dict(color=color, size=5, opacity=0.7),
                text=sub["ticker"], hovertemplate="%{text}<br>Fair: $%{x:.0f}<br>Price: $%{y:.0f}<extra></extra>"))
        mx = max(plot_df["fair_value_p50"].max(), plot_df["current_price"].max())
        fig_pv.add_trace(go.Scatter(x=[0, mx], y=[0, mx], mode="lines",
            line=dict(color="rgba(255,255,255,0.15)", dash="dot"), showlegend=False))
        fig_pv.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            height=400, margin=dict(l=40, r=10, t=10, b=40),
            xaxis=dict(title="Fair Value (P50)", gridcolor="rgba(255,255,255,0.04)"),
            yaxis=dict(title="Market Price", gridcolor="rgba(255,255,255,0.04)"),
            legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"))
        st.plotly_chart(fig_pv, use_container_width=True)
        st.caption("Below line = undervalued · Above = overvalued")

    with sc2:
        st.markdown("### Z-Score Distribution")
        z_clipped = df["mispricing_zscore"].clip(-10, 10)
        fig_z = go.Figure()
        fig_z.add_trace(go.Histogram(x=z_clipped, nbinsx=80,
            marker=dict(color=z_clipped.apply(lambda z: "#00d4aa" if z < -1.5 else "#ff6b6b" if z > 1.5 else "#334155"), line=dict(width=0)),
            hovertemplate="Z: %{x:.2f}<br>Count: %{y}<extra></extra>"))
        fig_z.add_vline(x=-1.5, line_dash="dot", line_color="#00d4aa", annotation_text="Under", annotation_font_color="#00d4aa")
        fig_z.add_vline(x=1.5, line_dash="dot", line_color="#ff6b6b", annotation_text="Over", annotation_font_color="#ff6b6b")
        fig_z.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            height=400, margin=dict(l=40, r=10, t=10, b=40),
            xaxis=dict(title="Z-Score", gridcolor="rgba(255,255,255,0.04)", range=[-8, 8]),
            yaxis=dict(title="Count", gridcolor="rgba(255,255,255,0.04)"), bargap=0.05, showlegend=False)
        st.plotly_chart(fig_z, use_container_width=True)

    # Conviction vs EV Gap
    st.markdown("### Conviction vs EV Gap")
    if "ev_gap_pct" in df.columns:
        has_data = df[df["conviction"].notna() & df["ev_gap_pct"].notna()].copy()
        if not has_data.empty:
            fig_ce = go.Figure()
            for sig, color in [("UNDERVALUED", "#00d4aa"), ("FAIR", "#475569"), ("OVERVALUED", "#ff6b6b")]:
                sub = has_data[has_data["signal"] == sig]
                fig_ce.add_trace(go.Scatter(x=sub["ev_gap_pct"], y=sub["conviction"],
                    mode="markers", name=sig, marker=dict(color=color, size=5, opacity=0.65),
                    text=sub["ticker"], hovertemplate="%{text}<br>EV Gap: %{x:+.1f}%<br>Conv: %{y:.3f}<extra></extra>"))
            fig_ce.add_vline(x=0, line_dash="solid", line_color="rgba(255,255,255,0.1)")
            fig_ce.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                height=380, margin=dict(l=40, r=10, t=10, b=40),
                xaxis=dict(title="EV Gap % (positive = undervalued)", gridcolor="rgba(255,255,255,0.04)"),
                yaxis=dict(title="Conviction", gridcolor="rgba(255,255,255,0.04)"),
                legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"))
            st.plotly_chart(fig_ce, use_container_width=True)
            st.caption("Top-right quadrant = high conviction + large expected value gap")
    else:
        st.info("EV Gap data not available. Re-run pipeline.")

# ── Lookup Tab ──
with tab_lookup:
    st.caption("Deep-dive into any stock. See the full valuation breakdown, fair value range, model contributions, and quality metrics.")
    query = st.text_input("Enter ticker", placeholder="AAPL, NVDA, TSLA...", label_visibility="collapsed")
    if query:
        match = df[df["ticker"].str.upper() == query.strip().upper()]
        if match.empty:
            st.error(f"No data for {query.upper()}")
        else:
            r = match.iloc[0].to_dict()  # Convert to dict to avoid pandas .get() issues
            sig_color = {"UNDERVALUED": "#00d4aa", "OVERVALUED": "#ff6b6b"}.get(r.get("signal", ""), "#94a3b8")
            pill_cls = "under" if r.get("signal") == "UNDERVALUED" else "over" if r.get("signal") == "OVERVALUED" else "fair"

            p10_s = _sfmt(r.get("fair_value_p10"), ".2f", "$")
            p90_s = _sfmt(r.get("fair_value_p90"), ".2f", "$")
            conv = r.get("conviction") or 0
            dr = r.get("downside_risk") or 0
            sp = r.get("signal_percentile") or 0.5
            mg = r.get("margin_pct") or 0
            sector = r.get("sector") or "—"
            pio = r.get("piotroski_score", "—")
            ev_gap_v = _sfmt(r.get("ev_gap_pct"), "+.1f", "", "%") if r.get("ev_gap_pct") is not None else "—"
            ta_v = _sfmt(r.get("tail_asymmetry"), ".2f")
            roic_v = _sfmt(r.get("roic"), ".1%") if r.get("roic") is not None and not pd.isna(r.get("roic")) else "—"
            wacc_v = _sfmt(r.get("wacc"), ".1%") if r.get("wacc") is not None and not pd.isna(r.get("wacc")) else "—"
            growth_v = _sfmt(r.get("fcf_growth_rate"), ".1%") if r.get("fcf_growth_rate") is not None and not pd.isna(r.get("fcf_growth_rate")) else "—"
            price_v = r.get("current_price", 0) or 0
            p50_v = r.get("fair_value_p50", 0) or 0
            z_v = r.get("mispricing_zscore", 0) or 0

            quality_icon = "✅" if r.get("quality_flag") else "⚠️"
            pio_display = f"{quality_icon} {pio}/9" if pio != "—" else "—"

            lc, rc = st.columns([2, 3])
            with lc:
                st.markdown(f"""
                <div class="card">
                    <div style="display:flex;align-items:center;gap:12px;">
                        <span style="font-size:2rem;font-weight:800;">{r.get('ticker','')}</span>
                        <span class="pill pill-{pill_cls}">{r.get('signal','')}</span>
                    </div>
                    <div style="opacity:0.4;font-size:0.8rem;margin-top:2px;">{sector}</div>
                    <div style="margin-top:20px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;">
                        <div><span class="card-label">Price</span><div class="card-value">${price_v:.2f}</div></div>
                        <div><span class="card-label">Fair Value</span><div class="card-value">${p50_v:.2f}</div></div>
                        <div><span class="card-label">Margin</span><div class="card-value" style="color:{sig_color};">{mg:+.1f}%</div></div>
                    </div>
                    <div style="margin-top:14px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;">
                        <div><span class="card-label">Range</span><div class="card-value">{p10_s} – {p90_s}</div></div>
                        <div><span class="card-label">Z-Score</span><div class="card-value">{z_v:+.2f}</div></div>
                        <div><span class="card-label">Conviction</span><div class="card-value">{conv:.3f}</div></div>
                    </div>
                    <div style="margin-top:14px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;">
                        <div><span class="card-label">EV Gap</span><div class="card-value">{ev_gap_v}</div></div>
                        <div><span class="card-label">Tail Asymmetry</span><div class="card-value">{ta_v}</div></div>
                        <div><span class="card-label">Downside Risk</span><div class="card-value">{dr:.2f}</div></div>
                    </div>
                    <div style="margin-top:14px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;">
                        <div><span class="card-label">ROIC</span><div class="card-value">{roic_v}</div></div>
                        <div><span class="card-label">WACC</span><div class="card-value">{wacc_v}</div></div>
                        <div><span class="card-label">Growth</span><div class="card-value">{growth_v}</div></div>
                    </div>
                    <div style="margin-top:14px;display:grid;grid-template-columns:1fr 1fr;gap:14px;">
                        <div><span class="card-label">Percentile</span><div class="card-value">{sp:.2%}</div></div>
                        <div><span class="card-label">Quality</span><div class="card-value">{pio_display}</div></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with rc:
                # Fair value range bar
                p10_num = r.get("fair_value_p10") or p50_v * 0.8
                p90_num = r.get("fair_value_p90") or p50_v * 1.2
                if pd.isna(p10_num): p10_num = p50_v * 0.8
                if pd.isna(p90_num): p90_num = p50_v * 1.2

                fig_range = go.Figure()
                fig_range.add_trace(go.Bar(x=[p90_num - p10_num], y=[""], base=[p10_num],
                    orientation="h", marker=dict(color="rgba(99,102,241,0.25)", line=dict(width=0)),
                    showlegend=False, hoverinfo="skip"))
                fig_range.add_trace(go.Scatter(x=[p50_v], y=[""], mode="markers",
                    marker=dict(color="#818cf8", size=14, symbol="diamond"),
                    name="Fair Value (P50)", hovertemplate=f"P50: ${p50_v:.2f}<extra></extra>"))
                fig_range.add_trace(go.Scatter(x=[price_v], y=[""], mode="markers",
                    marker=dict(color=sig_color, size=16, symbol="x", line=dict(width=2, color=sig_color)),
                    name="Market Price", hovertemplate=f"Price: ${price_v:.2f}<extra></extra>"))
                fig_range.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    height=120, margin=dict(l=10, r=10, t=30, b=10),
                    xaxis=dict(title="", gridcolor="rgba(255,255,255,0.04)", tickprefix="$"),
                    yaxis=dict(visible=False),
                    legend=dict(orientation="h", y=1.3, x=0.5, xanchor="center"),
                    title=dict(text="Price vs Fair Value Range", font=dict(size=13), x=0, y=0.95))
                st.plotly_chart(fig_range, use_container_width=True)

                # Z-Score gauge
                gauge = go.Figure(go.Indicator(mode="gauge+number", value=float(z_v),
                    number=dict(suffix="", font=dict(size=32)),
                    gauge=dict(axis=dict(range=[-5, 5], tickwidth=1, tickcolor="rgba(255,255,255,0.15)"),
                        bar=dict(color=sig_color, thickness=0.7), bgcolor="rgba(0,0,0,0)", borderwidth=0,
                        steps=[dict(range=[-5, -1.5], color="rgba(0,212,170,0.1)"),
                               dict(range=[-1.5, 1.5], color="rgba(255,255,255,0.02)"),
                               dict(range=[1.5, 5], color="rgba(255,107,107,0.1)")]),
                    title=dict(text="Z-Score", font=dict(size=12))))
                gauge.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                    height=200, margin=dict(l=20, r=20, t=50, b=10))
                st.plotly_chart(gauge, use_container_width=True)

            # Model breakdown
            has_models = any(r.get(c) is not None and not pd.isna(r.get(c, None))
                             for c in ["dcf_value", "relative_value", "earnings_value"])
            if has_models:
                st.markdown("<hr class='divider'>", unsafe_allow_html=True)
                st.markdown("##### Model Breakdown")
                mc1, mc2, mc3, mc4 = st.columns(4)
                mc1.metric("DCF", _sfmt(r.get("dcf_value"), ".2f", "$"))
                mc2.metric("Relative", _sfmt(r.get("relative_value"), ".2f", "$"))
                mc3.metric("Earnings", _sfmt(r.get("earnings_value"), ".2f", "$"))
                mc4.metric("Cap Eff α", _sfmt(r.get("capital_efficiency_alpha"), ".2f"))

# ── Footer ──
st.markdown("<hr class='divider'>", unsafe_allow_html=True)
st.markdown("<div style='text-align:center;opacity:0.25;font-size:0.7rem;padding:0.5rem 0;'>"
    "Alphacraft · Not financial advice · Valuations are probabilistic estimates</div>", unsafe_allow_html=True)
