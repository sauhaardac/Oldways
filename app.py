import json
import os

import geocoder
import pandas as pd
import plotly.express as px
from plotly.colors import label_rgb as rgb
import streamlit as st
import string
import itertools

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

    try:
        json.dump(seen, open('loaction_dump.json', 'w'))
    except PermissionError:
        pass

    locations['lat'] = lat
    locations['lng'] = lng
    locations['Location'] = location_names
    locations['# of Classes'] = locations.groupby(['lat', 'lng'])['lat'].transform('count')
    fig = px.scatter_geo(locations, lat="lat", lon='lng', size='# of Classes',
                         projection='albers usa',
                         hover_data={'lat': False, 'lng': False, '# of Classes': True, 'Location': True},
                         title='Class Locations', size_max=25)

    # qualitative data
    # automatically gets rid of empty answers 
    obstacle = [x for x in df["Biggest Obstacle To Healthy Eating"] if str(x) != 'nan']
    surprise = [x for x in df['"African Heritage Foods" Defined After Taking This Class/What surprised you most about the classes, recipes or African heritage foods? '] if str(x) != 'nan']
    recipes = [x for x in df["Most useful thing you learned in this program/What recipes were most interesting to you?"] if str(x) != 'nan']
    change = [x for x in df["Change Anything?"] if str(x) != 'nan']
    at_home = [x for x in df["Cook any recipes at home?/If didn't why?"] if str(x) != 'nan']
    change_eat = [x for x in df["Changed the way you eat?"] if str(x) != 'nan']
    comments = [x for x in df["Other Comments:"] if str(x) != 'nan']

    # fig.show()
    '## Analysis'
    with st.beta_expander('General Statistics'):
        st.success(f'There have been **{len(locations)}** classes taught with these filter options.')
        st.success(f'The classes were taught in **{len(set(location_names))}** different cities.')
        st.plotly_chart(fig, use_container_width=True)
        st.success(f'These classes reached **{len(df)}** students.')

        heritage_counts = df["History & Heritage Positive Motivators?"].str.lower().value_counts()
        yes = heritage_counts.get('yes', 1)
        no = heritage_counts.get('no', 0)
        st.success(f'**{100 * yes / (yes + no):.2f}%** of the '
                   f'{(yes + no)} students surveyed, said heritage/history '
                   f'are positive motivators for health.')
    with st.beta_expander('Improvements'):
        data_view = st.radio('How would you like to view the data?', ('% of People', '# of People'))

        topics = ['Cooking Frequency', 'Herbs and Spices', 'Greens', 'Whole Grains', 'Beans', 'Tubers', 'Vegetables',
                  'Fruits',
                  'Vegetarian-Based Meals', 'Exercise']
        percentages = []
        for i in range(len(topics)):
            # Create header names
            pre_string = "Pre"
            pre_name = "Pre - Num"
            post_name = "Post Num"

            if i != 0:  # artifact of how spreadsheet is formatted
                pre_name += ("." + str(i))
                post_name += ("." + str(i))
                pre_string += ("." + str(i))

            pre_post = df[[pre_name, post_name, pre_string]]
            pre_post["Difference"] = pre_post[post_name] - pre_post[pre_name]
            pre_post.dropna(inplace=True)  # drops the blank lines (they didn't answer)

            total_num = len(pre_post)
            increase_num = len(pre_post[pre_post['Difference'] > 0])
            same_num = len(pre_post[pre_post['Difference'] == 0])

            if '#' == data_view[0]:
                percent_increase = increase_num
                percent_same = same_num
                percentages.append([percent_increase, 'Increased', topics[i]])
                percentages.append([percent_same, 'No Change', topics[i]])
                percentages.append([total_num - percent_increase - percent_same, 'Decreased', topics[i]])
            else:
                percent_increase = round(100 * increase_num / total_num, 2)
                percent_same = round(100 * same_num / total_num, 2)
                percentages.append([percent_increase, 'Increased', topics[i]])
                percentages.append([percent_same, 'No Change', topics[i]])
                percentages.append([100 - percent_increase - percent_same, 'Decreased', topics[i]])

        percentage_df = pd.DataFrame(percentages, columns=[f'{data_view[0]} of People', 'Change', 'Category'])
        st.plotly_chart(px.bar(percentage_df, x='Category', y=f'{data_view[0]} of People', color='Change',
                               color_discrete_map={'Increased': rgb((166, 216, 84)),
                                                   'No Change': rgb((255, 217, 47)),
                                                   'Decreased': rgb((252, 141, 98))}))

    with st.beta_expander("Qualitative Data"):
        
        # goes through each set of responses and removes key words like "none" or "no reponse"
        modifier = 0
        for i in range(0, len(obstacle)):
            if obstacle[i - modifier].lower() == 'no response' or obstacle[i - modifier].lower() == 'not sure' or obstacle[i - modifier].lower() == 'nothing' or obstacle[i - modifier].lower() == 'none':
                obstacle.pop(i - modifier)
                modifier += 1

        modifier = 0
        for i in range(0, len(change)):
            if change[i - modifier].lower() == 'none' or change[i - modifier].lower() == 'no' or change[i - modifier].lower() == 'nothing' or change[i - modifier].lower() == "no response":
                change.pop(i - modifier)
                modifier += 1

        modifier = 0
        for i in range(0, len(at_home)):
            if type(at_home[i - modifier]) == str:
                if at_home[i - modifier].lower() == 'no' or at_home[i - modifier].lower() == 'not yet' or at_home[i - modifier].lower() == 'no response':
                    at_home.pop(i - modifier)
                    modifier += 1

        modifier = 0
        for i in range(0, len(comments)):
            if type(comments[i - modifier]) == str:
                if comments[i - modifier].lower() == 'none' or comments[i - modifier].lower() == 'no' or comments[i - modifier].lower() == 'nothing':
                    comments.pop(i - modifier)
                    modifier += 1
        
        # common words banned from being used in relevancy analysis for recipes question 
        banned_words = ["how", "food", "to", "i", "i", "and", "of", "eat", "that", "a", "with", "use", "in", "can", "eating", "you", "more", "the", "not", "is", "all", "be", "about", "are", "cook", "cooking"
                        "foods", "cooking", "using", "without", "as", "foods", "good", "have", "it", "my", "for", "learned", "meals", "prepare", "recipes", "them", "ways", "make", "try", "way", "what",
                        "your"]

        # goes through each response and add words to giant list
        word_breakdown = []
        for j in range(0, len(recipes)):
            word = recipes[j].translate(str.maketrans('', '', string.punctuation)) # gets rid of punctuation
            words = word.split() # splits into individual words
            for k in range(0, len(words)):
                if words[k].lower() not in banned_words: # makes sure it's not a banned word
                    word_breakdown.append(words[k].lower())

        # goes through previous list and correlates words with how often they appear
        word_counts = {}
        for l in range(0, len(word_breakdown)):
            if word_breakdown[l] not in word_counts.keys():
                word_counts[word_breakdown[l]] = word_breakdown.count(word_breakdown[l])
        
        # sorts words from highest to lowest frequency
        word_counts = dict(sorted(word_counts.items(), key=lambda item: item[1], reverse=True))
        out = dict(itertools.islice(word_counts.items(), 15))

        # sends data for bar chart
        chart_data = pd.DataFrame(
            out.values(),
            out.keys()
        )

        # displays graphs and headers and responses
        st.header("Most useful thing you learned in this program/What recipes were most interesting to you?")
        st.text("Breakdown of top 15 key words:")
        st.bar_chart(chart_data)
        st.text("All responses:")
        st.dataframe(recipes)
        st.header('Biggest Obstacle to Healthy Eating')
        st.text("Responses:")
        st.dataframe(obstacle)
        st.header('"African Heritage Foods" Defined After Taking This Class/What surprised you most about the classes, recipes or African heritage foods? ')
        st.text("Responses:")
        st.dataframe(surprise)
        st.header('Change Anything?')
        st.text("Responses:")
        st.dataframe(change)
        st.header("Cook any recipes at home?/If didn't why?")
        st.text("Responses:")
        st.dataframe(at_home)
        st.header("Changed the way you eat?")
        st.text("Responses:")
        st.dataframe(change_eat)
        st.header("Other Comments:")
        st.text("Responses:")
        st.dataframe(comments)

    if st.checkbox('Show Raw Data'):
        df
