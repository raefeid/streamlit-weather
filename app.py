import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import time
import asyncio

from analys import analyze_city_sequential, analyze_city_parallel
from weatherappi import get_current_weather_sync, get_current_weather_async

st.set_page_config(page_title="Temperature Analysis", page_icon="🌡️", layout="wide")

st.title("🌡️ Temperature Analysis and Monitoring")
st.markdown("---")

with st.sidebar:
    st.header("📁 Data Upload")
    uploaded_file = st.file_uploader("Upload temperature_data.csv", type="csv")

    st.header("🔑 API Configuration")
    api_key = st.text_input("OpenWeatherMap API Key", type="password")

    if uploaded_file is not None:
        st.success("✅ Data loaded successfully!")

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    cities = sorted(df['city'].unique())
    selected_city = st.selectbox("🌍 Select City", cities)

    city_data = df[df['city'] == selected_city].copy()

    city_data = city_data.reset_index(drop=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Data Range", f"{city_data['timestamp'].min().date()} to {city_data['timestamp'].max().date()}")
    with col2:
        st.metric("Number of Records", len(city_data))
    with col3:
        st.metric("Average Temperature", f"{city_data['temperature'].mean():.1f}°C")

    st.markdown("---")

    st.header("📊 Data Analysis")

    analysis_method = st.radio("Select analysis method:", ["Sequential", "Parallel"], horizontal=True)

    with st.spinner(f"Running {analysis_method.lower()} analysis..."):
        start_time = time.time()

        if analysis_method == "Sequential":
            results = analyze_city_sequential(city_data)
        else:
            results = analyze_city_parallel(city_data)

        analysis_time = time.time() - start_time
        st.info(f"⏱️ {analysis_method} analysis completed in {analysis_time:.2f} seconds")

    st.subheader("📈 Temperature Time Series with Anomalies")

    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(
        x=city_data['timestamp'], y=city_data['temperature'],
        mode='lines', name='Daily Temperature',
        line=dict(color='lightblue', width=1)
    ))
    fig1.add_trace(go.Scatter(
        x=city_data['timestamp'], y=results['rolling_mean'],
        mode='lines', name='30-day Moving Average',
        line=dict(color='red', width=2)
    ))

    anomalies_mask = results['is_anomaly'].values
    if isinstance(anomalies_mask, pd.Series):
        anomalies_mask = anomalies_mask.values

    anomalies = city_data[anomalies_mask]

    if len(anomalies) > 0:
        fig1.add_trace(go.Scatter(
            x=anomalies['timestamp'], y=anomalies['temperature'],
            mode='markers', name='Anomalies',
            marker=dict(color='red', size=6, symbol='x')
        ))

    fig1.update_layout(
        title=f"Temperature Trends in {selected_city}",
        xaxis_title="Date", yaxis_title="Temperature (°C)",
        height=500
    )
    st.plotly_chart(fig1, use_container_width=True)

    anomaly_count = results['is_anomaly'].sum() if hasattr(results['is_anomaly'], 'sum') else sum(results['is_anomaly'])
    anomaly_percent = (anomaly_count / len(city_data)) * 100
    st.info(f"📊 Found {anomaly_count} anomalies ({anomaly_percent:.1f}% of all data)")

    st.subheader("🌱 Seasonal Temperature Profiles")

    seasonal_stats = results['seasonal_stats']
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=seasonal_stats['season'], y=seasonal_stats['mean'],
        error_y=dict(type='data', array=seasonal_stats['std']),
        name='Mean Temperature',
        marker_color=['#3498db', '#2ecc71', '#e74c3c', '#f39c12']
    ))
    fig2.update_layout(
        title=f"Seasonal Temperature Profile for {selected_city}",
        xaxis_title="Season", yaxis_title="Temperature (°C)",
        height=400
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("📉 Long-term Temperature Trend")

    yearly_data = results['long_term_trend']

    from scipy import stats

    slope, intercept, r_value, p_value, std_err = stats.linregress(yearly_data['year'], yearly_data['avg_temperature'])

    fig3 = go.Figure()

    fig3.add_trace(go.Scatter(
        x=yearly_data['year'],
        y=yearly_data['avg_temperature'],
        mode='markers',
        name='Annual Average',
        marker=dict(color='blue', size=8)
    ))

    trend_y = slope * yearly_data['year'] + intercept
    fig3.add_trace(go.Scatter(
        x=yearly_data['year'],
        y=trend_y,
        mode='lines',
        name=f'Trend (slope: {slope:.2f}°C/year)',
        line=dict(color='red', width=2, dash='dash')
    ))

    fig3.update_layout(
        title=f"Annual Average Temperature Trend in {selected_city}",
        xaxis_title="Year",
        yaxis_title="Average Temperature (°C)",
        height=400
    )

    st.plotly_chart(fig3, use_container_width=True)

    if slope > 0:
        st.success(f"📈 Warming trend detected: +{slope:.2f}°C per year")
    elif slope < 0:
        st.warning(f"📉 Cooling trend detected: {slope:.2f}°C per year")
    else:
        st.info("📊 No significant trend detected")

    st.header("🌤️ Current Temperature Monitoring")


    def get_current_season():
        month = datetime.now().month
        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        else:
            return "autumn"


    if api_key:
        col1, col2 = st.columns(2)

        with col1:
            if st.button("🚀 Get Weather (Sync)", use_container_width=True):
                with st.spinner("Fetching synchronously..."):
                    start_sync = time.time()
                    current_temp, weather_desc = get_current_weather_sync(selected_city, api_key)
                    sync_time = time.time() - start_sync

                    if current_temp is not None:
                        st.metric("Current Temperature", f"{current_temp:.1f}°C")
                        st.write(f"**Condition:** {weather_desc}")
                        st.write(f"**Response time:** {sync_time:.2f} seconds")

                        current_season = get_current_season()
                        season_data = seasonal_stats[seasonal_stats['season'] == current_season]

                        if not season_data.empty:
                            season_mean = season_data['mean'].values[0]
                            season_std = season_data['std'].values[0]
                            lower_bound = season_mean - 2 * season_std
                            upper_bound = season_mean + 2 * season_std

                            st.write(f"**Current season:** {current_season.capitalize()}")
                            st.write(f"**Historical normal range:** {lower_bound:.1f}°C to {upper_bound:.1f}°C")

                            if current_temp < lower_bound or current_temp > upper_bound:
                                st.error("⚠️ Current temperature is ANOMALOUS for this season!")
                            else:
                                st.success("✅ Current temperature is within normal range")
                    else:
                        st.error("Invalid API key or network error")

        with col2:
            if st.button("🚀 Get Weather (Async)", use_container_width=True):
                with st.spinner("Fetching asynchronously..."):
                    start_async = time.time()
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    current_temp, weather_desc = loop.run_until_complete(
                        get_current_weather_async(selected_city, api_key)
                    )
                    async_time = time.time() - start_async

                    if current_temp is not None:
                        st.metric("Current Temperature", f"{current_temp:.1f}°C")
                        st.write(f"**Condition:** {weather_desc}")
                        st.write(f"Response time: {async_time:.2f} seconds")

                        current_season = get_current_season()
                        season_data = seasonal_stats[seasonal_stats['season'] == current_season]

                        if not season_data.empty:
                            season_mean = season_data['mean'].values[0]
                            season_std = season_data['std'].values[0]
                            lower_bound = season_mean - 2 * season_std
                            upper_bound = season_mean + 2 * season_std

                            st.write(f"**Current season:** {current_season.capitalize()}")
                            st.write(f"**Historical normal range:** {lower_bound:.1f}°C to {upper_bound:.1f}°C")

                            if current_temp < lower_bound or current_temp > upper_bound:
                                st.error("⚠️ Current temperature is ANOMALOUS for this season!")
                            else:
                                st.success("✅ Current temperature is within normal range")
                    else:
                        st.error("Invalid API key or network error")
    else:
        st.warning("⚠️ Please enter your OpenWeatherMap API key in the sidebar")

    with st.expander("📊 Descriptive Statistics"):
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Overall Statistics")
            st.write(city_data['temperature'].describe())
        with col2:
            st.subheader("Seasonal Statistics")
            st.dataframe(seasonal_stats.style.format({'mean': '{:.1f}', 'std': '{:.1f}'}))
else:
    st.info("👈 **Getting Started**\n\n"
            "1. First, you need to generate the data file locally:\n"
            "   - Run `python generate_data.py` on your computer\n"
            "   - This creates `temperature_data.csv`\n"
            "2. Upload that file using the sidebar\n"
            "3. Enter your OpenWeatherMap API key\n"
            "4. Select a city and start analyzing!")