import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time
import asyncio

from analys import analyze_city_sequential, analyze_city_parallel
from weatherappi import get_current_weather_sync, get_current_weather_async

st.set_page_config(page_title="Анализ температурных данных", page_icon="/icon.png", layout="wide")

st.title("Анализ температурных данных и мониторинг текущей температуры")
st.markdown("---")

with st.sidebar:
    st.header("Загрузка данных")
    uploaded_file = st.file_uploader("Загрузите файл temperature_data.csv", type="csv")

    st.header("Настройка API")
    api_key = st.text_input("API ключ OpenWeatherMap", type="password")

    if uploaded_file is not None:
        st.success("Данные успешно загружены")

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    cities = sorted(df['city'].unique())
    selected_city = st.selectbox("Выберите город", cities)

    city_data = df[df['city'] == selected_city].copy()

    city_data = city_data.reset_index(drop=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Период данных", f"{city_data['timestamp'].min().date()} - {city_data['timestamp'].max().date()}")
    with col2:
        st.metric("Количество записей", len(city_data))
    with col3:
        st.metric("Средняя температура", f"{city_data['temperature'].mean():.1f}°C")

    st.markdown("---")

    st.header("Анализ исторических данных")

    analysis_method = st.radio("Выберите метод анализа:", ["Последовательный", "Параллельный"], horizontal=True)

    with st.spinner(f"Выполняется {analysis_method.lower()} анализ..."):
        start_time = time.time()

        if analysis_method == "Последовательный":
            results = analyze_city_sequential(city_data)
        else:
            results = analyze_city_parallel(city_data)

        analysis_time = time.time() - start_time
        st.info(f"Время выполнения анализа: {analysis_time:.2f} секунд")

    st.subheader("Временной ряд температур с выделением аномалий")

    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(
        x=city_data['timestamp'], y=city_data['temperature'],
        mode='lines', name='Температура',
        line=dict(color='lightblue', width=1)
    ))
    fig1.add_trace(go.Scatter(
        x=city_data['timestamp'], y=results['rolling_mean'],
        mode='lines', name='Скользящее среднее (30 дней)',
        line=dict(color='red', width=2)
    ))

    anomalies_mask = results['is_anomaly'].values
    if isinstance(anomalies_mask, pd.Series):
        anomalies_mask = anomalies_mask.values

    anomalies = city_data[anomalies_mask]

    if len(anomalies) > 0:
        fig1.add_trace(go.Scatter(
            x=anomalies['timestamp'], y=anomalies['temperature'],
            mode='markers', name='Аномалии',
            marker=dict(color='red', size=6, symbol='x')
        ))

    fig1.update_layout(
        title=f"Температурный тренд в городе {selected_city}",
        xaxis_title="Дата", yaxis_title="Температура (°C)",
        height=500
    )
    st.plotly_chart(fig1, use_container_width=True)

    anomaly_count = results['is_anomaly'].sum() if hasattr(results['is_anomaly'], 'sum') else sum(results['is_anomaly'])
    anomaly_percent = (anomaly_count / len(city_data)) * 100
    st.info(f"Обнаружено аномалий: {anomaly_count} ({anomaly_percent:.1f}% от всех данных)")

    st.subheader("Сезонные профили температур")

    seasonal_stats = results['seasonal_stats']
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=seasonal_stats['season'], y=seasonal_stats['mean'],
        error_y=dict(type='data', array=seasonal_stats['std']),
        name='Средняя температура',
        marker_color=['#3498db', '#2ecc71', '#e74c3c', '#f39c12']
    ))
    fig2.update_layout(
        title=f"Сезонный профиль температуры для города {selected_city}",
        xaxis_title="Сезон", yaxis_title="Температура (°C)",
        height=400
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Долгосрочный тренд изменения температуры")

    yearly_data = results['long_term_trend']

    from scipy import stats

    slope, intercept, r_value, p_value, std_err = stats.linregress(yearly_data['year'], yearly_data['avg_temperature'])

    fig3 = go.Figure()

    fig3.add_trace(go.Scatter(
        x=yearly_data['year'],
        y=yearly_data['avg_temperature'],
        mode='markers',
        name='Среднегодовая температура',
        marker=dict(color='blue', size=8)
    ))

    trend_y = slope * yearly_data['year'] + intercept
    fig3.add_trace(go.Scatter(
        x=yearly_data['year'],
        y=trend_y,
        mode='lines',
        name=f'Линия тренда (изменение: {slope:.2f}°C/год)',
        line=dict(color='red', width=2, dash='dash')
    ))

    fig3.update_layout(
        title=f"Тренд среднегодовой температуры в городе {selected_city}",
        xaxis_title="Год",
        yaxis_title="Средняя температура (°C)",
        height=400
    )

    st.plotly_chart(fig3, use_container_width=True)

    if slope > 0:
        st.success(f"Обнаружен тренд на потепление: +{slope:.2f}°C в год")
    elif slope < 0:
        st.warning(f"Обнаружен тренд на похолодание: {slope:.2f}°C в год")
    else:
        st.info("Значимый тренд не обнаружен")

    st.header("Мониторинг текущей температуры")


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


    def get_season_name(season):
        season_names = {
            "winter": "зима",
            "spring": "весна",
            "summer": "лето",
            "autumn": "осень"
        }
        return season_names.get(season, season)


    if api_key:
        col1, col2 = st.columns(2)

        with col1:
            if st.button("Получить погоду (синхронно)", use_container_width=True):
                with st.spinner("Выполняется синхронный запрос..."):
                    start_sync = time.time()
                    current_temp, weather_desc = get_current_weather_sync(selected_city, api_key)
                    sync_time = time.time() - start_sync

                    if current_temp is not None:
                        st.metric("Текущая температура", f"{current_temp:.1f}°C")
                        st.write(f"**Погодные условия:** {weather_desc}")
                        st.write(f"**Время ответа:** {sync_time:.2f} секунд")

                        current_season = get_current_season()
                        season_data = seasonal_stats[seasonal_stats['season'] == current_season]

                        if not season_data.empty:
                            season_mean = season_data['mean'].values[0]
                            season_std = season_data['std'].values[0]
                            lower_bound = season_mean - 2 * season_std
                            upper_bound = season_mean + 2 * season_std

                            st.write(f"**Текущий сезон:** {get_season_name(current_season)}")
                            st.write(f"**Историческая норма для сезона:** {lower_bound:.1f}°C до {upper_bound:.1f}°C")

                            if current_temp < lower_bound or current_temp > upper_bound:
                                st.error("Текущая температура является АНОМАЛЬНОЙ для данного сезона!")
                            else:
                                st.success("Текущая температура находится в пределах нормы")
                    else:
                        st.error("Ошибка: Неверный API ключ или проблема с сетью")

        with col2:
            if st.button("Получить погоду (асинхронно)", use_container_width=True):
                with st.spinner("Выполняется асинхронный запрос..."):
                    start_async = time.time()
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    current_temp, weather_desc = loop.run_until_complete(
                        get_current_weather_async(selected_city, api_key)
                    )
                    async_time = time.time() - start_async

                    if current_temp is not None:
                        st.metric("Текущая температура", f"{current_temp:.1f}°C")
                        st.write(f"**Погодные условия:** {weather_desc}")
                        st.write(f"**Время ответа:** {async_time:.2f} секунд")

                        current_season = get_current_season()
                        season_data = seasonal_stats[seasonal_stats['season'] == current_season]

                        if not season_data.empty:
                            season_mean = season_data['mean'].values[0]
                            season_std = season_data['std'].values[0]
                            lower_bound = season_mean - 2 * season_std
                            upper_bound = season_mean + 2 * season_std

                            st.write(f"**Текущий сезон:** {get_season_name(current_season)}")
                            st.write(f"**Историческая норма для сезона:** {lower_bound:.1f}°C до {upper_bound:.1f}°C")

                            if current_temp < lower_bound or current_temp > upper_bound:
                                st.error("Текущая температура является АНОМАЛЬНОЙ для данного сезона!")
                            else:
                                st.success("Текущая температура находится в пределах нормы")
                    else:
                        st.error("Ошибка: Неверный API ключ или проблема с сетью")
    else:
        st.warning("Введите API ключ OpenWeatherMap в боковой панели")

    with st.expander("Описательная статистика"):
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Общая статистика")
            st.write(city_data['temperature'].describe())
        with col2:
            st.subheader("Сезонная статистика")
            seasonal_display = seasonal_stats.copy()
            seasonal_display.columns = ['Сезон', 'Средняя температура', 'Стандартное отклонение']
            seasonal_display['Средняя температура'] = seasonal_display['Средняя температура'].round(1)
            seasonal_display['Стандартное отклонение'] = seasonal_display['Стандартное отклонение'].round(1)

            season_translation = {
                'winter': 'Зима',
                'spring': 'Весна',
                'summer': 'Лето',
                'autumn': 'Осень'
            }
            seasonal_display['Сезон'] = seasonal_display['Сезон'].map(season_translation)

            st.dataframe(seasonal_display, use_container_width=True)
else:
    st.info("Начало работы\n\n"
            "1. Сгенерируйте файл данных с помощью команды:\n"
            "   python generate_data.py\n\n"
            "2. Загрузите файл temperature_data.csv через боковую панель\n\n"
            "3. Введите API ключ OpenWeatherMap\n\n"
            "4. Выберите город для анализа\n\n"
            "Города для тестирования:\n"
            "- Норма: Берлин, Каир, Дубай\n"
            "- Аномалия: Пекин, Москва")