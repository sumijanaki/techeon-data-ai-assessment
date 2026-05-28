import sys
import uuid
import argparse
import traceback
from datetime import datetime, timedelta
from config import logger, MARKETING_LOCATIONS
from pipeline import WeatherFetcher, WeatherTransformer, BigQueryLoader, PipelineAlerter

def parse_arguments():
    """Parses command line arguments for the weather ETL pipeline."""
    parser = argparse.ArgumentParser(description="Weather-Triggered Marketing Ingestion ETL Pipeline")
    parser.add_argument(
        "--start-date", 
        type=str, 
        help="Start date in YYYY-MM-DD format (defaults to 7 days ago)"
    )
    parser.add_argument(
        "--end-date", 
        type=str, 
        help="End date in YYYY-MM-DD format (defaults to today)"
    )
    return parser.parse_args()

def main():
    # 1. Initialize Pipeline Run Details
    run_id = str(uuid.uuid4())
    started_at = datetime.utcnow()
    
    logger.info(f"=========================================================================")
    logger.info(f"🚀 STARTING WEATHER ETL PIPELINE RUN: {run_id}")
    logger.info(f"Time: {started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    logger.info(f"=========================================================================")
    
    # Defaults
    args = parse_arguments()
    end_date = args.end_date or datetime.utcnow().strftime("%Y-%m-%d")
    start_date = args.start_date or (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    loader = None
    records_extracted = 0
    records_loaded = 0
    
    try:
        # 2. Instantiate Services
        fetcher = WeatherFetcher()
        transformer = WeatherTransformer()
        loader = BigQueryLoader()
        
        # 3. Create Dataset and Tables on BigQuery dynamically if missing
        loader.create_dataset_and_tables_if_not_exists()
        
        # 4. Process each Marketing Location
        for location_name, coords in MARKETING_LOCATIONS.items():
            lat = coords["latitude"]
            lon = coords["longitude"]
            
            logger.info(f"📍 Processing location '{location_name}' (lat={lat}, lon={lon}) from {start_date} to {end_date}")
            
            # Phase A: Extract (Raw JSON API payload)
            raw_payload = fetcher.fetch_weather(lat, lon, start_date, end_date)
            extracted_hours_count = len(raw_payload.get("hourly", {}).get("time", []))
            records_extracted += extracted_hours_count
            
            # Phase B: Load Raw (Bronze Zone)
            loader.load_raw_data(lat, lon, raw_payload)
            
            # Phase C: Transform (Flatten and Enrich)
            processed_records = transformer.transform(raw_payload)
            
            # Phase D: Load Processed (Silver Zone)
            loaded_count = loader.load_processed_data(processed_records)
            records_loaded += loaded_count
            
            logger.info(f"✅ Successfully completed ETL flow for '{location_name}'. Loaded {loaded_count} hours.")

        # 5. Success Audit Logging
        completed_at = datetime.utcnow()
        loader.log_run(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            status="SUCCESS",
            records_extracted=records_extracted,
            records_loaded=records_loaded
        )
        
        logger.info(f"=========================================================================")
        logger.info(f"🏆 PIPELINE EXECUTION SUCCESSFUL: Run ID {run_id}")
        logger.info(f"Total Extracted Hours: {records_extracted}")
        logger.info(f"Total Loaded Hours: {records_loaded}")
        logger.info(f"=========================================================================")
        
    except Exception as e:
        completed_at = datetime.utcnow()
        error_msg = str(e)
        traceback_str = traceback.format_exc()
        
        logger.critical(f"❌ PIPELINE RUN FAILED: {error_msg}")
        logger.critical(traceback_str)
        
        # Write FAILED status to Audit Table if loader was initialized
        if loader:
            try:
                loader.log_run(
                    run_id=run_id,
                    started_at=started_at,
                    completed_at=completed_at,
                    status="FAILED",
                    records_extracted=records_extracted,
                    records_loaded=records_loaded,
                    error_message=error_msg
                )
            except Exception as audit_err:
                logger.critical(f"Could not write failure audit log to BigQuery: {str(audit_err)}")
        
        # Fire SMTP / local HTML file alert
        try:
            PipelineAlerter.send_alert_email(error_msg, traceback_str)
        except Exception as alert_err:
            logger.critical(f"Failure in Alerting System: {str(alert_err)}")
            
        sys.exit(1)

if __name__ == "__main__":
    main()
