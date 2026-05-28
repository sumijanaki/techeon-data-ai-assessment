import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from config import logger

class FetcherError(Exception):
    """Base exception class for Fetcher Service errors."""
    pass

class WeatherFetcher:
    """Fetcher Service to connect to and extract data from the Open-Meteo API."""

    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, timeout: int = 10, max_retries: int = 3):
        """
        Initializes the fetcher with default timeout and retry settings.
        
        Args:
            timeout (int): Seconds to wait before raising a connection timeout.
            max_retries (int): Number of retry attempts for 429, 500, 502, 503, 504.
        """
        self.timeout = timeout
        
        # Configure standard HTTP Session with robust exponential backoff retries
        self.session = requests.Session()
        retries = Retry(
            total=max_retries,
            backoff_factor=1.0,  # Delays: 1s, 2s, 4s...
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        logger.info(f"Initialized WeatherFetcher with max_retries={max_retries}, timeout={timeout}s")

    def fetch_weather(self, latitude: float, longitude: float, start_date: str, end_date: str) -> dict:
        """
        Fetches hourly weather parameters from Open-Meteo API for a specific coordinate and date range.

        Args:
            latitude (float): Latitude coordinate.
            longitude (float): Longitude coordinate.
            start_date (str): Start date string in YYYY-MM-DD format.
            end_date (str): End date string in YYYY-MM-DD format.

        Returns:
            dict: Raw API JSON response payload.
        
        Raises:
            FetcherError: If fetching fails due to network, status, or validation issues.
        """
        logger.info(
            f"Initiating extraction: lat={latitude}, lon={longitude}, "
            f"period={start_date} to {end_date}"
        )

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
            "timezone": "auto"
        }

        start_time = time.time()
        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
            duration = time.time() - start_time
            logger.info(f"API Request completed in {duration:.2f}s with status_code={response.status_code}")

            # Check for HTTP Errors
            if response.status_code != 200:
                error_msg = f"API returned non-200 status code: {response.status_code}. Details: {response.text}"
                logger.error(error_msg)
                raise FetcherError(error_msg)

            raw_data = response.json()

            # Basic Validation of JSON structure
            if "hourly" not in raw_data or "time" not in raw_data["hourly"]:
                error_msg = "Corrupted API payload: missing required 'hourly' or 'hourly.time' nodes."
                logger.error(error_msg)
                raise FetcherError(error_msg)

            record_count = len(raw_data["hourly"]["time"])
            logger.info(f"Extraction successful. Retrieved raw payload containing {record_count} hourly records.")
            return raw_data

        except requests.exceptions.Timeout as e:
            error_msg = f"Network Timeout: Open-Meteo API failed to respond within {self.timeout} seconds."
            logger.error(error_msg)
            raise FetcherError(error_msg) from e

        except requests.exceptions.RequestException as e:
            error_msg = f"Network Error: Connection failed. Details: {str(e)}"
            logger.error(error_msg)
            raise FetcherError(error_msg) from e

        except ValueError as e:
            error_msg = f"Parsing Error: API response could not be parsed as JSON. Details: {str(e)}"
            logger.error(error_msg)
            raise FetcherError(error_msg) from e
