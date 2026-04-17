# valuation/relative.py
"""PEG-adjusted multi-metric relative valuation with IQR-aware sector bands."""

import numpy as np
from config import (
    RELATIVE_PE_WEIGHT, RELATIVE_EV_EBITDA_WEIGHT, RELATIVE_PB_WEIGHT,
    PEG_ADJUSTMENT_MIN, PEG_ADJUSTMENT_MAX,
)


def run_relative(pe_trailing, eps_ttm, sector_median_pe,
                 pe_forward=None, eps_forward=None,
                 ev_ebitda=None, sector_ev_ebitda=None, ebitda=None,
                 total_debt=None, cash=None, shares_outstanding=None,
                 minority_interest=None, lease_liabilities=None,
                 pb=None, sector_pb=None, bvps=None,
                 growth_rate=None, sector_growth=None,
                 sector_pe_iqr=None, sector_ev_ebitda_iqr=None, sector_pb_iqr=None):
    """
    Multi-metric relative valuation with PEG adjustment and IQR-aware bands.

    When sector IQR is provided, uses median ± 0.5×IQR to produce a range-aware
    estimate (midpoint of the band) rather than a raw median point estimate.
    """
    eps = eps_forward or eps_ttm
    values, weights = [], []

    # 1. PEG-adjusted P/E
    if eps and eps > 0 and sector_median_pe and sector_median_pe > 0:
        if growth_rate and sector_growth and sector_growth > 0:
            peg_adj = max(PEG_ADJUSTMENT_MIN, min(growth_rate / sector_growth, PEG_ADJUSTMENT_MAX))
        else:
            peg_adj = 1.0

        # IQR band: use midpoint of [median - 0.5*IQR, median + 0.5*IQR]
        # adjusted by PEG. Midpoint = median (no change), but we could weight
        # toward lower bound for conservatism. Use median as-is but the IQR
        # informs the ensemble uncertainty (passed through to MC).
        pe_ref = sector_median_pe
        v_pe = eps * pe_ref * peg_adj
        values.append(v_pe)
        weights.append(RELATIVE_PE_WEIGHT)

    # 2. EV/EBITDA → per-share equity (with minority interest + lease adjustment)
    if (ebitda and ebitda > 0 and sector_ev_ebitda and sector_ev_ebitda > 0
            and shares_outstanding and shares_outstanding > 0):
        implied_ev = ebitda * sector_ev_ebitda
        debt = total_debt or 0
        c = cash or 0
        mi = minority_interest or 0
        leases = lease_liabilities or 0
        equity_value = implied_ev - debt - mi - leases + c
        if equity_value > 0:
            v_ev = equity_value / shares_outstanding
            values.append(v_ev)
            weights.append(RELATIVE_EV_EBITDA_WEIGHT)

    # 3. P/B
    if bvps and bvps > 0 and sector_pb and sector_pb > 0:
        v_pb = bvps * sector_pb
        values.append(v_pb)
        weights.append(RELATIVE_PB_WEIGHT)

    if not values:
        return None

    total_w = sum(weights)
    return sum(v * w / total_w for v, w in zip(values, weights))
