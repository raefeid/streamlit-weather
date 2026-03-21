import pandas as pd
import numpy as np
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp


def calculate_rolling_stats(data, window=30):
    rolling_mean = data['temperature'].rolling(window=window, center=True).mean()
    rolling_std = data['temperature'].rolling(window=window, center=True).std()
    return rolling_mean, rolling_std


def detect_anomalies(data, rolling_mean, rolling_std):
    lower_bound = rolling_mean - 2 * rolling_std
    upper_bound = rolling_mean + 2 * rolling_std
    is_anomaly = (data['temperature'] < lower_bound) | (data['temperature'] > upper_bound)
    return is_anomaly


def calculate_seasonal_stats(city_data):
    seasonal_stats = city_data.groupby('season')['temperature'].agg(['mean', 'std']).reset_index()
    season_order = ['winter', 'spring', 'summer', 'autumn']
    seasonal_stats['season'] = pd.Categorical(seasonal_stats['season'], categories=season_order, ordered=True)
    seasonal_stats = seasonal_stats.sort_values('season').reset_index(drop=True)
    return seasonal_stats


def calculate_long_term_trend(city_data):
    yearly_avg = city_data.groupby(city_data['timestamp'].dt.year)['temperature'].mean().reset_index()
    yearly_avg.columns = ['year', 'avg_temperature']
    return yearly_avg


def analyze_city_sequential(city_data):
    rolling_mean, rolling_std = calculate_rolling_stats(city_data)
    is_anomaly = detect_anomalies(city_data, rolling_mean, rolling_std)
    seasonal_stats = calculate_seasonal_stats(city_data)
    long_term_trend = calculate_long_term_trend(city_data)

    return {
        'rolling_mean': rolling_mean,
        'rolling_std': rolling_std,
        'is_anomaly': is_anomaly,
        'seasonal_stats': seasonal_stats,
        'long_term_trend': long_term_trend
    }


def analyze_city_chunk(chunk_data):
    rolling_mean, rolling_std = calculate_rolling_stats(chunk_data)
    is_anomaly = detect_anomalies(chunk_data, rolling_mean, rolling_std)
    return rolling_mean, rolling_std, is_anomaly


def analyze_city_parallel(city_data):
    city_data_copy = city_data.copy()
    city_data_copy['year'] = city_data_copy['timestamp'].dt.year

    chunks = []
    for year, group in city_data_copy.groupby('year'):
        chunks.append(group.reset_index(drop=True))

    with ProcessPoolExecutor(max_workers=mp.cpu_count()) as executor:
        results = list(executor.map(analyze_city_chunk, chunks))

    rolling_means = []
    rolling_stds = []
    anomalies = []

    for rm, rs, anom in results:
        rolling_means.extend(rm)
        rolling_stds.extend(rs)
        anomalies.extend(anom)

    seasonal_stats = calculate_seasonal_stats(city_data)
    long_term_trend = calculate_long_term_trend(city_data)

    return {
        'rolling_mean': pd.Series(rolling_means),
        'rolling_std': pd.Series(rolling_stds),
        'is_anomaly': pd.Series(anomalies),
        'seasonal_stats': seasonal_stats,
        'long_term_trend': long_term_trend
    }