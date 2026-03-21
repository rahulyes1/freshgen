# ============================================================
# NIFTY 500 UNIVERSE — NSE ticker list for yfinance
# ============================================================
# All tickers use the .NS suffix (NSE) for yfinance compatibility.
# Organised by sector / market cap tier.
# Source: NSE India Nifty 500 index constituents.
# Last updated: March 2026
#
# To get the live/latest list from NSE:
#   python nifty500_universe.py --fetch
# ============================================================

# ── Nifty 50 (Large Cap Leaders) ─────────────────────────────
NIFTY_50 = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "KOTAKBANK.NS", "LT.NS", "SBIN.NS",
    "AXISBANK.NS", "BAJFINANCE.NS", "BHARTIARTL.NS", "ASIANPAINT.NS",
    "MARUTI.NS", "TITAN.NS", "SUNPHARMA.NS", "ULTRACEMCO.NS", "WIPRO.NS",
    "BAJAJFINSV.NS", "NESTLEIND.NS", "POWERGRID.NS", "TECHM.NS",
    "ADANIENT.NS", "ONGC.NS", "NTPC.NS", "JSWSTEEL.NS", "TATAMOTORS.NS",
    "M&M.NS", "HCLTECH.NS", "ADANIPORTS.NS", "TATASTEEL.NS", "COALINDIA.NS",
    "DIVISLAB.NS", "DRREDDY.NS", "CIPLA.NS", "BPCL.NS", "APOLLOHOSP.NS",
    "BAJAJ-AUTO.NS", "EICHERMOT.NS", "BRITANNIA.NS", "SHREECEM.NS",
    "HEROMOTOCO.NS", "INDUSINDBK.NS", "GRASIM.NS", "TATACONSUM.NS",
    "SBILIFE.NS", "HDFCLIFE.NS", "PIDILITIND.NS", "BEL.NS",
]

# ── Nifty Next 50 ─────────────────────────────────────────────
NIFTY_NEXT_50 = [
    "ADANIGREEN.NS", "ADANIPOWER.NS", "ADANITRANS.NS", "AMBUJACEM.NS",
    "ATGL.NS", "ATUL.NS", "BANKBARODA.NS", "BERGEPAINT.NS", "BOSCHLTD.NS",
    "CANBK.NS", "CHOLAFIN.NS", "COLPAL.NS", "CONCOR.NS", "CUMMINSIND.NS",
    "DABUR.NS", "DLF.NS", "DMART.NS", "FLUOROCHEM.NS", "GODREJCP.NS",
    "GODREJPROP.NS", "HAVELLS.NS", "HINDALCO.NS", "ICICIPRULI.NS",
    "ICICIGI.NS", "INDUSTOWER.NS", "IRCTC.NS", "JINDALSTEL.NS",
    "LTIM.NS", "LUPIN.NS", "RADICO.NS", "MOTHERSON.NS", "MUTHOOTFIN.NS",
    "NAUKRI.NS", "NYKAA.NS", "PAGEIND.NS", "PETRONET.NS",
    "PIIND.NS", "PNB.NS", "POLICYBZR.NS", "RECLTD.NS", "SAIL.NS",
    "SRF.NS", "TATACOMM.NS", "TORNTPHARM.NS", "TRENT.NS", "UBL.NS",
    "UNITDSPR.NS", "VBL.NS", "VEDL.NS",
]

