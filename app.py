# Imports
import os
import json
import re
import pandas as pd
import psycopg2
import streamlit as st
import logging

logging.basicConfig(level=logging.DEBUG)  # Set the logging level


# --------- Constants ---------

CREATE_TABLE_QUERY = '''CREATE TABLE IF NOT EXISTS results (
    id serial NOT NULL,
    author text,
    tweet_id integer,
    emotion text,
    sentence text,
    aspect_term text,
    sentiment text,
    PRIMARY KEY (id)
);'''

EMOTION_OPTIONS = [('Anger', 'Anger'), ('Sadness', 'Sadness'), ('Happiness', 'Happiness'), ('Fear', 'Fear'), ('None', 'None')]


# --------- Functions ---------

def connect_to_database():
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
    if upload_obj is None:
        return None
    try:
        df = pd.read_csv(upload_obj)
    except (ValueError, RuntimeError, TypeError, NameError):
        logging.debug("Unable to process your request.")
    return df


def save_results(data):
    # Connect to the PostgreSQL database
    conn = connect_to_database()
    if not conn:
        return

    # Create a cursor to execute queries
    cursor = conn.cursor()

    # Create a new table if it doesn't exist
    cursor.execute(CREATE_TABLE_QUERY)

    # Insert the data into the table
    for row in data.to_dict(orient='records'):
        insert_query = "INSERT INTO results (id, author, tweet_id, emotion, sentence, aspect_term, sentiment) VALUES (DEFAULT, %s, %s, %s, %s, %s, %s);"
        values = (st.session_state.user_id, row['q_num'], row['emotions'], row['sentence'], row['aspect_term'], row['sentiment'])
        cursor.execute(insert_query, values)

    # Increment Number
    st.session_state["question_number"] += 1  # Increment the question number for the next row

    # Commit the changes and close the connection
    conn.commit()
    conn.close()


def get_user_data(user_id):
    # Connect to the PostgreSQL database
    conn = connect_to_database()
    if not conn:
        return None

    # Create a cursor to execute queries
    cursor = conn.cursor()

    # Query the database to get the user's data
    query = "SELECT * FROM results WHERE author = %s ORDER BY tweet_id DESC LIMIT 1;"
    values = (user_id,)
    cursor.execute(query, values)
    result = cursor.fetchone()

    # Close the connection
    conn.close()

    return result


def extract_emotion_labels(emotion_data):
    return [emotion for emotion, label in emotion_data]


# --------- App ---------

# Load config file
with open('config.json') as f:
    config = json.load(f)

# Set title
st.title('Aspect-Based Emotion Labeling')

# Set initial state
if "start" not in st.session_state:
    st.session_state["start"] = False

if "expander" not in st.session_state:
    st.session_state["expander"] = True

user_ids = [i["name"] for i in config["users"]]

# For logging in
if st.session_state["start"] == False:

    # Prompt for user name
    user_name = st.text_input('Please enter your username')
    
    if user_name != '':
        
        st.write('Username:', user_name)
        
        # Get database data on user
        user_data = get_user_data(user_name)

        # If user already exists, return the current question number
        if user_data is not None:
            
            # If user is returning, retrieve their previous data for current question number
            question_number = user_data[2] # - 1  # Assuming the 'tweet_id' column is the third column in the table

        # If user hasn't done any labelling yet, set question number to 0
        else:
            # User is new, initialize question number to 0
            question_number = 0

        st.session_state["start"] = True
        # defining our Session State
        st.session_state["q_num"] = []
        st.session_state["emotions"] = []
        st.session_state.user_id = str(user_name)
        st.session_state["question_number"] = question_number
        
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
        percentage_progress = round((int(st.session_state.question_number) / len(df)) * 100)
        if percentage_progress < 100:
            st.progress(percentage_progress)
        else:
            st.progress(100)

        # If we haven't reached the end of the labeling task yet
        if st.session_state.question_number < len(df):
            
            # Set labeling parameters
            # These are the parameters that will be shown upon submission (i.e. for the next round)
            sentence = df["Sentence"][st.session_state.question_number]
            aspect_term = df["Aspect Terms"][st.session_state.question_number]
            sentiment = df["Sentiment"][st.session_state.question_number]

            # These are the parameters to submit when button hits submit (i.e. the parameters currently shown --> index -1)
            if st.session_state.question_number != 0:
                prev_sentence = df["Sentence"][st.session_state.question_number - 1]
                prev_aspect_term = df["Aspect Terms"][st.session_state.question_number - 1]
                prev_sentiment = df["Sentiment"][st.session_state.question_number - 1]
            # In the very first round (index = 0) use the current sentence
            else:
                prev_sentence = df["Sentence"][st.session_state.question_number]
                prev_aspect_term = df["Aspect Terms"][st.session_state.question_number]
                prev_sentiment = df["Sentiment"][st.session_state.question_number]

            # Highlight aspect term in the sentence           
            def highlight_aspect_term(sentence, aspect_term):
                aspect_term_pattern = re.escape(aspect_term)
                pattern = r"(?<![^\W_])" + aspect_term_pattern + r"(?![^\W_])"
                sentence_highlighted = re.sub(pattern, r"<span style='color:red'>\g<0></span>", sentence, flags=re.IGNORECASE)
                return sentence_highlighted

            sentence_highlight =  highlight_aspect_term(sentence, aspect_term)

            st.markdown(f"**Sentence:** {sentence_highlight}", unsafe_allow_html=True)
            st.markdown(f"**Aspect Term:** {aspect_term}")
            # st.markdown(f"**Sentiment:** {sentiment}")  # Leave out sentiment to not bias labeller 

            form_key = "my_form"
            with st.form(key=form_key):
                options = EMOTION_OPTIONS
                emotion = st.radio(
                    'Assign an emotion to the aspect phrase', 
                    options, 
                    index=4, 
                    format_func=lambda x: x[1])

                if st.form_submit_button("Submit"): 
                    emotion_to_add = emotion[0]
                    data = [[st.session_state.question_number, emotion_to_add, prev_sentence, prev_aspect_term, prev_sentiment]]
                    print(data)
                    save_results(pd.DataFrame(data, columns=["q_num", "emotions", "sentence", "aspect_term", "sentiment"]))
                    
            st.write("---")

        else:
            st.markdown("End of data.")
