"""
Processes downloaded TRI data:
- Builds calculated raw inputs for rolling-period analysis
- Calculates risk and return metrics in Python
- Emits public website analysis data without raw TRI values
"""

import pandas as pd
import math
from pathlib import Path
from dateutil.relativedelta import relativedelta

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_RISK_FREE_FILE = _PROJECT_ROOT / "Auctions of 364-Day Government of India Treasury Bills.xlsx"
_DEFAULT_LATEST_RETURN_YEARS = (1, 3, 5, 7, 10)


def _number(value):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _annualized_return(start, end, years):
    start = _number(start)
    end = _number(end)
    years = _number(years)
    if start is None or end is None or years is None or start <= 0 or years <= 0:
        return None
    try:
        return ((end / start) ** (1 / years) - 1) * 100
    except (OverflowError, ZeroDivisionError, ValueError):
        return None


def _average(values):
    numbers = [value for value in values if value is not None]
    if not numbers:
        return None
    return sum(numbers) / len(numbers)


def _min_or_none(values):
    numbers = [value for value in values if value is not None]
    return min(numbers) if numbers else None


def _max_or_none(values):
    numbers = [value for value in values if value is not None]
    return max(numbers) if numbers else None


def _sample_stddev(values):
    numbers = [value for value in values if value is not None]
    if len(numbers) < 2:
        return None
    average = sum(numbers) / len(numbers)
    variance = sum((value - average) ** 2 for value in numbers) / (len(numbers) - 1)
    return math.sqrt(variance)


def _quartiles(values):
    numbers = sorted(value for value in values if value is not None)
    if len(numbers) < 4:
        return None
    return (_percentile_inc(numbers, 0.25), _percentile_inc(numbers, 0.75))


