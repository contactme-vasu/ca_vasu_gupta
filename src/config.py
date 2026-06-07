"""
Configuration file for Nifty Index TRI Downloader & Analyzer.
Edit the INDEX_CATEGORIES dict below to add/remove indices.
"""

# ========================== USER SETTINGS ==========================

# Start date for historical data (April 1, 2005)
START_YEAR = 2005
START_MONTH = 4
START_DAY = 1

# Rolling return periods in years. One website analysis section is produced per
# entry. Edit freely: e.g. [3], [5], [3, 5], [1, 3, 5, 7].
ROLLING_YEARS_LIST = [3, 5]

# Latest trailing return periods in years. These columns show the annualized
# return ending at the latest available TRI date.
LATEST_RETURN_YEARS_LIST = [1, 3, 5, 7, 10]

# API Configuration
API_URL = "https://www.niftyindices.com/Backpage.aspx/getTotalReturnIndexString"

# ========================== INDEX LIST ==========================
# Mapping: Sub-Index Category -> List of Index Names
# Edit these lists to add/remove indices.
# The category MUST match exactly what the website uses.

INDEX_CATEGORIES = {
    "Broad Market Indices": [
        "NIFTY 100",
        "NIFTY 200",
        "NIFTY 50",
        "NIFTY 500",
        "NIFTY LARGEMIDCAP 250",
        "NIFTY MIDCAP 100",
        "NIFTY MIDCAP 150",
        "NIFTY MIDCAP 50",
        "NIFTY MIDCAP SELECT",
        "NIFTY MIDSMALLCAP 400",
        "NIFTY NEXT 50",
        "NIFTY SMALLCAP 100",
        "NIFTY SMALLCAP 250",
        "NIFTY TOTAL MARKET",
        "NIFTY500 LARGEMIDSMALL EQUAL-CAP WEIGHTED",
        "NIFTY500 MULTICAP 50:25:25",
    ],

    "Strategy Indices": [
        "NIFTY ALPHA 50",
        "NIFTY ALPHA LOW-VOLATILITY 30",
        "NIFTY ALPHA QUALITY LOW-VOLATILITY 30",
        "NIFTY ALPHA QUALITY VALUE LOW-VOLATILITY 30",
        "NIFTY LOW VOLATILITY 50",
        "NIFTY MIDCAP150 MOMENTUM 50",
        "NIFTY MIDCAP150 QUALITY 50",
        "NIFTY MIDSMALLCAP400 MOMENTUM QUALITY 100",
        "NIFTY QUALITY LOW-VOLATILITY 30",
        "NIFTY SMALLCAP250 MOMENTUM QUALITY 100",
        "NIFTY SMALLCAP250 QUALITY 50",
        "NIFTY TOP 10 EQUAL WEIGHT",
        "NIFTY TOP 15 EQUAL WEIGHT",
        "NIFTY TOP 20 EQUAL WEIGHT",
        "NIFTY100 ALPHA 30",
        "NIFTY100 EQUAL WEIGHT",
        "NIFTY100 LOW VOLATILITY 30",
        "NIFTY100 QUALITY 30",
        "NIFTY200 ALPHA 30",
        "NIFTY200 MOMENTUM 30",
        "NIFTY200 QUALITY 30",
        "NIFTY200 VALUE 30",
        "NIFTY50 EQUAL WEIGHT",
        "NIFTY50 VALUE 20",
        "NIFTY500 EQUAL WEIGHT",
        "NIFTY500 LOW VOLATILITY 50",
        "NIFTY500 MOMENTUM 50",
        "NIFTY500 MULTICAP MOMENTUM QUALITY 50",
        "NIFTY500 QUALITY 50",
        "NIFTY500 VALUE 50",
    ],
}
