import json
from datetime import datetime
import uuid
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from config import logger, BQ_DATASET, TABLE_RAW, TABLE_PROCESSED, TABLE_AUDIT, GCP_PROJECT_ID

class LoaderError(Exception):
    """Base exception class for Loader Service errors."""
    pass

class BigQueryLoader:
    """Service to handle dataset/table creation and data ingestion in Google BigQuery Sandbox."""

    def __init__(self):
        """Initializes the BigQuery Client and prepares the dataset and table names."""
        try:
            # If GCP_PROJECT_ID is provided in config, use it; otherwise fallback to ADC
            if GCP_PROJECT_ID:
                self.client = bigquery.Client(project=GCP_PROJECT_ID)
                logger.info(f"Initialized BigQuery Client with project: {GCP_PROJECT_ID}")
            else:
                self.client = bigquery.Client()
                logger.info(f"Initialized BigQuery Client with default project: {self.client.project}")
        except Exception as e:
            error_msg = f"Failed to initialize BigQuery Client. Details: {str(e)}"
            logger.error(error_msg)
            raise LoaderError(error_msg) from e

        # Resolve full table references with project ID
        self.project_id = self.client.project
        self.dataset_ref = bigquery.DatasetReference(self.project_id, BQ_DATASET)
        
        self.raw_table_ref = f"{self.project_id}.{TABLE_RAW}"
        self.processed_table_ref = f"{self.project_id}.{TABLE_PROCESSED}"
        self.audit_table_ref = f"{self.project_id}.{TABLE_AUDIT}"

    def create_dataset_and_tables_if_not_exists(self):
        """Creates the target BigQuery dataset and Bronze, Silver, and Audit tables if they do not exist."""
        # 1. Create Dataset
        try:
            self.client.get_dataset(self.dataset_ref)
            logger.info(f"Dataset {BQ_DATASET} already exists.")
        except NotFound:
            logger.info(f"Dataset {BQ_DATASET} not found. Creating a new dataset...")
            dataset = bigquery.Dataset(self.dataset_ref)
            dataset.location = "US"  # Standard location for sandbox
            dataset.description = "Dataset for Weather-Triggered Marketing Data Pipeline"
            try:
                self.client.create_dataset(dataset, timeout=30)
                logger.info(f"Successfully created dataset {BQ_DATASET} in {dataset.location}")
            except Exception as e:
                raise LoaderError(f"Failed to create dataset {BQ_DATASET}: {str(e)}")

        # 2. Define Table Schemas
        raw_schema = [
            bigquery.SchemaField("extracted_at", "TIMESTAMP", mode="REQUIRED", description="Timestamp of when extraction took place"),
            bigquery.SchemaField("latitude", "FLOAT", mode="REQUIRED", description="Target market latitude coordinate"),
            bigquery.SchemaField("longitude", "FLOAT", mode="REQUIRED", description="Target market longitude coordinate"),
            bigquery.SchemaField("raw_payload", "STRING", mode="REQUIRED", description="Complete, unmodified raw hourly JSON API payload string")
        ]

        processed_schema = [
            bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED", description="Hourly timestamp formatted in UTC"),
            bigquery.SchemaField("latitude", "FLOAT", mode="REQUIRED", description="Target market latitude"),
            bigquery.SchemaField("longitude", "FLOAT", mode="REQUIRED", description="Target market longitude"),
            bigquery.SchemaField("timezone", "STRING", mode="NULLABLE", description="Local timezone identifier"),
            bigquery.SchemaField("temperature", "FLOAT", mode="NULLABLE", description="Air temperature in degrees Celsius at 2 meters"),
            bigquery.SchemaField("relative_humidity", "FLOAT", mode="NULLABLE", description="Relative humidity in percentage at 2 meters"),
            bigquery.SchemaField("precipitation", "FLOAT", mode="NULLABLE", description="Precipitation depth in millimeters"),
            bigquery.SchemaField("wind_speed", "FLOAT", mode="NULLABLE", description="Wind speed in km/h at 10 meters"),
            bigquery.SchemaField("apparent_temperature", "FLOAT", mode="NULLABLE", description="Calculated apparent temperature (real-feel)"),
            bigquery.SchemaField("daily_temperature_amplitude", "FLOAT", mode="NULLABLE", description="Calculated diurnal daily max-min temperature amplitude")
        ]

        audit_schema = [
            bigquery.SchemaField("run_id", "STRING", mode="REQUIRED", description="Unique UUID identifying the pipeline execution run"),
            bigquery.SchemaField("started_at", "TIMESTAMP", mode="REQUIRED", description="Execution start timestamp"),
            bigquery.SchemaField("completed_at", "TIMESTAMP", mode="NULLABLE", description="Execution end timestamp"),
            bigquery.SchemaField("status", "STRING", mode="REQUIRED", description="Status code indicating SUCCESS or FAILED"),
            bigquery.SchemaField("records_extracted", "INTEGER", mode="NULLABLE", description="Count of raw hours retrieved"),
            bigquery.SchemaField("records_loaded", "INTEGER", mode="NULLABLE", description="Count of processed hours loaded successfully"),
            bigquery.SchemaField("error_message", "STRING", mode="NULLABLE", description="Error message detail if execution failed")
        ]

        # Helper method to safely create a table if not exists
        def create_table(table_id, schema, table_type_desc):
            try:
                self.client.get_table(table_id)
                logger.info(f"Table {table_id} already exists.")
            except NotFound:
                logger.info(f"Table {table_id} not found. Creating {table_type_desc} table...")
                table = bigquery.Table(table_id, schema=schema)
                # BigQuery Sandbox automatically handles table expiration, but let's make sure it's configurable if needed.
                try:
                    self.client.create_table(table, timeout=30)
                    logger.info(f"Successfully created table {table_id}")
                except Exception as e:
                    raise LoaderError(f"Failed to create table {table_id}: {str(e)}")

        create_table(self.raw_table_ref, raw_schema, "Bronze (Raw)")
        create_table(self.processed_table_ref, processed_schema, "Silver (Processed)")
        create_table(self.audit_table_ref, audit_schema, "Audit (Metadata/Run Log)")

    def load_raw_data(self, latitude: float, longitude: float, raw_payload: dict):
        """
        Saves the complete unmodified raw API payload into the Bronze layer raw table using standard batch-based ingestion.
        
        Args:
            latitude (float): Coordinate latitude
            longitude (float): Coordinate longitude
            raw_payload (dict): Raw dictionary returned from fetcher
        """
        logger.info(f"Loading raw payload to Bronze raw table for ({latitude}, {longitude})")
        
        row = {
            "extracted_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "latitude": latitude,
            "longitude": longitude,
            "raw_payload": json.dumps(raw_payload)
        }
        
        # Using load_table_from_json to perform a safe standard batch-insert job on BigQuery Sandbox
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON
        )
        
        try:
            job = self.client.load_table_from_json([row], self.raw_table_ref, job_config=job_config)
            job.result()  # Wait for the load job to complete
            logger.info("Successfully loaded raw payload to Bronze landing zone.")
        except Exception as e:
            error_msg = f"Failed to load raw JSON payload to BigQuery. Details: {str(e)}"
            logger.error(error_msg)
            raise LoaderError(error_msg) from e

    def load_processed_data(self, records: list) -> int:
        """
        Inserts clean, flat, typed records into the Silver analytical zone processed table.
        
        Args:
            records (list): List of flattened weather dictionaries from transformer.
            
        Returns:
            int: Number of records successfully loaded.
        """
        if not records:
            logger.warning("No processed records available to load. Skipping.")
            return 0
            
        logger.info(f"Loading {len(records)} records into Silver processed table...")
        
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON
        )
        
        try:
            job = self.client.load_table_from_json(records, self.processed_table_ref, job_config=job_config)
            job.result()  # Wait for job completion
            logger.info(f"Successfully loaded {len(records)} records to Silver analytical zone.")
            return len(records)
        except Exception as e:
            error_msg = f"Failed to load processed records to BigQuery. Details: {str(e)}"
            logger.error(error_msg)
            raise LoaderError(error_msg) from e

    def log_run(self, run_id: str, started_at: datetime, completed_at: datetime, status: str, 
                records_extracted: int = 0, records_loaded: int = 0, error_message: str = None):
        """
        Appends run details to the Audit Run Ledger (pipeline_runs_log).
        
        Args:
            run_id (str): Unique execution run identifier.
            started_at (datetime): Timestamp when job started.
            completed_at (datetime): Timestamp when job finished.
            status (str): SUCCESS or FAILED.
            records_extracted (int): Extracted count.
            records_loaded (int): Loaded count.
            error_message (str): Details of any failure.
        """
        logger.info(f"Auditing pipeline run. Run ID: {run_id}, Status: {status}")
        
        audit_row = {
            "run_id": run_id,
            "started_at": started_at.strftime("%Y-%m-%d %H:%M:%S"),
            "completed_at": completed_at.strftime("%Y-%m-%d %H:%M:%S") if completed_at else None,
            "status": status,
            "records_extracted": records_extracted,
            "records_loaded": records_loaded,
            "error_message": error_message
        }
        
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON
        )
        
        try:
            job = self.client.load_table_from_json([audit_row], self.audit_table_ref, job_config=job_config)
            job.result()
            logger.info("Successfully registered audit logs to pipeline_runs_log.")
        except Exception as e:
            # We log the error but don't crash to let the primary exception bubbles up/exits correctly
            logger.critical(f"FATAL: Audit table loading failed. Could not write log! Details: {str(e)}")