# ── Nifty Midcap 150 (High-Growth Swing Candidates) ──────────
NIFTY_MIDCAP = [
    "AARTIIND.NS", "ABCAPITAL.NS", "ABFRL.NS", "ACC.NS", "AIAENG.NS",
    "AJANTPHARM.NS", "ALKEM.NS", "APLLTD.NS", "APOLLOTYRE.NS", "ASTRAL.NS",
    "AAVAS.NS", "BANDHANBNK.NS", "BATAINDIA.NS", "BHARATFORG.NS",
    "BHEL.NS", "BIKAJI.NS", "BLUEDART.NS", "BLUESTARCO.NS", "BSOFT.NS",
    "CAMS.NS", "CANFINHOME.NS", "CARBORUNIV.NS", "CASTROLIND.NS",
    "CEATLTD.NS", "CENTRALBK.NS", "CENTURYPLY.NS", "CESC.NS",
    "CHAMBLFERT.NS", "CLEAN.NS", "COFORGE.NS", "CROMPTON.NS",
    "CYIENT.NS", "DALBHARAT.NS", "DEEPAKNTR.NS", "DELTACORP.NS",
    "DEVYANI.NS", "DHANUKA.NS", "DIXON.NS", "EDELWEISS.NS",
    "EMAMILTD.NS", "ENGINERSIN.NS", "ESCORTS.NS", "EXIDEIND.NS",
    "FEDERALBNK.NS", "FINCABLES.NS", "FINPIPE.NS", "FLUOROCHEM.NS",
    "GAIL.NS", "GALAXYSURF.NS", "GARFIBRES.NS", "GLAND.NS",
    "GLAXO.NS", "GNFC.NS", "GODFRYPHLP.NS", "GPPL.NS",
    "GRANULES.NS", "GSPL.NS", "GUJGASLTD.NS", "HAPPSTMNDS.NS",
    "HFCL.NS", "HINDPETRO.NS", "HONAUT.NS", "HSCL.NS",
    "IDFCFIRSTB.NS", "IFCI.NS", "IIFL.NS", "INDHOTEL.NS",
    "INDIGO.NS", "INOXWIND.NS", "IOC.NS", "IPCALAB.NS",
    "JKCEMENT.NS", "JKPAPER.NS", "JKTYRE.NS", "JUBLFOOD.NS",
    "JUBILANT.NS", "JUBLPHARMA.NS", "KAJARIACER.NS", "KALPATPOWR.NS",
    "KANSAINER.NS", "KARURVYSYA.NS", "KEI.NS", "KFINTECH.NS",
    "KIMS.NS", "KMARTHOTEL.NS", "KNRCON.NS", "KPITTECH.NS",
    "KRBL.NS", "LALPATHLAB.NS", "LAURUSLABS.NS", "LICHSGFIN.NS",
    "LICI.NS", "LINDEINDIA.NS", "LTF.NS", "LTTS.NS",
    "MAHABANK.NS", "MAHINDCIE.NS", "MANKIND.NS", "MARICO.NS",
    "MAXHEALTH.NS", "MCX.NS", "METROPOLIS.NS", "MINDTREE.NS",
    "MPHASIS.NS", "MRF.NS", "NATCOPHARM.NS", "NIACL.NS",
    "NLCINDIA.NS", "NMDC.NS", "NOCIL.NS", "NUVOCO.NS",
    "OBEROIRLTY.NS", "OIL.NS", "OFSS.NS", "OLECTRA.NS",
    "PERSISTENT.NS", "PFIZER.NS", "PHOENIXLTD.NS", "POLYMED.NS",
    "PRESTIGE.NS", "PRINCEPIPE.NS", "PRIVISCL.NS", "PSUBNKBEES.NS",
    "PVRINOX.NS", "RADICO.NS", "RAJESHEXPO.NS", "RAMCOCEM.NS",
    "RATNAMANI.NS", "RBA.NS", "REDINGTON.NS", "RITES.NS",
    "ROSSARI.NS", "ROUTE.NS", "SANOFI.NS", "SAPPHIRE.NS",
    "SCHAEFFLER.NS", "SEQUENT.NS", "SHYAMMETL.NS", "SIEMENS.NS",
    "SKFINDIA.NS", "SOBHA.NS", "SONACOMS.NS", "SOMANYCER.NS",
    "SPANDANA.NS", "STAR.NS", "STARHEALTH.NS", "STLTECH.NS",
    "SUMICHEM.NS", "SUNCLAYLTD.NS", "SUNFLAG.NS", "SUPREMEIND.NS",
    "SUVENPHAR.NS", "SWSOLAR.NS", "SYMPHONY.NS", "TANLA.NS",
    "TATACHEM.NS", "TATAELXSI.NS", "TATAINVEST.NS", "TATAPOWER.NS",
    "TCNSBRANDS.NS", "TEAMLEASE.NS", "THERMAX.NS", "TIMKEN.NS",
    "TITAGARH.NS", "TORNTPOWER.NS", "TTKPRESTIG.NS", "TV18BRDCST.NS",
    "TVSMOTOR.NS", "UCOBANK.NS", "UJJIVAN.NS", "UJJIVANSFB.NS",
    "UTIAMC.NS", "VAIBHAVGBL.NS", "VARROC.NS", "VBL.NS",
    "VINATIORGA.NS", "VOLTAMP.NS", "VOLTAS.NS", "VSTIND.NS",
    "WELCORP.NS", "WELSPUNLIV.NS", "WESTLIFE.NS", "WHIRLPOOL.NS",
    "WIPRO.NS", "WOCKPHARMA.NS", "YESBANK.NS", "ZEEL.NS",
    "ZENTEC.NS", "ZOMATO.NS", "ZYDUSLIFE.NS",
]

