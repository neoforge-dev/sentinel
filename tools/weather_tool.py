"""
Tool for fetching current weather data using OpenWeatherMap API.
"""

import os
import requests
import logging
import json

logger = logging.getLogger(__name__)

OPENWEATHERMAP_API_URL = "https://api.openweathermap.org/data/2.5/weather"

def get_current_weather(location: str) -> dict:
    """
    Fetches the current weather for a specified location.

    Args:
        location: The city name and optional country code (e.g., "London,UK").

    Returns:
        A dictionary containing weather data (temp, description, humidity, wind) 
        or an error message.
    """
    api_key = os.environ.get("OPENWEATHERMAP_API_KEY")
    if not api_key:
        logger.error("OpenWeatherMap API key not found in environment variable OPENWEATHERMAP_API_KEY.")
        return {"success": False, "error": "API key for OpenWeatherMap not configured."}

    params = {
        "q": location,
        "appid": api_key,
        "units": "metric"  # Use metric units (Celsius)
    }

    try:
        response = requests.get(OPENWEATHERMAP_API_URL, params=params, timeout=10)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        
        data = response.json()
        
        # Extract relevant information
        if "main" in data and "weather" in data and "wind" in data:
            weather_info = {
                "location": data.get("name", location.split(',')[0]),
                "temperature_celsius": data["main"].get("temp"),
                "feels_like_celsius": data["main"].get("feels_like"),
                "humidity_percent": data["main"].get("humidity"),
                "description": data["weather"][0].get("description", "N/A") if data["weather"] else "N/A",
                "wind_speed_mps": data["wind"].get("speed"),
            }
            return {"success": True, "weather": weather_info}
        else:
            logger.warning(f"Unexpected API response format from OpenWeatherMap: {data}")
            return {"success": False, "error": "Unexpected API response format.", "raw_data": data}
            
    except requests.exceptions.HTTPError as http_err:
        status_code = http_err.response.status_code
        logger.error(f"HTTP error occurred: {http_err}")
        if status_code == 401:
             return {"success": False, "error": "Invalid OpenWeatherMap API key."}
        elif status_code == 404:
             return {"success": False, "error": f"Location '{location}' not found."}
        else:
             return {"success": False, "error": f"HTTP error {status_code} occurred."}
    except requests.exceptions.ConnectionError:
        logger.error("Connection error connecting to OpenWeatherMap.")
        return {"success": False, "error": "Could not connect to weather service."}
    except requests.exceptions.Timeout:
        logger.error("Timeout connecting to OpenWeatherMap.")
        return {"success": False, "error": "Request to weather service timed out."}
    except requests.exceptions.RequestException as err:
        logger.error(f"An error occurred during weather request: {err}")
        return {"success": False, "error": f"An error occurred: {err}"}
    except Exception as e:
        logger.exception("An unexpected error occurred in get_current_weather")
        return {"success": False, "error": f"An unexpected error occurred: {str(e)}"}

if __name__ == '__main__':
    # Example usage (requires OPENWEATHERMAP_API_KEY env var)
    logging.basicConfig(level=logging.INFO)
    city = input("Enter city name (e.g., London,UK): ")
    if city:
        weather = get_current_weather(city)
        print(json.dumps(weather, indent=2))
    else:
        print("No city entered.") 