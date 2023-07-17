# Imports
import streamlit as st
import os
import pandas as pd
import json
import re
import psycopg2

@st.cache_data
def load_data(upload_obj):
    if upload_obj is None:
        return None
    try:
        df = pd.read_csv(upload_obj)
    except (ValueError, RuntimeError, TypeError, NameError):
        print("Unable to process your request.")
    return df

# Save labelled data to database table

def save_results(data):
    # Connect to the PostgreSQL database
    try:
        conn = psycopg2.connect(
            host=st.secrets["db_host"],
            database=st.secrets["db_database"],
            user=st.secrets["db_username"],
            password=st.secrets["db_password"],
            port="5432"  
        )
    except psycopg2.Error as e:
        print("Error connecting to the database:", e)
        return

    # Create a cursor to execute queries
    cursor = conn.cursor()

    # Create a new table if it doesn't exist
    create_table_query = '''CREATE TABLE IF NOT EXISTS results (
            id serial NOT NULL,
            author text,
            tweet_id integer,
            emotion text,
            sentence text,
            aspect_term text,
            sentiment text,
            PRIMARY KEY (id)
        );'''
    cursor.execute(create_table_query)

    # Insert the data into the table
    for row in data.to_dict(orient='records'):
        insert_query = f"INSERT INTO results (id, author, tweet_id, emotion, sentence, aspect_term, sentiment) VALUES (DEFAULT, '{st.session_state.user_id}', {row['q_num']}, '{row['emotions']}', '{row['sentence']}', '{row['aspect_term']}', '{row['sentiment']}');"
        cursor.execute(insert_query)
        
        # Increment Number
        st.session_state["question_number"] += 1  # Increment the question number for the next row

    # Commit the changes and close the connection
    conn.commit()
    conn.close()


# Query user data at start of session to check if some progress is already made
def get_user_data(user_id):
    # Connect to the PostgreSQL database
    try:
        conn = psycopg2.connect(
            host=st.secrets["db_host"],
            database=st.secrets["db_database"],
            user=st.secrets["db_username"],
            password=st.secrets["db_password"],
            port="5432" 
        )
    except psycopg2.Error as e:
        print("Error connecting to the database:", e)
        return None

    # Create a cursor to execute queries
    cursor = conn.cursor()

    # Query the database to get the user's data
    query = f"SELECT * FROM results WHERE author = '{user_id}' ORDER BY tweet_id DESC LIMIT 1;"
    cursor.execute(query)
    result = cursor.fetchone()

    # Close the connection
    conn.close()

    return result

# helper functions:
def increment_index():
    st.session_state["question_number"] += 1

def decrement_index():
    st.session_state["question_number"] -= 1

def extract_emotion_labels(emotion_data):
    return [emotion for emotion, label in emotion_data]


# Load config file
with open('config.json') as f:
    config = json.load(f)

# Set title
st.title('Geo-Social Analytics: Aspect Based Emotion Labeling')

# Set initial state
if "start" not in st.session_state:
    st.session_state["start"] = False

if "expander" not in st.session_state:
    st.session_state["expander"] = True

user_ids = [i["name"] for i in config["users"]]
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
            question_number = user_data[2] + 1  # Assuming the 'tweet_id' column is the third column in the table
        
        # If user hasn't done any labelling yet, set question number to 0
        else:
            # User is new, initialize question number to 0
            question_number = 0


        st.session_state["start"] = True
        # defining our Session State
        st.session_state["q_num"] = []
        st.session_state["emotions"] = []
        st.session_state.user_id = str(user_name)
        st.session_state.question_number = question_number
        st.button("Start Labeling")

    else:
        st.write('Username not found')

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


    if df is not None:

        st.progress(st.session_state.question_number/df.shape[0])

        if st.session_state.question_number < df.shape[0]:
            # Sentence
            sentence = df["Sentence"][st.session_state.question_number]
            aspect_term = df["Aspect Terms"][st.session_state.question_number]
            sentiment = df["Sentiment"][st.session_state.question_number]

            # Highlight aspect term in the sentence
            sentence = re.sub(
                r"\b" + re.escape(aspect_term) + r"\b",  # exact match of the aspect term
                lambda match: f"<span style='color:red'>{match.group(0)}</span>",  # wrap in HTML span tag with red color
                sentence,
                flags=re.IGNORECASE
            )

            st.markdown(f"**Sentence:** {sentence}", unsafe_allow_html=True)
            st.markdown(f"**Aspect Term:** {aspect_term}")
            st.markdown(f"**Sentiment:** {sentiment}")

            form_key = "my_form"
            with st.form(key=form_key):
                options = [('Anger', 'Anger'), ('Sadness', 'Sadness'), ('Happiness', 'Happiness'), ('Fear', 'Fear'), ('None', 'None')]
                emotion = st.radio(
                    'Assign an emotion to the aspect phrase', 
                    options, 
                    index=4, 
                    format_func=lambda x: x[1])

                if st.form_submit_button("Submit"):  #, on_click=increment_index):
                    print(emotion[0])
                    emotion_to_add = emotion[0]
                    # data = {"q_num": st.session_state.question_number, "emotions": emotion_to_add}
                    data = [[st.session_state.question_number, emotion_to_add, sentence, aspect_term, sentiment]]
                    save_results(pd.DataFrame(data, columns=["q_num", "emotions", "sentence", "aspect_term", "sentiment"]))
                    # increment_index()  # Increment the question number for the next sentence

                # if st.form_submit_button("Back"):
                #         decrement_index()  # Decrement the question number for the previous sentence
                #         increment_index()  # Increment the question number to display the previous sentence again

            st.write("---")
            # st.button("Next", on_click=increment_index)

        else:
            st.markdown("End of data.")
