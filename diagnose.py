from data_manager import get_recent_data
from indicators import add_all_indicators
import config as cfg

tickers = [
    'BAJFINANCE.NS','HDFCBANK.NS','INFY.NS','TCS.NS','WIPRO.NS',
    'TITAN.NS','ASIANPAINT.NS','PIDILITIND.NS','PAGEIND.NS','DIXON.NS'
]

print(f"{'Ticker':<20} {'InUptrend':<12} {'Near52W':<10} {'VolRatio':<10} Close vs SMA50")
print("-" * 70)
passed = 0
for t in tickers:
    df = get_recent_data(t, lookback_days=350)
    if df is None:
        print(f"{t:<20} no data")
        continue
    df = add_all_indicators(df, cfg)
    r = df.iloc[-1]
    trend   = bool(r["InUptrend"])
    near52  = bool(r["Near52WHigh"])
    vol     = float(r["VolRatio"])
    close   = float(r["Close"])
    sma50   = float(r["SMA50"])
    flag = " ✅ PASSES FILTERS" if trend and near52 else ""
    print(f"{t:<20} {str(trend):<12} {str(near52):<10} {vol:.2f}x      {close:.0f} vs {sma50:.0f}{flag}")
    if trend and near52:
        passed += 1

print("-" * 70)
print(f"\n{passed}/{len(tickers)} stocks pass InUptrend + Near52WHigh filters")
print("If 0 pass → bear market confirmed, scanner is correct")
print("If any pass → scanner should find setups, will investigate further")
