# Imports
import os
import json
import re
import pandas as pd
import psycopg2
import streamlit as st
import logging
from st_text_annotator import StTextAnnotator # target annotation
import json
from datetime import datetime


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
    target text COLLATE pg_catalog."default",
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
        insert_query = "INSERT INTO results (id, author, data_id, message_id, text, source, emotion, target, irrelevance) VALUES (DEFAULT, %s, %s, %s, %s, %s, %s, %s, %s);"
        values = (st.session_state.user_id, row['data_id'], row['message_id'], row['text'], row['source'], row['emotion'], row['target'], row['irrelevance'])
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


def save_discussion(data):
    """Save results to the database."""

    conn = connect_to_database()                    # Connect to db
    if not conn:
        return

    cursor = conn.cursor()                          # Create cursor to execute queries

    for row in data.to_dict(orient='records'):      # Insert the data into the table
        insert_query = "INSERT INTO discussion (id, author, text, date) VALUES (DEFAULT, %s, %s, %s);"
        values = (st.session_state.user_id, row['text'], row['date'])
        cursor.execute(insert_query, values)

    conn.commit()                                   # Commit the changes and close the connection
    conn.close()


def get_discussion_data():
    """Retrieve user data from the database."""

    conn = connect_to_database()                # Connect to the PostgreSQL database
    if not conn:
        return None

    cursor = conn.cursor()                      # Create a cursor to execute queries
    query = "SELECT * FROM discussion ORDER BY date DESC;"   # Query the database to get the user's data
    cursor.execute(query)
    result = cursor.fetchall()
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
        
            tab1, tab2, tab3  = st.tabs(["Annotation", "Guide", "Discussion Board"])

            with tab1:              # annotations
                
                st.markdown(f"**{source}:** <br> <br> {text} <br> <br> <br> ", unsafe_allow_html=True)             # The text that is actually shown to the user
                for link in str(photo_url).split(','):                                           # Show any images
                    if link != "nan":
                        st.image(link)

                def reset():                                                                # Reset session elements for form
                    st.session_state.update({
                        "irrelevance": False,
                        "emotion": "None"
                    })

                output = StTextAnnotator(text)

                if output:
                    target = json.dumps(output)
                else:
                    target = ''

                # st.write(output)
                st.write(target) 


                with st.form(key="my_form"):                            # The actual form                          
                    
                    # ----- expriment with target function ----

                    # ---- experiment over -----                

                    st.markdown(f"  ")
                    st.markdown(f"  ")        

                    emotion = st.radio('Chose the dominant emotion:', EMOTION_OPTIONS, index=EMOTION_OPTIONS.index((st.session_state.emotion, st.session_state.emotion)), format_func=lambda x: x[1])
                    
                    st.markdown(f"  ")
                    
                    irrelevance = st.checkbox('This tweet is NOT disaster related (tweet will be excluded)', value=st.session_state.irrelevance)
                    
                    st.markdown(f"  ")
                    st.markdown(f"  ")
                    
                    if st.form_submit_button("Submit", on_click=reset):
                        data = [[st.session_state.data_id, message_id, text, source, emotion[0], target, irrelevance]]
                        save_results(pd.DataFrame(data, columns=["data_id", "message_id", "text", "source", "emotion", "target", "irrelevance"]))
                        st.experimental_rerun()
           
            with tab2:              # guide
                st.subheader("WHAT IS AN ASPECT TERM")

                st.write("It's the target of an emotion. It pinpoints the particular part or attribute of a subject that emotions or sentiments are directed towards. " + 
                         "In simpler terms, it's the 'what' or 'who' that the sentiment or emotion in the statement is about. For instance, " +
                         "in the sentence 'The camera on this phone is amazing,' the aspect term is 'camera' as it is the specific feature of the "+
                         "phone being praised. It could be a particular element, attribute, or component of a product, service, event, or any other subject under consideration.")
                
                st.subheader("WHAT IS AN ASPECT BASED EMOTION")

                st.write("It's the emotion associated with the aspect term. The aspect-based emotion refers to the emotions or sentiments associated with a "+
                         "particular aspect or feature. It involves identifying and understanding the emotions expressed in relation to that specific aspect.")
                
                st.subheader("EMOTIONS MAP")

                st.image("images/emotions guide.png")

                with st.expander("Details on Happiness:"):
                    st.write("Happiness is a positive emotion characterized by feelings of joy, contentment, and satisfaction. "+
                             "Tweets expressing happiness may indicate a sense of pleasure, excitement, or delight. Examples of tweets "+
                             "expressing happiness could include positive experiences, achievements, celebrations, or expressions of gratitude.")
                    st.image("images/happy1.png")  
                    st.image("images/happy2.png")
                    st.image("images/happy3.png")      
                    st.image("images/happy4.png")

                with st.expander("Details on Anger:"):
                    st.write("Anger is a negative emotion associated with feelings of displeasure, irritation, or frustration. Tweets expressing "+
                             "anger may include instances of perceived injustice, provocation, or annoyance. Anger can be directed towards individuals, "+
                             "events, organizations, or societal issues. Examples of angry tweets might involve expressing outrage, criticism, or venting frustration.")
                    st.image("images/anger1.png")  
                    st.image("images/anger2.png")
                    st.image("images/anger3.png")      

                with st.expander("Details on Sadness:"):
                    st.write("Sadness is a negative emotion characterized by feelings of unhappiness, sorrow, or grief. Tweets expressing sadness may reflect "+
                             "emotions related to loss, disappointment, or melancholy. This category includes tweets that convey expressions of sadness, "+
                             "loneliness, heartbreak, or other forms of emotional distress. Examples of sad tweets could involve sharing personal setbacks, "+
                             "expressing empathy for others, or discussing emotional hardships.")
                    st.image("images/sad1.png")  
                    st.image("images/sad2.png")

                with st.expander("Details on Fear:"):
                    st.write("Fear is an emotion typically triggered by perceived threats, danger, or uncertainty. Tweets expressing fear may reflect feelings "+
                             "of anxiety, worry, or apprehension. This category can encompass concerns about personal safety, health, future events, or any "+
                             "other circumstances that evoke a sense of fear. Examples of fearful tweets might include expressing concern about a potential "+
                             "risk, expressing phobias, or discussing unsettling experiences.")

            with tab3:              # discussion board
                # st.subheader("ANNOTATOR DISCUSSION BOARD"
                
                st.markdown(" ")

                posts = get_discussion_data()
                if posts:
                    for post in posts:
                        st.markdown(f"**{post[1]}** ({post[3]})")  # Display author and date
                        st.write(post[2])  # Display the post text
                        st.markdown("  ")  # Add a separator line
                        st.markdown("---")  # Add a separator line
                        st.markdown("  ")  # Add a separator line

                # if st.button("Refresh Posts"):
                #     posts = get_discussion_data()
            
                with st.form(key="posts"):                            # The actual form                          
                    st.markdown("  ")  # Add a separator line

                    post_text = st.text_area('Add a post:', 'Thoughts, comments, ideas, examples...')

                    now = datetime.now()
                    date = now.strftime("%b-%d-%Y %H:%M")
                        
                    if st.form_submit_button("Post"):
                        post = [[post_text, date]]
                        save_discussion(pd.DataFrame(post, columns=["text", "date"]))
                        posts = get_discussion_data()

        else:
            st.markdown("End of data.")
            