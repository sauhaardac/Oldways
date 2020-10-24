import json

import geocoder
import pandas as pd
import streamlit as st
import plotly.express as px
import os

st.beta_set_page_config()
st.title('Oldways Data Analyzer')

'### Inputs'
excel_file = st.file_uploader(label='Excel File to Analyze', type=['xlsx'])
sheet_name = st.text_input(label='Sheet Name', value='Student Lifestyle Surveys')
header_row = st.number_input(label='Header Row', value=24) - 1


@st.cache
def load_sheet(excel_file, sheet_name, header_row):
    return pd.read_excel(excel_file, sheet_name, header=header_row)


if excel_file is not None:
    df = load_sheet(excel_file, sheet_name, header_row)

    '### Filters'

    # Filter Years
    min_year, max_year = int(df["Class End Date (year)"].min()), int(df["Class End Date (year)"].max())
    start_year, end_year = st.slider(label='Class Years', value=(min_year, max_year), min_value=min_year,
                                     max_value=max_year)
    df = df.loc[(start_year <= df['Class End Date (year)']) & (df['Class End Date (year)'] <= end_year)]

    # Filter Teachers
    teachers = st.multiselect(default=['All'], label='Teachers', options=['All'] + list(df['Teacher Name'].unique()))
    if 'All' not in teachers:
        df = df[df['Teacher Name'].isin(teachers)]

    locations = df[["Class Type", "Teacher Name", "Class End Date (year)", "Class Location Type", "City", "State"]]
    locations.drop_duplicates(inplace=True)

    seen = {} if not os.path.exists('loaction_dump.json') else json.load(open('loaction_dump.json', 'r'))
    lat = []
    lng = []
    location_names = []
    for city, state in zip(locations['City'], locations['State']):
        loc_str = f'{city}, {state}'
        if loc_str not in seen:
            geocode = geocoder.google(loc_str)
            seen[loc_str] = {'lat': geocode.latlng[0], 'lng': geocode.latlng[1]}
        lat.append(seen[loc_str]['lat'])
        lng.append(seen[loc_str]['lng'])
        location_names.append(loc_str)

    json.dump(seen, open('loaction_dump.json', 'w'))

    locations['lat'] = lat
    locations['lng'] = lng
    locations['Location'] = location_names
    locations['# of Classes'] = locations.groupby(['lat', 'lng'])['lat'].transform('count')
    fig = px.scatter_geo(locations, lat="lat", lon='lng', size='# of Classes',
                         projection='albers usa',
                         hover_data={'lat': False, 'lng': False, '# of Classes': True, 'Location': True},
                         title='Class Locations', size_max=25)
    # fig.show()
    '## Analysis'
    st.plotly_chart(fig, use_container_width=True)

    if st.checkbox('Show Raw Data'):
        df
