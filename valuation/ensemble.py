# valuation/ensemble.py
from config import DCF_WEIGHT, RELATIVE_WEIGHT, EARNINGS_WEIGHT

def ensemble(dcf, relative, earnings):
    values, weights = [], []
    if dcf:
        values.append(dcf); weights.append(DCF_WEIGHT)
    if relative:
        values.append(relative); weights.append(RELATIVE_WEIGHT)
    if earnings:
        values.append(earnings); weights.append(EARNINGS_WEIGHT)
    if not values:
        return None
    total_weight = sum(weights)
    return sum(v * w for v, w in zip(values, weights)) / total_weight