def _percentile_inc(numbers, percentile):
    if len(numbers) == 1:
        return numbers[0]
    rank = percentile * (len(numbers) - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return numbers[lower]
    weight = rank - lower
    return numbers[lower] + (numbers[upper] - numbers[lower]) * weight


def _json_number(value, digits=None):
    number = _number(value)
    if number is None:
        return None
    return round(number, digits) if digits is not None else number


def _sort_number(value):
    return value if value is not None else float("-inf")


# ========================== HELPER FUNCTIONS ==========================

def generate_rolling_periods(earliest_date, latest_date, rolling_years=3):
    """Generate rolling period start/end dates."""
    periods = []
    current_start = earliest_date
    while True:
        current_end = current_start + relativedelta(years=rolling_years, days=-1)
        if current_end > latest_date:
            break
        periods.append((current_start, current_end))
        current_start = current_start + relativedelta(years=1)
    return periods


def find_closest_date_value(df, target_date, tolerance_days=30):
    """Find the TRI value closest to the target date within tolerance."""
    dates = df["Date"]
    diff = abs(dates - pd.Timestamp(target_date))
    min_idx = diff.idxmin()
    min_diff = diff[min_idx].days
    if min_diff <= tolerance_days:
        return df.loc[min_idx, "Total Returns Index"]
    return None


def calculate_stddev(df):
    """Calculate annualized Std Dev from daily returns."""
    df = df.sort_values("Date").reset_index(drop=True)
    daily_returns = df["Total Returns Index"].pct_change().dropna()
    annual_stddev = daily_returns.std() * math.sqrt(252)
    return round(annual_stddev * 100, 2)


def calculate_max_drawdown(df):
    """Calculate worst peak-to-trough drawdown from the TRI series."""
    df = df.sort_values("Date").reset_index(drop=True)
    tri = df["Total Returns Index"]
    running_peak = tri.cummax()
    drawdowns = (tri / running_peak - 1) * 100
    return round(drawdowns.min(), 2)


def load_monthly_risk_free_returns(path=_RISK_FREE_FILE):
    """Load 364-day T-Bill yields and convert annual yields to monthly returns."""
    if not path.exists():
        raise FileNotFoundError(f"Risk-free data file not found: {path}")

    raw = pd.read_excel(path, header=None)
    header_row = None
    date_col = None
    yield_col = None
    for row_idx in range(len(raw)):
        values = [str(value).strip() for value in raw.iloc[row_idx].tolist()]
        if "Date of Auction" in values and "Implicit Yield at Cut-off Price (percent)" in values:
            header_row = row_idx
            date_col = values.index("Date of Auction")
            yield_col = values.index("Implicit Yield at Cut-off Price (percent)")
            break

    if header_row is None:
        raise ValueError("Could not find risk-free data headers in the T-Bill workbook.")

    risk_free = raw.iloc[header_row + 1:, [date_col, yield_col]].copy()
    risk_free.columns = ["Date", "Annual Yield (%)"]
    risk_free["Date"] = pd.to_datetime(risk_free["Date"], errors="coerce")
    risk_free["Annual Yield (%)"] = pd.to_numeric(risk_free["Annual Yield (%)"], errors="coerce")
    risk_free = risk_free.dropna().sort_values("Date").drop_duplicates("Date", keep="last")
    risk_free["Date"] = risk_free["Date"].astype("datetime64[ns]")
    risk_free["Monthly Risk-Free Return"] = (1 + risk_free["Annual Yield (%)"] / 100) ** (1 / 12) - 1
    return risk_free[["Date", "Monthly Risk-Free Return"]].reset_index(drop=True)


def calculate_sharpe_sortino(df, monthly_risk_free):
    """Calculate annualized Sharpe and Sortino ratios from monthly excess returns."""
    df = df.sort_values("Date").copy()
    monthly_tri = (
        df.set_index("Date")["Total Returns Index"]
        .resample("ME")
        .last()
        .dropna()
    )
    monthly_returns = monthly_tri.pct_change().dropna().reset_index()
    monthly_returns.columns = ["Date", "Monthly Return"]
    monthly_returns["Date"] = monthly_returns["Date"].astype("datetime64[ns]")

    if monthly_returns.empty or monthly_risk_free.empty:
        return None, None

    merged = pd.merge_asof(
        monthly_returns.sort_values("Date"),
        monthly_risk_free.sort_values("Date"),
        on="Date",
        direction="backward",
    ).dropna(subset=["Monthly Risk-Free Return"])

    if len(merged) < 2:
        return None, None

    excess_returns = merged["Monthly Return"] - merged["Monthly Risk-Free Return"]
    avg_excess = excess_returns.mean()
    excess_stddev = excess_returns.std()
    sharpe = None if excess_stddev == 0 or pd.isna(excess_stddev) else avg_excess / excess_stddev * math.sqrt(12)

    negative_excess = excess_returns[excess_returns < 0]
    downside_stddev = negative_excess.std()
    sortino = None if downside_stddev == 0 or pd.isna(downside_stddev) else avg_excess / downside_stddev * math.sqrt(12)

    return (
        None if sharpe is None else round(sharpe, 2),
        None if sortino is None else round(sortino, 2),
    )


# ========================== BUILD RAW DATA ==========================

def build_analysis(all_data, rolling_years=3, latest_return_years=None):
    """
    Extract calculated TRI inputs and risk metrics for public analysis output.
    Returns: (raw_data_df, num_periods)
    """
    if not all_data:
        print("No data to analyze.")
        return None, 0

    global_earliest = None
    global_latest = None
    for df in all_data.values():
        idx_earliest = df["Date"].min()
        idx_latest = df["Date"].max()
        if global_earliest is None or idx_earliest < global_earliest:
            global_earliest = idx_earliest
        if global_latest is None or idx_latest > global_latest:
            global_latest = idx_latest

    print(f"\nGlobal date range: {global_earliest.strftime('%d-%b-%Y')} to {global_latest.strftime('%d-%b-%Y')}")

    periods = generate_rolling_periods(global_earliest, global_latest, rolling_years)
    num_periods = len(periods)
    print(f"Generated {num_periods} rolling {rolling_years}-year periods")

    latest_return_years = tuple(latest_return_years or _DEFAULT_LATEST_RETURN_YEARS)
    monthly_risk_free = load_monthly_risk_free_returns()
    fund_rows = []
    for index_name, df in all_data.items():
        print(f"  Extracting: {index_name}...", end="")
        df = df.sort_values("Date").reset_index(drop=True)

        first_tri = df["Total Returns Index"].iloc[0]
        last_tri = df["Total Returns Index"].iloc[-1]
        start_date = df["Date"].iloc[0]
        end_date = df["Date"].iloc[-1]
        years = (end_date - start_date).days / 365.25

        stddev = calculate_stddev(df) if years > 0 and first_tri > 0 else None
        max_drawdown = calculate_max_drawdown(df) if years > 0 and first_tri > 0 else None
        sharpe, sortino = calculate_sharpe_sortino(df, monthly_risk_free) if years > 0 and first_tri > 0 else (None, None)

        row = {
            "Index Name": index_name,
            "First TRI": first_tri,
            "Last TRI": last_tri,
            "Years": round(years, 4),
            "Std Dev (%)": stddev,
            "Max Drawdown (%)": max_drawdown,
            "Sharpe Ratio": sharpe,
            "Sortino Ratio": sortino,
        }

        for years_back in latest_return_years:
            latest_start_date = end_date - relativedelta(years=years_back)
            row[f"Latest {years_back}Y Start TRI"] = find_closest_date_value(df, latest_start_date)

        for i, (p_start, p_end) in enumerate(periods):
            row[f"P{i+1} Start TRI"] = find_closest_date_value(df, p_start)
            row[f"P{i+1} End TRI"] = find_closest_date_value(df, p_end)

        fund_rows.append(row)
        print(" done")

    raw_data_df = pd.DataFrame(fund_rows)
    return raw_data_df, num_periods


def build_public_site_data(periods_data, amc_lookup=None, source_lookup=None,
                           latest_return_years=None, data_updated_through=None,
                           generated_at=None):
    """Build public website JSON from calculated raw analysis inputs.

    The output intentionally excludes raw TRI values and per-window rolling
    return arrays. Those are kept only in the backend/cache for calculations.
    """
    latest_return_years = tuple(latest_return_years or _DEFAULT_LATEST_RETURN_YEARS)
    periods = []

    for rolling_years, raw_data_df, num_periods in periods_data:
        rows = _build_public_period_rows(
            rolling_years,
            raw_data_df,
            num_periods,
            latest_return_years,
            amc_lookup=amc_lookup,
            source_lookup=source_lookup,
        )
        periods.append(
            {
                "label": f"{rolling_years}Y",
                "rollingYears": rolling_years,
                "averageRollingReturnLabel": f"Average {rolling_years} Year Rolling Return (%)",
                "rows": rows,
                "summary": _summarize_public_rows(rows),
            }
        )

    return {
        "title": "Index Funds Analysis",
        "dataUpdatedThrough": data_updated_through,
        "generatedAt": generated_at,
        "sources": [
            {
                "text": "Total Returns Index values downloaded from niftyindices.com",
                "url": "https://www.niftyindices.com/",
            },
            {
                "text": "AMC/index-fund availability parsed from the index fund listing data on niftyindices.com",
                "url": "https://www.niftyindices.com/",
            },
            {
                "text": "Risk-free return uses RBI 364-day Government of India Treasury Bill auction yields",
                "url": "https://www.rbi.org.in/",
            },
        ],
        "periods": periods,
    }


def _build_public_period_rows(rolling_years, raw_data_df, num_periods,
                              latest_return_years, amc_lookup=None,
                              source_lookup=None):
    rolling_columns = [[] for _ in range(num_periods)]
    base_rows = []

    for _, row in raw_data_df.iterrows():
        first_tri = _number(row.get("First TRI"))
        last_tri = _number(row.get("Last TRI"))
        years = _number(row.get("Years"))

        latest_returns = {}
        for years_back in latest_return_years:
            latest_returns[f"latest{years_back}YearReturn"] = _json_number(
                _annualized_return(row.get(f"Latest {years_back}Y Start TRI"), last_tri, years_back)
            )

        rolling_returns = []
        for i in range(num_periods):
            value = _annualized_return(
                row.get(f"P{i+1} Start TRI"),
                row.get(f"P{i+1} End TRI"),
                rolling_years,
            )
            rolling_returns.append(value)
            rolling_columns[i].append(value)

        index_name = str(row["Index Name"])
        amcs = amc_lookup(index_name) if amc_lookup else []
        source_url = source_lookup(index_name) if source_lookup else ""

        base_rows.append(
            {
                "indexName": index_name,
                "cagr": _json_number(_annualized_return(first_tri, last_tri, years)),
                "stdDev": _json_number(row.get("Std Dev (%)")),
                "maxDrawdown": _json_number(row.get("Max Drawdown (%)")),
                "sharpeRatio": _json_number(row.get("Sharpe Ratio"), 2),
                "sortinoRatio": _json_number(row.get("Sortino Ratio"), 2),
                "yearsOfData": int(years) if years is not None else None,
                "averageRollingReturn": _json_number(_average(rolling_returns)),
                "worstRollingReturn": _json_number(_min_or_none(rolling_returns)),
                "bestRollingReturn": _json_number(_max_or_none(rolling_returns)),
                "rollingReturnStdDev": _json_number(_sample_stddev(rolling_returns)),
                "_rollingReturns": rolling_returns,
                "amcs": amcs,
                "sourceUrl": source_url,
            }
        )
        base_rows[-1].update(latest_returns)

    quartiles = [_quartiles(values) for values in rolling_columns]
    for row in base_rows:
        top_count = 0
        bottom_count = 0
        for value, qs in zip(row["_rollingReturns"], quartiles):
            if value is None or qs is None:
                continue
            q1, q3 = qs
            if value >= q3:
                top_count += 1
            if value <= q1:
                bottom_count += 1
        row["topQuartileCount"] = top_count
        row["bottomQuartileCount"] = bottom_count
        row["topBottomRatio"] = top_count if bottom_count == 0 else round(top_count / bottom_count, 2)
        del row["_rollingReturns"]

    return sorted(
        base_rows,
        key=lambda item: (_sort_number(item["topBottomRatio"]), _sort_number(item["cagr"])),
        reverse=True,
    )


def _summarize_public_rows(rows):
    cagr_values = [row["cagr"] for row in rows if row["cagr"] is not None]
    avg_values = [row["averageRollingReturn"] for row in rows if row["averageRollingReturn"] is not None]
    return {
        "indexCount": len(rows),
        "withAmcCount": sum(1 for row in rows if row["amcs"]),
        "bestCagr": max(cagr_values) if cagr_values else None,
        "bestAverageRollingReturn": max(avg_values) if avg_values else None,
    }


