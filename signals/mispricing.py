from scipy import stats
from config import UNDERVALUED_THRESHOLD, OVERVALUED_THRESHOLD

def compute_signal(current_price, simulation_result, piotroski_score):
    if not simulation_result or not current_price:
        return None

    p50 = simulation_result["p50"]
    std = simulation_result["std"]
    if std == 0:
        return None

    z = (current_price - p50) / std
    overvalued_prob = float(stats.norm.cdf(z))

    if z < UNDERVALUED_THRESHOLD:
        signal = "UNDERVALUED"
    elif z > OVERVALUED_THRESHOLD:
        signal = "OVERVALUED"
    else:
        signal = "FAIR"

    return {
        "current_price": current_price,
        "fair_value_p50": round(p50, 2),
        "mispricing_zscore": round(z, 3),
        "undervalued_prob": round((1 - overvalued_prob) * 100, 1),
        "overvalued_prob": round(overvalued_prob * 100, 1),
        "quality_flag": 1 if piotroski_score >= 4 else 0,
        "signal": signal,
    }
