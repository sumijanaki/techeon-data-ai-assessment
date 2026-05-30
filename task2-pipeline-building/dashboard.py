import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from google.cloud import bigquery
from dotenv import load_dotenv
from datetime import datetime, timedelta

# =========================================================================
# 🎨 STREAMLIT PAGE CONFIGURATION & THEMING
# =========================================================================
st.set_page_config(
    page_title="Weather-Triggered Marketing Dashboard",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Premium Glassmorphism and Styling
st.markdown("""
<style>
    /* Dark Theme Styles */
    .reportview-container {
        background: #0e1117;
    }
    
    /* Premium KPI Card Styling */
    .kpi-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    .kpi-title {
        font-size: 14px;
        color: #8892b0;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 10px;
    }
    .kpi-value {
        font-size: 28px;
        font-weight: bold;
        color: #64ffda;
    }
    
    /* Footer Styling */
    .footer {
        text-align: center;
        color: #8892b0;
        padding: 20px;
        font-size: 12px;
        margin-top: 50px;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
    }
</style>
""", unsafe_allowed_html=True)

# Load environment variables
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))

# =========================================================================
# 🔑 BIGQUERY CONNECTION
# =========================================================================
@st.cache_resource
def get_bq_client():
    """Initializes and caches the Google BigQuery Client."""
    # Ensure credential environment variable is loaded
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_path:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path
    
    project_id = os.getenv("GCP_PROJECT_ID", "corded-sunbeam-411604")
    try:
        return bigquery.Client(project=project_id)
    except Exception as e:
        st.error(f"Failed to initialize BigQuery Client: {str(e)}")
        return None

bq_client = get_bq_client()

# =========================================================================
# 📥 DATA LOAD AND QUERYING
# =========================================================================
@st.cache_data(ttl=600)  # Cache data for 10 minutes
def fetch_dashboard_data():
    """Executes the weather analytics and trigger logic SQL on BigQuery."""
    if not bq_client:
        return pd.DataFrame()
        
    query_file = os.path.join(BASE_DIR, "queries", "summary.sql")
    if not os.path.exists(query_file):
        st.error(f"SQL file not found at {query_file}")
        return pd.DataFrame()
        
    with open(query_file, "r", encoding="utf-8") as f:
        sql = f.read()
        
    try:
        query_job = bq_client.query(sql)
        results = query_job.to_dataframe()
        # Parse weather_date to pandas datetime
        results['weather_date'] = pd.to_datetime(results['weather_date'])
        return results
    except Exception as e:
        st.error(f"Error querying BigQuery: {str(e)}")
        return pd.DataFrame()

df_raw = fetch_dashboard_data()

# =========================================================================
# 🎛️ SIDEBAR CONTROLS
# =========================================================================
st.sidebar.image("https://img.icons8.com/clouds/200/sun.png", width=100)
st.sidebar.title("Dashboard Controls")
st.sidebar.write("Configure your targets and views.")

if not df_raw.empty:
    # 1. Location Mapping
    unique_lats = df_raw["latitude"].unique()
    # Provide simple text labels for locations based on config
    locations_map = {
        "New York": 40.7128,
        "London": 51.5074,
        "Tokyo": 35.6762,
        "Sydney": -33.8688
    }
    # Inverse map to label latitude coordinates
    inv_map = {v: k for k, v in locations_map.items()}
    df_raw["location_name"] = df_raw["latitude"].map(lambda x: inv_map.get(round(x, 4), f"Lat: {x}"))
    
    # Selection Filter
    selected_locations = st.sidebar.multiselect(
        "Select Locations",
        options=df_raw["location_name"].unique(),
        default=df_raw["location_name"].unique()
    )
    
    # 2. Date Range Filter
    min_date = df_raw["weather_date"].min().date()
    max_date = df_raw["weather_date"].max().date()
    
    date_range = st.sidebar.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    # Apply filters
    df_filtered = df_raw[df_raw["location_name"].isin(selected_locations)]
    if len(date_range) == 2:
        start_dt, end_dt = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        df_filtered = df_filtered[(df_filtered["weather_date"] >= start_dt) & (df_filtered["weather_date"] <= end_dt)]
else:
    st.sidebar.warning("No data retrieved from BigQuery.")
    df_filtered = pd.DataFrame()

# =========================================================================
# 📊 MAIN PANEL - HEADER
# =========================================================================
st.title("🌤️ Weather-Triggered Marketing Analytics")
st.write("Real-time telemetry and target campaign triggers loaded directly from BigQuery.")

