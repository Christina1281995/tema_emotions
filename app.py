# Imports
import os
import json
import re
import pandas as pd
import psycopg2
import streamlit as st
import logging

# Set up logging
# logging.basicConfig(level=logging.DEBUG)


# Constants

CREATE_TABLE_QUERY = '''CREATE TABLE IF NOT EXISTS public.results
(
    id SERIAL PRIMARY KEY,
    author text COLLATE pg_catalog."default",
    data_id integer,
    message_id BIGINT, 
    text text COLLATE pg_catalog."default",
    source text COLLATE pg_catalog."default",
    emotion text COLLATE pg_catalog."default",
    irrelevance boolean
);'''

EMOTION_OPTIONS = [('Anger', 'Anger'), ('Sadness', 'Sadness'), ('Happiness', 'Happiness'), ('Fear', 'Fear'), ('None', 'None')]


# Functions

def connect_to_database():
    """Connect to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host=st.secrets["db_host"],
            database=st.secrets["db_database"],
            user=st.secrets["db_username"],
            password=st.secrets["db_password"],
            port="5432"
        )
        return conn
    except psycopg2.Error as e:
        logging.debug("Error connecting to the database:", e)
        return None


@st.cache_data
def load_data(upload_obj):
    """Load data from uploaded CSV."""
    if upload_obj is None:
        return None
    try:
        df = pd.read_csv(upload_obj)
    except (ValueError, RuntimeError, TypeError, NameError):
        logging.debug("Unable to process your request.")
    return df


def save_results(data):
    """Save results to the database."""

    conn = connect_to_database()                    # Connect to db
    if not conn:
        return

    cursor = conn.cursor()                          # Create cursor to execute queries
    cursor.execute(CREATE_TABLE_QUERY)              # Create a new table if it doesn't exist

    for row in data.to_dict(orient='records'):      # Insert the data into the table
        insert_query = "INSERT INTO results (id, author, data_id, message_id, text, source, emotion, irrelevance) VALUES (DEFAULT, %s, %s, %s, %s, %s, %s, %s);"
        values = (st.session_state.user_id, row['data_id'], row['message_id'], row['text'], row['source'], row['emotion'], row['irrelevance'])
        cursor.execute(insert_query, values)

    st.session_state["data_id"] += 1                # Increment the question number for the next row
    conn.commit()                                   # Commit the changes and close the connection
    conn.close()


def get_user_data(user_id):
    """Retrieve user data from the database."""

    conn = connect_to_database()                # Connect to the PostgreSQL database
    if not conn:
        return None

    cursor = conn.cursor()                      # Create a cursor to execute queries
    query = "SELECT * FROM results WHERE author = %s ORDER BY data_id DESC LIMIT 1;"   # Query the database to get the user's data
    values = (user_id,)
    cursor.execute(query, values)
    result = cursor.fetchone()
    conn.close()                                # Close the connection

    return result


def extract_emotion_labels(emotion_data):
    return [emotion for emotion, label in emotion_data]


# App

# Load config file
with open('config.json') as f:
    config = json.load(f)

st.title('Emotion Labeling for TEMA')

# Initialize session state
if "start" not in st.session_state:
    st.session_state["start"] = False
# if "expander" not in st.session_state:
#     st.session_state["expander"] = True
if "irrelevance" not in st.session_state:
    st.session_state.irrelevance = False
if "emotion" not in st.session_state:
    st.session_state.emotion = "None"

user_ids = [i["name"] for i in config["users"]]

# Login
if not st.session_state["start"]:

    user_name = st.text_input('Please enter your username')             # Prompt for user name
    if user_name:
        st.write('Username:', user_name)       
        user_data = get_user_data(user_name)                            # Get database data on user
        data_id = user_data[2] + 1 if user_data else 0                  # Set data_id to last labeled data item if user already exists in db, else 0

        st.session_state.update({                                       # Add data into session state
            "start": True,
            "data_id": data_id,
            "user_id": user_name
        })        
        st.button("Start Labeling")

    else:
        st.write('Username not found')

# If session_state["start"] == True
else:
    # Get pre-loaded data that is assigned to the username
    if config["predefined"]:
        path = [j["data_path"] for j in config["users"] if j["name"] == st.session_state.user_id][-1]
        df = pd.read_csv(path)

    else:
        with st.expander("Upload data", expanded=st.session_state.expander):
            # load data 
            uploaded_data = st.file_uploader("Csv file", type = ['.csv'])
            df = load_data(uploaded_data)
            st.info("Upload data")
            st.session_state.expander = False

    # If there is data
    if df is not None:
        
        # Show current progress
        percentage_progress = round((int(st.session_state.data_id) / len(df)) * 100)
        if percentage_progress < 100:
            st.progress(percentage_progress)
        else:
            st.progress(100)

        # If we haven't reached the end of the labeling task yet
        if st.session_state.data_id < len(df):
            
            # Set labeling parameters
            # These are the parameters that will be shown upon submission (i.e. for the next round)
            message_id = df['message_id'][st.session_state.data_id]
            text = df["text"][st.session_state.data_id]
            source = df['source'][st.session_state.data_id]
            photo_url = str(df['photo_url'][st.session_state.data_id])
            links_list = photo_url.split(',')

            # The text that is actually shown to the user
            st.markdown(f"**{source}:**")
            st.markdown(f"<br> {text} <br> <br> ", unsafe_allow_html=True)
            if photo_url != 'nan':
                if len(links_list) == 1:
                    st.image(links_list[0])
                else: 
                    for i in range(len(links_list)):
                        st.image(links_list[i])

            def reset():
                # Reset the form elements in session state
                st.session_state.irrelevance = False
                st.session_state.emotion = "None"
        
            
            form_key = "my_form"
            with st.form(key=form_key):
                
                # set irrelevant
                irrelevance = st.checkbox(
                    'This tweet is NOT disaster related (tweet will be excluded)',
                    # value=False
                    value=st.session_state.irrelevance
                )

                st.markdown(f"  ")
                
                # chose emotions
                options = EMOTION_OPTIONS
                emotion = st.radio(
                    'Chose the dominant emotion:', 
                    options, 
                    # index=4, 
                    index=options.index((st.session_state.emotion, st.session_state.emotion)), 
                    # index = st.session_state.emotion,
                    format_func=lambda x: x[1])

                st.markdown(f"  ")
                st.markdown(f"  ")


                if st.form_submit_button("Submit", on_click=reset): 
                    emotion_to_add = emotion[0]
                    data = [[st.session_state.data_id, message_id, text, source, emotion_to_add, irrelevance]]
                    save_results(pd.DataFrame(data, columns=["data_id", "message_id", "text", "source", "emotion", "irrelevance"]))
                
                    
                    # Rerun the app to reset the form elements
                    st.experimental_rerun()

            # st.write("---")

        else:
            st.markdown("End of data.")