import streamlit as st
import pandas as pd
import pydeck as pdk
import requests
import io

api_key = st.secrets["FIRMS_API_KEY"]

st.set_page_config(page_title="Global Fire Hotspots", layout="wide")

def fetch_data(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            return df, None
        else:
            return None, f"API Error: Status code {response.status_code}"
    except Exception as e:
        return None, f"Error fetching data: {str(e)}"


st.title("Global Fire Hotspots Map")


data_url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{api_key}/VIIRS_SNPP_NRT/world/1/2025-02-24"


with st.spinner("Fetching fire data from NASA FIRMS..."):
    fire_data, error = fetch_data(data_url)


if error:
    st.error(error)
elif fire_data is None or fire_data.empty:
    st.error("No data found for the selected date range.")
    st.stop()
else:
    
    st.write("Columns in the data:", fire_data.columns)
    st.write("First few rows of the data:", fire_data.head())

    
    if 'bright_ti4' in fire_data.columns:
        fire_data = fire_data.rename(columns={'bright_ti4': 'brightness'})
    elif 'bright_ti5' in fire_data.columns:  
        fire_data = fire_data.rename(columns={'bright_ti5': 'brightness'})
    else:
        st.error("Brightness column not found in the data.")
        st.stop()  

    
    def classify_region(row):
        lat, lon = row['latitude'], row['longitude']
        if lat > 30 and -130 < lon < -110:
            return "Western North America"
        elif -40 < lat < 0 and 110 < lon < 160:
            return "Australia"
        elif -20 < lat < 0 and -70 < lon < -50:
            return "Amazon"
        elif -10 < lat < 10 and 95 < lon < 125:
            return "Indonesia"
        elif -15 < lat < 15 and 10 < lon < 40:
            return "Central Africa"
        else:
            return "Other"

    fire_data['region'] = fire_data.apply(classify_region, axis=1)

    
    st.subheader("Fire Hotspot Statistics")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Hotspots", f"{len(fire_data):,}")
    col2.metric("Average Brightness", f"{fire_data['brightness'].mean():.1f}K")
    col3.metric("Regions Affected", f"{fire_data['region'].nunique()}")

    
    selected_regions = st.multiselect(
        "Filter by Region",
        options=fire_data['region'].unique(),
        default=fire_data['region'].unique()
    )

    
    if selected_regions:
        display_data = fire_data[fire_data['region'].isin(selected_regions)]
    else:
        display_data = fire_data

    
    view_state = pdk.ViewState(
        latitude=0,
        longitude=0,
        zoom=1.5,
        pitch=50,
    )

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