# ── High-Growth / Momentum Favourites (Swing Trading Focus) ──
MOMENTUM_PICKS = [
    # Defence & Capital Goods (hot sector 2023-25)
    "HAL.NS", "BEL.NS", "GRSE.NS", "COCHINSHIP.NS", "MAZDOCK.NS",
    "BHEL.NS", "AIAENG.NS", "BEML.NS", "DATAPATTNS.NS", "PARAS.NS",
    # Railways
    "IRFC.NS", "RVNL.NS", "RAILTEL.NS", "IRCON.NS", "TITAGARH.NS",
    # PSU Banks (momentum plays)
    "SBIN.NS", "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "UNIONBANK.NS",
    # Renewables
    "ADANIGREEN.NS", "TATAPOWER.NS", "SJVN.NS", "NHPC.NS", "CESC.NS",
    # EV / Auto Ancillary
    "TVSMOTOR.NS", "BAJAJ-AUTO.NS", "SONACOMS.NS",
    # IT Mid-cap (high momentum)
    "PERSISTENT.NS", "COFORGE.NS", "LTTS.NS", "KPITTECH.NS",
    "TANLA.NS", "HAPPSTMNDS.NS", "BSOFT.NS",
    # Specialty Chemicals
    "DEEPAKNTR.NS", "ATUL.NS", "SRF.NS", "AARTIIND.NS", "VINATIORGA.NS",
    # Consumer / Retail
    "TRENT.NS", "DMART.NS", "NYKAA.NS", "DEVYANI.NS", "JUBLFOOD.NS",
    # Hospitals / Healthcare
    "APOLLOHOSP.NS", "MAXHEALTH.NS", "KIMS.NS", "FORTIS.NS",
    # Infra / Real Estate
    "DLF.NS", "GODREJPROP.NS", "PRESTIGE.NS", "PHOENIXLTD.NS",
    "OBEROIRLTY.NS", "SOBHA.NS",
    # Financials
    "BAJFINANCE.NS", "CHOLAFIN.NS", "MUTHOOTFIN.NS", "IIFL.NS",
    "CANFINHOME.NS", "AAVAS.NS",
]

# ── Full Nifty 500 (deduplicated) ─────────────────────────────
def get_nifty500() -> list[str]:
    """Return the full deduplicated Nifty 500 ticker list."""
    seen = set()
    result = []
    for t in NIFTY_50 + NIFTY_NEXT_50 + NIFTY_MIDCAP + MOMENTUM_PICKS:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def get_momentum_universe() -> list[str]:
    """
    Return a curated high-growth subset — best for swing trading.
    Combines Nifty Next 50, Midcap leaders, and momentum picks.
    (~200 tickers — practical for backtesting)
    """
    seen = set()
    result = []
    for t in NIFTY_50 + NIFTY_NEXT_50 + MOMENTUM_PICKS:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


_CACHE_FILE = __file__.replace("nifty500_universe.py", "data/nifty500_cache.txt")


def fetch_live_nifty500() -> list[str]:
    """
    Fetch the real Nifty 500 list (all 500 stocks) from NSE India.
    Result is cached to data/nifty500_cache.txt and refreshed once per day.
    Falls back to hardcoded ~250-stock list if NSE is unreachable.
    """
    import os, time

    # ── Serve from daily cache ─────────────────────────────────
    if os.path.exists(_CACHE_FILE):
        age_hours = (time.time() - os.path.getmtime(_CACHE_FILE)) / 3600
        if age_hours < 24:
            with open(_CACHE_FILE) as f:
                tickers = [line.strip() for line in f if line.strip()]
            if len(tickers) > 100:
                print(f"  [Universe] Loaded {len(tickers)} tickers from cache ({age_hours:.1f}h old).")
                return tickers

    # ── Fetch from NSE ─────────────────────────────────────────
    try:
        import requests

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/market-data/live-equity-market",
        }
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers, timeout=10)

        url = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20500"
        resp = session.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        data = resp.json()
        # NSE returns the index itself as first item — skip it
        tickers = [
            f"{item['symbol']}.NS"
            for item in data.get("data", [])
            if item.get("symbol") and item["symbol"] != "NIFTY 500"
        ]

        if len(tickers) < 400:
            raise ValueError(f"Only got {len(tickers)} tickers — NSE response looks incomplete")

        # Save to cache
        os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)
        with open(_CACHE_FILE, "w") as f:
            f.write("\n".join(tickers))

        print(f"  [Universe] Fetched {len(tickers)} tickers from NSE and cached.")
        return tickers

    except Exception as e:
        print(f"  [Universe] NSE fetch failed ({e}). Using hardcoded list ({len(get_nifty500())} stocks).")
        return get_nifty500()


def get_full_universe() -> list[str]:
    """
    Best-effort full Nifty 500 universe.
    Tries live NSE fetch first, falls back to hardcoded ~250.
    Use this as the default for scanning.
    """
    return fetch_live_nifty500()


# ── CLI usage ─────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true", help="Fetch live list from NSE")
    parser.add_argument("--count", action="store_true", help="Print ticker count")
    args = parser.parse_args()

    if args.fetch:
        tickers = fetch_live_nifty500()
    else:
        tickers = get_nifty500()

    if args.count:
        print(f"Nifty 500 Universe: {len(tickers)} tickers")
    else:
        for t in tickers:
            print(t)
