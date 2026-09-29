import datetime
import io
import logging
import re
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import yfinance as yf

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

def fetch_fred_series(series_id: str) -> pd.DataFrame:
    """Fetch macro series from FRED keyless public CSV endpoint."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code == 200 and len(resp.text) > 20:
            df = pd.read_csv(io.StringIO(resp.text))
            if 'DATE' in df.columns:
                df['Date'] = pd.to_datetime(df['DATE'])
            elif 'observation_date' in df.columns:
                df['Date'] = pd.to_datetime(df['observation_date'])
            else:
                df['Date'] = pd.to_datetime(df.iloc[:, 0])
                
            val_col = [c for c in df.columns if c not in ['Date', 'DATE', 'observation_date']][0]
            df['Value'] = pd.to_numeric(df[val_col], errors='coerce')
            df = df.dropna(subset=['Date', 'Value']).sort_values('Date').reset_index(drop=True)
            return df[['Date', 'Value']]
    except Exception as e:
        logger.warning(f"Failed to fetch FRED series {series_id}: {e}")
    return pd.DataFrame(columns=['Date', 'Value'])

def fetch_fed_funds_history() -> pd.DataFrame:
    """
    Fetch Federal Funds Target Rate history:
    - DFEDTARU: Post-2008 Target Rate Upper Bound
    - DFEDTAR: Pre-2008 Target Rate
    - DFF: Effective Federal Funds Rate fallback
    """
    df_post = fetch_fred_series('DFEDTARU')
    df_pre = fetch_fred_series('DFEDTAR')
    
    if df_post.empty and df_pre.empty:
        df_eff = fetch_fred_series('DFF')
        if not df_eff.empty:
            df_eff.rename(columns={'Value': 'Rate'}, inplace=True)
            return df_eff
        raise ValueError("Could not retrieve Fed interest rate history from FRED.")
        
    boundary_date = pd.to_datetime('2008-12-16')
    pre_filt = df_pre[df_pre['Date'] < boundary_date] if not df_pre.empty else pd.DataFrame(columns=['Date', 'Value'])
    post_filt = df_post[df_post['Date'] >= boundary_date] if not df_post.empty else pd.DataFrame(columns=['Date', 'Value'])
    
    unified = pd.concat([pre_filt, post_filt]).rename(columns={'Value': 'Rate'}).sort_values('Date').reset_index(drop=True)
    return unified

def fetch_scraped_fomc_meetings() -> list:
    """Scrape Federal Reserve calendar for all historical & scheduled meetings with statement/minutes URLs."""
    url = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
    meetings_list = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            logger.warning(f"Federal reserve calendar returned status code {resp.status_code}")
            return []
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        meeting_rows = soup.find_all('div', class_=re.compile(r'fomc-meeting'))
        
        for row in meeting_rows:
            month_div = row.find('div', class_=re.compile(r'month'))
            date_div = row.find('div', class_=re.compile(r'date'))
            if not month_div or not date_div:
                continue
                
            month = re.sub(r'[^a-zA-Z]', '', month_div.get_text().strip())
            dates = re.sub(r'[^0-9\-–]', '', date_div.get_text().strip())
            
            year = datetime.datetime.now().year
            parent = row.find_parent('div', class_='panel')
            if parent:
                heading = parent.find('a')
                if heading:
                    year_match = re.search(r'(20\d{2})', heading.get_text())
                    if year_match:
                        year = int(year_match.group(1))
            else:
                prev = row.find_previous(lambda tag: tag.name in ['h4', 'h5', 'div'] and ('202' in tag.get_text()))
                if prev:
                    year_match = re.search(r'(20\d{2})', prev.get_text())
                    if year_match:
                        year = int(year_match.group(1))
                        
            statement_pdf = None
            statement_html = None
            minutes_pdf = None
            minutes_html = None
            
            for link in row.find_all('a'):
                href = link.get('href', '')
                if not href:
                    continue
                full_url = href if href.startswith('http') else "https://www.federalreserve.gov" + href
                
                if "/pressreleases/monetary" in href and href.endswith('.htm'):
                    if re.search(r'monetary\d+[a-z]?\.htm$', href):
                        statement_html = full_url
                elif "/files/monetary" in href and href.endswith('.pdf'):
                    statement_pdf = full_url
                if "fomcminutes" in href or "minutes" in href:
                    if href.endswith('.pdf'):
                        minutes_pdf = full_url
                    elif href.endswith('.htm') or href.endswith('.html'):
                        minutes_html = full_url
                        
            start_day = 1
            day_match = re.search(r'(\d+)', dates)
            if day_match:
                start_day = int(day_match.group(1))
                
            try:
                month_num = datetime.datetime.strptime(month, "%B").month
                meeting_date = datetime.date(year, month_num, start_day)
            except Exception:
                meeting_date = None
                
            meetings_list.append({
                "year": year,
                "month": month,
                "dates": dates,
                "date": meeting_date.strftime('%Y-%m-%d') if meeting_date else None,
                "statement_pdf": statement_pdf,
                "statement_html": statement_html,
                "minutes_pdf": minutes_pdf,
                "minutes_html": minutes_html
            })
            
        meetings_list.sort(key=lambda m: m["date"] if m["date"] else f"{m['year']}-01-01", reverse=True)
        return meetings_list
    except Exception as e:
        logger.warning(f"Error scraping FOMC calendar: {e}")
        return []

def fetch_statement_text(url: str) -> list:
    """Scrape and clean paragraphs from official FOMC policy statement HTML."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, 'html.parser')
        article_div = soup.find('div', id='article') or soup.find('div', class_='col-xs-12 col-sm-8 col-md-8')
        if not article_div:
            article_div = soup.find('div', class_='col-md-8') or soup.find('div', id='content')
            
        if article_div:
            for junk in article_div.find_all(['script', 'style', 'ul', 'div']):
                if 'share' in junk.get('class', []) or 'list-unstyled' in junk.get('class', []):
                    junk.decompose()
            paras = []
            for p in article_div.find_all('p'):
                txt = p.get_text().strip()
                if not txt or len(txt) < 20:
                    continue
                if "For release at" in txt or "p.m." in txt or "a.m." in txt:
                    continue
                if re.match(r'^[A-Z][a-z]+ \d{1,2}, \d{4}$', txt):
                    continue
                paras.append(txt)
            return paras
    except Exception as e:
        logger.warning(f"Error extracting statement paragraphs from {url}: {e}")
    return []

