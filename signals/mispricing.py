# signals/mispricing.py
from scipy import stats

def compute_signal(current_price, simulation_result, piotroski_score):
    if not simulation_result or not current_price:
        return None

    p50 = simulation_result["p50"]
    std = simulation_result["std"]

    if std == 0:
        return None

    z_score = (current_price - p50) / std

    # probability current price is above fair value distribution
    overvalued_prob = float(stats.norm.cdf(z_score))
    undervalued_prob = 1 - overvalued_prob

    if z_score < -1.5:
        signal = "UNDERVALUED"
    elif z_score > 1.5:
        signal = "OVERVALUED"
    else:
        signal = "FAIR"

    quality_flag = 1 if piotroski_score >= 4 else 0

    return {
        "current_price": current_price,
        "fair_value_p50": p50,
        "mispricing_zscore": round(z_score, 3),
        "undervalued_prob": round(undervalued_prob * 100, 1),
        "overvalued_prob": round(overvalued_prob * 100, 1),
        "quality_flag": quality_flag,
        "signal": signal,
    }