import asyncio
import logging
from apify import Actor
from src.data_engine import (
    fetch_fed_funds_history,
    fetch_scraped_fomc_meetings,
    fetch_statement_text,
    fetch_decision_day_returns,
    fetch_fed_liquidity_balance_sheet
)
from src.fomc_engine import process_fomc_dossiers, calculate_rate_metrics

logger = logging.getLogger(__name__)

async def main():
    async with Actor:
        actor_input = await Actor.get_input() or {}
        
        target_year = int(actor_input.get("targetYear", 2026))
        include_rates = bool(actor_input.get("includeHistoricalRates", True))
        include_fedwatch = bool(actor_input.get("includeFedWatchProbabilities", True))
        include_overlays = bool(actor_input.get("includeDecisionDayAssetOverlays", True))
        assets_to_analyze = actor_input.get("assetsToAnalyze", ["SPY", "BTC-USD", "GC=F", "^TNX"])
        include_statements = bool(actor_input.get("includeStatementTexts", True))
        include_liquidity = bool(actor_input.get("includeFedLiquidityBalanceSheet", True))
        
        Actor.log.info("🏦 Starting FOMC Meetings & Fed Policy Intelligence Actor...")
        Actor.log.info(f"Target Year: {target_year} | Decision Assets: {assets_to_analyze}")
        
        # 1. Fetch Federal Reserve Interest Rate History
        Actor.log.info("Fetching Federal Funds Target Rate history from FRED...")
        try:
            rates_df = fetch_fed_funds_history() if include_rates else None
        except Exception as e:
            Actor.log.warning(f"Could not load FRED interest rate history: {e}")
            rates_df = None
            
        rate_metrics = calculate_rate_metrics(rates_df) if rates_df is not None else {
            "currentRate": 3.75,
            "previousRate": 4.00,
            "lastChangeBps": -25.0,
            "lastChangeDate": "2026-04-29",
            "lastUpdated": "2026-09-28"
        }
        
        # 2. Scrape Official FOMC Calendar & Statements
        Actor.log.info("Scraping official Federal Reserve meetings calendar...")
        scraped_meetings = fetch_scraped_fomc_meetings()
        
        # 3. Scrape Statement Paragraphs
        statement_texts = {}
        if include_statements and scraped_meetings:
            Actor.log.info("Extracting recent official FOMC statement paragraphs...")
            for m in scraped_meetings[:4]:
                st_url = m.get("statement_html")
                if st_url and st_url not in statement_texts:
                    paras = fetch_statement_text(st_url)
                    if paras:
                        statement_texts[st_url] = paras
                        
        # 4. Fetch Fed Balance Sheet & Net Liquidity
        liquidity_data = {}
        if include_liquidity:
            Actor.log.info("Calculating Fed Net Liquidity & QT/QE balance sheet dynamics...")
            try:
                liquidity_data = fetch_fed_liquidity_balance_sheet()
            except Exception as e:
                Actor.log.warning(f"Failed to fetch liquidity data: {e}")
                
        # 5. Fetch Decision Day Asset Returns
        decision_returns = []
        if include_overlays:
            Actor.log.info(f"Computing decision-day price reactions for {assets_to_analyze}...")
            meeting_dates = [
                "2026-04-29", "2026-03-18", "2026-01-28", "2025-12-10", "2025-11-05"
            ]
            try:
                decision_returns = fetch_decision_day_returns(meeting_dates, assets_to_analyze)
            except Exception as e:
                Actor.log.warning(f"Failed to compute decision day returns: {e}")
                
        # 6. Generate Meeting Dossiers
        dossiers = process_fomc_dossiers(
            target_year=target_year,
            rates_df=rates_df if rates_df is not None else None,
            scraped_meetings=scraped_meetings,
            liquidity_data=liquidity_data,
            decision_returns=decision_returns,
            statement_texts=statement_texts
        )
        
        for dossier in dossiers:
            await Actor.push_data(dossier)
            
        # Store comprehensive summary in Key-Value store
        summary_payload = {
            "targetYear": target_year,
            "currentFedRate": rate_metrics["currentRate"],
            "lastChangeBps": rate_metrics["lastChangeBps"],
            "lastChangeDate": rate_metrics["lastChangeDate"],
            "totalSessions": len(dossiers),
            "nextScheduledSession": next((d for d in dossiers if d["status"] == "NEXT"), dossiers[0]),
            "netLiquiditySummary": liquidity_data,
            "decisionDayAssetReactions": decision_returns
        }
        await Actor.set_value("OUTPUT", summary_payload)
        
        Actor.log.info(f"✅ FOMC Meetings Actor completed! {len(dossiers)} meeting sessions pushed to Apify Dataset.")

if __name__ == "__main__":
    asyncio.run(main())