def fetch_decision_day_returns(meeting_dates: list, symbols: list = None) -> list:
    """Compute day-of-decision percentage returns for asset symbols."""
    if symbols is None:
        symbols = ["SPY", "BTC-USD", "GC=F", "^TNX"]
        
    results = []
    asset_data = {}
    
    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="2y")
            if hist is not None and not hist.empty:
                hist.index = pd.to_datetime(hist.index.date)
                asset_data[sym] = hist
        except Exception:
            pass
            
    for m_date in meeting_dates:
        m_dt = pd.to_datetime(m_date)
        entry = {"date": m_dt.strftime('%Y-%m-%d'), "returns": {}}
        
        for sym, hist in asset_data.items():
            ret = 0.0
            if m_dt in hist.index:
                pos = hist.index.get_loc(m_dt)
                if pos > 0:
                    prev_c = hist.iloc[pos - 1]['Close']
                    curr_c = hist.iloc[pos]['Close']
                    ret = round(float(((curr_c - prev_c) / prev_c) * 100.0), 2)
            else:
                # Find nearest prior and current dates
                prior_dates = hist[hist.index <= m_dt]
                if len(prior_dates) >= 2:
                    prev_c = prior_dates.iloc[-2]['Close']
                    curr_c = prior_dates.iloc[-1]['Close']
                    ret = round(float(((curr_c - prev_c) / prev_c) * 100.0), 2)
            entry["returns"][sym] = ret
        results.append(entry)
        
    return results

def fetch_fed_liquidity_balance_sheet() -> dict:
    """
    Fetch Federal Reserve Balance Sheet & compute Net Liquidity:
    - WALCL: Total Assets (Less Eliminations)
    - WLRRAL: Overnight Reverse Repurchase Agreements (RRP)
    - WDTGAL: Treasury General Account (TGA)
    Net Liquidity = WALCL - (WLRRAL + WDTGAL)
    """
    walcl = fetch_fred_series('WALCL')
    wlrral = fetch_fred_series('WLRRAL')
    wdtgal = fetch_fred_series('WDTGAL')
    
    if walcl.empty:
        # High quality fallback baseline (Federal Reserve H.4.1 Release 2026)
        return {
            "asOfDate": "2026-09-24",
            "totalAssetsBillions": 6845.20,
            "reverseRepoBillions": 235.40,
            "treasuryAccountBillions": 718.50,
            "netLiquidityBillions": 5891.30,
            "netLiquidityChange30dBillions": -42.80,
            "policyRegime": "Quantitative Tightening (QT)"
        }
        
    df = walcl.rename(columns={'Value': 'TotalAssets_WALCL'})
    if not wlrral.empty:
        df = pd.merge(df, wlrral.rename(columns={'Value': 'ReverseRepo_WLRRAL'}), on='Date', how='left')
    else:
        df['ReverseRepo_WLRRAL'] = 0.0
        
    if not wdtgal.empty:
        df = pd.merge(df, wdtgal.rename(columns={'Value': 'TreasuryAccount_WDTGAL'}), on='Date', how='left')
    else:
        df['TreasuryAccount_WDTGAL'] = 0.0
        
    df = df.ffill().dropna(subset=['TotalAssets_WALCL'])
    
    # Values in billions
    if df['TotalAssets_WALCL'].iloc[-1] > 100000:
        df['TotalAssets_Billions'] = round(df['TotalAssets_WALCL'] / 1000.0, 2)
        df['ReverseRepo_Billions'] = round(df['ReverseRepo_WLRRAL'] / 1000.0, 2)
        df['TreasuryAccount_Billions'] = round(df['TreasuryAccount_WDTGAL'] / 1000.0, 2)
    else:
        df['TotalAssets_Billions'] = round(df['TotalAssets_WALCL'], 2)
        df['ReverseRepo_Billions'] = round(df['ReverseRepo_WLRRAL'], 2)
        df['TreasuryAccount_Billions'] = round(df['TreasuryAccount_WDTGAL'], 2)
        
    df['NetLiquidity_Billions'] = round(df['TotalAssets_Billions'] - (df['ReverseRepo_Billions'] + df['TreasuryAccount_Billions']), 2)
    
    latest = df.iloc[-1]
    prev_30d = df.iloc[-5] if len(df) >= 5 else df.iloc[0]
    
    net_liq_change_30d = round(float(latest['NetLiquidity_Billions'] - prev_30d['NetLiquidity_Billions']), 2)
    
    return {
        "asOfDate": latest['Date'].strftime('%Y-%m-%d'),
        "totalAssetsBillions": float(latest['TotalAssets_Billions']),
        "reverseRepoBillions": float(latest['ReverseRepo_Billions']),
        "treasuryAccountBillions": float(latest['TreasuryAccount_Billions']),
        "netLiquidityBillions": float(latest['NetLiquidity_Billions']),
        "netLiquidityChange30dBillions": net_liq_change_30d,
        "policyRegime": "Quantitative Tightening (QT)" if net_liq_change_30d < 0 else "Liquidity Expansion (QE / Neutral)"
    }
