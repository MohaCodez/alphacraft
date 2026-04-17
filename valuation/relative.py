def run_relative(pe_trailing, eps_ttm, sector_median_pe, pe_forward=None, eps_forward=None):
    """Sector-adjusted fair value: what would the stock be worth at the sector median P/E?"""
    eps = eps_forward or eps_ttm
    pe_ref = sector_median_pe
    if not eps or not pe_ref or eps <= 0:
        return None
    return eps * pe_ref
