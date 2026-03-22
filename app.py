import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import time

from analys import analyze_city_sequential
from weatherappi import get_current_weather_sync
from data import seasonal_temperatures, month_to_season, generate_realistic_temperature_data

# --- Page Config ---
st.set_page_config(
    page_title="Weather Insights",
    page_icon="icon.png",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- Custom CSS ---
st.markdown("""
<style>
    /* Clean up top padding */
    .block-container { padding-top: 2rem; }

    /* Hero header */
    .hero-title {
        font-size: 2.4rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .hero-subtitle {
        font-size: 1.1rem;
        color: #888;
        margin-bottom: 1.5rem;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border: 1px solid #475569;
        border-radius: 12px;
        padding: 1rem 1.2rem;
    }
    [data-testid="stMetric"] label {
        color: #94a3b8 !important;
        font-size: 0.85rem !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.6rem !important;
        font-weight: 600 !important;
    }

    /* Section headers */
    .section-header {
        font-size: 1.3rem;
        font-weight: 600;
        margin-top: 2rem;
        margin-bottom: 0.5rem;
        padding-bottom: 0.4rem;
        border-bottom: 2px solid #3b82f6;
        display: inline-block;
    }

    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 0.5rem 1.5rem;
    }

    /* Hide hamburger menu and footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# --- Data Loading (cached) ---
@st.cache_data
def load_data():
    cities = list(seasonal_temperatures.keys())
    df = generate_realistic_temperature_data(cities, num_years=10)
    return df


@st.cache_data
def run_analysis(city_data_json):
    city_data = pd.read_json(city_data_json)
    city_data['timestamp'] = pd.to_datetime(city_data['timestamp'])
    return analyze_city_sequential(city_data)


# --- Header ---
st.markdown('<p class="hero-title">Weather Insights</p>', unsafe_allow_html=True)
st.markdown('<p class="hero-subtitle">Historical temperature analysis & live weather monitoring for 15 major cities</p>', unsafe_allow_html=True)

# --- Load data automatically ---
with st.spinner("Loading temperature data..."):
    df = load_data()
    df['timestamp'] = pd.to_datetime(df['timestamp'])

cities = sorted(df['city'].unique())

# --- City selector (prominent, top of page) ---
col_city, col_api = st.columns([2, 3])
with col_city:
    selected_city = st.selectbox(
        "Select a city",
        cities,
        index=cities.index("New York") if "New York" in cities else 0,
    )
with col_api:
    api_key = st.text_input(
        "OpenWeatherMap API key (optional, for live weather)",
        type="password",
        help="Get a free key at openweathermap.org",
    )

city_data = df[df['city'] == selected_city].copy().reset_index(drop=True)

# --- Key Metrics ---
st.markdown("")
avg_temp = city_data['temperature'].mean()
min_temp = city_data['temperature'].min()
max_temp = city_data['temperature'].max()
date_range = f"{city_data['timestamp'].min().strftime('%b %Y')} - {city_data['timestamp'].max().strftime('%b %Y')}"

m1, m2, m3, m4 = st.columns(4)
m1.metric("Average Temp", f"{avg_temp:.1f} C")
m2.metric("Record Low", f"{min_temp:.1f} C")
m3.metric("Record High", f"{max_temp:.1f} C")
m4.metric("Data Period", date_range)

# --- Run Analysis ---
results = run_analysis(city_data.to_json())

# --- Tabs for content ---
tab_trends, tab_seasons, tab_live = st.tabs(["Trends & Anomalies", "Seasonal Profile", "Live Weather"])

# ==================== TAB 1: Trends ====================
with tab_trends:
    st.markdown('<p class="section-header">Temperature Timeline</p>', unsafe_allow_html=True)

    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(
        x=city_data['timestamp'], y=city_data['temperature'],
        mode='lines', name='Daily Temp',
        line=dict(color='rgba(96, 165, 250, 0.4)', width=1),
        hovertemplate='%{x|%b %d, %Y}<br>%{y:.1f} C<extra></extra>',
    ))
    fig1.add_trace(go.Scatter(
        x=city_data['timestamp'], y=results['rolling_mean'],
        mode='lines', name='30-Day Average',
        line=dict(color='#3b82f6', width=2.5),
        hovertemplate='%{x|%b %d, %Y}<br>Avg: %{y:.1f} C<extra></extra>',
    ))

    anomalies_mask = results['is_anomaly'].values
    if isinstance(anomalies_mask, pd.Series):
        anomalies_mask = anomalies_mask.values
    anomalies = city_data[anomalies_mask]

    if len(anomalies) > 0:
        fig1.add_trace(go.Scatter(
            x=anomalies['timestamp'], y=anomalies['temperature'],
            mode='markers', name='Anomalies',
            marker=dict(color='#ef4444', size=5, symbol='circle', opacity=0.7),
            hovertemplate='%{x|%b %d, %Y}<br>Anomaly: %{y:.1f} C<extra></extra>',
        ))

    fig1.update_layout(
        xaxis_title="", yaxis_title="Temperature (C)",
        height=450,
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
    )
    st.plotly_chart(fig1, use_container_width=True)

    # Anomaly summary
    anomaly_count = results['is_anomaly'].sum() if hasattr(results['is_anomaly'], 'sum') else sum(results['is_anomaly'])
    anomaly_percent = (anomaly_count / len(city_data)) * 100
    st.caption(f"Detected **{anomaly_count}** anomalies ({anomaly_percent:.1f}% of all readings) using 2-sigma threshold on 30-day rolling window.")

    # Long-term trend
    st.markdown('<p class="section-header">Long-Term Trend</p>', unsafe_allow_html=True)

    yearly_data = results['long_term_trend']
    from scipy import stats as sp_stats
    slope, intercept, r_value, p_value, std_err = sp_stats.linregress(yearly_data['year'], yearly_data['avg_temperature'])

    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=yearly_data['year'], y=yearly_data['avg_temperature'],
        mode='markers+lines', name='Yearly Average',
        marker=dict(color='#3b82f6', size=9),
        line=dict(color='rgba(96, 165, 250, 0.3)', width=1),
        hovertemplate='%{x}<br>%{y:.2f} C<extra></extra>',
    ))
    trend_y = slope * yearly_data['year'] + intercept
    fig3.add_trace(go.Scatter(
        x=yearly_data['year'], y=trend_y,
        mode='lines', name=f'Trend ({slope:+.3f} C/year)',
        line=dict(color='#f59e0b', width=2, dash='dash'),
    ))
    fig3.update_layout(
        xaxis_title="Year", yaxis_title="Avg Temperature (C)",
        height=350,
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)", dtick=1),
        yaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
    )
    st.plotly_chart(fig3, use_container_width=True)

    if slope > 0:
        st.success(f"Warming trend detected: **+{slope:.3f} C/year**")
    elif slope < 0:
        st.warning(f"Cooling trend detected: **{slope:.3f} C/year**")
    else:
        st.info("No significant trend detected.")

# ==================== TAB 2: Seasonal ====================
with tab_seasons:
    st.markdown('<p class="section-header">Seasonal Temperature Profile</p>', unsafe_allow_html=True)

    seasonal_stats = results['seasonal_stats']
    season_labels = {'winter': 'Winter', 'spring': 'Spring', 'summer': 'Summer', 'autumn': 'Autumn'}
    season_colors = ['#60a5fa', '#34d399', '#f87171', '#fbbf24']
    season_icons = ['Winter', 'Spring', 'Summer', 'Autumn']

    # Season metric cards
    s1, s2, s3, s4 = st.columns(4)
    for col, (_, row) in zip([s1, s2, s3, s4], seasonal_stats.iterrows()):
        label = season_labels.get(row['season'], row['season'])
        col.metric(label, f"{row['mean']:.1f} C", f"+/- {row['std']:.1f}")

    st.markdown("")

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=[season_labels.get(s, s) for s in seasonal_stats['season']],
        y=seasonal_stats['mean'],
        error_y=dict(type='data', array=seasonal_stats['std'], color='rgba(255,255,255,0.3)'),
        marker_color=season_colors,
        marker_line=dict(width=0),
        hovertemplate='%{x}<br>Mean: %{y:.1f} C<extra></extra>',
    ))
    fig2.update_layout(
        xaxis_title="", yaxis_title="Temperature (C)",
        height=380,
        margin=dict(l=0, r=0, t=20, b=0),
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
        showlegend=False,
    )
    st.plotly_chart(fig2, use_container_width=True)

    # Descriptive stats in expander
    with st.expander("Detailed Statistics"):
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Overall Statistics**")
            desc = city_data['temperature'].describe().round(1)
            desc.index = ['Count', 'Mean', 'Std Dev', 'Min', '25%', 'Median', '75%', 'Max']
            st.dataframe(desc, use_container_width=True)
        with col_b:
            st.markdown("**By Season**")
            display = seasonal_stats.copy()
            display.columns = ['Season', 'Mean (C)', 'Std Dev (C)']
            display['Mean (C)'] = display['Mean (C)'].round(1)
            display['Std Dev (C)'] = display['Std Dev (C)'].round(1)
            display['Season'] = display['Season'].map(season_labels)
            st.dataframe(display, use_container_width=True, hide_index=True)

# ==================== TAB 3: Live Weather ====================
with tab_live:
    st.markdown('<p class="section-header">Current Weather</p>', unsafe_allow_html=True)

    if not api_key:
        st.info("Enter your OpenWeatherMap API key above to see live weather data and compare it against historical norms.")
    else:
        if st.button("Fetch Current Weather", type="primary", use_container_width=False):
            with st.spinner("Fetching weather data..."):
                current_temp, weather_desc = get_current_weather_sync(selected_city, api_key)

            if current_temp is not None:
                def get_current_season():
                    m = datetime.now().month
                    if m in [12, 1, 2]: return "winter"
                    elif m in [3, 4, 5]: return "spring"
                    elif m in [6, 7, 8]: return "summer"
                    else: return "autumn"

                current_season = get_current_season()
                season_data = seasonal_stats[seasonal_stats['season'] == current_season]

                lw1, lw2 = st.columns([1, 2])
                with lw1:
                    st.metric("Temperature Now", f"{current_temp:.1f} C")
                    st.markdown(f"**Conditions:** {weather_desc.title()}")
                    st.markdown(f"**Season:** {season_labels.get(current_season, current_season)}")

                with lw2:
                    if not season_data.empty:
                        season_mean = season_data['mean'].values[0]
                        season_std = season_data['std'].values[0]
                        lower = season_mean - 2 * season_std
                        upper = season_mean + 2 * season_std

                        # Gauge-like visualization
                        fig_gauge = go.Figure()
                        fig_gauge.add_trace(go.Indicator(
                            mode="gauge+number+delta",
                            value=current_temp,
                            delta={'reference': season_mean, 'suffix': ' C vs avg'},
                            gauge={
                                'axis': {'range': [lower - 5, upper + 5], 'ticksuffix': ' C'},
                                'bar': {'color': '#3b82f6'},
                                'bgcolor': 'rgba(0,0,0,0)',
                                'steps': [
                                    {'range': [lower - 5, lower], 'color': 'rgba(239,68,68,0.2)'},
                                    {'range': [lower, upper], 'color': 'rgba(52,211,153,0.2)'},
                                    {'range': [upper, upper + 5], 'color': 'rgba(239,68,68,0.2)'},
                                ],
                                'threshold': {
                                    'line': {'color': '#f59e0b', 'width': 3},
                                    'thickness': 0.8,
                                    'value': season_mean,
                                },
                            },
                            number={'suffix': ' C'},
                            title={'text': f"vs {season_labels.get(current_season, '')} Normal"},
                        ))
                        fig_gauge.update_layout(
                            height=250,
                            margin=dict(l=20, r=20, t=40, b=0),
                        )
                        st.plotly_chart(fig_gauge, use_container_width=True)

                        if current_temp < lower or current_temp > upper:
                            st.error(f"Current temperature is **anomalous** for {season_labels.get(current_season, current_season).lower()}! Normal range: {lower:.1f} to {upper:.1f} C")
                        else:
                            st.success(f"Temperature is within the normal range for {season_labels.get(current_season, current_season).lower()} ({lower:.1f} to {upper:.1f} C)")
            else:
                st.error("Could not fetch weather data. Check your API key and try again.")
