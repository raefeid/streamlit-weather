import requests
import aiohttp


def get_current_weather_sync(city, api_key):
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            return data['main']['temp'], data['weather'][0]['description']
        elif response.status_code == 401:
            return None, None
        else:
            return None, None
    except Exception:
        return None, None


async def get_current_weather_async(city, api_key):
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['main']['temp'], data['weather'][0]['description']
                elif response.status == 401:
                    return None, None
                else:
                    return None, None
    except Exception:
        return None, None