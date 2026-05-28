import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Base Directory of the Project
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file
load_dotenv(dotenv_path=BASE_DIR / ".env")

# =========================================================================
# 📝 LOGGING CONFIGURATION
# =========================================================================
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "pipeline.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("weather_pipeline")

# =========================================================================
# 🌐 GOOGLE BIGQUERY CONFIGURATIONS
# =========================================================================
# BigQuery client automatically looks for standard GCP env vars or ADC.
# If a specific project is configured, we use it.
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")  # Optional: Let BQ SDK fallback to default credentials if not set
BQ_DATASET = os.getenv("BQ_DATASET", "weather_triggered_marketing")

# Table Definitions
TABLE_RAW = f"{BQ_DATASET}.raw_weather_data"
TABLE_PROCESSED = f"{BQ_DATASET}.processed_weather_data"
TABLE_AUDIT = f"{BQ_DATASET}.pipeline_runs_log"

# =========================================================================
# 📍 DEFAULT TARGET MARKETING HUBS (COORDINATES)
# =========================================================================
MARKETING_LOCATIONS = {
    "New York": {"latitude": 40.7128, "longitude": -74.0060},
    "London": {"latitude": 51.5074, "longitude": -0.1278},
    "Tokyo": {"latitude": 35.6762, "longitude": 139.6503},
    "Sydney": {"latitude": -33.8688, "longitude": 151.2093}
}

# =========================================================================
# 🚨 failure SMTP ALERTING CONFIGURATIONS
# =========================================================================
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
ALERT_RECEIVER_EMAIL = os.getenv("ALERT_RECEIVER_EMAIL", "alerts@tacheon.in")
ALERT_SENDER_EMAIL = os.getenv("ALERT_SENDER_EMAIL", "pipeline-alerts@tacheon.in")

# Flag to mock emails during tests if real SMTP parameters are missing
MOCK_ALERTING = os.getenv("MOCK_ALERTING", "true").lower() in ("true", "1", "yes")
