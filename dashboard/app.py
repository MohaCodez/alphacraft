# dashboard/app.py
import streamlit as st
import pandas as pd
import plotly.express as px
from data.store import get_latest_signals

st.set_page_config(page_title="Alphacraft", layout="wide")
st.title("Alphacraft — Probabilistic Valuation Engine")

signals = get_latest_signals()
df = pd.DataFrame(signals)

col1, col2, col3 = st.columns(3)
col1.metric("Stocks Analyzed", len(df))
col2.metric("Undervalued", len(df[df["signal"] == "UNDERVALUED"]))
col3.metric("Overvalued", len(df[df["signal"] == "OVERVALUED"]))

st.subheader("Top Undervalued (Quality Filtered)")
undervalued = df[(df["signal"] == "UNDERVALUED") & (df["quality_flag"] == 1)].sort_values("mispricing_zscore")
st.dataframe(undervalued[["ticker", "current_price", "fair_value_p50", "mispricing_zscore", "undervalued_prob"]].head(15))

st.subheader("Top Overvalued")
overvalued = df[df["signal"] == "OVERVALUED"].sort_values("mispricing_zscore", ascending=False)
st.dataframe(overvalued[["ticker", "current_price", "fair_value_p50", "mispricing_zscore", "overvalued_prob"]].head(15))

st.subheader("Mispricing Distribution")
fig = px.histogram(df, x="mispricing_zscore", nbins=50, color_discrete_sequence=["#00d4aa"])
st.plotly_chart(fig, use_container_width=True)