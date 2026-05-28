import math
from datetime import datetime
from config import logger

class TransformationError(Exception):
    """Base exception class for Transformation Service errors."""
    pass

class WeatherTransformer:
    """Service to clean, flatten, and enrich nested weather data with marketing metrics."""

    @staticmethod
    def calculate_apparent_temperature(temp_c: float, humidity: float, wind_speed_kmh: float) -> float:
        """
        Calculates the Apparent Temperature (Real Feel / Heat Stress Index) using a 
        standard meteorological formula combining temperature, water vapor pressure, and wind speed.
        
        Formula:
            AT = T + 0.33 * e - 0.70 * ws - 4.00
        Where:
            T  = Temperature in °C
            e  = Water vapor pressure in hPa
            ws = Wind speed in m/s (wind_speed_kmh / 3.6)
            e  = (RH / 100) * 6.105 * exp((17.27 * T) / (237.7 + T))
            
        Args:
            temp_c (float): Temperature in degrees Celsius.
            humidity (float): Relative humidity in percentage (0 to 100).
            wind_speed_kmh (float): Wind speed in kilometers per hour.
            
        Returns:
            float: Calculated apparent temperature in °C rounded to 2 decimal places.
        """
        try:
            # Handle possible null inputs safely
            if temp_c is None or humidity is None or wind_speed_kmh is None:
                return None

            # 1. Convert wind speed from km/h to m/s
            ws = wind_speed_kmh / 3.6

            # 2. Calculate water vapor pressure (e) in hPa
            # Standard Magnus-Tetens formula for saturated vapor pressure
            e_sat = 6.105 * math.exp((17.27 * temp_c) / (237.7 + temp_c))
            e = (humidity / 100.0) * e_sat

            # 3. Calculate apparent temperature (AT)
            at = temp_c + (0.33 * e) - (0.70 * ws) - 4.0
            return round(at, 2)
        except Exception as e:
            logger.warning(f"Error calculating apparent temperature for T={temp_c}, RH={humidity}: {str(e)}")
            return None

    def transform(self, raw_data: dict) -> list:
        """
        Processes the nested raw API payload into a clean, flat, typed tabular structure.
        Additionally computes derived fields (apparent temperature and daily temperature amplitude).

        Args:
            raw_data (dict): Raw JSON dictionary fetched from the API.

        Returns:
            list: A list of flattened, validated dictionaries ready for database load.

        Raises:
            TransformationError: If data arrays are inconsistent or parsing fails.
        """
        logger.info("Initiating transformation, flattening, and KPI derivations.")

        # Extract metadata from top-level response
        latitude = raw_data.get("latitude")
        longitude = raw_data.get("longitude")
        timezone = raw_data.get("timezone", "UTC")

        hourly = raw_data.get("hourly", {})
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        humidities = hourly.get("relative_humidity_2m", [])
        precips = hourly.get("precipitation", [])
        winds = hourly.get("wind_speed_10m", [])

        # Validate array sizes
        lengths = {
            "time": len(times),
            "temperature": len(temps),
            "humidity": len(humidities),
            "precipitation": len(precips),
            "wind_speed": len(winds)
        }

        if len(set(lengths.values())) > 1:
            error_msg = f"Inconsistent array lengths returned from API: {lengths}"
            logger.error(error_msg)
            raise TransformationError(error_msg)

        total_records = lengths["time"]
        if total_records == 0:
            logger.warning("Empty dataset received. Skipping transformation.")
            return []

        # ---------------------------------------------------------------------
        # Pre-compute Daily Extremes for Diurnal Amplitude Calculation
        # ---------------------------------------------------------------------
        # We group hourly temperatures by date (YYYY-MM-DD) to calculate daily min/max
        daily_temps = {}
        for index in range(total_records):
            time_str = times[index]
            temp = temps[index]
            if time_str and temp is not None:
                date_str = time_str.split("T")[0]
                if date_str not in daily_temps:
                    daily_temps[date_str] = []
                daily_temps[date_str].append(temp)

        daily_amplitudes = {}
        for date_str, temp_list in daily_temps.items():
            if temp_list:
                daily_amplitudes[date_str] = round(max(temp_list) - min(temp_list), 2)

        # ---------------------------------------------------------------------
        # Flat Array Building and Formatting
        # ---------------------------------------------------------------------
        processed_records = []
        for i in range(total_records):
            raw_time_str = times[i]
            
            # Enforce clean ISO Datetime format compatible with BigQuery
            try:
                dt_obj = datetime.strptime(raw_time_str, "%Y-%m-%dT%H:%M")
                formatted_timestamp = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
                date_key = raw_time_str.split("T")[0]
            except Exception as e:
                logger.warning(f"Invalid timestamp '{raw_time_str}' encountered at index {i}: {str(e)}")
                continue

            # Standardize numeric values with null-safety
            temp = float(temps[i]) if temps[i] is not None else None
            humidity = float(humidities[i]) if humidities[i] is not None else None
            precipitation = float(precips[i]) if precips[i] is not None else None
            wind_speed = float(winds[i]) if winds[i] is not None else None

            # 🧠 DERIVED FIELD 1: Apparent Temperature (Real Feel / Heat Stress Indicator)
            apparent_temp = self.calculate_apparent_temperature(temp, humidity, wind_speed)

            # 🧠 DERIVED FIELD 2: Daily Temperature Amplitude (Volatility Metric)
            temp_amplitude = daily_amplitudes.get(date_key)

            # Construct clean, flat, descriptive record
            record = {
                "timestamp": formatted_timestamp,
                "latitude": float(latitude) if latitude is not None else None,
                "longitude": float(longitude) if longitude is not None else None,
                "timezone": str(timezone),
                "temperature": temp,
                "relative_humidity": humidity,
                "precipitation": precipitation,
                "wind_speed": wind_speed,
                "apparent_temperature": apparent_temp,
                "daily_temperature_amplitude": temp_amplitude
            }
            processed_records.append(record)

        logger.info(
            f"Transformation successfully completed. Flat tabular set generated "
            f"with {len(processed_records)} records, including derived apparent temperature "
            f"and amplitude metrics."
        )
        return processed_records
