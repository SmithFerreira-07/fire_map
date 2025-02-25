import streamlit as st
import pandas as pd
import pydeck as pdk
import requests
import io
from datetime import datetime

api_key = st.secrets["FIRMS_API_KEY"]

st.set_page_config(page_title="Global Fire Hotspots", layout="wide")

#Will use a sql for this maybe...
REGIONS = {
    "Western North America": {"lat_min": 30, "lat_max": 60, "lon_min": -130, "lon_max": -110},
    "Eastern North America": {"lat_min": 25, "lat_max": 50, "lon_min": -90, "lon_max": -60},
    "Central America": {"lat_min": 8, "lat_max": 25, "lon_min": -110, "lon_max": -60},
    "Amazon": {"lat_min": -20, "lat_max": 0, "lon_min": -80, "lon_max": -50},
    "Southern South America": {"lat_min": -55, "lat_max": -20, "lon_min": -80, "lon_max": -35},
    "Western Europe": {"lat_min": 35, "lat_max": 60, "lon_min": -10, "lon_max": 20},
    "Eastern Europe": {"lat_min": 35, "lat_max": 60, "lon_min": 20, "lon_max": 45},
    "Central Africa": {"lat_min": -15, "lat_max": 15, "lon_min": 10, "lon_max": 40},
    "Southern Africa": {"lat_min": -35, "lat_max": -15, "lon_min": 10, "lon_max": 40},
    "Northern Africa": {"lat_min": 15, "lat_max": 35, "lon_min": -10, "lon_max": 40},
    "Middle East": {"lat_min": 15, "lat_max": 40, "lon_min": 40, "lon_max": 65},
    "South Asia": {"lat_min": 5, "lat_max": 35, "lon_min": 65, "lon_max": 95},
    "Southeast Asia": {"lat_min": -10, "lat_max": 20, "lon_min": 95, "lon_max": 125},
    "Indonesia": {"lat_min": -10, "lat_max": 10, "lon_min": 95, "lon_max": 125},
    "East Asia": {"lat_min": 20, "lat_max": 50, "lon_min": 95, "lon_max": 145},
    "Australia": {"lat_min": -40, "lat_max": -10, "lon_min": 110, "lon_max": 155},
    "New Zealand": {"lat_min": -47, "lat_max": -34, "lon_min": 165, "lon_max": 178},
    "Arctic": {"lat_min": 60, "lat_max": 90, "lon_min": -180, "lon_max": 180},
    "Antarctica": {"lat_min": -90, "lat_max": -60, "lon_min": -180, "lon_max": 180},
}

#TODO needs to work with cache data, so it doesn't need to fetch everytime
def fetch_data(days):
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{api_key}/VIIRS_SNPP_NRT/world/{days}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            if df.empty:
                return None, "No data found for the selected date range."
            
            required_cols = ['latitude', 'longitude']
            if not all(col in df.columns for col in required_cols):
                return None, "API response doesn't contain required location data."
            
            df['brightness'] = df.get('bright_ti4', df.get('bright_ti5', 0))
            df['region'] = df.apply(classify_region, axis=1)
            return df, None
        else:
            return None, f"API Error: Status code {response.status_code}"
    except Exception as e:
        return None, f"Error fetching data: {str(e)}"

def classify_region(row):
    lat, lon = row['latitude'], row['longitude']
    
    for region_name, bounds in REGIONS.items():
        if (bounds["lat_min"] <= lat <= bounds["lat_max"] and 
            bounds["lon_min"] <= lon <= bounds["lon_max"]):
            return region_name
    
    return "Other"

def calculate_map_view(data):
    if data is None or len(data) == 0:
        return pdk.ViewState(latitude=0, longitude=0, zoom=1.5, pitch=50)
    center_lat = data['latitude'].mean()
    center_lon = data['longitude'].mean()
    lat_range = data['latitude'].max() - data['latitude'].min()
    lon_range = data['longitude'].max() - data['longitude'].min()
    spread = max(lat_range, lon_range)
    if spread > 50:
        zoom = 1.5  
    elif spread > 20:
        zoom = 2.5  
    elif spread > 10:
        zoom = 3.5  
    else:
        zoom = 4.5  
    
    return pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=zoom, pitch=50)


st.title("Global Fire Hotspots Map")


day_span = st.slider("Select number of days to display", 2, 10, 2)

with st.spinner(f"Fetching fire data for the past {day_span} day(s)..."):
    fire_data, error = fetch_data(day_span)

if error:
    st.error(error)
else:
    st.subheader("Fire Hotspot Statistics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Hotspots", f"{len(fire_data):,}")
    col2.metric("Average Brightness", f"{fire_data['brightness'].mean():.1f}K")
    region_counts = fire_data['region'].value_counts()
    top_region = region_counts.index[0] if not region_counts.empty else "None"
    top_region_pct = 100 * region_counts.iloc[0] / len(fire_data) if not region_counts.empty else 0
    col4.metric("Top Region", f"{top_region} ({top_region_pct:.1f}%)")

    selected_regions = st.multiselect(
        "Filter by Region",
        options=sorted(fire_data['region'].unique()),
        default=list(fire_data['region'].unique())
    )

    display_data = fire_data[fire_data['region'].isin(selected_regions)] if selected_regions else fire_data

    view_state = calculate_map_view(display_data)

    layers = [
        pdk.Layer(
            'HeatmapLayer',
            data=display_data,
            get_position=['longitude', 'latitude'],
            get_weight='brightness',
            radiusPixels=60,
        ),
        pdk.Layer(
            'ScatterplotLayer',
            data=display_data,
            get_position=['longitude', 'latitude'],
            get_color=[200, 30, 0, 160],
            get_radius=30000,
            pickable=True,
        ),
    ]

    tooltip = {
        "html": """
            <b>Region:</b> {region}<br/>
            <b>Brightness:</b> {brightness}K<br/>
            <b>Latitude:</b> {latitude}°<br/>
            <b>Longitude:</b> {longitude}°
        """,
        "style": {
            "backgroundColor": "black",
            "color": "white",
            "fontSize": "12px"
        }
    }

    st.pydeck_chart(pdk.Deck(
        map_style='mapbox://styles/mapbox/dark-v10',
        initial_view_state=view_state,
        layers=layers,
        tooltip=tooltip
    ))


    if st.checkbox("Show raw data"):
        st.dataframe(display_data)