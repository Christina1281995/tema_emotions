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
import time
import pytz

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans&display=swap');

        .sidebar .markdown-text-container {
            word-wrap: break-word;
            white-space: pre-line;
        }
            
        .sidebar .block-container {
            width: 33%;
        }
    </style>
""", unsafe_allow_html=True)



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


def get_user_data_all(user_id):
    """Retrieve user data from the database."""

    conn = connect_to_database()                # Connect to the PostgreSQL database
    if not conn:
        return None

    cursor = conn.cursor()                      # Create a cursor to execute queries
    query = "SELECT * FROM results WHERE author = %s ORDER BY data_id DESC;"   # Query the database to get the user's data
    values = (user_id,)
    cursor.execute(query, values)
    result = cursor.fetchall()
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
    query = "SELECT * FROM discussion ORDER BY date ASC;"   # Query the database to get the user's data
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

# Load Data
else:                                                                  # If session_state["start"] == True
    path = [j["data_path"] for j in config["users"] if j["name"] == st.session_state.user_id][-1]
    df = pd.read_csv(path) if config["predefined"] else load_data(st.file_uploader("Csv file", type=['.csv']))

    if df is not None:                                                                  # If there is data
        st.progress(round((int(st.session_state.data_id) / len(df)) * 100))             # Show progress bar

        if st.session_state.data_id < len(df):                                          # If we haven't reached the end of the labeling task yet
            message_id, text, source, photo_url = df.loc[st.session_state.data_id, ['message_id', 'text', 'source', 'photo_url']]       # Set labeling parameters
        
            # tab1, tab2, tab3, tab4  = st.tabs(["Annotation", "Your Annotated Tweets", "Guide", "Discussion Board"])
            tab1, tab3, tab4 = st.tabs(["Annotation", "Guide", "Discussion Board"])

            with tab1:              # annotations

                # Define the content to be displayed in the sidebar

                st.sidebar.header('Tweet')
                
                st.sidebar.markdown(f"""
                <span style="font-family: 'IBM Plex Sans', sans-serif; color: #CCD3DA; font-size: 14px">
                    Tweet Nr {str(st.session_state.data_id)} - {source}
                </span>
                <br><br>
                {text}
                """, unsafe_allow_html=True)
                
                for link in str(photo_url).split(','):
                    if link != "nan":
                        st.sidebar.image(link)


                # st.markdown(f"{text} <br> <br> <br> ", unsafe_allow_html=True)             # The text that is actually shown to the user

                # Display the content in the sidebar
                # st.sidebar.markdown(content, unsafe_allow_html=True)
                


                def reset():                                                                # Reset session elements for form
                    st.session_state.update({
                        "irrelevance": False,
                        "emotion": "None"
                    })


                with st.form(key="my_form"):                            # The actual form                          
                
                    st.write(f"**Select the Target of the Emotion in the Text Below**") 
                    output = StTextAnnotator(text)
                    # st.markdown("  ")
                    st.write("---")
                    st.markdown("  ")

                    st.write(f"**Chose the Most Dominant Emotion**") 
                    emotion = st.radio('Chose the most dominant emotion', EMOTION_OPTIONS, index=EMOTION_OPTIONS.index((st.session_state.emotion, st.session_state.emotion)), format_func=lambda x: x[1], label_visibility="hidden")
                    # st.markdown("  ")
                    st.write("---")
                    st.markdown("  ")
                    
                    st.write(f"**Mark Tweet as Non-Disaster-Related**") 
                    irrelevance = st.checkbox('This tweet is NOT disaster related (tweet will be excluded)', value=st.session_state.irrelevance)
                    # st.markdown("  ")
                    st.write("---")
                    st.markdown("  ")
                    
                    if st.form_submit_button("Submit", on_click=reset):
                        if output:
                            target = json.dumps(output)
                        else:
                            target = ''
                        data = [[st.session_state.data_id, message_id, text, source, emotion[0], target, irrelevance]]
                        save_results(pd.DataFrame(data, columns=["data_id", "message_id", "text", "source", "emotion", "target", "irrelevance"]))
                        st.experimental_rerun()

            # with tab2:
            #     st.write("Your Annotated Tweets")
                
            #     if st.button("Refresh Annotations"):
            #         st.experimental_rerun() 
                
            #     user_annotations = get_user_data_all(st.session_state.user_id)
            #     for annotation in user_annotations:
            #         st.markdown(f"**Text:** {annotation[4]}")  # Display the text of the annotation
            #         st.markdown(f"**Emotion:** {annotation[6]}")  # Display the emotion of the annotation
            #         st.markdown(f"**Target:** {annotation[7]}")  # Display the target of the annotation
                    
            #         with st.expander("Edit Annotation"):  # Expandable section for editing
            #             # Display the annotation form pre-filled with existing data
            #             emotion = st.radio('Choose the dominant emotion:', EMOTION_OPTIONS, index=EMOTION_OPTIONS.index((annotation[6], annotation[6])))
            #             target = StTextAnnotator(annotation[4])
            #             irrelevance = st.checkbox('This tweet is NOT disaster related (tweet will be excluded)', value=annotation[8], key=f"irrelevance_{annotation[0]}")
                        
            #             if st.button(f"Update Annotation {annotation[2]}"):  # Button to submit the updated annotation
            #                 # Update the database with the new annotation data
            #                 conn = connect_to_database()
            #                 cursor = conn.cursor()
            #                 update_query = "UPDATE results SET emotion = %s, target = %s, irrelevance = %s WHERE id = %s;"
            #                 values = (emotion, json.dumps(target), irrelevance, annotation[0])
            #                 cursor.execute(update_query, values)
            #                 conn.commit()
            #                 conn.close()
            #                 st.success("Annotation updated!")

            with tab3:              # guide
                st.write("**Aspect Terms**")
                st.write("It's the target of an emotion. It pinpoints the particular part or attribute of a subject that emotions or sentiments are directed towards. " + 
                         "In simpler terms, it's the 'what' or 'who' that the sentiment or emotion in the statement is about. For instance, " +
                         "in the sentence 'The camera on this phone is amazing,' the aspect term is 'camera' as it is the specific feature of the "+
                         "phone being praised. It could be a particular element, attribute, or component of a product, service, event, or any other subject under consideration.")
                st.write(" ")

                st.write("**Aspect Based Emotions**")
                st.write("It's the emotion associated with the aspect term. The aspect-based emotion refers to the emotions or sentiments associated with a "+
                         "particular aspect or feature. It involves identifying and understanding the emotions expressed in relation to that specific aspect.")
                st.write(" ")

                st.write("**Emotions Map**")
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

            with tab4:              # discussion board
                
                st.markdown(" ")
                posts = get_discussion_data()
                if posts:
                    for post in posts:
                        formatted_date = post[3].strftime("%b-%d-%Y %H:%M")         # Format the timestamp
                        st.markdown(f"**{post[1]}** ({formatted_date})")            # Display author and date
                        st.write(post[2])                                           # Display the post text
                        st.markdown("---")                                          # Add a separator line

                if st.button("Refresh Posts"):
                    posts = get_discussion_data()
                st.markdown("  ")  # Add space
                st.markdown("  ")  # Add a space
                # st.markdown("  ")  # Add a space
                
                with st.form(key="posts"):                                                   

                    post_text = st.text_area('Add a post:', 'Thoughts, comments, ideas, examples...')

                    cet = pytz.timezone('CET')
                    now = datetime.now(cet)
                    date = now.strftime("%b-%d-%Y %H:%M")
                        
                    if st.form_submit_button("Post"):
                        post = [[post_text, date]]
                        save_discussion(pd.DataFrame(post, columns=["text", "date"]))


        else:
            st.markdown("End of data.")
            