if not df_filtered.empty:
    # =========================================================================
    # 📈 ROW 1: KPI SCORECARDS
    # =========================================================================
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avg_temp = df_filtered["avg_temperature"].mean()
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Average Temp</div>
            <div class="kpi-value">{avg_temp:.1f}°C</div>
        </div>
        """, unsafe_allowed_html=True)
        
    with col2:
        max_apparent = df_filtered["max_apparent_temperature"].max()
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Max Apparent Temp</div>
            <div class="kpi-value">{max_apparent:.1f}°C</div>
        </div>
        """, unsafe_allowed_html=True)
        
    with col3:
        total_precip = df_filtered["total_precipitation"].sum()
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Total Precipitation</div>
            <div class="kpi-value">{total_precip:.1f} mm</div>
        </div>
        """, unsafe_allowed_html=True)
        
    with col4:
        avg_humidity = df_filtered["avg_relative_humidity"].mean()
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Average Humidity</div>
            <div class="kpi-value">{avg_humidity:.1f}%</div>
        </div>
        """, unsafe_allowed_html=True)

    st.write("") # Spacer

    # =========================================================================
    # 🗺️ ROW 2: MAP & TRENDS
    # =========================================================================
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        st.subheader("📍 Target Marketing Hub Locations")
        # Aggregated locations for the map view
        map_df = df_filtered.groupby(["location_name", "latitude", "longitude"]).agg({
            "avg_temperature": "mean",
            "max_apparent_temperature": "max",
            "total_precipitation": "sum"
        }).reset_index()
        
        fig_map = px.scatter_mapbox(
            map_df,
            lat="latitude",
            lon="longitude",
            color="avg_temperature",
            size="max_apparent_temperature",
            color_continuous_scale=px.colors.sequential.Thermal,
            hover_name="location_name",
            hover_data={"total_precipitation": True, "avg_temperature": ":.2f"},
            zoom=1,
            height=400,
            mapbox_style="carto-darkmatter"
        )
        fig_map.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
        st.plotly_chart(fig_map, use_container_width=True)

    with col_right:
        st.subheader("📈 Apparent Temperature & Rain Trends")
        
        # Trend line plot
        trend_df = df_filtered.groupby("weather_date").agg({
            "max_apparent_temperature": "mean",
            "total_precipitation": "mean"
        }).reset_index()
        
        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(
            x=trend_df["weather_date"],
            y=trend_df["max_apparent_temperature"],
            name="Max Feel Temp (°C)",
            line=dict(color="#64ffda", width=3)
        ))
        fig_trend.add_trace(go.Scatter(
            x=trend_df["weather_date"],
            y=trend_df["total_precipitation"],
            name="Avg Precipitation (mm)",
            line=dict(color="#00b0ff", width=3),
            yaxis="y2"
        ))
        
        fig_trend.update_layout(
            height=400,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            yaxis=dict(title="Temperature (°C)", titlefont=dict(color="#64ffda"), tickfont=dict(color="#64ffda")),
            yaxis2=dict(title="Precipitation (mm)", titlefont=dict(color="#00b0ff"), tickfont=dict(color="#00b0ff"), anchor="x", overlaying="y", side="right"),
            legend=dict(x=0.01, y=0.99, bgcolor='rgba(0,0,0,0.5)'),
            margin=dict(l=20, r=20, t=10, b=20)
        )
        st.plotly_chart(fig_trend, use_container_width=True)

    # =========================================================================
    # 🎯 ROW 3: DETAILED TABLE WITH ACTIVE TRIGGERS
    # =========================================================================
    st.subheader("🎯 Active Marketing Campaign Triggers Ledger")
    st.write("Green cells indicate weather trigger criteria met. Highlighted ads are active in those markets.")
    
    # Columns to show in table
    grid_cols = [
        "weather_date", "location_name", "avg_temperature", "total_precipitation",
        "trigger_extreme_heat_ads", "trigger_umbrella_ads", 
        "trigger_heat_stress_alerts", "trigger_layering_apparel_ads"
    ]
    
    table_df = df_filtered[grid_cols].copy()
    # Format date display
    table_df["weather_date"] = table_df["weather_date"].dt.strftime('%Y-%m-%d')
    
    # Pandas styling map for true/false trigger grids
    def highlight_triggers(val):
        if val is True:
            return 'background-color: rgba(100, 255, 218, 0.2); color: #64ffda; font-weight: bold;'
        elif val is False:
            return 'background-color: rgba(255, 255, 255, 0.02); color: #8892b0;'
        return ''
        
    styled_table = table_df.style.map(
        highlight_triggers, 
        subset=[
            "trigger_extreme_heat_ads", 
            "trigger_umbrella_ads", 
            "trigger_heat_stress_alerts", 
            "trigger_layering_apparel_ads"
        ]
    )
    
    st.dataframe(styled_table, use_container_width=True, height=350)

else:
    st.info("No records found matching filters.")

# Footer
st.markdown("""
<div class="footer">
    Weather-Triggered Marketing Analytics ETL • Built with Streamlit, Plotly & Google BigQuery Sandbox
</div>
""", unsafe_allowed_html=True)
