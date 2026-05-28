-- =========================================================================
-- 📊 WEATHER TRIGGERED MARKETING ANALYTICS SUMMARY QUERY
-- =========================================================================
-- Core Objectives:
-- 1. Aggregate hourly weather data into daily high-value marketing profiles.
-- 2. Calculate daily extremes, real-feel heat indexes, and diurnal volatility.
-- 3. Apply semantic triggers for ad placements based on environmental stress thresholds.
-- 4. Enforce robust null/zero-division safety using COALESCE and SAFE_DIVIDE.
-- =========================================================================

WITH daily_weather_aggregates AS (
  SELECT
    -- Truncate hourly timestamp to standard date format
    EXTRACT(DATE FROM timestamp) AS weather_date,
    latitude,
    longitude,
    MAX(timezone) AS location_timezone,
    
    -- Standard meteorological aggregations
    ROUND(AVG(temperature), 2) AS avg_temperature,
    ROUND(MIN(temperature), 2) AS min_temperature,
    ROUND(MAX(temperature), 2) AS max_temperature,
    ROUND(AVG(relative_humidity), 2) AS avg_relative_humidity,
    ROUND(SUM(precipitation), 2) AS total_precipitation,
    ROUND(MAX(wind_speed), 2) AS max_wind_speed,
    
    -- Advanced marketing and thermal stress KPIs
    ROUND(MAX(apparent_temperature), 2) AS max_apparent_temperature,
    
    -- Diurnal amplitude (extreme daily temperature swings)
    -- Fallback to calculated daily max-min if the pre-computed column is null
    ROUND(
      COALESCE(
        MAX(daily_temperature_amplitude), 
        (MAX(temperature) - MIN(temperature))
      ), 
      2
    ) AS diurnal_temperature_amplitude
  FROM
    `weather_triggered_marketing.processed_weather_data`
  GROUP BY
    weather_date,
    latitude,
    longitude
)

SELECT
  weather_date,
  latitude,
  longitude,
  location_timezone,
  avg_temperature,
  min_temperature,
  max_temperature,
  avg_relative_humidity,
  total_precipitation,
  max_wind_speed,
  max_apparent_temperature,
  diurnal_temperature_amplitude,

  -- Safe Metrics using SAFE_DIVIDE and COALESCE
  -- Ratio of Precipitation to average humidity (Marketing interest for damp/muggy conditions)
  ROUND(
    COALESCE(
      SAFE_DIVIDE(total_precipitation, avg_relative_humidity), 
      0.0
    ), 
    4
  ) AS precipitation_humidity_ratio,

  -- =========================================================================
  -- 🎯 MARKETING TRIGGERS / SEGMENTATION LOGIC
  -- =========================================================================
  -- 1. Extreme Heat Alert (Temperature exceeds 35°C): Trigger cooling product ads (beverages, ACs)
  CASE 
    WHEN max_temperature > 35.0 THEN TRUE 
    ELSE FALSE 
  END AS trigger_extreme_heat_ads,

  -- 2. Heavy Rain Alert (Precipitation exceeds 5mm): Trigger ride-share, umbrella, or indoor-activity ads
  CASE 
    WHEN total_precipitation > 5.0 THEN TRUE 
    ELSE FALSE 
  END AS trigger_umbrella_ads,

  -- 3. Real-feel Thermal Stress Alert (Apparent temperature exceeds 38°C): Trigger health/dehydration alerts
  CASE 
    WHEN max_apparent_temperature > 38.0 THEN TRUE 
    ELSE FALSE 
  END AS trigger_heat_stress_alerts,

  -- 4. Thermal Volatility Alert (Diurnal swing exceeds 12°C): Trigger apparel ads (layering garments)
  CASE 
    WHEN diurnal_temperature_amplitude > 12.0 THEN TRUE 
    ELSE FALSE 
  END AS trigger_layering_apparel_ads

FROM
  daily_weather_aggregates
ORDER BY
  weather_date DESC,
  latitude,
  longitude;
