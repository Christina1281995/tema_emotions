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
if not st.session_state["start"]:                                       # If session_state["start"] == False

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

else:                                                                  # If session_state["start"] == True
    # Load Data
    path = [j["data_path"] for j in config["users"] if j["name"] == st.session_state.user_id][-1]
    df = pd.read_csv(path) if config["predefined"] else load_data(st.file_uploader("Csv file", type=['.csv']))

    if df is not None:                                                                  # If there is data
        st.progress(round((int(st.session_state.data_id) / len(df)) * 100))             # Show progress bar

        if st.session_state.data_id < len(df):                                          # If we haven't reached the end of the labeling task yet
            message_id, text, source, photo_url = df.loc[st.session_state.data_id, ['message_id', 'text', 'source', 'photo_url']]       # Set labeling parameters
            st.markdown(f"**{source}:** <br> <br> {text} <br> <br> <br> ", unsafe_allow_html=True)             # The text that is actually shown to the user
            for link in str(photo_url).split(','):                                           # Show any images
                if link != "nan":
                    st.image(link)

            def reset():                                                                # Reset session elements for form
                st.session_state.update({
                    "irrelevance": False,
                    "emotion": "None"
                })
        
            with st.form(key="my_form"):                            # The actual form                          
                irrelevance = st.checkbox('This tweet is NOT disaster related (tweet will be excluded)', value=st.session_state.irrelevance)
                
                st.markdown(f"  ")
                
                emotion = st.radio('Chose the dominant emotion:', EMOTION_OPTIONS, index=EMOTION_OPTIONS.index((st.session_state.emotion, st.session_state.emotion)), format_func=lambda x: x[1])
                # chose emotions
                # options = EMOTION_OPTIONS
                # emotion = st.radio(
                #     'Chose the dominant emotion:', 
                #     options, 
                #     # index=4, 
                #     index=options.index((st.session_state.emotion, st.session_state.emotion)), 
                #     # index = st.session_state.emotion,
                #     format_func=lambda x: x[1])
                
                st.markdown(f"  ")
                st.markdown(f"  ")
                
                if st.form_submit_button("Submit", on_click=reset):
                    data = [[st.session_state.data_id, message_id, text, source, emotion, irrelevance]]
                    save_results(pd.DataFrame(data, columns=["data_id", "message_id", "text", "source", "emotion", "irrelevance"]))
                    st.experimental_rerun()
            # st.write("---")

        else:
            st.markdown("End of data.")