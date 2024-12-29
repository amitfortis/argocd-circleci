from flask import abort
from geopy.geocoders import Nominatim
import openmeteo_requests
import requests_cache
import pandas as pd
from retry_requests import retry


def get_location(user_location):
    geolocator = Nominatim(user_agent="locator")
    request_location = geolocator.geocode(user_location, language="en")
    if request_location is None:
        abort(400)
    return request_location


class WeatherData:
    def __init__(self, user_location):
        self.location = get_location(user_location)
        self.dataframe = api_request(self.location)
        if self.dataframe is None:
            abort(500)
        self.days = self.create_days()

    def create_days(self):
        days = []
        if "Nighttime Temperature" not in self.dataframe.columns:
            for _, row in self.dataframe.iterrows():
                day = Day(
                    date=row["date"],
                    day_temp=row["Daytime Temperature"],
                    day_humidity=row["Daytime Humidity"],
                    location=self.location,
                )
                days.append(day)
        else:
            for _, row in self.dataframe.iterrows():
                day = Day(
                    date=row["date"],
                    day_temp=row["Daytime Temperature"],
                    night_temp=row["Nighttime Temperature"],
                    day_humidity=row["Daytime Humidity"],
                    night_humidity=row["Nighttime Humidity"],
                    location=self.location,
                )
                days.append(day)
        return days


class Day:
    def __init__(
        self,
        date,
        location,
        day_temp="N/A",
        night_temp="N/A",
        day_humidity="N/A",
        night_humidity="N/A",
    ):
        self.date = date
        self.day_temperature = day_temp
        self.night_temperature = night_temp
        self.day_humidity = day_humidity
        self.night_humidity = night_humidity
        self.location = location


def api_request(request_location):
    cache_session = requests_cache.CachedSession(".cache", expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": request_location.latitude,
        "longitude": request_location.longitude,
        "hourly": ["temperature_2m", "relative_humidity_2m", "is_day"],
        "timezone": "auto",
    }

    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]
    hourly = response.Hourly()
    hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
    hourly_relative_humidity_2m = hourly.Variables(1).ValuesAsNumpy()
    hourly_is_day = hourly.Variables(2).ValuesAsNumpy()
    offset = response.UtcOffsetSeconds()

    hourly_data = dict(
        date=pd.date_range(
            start=pd.to_datetime(hourly.Time() + offset, unit="s", utc=False),
            end=pd.to_datetime(hourly.TimeEnd() + offset, unit="s", utc=False),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left",
        )
    )
    hourly_data["temperature_2m"] = hourly_temperature_2m
    hourly_data["relative_humidity_2m"] = hourly_relative_humidity_2m
    hourly_data["is_day"] = hourly_is_day.astype(str)
    hourly_dataframe = pd.DataFrame(data=hourly_data)
    hourly_dataframe["time"] = pd.to_datetime(hourly_dataframe["date"]).dt.time
    hourly_dataframe["date"] = pd.to_datetime(hourly_dataframe["date"]).dt.date
    result_df = aggregate_daytime_nighttime(hourly_dataframe)
    return result_df


def aggregate_daytime_nighttime(hdf):
    if ((hdf["is_day"].to_numpy())[0] == (hdf["is_day"].to_numpy())).all():
        avg_values_per_date = (
            hdf.groupby(["date"])
            .agg(
                avg_temperature_2m=("temperature_2m", "mean"),
                avg_relative_humidity_2m=("relative_humidity_2m", "mean"),
            )
            .reset_index()
        )
        avg_values = avg_values_per_date.rename(
            columns={
                "avg_temperature_2m": "Daytime Temperature",
                "avg_relative_humidity_2m": "Daytime Humidity",
            }
        )

    else:
        avg_values_per_date = (
            hdf.groupby(["date", "is_day"])
            .agg(
                avg_temperature_2m=("temperature_2m", "mean"),
                avg_relative_humidity_2m=("relative_humidity_2m", "mean"),
            )
            .reset_index()
        )
        avg_values = avg_values_per_date.pivot(
            index="date", columns="is_day"
        ).reset_index()
        avg_values.columns = [
            "_".join(col).strip() if col[1] else col[0]
            for col in avg_values.columns.values
        ]
        avg_values.rename(
            columns={
                "date_": "date",
                "avg_temperature_2m_1.0": "Daytime Temperature",
                "avg_temperature_2m_0.0": "Nighttime Temperature",
                "avg_relative_humidity_2m_1.0": "Daytime Humidity",
                "avg_relative_humidity_2m_0.0": "Nighttime Humidity",
            },
            inplace=True,
        )
    return avg_values
