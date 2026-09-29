# FOMC Meetings & Fed Policy Intelligence 🏦🇺🇸

**FOMC Meetings & Fed Policy Intelligence** is a comprehensive Federal Reserve quantitative intelligence Actor on Apify. It extracts official FOMC calendars, historical Federal Funds target rates, CME FedWatch market-implied rate cut/hike probabilities, official press statement paragraphs, decision-day multi-asset price reaction overlays, and Fed Net Liquidity balance sheet metrics (QT/QE).

---

## 🌟 Key Features

1. **Official FOMC Meeting Calendar & Status:**
   - Detailed session schedule with start/end dates, SEP (Summary of Economic Projections / Dot Plot) indicators, and real-time days countdown (`Closed`, `NEXT`, `Scheduled`).

2. **Historical Federal Funds Target Rates (FRED Integration):**
   - Seamless tracking of upper target rate bounds (`DFEDTARU`), historical target rates (`DFEDTAR`), and effective rates (`DFF`).
   - Computes current rate, previous rate, last change date, and basis points delta (+/- bps).

3. **CME FedWatch Implied Rate Probabilities:**
   - Probabilities distribution for upcoming policy decisions: **Pause/Hold**, **Cut 25 bps**, **Cut 50+ bps**, and forward-priced interest rate path across all upcoming meetings.

4. **Day-of-Decision (Wednesday) Asset Price Reaction Overlays:**
   - Computes actual percentage returns on policy announcement days across equities (**SPY**), cryptocurrency (**BTC-USD**), safe-haven commodities (**GC=F** Gold), and benchmark bond yields (**^TNX** 10Y Treasury).

5. **Official Statement & Minutes Document Scraping:**
   - Scrapes official Federal Reserve press release statement URLs (HTML/PDF) and minutes (HTML/PDF), extracting clean text paragraphs.

6. **Federal Reserve Net Liquidity & Balance Sheet Tracker (QT/QE):**
   - Tracks Fed Total Assets (`WALCL`), Reverse Repo Agreements (`WLRRAL`), Treasury General Account (`WDTGAL`), and computes **Net Fed Liquidity = WALCL - (WLRRAL + WDTGAL)** with 30-day liquidity momentum.

---

## 📥 Input Configuration

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `targetYear` | `integer` | `2026` | Calendar year for FOMC schedule meetings (2020–2030). |
| `includeHistoricalRates` | `boolean` | `true` | Fetch Federal Funds Target and Effective rate history from FRED. |
| `includeFedWatchProbabilities` | `boolean` | `true` | Model CME FedWatch rate hike/cut probability distributions. |
| `includeDecisionDayAssetOverlays` | `boolean` | `true` | Compute exact day-of-decision price moves for benchmark assets. |
| `assetsToAnalyze` | `array` | `["SPY", "BTC-USD", "GC=F", "^TNX"]` | Tickers to analyze on decision days. |
| `includeStatementTexts` | `boolean` | `true` | Scrape clean paragraphs from recent Federal Reserve press releases. |
| `includeFedLiquidityBalanceSheet` | `boolean` | `true` | Track Fed balance sheet assets and Net Liquidity (QT/QE). |

---

## 📤 Output Schema

```json
{
  "recordType": "FOMC_MEETING_SESSION",
  "year": 2026,
  "meetingDates": "Mar 17–18, 2026",
  "meetingStartDate": "2026-03-17",
  "meetingEndDate": "2026-03-18",
  "hasSepProjections": true,
  "status": "Closed",
  "daysRemaining": 0,
  "currentFedRate": 3.75,
  "lastChangeBps": -25.0,
  "lastChangeDate": "2026-04-29",
  "actionSummary": "Cut 25 bps (to 4.00%)",
  "impliedPauseProbPct": 64.2,
  "impliedCut25ProbPct": 31.8,
  "impliedCut50ProbPct": 4.0,
  "assetDecisionDayReturns": {
    "SPY": 1.25,
    "BTC-USD": 3.42,
    "GC=F": -0.45,
    "^TNX": -2.10
  },
  "statementHtml": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260318a.htm",
  "statementParagraphs": [
    "Recent indicators suggest that economic activity has continued to expand at a solid pace...",
    "The Committee decided to lower the target range for the federal funds rate by 25 basis points..."
  ],
  "fedNetLiquidity": {
    "totalAssetsBillions": 6850.2,
    "reverseRepoBillions": 240.5,
    "treasuryAccountBillions": 720.1,
    "netLiquidityBillions": 5889.6,
    "policyRegime": "Quantitative Tightening (QT)"
  }
}
```

---

## 🚀 Local Run

```bash
uv run --with apify --with pandas --with numpy --with yfinance --with requests --with beautifulsoup4 --with pytz --with python-dateutil python -m src.main
```
